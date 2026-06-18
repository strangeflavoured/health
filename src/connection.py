"""Redis connection from inside container network."""

from __future__ import annotations

import logging
import os
import ssl as ssl_module
from pathlib import Path

import redis

logger = logging.getLogger(__name__)


def docker_redis_connect(acl_user: str = "app") -> redis.Redis[str]:
    """Connect to redis from inside sandbox container.

    Args:
        acl_user (str): Account to connect to, defaults to `app`.

    """
    conn_args: dict[str, str | int | bool] = {
        "host": os.environ["REDIS_HOST"],
        "port": int(os.environ["REDIS_PORT"]),
        "db": int(os.environ["REDIS_DB"]),
        "username": acl_user,
        "password": Path(f"/run/secrets/{acl_user}_password").read_text().strip(),
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
    client: redis.Redis[str] = redis.Redis(**conn_args, **mtls_kwargs)  # type: ignore[call-overload]  # ty: ignore[no-matching-overload, invalid-assignment]
    return client
