"""Health Data Importer.

Uploads Apple Health ``export.zip`` data to a local Redis TimeSeries database
via an Extract → Transform → Load (ETL) pipeline.  Workouts, correlations,
activity summaries, and GPS routes are additionally stored as Redis JSON
documents so they can be queried through the RediSearch indexes provisioned by
:mod:`src.redis_setup`.

Cache format
------------
The five DataFrames are split across two serialisation formats to balance
file size, performance, and code simplicity:

* **Records, activities, routes** — Feather (Apache Arrow IPC).  These tables
  contain only Arrow-native scalar types (strings, floats, ``datetime64``).
  Feather's columnar layout and optional LZ4 compression produce the smallest
  files and the fastest read/write for large row counts.

* **Workouts, correlations** — pickle (``protocol=5``).  These tables carry
  nested Python objects (dicts and lists) in their ``meta``, ``events``,
  ``statistics``, ``route``, ``activities``, and ``records`` columns.  Pickle
  serialises the Python object graph directly, avoiding the JSON
  encode/decode step that Feather would require.  The tables are small (rarely
  more than a few thousand rows), so pickle's larger per-file overhead is
  inconsequential.

Typical usage::

    importer = HealthDataImporter()
    importer.etl(write_feather=True)

    for f in importer.failures:
        print(f)

    # Retry only the failed data points (can be called in a new session)
    importer.retry_failed()

    # Overwrite existing data points with the latest values
    importer.update()
"""

import logging
import math
from pathlib import Path

import pandas as pd
import redis
from pyarrow import feather
from redis.commands.timeseries import TimeSeries

from ..model import HKTypeIdentifierRegistry
from ..redis_setup import ensure_ts_key
from .parser import parse_apple_health, parse_apple_health_routes
from .pipeline import upload_batch
from .response import (
    BATCH_SIZE,
    BatchFailure,
    DuplicatePolicy,
    RowFailure,
    UploadFailure,
    count_failures,
    failures_from_json,
    failures_to_json,
)
from .transform import transform

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Document-upload helpers (Workout / Correlation / ActivitySummary / Route)
# ---------------------------------------------------------------------------


def _parse_hk_timestamp(value: str | None) -> int | None:
    """Convert an Apple Health date string to a Unix integer timestamp.

    Args:
        value: Date string in Apple Health format
            (e.g. ``"2024-01-01 00:00:00 +0000"``), or ``None``.

    Returns:
        Unix timestamp in whole seconds, or ``None`` if *value* is ``None``.

    Example::

        _parse_hk_timestamp("2024-01-01 00:00:00 +0000")  # → 1704067200
        _parse_hk_timestamp(None)                          # → None

    """
    if value is None:
        return None
    return int(pd.Timestamp(value).timestamp())


def _sanitize_doc(doc: dict) -> dict:
    """Replace ``float('nan')`` values with ``None`` for JSON-safe serialisation.

    Redis's JSON module rejects ``NaN`` because it is not valid JSON.

    Args:
        doc: Arbitrary ``str → Any`` mapping, typically a row from a
            DataFrame converted via ``.to_dict()``.

    Returns:
        A new dict with all ``float('nan')`` values replaced by ``None``.

    """
    return {
        k: (None if isinstance(v, float) and math.isnan(v) else v)
        for k, v in doc.items()
    }


def _load_documents(
    workouts: pd.DataFrame,
    correlations: pd.DataFrame,
    activities: pd.DataFrame,
    r: redis.Redis,
) -> None:
    """Upload workout, correlation, and activity documents to Redis JSON.

    Each document type is stored under a distinct key namespace:

    * ``workout:<startDate_unix>:<workoutActivityType>``
    * ``correlation:<startDate_unix>:<type>``
    * ``activity:<dateComponents>``

    String date fields are converted to Unix integer timestamps so the
    RediSearch ``NumericField`` indexes defined in
    :data:`src.redis_setup._INDICES` work correctly.  A ``metaKeys`` field is
    added to workouts and correlations to support
    ``TagField("$.metaKeys[*]", …)`` queries.  Activities receive a ``date``
    integer field derived from ``dateComponents``.

    This function is idempotent: re-running an import overwrites existing
    documents at the same key.

    Args:
        workouts: Workout DataFrame.  May be empty.
        correlations: Correlation DataFrame.  May be empty.
        activities: ActivitySummary DataFrame.  May be empty.
        r: Active Redis connection with the JSON module loaded.

    """
    n_workouts = n_correlations = n_activities = 0

    for _, row in workouts.iterrows():
        rd = _sanitize_doc(row.to_dict())
        start_ts = _parse_hk_timestamp(rd.get("startDate"))
        end_ts = _parse_hk_timestamp(rd.get("endDate"))
        activity_type = rd.get("workoutActivityType", "unknown")
        doc = {
            **rd,
            "startDate": start_ts,
            "endDate": end_ts,
            "metaKeys": list((rd.get("meta") or {}).keys()),
        }
        key = f"workout:{start_ts}:{activity_type}"
        r.json().set(key, "$", doc)
        n_workouts += 1

    for _, row in correlations.iterrows():
        rd = _sanitize_doc(row.to_dict())
        start_ts = _parse_hk_timestamp(rd.get("startDate"))
        end_ts = _parse_hk_timestamp(rd.get("endDate"))
        corr_type = rd.get("type", "unknown")
        doc = {
            **rd,
            "startDate": start_ts,
            "endDate": end_ts,
            "metaKeys": list((rd.get("meta") or {}).keys()),
        }
        key = f"correlation:{start_ts}:{corr_type}"
        r.json().set(key, "$", doc)
        n_correlations += 1

    for _, row in activities.iterrows():
        rd = _sanitize_doc(row.to_dict())
        date_str = rd.get("dateComponents")
        date_ts = _parse_hk_timestamp(date_str) if date_str else None
        doc = {**rd, "date": date_ts}
        key = f"activity:{date_str}"
        r.json().set(key, "$", doc)
        n_activities += 1

    logger.info(
        "Stored %d workout(s), %d correlation(s), %d activity summary(ies).",
        n_workouts,
        n_correlations,
        n_activities,
    )


def _upload_routes(
    routes: pd.DataFrame,
    workouts: pd.DataFrame,
    r: redis.Redis,
) -> None:
    """Upload GPS route trackpoints as Redis JSON documents.

    Groups the *routes* DataFrame by workout using the ``file`` column,
    which matches the paths listed in ``workout["route"]["files"]``.  Each
    workout's trackpoints are stored as a JSON document under
    ``route:<startDate_unix>:<workoutActivityType>``, mirroring the workout
    key pattern so the route can be retrieved by constructing the key from a
    known workout.

    The ``time`` column (``datetime64[ns, UTC]``) is converted to a Unix
    integer timestamp before JSON serialisation.  All ``NaN`` float fields
    are replaced with ``None`` via :func:`_sanitize_doc`.

    Args:
        routes: Routes DataFrame produced by
            :func:`.parser.parse_apple_health_routes`.  May be empty.
        workouts: Workout DataFrame — needed to map file paths back to
            workout keys.  May be empty.
        r: Active Redis connection with the JSON module loaded.

    """
    if routes.empty or workouts.empty:
        return

    n_stored = 0
    for _, workout_row in workouts.iterrows():
        rd = workout_row.to_dict()
        route_info = rd.get("route")
        if not isinstance(route_info, dict):
            continue
        route_files = route_info.get("files") or []
        if not route_files:
            continue

        start_ts = _parse_hk_timestamp(rd.get("startDate"))
        activity_type = rd.get("workoutActivityType", "unknown")

        workout_routes = routes[routes["file"].isin(route_files)]
        if workout_routes.empty:
            continue

        trackpoints: list[dict] = []
        for _, tp in workout_routes.iterrows():
            tp_dict = tp.to_dict()
            # Convert pandas Timestamp to Unix int
            t = tp_dict.get("time")
            if hasattr(t, "timestamp"):
                tp_dict["time"] = int(t.timestamp())
            elif t is None or (isinstance(t, float) and math.isnan(t)):
                tp_dict["time"] = None
            trackpoints.append(_sanitize_doc(tp_dict))

        key = f"route:{start_ts}:{activity_type}"
        doc = {
            "workoutKey": f"workout:{start_ts}:{activity_type}",
            "trackpoints": trackpoints,
        }
        r.json().set(key, "$", doc)
        n_stored += 1
        logger.debug("Stored route %s (%d trackpoints).", key, len(trackpoints))

    logger.info("Stored %d route(s).", n_stored)


# ---------------------------------------------------------------------------
# Public importer class
# ---------------------------------------------------------------------------


class HealthDataImporter:
    """Import Apple Health export data into Redis TimeSeries.

    After calling :meth:`etl` or :meth:`update`, any upload failures are
    accessible via :attr:`failures` and persisted to :attr:`failures_file`
    so that :meth:`retry_failed` can be called in a later Python session.

    Args:
        connection: :class:`redis.Redis` to connect to.
        data_dir: Sub-directory (relative to *working_dir*) that holds data
            files.
        in_file: Name of the Apple Health ZIP export inside *data_dir*.
        working_dir: Root directory; defaults to the current working directory.
        out_file: Name of the Feather cache for the records DataFrame.
        failures_file: Name of the JSON file that persists upload failures
            between sessions.

    Example::

        importer = HealthDataImporter(connection=redis_connect())
        importer.etl(write_feather=True)

    """

    def __init__(
        self,
        connection: redis.Redis,
        data_dir: str = "data",
        in_file: str = "export.zip",
        working_dir: Path | str | None = None,
        out_file: str = "export.feather",
        failures_file: str = "upload_failures.json",
    ) -> None:
        """Initialise the importer and resolve its working paths.

        Args:
            connection: Redis client used for all TimeSeries writes.
            data_dir: Directory (relative to ``working_dir``) holding the Apple
                Health export and where intermediate/output files are written.
            in_file: Name of the Apple Health export archive within ``data_dir``.
            working_dir: Base directory the other paths are resolved against.
                Defaults to the current working directory.
            out_file: Name of the Feather cache file for the *records*
                DataFrame (``export.feather`` by default).  Sibling cache
                files are derived from this stem: ``*_activities.feather``
                and ``*_routes.feather`` (Feather), plus ``*_workouts.pkl``
                and ``*_correlations.pkl`` (pickle, for tables with nested
                Python objects).
            failures_file: Name of the JSON file used to persist per-row upload
                failures so retries survive across runs.

        Raises:
            FileNotFoundError: If ``data_dir`` does not exist.

        """
        base = Path.cwd() if working_dir is None else Path(working_dir)

        self.data_dir: Path = base / data_dir
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory {self.data_dir} does not exist.")

        self.zip_file: Path = self.data_dir / in_file
        # Records feather (name supplied by caller)
        self.output_file: Path = self.data_dir / out_file
        stem = self.output_file.stem
        # Scalar-only tables → Feather (columnar, compact, fast for large row counts)
        self.activities_file: Path = self.data_dir / f"{stem}_activities.feather"
        self.routes_file: Path = self.data_dir / f"{stem}_routes.feather"
        # Tables with nested Python objects → pickle (no encode/decode shim needed)
        self.workouts_file: Path = self.data_dir / f"{stem}_workouts.pkl"
        self.correlations_file: Path = self.data_dir / f"{stem}_correlations.pkl"

        self.failures_file: Path = self.data_dir / failures_file
        self.connection = connection

        # In-memory mirror of the failures file.
        self.failures: list[UploadFailure] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def etl(
        self,
        *,
        write_feather: bool = False,
        persist_failures: bool = True,
        no_cache: bool = False,
    ) -> None:
        """Run the full Extract → Transform → Load pipeline.

        Uploads health records to Redis TimeSeries and stores workouts,
        correlations, activity summaries, and GPS routes as Redis JSON
        documents.  Uses :class:`~.response.DuplicatePolicy.FIRST` for
        TimeSeries writes so that re-running the same export never overwrites
        existing data points.

        Args:
            write_feather: Persist all five DataFrames as Feather caches so
                that subsequent runs skip the slow XML extraction step.
            persist_failures: Write the failures JSON file so that
                :meth:`retry_failed` can be called in another session.
            no_cache: If ``True``, ignore any pre-existing Feather caches and
                always read from the ZIP export.

        Raises:
            FileNotFoundError: When neither the Feather caches nor the source
                ZIP can be found.

        Example::

            importer.etl(write_feather=True)

        """
        records, correlations, workouts, activities, routes = self._extract(
            write_feather=write_feather, no_cache=no_cache
        )
        transform(records)
        self.failures = _load(records, self.connection)

        if self.failures:
            logger.warning(
                "%s.etl incomplete: %d of %d datapoints failed to upload.",
                self.__class__,
                count_failures(self.failures, records),
                len(records),
            )

        _load_documents(workouts, correlations, activities, self.connection)
        _upload_routes(routes, workouts, self.connection)

        if persist_failures:
            self._update_failures_file()

    def retry_failed(self, *, persist_failures: bool = True) -> None:
        """Re-attempt uploading every data point recorded in :attr:`failures_file`.

        Loads the records DataFrame from the Feather cache (or re-parses from
        the ZIP if the cache is absent), selects only the rows that previously
        failed, and calls :func:`_load` on that subset.  Workouts,
        correlations, activities, and routes are **not** re-uploaded; only
        TimeSeries records are retried.

        After the retry:

        * All failures resolved → failures file is deleted.
        * Some failures remain → file is overwritten with only the
          still-failing entries.

        Args:
            persist_failures: Write the updated failures file after the retry.

        Raises:
            FileNotFoundError: If :attr:`failures_file` does not exist, or if
                neither the records Feather cache nor the ZIP can be found.

        Example::

            importer.retry_failed()
            if not importer.failures:
                print("All failures resolved.")

        """
        logger.warning(
            "Starting retry_failed.\n\tThis will only"
            " produce correct results if feather file"
            " has not changed since previous run."
        )

        self.failures = self._read_failures_file()
        if not self.failures:
            self._delete_failures_file()
            logger.warning("retry_failed: failures file is empty, nothing to retry.")
            return None

        # Only records are needed — use the dedicated records-only loader so
        # retry still works even if only the records feather exists.
        records = self._extract_records_only(no_cache=False)

        row_selectors: list = []
        for f in self.failures:
            match f:
                case BatchFailure(data_type=t, batch_nr=n):
                    row_selectors.extend(
                        records[records["type"] == t].index[
                            n * BATCH_SIZE : (n + 1) * BATCH_SIZE
                        ]
                    )
                case RowFailure(row_index=i):
                    row_selectors.append(i)

        retry_df = records[records.index.isin(row_selectors)]
        transform(retry_df)

        n_before = count_failures(self.failures, records)
        self.failures = _load(
            df=retry_df, r=self.connection, duplicate_policy=DuplicatePolicy.FIRST
        )

        n_after = count_failures(self.failures, records)
        logger.info(
            "retry_failed complete: %d/%d failure(s) resolved, %d remaining.",
            n_before - n_after,
            n_before,
            n_after,
        )

        if persist_failures:
            self._update_failures_file()

    def update(
        self,
        *,
        write_feather: bool = False,
        persist_failures: bool = True,
        no_cache: bool = False,
    ) -> None:
        """Re-import the export, **overwriting** existing data points.

        Identical to :meth:`etl` except it uses
        :class:`~.response.DuplicatePolicy.LAST` for TimeSeries writes, and
        all JSON documents (workouts, correlations, activities, routes) are
        also overwritten.

        Args:
            write_feather: Persist all five DataFrames as Feather caches.
            persist_failures: Write the failures JSON file.
            no_cache: If ``True``, ignore any pre-existing Feather caches.

        Example::

            importer.update()

        """
        records, correlations, workouts, activities, routes = self._extract(
            write_feather=write_feather, no_cache=no_cache
        )
        transform(records)
        self.failures = _load(
            records,
            self.connection,
            duplicate_policy=DuplicatePolicy.LAST,
        )

        if self.failures:
            logger.warning(
                "%s.update incomplete: %d of %d datapoints failed to upload.",
                self.__class__,
                count_failures(self.failures, records),
                len(records),
            )

        _load_documents(workouts, correlations, activities, self.connection)
        _upload_routes(routes, workouts, self.connection)

        if persist_failures:
            self._update_failures_file()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _all_caches_exist(self) -> bool:
        """Return ``True`` if every Feather cache file is present on disk.

        A partial cache (e.g. only the records feather from a pre-route run)
        is treated as a cache miss so the full ZIP is re-parsed and all five
        files are written together.

        """
        return all(
            p.exists()
            for p in (
                self.output_file,
                self.workouts_file,
                self.correlations_file,
                self.activities_file,
                self.routes_file,
            )
        )

    def _write_all_caches(
        self,
        records: pd.DataFrame,
        correlations: pd.DataFrame,
        workouts: pd.DataFrame,
        activities: pd.DataFrame,
        routes: pd.DataFrame,
    ) -> None:
        """Write all five DataFrames to their respective cache files.

        Tables with scalar-only columns are written as Feather; tables that
        carry nested Python objects (dicts / lists) are written as pickle so
        no JSON encode/decode shim is required.

        ================  ==========  ==========================================
        File              Format      Rationale
        ================  ==========  ==========================================
        records           Feather     Millions of rows; columnar compression wins
        activities        Feather     Scalar strings; small, fast either way
        routes            Feather     Float + datetime columns; Arrow is optimal
        workouts          pickle      Contains meta/events/statistics/route dicts
        correlations      pickle      Contains meta/records dicts
        ================  ==========  ==========================================

        Args:
            records: Health records DataFrame.
            correlations: Correlation DataFrame (nested dicts/lists).
            workouts: Workout DataFrame (nested dicts/lists).
            activities: ActivitySummary DataFrame.
            routes: GPS routes DataFrame.

        """
        logger.info("Writing caches to %s", self.data_dir)
        records.to_feather(self.output_file)
        activities.to_feather(self.activities_file)
        routes.to_feather(self.routes_file)
        workouts.to_pickle(self.workouts_file)
        correlations.to_pickle(self.correlations_file)
        logger.info("All caches written.")

    def _read_all_caches(
        self,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Load all five DataFrames from their cache files.

        Feather files are read with :func:`pyarrow.feather.read_feather`;
        pickle files are read with :func:`pandas.read_pickle`.  No
        encode/decode step is required — the complex Python objects in the
        workout and correlation DataFrames are restored directly by pickle.

        Returns:
            5-tuple of ``(records, correlations, workouts, activities, routes)``.

        """
        logger.info("All caches found; skipping XML conversion.")

        return (
            feather.read_feather(self.output_file),
            pd.read_pickle(self.correlations_file),  # noqa: S301
            pd.read_pickle(self.workouts_file),  # noqa: S301
            feather.read_feather(self.activities_file),
            feather.read_feather(self.routes_file),
        )

    def _extract(
        self, *, write_feather: bool, no_cache: bool
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Parse the Apple Health export and return all five DataFrames.

        Loads from the Feather caches when *all five* cache files exist and
        ``no_cache`` is ``False``; otherwise parses the ZIP export.  Routes
        are collected by reading the ``route["files"]`` field of each workout
        and calling :func:`.parser.parse_apple_health_routes`.

        Args:
            write_feather: Write all five Feather cache files after parsing.
            no_cache: If ``True``, always parse from the ZIP even when caches
                exists.

        Returns:
            5-tuple ``(records, correlations, workouts, activities, routes)``.

        Raises:
            FileNotFoundError: When the Feather caches are absent or incomplete
                *and* the ZIP export cannot be found.

        """
        logger.info("Extracting export data...")
        if not no_cache and self._all_caches_exist():
            return self._read_all_caches()

        if not self.zip_file.exists():
            raise FileNotFoundError(
                f"No export file found. Expected one of:\n"
                f"  {self.output_file}  (+ sibling caches)\n"
                f"  {self.zip_file}"
            )

        logger.info("Parsing ZIP export...")
        record_df, correlation_df, workout_df, activity_df = parse_apple_health(
            zip_path=self.zip_file
        )

        # Collect route file paths from workouts and parse all at once.
        routes_df = self._parse_routes(workout_df)

        if write_feather:
            self._write_all_caches(
                record_df, correlation_df, workout_df, activity_df, routes_df
            )

        return record_df, correlation_df, workout_df, activity_df, routes_df

    def _extract_records_only(self, *, no_cache: bool) -> pd.DataFrame:
        """Load only the records DataFrame, preferring the Feather cache.

        Unlike :meth:`_extract`, this method succeeds as long as the *records*
        Feather file exists, even when the other four caches are absent.  It is
        used exclusively by :meth:`retry_failed` so that a retry run never
        requires the full ZIP to be present.

        Args:
            no_cache: If ``True``, bypass the Feather cache and parse from ZIP.

        Returns:
            The raw health records DataFrame.

        Raises:
            FileNotFoundError: When neither the records Feather cache nor the
                ZIP export can be found.

        """
        logger.info("Extracting records data...")
        if not no_cache and self.output_file.exists():
            logger.info("Records Feather cache found; loading records.")
            return feather.read_feather(self.output_file)

        if not self.zip_file.exists():
            raise FileNotFoundError(
                f"No export file found. Expected one of:\n"
                f"  {self.output_file}\n"
                f"  {self.zip_file}"
            )

        logger.info("Parsing records from ZIP export...")
        record_df, _, _, _ = parse_apple_health(zip_path=self.zip_file)
        return record_df

    def _parse_routes(self, workout_df: pd.DataFrame) -> pd.DataFrame:
        """Parse GPS routes from all workouts that carry a route reference.

        Collects every unique GPX path listed in ``workout["route"]["files"]``
        and delegates a single call to
        :func:`.parser.parse_apple_health_routes`.

        Args:
            workout_df: Workout DataFrame as returned by
                :func:`.parser.parse_apple_health`.

        Returns:
            Routes DataFrame, or an empty DataFrame when no workouts have a
            route.

        """
        if workout_df.empty or "route" not in workout_df.columns:
            return pd.DataFrame()

        route_paths: list[str] = [
            path
            for route in workout_df["route"].dropna()
            if isinstance(route, dict)
            for path in (route.get("files") or [])
        ]

        if not route_paths:
            return pd.DataFrame()

        logger.info("Parsing %d GPX route file(s)...", len(route_paths))
        return parse_apple_health_routes(self.zip_file, paths=route_paths)

    def _update_failures_file(self) -> None:
        """Persist or clear the failures file to match in-memory state."""
        if self.failures:
            self._write_failures_file(self.failures)
        else:
            self._delete_failures_file()

    def _write_failures_file(self, failures: list[UploadFailure]) -> None:
        """Serialise *failures* and write them to :attr:`failures_file`.

        Args:
            failures: List of :class:`~.response.UploadFailure` objects.

        """
        self.failures_file.write_text(failures_to_json(failures), encoding="utf-8")
        logger.info("Wrote %d failure(s) to %s", len(failures), self.failures_file)

    def _delete_failures_file(self) -> None:
        """Delete :attr:`failures_file` if it exists."""
        if self.failures_file.exists():
            self.failures_file.unlink()
            logger.info("Deleted failures file %s (all resolved).", self.failures_file)

    def _read_failures_file(self) -> list[UploadFailure]:
        """Read and deserialise the failures file.

        Returns:
            List of :class:`~.response.UploadFailure` objects.

        Raises:
            FileNotFoundError: If :attr:`failures_file` does not exist.

        """
        if not self.failures_file.exists():
            raise FileNotFoundError(
                f"Failures file not found: {self.failures_file}\n"
                "Run etl() or update() first, or check that the file has "
                "not been manually deleted or moved."
            )
        text = self.failures_file.read_text(encoding="utf-8")
        failures = failures_from_json(text)
        logger.info("Read %d failure(s) from %s", len(failures), self.failures_file)
        return failures


def _load(
    df: pd.DataFrame,
    r: redis.Redis,
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.FIRST,
) -> list[UploadFailure]:
    """Batch-upload all records to Redis TimeSeries.

    Each unique ``type`` is uploaded in its own pipeline in batches of
    :data:`~.response.BATCH_SIZE` rows.  Before the first batch for each type,
    :func:`~src.redis_setup.ensure_ts_key` provisions the ``:start`` / ``:end``
    keys with metadata labels derived from the transformed DataFrame's ``unit``
    and ``group`` columns.

    Args:
        df: Transformed health records DataFrame.  Must have ``type``,
            ``unit``, and ``group`` columns.
        r: Active Redis connection.
        duplicate_policy: Write-conflict strategy for ``TS.ADD``.

    Returns:
        List of :class:`~.response.UploadFailure` objects; empty on full
        success.

    """
    logger.info(
        "Loading data to Redis TimeSeries (duplicate_policy=%s)...",
        duplicate_policy.value,
    )
    rts: TimeSeries = r.ts()
    failures: list[UploadFailure] = []

    data_types = df["type"].unique()
    logger.info(f"Found {len(data_types)} data types.")
    for data_type in data_types:
        batch_df = df[df["type"] == data_type]
        n = len(batch_df)
        logger.info(
            "%s: Uploading %i rows in %i batches.", data_type, n, n // BATCH_SIZE + 1
        )

        # make sure labels exist
        cls = HKTypeIdentifierRegistry[data_type]
        base_labels: dict[str, str] = {
            "unit": cls.unit,
            "identifier": data_type,
            "group": cls.group,
        }
        ensure_ts_key(
            r, f"ts:{data_type}:start", labels=base_labels | {"event_type": "start"}
        )
        ensure_ts_key(
            r, f"ts:{data_type}:end", labels=base_labels | {"event_type": "end"}
        )

        for i in range(0, n, BATCH_SIZE):
            _df = batch_df.iloc[i : i + BATCH_SIZE]

            try:
                row_failures = upload_batch(
                    rts,
                    _df,
                    duplicate_policy=duplicate_policy,
                )

                if row_failures:
                    logger.warning(
                        "\tBatch %i: %d/%d row(s) failed.",
                        i // BATCH_SIZE + 1,
                        len(row_failures),
                        len(_df),
                    )
                    failures.extend(row_failures)

            except IndexError as exc:
                batch_failure = BatchFailure(
                    data_type=data_type, batch_nr=i // BATCH_SIZE, error=str(exc)
                )
                logger.exception(
                    "\tBatch %i: Could not resolve failures:\n\t\t%s",
                    i // BATCH_SIZE + 1,
                    batch_failure,
                )
                failures.append(batch_failure)

            except redis.RedisError as exc:
                batch_failure = BatchFailure(
                    data_type=data_type, batch_nr=i // BATCH_SIZE, error=str(exc)
                )
                logger.exception(
                    "\tBatch %i: Entire batch failed:\n\t\t%s",
                    i // BATCH_SIZE + 1,
                    batch_failure,
                )
                failures.append(batch_failure)

    return failures
