"""Tests for the API app.

Covers views, URL routing, and Redis interaction. Redis calls should be
mocked to keep tests hermetic and fast. Use DRF's APIClient for
endpoint tests.
"""

import pytest
import redis
from fakeredis import FakeRedis
from rest_framework.test import APIClient


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr("apps.api.connection.docker_redis_connect", lambda: fake)
    monkeypatch.setattr("apps.api.connection._client", None)  # reset singleton
    return fake


def test_health_endpoint_ok(fake_redis):  # noqa: ARG001
    client = APIClient()
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_redis_down(monkeypatch):
    def broken():
        raise redis.ConnectionError()

    monkeypatch.setattr("apps.api.connection.docker_redis_connect", broken)
    monkeypatch.setattr("apps.api.connection._client", None)

    client = APIClient()
    response = client.get("/api/health/")
    assert response.status_code == 503
