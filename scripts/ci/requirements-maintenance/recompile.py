"""Recompile requirements files in DAG order, resolving updates and conflicts.

Reads ORDERED_GROUPS (JSON list-of-lists of .in file paths) from the environment,
runs pip-compile --upgrade on each file in topological order, and writes the
results back to the corresponding .txt files in-place.

Environment variables
---------------------
ORDERED_GROUPS
    JSON-encoded list of groups, each group a list of .in file paths.
    Groups are processed sequentially; files within a group are independent
    and could be parallelised, but are run sequentially here for simplicity.
    Example: '[["base.in"], ["api/requirements.in", "worker/requirements.in"]]'
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _resolve_pip_compile() -> Path:
    """Return the pip-compile binary co-located with the current interpreter."""
    candidate = Path(sys.executable).parent / "pip-compile"
    if candidate.is_file():
        return candidate
    # Fall back to PATH resolution for editable / non-standard installs
    found = shutil.which("pip-compile")
    if found:
        return Path(found)
    raise FileNotFoundError(
        "pip-compile not found — is pip-tools installed in this environment?"
    )


PIP_COMPILE = _resolve_pip_compile()


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def pip_check() -> tuple[bool, str]:
    """Run pip check against the current environment.

    Returns a (success, log) tuple. A non-zero exit code means pip found
    dependency conflicts in the installed packages — this indicates the
    recompiled .txt files would produce a broken environment.
    """
    result = subprocess.run(  # noqa: S603
        [str(Path(sys.executable).parent / "pip"), "check"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stdout + result.stderr


def output_file(in_path: Path) -> Path:
    """Derive the .txt output path from a .in input path."""
    return in_path.with_suffix(".txt")


def recompile_one(in_path: Path) -> tuple[bool, str]:
    """Run pip-compile --upgrade on *in_path*, writing result to the .txt file.

    Returns a (success, log) tuple where *log* is combined stdout+stderr.
    """
    out_path = output_file(in_path)
    result = subprocess.run(  # noqa: S603
        [
            str(PIP_COMPILE),
            "--upgrade",
            "--quiet",
            "--no-header",
            "--no-annotations",
            "--output-file",
            str(out_path),
            str(in_path),
        ],
        capture_output=True,
        text=True,
    )
    log = result.stdout + result.stderr
    return result.returncode == 0, log


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Recompile updated dependencies in DAG order and run pip check."""
    raw = os.environ.get("ORDERED_GROUPS")
    if not raw:
        print("::error::ORDERED_GROUPS is not set", flush=True)
        return 1

    try:
        ordered_groups: list[list[str]] = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"::error::ORDERED_GROUPS is not valid JSON: {exc}", flush=True)
        return 1

    failures: list[Path] = []

    for group_index, group in enumerate(ordered_groups):
        print(f"\n── Group {group_index + 1}/{len(ordered_groups)} ──", flush=True)

        for raw_path in group:
            in_path = Path(raw_path)

            if not in_path.exists():
                print(f"  [SKIP] {in_path} — file not found", flush=True)
                continue

            print(f"  [COMPILE] {in_path} → {output_file(in_path)}", flush=True)
            success, log = recompile_one(in_path)

            if log.strip():
                # Indent pip-compile output so it's visually nested in CI logs
                for line in log.splitlines():
                    print(f"    {line}", flush=True)

            if success:
                print(f"  [OK] {in_path}", flush=True)
            else:
                print(f"  [FAIL] {in_path}", flush=True)
                failures.append(in_path)

    if failures:
        print("\n::error::The following files failed to recompile:", flush=True)
        for path in failures:
            print(f"  - {path}", flush=True)
        return 1

    print(f"\nRecompiled {sum(len(g) for g in ordered_groups)} file(s) successfully.")

    print("\n── pip check ──", flush=True)
    ok, log = pip_check()
    if log.strip():
        for line in log.splitlines():
            print(f"  {line}", flush=True)
    if ok:
        print("  [OK] No dependency conflicts detected.", flush=True)
    else:
        print(
            "::error::pip check reported conflicts after recompile — "
            "the generated .txt files may be inconsistent.",
            flush=True,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
