from services import alert_processor
from tests.conftest import FakeResponse


class _CapturingSupabase:
    """Minimal chain: table(...).insert(...).execute() or .update(...).eq(...).in_(...).execute()"""

    def __init__(self):
        self.inserts = []
        self.updates = []

    def table(self, _name):
        return _TableChain(self)


class _TableChain:
    def __init__(self, root: _CapturingSupabase):
        self._root = root

    def insert(self, row):
        self._root.inserts.append(row)
        return self

    def update(self, row):
        self._root.updates.append(row)
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def execute(self):
        return FakeResponse([])


def _firing_webhook(container_docker_id="/docker/abcdef1234567890abcdef"):
    return {
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "ContainerCrashed",
                    "id": container_docker_id,
                    "instance": "cadvisor:8080",
                    "severity": "high",
                },
                "annotations": {"summary": "Contenedor dejó de reportar métricas"},
                "startsAt": "2026-03-24T12:00:00.000Z",
            }
        ],
    }


def test_alerts_firing_creates_incident(client, monkeypatch):
    capture = _CapturingSupabase()
    monkeypatch.setattr(alert_processor, "supabase", capture)
    monkeypatch.setattr(alert_processor, "query_loki_logs", lambda *_a, **_k: "")

    response = client.post("/api/alerts", json=_firing_webhook())

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert len(capture.inserts) == 1
    row = capture.inserts[0]
    assert row["container_name"] == "abcdef123456"
    assert row["server_name"] == "localhost"
    assert row["status"] == "detected"
    assert row["title"] == "Contenedor dejó de reportar métricas"


def test_alerts_resolved_does_not_create_incident(client, monkeypatch):
    capture = _CapturingSupabase()
    monkeypatch.setattr(alert_processor, "supabase", capture)

    body = _firing_webhook()
    body["alerts"][0]["status"] = "resolved"
    body["status"] = "resolved"

    response = client.post("/api/alerts", json=body)

    assert response.status_code == 200
    assert len(capture.inserts) == 0
    assert len(capture.updates) == 1


def test_alerts_invalid_payload_returns_unprocessable(client):
    response = client.post("/api/alerts", json={"status": "firing"})

    assert response.status_code == 422
