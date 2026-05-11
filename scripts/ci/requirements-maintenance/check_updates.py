"""Detect available dependency updates using pip-compile --upgrade --dry-run.

For each .in file, compare the existing .txt lockfile against what
pip-compile would produce with --upgrade. Differences are recorded
as available updates. This respects constraints declared in the .in
files (unlike `pip list --outdated`, which ignores them).

Writes REPORTS/updates.json:
  { "path/to/requirements.in": [
      {"package": "...", "current": "...", "latest": "..."}, ...
    ], ... }
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPORTS = Path(os.environ.get("REPORTS_DIR", "build/reports"))
PIN_RE = re.compile(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)")


def parse_pins(text: str) -> dict[str, str]:
    """Extract package==version pins from a compiled requirements file."""
    pins: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Strip inline comments and environment markers
        line = line.split("#", 1)[0].strip()
        line = line.split(";", 1)[0].strip()
        match = PIN_RE.match(line)
        if match:
            pins[match.group(1).lower()] = match.group(2)
    return pins


def compile_upgraded(in_file: Path, out_file: Path) -> bool:
    """Run pip-compile --upgrade --dry-run; write result to out_file."""
    exe = Path(sys.executable).parent / "pip-compile"
    if not exe.is_file():
        raise FileNotFoundError(f"pip-compile not found at {exe}")
    result = subprocess.run(  # noqa: S603
        [
            exe,
            "--upgrade",
            "--quiet",
            "--no-header",
            "--no-annotations",
            "--output-file",
            str(out_file),
            str(in_file),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  pip-compile failed for {in_file}:")
        print(result.stderr)
        return False
    return True


def diff_pins(
    current: dict[str, str], upgraded: dict[str, str]
) -> list[dict[str, str]]:
    """Return list of changes between two pin sets (added, removed, changed)."""
    changes: list[dict[str, str]] = []
    all_names = set(current) | set(upgraded)
    for name in sorted(all_names):
        cur = current.get(name)
        new = upgraded.get(name)
        if cur == new:
            continue
        changes.append(
            {
                "package": name,
                "current": cur or "(absent)",
                "latest": new or "(removed)",
            }
        )
    return changes


def main() -> int:
    """Check dependency files one by one for available updates."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    all_files = json.loads(os.environ.get("ALL_FILES", "[]"))

    updates: dict[str, list[dict[str, str]]] = {}
    total = 0

    for in_path in all_files:
        in_file = Path(in_path)
        txt_file = in_file.with_suffix(".txt")
        if not txt_file.exists():
            continue

        current_pins = parse_pins(txt_file.read_text())

        with tempfile.TemporaryDirectory(prefix="upgraded-") as dir_str:
            upgraded_path = Path(f"{dir_str}/{in_file.name}.txt")
            if not compile_upgraded(in_file, upgraded_path):
                continue
            upgraded_pins = parse_pins(upgraded_path.read_text())

        changes = diff_pins(current_pins, upgraded_pins)

        if changes:
            updates[in_path] = changes
            total += len(changes)
            for change in changes:
                print(
                    f"  {change['package']}: {change['current']} "
                    f"-> {change['latest']}  [{in_path}]"
                )

    (REPORTS / "updates.json").write_text(json.dumps(updates, indent=2))
    print(f"\nTotal: {total} updates across {len(updates)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
