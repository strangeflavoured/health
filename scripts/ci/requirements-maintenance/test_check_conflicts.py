"""Tests for check_conflicts.py — subprocess orchestration with mocking."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import check_conflicts
import pytest


class TestSlug:
    def test_simple(self):
        assert (
            check_conflicts.slug("backend/requirements.in") == "backend-requirements-in"
        )

    def test_no_dots_or_slashes(self):
        assert check_conflicts.slug("simple") == "simple"

    def test_multiple_separators(self):
        assert check_conflicts.slug("a/b/c.d.e.in") == "a-b-c-d-e-in"


class TestRunCapture:
    def test_returns_combined_output(self):
        with patch("check_conflicts.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="hello\n", stderr="world\n"
            )
            code, output = check_conflicts.run_capture(["echo", "test"])

        assert code == 0
        assert "hello" in output
        assert "world" in output

    def test_returns_failure_code(self):
        with patch("check_conflicts.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            code, output = check_conflicts.run_capture(["false"])

        assert code == 1
        assert "error" in output


class TestCheckOne:
    def test_successful_install_and_check(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(check_conflicts, "REPORTS", tmp_path)
        txt_file = tmp_path / "requirements.txt"
        txt_file.write_text("django==4.2.1\n")

        # All subprocess calls succeed
        with (
            patch("check_conflicts.run_capture") as mock_run,
            patch("check_conflicts.venv.create") as mock_venv,
        ):
            mock_run.return_value = (0, "OK")
            result = check_conflicts.check_one(
                "requirements.in", txt_file, tmp_path / "venv"
            )

        assert result["install_ok"] is True
        assert result["check_ok"] is True
        mock_venv.assert_called_once()

    def test_install_failure(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(check_conflicts, "REPORTS", tmp_path)
        txt_file = tmp_path / "requirements.txt"
        txt_file.write_text("nonexistent==999\n")

        call_count = 0

        def mock_run_capture(cmd):
            nonlocal call_count
            call_count += 1
            # Both install attempts fail (with and without --require-hashes)
            if "install" in cmd:
                return (1, "ERROR: could not find package")
            return (0, "")  # pip check would pass

        with (
            patch("check_conflicts.run_capture", side_effect=mock_run_capture),
            patch("check_conflicts.venv.create"),
        ):
            result = check_conflicts.check_one(
                "requirements.in", txt_file, tmp_path / "venv"
            )

        assert result["install_ok"] is False

    def test_check_failure(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(check_conflicts, "REPORTS", tmp_path)
        txt_file = tmp_path / "requirements.txt"
        txt_file.write_text("django==4.2.1\n")

        def mock_run_capture(cmd):
            if "check" in cmd:
                return (1, "pkg-a 1.0 requires pkg-b<2 but you have 3.0")
            return (0, "")

        with (
            patch("check_conflicts.run_capture", side_effect=mock_run_capture),
            patch("check_conflicts.venv.create"),
        ):
            result = check_conflicts.check_one(
                "requirements.in", txt_file, tmp_path / "venv"
            )

        assert result["install_ok"] is True
        assert result["check_ok"] is False

    def test_falls_back_when_hashes_unavailable(self, tmp_path: Path, monkeypatch):
        """If --require-hashes fails because lockfile has no hashes, retry without."""
        monkeypatch.setattr(check_conflicts, "REPORTS", tmp_path)
        txt_file = tmp_path / "requirements.txt"
        txt_file.write_text("django==4.2.1\n")

        call_log: list[list[str]] = []

        def mock_run_capture(cmd):
            call_log.append(cmd)
            # First call (with --require-hashes) fails with hash error
            if "--require-hashes" in cmd:
                return (1, "ERROR: hash mismatch, --require-hashes mode")
            # Retry without --require-hashes succeeds
            if "install" in cmd:
                return (0, "Installed")
            return (0, "")  # pip check passes

        with (
            patch("check_conflicts.run_capture", side_effect=mock_run_capture),
            patch("check_conflicts.venv.create"),
        ):
            result = check_conflicts.check_one(
                "requirements.in", txt_file, tmp_path / "venv"
            )

        # Should have retried without --require-hashes
        assert any(
            "--require-hashes" not in cmd for cmd in call_log if "install" in cmd
        )
        assert result["install_ok"] is True

    def test_writes_logs_to_reports(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(check_conflicts, "REPORTS", tmp_path)
        txt_file = tmp_path / "requirements.txt"
        txt_file.write_text("django==4.2.1\n")

        with (
            patch("check_conflicts.run_capture", return_value=(0, "log content")),
            patch("check_conflicts.venv.create"),
        ):
            check_conflicts.check_one(
                "backend/requirements.in", txt_file, tmp_path / "venv"
            )

        # Logs should be written with slugified filenames
        install_log = tmp_path / "install-backend-requirements-in.log"
        check_log = tmp_path / "check-backend-requirements-in.log"
        assert install_log.exists()
        assert check_log.exists()


class TestMain:
    def test_no_files(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(check_conflicts, "REPORTS", tmp_path)
        monkeypatch.setenv("ALL_FILES", "[]")
        assert check_conflicts.main() == 0
        assert json.loads((tmp_path / "conflicts.json").read_text()) == {}

    def test_all_clean(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(check_conflicts, "REPORTS", tmp_path / "reports")
        (tmp_path / "reports").mkdir()

        (tmp_path / "requirements.in").write_text("django\n")
        (tmp_path / "requirements.txt").write_text("django==4.2.1\n")
        monkeypatch.setenv("ALL_FILES", json.dumps(["requirements.in"]))

        def fake_check_one(_in_path, _txt_path, _venv_dir):
            return {
                "install_ok": True,
                "check_ok": True,
                "install_log": "",
                "check_log": "",
            }

        monkeypatch.setattr(check_conflicts, "check_one", fake_check_one)
        with patch("check_conflicts.shutil.rmtree"):
            assert check_conflicts.main() == 0

    def test_returns_nonzero_on_failure(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(check_conflicts, "REPORTS", tmp_path / "reports")
        (tmp_path / "reports").mkdir()

        (tmp_path / "requirements.in").write_text("django\n")
        (tmp_path / "requirements.txt").write_text("django==4.2.1\n")
        monkeypatch.setenv("ALL_FILES", json.dumps(["requirements.in"]))

        def fake_check_one(_in_path, _txt_path, _venv_dir):
            return {
                "install_ok": True,
                "check_ok": False,
                "install_log": "",
                "check_log": "conflict",
            }

        monkeypatch.setattr(check_conflicts, "check_one", fake_check_one)
        with patch("check_conflicts.shutil.rmtree"):
            assert check_conflicts.main() == 1

    def test_skips_missing_txt(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(check_conflicts, "REPORTS", tmp_path / "reports")
        (tmp_path / "reports").mkdir()

        (tmp_path / "requirements.in").write_text("django\n")
        # No .txt file
        monkeypatch.setenv("ALL_FILES", json.dumps(["requirements.in"]))

        called = []
        monkeypatch.setattr(
            check_conflicts,
            "check_one",
            lambda *_, **__: (
                called.append(True)
                or {
                    "install_ok": True,
                    "check_ok": True,
                    "install_log": "",
                    "check_log": "",
                }
            ),
        )

        assert check_conflicts.main() == 0
        assert called == []

    def test_cleans_up_venvs(self, tmp_path: Path, monkeypatch):
        """Venvs should be removed after each check, even on failure."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(check_conflicts, "REPORTS", tmp_path / "reports")
        (tmp_path / "reports").mkdir()

        (tmp_path / "requirements.in").write_text("django\n")
        (tmp_path / "requirements.txt").write_text("django==4.2.1\n")
        monkeypatch.setenv("ALL_FILES", json.dumps(["requirements.in"]))

        def explode(*_, **__):
            raise RuntimeError("simulated failure")

        monkeypatch.setattr(check_conflicts, "check_one", explode)

        with (
            patch("check_conflicts.shutil.rmtree") as mock_rmtree,
            pytest.raises(RuntimeError),
        ):
            check_conflicts.main()

        mock_rmtree.assert_called()
