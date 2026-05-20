#!/usr/bin/env python3
"""
Seed de runbooks para el KubernetesAgent en ChromaDB.

Ejecutar desde el directorio Backend/:
    python scripts/seed_kubernetes_runbooks.py

Carga los runbooks en la colección 'runbooks-kubernetes'.
Si la colección ya tenía datos previos, los elimina y recarga desde cero.
"""

import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import chromadb

CHROMA_HOST = os.getenv("CHROMA_HOST", "http://localhost:8001")
COLLECTION_NAME = "runbooks-kubernetes"

RUNBOOKS = [
    {
        "id": "k8s-runbook-crashloop-001",
        "type": "app_crash",
        "text": """RUNBOOK: CrashLoopBackOff en Kubernetes

TIPO: app_crash / restart_loop

SEÑALES:
- kube_pod_container_status_waiting_reason{reason="CrashLoopBackOff"} == 1
- kubectl get pods muestra STATUS: CrashLoopBackOff
- RESTARTS count aumentando continuamente
- Alertas: KubePodCrashLoopBackOff

CAUSAS FRECUENTES:
1. El proceso principal del contenedor termina con código de error distinto de 0
   - Falta de variables de entorno obligatorias
   - Fichero de configuración ausente o malformado
   - Error de inicio de la aplicación (puerto ya en uso, permiso denegado)
2. OOMKill inmediato antes de que el contenedor pueda registrarse como Ready
   (el memory limit es demasiado bajo para el proceso de arranque)
3. Liveness probe demasiado agresiva — mata el contenedor antes de que la app levante
4. Imagen corrupta o entrypoint incorrecto

DIAGNÓSTICO:
1. Ver el estado del pod:
   kubectl get pod <pod-name> -n <namespace> -o wide
2. Ver los logs del contenedor que crashea (ejecución actual):
   kubectl logs <pod-name> -n <namespace> --tail=100
3. Ver los logs de la ejecución anterior (la que crasheó):
   kubectl logs <pod-name> -n <namespace> --previous --tail=100
4. Ver los eventos del pod (Back-off, OOMKill, etc.):
   kubectl describe pod <pod-name> -n <namespace>
5. Inspeccionar el exit code:
   kubectl get pod <pod-name> -o jsonpath='{.status.containerStatuses[0].lastState.terminated}'

ACCIONES RECOMENDADAS:
1. Si es un problema de configuración: corregir el ConfigMap/Secret y hacer rollout restart:
   kubectl rollout restart deployment/<deployment-name> -n <namespace>
2. Si es OOMKill: aumentar el memory limit en el Deployment spec y hacer rollout restart
3. Si es liveness probe: aumentar initialDelaySeconds o failureThreshold
4. Para diagnosticar sin modificar el clúster: ejecutar el contenedor con shell:
   kubectl run debug --image=<imagen> -it --rm -- /bin/sh

PREVENCIÓN:
- Definir siempre REQUESTS y LIMITS de memoria apropiados
- Usar readiness probes separadas de liveness probes
- Testear las imágenes localmente antes de desplegar
- Configurar PodDisruptionBudget para deployments críticos""",
    },
    {
        "id": "k8s-runbook-oom-001",
        "type": "oom",
        "text": """RUNBOOK: OOMKilled en pod Kubernetes

TIPO: oom

SEÑALES:
- kube_pod_container_status_last_terminated_reason{reason="OOMKilled"} == 1
- kubectl describe pod muestra: "OOMKilled" en Last State
- Exit code 137 en el contenedor terminado
- Posible CrashLoopBackOff posterior si el memory leak es recurrente
- Alertas: KubePodOOMKilled

CAUSAS FRECUENTES:
1. Memory limit demasiado bajo para la carga real de trabajo
2. Memory leak en la aplicación (uso de memoria crece indefinidamente)
3. Request de memoria no representa el uso real (sizing incorrecto)
4. Pico de tráfico o carga que excede el límite configurado
5. JVM / Node.js sin límite de heap configurado → usa toda la memoria del contenedor

DIAGNÓSTICO:
1. Confirmar el OOM:
   kubectl describe pod <pod-name> -n <namespace> | grep -A5 "Last State"
2. Ver los logs antes del kill (si quedan):
   kubectl logs <pod-name> -n <namespace> --previous --tail=200
3. Ver los límites configurados:
   kubectl get pod <pod-name> -o jsonpath='{.spec.containers[*].resources}'
4. Ver métricas de memoria (si kube-state-metrics disponible):
   PromQL: container_memory_working_set_bytes{pod="<pod-name>"}

ACCIONES INMEDIATAS:
1. Aumentar el memory limit en el Deployment y hacer rollout restart:
   kubectl rollout restart deployment/<deployment-name> -n <namespace>
2. Si hay pico temporal: reiniciar el pod para liberar memoria mientras se investiga:
   kubectl delete pod <pod-name> -n <namespace>

AJUSTE DE LÍMITES (regla de oro):
- Requests = uso promedio en producción (P50)
- Limits = 2x el request o P99 histórico, lo que sea mayor
- Para JVM: agregar -Xmx al entrypoint para limitar el heap

PREVENCIÓN:
- Configurar Vertical Pod Autoscaler (VPA) para recomendaciones automáticas
- Monitorizar container_memory_working_set_bytes en Grafana
- Configurar alertas de uso >80% del limit antes de llegar al OOM""",
    },
    {
        "id": "k8s-runbook-imagepull-001",
        "type": "dependency_failure",
        "text": """RUNBOOK: ImagePullBackOff / ErrImagePull en Kubernetes

TIPO: dependency_failure / config_error

SEÑALES:
- kubectl get pods muestra: ImagePullBackOff o ErrImagePull en STATUS
- Eventos del pod: "Failed to pull image", "rpc error: code = Unknown"
- El pod nunca llega a estado Running
- waiting reason: ImagePullBackOff

CAUSAS FRECUENTES:
1. Tag de imagen inexistente (typo, tag eliminado del registry)
2. Imagen o repositorio privado sin ImagePullSecret configurado
3. ImagePullSecret expirado o con credenciales incorrectas
4. Registry inaccesible desde el clúster (problema de red, DNS, firewall)
5. Rate limiting del registry (Docker Hub limita pulls de IPs no autenticadas)

DIAGNÓSTICO:
1. Ver el error exacto:
   kubectl describe pod <pod-name> -n <namespace> | grep -A10 "Events"
2. Verificar que la imagen existe:
   docker pull <imagen>:<tag>  (desde fuera del clúster)
3. Verificar el ImagePullSecret configurado:
   kubectl get pod <pod-name> -o jsonpath='{.spec.imagePullSecrets}'
4. Verificar que el Secret existe en el namespace:
   kubectl get secret <secret-name> -n <namespace>
5. Verificar la conectividad al registry desde dentro del clúster:
   kubectl run nettest --image=busybox -it --rm -- wget -q -O- https://registry.hub.docker.com

ACCIONES RECOMENDADAS:
1. Si el tag es incorrecto: actualizar el Deployment con el tag correcto + rollout restart:
   kubectl rollout restart deployment/<deployment-name> -n <namespace>
2. Si falta ImagePullSecret: crear el secret y añadirlo al Deployment
3. Si las credenciales expiraron: renovar el Secret con las nuevas credenciales

CREAR ImagePullSecret:
  kubectl create secret docker-registry <nombre-secret> \\
    --docker-server=<registry-url> \\
    --docker-username=<user> \\
    --docker-password=<token> \\
    -n <namespace>

PREVENCIÓN:
- Usar tags inmutables (SHA digest) en producción en vez de :latest
- Configurar renovación automática de tokens de registry
- Usar un registry privado interno (Harbor, ECR) para evitar rate limits""",
    },
    {
        "id": "k8s-runbook-pending-001",
        "type": "disk_pressure",
        "text": """RUNBOOK: Pod en estado Pending por restricciones de recursos

TIPO: resource_constraint / config_error

SEÑALES:
- kubectl get pods muestra STATUS: Pending durante más de 1-2 minutos
- Eventos: "Insufficient cpu", "Insufficient memory", "Unschedulable"
- 0/N nodes are available: insufficient cpu/memory
- El pod no puede ser programado en ningún nodo

CAUSAS FRECUENTES:
1. Requests de CPU/memoria superiores a los disponibles en cualquier nodo
2. Node selector o affinity sin ningún nodo que haga match
3. Taint en todos los nodos sin Toleration correspondiente en el pod
4. PersistentVolumeClaim (PVC) no satisfecho (StorageClass incorrecta, sin PVs disponibles)
5. Límite de pods por nodo alcanzado (maxPods en kubelet)
6. ResourceQuota del namespace agotada

DIAGNÓSTICO:
1. Ver por qué no puede ser programado:
   kubectl describe pod <pod-name> -n <namespace> | grep -A20 "Events"
2. Ver la capacidad de los nodos:
   kubectl describe nodes | grep -A5 "Allocated resources"
3. Ver las ResourceQuotas del namespace:
   kubectl describe resourcequota -n <namespace>
4. Ver los nodos disponibles y su estado:
   kubectl get nodes -o wide
5. Ver el PVC si aplica:
   kubectl get pvc -n <namespace>

ACCIONES RECOMENDADAS:
1. Si las requests son demasiado altas: reducirlas en el Deployment spec + rollout restart:
   kubectl rollout restart deployment/<deployment-name> -n <namespace>
2. Si la ResourceQuota está agotada: revisar si hay pods zombies que limpiar
3. Si los nodos están llenos: escalar el node group (aumentar máquinas en el clúster)
4. Si es un PVC pending: revisar la StorageClass y crear un PV manualmente si necesario

PREVENCIÓN:
- Definir LimitRange en cada namespace para evitar pods sin limits
- Monitorizar la utilización de nodos (kube_node_status_allocatable vs kube_node_status_capacity)
- Configurar Cluster Autoscaler si hay cargas variables""",
    },
    {
        "id": "k8s-runbook-notready-001",
        "type": "network_error",
        "text": """RUNBOOK: Nodo Kubernetes en estado NotReady

TIPO: network_error / config_error

SEÑALES:
- kubectl get nodes muestra STATUS: NotReady
- kube_node_status_condition{condition="Ready",status="true"} == 0
- Pods en el nodo moviéndose a otros nodos (eviction)
- Alertas: KubeNodeNotReady

CAUSAS FRECUENTES:
1. Kubelet caído o inaccesible en el nodo
2. Presión de disco en el nodo (DiskPressure condition = True)
3. Presión de memoria en el nodo (MemoryPressure condition = True)
4. PID pressure (demasiados procesos)
5. Problema de red — el nodo no puede comunicarse con el API server
6. Certificados de kubelet expirados

DIAGNÓSTICO:
1. Ver las condiciones del nodo:
   kubectl describe node <node-name> | grep -A20 "Conditions"
2. Ver los eventos del nodo:
   kubectl get events -n kube-system --field-selector involvedObject.name=<node-name>
3. SSH al nodo y verificar kubelet:
   systemctl status kubelet
   journalctl -u kubelet --since "10 minutes ago"
4. Ver uso de disco:
   df -h
5. Ver uso de memoria:
   free -h && cat /proc/meminfo | grep MemAvailable

ACCIONES SEGÚN CAUSA:
- DiskPressure: limpiar imágenes sin uso: docker image prune -a
- MemoryPressure: identificar y escalar el proceso que consume memoria
- Kubelet caído: systemctl restart kubelet
- Red: verificar firewall y conectividad al API server

IMPACTO EN EL CLÚSTER:
- Los pods del nodo serán eviccionados si el nodo sigue NotReady >5 min
- Los nuevos pods no serán programados en el nodo NotReady
- Los PVs de tipo local en el nodo pueden quedar inutilizables

PREVENCIÓN:
- Configurar alertas de uso de disco >80% por nodo
- Usar Cluster Autoscaler para drenar nodos con presión y escalar
- Usar DaemonSet de limpieza de imágenes (node-problem-detector)""",
    },
    {
        "id": "k8s-runbook-deployment-mismatch-001",
        "type": "dependency_failure",
        "text": """RUNBOOK: Deployment con réplicas insuficientes (replica mismatch)

TIPO: dependency_failure / app_crash

SEÑALES:
- kube_deployment_status_replicas_available < kube_deployment_spec_replicas
- kubectl get deployment muestra READY: N/M donde N < M
- Alertas: KubeDeploymentReplicasMismatch
- Pods del deployment en CrashLoopBackOff, Pending o Error

CAUSAS FRECUENTES:
1. Pods en CrashLoopBackOff impiden alcanzar el número de réplicas deseado
2. Nodos sin capacidad para programar los pods faltantes
3. Rollout atascado (versión antigua no puede terminar, nueva no puede arrancar)
4. PodDisruptionBudget (PDB) muy restrictivo que bloquea la actualización
5. ImagePullBackOff en la nueva versión durante un rollout

DIAGNÓSTICO:
1. Ver el estado del deployment:
   kubectl describe deployment <deployment-name> -n <namespace>
2. Listar los pods del deployment y su estado:
   kubectl get pods -l app=<selector> -n <namespace>
3. Ver los eventos del deployment:
   kubectl get events -n <namespace> | grep <deployment-name>
4. Ver el historial de rollouts:
   kubectl rollout history deployment/<deployment-name> -n <namespace>
5. Ver el status del rollout en curso:
   kubectl rollout status deployment/<deployment-name> -n <namespace>

ACCIONES RECOMENDADAS:
1. Si el rollout está atascado: hacer rollback a la versión anterior:
   kubectl rollout undo deployment/<deployment-name> -n <namespace>
2. Si los pods tienen CrashLoopBackOff: investigar los logs y hacer rollout restart:
   kubectl rollout restart deployment/<deployment-name> -n <namespace>
3. Si es problema de capacidad: escalar el deployment a menos réplicas temporalmente:
   kubectl scale deployment/<deployment-name> --replicas=<N> -n <namespace>
4. Si el PDB bloquea: revisar con:
   kubectl describe pdb -n <namespace>

PREVENCIÓN:
- Configurar readiness probes correctas para evitar que pods en error reciban tráfico
- Usar strategy.rollingUpdate.maxSurge y maxUnavailable apropiados
- Configurar PDB con minAvailable >= 1 pero no tan restrictivo que bloquee rollouts
- Monitorizar kube_deployment_status_replicas_available en Grafana""",
    },
]


def seed():
    parsed = urlparse(CHROMA_HOST)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8001

    print(f"Conectando a ChromaDB en {host}:{port}...")
    client = chromadb.HttpClient(host=host, port=port)

    try:
        existing = client.get_collection(COLLECTION_NAME)
        print(f"Colección '{COLLECTION_NAME}' ya existe — eliminando para re-seed...")
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    print(f"Colección '{COLLECTION_NAME}' creada.")

    ids = [r["id"] for r in RUNBOOKS]
    docs = [r["text"] for r in RUNBOOKS]
    metas = [{"type": r["type"], "source": "kubernetes-runbook"} for r in RUNBOOKS]

    collection.add(ids=ids, documents=docs, metadatas=metas)
    print(f"✓ {len(RUNBOOKS)} runbooks de Kubernetes indexados en '{COLLECTION_NAME}'.")

    print("\nRunbooks cargados:")
    for r in RUNBOOKS:
        print(f"  • {r['id']} [{r['type']}]")


if __name__ == "__main__":
    seed()
