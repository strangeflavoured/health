"""Check each .in/.txt pair for install errors and pip conflicts.

Each environment is installed into its own fresh venv to avoid
flagging conflicts that are artifacts of installing unrelated
environments together.

Writes per-file logs to REPORTS and a combined conflicts.json:
  { "path/to/requirements.in": {
      "install_ok": bool,
      "check_ok": bool,
      "install_log": "...",
      "check_log": "..."
    }, ... }

Exits non-zero if any environment failed install or pip check.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

REPORTS = Path(os.environ.get("REPORTS_DIR", "build/reports"))


def slug(path: str) -> str:
    """Convert path to filename."""
    return path.replace("/", "-").replace(".", "-")


def run_capture(cmd: list[str]) -> tuple[int, str]:
    """Run a command and capture stdout, stderr and return a tuple."""
    exe = shutil.which(cmd[0], mode=os.X_OK)
    if exe is None:
        raise FileNotFoundError(f"executable not found: {cmd[0]}")
    result = subprocess.run(  # noqa: S603
        [exe, *cmd[1:]], capture_output=True, text=True, check=True
    )
    return result.returncode, (result.stdout + result.stderr)


def check_one(in_path: str, txt_path: Path, venv_dir: Path) -> dict:
    """Install one dependency and run `pip check`."""
    venv.create(venv_dir, with_pip=True, clear=True)
    pip = venv_dir / "bin" / "pip"

    install_code, install_log = run_capture(
        [str(pip), "install", "--require-hashes", "-r", str(txt_path), "--quiet"]
    )

    check_code, check_log = run_capture([str(pip), "check"])

    (REPORTS / f"install-{slug(in_path)}.log").write_text(install_log)
    (REPORTS / f"check-{slug(in_path)}.log").write_text(check_log)

    return {
        "install_ok": install_code == 0,
        "check_ok": check_code == 0,
        "install_log": install_log,
        "check_log": check_log,
    }


def main() -> int:
    """Install dependency files one by one and check for conflicts."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    all_files = json.loads(os.environ.get("ALL_FILES", "[]"))

    results: dict[str, dict] = {}
    failed = False

    for in_path in all_files:
        in_file = Path(in_path)
        txt_file = in_file.with_suffix(".txt")
        if not txt_file.exists():
            continue

        print(f"=== Checking {txt_file} ===")
        with tempfile.TemporaryDirectory(
            prefix=f"venv-{slug(in_path)}-"
        ) as venv_dir_str:
            venv_dir = Path(venv_dir_str)
            try:
                result = check_one(in_path, txt_file, venv_dir)
            finally:
                shutil.rmtree(venv_dir, ignore_errors=True)

        results[in_path] = result

        if not result["install_ok"]:
            print(f"::error file={txt_file}::Install failed")
            print(result["install_log"])
            failed = True
        if not result["check_ok"]:
            print(f"::error file={txt_file}::pip check found conflicts")
            print(result["check_log"])
            failed = True
        if result["install_ok"] and result["check_ok"]:
            print("  OK")

    (REPORTS / "conflicts.json").write_text(json.dumps(results, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
