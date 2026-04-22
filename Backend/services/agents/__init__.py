"""
Framework multiagente de Sentinel.

Cada dominio (docker, kubernetes, postgres, ...) vive en su propia carpeta
y se registra en el Registry. El Supervisor enruta cada incidente al
especialista correcto.

Añadir un nuevo dominio = crear carpeta con agent.py, tools.py, prompt.md
y llamar register_agent() al importarlo. Sin tocar el core.
"""

from services.agents.base import DomainAgent, IncidentContext

# Importa los dominios concretos para que se auto-registren.
# Añadir más dominios aquí cuando existan.
from services.agents.docker import agent as _docker_agent  # noqa: F401
from services.agents.registry import get_agent, list_agents, register_agent

__all__ = [
    "DomainAgent",
    "IncidentContext",
    "register_agent",
    "get_agent",
    "list_agents",
]
