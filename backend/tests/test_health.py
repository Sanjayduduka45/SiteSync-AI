"""
Phase 1 backend tests — health endpoint.
Uses httpx TestClient (synchronous) so no pytest-asyncio configuration is needed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_response_schema() -> None:
    response = client.get("/api/v1/health")
    body = response.json()
    assert "status" in body
    assert "version" in body
    assert "environment" in body


def test_health_status_is_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.json()["status"] == "ok"


def test_health_environment_defaults_to_development() -> None:
    response = client.get("/api/v1/health")
    # In test, APP_ENV is not set so it falls back to the default "development"
    assert response.json()["environment"] == "development"


def test_unknown_route_returns_404() -> None:
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
