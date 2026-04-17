"""
Contrato que deben cumplir todos los agentes de dominio.

Un DomainAgent es auto-contenido: sabe si una alerta le corresponde, qué
tools puede ejecutar, qué colecciones de memoria consulta y cómo investiga.
El Supervisor no conoce los detalles — solo invoca esta interfaz.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class IncidentContext:
    """
    Todo lo que un agente recibe para razonar sobre un incidente.
    Se construye una sola vez (en run_investigation) y se pasa inmutable.
    """
    incident_id: str
    title: str
    target: str                     # container_name, db_instance, etc.
    severity: str
    logs: str
    incident_type: Optional[str] = None
    labels: dict = field(default_factory=dict)


@dataclass
class ToolCall:
    """Registro de una invocación de tool — se persiste en Supabase."""
    name: str
    args: dict
    result_preview: str             # primeros ~500 chars del resultado


@dataclass
class InvestigationResult:
    """Lo que devuelve un agente tras investigar."""
    analysis: str                   # markdown con el razonamiento final
    tool_calls: list[ToolCall] = field(default_factory=list)
    similar_past_incidents: list[dict] = field(default_factory=list)


class DomainAgent(ABC):
    """
    Clase base de los agentes especializados.

    Subclases a implementar:
      - name:        identificador único ("docker", "postgres", ...)
      - matches():   ¿esta alerta me corresponde?
      - tools():     tools disponibles para mi LLM
      - system_prompt(): texto que define mi rol
      - investigate(): loop de razonamiento + tools
    """

    # Identidad
    name: str = ""

    # Colecciones de ChromaDB (convención: <tipo>-<dominio>)
    @property
    def runbooks_collection(self) -> str:
        return f"runbooks-{self.name}"

    @property
    def incidents_collection(self) -> str:
        return f"incidents-{self.name}"

    # ── Interfaz obligatoria ──────────────────────────────────────────────────

    @abstractmethod
    def matches(self, ctx: IncidentContext) -> bool:
        """¿Este agente es el adecuado para esta alerta?"""

    @abstractmethod
    def tools(self) -> list[Callable]:
        """Funciones decoradas con @tool de langchain que el LLM puede invocar."""

    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt que define el rol y restricciones del agente."""

    @abstractmethod
    def investigate(self, ctx: IncidentContext) -> InvestigationResult:
        """
        Loop principal del agente. Debe:
          1. Consultar runbooks (self.recall_runbooks)
          2. Consultar incidentes similares (self.recall_similar_incidents)
          3. Razonar / invocar tools según convenga
          4. Devolver InvestigationResult con análisis final
        """

    # ── Ayudas que todos los agentes comparten ────────────────────────────────

    def recall_runbooks(self, query: str, k: int = 3) -> list[str]:
        """Devuelve los k runbooks más relevantes para esta query."""
        from services.agents.memory.runbooks import query_runbooks
        return query_runbooks(self.runbooks_collection, query, k=k)

    def recall_similar_incidents(self, query: str, k: int = 3) -> list[dict]:
        """
        Devuelve los k incidentes pasados más parecidos con su metadata
        (incident_id, outcome, resolved_at, tools_used, summary).
        """
        from services.agents.memory.incidents import query_incidents
        return query_incidents(self.incidents_collection, query, k=k)

    def remember_incident(self, ctx: IncidentContext, result: InvestigationResult) -> None:
        """Persiste este incidente en la memoria episódica del dominio."""
        from services.agents.memory.incidents import store_incident
        store_incident(self.incidents_collection, ctx, result)
