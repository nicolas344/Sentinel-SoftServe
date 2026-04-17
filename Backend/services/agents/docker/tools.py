"""
Tools del agente Docker.

Todas son read-only: inspeccionan el estado actual del daemon Docker sin
modificar nada. Si el socket Docker no está accesible (ej. el backend corre
fuera de Docker o sin bind del socket), las tools devuelven un mensaje
descriptivo en lugar de fallar — el agente puede seguir razonando con
los logs de Loki que ya tiene en contexto.
"""

import json
import logging
import os
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_DOCKER_CLIENT = None
_DOCKER_CLIENT_ERROR: Optional[str] = None


def _get_docker():
    """Cliente Docker SDK. Cachea el resultado (bueno o malo) para no reintentar."""
    global _DOCKER_CLIENT, _DOCKER_CLIENT_ERROR
    if _DOCKER_CLIENT is not None or _DOCKER_CLIENT_ERROR is not None:
        return _DOCKER_CLIENT

    try:
        import docker  # type: ignore
        base_url = os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
        _DOCKER_CLIENT = docker.DockerClient(base_url=base_url)
        _DOCKER_CLIENT.ping()
        logger.info(f"[docker.tools] Conectado al daemon Docker en {base_url}")
    except Exception as e:
        _DOCKER_CLIENT_ERROR = str(e)
        logger.warning(f"[docker.tools] Docker SDK no disponible: {e}")
    return _DOCKER_CLIENT


def _unavailable(tool_name: str) -> str:
    return (
        f"Tool '{tool_name}' no disponible: el backend no puede acceder al "
        f"daemon Docker ({_DOCKER_CLIENT_ERROR or 'socket no montado'}). "
        f"Razona con los logs de Loki que ya tienes en contexto."
    )


def _find_container(client, name_or_id: str):
    """Busca por nombre exacto, luego por prefijo de ID."""
    try:
        return client.containers.get(name_or_id)
    except Exception:
        pass
    for c in client.containers.list(all=True):
        if c.name == name_or_id or c.id.startswith(name_or_id):
            return c
    return None


# ── Tools expuestas al LLM ────────────────────────────────────────────────────

@tool
def docker_inspect(container: str) -> str:
    """Inspecciona un contenedor Docker y retorna su estado actual resumido:
    status, exit code, restart count, límites de memoria/CPU, health check,
    imagen, fecha de creación. Úsalo para confirmar el estado actual del
    contenedor tras una alerta."""
    client = _get_docker()
    if client is None:
        return _unavailable("docker_inspect")

    c = _find_container(client, container)
    if c is None:
        return f"Contenedor '{container}' no encontrado."

    data = c.attrs
    state = data.get("State", {})
    host_cfg = data.get("HostConfig", {})
    summary = {
        "name": data.get("Name", "").lstrip("/"),
        "id_short": c.id[:12],
        "image": data.get("Config", {}).get("Image"),
        "status": state.get("Status"),
        "running": state.get("Running"),
        "exit_code": state.get("ExitCode"),
        "error": state.get("Error"),
        "oom_killed": state.get("OOMKilled"),
        "restart_count": data.get("RestartCount"),
        "started_at": state.get("StartedAt"),
        "finished_at": state.get("FinishedAt"),
        "health": (state.get("Health") or {}).get("Status"),
        "mem_limit_bytes": host_cfg.get("Memory"),
        "nano_cpus": host_cfg.get("NanoCpus"),
        "restart_policy": (host_cfg.get("RestartPolicy") or {}).get("Name"),
    }
    return json.dumps(summary, indent=2, default=str)


@tool
def docker_logs(container: str, tail: int = 50) -> str:
    """Obtiene las últimas líneas de log de un contenedor directamente
    desde el daemon Docker (útil cuando los logs de Loki no son suficientes
    o se necesitan líneas más recientes). Parámetros: container (nombre o id),
    tail (cuántas líneas devolver, máximo 200)."""
    client = _get_docker()
    if client is None:
        return _unavailable("docker_logs")

    c = _find_container(client, container)
    if c is None:
        return f"Contenedor '{container}' no encontrado."

    tail = max(1, min(tail, 200))
    try:
        raw = c.logs(tail=tail, timestamps=True).decode("utf-8", errors="replace")
        return raw or "(sin logs recientes)"
    except Exception as e:
        return f"Error obteniendo logs: {e}"


@tool
def docker_stats(container: str) -> str:
    """Snapshot puntual de uso de recursos del contenedor: CPU %, uso de
    memoria vs. límite, I/O de red y disco. Úsalo para ver si el contenedor
    está cerca de sus límites en este momento."""
    client = _get_docker()
    if client is None:
        return _unavailable("docker_stats")

    c = _find_container(client, container)
    if c is None:
        return f"Contenedor '{container}' no encontrado."

    try:
        s = c.stats(stream=False)
    except Exception as e:
        return f"Error obteniendo stats: {e}"

    # Calculo de CPU % según documentación oficial de Docker
    cpu_stats = s.get("cpu_stats", {})
    precpu = s.get("precpu_stats", {})
    cpu_delta = cpu_stats.get("cpu_usage", {}).get("total_usage", 0) - \
                precpu.get("cpu_usage", {}).get("total_usage", 0)
    sys_delta = cpu_stats.get("system_cpu_usage", 0) - precpu.get("system_cpu_usage", 0)
    online_cpus = cpu_stats.get("online_cpus", 1) or 1
    cpu_pct = (cpu_delta / sys_delta) * online_cpus * 100.0 if sys_delta > 0 else 0.0

    mem_usage = s.get("memory_stats", {}).get("usage", 0)
    mem_limit = s.get("memory_stats", {}).get("limit", 1)
    mem_pct = (mem_usage / mem_limit) * 100.0 if mem_limit > 0 else 0.0

    summary = {
        "cpu_percent": round(cpu_pct, 2),
        "mem_usage_mb": round(mem_usage / (1024 * 1024), 2),
        "mem_limit_mb": round(mem_limit / (1024 * 1024), 2),
        "mem_percent": round(mem_pct, 2),
        "pids": s.get("pids_stats", {}).get("current"),
    }
    return json.dumps(summary, indent=2)


@tool
def docker_ps() -> str:
    """Lista todos los contenedores (corriendo y detenidos) con su estado
    básico. Útil para ver el panorama general o detectar contenedores
    relacionados al que falló."""
    client = _get_docker()
    if client is None:
        return _unavailable("docker_ps")

    try:
        containers = client.containers.list(all=True)
    except Exception as e:
        return f"Error listando contenedores: {e}"

    rows = []
    for c in containers:
        rows.append({
            "name": c.name,
            "id_short": c.id[:12],
            "status": c.status,
            "image": c.attrs.get("Config", {}).get("Image"),
        })
    return json.dumps(rows, indent=2)


def all_tools() -> list:
    """Lista de tools que el DockerAgent expone al LLM."""
    return [docker_inspect, docker_logs, docker_stats, docker_ps]
