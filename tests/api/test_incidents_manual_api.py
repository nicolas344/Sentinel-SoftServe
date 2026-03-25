from routers import incidents
from tests.conftest import FakeResponse


class _InsertCapture:
    def __init__(self):
        self.rows = []

    def table(self, _name):
        return self

    def insert(self, row):
        self.rows.append(row)
        return self

    def execute(self):
        last = self.rows[-1]
        return FakeResponse([{**last, "id": "inc-manual-1"}])


def test_create_manual_incident_success(client, monkeypatch):
    capture = _InsertCapture()
    monkeypatch.setattr(incidents, "supabase", capture)

    payload = {
        "title": "DB connection pool exhausted",
        "container_name": "api-orders",
        "severity": "high",
    }
    response = client.post("/api/incidents/", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == payload["title"]
    assert body["container_name"] == payload["container_name"]
    assert body["severity"] == "high"
    assert body["status"] == "detected"
    assert body["id"] == "inc-manual-1"
    assert len(capture.rows) == 1
    assert capture.rows[0]["status"] == "detected"


def test_create_manual_incident_missing_required_fields(client):
    response = client.post("/api/incidents/", json={"title": "Only title"})

    assert response.status_code == 422


def test_create_manual_incident_invalid_severity(client):
    response = client.post(
        "/api/incidents/",
        json={
            "title": "x",
            "container_name": "svc",
            "severity": "urgent",
        },
    )

    assert response.status_code == 422
