"""Tests for the workers app.

Covers Celery task logic. Tasks should be tested with
CELERY_TASK_ALWAYS_EAGER=True in the test settings so they run
synchronously without a broker.
"""
