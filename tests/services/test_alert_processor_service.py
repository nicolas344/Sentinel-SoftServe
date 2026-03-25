from datetime import datetime, timezone

import requests

from services import alert_processor


class DummyLokiResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_query_loki_logs_formats_output_lines(monkeypatch):
    payload = {
        "data": {
            "result": [
                {
                    "values": [
                        ["1711281600000000000", "first line"],
                        ["1711281660000000000", "second line"],
                    ]
                }
            ]
        }
    }

    def fake_get(*_args, **_kwargs):
        return DummyLokiResponse(payload)

    monkeypatch.setattr(alert_processor.requests, "get", fake_get)

    output = alert_processor.query_loki_logs(
        container_id="abc123",
        alert_time=datetime.now(tz=timezone.utc),
        lines=10,
    )

    assert "first line" in output
    assert "second line" in output
    assert "UTC" in output


def test_query_loki_logs_returns_empty_when_loki_unavailable(monkeypatch):
    def fake_get(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError("loki down")

    monkeypatch.setattr(alert_processor.requests, "get", fake_get)

    output = alert_processor.query_loki_logs(
        container_id="abc123",
        alert_time=datetime.now(tz=timezone.utc),
    )

    assert output == ""
