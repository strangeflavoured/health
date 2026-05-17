"""Module for data import."""

from .importer import HealthDataImporter

# claim ownership for sphinx apidoc
HealthDataImporter.__module__ = __name__

__all__ = ["HealthDataImporter"]
