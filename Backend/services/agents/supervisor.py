"""
Supervisor: orquesta todo el ciclo de triage de un incidente.

Responsabilidades:
  1. Clasificar el incidente (Lab 1 — Alert Intake) con un LLM ligero.
  2. Seleccionar el agente de dominio apropiado (registry).
  3. Delegar la investigación al especialista.
  4. Persistir el resultado en Supabase + memoria episódica.
  5. Crear la traza en LangFuse.

Este módulo NO conoce detalles de ningún dominio. Añadir un dominio nuevo
(kubernetes, postgres, ...) no requiere tocar este archivo — solo registrar
el agente.
"""

import json
import logging
import os

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from db.supabase_client import supabase
from services.agents.base import IncidentContext, InvestigationResult
from services.agents.registry import find_agent_for, list_agents

logger = logging.getLogger(__name__)

# LangFuse — SDK directo, igual que antes
_langfuse = None
try:
    from langfuse import Langfuse
    _langfuse = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
        host=os.getenv("LANGFUSE_HOST", "http://localhost:3001"),
    )
except Exception as _e:
    logger.warning(f"LangFuse no disponible: {_e}")


# Categorías soportadas por la clasificación. Las mismas que el engine anterior
# para no romper el frontend.
_INCIDENT_TYPES = [
    "app_crash", "oom", "config_error", "dependency_failure",
    "memory_pressure", "cpu_throttling", "restart_loop",
    "network_error", "disk_pressure", "unknown",
]


# ── Nodo 1: Clasificación ─────────────────────────────────────────────────────

def _classify(ctx: IncidentContext) -> tuple[str, str]:
    """
    Clasifica el incidente con el LLM. Retorna (incident_type, reasoning).
    Este paso sigue siendo compartido por todos los dominios — cada agente
    puede refinar después si lo necesita.
    """
    logs_preview = (ctx.logs or "Sin logs disponibles.")[:800]
    types_list = ", ".join(_INCIDENT_TYPES)

    prompt = f"""Eres un clasificador de incidentes DevOps.

Analiza el siguiente incidente y clasifícalo en UNA sola categoría de esta lista:
{types_list}

Título: {ctx.title}
Target: {ctx.target}
Severidad: {ctx.severity}
Logs (vista previa):
{logs_preview}

Responde ÚNICAMENTE con JSON válido:
{{"incident_type": "<categoría>", "reasoning": "<máx 2 oraciones en español>"}}"""

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = (response.content or "").strip()
        # Tolera respuestas envueltas en ```json ... ``` por si el modelo ignora response_format
        if raw.startswith("```"):
            raw = raw.strip("`").lstrip("json").strip()
        parsed = json.loads(raw)
        itype = parsed.get("incident_type", "unknown")
        if itype not in _INCIDENT_TYPES:
            itype = "unknown"
        reasoning = parsed.get("reasoning", "Sin razonamiento disponible.")
        return itype, reasoning
    except Exception as e:
        logger.error(f"[Supervisor] Error clasificando {ctx.incident_id[:8]}: {e}")
        return "unknown", "Error al clasificar automáticamente."


# ── Nodo 2: Persistencia ──────────────────────────────────────────────────────

def _update_incident(incident_id: str, fields: dict) -> None:
    try:
        supabase.table("incidents").update(fields).eq("id", incident_id).execute()
    except Exception as e:
        logger.error(f"[Supervisor] Error actualizando Supabase {incident_id[:8]}: {e}")


def _render_final_reasoning(
    classification_reason: str,
    incident_type: str,
    agent_name: str,
    result: InvestigationResult,
) -> str:
    """Markdown que se guarda en agent_reasoning (visible en UI)."""
    tools_line = (
        "— ".join(f"`{tc.name}`" for tc in result.tool_calls)
        if result.tool_calls else "ninguna"
    )
    similar_count = len(result.similar_past_incidents)

    return (
        f"## Clasificación inicial\n\n"
        f"**Tipo detectado:** `{incident_type}`\n\n"
        f"{classification_reason}\n\n"
        f"---\n\n"
        f"## Investigación (agente `{agent_name}`)\n\n"
        f"_Tools invocadas: {tools_line}. Incidentes similares encontrados: {similar_count}._\n\n"
        f"{result.analysis}"
    )


# ── Punto de entrada ──────────────────────────────────────────────────────────

def run_triage(ctx: IncidentContext) -> None:
    """
    Orquesta el ciclo completo: clasificar → enrutar → investigar → persistir.
    Pensado para correr como BackgroundTask de FastAPI.
    """
    logger.info(f"[Supervisor] Iniciando triage de {ctx.incident_id[:8]}")

    trace = None
    if _langfuse:
        try:
            trace = _langfuse.trace(
                name=f"incident-{ctx.incident_id[:8]}",
                input={"title": ctx.title, "severity": ctx.severity, "target": ctx.target},
                tags=["sentinel", ctx.severity, "multiagent"],
            )
        except Exception as e:
            logger.warning(f"No se pudo crear traza LangFuse: {e}")

    try:
        # 1. Clasificación
        incident_type, class_reason = _classify(ctx)
        ctx.incident_type = incident_type

        _update_incident(ctx.incident_id, {
            "status": "investigating",
            "incident_type": incident_type,
            "agent_reasoning": (
                f"## Clasificación inicial\n\n"
                f"**Tipo detectado:** `{incident_type}`\n\n{class_reason}"
            ),
        })

        # 2. Routing
        agent = find_agent_for(ctx)
        if agent is None:
            registered = [a.name for a in list_agents()]
            msg = (
                f"No hay agente registrado que maneje esta alerta. "
                f"Agentes disponibles: {registered or 'ninguno'}."
            )
            logger.error(f"[Supervisor] {msg}")
            _update_incident(ctx.incident_id, {
                "status": "analyzed",
                "agent_reasoning": (
                    f"## Clasificación\n\n`{incident_type}` — {class_reason}\n\n"
                    f"## Error de routing\n\n{msg}"
                ),
            })
            return

        logger.info(f"[Supervisor] Enrutando {ctx.incident_id[:8]} → '{agent.name}'")

        # 3. Investigación
        result = agent.investigate(ctx)

        # 4. Memoria episódica
        agent.remember_incident(ctx, result)

        # 5. Persistencia final
        full_reasoning = _render_final_reasoning(class_reason, incident_type, agent.name, result)
        _update_incident(ctx.incident_id, {
            "status": "analyzed",
            "agent_reasoning": full_reasoning,
        })

        if trace:
            trace.update(output={
                "status": "analyzed",
                "agent": agent.name,
                "tools_used": [tc.name for tc in result.tool_calls],
                "similar_incidents": len(result.similar_past_incidents),
            })

        logger.info(f"[Supervisor] Triage completado {ctx.incident_id[:8]} por '{agent.name}'")

    except Exception as e:
        logger.exception(f"[Supervisor] Fallo en triage de {ctx.incident_id[:8]}")
        if trace:
            trace.update(output={"error": str(e)})
    finally:
        if _langfuse:
            try:
                _langfuse.flush()
            except Exception:
                pass
