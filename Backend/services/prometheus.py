"""
Consultas a Prometheus para obtener métricas de contenedores y PostgreSQL.

Se usa en el endpoint GET /api/incidents/{id}/metrics (US-06b).
Si Prometheus no está disponible, todas las funciones retornan None en los campos.

Nota sobre cAdvisor en macOS: las versiones recientes de cAdvisor no exponen el
label `name` en sus métricas — solo exponen `id` (path completo del contenedor,
e.g. /docker/abc123...). Por eso _resolve_container_id() convierte el nombre del
contenedor a su ID completo vía la API de Docker antes de consultar Prometheus.
"""

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
DOCKER_SOCKET  = "unix:///var/run/docker.sock"


def _query(expr: str) -> Optional[float]:
    try:
        r = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": expr},
            timeout=5,
        )
        r.raise_for_status()
        results = r.json().get("data", {}).get("result", [])
        if results:
            return float(results[0]["value"][1])
        return None
    except Exception as e:
        logger.debug(f"[Prometheus] query falló ({expr[:60]}…): {e}")
        return None


def _resolve_container_id(container_name: str) -> Optional[str]:
    """
    Convierte el nombre de un contenedor Docker a su ID completo (64 chars).
    Necesario porque cAdvisor en macOS expone las métricas por id=/docker/<ID>
    en lugar del label name=<nombre>.
    Retorna None si el contenedor no existe o Docker no está disponible.
    """
    try:
        import docker  # importación diferida para no bloquear arranque
        client = docker.from_env()
        container = client.containers.get(container_name)
        return container.id
    except Exception:
        return None


def _container_label(container_name: str) -> str:
    """
    Devuelve el selector PromQL correcto para el contenedor dado.
    - Si el contenedor existe en Docker → id="/docker/<FULL_ID>"
    - Si no (contenedor ya muerto o hash corto) → name="<container_name>" como fallback
    """
    full_id = _resolve_container_id(container_name)
    if full_id:
        return f'id="/docker/{full_id}"'
    # Fallback: intenta con name (funciona si cAdvisor sí exporta ese label)
    return f'name="{container_name}"'


def get_container_metrics(container_name: str) -> dict:
    """
    Métricas en tiempo real de un contenedor Docker/Podman via cAdvisor.
    Retorna siempre un dict con type='container'; los campos pueden ser None
    si el contenedor no existe o Prometheus no está disponible.
    """
    lbl = _container_label(container_name)

    mem_usage = _query(f'container_memory_usage_bytes{{{lbl}}}')
    mem_limit = _query(f'container_spec_memory_limit_bytes{{{lbl}}}')
    cpu_rate  = _query(f'sum(rate(container_cpu_usage_seconds_total{{{lbl}}}[5m]))')
    net_in    = _query(f'sum(rate(container_network_receive_bytes_total{{{lbl}}}[5m]))')
    net_out   = _query(f'sum(rate(container_network_transmit_bytes_total{{{lbl}}}[5m]))')
    restarts  = _query(f'changes(container_start_time_seconds{{{lbl}}}[1h])')

    mem_pct = None
    if mem_usage is not None and mem_limit and mem_limit > 0:
        mem_pct = round(mem_usage / mem_limit * 100, 1)

    return {
        "type":           "container",
        "mem_usage_mb":   round(mem_usage / 1024 / 1024, 1) if mem_usage is not None else None,
        "mem_limit_mb":   round(mem_limit / 1024 / 1024, 1) if mem_limit is not None else None,
        "mem_percent":    mem_pct,
        "cpu_percent":    round(cpu_rate * 100, 2) if cpu_rate is not None else None,
        "net_in_kbps":    round(net_in / 1024, 1) if net_in is not None else None,
        "net_out_kbps":   round(net_out / 1024, 1) if net_out is not None else None,
        "restarts_1h":    int(restarts) if restarts is not None else None,
    }


def get_kubernetes_metrics(pod_name: str, namespace: str = "default") -> dict:
    """
    Métricas de un pod Kubernetes via kube-state-metrics y cAdvisor.
    Retorna siempre un dict con type='kubernetes'; los campos pueden ser None
    si kube-state-metrics no está disponible o el pod no existe en Prometheus.
    """
    ns_pod = f'namespace="{namespace}",pod="{pod_name}"'

    # CPU: uso en cores (kube-state-metrics no provee CPU directamente; usamos cAdvisor)
    cpu_rate   = _query(
        f'sum(rate(container_cpu_usage_seconds_total{{{ns_pod},container!=""}}[5m]))'
    )
    mem_usage  = _query(f'sum(container_memory_working_set_bytes{{{ns_pod},container!=""}})')
    mem_limit  = _query(
        f'sum(container_spec_memory_limit_bytes{{{ns_pod},container!="",container!="POD"}})'
    )

    # kube-state-metrics
    restarts  = _query(f'sum(kube_pod_container_status_restarts_total{{{ns_pod}}})')
    ready     = _query(f'kube_pod_status_ready{{{ns_pod},condition="true"}}')
    phase_run = _query(f'kube_pod_status_phase{{{ns_pod},phase="Running"}}')

    mem_mb       = round(mem_usage / 1024 / 1024, 1) if mem_usage is not None else None
    mem_limit_mb = round(mem_limit / 1024 / 1024, 1) if mem_limit is not None else None
    mem_pct      = None
    if mem_mb is not None and mem_limit_mb and mem_limit_mb > 0:
        mem_pct = round(mem_mb / mem_limit_mb * 100, 1)

    return {
        "type":           "kubernetes",
        "cpu_percent":    round(cpu_rate * 100, 2) if cpu_rate is not None else None,
        "mem_usage_mb":   mem_mb,
        "mem_limit_mb":   mem_limit_mb,
        "mem_percent":    mem_pct,
        "restarts_total": int(restarts) if restarts is not None else None,
        "ready":          bool(ready) if ready is not None else None,
        "running":        bool(phase_run) if phase_run is not None else None,
    }


def get_postgres_metrics(datname: str) -> dict:
    """
    Métricas en tiempo real de una base de datos PostgreSQL via postgres-exporter.
    """
    connections = _query(f'sum(pg_stat_activity_count{{datname="{datname}"}})')
    max_conn    = _query("pg_settings_max_connections")
    db_size     = _query(f'pg_database_size_bytes{{datname="{datname}"}}')
    deadlocks   = _query(f'rate(pg_stat_database_deadlocks{{datname="{datname}"}}[5m])')
    blks_hit    = _query(f'rate(pg_stat_database_blks_hit{{datname="{datname}"}}[5m])')
    blks_read   = _query(f'rate(pg_stat_database_blks_read{{datname="{datname}"}}[5m])')
    longest_tx  = _query(
        f'max(max_over_time(pg_stat_activity_max_tx_duration{{datname="{datname}",state="active"}}[5m]))'
    )

    cache_hit = None
    if blks_hit is not None and blks_read is not None:
        total = blks_hit + blks_read
        if total > 0:
            cache_hit = round(blks_hit / total * 100, 1)

    conn_pct = None
    if connections is not None and max_conn and max_conn > 0:
        conn_pct = round(connections / max_conn * 100, 1)

    return {
        "type":              "postgres",
        "connections":       int(connections) if connections is not None else None,
        "max_connections":   int(max_conn) if max_conn is not None else None,
        "conn_percent":      conn_pct,
        "db_size_mb":        round(db_size / 1024 / 1024, 1) if db_size is not None else None,
        "cache_hit_percent": cache_hit,
        "deadlocks_per_min": round(deadlocks * 60, 2) if deadlocks is not None else None,
        "longest_tx_sec":    round(longest_tx, 1) if longest_tx is not None else None,
    }
