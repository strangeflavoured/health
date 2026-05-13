"""Main module."""

import json
from pathlib import Path

from .importer import HealthDataImporter

with open(Path(__file__).parents[1] / "versions.json") as f:
    __version__ = json.load(f)["latest"]

__all__ = ["HealthDataImporter", "__version__"]
