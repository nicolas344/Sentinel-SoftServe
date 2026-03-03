import os
import requests
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from db.supabase_client import supabase

logger = logging.getLogger(__name__)

LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")

SEVERITY_MAP = {
    "ContainerCrashed": "high",
    "ContainerOOMKilled": "critical",
}


def _extract_container_id(raw_id: str) -> str:
    """
    Convierte '/docker/abc123def456...' en 'abc123def456' (ID completo).
    """
    return raw_id.replace("/docker/", "").strip("/")


def query_loki_logs(container_id: str, alert_time: datetime, lines: int = 100) -> str:
    """
    Consulta Loki para obtener los logs del contenedor usando su ID.
    Promtail etiqueta los logs con container_id=<id_completo>.
    Busca en una ventana de 5 minutos antes del crash.
    """
    if not container_id:
        return ""

    try:
        start = alert_time - timedelta(minutes=5)
        end = alert_time + timedelta(minutes=1)

        params = {
            "query": f'{{container_id="{container_id}"}}',
            "start": str(int(start.timestamp() * 1e9)),
            "end": str(int(end.timestamp() * 1e9)),
            "limit": lines,
            "direction": "forward",
        }

        response = requests.get(
            f"{LOKI_URL}/loki/api/v1/query_range",
            params=params,
            timeout=5,
        )
        response.raise_for_status()

        streams = response.json().get("data", {}).get("result", [])

        if not streams:
            logger.warning(f"Sin logs en Loki para container_id='{container_id[:12]}'")
            return ""

        log_lines = []
        for stream in streams:
            for ts_ns, line in stream.get("values", []):
                ts = datetime.fromtimestamp(int(ts_ns) / 1e9, tz=timezone.utc)
                log_lines.append((ts, line))

        log_lines.sort(key=lambda x: x[0])

        formatted = "\n".join(
            f"[{ts.strftime('%Y-%m-%d %H:%M:%S UTC')}] {line}"
            for ts, line in log_lines[-lines:]
        )
        logger.info(f"Logs obtenidos de Loki: {len(log_lines)} líneas para {container_id[:12]}")
        return formatted

    except requests.exceptions.ConnectionError:
        logger.warning(f"No se pudo conectar a Loki ({LOKI_URL}) — logs no disponibles")
        return ""
    except Exception as e:
        logger.error(f"Error consultando Loki: {e}")
        return ""


def process_prometheus_alert(alert: dict) -> Optional[Tuple[str, str, str, str, str]]:
    """
    Convierte una alerta de Alertmanager en un incidente de Sentinel.
    - status 'firing'   → crea incidente, retorna (incident_id, container_name, logs, severity, title)
    - status 'resolved' → cierra incidentes activos del contenedor, retorna None
    """
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    status = alert.get("status", "firing")

    alert_name = labels.get("alertname", "UnknownAlert")
    severity = labels.get("severity") or SEVERITY_MAP.get(alert_name, "medium")
    summary = annotations.get("summary", f"Alerta: {alert_name}")

    # cAdvisor expone el label 'id' como '/docker/<container_id>'
    raw_id = labels.get("id", "")
    container_id = _extract_container_id(raw_id)
    container_name = container_id[:12] if container_id else "unknown"

    raw_instance = labels.get("instance", "")
    # 'instance' en cAdvisor local es 'cadvisor:8080' — usamos 'localhost'
    if not raw_instance or raw_instance.startswith("cadvisor"):
        server_name = "localhost"
    else:
        server_name = raw_instance.split(":")[0]

    if status == "resolved":
        _resolve_incident(container_name)
        return None

    # Timestamp de inicio de la alerta
    starts_at_str = alert.get("startsAt", "")
    try:
        alert_time = datetime.fromisoformat(starts_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        alert_time = datetime.now(tz=timezone.utc)

    logs = query_loki_logs(container_id, alert_time)

    incident = {
        "title": summary,
        "container_name": container_name,
        "severity": severity,
        "status": "detected",
        "logs": logs if logs else annotations.get("description") or None,
        "server_name": server_name,
    }

    try:
        response = supabase.table("incidents").insert(incident).execute()
        incident_id = response.data[0]["id"]
        logger.info(
            f"Incidente creado — id: {incident_id[:8]}, container: {container_name}, "
            f"severidad: {severity}, logs: {len(logs)} chars"
        )
        return (incident_id, container_name, logs, severity, incident["title"])
    except Exception as e:
        logger.error(f"Error al crear incidente en Supabase: {e}")
        return None


def _resolve_incident(container_name: str):
    """
    Marca como 'resolved' todos los incidentes activos de ese contenedor.
    """
    try:
        response = (
            supabase.table("incidents")
            .update({"status": "resolved"})
            .eq("container_name", container_name)
            .in_("status", ["detected", "investigating"])
            .execute()
        )
        if response.data:
            logger.info(f"Incidente resuelto automáticamente — contenedor: {container_name}")
    except Exception as e:
        logger.error(f"Error resolviendo incidente para '{container_name}': {e}")
