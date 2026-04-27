"""Import Apple Health Export Data to Redis."""

import datetime
import logging

from src.connection import redis_connect
from src.importer import HealthDataImporter

if __name__ == "__main__":
    # configure logging
    logger = logging.getLogger(__name__)

    warnings_logger = logging.getLogger("py.warnings")
    logging.captureWarnings(capture=True)

    now = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    logging.basicConfig(
        filename=f"/home/health/output/{now}_report.log",
        level=logging.INFO,
        force=True,
        format="%(asctime)s %(name)s[%(process)d] %(levelname)s %(message)s",
    )

    r = redis_connect(tls=True)
    if r.ping():
        try:
            HealthDataImporter(connection=r).etl(write_feather=True)
            logger.info("Successfully imported Apple Health Export Data.")
        except Exception as e:  # noqa: BLE001
            warnings_logger.error(e)
            if isinstance(e, ExceptionGroup):
                for exc in e.exceptions:
                    warnings_logger.error(exc)
            logger.info("FAILED to import Apple Health Export Data.")
