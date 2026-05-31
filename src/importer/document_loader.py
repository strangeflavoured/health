"""Upload workouts, correlations, activity summaries, and routes to Redis as JSON.

The records DataFrame is loaded into RedisTimeSeries via
:mod:`~src.importer.pipeline`.  The remaining three DataFrames produced by
:func:`~src.importer.parser.parse_apple_health` plus the routes DataFrame
produced by :func:`~src.importer.parser.parse_apple_health_routes` are
*document* data — variable-shape records that don't fit a time-series
schema.  They are stored as RedisJSON documents whose key prefixes match
the indexes declared in :mod:`~src.redis_setup`:

============  ====================  =================================
Source        Redis key prefix      Index
============  ====================  =================================
workouts      ``workout:<uuid>``    ``idx:workouts``
correlations  ``correlation:<n>``   ``idx:correlations``
activities    ``activity:<date>``   ``idx:activities``
routes        ``route:<workoutId>`` ``idx:routes``
============  ====================  =================================

Shape contract
--------------
Every document carries a top-level ``metaKeys`` field (``list[str]``) — the
keys of its ``meta`` dict — so that the ``$.metaKeys[*]`` TagField paths in
:data:`~src.redis_setup._INDICES` resolve to real values.  Without this
materialisation step the indexes would silently match nothing.

Timestamps (``startDate``, ``endDate``, ``creationDate``, and the workout
``date`` event field) are written as **int64 Unix seconds**, matching the
RediSearch ``NumericField`` declarations and the TimeSeries timestamps used
elsewhere.

Failure handling
----------------
A document upload uses ``JSON.SET`` and is therefore either fully written
or not written at all — the granular row/end split that
:mod:`~src.importer.pipeline` does is meaningless here.  Failed documents
are reported as :class:`~.response.BatchFailure` with a synthetic
``batch_nr`` of ``-1`` so they survive the standard ``retry_failed``
plumbing while remaining distinguishable from time-series batches.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
import redis
from pandas.api.typing import NaTType
from redis.exceptions import RedisError

from .response import BatchFailure, UploadFailure

logger = logging.getLogger(__name__)

_PIPELINE_BATCH = 200  # documents per JSON.SET pipeline round-trip

_NUMERIC_ACTIVITY_FIELDS = (
    "activeEnergyBurned",
    "activeEnergyBurnedGoal",
    "appleExerciseTime",
    "appleExerciseTimeGoal",
    "appleStandHours",
    "appleStandHoursGoal",
    "appleMoveTime",
    "appleMoveTimeGoal",
)

# ---------------------------------------------------------------------------
# Timestamp coercion
# ---------------------------------------------------------------------------


_TS_FIELDS = ("startDate", "endDate", "creationDate")


def _to_unix_seconds(
    value: str | int | float | np.integer | pd.Timestamp | NaTType | None,
) -> int | None:
    """Coerce a single timestamp value to int64 Unix seconds (or None).

    Accepts:

    * ``None``, ``NaN``, ``NaT`` → ``None``
    * Plain ``int`` or numpy integer → returned as-is (already Unix seconds)
    * Anything else → parsed via :func:`pandas.to_datetime` with ``utc=True``;
      the result's ``.value`` (always nanoseconds since epoch) is divided
      by 10⁹ to produce whole seconds.

    The ``int`` pass-through matters because the records DataFrame's
    timestamp columns are already int64 Unix seconds by the time the
    document loaders run (see :func:`~src.importer.transform.transform`);
    re-parsing them would treat their values as nanoseconds and produce
    nonsense.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    # int-like → already Unix seconds; do not re-parse.
    if isinstance(value, (int,)) and not isinstance(value, bool):
        return int(value)
    # numpy integer types
    if hasattr(value, "dtype") and getattr(value.dtype, "kind", None) == "i":
        return int(value)
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    # ts.value is always nanoseconds since epoch on pandas Timestamp.
    return int(ts.value // 1_000_000_000)


def _coerce_timestamps(d: dict[str, Any], fields: tuple[str, ...] = _TS_FIELDS) -> None:
    """Convert ``fields`` of *d* in-place from string/datetime to Unix seconds."""
    for f in fields:
        if f in d and d[f] is not None:
            d[f] = _to_unix_seconds(d[f])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _attach_meta_keys(doc: dict[str, Any]) -> None:
    """Add a ``metaKeys`` list to *doc* mirroring the keys of ``doc['meta']``.

    The RediSearch indexes declared in :mod:`~src.redis_setup` use
    ``$.metaKeys[*]`` as their TagField path; without this materialisation
    the indexes would not match any documents.
    """
    meta = doc.get("meta")
    doc["metaKeys"] = list(meta.keys()) if isinstance(meta, dict) else []


def _row_to_dict(row: pd.Series) -> dict[str, Any]:
    """Convert a DataFrame row to a plain JSON-serialisable dict.

    Pandas ``NaT`` and ``NaN`` values are coerced to ``None`` so JSON
    serialisation does not emit ``"NaN"`` literals.
    """
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, float) and pd.isna(v) or v is pd.NaT:
            out[k] = None
        else:
            out[k] = v
    return out


def _execute_pipeline(
    pipe: redis.client.Pipeline,
    keys: list[str],
    prefix: str,
) -> list[UploadFailure]:
    """Flush *pipe* and turn any :class:`RedisError` responses into failures.

    A document upload is atomic at the ``JSON.SET`` level — either the
    document is written or it isn't.  Per-document failures are therefore
    reported as ``BatchFailure(batch_nr=-1)`` with the key embedded in the
    ``data_type`` field; the negative batch number marks them as
    document-class failures so :func:`~.importer._load`-style retries can
    handle them separately.
    """
    try:
        responses = pipe.execute(raise_on_error=False)
    except RedisError as exc:
        logger.exception("Pipeline execute failed for prefix %s", prefix)
        return [BatchFailure(data_type=prefix, batch_nr=-1, error=str(exc))]

    failures: list[UploadFailure] = []
    for key, resp in zip(keys, responses, strict=True):
        if isinstance(resp, Exception):
            failures.append(
                BatchFailure(
                    data_type=f"{prefix}:{key}",
                    batch_nr=-1,
                    error=str(resp),
                )
            )
    return failures


# ---------------------------------------------------------------------------
# Per-DataFrame loaders
# ---------------------------------------------------------------------------


def load_workouts(r: redis.Redis, df: pd.DataFrame) -> list[UploadFailure]:
    """Upload workouts as ``workout:<uuid>`` JSON documents.

    Each workout row becomes a single JSON document.  Nested
    ``events``/``statistics``/``activities``/``route`` lists from
    :func:`~src.importer.parser.parse_apple_health` are preserved verbatim
    and their own timestamps are coerced where present.

    Key derivation
    --------------
    Apple Health does not expose a workout-level ``uuid`` on every export,
    so the key is built from ``startDate`` (already an int64 by the time
    this function runs, or the raw timestamp string).  Same-millisecond
    duplicates are extremely unlikely in real data.

    Args:
        r: Connected Redis client.
        df: Workouts DataFrame from :func:`parse_apple_health`.

    Returns:
        List of :class:`~.response.UploadFailure` objects; empty on full
        success.

    """
    if df.empty:
        return []

    logger.info("Loading %d workouts as JSON documents.", len(df))
    failures: list[UploadFailure] = []
    pipe = r.pipeline()
    keys: list[str] = []

    for i, row in enumerate(df.itertuples(index=False), start=1):
        doc = _row_to_dict(pd.Series(row._asdict()))
        _coerce_timestamps(doc)
        # Coerce nested event/activity timestamps as well.
        for ev in doc.get("events") or []:
            _coerce_timestamps(ev, ("date",))
        for stat in doc.get("statistics") or []:
            _coerce_timestamps(stat)
        for activity in doc.get("activities") or []:
            _coerce_timestamps(activity)
            for ev in activity.get("events") or []:
                _coerce_timestamps(ev, ("date",))
            for stat in activity.get("statistics") or []:
                _coerce_timestamps(stat)
        if doc.get("route") is not None:
            _coerce_timestamps(doc["route"])

        _attach_meta_keys(doc)

        key = f"workout:{doc.get('startDate')}-{i}"
        pipe.json().set(key, "$", doc)
        keys.append(key)

        if i % _PIPELINE_BATCH == 0:
            failures.extend(_execute_pipeline(pipe, keys, "workout"))
            pipe = r.pipeline()
            keys = []

    if keys:
        failures.extend(_execute_pipeline(pipe, keys, "workout"))
    return failures


def load_correlations(r: redis.Redis, df: pd.DataFrame) -> list[UploadFailure]:
    """Upload correlations as ``correlation:<n>`` JSON documents.

    Each correlation bundles 2+ Record children (e.g. systolic + diastolic
    BP).  The nested records list is preserved verbatim and their
    timestamps are coerced.

    Args:
        r: Connected Redis client.
        df: Correlations DataFrame from :func:`parse_apple_health`.

    Returns:
        List of :class:`~.response.UploadFailure` objects; empty on full
        success.

    """
    if df.empty:
        return []

    logger.info("Loading %d correlations as JSON documents.", len(df))
    failures: list[UploadFailure] = []
    pipe = r.pipeline()
    keys: list[str] = []

    for i, row in enumerate(df.itertuples(index=False), start=1):
        doc = _row_to_dict(pd.Series(row._asdict()))
        _coerce_timestamps(doc)
        for rec in doc.get("records") or []:
            _coerce_timestamps(rec)
        _attach_meta_keys(doc)

        key = f"correlation:{doc.get('startDate')}-{i}"
        pipe.json().set(key, "$", doc)
        keys.append(key)

        if i % _PIPELINE_BATCH == 0:
            failures.extend(_execute_pipeline(pipe, keys, "correlation"))
            pipe = r.pipeline()
            keys = []

    if keys:
        failures.extend(_execute_pipeline(pipe, keys, "correlation"))
    return failures


def load_activities(r: redis.Redis, df: pd.DataFrame) -> list[UploadFailure]:
    """Upload activity summaries as ``activity:<date>`` JSON documents.

    Numeric attributes are coerced from string to ``float`` so the
    NumericField indexes resolve correctly.  ``dateComponents`` is parsed
    to int64 Unix seconds and stored as ``date``.

    Args:
        r: Connected Redis client.
        df: Activity-summary DataFrame from :func:`parse_apple_health`.

    Returns:
        List of :class:`~.response.UploadFailure` objects; empty on full
        success.

    """
    if df.empty:
        return []

    logger.info("Loading %d activity summaries as JSON documents.", len(df))

    failures: list[UploadFailure] = []
    pipe = r.pipeline()
    keys: list[str] = []

    for i, row in enumerate(df.itertuples(index=False), start=1):
        doc = _row_to_dict(pd.Series(row._asdict()))

        for f in _NUMERIC_ACTIVITY_FIELDS:
            if doc.get(f) is not None:
                try:
                    doc[f] = float(doc[f])
                except (TypeError, ValueError):
                    doc[f] = None

        date_str = doc.get("dateComponents")
        doc["date"] = _to_unix_seconds(date_str) if date_str else None

        key = f"activity:{date_str or i}"
        pipe.json().set(key, "$", doc)
        keys.append(key)

        if i % _PIPELINE_BATCH == 0:
            failures.extend(_execute_pipeline(pipe, keys, "activity"))
            pipe = r.pipeline()
            keys = []

    if keys:
        failures.extend(_execute_pipeline(pipe, keys, "activity"))
    return failures


def load_routes(r: redis.Redis, routes_df: pd.DataFrame) -> list[UploadFailure]:
    """Upload route GPX trackpoints as ``route:<gpx-filename>`` JSON documents.

    Each GPX file (one per workout) is collapsed into a single document
    whose ``points`` field is a list of trackpoint dicts.  This keeps the
    workout-route relationship intact while bounding the number of Redis
    keys to one per workout rather than one per GPS sample.

    Args:
        r: Connected Redis client.
        routes_df: Trackpoints DataFrame from
            :func:`~src.importer.parser.parse_apple_health_routes`.  One
            row per trackpoint; the ``file`` column groups them.

    Returns:
        List of :class:`~.response.UploadFailure` objects; empty on full
        success.

    """
    if routes_df.empty:
        return []

    logger.info(
        "Loading routes from %d trackpoints across %d files.",
        len(routes_df),
        routes_df["file"].nunique(),
    )

    # Materialise the time column as int64 Unix seconds before grouping so
    # the JSON output is uniform.  The divisor depends on pandas' internal
    # resolution (``s``/``ms``/``us``/``ns``), which has changed across
    # pandas versions — derive it from the dtype rather than hard-coding ns.
    if pd.api.types.is_datetime64_any_dtype(routes_df["time"]):
        time_col = routes_df["time"]
        # Pull the resolution out of the *original* dtype before any
        # tz operation; ``tz_localize(None)`` returns a numpy dtype that
        # has no ``.unit`` attribute on some pandas versions.
        unit_str = str(time_col.dtype)  # e.g. "datetime64[us, UTC]" or "datetime64[ns]"
        for u, d in (
            ("[s", 1),
            ("[ms", 1_000),
            ("[us", 1_000_000),
            ("[ns", 1_000_000_000),
        ):
            if u in unit_str:
                divisor = d
                break
        else:
            divisor = 1_000_000_000  # safe default
        if time_col.dt.tz is not None:
            time_col = time_col.dt.tz_convert("UTC").dt.tz_localize(None)
        times = (time_col.astype("int64") // divisor).to_numpy()
        routes_df = routes_df.assign(time=times)

    failures: list[UploadFailure] = []
    pipe = r.pipeline()
    keys: list[str] = []

    grouped = routes_df.groupby("file", sort=False)
    for i, (file_path, group) in enumerate(grouped, start=1):
        # Drop the redundant ``file`` column from each point.
        point_cols = [c for c in group.columns if c != "file"]
        points = group[point_cols].to_dict(orient="records")

        # JSON-clean NaN values from each point dict.
        clean_points = []
        for p in points:
            clean_points.append(
                {
                    k: (None if isinstance(v, float) and pd.isna(v) else v)
                    for k, v in p.items()
                }
            )

        doc = {
            "file": file_path,
            "workoutId": file_path.rsplit("/", 1)[-1].removesuffix(".gpx"),
            "numPoints": len(clean_points),
            "startDate": clean_points[0]["time"] if clean_points else None,
            "endDate": clean_points[-1]["time"] if clean_points else None,
            "sourceName": None,  # populated by the workout linker if needed
            "points": clean_points,
        }

        key = f"route:{doc['workoutId']}"
        pipe.json().set(key, "$", doc)
        keys.append(key)

        if i % _PIPELINE_BATCH == 0:
            failures.extend(_execute_pipeline(pipe, keys, "route"))
            pipe = r.pipeline()
            keys = []

    if keys:
        failures.extend(_execute_pipeline(pipe, keys, "route"))
    return failures
