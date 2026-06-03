"""Health Data Importer.

Uploads Apple Health ``export.zip`` data to Redis via an Extract → Transform
→ Load (ETL) pipeline.

Data flow
---------
:func:`~src.importer.parser.parse_apple_health` produces four DataFrames
from the export archive:

* **records** — billions-scale rows, written to RedisTimeSeries as
  ``ts:<type>:start`` and ``ts:<type>:end`` keys.
* **workouts**, **correlations**, **activity summaries** — thousands-scale
  rows, written as RedisJSON documents (``workout:``, ``correlation:``,
  ``activity:`` key prefixes).
* **routes** — workout-route GPX files parsed lazily by
  :func:`~src.importer.parser.parse_apple_health_routes`; one JSON
  document per workout under the ``route:`` prefix.

The TimeSeries side is the hot path (millions of writes); it goes through
:mod:`~src.importer.pipeline`.  The JSON side is comparatively small and
goes through :mod:`~src.importer.document_loader`.

Typical usage::

    importer = HealthDataImporter(connection=redis_connect())
    importer.etl(write_feather=True)

    for f in importer.failures:
        print(f)

    # Retry only the failed data points (can be called in a new session
    # as long as data/export.feather and data/upload_failures.json exist).
    importer.retry_failed()

    # Overwrite existing data points with the latest values.
    importer.update()
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import redis
from pyarrow import feather

from ..redis_setup import ensure_ts_key
from .document_loader import (
    load_activities,
    load_correlations,
    load_routes,
    load_workouts,
)
from .parser import RECORD_ATTRS, parse_apple_health, parse_apple_health_routes
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

# Number of data types uploaded concurrently.  Each worker handles
# all batches for one type sequentially; types are independent.
MAX_UPLOAD_WORKERS: int = 4


class HealthDataImporter:
    """Import Apple Health export data into Redis.

    After calling :meth:`etl` or :meth:`update`, any upload failures are
    accessible via :attr:`failures` and persisted to :attr:`failures_file`
    so :meth:`retry_failed` can be called in a later Python session.

    Args:
        connection: :class:`redis.Redis` client used for all writes.
        data_dir: Sub-directory (relative to *working_dir*) that holds
            data files.
        in_file: Name of the Apple Health ZIP export inside *data_dir*.
        working_dir: Root directory; defaults to the current working
            directory.
        out_file: Name of the Feather cache file written to *data_dir*.
        failures_file: Name of the JSON file that persists upload failures
            between sessions.

    Example::

        # Conventional data/export.zip layout
        importer = HealthDataImporter(connection=redis_connect())
        importer.etl(write_feather=True)

        # Non-standard layout
        HealthDataImporter(
            data_dir="exports",
            in_file="2026-q1.zip",
            connection=redis_connect(),
        )

    """

    def __init__(
        self,
        connection: redis.Redis[str],
        data_dir: str = "data",
        in_file: str = "export.zip",
        working_dir: Path | str | None = None,
        out_file: str = "export.feather",
        failures_file: str = "upload_failures.json",
    ) -> None:
        """Initialise the importer and resolve its working paths.

        Args:
            connection: Redis client used for all writes.
            data_dir: Directory (relative to ``working_dir``) holding the
                Apple Health export and where intermediate / output files
                are written.
            in_file: Name of the Apple Health export archive within
                ``data_dir``.
            working_dir: Base directory the other paths are resolved
                against.  Defaults to the current working directory.
            out_file: Name of the cached Feather DataFrame written under
                ``data_dir``.
            failures_file: Name of the JSON file used to persist per-row
                upload failures so retries survive across runs.

        Raises:
            FileNotFoundError: If ``data_dir`` does not exist.

        """
        base = Path.cwd() if working_dir is None else Path(working_dir)

        self.data_dir: Path = base / data_dir
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory {self.data_dir} does not exist.")

        self.zip_file: Path = self.data_dir / in_file
        self.output_file: Path = self.data_dir / out_file
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
        from_date: pd.Timestamp | None = None,
    ) -> None:
        """Run the full Extract → Transform → Load pipeline.

        Uses :class:`DuplicatePolicy.FIRST` so that re-running the same
        export never overwrites existing data points.  To overwrite, use
        :meth:`update` instead.

        Side effects per call:

        1. Records → RedisTimeSeries (millions of points).
        2. Workouts, correlations, activity summaries → RedisJSON.
        3. Routes (GPX trackpoints) → RedisJSON, one document per workout.
        4. ``data/upload_failures.json`` is written if any uploads failed,
           or deleted if everything succeeded.

        When setting ``persist_failures=True`` any upload failures
        **overwrite** :attr:`failures_file` so that :meth:`retry_failed`
        can be called in another Python session::

            importer.etl(persist_failures=True)
            if importer.failures:
                importer.retry_failed()

        Args:
            write_feather: Persist the parsed records DataFrame as a
                Feather cache so subsequent runs skip the slow XML
                extraction step.  The Feather cache only stores the
                records DataFrame; workouts / correlations / activities /
                routes are always re-parsed from the ZIP.
            persist_failures: Persist a file that contains which data
                could not be uploaded as a JSON file.
            no_cache: If True, ignore any pre-existing cache and read the
                ZIP input from scratch.
            from_date: Lower date boundary to upload data from.

        Raises:
            FileNotFoundError: When neither the Feather cache nor the
                source ZIP can be found.
            NotImplementedError: If ``NaN`` values are found in any column
                other than ``unit`` / ``device``, indicating an unexpected
                schema change.
            ValueError: If a row without a unit has a numeric ``value``;
                only categorical string values are expected in that
                position.

        Example::

            importer.etl(write_feather=True)

        """
        records_df, correlations_df, workouts_df, activities_df, routes_df = (
            self._extract(
                write_feather=write_feather, no_cache=no_cache, from_date=from_date
            )
        )

        records_df.drop_duplicates(subset=RECORD_ATTRS, inplace=True)  # noqa: PD002
        transform(records_df)
        self.failures = _load(records_df, self.connection)
        # Document uploads have their own failure paths; aggregate them.
        self.failures.extend(load_workouts(self.connection, workouts_df))
        self.failures.extend(load_correlations(self.connection, correlations_df))
        self.failures.extend(load_activities(self.connection, activities_df))
        self.failures.extend(load_routes(self.connection, routes_df))

        if self.failures:
            logger.warning(
                "%s.etl incomplete: %d of %d datapoints failed to upload.",
                self.__class__,
                count_failures(self.failures, records_df),
                len(records_df),
            )

        if persist_failures:
            self._update_failures_file()

    def retry_failed(self, *, persist_failures: bool = True) -> None:
        """Re-attempt uploading every data point recorded in :attr:`failures_file`.

        Reads the failures JSON file written by the most recent
        :meth:`etl`, :meth:`update`, or previous :meth:`retry_failed`
        call, then re-attempts those rows only.  Document-level failures
        (workouts, correlations, …) are reported with ``batch_nr == -1``
        and are not retried by this method — re-run :meth:`etl` to
        reattempt those.

        Retry behaviour:

        * Reads the records DataFrame from ``out_file`` and selects the
          rows referenced by the failures file.
        * Runs :func:`transform` on the selection and calls
          :func:`_load` again.

        After the retry:

        * If **all** previously failed data points now succeed, the
          failures file is **deleted**.
        * If **some** failures remain, the file is **overwritten** with
          only the still-failing entries.

        Args:
            persist_failures: Persist a file that contains which data
                could not be uploaded as a JSON file.

        Raises:
            FileNotFoundError: When neither the Feather cache nor the
                source ZIP can be found, or if :attr:`failures_file` does
                not exist.
            NotImplementedError: If ``NaN`` values are found in any
                column other than ``unit`` / ``device``.
            ValueError: If a row without a unit has a numeric ``value``.

        Example::

            importer.retry_failed()
            if not importer.failures:
                print("All failures resolved.")

        """
        logger.warning(
            "Starting retry_failed.\n\tThis will only"
            " produce correct results if the feather file"
            " has not changed since the previous run."
        )

        self.failures = self._read_failures_file()
        if not self.failures:
            self._delete_failures_file()
            logger.warning("retry_failed: failures file is empty, nothing to retry.")
            return None

        records_df, *_ = self._extract(write_feather=False, no_cache=False)
        records_df.drop_duplicates(subset=RECORD_ATTRS, inplace=True)  # noqa: PD002

        row_selectors: list[int] = []
        for f in self.failures:
            match f:
                case BatchFailure(data_type=t, batch_nr=n) if n >= 0:
                    row_selectors.extend(
                        records_df[records_df["type"] == t].index[
                            n * BATCH_SIZE : (n + 1) * BATCH_SIZE
                        ]
                    )
                case RowFailure(row_index=i):
                    row_selectors.append(i)
                case _:
                    # Document-class failure (batch_nr == -1); skip here.
                    continue

        retry_df = records_df[records_df.index.isin(row_selectors)]
        transform(retry_df)

        r = self.connection
        n_before = count_failures(self.failures, records_df)
        self.failures = _load(df=retry_df, r=r, duplicate_policy=DuplicatePolicy.FIRST)

        n_after = count_failures(self.failures, records_df)
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
        from_date: pd.Timestamp | None = None,
    ) -> None:
        """Re-import the export, **overwriting** existing TimeSeries points.

        Identical to :meth:`etl` except it uses ``DuplicatePolicy.LAST``,
        which means any TimeSeries timestamp already present in Redis is
        overwritten with the new value rather than kept.  JSON documents
        (workouts, correlations, …) are written with ``JSON.SET`` and are
        always replaced regardless of duplicate policy.

        Args:
            write_feather: Persist the parsed records DataFrame as a
                Feather cache.
            persist_failures: Persist a file that contains which data
                could not be uploaded as a JSON file.
            no_cache: If True, ignore any pre-existing cache and read the
                ZIP input from scratch.
            from_date: Lower date boundary to upload data from.

        Raises:
            FileNotFoundError: When neither the Feather cache nor the
                source ZIP can be found.
            NotImplementedError: If ``NaN`` values are found in any
                column other than ``unit`` / ``device``.
            ValueError: If a row without a unit has a numeric ``value``.

        Example::

            importer.update()

        """
        records_df, correlations_df, workouts_df, activities_df, routes_df = (
            self._extract(
                write_feather=write_feather, no_cache=no_cache, from_date=from_date
            )
        )

        records_df.drop_duplicates(subset=RECORD_ATTRS, inplace=True)  # noqa: PD002
        transform(records_df)
        self.failures = _load(
            records_df,
            self.connection,
            duplicate_policy=DuplicatePolicy.LAST,
        )
        self.failures.extend(load_workouts(self.connection, workouts_df))
        self.failures.extend(load_correlations(self.connection, correlations_df))
        self.failures.extend(load_activities(self.connection, activities_df))
        self.failures.extend(load_routes(self.connection, routes_df))

        if self.failures:
            logger.warning(
                "%s.update incomplete: %d of %d datapoints failed to upload.",
                self.__class__,
                count_failures(self.failures, records_df),
                len(records_df),
            )

        if persist_failures:
            self._update_failures_file()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract(
        self,
        *,
        write_feather: bool,
        no_cache: bool,
        from_date: pd.Timestamp | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Parse the Apple Health export and return all five DataFrames.

        Returns a tuple of
        ``(records, correlations, workouts, activities, routes)``.  The
        ``routes`` DataFrame is parsed lazily by
        :func:`parse_apple_health_routes` only when at least one workout
        carries a route; otherwise it is an empty DataFrame.

        Feather caching is records-only — workouts / correlations /
        activities / routes are always parsed from the ZIP because their
        on-disk size is negligible compared to records and they are read
        far less often.

        Args:
            write_feather: Write a Feather cache file after parsing the
                ZIP export.
            no_cache: If True, ignore the pre-existing Feather cache and
                re-read from the ZIP.
            from_date: Date to process data from. If not set, all data are
                processed.

        Returns:
            ``(records_df, correlations_df, workouts_df, activities_df,
            routes_df)``.

        Raises:
            FileNotFoundError: When neither the Feather cache nor the
                source ZIP can be found.

        Example::

            records, corrs, workouts, activities, routes = importer._extract(
                write_feather=True, no_cache=False
            )

        """
        logger.info("Extracting export data...")

        # Feather cache fast path — only records, but it's the heavy one.
        if self.output_file.exists() and not no_cache:
            logger.info("Feather cache found; using cached records DataFrame.")
            records_df: pd.DataFrame = feather.read_feather(self.output_file)  # type: ignore[no-untyped-call]

            # We still need the document data — re-parse from ZIP if available.
            if self.zip_file.exists():
                _, correlations_df, workouts_df, activities_df = parse_apple_health(
                    zip_path=self.zip_file,
                    from_date=from_date,
                    skip_records=True,
                )
                routes_df = self._extract_routes(workouts_df)
            else:
                logger.info(
                    "ZIP not available alongside Feather cache; skipping "
                    "document tables."
                )
                empty = pd.DataFrame()
                correlations_df = workouts_df = activities_df = routes_df = empty
            return records_df, correlations_df, workouts_df, activities_df, routes_df

        if not self.zip_file.exists():
            raise FileNotFoundError(
                f"No export file found. Expected one of:\n"
                f"  {self.output_file}\n"
                f"  {self.zip_file}"
            )

        logger.info("Parsing ZIP export...")
        records_df, correlations_df, workouts_df, activities_df = parse_apple_health(
            zip_path=self.zip_file
        )
        routes_df = self._extract_routes(workouts_df)

        if write_feather:
            logger.info("Writing Feather cache to %s", self.output_file)
            records_df.to_feather(self.output_file)

        return records_df, correlations_df, workouts_df, activities_df, routes_df

    def _extract_routes(self, workouts_df: pd.DataFrame) -> pd.DataFrame:
        """Parse GPX route files referenced by *workouts_df*.

        Returns an empty DataFrame if no workouts have routes or if the
        ZIP file is absent (the records-only feather-cache path).

        Args:
            workouts_df: Workouts DataFrame whose ``route`` column may
                contain dicts with a ``files`` list.

        Returns:
            A DataFrame of trackpoints as produced by
            :func:`parse_apple_health_routes`, or an empty DataFrame if
            no routes are referenced.

        """
        if workouts_df.empty or "route" not in workouts_df.columns:
            return pd.DataFrame()
        if not self.zip_file.exists():
            return pd.DataFrame()

        route_paths = [
            path.lstrip("/")
            for route in workouts_df["route"].dropna()
            for path in (route.get("files") or [])
        ]
        if not route_paths:
            return pd.DataFrame()

        logger.info("Parsing %d workout route GPX file(s).", len(route_paths))
        return parse_apple_health_routes(self.zip_file, paths=route_paths)

    def _update_failures_file(self) -> None:
        """Persist or clear the failures file to match in-memory state.

        Writes :attr:`failures` to disk when any failures are recorded,
        and deletes the file when the list is empty so a clean run leaves
        no stale failures behind.
        """
        if self.failures:
            self._write_failures_file(self.failures)
        else:
            self._delete_failures_file()

    def _write_failures_file(self, failures: list[UploadFailure]) -> None:
        """Serialise *failures* and write them to :attr:`failures_file`.

        Overwrites any existing file so the file always reflects the
        current state.
        """
        self.failures_file.write_text(failures_to_json(failures), encoding="utf-8")
        logger.info("Wrote %d failure(s) to %s", len(failures), self.failures_file)

    def _delete_failures_file(self) -> None:
        """Delete :attr:`failures_file` if it exists.

        Called after a fully successful load or a fully successful retry
        so no stale file misleads a future :meth:`retry_failed` call.
        """
        if self.failures_file.exists():
            self.failures_file.unlink()
            logger.info("Deleted failures file %s (all resolved).", self.failures_file)

    def _read_failures_file(self) -> list[UploadFailure]:
        """Read and deserialise the failures file.

        Returns:
            List of :class:`~.response.UploadFailure` objects.

        Raises:
            FileNotFoundError: If :attr:`failures_file` does not exist.
            ValueError: If the file contains an unrecognised ``kind`` value.

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


def _upload_type(
    data_type: str,
    batch_df: pd.DataFrame,
    r: redis.Redis[str],
    duplicate_policy: DuplicatePolicy,
) -> list[UploadFailure]:
    """Upload all batches for one data type and return any failures.

    Intended to be called from a :class:`~concurrent.futures.ThreadPoolExecutor`
    worker.  Each call is self-contained: it provisions its two TimeSeries keys
    (setting the duplicate policy so ``TS.MADD`` uses the right conflict
    strategy), then loops over BATCH_SIZE slices of *batch_df* issuing one
    ``TS.MADD`` per slice.

    The :class:`redis.Redis` client is shared across workers via its internal
    :class:`~redis.connection.ConnectionPool`; individual ``TS.MADD`` calls
    each check out a connection, send the command, receive the reply, and
    return the connection — which is thread-safe.

    Args:
        data_type: The HK type identifier string (e.g.
            ``"HKQuantityTypeIdentifierHeartRate"``).
        batch_df: All transformed rows for *data_type*.
        r: Shared Redis client.  Thread-safe for individual commands.
        duplicate_policy: Write-conflict strategy; sets the key-level policy
            via :func:`~src.redis_setup.ensure_ts_key` before the first
            ``TS.MADD`` for this type.

    Returns:
        List of :class:`~.response.UploadFailure` objects; empty on
        full success.

    Raises:
        ValueError: If ensure_ts_label finds that labels don't match.

    """
    n = len(batch_df)
    rts = r.ts()
    failures: list[UploadFailure] = []

    sample = batch_df.iloc[0]
    base_labels: dict[str, str] = {
        "unit": str(sample["unit"]),
        "identifier": data_type,
        "group": str(sample["group"]),
    }
    ensure_ts_key(
        r,
        f"ts:{data_type}:start",
        labels=base_labels | {"event_type": "start"},
        duplicate_policy=duplicate_policy.value,
    )
    ensure_ts_key(
        r,
        f"ts:{data_type}:end",
        labels=base_labels | {"event_type": "end"},
        duplicate_policy=duplicate_policy.value,
    )

    logger.info(
        "%s: uploading %d rows in %d batch(es).",
        data_type,
        n,
        -(-n // BATCH_SIZE),
    )

    for i in range(0, n, BATCH_SIZE):
        _df = batch_df.iloc[i : i + BATCH_SIZE]
        try:
            row_failures = upload_batch(rts, _df)
            if row_failures:
                logger.warning(
                    "	Batch %d: %d/%d row(s) failed.",
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
                "\t\tBatch %d: could not resolve failures: %s",
                i // BATCH_SIZE + 1,
                batch_failure,
            )
            failures.append(batch_failure)
        except redis.RedisError as exc:
            batch_failure = BatchFailure(
                data_type=data_type, batch_nr=i // BATCH_SIZE, error=str(exc)
            )
            logger.exception(
                "\t\tBatch %d: entire batch failed: %s",
                i // BATCH_SIZE + 1,
                batch_failure,
            )
            failures.append(batch_failure)

    return failures


def _load(
    df: pd.DataFrame,
    r: redis.Redis[str],
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.FIRST,
) -> list[UploadFailure]:
    """Batch-upload all records to Redis TimeSeries using worker threads.

    Fans out across unique data types using a
    :class:`~concurrent.futures.ThreadPoolExecutor` with
    :data:`MAX_UPLOAD_WORKERS` threads.  Each worker calls
    :func:`_upload_type`, which provisions the two TimeSeries keys for that
    type (setting the duplicate policy for ``TS.MADD``), then uploads all
    batches for that type sequentially.

    Types are independent — they write to different keys — so there is no
    contention between workers.  The shared :class:`redis.Redis` client is
    thread-safe: each ``TS.MADD`` call checks out a connection from the
    client's internal pool, sends the command, and returns the connection.

    Args:
        df: Transformed health records DataFrame.
        r: Shared Redis client.
        duplicate_policy: Write-conflict strategy passed to
            :func:`_upload_type` and ultimately to
            :func:`~src.redis_setup.ensure_ts_key`.

    Returns:
        Aggregated list of :class:`~.response.UploadFailure` objects from all
        workers; empty on full success.

    Example::

        failures = _load(df, redis_client, DuplicatePolicy.LAST)

    """
    logger.info(
        "Loading data to Redis TimeSeries (duplicate_policy=%s, workers=%d)...",
        duplicate_policy.value,
        MAX_UPLOAD_WORKERS,
    )
    failures: list[UploadFailure] = []

    data_types = df["type"].unique()
    logger.info("Found %d data type(s).", len(data_types))

    with ThreadPoolExecutor(max_workers=MAX_UPLOAD_WORKERS) as pool:
        future_to_type = {
            pool.submit(
                _upload_type,
                dt,
                df[df["type"] == dt],
                r,
                duplicate_policy,
            ): dt
            for dt in data_types
            if len(df[df["type"] == dt]) > 0
        }

        for future in as_completed(future_to_type):
            data_type = future_to_type[future]
            try:
                failures.extend(future.result())
            except Exception as exc:  # noqa: BLE001
                batch_failure = BatchFailure(
                    data_type=data_type, batch_nr=0, error=str(exc)
                )
                logger.exception("Unexpected error uploading %s: %s", data_type, exc)
                failures.append(batch_failure)

    return failures
