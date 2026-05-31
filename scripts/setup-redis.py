"""Provision RediSearch indexes and TimeSeries labels for the Apple Health dataset.

Usage::

    python scripts/setup-redis.py                # dry-run; nothing is written
    python scripts/setup-redis.py --execute      # actually create indexes
    python scripts/setup-redis.py --execute --force
                                                 # drop existing indexes
                                                 # before recreating

Flags
-----
--execute
    Disable dry-run mode and actually issue mutating commands against Redis.
    Without this flag, the script only logs what it *would* do.

--force
    Drop indexes that already exist and recreate them.  Only meaningful with
    ``--execute``.  Use this after changing index field definitions in
    :mod:`src.redis_setup`.

The script always finishes with a status table written to the log when running
in execute mode.
"""

from __future__ import annotations

import argparse
import logging
import sys

import redis
from setup_logger import configure_logging

from src.connection import docker_redis_connect
from src.redis_setup import (
    print_status,
    records_labels,
    setup_indexes,
    upsert_ts_labels,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command-line arguments for the setup script."""
    parser = argparse.ArgumentParser(
        prog="setup-redis.py",
        description=(
            "Provision RediSearch indexes and TimeSeries labels for the "
            "Apple Health dataset.  Dry-run by default — pass --execute to "
            "actually write to Redis."
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Disable dry-run mode and actually write to Redis.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Drop and recreate indexes that already exist (requires --execute).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point — parse args, connect, and run setup.

    Returns:
        Process exit code (0 on success, non-zero on failure).

    """
    args = _parse_args(argv)
    dry_run = not args.execute
    force = args.force

    configure_logging(__file__)
    logger = logging.getLogger(__name__)

    r = docker_redis_connect(acl_user="admin")
    try:
        r.ping()
    except redis.RedisError as exc:
        logger.error(exc)
        logger.warning("FAILED to connect to Redis.")
        return 1

    if dry_run:
        logger.info("dry-run mode — no changes will be made")
        if force:
            logger.warning("--force is ignored in dry-run mode (use --execute).")

    setup_indexes(r, dry_run=dry_run, force=force)
    upsert_ts_labels(r, records_labels(), dry_run=dry_run)

    if not dry_run:
        print_status(r)

    return 0


if __name__ == "__main__":
    sys.exit(main())
