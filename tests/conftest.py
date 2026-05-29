"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import sys
import types

import pytest

from src.model.base import MissingUnit

# ---------------------------------------------------------------------------
# Stub src.model before any test module imports src.redis_setup.
# Module-level code here runs before pytest collection, so the
# `from .model import HKTypeIdentifierRegistry` inside redis_setup.py
# resolves to the fake registry at import time.
# ---------------------------------------------------------------------------

_FakeQuantityType = types.SimpleNamespace(unit="count/min", group="vitals")
_FakeCategoryType = types.SimpleNamespace(
    unit=MissingUnit.CATEGORICAL.value, group="sleep"
)

FAKE_REGISTRY = {
    "HKQuantityTypeIdentifierHeartRate": _FakeQuantityType,
    "HKCategoryTypeIdentifierSleepAnalysis": _FakeCategoryType,
}

stub = types.ModuleType("src.model")
stub.HKTypeIdentifierRegistry = FAKE_REGISTRY
stub.HKQuantityTypeIdentifierRegistry = FAKE_REGISTRY
sys.modules["src.model"] = stub


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_redis_env(monkeypatch):
    """Remove any stray REDIS_* variables from the environment for each test."""
    for var in (
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_DB",
        "APP_PASSWORD",
        "REDIS_APP_CERT",
        "REDIS_APP_KEY",
        "REDIS_CA_CERT",
        "REDIS_CERTS_DIR",
    ):
        monkeypatch.delenv(var, raising=False)
