"""Tests for summarise.py — combining reports into outputs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import summarise


class TestLoadJson:
    def test_missing_file_returns_default(self, tmp_path: Path):
        assert summarise.load_json(tmp_path / "nope.json", {}) == {}
        assert summarise.load_json(tmp_path / "nope.json", []) == []

    def test_invalid_json_returns_default(self, tmp_path: Path):
        f = tmp_path / "bad.json"
        f.write_text("not valid json {")
        assert summarise.load_json(f, {}) == {}

    def test_valid_json(self, tmp_path: Path):
        f = tmp_path / "good.json"
        f.write_text('{"key": "value"}')
        assert summarise.load_json(f, {}) == {"key": "value"}


@pytest.fixture
def reports_dir(tmp_path: Path, monkeypatch):
    """Redirect summarise.REPORTS to a tmp dir."""
    monkeypatch.setattr(summarise, "REPORTS", tmp_path)
    return tmp_path


class TestMain:
    def test_all_clean(self, reports_dir: Path, monkeypatch, _capsys):
        (reports_dir / "updates.json").write_text("{}")
        (reports_dir / "conflicts.json").write_text("{}")
        (reports_dir / "deptry.json").write_text("{}")

        output_file = reports_dir / "gha_output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        assert summarise.main() == 0

        outputs = dict(
            line.split("=", 1)
            for line in output_file.read_text().splitlines()
            if "=" in line
        )
        assert outputs["has_updates"] == "false"
        assert outputs["has_conflicts"] == "false"
        assert outputs["has_unused"] == "false"
        assert outputs["has_changes"] == "false"

    def test_updates_detected(self, reports_dir: Path, monkeypatch):
        (reports_dir / "updates.json").write_text(
            json.dumps({"requirements.in": [{"package": "django"}]})
        )
        (reports_dir / "conflicts.json").write_text("{}")
        (reports_dir / "deptry.json").write_text("{}")

        output_file = reports_dir / "gha_output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        summarise.main()
        outputs = dict(
            line.split("=", 1)
            for line in output_file.read_text().splitlines()
            if "=" in line
        )
        assert outputs["has_updates"] == "true"
        assert outputs["has_changes"] == "true"  # alias

    def test_conflicts_detected(self, reports_dir: Path, monkeypatch):
        (reports_dir / "updates.json").write_text("{}")
        (reports_dir / "conflicts.json").write_text(
            json.dumps(
                {
                    "requirements.in": {
                        "install_ok": True,
                        "check_ok": False,  # conflict
                        "install_log": "",
                        "check_log": "pkg-a requires pkg-b<2 but you have 2.0",
                    }
                }
            )
        )
        (reports_dir / "deptry.json").write_text("{}")

        output_file = reports_dir / "gha_output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        summarise.main()
        outputs = dict(
            line.split("=", 1)
            for line in output_file.read_text().splitlines()
            if "=" in line
        )
        assert outputs["has_conflicts"] == "true"

    def test_install_failure_counts_as_conflict(self, reports_dir: Path, monkeypatch):
        (reports_dir / "updates.json").write_text("{}")
        (reports_dir / "conflicts.json").write_text(
            json.dumps(
                {
                    "requirements.in": {
                        "install_ok": False,
                        "check_ok": True,
                        "install_log": "ERROR: could not find package",
                        "check_log": "",
                    }
                }
            )
        )
        (reports_dir / "deptry.json").write_text("{}")

        output_file = reports_dir / "gha_output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        summarise.main()
        outputs = dict(
            line.split("=", 1)
            for line in output_file.read_text().splitlines()
            if "=" in line
        )
        assert outputs["has_conflicts"] == "true"

    def test_writes_summary_json(self, reports_dir: Path, monkeypatch):
        (reports_dir / "updates.json").write_text('{"a.in": []}')
        (reports_dir / "conflicts.json").write_text("{}")
        (reports_dir / "deptry.json").write_text('{"misplaced_dev_dependencies": []}')

        monkeypatch.setenv("GITHUB_OUTPUT", str(reports_dir / "out"))
        summarise.main()

        summary = json.loads((reports_dir / "summary.json").read_text())
        assert "updates" in summary
        assert "conflicts" in summary
        assert "unused" in summary

    def test_missing_files_handled(self, reports_dir: Path, monkeypatch):
        # No report files exist at all
        monkeypatch.setenv("GITHUB_OUTPUT", str(reports_dir / "out"))
        assert summarise.main() == 0

        outputs = dict(
            line.split("=", 1)
            for line in (reports_dir / "out").read_text().splitlines()
            if "=" in line
        )
        # All flags should be false when no reports exist
        assert outputs["has_updates"] == "false"
        assert outputs["has_conflicts"] == "false"
        assert outputs["has_unused"] == "false"
