"""
KubernetesAgent — especialista en incidentes de workloads Kubernetes.

Mismo patrón ReAct acotado que DockerAgent y PodmanAgent:
- Consulta runbooks y memoria episódica antes de razonar.
- Puede invocar tools read-only vía el SDK oficial de Kubernetes.
- El target es el nombre del pod o deployment afectado.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
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
from services.agents.kubernetes.tools import all_tools
from services.agents.registry import register_agent

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompt.md"
_MAX_TOOL_ITERATIONS = 4
_MEMORY_STAGE_TIMEOUT_SEC = 8


class KubernetesAgent(DomainAgent):
    name = "kubernetes"

    def matches(self, ctx: IncidentContext) -> bool:
        source = (ctx.labels.get("source_type") or "").lower()
        if source == "database":
            return False
        runtime = (ctx.labels.get("container_runtime") or "").lower()
        if runtime == "kubernetes":
            return True
        # También captura targets con prefijos de recursos K8s
        target = (ctx.target or "").lower()
        return target.startswith("pod/") or target.startswith("deployment/")

    def tools(self) -> list[Callable]:
        return all_tools()

    def system_prompt(self) -> str:
        try:
            return _PROMPT_PATH.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"[KubernetesAgent] No se pudo leer prompt.md: {e}")
            return "Eres un ingeniero SRE analizando incidentes de Kubernetes."

    def investigate(self, ctx: IncidentContext) -> InvestigationResult:
        logger.info(f"[KubernetesAgent] Investigando incidente {ctx.incident_id[:8]}")

        query = f"{ctx.incident_type or ''} {ctx.title} {ctx.logs[:300]}"
        runbooks = self._safe_recall(self.recall_runbooks, query, k=3, label="runbooks")
        past_incidents = self._safe_recall(
            self.recall_similar_incidents, query, k=3, label="memoria"
        )

        user_msg = _build_user_message(ctx, runbooks, past_incidents)
        analysis, tool_calls = self._react_loop(user_msg)

        return InvestigationResult(
            analysis=analysis,
            tool_calls=tool_calls,
            similar_past_incidents=past_incidents,
        )

    def _safe_recall(self, fn, query: str, k: int, label: str):
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            future = pool.submit(fn, query, k)
            result = future.result(timeout=_MEMORY_STAGE_TIMEOUT_SEC)
            pool.shutdown(wait=False, cancel_futures=True)
            return result
        except FutureTimeoutError:
            pool.shutdown(wait=False, cancel_futures=True)
            logger.warning(f"[KubernetesAgent] Timeout consultando {label}; continúo sin él")
            return []
        except Exception as e:
            pool.shutdown(wait=False, cancel_futures=True)
            logger.warning(f"[KubernetesAgent] Error consultando {label}: {e}")
            return []

    def _react_loop(self, user_msg: str) -> tuple[str, list[ToolCall]]:
        tools = self.tools()
        tool_map = {t.name: t for t in tools}

        llm_base = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=45,
            max_retries=1,
        )
        llm = llm_base.bind_tools(tools)

        messages = [
            SystemMessage(content=self.system_prompt()),
            HumanMessage(content=user_msg),
        ]
        recorded: list[ToolCall] = []

        for _ in range(_MAX_TOOL_ITERATIONS):
            response: AIMessage = llm.invoke(messages)
            messages.append(response)

            pending = getattr(response, "tool_calls", None) or []
            if not pending:
                return (response.content or "").strip(), recorded

            for call in pending:
                tool_name = call.get("name") if isinstance(call, dict) else call.name
                tool_args = call.get("args", {}) if isinstance(call, dict) else call.args
                tool_id = call.get("id") if isinstance(call, dict) else call.id

                tool_fn = tool_map.get(tool_name)
                try:
                    result = (
                        tool_fn.invoke(tool_args) if tool_fn
                        else f"Tool '{tool_name}' no existe."
                    )
                except Exception as e:
                    result = f"Error ejecutando '{tool_name}': {e}"

                recorded.append(ToolCall(
                    name=tool_name, args=tool_args, result_preview=str(result)[:500]
                ))
                messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))

        # Límite alcanzado — llamada final sin tools para obtener análisis
        messages.append(HumanMessage(
            content="Límite de tool calls alcanzado. Redacta el análisis "
                    "final ahora con la información que tienes."
        ))
        final: AIMessage = llm_base.invoke(messages)
        return (final.content or "(sin análisis)").strip(), recorded


def _build_user_message(ctx: IncidentContext, runbooks: list[str], past: list[dict]) -> str:
    runbooks_text = (
        "\n\n---\n\n".join(runbooks) if runbooks
        else "(no hay runbooks indexados para Kubernetes)"
    )

    if past:
        past_lines = []
        for p in past:
            meta = p.get("metadata", {}) or {}
            past_lines.append(
                f"- **Incidente {str(meta.get('incident_id',''))[:8]}** "
                f"({meta.get('stored_at','?')[:10]}) — "
                f"tipo `{meta.get('incident_type','?')}`, "
                f"target `{meta.get('target','?')}`, "
                f"similitud: {1-(p.get('distance') or 0):.2f}\n"
                f"  {(p.get('document') or '')[:300]}..."
            )
        past_text = "\n".join(past_lines)
    else:
        past_text = "(primer incidente de este tipo en memoria)"

    return f"""INCIDENTE ACTUAL
- ID: {ctx.incident_id}
- Título: {ctx.title}
- Target (pod/deployment): {ctx.target}
- Severidad: {ctx.severity}
- Tipo clasificado: {ctx.incident_type or 'pendiente'}

LOGS / DESCRIPCIÓN RECIENTE:
{(ctx.logs or '(sin logs disponibles)')[:3000]}

RUNBOOKS RELEVANTES:
{runbooks_text}

INCIDENTES PASADOS SIMILARES:
{past_text}

Analiza el incidente con el formato markdown que te indicó el sistema. Si
necesitas más evidencia del estado actual del pod o deployment, usa tus tools."""


register_agent(KubernetesAgent())
