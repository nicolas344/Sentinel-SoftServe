import logging

from services.agents.memory.chroma_client import get_or_create_collection

logger = logging.getLogger(__name__)

_POST_MORTEM_COLLECTION = "postmortems-incidents"


def store_post_mortem_in_kb(incident: dict, content_md: str) -> None:
    incident_id = str(incident.get("id") or "")
    if not incident_id or not content_md.strip():
        return

    metadata = {
        "incident_id": incident_id,
        "title": incident.get("title") or "",
        "severity": incident.get("severity") or "",
        "status": incident.get("status") or "",
        "target": incident.get("target") or "",
        "source_type": incident.get("source_type") or "",
        "resolved_at": incident.get("resolved_at") or "",
    }

    try:
        collection = get_or_create_collection(_POST_MORTEM_COLLECTION)
        collection.upsert(
            ids=[incident_id],
            documents=[content_md[:12000]],
            metadatas=[metadata],
        )
    except Exception as exc:
        logger.warning(f"[postmortem.kb] No se pudo guardar en ChromaDB {incident_id[:8]}: {exc}")
