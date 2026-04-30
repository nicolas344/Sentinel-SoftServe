"""
Tools del PodmanAgent.

Todas son read-only: consultan el estado del daemon Podman sin modificar nada.
Usan el Docker SDK apuntado al socket de Podman (API compatible).
Si Podman no está accesible, devuelven un mensaje descriptivo para que el
agente continúe razonando con los logs que ya tiene en contexto.

Variables de entorno:
  PODMAN_HOST — socket de Podman, ej: unix:///run/user/1000/podman/podman.sock
                Si no se define, intenta el socket estándar de Podman rootless.
"""

import json
import logging
import os
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_PODMAN_CLIENT = None
_PODMAN_CLIENT_ERROR: Optional[str] = None

_DEFAULT_SOCKETS = [
    "unix:///run/user/1000/podman/podman.sock",
    "unix:///run/user/501/podman/podman.sock",   # macOS podman machine
    "unix:///tmp/podman.sock",
]


def _get_podman():
    global _PODMAN_CLIENT, _PODMAN_CLIENT_ERROR
    if _PODMAN_CLIENT is not None or _PODMAN_CLIENT_ERROR is not None:
        return _PODMAN_CLIENT

    try:
        import docker  # type: ignore

        socket = os.getenv("PODMAN_HOST") or os.getenv("DOCKER_HOST")
        candidates = [socket] if socket else _DEFAULT_SOCKETS

        for url in candidates:
            try:
                client = docker.DockerClient(base_url=url)
                client.ping()
                _PODMAN_CLIENT = client
                logger.info(f"[podman.tools] Conectado a Podman en {url}")
                return _PODMAN_CLIENT
            except Exception:
                continue

        raise RuntimeError("No se encontró ningún socket de Podman accesible.")
    except Exception as e:
        _PODMAN_CLIENT_ERROR = str(e)
        logger.warning(f"[podman.tools] Podman no disponible: {e}")
    return None


def _unavailable(tool_name: str) -> str:
    return (
        f"Tool '{tool_name}' no disponible: el backend no puede acceder al "
        f"daemon Podman ({_PODMAN_CLIENT_ERROR or 'socket no montado'}). "
        f"Razona con los logs que ya tienes en contexto."
    )


def _find_container(client, name_or_id: str):
    try:
        return client.containers.get(name_or_id)
    except Exception:
        pass
    for c in client.containers.list(all=True):
        if c.name == name_or_id or c.id.startswith(name_or_id):
            return c
    return None


@tool
def podman_inspect(container_name: str) -> str:
    """Inspecciona un contenedor Podman: estado actual, configuración de recursos
    (memoria, CPU), restart policy, exit code y tiempo de parada. Úsalo para
    confirmar si el contenedor sigue caído y cuáles eran sus límites."""
    client = _get_podman()
    if client is None:
        return _unavailable("podman_inspect")
    try:
        c = _find_container(client, container_name)
        if c is None:
            return f"Contenedor '{container_name}' no encontrado en Podman."
        c.reload()
        attrs = c.attrs or {}
        state = attrs.get("State", {})
        host_cfg = attrs.get("HostConfig", {})
        return json.dumps({
            "name":          c.name,
            "status":        c.status,
            "exit_code":     state.get("ExitCode"),
            "error":         state.get("Error") or "",
            "started_at":    state.get("StartedAt", "")[:19],
            "finished_at":   state.get("FinishedAt", "")[:19],
            "oom_killed":    state.get("OOMKilled", False),
            "restart_count": attrs.get("RestartCount", 0),
            "mem_limit_mb":  round((host_cfg.get("Memory") or 0) / 1024 / 1024, 1),
            "cpu_quota":     host_cfg.get("CpuQuota", 0),
            "image":         attrs.get("Config", {}).get("Image", ""),
        }, indent=2)
    except Exception as e:
        return f"Error inspeccionando '{container_name}': {e}"


@tool
def podman_logs(container_name: str, tail: int = 80) -> str:
    """Obtiene las últimas líneas de logs de un contenedor Podman (incluyendo
    contenedores detenidos). Úsalo para ver el mensaje de error justo antes
    de que el proceso muriera."""
    client = _get_podman()
    if client is None:
        return _unavailable("podman_logs")
    try:
        c = _find_container(client, container_name)
        if c is None:
            return f"Contenedor '{container_name}' no encontrado en Podman."
        raw = c.logs(tail=tail, timestamps=True, stdout=True, stderr=True)
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return "".join(
            chunk.decode("utf-8", errors="replace") if isinstance(chunk, bytes) else chunk
            for chunk in raw
        )
    except Exception as e:
        return f"Error obteniendo logs de '{container_name}': {e}"


@tool
def podman_stats(container_name: str) -> str:
    """Obtiene el uso actual de CPU y memoria del contenedor Podman. Solo
    disponible si el contenedor está corriendo. Úsalo para detectar memory
    leaks o consumo anormal de CPU en tiempo real."""
    client = _get_podman()
    if client is None:
        return _unavailable("podman_stats")
    try:
        c = _find_container(client, container_name)
        if c is None:
            return f"Contenedor '{container_name}' no encontrado en Podman."
        if c.status != "running":
            return f"El contenedor '{container_name}' está {c.status} — stats no disponibles."
        stats = c.stats(stream=False)
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                    stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"].get("system_cpu_usage", 0) - \
                       stats["precpu_stats"].get("system_cpu_usage", 0)
        num_cpus = stats["cpu_stats"].get("online_cpus") or \
                   len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage") or [1])
        cpu_pct = (cpu_delta / system_delta) * num_cpus * 100 if system_delta > 0 else 0

        mem = stats["memory_stats"]
        mem_used_mb = round(mem.get("usage", 0) / 1024 / 1024, 1)
        mem_limit_mb = round(mem.get("limit", 0) / 1024 / 1024, 1)
        mem_pct = round(mem_used_mb / mem_limit_mb * 100, 1) if mem_limit_mb > 0 else 0

        return json.dumps({
            "container": container_name,
            "cpu_percent": round(cpu_pct, 2),
            "mem_used_mb": mem_used_mb,
            "mem_limit_mb": mem_limit_mb,
            "mem_percent": mem_pct,
        }, indent=2)
    except Exception as e:
        return f"Error obteniendo stats de '{container_name}': {e}"


@tool
def podman_ps() -> str:
    """Lista todos los contenedores Podman (corriendo y detenidos) con su estado,
    imagen, tiempo de creación y puertos. Úsalo para ver qué contenedores hay
    en el host y si alguno está en estado de error o reinicios continuos."""
    client = _get_podman()
    if client is None:
        return _unavailable("podman_ps")
    try:
        containers = client.containers.list(all=True)
        result = []
        for c in containers:
            result.append({
                "name":    c.name,
                "id":      c.short_id,
                "status":  c.status,
                "image":   c.image.tags[0] if c.image.tags else c.image.short_id,
            })
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error listando contenedores Podman: {e}"


def all_tools() -> list:
    return [podman_inspect, podman_logs, podman_stats, podman_ps]
