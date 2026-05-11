"""Tests for build_dag.py — DAG construction logic."""

from __future__ import annotations

import json
from pathlib import Path

import build_dag
import pytest

# ---------------------------------------------------------------------------
# topo_groups — pure function, easiest to exhaustively test
# ---------------------------------------------------------------------------


class TestTopoGroups:
    def test_empty(self):
        assert build_dag.topo_groups([], {}) == []

    def test_single_file_no_deps(self):
        assert build_dag.topo_groups(["a.in"], {"a.in": []}) == [["a.in"]]

    def test_independent_files_grouped_together(self):
        keys = ["a.in", "b.in", "c.in"]
        deps = {"a.in": [], "b.in": [], "c.in": []}
        # All three have no deps -> one group, sorted
        assert build_dag.topo_groups(keys, deps) == [["a.in", "b.in", "c.in"]]

    def test_linear_chain(self):
        # c -> b -> a (c depends on b, b depends on a)
        keys = ["a.in", "b.in", "c.in"]
        deps = {"a.in": [], "b.in": ["a.in"], "c.in": ["b.in"]}
        assert build_dag.topo_groups(keys, deps) == [
            ["a.in"],
            ["b.in"],
            ["c.in"],
        ]

    def test_diamond(self):
        # d depends on b and c; b and c both depend on a
        keys = ["a.in", "b.in", "c.in", "d.in"]
        deps = {
            "a.in": [],
            "b.in": ["a.in"],
            "c.in": ["a.in"],
            "d.in": ["b.in", "c.in"],
        }
        assert build_dag.topo_groups(keys, deps) == [
            ["a.in"],
            ["b.in", "c.in"],
            ["d.in"],
        ]

    def test_cycle_raises(self):
        keys = ["a.in", "b.in"]
        deps = {"a.in": ["b.in"], "b.in": ["a.in"]}
        with pytest.raises(RuntimeError, match="Circular dependency"):
            build_dag.topo_groups(keys, deps)

    def test_self_cycle_raises(self):
        with pytest.raises(RuntimeError, match="Circular dependency"):
            build_dag.topo_groups(["a.in"], {"a.in": ["a.in"]})

    def test_dependency_outside_keys_is_ignored(self):
        # If a referenced file isn't in our discovered set, it shouldn't
        # affect ordering (treated as external).
        keys = ["a.in"]
        deps = {"a.in": ["external.in"]}
        assert build_dag.topo_groups(keys, deps) == [["a.in"]]


# ---------------------------------------------------------------------------
# get_includes — reads files, so uses tmp_path fixture
# ---------------------------------------------------------------------------


class TestGetIncludes:
    def test_no_includes(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "requirements.in"
        f.write_text("django\npytest\n")
        assert build_dag.get_includes(Path("requirements.in")) == []

    def test_single_include(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "base.in").write_text("django\n")
        (tmp_path / "dev.in").write_text("-r base.in\npytest\n")
        result = build_dag.get_includes(Path("dev.in"))
        assert result == ["base.in"]

    def test_include_via_txt_resolves_to_in(self, tmp_path: Path, monkeypatch):
        """`-r base.txt` (compiled lockfile) -> tracks base.in as the source."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "base.in").write_text("django\n")
        (tmp_path / "base.txt").write_text("django==4.2.1\n")
        (tmp_path / "dev.in").write_text("-r base.txt\npytest\n")
        result = build_dag.get_includes(Path("dev.in"))
        assert result == ["base.in"]

    def test_relative_include_across_dirs(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "shared").mkdir()
        (tmp_path / "shared" / "base.in").write_text("django\n")
        (tmp_path / "backend").mkdir()
        (tmp_path / "backend" / "dev.in").write_text("-r ../shared/base.in\npytest\n")
        result = build_dag.get_includes(Path("backend/dev.in"))
        assert result == [str(Path("shared/base.in"))]

    def test_missing_file_returns_empty(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert build_dag.get_includes(Path("does-not-exist.in")) == []

    def test_ignores_non_dash_r_lines(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "requirements.in").write_text(
            "# comment\n"
            "django\n"
            "--index-url https://example.com\n"
            "-c constraints.txt\n"  # -c is constraints, not -r
        )
        assert build_dag.get_includes(Path("requirements.in")) == []


# ---------------------------------------------------------------------------
# find_in_files — filesystem traversal
# ---------------------------------------------------------------------------


class TestFindInFiles:
    def test_no_files(self, tmp_path: Path):
        assert build_dag.find_in_files(tmp_path) == []

    def test_flat_layout(self, tmp_path: Path):
        (tmp_path / "requirements.in").touch()
        (tmp_path / "requirements-dev.in").touch()
        (tmp_path / "dev-requirements.in").touch()
        result = build_dag.find_in_files(tmp_path)
        assert len(result) == 3

    def test_directory_layout(self, tmp_path: Path):
        (tmp_path / "requirements").mkdir()
        (tmp_path / "requirements" / "base.in").touch()
        (tmp_path / "requirements" / "dev.in").touch()
        result = build_dag.find_in_files(tmp_path)
        assert len(result) == 2

    def test_deduplicates_overlapping_matches(self, tmp_path: Path):
        # requirements/requirements.in matches BOTH glob patterns
        (tmp_path / "requirements").mkdir()
        f = tmp_path / "requirements" / "requirements.in"
        f.touch()
        result = build_dag.find_in_files(tmp_path)
        assert result == [f]

    def test_ignores_txt_files(self, tmp_path: Path):
        (tmp_path / "requirements.in").touch()
        (tmp_path / "requirements.txt").touch()
        assert len(build_dag.find_in_files(tmp_path)) == 1

    def test_results_are_sorted(self, tmp_path: Path):
        (tmp_path / "z-requirements.in").touch()
        (tmp_path / "a-requirements.in").touch()
        (tmp_path / "m-requirements.in").touch()
        result = build_dag.find_in_files(tmp_path)
        names = [p.name for p in result]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# write_output — GHA integration
# ---------------------------------------------------------------------------


class TestWriteOutput:
    def test_writes_to_github_output(self, tmp_path: Path, monkeypatch):
        output_file = tmp_path / "gha_output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
        build_dag.write_output("foo", "bar")
        build_dag.write_output("baz", "qux")
        assert output_file.read_text() == "foo=bar\nbaz=qux\n"

    def test_falls_back_to_stdout_locally(self, capsys, monkeypatch):
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
        build_dag.write_output("foo", "bar")
        assert "foo=bar" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# End-to-end: main() with a real directory tree
# ---------------------------------------------------------------------------


class TestMainEndToEnd:
    def test_full_run_with_fixture(self, tmp_path: Path, monkeypatch):
        # Set up a realistic .in file structure
        (tmp_path / "backend").mkdir()
        (tmp_path / "backend" / "requirements.in").write_text("django\n")
        (tmp_path / "backend" / "requirements-dev.in").write_text(
            "-r requirements.in\npytest\n"
        )
        (tmp_path / "frontend").mkdir()
        (tmp_path / "frontend" / "requirements.in").write_text("requests\n")

        output_file = tmp_path / "gha_output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
        monkeypatch.chdir(tmp_path)

        assert build_dag.main() == 0

        lines = dict(
            line.split("=", 1)
            for line in output_file.read_text().splitlines()
            if "=" in line
        )
        assert lines["has_files"] == "true"
        groups = json.loads(lines["ordered_groups"])
        all_files = json.loads(lines["all_files"])

        assert len(groups) == 2
        # Group 0: leaves (no .in deps)
        assert "backend/requirements.in" in groups[0]
        assert "frontend/requirements.in" in groups[0]
        # Group 1: dev file that depends on backend/requirements.in
        assert groups[1] == ["backend/requirements-dev.in"]
        assert len(all_files) == 3

    def test_empty_tree(self, tmp_path: Path, monkeypatch):
        output_file = tmp_path / "gha_output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
        monkeypatch.chdir(tmp_path)

        assert build_dag.main() == 0
        content = output_file.read_text()
        assert "has_files=false" in content
        assert "ordered_groups=[]" in content

    def test_cycle_returns_nonzero(self, tmp_path: Path, monkeypatch):
        (tmp_path / "a.in").write_text("-r b.in\n")
        (tmp_path / "b.in").write_text("-r a.in\n")
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
        monkeypatch.chdir(tmp_path)
        # find_in_files matches "requirements*.in" — a.in / b.in won't match.
        # Use realistic names:
        (tmp_path / "a.in").unlink()
        (tmp_path / "b.in").unlink()
        (tmp_path / "requirements-a.in").write_text("-r requirements-b.in\n")
        (tmp_path / "requirements-b.in").write_text("-r requirements-a.in\n")

        assert build_dag.main() == 1
