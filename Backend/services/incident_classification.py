import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

CLASSIFICATION_LABELS = frozenset(
    {"app_crash", "oom", "config_error", "dependency_failure", "unknown"}
)


def _normalize_label(raw: str) -> str:
    if raw in CLASSIFICATION_LABELS:
        return raw
    return "unknown"


def classify_incident_text(
    title: str,
    severity: str,
    logs: Optional[str],
    classify_fn: Callable[..., str],
) -> str:
    """Calls the LLM/classifier; on any failure returns ``unknown``."""
    try:
        label = classify_fn(title=title, severity=severity, logs=logs or "")
        return _normalize_label(label)
    except Exception as exc:
        logger.warning("Classification failed: %s", exc)
        return "unknown"


def apply_auto_classification(
    incident_id: str,
    title: str,
    severity: str,
    logs: Optional[str],
    *,
    supabase_client: Any,
    classify_fn: Callable[..., str],
) -> str:
    """
    Sets status to ``investigating``, runs classification, persists ``incident_type``.
    """
    (
        supabase_client.table("incidents")
        .update({"status": "investigating"})
        .eq("id", incident_id)
        .execute()
    )

    label = classify_incident_text(title, severity, logs, classify_fn)

    (
        supabase_client.table("incidents")
        .update({"incident_type": label})
        .eq("id", incident_id)
        .execute()
    )

    return label
