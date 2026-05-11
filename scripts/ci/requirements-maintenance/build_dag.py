"""Build a topological compile order for pip-tools .in files.

Discovers requirements*.in files, reads `-r ...` includes, and emits
groups of files that can be compiled in parallel (each group depends
only on earlier groups).

Outputs (to $GITHUB_OUTPUT if set, else stdout):
  ordered_groups : JSON list of lists of file paths
  all_files      : JSON list of all file paths
  has_files      : "true" / "false"
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def find_in_files(root: Path) -> list[Path]:
    """Find all requirements .in files under root, deduplicated and sorted.

    Matches the dorny filter:
      - '**/{requirements,*-requirements,requirements-*}.in'
      - '**/requirements/*.in'
    """
    matches = set(root.rglob("{requirements,*-requirements,requirements-*}.in")) | set(
        root.rglob("requirements/*.in")
    )
    return sorted(matches)


def get_includes(in_file: Path) -> list[str]:
    """Return the .in files referenced via `-r` from this file."""
    deps: list[str] = []
    try:
        lines = in_file.read_text().splitlines()
    except OSError:
        return deps

    for raw in lines:
        line = raw.strip()
        if not line.startswith("-r "):
            continue
        ref = line[3:].strip()
        resolved = (in_file.parent / ref).resolve()
        # We only track .in -> .in includes; if the referenced file
        # is a .txt (a compiled lockfile), we look at its .in equivalent.
        in_equiv = resolved.with_suffix(".in")
        if in_equiv.exists():
            deps.append(str(in_equiv.relative_to(Path.cwd())))
    return deps


def topo_groups(all_keys: list[str], deps_map: dict[str, list[str]]) -> list[list[str]]:
    """Kahn's algorithm, grouped by level. Raises on cycles."""
    in_degree = {k: 0 for k in all_keys}
    dependents: dict[str, list[str]] = {k: [] for k in all_keys}

    for key, deps in deps_map.items():
        for dep in deps:
            if dep in in_degree:
                in_degree[key] += 1
                dependents[dep].append(key)

    groups: list[list[str]] = []
    remaining = set(all_keys)
    while remaining:
        group = sorted(k for k in remaining if in_degree[k] == 0)
        if not group:
            raise RuntimeError(f"Circular dependency detected in: {sorted(remaining)}")
        groups.append(group)
        for key in group:
            remaining.remove(key)
            for dep in dependents[key]:
                in_degree[dep] -= 1
    return groups


def write_output(key: str, value: str) -> None:
    """Write to $GITHUB_OUTPUT or fall back to stdout for local runs."""
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as fh:
            fh.write(f"{key}={value}\n")
    else:
        print(f"{key}={value}")


def main() -> int:
    """Build a topological compile order for pip-tools .in files.

    Returns 0 on success, 1 on failure.
    """
    failed = False
    root = Path.cwd()
    in_files = find_in_files(root)

    if not in_files:
        print("No .in files found")
        write_output("has_files", "false")
        write_output("ordered_groups", "[]")
        write_output("all_files", "[]")
        return 0

    # Check that
    needs_compile = []
    for in_path in in_files:
        in_file = Path(in_path)
        txt_file = in_file.with_suffix(".txt")
        if not txt_file.exists():
            needs_compile.append(in_file)

    if needs_compile:
        for f in needs_compile:
            print(f"::error file={f}::Please compile first.")
        failed = True

    all_keys = [str(f.relative_to(root)) for f in in_files]
    deps_map = {k: get_includes(Path(k)) for k in all_keys}

    groups: list[list[str]] = []
    try:
        groups = topo_groups(all_keys, deps_map)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        failed = True

    print(f"Compile order ({len(groups)} groups):")
    for i, group in enumerate(groups):
        print(f"  Group {i}: {group}")

    write_output("ordered_groups", json.dumps(groups))
    write_output("all_files", json.dumps(all_keys))
    write_output("has_files", "true")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
