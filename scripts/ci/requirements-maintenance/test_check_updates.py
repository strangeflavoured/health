"""Tests for check_updates.py — pin parsing and diff logic.

The subprocess-heavy compile_upgraded() function is tested via mocking;
parse_pins and diff_pins are pure and tested directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import check_updates

# ---------------------------------------------------------------------------
# parse_pins
# ---------------------------------------------------------------------------


class TestParsePins:
    def test_empty(self):
        assert check_updates.parse_pins("") == {}

    def test_simple_pin(self):
        assert check_updates.parse_pins("django==4.2.1\n") == {"django": "4.2.1"}

    def test_multiple_pins(self):
        text = "django==4.2.1\npytest==7.4.0\nrequests==2.31.0\n"
        result = check_updates.parse_pins(text)
        assert result == {"django": "4.2.1", "pytest": "7.4.0", "requests": "2.31.0"}

    def test_ignores_comments(self):
        text = "# header comment\ndjango==4.2.1  # inline\n"
        assert check_updates.parse_pins(text) == {"django": "4.2.1"}

    def test_ignores_blank_lines(self):
        text = "\ndjango==4.2.1\n\n\npytest==7.4.0\n\n"
        result = check_updates.parse_pins(text)
        assert result == {"django": "4.2.1", "pytest": "7.4.0"}

    def test_handles_environment_markers(self):
        text = 'tomli==2.0.1 ; python_version < "3.11"\n'
        assert check_updates.parse_pins(text) == {"tomli": "2.0.1"}

    def test_handles_hash_continuations(self):
        text = (
            "django==4.2.1 \\\n"
            "    --hash=sha256:abc123 \\\n"
            "    --hash=sha256:def456\n"
            "pytest==7.4.0\n"
        )
        result = check_updates.parse_pins(text)
        assert result == {"django": "4.2.1", "pytest": "7.4.0"}

    def test_case_insensitive_names(self):
        text = "Django==4.2.1\nPyYAML==6.0.1\n"
        result = check_updates.parse_pins(text)
        assert result == {"django": "4.2.1", "pyyaml": "6.0.1"}

    def test_skips_non_pinned_lines(self):
        # pip-tools sometimes leaves "# via X" lines, --index-url, etc.
        text = (
            "--index-url https://pypi.org/simple/\n"
            "django==4.2.1\n"
            "    # via my-package\n"
        )
        assert check_updates.parse_pins(text) == {"django": "4.2.1"}

    def test_handles_package_names_with_dots(self):
        # e.g., zope.interface, ruamel.yaml
        text = "zope.interface==5.5.0\nruamel.yaml==0.17.32\n"
        result = check_updates.parse_pins(text)
        assert result == {"zope.interface": "5.5.0", "ruamel.yaml": "0.17.32"}

    def test_handles_local_version_identifiers(self):
        # PEP 440 local versions like 1.0.0+cpu
        text = "torch==2.1.0+cpu\n"
        assert check_updates.parse_pins(text) == {"torch": "2.1.0+cpu"}

    def test_prerelease_versions(self):
        text = "some-pkg==1.0.0rc1\nother==2.0.0a3\n"
        result = check_updates.parse_pins(text)
        assert result == {"some-pkg": "1.0.0rc1", "other": "2.0.0a3"}


# ---------------------------------------------------------------------------
# diff_pins
# ---------------------------------------------------------------------------


class TestDiffPins:
    def test_no_changes(self):
        pins = {"django": "4.2.1"}
        assert check_updates.diff_pins(pins, pins) == []

    def test_version_change(self):
        current = {"django": "4.2.1"}
        upgraded = {"django": "4.2.5"}
        assert check_updates.diff_pins(current, upgraded) == [
            {"package": "django", "current": "4.2.1", "latest": "4.2.5"}
        ]

    def test_added_package(self):
        current = {"django": "4.2.1"}
        upgraded = {"django": "4.2.1", "new-pkg": "1.0.0"}
        result = check_updates.diff_pins(current, upgraded)
        assert result == [
            {"package": "new-pkg", "current": "(absent)", "latest": "1.0.0"}
        ]

    def test_removed_package(self):
        current = {"django": "4.2.1", "old-pkg": "0.1.0"}
        upgraded = {"django": "4.2.1"}
        result = check_updates.diff_pins(current, upgraded)
        assert result == [
            {"package": "old-pkg", "current": "0.1.0", "latest": "(removed)"}
        ]

    def test_results_sorted_by_package_name(self):
        current = {"zlib": "1.0", "alpha": "1.0", "middle": "1.0"}
        upgraded = {"zlib": "2.0", "alpha": "2.0", "middle": "2.0"}
        result = check_updates.diff_pins(current, upgraded)
        names = [r["package"] for r in result]
        assert names == sorted(names)

    def test_empty_inputs(self):
        assert check_updates.diff_pins({}, {}) == []

    def test_complete_replacement(self):
        current = {"a": "1.0", "b": "1.0"}
        upgraded = {"c": "1.0", "d": "1.0"}
        result = check_updates.diff_pins(current, upgraded)
        assert len(result) == 4


# ---------------------------------------------------------------------------
# compile_upgraded — subprocess wrapper, mocked
# ---------------------------------------------------------------------------


class TestCompileUpgraded:
    def test_success(self, tmp_path: Path):
        in_file = tmp_path / "requirements.in"
        in_file.write_text("django\n")
        out_file = tmp_path / "out.txt"

        with patch("check_updates.subprocess.run") as mock_run:
            mock_run.return_value = type(
                "R", (), {"returncode": 0, "stderr": "", "stdout": ""}
            )()
            assert check_updates.compile_upgraded(in_file, out_file) is True

        # Verify pip-compile was called with the right flags
        call_args = mock_run.call_args[0][0]
        assert "pip-compile" in call_args
        assert "--upgrade" in call_args
        assert str(in_file) in call_args
        assert str(out_file) in call_args

    def test_failure(self, tmp_path: Path, capsys):
        in_file = tmp_path / "requirements.in"
        in_file.write_text("nonexistent-pkg-xyz\n")
        out_file = tmp_path / "out.txt"

        with patch("check_updates.subprocess.run") as mock_run:
            mock_run.return_value = type(
                "R",
                (),
                {"returncode": 1, "stderr": "ERROR: could not find", "stdout": ""},
            )()
            assert check_updates.compile_upgraded(in_file, out_file) is False

        assert "pip-compile failed" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# main() — end-to-end with mocked pip-compile
# ---------------------------------------------------------------------------


class TestMain:
    def test_no_files(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("ALL_FILES", "[]")
        monkeypatch.setattr(check_updates, "REPORTS", tmp_path)
        assert check_updates.main() == 0
        assert (tmp_path / "updates.json").read_text() == "{}"

    def test_detects_version_bumps(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(check_updates, "REPORTS", tmp_path / "reports")
        (tmp_path / "reports").mkdir()

        (tmp_path / "requirements.in").write_text("django\n")
        (tmp_path / "requirements.txt").write_text("django==4.2.1\n")

        monkeypatch.setenv("ALL_FILES", json.dumps(["requirements.in"]))

        def fake_compile(_in_file, out_file):
            Path(out_file).write_text("django==4.2.5\n")
            return True

        monkeypatch.setattr(check_updates, "compile_upgraded", fake_compile)

        assert check_updates.main() == 0
        updates = json.loads((tmp_path / "reports" / "updates.json").read_text())
        assert "requirements.in" in updates
        assert updates["requirements.in"][0]["package"] == "django"
        assert updates["requirements.in"][0]["current"] == "4.2.1"
        assert updates["requirements.in"][0]["latest"] == "4.2.5"

    def test_no_changes_writes_empty_dict(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(check_updates, "REPORTS", tmp_path / "reports")
        (tmp_path / "reports").mkdir()

        (tmp_path / "requirements.in").write_text("django\n")
        (tmp_path / "requirements.txt").write_text("django==4.2.1\n")

        monkeypatch.setenv("ALL_FILES", json.dumps(["requirements.in"]))

        def fake_compile(_in_file, out_file):
            Path(out_file).write_text("django==4.2.1\n")  # same version
            return True

        monkeypatch.setattr(check_updates, "compile_upgraded", fake_compile)
        assert check_updates.main() == 0

        updates = json.loads((tmp_path / "reports" / "updates.json").read_text())
        assert updates == {}

    def test_missing_txt_file_skipped(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(check_updates, "REPORTS", tmp_path / "reports")
        (tmp_path / "reports").mkdir()

        (tmp_path / "requirements.in").write_text("django\n")
        # No .txt file

        monkeypatch.setenv("ALL_FILES", json.dumps(["requirements.in"]))

        # compile_upgraded shouldn't even be called
        called = []

        def fake_compile(_in_file, _out_file):
            called.append(True)
            return True

        monkeypatch.setattr(check_updates, "compile_upgraded", fake_compile)
        assert check_updates.main() == 0
        assert called == []
