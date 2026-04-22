"""
PostgresAgent — especialista en incidentes de bases de datos PostgreSQL.

Maneja alertas generadas por postgres-exporter: conexiones agotadas,
transacciones largas, deadlocks, lag de replicación, bajo cache hit ratio
y crecimiento acelerado de la BD.

Usa el mismo patrón ReAct acotado que el DockerAgent:
- Consulta runbooks y memoria episódica antes de razonar.
- Puede invocar tools read-only vía psycopg2 para obtener el estado
  actual de la BD si el contexto del incidente no es suficiente.
- El target tiene formato 'postgres/<nombre_db>'.
"""

import logging
import os
from pathlib import Path
from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from services.agents.base import (
    DomainAgent,
    IncidentContext,
    InvestigationResult,
    ToolCall,
)
from services.agents.postgres.tools import all_tools
from services.agents.registry import register_agent

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompt.md"
_MAX_TOOL_ITERATIONS = 4


class PostgresAgent(DomainAgent):
    name = "postgres"

    # ── Contrato de DomainAgent ───────────────────────────────────────────────

    def matches(self, ctx: IncidentContext) -> bool:
        """Este incidente es mío si source_type es 'database' o el target
        comienza con 'postgres/'."""
        source = (ctx.labels.get("source_type") or "").lower()
        if source == "database":
            return True
        return ctx.target.lower().startswith("postgres/")

    def tools(self) -> list[Callable]:
        return all_tools()

    def system_prompt(self) -> str:
        try:
            return _PROMPT_PATH.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"[PostgresAgent] No se pudo leer prompt.md: {e}")
            return "Eres un DBA senior analizando incidentes de PostgreSQL."

    def investigate(self, ctx: IncidentContext) -> InvestigationResult:
        logger.info(f"[PostgresAgent] Investigando incidente {ctx.incident_id[:8]}")

        # 1. Memoria: runbooks + incidentes pasados similares
        query = f"{ctx.incident_type or ''} {ctx.title} {ctx.target}"
        runbooks = self.recall_runbooks(query, k=3)
        past_incidents = self.recall_similar_incidents(query, k=3)

        # 2. Construye el mensaje de usuario con toda la evidencia
        user_msg = _build_user_message(ctx, runbooks, past_incidents)

        # 3. Loop ReAct acotado
        analysis, tool_calls = self._react_loop(user_msg)

        return InvestigationResult(
            analysis=analysis,
            tool_calls=tool_calls,
            similar_past_incidents=past_incidents,
        )

    # ── Interno ───────────────────────────────────────────────────────────────

    def _react_loop(self, user_msg: str) -> tuple[str, list[ToolCall]]:
        tools = self.tools()
        tool_map = {t.name: t for t in tools}

        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY"),
        ).bind_tools(tools)

        messages = [
            SystemMessage(content=self.system_prompt()),
            HumanMessage(content=user_msg),
        ]
        recorded: list[ToolCall] = []

        for i in range(_MAX_TOOL_ITERATIONS + 1):
            response: AIMessage = llm.invoke(messages)
            messages.append(response)

            pending = getattr(response, "tool_calls", None) or []
            if not pending:
                return (response.content or "").strip(), recorded

            if i == _MAX_TOOL_ITERATIONS:
                messages.append(HumanMessage(
                    content="Límite de tool calls alcanzado. Redacta el análisis "
                            "final ahora con la información que tienes."
                ))
                continue

            for call in pending:
                tool_name = call.get("name") if isinstance(call, dict) else call.name
                tool_args = call.get("args", {}) if isinstance(call, dict) else call.args
                tool_id   = call.get("id")   if isinstance(call, dict) else call.id

                tool_fn = tool_map.get(tool_name)
                if tool_fn is None:
                    result = f"Tool '{tool_name}' no existe."
                else:
                    try:
                        result = tool_fn.invoke(tool_args)
                    except Exception as e:
                        result = f"Error ejecutando '{tool_name}': {e}"

                recorded.append(ToolCall(
                    name=tool_name,
                    args=tool_args,
                    result_preview=str(result)[:500],
                ))
                messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))

        final = next((m.content for m in reversed(messages)
                      if isinstance(m, AIMessage) and m.content), "")
        return (final or "(sin análisis)").strip(), recorded


# ── Formateo del mensaje de usuario ───────────────────────────────────────────

def _parse_datname(target: str) -> str:
    """Extrae el nombre de la BD de 'postgres/<nombre_db>'."""
    if "/" in target:
        return target.split("/", 1)[1]
    return target


def _build_user_message(
    ctx: IncidentContext,
    runbooks: list[str],
    past: list[dict],
) -> str:
    runbooks_text = (
        "\n\n---\n\n".join(runbooks) if runbooks
        else "(no hay runbooks indexados para este dominio)"
    )

    if past:
        past_lines = []
        for p in past:
            meta = p.get("metadata", {}) or {}
            past_lines.append(
                f"- **Incidente {str(meta.get('incident_id', ''))[:8]}** "
                f"({meta.get('stored_at', '?')[:10]}) — "
                f"tipo `{meta.get('incident_type', '?')}`, "
                f"target `{meta.get('target', '?')}`, "
                f"similitud: {1 - (p.get('distance') or 0):.2f}\n"
                f"  {(p.get('document') or '')[:300]}..."
            )
        past_text = "\n".join(past_lines)
    else:
        past_text = "(primer incidente de este tipo en memoria)"

    datname = _parse_datname(ctx.target)
    description = ctx.logs or "(sin descripción disponible — usa las tools para obtener métricas actuales)"

    return f"""INCIDENTE ACTUAL
- ID: {ctx.incident_id}
- Título: {ctx.title}
- Base de datos: {datname}
- Target: {ctx.target}
- Severidad: {ctx.severity}
- Tipo clasificado: {ctx.incident_type or 'pendiente'}

DESCRIPCIÓN / MÉTRICAS DEL INCIDENTE:
{description[:3000]}

RUNBOOKS RELEVANTES:
{runbooks_text}

INCIDENTES PASADOS SIMILARES:
{past_text}

Analiza el incidente con el formato markdown que te indicó el sistema. Si
necesitas métricas actuales de la BD, usa tus tools (pg_stat_activity,
pg_stat_database, pg_stat_replication, pg_locks) filtrando por datname='{datname}'."""


# ── Auto-registro ─────────────────────────────────────────────────────────────

register_agent(PostgresAgent())
