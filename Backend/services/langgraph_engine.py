"""
Punto de entrada público al motor de triage de Sentinel.

Este módulo mantiene la firma pública `run_langgraph_engine(...)` que usan
los routers (alerts.py, incidents.py) como BackgroundTask. Internamente
delega al nuevo framework multiagente en `services.agents`:

    run_langgraph_engine()  →  Supervisor.run_triage()
                                    ├── clasifica
                                    ├── enruta al DomainAgent correspondiente
                                    ├── invoca tools si hace falta
                                    ├── consulta memoria episódica
                                    └── persiste resultado

Para añadir un nuevo dominio (podman, postgres, ...) basta con crear
`services/agents/<dominio>/agent.py` con un subclass de DomainAgent y
llamar `register_agent()`. Este archivo no necesita cambios.
"""

import logging

# Importar el paquete agents dispara el auto-registro de todos los dominios
# (docker, y en el futuro podman, postgres, etc.) en el Registry.
import services.agents  # noqa: F401
from services.agents.base import IncidentContext
from services.agents.supervisor import run_triage

logger = logging.getLogger(__name__)


def run_langgraph_engine(
    incident_id: str,
    container_name: str,
    logs: str,
    severity: str,
    title: str,
    labels: dict | None = None,
) -> None:
    """
    Lanza el pipeline multiagente para un incidente.
    Diseñado para ejecutarse como BackgroundTask de FastAPI.

    `labels` lleva metadatos de routing, ej: {"container_runtime": "podman"}.
    El Supervisor los pasa al DomainAgent para que matches() funcione.
    """
    ctx = IncidentContext(
        incident_id=incident_id,
        title=title,
        target=container_name,
        severity=severity,
        logs=logs or "",
        labels=labels or {},
    )
    run_triage(ctx)
