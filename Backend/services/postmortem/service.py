import logging
from datetime import datetime, timezone
from typing import Any

from db.supabase_client import supabase
from services.postmortem.formatters import format_mttr
from services.postmortem.generator import generate_post_mortem_with_llm
from services.postmortem.knowledge_base import store_post_mortem_in_kb

logger = logging.getLogger(__name__)
_EVENTS_HAS_CREATED_AT: bool | None = None


def _get_incident(incident_id: str) -> dict[str, Any] | None:
    try:
        response = (
            supabase.table("incidents")
            .select("*")
            .eq("id", incident_id)
            .single()
            .execute()
        )
        return response.data
    except Exception:
        return None


def _get_timeline(incident_id: str) -> list[dict[str, Any]]:
    global _EVENTS_HAS_CREATED_AT

    if _EVENTS_HAS_CREATED_AT is None:
        try:
            supabase.table("incident_events").select("created_at").limit(1).execute()
            _EVENTS_HAS_CREATED_AT = True
        except Exception:
            _EVENTS_HAS_CREATED_AT = False

    if _EVENTS_HAS_CREATED_AT:
        try:
            response = (
                supabase.table("incident_events")
                .select("status,created_at")
                .eq("incident_id", incident_id)
                .order("created_at", desc=False)
                .execute()
            )
            return response.data or []
        except Exception as exc:
            logger.warning(
                f"[postmortem.service] Timeline con created_at falló"
                f" para {incident_id[:8]}: {exc}"
            )

    try:
        fallback = (
            supabase.table("incident_events")
            .select("status")
            .eq("incident_id", incident_id)
            .execute()
        )
        events = fallback.data or []
        return [{"status": e.get("status"), "created_at": None} for e in events]
    except Exception as fallback_exc:
        logger.warning(
            f"[postmortem.service] No se pudo cargar timeline fallback"
            f" {incident_id[:8]}: {fallback_exc}"
        )
        return []


def generate_post_mortem_for_incident(incident_id: str, force: bool = False) -> str | None:
    incident = _get_incident(incident_id)
    if not incident:
        return None

    if incident.get("status") != "resolved":
        return None

    current = (incident.get("post_mortem_md") or "").strip()
    if current and not force:
        return current

    resolved_at = incident.get("resolved_at") or incident.get("updated_at")
    mttr = format_mttr(incident.get("created_at"), resolved_at)
    timeline = _get_timeline(incident_id)
    generated = generate_post_mortem_with_llm(incident, timeline, mttr)

    save_post_mortem(incident_id, generated, incident=incident)
    return generated


def save_post_mortem(
    incident_id: str, content_md: str, incident: dict[str, Any] | None = None
) -> None:
    if not content_md.strip():
        return

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    try:
        supabase.table("incidents").update({
            "post_mortem_md": content_md,
            "post_mortem_updated_at": now_iso,
        }).eq("id", incident_id).execute()
    except Exception as exc:
        logger.warning(
            f"[postmortem.service] No se pudo persistir post-mortem"
            f" {incident_id[:8]}: {exc}"
        )
        return

    if not incident:
        incident = _get_incident(incident_id)
    if incident:
        incident["post_mortem_updated_at"] = now_iso
        store_post_mortem_in_kb(incident, content_md)


def build_incident_export_payload(incident_id: str) -> dict[str, Any] | None:
    incident = _get_incident(incident_id)
    if not incident:
        return None

    timeline = _get_timeline(incident_id)
    mttr = format_mttr(
        incident.get("created_at"),
        incident.get("resolved_at") or incident.get("updated_at"),
    )

    decisions: list[dict[str, Any]] = []
    if incident.get("proposed_action"):
        decisions.append({
            "type": "proposed_action",
            "detail": incident.get("proposed_action"),
            "at": incident.get("updated_at") or incident.get("created_at"),
        })
    if incident.get("action_error"):
        decisions.append({
            "type": "action_error",
            "detail": incident.get("action_error"),
            "at": incident.get("updated_at") or incident.get("created_at"),
        })

    actions: list[dict[str, Any]] = []
    if incident.get("proposed_action") or incident.get("action_result"):
        actions.append({
            "name": "incident_action",
            "command": incident.get("proposed_action") or "",
            "executed_at": incident.get("executed_at"),
            "status": incident.get("status"),
            "output": incident.get("action_result") or incident.get("action_error") or "",
        })

    return {
        "metadata": {
            "id": incident.get("id"),
            "title": incident.get("title"),
            "severity": incident.get("severity"),
            "status": incident.get("status"),
            "source_type": incident.get("source_type"),
            "target": incident.get("target"),
            "created_at": incident.get("created_at"),
            "resolved_at": incident.get("resolved_at"),
            "mttr": mttr,
        },
        "evidence": {
            "logs": incident.get("logs") or "",
            "metrics_snapshot": incident.get("metrics_snapshot") or {},
            "agent_reasoning": incident.get("agent_reasoning") or "",
        },
        "timeline": timeline,
        "decisions": decisions,
        "actions": actions,
        "post_mortem": incident.get("post_mortem_md") or "",
    }
