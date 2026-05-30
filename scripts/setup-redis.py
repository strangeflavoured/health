"""Provision RediSearch indexes and TimeSeries labels for the Apple Health dataset."""

import argparse
import logging

import redis
from setup_logger import configure_logging

from src.connection import docker_redis_connect
from src.redis_setup import (
    print_status,
    records_labels,
    setup_indexes,
    upsert_ts_labels,
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Provision RediSearch indexes and TimeSeries labels."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes (default is dry-run).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force index setup when supported.",
    )
    args = parser.parse_args()

    dry_run = not args.execute
    force = args.force

    configure_logging(__file__)
    logger = logging.getLogger(__name__)

    r = docker_redis_connect()
    try:
        r.ping()
    except redis.RedisError as e:
        logger.error(e)
        logger.warning("FAILED to connect to Redis.")
        raise e

    if dry_run:
        logger.info("dry-run mode — no changes will be made")

    setup_indexes(r, dry_run=dry_run, force=force)
    upsert_ts_labels(r, records_labels(), dry_run=dry_run)

    if not dry_run:
        print_status(r)
