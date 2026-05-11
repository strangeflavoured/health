"""Combine analysis reports into summary.json and emit GHA outputs.

Inputs (files in REPORTS):
  updates.json    : from check_updates.py
  conflicts.json  : from check_conflicts.py
  deptry.json     : from deptry

Outputs (to $GITHUB_OUTPUT):
  has_updates    : "true" if any package has a newer version available
  has_conflicts  : "true" if any environment had install or pip-check failures
  has_unused     : "true" if deptry found any issues
  has_changes    : "true" if has_updates is true (kept for backward compat)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")

REPORTS = Path(os.environ.get("REPORTS_DIR", "build/reports"))


def load_json[T](path: Path, default: T) -> Any | T:  # noqa: ANN401
    """Load and parse JSON from *path*.

    Returns *default* if the file is missing or unreadable.
    """
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def write_output(key: str, value: str) -> None:
    """Write key/value to output.

    If `GITHUB_OUTPUT` is set it is written to that file, otherwise it
    is printed to stdout.
    """
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as fh:
            fh.write(f"{key}={value}\n")
    else:
        print(f"{key}={value}")


def main() -> int:
    """Summarise dependency analysis."""
    updates = load_json(REPORTS / "updates.json", {})
    conflicts = load_json(REPORTS / "conflicts.json", {})
    deptry = load_json(REPORTS / "deptry.json", {})

    has_updates = bool(updates)
    has_conflicts = any(
        not r.get("install_ok", True) or not r.get("check_ok", True)
        for r in conflicts.values()
    )
    has_unused = bool(deptry) if isinstance(deptry, dict) else bool(deptry)

    summary = {
        "updates": updates,
        "conflicts": conflicts,
        "unused": deptry,
        "has_updates": has_updates,
        "has_conflicts": has_conflicts,
        "has_unused": has_unused,
    }
    (REPORTS / "summary.json").write_text(json.dumps(summary, indent=2))

    print("Analysis summary:")
    print(f"  Updates available: {has_updates}")
    print(f"  Conflicts found:   {has_conflicts}")
    print(f"  Unused detected:   {has_unused}")

    write_output("has_updates", "true" if has_updates else "false")
    write_output("has_conflicts", "true" if has_conflicts else "false")
    write_output("has_unused", "true" if has_unused else "false")
    write_output("has_changes", "true" if has_updates else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
