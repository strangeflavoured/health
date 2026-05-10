"""Test settings.

Extends base.py with DEBUG=True, permissive ALLOWED_HOSTS, and open
CORS. Not safe for production use.
"""

from .base import *

DEBUG = True

ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Faster password hashing in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]


class DisableMigrations:
    """Disable migrations for speed (uses syncdb instead)."""

    def __contains__(self, _item: object) -> bool:
        """Return True for all items to disable all migrations."""
        return True

    def __getitem__(self, _item: object) -> None:
        """Return None for all items to disable all migrations."""
        return None


MIGRATION_MODULES = DisableMigrations()

# silence logging noise during tests
LOGGING = {}

# avoid needing a real email backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
