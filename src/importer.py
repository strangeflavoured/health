import logging
import os
from io import BytesIO
from pathlib import Path

import pandas as pd
import redis
from apple_health_exporter import health_xml_to_feather
from pyarrow import feather
from redis.commands.timeseries import TimeSeries

from connection import redis_connect
from models import BatchFailure, DuplicatePolicy, UploadFailure, failures_to_json
from pipeline import upload_batch
from transform import transform

logger = logging.getLogger(__name__)


class HealthDataImporter:
    def __init__(
        self,
        working_dir: Path | str | None = None,
        data_dir: str = "data",
        in_file: str = "export.zip",
        out_file: str = "export.feather",
        failures_file: str = "upload_failures.json",
        connection: redis.Redis | None = None,
    ) -> None:

        base = Path.cwd() if working_dir is None else Path(working_dir)

        self.data_dir: Path = base / data_dir
        if not os.path.exists(self.data_dir):
            raise FileNotFoundError(f"Data directory {self.data_dir} does not exist.")

        self.zip_file: Path = self.data_dir / in_file
        self.output_file: Path = self.data_dir / out_file
        self.failures_file: Path = self.data_dir / failures_file
        self.connection: redis.Redis | None = connection

        # In-memory mirror of the failures file.
        self.failures: list[UploadFailure] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(
        self,
        url: str | None = None,
        *,
        tls: bool = False,
        tls_client_cert: str | None = None,
        tls_client_key: str | None = None,
        tls_ca_cert: str | None = None,
        tls_check_hostname: bool = True,
        force: bool = False,
    ) -> redis.Redis:
        """Return the cached Redis connection, creating one if necessary.

        All ``tls_*`` and ``url`` arguments are forwarded directly to
        :func:`~connection.redis_connect`; see that function for full
        documentation on connection modes and TLS path resolution.

        Args:
            url: Full Redis connection URL.  ``None`` uses env-var mode.
            tls: Wrap the connection in TLS.
            tls_client_cert: Path to PEM client certificate (mTLS only).
            tls_client_key: Path to PEM client private key (mTLS only).
            tls_ca_cert: Path to CA bundle; ``None`` uses the system store.
            tls_check_hostname: Enforce SNI hostname verification.
                **Do not set to** ``False`` **in production.**
            force: When ``True``, always create a fresh connection even if
                one is already cached in :attr:`connection`.

        Returns:
            A connected :class:`redis.Redis` instance.

        Raises:
            ~connection.RedisEnvError: If env-var mode is used and a required
                variable is missing.
            ~connection.TLSConfigError: If TLS is active and TLS paths cannot
                be resolved.

        Example::

            r = importer.connect(tls=True)

        """
        if self.connection is None or force:
            self.connection = redis_connect(
                url=url,
                tls=tls,
                tls_client_cert=tls_client_cert,
                tls_client_key=tls_client_key,
                tls_ca_cert=tls_ca_cert,
                tls_check_hostname=tls_check_hostname,
            )
        return self.connection

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
        self.failures = self._load(df, self.connect())

        if self.failures:
            logger.warning(
                "%s.etl incomplete: %d of %d datapoints failed to upload.",
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
        buffer = BytesIO()
        health_xml_to_feather(zip_file=self.zip_file, output_file=buffer)

        if write_feather:
            logger.info("Writing Feather cache to %s", self.output_file)
            self.output_file.write_bytes(buffer.getbuffer())

        return feather.read_feather(buffer)

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

    def _update_failure_file(self) -> None:
        if self.failures:
            self._write_failure_file(self.failures)
        else:
            self._delete_failure_file()

    def _write_failure_file(self, failures: list[UploadFailure]) -> None:
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

    def _delete_failure_file(self) -> None:
        """Delete :attr:`failures_file` if it exists.

        Called after a fully successful load or a fully successful retry to
        ensure no stale file misleads a future :meth:`retry_failed` call.

        Example::

            importer._delete_failures_file()
        """
        if self.failures_file.exists():
            self.failures_file.unlink()
            logger.info("Deleted failures file %s (all resolved).", self.failures_file)


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

        failures = importer._load(df, importer.connect(), DuplicatePolicy.LAST)

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
