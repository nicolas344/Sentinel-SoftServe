from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from services.alert_processor import process_prometheus_alert
from services.langgraph_engine import run_langgraph_engine

router = APIRouter(prefix="/api", tags=["alerts"])


class AlertmanagerAlert(BaseModel):
    status: str
    labels: Dict[str, Any]
    annotations: Dict[str, Any]
    startsAt: str
    endsAt: Optional[str] = None
    generatorURL: Optional[str] = None
    fingerprint: Optional[str] = None


class AlertmanagerWebhook(BaseModel):
    version: Optional[str] = None
    groupKey: Optional[str] = None
    status: str
    receiver: Optional[str] = None
    groupLabels: Optional[Dict[str, Any]] = {}
    commonLabels: Optional[Dict[str, Any]] = {}
    commonAnnotations: Optional[Dict[str, Any]] = {}
    externalURL: Optional[str] = None
    alerts: List[AlertmanagerAlert]


@router.post("/alerts")
async def receive_alertmanager_webhook(
    webhook: AlertmanagerWebhook,
    background_tasks: BackgroundTasks,
):
    """
    Recibe webhooks de Prometheus Alertmanager y crea incidentes en Sentinel.
    Si la alerta es 'firing', lanza el motor LangGraph en background tras crear el incidente.
    """
    for alert in webhook.alerts:
        result = process_prometheus_alert(alert.model_dump())
        if result:
            incident_id, container_name, logs, severity, title = result
            background_tasks.add_task(
                run_langgraph_engine,
                incident_id,
                container_name,
                logs,
                severity,
                title,
            )

    return {"message": "Alertas procesadas", "count": len(webhook.alerts)}
