"""
DockerAgent — especialista en incidentes de contenedores Docker.

Sustituye al antiguo lab2_investigation: además de consultar runbooks,
- Consulta incidentes pasados similares (memoria episódica).
- Puede invocar tools reales (docker_inspect, logs, stats, ps) cuando necesita
  evidencia adicional que los logs de Loki no le dan.
- Persiste el incidente resuelto en la memoria episódica al terminar.
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
from services.agents.docker.tools import all_tools
from services.agents.registry import register_agent

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompt.md"
_MAX_TOOL_ITERATIONS = 4  # evita loops infinitos del LLM


class DockerAgent(DomainAgent):
    name = "docker"

    # ── Contrato de DomainAgent ───────────────────────────────────────────────

    def matches(self, ctx: IncidentContext) -> bool:
        """
        Esta alerta es mía si el label 'job' o 'runtime' indica Docker, o si no
        hay ninguna pista (Docker es el dominio por defecto de Sentinel hoy).
        """
        runtime = (ctx.labels.get("container_runtime") or "").lower()
        if runtime == "docker":
            return True
        if runtime in {"podman", "containerd"}:
            return False
        # Default: si hay container_name, asumimos Docker.
        return bool(ctx.target)

    def tools(self) -> list[Callable]:
        return all_tools()

    def system_prompt(self) -> str:
        try:
            return _PROMPT_PATH.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"[DockerAgent] No se pudo leer prompt.md: {e}")
            return "Eres un ingeniero SRE analizando incidentes de Docker."

    def investigate(self, ctx: IncidentContext) -> InvestigationResult:
        logger.info(f"[DockerAgent] Investigando incidente {ctx.incident_id[:8]}")

        # 1. Memoria: runbooks + incidentes pasados similares
        query = f"{ctx.incident_type or ''} {ctx.title} {ctx.logs[:300]}"
        runbooks = self.recall_runbooks(query, k=3)
        past_incidents = self.recall_similar_incidents(query, k=3)

        # 2. Construye el mensaje de usuario con toda la evidencia
        user_msg = _build_user_message(ctx, runbooks, past_incidents)

        # 3. Loop ReAct manual — bounded, sin dependencias extra de langgraph prebuilt
        analysis, tool_calls = self._react_loop(user_msg)

        return InvestigationResult(
            analysis=analysis,
            tool_calls=tool_calls,
            similar_past_incidents=past_incidents,
        )

    # ── Interno ───────────────────────────────────────────────────────────────

    def _react_loop(self, user_msg: str) -> tuple[str, list[ToolCall]]:
        """
        Loop acotado: el LLM puede llamar tools hasta _MAX_TOOL_ITERATIONS veces.
        Cuando emite una respuesta sin tool_calls, se considera análisis final.
        """
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
                # No más tools → esta es la respuesta final
                return (response.content or "").strip(), recorded

            # Si ya gastamos todas las iteraciones, forzamos una respuesta final
            if i == _MAX_TOOL_ITERATIONS:
                messages.append(HumanMessage(
                    content="Límite de tool calls alcanzado. Redacta el análisis "
                            "final ahora con la información que tienes."
                ))
                continue

            for call in pending:
                tool_name = call.get("name") if isinstance(call, dict) else call.name
                tool_args = call.get("args", {}) if isinstance(call, dict) else call.args
                tool_id = call.get("id") if isinstance(call, dict) else call.id

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

        # Fallback — no debería llegarse aquí
        final = next((m.content for m in reversed(messages)
                      if isinstance(m, AIMessage) and m.content), "")
        return (final or "(sin análisis)").strip(), recorded


# ── Formateo del mensaje de usuario ───────────────────────────────────────────

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

    logs = ctx.logs or "(sin logs disponibles)"

    return f"""INCIDENTE ACTUAL
- ID: {ctx.incident_id}
- Título: {ctx.title}
- Contenedor: {ctx.target}
- Severidad: {ctx.severity}
- Tipo clasificado: {ctx.incident_type or 'pendiente'}

LOGS RECIENTES (Loki):
{logs[:3000]}

RUNBOOKS RELEVANTES:
{runbooks_text}

INCIDENTES PASADOS SIMILARES:
{past_text}

Analiza el incidente con el formato markdown que te indicó el sistema. Si
necesitas más evidencia del estado actual del contenedor, usa tus tools."""


# ── Auto-registro ─────────────────────────────────────────────────────────────

register_agent(DockerAgent())
