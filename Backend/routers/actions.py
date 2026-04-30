import re
import shlex
import subprocess
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user
from db.supabase_client import supabase

router = APIRouter(prefix="/api", tags=["actions"])

_CONTAINER_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")


class ExecuteActionRequest(BaseModel):
    incident_id: str = Field(..., min_length=1)
    command: str = Field(..., min_length=1, max_length=200)


class ExecuteActionResponse(BaseModel):
    incident_id: str
    status: str
    exit_code: int
    stdout: str
    stderr: str
    friendly_message: str | None = None


def _validate_and_parse_command(command: str) -> list[str]:
    """
    Acepta unicamente:
      - docker restart <container>
      - docker logs <container>
    """
    try:
        tokens = shlex.split(command.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Comando invalido: {exc}")

    if len(tokens) != 3:
        raise HTTPException(status_code=400, detail="Formato de comando no permitido")

    if tokens[0] != "docker" or tokens[1] not in {"restart", "logs"}:
        raise HTTPException(status_code=400, detail="Comando no permitido")

    container = tokens[2]
    if not _CONTAINER_NAME_RE.match(container):
        raise HTTPException(status_code=400, detail="Nombre de contenedor invalido")

    return tokens


@router.post("/execute-action", response_model=ExecuteActionResponse)
async def execute_action(body: ExecuteActionRequest, user=Depends(get_current_user)):
    incident_response = (
        supabase.table("incidents")
        .select("id,status,proposed_action")
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

    command_tokens = _validate_and_parse_command(requested_command)

    supabase.table("incidents").update({"status": "executing_solution"}).eq("id", body.incident_id).execute()

    executed_at = datetime.now(tz=timezone.utc).isoformat()
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

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    status = "resolved" if completed.returncode == 0 else "failed"

    supabase.table("incidents").update({
        "status": status,
        "action_result": stdout,
        "action_error": stderr,
        "executed_at": executed_at,
    }).eq("id", body.incident_id).execute()

    return ExecuteActionResponse(
        incident_id=body.incident_id,
        status=status,
        exit_code=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        friendly_message=(
            None
            if status == "resolved"
            else "La ejecución automática falló. Se recomienda revisión manual."
        ),
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
    return {"incident_id": incident_id, "status": "analyzed", "note": note}
