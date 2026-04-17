import logging
import os
from io import BytesIO
from pathlib import Path

import pandas as pd
from apple_health_exporter import health_xml_to_feather
from pyarrow import feather

from transform import transform

logger = logging.getLogger(__name__)


class HealthDataImporter:
    def __init__(
        self,
        working_dir: Path | str | None = None,
        data_dir: str = "data",
        in_file: str = "export.zip",
        out_file: str = "export.feather",
    ) -> None:

        base = Path.cwd() if working_dir is None else Path(working_dir)

        self.data_dir: Path = base / data_dir
        if not os.path.exists(self.data_dir):
            raise FileNotFoundError(f"Data directory {self.data_dir} does not exist.")

        self.zip_file: Path = self.data_dir / in_file
        self.output_file: Path = self.data_dir / out_file

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
