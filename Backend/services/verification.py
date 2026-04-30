"""
Verificación post-acción para HU-13.

Tras ejecutar un comando (p.ej. docker restart), espera unos segundos y
comprueba si el contenedor volvió a estado 'running'. El resultado se
adjunta al agent_reasoning del incidente y el status cambia a:
  - 'resolved'   → el contenedor está corriendo
  - 'failed'     → el contenedor sigue caído o no se encontró

Se ejecuta como BackgroundTask de FastAPI, por lo que no bloquea la respuesta
al usuario. La UI se actualiza automáticamente vía Supabase Realtime.
"""

import logging
import os
import time
from datetime import datetime, timezone

from db.supabase_client import supabase

logger = logging.getLogger(__name__)

_WAIT_SEC = 8

_PODMAN_SOCKETS = [
    "unix:///run/user/1000/podman/podman.sock",
    "unix:///run/user/501/podman/podman.sock",
    "unix:///tmp/podman.sock",
]


def verify_resolution(
    incident_id: str,
    target: str,
    runtime: str,
    current_reasoning: str,
) -> None:
    """
    Verifica si el contenedor/servicio se recuperó tras la ejecución de la acción.
    Pensado para correr como BackgroundTask.
    """
    logger.info(f"[Verification] Esperando {_WAIT_SEC}s para verificar {incident_id[:8]}")
    time.sleep(_WAIT_SEC)

    try:
        check = _inspect_container(target, runtime)
        section = _render_section(check)
        new_status = "resolved" if check["healthy"] else "failed"
        resolved_at = datetime.now(tz=timezone.utc).isoformat() if new_status == "resolved" else None

        update = {
            "status": new_status,
            "agent_reasoning": (current_reasoning or "") + "\n\n---\n\n" + section,
        }
        if resolved_at:
            update["resolved_at"] = resolved_at

        supabase.table("incidents").update(update).eq("id", incident_id).execute()
        logger.info(f"[Verification] {incident_id[:8]} → {new_status}")

    except Exception as exc:
        logger.error(f"[Verification] Error inspeccionando {incident_id[:8]}: {exc}")
        # El comando ya se ejecutó correctamente; resolvemos con advertencia.
        warning = (
            "\n\n---\n\n"
            "## Verificación de resolución\n\n"
            f"⚠️ No se pudo verificar el estado del contenedor automáticamente: `{exc}`\n\n"
            "El comando se ejecutó sin errores. Verifica el estado manualmente."
        )
        supabase.table("incidents").update({
            "status": "resolved",
            "agent_reasoning": (current_reasoning or "") + warning,
            "resolved_at": datetime.now(tz=timezone.utc).isoformat(),
        }).eq("id", incident_id).execute()


def _inspect_container(target: str, runtime: str) -> dict:
    import docker  # type: ignore

    client = _get_client(runtime)
    try:
        container = client.containers.get(target)
        container.reload()
    except docker.errors.NotFound:
        return {
            "healthy": False,
            "status": "not_found",
            "exit_code": -1,
            "oom_killed": False,
            "started_at": "",
            "health_status": "none",
            "error": f"Contenedor '{target}' no encontrado",
        }

    state = container.attrs.get("State", {})
    health = state.get("Health", {})
    return {
        "healthy": container.status == "running",
        "status": container.status,
        "exit_code": state.get("ExitCode", 0),
        "oom_killed": state.get("OOMKilled", False),
        "started_at": state.get("StartedAt", "")[:19],
        "health_status": health.get("Status", "none"),
        "error": state.get("Error", ""),
    }


def _get_client(runtime: str):
    import docker  # type: ignore

    if runtime == "podman":
        custom = os.getenv("PODMAN_HOST")
        candidates = [custom] if custom else _PODMAN_SOCKETS
        for url in candidates:
            try:
                c = docker.DockerClient(base_url=url)
                c.ping()
                return c
            except Exception:
                continue
        raise RuntimeError("Socket de Podman no accesible")

    return docker.from_env()


def _render_section(r: dict) -> str:
    if r["healthy"]:
        heading = "Verificación de resolución — Servicio recuperado"
        summary = "El contenedor volvió a estado `running`. El reinicio fue exitoso."
    else:
        heading = "Verificación de resolución — Servicio no recuperado"
        summary = f"El contenedor está en estado `{r['status']}` después del reinicio. Requiere atención manual."

    rows = [
        f"| Estado | `{r['status']}` |",
        f"| Exit code | `{r['exit_code']}` |",
        f"| OOM Killed | `{r['oom_killed']}` |",
        f"| Arrancó en | `{r['started_at'] or '—'}` |",
        f"| Health check | `{r['health_status']}` |",
    ]
    if r.get("error"):
        rows.append(f"| Error | `{r['error'][:120]}` |")

    return "\n".join([
        f"## {heading}",
        "",
        summary,
        "",
        "| Campo | Valor |",
        "|-------|-------|",
        *rows,
    ])
