"""Tests for scripts/ci/requirements-maintenance/recompile.py."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from recompile import main, output_file, pip_check, recompile_one

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


@pytest.fixture(autouse=True)
def _patch_pip_compile(tmp_path):
    with patch("recompile.PIP_COMPILE", tmp_path / "pip-compile"):
        yield


# ---------------------------------------------------------------------------
# output_file
# ---------------------------------------------------------------------------


class TestOutputFile:
    def test_replaces_in_suffix_with_txt(self) -> None:
        assert output_file(Path("requirements.in")) == Path("requirements.txt")

    def test_preserves_parent_directory(self) -> None:
        assert output_file(Path("api/requirements.in")) == Path("api/requirements.txt")

    def test_deep_path(self) -> None:
        assert output_file(Path("a/b/c/deps.in")) == Path("a/b/c/deps.txt")


# ---------------------------------------------------------------------------
# pip_check
# ---------------------------------------------------------------------------


class TestPipCheck:
    def test_returns_true_when_pip_exits_zero(self) -> None:
        with patch(
            "recompile.subprocess.run",
            return_value=_make_completed(0, "No broken requirements found."),
        ):
            ok, log = pip_check()
        assert ok is True
        assert "No broken requirements" in log

    def test_returns_false_when_pip_exits_nonzero(self) -> None:
        conflict = "somepackage 1.0 has requirement other>=2.0, but you have other 1.0."
        with patch(
            "recompile.subprocess.run", return_value=_make_completed(1, conflict)
        ):
            ok, log = pip_check()
        assert ok is False
        assert "somepackage" in log

    def test_combines_stdout_and_stderr(self) -> None:
        with patch(
            "recompile.subprocess.run", return_value=_make_completed(0, "out", "err")
        ):
            _, log = pip_check()
        assert log == "outerr"

    def test_calls_pip_in_same_directory_as_interpreter(self) -> None:
        with patch(
            "recompile.subprocess.run", return_value=_make_completed(0)
        ) as mock_run:
            pip_check()
        cmd = mock_run.call_args[0][0]
        assert cmd[0].endswith("pip") or cmd[0].endswith("pip.exe")
        assert cmd[1] == "check"


# ---------------------------------------------------------------------------
# recompile_one
# ---------------------------------------------------------------------------


class TestRecompileOne:
    def test_returns_true_on_success(self, tmp_path: Path) -> None:
        in_file = tmp_path / "requirements.in"
        in_file.write_text("django\n")
        with patch(
            "recompile.subprocess.run", return_value=_make_completed(0, "compiled")
        ):
            ok, log = recompile_one(in_file)
        assert ok is True
        assert log == "compiled"

    def test_returns_false_on_failure(self, tmp_path: Path) -> None:
        in_file = tmp_path / "requirements.in"
        in_file.write_text("django\n")
        with patch(
            "recompile.subprocess.run",
            return_value=_make_completed(1, "", "Could not find a version"),
        ):
            ok, log = recompile_one(in_file)
        assert ok is False
        assert "Could not find" in log

    def test_passes_correct_flags(self, tmp_path: Path) -> None:
        in_file = tmp_path / "requirements.in"
        in_file.write_text("")
        with patch(
            "recompile.subprocess.run", return_value=_make_completed(0)
        ) as mock_run:
            recompile_one(in_file)
        cmd = mock_run.call_args[0][0]
        assert "--upgrade" in cmd
        assert "--quiet" in cmd
        assert "--no-header" in cmd
        assert "--no-annotations" in cmd

    def test_output_file_path_passed_correctly(self, tmp_path: Path) -> None:
        in_file = tmp_path / "requirements.in"
        in_file.write_text("")
        with patch(
            "recompile.subprocess.run", return_value=_make_completed(0)
        ) as mock_run:
            recompile_one(in_file)
        cmd = mock_run.call_args[0][0]
        out_idx = cmd.index("--output-file") + 1
        assert cmd[out_idx] == str(tmp_path / "requirements.txt")

    def test_input_file_is_last_argument(self, tmp_path: Path) -> None:
        in_file = tmp_path / "requirements.in"
        in_file.write_text("")
        with patch(
            "recompile.subprocess.run", return_value=_make_completed(0)
        ) as mock_run:
            recompile_one(in_file)
        cmd = mock_run.call_args[0][0]
        assert cmd[-1] == str(in_file)

    def test_combines_stdout_and_stderr_in_log(self, tmp_path: Path) -> None:
        in_file = tmp_path / "requirements.in"
        in_file.write_text("")
        with patch(
            "recompile.subprocess.run", return_value=_make_completed(0, "out", "err")
        ):
            _, log = recompile_one(in_file)
        assert log == "outerr"


# ---------------------------------------------------------------------------
# main — environment parsing
# ---------------------------------------------------------------------------


class TestMainEnvParsing:
    def test_missing_env_var_returns_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ORDERED_GROUPS", raising=False)
        assert main() == 1

    def test_empty_env_var_returns_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ORDERED_GROUPS", "")
        assert main() == 1

    def test_invalid_json_returns_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ORDERED_GROUPS", "{not valid json")
        assert main() == 1

    def test_empty_groups_list_runs_pip_check(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([]))
        with patch("recompile.pip_check", return_value=(True, "")) as mock_check:
            result = main()
        mock_check.assert_called_once()
        assert result == 0


# ---------------------------------------------------------------------------
# main — compile loop
# ---------------------------------------------------------------------------


class TestMainCompileLoop:
    def test_skips_missing_files(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        monkeypatch.setenv(
            "ORDERED_GROUPS", json.dumps([[str(tmp_path / "missing.in")]])
        )
        with patch("recompile.pip_check", return_value=(True, "")):
            result = main()
        assert result == 0
        assert "SKIP" in capsys.readouterr().out

    def test_successful_compile_returns_0(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        in_file = tmp_path / "requirements.in"
        in_file.write_text("django\n")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(in_file)]]))
        with (
            patch("recompile.recompile_one", return_value=(True, "")),
            patch("recompile.pip_check", return_value=(True, "")),
        ):
            result = main()
        assert result == 0

    def test_failed_compile_returns_1(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        in_file = tmp_path / "requirements.in"
        in_file.write_text("django\n")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(in_file)]]))
        with patch("recompile.recompile_one", return_value=(False, "resolution error")):
            result = main()
        assert result == 1

    def test_compile_failure_skips_pip_check(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        in_file = tmp_path / "requirements.in"
        in_file.write_text("django\n")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(in_file)]]))
        with (
            patch("recompile.recompile_one", return_value=(False, "error")),
            patch("recompile.pip_check") as mock_check,
        ):
            main()
        mock_check.assert_not_called()

    def test_processes_multiple_groups_in_order(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        file_a = tmp_path / "a.in"
        file_b = tmp_path / "b.in"
        file_a.write_text("")
        file_b.write_text("")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(file_a)], [str(file_b)]]))
        call_order: list[str] = []

        def fake_compile(in_path: Path) -> tuple[bool, str]:
            call_order.append(in_path.name)
            return True, ""

        with (
            patch("recompile.recompile_one", side_effect=fake_compile),
            patch("recompile.pip_check", return_value=(True, "")),
        ):
            result = main()

        assert result == 0
        assert call_order == ["a.in", "b.in"]

    def test_processes_multiple_files_within_group(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        file_a = tmp_path / "a.in"
        file_b = tmp_path / "b.in"
        file_a.write_text("")
        file_b.write_text("")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(file_a), str(file_b)]]))
        compiled: list[str] = []

        def fake_compile(in_path: Path) -> tuple[bool, str]:
            compiled.append(in_path.name)
            return True, ""

        with (
            patch("recompile.recompile_one", side_effect=fake_compile),
            patch("recompile.pip_check", return_value=(True, "")),
        ):
            main()

        assert set(compiled) == {"a.in", "b.in"}

    def test_collects_all_failures_before_returning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """All files in a group are attempted even if one fails."""
        file_a = tmp_path / "a.in"
        file_b = tmp_path / "b.in"
        file_a.write_text("")
        file_b.write_text("")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(file_a), str(file_b)]]))
        with patch("recompile.recompile_one", return_value=(False, "error")):
            result = main()
        out = capsys.readouterr().out
        assert result == 1
        assert "a.in" in out
        assert "b.in" in out


# ---------------------------------------------------------------------------
# main — pip check integration
# ---------------------------------------------------------------------------


class TestMainPipCheck:
    def test_pip_check_failure_returns_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([]))
        with patch("recompile.pip_check", return_value=(False, "conflict detected")):
            result = main()
        assert result == 1

    def test_pip_check_output_printed(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([]))
        with patch(
            "recompile.pip_check", return_value=(True, "No broken requirements found.")
        ):
            main()
        assert "No broken requirements found." in capsys.readouterr().out

    def test_pip_check_called_exactly_once_on_success(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        in_file = tmp_path / "requirements.in"
        in_file.write_text("")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(in_file)]]))
        with (
            patch("recompile.recompile_one", return_value=(True, "")),
            patch("recompile.pip_check", return_value=(True, "")) as mock_check,
        ):
            main()
        mock_check.assert_called_once()
