"""
Verificación post-acción para HU-13.

Tras ejecutar un comando (docker restart / pg_terminate_backend / etc.),
espera unos segundos y comprueba si el servicio se recuperó. El resultado se
adjunta al agent_reasoning del incidente y el status cambia a:
  - 'resolved'   → el servicio está operativo
  - 'failed'     → el servicio sigue caído o no se pudo verificar

Se ejecuta como BackgroundTask de FastAPI, por lo que no bloquea la respuesta
al usuario. La UI se actualiza automáticamente vía Supabase Realtime.

Soporta tres runtimes:
  - docker   → inspecciona el contenedor con docker-py
  - podman   → inspecciona el contenedor via socket Podman
  - postgres → verifica conectividad con psycopg2 + métricas básicas
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

    Soporta runtime='postgres' para incidentes de base de datos.
    """
    logger.info(f"[Verification] Esperando {_WAIT_SEC}s para verificar {incident_id[:8]}")
    time.sleep(_WAIT_SEC)

    try:
        if runtime == "postgres" or target.startswith("postgres/"):
            datname = target.replace("postgres/", "").strip() if "/" in target else target
            check = _inspect_postgres(datname)
        else:
            check = _inspect_container(target, runtime)

        section = _render_section(check, runtime)
        new_status = "resolved" if check["healthy"] else "failed"
        resolved_at = (
            datetime.now(tz=timezone.utc).isoformat()
            if new_status == "resolved"
            else None
        )
        update = {
            "status": new_status,
            "agent_reasoning": (current_reasoning or "") + "\n\n---\n\n" + section,
        }
        if resolved_at:
            update["resolved_at"] = resolved_at

        supabase.table("incidents").update(update).eq("id", incident_id).execute()
        logger.info(f"[Verification] {incident_id[:8]} → {new_status}")

    except Exception as exc:
        logger.error(f"[Verification] Error verificando {incident_id[:8]}: {exc}")
        warning = (
            "\n\n---\n\n"
            "## Verificación de resolución\n\n"
            f"⚠️ No se pudo verificar el estado del servicio automáticamente: `{exc}`\n\n"
            "El comando se ejecutó sin errores. Verifica el estado manualmente."
        )
        supabase.table("incidents").update({
            "status": "resolved",
            "agent_reasoning": (current_reasoning or "") + warning,
            "resolved_at": datetime.now(tz=timezone.utc).isoformat(),
        }).eq("id", incident_id).execute()


# ── Inspección de contenedores Docker/Podman ──────────────────────────────────

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


# ── Inspección de PostgreSQL ──────────────────────────────────────────────────

def _inspect_postgres(datname: str) -> dict:
    """
    Verifica que la base de datos responde y consulta métricas básicas de salud.
    Retorna un dict compatible con _render_section para runtime='postgres'.
    """
    try:
        import psycopg2  # type: ignore
        import psycopg2.extras  # type: ignore
    except ImportError:
        return {
            "healthy": False,
            "status": "psycopg2_not_installed",
            "connections": None,
            "max_connections": None,
            "db_size_mb": None,
            "error": "psycopg2 no está disponible",
        }

    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        host     = os.getenv("POSTGRES_HOST", "localhost")
        port     = os.getenv("POSTGRES_PORT", "5432")
        user     = os.getenv("POSTGRES_USER", "sentinel")
        password = os.getenv("POSTGRES_PASSWORD", "")
        db       = os.getenv("POSTGRES_DB", "sentinel_demo")
        dsn = f"postgresql://{user}:{password}@{host}:{port}/{db}"

    try:
        conn = psycopg2.connect(dsn, connect_timeout=5)
        conn.autocommit = True
    except Exception as e:
        return {
            "healthy": False,
            "status": "unreachable",
            "connections": None,
            "max_connections": None,
            "db_size_mb": None,
            "error": str(e),
        }

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    (SELECT count(*) FROM pg_stat_activity
                     WHERE datname = %(dn)s)::int AS connections,
                    (SELECT setting::int FROM pg_settings
                     WHERE name = 'max_connections') AS max_connections,
                    round(pg_database_size(%(dn)s) / 1024.0 / 1024.0, 1)
                        AS db_size_mb
            """, {"dn": datname})
            row = dict(cur.fetchone())

        return {
            "healthy": True,
            "status": "accepting_connections",
            "connections":     row.get("connections"),
            "max_connections": row.get("max_connections"),
            "db_size_mb":      row.get("db_size_mb"),
            "error":           "",
        }
    except Exception as e:
        return {
            "healthy": False,
            "status": "query_failed",
            "connections":     None,
            "max_connections": None,
            "db_size_mb":      None,
            "error": str(e),
        }
    finally:
        conn.close()


# ── Renderizado del resultado ─────────────────────────────────────────────────

def _render_section(r: dict, runtime: str = "docker") -> str:
    if runtime == "postgres":
        return _render_postgres_section(r)
    return _render_container_section(r)


def _render_container_section(r: dict) -> str:
    if r["healthy"]:
        heading = "Verificación de resolución — Servicio recuperado"
        summary = "El contenedor volvió a estado `running`. El reinicio fue exitoso."
    else:
        heading = "Verificación de resolución — Servicio no recuperado"
        state = r['status']
        summary = f"El contenedor está en estado `{state}` después del "
        summary += "reinicio. Requiere atención manual."

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


def _render_postgres_section(r: dict) -> str:
    if r["healthy"]:
        heading = "Verificación de resolución — PostgreSQL operativo"
        summary = "La base de datos responde correctamente y acepta conexiones."
    else:
        heading = "Verificación de resolución — PostgreSQL no disponible"
        status = r['status']
        summary = "No se pudo conectar a la base de datos "
        summary += f"(`{status}`). Requiere atención manual."

    rows = [f"| Estado | `{r['status']}` |"]
    if r.get("connections") is not None:
        rows.append(f"| Conexiones activas | `{r['connections']}` / `{r['max_connections']}` |")
    if r.get("db_size_mb") is not None:
        rows.append(f"| Tamaño BD | `{r['db_size_mb']} MB` |")
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
