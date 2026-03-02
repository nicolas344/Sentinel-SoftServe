from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from services.alert_processor import process_prometheus_alert

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
async def receive_alertmanager_webhook(webhook: AlertmanagerWebhook):
    """
    Recibe webhooks de Prometheus Alertmanager y crea incidentes en Sentinel.
    """
    for alert in webhook.alerts:
        process_prometheus_alert(alert.model_dump())

    return {"message": "Alertas procesadas", "count": len(webhook.alerts)}
