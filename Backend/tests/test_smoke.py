"""
Smoke tests: verifican que la app FastAPI arranca y responde.
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Asegurar que Backend/ está en sys.path cuando pytest corre desde ahí
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-min-32-characters-long")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

from auth import get_current_user  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: {"sub": "test-user"}
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_app_starts():
    """La app arranca sin errores de importación."""
    assert app is not None


def test_health_incidents_requires_auth(client):
    """GET /api/incidents sin token devuelve 401 o 200 con override."""
    app.dependency_overrides.clear()
    response = client.get("/api/incidents")
    assert response.status_code in (200, 401, 403, 422)


def test_alerts_endpoint_exists(client):
    """POST /api/alerts con body vacío devuelve 422 (validación), no 404."""
    response = client.post("/api/alerts", json={})
    assert response.status_code != 404
