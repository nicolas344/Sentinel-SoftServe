"""
Registro de eventos de transición de estado de incidentes.

Cada vez que un incidente cambia de estado, se inserta una fila en
`incident_events`. Esto permite mostrar timestamps exactos en el
timeline del frontend (Issue #17).

Todas las funciones son best-effort: si Supabase falla, solo se
loguea una advertencia y el flujo principal continúa sin interrupción.
"""

import logging

from db.supabase_client import supabase

logger = logging.getLogger(__name__)


def record_event(incident_id: str, status: str) -> None:
    """Inserta una fila en incident_events para registrar la transición de estado."""
    try:
        supabase.table("incident_events").insert({
            "incident_id": incident_id,
            "status": status,
        }).execute()
    except Exception as e:
        logger.warning(
            f"[Events] No se pudo registrar evento '{status}' "
            f"para {incident_id[:8]}: {e}"
        )
