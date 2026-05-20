"""
Guardrails: capa de seguridad del agente de Sentinel.

Un guardrail es una verificación determinista que se ejecuta ANTES y DESPUÉS
de que el LLM razone. Su trabajo es impedir que el agente:

  1. Sea manipulado por contenido malicioso en los logs (prompt injection).
  2. Produzca una clasificación inválida que rompa el frontend.
  3. Proponga una acción fuera de la lista blanca de comandos seguros.
  4. Se desvíe del tema — responder cosas que no son del incidente.

Diseño: reglas, no LLM. Los guardrails NO llaman a OpenAI — son rápidos,
deterministas y gratis. Esto respeta el NFR-10 (máx 5 llamadas LLM/min) y
hace que el comportamiento sea 100% auditable y testeable.

Se integra en el Supervisor (services/agents/supervisor.py), que actúa como
el grafo de LangGraph: cada guardrail es un punto de control entre nodos.
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Resultado de un guardrail ─────────────────────────────────────────────────

@dataclass
class GuardrailResult:
    """
    Resultado de pasar por un guardrail.

    - passed:    True si el contenido es seguro.
    - sanitized: el contenido ya limpio/corregido (puede diferir del original).
    - violations: lista de razones por las que falló (vacía si passed=True).
    """
    passed: bool
    sanitized: str = ""
    violations: list[str] = field(default_factory=list)


# ── Catálogos de lo que SÍ está permitido ─────────────────────────────────────

# Tipos de incidente válidos. Si el LLM inventa otro, lo forzamos a "unknown".
_VALID_INCIDENT_TYPES = {
    "app_crash", "oom", "config_error", "dependency_failure",
    "memory_pressure", "cpu_throttling", "restart_loop",
    "network_error", "disk_pressure", "unknown",
}

# Lista blanca de acciones que el agente puede proponer. Cualquier comando
# fuera de estos patrones se bloquea: el agente NO puede proponer otra cosa.
_ALLOWED_ACTION_PATTERNS = [
    re.compile(r"^docker (restart|logs) [a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$"),
    re.compile(r"^podman (restart|logs) [a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$"),
    re.compile(r"^pg_(stat_activity|cancel_backend|terminate_backend) "
               r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$"),
    # Kubernetes — kubectl rollout restart deployment/<name> [-n <namespace>]
    re.compile(
        r"^kubectl rollout restart deployment/[a-zA-Z0-9][a-zA-Z0-9-]{0,62}"
        r"( -n [a-zA-Z0-9][a-zA-Z0-9-]{0,62})?$"
    ),
    # Kubernetes — kubectl delete pod <pod-name> [-n <namespace>]
    re.compile(
        r"^kubectl delete pod [a-zA-Z0-9][a-zA-Z0-9-]{0,62}"
        r"( -n [a-zA-Z0-9][a-zA-Z0-9-]{0,62})?$"
    ),
    # Kubernetes — kubectl scale deployment/<name> --replicas=<0-10> [-n <namespace>]
    re.compile(
        r"^kubectl scale deployment/[a-zA-Z0-9][a-zA-Z0-9-]{0,62}"
        r" --replicas=(10|[0-9])"
        r"( -n [a-zA-Z0-9][a-zA-Z0-9-]{0,62})?$"
    ),
]

# Frases típicas de prompt injection — alguien que mete instrucciones en los
# logs para secuestrar al agente. No es exhaustivo, pero corta lo más común.
_INJECTION_PATTERNS = [
    re.compile(r"ignore (all |the |your |previous )+(instructions|prompt|rules)", re.I),
    re.compile(r"olvida (todas )?(las )?instrucciones (previas|anteriores)", re.I),
    re.compile(r"you are now (a|an) ", re.I),
    re.compile(r"ahora eres (un|una) ", re.I),
    re.compile(r"system prompt", re.I),
    re.compile(r"reveal your (instructions|prompt|system)", re.I),
    re.compile(r"act as (a|an) ", re.I),
    re.compile(r"disregard (the |all |your )", re.I),
]

# Señales de que el análisis se salió del dominio DevOps/incidentes. Si el
# agente empieza a hablar de esto, algo lo desvió.
_OFF_TOPIC_PATTERNS = [
    re.compile(r"\b(receta\s+de\s+cocina|chiste|poema|canción|cancion)\b", re.I),
    # "política" se excluye: colisiona con términos técnicos como "política de reinicio",
    # "política de restart", "política de recursos" — falsos positivos frecuentes en DevOps.
    re.compile(r"\b(religión|religion|partido\s+político|elecciones presidenciales)\b", re.I),
    re.compile(r"\b(bitcoin|criptomoneda|invertir en bolsa|acciones de bolsa)\b", re.I),
]

# Longitud máxima de logs que se le pasa al LLM. Más allá de esto es ruido y
# además abre la puerta a inyecciones escondidas en logs gigantes.
_MAX_LOG_CHARS = 4000


# ── Guardrail 1: Entrada (antes de que el LLM vea el incidente) ────────────────

def check_input(title: str, logs: str) -> GuardrailResult:
    """
    Guardrail de ENTRADA. Se ejecuta antes de mandar el incidente al LLM.

    - Recorta los logs a un tamaño razonable.
    - Detecta intentos de prompt injection dentro del título o los logs.
    - Si encuentra inyección, neutraliza la línea ofensiva en vez de abortar:
      el incidente igual debe analizarse, pero sin obedecer la inyección.

    Retorna GuardrailResult con `sanitized` = logs ya limpios.
    """
    violations: list[str] = []
    safe_logs = (logs or "")[:_MAX_LOG_CHARS]
    combined = f"{title or ''}\n{safe_logs}"

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(combined):
            violations.append(f"Posible prompt injection detectado: patrón '{pattern.pattern}'")

    if violations:
        # Neutralizar: marcar las líneas sospechosas en vez de obedecerlas.
        cleaned_lines = []
        for line in safe_logs.splitlines():
            if any(p.search(line) for p in _INJECTION_PATTERNS):
                cleaned_lines.append("[LÍNEA NEUTRALIZADA POR GUARDRAIL — posible inyección]")
            else:
                cleaned_lines.append(line)
        safe_logs = "\n".join(cleaned_lines)
        logger.warning(f"[guardrails.input] {len(violations)} violación(es): {violations}")

    return GuardrailResult(
        passed=len(violations) == 0,
        sanitized=safe_logs,
        violations=violations,
    )


# ── Guardrail 2: Clasificación (después de Lab 1 — Alert Intake) ───────────────

def check_incident_type(incident_type: str) -> GuardrailResult:
    """
    Guardrail de CLASIFICACIÓN. Garantiza que el tipo de incidente sea uno de
    los valores válidos. Si el LLM inventa una categoría, la forzamos a
    'unknown' — el frontend solo entiende este conjunto cerrado.
    """
    itype = (incident_type or "").strip().lower()
    if itype in _VALID_INCIDENT_TYPES:
        return GuardrailResult(passed=True, sanitized=itype)

    logger.warning(f"[guardrails.classification] Tipo inválido '{incident_type}' → 'unknown'")
    return GuardrailResult(
        passed=False,
        sanitized="unknown",
        violations=[f"Tipo de incidente fuera del catálogo: '{incident_type}'"],
    )


# ── Guardrail 3: Acción propuesta (antes de pasar a aprobación humana) ─────────

def check_proposed_action(action: str | None) -> GuardrailResult:
    """
    Guardrail de ACCIÓN. Es el más importante: verifica que la acción que el
    agente quiere proponer esté EXACTAMENTE dentro de la lista blanca de
    comandos seguros.

    Esto es defensa en profundidad: aunque `_build_proposed_action` ya genera
    comandos seguros, este guardrail los re-valida de forma independiente. Si
    el día de mañana alguien cambia esa función o un agente nuevo propone algo
    raro, el guardrail lo corta antes de que llegue al ingeniero.

    - action=None es válido (significa "no hay acción que proponer").
    - Cualquier comando que no matchee la whitelist se bloquea (sanitized=None).
    """
    if action is None or action.strip() == "":
        return GuardrailResult(passed=True, sanitized="")

    candidate = action.strip()

    # Bloqueo explícito de caracteres de encadenamiento de shell.
    if any(ch in candidate for ch in (";", "&&", "||", "|", "`", "$(", ">", "<")):
        logger.error(f"[guardrails.action] BLOQUEADA acción con metacaracteres: '{candidate}'")
        return GuardrailResult(
            passed=False,
            sanitized="",
            violations=[f"Acción contiene metacaracteres de shell: '{candidate}'"],
        )

    for pattern in _ALLOWED_ACTION_PATTERNS:
        if pattern.match(candidate):
            return GuardrailResult(passed=True, sanitized=candidate)

    logger.error(f"[guardrails.action] BLOQUEADA acción fuera de la whitelist: '{candidate}'")
    return GuardrailResult(
        passed=False,
        sanitized="",
        violations=[f"Acción no está en la lista blanca de comandos seguros: '{candidate}'"],
    )


# ── Guardrail 4: Salida / scope (después de Lab 2 — Investigation) ─────────────

def check_analysis_output(analysis: str) -> GuardrailResult:
    """
    Guardrail de SCOPE. Revisa que el análisis final del agente se mantenga en
    el dominio: incidentes DevOps. Si el agente fue desviado y empezó a hablar
    de temas ajenos, lo marcamos.

    No reescribe el análisis (eso requeriría otro LLM y rompería NFR-10);
    en su lugar, antepone una advertencia visible para el ingeniero y deja
    registro en los logs / LangFuse.
    """
    text = analysis or ""
    violations: list[str] = []

    if len(text.strip()) < 20:
        violations.append("El análisis del agente está vacío o es demasiado corto.")

    for pattern in _OFF_TOPIC_PATTERNS:
        if pattern.search(text):
            violations.append(f"El análisis contiene contenido fuera de tema: '{pattern.pattern}'")

    if not violations:
        return GuardrailResult(passed=True, sanitized=text)

    logger.warning(f"[guardrails.output] {len(violations)} violación(es): {violations}")
    warning_banner = (
        "> ⚠️ **Aviso del guardrail:** la respuesta del agente fue marcada por "
        "posible desviación del tema o contenido incompleto. Revísala con criterio.\n\n"
    )
    return GuardrailResult(
        passed=False,
        sanitized=warning_banner + text,
        violations=violations,
    )
