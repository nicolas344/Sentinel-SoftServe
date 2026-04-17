"""
Registro global de agentes de dominio.

Cada dominio llama register_agent(MyAgent()) al importarse. El Supervisor
consulta el registro para decidir a quién enrutar la alerta.
"""

import logging
from typing import Optional

from services.agents.base import DomainAgent, IncidentContext

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, DomainAgent] = {}


def register_agent(agent: DomainAgent) -> None:
    """Registra un agente. Idempotente: re-registrar sobreescribe."""
    if not agent.name:
        raise ValueError("DomainAgent.name no puede estar vacío.")
    _REGISTRY[agent.name] = agent
    logger.info(f"Agente registrado: '{agent.name}'")


def get_agent(name: str) -> Optional[DomainAgent]:
    return _REGISTRY.get(name)


def list_agents() -> list[DomainAgent]:
    return list(_REGISTRY.values())


def find_agent_for(ctx: IncidentContext) -> Optional[DomainAgent]:
    """
    Primer agente cuyo matches() retorne True. El orden es no determinístico;
    si dos agentes pueden manejar la misma alerta, definir prioridad en
    matches() (ej. reglas más específicas primero).
    """
    for agent in _REGISTRY.values():
        try:
            if agent.matches(ctx):
                return agent
        except Exception as e:
            logger.warning(f"matches() falló en agente '{agent.name}': {e}")
    return None
