"""Import Apple Health Export Data to Redis."""

import logging

import redis
from setup_logger import configure_logging

from src.connection import redis_connect
from src.importer import HealthDataImporter

if __name__ == "__main__":
    configure_logging(__file__)
    logger = logging.getLogger(__name__)

    r = redis_connect(tls=True)

    try:
        r.ping()
    except redis.RedisError as e:
        logger.error(e)
        logger.warning("FAILED to connect to Redis.")
        raise e

    try:
        HealthDataImporter(connection=r).etl(write_feather=True)
        logger.info("Successfully imported Apple Health Export Data.")
    except Exception as e:  # noqa: BLE001
        logger.error(e)
        if isinstance(e, ExceptionGroup):
            for exc in e.exceptions:
                logger.error(exc)
        logger.warning("FAILED to import Apple Health Export Data.")
