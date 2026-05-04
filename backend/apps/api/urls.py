"""URL configuration for the API app.

All patterns are mounted under /api/ by the root config/urls.py.
Add a new path() entry here when introducing a new view.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
]
