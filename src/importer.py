import logging
import os
from io import BytesIO
from pathlib import Path

import pandas as pd
import redis
from apple_health_exporter import health_xml_to_feather
from pyarrow import feather

from connection import redis_connect
from transform import transform

logger = logging.getLogger(__name__)


class HealthDataImporter:
    def __init__(
        self,
        working_dir: Path | str | None = None,
        data_dir: str = "data",
        in_file: str = "export.zip",
        out_file: str = "export.feather",
        connection: redis.Redis | None = None,
    ) -> None:

        base = Path.cwd() if working_dir is None else Path(working_dir)

        self.data_dir: Path = base / data_dir
        if not os.path.exists(self.data_dir):
            raise FileNotFoundError(f"Data directory {self.data_dir} does not exist.")

        self.zip_file: Path = self.data_dir / in_file
        self.output_file: Path = self.data_dir / out_file
        self.connection: redis.Redis | None = connection

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
