"""Tests for build_dag.py — DAG construction, topological sort, install stacks.

Security focus: ``get_includes`` must reject every form of escape from the
project root (relative traversal, absolute path, symlink), and
``find_in_files`` must terminate on symlink loops rather than hanging.

Performance focus: ``main()`` and ``topo_groups`` must complete in bounded
time for realistically-sized dependency graphs.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.ci.requirements_maintenance.build_dag as build_dag  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_in(directory: Path, name: str, includes: list[str] | None = None) -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["requests\n"]
    for inc in includes or []:
        lines.append(f"-r {inc}\n")
    path.write_text("".join(lines))
    return path


# ---------------------------------------------------------------------------
# find_in_files
# ---------------------------------------------------------------------------


class TestFindInFiles:
    def test_finds_requirements_in(self, tmp_path):
        write_in(tmp_path, "requirements.in")
        found = build_dag.find_in_files(tmp_path)
        assert any(p.name == "requirements.in" for p in found)

    def test_finds_prefixed_pattern(self, tmp_path):
        write_in(tmp_path, "requirements-dev.in")
        write_in(tmp_path, "base-requirements.in")
        found = {p.name for p in build_dag.find_in_files(tmp_path)}
        assert "requirements-dev.in" in found
        assert "base-requirements.in" in found

    def test_finds_in_subdirectory(self, tmp_path):
        (tmp_path / "backend" / "requirements").mkdir(parents=True)
        write_in(tmp_path / "backend" / "requirements", "base.in")
        found = build_dag.find_in_files(tmp_path)
        names = [p.name for p in found]
        assert "base.in" in names

    def test_ignores_unrelated_in_files(self, tmp_path):
        (tmp_path / "setup.in").write_text("ignored")
        (tmp_path / "something.in").write_text("ignored")
        found = build_dag.find_in_files(tmp_path)
        assert all(
            "requirements" in p.name or p.parent.name == "requirements" for p in found
        )

    def test_deduplicates_results(self, tmp_path):
        write_in(tmp_path, "requirements.in")
        found = build_dag.find_in_files(tmp_path)
        paths = [str(p) for p in found]
        assert len(paths) == len(set(paths))

    def test_returns_sorted(self, tmp_path):
        write_in(tmp_path, "requirements-z.in")
        write_in(tmp_path, "requirements-a.in")
        found = build_dag.find_in_files(tmp_path)
        names = [p.name for p in found]
        assert names == sorted(names)

    def test_empty_directory(self, tmp_path):
        assert build_dag.find_in_files(tmp_path) == []

    def test_does_not_match_bare_dash_in_or_dash_requirements_in(self, tmp_path):
        """Patterns require at least one character before the dash separator."""
        # These should NOT match because the ?* quantifier requires a non-empty
        # prefix/suffix around the dash.
        (tmp_path / "-requirements.in").write_text("x")  # bare dash prefix
        (tmp_path / "requirements-.in").write_text("x")  # bare dash suffix
        found = {p.name for p in build_dag.find_in_files(tmp_path)}
        assert "-requirements.in" not in found
        assert "requirements-.in" not in found

    def test_symlink_loop_terminates(self, tmp_path):
        """A symlink pointing back at an ancestor must not cause infinite recursion.

        ``pathlib.Path.rglob`` follows symlinks by default in older Python
        versions but raises on cycles in 3.13+; older versions can hang.
        We bound this with a generous wall-clock timeout to catch regressions.
        """
        (tmp_path / "real").mkdir()
        write_in(tmp_path / "real", "requirements.in")
        # Symlink loop: tmp_path/loop -> tmp_path
        loop = tmp_path / "loop"
        loop.symlink_to(tmp_path, target_is_directory=True)
        start = time.monotonic()
        try:
            found = build_dag.find_in_files(tmp_path)
        except OSError:
            # Python 3.13+ may raise on detected loop — acceptable
            return
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"find_in_files hung on symlink loop ({elapsed:.1f}s)"
        # At least the legitimate file should be found
        assert any("requirements.in" in str(p) for p in found)


# ---------------------------------------------------------------------------
# get_includes
# ---------------------------------------------------------------------------


class TestGetIncludes:
    def test_parses_relative_include(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        base = write_in(tmp_path, "requirements.in")
        dep = write_in(tmp_path, "requirements-dev.in")
        base.write_text(f"-r {dep.name}\n")
        result = build_dag.get_includes(base)
        assert any("requirements-dev.in" in r for r in result)

    def test_ignores_txt_if_no_in_equivalent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        base = tmp_path / "requirements.in"
        base.write_text("-r some-lockfile.txt\n")
        result = build_dag.get_includes(base)
        assert result == []

    def test_resolves_txt_reference_to_in_if_exists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        base = tmp_path / "requirements.in"
        dep_txt = tmp_path / "requirements-base.txt"
        dep_in = tmp_path / "requirements-base.in"
        dep_txt.write_text("requests\n")
        dep_in.write_text("requests\n")
        base.write_text(f"-r {dep_txt.name}\n")
        result = build_dag.get_includes(base)
        assert any("requirements-base.in" in r for r in result)

    def test_strips_inline_comment(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        dep = write_in(tmp_path, "requirements-base.in")
        main = tmp_path / "requirements.in"
        main.write_text(f"-r {dep.name}  # install base first\n")
        result = build_dag.get_includes(main)
        assert any("requirements-base.in" in r for r in result)

    def test_ignores_non_include_lines(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        main = tmp_path / "requirements.in"
        main.write_text("requests>=2.0\nflask\n--index-url https://pypi.org/simple\n")
        assert build_dag.get_includes(main) == []

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ghost = tmp_path / "nonexistent.in"
        assert build_dag.get_includes(ghost) == []

    def test_multiple_includes(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        a = write_in(tmp_path, "requirements-a.in")
        b = write_in(tmp_path, "requirements-b.in")
        main = tmp_path / "requirements.in"
        main.write_text(f"-r {a.name}\n-r {b.name}\n")
        result = build_dag.get_includes(main)
        assert len(result) == 2

    def test_empty_ref_after_dash_r(self, tmp_path, monkeypatch):
        """`-r ` with nothing after must not crash or escape the root."""
        monkeypatch.chdir(tmp_path)
        main = tmp_path / "requirements.in"
        main.write_text("-r \n-r\t\n")
        result = build_dag.get_includes(main)
        assert result == []

    def test_ref_with_extra_whitespace(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        dep = write_in(tmp_path, "requirements-base.in")
        main = tmp_path / "requirements.in"
        main.write_text(f"-r    {dep.name}   \n")
        result = build_dag.get_includes(main)
        assert any("requirements-base.in" in r for r in result)

    # ---- Security: path traversal rejection ----

    def test_security_path_traversal_in_include(self, tmp_path, monkeypatch):
        """A ``-r ../../etc/passwd`` style reference must be explicitly rejected."""
        monkeypatch.chdir(tmp_path)
        main = tmp_path / "requirements.in"
        main.write_text("-r ../../etc/passwd\n")
        assert build_dag.get_includes(main) == []

    def test_security_absolute_path_in_include(self, tmp_path, monkeypatch):
        """An absolute ``-r /etc/passwd`` reference must be rejected."""
        monkeypatch.chdir(tmp_path)
        evil_in = tmp_path.parent / "evil.in"
        evil_in.write_text("evil\n")
        main = tmp_path / "requirements.in"
        main.write_text(f"-r {evil_in}\n")
        assert build_dag.get_includes(main) == []

    def test_security_sibling_directory_escape(self, tmp_path, monkeypatch):
        """``../sibling/requirements.in`` must be rejected when outside cwd."""
        monkeypatch.chdir(tmp_path)
        sibling = tmp_path.parent / "sibling_project"
        sibling.mkdir(exist_ok=True)
        (sibling / "requirements.in").write_text("flask\n")
        main = tmp_path / "requirements.in"
        main.write_text("-r ../sibling_project/requirements.in\n")
        assert build_dag.get_includes(main) == []

    def test_security_symlink_target_outside_root(self, tmp_path, monkeypatch):
        """A symlink whose target is outside cwd must be rejected after resolve()."""
        outside = tmp_path.parent / "outside_root"
        outside.mkdir(exist_ok=True)
        (outside / "evil.in").write_text("evil\n")

        monkeypatch.chdir(tmp_path)
        link = tmp_path / "evil.in"
        link.symlink_to(outside / "evil.in")
        main = tmp_path / "requirements.in"
        main.write_text(f"-r {link.name}\n")
        assert build_dag.get_includes(main) == []


# ---------------------------------------------------------------------------
# topo_groups
# ---------------------------------------------------------------------------


class TestTopoGroups:
    def test_single_node_no_deps(self):
        assert build_dag.topo_groups(["a.in"], {"a.in": []}) == [["a.in"]]

    def test_linear_chain(self):
        keys = ["a.in", "b.in", "c.in"]
        deps = {"a.in": [], "b.in": ["a.in"], "c.in": ["b.in"]}
        groups = build_dag.topo_groups(keys, deps)
        flat = [item for g in groups for item in g]
        assert flat.index("a.in") < flat.index("b.in") < flat.index("c.in")

    def test_parallel_independent_nodes(self):
        keys = ["a.in", "b.in", "c.in"]
        deps = {"a.in": [], "b.in": [], "c.in": []}
        groups = build_dag.topo_groups(keys, deps)
        assert len(groups) == 1
        assert sorted(groups[0]) == keys

    def test_diamond_dependency(self):
        """A->B, A->C, B->D, C->D: D first, B/C middle, A last."""
        keys = ["d.in", "b.in", "c.in", "a.in"]
        deps = {
            "d.in": [],
            "b.in": ["d.in"],
            "c.in": ["d.in"],
            "a.in": ["b.in", "c.in"],
        }
        groups = build_dag.topo_groups(keys, deps)
        flat = [item for g in groups for item in g]
        assert flat.index("d.in") < flat.index("b.in")
        assert flat.index("d.in") < flat.index("c.in")
        assert flat.index("b.in") < flat.index("a.in")
        assert flat.index("c.in") < flat.index("a.in")

    def test_cycle_raises_runtime_error(self):
        keys = ["a.in", "b.in"]
        deps = {"a.in": ["b.in"], "b.in": ["a.in"]}
        with pytest.raises(RuntimeError, match="[Cc]ircular"):
            build_dag.topo_groups(keys, deps)

    def test_self_loop_raises(self):
        keys = ["a.in"]
        deps = {"a.in": ["a.in"]}
        with pytest.raises(RuntimeError):
            build_dag.topo_groups(keys, deps)

    def test_three_node_cycle_raises(self):
        keys = ["a.in", "b.in", "c.in"]
        deps = {"a.in": ["c.in"], "b.in": ["a.in"], "c.in": ["b.in"]}
        with pytest.raises(RuntimeError):
            build_dag.topo_groups(keys, deps)

    def test_output_contains_all_keys(self):
        keys = ["a.in", "b.in", "c.in", "d.in"]
        deps = {"a.in": [], "b.in": ["a.in"], "c.in": [], "d.in": ["c.in"]}
        groups = build_dag.topo_groups(keys, deps)
        flat = [item for g in groups for item in g]
        assert sorted(flat) == sorted(keys)

    def test_groups_are_internally_sorted(self):
        keys = ["z.in", "a.in", "m.in"]
        deps = {"z.in": [], "a.in": [], "m.in": []}
        groups = build_dag.topo_groups(keys, deps)
        assert groups[0] == sorted(groups[0])

    def test_dep_referencing_unknown_key_is_ignored(self):
        """A dep pointing at a key not in ``all_keys`` must be silently ignored."""
        keys = ["a.in"]
        deps = {"a.in": ["unknown.in"]}
        groups = build_dag.topo_groups(keys, deps)
        # The unknown dep is dropped via ``if dep in in_degree``; ``a.in`` is
        # the only node and has no satisfied prerequisite, so it ships first.
        assert groups == [["a.in"]]

    def test_performance_thousand_nodes(self):
        """A 1000-node parallel graph must process well under one second."""
        keys = [f"n{i:04d}.in" for i in range(1000)]
        deps = {k: [] for k in keys}
        start = time.monotonic()
        groups = build_dag.topo_groups(keys, deps)
        elapsed = time.monotonic() - start
        assert sum(len(g) for g in groups) == 1000
        assert elapsed < 1.0, f"topo_groups took {elapsed:.2f}s for 1000 nodes"


# ---------------------------------------------------------------------------
# build_stacks
# ---------------------------------------------------------------------------


class TestBuildStacks:
    def test_single_terminal(self):
        keys = ["base.in", "api.in"]
        deps = {"base.in": [], "api.in": ["base.in"]}
        stacks = build_dag.build_stacks(keys, deps)
        assert len(stacks) == 1
        assert stacks[0].index("base.txt") < stacks[0].index("api.txt")

    def test_two_independent_terminals(self):
        keys = ["a.in", "b.in"]
        deps = {"a.in": [], "b.in": []}
        assert len(build_dag.build_stacks(keys, deps)) == 2

    def test_paths_converted_to_txt(self):
        keys = ["reqs/base.in", "reqs/api.in"]
        deps = {"reqs/base.in": [], "reqs/api.in": ["reqs/base.in"]}
        stacks = build_dag.build_stacks(keys, deps)
        all_paths = [p for s in stacks for p in s]
        assert all(p.endswith(".txt") for p in all_paths)

    def test_diamond_produces_single_stack(self):
        keys = ["d.in", "b.in", "c.in", "a.in"]
        deps = {
            "d.in": [],
            "b.in": ["d.in"],
            "c.in": ["d.in"],
            "a.in": ["b.in", "c.in"],
        }
        stacks = build_dag.build_stacks(keys, deps)
        assert len(stacks) == 1
        assert "a.txt" in stacks[0]
        assert "d.txt" in stacks[0]


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------


class TestMain:
    def test_no_in_files_writes_false(self, tmp_cwd, github_output):  # noqa: ARG002
        rc = build_dag.main()
        assert rc == 0
        outputs = github_output()
        assert outputs["has_files"] == "false"

    def test_single_in_file(self, tmp_cwd, github_output):
        write_in(tmp_cwd, "requirements.in")
        rc = build_dag.main()
        assert rc == 0
        outputs = github_output()
        assert outputs["has_files"] == "true"
        groups = json.loads(outputs["ordered_groups"])
        assert any("requirements.in" in f for g in groups for f in g)

    def test_cycle_returns_nonzero(self, tmp_cwd, github_output):  # noqa: ARG002
        a = write_in(tmp_cwd, "requirements-a.in")
        b = write_in(tmp_cwd, "requirements-b.in")
        a.write_text(f"-r {b.name}\n")
        b.write_text(f"-r {a.name}\n")
        rc = build_dag.main()
        assert rc == 1

    def test_all_files_in_output(self, tmp_cwd, github_output):
        write_in(tmp_cwd, "requirements.in")
        write_in(tmp_cwd, "requirements-dev.in")
        build_dag.main()
        outputs = github_output()
        all_files = json.loads(outputs["all_files"])
        names = [Path(f).name for f in all_files]
        assert "requirements.in" in names
        assert "requirements-dev.in" in names

    def test_performance_wide_graph(self, tmp_cwd, github_output):  # noqa: ARG002
        """100 independent .in files should complete in under 2 seconds."""
        for i in range(100):
            write_in(tmp_cwd, f"requirements-svc{i:03d}.in")
        start = time.monotonic()
        rc = build_dag.main()
        elapsed = time.monotonic() - start
        assert rc == 0
        assert elapsed < 2.0, f"main() took {elapsed:.2f}s for 100 files"

    def test_performance_deep_chain(self, tmp_cwd, github_output):  # noqa: ARG002
        """50-level deep chain should complete quickly."""
        prev = write_in(tmp_cwd, "requirements-00.in")
        for i in range(1, 50):
            name = f"requirements-{i:02d}.in"
            cur = tmp_cwd / name
            cur.write_text(f"-r {prev.name}\n")
            prev = cur
        start = time.monotonic()
        rc = build_dag.main()
        elapsed = time.monotonic() - start
        assert rc == 0
        assert elapsed < 2.0


# ---------------------------------------------------------------------------
# write_output
# ---------------------------------------------------------------------------


class TestWriteOutput:
    def test_writes_to_github_output_file(self, tmp_path, monkeypatch):
        out_file = tmp_path / "out.txt"
        out_file.touch()
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))
        build_dag.write_output("my_key", "my_value")
        assert "my_key=my_value" in out_file.read_text()

    def test_writes_to_stdout_when_no_env(self, monkeypatch, capsys):
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
        build_dag.write_output("k", "v")
        assert "k=v" in capsys.readouterr().out

    def test_appends_rather_than_overwrites(self, tmp_path, monkeypatch):
        out_file = tmp_path / "out.txt"
        out_file.write_text("existing=value\n")
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))
        build_dag.write_output("new", "thing")
        content = out_file.read_text()
        assert "existing=value" in content
        assert "new=thing" in content

    def test_value_with_newline_written_verbatim(self, tmp_path, monkeypatch):
        """``write_output`` does not escape newlines; documents current behaviour.

        GitHub's workflow runner treats a literal newline in a value as the end
        of the key=value pair, so callers must ensure values never contain
        newlines or use the multi-line ``<<DELIMITER`` form.  This test pins
        the current naive write so any future change has to be deliberate.
        """
        out_file = tmp_path / "out.txt"
        out_file.touch()
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))
        build_dag.write_output("multi", "line1\nline2")
        content = out_file.read_text()
        assert "multi=line1\nline2" in content
