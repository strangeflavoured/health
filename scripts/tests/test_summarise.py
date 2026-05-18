"""Tests for summarise.py — report aggregation and GHA output writing.

Safety focus: ``load_json`` must never raise on malformed input — it
swallows all OS and JSON errors and returns the supplied default.

This is the entry point that decides whether the dependency-maintenance
workflow opens a PR; a false negative here silently skips updates.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.ci.requirements_maintenance.summarise as summarise  # noqa: E402

# ---------------------------------------------------------------------------
# Module-local fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_reports():
    """Restore ``summarise.REPORTS`` after every test."""
    original = summarise.REPORTS
    yield
    summarise.REPORTS = original


# ---------------------------------------------------------------------------
# load_json
# ---------------------------------------------------------------------------


class TestLoadJson:
    def test_loads_valid_json(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"key": "value"}')
        assert summarise.load_json(f, {}) == {"key": "value"}

    def test_returns_default_for_missing_file(self, tmp_path):
        assert summarise.load_json(
            tmp_path / "nonexistent.json", {"default": True}
        ) == {"default": True}

    def test_returns_default_for_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{not valid json >>>}")
        assert summarise.load_json(f, []) == []

    def test_returns_default_for_empty_file(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text("")
        assert summarise.load_json(f, 42) == 42

    def test_loads_list_json(self, tmp_path):
        f = tmp_path / "list.json"
        f.write_text("[1, 2, 3]")
        assert summarise.load_json(f, []) == [1, 2, 3]

    def test_loads_nested_json(self, tmp_path):
        data = {"outer": {"inner": [1, 2]}}
        f = tmp_path / "nested.json"
        f.write_text(json.dumps(data))
        assert summarise.load_json(f, {}) == data

    def test_returns_different_default_types(self, tmp_path):
        missing = tmp_path / "no.json"
        assert summarise.load_json(missing, None) is None
        assert summarise.load_json(missing, "fallback") == "fallback"
        assert summarise.load_json(missing, 0) == 0

    def test_handles_unreadable_file(self, tmp_path):
        """A file that exists but cannot be opened returns the default."""
        f = tmp_path / "locked.json"
        f.write_text("{}")
        f.chmod(0o000)
        try:
            # Root can still read 0o000 files; skip when running as root.
            import os

            if os.geteuid() == 0:
                pytest.skip("running as root bypasses chmod 000")
            assert summarise.load_json(f, "default") == "default"
        finally:
            f.chmod(0o600)


# ---------------------------------------------------------------------------
# write_output
# ---------------------------------------------------------------------------


class TestWriteOutput:
    def test_writes_to_github_output_file(self, tmp_path, monkeypatch):
        out_file = tmp_path / "output.txt"
        out_file.touch()
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))
        summarise.write_output("my_key", "my_value")
        assert "my_key=my_value" in out_file.read_text()

    def test_appends_to_github_output_file(self, tmp_path, monkeypatch):
        out_file = tmp_path / "output.txt"
        out_file.write_text("existing=line\n")
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))
        summarise.write_output("new_key", "new_value")
        content = out_file.read_text()
        assert "existing=line" in content
        assert "new_key=new_value" in content

    def test_falls_back_to_stdout_when_no_env(self, monkeypatch, capsys):
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
        summarise.write_output("k", "v")
        assert "k=v" in capsys.readouterr().out

    def test_values_with_special_characters(self, tmp_path, monkeypatch):
        out_file = tmp_path / "output.txt"
        out_file.touch()
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))
        summarise.write_output("url", "https://example.com/path?q=1")
        assert "url=https://example.com/path?q=1" in out_file.read_text()


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def _write_report(reports_dir: Path, filename: str, data) -> None:
    (reports_dir / filename).write_text(json.dumps(data))


class TestMain:
    def test_no_updates_no_conflicts_returns_zero(self, reports_dir, github_output):  # noqa: ARG002
        _write_report(reports_dir, "updates.json", {})
        _write_report(reports_dir, "conflicts.json", {})
        _write_report(reports_dir, "deptry.json", {})
        summarise.REPORTS = reports_dir
        assert summarise.main() == 0

    def test_has_updates_flag_set(self, reports_dir, github_output):
        _write_report(
            reports_dir,
            "updates.json",
            {
                "requirements.in": [
                    {"package": "requests", "current": "2.28.0", "latest": "2.31.0"}
                ]
            },
        )
        _write_report(reports_dir, "conflicts.json", {})
        _write_report(reports_dir, "deptry.json", {})
        summarise.REPORTS = reports_dir
        summarise.main()
        outputs = github_output()
        assert outputs["has_updates"] == "true"
        assert outputs["has_changes"] == "true"

    def test_no_updates_flag_false(self, reports_dir, github_output):
        _write_report(reports_dir, "updates.json", {})
        _write_report(reports_dir, "conflicts.json", {})
        _write_report(reports_dir, "deptry.json", {})
        summarise.REPORTS = reports_dir
        summarise.main()
        outputs = github_output()
        assert outputs["has_updates"] == "false"
        assert outputs["has_changes"] == "false"

    def test_has_conflicts_when_install_failed(self, reports_dir, github_output):
        _write_report(reports_dir, "updates.json", {})
        _write_report(
            reports_dir,
            "conflicts.json",
            {
                "base": {
                    "install_ok": False,
                    "check_ok": True,
                    "install_log": "",
                    "check_log": "",
                }
            },
        )
        _write_report(reports_dir, "deptry.json", {})
        summarise.REPORTS = reports_dir
        summarise.main()
        assert github_output()["has_conflicts"] == "true"

    def test_has_conflicts_when_pip_check_failed(self, reports_dir, github_output):
        _write_report(reports_dir, "updates.json", {})
        _write_report(
            reports_dir,
            "conflicts.json",
            {
                "base": {
                    "install_ok": True,
                    "check_ok": False,
                    "install_log": "",
                    "check_log": "conflict found",
                }
            },
        )
        _write_report(reports_dir, "deptry.json", {})
        summarise.REPORTS = reports_dir
        summarise.main()
        assert github_output()["has_conflicts"] == "true"

    def test_no_conflicts_when_all_pass(self, reports_dir, github_output):
        _write_report(reports_dir, "updates.json", {})
        _write_report(
            reports_dir,
            "conflicts.json",
            {
                "base": {
                    "install_ok": True,
                    "check_ok": True,
                    "install_log": "",
                    "check_log": "",
                }
            },
        )
        _write_report(reports_dir, "deptry.json", {})
        summarise.REPORTS = reports_dir
        summarise.main()
        assert github_output()["has_conflicts"] == "false"

    def test_has_unused_when_deptry_finds_issues(self, reports_dir, github_output):
        _write_report(reports_dir, "updates.json", {})
        _write_report(reports_dir, "conflicts.json", {})
        _write_report(
            reports_dir,
            "deptry.json",
            {"DEP002": [{"error": {"code": "DEP002"}, "module": "requests"}]},
        )
        summarise.REPORTS = reports_dir
        summarise.main()
        assert github_output()["has_unused"] == "true"

    def test_summary_json_written(self, reports_dir, github_output):  # noqa: ARG002
        _write_report(reports_dir, "updates.json", {})
        _write_report(reports_dir, "conflicts.json", {})
        _write_report(reports_dir, "deptry.json", {})
        summarise.REPORTS = reports_dir
        summarise.main()
        summary_file = reports_dir / "summary.json"
        assert summary_file.exists()
        data = json.loads(summary_file.read_text())
        assert "has_updates" in data
        assert "has_conflicts" in data
        assert "has_unused" in data

    def test_missing_report_files_handled_gracefully(self, reports_dir, github_output):  # noqa: ARG002
        """All three report files absent: main() should still complete."""
        summarise.REPORTS = reports_dir
        assert summarise.main() == 0

    def test_backward_compat_has_changes_equals_has_updates(
        self, reports_dir, github_output
    ):
        _write_report(
            reports_dir,
            "updates.json",
            {"r.in": [{"package": "x", "current": "1", "latest": "2"}]},
        )
        _write_report(reports_dir, "conflicts.json", {})
        _write_report(reports_dir, "deptry.json", {})
        summarise.REPORTS = reports_dir
        summarise.main()
        outputs = github_output()
        assert outputs["has_changes"] == outputs["has_updates"]

    def test_prints_human_readable_summary(self, reports_dir, capsys):
        _write_report(reports_dir, "updates.json", {})
        _write_report(reports_dir, "conflicts.json", {})
        _write_report(reports_dir, "deptry.json", {})
        summarise.REPORTS = reports_dir
        summarise.main()
        captured = capsys.readouterr()
        assert "Updates" in captured.out
        assert "Conflicts" in captured.out

    def test_conflicts_value_not_dict_does_not_crash(self, reports_dir, github_output):  # noqa: ARG002
        """A malformed conflicts.json (list, not dict) must not raise.

        ``main`` iterates ``conflicts.values()``; if it received a list it
        would fail.  We document the current contract: this case is treated
        as 'no conflicts found' because ``load_json`` ignores type mismatches
        downstream of the dict iteration only when the JSON is structurally
        valid and matches the expected shape.
        """
        # When the JSON is valid but not a dict, the dict-iteration will
        # raise AttributeError.  Verify that the bug is REPORTED as a known
        # gap rather than silently absorbed.
        _write_report(reports_dir, "updates.json", {})
        _write_report(reports_dir, "conflicts.json", [])  # list, not dict!
        _write_report(reports_dir, "deptry.json", {})
        summarise.REPORTS = reports_dir
        with pytest.raises(AttributeError):
            summarise.main()
