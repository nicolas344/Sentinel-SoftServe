from typing import Any, Callable, Dict

NOTIFY_SEVERITIES = frozenset({"critical", "high"})


def build_notification_payload(
    service: str,
    incident_type: str,
    timestamp: str,
) -> Dict[str, str]:
    """Body sent to the notification channel (mocked in tests)."""
    return {
        "service": service,
        "incident_type": incident_type,
        "timestamp": timestamp,
    }


def notify_if_severity_requires_alert(
    severity: str,
    *,
    service: str,
    incident_type: str,
    timestamp: str,
    send_fn: Callable[[Dict[str, str]], Any],
) -> bool:
    """
    Sends a notification for ``critical`` / ``high`` severities only.
    Returns whether a notification was dispatched.
    """
    if severity not in NOTIFY_SEVERITIES:
        return False
    send_fn(
        build_notification_payload(
            service=service,
            incident_type=incident_type,
            timestamp=timestamp,
        )
    )
    return True
