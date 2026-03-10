from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
from db.supabase_client import supabase
from models.incident import IncidentStatusUpdate

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("/")
async def list_incidents(user=Depends(get_current_user)):
    response = (
        supabase.table("incidents")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return response.data


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
