import math
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user
from db.supabase_client import supabase
from models.incident import IncidentStatusUpdate
from services.agents.memory.incidents import query_incidents
from services.agents.memory.runbooks import query_runbooks
from services.langgraph_engine import run_langgraph_engine
from services.prometheus import get_container_metrics, get_postgres_metrics

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


_TERMINAL_STATUSES = ("resolved", "failed")


@router.get("/")
async def list_incidents(
    source_type:       Optional[str] = None,
    container_runtime: Optional[str] = None,
    severity:          Optional[str] = None,
    status:            Optional[str] = None,
    page:              int = 1,
    limit:             int = 20,
    user=Depends(get_current_user),
):
    q = supabase.table("incidents").select("*", count="exact")
    if source_type:
        q = q.eq("source_type", source_type)
    if container_runtime:
        q = q.eq("container_runtime", container_runtime)
    if severity:
        q = q.eq("severity", severity)
    # "active" is an alias for all non-terminal statuses
    if status == "active":
        q = q.not_.in_("status", list(_TERMINAL_STATUSES))
    elif status:
        q = q.eq("status", status)

    offset = (page - 1) * limit
    response = q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    total = response.count or 0
    return {
        "data":  response.data,
        "total": total,
        "page":  page,
        "limit": limit,
        "pages": math.ceil(total / limit) if total else 0,
    }


@router.get("/{incident_id}")
async def get_incident(incident_id: str, user=Depends(get_current_user)):
    try:
        response = (
            supabase.table("incidents")
            .select("*")
            .eq("id", incident_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
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


def _runbook_collection(source_type: str) -> str:
    return "runbooks-postgres" if source_type == "database" else "runbooks-docker"


def _incidents_collection(source_type: str) -> str:
    return "incidents-postgres" if source_type == "database" else "incidents-docker"


def _parse_runbook_title(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("RUNBOOK:"):
            return line.replace("RUNBOOK:", "").strip()
    return "Runbook"


@router.get("/{incident_id}/runbooks")
async def get_incident_runbooks(
    incident_id: str,
    q: Optional[str] = None,
    user=Depends(get_current_user),
):
    try:
        response = (
            supabase.table("incidents")
            .select("source_type,incident_type,title")
            .eq("id", incident_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    if not response.data:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    incident = response.data
    collection = _runbook_collection(incident.get("source_type") or "container")
    query = q or f"{incident.get('incident_type') or 'unknown'} {incident.get('title') or ''}"

    texts = query_runbooks(collection, query.strip(), k=5)
    return [{"title": _parse_runbook_title(t), "content": t} for t in texts]


@router.get("/{incident_id}/similar")
async def get_similar_incidents(
    incident_id: str,
    user=Depends(get_current_user),
):
    try:
        response = (
            supabase.table("incidents")
            .select("source_type,incident_type,title,severity")
            .eq("id", incident_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    if not response.data:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    incident = response.data
    collection = _incidents_collection(incident.get("source_type") or "container")
    query = f"{incident.get('incident_type') or 'unknown'} {incident.get('title') or ''}"

    results = query_incidents(collection, query.strip(), k=6)
    return [r for r in results if r["id"] != incident_id]


@router.get("/{incident_id}/metrics")
async def get_incident_metrics(incident_id: str, user=Depends(get_current_user)):
    try:
        response = (
            supabase.table("incidents")
            .select("target,source_type,metrics_snapshot")
            .eq("id", incident_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    if not response.data:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    incident    = response.data
    target      = (incident.get("target") or "").strip()
    source_type = (incident.get("source_type") or "container").lower()

    try:
        if source_type == "database":
            datname = target.replace("postgres/", "")
            return get_postgres_metrics(datname)
        return get_container_metrics(target)
    except Exception as exc:
        snapshot = incident.get("metrics_snapshot")
        if snapshot:
            return snapshot
        raise HTTPException(status_code=503, detail=f"Métricas no disponibles: {exc}")
