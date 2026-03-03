import os
import json
import logging
from typing import TypedDict, Optional
from urllib.parse import urlparse

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END
import chromadb

from db.supabase_client import supabase

logger = logging.getLogger(__name__)

# LangFuse — SDK directo (sin dependencia de langchain)
# CallbackHandler de langfuse.callback requiere 'langchain' instalado, que en v1.x causa conflicto.
# Usamos el SDK nativo: langfuse.Langfuse — crea trazas directamente sin el callback bridge.
_langfuse = None
try:
    from langfuse import Langfuse
    _langfuse = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
        host=os.getenv("LANGFUSE_HOST", "http://localhost:3001"),
    )
    logger.info("LangFuse inicializado correctamente.")
except Exception as _lf_err:
    logger.warning(f"LangFuse no disponible — trazabilidad desactivada: {_lf_err}")


# ── Estado compartido entre todos los nodos del grafo ────────────────────────

class IncidentState(TypedDict):
    incident_id: str
    container_name: str
    logs: str
    severity: str
    title: str
    incident_type: Optional[str]
    agent_reasoning: str


# ── Helpers internos ──────────────────────────────────────────────────────────

def _get_llm() -> ChatOpenAI:
    """Instancia el LLM. gpt-4o-mini en Sprint 1 (low-cost). Cambiar en .env para Sprint 2."""
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
    )


def _get_chroma_collection():
    """Conecta al contenedor ChromaDB y retorna la colección 'runbooks'."""
    chroma_url = os.getenv("CHROMA_HOST", "http://localhost:8001")
    parsed = urlparse(chroma_url)
    client = chromadb.HttpClient(host=parsed.hostname, port=parsed.port or 8001)
    return client.get_or_create_collection("runbooks")


# ── Lab 1: Alert Intake ───────────────────────────────────────────────────────

def lab1_alert_intake(state: IncidentState) -> dict:
    """
    Nodo 1 del grafo. Clasifica el tipo de incidente con el LLM.

    Entrada:  título, container_name, severity, primeras líneas de logs.
    Salida:   incident_type + reasoning inicial.
    Supabase: status → 'investigating', incident_type, agent_reasoning (paso 1).
    """
    logs_preview = state["logs"][:800] if state["logs"] else "Sin logs disponibles."

    prompt = f"""Eres un agente de clasificación de incidentes DevOps.

Analiza el siguiente incidente y clasifícalo en una sola categoría.

Título: {state["title"]}
Contenedor: {state["container_name"]}
Severidad: {state["severity"]}
Logs (vista previa):
{logs_preview}

Categorías disponibles:
- app_crash: La aplicación lanzó una excepción, pánico o error fatal no manejado.
- oom: El contenedor fue terminado por el kernel por falta de memoria (exit code 137, OOM Killer).
- config_error: Variables de entorno faltantes o archivos de configuración inválidos.
- dependency_failure: Servicio externo no disponible (base de datos caída, connection refused, timeout).
- unknown: No encaja en ninguna de las categorías anteriores.

Responde ÚNICAMENTE con un JSON válido con este formato exacto (sin texto adicional):
{{
  "incident_type": "<una de las cinco categorías>",
  "reasoning": "<explicación breve en español de por qué clasificaste así, máximo 2 oraciones>"
}}"""

    llm = _get_llm()
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        parsed = json.loads(response.content.strip())
        incident_type = parsed.get("incident_type", "unknown")
        step1_text = parsed.get("reasoning", "Sin razonamiento disponible.")
    except Exception as e:
        logger.error(f"[Lab1] Error clasificando incidente {state['incident_id'][:8]}: {e}")
        incident_type = "unknown"
        step1_text = "Error al clasificar el incidente automáticamente."

    reasoning_step1 = (
        f"## Clasificación inicial (Lab 1 — Alert Intake)\n\n"
        f"**Tipo detectado:** `{incident_type}`\n\n"
        f"{step1_text}"
    )

    try:
        supabase.table("incidents").update({
            "status": "investigating",
            "incident_type": incident_type,
            "agent_reasoning": reasoning_step1,
        }).eq("id", state["incident_id"]).execute()
        logger.info(f"[Lab1] Completado — incidente {state['incident_id'][:8]}: {incident_type}")
    except Exception as e:
        logger.error(f"[Lab1] Error actualizando Supabase: {e}")

    return {
        "incident_type": incident_type,
        "agent_reasoning": reasoning_step1,
    }


# ── Lab 2: Investigation ──────────────────────────────────────────────────────

def lab2_investigation(state: IncidentState) -> dict:
    """
    Nodo 2 del grafo. Consulta ChromaDB por runbooks relevantes y analiza el root cause.

    Entrada:  incident_type + logs completos + runbooks de ChromaDB.
    Salida:   análisis completo en markdown.
    Supabase: status → 'analyzed', agent_reasoning (completo).
    """
    incident_type = state["incident_type"] or "unknown"

    # Búsqueda semántica en ChromaDB — retorna los 3 runbooks más relevantes
    try:
        collection = _get_chroma_collection()
        query_text = f"{incident_type} {state['title']} {state['logs'][:300]}"
        results = collection.query(query_texts=[query_text], n_results=3)
        docs = results.get("documents", [[]])[0]
        runbooks_text = "\n\n---\n\n".join(docs) if docs else "Sin runbooks disponibles."
    except Exception as e:
        logger.warning(f"[Lab2] ChromaDB no disponible: {e}")
        runbooks_text = "Sin runbooks disponibles (ChromaDB no accesible)."

    logs_full = state["logs"] if state["logs"] else "Sin logs disponibles."

    prompt = f"""Eres un ingeniero SRE senior analizando un incidente de producción real.

INCIDENTE:
- Tipo clasificado: {incident_type}
- Contenedor: {state["container_name"]}
- Severidad: {state["severity"]}
- Título: {state["title"]}

LOGS COMPLETOS DEL CONTENEDOR:
{logs_full[:3000]}

RUNBOOKS OPERACIONALES RELEVANTES:
{runbooks_text}

Realiza un análisis técnico completo en español. Usa exactamente este formato markdown:

## Causa Raíz
[Explica qué originó el incidente basándote en los logs y en los runbooks]

## Evidencia en Logs
[Cita las líneas de log específicas que confirman tu diagnóstico]

## Acciones Recomendadas
[Lista numerada de acciones concretas y ordenadas por urgencia para resolver el incidente]

## Evaluación de Urgencia
[Evalúa el impacto real en el sistema y si requiere atención inmediata o puede esperar]"""

    llm = _get_llm()
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        analysis = response.content.strip()
    except Exception as e:
        logger.error(f"[Lab2] Error analizando incidente {state['incident_id'][:8]}: {e}")
        analysis = "## Error\n\nNo se pudo completar el análisis de investigación."

    full_reasoning = (
        f"{state['agent_reasoning']}\n\n"
        f"---\n\n"
        f"## Investigación completa (Lab 2 — Investigation)\n\n"
        f"{analysis}"
    )

    try:
        supabase.table("incidents").update({
            "status": "analyzed",
            "agent_reasoning": full_reasoning,
        }).eq("id", state["incident_id"]).execute()
        logger.info(f"[Lab2] Completado — incidente {state['incident_id'][:8]} analizado")
    except Exception as e:
        logger.error(f"[Lab2] Error actualizando Supabase: {e}")

    return {"agent_reasoning": full_reasoning}


# ── Compilación del grafo (se hace una sola vez al importar el módulo) ────────

def _build_graph():
    workflow = StateGraph(IncidentState)
    workflow.add_node("lab1_alert_intake", lab1_alert_intake)
    workflow.add_node("lab2_investigation", lab2_investigation)
    workflow.set_entry_point("lab1_alert_intake")
    workflow.add_edge("lab1_alert_intake", "lab2_investigation")
    workflow.add_edge("lab2_investigation", END)
    return workflow.compile()


_graph = _build_graph()


# ── Punto de entrada público (llamado desde alerts.py via BackgroundTask) ─────

def run_langgraph_engine(
    incident_id: str,
    container_name: str,
    logs: str,
    severity: str,
    title: str,
) -> None:
    """
    Lanza el grafo LangGraph para un incidente dado.
    Diseñado para ejecutarse como BackgroundTask de FastAPI — no bloquea la respuesta HTTP.
    Cada nodo actualiza Supabase directamente; el frontend lo ve en tiempo real vía Realtime.
    """
    logger.info(f"Iniciando LangGraph engine — incidente {incident_id[:8]}")

    initial_state: IncidentState = {
        "incident_id": incident_id,
        "container_name": container_name,
        "logs": logs or "",
        "severity": severity,
        "title": title,
        "incident_type": None,
        "agent_reasoning": "",
    }

    # Crear traza en LangFuse (si está disponible)
    trace = None
    if _langfuse:
        try:
            trace = _langfuse.trace(
                name=f"incident-{incident_id[:8]}",
                input={"title": title, "severity": severity, "container": container_name},
                tags=["sentinel", severity, "sprint1"],
            )
        except Exception as e:
            logger.warning(f"No se pudo crear traza LangFuse: {e}")

    try:
        _graph.invoke(initial_state)
        if trace:
            trace.update(output={"status": "analyzed"})
        logger.info(f"LangGraph engine completado — incidente {incident_id[:8]}")
    except Exception as e:
        logger.error(f"LangGraph engine falló para incidente {incident_id[:8]}: {e}")
        if trace:
            trace.update(output={"error": str(e)})
    finally:
        if _langfuse:
            try:
                _langfuse.flush()
            except Exception:
                pass
