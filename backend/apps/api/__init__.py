"""REST API app.

Exposes health data stored in Redis via DRF endpoints. Handles Redis
connection management via a module-level singleton and serialises
responses to JSON.
"""
