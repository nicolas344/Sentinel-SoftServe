from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
from db.supabase_client import supabase
from models.incident import IncidentStatusUpdate, ManualIncidentCreate

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("/")
async def list_incidents(
    user=Depends(get_current_user),
    status: Optional[str] = None,
):
    query = supabase.table("incidents").select("*")
    if status is not None:
        query = query.eq("status", status)
    response = query.order("created_at", desc=True).execute()
    return response.data


@router.post("/")
async def create_incident_manual(
    body: ManualIncidentCreate,
    user=Depends(get_current_user),
):
    row = {
        "title": body.title,
        "container_name": body.container_name,
        "severity": body.severity,
        "status": "detected",
    }
    response = supabase.table("incidents").insert(row).execute()
    if isinstance(response.data, list) and response.data:
        return response.data[0]
    if isinstance(response.data, dict):
        return response.data
    return row


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
