# vulture_allowlist.py
#
# Purpose: suppress Vulture false positives for code that IS used, but not
# in a way Vulture can trace statically (dynamic dispatch, DI frameworks,
# Docker entrypoints, Redis-OM field descriptors, etc.).
#
# How to use:
#   - Run `vulture src/ --make-whitelist` to generate an initial list.
#   - Move only INTENTIONAL suppressions here; fix genuine dead code.
#   - Keep entries grouped by reason so reviewers understand each decision.
#
# Vulture reads this file as valid Python, so syntax must be correct.
# Each entry is a reference that makes Vulture believe the symbol is used.

# ── Docker entrypoints ────────────────────────────────────────────────────────
# These functions are invoked by the container runtime (CMD / ENTRYPOINT in
# Dockerfile or the `command:` key in docker-compose.yml), not by Python
# imports. Vulture cannot see across the Docker boundary.
from src.entrypoints import main  # noqa: F401 – called by Docker CMD

# ── Redis-Stack / redis-om field descriptors ──────────────────────────────────
# redis-om accesses model fields via class-level descriptors (__get__/__set__).
# The fields are never called directly in application code, so Vulture flags
# them as unused. The `_` assignment is the conventional Vulture suppression.
from src.models.session import SessionModel
from src.worker import run_worker  # noqa: F401 – called by docker-compose command

_ = SessionModel.user_id
_ = SessionModel.created_at
_ = SessionModel.ttl
_ = SessionModel.payload

# ── Redis-Stack index definitions ─────────────────────────────────────────────
# Migrator().run() and Migrator.run_migrations() scan for classes decorated
# with @JsonModel / @HashModel and build the index automatically at startup.
# These class bodies are never explicitly instantiated in tests or app code.
from src.models.session import SessionModel as _SessionModel  # noqa: F811

_SessionModel.__init__

# ── API entry points registered via decorator (FastAPI / Flask) ───────────────
# Decorated route handlers are registered into the router registry at import
# time; they are never called by name in application code.
from src.api.health import health_check  # noqa: F401 – @router.get("/health")
from src.api.session import create_session, delete_session, get_session  # noqa: F401

# ── Pydantic response/request schemas ─────────────────────────────────────────
# Fields on Pydantic models are accessed via model_fields / __annotations__
# at runtime, not as direct attribute references in source code.
from src.schemas.session import SessionCreateRequest

_ = SessionCreateRequest.ttl_seconds
_ = SessionCreateRequest.metadata

# ── pytest fixtures (if src/ accidentally includes conftest.py) ───────────────
# Fixtures are injected by pytest via name matching, never called explicitly.
# Prefer keeping conftest.py outside src/; list here only if unavoidable.
# from src.conftest import redis_client    # uncomment if needed
