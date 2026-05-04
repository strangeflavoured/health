"""API views for health data endpoints.

Each view reads from Redis via get_redis_client() and returns JSON
responses. Computation-heavy operations should be dispatched to
apps/workers/tasks.py rather than run inline.
"""

import logging

import redis
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .connection import get_redis_client

logger = logging.getLogger(__name__)


@api_view(["GET"])
def health(_request: Request) -> Response:
    """Check API and Redis connectivity.

    Args:
        _request: The incoming HTTP request.

    Returns:
        Response: JSON with status 'ok' if Redis responds to PING,
            or status 503 with error detail if not.

    """
    try:
        get_redis_client().ping()
    except redis.exceptions.RedisError as exc:
        logger.error("Redis health check failed: %s", exc)
        return Response(
            {"status": "error", "detail": "Redis unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({"status": "ok"})
