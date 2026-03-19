from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from auth import get_current_user
from db.supabase_client import supabase
from services.langgraph_engine import run_langgraph_engine
from models.incident import IncidentStatusUpdate
from typing import Literal

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



class CreateIncidentManual(BaseModel):
    title : str # requiere minimo 1 caracter

    container_name : str # requiere minimo 1 caracter

    severity : Literal["critical", "high", "medium", "low"]




@router.post("/", status_code=201)
async def create_incident(
    body: CreateIncidentManual, 
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user)
):
    incident_data ={
        "title" : body.title.strip(),
        "container_name" : body.container_name.strip(),
        "severity" : body.severity,
        "status" : "detected",
        "incident_type" : "manual",

    }
    response = supabase.table("incidents").insert(incident_data).execute()
    created_incident = response.data[0]
    
    # Trigger AI investigation in the background
    background_tasks.add_task(
        run_langgraph_engine,
        incident_id=created_incident["id"],
        container_name=created_incident["container_name"],
        logs="",  # Manual incidents don't have upfront logs yet
        severity=created_incident["severity"],
        title=created_incident["title"],
    )
    
    return created_incident





    



