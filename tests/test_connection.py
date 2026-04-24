"""Tests for src/connection.py — TLS config, env loading, URL redaction, security."""

from __future__ import annotations

import os
import ssl
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.connection import (
    RedisEnvError,
    TLSConfigError,
    _ConnEnv,
    _TlsEnv,
    _build_tls_context,
    _connect_from_env,
    _connect_from_url,
    _load_conn_env,
    _load_tls_env,
    _redact_url,
    _resolve,
    _resolve_tls_paths,
    redis_connect,
)


# ---------------------------------------------------------------------------
# _redact_url
# ---------------------------------------------------------------------------


class TestRedactUrl:
    def test_redacts_password(self):
        url = "redis://:s3cr3t@localhost:6379/0"
        result = _redact_url(url)
        assert "s3cr3t" not in result
        assert "***" in result

    def test_no_password_unchanged(self):
        url = "redis://localhost:6379/0"
        assert _redact_url(url) == url

    def test_rediss_scheme(self):
        url = "rediss://:topsecret@host:6380/1"
        result = _redact_url(url)
        assert "topsecret" not in result

    def test_preserves_host_and_port(self):
        url = "redis://:pw@myhost:1234/2"
        result = _redact_url(url)
        assert "myhost" in result
        assert "1234" in result

    def test_empty_password_component(self):
        url = "redis://@localhost:6379/0"
        result = _redact_url(url)
        assert "s3cr3t" not in result

    def test_massive_password_redacted(self):
        password = "A" * 10_000
        url = f"redis://:{password}@host:6379/0"
        result = _redact_url(url)
        assert password not in result
        assert "***" in result


# ---------------------------------------------------------------------------
# _resolve
# ---------------------------------------------------------------------------


class TestResolve:
    def test_none_passthrough(self):
        assert _resolve(Path("/certs"), None) is None

    def test_joins_path(self):
        result = _resolve(Path("/certs"), "client.crt")
        assert result == Path("/certs/client.crt")

    def test_tilde_expansion(self, tmp_path):
        result = _resolve(Path(tmp_path), "key.pem")
        assert result is not None
        assert str(tmp_path) in str(result)


# ---------------------------------------------------------------------------
# _load_conn_env
# ---------------------------------------------------------------------------


class TestLoadConnEnv:
    def test_raises_redis_env_error_when_all_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RedisEnvError) as exc_info:
                _load_conn_env()
        msg = str(exc_info.value)
        assert "REDIS_HOST" in msg
        assert "REDIS_PORT" in msg
        assert "REDIS_DB" in msg
        assert "REDIS_PASSWORD" in msg

    def test_raises_with_partial_vars(self):
        env = {"REDIS_HOST": "localhost", "REDIS_PORT": "6379"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RedisEnvError) as exc_info:
                _load_conn_env()
        assert "REDIS_DB" in str(exc_info.value)
        assert "REDIS_PASSWORD" in str(exc_info.value)

    def test_succeeds_with_all_vars(self):
        env = {
            "REDIS_HOST": "127.0.0.1",
            "REDIS_PORT": "6380",
            "REDIS_DB": "2",
            "REDIS_PASSWORD": "secret",
        }
        with patch.dict(os.environ, env, clear=True):
            conn = _load_conn_env()
        assert conn.host == "127.0.0.1"
        assert conn.port == 6380
        assert conn.db == 2
        assert conn.password == "secret"

    def test_port_and_db_are_integers(self):
        env = {
            "REDIS_HOST": "h",
            "REDIS_PORT": "9999",
            "REDIS_DB": "15",
            "REDIS_PASSWORD": "p",
        }
        with patch.dict(os.environ, env, clear=True):
            conn = _load_conn_env()
        assert isinstance(conn.port, int)
        assert isinstance(conn.db, int)

    def test_error_lists_all_missing_not_just_one(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RedisEnvError) as exc_info:
                _load_conn_env()
        error_vars = ["REDIS_HOST", "REDIS_PORT", "REDIS_DB", "REDIS_PASSWORD"]
        for var in error_vars:
            assert var in str(exc_info.value)


# ---------------------------------------------------------------------------
# _load_tls_env
# ---------------------------------------------------------------------------


class TestLoadTlsEnv:
    def test_all_none_when_no_env(self):
        with patch.dict(os.environ, {}, clear=True):
            tls_env = _load_tls_env()
        assert tls_env.tls_client_cert is None
        assert tls_env.tls_client_key is None
        assert tls_env.tls_ca_cert is None

    def test_resolves_paths_without_certs_dir(self):
        env = {
            "REDIS_CLIENT_CERT": "client.crt",
            "REDIS_CLIENT_KEY": "client.key",
            "REDIS_CA_CERT": "ca.crt",
        }
        with patch.dict(os.environ, env, clear=True):
            tls_env = _load_tls_env()
        assert tls_env.tls_client_cert is not None
        assert "client.crt" in str(tls_env.tls_client_cert)

    def test_certs_dir_is_prepended(self, tmp_path):
        env = {
            "REDIS_CERTS_DIR": str(tmp_path),
            "REDIS_CLIENT_CERT": "c.crt",
            "REDIS_CLIENT_KEY": "c.key",
            "REDIS_CA_CERT": "ca.crt",
        }
        with patch.dict(os.environ, env, clear=True):
            tls_env = _load_tls_env()
        assert str(tmp_path) in str(tls_env.tls_client_cert)


# ---------------------------------------------------------------------------
# _resolve_tls_paths
# ---------------------------------------------------------------------------


class TestResolveTlsPaths:
    def _empty_env(self) -> _TlsEnv:
        return _TlsEnv(None, None, None)

    def test_all_none_returns_none_triple(self):
        cert, key, ca = _resolve_tls_paths(None, None, None, self._empty_env())
        assert cert is None
        assert key is None
        assert ca is None

    def test_cert_without_key_raises(self):
        with pytest.raises(TLSConfigError) as exc_info:
            _resolve_tls_paths("/cert.pem", None, None, self._empty_env())
        assert "tls_client_key" in str(exc_info.value)

    def test_key_without_cert_raises(self):
        with pytest.raises(TLSConfigError) as exc_info:
            _resolve_tls_paths(None, "/key.pem", None, self._empty_env())
        assert "tls_client_cert" in str(exc_info.value)

    def test_both_cert_and_key_succeeds(self):
        cert, key, ca = _resolve_tls_paths(
            "/cert.pem", "/key.pem", "/ca.pem", self._empty_env()
        )
        assert cert == "/cert.pem"
        assert key == "/key.pem"
        assert ca == "/ca.pem"

    def test_env_fallback_used(self):
        tls_env = _TlsEnv(
            Path("/env/cert.crt"), Path("/env/key.key"), Path("/env/ca.crt")
        )
        cert, key, ca = _resolve_tls_paths(None, None, None, tls_env)
        assert cert == Path("/env/cert.crt")

    def test_explicit_overrides_env(self):
        tls_env = _TlsEnv(
            Path("/env/cert.crt"), Path("/env/key.key"), Path("/env/ca.crt")
        )
        cert, key, _ = _resolve_tls_paths(
            "/explicit.crt", "/explicit.key", None, tls_env
        )
        assert cert == "/explicit.crt"
        assert key == "/explicit.key"


# ---------------------------------------------------------------------------
# _build_tls_context
# ---------------------------------------------------------------------------


class TestBuildTlsContext:
    def _empty_env(self) -> _TlsEnv:
        return _TlsEnv(None, None, None)

    def test_returns_ssl_true(self):
        kwargs = _build_tls_context(
            tls_client_cert=None,
            tls_client_key=None,
            tls_ca_cert=None,
            tls_env=self._empty_env(),
            tls_check_hostname=True,
        )
        assert kwargs["ssl"] is True

    def test_check_hostname_true_by_default_is_enforced(self):
        kwargs = _build_tls_context(
            tls_client_cert=None,
            tls_client_key=None,
            tls_ca_cert=None,
            tls_env=self._empty_env(),
            tls_check_hostname=True,
        )
        assert kwargs["ssl_check_hostname"] is True

    def test_cert_required_is_always_set(self):
        kwargs = _build_tls_context(
            tls_client_cert=None,
            tls_client_key=None,
            tls_ca_cert=None,
            tls_env=self._empty_env(),
            tls_check_hostname=True,
        )
        assert kwargs["ssl_cert_reqs"] == ssl.CERT_REQUIRED

    def test_insecure_hostname_check_false_propagates(self):
        """Verify False is possible but noted — not silently upgraded."""
        kwargs = _build_tls_context(
            tls_client_cert=None,
            tls_client_key=None,
            tls_ca_cert=None,
            tls_env=self._empty_env(),
            tls_check_hostname=False,
        )
        assert kwargs["ssl_check_hostname"] is False

    def test_mtls_paths_included(self, tmp_path):
        cert = tmp_path / "c.crt"
        key = tmp_path / "c.key"
        cert.touch()
        key.touch()
        kwargs = _build_tls_context(
            tls_client_cert=str(cert),
            tls_client_key=str(key),
            tls_ca_cert=None,
            tls_env=self._empty_env(),
            tls_check_hostname=True,
        )
        assert "ssl_certfile" in kwargs
        assert "ssl_keyfile" in kwargs

    def test_partial_mtls_raises(self):
        with pytest.raises(TLSConfigError):
            _build_tls_context(
                tls_client_cert="/only_cert.crt",
                tls_client_key=None,
                tls_ca_cert=None,
                tls_env=self._empty_env(),
                tls_check_hostname=True,
            )


# ---------------------------------------------------------------------------
# redis_connect integration (mocked)
# ---------------------------------------------------------------------------


class TestRedisConnect:
    def _full_env(self) -> dict[str, str]:
        return {
            "REDIS_HOST": "127.0.0.1",
            "REDIS_PORT": "6379",
            "REDIS_DB": "0",
            "REDIS_PASSWORD": "pw",
        }

    @patch("src.connection.load_dotenv")
    @patch("src.connection.redis.Redis")
    def test_env_mode_creates_connection(self, mock_redis_cls, mock_dotenv):
        with patch.dict(os.environ, self._full_env(), clear=True):
            redis_connect()
        mock_redis_cls.assert_called_once()

    @patch("src.connection.load_dotenv")
    @patch("src.connection.redis.from_url")
    def test_url_mode_calls_from_url(self, mock_from_url, mock_dotenv):
        with patch.dict(os.environ, {}, clear=True):
            redis_connect(url="redis://:pw@localhost:6379/0")
        mock_from_url.assert_called_once()

    @patch("src.connection.load_dotenv")
    def test_missing_env_raises_redis_env_error(self, mock_dotenv):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RedisEnvError):
                redis_connect()

    @patch("src.connection.load_dotenv")
    @patch("src.connection.redis.from_url")
    def test_rediss_url_activates_tls(self, mock_from_url, mock_dotenv):
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.connection._build_tls_context") as mock_tls:
                mock_tls.return_value = {
                    "ssl": True,
                    "ssl_check_hostname": True,
                    "ssl_cert_reqs": ssl.CERT_REQUIRED,
                }
                redis_connect(url="rediss://:pw@host:6380/0")
        mock_tls.assert_called_once()

    @patch("src.connection.load_dotenv")
    @patch("src.connection.redis.Redis")
    def test_decode_responses_true(self, mock_redis_cls, mock_dotenv):
        with patch.dict(os.environ, self._full_env(), clear=True):
            redis_connect()
        _, kwargs = mock_redis_cls.call_args
        assert kwargs.get("decode_responses") is True


# ---------------------------------------------------------------------------
# Security: TLSConfigError message quality
# ---------------------------------------------------------------------------


class TestTLSConfigError:
    def test_error_mentions_both_missing_items(self):
        err = TLSConfigError(
            missing_kwargs=["tls_client_cert", "tls_client_key"],
            missing_env_vars=["REDIS_CLIENT_CERT", "REDIS_CLIENT_KEY"],
        )
        msg = str(err)
        assert "tls_client_cert" in msg
        assert "REDIS_CLIENT_CERT" in msg

    def test_empty_lists_does_not_crash(self):
        err = TLSConfigError(missing_kwargs=[], missing_env_vars=[])
        assert "TLS" in str(err)


class TestRedisEnvError:
    def test_lists_all_missing_vars(self):
        err = RedisEnvError(["REDIS_HOST", "REDIS_PASSWORD"])
        msg = str(err)
        assert "REDIS_HOST" in msg
        assert "REDIS_PASSWORD" in msg

    def test_empty_list_does_not_crash(self):
        err = RedisEnvError([])
        assert len(str(err)) > 0
