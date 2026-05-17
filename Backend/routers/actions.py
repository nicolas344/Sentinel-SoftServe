import json
import logging
import os
import re
import shlex
import subprocess
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user
from db.supabase_client import supabase
from services.incident_events import record_event
from services.verification import verify_resolution

router = APIRouter(prefix="/api", tags=["actions"])

logger = logging.getLogger(__name__)

_CONTAINER_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
_PG_DATNAME_RE     = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$")

_PG_ALLOWED_FUNCS    = {"pg_stat_activity", "pg_cancel_backend", "pg_terminate_backend"}
_PODMAN_ALLOWED_CMDS = {"restart", "logs"}


class ExecuteActionRequest(BaseModel):
    incident_id: str = Field(..., min_length=1)
    command: str = Field(..., min_length=1, max_length=200)


class ExecuteActionResponse(BaseModel):
    incident_id: str
    status: str
    exit_code: int
    stdout: str
    stderr: str
    friendly_message: Optional[str] = None


# ── Validadores ───────────────────────────────────────────────────────────────

def _validate_container_command(command: str) -> list[str]:
    """
    Acepta unicamente:
      - docker restart <container>
      - docker logs <container>
      - podman restart <container>
      - podman logs <container>
    """
    try:
        tokens = shlex.split(command.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Comando invalido: {exc}")

    if len(tokens) != 3:
        raise HTTPException(status_code=400, detail="Formato de comando no permitido")

    runtime_bin, subcommand, container = tokens

    if runtime_bin not in {"docker", "podman"}:
        raise HTTPException(status_code=400, detail="Comando no permitido")

    allowed_cmds = {"restart", "logs"}
    if subcommand not in allowed_cmds:
        raise HTTPException(status_code=400, detail=f"Subcomando '{subcommand}' no permitido")

    if not _CONTAINER_NAME_RE.match(container):
        raise HTTPException(status_code=400, detail="Nombre de contenedor invalido")

    return tokens


def _validate_pg_command(command: str) -> tuple[str, str]:
    """
    Acepta unicamente:
      - pg_stat_activity <datname>      (solo lectura — observación)
      - pg_cancel_backend <datname>     (cancela query activa, conexión sigue viva)
      - pg_terminate_backend <datname>  (termina todas las conexiones de la BD)
    Retorna (funcion, datname).
    """
    tokens = command.strip().split()
    if len(tokens) != 2:
        raise HTTPException(status_code=400, detail="Formato de comando Postgres no permitido")

    func, datname = tokens
    if func not in _PG_ALLOWED_FUNCS:
        raise HTTPException(status_code=400, detail=f"Función Postgres no permitida: '{func}'")
    if not _PG_DATNAME_RE.match(datname):
        raise HTTPException(status_code=400, detail="Nombre de base de datos inválido")

    return func, datname


# ── Ejecutores ────────────────────────────────────────────────────────────────

def _run_podman_command(subcommand: str, container_name: str) -> tuple[int, str, str]:
    """
    Ejecuta restart o logs sobre un contenedor Podman usando el Docker SDK
    apuntando al socket rootless de Podman (PODMAN_HOST).
    No requiere el binario 'podman' en el sistema.
    """
    podman_host = os.getenv("PODMAN_HOST", "unix:///run/podman/podman.sock")
    try:
        import docker  # type: ignore
        client = docker.DockerClient(base_url=podman_host, timeout=15)
    except Exception as e:
        return 1, "", f"No se pudo inicializar cliente Podman: {e}"

    try:
        container = client.containers.get(container_name)
    except docker.errors.NotFound:
        return 1, "", f"Contenedor '{container_name}' no encontrado en Podman"
    except Exception as e:
        return 1, "", f"Error al obtener contenedor '{container_name}': {e}"

    try:
        if subcommand == "restart":
            container.restart(timeout=10)
            return 0, f"Contenedor '{container_name}' reiniciado correctamente", ""
        elif subcommand == "logs":
            raw = container.logs(tail=100, timestamps=True)
            return 0, raw.decode("utf-8", errors="replace"), ""
        else:
            return 1, "", f"Subcomando Podman no soportado: '{subcommand}'"
    except Exception as e:
        return 1, "", f"Error ejecutando podman {subcommand} {container_name}: {e}"
    finally:
        client.close()


def _run_pg_command(func: str, datname: str) -> tuple[int, str, str]:
    """
    Ejecuta la función Postgres segura contra la BD indicada.
    Retorna (exit_code, stdout_json, stderr).
    - pg_stat_activity     → SELECT de pg_stat_activity (lectura)
    - pg_cancel_backend    → pg_cancel_backend() sobre queries activas
    - pg_terminate_backend → pg_terminate_backend() sobre todas las conexiones
    """
    try:
        import psycopg2  # type: ignore
        import psycopg2.extras  # type: ignore
    except ImportError:
        return 1, "", "psycopg2 no está instalado en el backend"

    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        host     = os.getenv("POSTGRES_HOST", "localhost")
        port     = os.getenv("POSTGRES_PORT", "5432")
        user     = os.getenv("POSTGRES_USER", "sentinel")
        password = os.getenv("POSTGRES_PASSWORD", "")
        db       = os.getenv("POSTGRES_DB", "sentinel_demo")
        dsn = f"postgresql://{user}:{password}@{host}:{port}/{db}"

    try:
        conn = psycopg2.connect(dsn, connect_timeout=10)
        conn.autocommit = True
    except Exception as e:
        return 1, "", f"No se pudo conectar a PostgreSQL: {e}"

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if func == "pg_stat_activity":
                cur.execute("""
                    SELECT pid, usename, state, wait_event_type, wait_event,
                           EXTRACT(EPOCH FROM (now() - query_start))::int AS duracion_s,
                           LEFT(query, 200) AS query
                    FROM pg_stat_activity
                    WHERE datname = %s AND pid <> pg_backend_pid()
                    ORDER BY duracion_s DESC NULLS LAST
                    LIMIT 20
                """, (datname,))
                rows = [dict(r) for r in cur.fetchall()]
                stdout = json.dumps({"datname": datname, "conexiones": rows}, indent=2, default=str)

            elif func == "pg_cancel_backend":
                cur.execute("""
                    SELECT pid, pg_cancel_backend(pid) AS cancelado,
                           LEFT(query, 100) AS query
                    FROM pg_stat_activity
                    WHERE datname = %s
                      AND state = 'active'
                      AND pid <> pg_backend_pid()
                """, (datname,))
                rows = [dict(r) for r in cur.fetchall()]
                stdout = json.dumps({
                    "datname": datname,
                    "queries_canceladas": len([r for r in rows if r.get("cancelado")]),
                    "detalle": rows,
                }, indent=2, default=str)

            elif func == "pg_terminate_backend":
                cur.execute("""
                    SELECT pid, pg_terminate_backend(pid) AS terminado,
                           usename, state, LEFT(query, 100) AS query
                    FROM pg_stat_activity
                    WHERE datname = %s AND pid <> pg_backend_pid()
                """, (datname,))
                rows = [dict(r) for r in cur.fetchall()]
                stdout = json.dumps({
                    "datname": datname,
                    "conexiones_terminadas": len([r for r in rows if r.get("terminado")]),
                    "detalle": rows,
                }, indent=2, default=str)

            else:
                stdout = ""

        return 0, stdout, ""

    except Exception as e:
        return 1, "", f"Error ejecutando {func}: {e}"
    finally:
        conn.close()


# ── Endpoint principal ────────────────────────────────────────────────────────

@router.post("/execute-action", response_model=ExecuteActionResponse)
async def execute_action(
    body: ExecuteActionRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    incident_response = (
        supabase.table("incidents")
        .select("id,status,proposed_action,target,source_type,agent_reasoning,container_runtime")
        .eq("id", body.incident_id)
        .single()
        .execute()
    )

    incident = incident_response.data
    if not incident:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    if incident.get("status") != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail="El incidente no esta en estado 'Esperando aprobacion'",
        )

    proposed_action = (incident.get("proposed_action") or "").strip()
    requested_command = body.command.strip()

    if not proposed_action:
        raise HTTPException(status_code=400, detail="El incidente no tiene accion propuesta")

    if requested_command != proposed_action:
        raise HTTPException(
            status_code=400,
            detail="El comando no coincide con la accion propuesta del incidente",
        )

    source_type = (incident.get("source_type") or "container").lower()
    is_postgres  = requested_command.split()[0] in _PG_ALLOWED_FUNCS or source_type == "database"

    supabase.table("incidents").update({"status": "executing_solution"}).eq("id", body.incident_id).execute()
    record_event(body.incident_id, "executing_solution")
    executed_at = datetime.now(tz=timezone.utc).isoformat()

    # ── Rama Postgres ─────────────────────────────────────────────────────────
    if is_postgres:
        func, datname = _validate_pg_command(requested_command)
        logger.info(f"[actions] Ejecutando Postgres: {func}({datname})")
        exit_code, stdout, stderr = _run_pg_command(func, datname)

        if exit_code == 0:
            supabase.table("incidents").update({
                "status": "verifying",
                "action_result": stdout,
                "action_error": stderr or None,
                "executed_at": executed_at,
            }).eq("id", body.incident_id).execute()
            record_event(body.incident_id, "verifying")

            current_reasoning = (incident.get("agent_reasoning") or "").strip()
            background_tasks.add_task(
                verify_resolution,
                body.incident_id,
                incident.get("target", f"postgres/{datname}"),
                "postgres",
                current_reasoning,
            )

            return ExecuteActionResponse(
                incident_id=body.incident_id,
                status="verifying",
                exit_code=0,
                stdout=stdout,
                stderr=stderr,
            )

        supabase.table("incidents").update({
            "status": "failed",
            "action_result": stdout,
            "action_error": stderr,
            "executed_at": executed_at,
        }).eq("id", body.incident_id).execute()
        record_event(body.incident_id, "failed")

        return ExecuteActionResponse(
            incident_id=body.incident_id,
            status="failed",
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            friendly_message="La ejecución Postgres falló. Revisa los logs del backend.",
        )

    # ── Rama Docker / Podman ─────────────────────────────────────────────────
    command_tokens = _validate_container_command(requested_command)
    runtime_bin, subcommand, container_name = command_tokens

    if runtime_bin == "podman":
        # Podman: usar Docker SDK apuntando al socket rootless (no hay binario podman en el backend)
        logger.info(f"[actions] Ejecutando via SDK Podman: {subcommand} {container_name}")
        exit_code, stdout, stderr = _run_podman_command(subcommand, container_name)
    else:
        # Docker: subprocess normal
        try:
            completed = subprocess.run(
                command_tokens,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except FileNotFoundError:
            stderr = "El runtime no tiene disponible el binario 'docker'"
            supabase.table("incidents").update({
                "status": "failed",
                "action_result": "",
                "action_error": stderr,
                "executed_at": executed_at,
            }).eq("id", body.incident_id).execute()

            return ExecuteActionResponse(
                incident_id=body.incident_id,
                status="failed",
                exit_code=127,
                stdout="",
                stderr=stderr,
                friendly_message="La ejecución automática falló. Se recomienda revisión manual.",
            )
        except subprocess.TimeoutExpired as exc:
            stderr = (exc.stderr or "").strip() or "Timeout al ejecutar el comando"
            stdout = (exc.stdout or "").strip()
            supabase.table("incidents").update({
                "status": "failed",
                "action_result": stdout,
                "action_error": stderr,
                "executed_at": executed_at,
            }).eq("id", body.incident_id).execute()

            return ExecuteActionResponse(
                incident_id=body.incident_id,
                status="failed",
                exit_code=124,
                stdout=stdout,
                stderr=stderr,
                friendly_message="La ejecución automática falló. Se recomienda revisión manual.",
            )

        exit_code = completed.returncode
        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()

    if exit_code == 0:
        supabase.table("incidents").update({
            "status": "verifying",
            "action_result": stdout,
            "action_error": stderr,
            "executed_at": executed_at,
        }).eq("id", body.incident_id).execute()
        record_event(body.incident_id, "verifying")

        current_reasoning = (incident.get("agent_reasoning") or "").strip()
        container_runtime = command_tokens[0]  # "docker" o "podman"
        background_tasks.add_task(
            verify_resolution,
            body.incident_id,
            incident["target"] if "target" in incident else command_tokens[2],
            container_runtime,
            current_reasoning,
        )

        return ExecuteActionResponse(
            incident_id=body.incident_id,
            status="verifying",
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    # Comando fallido → failed inmediato
    supabase.table("incidents").update({
        "status": "failed",
        "action_result": stdout,
        "action_error": stderr,
        "executed_at": executed_at,
    }).eq("id", body.incident_id).execute()
    record_event(body.incident_id, "failed")

    return ExecuteActionResponse(
        incident_id=body.incident_id,
        status="failed",
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        friendly_message="La ejecución automática falló. Se recomienda revisión manual.",
    )


class ActionDecisionRequest(BaseModel):
    comment: str = Field(default="", max_length=500)


def _get_awaiting_incident(incident_id: str):
    response = (
        supabase.table("incidents")
        .select("id,status")
        .eq("id", incident_id)
        .single()
        .execute()
    )
    incident = response.data
    if not incident:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    if incident.get("status") != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail="El incidente no está en estado 'Esperando aprobación'",
        )
    return incident


@router.post("/incidents/{incident_id}/reject")
async def reject_action(
    incident_id: str,
    body: ActionDecisionRequest,
    user=Depends(get_current_user),
):
    _get_awaiting_incident(incident_id)
    note = body.comment.strip() or "Acción rechazada por el ingeniero."
    supabase.table("incidents").update({
        "status": "failed",
        "action_error": f"[RECHAZADO] {note}",
        "executed_at": datetime.now(tz=timezone.utc).isoformat(),
    }).eq("id", incident_id).execute()
    record_event(incident_id, "failed")
    return {"incident_id": incident_id, "status": "failed", "note": note}


@router.post("/incidents/{incident_id}/postpone")
async def postpone_action(
    incident_id: str,
    body: ActionDecisionRequest,
    user=Depends(get_current_user),
):
    _get_awaiting_incident(incident_id)
    note = body.comment.strip() or "Acción pospuesta por el ingeniero."
    supabase.table("incidents").update({
        "status": "analyzed",
        "action_error": f"[POSPUESTO] {note}",
    }).eq("id", incident_id).execute()
    record_event(incident_id, "analyzed")
    return {"incident_id": incident_id, "status": "analyzed", "note": note}
