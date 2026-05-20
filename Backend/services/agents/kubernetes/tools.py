"""
Tools del KubernetesAgent.

Todas son read-only: consultan el estado del clúster Kubernetes sin modificar nada.
Usan el SDK oficial de Python para Kubernetes.

Orden de carga de configuración:
  1. K8S_PROXY_URL env var  → conexión HTTP directa al proxy (Docker Desktop / dev local)
  2. In-cluster config      → cuando el backend corre como pod dentro del clúster
  3. KUBECONFIG / ~/.kube/config → kubeconfig estándar (producción / CI)
"""

import json
import logging
import os
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_K8S_AVAILABLE: Optional[bool] = None
_K8S_ERROR: Optional[str] = None


def _init_k8s() -> bool:
    """
    Inicializa la configuración del SDK de Kubernetes.
    Cachea el resultado (bueno o malo) para no reintentar en cada tool call.

    K8S_PROXY_URL: URL de un kubectl proxy HTTP (ej. http://192.168.1.2:8555).
    Útil cuando el backend corre en Docker Desktop y no puede alcanzar el API
    server directamente; se arranca el proxy en la IP LAN del host antes del demo.
    """
    global _K8S_AVAILABLE, _K8S_ERROR
    if _K8S_AVAILABLE is not None:
        return _K8S_AVAILABLE

    try:
        import kubernetes  # type: ignore

        proxy_url = os.getenv("K8S_PROXY_URL", "").strip()
        if proxy_url:
            cfg = kubernetes.client.Configuration()
            cfg.host = proxy_url
            cfg.verify_ssl = False
            kubernetes.client.Configuration.set_default(cfg)
            logger.info(f"[k8s.tools] Usando proxy HTTP: {proxy_url}")
        else:
            try:
                kubernetes.config.load_incluster_config()
                logger.info("[k8s.tools] Configuración in-cluster cargada")
            except kubernetes.config.config_exception.ConfigException:
                kubernetes.config.load_kube_config()
                logger.info("[k8s.tools] Kubeconfig local cargado")

        _K8S_AVAILABLE = True
    except Exception as e:
        _K8S_ERROR = str(e)
        _K8S_AVAILABLE = False
        logger.warning(f"[k8s.tools] SDK de Kubernetes no disponible: {e}")

    return _K8S_AVAILABLE


def _unavailable(tool_name: str) -> str:
    return (
        f"Tool '{tool_name}' no disponible: el backend no puede conectarse al "
        f"clúster Kubernetes ({_K8S_ERROR or 'kubeconfig no encontrado'}). "
        f"Razona con los logs que ya tienes en contexto."
    )


def _container_state_str(state) -> str:
    """Convierte un objeto ContainerState del SDK en una cadena legible."""
    if state is None:
        return "Unknown"
    if state.waiting:
        return f"Waiting({state.waiting.reason or 'unknown'})"
    if state.running:
        started = str(state.running.started_at)[:19] if state.running.started_at else "?"
        return f"Running(since={started})"
    if state.terminated:
        t = state.terminated
        return f"Terminated(reason={t.reason or 'unknown'}, exit={t.exit_code})"
    return "Unknown"


@tool
def get_pod_status(pod_name: str, namespace: str = "default") -> str:
    """Obtiene el estado completo de un pod Kubernetes: fase (Running/Pending/Failed),
    condiciones (Ready, PodScheduled), estado por contenedor (incluyendo
    CrashLoopBackOff, OOMKilled, ImagePullBackOff), restart count, nodo asignado
    y dirección IP. Úsalo primero ante cualquier incidente de pod."""
    if not _init_k8s():
        return _unavailable("get_pod_status")
    try:
        import kubernetes  # type: ignore

        v1 = kubernetes.client.CoreV1Api()
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)

        containers = []
        for cs in (pod.status.container_statuses or []):
            containers.append({
                "name": cs.name,
                "image": cs.image,
                "ready": cs.ready,
                "restart_count": cs.restart_count,
                "state": _container_state_str(cs.state),
                "last_state": _container_state_str(cs.last_state),
            })

        conditions = [
            {
                "type": c.type,
                "status": c.status,
                "reason": c.reason or "",
                "message": (c.message or "")[:120],
            }
            for c in (pod.status.conditions or [])
        ]

        return json.dumps({
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "phase": pod.status.phase,
            "node": pod.spec.node_name,
            "pod_ip": pod.status.pod_ip,
            "start_time": str(pod.status.start_time)[:19] if pod.status.start_time else None,
            "containers": containers,
            "conditions": conditions,
        }, indent=2)
    except Exception as e:
        return f"Error obteniendo estado del pod '{pod_name}' en '{namespace}': {e}"


@tool
def describe_pod(pod_name: str, namespace: str = "default") -> str:
    """Descripción detallada de un pod: especificación completa de recursos
    (CPU/memoria requests y limits), variables de entorno relevantes, volúmenes
    montados, probes de liveness/readiness, y estado de init containers.
    Úsalo cuando necesitas ver la configuración completa del pod."""
    if not _init_k8s():
        return _unavailable("describe_pod")
    try:
        import kubernetes  # type: ignore

        v1 = kubernetes.client.CoreV1Api()
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)

        containers_spec = []
        for c in (pod.spec.containers or []):
            resources = c.resources or kubernetes.client.V1ResourceRequirements()
            liveness = None
            readiness = None
            if c.liveness_probe:
                liveness = str(c.liveness_probe.to_dict())[:200]
            if c.readiness_probe:
                readiness = str(c.readiness_probe.to_dict())[:200]
            containers_spec.append({
                "name": c.name,
                "image": c.image,
                "resources": {
                    "requests": (resources.requests or {}),
                    "limits": (resources.limits or {}),
                },
                "liveness_probe": liveness,
                "readiness_probe": readiness,
                "env_count": len(c.env or []),
            })

        volumes = [v.name for v in (pod.spec.volumes or [])]
        init_containers = [
            {"name": ic.name, "image": ic.image}
            for ic in (pod.spec.init_containers or [])
        ]

        return json.dumps({
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "labels": pod.metadata.labels or {},
            "node_selector": pod.spec.node_selector or {},
            "service_account": pod.spec.service_account_name,
            "restart_policy": pod.spec.restart_policy,
            "containers": containers_spec,
            "init_containers": init_containers,
            "volumes": volumes,
        }, indent=2)
    except Exception as e:
        return f"Error describiendo pod '{pod_name}' en '{namespace}': {e}"


@tool
def get_pod_logs(pod_name: str, namespace: str = "default", tail: int = 100) -> str:
    """Obtiene las últimas líneas de logs de un pod Kubernetes (incluyendo pods
    terminados, usando previous=True si el pod está en CrashLoopBackOff).
    Úsalo para ver el error exacto que causó que el proceso muriera."""
    if not _init_k8s():
        return _unavailable("get_pod_logs")
    try:
        import kubernetes  # type: ignore

        v1 = kubernetes.client.CoreV1Api()
        tail = max(1, min(tail, 500))

        try:
            logs = v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=tail,
                timestamps=True,
            )
            if logs:
                return logs
        except kubernetes.client.exceptions.ApiException:
            pass

        # Si el contenedor no está corriendo, intentar con previous=True
        try:
            logs = v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=tail,
                timestamps=True,
                previous=True,
            )
            return (
                f"[Logs de ejecución anterior]\n{logs}" if logs
                else "(sin logs de ejecución anterior)"
            )
        except Exception as e2:
            return f"No se pudieron obtener logs de '{pod_name}': {e2}"

    except Exception as e:
        return f"Error obteniendo logs del pod '{pod_name}' en '{namespace}': {e}"


@tool
def get_pod_events(pod_name: str, namespace: str = "default") -> str:
    """Lista los eventos de Kubernetes asociados a un pod específico: backoffs,
    OOMKills, fallos de scheduling, problemas de imagen, montaje de volúmenes.
    Los eventos son la fuente más directa del motivo de un fallo."""
    if not _init_k8s():
        return _unavailable("get_pod_events")
    try:
        import kubernetes  # type: ignore

        v1 = kubernetes.client.CoreV1Api()
        events = v1.list_namespaced_event(
            namespace=namespace,
            field_selector=f"involvedObject.name={pod_name}",
        )

        from datetime import datetime, timezone
        _epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

        result = []
        for e in sorted(
            events.items,
            key=lambda x: x.last_timestamp or x.event_time or _epoch,
            reverse=True,
        )[:20]:
            result.append({
                "type": e.type,
                "reason": e.reason,
                "message": (e.message or "")[:200],
                "count": e.count,
                "first_time": str(e.first_timestamp)[:19] if e.first_timestamp else None,
                "last_time": str(e.last_timestamp)[:19] if e.last_timestamp else None,
            })

        if not result:
            return f"No se encontraron eventos para el pod '{pod_name}' en '{namespace}'."
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error obteniendo eventos del pod '{pod_name}' en '{namespace}': {e}"


@tool
def get_deployment_status(deployment_name: str, namespace: str = "default") -> str:
    """Obtiene el estado de un Deployment Kubernetes: réplicas deseadas vs.
    disponibles vs. ready, estrategia de actualización, condiciones (Available,
    Progressing), y selector de pods. Úsalo para diagnosticar replica mismatch
    o rollouts atascados."""
    if not _init_k8s():
        return _unavailable("get_deployment_status")
    try:
        import kubernetes  # type: ignore

        apps_v1 = kubernetes.client.AppsV1Api()
        dep = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)

        status = dep.status
        spec = dep.spec
        conditions = [
            {
                "type": c.type, "status": c.status,
                "reason": c.reason or "", "message": (c.message or "")[:120],
            }
            for c in (status.conditions or [])
        ]

        strategy = spec.strategy
        strategy_type = strategy.type if strategy else "RollingUpdate"

        return json.dumps({
            "name": dep.metadata.name,
            "namespace": dep.metadata.namespace,
            "replicas_desired": spec.replicas,
            "replicas_ready": status.ready_replicas or 0,
            "replicas_available": status.available_replicas or 0,
            "replicas_updated": status.updated_replicas or 0,
            "observed_generation": status.observed_generation,
            "strategy": strategy_type,
            "conditions": conditions,
            "labels": dep.metadata.labels or {},
            "selector": (spec.selector.match_labels or {}) if spec.selector else {},
        }, indent=2)
    except Exception as e:
        return f"Error obteniendo estado del deployment '{deployment_name}' en '{namespace}': {e}"


@tool
def list_failing_pods(namespace: str = "default") -> str:
    """Lista todos los pods en el namespace que NO están en estado Running/Succeeded:
    Pending, Failed, Unknown, o Running pero con contenedores en CrashLoopBackOff /
    ImagePullBackOff / OOMKilled. Úsalo para ver el panorama general del namespace
    y encontrar pods relacionados al incidente."""
    if not _init_k8s():
        return _unavailable("list_failing_pods")
    try:
        import kubernetes  # type: ignore

        v1 = kubernetes.client.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace=namespace)

        failing = []
        for pod in pods.items:
            phase = pod.status.phase or "Unknown"
            if phase in ("Succeeded",):
                continue

            problem = None
            if phase not in ("Running",):
                problem = f"phase={phase}"
            else:
                for cs in (pod.status.container_statuses or []):
                    if cs.state and cs.state.waiting:
                        reason = cs.state.waiting.reason or "Waiting"
                        if reason not in ("ContainerCreating", "PodInitializing"):
                            problem = f"{cs.name}:{reason}"
                            break
                    if not cs.ready:
                        problem = problem or f"{cs.name}:NotReady"

            if problem:
                restart_count = sum(
                    cs.restart_count for cs in (pod.status.container_statuses or [])
                )
                failing.append({
                    "name": pod.metadata.name,
                    "phase": phase,
                    "problem": problem,
                    "restart_count": restart_count,
                    "node": pod.spec.node_name,
                })

        if not failing:
            return f"Todos los pods en '{namespace}' están en buen estado."
        return json.dumps(failing, indent=2)
    except Exception as e:
        return f"Error listando pods fallidos en '{namespace}': {e}"


def all_tools() -> list:
    return [
        get_pod_status,
        describe_pod,
        get_pod_logs,
        get_pod_events,
        get_deployment_status,
        list_failing_pods,
    ]
