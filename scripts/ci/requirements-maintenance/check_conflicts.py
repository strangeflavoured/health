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
from pathlib import Path

_UV = shutil.which("uv")
if _UV is None:
    raise FileNotFoundError(
        "uv not found on PATH — ensure the workflow runs astral-sh/setup-uv "
        "before this script."
    )
UV: str = _UV

REPORTS = Path(os.environ.get("REPORTS_DIR", "build/reports"))


def slug(name: str) -> str:
    """Sanitise a label for use as a filename."""
    return name.replace("/", "-").replace(".", "-").replace("+", "_")


def stack_label(stack: list[str]) -> str:
    """Human-readable, stable identifier for a stack."""
    return "+".join(Path(f).stem for f in stack)


def run_capture(cmd: list[str]) -> tuple[int, str]:
    """Run a command and capture stdout, stderr and return a tuple."""
    exe = shutil.which(cmd[0], mode=os.X_OK)
    if exe is None:
        raise FileNotFoundError(f"executable not found: {cmd[0]}")
    result = subprocess.run(  # noqa: S603
        [exe, *cmd[1:]], capture_output=True, text=True, check=False
    )
    return result.returncode, (result.stdout + result.stderr)


def check_stack(stack: list[str], venv_dir: Path) -> dict:
    """Install every .txt in the stack into a fresh venv, then run pip check."""
    code, log = run_capture([UV, "venv", "--quiet", str(venv_dir)])
    if code != 0:
        return {
            "stack": stack,
            "install_ok": False,
            "check_ok": False,
            "install_log": f"uv venv failed: {log}",
            "check_log": "",
        }
    python = venv_dir / "bin" / "python"

    install_logs: list[str] = []
    install_ok = True

    for txt_path in stack:
        if not Path(txt_path).exists():
            install_logs.append(f"--- {txt_path} ---\nMISSING")
            install_ok = False
            break
        code, log = run_capture(
            [
                UV,
                "pip",
                "install",
                "--python",
                str(python),
                "--require-hashes",
                "-r",
                txt_path,
                "--quiet",
            ]
        )
        install_logs.append(f"--- {txt_path} ---\n{log}")

        if code != 0:
            install_ok = False
            break

    check_code, check_log = run_capture([UV, "pip", "check", "--python", str(python)])

    label = stack_label(stack)
    install_log = "\n".join(install_logs)
    (REPORTS / f"install-{slug(label)}.log").write_text(install_log)
    (REPORTS / f"check-{slug(label)}.log").write_text(check_log)

    return {
        "stack": stack,
        "install_ok": install_ok,
        "check_ok": check_code == 0,
        "install_log": install_log,
        "check_log": check_log,
    }


def main() -> int:
    """Install dependency files one by one and check for conflicts."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    stacks = json.loads(os.environ.get("STACKS", "[]"))

    results: dict[str, dict] = {}
    failed = False

    for stack in stacks:
        label = stack_label(stack)
        print(f"=== Checking stack: {label} ===")
        try:
            with tempfile.TemporaryDirectory(prefix=f"venv-{slug(label)}-") as tmp:
                result = check_stack(stack, Path(tmp))
        except Exception as exc:  # noqa: BLE001
            result = {
                "stack": stack,
                "install_ok": False,
                "check_ok": False,
                "install_log": f"exception during check: {exc!r}",
                "check_log": "",
            }
        results[label] = result

        if not result["install_ok"]:
            print(f"::error::Install failed for stack: {label}")
            print(result["install_log"])
            failed = True
        if not result["check_ok"]:
            print(f"::error::pip check found conflicts in stack: {label}")
            print(result["check_log"])
            failed = True
        if result["install_ok"] and result["check_ok"]:
            print("  OK")

    total = len(results)
    install_failed = sum(1 for r in results.values() if not r["install_ok"])
    check_failed = sum(1 for r in results.values() if not r["check_ok"])
    print(
        f"\n=== {total} stacks: {install_failed} install fail, {check_failed} check fail ==="  # noqa: E501
    )

    (REPORTS / "conflicts.json").write_text(json.dumps(results, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
