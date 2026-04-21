"""Health Data Importer.

Uploads Apple Health ``export.zip`` data to a local Redis TimeSeries database
via an Extract → Transform → Load (ETL) pipeline.

Typical usage::

    importer = HealthDataImporter()
    importer.etl(write_feather=True)

    for f in importer.failures:
        print(f)

    # Retry only the failed data points (can be called in a new session)
    remaining = importer.retry_failed(df)

    # Overwrite existing data points with the latest values
    importer.update()
"""

import logging
from pathlib import Path

import pandas as pd
import redis
from pyarrow import feather
from redis.commands.timeseries import TimeSeries

from .models import (
    BatchFailure,
    DuplicatePolicy,
    RowFailure,
    UploadFailure,
    failures_from_json,
    failures_to_json,
)
from .parser import parse_apple_health
from .pipeline import upload_batch
from .transform import transform

logger = logging.getLogger(__name__)


class HealthDataImporter:
    """Import Apple Health export data into Redis TimeSeries.

    After calling :meth:`etl` or :meth:`update`, any upload failures are
    accessible via :attr:`failures` and persisted to :attr:`failures_file`
    so that :meth:`retry_failed` can be called in a later Python session.

    Args:
        data_dir: Sub-directory (relative to *working_dir*) that holds data
            files.
        in_file: Name of the Apple Health ZIP export inside *data_dir*.
        connection: :class:`redis.Redis` to connect to.
        working_dir: Root directory; defaults to the current working directory.
        out_file: Name of the Feather cache file written to *data_dir*.
        failures_file: Name of the JSON file that persists upload failures
            between sessions.


    Example::

        importer = HealthDataImporter(
            data_dir="data",
            in_file="export.zip",
            connection=redis_connect()
        )
        importer.etl(write_feather=True)

    """

    def __init__(
        self,
        data_dir: str,
        in_file: str,
        connection: redis.Redis,
        working_dir: Path | str | None = None,
        out_file: str = "export.feather",
        failures_file: str = "upload_failures.json",
    ) -> None:

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
    ) -> None:
        """Run the full Extract → Transform → Load pipeline.

        Uses ``duplicate_policy="FIRST"`` so that re-running the same export
        never overwrites existing data points.  To overwrite, use
        :meth:`update` instead.

        When setting `persist_failures=True` any upload failures **overwrite**
        :attr:`failures_file` so that :meth:`retry_failed` can be called in
        another Python session::

            importer.etl(persist_failures=True)
            # failures are persisted at data/upload_failures.json and as
            # instance attribute
            if importer.failures:
                importer.retry_failed(df)

        Args:
            write_feather: Persist the parsed data as a Feather cache so that
                subsequent runs skip the slow XML extraction step.
            persist_failures: Persist a file that contains which data could not
                be uploaded as a JSON file.

        Raises:
            FileNotFoundError: When neither the Feather cache nor the source
                ZIP can be found.
            NotImplementedError: If ``NaN`` values are found in any column other
                than ``unit``, indicating an unexpected schema change.
            ValueError: If a row without a unit has a numeric ``value``; only
                categorical string values are expected in that position.

        Example::

            importer.etl(write_feather=True)

        """
        df = self._extract(write_feather=write_feather)
        self._transform(df)
        self.failures = self._load(df, self.connection)

        if self.failures:
            logger.warning(
                "%s.etl incomplete: %d of %d datapoints failed to upload.",
                self.__class__,
                len(self.failures),
                len(df),
            )

        if persist_failures:
            self._update_failures_file()

    def retry_failed(self, *, persist_failures: bool = True) -> None:
        """Re-attempt uploading every data point recorded in :attr:`failures_file`.

        Reads the failures JSON file written by the most recent :meth:`etl`,
        :meth:`update`, or previous :meth:`retry_failed` call which **overwrites**
        :attr:`failures`. This method can be called in a completely separate Python
        session as long as the failures file and the Feather cache still exist::

            # New session — no need to re-run etl()
            importer = HealthDataImporter()
            df = feather.read_feather("data/export.feather")
            importer.retry_failed()

        Retry behaviour:

        Loads dataframe from `self.out_file` and finds entries that failed to upload,
        and passes this subset to :meth:`_load`.

        After the retry:

        * If **all** previously failed data points now succeed, the failures
          file is **deleted**.
        * If **some** failures remain, the file is **overwritten** with only
          the still-failing entries.

        Args::
            persist_failures: Persist a file that contains which data could not
                be uploaded as a JSON file.

        Raises::
            FileNotFoundError: When neither the Feather cache nor the source
                ZIP can be found, or if :attr:`failures_file` does not exist.
            NotImplementedError: If ``NaN`` values are found in any column other
                than ``unit``, indicating an unexpected schema change.
            ValueError: If a row without a unit has a numeric ``value``; only
                categorical string values are expected in that position.

        Example::

            importer.retry_failed()
            if not importer.failures:
                print("All failures resolved.")

        """
        logger.warning(
            "Starting retry_failed.\nThis will only"
            " produce correct results if feather file"
            " has not changed since previous run."
        )

        # Always read from disk so the method works across sessions.
        self.failures = self._read_failures_file()
        if not self.failures:
            self._delete_failures_file()
            logger.warning("retry_failed: failures file is empty, nothing to retry.")
            return None

        df = self._extract(write_feather=False)
        self._transform(df)

        type_selectors = []
        row_selectors = []
        for f in self.failures:
            if isinstance(f, BatchFailure):
                type_selectors.append(f.data_type)
            elif isinstance(f, RowFailure):
                row_selectors.append(f.row_index)

        retry_df = df[df["type"].isin(type_selectors) | df.index.isin(row_selectors)]

        r = self.connection
        n_before = len(self.failures)
        self.failures = self._load(
            df=retry_df, r=r, duplicate_policy=DuplicatePolicy.FIRST
        )

        n_resolved = n_before - len(self.failures)
        logger.info(
            "retry_failed complete: %d/%d failure(s) resolved, %d remaining.",
            n_resolved,
            n_before,
            len(self.failures),
        )

        if persist_failures:
            self._update_failures_file()

    def update(
        self,
        *,
        write_feather: bool = False,
        persist_failures: bool = True,
    ) -> None:
        """Re-import the export, **overwriting** existing data points.

        Identical to :meth:`etl` except it uses ``duplicate_policy="LAST"``,
        which means any timestamp that already exists in Redis is overwritten
        with the new value rather than kept.

        Args:
            write_feather: Persist the parsed data as a Feather cache.
            persist_failures: Persist a file that contains which data could not
                be uploaded as a JSON file.

        Raises:
            FileNotFoundError: When neither the Feather cache nor the source
                ZIP can be found.
            NotImplementedError: If ``NaN`` values are found in any column other
                than ``unit``, indicating an unexpected schema change.
            ValueError: If a row without a unit has a numeric ``value``; only
                categorical string values are expected in that position.

        Example::

            importer.update()

        """
        df = self._extract(write_feather=write_feather)
        self._transform(df)
        self.failures = self._load(
            df,
            self.connection,
            duplicate_policy=DuplicatePolicy.LAST,
        )

        if self.failures:
            logger.warning(
                "%s.update incomplete: %d of %d datapoints failed to upload.",
                self.__class__,
                len(self.failures),
                len(df),
            )

        if persist_failures:
            self._update_failures_file()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract(self, *, write_feather: bool) -> pd.DataFrame:
        """Parse the Apple Health export and return a raw DataFrame.

        Prefers the Feather cache at :attr:`output_file` to avoid re-running
        the slow XML-to-Feather conversion.  Falls back to the ZIP export at
        :attr:`zip_file` if no cache exists.

        Args:
            write_feather: Write a Feather cache file after parsing the ZIP
                export.

        Returns:
            Raw health records as a :class:`~pandas.DataFrame`.

        Raises:
            FileNotFoundError: When neither the Feather cache nor the source
                ZIP can be found.

        Example::

            df = importer._extract(write_feather=True)

        """
        logger.info("Extracting export data...")
        if self.output_file.exists():
            logger.info("Feather cache found; skipping XML conversion.")
            return feather.read_feather(self.output_file)

        if not self.zip_file.exists():
            raise FileNotFoundError(
                f"No export file found. Expected one of:\n"
                f"  {self.output_file}\n"
                f"  {self.zip_file}"
            )

        logger.info("Converting ZIP export to Feather format...")
        df = parse_apple_health(zip_path=self.zip_file)

        if write_feather:
            logger.info("Writing Feather cache to %s", self.output_file)
            df.to_feather(self.output_file)

        return df

    @staticmethod
    def _transform(df: pd.DataFrame) -> None:
        """Wrapper for :func:`transform.transform`."""  # noqa: D401
        transform(df)

    @staticmethod
    def _load(
        df: pd.DataFrame,
        r: redis.Redis,
        duplicate_policy: DuplicatePolicy = DuplicatePolicy.FIRST,
    ) -> list[UploadFailure]:
        """Wrapper for :func:`_load`."""  # noqa: D401
        return _load(df, r, duplicate_policy)

    def _update_failures_file(self) -> None:
        if self.failures:
            self._write_failures_file(self.failures)
        else:
            self._delete_failures_file()

    def _write_failures_file(self, failures: list[UploadFailure]) -> None:
        """Serialise *failures* and write them to :attr:`failures_file`.

        Overwrites any existing file so the file always reflects the current state.

        Args:
            failures: List of :class:`~models.UploadFailure` objects to
                persist.

        Example::

            importer._write_failures_file(importer.failures)

        """
        self.failures_file.write_text(failures_to_json(failures), encoding="utf-8")
        logger.info("Wrote %d failure(s) to %s", len(failures), self.failures_file)

    def _delete_failures_file(self) -> None:
        """Delete :attr:`failures_file` if it exists.

        Called after a fully successful load or a fully successful retry to
        ensure no stale file misleads a future :meth:`retry_failed` call.

        Example::

            importer._delete_failures_file()
        """
        if self.failures_file.exists():
            self.failures_file.unlink()
            logger.info("Deleted failures file %s (all resolved).", self.failures_file)

    def _read_failures_file(self) -> list[UploadFailure]:
        """Read and deserialise the failures file.

        Returns:
            List of :class:`~models.UploadFailure` objects.

        Raises:
            FileNotFoundError: If :attr:`failures_file` does not exist.
            ValueError: If the file contains an unrecognised ``kind`` value.

        Example::

            failures = importer._read_failures_file()

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

    Each unique ``type`` is uploaded in its own pipeline transaction
    so that a failure in one type does not abort the others. Returns
    a list of ``UploadFailure`` objects.

    Args:
        df: Transformed health records.
        r: Active Redis connection.
        duplicate_policy: ``"FIRST"`` (default, used by :meth:`etl` and
            :meth:`retry_failed`) or ``"LAST"`` (used by :meth:`update`).

    Returns:
        A new list of UploadFailure objects. Empty if all data points
        were successfully uploaded.

    Example::

        failures = importer._load(df, importer.connection, DuplicatePolicy.LAST)

    """
    logger.info(
        "Loading data to Redis TimeSeries (duplicate_policy=%s)...",
        duplicate_policy.value,
    )
    rts: TimeSeries = r.ts()
    failures: list[UploadFailure] = []

    for data_type in df["type"].unique():
        logger.info("Uploading batch for type: %s", data_type)
        batch_df = df[df["type"] == data_type]

        try:
            row_failures = upload_batch(
                rts,
                batch_df,
                duplicate_policy=duplicate_policy,
            )

            if row_failures:
                logger.warning(
                    "Type %s batch: %d/%d row(s) failed.",
                    data_type,
                    len(row_failures),
                    len(batch_df),
                )

                failures.extend(row_failures)
        except IndexError as exc:
            batch_failure = BatchFailure(data_type=data_type, error=str(exc))
            logger.exception(
                "Could not resolve failures for type '%s': %s",
                data_type,
                batch_failure,
            )
            failures.append(batch_failure)

        except redis.RedisError as exc:
            batch_failure = BatchFailure(data_type=data_type, error=str(exc))
            logger.exception(
                "Entire batch for type '%s' failed: %s",
                data_type,
                batch_failure,
            )
            failures.append(batch_failure)

    return failures
