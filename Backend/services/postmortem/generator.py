import json
import logging
import os
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from services.postmortem.formatters import format_timeline_markdown
from services.postmortem.template import render_post_mortem_template

logger = logging.getLogger(__name__)


def _fallback_post_mortem(incident: dict[str, Any], timeline: list[dict[str, Any]], mttr: str) -> str:
    return render_post_mortem_template(
        title=incident.get("title") or "Incidente",
        summary=(incident.get("logs") or "No hay descripción disponible")[:700],
        root_cause="Pendiente de validación manual por el equipo de guardia.",
        timeline=format_timeline_markdown(timeline),
        resolution=(incident.get("action_result") or "Se estabilizó el servicio y quedó en estado resolved.")[:700],
        mttr=mttr,
        lessons_learned="1. Mejorar observabilidad en componentes críticos.\n2. Definir runbooks más específicos por tipo de incidente.",
        preventive_actions="1. Agregar alertas tempranas con umbrales más conservadores.\n2. Revisar capacidad y límites del recurso afectado.",
    )


def generate_post_mortem_with_llm(
    incident: dict[str, Any],
    timeline: list[dict[str, Any]],
    mttr: str,
) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _fallback_post_mortem(incident, timeline, mttr)

    timeline_text = format_timeline_markdown(timeline)
    payload = {
        "title": incident.get("title"),
        "severity": incident.get("severity"),
        "status": incident.get("status"),
        "target": incident.get("target"),
        "source_type": incident.get("source_type"),
        "logs": (incident.get("logs") or "")[:2500],
        "agent_reasoning": (incident.get("agent_reasoning") or "")[:3500],
        "action_result": (incident.get("action_result") or "")[:1500],
        "action_error": (incident.get("action_error") or "")[:1000],
        "timeline": timeline_text,
        "mttr": mttr,
    }

    prompt = (
        "Genera un post-mortem técnico en español en formato Markdown. "
        "Responde SOLO con markdown y usando exactamente estas secciones:\n"
        "# Post-Mortem: [Incident Title]\n"
        "## Summary\n"
        "## Root Cause\n"
        "## Timeline\n"
        "## Resolution\n"
        "## MTTR\n"
        "## Lessons Learned\n"
        "## Preventive Actions\n\n"
        "Debe ser concreto, accionable y no inventar datos fuera del contexto.\n\n"
        f"Contexto JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )

    try:
        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.2,
            api_key=api_key,
            timeout=45,
            max_retries=1,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        content = (response.content or "").strip()
        return content or _fallback_post_mortem(incident, timeline, mttr)
    except Exception as exc:
        logger.warning(f"[postmortem.generator] Fallback por error de LLM: {exc}")
        return _fallback_post_mortem(incident, timeline, mttr)
