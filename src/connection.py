"""Redis connection from inside container network."""

import logging
import os
import ssl as ssl_module
from pathlib import Path

import redis

logger = logging.getLogger(__name__)


def docker_redis_connect() -> redis.Redis:
    """Connect to redis from inside sandbox container."""
    conn_args = {
        "host": os.getenv("REDIS_HOST"),
        "port": int(os.getenv("REDIS_PORT")),
        "db": int(os.getenv("REDIS_DB")),
        "username": "app",
        "password": Path("/run/secrets/app_password").read_text().strip(),
        "decode_responses": True,
    }

    mtls_kwargs = {
        "ssl": True,
        "ssl_certfile": "/run/secrets/app.pem",
        "ssl_keyfile": "/run/secrets/app.key",
        "ssl_ca_certs": "/run/secrets/ca.pem",
        "ssl_check_hostname": True,
        "ssl_cert_reqs": ssl_module.CERT_REQUIRED,
    }

    logger.info(
        f"Connecting to redis://{conn_args['username']}:***@{conn_args['host']}:{conn_args['port']}/{conn_args['db']}"
    )

    return redis.Redis(
        **conn_args,
        **mtls_kwargs,
    )
