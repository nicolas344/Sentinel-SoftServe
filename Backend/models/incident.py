from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime


class ManualIncidentCreate(BaseModel):
    """Payload for manually creating an incident from the frontend."""

    title: str
    container_name: str
    severity: Literal["critical", "high", "medium", "low"]


class IncidentCreate(BaseModel):
    title: str
    container_name: str
    exit_code: Optional[str] = None
    severity: str = "medium"
    status: str = "detected"
    logs: Optional[str] = None


class IncidentStatusUpdate(BaseModel):
    status: str


class IncidentResponse(BaseModel):
    id: str
    title: str
    container_name: str
    exit_code: Optional[str] = None
    severity: str
    status: str
    logs: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
