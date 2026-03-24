from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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
    incident_type: Optional[str] = None
    agent_reasoning: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
