"""
Rescate de incidentes huérfanos.

El triage corre como BackgroundTask de FastAPI: si el proceso se reinicia
(deploy, crash, dyno dormido) a mitad de pipeline, el incidente queda
atascado para siempre en un estado de procesamiento ('detected',
'investigating', 'executing_solution', 'verifying') sin que nadie lo retome.

Este módulo corre un sweep al arrancar y luego cada SWEEP_INTERVAL_SEC:
los incidentes en estado de procesamiento cuya última actividad supera
STUCK_THRESHOLD_MIN se marcan como 'failed' con una nota explicativa, para
que el ingeniero los vea en el dashboard en lugar de creer que siguen en curso.

'analyzed' y 'awaiting_approval' NO se tocan: son estados de espera humana
legítimamente largos.
"""

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from db.supabase_client import supabase
from services.incident_events import record_event

logger = logging.getLogger(__name__)

STUCK_THRESHOLD_MIN = int(os.getenv("RECOVERY_STUCK_THRESHOLD_MIN", "30"))
SWEEP_INTERVAL_SEC = int(os.getenv("RECOVERY_SWEEP_INTERVAL_SEC", "900"))

# Estados transitorios que un proceso vivo resuelve en segundos/minutos.
_PROCESSING_STATUSES = ("detected", "investigating", "executing_solution", "verifying")

_ORPHAN_NOTE = (
    "[RECOVERY] El incidente quedó huérfano: el backend se reinició mientras "
    "el pipeline estaba en curso y el procesamiento no se retomó. "
    "Requiere revisión manual."
)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def sweep_orphaned_incidents() -> int:
    """
    Marca como 'failed' los incidentes atascados en estados de procesamiento.
    Retorna cuántos se rescataron.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=STUCK_THRESHOLD_MIN)
    rescued = 0

    try:
        response = (
            supabase.table("incidents")
            .select("id,status,created_at,executed_at")
            .in_("status", list(_PROCESSING_STATUSES))
            .execute()
        )
    except Exception as e:
        logger.warning(f"[Recovery] No se pudo consultar incidentes atascados: {e}")
        return 0

    for incident in response.data or []:
        # Para executing/verifying la referencia es el momento de ejecución;
        # para detected/investigating, el de creación.
        reference = _parse_ts(incident.get("executed_at")) or _parse_ts(incident.get("created_at"))
        if reference is None or reference > cutoff:
            continue

        try:
            # Condicionado al estado leído: si el pipeline avanzó entre el
            # SELECT y este UPDATE, no pisamos la transición legítima.
            claim = (
                supabase.table("incidents")
                .update({"status": "failed", "action_error": _ORPHAN_NOTE})
                .eq("id", incident["id"])
                .eq("status", incident["status"])
                .execute()
            )
            if claim.data:
                record_event(incident["id"], "failed")
                rescued += 1
                logger.info(
                    f"[Recovery] Incidente {incident['id'][:8]} rescatado "
                    f"(atascado en '{incident['status']}')"
                )
        except Exception as e:
            logger.warning(f"[Recovery] Error rescatando {incident['id'][:8]}: {e}")

    return rescued


_loop_started = False


def start_recovery_loop() -> None:
    """Lanza el sweep en un hilo daemon: una pasada al arrancar y luego periódica."""
    global _loop_started
    if _loop_started:
        return
    _loop_started = True

    def _loop():
        time.sleep(10)  # dejar que el arranque termine antes del primer sweep
        while True:
            try:
                rescued = sweep_orphaned_incidents()
                if rescued:
                    logger.info(f"[Recovery] Sweep completado: {rescued} incidentes rescatados")
            except Exception as e:
                logger.warning(f"[Recovery] Sweep falló: {e}")
            time.sleep(SWEEP_INTERVAL_SEC)

    threading.Thread(target=_loop, name="sentinel-recovery", daemon=True).start()
