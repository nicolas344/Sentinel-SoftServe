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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from db.supabase_client import supabase
from services.agents import guardrails
from services.agents.base import IncidentContext, InvestigationResult
from services.agents.registry import find_agent_for, list_agents
from services.incident_events import record_event

logger = logging.getLogger(__name__)
_MEMORY_WRITE_TIMEOUT_SEC = 8

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
        timeout=45,
        max_retries=1,
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


def _build_proposed_action(ctx: IncidentContext, incident_type: str) -> str | None:
    """
    Genera una accion segura por defecto para ejecucion bajo aprobacion humana.
    Soporta comandos Docker whitelisteados y funciones Postgres de solo lectura/cancelacion.
    """
    runtime = (ctx.labels.get("container_runtime") or "").lower()
    source_type = (ctx.labels.get("source_type") or "container").lower()
    target = (ctx.target or "").strip()

    # ── Incidentes de base de datos (PostgreSQL) ──────────────────────────────
    if source_type == "database":
        datname = target.replace("postgres/", "").strip()
        if not datname or " " in datname or "/" in datname:
            return None
        # Terminamos conexiones activas si la BD está saturada o en crash
        if incident_type in {"app_crash", "dependency_failure", "restart_loop", "memory_pressure"}:
            return f"pg_terminate_backend {datname}"
        # Para deadlocks o CPU alta intentamos cancelar queries sin matar la conexión
        if incident_type in {"cpu_throttling", "network_error"}:
            return f"pg_cancel_backend {datname}"
        # En cualquier otro caso, una observación sin efecto secundario
        return f"pg_stat_activity {datname}"

    # ── Incidentes de contenedor Podman ──────────────────────────────────────
    if runtime == "podman":
        if not target or "/" in target or " " in target:
            return None
        if incident_type in {"app_crash", "oom", "restart_loop", "dependency_failure", "config_error"}:
            return f"podman restart {target}"
        return f"podman logs {target}"

    # ── Incidentes de workload Kubernetes ────────────────────────────────────
    if runtime == "kubernetes":
        namespace = (ctx.labels.get("namespace") or "default").strip()
        # Strip pod/ or deployment/ prefix to get the bare name
        clean = target.replace("pod/", "").replace("deployment/", "").strip()
        if not clean or "/" in clean or " " in clean:
            return None
        # Crash/OOM/restart → delete the pod so the ReplicaSet recreates it fresh
        if incident_type in {"app_crash", "oom", "restart_loop", "dependency_failure", "config_error"}:
            return f"kubectl delete pod {clean} -n {namespace}"
        return f"kubectl rollout restart deployment/{clean} -n {namespace}"

    # ── Incidentes de contenedor Docker ──────────────────────────────────────
    if runtime and runtime != "docker":
        return None
    if not target or "/" in target or " " in target:
        return None

    if incident_type in {"app_crash", "oom", "restart_loop", "dependency_failure", "config_error"}:
        return f"docker restart {target}"

    return f"docker logs {target}"


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
        # ── Guardrail de ENTRADA ──────────────────────────────────────────────
        # Recorta logs y neutraliza intentos de prompt injection ANTES de que
        # el LLM vea el incidente.
        input_check = guardrails.check_input(ctx.title, ctx.logs)
        ctx.logs = input_check.sanitized
        if not input_check.passed:
            logger.warning(
                f"[Supervisor] Guardrail de entrada activado en {ctx.incident_id[:8]}: "
                f"{input_check.violations}"
            )

        # 1. Clasificación (Lab 1 — Alert Intake)
        incident_type, class_reason = _classify(ctx)

        # ── Guardrail de CLASIFICACIÓN ────────────────────────────────────────
        # El tipo de incidente debe pertenecer al catálogo cerrado; si el LLM
        # inventó una categoría, se fuerza a 'unknown'.
        type_check = guardrails.check_incident_type(incident_type)
        incident_type = type_check.sanitized
        ctx.incident_type = incident_type

        _update_incident(ctx.incident_id, {
            "status": "investigating",
            "incident_type": incident_type,
            "agent_reasoning": (
                f"## Clasificación inicial\n\n"
                f"**Tipo detectado:** `{incident_type}`\n\n{class_reason}"
            ),
        })
        record_event(ctx.incident_id, "investigating")

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
            record_event(ctx.incident_id, "analyzed")
            return

        logger.info(f"[Supervisor] Enrutando {ctx.incident_id[:8]} → '{agent.name}'")

        # 3. Investigación (Lab 2 — Investigation)
        result = agent.investigate(ctx)

        # ── Guardrail de SALIDA / SCOPE ───────────────────────────────────────
        # Verifica que el análisis del agente no se haya desviado del dominio
        # DevOps. Si se desvió, antepone una advertencia visible al ingeniero.
        output_check = guardrails.check_analysis_output(result.analysis)
        result.analysis = output_check.sanitized
        if not output_check.passed:
            logger.warning(
                f"[Supervisor] Guardrail de salida activado en {ctx.incident_id[:8]}: "
                f"{output_check.violations}"
            )

        # 4. Persistencia final
        full_reasoning = _render_final_reasoning(class_reason, incident_type, agent.name, result)
        proposed_action = _build_proposed_action(ctx, incident_type)

        # ── Guardrail de ACCIÓN ───────────────────────────────────────────────
        # Re-valida de forma independiente que la acción propuesta esté en la
        # lista blanca de comandos seguros. Si no lo está, NO se propone nada:
        # el incidente queda en 'analyzed' para revisión manual del ingeniero.
        action_check = guardrails.check_proposed_action(proposed_action)
        if not action_check.passed:
            logger.error(
                f"[Supervisor] Guardrail de acción BLOQUEÓ '{proposed_action}' "
                f"en {ctx.incident_id[:8]}: {action_check.violations}"
            )
            proposed_action = None
        else:
            proposed_action = action_check.sanitized or None

        _update_incident(ctx.incident_id, {
            "status": "analyzed",
            "agent_reasoning": full_reasoning,
        })
        record_event(ctx.incident_id, "analyzed")

        # Pasa a gate de aprobacion cuando hay accion segura propuesta.
        if proposed_action:
            _update_incident(ctx.incident_id, {
                "status": "awaiting_approval",
                "proposed_action": proposed_action,
            })
            record_event(ctx.incident_id, "awaiting_approval")

        # 5. Memoria episódica (best-effort, no bloqueante)
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            future = pool.submit(agent.remember_incident, ctx, result)
            future.result(timeout=_MEMORY_WRITE_TIMEOUT_SEC)
            pool.shutdown(wait=False, cancel_futures=True)
        except FutureTimeoutError:
            pool.shutdown(wait=False, cancel_futures=True)
            logger.warning(f"[Supervisor] Timeout guardando memoria para {ctx.incident_id[:8]}; continuo")
        except Exception as e:
            pool.shutdown(wait=False, cancel_futures=True)
            logger.warning(f"[Supervisor] Error guardando memoria para {ctx.incident_id[:8]}: {e}")

        if trace:
            trace.update(output={
                "status": "awaiting_approval" if proposed_action else "analyzed",
                "agent": agent.name,
                "tools_used": [tc.name for tc in result.tool_calls],
                "similar_incidents": len(result.similar_past_incidents),
                "proposed_action": proposed_action,
            })

        logger.info(f"[Supervisor] Triage completado {ctx.incident_id[:8]} por '{agent.name}'")

    except Exception as e:
        logger.exception(f"[Supervisor] Fallo en triage de {ctx.incident_id[:8]}")
        _update_incident(ctx.incident_id, {
            "status": "failed",
            "agent_reasoning": (
                "## Error\n\n"
                "No se pudo completar la investigación automática. "
                "Revisa conectividad a servicios (OpenAI/Chroma/LangFuse) y logs del backend."
            ),
            "action_error": str(e),
        })
        record_event(ctx.incident_id, "failed")
        if trace:
            trace.update(output={"error": str(e)})
    finally:
        if _langfuse:
            try:
                _langfuse.flush()
            except Exception:
                pass
