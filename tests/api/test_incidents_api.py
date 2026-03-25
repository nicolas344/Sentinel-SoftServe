from routers import incidents
from tests.conftest import FakeResponse, FakeSupabaseClient


def test_get_incident_api_success_returns_full_details(client, monkeypatch):
    incident_row = {
        "id": "inc-100",
        "container_name": "worker-01",
        "severity": "high",
        "status": "investigating",
        "server_name": "srv-01",
        "created_at": "2026-03-24T10:10:00Z",
        "logs": "error stacktrace",
        "incident_type": "ContainerCrashed",
        "agent_reasoning": "Crash loop observed after deployment.",
    }
    monkeypatch.setattr(incidents, "supabase", FakeSupabaseClient(incident_row))

    response = client.get("/api/incidents/inc-100")

    assert response.status_code == 200
    body = response.json()
    assert body["container_name"] == "worker-01"
    assert body["severity"] == "high"
    assert body["status"] == "investigating"
    assert body["server_name"] == "srv-01"
    assert body["created_at"] == "2026-03-24T10:10:00Z"
    assert body["logs"] == "error stacktrace"
    assert body["incident_type"] == "ContainerCrashed"
    assert body["agent_reasoning"] == "Crash loop observed after deployment."


def test_get_incident_api_returns_404_when_incident_missing(client, monkeypatch):
    monkeypatch.setattr(incidents, "supabase", FakeSupabaseClient(None))

    response = client.get("/api/incidents/missing-id")

    assert response.status_code == 404
    assert response.json() == {"detail": "Incidente no encontrado"}


def test_get_incident_api_simulates_realtime_update(client, monkeypatch):
    sequence = iter(
        [
            {
                "id": "inc-rt-1",
                "container_name": "job-runner",
                "severity": "medium",
                "status": "detected",
                "server_name": "srv-rt",
                "created_at": "2026-03-24T11:00:00Z",
                "logs": "initial logs",
                "incident_type": "ContainerCrashed",
                "agent_reasoning": "Initial triage.",
            },
            {
                "id": "inc-rt-1",
                "container_name": "job-runner",
                "severity": "medium",
                "status": "resolved",
                "server_name": "srv-rt",
                "created_at": "2026-03-24T11:00:00Z",
                "logs": "initial logs\nfixed",
                "incident_type": "ContainerCrashed",
                "agent_reasoning": "Issue resolved after restart.",
            },
        ]
    )

    class SequenceSupabase:
        def table(self, _table_name):
            return self

        def select(self, _value):
            return self

        def eq(self, _key, _value):
            return self

        def single(self):
            return self

        def execute(self):
            return FakeResponse(next(sequence))

    monkeypatch.setattr(incidents, "supabase", SequenceSupabase())

    first = client.get("/api/incidents/inc-rt-1")
    second = client.get("/api/incidents/inc-rt-1")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "detected"
    assert second.json()["status"] == "resolved"
    assert "fixed" in second.json()["logs"]
