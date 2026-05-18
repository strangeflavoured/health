"""Tests for recompile.py — requirements recompilation in DAG order.

Security focus: ``recompile_one`` and ``pip_check`` must invoke uv via
``subprocess.run`` with a list (no shell=True); paths from ORDERED_GROUPS
flow through Path/str without ever reaching a shell.

Safety focus: ``main()`` must collect every failure and skip the
post-compile pip-check whenever any compile failed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.ci.requirements_maintenance.recompile as recompile  # noqa: E402

# ---------------------------------------------------------------------------
# Module-local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_uv(monkeypatch):
    """Replace ``get_uv()`` so the command-list build never raises."""
    monkeypatch.setattr(recompile, "get_uv", lambda: "uv")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


# ---------------------------------------------------------------------------
# output_file
# ---------------------------------------------------------------------------


class TestOutputFile:
    def test_replaces_in_suffix_with_txt(self):
        assert recompile.output_file(Path("requirements.in")) == Path(
            "requirements.txt"
        )

    def test_preserves_parent_directory(self):
        assert recompile.output_file(Path("api/requirements.in")) == Path(
            "api/requirements.txt"
        )

    def test_deep_path(self):
        assert recompile.output_file(Path("a/b/c/deps.in")) == Path("a/b/c/deps.txt")

    def test_input_object_not_mutated(self):
        p = Path("requirements.in")
        recompile.output_file(p)
        assert p == Path("requirements.in")


# ---------------------------------------------------------------------------
# pip_check
# ---------------------------------------------------------------------------


class TestPipCheck:
    def test_returns_true_when_pip_exits_zero(self):
        with patch(
            "subprocess.run",
            return_value=_make_completed(0, "No broken requirements found."),
        ):
            ok, log = recompile.pip_check()
        assert ok is True
        assert "No broken requirements" in log

    def test_returns_false_when_pip_exits_nonzero(self):
        conflict = "somepackage 1.0 has requirement other>=2.0, but you have other 1.0."
        with patch("subprocess.run", return_value=_make_completed(1, conflict)):
            ok, log = recompile.pip_check()
        assert ok is False
        assert "somepackage" in log

    def test_combines_stdout_and_stderr(self):
        with patch("subprocess.run", return_value=_make_completed(0, "out", "err")):
            _, log = recompile.pip_check()
        assert log == "outerr"

    def test_calls_uv_pip_check(self):
        """Command line must be ``[<uv>, "pip", "check"]`` exactly."""
        with patch("subprocess.run", return_value=_make_completed(0)) as mock_run:
            recompile.pip_check()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["uv", "pip", "check"]

    def test_command_does_not_use_shell(self):
        with patch("subprocess.run", return_value=_make_completed(0)) as mock_run:
            recompile.pip_check()
        assert mock_run.call_args.kwargs.get("shell", False) is False


# ---------------------------------------------------------------------------
# recompile_one
# ---------------------------------------------------------------------------


class TestRecompileOne:
    def test_returns_true_on_success(self, tmp_path):
        in_file = tmp_path / "requirements.in"
        in_file.write_text("django\n")
        with patch("subprocess.run", return_value=_make_completed(0, "compiled")):
            ok, log = recompile.recompile_one(in_file)
        assert ok is True
        assert log == "compiled"

    def test_returns_false_on_failure(self, tmp_path):
        in_file = tmp_path / "requirements.in"
        in_file.write_text("django\n")
        with patch(
            "subprocess.run",
            return_value=_make_completed(1, "", "Could not find a version"),
        ):
            ok, log = recompile.recompile_one(in_file)
        assert ok is False
        assert "Could not find" in log

    def test_passes_correct_flags(self, tmp_path):
        """Verify all flags actually present in the implementation."""
        in_file = tmp_path / "requirements.in"
        in_file.write_text("")
        with patch("subprocess.run", return_value=_make_completed(0)) as mock_run:
            recompile.recompile_one(in_file)
        cmd = mock_run.call_args[0][0]
        assert "--upgrade" in cmd
        assert "--quiet" in cmd
        assert "--generate-hashes" in cmd
        assert "--allow-unsafe" in cmd
        assert "--output-file" in cmd

    def test_output_file_path_passed_correctly(self, tmp_path):
        in_file = tmp_path / "requirements.in"
        in_file.write_text("")
        with patch("subprocess.run", return_value=_make_completed(0)) as mock_run:
            recompile.recompile_one(in_file)
        cmd = mock_run.call_args[0][0]
        out_idx = cmd.index("--output-file") + 1
        assert cmd[out_idx] == str(tmp_path / "requirements.txt")

    def test_input_file_is_last_argument(self, tmp_path):
        in_file = tmp_path / "requirements.in"
        in_file.write_text("")
        with patch("subprocess.run", return_value=_make_completed(0)) as mock_run:
            recompile.recompile_one(in_file)
        cmd = mock_run.call_args[0][0]
        assert cmd[-1] == str(in_file)

    def test_combines_stdout_and_stderr_in_log(self, tmp_path):
        in_file = tmp_path / "requirements.in"
        in_file.write_text("")
        with patch("subprocess.run", return_value=_make_completed(0, "out", "err")):
            _, log = recompile.recompile_one(in_file)
        assert log == "outerr"

    def test_command_does_not_use_shell(self, tmp_path):
        in_file = tmp_path / "requirements.in"
        in_file.write_text("")
        with patch("subprocess.run", return_value=_make_completed(0)) as mock_run:
            recompile.recompile_one(in_file)
        assert mock_run.call_args.kwargs.get("shell", False) is False

    def test_path_with_shell_metacharacters_passed_literally(self, tmp_path):
        """An in_path containing shell metacharacters must reach uv verbatim,
        not as a shell-interpreted command.
        """
        evil = tmp_path / "a; echo PWND.in"
        evil.write_text("")
        with patch("subprocess.run", return_value=_make_completed(0)) as mock_run:
            recompile.recompile_one(evil)
        cmd = mock_run.call_args[0][0]
        assert cmd[-1] == str(evil)
        # The semicolon and space appear inside a single argv element, never split.
        assert "; echo PWND" in cmd[-1]


# ---------------------------------------------------------------------------
# main() — env parsing
# ---------------------------------------------------------------------------


class TestMainEnvParsing:
    def test_missing_env_var_returns_1(self, monkeypatch):
        monkeypatch.delenv("ORDERED_GROUPS", raising=False)
        assert recompile.main() == 1

    def test_empty_env_var_returns_1(self, monkeypatch):
        monkeypatch.setenv("ORDERED_GROUPS", "")
        assert recompile.main() == 1

    def test_invalid_json_returns_1(self, monkeypatch):
        monkeypatch.setenv("ORDERED_GROUPS", "{not valid json")
        assert recompile.main() == 1

    def test_empty_groups_list_runs_pip_check(self, monkeypatch):
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([]))
        with patch.object(
            recompile, "pip_check", return_value=(True, "")
        ) as mock_check:
            result = recompile.main()
        mock_check.assert_called_once()
        assert result == 0


# ---------------------------------------------------------------------------
# main() — compile loop
# ---------------------------------------------------------------------------


class TestMainCompileLoop:
    def test_skips_missing_files(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setenv(
            "ORDERED_GROUPS", json.dumps([[str(tmp_path / "missing.in")]])
        )
        with patch.object(recompile, "pip_check", return_value=(True, "")):
            result = recompile.main()
        assert result == 0
        assert "SKIP" in capsys.readouterr().out

    def test_successful_compile_returns_0(self, monkeypatch, tmp_path):
        in_file = tmp_path / "requirements.in"
        in_file.write_text("django\n")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(in_file)]]))
        with (
            patch.object(recompile, "recompile_one", return_value=(True, "")),
            patch.object(recompile, "pip_check", return_value=(True, "")),
        ):
            assert recompile.main() == 0

    def test_failed_compile_returns_1(self, monkeypatch, tmp_path):
        in_file = tmp_path / "requirements.in"
        in_file.write_text("django\n")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(in_file)]]))
        with patch.object(
            recompile, "recompile_one", return_value=(False, "resolution error")
        ):
            assert recompile.main() == 1

    def test_compile_failure_skips_pip_check(self, monkeypatch, tmp_path):
        in_file = tmp_path / "requirements.in"
        in_file.write_text("django\n")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(in_file)]]))
        with (
            patch.object(recompile, "recompile_one", return_value=(False, "error")),
            patch.object(recompile, "pip_check") as mock_check,
        ):
            recompile.main()
        mock_check.assert_not_called()

    def test_processes_multiple_groups_in_order(self, monkeypatch, tmp_path):
        file_a = tmp_path / "a.in"
        file_b = tmp_path / "b.in"
        file_a.write_text("")
        file_b.write_text("")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(file_a)], [str(file_b)]]))
        call_order: list[str] = []

        def fake_compile(in_path):
            call_order.append(in_path.name)
            return True, ""

        with (
            patch.object(recompile, "recompile_one", side_effect=fake_compile),
            patch.object(recompile, "pip_check", return_value=(True, "")),
        ):
            assert recompile.main() == 0
        assert call_order == ["a.in", "b.in"]

    def test_processes_multiple_files_within_group(self, monkeypatch, tmp_path):
        file_a = tmp_path / "a.in"
        file_b = tmp_path / "b.in"
        file_a.write_text("")
        file_b.write_text("")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(file_a), str(file_b)]]))
        compiled: list[str] = []

        def fake_compile(in_path):
            compiled.append(in_path.name)
            return True, ""

        with (
            patch.object(recompile, "recompile_one", side_effect=fake_compile),
            patch.object(recompile, "pip_check", return_value=(True, "")),
        ):
            recompile.main()
        assert set(compiled) == {"a.in", "b.in"}

    def test_collects_all_failures_before_returning(
        self, monkeypatch, tmp_path, capsys
    ):
        """All files in a group are attempted even when one fails."""
        file_a = tmp_path / "a.in"
        file_b = tmp_path / "b.in"
        file_a.write_text("")
        file_b.write_text("")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(file_a), str(file_b)]]))
        with patch.object(recompile, "recompile_one", return_value=(False, "error")):
            result = recompile.main()
        out = capsys.readouterr().out
        assert result == 1
        assert "a.in" in out
        assert "b.in" in out

    def test_ordered_groups_with_special_chars_in_path(self, monkeypatch, tmp_path):
        """A path containing semicolons survives JSON round-trip and reaches
        ``recompile_one`` as a literal Path, not a shell-split string.
        """
        weird = tmp_path / "weird; name.in"
        weird.write_text("")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(weird)]]))
        seen: list[Path] = []

        def fake_compile(in_path):
            seen.append(in_path)
            return True, ""

        with (
            patch.object(recompile, "recompile_one", side_effect=fake_compile),
            patch.object(recompile, "pip_check", return_value=(True, "")),
        ):
            recompile.main()
        assert len(seen) == 1
        assert seen[0] == weird


# ---------------------------------------------------------------------------
# main() — pip check integration
# ---------------------------------------------------------------------------


class TestMainPipCheck:
    def test_pip_check_failure_returns_1(self, monkeypatch):
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([]))
        with patch.object(recompile, "pip_check", return_value=(False, "conflict")):
            assert recompile.main() == 1

    def test_pip_check_output_printed(self, monkeypatch, capsys):
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([]))
        with patch.object(
            recompile, "pip_check", return_value=(True, "No broken requirements found.")
        ):
            recompile.main()
        assert "No broken requirements found." in capsys.readouterr().out

    def test_pip_check_called_exactly_once_on_success(self, monkeypatch, tmp_path):
        in_file = tmp_path / "requirements.in"
        in_file.write_text("")
        monkeypatch.setenv("ORDERED_GROUPS", json.dumps([[str(in_file)]]))
        with (
            patch.object(recompile, "recompile_one", return_value=(True, "")),
            patch.object(recompile, "pip_check", return_value=(True, "")) as mock_check,
        ):
            recompile.main()
        mock_check.assert_called_once()
