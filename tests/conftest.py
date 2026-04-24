"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import os
import pytest


@pytest.fixture(autouse=True)
def _clean_redis_env(monkeypatch):
    """Remove any stray REDIS_* variables from the environment for each test."""
    for var in (
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_DB",
        "REDIS_PASSWORD",
        "REDIS_CLIENT_CERT",
        "REDIS_CLIENT_KEY",
        "REDIS_CA_CERT",
        "REDIS_CERTS_DIR",
    ):
        monkeypatch.delenv(var, raising=False)
