from services.incident_notifications import (
    build_notification_payload,
    notify_if_severity_requires_alert,
)


def test_notification_sent_for_critical_or_high():
    sent = []

    def send_fn(payload):
        sent.append(payload)

    for severity in ("critical", "high"):
        sent.clear()
        ok = notify_if_severity_requires_alert(
            severity,
            service="api-orders",
            incident_type="oom",
            timestamp="2026-03-24T15:00:00Z",
            send_fn=send_fn,
        )
        assert ok is True
        assert len(sent) == 1
        assert sent[0]["service"] == "api-orders"
        assert sent[0]["incident_type"] == "oom"
        assert sent[0]["timestamp"] == "2026-03-24T15:00:00Z"


def test_notification_not_sent_for_medium_or_low():
    sent = []

    def send_fn(payload):
        sent.append(payload)

    for severity in ("medium", "low"):
        sent.clear()
        ok = notify_if_severity_requires_alert(
            severity,
            service="worker",
            incident_type="app_crash",
            timestamp="2026-03-24T16:00:00Z",
            send_fn=send_fn,
        )
        assert ok is False
        assert sent == []


def test_notification_payload_has_required_fields():
    payload = build_notification_payload(
        service="payments",
        incident_type="dependency_failure",
        timestamp="2026-03-24T17:30:00Z",
    )
    assert set(payload.keys()) == {"service", "incident_type", "timestamp"}
    assert payload["service"] == "payments"
    assert payload["incident_type"] == "dependency_failure"
    assert payload["timestamp"] == "2026-03-24T17:30:00Z"
