"""
Agente de dominio: Docker.

Investiga incidentes de contenedores Docker (OOM, crash, restart loop, etc.)
usando logs de Loki (vía IncidentContext) y el Docker SDK cuando el socket
está disponible.
"""
