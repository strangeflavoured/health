"""Tests for check_conflicts.py — dependency conflict detection.

Security focus: ``run_capture`` must reject missing executables before any
subprocess is launched; ``slug`` must produce filesystem-safe names so per-
stack log files cannot escape the reports directory.

Safety focus: ``check_stack`` must not crash on any stack shape (empty,
missing-file, install-fail, check-fail); ``main`` aggregates results
without losing failures.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.ci.requirements_maintenance.check_conflicts as check_conflicts  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_uv(monkeypatch):
    """Prevent ``get_uv()`` from raising in environments without uv on PATH.

    ``check_stack`` and ``main`` call ``get_uv()`` as part of building the
    command list passed to ``run_capture``; the call happens before any mock
    on ``run_capture`` can intercept it.  Replacing ``get_uv`` with a lambda
    returning a harmless string is sufficient — the resulting command list
    is then captured by the mock without ever spawning a subprocess.
    """
    monkeypatch.setattr(check_conflicts, "get_uv", lambda: "uv")


@pytest.fixture(autouse=True)
def _restore_reports():
    """Restore ``check_conflicts.REPORTS`` after every test that mutates it.

    The module attribute is evaluated at import time from ``REPORTS_DIR``;
    tests overwrite it directly to redirect output to a tmp directory.
    Without restoration, a later test in the session can see a stale Path
    pointing at a deleted tmp dir.
    """
    original = check_conflicts.REPORTS
    yield
    check_conflicts.REPORTS = original


# ---------------------------------------------------------------------------
# slug / stack_label
# ---------------------------------------------------------------------------


class TestSlug:
    def test_replaces_slashes(self):
        assert "/" not in check_conflicts.slug("a/b/c.in")

    def test_replaces_dots(self):
        assert "." not in check_conflicts.slug("req.in")

    def test_replaces_plus(self):
        assert "+" not in check_conflicts.slug("a+b")

    def test_stable_on_repeated_call(self):
        assert check_conflicts.slug("x/y.in") == check_conflicts.slug("x/y.in")

    def test_path_traversal_dots_not_normalised(self):
        """slug() only remaps '.' '/' '+'; verify no '/' or '..' survives.

        The slug is used as a filename suffix inside REPORTS; the directory
        write target is REPORTS/install-<slug>.log via str concat.  Verify
        that '..' input cannot produce a filename containing a separator
        sequence that pathlib would interpret as a parent reference.
        """
        result = check_conflicts.slug("../etc/passwd")
        assert "/" not in result
        assert ".." not in result
        # Both '.' and '/' are remapped to '-', so '../' yields '---'.
        assert result == "---etc-passwd"

    def test_does_not_strip_or_escape_other_chars(self):
        """Document the limited scope of slug(): only / . + are remapped."""
        # Backslash, semicolon, dollar etc are passed through; the caller
        # must not splice slug output into anything shell-interpreted.
        assert check_conflicts.slug("a;b") == "a;b"
        assert check_conflicts.slug("a$b") == "a$b"
        assert check_conflicts.slug("a\\b") == "a\\b"


class TestStackLabel:
    def test_single_file(self):
        assert check_conflicts.stack_label(["requirements/base.txt"]) == "base"

    def test_multiple_files_joined(self):
        label = check_conflicts.stack_label(["base.txt", "api.txt"])
        assert "base" in label
        assert "api" in label
        assert "+" in label

    def test_order_preserved(self):
        label = check_conflicts.stack_label(["first.txt", "second.txt"])
        assert label.index("first") < label.index("second")

    def test_empty_stack(self):
        assert check_conflicts.stack_label([]) == ""


# ---------------------------------------------------------------------------
# run_capture
# ---------------------------------------------------------------------------


class TestRunCapture:
    def test_success_returns_zero_and_output(self):
        code, log = check_conflicts.run_capture(["echo", "hello"])
        assert code == 0
        assert "hello" in log

    def test_failure_returns_nonzero(self):
        code, _log = check_conflicts.run_capture(["false"])
        assert code != 0

    def test_missing_executable_raises(self):
        with pytest.raises(FileNotFoundError):
            check_conflicts.run_capture(["__no_such_binary__"])

    def test_stderr_captured(self):
        _, log = check_conflicts.run_capture(
            ["python3", "-c", "import sys; sys.stderr.write('err_msg')"]
        )
        assert "err_msg" in log

    def test_stdout_and_stderr_combined(self):
        _, log = check_conflicts.run_capture(
            [
                "python3",
                "-c",
                "import sys; sys.stdout.write('out'); sys.stderr.write('err')",
            ]
        )
        assert "out" in log
        assert "err" in log

    def test_does_not_invoke_shell(self):
        """Arguments must be passed to subprocess as a list, not shell-evaluated.

        If subprocess were invoked with ``shell=True`` a metacharacter in
        argv[1] could spawn an unintended subprocess.  Here we pass ``;
        echo PWND`` as a single argument to ``echo``; the literal string
        must appear in the output, with no ``PWND`` line.
        """
        code, log = check_conflicts.run_capture(["echo", "; echo PWND"])
        assert code == 0
        # echo prints its argument literally; the metacharacters never reach a shell.
        assert "; echo PWND" in log
        # And the implicit assertion: PWND only appears as part of our literal.
        assert log.count("PWND") == 1


# ---------------------------------------------------------------------------
# check_stack
# ---------------------------------------------------------------------------


class TestCheckStack:
    def test_missing_txt_file_marks_install_failed(self, tmp_path):
        check_conflicts.REPORTS = tmp_path
        stack = ["nonexistent.txt"]
        with patch.object(check_conflicts, "run_capture") as mock_run:
            mock_run.return_value = (0, "some output")
            result = check_conflicts.check_stack(stack, tmp_path / "venv")
        assert result["install_ok"] is False
        assert f"--- {stack[0]} ---\nMISSING" in result["install_log"]

    def test_uv_venv_failure_marks_install_failed(self, tmp_path):
        check_conflicts.REPORTS = tmp_path
        with patch.object(check_conflicts, "run_capture") as mock_run:
            mock_run.return_value = (1, "venv creation failed")
            result = check_conflicts.check_stack(["req.txt"], tmp_path / "venv")
        assert result["install_ok"] is False
        assert "venv failed" in result["install_log"]

    def test_install_failure_marks_install_failed(self, tmp_path):
        check_conflicts.REPORTS = tmp_path
        txt = tmp_path / "requirements.txt"
        txt.write_text("requests==2.0.0\n")

        def fake_run(cmd):
            if "venv" in cmd:
                python = tmp_path / "venv" / "bin" / "python"
                python.parent.mkdir(parents=True, exist_ok=True)
                python.touch()
                return (0, "")
            if "install" in cmd:
                return (1, "install failed: conflict")
            return (0, "No issues found")

        with patch.object(check_conflicts, "run_capture", side_effect=fake_run):
            result = check_conflicts.check_stack([str(txt)], tmp_path / "venv")
        assert result["install_ok"] is False

    def test_pip_check_failure_recorded(self, tmp_path):
        check_conflicts.REPORTS = tmp_path
        txt = tmp_path / "requirements.txt"
        txt.write_text("requests==2.0.0\n")

        def fake_run(cmd):
            if "venv" in cmd:
                python = tmp_path / "venv" / "bin" / "python"
                python.parent.mkdir(parents=True, exist_ok=True)
                python.touch()
                return (0, "")
            if "install" in cmd:
                return (0, "")
            if "check" in cmd:
                return (1, "packageA 1.0 has requirement packageB>=2.0")
            return (0, "")

        with patch.object(check_conflicts, "run_capture", side_effect=fake_run):
            result = check_conflicts.check_stack([str(txt)], tmp_path / "venv")
        assert result["check_ok"] is False
        assert "packageA" in result["check_log"]

    def test_success_path(self, tmp_path):
        check_conflicts.REPORTS = tmp_path
        txt = tmp_path / "requirements.txt"
        txt.write_text("requests==2.0.0\n")

        def fake_run(cmd):
            if "venv" in cmd:
                python = tmp_path / "venv" / "bin" / "python"
                python.parent.mkdir(parents=True, exist_ok=True)
                python.touch()
                return (0, "")
            return (0, "No issues found")

        with patch.object(check_conflicts, "run_capture", side_effect=fake_run):
            result = check_conflicts.check_stack([str(txt)], tmp_path / "venv")
        assert result["install_ok"] is True
        assert result["check_ok"] is True

    def test_logs_written_to_reports(self, tmp_path):
        check_conflicts.REPORTS = tmp_path
        txt = tmp_path / "requirements.txt"
        txt.write_text("requests==2.0.0\n")

        def fake_run(cmd):
            if "venv" in cmd:
                python = tmp_path / "venv" / "bin" / "python"
                python.parent.mkdir(parents=True, exist_ok=True)
                python.touch()
                return (0, "")
            return (0, "ok")

        with patch.object(check_conflicts, "run_capture", side_effect=fake_run):
            check_conflicts.check_stack([str(txt)], tmp_path / "venv")
        log_files = list(tmp_path.glob("*.log"))
        assert len(log_files) >= 1

    def test_install_install_require_hashes_flag(self, tmp_path):
        """Install must use --require-hashes to enforce hash-pinned dependencies.

        This is a security-critical flag: without it, pip will accept any
        version that matches the spec, defeating the lockfile guarantee.
        """
        check_conflicts.REPORTS = tmp_path
        txt = tmp_path / "requirements.txt"
        txt.write_text("requests==2.0.0\n")

        captured_cmds: list[list[str]] = []

        def fake_run(cmd):
            captured_cmds.append(cmd)
            if "venv" in cmd:
                python = tmp_path / "venv" / "bin" / "python"
                python.parent.mkdir(parents=True, exist_ok=True)
                python.touch()
                return (0, "")
            return (0, "")

        with patch.object(check_conflicts, "run_capture", side_effect=fake_run):
            check_conflicts.check_stack([str(txt)], tmp_path / "venv")

        install_cmds = [c for c in captured_cmds if "install" in c]
        assert install_cmds, "no install command was issued"
        assert "--require-hashes" in install_cmds[0]


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestMain:
    def _run_main_with_stacks(self, stacks, reports_dir, monkeypatch, fake_run=None):
        monkeypatch.setenv("STACKS", json.dumps(stacks))
        check_conflicts.REPORTS = reports_dir
        if fake_run:
            with patch.object(check_conflicts, "run_capture", side_effect=fake_run):
                return check_conflicts.main()
        return check_conflicts.main()

    def test_empty_stacks_returns_zero(self, tmp_path, monkeypatch):
        rc = self._run_main_with_stacks([], tmp_path, monkeypatch)
        assert rc == 0

    def test_conflicts_json_written(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STACKS", "[]")
        check_conflicts.REPORTS = tmp_path
        check_conflicts.main()
        assert (tmp_path / "conflicts.json").exists()

    def test_returns_nonzero_on_install_failure(self, tmp_path, monkeypatch):
        txt = tmp_path / "requirements.txt"
        txt.write_text("requests\n")

        def fake_run(cmd):
            if "venv" in cmd:
                python = tmp_path / "venv2" / "bin" / "python"
                python.parent.mkdir(parents=True, exist_ok=True)
                python.touch()
                return (0, "")
            if "install" in cmd:
                return (1, "conflict!")
            return (0, "")

        rc = self._run_main_with_stacks(
            [[str(txt)]], tmp_path, monkeypatch, fake_run=fake_run
        )
        assert rc == 1

    def test_returns_zero_when_all_pass(self, tmp_path, monkeypatch):
        txt = tmp_path / "requirements.txt"
        txt.write_text("requests\n")

        def fake_run(cmd):
            if "venv" in cmd:
                python = tmp_path / "venv3" / "bin" / "python"
                python.parent.mkdir(parents=True, exist_ok=True)
                python.touch()
                return (0, "")
            return (0, "No issues")

        rc = self._run_main_with_stacks(
            [[str(txt)]], tmp_path, monkeypatch, fake_run=fake_run
        )
        assert rc == 0

    def test_summary_counts_printed(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("STACKS", "[]")
        check_conflicts.REPORTS = tmp_path
        check_conflicts.main()
        captured = capsys.readouterr()
        assert "stacks" in captured.out.lower()

    def test_missing_stacks_env_defaults_to_empty(self, tmp_path, monkeypatch):
        monkeypatch.delenv("STACKS", raising=False)
        check_conflicts.REPORTS = tmp_path
        rc = check_conflicts.main()
        assert rc == 0

    def test_exception_during_check_is_caught_and_recorded(
        self,
        tmp_path,
        monkeypatch,
        capsys,  # noqa: ARG002
    ):
        """A raise in check_stack must not abort the loop — it's caught
        and the failure is recorded against the stack.
        """
        txt = tmp_path / "requirements.txt"
        txt.write_text("requests\n")

        def fake_run(_cmd):
            raise RuntimeError("simulated catastrophic failure")

        rc = self._run_main_with_stacks(
            [[str(txt)]], tmp_path, monkeypatch, fake_run=fake_run
        )
        assert rc == 1
        results = json.loads((tmp_path / "conflicts.json").read_text())
        # Exactly one result was recorded
        assert len(results) == 1
        only = next(iter(results.values()))
        assert only["install_ok"] is False
        assert "exception" in only["install_log"].lower()
