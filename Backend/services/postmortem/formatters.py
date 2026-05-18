from datetime import datetime, timezone
from typing import Any


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def format_mttr(created_at: str | None, resolved_at: str | None) -> str:
    start = parse_iso(created_at)
    end = parse_iso(resolved_at)
    if not start or not end:
        return "No disponible"

    delta = end - start
    total_sec = int(delta.total_seconds())
    if total_sec < 0:
        return "No disponible"

    mins, sec = divmod(total_sec, 60)
    hrs, mins = divmod(mins, 60)
    if hrs:
        return f"{hrs}h {mins}m {sec}s"
    if mins:
        return f"{mins}m {sec}s"
    return f"{sec}s"


def format_timeline_markdown(events: list[dict[str, Any]]) -> str:
    if not events:
        return "- Sin eventos registrados"

    lines: list[str] = []
    for event in events:
        status = event.get("status", "unknown")
        when = event.get("created_at") or event.get("updated_at") or ""
        pretty_when = when.replace("T", " ").replace("+00:00", " UTC") if when else "sin fecha"
        lines.append(f"- [{pretty_when}] `{status}`")
    return "\n".join(lines)


def format_incident_export_markdown(payload: dict[str, Any]) -> str:
    incident = payload.get("metadata", {})
    evidence = payload.get("evidence", {})
    timeline = payload.get("timeline", [])
    decisions = payload.get("decisions", [])
    actions = payload.get("actions", [])

    lines = [
        f"# Incident Export: {incident.get('title') or 'Sin título'}",
        "",
        "## Metadata",
        f"- ID: `{incident.get('id', 'N/A')}`",
        f"- Severity: `{incident.get('severity', 'N/A')}`",
        f"- Status: `{incident.get('status', 'N/A')}`",
        f"- Source type: `{incident.get('source_type', 'N/A')}`",
        f"- Target: `{incident.get('target', 'N/A')}`",
        f"- Created at: `{incident.get('created_at', 'N/A')}`",
        f"- Resolved at: `{incident.get('resolved_at', 'N/A')}`",
        f"- MTTR: `{incident.get('mttr', 'No disponible')}`",
        "",
        "## Evidence",
        "### Metrics Snapshot",
        "```json",
        str(evidence.get("metrics_snapshot") or {}),
        "```",
        "",
        "### Logs",
        (evidence.get("logs") or "Sin logs")[:4000],
        "",
        "### Agent Reasoning",
        evidence.get("agent_reasoning") or "Sin razonamiento disponible",
        "",
        "## Timeline",
    ]

    if timeline:
        for event in timeline:
            lines.append(
                f"- [{event.get('created_at', 'N/A')}] `{event.get('status', 'unknown')}`"
            )
    else:
        lines.append("- Sin eventos")

    lines.extend(["", "## Decisions"])
    if decisions:
        for decision in decisions:
            lines.append(
                f"- [{decision.get('at', 'N/A')}] {decision.get('type', 'decision')}: {decision.get('detail', '')}"
            )
    else:
        lines.append("- Sin decisiones registradas")

    lines.extend(["", "## Actions"])
    if actions:
        for action in actions:
            lines.extend([
                f"### {action.get('name', 'action')}",
                f"- Command: `{action.get('command', 'N/A')}`",
                f"- Executed at: `{action.get('executed_at', 'N/A')}`",
                f"- Status: `{action.get('status', 'N/A')}`",
                "- Output:",
                "```",
                (action.get("output") or "")[0:3000],
                "```",
                "",
            ])
    else:
        lines.append("- Sin acciones registradas")

    post_mortem = payload.get("post_mortem")
    if post_mortem:
        lines.extend(["", "## Post-Mortem", post_mortem])

    return "\n".join(lines).strip() + "\n"
