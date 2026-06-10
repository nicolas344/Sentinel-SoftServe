"""
Tests de autenticación del webhook /api/alerts (ALERT_WEBHOOK_SECRET).
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-min-32-characters-long")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

from main import app  # noqa: E402

_EMPTY_WEBHOOK = {"status": "firing", "alerts": []}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def with_secret(monkeypatch):
    monkeypatch.setenv("ALERT_WEBHOOK_SECRET", "super-secreto")


def test_rejects_without_header(client, with_secret):
    response = client.post("/api/alerts", json=_EMPTY_WEBHOOK)
    assert response.status_code == 401


def test_rejects_wrong_secret(client, with_secret):
    response = client.post(
        "/api/alerts",
        json=_EMPTY_WEBHOOK,
        headers={"Authorization": "Bearer incorrecto"},
    )
    assert response.status_code == 401


def test_accepts_correct_secret(client, with_secret):
    response = client.post(
        "/api/alerts",
        json=_EMPTY_WEBHOOK,
        headers={"Authorization": "Bearer super-secreto"},
    )
    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_open_when_secret_not_configured(client, monkeypatch):
    monkeypatch.delenv("ALERT_WEBHOOK_SECRET", raising=False)
    response = client.post("/api/alerts", json=_EMPTY_WEBHOOK)
    assert response.status_code == 200
