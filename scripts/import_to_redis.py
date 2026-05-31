"""Import Apple Health Export Data to Redis."""

import logging

import redis
from setup_logger import configure_logging, log_peak_memory

from src.connection import docker_redis_connect
from src.importer import HealthDataImporter

if __name__ == "__main__":
    # set up logger
    configure_logging(__file__)
    logger = logging.getLogger(__name__)

    # test connection
    r = docker_redis_connect()
    try:
        r.ping()
    except redis.RedisError as e:
        logger.error(e)
        logger.warning("FAILED to connect to Redis.")
        raise e

    importer = HealthDataImporter(connection=r)
    if importer.failures_file.exists():
        importer.retry_failed()
        logger.info("Successfully imported previously failed Apple Health data.")
        log_peak_memory(logger)
    else:
        try:
            importer.etl(write_feather=True)
            logger.info("Successfully imported Apple Health Export Data.")
        except Exception as e:  # noqa: BLE001
            logger.error(e)
            if isinstance(e, ExceptionGroup):
                for exc in e.exceptions:
                    logger.error(exc)
            logger.warning("FAILED to import Apple Health Export Data.")

    log_peak_memory(logger)
