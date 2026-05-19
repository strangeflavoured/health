"""Shared utils for requirements-maintenance scripts."""

import shutil


def get_uv() -> str:
    """Return the path to uv, raising only when first called at runtime."""
    uv = shutil.which("uv")
    if uv is None:
        raise FileNotFoundError(
            "uv not found on PATH — ensure the workflow runs astral-sh/setup-uv "
            "before this script."
        )
    return uv
