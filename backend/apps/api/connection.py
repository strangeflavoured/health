"""Redis client initialisation for the API app.

Wraps docker_redis_connect() from src/connection.py in a module-level
singleton so the mTLS and ACL handshake happens once per process rather
than on every request. Celery workers each get their own instance.
"""

import logging

import redis

from src.connection import docker_redis_connect

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Return a shared Redis client, creating it on first call.

    Delegates to docker_redis_connect() from src/connection.py, which
    handles mTLS and ACL via Docker secrets. The client is cached at
    module level so the connection is established once per process
    (each Celery worker or Django process gets its own instance).

    Returns:
        redis.Redis: Authenticated, mTLS-secured client.

    Raises:
        redis.exceptions.ConnectionError: If the connection cannot be
            established on first call.

    """
    global _client
    if _client is None:
        logger.info("Initialising Redis client")
        _client = docker_redis_connect()
    return _client
