import hmac
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel

from services.alert_processor import process_prometheus_alert
from services.langgraph_engine import run_langgraph_engine

router = APIRouter(prefix="/api", tags=["alerts"])

logger = logging.getLogger(__name__)

_webhook_secret_warned = False


def _verify_webhook_secret(authorization: Optional[str]) -> None:
    """
    Valida el secreto compartido del webhook (ALERT_WEBHOOK_SECRET).

    Alertmanager lo envía como 'Authorization: Bearer <secreto>' (ver
    http_config.authorization en alertmanager.yml). Si la variable de entorno
    no está configurada, el endpoint queda abierto (modo desarrollo) y se
    loguea una advertencia una sola vez.
    """
    global _webhook_secret_warned
    secret = os.getenv("ALERT_WEBHOOK_SECRET", "").strip()

    if not secret:
        if not _webhook_secret_warned:
            logger.warning(
                "[alerts] ALERT_WEBHOOK_SECRET no configurado — el webhook "
                "/api/alerts acepta peticiones sin autenticar. No usar así en producción."
            )
            _webhook_secret_warned = True
        return

    provided = ""
    if authorization and authorization.lower().startswith("bearer "):
        provided = authorization[len("Bearer "):]

    if not hmac.compare_digest(provided, secret):
        raise HTTPException(status_code=401, detail="Webhook no autorizado")


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
    authorization: Optional[str] = Header(default=None),
):
    """
    Recibe webhooks de Prometheus Alertmanager y crea incidentes en Sentinel.
    Si la alerta es 'firing', lanza el motor LangGraph en background.
    Requiere 'Authorization: Bearer <ALERT_WEBHOOK_SECRET>' cuando el secreto
    está configurado.
    """
    _verify_webhook_secret(authorization)
    for alert in webhook.alerts:
        result = process_prometheus_alert(alert.model_dump())
        if result:
            incident_id, target, logs, severity, title, container_runtime = result
            labels: dict = {}
            if container_runtime:
                labels["container_runtime"] = container_runtime
            # Propagar source_type para que el supervisor pueda proponer acciones correctas
            source_type = alert.labels.get("source_type", "container")
            labels["source_type"] = source_type
            background_tasks.add_task(
                run_langgraph_engine,
                incident_id,
                target,
                logs,
                severity,
                title,
                labels=labels,
            )

    return {"message": "Alertas procesadas", "count": len(webhook.alerts)}
