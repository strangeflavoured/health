"""Redis connection factory for the Apple Health importer.

Supports two connection modes:

* **URL mode** — pass a full ``rediss://`` / ``redis://`` URL.
* **Env-var mode** (default) — reads ``REDIS_*`` variables from the
  environment (populated via a ``.env`` file or the shell).

All environment variable names are declared as module-level ``_ENV_*``
constants.  Environment variables are read lazily inside
:func:`redis_connect` (after a single :func:`~dotenv.load_dotenv` call),
never at module import time:

* :func:`_load_tls_env` — reads the four ``REDIS_*`` TLS file/path names.  Called
  whenever TLS is active, regardless of connection mode.  Raises
  :class:`TLSConfigError` on missing mTLS paths.
* :func:`_load_conn_env` — reads ``REDIS_HOST/PORT/DB/PASSWORD`` from `.env`.  Called
  only in env-var mode (``url=None``).  Raises :class:`RedisEnvError` on
  missing variables.
"""

import logging
import os
import ssl as ssl_module
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import redis
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment variable names — single source of truth
# ---------------------------------------------------------------------------

_ENV_HOST = "REDIS_HOST"
_ENV_PORT = "REDIS_PORT"
_ENV_DB = "REDIS_DB"
_ENV_PASSWORD = "REDIS_PASSWORD"  # noqa: S105
_ENV_CLIENT_CERT = "REDIS_CLIENT_CERT"
_ENV_CLIENT_KEY = "REDIS_CLIENT_KEY"
_ENV_CA_CERT = "REDIS_CA_CERT"
_ENV_CERTS_DIR = "REDIS_CERTS_DIR"

_REQUIRED_CONN_VARS: tuple[str, ...] = (
    _ENV_HOST,
    _ENV_PORT,
    _ENV_DB,
    _ENV_PASSWORD,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RedisEnvError(EnvironmentError):
    """Raised when required Redis *connection* variables are missing.

    Only raised in env-var mode (``url=None``).  Lists every missing
    variable at once so the caller can fix all problems in one go.

    Args:
        missing_env_vars: Environment variable names that are unset or empty.

    Example::

        raise RedisEnvError(missing_env_vars=["REDIS_HOST", "REDIS_PASSWORD"])

    """

    def __init__(self, missing_env_vars: list[str]) -> None:
        joined = ", ".join(f"``{v}``" for v in missing_env_vars)
        super().__init__(
            "Redis connection configuration is incomplete.\n"
            f"  Missing environment variables: {joined}\n"
            "\nSet the missing variables in your .env file or shell environment."
        )


class TLSConfigError(EnvironmentError):
    """Raised when TLS is active but required TLS paths cannot be resolved.

    Raised when ``tls=True`` or a ``rediss://`` URL is used and one or more
    certificate paths are absent from both keyword arguments and environment
    variables.  Lists every missing item so the caller can resolve all
    problems without iterating through repeated failures.

    The cert/key paths are resolved in this order for each argument:

    1. Explicit keyword argument to :func:`redis_connect`.
    2. Corresponding environment variable
       (``REDIS_CLIENT_CERT``, ``REDIS_CLIENT_KEY``, ``REDIS_CA_CERT``).

    Args:
        missing_kwargs: Keyword argument names that were not supplied.
        missing_env_vars: Environment variable names that are unset or empty.

    Example::

        raise TLSConfigError(
            missing_kwargs=["tls_client_cert"],
            missing_env_vars=["REDIS_CLIENT_CERT"],
        )

    """

    def __init__(
        self,
        missing_kwargs: list[str],
        missing_env_vars: list[str],
    ) -> None:
        lines = ["TLS is enabled but TLS configuration is incomplete.\n"]
        if missing_kwargs:
            joined = ", ".join(f"``{k}``" for k in missing_kwargs)
            lines.append(f"  Missing keyword arguments : {joined}")
        if missing_env_vars:
            joined = ", ".join(f"``{v}``" for v in missing_env_vars)
            lines.append(f"  Missing environment variables: {joined}")
        lines.append(
            "\nProvide each value either as a keyword argument to "
            "``redis_connect()`` or as an environment variable in your "
            ".env file."
        )
        super().__init__("\n".join(lines))


# ---------------------------------------------------------------------------
# Environment config dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ConnEnv:
    """Connection parameters read from ``REDIS_{HOST,PORT,DB,PASSWORD}``.

    Produced by :func:`_load_conn_env`.  All fields are always populated;
    construction fails before this dataclass is instantiated if any variable
    is absent.

    Attributes:
        host: Value of ``REDIS_HOST``.
        port: Value of ``REDIS_PORT`` parsed as ``int``.
        db: Value of ``REDIS_DB`` parsed as ``int``.
        password: Value of ``REDIS_PASSWORD``.

    Example::

        conn = _load_conn_env()
        print(conn.host, conn.port)

    """

    host: str
    port: int
    db: int
    password: str


@dataclass(frozen=True)
class _TlsEnv:
    """TLS certificate paths read from the ``REDIS_*`` TLS environment variables.

    Produced by :func:`_load_tls_env`.  All three fields may be ``None``
    when the corresponding variable is absent — callers are responsible for
    validating the mTLS pairing rule before use.

    Attributes:
        tls_client_cert: Value of ``REDIS_CLIENT_CERT``, or ``None``.
        tls_client_key: Value of ``REDIS_CLIENT_KEY``, or ``None``.
        tls_ca_cert: Value of ``REDIS_CA_CERT``, or ``None``.

    Example::

        tls_env = _load_tls_env()
        print(tls_env.tls_client_cert)

    """

    tls_client_cert: Path | None
    tls_client_key: Path | None
    tls_ca_cert: Path | None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_conn_env() -> _ConnEnv:
    """Read and validate the four required Redis connection variables.

    Assumes :func:`~dotenv.load_dotenv` has already been called by the
    public entry-point (:func:`redis_connect`).  All four variables are
    checked together; if any are missing, a single :class:`RedisEnvError`
    is raised listing every absent variable.

    Returns:
        A fully populated :class:`_ConnEnv`.

    Raises:
        RedisEnvError: If one or more of ``REDIS_HOST``, ``REDIS_PORT``,
            ``REDIS_DB``, or ``REDIS_PASSWORD`` are unset or empty.

    Example::

        conn = _load_conn_env()
        print(conn.host, conn.port)

    """
    missing = [var for var in _REQUIRED_CONN_VARS if not os.getenv(var)]
    if missing:
        raise RedisEnvError(missing_env_vars=missing)
    return _ConnEnv(
        host=os.environ[_ENV_HOST],
        port=int(os.environ[_ENV_PORT]),
        db=int(os.environ[_ENV_DB]),
        password=os.environ[_ENV_PASSWORD],
    )


def _load_tls_env() -> _TlsEnv:
    """Read the three optional ``REDIS_*`` TLS environment variables.

    Assumes :func:`~dotenv.load_dotenv` has already been called by the
    public entry-point (:func:`redis_connect`).  All three fields are
    optional at the env-var level; the mTLS pairing rule (cert + key both
    present or both absent) is enforced later by :func:`_resolve_tls_paths`.

    Returns:
        An :class:`_TlsEnv` with ``None`` for any absent variable.

    Example::

        tls_env = _load_tls_env()
        print(tls_env.tls_client_cert)

    """
    certs_path = os.getenv(_ENV_CERTS_DIR)
    tls_client_cert = os.getenv(_ENV_CLIENT_CERT)
    tls_client_key = os.getenv(_ENV_CLIENT_KEY)
    tls_ca_cert = os.getenv(_ENV_CA_CERT)

    path = Path(certs_path).expanduser() if certs_path else Path()

    return _TlsEnv(
        tls_client_cert=_resolve(path, tls_client_cert),
        tls_client_key=_resolve(path, tls_client_key),
        tls_ca_cert=_resolve(path, tls_ca_cert),
    )


def _resolve(path: Path, filename: str | None) -> Path | None:
    """Join *filename* onto *path* with ``~`` expansion; pass through ``None``."""
    if filename is None:
        return None
    return (path / filename).expanduser()


def _redact_url(url: str) -> str:
    """Return *url* with the password component replaced by ``'***'``.

    Safe to pass to loggers — never logs credentials.

    Args:
        url: A Redis connection URL, e.g. ``redis://:secret@host:6379/0``.

    Returns:
        The same URL with any inline password replaced by ``***``.

    Example::

        >>> _redact_url("redis://:s3cr3t@localhost:6379/0")
        'redis://:***@localhost:6379/0'

    """
    parsed = urlparse(url)
    if not parsed.password:
        return url

    user = parsed.username or ""
    host = parsed.hostname or ""
    netloc = f"{user}:***@{host}"

    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"

    return parsed._replace(netloc=netloc).geturl()


def _resolve_tls_paths(
    tls_client_cert: str | None,
    tls_client_key: str | None,
    tls_ca_cert: str | None,
    tls_env: _TlsEnv,
) -> tuple[str | None, str | None, str | None]:
    """Resolve all three TLS paths and enforce the mTLS pairing rule.

    Each path is resolved in priority order:

    1. Explicit keyword argument.
    2. Corresponding field on *tls_env* (read from the environment).
    3. ``None``.

    After resolution, ``tls_client_cert`` and ``tls_client_key`` must either *both*
    be present (mTLS) or *both* absent (server-auth only).  A mismatched pair
    raises :class:`TLSConfigError`.  ``tls_ca_certs`` may always be ``None``
    (the system CA store is used in that case).

    Args:
        tls_client_cert: Explicit client certificate path, or ``None``.
        tls_client_key: Explicit client private-key path, or ``None``.
        tls_ca_cert: Explicit CA bundle path, or ``None``.
        tls_env: TLS paths loaded from environment variables.

    Returns:
        3-tuple ``(tls_client_cert, tls_client_key, tls_ca_certs)`` with all
        environment fallbacks applied.

    Raises:
        TLSConfigError: If exactly one of ``tls_client_cert`` / ``tls_client_key``
            is resolved (mTLS requires both or neither).

    Example::

        tls_env = _load_tls_env()
        certfile, keyfile, ca = _resolve_tls_paths(None, None, None, tls_env)

    """
    resolved_certfile = tls_client_cert or tls_env.tls_client_cert
    resolved_keyfile = tls_client_key or tls_env.tls_client_key
    resolved_ca_certs = tls_ca_cert or tls_env.tls_ca_cert

    cert_present = resolved_certfile is not None
    key_present = resolved_keyfile is not None

    if cert_present != key_present:
        missing_kwargs: list[str] = []
        missing_env_vars: list[str] = []
        if not cert_present:
            missing_kwargs.append("tls_client_cert")
            missing_env_vars.append(_ENV_CLIENT_CERT)
        if not key_present:
            missing_kwargs.append("tls_client_key")
            missing_env_vars.append(_ENV_CLIENT_KEY)
        raise TLSConfigError(
            missing_kwargs=missing_kwargs,
            missing_env_vars=missing_env_vars,
        )

    return resolved_certfile, resolved_keyfile, resolved_ca_certs


def _build_tls_context(
    *,
    tls_client_cert: str | None,
    tls_client_key: str | None,
    tls_ca_cert: str | None,
    tls_env: _TlsEnv,
    tls_check_hostname: bool,
) -> dict[str, Any]:
    """Build and return a dict of TLS keyword arguments for a Redis constructor.

    Delegates path resolution (including env-var fallback and mTLS pairing
    validation) to :func:`_resolve_tls_paths`, then constructs a configured
    :class:`ssl.SSLContext`.

    Returning a fresh dict (rather than mutating a caller-supplied one) makes
    the function side-effect-free and easier to test in isolation.

    Args:
        tls_client_cert: Client certificate path or ``None`` (env fallback:
            ``REDIS_CLIENT_CERT``).
        tls_client_key: Client private-key path or ``None`` (env fallback:
            ``REDIS_CLIENT_KEY``).
        tls_ca_cert: CA bundle path or ``None`` (env fallback:
            ``REDIS_CA_CERT``; system store used when absent).
        tls_env: TLS paths loaded from environment variables.
        tls_check_hostname: Enforce SNI hostname verification.
            **Do not set to** ``False`` **in production** — disabling
            hostname verification allows MitM attacks.


    Returns:
        A dict with ``"tls": True`` and ``"tls_context"`` keys, ready to
        be unpacked into the ``redis.Redis`` constructor.

    Raises:
        TLSConfigError: If mTLS paths are only partially provided.

    Example::

        tls_env = _load_tls_env()
        kwargs = _build_tls_context(tls_client_cert=None, tls_client_key=None,
            tls_ca_cert=None, tls_env=tls_env,tls_check_hostname=True)
        client = redis.from_url(url, **kwargs)

    """
    certfile, keyfile, ca_cert = _resolve_tls_paths(
        tls_client_cert, tls_client_key, tls_ca_cert, tls_env
    )

    kwargs: dict[str, Any] = {"ssl": True}

    if certfile:
        kwargs["ssl_certfile"] = str(certfile)
    if keyfile:
        kwargs["ssl_keyfile"] = str(keyfile)
    if ca_cert:
        kwargs["ssl_ca_certs"] = str(ca_cert)

    kwargs["ssl_check_hostname"] = tls_check_hostname
    kwargs["ssl_cert_reqs"] = ssl_module.CERT_REQUIRED

    return kwargs


def _connect_from_url(url: str, tls_kwargs: dict[str, Any]) -> redis.Redis:
    """Create a Redis connection from a URL string.

    Args:
        url: Full Redis connection URL.  Password is redacted in log output.
        tls_kwargs: Pre-built TLS keyword arguments (may be empty).

    Returns:
        A connected :class:`redis.Redis` instance with ``decode_responses=True``.

    Example::

        r = _connect_from_url("rediss://:pw@host:6380/0", tls_kwargs={})

    """
    logger.info("Connecting to Redis via URL: %s", _redact_url(url))
    return redis.from_url(url, decode_responses=True, **tls_kwargs)


def _connect_from_env(conn_env: _ConnEnv, tls_kwargs: dict[str, Any]) -> redis.Redis:
    """Create a Redis connection from a pre-loaded :class:`_ConnEnv`.

    Args:
        conn_env: Connection parameters produced by :func:`_load_conn_env`.
        tls_kwargs: Pre-built TLS keyword arguments (may be empty).

    Returns:
        A connected :class:`redis.Redis` instance with ``decode_responses=True``.

    Example::

        conn_env = _load_conn_env()
        r = _connect_from_env(conn_env, tls_kwargs={})

    """
    logger.info(
        "Connecting to Redis at %s:%d/%d",
        conn_env.host,
        conn_env.port,
        conn_env.db,
    )
    return redis.Redis(
        host=conn_env.host,
        port=conn_env.port,
        db=conn_env.db,
        password=conn_env.password,
        decode_responses=True,
        **tls_kwargs,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def redis_connect(
    url: str | None = None,
    *,
    tls: bool = False,
    tls_client_cert: str | None = None,
    tls_client_key: str | None = None,
    tls_ca_cert: str | None = None,
    tls_check_hostname: bool = True,
) -> redis.Redis:
    """Create a Redis connection with optional TLS support.

    Two connection modes are supported:

    **Mode 1 – URL string** (``url`` is provided)::

        redis_connect(url="rediss://:<password>@redis.example.com:6380/0")

    **Mode 2 – env-vars** (default, ``url`` is ``None``)::

        # .env
        REDIS_HOST=127.0.0.1
        REDIS_PORT=6380
        REDIS_DB=0
        REDIS_PASSWORD=secret

    :func:`~dotenv.load_dotenv` is called once here before any env-var reads,
    ensuring ``.env`` files are honoured in both connection modes without
    redundant I/O.

    **TLS path resolution** (when TLS is active in either mode):

    Each ``tls_*`` path is resolved in this order:

    1. Explicit keyword argument.
    2. Corresponding env var (``REDIS_CLIENT_CERT``, ``REDIS_CLIENT_KEY``,
       ``REDIS_CA_CERT``).
    3. ``None`` — valid only for ``tls_ca_cert`` (system CA store is used).

    mTLS requires ``tls_client_cert`` **and** ``tls_client_key`` together, or
    neither.  Supplying only one raises :class:`TLSConfigError`.

    Args:
        url: Full Redis connection URL.  Password is redacted in logs.
            When ``None``, connection parameters are read from env vars.
        tls: Wrap the connection in TLS.  Also implicitly ``True`` when
            *url* starts with ``rediss://``.
        tls_client_cert: Path to PEM client certificate (mTLS only).
            Falls back to ``REDIS_CLIENT_CERT`` env var.
        tls_client_key: Path to PEM client private key (mTLS only).
            Falls back to ``REDIS_CLIENT_KEY`` env var.
        tls_ca_cert: Path to CA bundle.  Falls back to ``REDIS_CA_CERT``
            env var; ``None`` uses the system CA store.
        tls_check_hostname: Enforce SNI hostname verification.
            **Do not set to** ``False`` **in production** — disabling this
            allows MitM attacks.

    Returns:
        A connected :class:`redis.Redis` instance.

    Raises:
        TLSConfigError: When TLS is active (``tls=True`` or ``rediss://`` URL)
            and required TLS paths cannot be resolved from kwargs or env vars.
        RedisEnvError: When ``url=None`` and one or more of ``REDIS_HOST``,
            ``REDIS_PORT``, ``REDIS_DB``, or ``REDIS_PASSWORD`` are unset.

    Example::

        # Env-var mode with TLS — cert paths read from .env
        r = redis_connect(tls=True)

        # URL mode with explicit mTLS certs
        r = redis_connect(
            url="rediss://:pw@host:6380/0",
            tls_client_cert="/certs/client.crt",
            tls_client_key="/certs/client.key",
        )

    """
    # Single load_dotenv call covers both env loaders below.
    load_dotenv()

    tls_active = tls or (url is not None and url.startswith("rediss://"))
    tls_kwargs: dict[str, Any] = (
        _build_tls_context(
            tls_client_cert=tls_client_cert,
            tls_client_key=tls_client_key,
            tls_ca_cert=tls_ca_cert,
            tls_check_hostname=tls_check_hostname,
            tls_env=_load_tls_env(),
        )
        if tls_active
        else {}
    )

    if url is not None:
        return _connect_from_url(url, tls_kwargs)
    return _connect_from_env(_load_conn_env(), tls_kwargs)
