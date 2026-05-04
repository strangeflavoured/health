"""Development settings.

Extends base.py with DEBUG=True, permissive ALLOWED_HOSTS, and open
CORS. Not safe for production use.
"""

from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True
