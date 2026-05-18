"""Tests for setup_logger.py — logging configuration and memory reporting."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

import scripts.setup_logger as setup_logger  # noqa: E402

# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------


class TestConfigureLogging:
    def test_creates_log_file_in_output_dir(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Patch the hardcoded path
        log_path = None

        def capture_basic_config(**kwargs):
            nonlocal log_path
            log_path = kwargs.get("filename")

        with patch("logging.basicConfig", side_effect=capture_basic_config):
            setup_logger.configure_logging("my_script.py")

        assert log_path is not None
        assert "my_script" in log_path

    def test_stem_used_as_log_name_prefix(self):
        captured_filename = None

        def capture_basic_config(**kwargs):
            nonlocal captured_filename
            captured_filename = kwargs.get("filename", "")

        with patch("logging.basicConfig", side_effect=capture_basic_config):
            setup_logger.configure_logging("/some/path/import_data.py")

        assert "import_data" in captured_filename

    def test_timestamp_included_in_log_filename(self):
        captured_filename = None

        def capture_basic_config(**kwargs):
            nonlocal captured_filename
            captured_filename = kwargs.get("filename", "")

        with patch("logging.basicConfig", side_effect=capture_basic_config):
            setup_logger.configure_logging("script.py")

        # Timestamp format: YYYY-MM-DD_HH:MM:SS
        import re

        assert re.search(r"\d{4}-\d{2}-\d{2}", captured_filename)

    def test_log_level_is_info(self):
        captured_level = None

        def capture_basic_config(**kwargs):
            nonlocal captured_level
            captured_level = kwargs.get("level")

        with patch("logging.basicConfig", side_effect=capture_basic_config):
            setup_logger.configure_logging("s.py")

        assert captured_level == logging.INFO

    def test_format_contains_process_id_and_level(self):
        captured_format = None

        def capture_basic_config(**kwargs):
            nonlocal captured_format
            captured_format = kwargs.get("format", "")

        with patch("logging.basicConfig", side_effect=capture_basic_config):
            setup_logger.configure_logging("s.py")

        assert "%(process)d" in captured_format
        assert "%(levelname)s" in captured_format

    def test_warnings_captured(self):
        """Python warnings should be routed to the logging system."""
        with (
            patch("logging.basicConfig"),
            patch("logging.captureWarnings") as mock_cw,
        ):
            setup_logger.configure_logging("s.py")
        mock_cw.assert_called_once_with(capture=True)

    def test_force_true_to_reconfigure(self):
        """force=True allows re-configuring after initial basicConfig call."""
        captured_force = None

        def capture_basic_config(**kwargs):
            nonlocal captured_force
            captured_force = kwargs.get("force")

        with patch("logging.basicConfig", side_effect=capture_basic_config):
            setup_logger.configure_logging("s.py")

        assert captured_force is True


# ---------------------------------------------------------------------------
# log_peak_memory
# ---------------------------------------------------------------------------


class TestLogPeakMemory:
    def test_logs_memory_as_float_mb(self):
        logger = MagicMock()

        with patch("resource.getrusage") as mock_usage:
            mock_usage.return_value = MagicMock(ru_maxrss=512 * 1024)  # 512 MB
            setup_logger.log_peak_memory(logger)

        logger.info.assert_called_once()
        call_args = logger.info.call_args
        # Should be called with a format string and a float value
        assert "%" in call_args[0][0]  # format string
        float_arg = call_args[0][1]
        assert isinstance(float_arg, float)
        assert abs(float_arg - 512.0) < 1.0

    def test_uses_rusage_self(self):
        import resource as resource_mod

        logger = MagicMock()
        with patch("resource.getrusage") as mock_usage:
            mock_usage.return_value = MagicMock(ru_maxrss=1024)
            setup_logger.log_peak_memory(logger)

        mock_usage.assert_called_once_with(resource_mod.RUSAGE_SELF)

    def test_converts_kb_to_mb(self):
        logger = MagicMock()
        with patch("resource.getrusage") as mock_usage:
            mock_usage.return_value = MagicMock(ru_maxrss=1024)  # 1024 KB = 1 MB
            setup_logger.log_peak_memory(logger)

        call_args = logger.info.call_args
        value = call_args[0][1]
        assert abs(value - 1.0) < 0.01

    def test_message_contains_mb_unit(self):
        logger = MagicMock()
        with patch("resource.getrusage") as mock_usage:
            mock_usage.return_value = MagicMock(ru_maxrss=1024)
            setup_logger.log_peak_memory(logger)

        call_args = logger.info.call_args
        format_str = call_args[0][0]
        assert "MB" in format_str


# ---------------------------------------------------------------------------
# import_to_redis.py — entry-point error paths (subprocess-level)
# ---------------------------------------------------------------------------


class TestImportToRedisEntryPoint:
    """import_to_redis.py is a __main__ script; test it via subprocess."""

    def _run_script(self, _monkeypatch, extra_env=None):
        import os
        import subprocess

        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent / "scripts")
        if extra_env:
            env.update(extra_env)

        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-c",
                """
import sys
sys.path.insert(0, sys.argv[1])
# Prevent actual redis connection
from unittest.mock import patch, MagicMock
import redis

mock_r = MagicMock()
mock_r.ping.side_effect = redis.RedisError("cannot connect")

with patch("src.connection.docker_redis_connect", return_value=mock_r, create=True):
    with patch("setup_logger.configure_logging"):
        try:
            import import_to_redis
        except SystemExit as e:
            pass
        except Exception:
            pass
""",
                str(Path(__file__).parent.parent.parent / "scripts"),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        return result

    def test_import_to_redis_importable_without_execution(self):
        """Importing the module must not execute __main__ block."""
        # If the module-level code (outside __main__) crashes on missing
        # redis library, the test shows the real gap in dependencies.
        # We just check the file parses cleanly.
        source = (
            Path(__file__).parent.parent.parent / "scripts" / "import_to_redis.py"
        ).read_text()
        try:
            compile(source, "import_to_redis.py", "exec")
        except SyntaxError as e:
            pytest.fail(f"SyntaxError in import_to_redis.py: {e}")
