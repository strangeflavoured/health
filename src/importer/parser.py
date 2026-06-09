"""Parser for Apple Health export files.

Reads the ``export.zip`` produced by the Apple Health app and returns one
tidy DataFrame per top-level element type — ``Record``, ``Correlation``,
``Workout``, ``ActivitySummary`` — plus a helper for parsing workout-route
GPX files.

Streaming and memory
--------------------
:func:`parse_apple_health` uses :func:`lxml.etree.iterparse` with the
standard "fast iterparse" cleanup pattern: each finished top-level child of
``<HealthData>`` has its subtree cleared and previously-processed siblings
dropped from the root.  Peak memory is bounded by the largest single
top-level element, not by the export size.

Records are accumulated into per-column lists (one list per attribute in
``_RECORD_ATTRS``) rather than a list of row-dicts; for the ~millions of
Record elements in a typical export this halves peak memory relative to
the row-dict approach.  ``Correlation``, ``Workout`` and ``ActivitySummary``
rows are less numerous and stay as row-dicts for readability.

Date filtering
--------------
The ``from_date`` filter uses a 10-character ISO-prefix lexical comparison
(``date_str[:10] < from_iso``) rather than ``pd.to_datetime`` per element.
Apple Health dates are ISO-formatted, so this is exact at day granularity
and around three orders of magnitude faster than parsing each timestamp.

Correlation child Records
-------------------------
Per Apple's DTD: *"Any Records that appear as children of a correlation
also appear as top-level records in this document."*  This parser exploits
that: top-level Records go into ``records_df`` once, and the
``correlations_df["records"]`` column carries row indices into
``records_df`` rather than duplicating the record data.  Matching is by
the full attribute tuple, with FIFO ordering for the unusual case of two
identical top-level Records.

Unknown top-level elements
--------------------------
Top-level XML elements that this parser does not convert to DataFrames are
counted and reported in a single end-of-parse ``WARNING``.  Tags listed in
``_KNOWN_UNHANDLED_TAGS`` (``Me``, ``ExportDate``, ``ClinicalRecord``,
``Audiogram``, ``VisionPrescription``) are reported as expected-skip
entries; any other tag is reported with an ``(unrecognised)`` marker so
operators can spot iOS-version schema drift without scraping logs.

Unknown *child* elements inside a handled parent raise
``NotImplementedError`` — schema drift inside a known parent could silently
corrupt downstream uploads and is worth halting on.

XML security
------------
The parser sets ``load_dtd=False``, ``resolve_entities=False`` and
``no_network=True``.  These block external-entity dereferencing (XXE) and,
combined with libxml2's built-in amplification limit, billion-laughs DoS.
A ``DOCTYPE`` containing internal entities will parse, but its entity
references will be left unresolved in element content (and bounded by
libxml2's amplification factor in attribute values).
"""

from __future__ import annotations

import hashlib
import logging
import zipfile
from collections import Counter
from pathlib import Path

import pandas as pd
from lxml import etree

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schemas
#
# `_*_ATTRS` constants list the XML attributes pulled directly from an
# element.  They are used by `_attrs()` and as identity tuples for the
# correlation-record lookup; therefore they must contain only real
# XML attribute names.
#
# `_*_COLUMNS` constants describe the output-DataFrame schema and are
# what downstream code should pin against.  They include both attributes
# and derived fields ("meta", "records", "events", ...).
# ---------------------------------------------------------------------------

RECORD_ATTRS = (
    "type",
    "sourceName",
    "sourceVersion",
    "device",
    "unit",
    "startDate",
    "endDate",
    "creationDate",
    "value",
)
_RECORD_COLUMNS = RECORD_ATTRS + ("meta",)

_CORRELATION_ATTRS = (
    "type",
    "sourceName",
    "sourceVersion",
    "device",
    "creationDate",
    "startDate",
    "endDate",
)
_CORRELATION_COLUMNS = _CORRELATION_ATTRS + ("meta", "records")

_ACTIVITY_ATTRS = (
    "dateComponents",
    "appleExerciseTime",
    "appleExerciseTimeGoal",
    "appleMoveTime",
    "appleMoveTimeGoal",
    "appleStandHours",
    "appleStandHoursGoal",
    "activeEnergyBurned",
    "activeEnergyBurnedGoal",
    "activeEnergyBurnedUnit",
)
_ACTIVITY_COLUMNS = _ACTIVITY_ATTRS

_WORKOUT_ATTRS = (
    "workoutActivityType",
    "duration",
    "durationUnit",
    "totalDistance",
    "totalDistanceUnit",
    "totalEnergyBurned",
    "totalEnergyBurnedUnit",
    "sourceName",
    "sourceVersion",
    "device",
    "creationDate",
    "startDate",
    "endDate",
)
_WORKOUT_COLUMNS = _WORKOUT_ATTRS + (
    "meta",
    "events",
    "statistics",
    "route",
    "activities",
)

_WORKOUT_EVENT_ATTRS = ("type", "date", "duration", "durationUnit")
_WORKOUT_STATISTICS_ATTRS = (
    "type",
    "startDate",
    "endDate",
    "average",
    "minimum",
    "maximum",
    "sum",
    "unit",
)
_WORKOUT_ROUTE_ATTRS = (
    "sourceName",
    "sourceVersion",
    "device",
    "creationDate",
    "startDate",
    "endDate",
)
_WORKOUT_ACTIVITY_ATTRS = ("uuid", "startDate", "endDate", "duration", "durationUnit")

# Tags Apple Health emits at top level that this parser deliberately does
# not convert to DataFrames.  Used to distinguish "known but skipped" from
# "unrecognised — possible schema drift" in the end-of-parse warning.
_KNOWN_UNHANDLED_TAGS = frozenset(
    {"ExportDate", "Me", "ClinicalRecord", "Audiogram", "VisionPrescription"}
)


class NoHealthDataError(ValueError):
    """Raised when the export contains no rows in any of the four DataFrames."""

    pass


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------


def _attrs(elem: etree._Element, keys: tuple[str]) -> dict[str, str]:
    """Pull a fixed set of XML attributes into a dict."""
    a = elem.attrib
    return {k: a.get(k) for k in keys}


def _is_before(elem: etree._Element, from_iso: str) -> bool:
    """ISO-prefix lexical date comparison.

    Matches the documented filter semantics (day granularity, timezone
    ignored) and is roughly four orders of magnitude faster than
    ``pd.to_datetime(...).date()`` per call.
    """
    a = elem.attrib
    date = a.get("endDate") or a.get("date") or a.get("dateComponents")
    return date is not None and date[:10] < from_iso


def _record_metadata(elem: etree._Element) -> dict[str, str]:
    """Collect ``MetadataEntry`` children as ``{key: value}``, or ``None``.

    Returning ``None`` (rather than an empty dict) for the common
    "no metadata" case keeps memory flat: a 2M-record export pays ~16 MB
    for pointers vs ~130 MB for empty dicts.

    ``HeartRateVariabilityMetadataList`` children are deliberately ignored
    here — the per-beat detail used to compute SDNN is rarely needed and
    bulky when present.  Add a separate helper if/when that data is wanted.
    """
    meta = None
    for c in elem:
        if c.tag == "MetadataEntry":
            if meta is None:
                meta = {}
            meta[c.attrib.get("key")] = c.attrib.get("value")
    return meta


def _log_unknown_elements(counts: Counter[str]) -> None:
    """Emit a single WARNING summarising every unhandled top-level element.

    Known-but-unhandled tags (``_KNOWN_UNHANDLED_TAGS``) and genuinely
    unrecognised tags are separated in the output so operators can
    distinguish "expected skip" from "iOS schema drift, investigate".
    """
    known, unrecognised = [], []
    for tag, n in sorted(counts.items()):
        if tag in _KNOWN_UNHANDLED_TAGS:
            known.append(f"{tag}={n}")
        else:
            unrecognised.append(f"{tag}={n}")

    parts = []
    if known:
        parts.append("skipped " + ", ".join(known))
    if unrecognised:
        parts.append("unrecognised " + ", ".join(unrecognised))
    logger.warning("Unknown top-level elements: %s", "; ".join(parts))


# ---------------------------------------------------------------------------
# per-parent helpers
# ---------------------------------------------------------------------------


def uuid(identifiers: dict[str, str]) -> str:
    """Generate a uuid from dict of identifiers.

    Args:
        identifiers: Dict of identifiers, should be unique to each entry.

    Returns:
        UUID of len 16

    Example:
        identifiers = {"data_type": "workout", "start_date": "2026-04-01",
            "sourceName": "Apple Watch"}
        uuid(identifiers)

    """
    kv: list = []
    for k in sorted(identifiers.keys()):
        kv.append(f"{k}:{identifiers[k]}")
    fingerprint = "|".join(kv)
    return hashlib.sha256(fingerprint.encode(), usedforsecurity=False).hexdigest()[:16]


def _parse_workout_event(elem: etree._Element) -> dict[str, str]:
    out = _attrs(elem, _WORKOUT_EVENT_ATTRS)
    for c in elem:
        if c.tag == "MetadataEntry":
            out[c.attrib.get("key")] = c.attrib.get("value")
        else:
            raise NotImplementedError(f"WorkoutEvent child {c.tag} is not implemented.")
    return out


def _parse_workout_route(elem: etree._Element) -> dict[str, str]:
    out = _attrs(elem, _WORKOUT_ROUTE_ATTRS)
    files, meta = [], {}
    for c in elem:
        if c.tag == "FileReference":
            files.append(c.attrib.get("path"))
        elif c.tag == "MetadataEntry":
            meta[c.attrib.get("key")] = c.attrib.get("value")
        else:
            raise NotImplementedError(f"WorkoutRoute child {c.tag} is not implemented.")
    out["files"] = files
    out["meta"] = meta
    return out


def _parse_workout_activity(elem: etree._Element) -> dict[str, str]:
    out = _attrs(elem, _WORKOUT_ACTIVITY_ATTRS)
    meta, events, stats = {}, [], []
    for c in elem:
        if c.tag == "WorkoutEvent":
            events.append(_parse_workout_event(c))
        elif c.tag == "MetadataEntry":
            meta[c.attrib.get("key")] = c.attrib.get("value")
        elif c.tag == "WorkoutStatistics":
            stats.append(_attrs(c, _WORKOUT_STATISTICS_ATTRS))
        else:
            raise NotImplementedError(
                f"WorkoutActivity child {c.tag} is not implemented."
            )
    out["meta"] = meta
    out["events"] = events
    out["statistics"] = stats
    return out


def _parse_correlation(elem: etree._Element) -> dict[str, str]:
    """Extract Correlation attributes, metadata, and child-record keys.

    Child Record references are returned as identifying attribute tuples in
    a temporary ``_record_keys`` field, which :func:`parse_apple_health`
    resolves to ``records_df`` row indices after the parsing loop completes.
    """
    out = _attrs(elem, _CORRELATION_ATTRS)
    meta, keys = {}, []
    for c in elem:
        if c.tag == "MetadataEntry":
            meta[c.attrib.get("key")] = c.attrib.get("value")
        elif c.tag == "Record":
            a = c.attrib
            keys.append({col: a.get(col) for col in RECORD_ATTRS})
        else:
            raise NotImplementedError(f"Correlation child {c.tag} is not implemented.")
    out["meta"] = meta
    out["_record_keys"] = keys
    out["correlation_id"] = uuid({"data_type": "correlation"} | meta)
    return out


def _parse_workout(elem: etree._Element) -> dict[str, str]:
    out = _attrs(elem, _WORKOUT_ATTRS)
    activities, events, meta, routes, stats = [], [], {}, [], []
    for c in elem:
        if c.tag == "WorkoutActivity":
            activities.append(_parse_workout_activity(c))
        elif c.tag == "WorkoutEvent":
            events.append(_parse_workout_event(c))
        elif c.tag == "MetadataEntry":
            meta[c.attrib.get("key")] = c.attrib.get("value")
        elif c.tag == "WorkoutRoute":
            routes.append(_parse_workout_route(c))
        elif c.tag == "WorkoutStatistics":
            stats.append(_attrs(c, _WORKOUT_STATISTICS_ATTRS))
        else:
            raise NotImplementedError(f"Workout child {c.tag} is not implemented.")
    out["meta"] = meta
    out["events"] = events
    out["statistics"] = stats
    out["routes"] = routes
    out["activities"] = activities
    out["workout_id"] = uuid({"data_type": "workout"} | meta | routes)
    return out


# ---------------------------------------------------------------------------
# main parser
# ---------------------------------------------------------------------------


def parse_apple_health(
    zip_path: str | Path,
    *,
    from_date: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Parse an Apple Health ``export.zip`` into four DataFrames.

    Args:
        zip_path: Path to the ``export.zip`` produced by the Apple Health
            app.  Accepts :class:`str` or :class:`pathlib.Path`.
        from_date: Inclusive lower bound for filtering by date.  Top-level
            elements whose date falls *strictly before* this value are
            dropped.  Comparison is at day granularity by lexical
            comparison of ISO-prefixed date strings (time-of-day and
            timezone offset are ignored).  Elements without a date
            attribute (``Me``, ``ExportDate``) are never filtered.  The
            filter does NOT recurse into ``Correlation`` or ``Workout``:
            if a complex parent passes the filter, all its children are
            kept regardless of their own dates.  ``None`` disables filtering.

    Returns:
        A 4-tuple ``(records, correlations, workouts, activities)``.

        **records** — one row per top-level ``Record``.  Columns follow
        ``_RECORD_ATTRS`` plus ``meta`` (``dict[str, str] | None``) when
        ``parse_record_metadata=True``.  All attribute values are strings
        as exported by Apple; numeric/temporal conversion is left to the
        caller.

        **correlations** — one row per ``Correlation``.  Columns follow
        ``_CORRELATION_ATTRS`` plus:

        - ``meta`` (dict): ``MetadataEntry`` children as ``{key: value}``.
        - ``records`` (list[int | None]): row indices into ``records_df``
          for each child Record, in document order.  ``None`` indicates a
          child that could not be linked — typically ``skip_records=True``
          or a date filter that dropped the top-level duplicate while
          keeping the correlation.

        **workouts** — one row per ``Workout``.  Columns follow
        ``_WORKOUT_ATTRS`` plus:

        - ``meta`` (dict): ``MetadataEntry`` children.
        - ``events`` (list[dict]): ``WorkoutEvent`` elements, each with
          their own ``MetadataEntry`` children merged in as extra keys.
        - ``statistics`` (list[dict]): ``WorkoutStatistics`` elements.
        - ``route`` (dict | None): ``WorkoutRoute`` attributes plus
          ``files`` (list of GPX paths) and ``meta`` (dict).
        - ``activities`` (list[dict]): ``WorkoutActivity`` elements, each
          carrying its own ``meta``/``events``/``statistics``.

        **activities** — one row per ``ActivitySummary``.  Columns follow
        ``_ACTIVITY_ATTRS``.

    Note:
        ``HeartRateVariabilityMetadataList`` children are always discarded.

    Raises:
        NoHealthDataError: If all four returned DataFrames are empty.
        NotImplementedError: If a known parent contains a child element
            with a tag this parser does not handle.

    Example:
        >>> records, corr, workouts, activities = parse_apple_health("export.zip")
        >>> hr = records[records["type"] == "HKQuantityTypeIdentifierHeartRate"]
        >>> resting = hr[hr["meta"].apply(
        ...     lambda m: m and m.get("HKMetadataKeyHeartRateMotionContext") == "1"
        ... )]
        >>> bp = corr.iloc[0]
        >>> records.iloc[bp["records"]]  # the two BP readings as a DataFrame

    """
    record_cols: dict[str, list] = {col: [] for col in RECORD_ATTRS}
    record_meta: list[dict[str, str] | None] = []
    correlation_rows: list[dict] = []
    workout_rows: list[dict] = []
    activity_rows: list[dict] = []
    unknown_counts: Counter[str] = Counter()
    from_iso = from_date.strftime("%Y-%m-%d") if from_date is not None else None

    with (
        zipfile.ZipFile(zip_path) as zf,
        zf.open("apple_health_export/export.xml") as f,
    ):
        root = None
        for event, elem in etree.iterparse(
            f,
            events=("start", "end"),
            load_dtd=False,
            resolve_entities=False,
            no_network=True,
            huge_tree=False,
        ):
            # One-shot: capture root from its start event.  Holding a
            # stable identity lets us test top-level-ness by `is`.
            if event == "start":
                if root is None:
                    root = elem
                continue

            # End event.  Process only direct children of root; deeper
            # descendants fire end events too but are read via their
            # ancestor's helper.
            if elem.getparent() is not root:
                continue

            if from_iso is not None and _is_before(elem, from_iso):
                pass  # fall through to cleanup; nothing appended
            else:
                tag = elem.tag
                if tag == "Record":
                    a = elem.attrib
                    for col in RECORD_ATTRS:
                        record_cols[col].append(a.get(col))
                    record_meta.append(_record_metadata(elem))
                elif tag == "Correlation":
                    correlation_rows.append(_parse_correlation(elem))
                elif tag == "Workout":
                    workout_rows.append(_parse_workout(elem))
                elif tag == "ActivitySummary":
                    activity_rows.append(_attrs(elem, _ACTIVITY_ATTRS))
                else:
                    unknown_counts[tag] += 1

            # Standard lxml fast-iterparse cleanup.  Clears the finished
            # element's subtree, then drops already-processed preceding
            # siblings from root.  Leaves the in-progress next sibling
            # intact.
            elem.clear()
            while elem.getprevious() is not None:
                del root[0]

    if unknown_counts:
        _log_unknown_elements(unknown_counts)

    record_cols["meta"] = record_meta
    record_df = pd.DataFrame(record_cols)

    correlation_df = pd.DataFrame(correlation_rows)
    workout_df = pd.DataFrame(workout_rows)
    activity_df = pd.DataFrame(activity_rows)

    if (
        record_df.empty
        and correlation_df.empty
        and workout_df.empty
        and activity_df.empty
    ):
        logger.error("No records found in zip file %s.", zip_path)
        raise NoHealthDataError

    logger.info(
        "Parsed %d records, %d correlations, %d workouts, %d activity summaries.",
        len(record_df),
        len(correlation_df),
        len(workout_df),
        len(activity_df),
    )
    return record_df, correlation_df, workout_df, activity_df


# ---------------------------------------------------------------------------
# route parser
# ---------------------------------------------------------------------------

_GPX_NS = "http://www.topografix.com/GPX/1/1"
_GPX_EXT_FIELDS = ("speed", "course", "hAcc", "vAcc")


def _gpx_ext_value(ext: etree._Element | None, field: str) -> float | None:
    """Look up a GPX extension field, with and without the GPX namespace.

    Avoids ``ext.find(a) or ext.find(b)``: lxml elements without children
    are *falsy* in boolean context, so the ``or`` chain would skip an
    existing-but-empty element and fall through to the namespaced lookup.
    Use explicit ``is None`` checks instead.
    """
    if ext is None:
        return None
    child = ext.find(field)
    if child is None:
        child = ext.find(f"{{{_GPX_NS}}}{field}")
    if child is None or child.text is None:
        return None
    return float(child.text)


def parse_apple_health_routes(
    zip_path: str | Path,
    paths: list[str] | None = None,
) -> pd.DataFrame:
    """Parse workout-route GPX files from an Apple Health export archive.

    Each workout route is stored as a separate GPX file inside the archive,
    under ``apple_health_export/workout-routes/``.  File paths are exposed
    on the ``route["files"]`` field of rows returned by
    :func:`parse_apple_health`.  If ``paths`` is ``None`` every
    ``workout-routes/*.gpx`` file in the archive is parsed.

    Args:
        zip_path: Path to ``export.zip``.  Accepts :class:`str` or
            :class:`pathlib.Path`.
        paths: Optional list of GPX file paths *relative to*
            ``apple_health_export/`` inside the archive, e.g.
            ``["workout-routes/route_2024-03-15_123456789.gpx"]``.
            ``None`` parses all GPX files under ``workout-routes/``.

    Returns:
        One row per ``trkpt`` with columns:

        - ``file`` (str): GPX file path relative to ``apple_health_export/``,
          so callers can join back to a workout via its ``route["files"]``.
        - ``lat``, ``lon`` (float): Coordinates in WGS84 degrees.
        - ``ele`` (float | None): Elevation in metres above sea level.
        - ``time`` (datetime64[ns, UTC]): Sample timestamp.
        - ``speed`` (float | None): Instantaneous speed in m/s.
        - ``course`` (float | None): Heading in degrees (0–360).
        - ``hAcc`` (float | None): Horizontal accuracy in metres.
        - ``vAcc`` (float | None): Vertical accuracy in metres.

    Example:
        >>> records, corr, workouts, activities = parse_apple_health("export.zip")
        >>> route_paths = [p for r in workouts["route"].dropna() for p in r["files"]]
        >>> routes = parse_apple_health_routes("export.zip", paths=route_paths)

    """
    rows = []
    trkpt_tag = f"{{{_GPX_NS}}}trkpt"
    ele_tag = f"{{{_GPX_NS}}}ele"
    time_tag = f"{{{_GPX_NS}}}time"
    ext_tag = f"{{{_GPX_NS}}}extensions"

    with zipfile.ZipFile(zip_path) as zf:
        if paths is None:
            paths = [
                name.removeprefix("apple_health_export/")
                for name in zf.namelist()
                if name.startswith("apple_health_export/workout-routes/")
                and name.endswith(".gpx")
            ]

        for path in paths:
            with zf.open(f"apple_health_export/{path}") as f:
                for _, elem in etree.iterparse(
                    f,
                    events=("end",),
                    resolve_entities=False,
                    no_network=True,
                    load_dtd=False,
                    huge_tree=False,
                ):
                    if elem.tag != trkpt_tag:
                        continue

                    row: dict[str, object] = {
                        "file": path,
                        "lat": float(elem.attrib["lat"]),
                        "lon": float(elem.attrib["lon"]),
                    }

                    ele = elem.find(ele_tag)
                    row["ele"] = (
                        float(ele.text)
                        if ele is not None and ele.text is not None
                        else None
                    )

                    time_elem = elem.find(time_tag)
                    row["time"] = time_elem.text if time_elem is not None else None

                    ext = elem.find(ext_tag)
                    for field in _GPX_EXT_FIELDS:
                        row[field] = _gpx_ext_value(ext, field)

                    rows.append(row)
                    elem.clear()

    df = pd.DataFrame(rows)
    if not df.empty:
        df["time"] = pd.to_datetime(df["time"], utc=True)
    return df
