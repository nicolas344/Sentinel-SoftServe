import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import requests

from db.supabase_client import supabase

logger = logging.getLogger(__name__)

LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")

SEVERITY_MAP = {
    # Docker
    "ContainerCrashed":            "high",
    "ContainerOOMKilled":          "critical",
    "ContainerHighMemory":         "high",
    "ContainerCPUThrottling":      "medium",
    "ContainerRestartLoop":        "high",
    "ContainerUnhealthy":          "high",
    "ContainerNetworkErrors":      "medium",
    "ContainerNetworkPacketDrop":  "medium",
    "ContainerDiskPressure":       "high",
    "ContainerHighSwap":           "medium",
    # Kubernetes (kube-state-metrics) — agente pendiente de implementar
    # "KubePodCrashLooping":        "critical",
    # "KubePodOOMKilled":           "critical",
    # "KubePodNotReady":            "high",
    # "KubeDeploymentUnavailable":  "high",
    # "KubeNodeNotReady":           "critical",
    # PostgreSQL (postgres-exporter)
    "PostgresConnectionsExhausted":   "critical",
    "PostgresLongRunningTransaction":  "high",
    "PostgresDeadLocks":               "high",
    "PostgresReplicationLag":          "critical",
    "PostgresLowCacheHitRatio":        "medium",
    "PostgresDatabaseSizeGrowth":      "medium",
}


def _has_active_incident(target: str) -> bool:
    """
    Verifica si ya existe un incidente activo para este target.
    Evita crear duplicados cuando varias alertas se disparan en cascada.
    """
    try:
        response = (
            supabase.table("incidents")
            .select("id")
            .eq("target", target)
            .in_("status", [
                "detected",
                "investigating",
                "analyzed",
                "awaiting_approval",
                "executing_solution",
            ])
            .execute()
        )
        return len(response.data) > 0
    except Exception as e:
        logger.error(f"Error verificando incidente activo para '{target}': {e}")
        return False


def _extract_container_id(raw_id: str, runtime: str = "docker") -> str:
    """
    Docker (cAdvisor): '/docker/abc123...' → 'abc123...'
    Kubernetes: el target se construye desde namespace/pod (no usa container_id)
    """
    if runtime == "docker":
        return raw_id.replace("/docker/", "").strip("/")
    return raw_id.strip()


def query_loki_logs(container_id: str, alert_time: datetime, lines: int = 100) -> str:
    """
    Consulta Loki para obtener logs del contenedor usando su ID.
    Busca en una ventana de 5 minutos antes del crash.
    """
    if not container_id:
        return ""

    try:
        start = alert_time - timedelta(minutes=5)
        end   = alert_time + timedelta(minutes=1)

        params = {
            "query":     f'{{container_id="{container_id}"}}',
            "start":     str(int(start.timestamp() * 1e9)),
            "end":       str(int(end.timestamp() * 1e9)),
            "limit":     lines,
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


def process_prometheus_alert(alert: dict) -> Optional[Tuple[str, str, str, str, str, str]]:
    """
    Convierte una alerta de Alertmanager en un incidente de Sentinel.
    - status 'firing'   → crea incidente, retorna (incident_id, target, logs, severity, title, container_runtime)
    - status 'resolved' → cierra incidentes activos del target, retorna None
    """
    labels      = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    status      = alert.get("status", "firing")

    alert_name = labels.get("alertname", "UnknownAlert")
    severity   = labels.get("severity") or SEVERITY_MAP.get(alert_name, "medium")
    summary    = annotations.get("summary", f"Alerta: {alert_name}")

    # Determinar source_type y container_runtime desde los labels de la alerta
    source_type = labels.get("source_type", "container")
    container_runtime = labels.get("container_runtime", "docker") if source_type == "container" else None

    # Extraer identificador del target
    raw_id         = labels.get("id", "")
    container_id   = _extract_container_id(raw_id, container_runtime or "docker")
    target         = labels.get("name") or (container_id[:12] if container_id else "unknown")

    # Para incidentes de base de datos el target es "postgres/<datname>"
    if source_type == "database":
        datname = labels.get("datname", "unknown")
        target  = f"postgres/{datname}"

    raw_instance = labels.get("instance", "")
    if not raw_instance or raw_instance.startswith("cadvisor"):
        server_name = "localhost"
    else:
        server_name = raw_instance.split(":")[0]

    if status == "resolved":
        _resolve_incident(target)
        return None

    try:
        alert_time = datetime.fromisoformat(
            alert.get("startsAt", "").replace("Z", "+00:00")
        )
    except (ValueError, AttributeError):
        alert_time = datetime.now(tz=timezone.utc)

    # Logs desde Loki (solo para contenedores — Postgres no tiene logs en Loki por ahora)
    logs = ""
    if source_type == "container" and container_id:
        logs = query_loki_logs(container_id, alert_time)

    if not logs:
        logs = annotations.get("description") or ""

    if target != "unknown" and _has_active_incident(target):
        logger.info(f"Incidente activo ya existe para '{target}' ({alert_name}) — omitiendo duplicado")
        return None

    incident = {
        "title":             summary,
        "target":            target,
        "severity":          severity,
        "status":            "detected",
        "source_type":       source_type,
        "container_runtime": container_runtime,
        "logs":              logs or None,
        "server_name":       server_name,
    }

    try:
        response  = supabase.table("incidents").insert(incident).execute()
        incident_id = response.data[0]["id"]
        logger.info(
            f"Incidente creado — id: {incident_id[:8]}, target: {target}, "
            f"source: {source_type}, runtime: {container_runtime}, severidad: {severity}"
        )
        return (incident_id, target, logs, severity, summary, container_runtime or "")
    except Exception as e:
        logger.error(f"Error al crear incidente en Supabase: {e}")
        return None


def _resolve_incident(target: str) -> None:
    """Marca como 'resolved' todos los incidentes activos de ese target."""
    try:
        response = (
            supabase.table("incidents")
            .update({
                "status":      "resolved",
                "resolved_at": datetime.now(tz=timezone.utc).isoformat(),
            })
            .eq("target", target)
            .in_("status", [
                "detected",
                "investigating",
                "analyzed",
                "awaiting_approval",
                "executing_solution",
            ])
            .execute()
        )
        if response.data:
            logger.info(f"Incidente resuelto automáticamente — target: {target}")
    except Exception as e:
        logger.error(f"Error resolviendo incidente para '{target}': {e}")
