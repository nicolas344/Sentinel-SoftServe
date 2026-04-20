"""
Memoria episódica: incidentes pasados del dominio.

A diferencia de runbooks (curados), esta memoria crece sola: cada
incidente investigado se almacena como un documento con metadata.
Cuando llega una alerta nueva, el agente consulta aquí buscando "¿esto
ya pasó antes? ¿qué funcionó?".

Convención de colección: incidents-<dominio> (ej. incidents-docker).
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from services.agents.memory.chroma_client import get_or_create_collection

if TYPE_CHECKING:
    from services.agents.base import IncidentContext, InvestigationResult

logger = logging.getLogger(__name__)


def _build_document(ctx: "IncidentContext", result: "InvestigationResult") -> str:
    """
    Texto que se embedará. Lo que entra aquí es lo que se puede recuperar
    después por similitud semántica, así que incluir señales fuertes:
    título, tipo, target, y un resumen condensado del análisis.
    """
    analysis_brief = result.analysis[:1500]  # limitar tamaño del embedding
    return (
        f"Título: {ctx.title}\n"
        f"Tipo: {ctx.incident_type or 'unknown'}\n"
        f"Target: {ctx.target}\n"
        f"Severidad: {ctx.severity}\n\n"
        f"{analysis_brief}"
    )


def store_incident(
    collection_name: str,
    ctx: "IncidentContext",
    result: "InvestigationResult",
) -> None:
    """
    Guarda un incidente investigado en la memoria episódica del dominio.
    Idempotente: si ya existe un documento con el mismo incident_id, lo reemplaza.
    """
    try:
        collection = get_or_create_collection(collection_name)

        tools_used = [tc.name for tc in result.tool_calls]
        metadata = {
            "incident_id": ctx.incident_id,
            "title": ctx.title,
            "target": ctx.target,
            "severity": ctx.severity,
            "incident_type": ctx.incident_type or "unknown",
            "tools_used": ",".join(tools_used),  # Chroma no acepta listas en metadata
            "stored_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        doc = _build_document(ctx, result)

        collection.upsert(
            ids=[ctx.incident_id],
            documents=[doc],
            metadatas=[metadata],
        )
        logger.info(
            f"[memory.incidents] Incidente '{ctx.incident_id[:8]}' almacenado en "
            f"'{collection_name}' (tools: {tools_used or 'ninguno'})"
        )
    except Exception as e:
        logger.warning(f"[memory.incidents] No se pudo almacenar '{ctx.incident_id[:8]}': {e}")


def query_incidents(collection_name: str, query: str, k: int = 3) -> list[dict]:
    """
    Devuelve los k incidentes pasados más parecidos, cada uno como dict con:
      - id, document (texto original), metadata, distance
    Se filtran los documentos con distancia > 1.5 (poco parecido) para no
    inyectar ruido en el prompt.
    """
    try:
        collection = get_or_create_collection(collection_name)
        results = collection.query(
            query_texts=[query],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        out = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        for i, d, m, dist in zip(ids, docs, metas, dists):
            if dist is not None and dist > 1.5:
                continue
            out.append({"id": i, "document": d, "metadata": m or {}, "distance": dist})
        return out
    except Exception as e:
        logger.warning(f"[memory.incidents] Falla al consultar '{collection_name}': {e}")
        return []
