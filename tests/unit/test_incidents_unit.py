import asyncio

import pytest
from fastapi import HTTPException

from routers import incidents
from tests.conftest import FakeSupabaseClient


def test_get_incident_logic_returns_expected_fields(monkeypatch):
    incident_row = {
        "id": "inc-001",
        "container_name": "api-container",
        "severity": "critical",
        "status": "detected",
        "server_name": "node-a",
        "created_at": "2026-03-24T12:00:00Z",
        "logs": "panic: out of memory",
        "incident_type": "ContainerOOMKilled",
        "agent_reasoning": "Detected OOM pattern in logs and abrupt restart.",
    }
    monkeypatch.setattr(incidents, "supabase", FakeSupabaseClient(incident_row))

    result = asyncio.run(incidents.get_incident("inc-001", user={"sub": "u1"}))

    assert result["container_name"] == "api-container"
    assert result["severity"] == "critical"
    assert result["status"] == "detected"
    assert result["server_name"] == "node-a"
    assert result["created_at"] == "2026-03-24T12:00:00Z"
    assert result["logs"] == "panic: out of memory"
    assert result["incident_type"] == "ContainerOOMKilled"
    assert "agent_reasoning" in result


def test_get_incident_logic_returns_404_when_not_found(monkeypatch):
    monkeypatch.setattr(incidents, "supabase", FakeSupabaseClient(None))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(incidents.get_incident("missing-id", user={"sub": "u1"}))

    assert exc.value.status_code == 404
    assert exc.value.detail == "Incidente no encontrado"
