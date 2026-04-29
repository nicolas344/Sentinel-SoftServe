from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

SourceType   = Literal["container", "database", "manual"]
RuntimeType  = Literal["docker", "kubernetes"]
SeverityType = Literal["critical", "high", "medium", "low"]
StatusType   = Literal[
    "detected",
    "investigating",
    "analyzed",
    "awaiting_approval",
    "executing_solution",
    "resolved",
    "failed",
]


class IncidentCreate(BaseModel):
    title:             str
    target:            str
    severity:          SeverityType = "medium"
    status:            StatusType   = "detected"
    source_type:       SourceType   = "container"
    container_runtime: Optional[RuntimeType] = "docker"
    logs:              Optional[str] = None
    server_name:       Optional[str] = None
    metrics_snapshot:  Optional[dict] = None


class IncidentStatusUpdate(BaseModel):
    status: StatusType


class IncidentResponse(BaseModel):
    id:                str
    title:             str
    target:            str
    severity:          str
    status:            str
    source_type:       str = "container"
    container_runtime: Optional[str] = "docker"
    logs:              Optional[str] = None
    server_name:       Optional[str] = None
    incident_type:     Optional[str] = None
    agent_reasoning:   Optional[str] = None
    proposed_action:   Optional[str] = None
    action_result:     Optional[str] = None
    action_error:      Optional[str] = None
    executed_at:       Optional[datetime] = None
    resolved_at:       Optional[datetime] = None
    metrics_snapshot:  Optional[dict] = None
    created_at:        datetime
    updated_at:        Optional[datetime] = None
