"""
Grafo de guardrails (LangGraph).

Orquesta la defensa híbrida como un grafo de estado real de LangGraph:

        START
          │
          ▼
    ┌───────────┐   reglas deterministas (rápidas, gratis):
    │ rules_node│   recorta, neutraliza inyección obvia, valida formato
    └───────────┘
          │
   (condicional)
    ┌─────┴─────────────┐
    │                   │
 bloqueado por      pasó las reglas
 reglas graves          │
    │                   ▼
    │            ┌──────────────┐   capa semántica:
    │            │ llm_judge_node│  un LLM juzga manipulación / tópico
    │            └──────────────┘
    │                   │
    └─────────┬─────────┘
              ▼
             END

Por qué un grafo y no if/else: hace explícito el flujo de control, es lo que
LangGraph está hecho para modelar, queda trazable en LangFuse igual que el
resto del pipeline, y permite añadir nodos nuevos (ej. detección de PII) sin
reescribir la lógica. Es el patrón que recomienda la doc de LangChain/LangGraph
para guardrails.

El supervisor invoca `run_input_guardrail()` y `run_output_guardrail()`, que
compilan el grafo una sola vez y lo ejecutan.
"""

import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from services.agents import guardrails, llm_guardrail

logger = logging.getLogger(__name__)


# ── Estado que fluye por el grafo ──────────────────────────────────────────────

class GuardrailState(TypedDict, total=False):
    text: str               # texto a evaluar (logs o análisis)
    stage: str              # "input" | "output"
    rules_passed: bool      # ¿pasó la capa de reglas?
    llm_passed: bool        # ¿pasó la capa semántica?
    sanitized: str          # texto ya procesado/seguro
    violations: list[str]   # razones acumuladas


# ── Nodo 1: reglas deterministas ───────────────────────────────────────────────

def _rules_node(state: GuardrailState) -> GuardrailState:
    """Primera línea: barata y determinista. Reusa guardrails.py."""
    stage = state.get("stage", "input")
    text = state.get("text", "")

    if stage == "input":
        result = guardrails.check_input(title="", logs=text)
    else:  # "output"
        result = guardrails.check_analysis_output(text)

    return {
        **state,
        "rules_passed": result.passed,
        "sanitized": result.sanitized,
        "violations": list(result.violations),
    }


# ── Nodo 2: juez semántico (LLM) ───────────────────────────────────────────────

def _llm_judge_node(state: GuardrailState) -> GuardrailState:
    """Segunda línea: entiende intención y tópico. Fail-open."""
    stage = state.get("stage", "input")
    verdict = llm_guardrail.judge(state.get("sanitized") or state.get("text", ""), stage=stage)

    violations = list(state.get("violations", []))
    llm_passed = verdict["safe"] and verdict["on_topic"]
    if not llm_passed:
        violations.append(f"LLM-juez: {verdict.get('reason', 'contenido marcado')}")
        logger.warning(f"[guardrail_graph] LLM-juez marcó contenido en etapa '{stage}': {verdict}")

    return {**state, "llm_passed": llm_passed, "violations": violations}


# ── Arista condicional tras las reglas ──────────────────────────────────────────

def _after_rules(state: GuardrailState) -> str:
    """
    Si las reglas ya neutralizaron una inyección evidente en la ENTRADA, igual
    pasamos por el LLM (puede haber inyección parafraseada). Solo saltamos el
    LLM si no hay texto que evaluar.
    """
    if not (state.get("sanitized") or state.get("text")):
        return "skip"
    return "judge"


# ── Compilación del grafo (una sola vez) ────────────────────────────────────────

def _build_graph():
    g = StateGraph(GuardrailState)
    g.add_node("rules", _rules_node)
    g.add_node("judge", _llm_judge_node)

    g.add_edge(START, "rules")
    g.add_conditional_edges("rules", _after_rules, {"judge": "judge", "skip": END})
    g.add_edge("judge", END)
    return g.compile()


_GRAPH = _build_graph()


# ── API pública que usa el Supervisor ───────────────────────────────────────────

def run_input_guardrail(title: str, logs: str) -> GuardrailState:
    """
    Guardrail de ENTRADA por el grafo: reglas → LLM-juez.
    Devuelve el estado final; `sanitized` son los logs ya seguros.
    """
    combined = f"{title}\n{logs}" if title else (logs or "")
    final = _GRAPH.invoke({"text": combined, "stage": "input"})
    # Si el LLM marcó manipulación, blindamos el texto por completo.
    if final.get("llm_passed") is False:
        final["sanitized"] = "[CONTENIDO BLOQUEADO POR GUARDRAIL SEMÁNTICO]"
    return final


def run_output_guardrail(analysis: str) -> GuardrailState:
    """
    Guardrail de SALIDA por el grafo: reglas → LLM-juez.
    Devuelve el estado final; `sanitized` es el análisis (con aviso si se marcó).
    """
    final = _GRAPH.invoke({"text": analysis or "", "stage": "output"})
    already_flagged = "guardrail" in (final.get("sanitized") or "").lower()
    if final.get("llm_passed") is False and not already_flagged:
        final["sanitized"] = (
            "> ⚠️ **Aviso del guardrail semántico:** la respuesta fue marcada como "
            "posible desvío del dominio. Revísala con criterio.\n\n"
            + (final.get("sanitized") or analysis or "")
        )
    return final
