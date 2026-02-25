import os
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from services.docker_monitor import create_incident_from_event

router = APIRouter(prefix="/api/docker", tags=["docker"])

SENTINEL_AGENT_KEY = os.getenv("SENTINEL_AGENT_KEY")


def verify_agent_key(x_agent_key: Optional[str] = Header(None)):
    if not SENTINEL_AGENT_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SENTINEL_AGENT_KEY no configurada en el servidor",
        )
    if x_agent_key != SENTINEL_AGENT_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida",
        )


class DockerEventPayload(BaseModel):
    Type: str
    Action: str
    Actor: dict
    time: Optional[int] = None
    server_name: Optional[str] = "remote"


@router.post("/events")
async def receive_docker_event(
    event: DockerEventPayload,
    x_agent_key: Optional[str] = Header(None),
):
    """
    Modo pasivo: recibe eventos Docker via webhook desde agentes remotos.
    Requiere header X-Agent-Key para autenticación.
    """
    verify_agent_key(x_agent_key)

    if event.Type == "container" and event.Action in ("die", "oom"):
        create_incident_from_event(event.model_dump())
        return {"message": "Evento procesado", "action": event.Action}

    return {"message": "Evento ignorado", "action": event.Action}
