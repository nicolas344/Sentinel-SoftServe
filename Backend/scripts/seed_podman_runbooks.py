#!/usr/bin/env python3
"""
Seed de runbooks para el PodmanAgent en ChromaDB.

Ejecutar desde el directorio Backend/:
    python scripts/seed_podman_runbooks.py

Carga los runbooks en la colección 'runbooks-podman'.
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
COLLECTION_NAME = "runbooks-podman"

RUNBOOKS = [
    {
        "id": "podman-runbook-crash-001",
        "type": "app_crash",
        "text": """RUNBOOK: Contenedor caído — PodmanContainerCrashed

TIPO: app_crash

SEÑALES:
- podman_container_state == 4 (exited) de forma inesperada
- Estado del contenedor: exited con exit code distinto de 0
- El servicio deja de responder en su puerto

DIAGNÓSTICO:
En Podman rootless el contenedor es un proceso hijo directo del usuario (no hay daemon).
Si el proceso padre muere (logout de sesión, reboot) los contenedores mueren con él.
Otras causas frecuentes:
- La aplicación lanzó una excepción no capturada y salió (exit code 1)
- Error de configuración al arrancar (variables de entorno faltantes, fichero config ausente)
- El proceso fue terminado por señal (SIGKILL, SIGTERM de un script externo)
- OOM Kill del kernel (verificar con podman inspect —> OOMKilled: true)

DIFERENCIAS PODMAN vs DOCKER:
- No hay restart automático a menos que se configure --restart=always en el pod/contenedor
- En rootless, el socket está en /run/user/<uid>/podman/podman.sock
- Systemd units son la forma canónica de gestionar reinicios en Podman rootless

ACCIONES RECOMENDADAS:
1. Ver el estado y exit code del contenedor:
   podman inspect <nombre> --format "{{.State.ExitCode}} {{.State.Error}}"
2. Ver los últimos logs antes del crash:
   podman logs --tail 100 <nombre>
3. Reiniciar el contenedor:
   podman start <nombre>
4. Si el reinicio falla, ver qué ocurre en tiempo real:
   podman start <nombre> && podman logs -f <nombre>
5. Si es rootless y se cayó por logout: activar linger para que los contenedores
   persistan sin sesión activa:
   loginctl enable-linger <usuario>
6. Para reinicio automático, generar una systemd unit:
   podman generate systemd --name <nombre> --files --new

URGENCIA: ALTA — el servicio está caído""",
    },
    {
        "id": "podman-runbook-oom-001",
        "type": "oom",
        "text": """RUNBOOK: OOM Kill — PodmanContainerOOMKilled

TIPO: oom

SEÑALES:
- increase(podman_container_oom_events_total[5m]) > 0
- podman inspect muestra OOMKilled: true
- El contenedor se reinicia con exit code 137 (SIGKILL)
- Logs muestran: "Killed" o "Out of memory: Kill process"

DIAGNÓSTICO:
El OOM Killer del kernel termina el proceso cuando el sistema no tiene suficiente
memoria física + swap. En Podman rootless los límites de memoria son más estrictos
porque se aplican cgroups v2 por usuario. Causas comunes:
- Memory limit demasiado bajo para la carga actual de la aplicación
- Memory leak en la aplicación (memoria crece indefinidamente)
- Pico de carga inesperado que supera el límite configurado
- JVM o runtime con heap mal configurado para el límite del contenedor

DIFERENCIAS PODMAN vs DOCKER:
- Podman usa cgroups v2 por defecto en sistemas modernos (más granular)
- En rootless, los límites de memoria los gestiona systemd por usuario
- El OOM killer puede afectar al pod completo si se configura con --oom-kill-disable=false

ACCIONES RECOMENDADAS:
1. Confirmar que fue OOM:
   podman inspect <nombre> --format "OOMKilled: {{.State.OOMKilled}}"
2. Ver el uso de memoria antes del OOM (si el contenedor está vivo brevemente):
   podman stats <nombre> --no-stream
3. Aumentar el límite de memoria del contenedor:
   podman update --memory 512m --memory-swap 512m <nombre>
   (o recrea el contenedor con --memory aumentado)
4. Si la aplicación es Java/JVM: configurar -XX:MaxRAMPercentage=75 para que
   respete el límite del contenedor automáticamente
5. Revisar si hay memory leak: monitorear uso de memoria con podman stats durante
   un período de carga normal
6. Si el límite ya es adecuado: revisar el código de la aplicación buscando leaks

URGENCIA: CRÍTICA — el servicio está caído por falta de memoria""",
    },
    {
        "id": "podman-runbook-high-memory-001",
        "type": "high_memory",
        "text": """RUNBOOK: Alta memoria — PodmanContainerHighMemory

TIPO: high_memory

SEÑALES:
- (podman_container_mem_usage_bytes / podman_container_mem_limit_bytes) * 100 > 85
- podman stats muestra MEM USAGE/LIMIT > 85%
- El sistema puede empezar a usar swap si hay disponible

DIAGNÓSTICO:
Uso de memoria por encima del 85% del límite es señal de OOM inminente.
En Podman las causas son similares a Docker pero con matices:
- Caches internas de la aplicación que crecen con el tiempo
- Muchas conexiones activas sin cerrar
- JVM con GC que no libera memoria a tiempo
- Carga de trabajo mayor de la esperada para el límite configurado

ACCIONES RECOMENDADAS:
1. Ver memoria en tiempo real:
   podman stats <nombre> --no-stream --format "table {{.Name}} {{.MemUsage}} {{.MemPerc}}"
2. Si la aplicación tiene API de métricas/actuator: consultar uso interno de heap
3. Aumentar límite de memoria preventivamente:
   podman update --memory 1g <nombre>
4. Forzar GC si es JVM (via JMX o API de administración)
5. Revisar si hay endpoints con alta carga de datos en memoria
6. Si el sistema tiene swap disponible y el contenedor no lo usa:
   podman update --memory-swap -1 <nombre>  # usa swap ilimitado del host

URGENCIA: ALTA — OOM Kill inminente si no se actúa""",
    },
    {
        "id": "podman-runbook-restart-loop-001",
        "type": "restart_loop",
        "text": """RUNBOOK: Restart loop — PodmanContainerRestartLoop

TIPO: restart_loop

SEÑALES:
- changes(podman_container_state[10m]) >= 3
- podman ps muestra STATUS: Restarting
- Los logs muestran el mismo error repetidamente al arrancar
- El exit code es siempre el mismo (típicamente 1, 2 o 127)

DIAGNÓSTICO:
Un contenedor Podman en restart loop está fallando al arrancar o poco después.
Diferencia clave con Docker: en Podman rootless el reinicio automático requiere
que el contenedor tenga --restart=always y que linger esté habilitado para el usuario.
Causas comunes:
- Variable de entorno faltante o incorrecta (el proceso sale con código de error)
- Servicio externo no disponible al arrancar (base de datos, API, etc.)
- Permisos incorrectos en volúmenes montados (rootless cambia el UID del proceso)
- Imagen corrupta o incompatible con la arquitectura del host
- Puerto ya en uso por otro proceso o contenedor

DIFERENCIAS PODMAN vs DOCKER:
- En rootless, los volúmenes del host pueden tener problemas de UID/GID mapping
  (el proceso dentro del contenedor corre como UID 0 mapeado a tu UID real)
- Verificar permisos con: podman unshare ls -la /ruta/en/host

ACCIONES RECOMENDADAS:
1. Ver cuántas veces reinició y el exit code:
   podman inspect <nombre> --format "RestartCount={{.RestartCount}} ExitCode={{.State.ExitCode}}"
2. Ver los logs del último intento (incluye arranques fallidos):
   podman logs --tail 50 <nombre>
3. Detener el loop de reinicios para investigar:
   podman stop <nombre>
4. Probar arranque interactivo para ver el error en tiempo real:
   podman run --rm -it --entrypoint /bin/sh <imagen>
5. Si hay problema de permisos en volúmenes:
   podman unshare chown -R 0:0 /ruta/del/volumen
6. Si el servicio externo no está listo: añadir --health-start-period o lógica de retry
   en la aplicación

URGENCIA: ALTA — el servicio no está disponible""",
    },
    {
        "id": "podman-runbook-config-error-001",
        "type": "config_error",
        "text": """RUNBOOK: Error de configuración — PodmanContainerUnhealthy / config_error

TIPO: config_error

SEÑALES:
- El contenedor arranca pero el servicio no responde
- Logs muestran: "configuration file not found", "invalid environment variable", "permission denied"
- podman_container_state == 2 (stopped) sostenido
- Exit code 1 o 2 (error genérico de la aplicación)

DIAGNÓSTICO:
Errores de configuración en Podman tienen particularidades respecto a Docker:
- Variables de entorno: Podman las pasa directamente sin daemon intermedio; errores
  tipográficos en nombres de variables son comunes
- Montaje de volúmenes: en rootless, los paths del host se remapean a través de
  el namespace de usuario; un path que no existe en el host falla silenciosamente
- Secrets y configs: Podman soporta secrets nativos pero la gestión es diferente
  a Docker Swarm
- Red: en rootless la red de pods usa slirp4netns por defecto; ciertos puertos
  privilegiados (< 1024) requieren configuración adicional

ACCIONES RECOMENDADAS:
1. Ver variables de entorno activas en el contenedor:
   podman exec <nombre> env | sort
2. Verificar que los volúmenes están montados correctamente:
   podman inspect <nombre> --format "{{json .Mounts}}"
3. Si hay secrets, verificar que existen:
   podman secret ls
4. Ejecutar el contenedor con shell para inspeccionar:
   podman run --rm -it --env-file .env <imagen> /bin/sh
5. Si hay problemas de red (puerto en uso):
   ss -tlnp | grep <puerto>
6. Para puertos privilegiados en rootless:
   sysctl net.ipv4.ip_unprivileged_port_start=80

URGENCIA: ALTA — el servicio está caído por mal configuración""",
    },
    {
        "id": "podman-runbook-dependency-001",
        "type": "dependency_failure",
        "text": """RUNBOOK: Fallo de dependencia — PodmanContainerCrashed (dependency_failure)

TIPO: dependency_failure

SEÑALES:
- Logs muestran: "connection refused", "no such host", "timeout", "ECONNREFUSED"
- El contenedor crashea justo después de intentar conectar a otro servicio
- Otros contenedores del mismo pod están en estado error

DIAGNÓSTICO:
En un entorno Podman, las dependencias entre contenedores se gestionan diferente a Docker:
- Los pods de Podman agrupan contenedores (similar a Kubernetes); si el infracontainer
  falla, todos los contenedores del pod fallan
- En rootless, la red entre pods usa slirp4netns: la resolución DNS depende de
  la configuración de /etc/resolv.conf del host
- Los healthchecks de dependencia no están integrados nativamente en Podman
  (no hay depends_on como Docker Compose)

ACCIONES RECOMENDADAS:
1. Ver el estado de todos los contenedores del pod:
   podman pod inspect <nombre-pod> --format "{{json .Containers}}"
2. Verificar conectividad desde dentro del contenedor:
   podman exec <nombre> curl -s http://<servicio>:<puerto>/health
3. Ver si el servicio del que depende está corriendo:
   podman ps --filter name=<servicio-dependencia>
4. Ver logs del servicio dependencia:
   podman logs --tail 30 <nombre-servicio-dependencia>
5. Si el fallo es DNS: verificar resolución desde dentro del contenedor:
   podman exec <nombre> nslookup <hostname>
6. Añadir lógica de retry/backoff en la aplicación o un init container que espere
   a que la dependencia esté lista

URGENCIA: ALTA — el servicio no puede operar sin sus dependencias""",
    },
]


def seed():
    parsed = urlparse(CHROMA_HOST)
    client = chromadb.HttpClient(host=parsed.hostname, port=parsed.port or 8000)

    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"Colección '{COLLECTION_NAME}' previa eliminada.")
    except Exception:
        pass

    collection = client.create_collection(COLLECTION_NAME)

    collection.add(
        documents=[r["text"] for r in RUNBOOKS],
        ids=[r["id"] for r in RUNBOOKS],
        metadatas=[{"type": r["type"], "domain": "podman"} for r in RUNBOOKS],
    )

    print(f"✓ {len(RUNBOOKS)} runbooks cargados en '{COLLECTION_NAME}' ({CHROMA_HOST}).")
    print("  Tipos cargados:", [r["type"] for r in RUNBOOKS])


if __name__ == "__main__":
    seed()
