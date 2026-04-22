from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user
from db.supabase_client import supabase
from models.incident import IncidentStatusUpdate
from services.langgraph_engine import run_langgraph_engine

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("/")
async def list_incidents(
    source_type:       Optional[str] = None,
    container_runtime: Optional[str] = None,
    severity:          Optional[str] = None,
    status:            Optional[str] = None,
    user=Depends(get_current_user),
):
    q = supabase.table("incidents").select("*")
    if source_type:
        q = q.eq("source_type", source_type)
    if container_runtime:
        q = q.eq("container_runtime", container_runtime)
    if severity:
        q = q.eq("severity", severity)
    if status:
        q = q.eq("status", status)
    return q.order("created_at", desc=True).execute().data


@router.get("/{incident_id}")
async def get_incident(incident_id: str, user=Depends(get_current_user)):
    response = (
        supabase.table("incidents")
        .select("*")
        .eq("id", incident_id)
        .single()
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    return response.data


@router.patch("/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    body: IncidentStatusUpdate,
    user=Depends(get_current_user),
):
    response = (
        supabase.table("incidents")
        .update({"status": body.status})
        .eq("id", incident_id)
        .execute()
    )
    return response.data


class CreateIncidentManual(BaseModel):
    title:       str  = Field(..., min_length=1, max_length=200)
    target:      str  = Field(..., min_length=1, max_length=100)
    severity:    Literal["critical", "high", "medium", "low"]
    source_type: Literal["container", "database", "manual"] = "manual"
    description: Optional[str] = Field(default=None, max_length=5000)


@router.post("/", status_code=201)
async def create_incident(
    body: CreateIncidentManual,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    # container_runtime es None para incidentes de base de datos o manuales
    container_runtime = "docker" if body.source_type == "container" else None

    incident_data = {
        "title":             body.title.strip(),
        "target":            body.target.strip(),
        "severity":          body.severity,
        "status":            "detected",
        "source_type":       body.source_type,
        "container_runtime": container_runtime,
        "incident_type":     "manual",
        "logs":              body.description.strip() if body.description else None,
    }
    response         = supabase.table("incidents").insert(incident_data).execute()
    created_incident = response.data[0]

    background_tasks.add_task(
        run_langgraph_engine,
        incident_id=created_incident["id"],
        container_name=created_incident["target"],
        logs=body.description or "",
        severity=created_incident["severity"],
        title=created_incident["title"],
        labels={"source_type": body.source_type, "container_runtime": container_runtime or ""},
    )

    return created_incident
