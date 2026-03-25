import json
import logging
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)

URGENCY_LEVELS = frozenset({"immediate", "monitor", "low"})


def _agent_reasoning_payload(
    root_cause: str, recommended_actions: list, urgency: str
) -> str:
    body = {
        "root_cause": root_cause,
        "recommended_actions": recommended_actions,
        "urgency": urgency,
    }
    return json.dumps(body, ensure_ascii=False)


def run_root_cause_analysis(
    incident_id: str,
    logs: str,
    *,
    supabase_client: Any,
    analyze_fn: Callable[..., Dict[str, Any]],
) -> bool:
    """
    Runs LLM+runbooks analysis on ``logs``, persists ``agent_reasoning`` and ``analyzed`` status.
    Returns False on failure or invalid analyzer output (never raises to callers).
    """
    try:
        raw = analyze_fn(logs=logs)
        root_cause = (raw.get("root_cause") or "").strip()
        actions = raw.get("recommended_actions") or []
        urgency = raw.get("urgency") or "low"

        if not root_cause or not isinstance(actions, list):
            return False
        if len(actions) < 3:
            logger.warning("Root cause analysis: need at least 3 recommended actions")
            return False
        if urgency not in URGENCY_LEVELS:
            urgency = "low"

        reasoning = _agent_reasoning_payload(root_cause, actions, urgency)
        (
            supabase_client.table("incidents")
            .update({"status": "analyzed", "agent_reasoning": reasoning})
            .eq("id", incident_id)
            .execute()
        )
        return True
    except Exception as exc:
        logger.warning("Root cause analysis failed: %s", exc)
        return False
