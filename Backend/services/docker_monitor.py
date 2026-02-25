import docker
import os
import socket
import threading
import logging

from db.supabase_client import supabase

LOCAL_SERVER_NAME = socket.gethostname()

logger = logging.getLogger(__name__)

WATCHED_ACTIONS = ("die", "oom")

# Exit codes que indican parada intencional — no son incidentes reales
INTENTIONAL_EXIT_CODES = {"0", "130", "143"}

SEVERITY_MAP = {
    "oom": "critical",
    "137": "critical",   # SIGKILL / OOM killer
    "1": "high",
    "2": "high",
}


def get_docker_client() -> docker.DockerClient:
    try:
        return docker.from_env()
    except docker.errors.DockerException:
        fallback = f'unix://{os.path.expanduser("~")}/.docker/run/docker.sock'
        return docker.DockerClient(base_url=fallback)


LOG_TAIL_LINES = 100


def fetch_container_logs(client: docker.DockerClient, container_id: str) -> str:
    """
    Obtiene los últimos logs del contenedor. El contenedor ya está detenido
    pero Docker conserva los logs hasta que sea eliminado.
    Retorna string vacío si no se pueden obtener (ej: contenedor con --rm ya eliminado).
    """
    try:
        container = client.containers.get(container_id)
        raw_logs = container.logs(tail=LOG_TAIL_LINES, timestamps=True)
        return raw_logs.decode("utf-8", errors="replace")
    except docker.errors.NotFound:
        logger.warning(f"Contenedor {container_id} ya eliminado — logs no disponibles")
        return ""
    except Exception as e:
        logger.error(f"Error obteniendo logs del contenedor {container_id}: {e}")
        return ""


def create_incident_from_event(
    event: dict,
    client: docker.DockerClient = None,
    server_name: str = None,
):
    attrs = event.get("Actor", {}).get("Attributes", {})
    container_id = event.get("Actor", {}).get("ID", "")
    container_name = attrs.get("name", "unknown")
    exit_code = attrs.get("exitCode", "unknown")
    action = event.get("Action", "die")

    # Ignorar paradas intencionales (docker stop, Ctrl+C, salida limpia)
    if exit_code in INTENTIONAL_EXIT_CODES:
        logger.info(f"Contenedor '{container_name}' detenido intencionalmente (exit {exit_code}) — ignorado")
        return

    # Determinar severidad por exit_code primero, luego por acción
    severity = SEVERITY_MAP.get(exit_code) or SEVERITY_MAP.get(action, "medium")

    # Si el agente remoto ya envió los logs, usarlos directamente
    logs = event.get("logs_override") or ""
    if not logs and client and container_id:
        logs = fetch_container_logs(client, container_id)

    # server_name: viene del agente remoto o se usa el hostname local
    resolved_server = server_name or event.get("server_name") or LOCAL_SERVER_NAME

    incident = {
        "title": f"Contenedor '{container_name}' falló ({action})",
        "container_name": container_name,
        "exit_code": exit_code,
        "severity": severity,
        "status": "detected",
        "logs": logs or None,
        "server_name": resolved_server,
    }

    try:
        supabase.table("incidents").insert(incident).execute()
        logger.info(f"Incidente creado — contenedor: {container_name}, acción: {action}, logs: {len(logs)} chars")
    except Exception as e:
        logger.error(f"Error al crear incidente en Supabase: {e}")


def _monitor_loop():
    try:
        client = get_docker_client()
        logger.info("Docker monitor activo — escuchando eventos del daemon...")

        for event in client.events(decode=True):
            if (
                event.get("Type") == "container"
                and event.get("Action") in WATCHED_ACTIONS
            ):
                create_incident_from_event(event, client=client)

    except Exception as e:
        logger.error(f"Docker monitor detenido inesperadamente: {e}")


def run_monitor_in_background():
    thread = threading.Thread(target=_monitor_loop, daemon=True, name="docker-monitor")
    thread.start()
    logger.info("Thread docker-monitor iniciado")
    return thread
