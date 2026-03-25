from routers import incidents
from tests.conftest import FakeResponse, FakeSupabaseClient


class _ListQueryRecorder:
    def __init__(self, rows):
        self._rows = rows
        self.order_calls = []
        self.eq_calls = []

    def select(self, _value):
        return self

    def eq(self, key, value):
        self.eq_calls.append((key, value))
        return self

    def order(self, column, desc=False):
        self.order_calls.append((column, desc))
        return self

    def execute(self):
        return FakeResponse(self._rows)


class _ListSupabaseRecorder:
    def __init__(self, rows):
        self.rows = rows
        self.last_query = None

    def table(self, _name):
        self.last_query = _ListQueryRecorder(self.rows)
        return self.last_query


def test_list_incidents_success_returns_rows(client, monkeypatch):
    rows = [
        {"id": "a", "title": "One", "status": "detected", "created_at": "2026-03-24T10:00:00Z"},
        {"id": "b", "title": "Two", "status": "resolved", "created_at": "2026-03-24T09:00:00Z"},
    ]
    monkeypatch.setattr(incidents, "supabase", FakeSupabaseClient(rows))

    response = client.get("/api/incidents/")

    assert response.status_code == 200
    assert response.json() == rows


def test_list_incidents_orders_by_created_at_desc(client, monkeypatch):
    rows = [{"id": "x", "created_at": "2026-03-24T12:00:00Z"}]
    recorder = _ListSupabaseRecorder(rows)
    monkeypatch.setattr(incidents, "supabase", recorder)

    response = client.get("/api/incidents/")

    assert response.status_code == 200
    assert recorder.last_query.order_calls == [("created_at", True)]


def test_list_incidents_filters_by_status_query_param(client, monkeypatch):
    rows = [{"id": "1", "status": "detected"}]
    recorder = _ListSupabaseRecorder(rows)
    monkeypatch.setattr(incidents, "supabase", recorder)

    response = client.get("/api/incidents/?status=detected")

    assert response.status_code == 200
    assert recorder.last_query.eq_calls == [("status", "detected")]


def test_list_incidents_empty_list(client, monkeypatch):
    monkeypatch.setattr(incidents, "supabase", FakeSupabaseClient([]))

    response = client.get("/api/incidents/")

    assert response.status_code == 200
    assert response.json() == []
