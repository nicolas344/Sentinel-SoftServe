#!/usr/bin/env python3
"""
Seed inicial de ChromaDB con runbooks operacionales para Sentinel.

Ejecutar desde el directorio Backend/:
    python scripts/seed_chromadb.py

Carga los runbooks en colecciones separadas por dominio siguiendo la
convención del framework multiagente:
    - runbooks-docker   (este script)
    - runbooks-podman   (seed propio cuando añadamos el agente)
    - runbooks-postgres (seed propio cuando añadamos el agente)

Si la colección ya tenía datos previos, los elimina y recarga desde cero.
"""

import os
import sys
from urllib.parse import urlparse

# Cargar variables de entorno desde Backend/.env
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import chromadb

CHROMA_HOST = os.getenv("CHROMA_HOST", "http://localhost:8001")
COLLECTION_NAME = "runbooks-docker"  # dominio: docker (convención del framework multiagente)

# ── Runbooks ──────────────────────────────────────────────────────────────────
# Cada runbook tiene: id único, tipo (coincide con incident_type del agente), y texto completo.
# El texto es lo que ChromaDB convierte a vector y el LLM recibe como contexto en Lab 2.

RUNBOOKS = [
    {
        "id": "runbook-oom-001",
        "type": "oom",
        "text": """RUNBOOK: OOM Killed — Contenedor terminado por falta de memoria

TIPO: oom

SEÑALES EN LOGS:
- "Out of memory: Kill process"
- "Killed process" seguido del nombre del proceso
- Container exits con código 137
- "Cannot allocate memory"
- "java.lang.OutOfMemoryError" (aplicaciones JVM)
- "MemoryError" (Python)
- Proceso termina abruptamente sin mensaje de error de la aplicación

DIAGNÓSTICO:
El contenedor fue terminado por el OOM Killer del kernel Linux porque el proceso
excedió el límite de memoria disponible o la memoria del host. Causas comunes:
- Memory leak en la aplicación: uso de memoria crece continuamente sin liberarse
- Pico de tráfico que supera el límite configurado en docker-compose
- Límite de memoria del contenedor demasiado bajo para la carga real
- Carga de datasets o archivos grandes en memoria sin liberarlos

ACCIONES RECOMENDADAS:
1. Verificar el límite de memoria configurado: docker inspect <contenedor> | grep -i memory
2. Reiniciar el contenedor inmediatamente para restaurar el servicio
3. Revisar si el uso de memoria crece de forma sostenida (memory leak) con: docker stats <contenedor>
4. Si el límite es muy bajo para la carga normal: aumentarlo en docker-compose.yml bajo 'mem_limit'
5. Si es memory leak: revisar el código buscando objetos que no se liberan, caches sin límite, conexiones no cerradas
6. Configurar restart: always o restart: on-failure en docker-compose para recuperación automática
7. Agregar monitoreo de memoria en Grafana con alerta antes de llegar al límite (ej. al 80%)

URGENCIA: CRÍTICA — el servicio está completamente caído""",
    },
    {
        "id": "runbook-app-crash-001",
        "type": "app_crash",
        "text": """RUNBOOK: App Crash — Excepción o error fatal en la aplicación

TIPO: app_crash

SEÑALES EN LOGS:
- "Exception", "Error", "Fatal", "Panic", "Segmentation fault"
- Stack traces de la aplicación (líneas con "at ...", "File ...", "goroutine ...")
- "Unhandled exception", "panic: runtime error", "fatal error"
- "Process exited with code 1" o cualquier código distinto de 0
- Mensajes de error seguidos por cierre abrupto del proceso
- "SIGSEGV", "SIGABRT" en aplicaciones de bajo nivel

DIAGNÓSTICO:
La aplicación dentro del contenedor terminó inesperadamente por un error no manejado.
El proceso cerró de forma anormal. Causas comunes:
- Excepción no capturada en el código (NullPointerException, IndexError, etc.)
- Pánico en Go/Rust o excepción no controlada en Python/Java/Node.js
- Corrupción de estado interno por concurrencia
- Bug en el código que se activa bajo condiciones específicas de datos o carga
- División por cero, acceso a memoria inválida, stack overflow

ACCIONES RECOMENDADAS:
1. Localizar el stack trace completo en los logs — identifica el archivo y número de línea del error
2. Reiniciar el contenedor inmediatamente para restaurar el servicio
3. Reproducir el error localmente con los mismos parámetros o datos de entrada
4. Corregir el bug en el código en el punto exacto indicado por el stack trace
5. Agregar manejo de excepciones apropiado (try/catch, recover, etc.) en el punto de fallo
6. Crear un issue en el repositorio con: stack trace completo, condiciones que lo reproducen, datos de entrada
7. Evaluar si el error ocurre bajo condiciones específicas: alta carga, datos corruptos, hora del día

URGENCIA: ALTA — el servicio está caído pero el sistema suele ser recuperable""",
    },
    {
        "id": "runbook-config-error-001",
        "type": "config_error",
        "text": """RUNBOOK: Config Error — Error de configuración al arrancar o durante ejecución

TIPO: config_error

SEÑALES EN LOGS:
- "Environment variable not found", "Missing required env var", "getenv returned nil"
- "Configuration file not found", "No such file or directory" referenciando archivos .env o .yml
- "Invalid configuration", "Failed to parse config", "yaml: unmarshal errors"
- "Permission denied" al leer archivos de configuración
- "KeyError", "undefined", "null" referenciando variables de entorno
- El contenedor termina en los primeros 1-5 segundos de arranque (antes de atender requests)
- "port already in use" (error de configuración de red)

DIAGNÓSTICO:
El contenedor falla durante el arranque o en los primeros momentos de ejecución por
problemas en su configuración. Causas comunes:
- Variables de entorno requeridas no definidas en docker-compose.yml o el .env del contenedor
- Archivo de configuración (.env, config.yml, appsettings.json) faltante o con formato inválido
- Permisos incorrectos en archivos de configuración montados como volúmenes Docker
- Valores de configuración inválidos: URLs mal formadas, puertos fuera de rango, paths inexistentes
- Diferencia entre configuración de desarrollo y producción (variables que existen localmente pero no en el contenedor)

ACCIONES RECOMENDADAS:
1. Revisar los primeros 10 mensajes de log del contenedor — el error de config aparece al inicio
2. Verificar que todas las variables de entorno requeridas estén definidas en docker-compose.yml
3. Comparar la configuración actual con la documentada en README o CLAUDE.md del proyecto
4. Revisar los archivos de configuración montados como volúmenes: docker inspect <contenedor> --format='{{json .Mounts}}'
5. Verificar permisos de archivos de config: ls -la <ruta_del_archivo>
6. Probar la configuración localmente ejecutando el contenedor con las mismas variables antes de redesplegar
7. Agregar validación de variables de entorno al inicio de la aplicación para detectar el problema antes

URGENCIA: MEDIA — generalmente fácil de resolver una vez identificada la variable faltante o el archivo mal configurado""",
    },
    {
        "id": "runbook-dependency-failure-001",
        "type": "dependency_failure",
        "text": """RUNBOOK: Dependency Failure — Servicio externo no disponible

TIPO: dependency_failure

SEÑALES EN LOGS:
- "Connection refused", "ECONNREFUSED", "connection refused"
- "Connection timed out", "dial tcp: i/o timeout", "context deadline exceeded"
- "Database connection failed", "could not connect to server", "FATAL: role does not exist"
- "Service unavailable", "502 Bad Gateway", "503 Service Unavailable"
- Reintentos de conexión fallidos en secuencia antes del crash
- "Max retries exceeded", "retry limit reached"
- "no route to host", "network unreachable"
- "Authentication failed" al conectar a bases de datos o servicios

DIAGNÓSTICO:
El contenedor no puede conectarse a un servicio del que depende. El servicio dependiente
está inaccesible por alguna de estas razones:
- El servicio dependiente está caído o no terminó de arrancar aún (race condition en startup)
- Los contenedores están en redes Docker distintas o el nombre del host es incorrecto
- Credenciales incorrectas para la conexión (usuario, contraseña, token)
- El servicio dependiente está sobrecargado y rechaza nuevas conexiones
- Timeout de conexión demasiado corto configurado en la aplicación
- Reglas de firewall bloqueando el tráfico entre contenedores

ACCIONES RECOMENDADAS:
1. Identificar exactamente qué servicio falla: buscar el nombre del host o IP en los logs de error
2. Verificar si el servicio dependiente está corriendo: docker ps | grep <nombre-del-servicio>
3. Revisar los logs del servicio dependiente: docker logs <nombre-del-servicio> --tail 50
4. Verificar la red Docker: docker network inspect <nombre-de-la-red>
5. Comprobar que los nombres de host en las variables de entorno coincidan con los nombres de los servicios en docker-compose
6. Revisar credenciales de conexión en las variables de entorno
7. Agregar depends_on con healthcheck en docker-compose.yml para asegurar orden de arranque
8. Implementar lógica de reintento con backoff exponencial en la aplicación

URGENCIA: ALTA — el servicio está caído pero la causa es externa y normalmente resoluble""",
    },
    {
        "id": "runbook-memory-pressure-001",
        "type": "memory_pressure",
        "text": """RUNBOOK: Memory Pressure — Contenedor cerca del límite de memoria

TIPO: memory_pressure

SEÑALES EN LOGS:
- Aplicación cada vez más lenta o con latencias altas
- "GC overhead limit exceeded" (JVM) — el garbage collector consume > 98% del tiempo
- "Warning: high memory usage" en logs de la aplicación
- Respuestas HTTP lentas o timeouts intermitentes sin error explícito
- "Allocation failed" o "out of memory" sin que el kernel haya matado el proceso aún
- Logs de caché o pool de conexiones indicando presión: "evicting", "pool exhausted"

DIAGNÓSTICO:
El contenedor está usando más del 85% de su límite de memoria configurado de forma sostenida.
No ha crasheado aún, pero el OOM Kill es inminente si la tendencia continúa. Causas comunes:
- Tráfico o carga más alta de lo habitual que supera el límite configurado
- Memory leak gradual: la memoria crece continuamente sin liberarse entre requests
- Caché en memoria sin límite superior que crece con el tiempo
- Límite de memoria configurado demasiado bajo para la carga normal del servicio
- Carga de datos grandes en memoria (reportes, exports, procesamiento de archivos)

ACCIONES RECOMENDADAS:
1. Verificar el límite actual: docker inspect <contenedor> | grep -i memory
2. Monitorear el uso en tiempo real: docker stats <contenedor> --no-stream
3. Si el límite es bajo para la carga normal: aumentarlo en docker-compose.yml bajo 'mem_limit'
4. Revisar si el uso crece de forma sostenida (leak) o en picos (carga): comparar usage a lo largo del tiempo en Grafana
5. Si es un memory leak: revisar caches sin límite, conexiones no cerradas, objetos acumulados
6. Si es pico de carga: implementar rate limiting o escalar horizontalmente el servicio
7. Configurar alerta de Grafana al 70% para tener más margen de reacción antes del OOM
8. Si el OOM Kill es inminente y el servicio es crítico: reiniciar el contenedor preventivamente

URGENCIA: ALTA — el servicio está degradándose y crasheará pronto si no se actúa""",
    },
    {
        "id": "runbook-cpu-throttling-001",
        "type": "cpu_throttling",
        "text": """RUNBOOK: CPU Throttling — Contenedor limitado por CPU quota

TIPO: cpu_throttling

SEÑALES EN LOGS:
- Latencias de respuesta más altas de lo normal sin errores explícitos
- Timeouts en requests entre microservicios
- "Request timeout" o "context deadline exceeded" en llamadas internas
- Operaciones que normalmente son rápidas toman mucho más tiempo
- Health checks fallando por timeout (no por error de aplicación)
- Logs de la aplicación muestran procesamiento lento sin causa aparente

DIAGNÓSTICO:
El contenedor tiene más del 25% de sus períodos de CPU CFS throttled de forma sostenida.
Esto significa que el proceso quiere usar CPU pero el kernel lo detiene por exceder el CPU limit
configurado en docker-compose. La aplicación no crashea, pero responde lentamente. Causas comunes:
- CPU limit configurado demasiado bajo para la carga actual del servicio
- Pico de carga que supera temporalmente el CPU limit configurado
- Un proceso dentro del contenedor consumiendo CPU de forma anormal (loop infinito, bug)
- Operaciones costosas en CPU (serialización, compresión, criptografía) sin paralelismo

ACCIONES RECOMENDADAS:
1. Verificar el CPU limit actual: docker inspect <contenedor> --format='{{.HostConfig.NanoCpus}}'
2. Identificar qué proceso consume más CPU dentro del contenedor: docker exec <contenedor> top
3. Ver el porcentaje de throttling en Prometheus: container_cpu_cfs_throttled_periods_total
4. Si el CPU limit es bajo para la carga normal: aumentarlo en docker-compose.yml bajo 'cpus'
5. Si es un proceso específico el que consume de más: investigar bug de CPU en ese proceso
6. Si es carga legítima: considerar escalar horizontalmente (más réplicas) en vez de aumentar CPU limit
7. Revisar si hay operaciones bloqueantes en el event loop (Node.js) o sincrónicas innecesarias
8. Agregar métricas de latencia en la aplicación para correlacionar con los períodos de throttling

URGENCIA: MEDIA — el servicio está degradado pero operativo. Actuar antes de que cause timeouts en cascada""",
    },
    {
        "id": "runbook-restart-loop-001",
        "type": "restart_loop",
        "text": """RUNBOOK: Restart Loop — Contenedor reiniciando repetidamente

TIPO: restart_loop

SEÑALES EN LOGS:
- Los logs del contenedor empiezan desde el inicio repetidamente (mensajes de arranque)
- "Starting...", "Initializing..." aparecen múltiples veces en poco tiempo
- El mismo error aparece al final de cada ciclo de logs antes del reinicio
- "Container is restarting" en eventos de Docker
- Los logs de otras herramientas muestran health checks fallando y recuperándose en ciclos
- El servicio aparece como "Up X seconds" repetidamente en docker ps

DIAGNÓSTICO:
El contenedor se reinició 3 o más veces en los últimos 10 minutos. Esto indica que la política
de restart (restart: always o on-failure) está haciendo que Docker lo reinicie automáticamente,
pero el problema persiste. Causas comunes:
- Error fatal que ocurre en el arranque: config_error o dependency_failure al iniciar
- OOM Kill en cada arranque porque el servicio consume demasiada memoria al inicializar
- Dependency no disponible: el servicio depende de una base de datos que no está lista
- Bug introducido recientemente que causa crash inmediato bajo ciertas condiciones
- Exit code != 0 por error de configuración que solo se manifiesta al arrancar

ACCIONES RECOMENDADAS:
1. Ver los logs del ciclo de restart más reciente: docker logs <contenedor> --tail 50
2. Verificar el exit code del último crash: docker inspect <contenedor> --format='{{.State.ExitCode}}'
   - Exit code 137: OOM — ver runbook oom
   - Exit code 1: error de aplicación — ver stack trace en logs
   - Exit code 143: SIGTERM externo — verificar si algo está mandando señales al contenedor
3. Revisar si las dependencias están disponibles: docker ps | grep <servicio-dependiente>
4. Verificar si hubo cambios recientes de código o configuración que coincidan con el inicio del loop
5. Detener el loop temporalmente para investigar: docker update --restart no <contenedor>
6. Revisar variables de entorno y archivos de config necesarios para el arranque
7. Si es dependency_failure: agregar depends_on con healthcheck en docker-compose.yml
8. Una vez corregida la causa raíz, restaurar la política de restart: docker update --restart on-failure <contenedor>

URGENCIA: ALTA — el servicio no está disponible y consume recursos en cada reinicio fallido""",
    },
    {
        "id": "runbook-network-error-001",
        "type": "network_error",
        "text": """RUNBOOK: Network Error — Errores o pérdida de paquetes en red

TIPO: network_error

SEÑALES EN LOGS:
- "Connection reset by peer", "broken pipe", "ECONNRESET"
- "i/o timeout", "dial tcp: i/o timeout", "read tcp: use of closed network connection"
- Errores intermitentes de conexión que no eran persistentes antes
- Timeouts en llamadas a APIs externas o entre microservicios
- "packet loss" en herramientas de diagnóstico de red
- Errores 502 o 504 en gateways que enrutan al contenedor

DIAGNÓSTICO:
El contenedor presenta una tasa elevada de errores de red (receive + transmit errors) o paquetes
descartados. Esto no significa que el servicio esté caído, pero la comunicación de red está
degradada. Causas comunes:
- Saturación del interfaz de red del host Docker
- Conflictos de red entre contenedores en la misma red Docker
- MTU mismatch entre la red del host y la red Docker virtual
- El contenedor receptor está saturado y descarta paquetes entrantes (buffer overflow)
- Problema de hardware o configuración de red del host

ACCIONES RECOMENDADAS:
1. Verificar conectividad básica: docker exec <contenedor> ping <otro-servicio>
2. Inspeccionar la red Docker: docker network inspect <nombre-de-red>
3. Ver las interfaces de red del contenedor: docker exec <contenedor> ip -s link
4. Revisar si el host tiene problemas de red: ifconfig o ip -s link en el host
5. Verificar si el MTU está correctamente configurado en la red Docker (default: 1500)
6. Revisar si hay saturación del host: netstat -s | grep -i error en el host
7. Si los errores son entre contenedores específicos: revisar que estén en la misma red Docker
8. Si el error es con servicios externos: verificar reglas de firewall y DNS del host

URGENCIA: MEDIA — el servicio puede seguir operando pero con degradación. Investigar antes de que cause fallos en cascada""",
    },
    {
        "id": "runbook-disk-pressure-001",
        "type": "disk_pressure",
        "text": """RUNBOOK: Disk Pressure — Disco del contenedor casi lleno

TIPO: disk_pressure

SEÑALES EN LOGS:
- "No space left on device", "ENOSPC", "disk quota exceeded"
- "Failed to write to file", "write error: no space left"
- Base de datos reporta error al crear archivos de WAL o checkpoint
- "Unable to create temporary file" en operaciones de sort o join en bases de datos
- Logs de la aplicación dejan de escribirse o se truncan
- Errores de escritura en cualquier operación de I/O (uploads, logs, caché en disco)

DIAGNÓSTICO:
El contenedor está usando más del 85% de su límite de almacenamiento en disco de forma sostenida.
Si llega al 100%, cualquier operación de escritura fallará, incluyendo logs, WAL de bases de datos,
uploads de archivos y escrituras de caché. Causas comunes:
- Acumulación de logs dentro del contenedor sin rotación configurada
- Base de datos creciendo sin límite en un volumen de capacidad fija
- Archivos temporales que no se limpian (tmp, cache, uploads sin procesar)
- Índices o archivos de datos que crecieron más de lo esperado
- Backups o dumps almacenados localmente en el contenedor

ACCIONES RECOMENDADAS:
1. Identificar qué ocupa más espacio: docker exec <contenedor> df -h && du -sh /* 2>/dev/null | sort -rh | head -20
2. Ver el límite de storage configurado: docker inspect <contenedor> --format='{{.HostConfig.StorageOpt}}'
3. Limpiar logs dentro del contenedor si es posible: docker exec <contenedor> find /var/log -name "*.log" -mtime +7 -delete
4. Limpiar archivos temporales: docker exec <contenedor> find /tmp -mtime +1 -delete
5. Si es una base de datos: revisar si hay archivos WAL o backups acumulados
6. Si el límite de disco es bajo: aumentarlo en docker-compose.yml bajo 'storage_opt'
7. Configurar log rotation en la aplicación o usar el log driver de Docker (json-file con max-size)
8. Considerar mover datos persistentes a volúmenes Docker externos en vez de el filesystem del contenedor

URGENCIA: ALTA — cuando llegue al 100% el servicio fallará con errores de escritura no recuperables""",
    },
    {
        "id": "runbook-unknown-001",
        "type": "unknown",
        "text": """RUNBOOK: Unknown Failure — Causa de fallo no determinada

TIPO: unknown

SEÑALES:
- Logs insuficientes, vacíos o ausentes
- El contenedor termina sin mensaje de error claro
- Exit code no estándar (distinto de 0, 1, 137)
- Logs que no encajan en patrones conocidos de oom, app_crash, config_error o dependency_failure
- El contenedor termina silenciosamente sin ningún output

DIAGNÓSTICO:
No se pudo clasificar el tipo de incidente con la información disponible.
El contenedor terminó inesperadamente sin evidencia clara de la causa en los logs.
Puede deberse a: señal del sistema operativo, problema de hardware, problema de kernel,
proceso padre terminado, o la aplicación tiene logging insuficiente.

ACCIONES DE INVESTIGACIÓN:
1. Revisar el exit code del contenedor: docker inspect <contenedor> --format='{{.State.ExitCode}}'
   - Exit code 0: salida limpia (el proceso decidió terminar)
   - Exit code 1: error genérico de la aplicación
   - Exit code 137: OOM o SIGKILL (reclasificar como oom)
   - Exit code 139: Segmentation fault (reclasificar como app_crash)
   - Exit code 143: SIGTERM (el contenedor fue detenido externamente)
2. Revisar logs completos del contenedor sin límite: docker logs <contenedor> --since 10m
3. Revisar mensajes del kernel: dmesg | tail -50
4. Verificar el estado de salud del host (disco, CPU, memoria del host)
5. Revisar si hubo cambios recientes en el código, configuración o dependencias
6. Aumentar el nivel de logging en la aplicación (DEBUG) y reproducir el problema
7. Escalar al equipo de desarrollo con todos los logs recolectados

URGENCIA: VARIABLE — investigar con calma para determinar la causa real antes de actuar""",
    },
]


# ── Función principal ─────────────────────────────────────────────────────────

def seed():
    parsed = urlparse(CHROMA_HOST)
    client = chromadb.HttpClient(host=parsed.hostname, port=parsed.port or 8000)

    # Eliminar la colección previa (nombre nuevo y también el viejo por compat)
    for legacy_name in (COLLECTION_NAME, "runbooks"):
        try:
            client.delete_collection(legacy_name)
            print(f"Colección '{legacy_name}' previa eliminada.")
        except Exception:
            pass

    collection = client.create_collection(COLLECTION_NAME)

    collection.add(
        documents=[r["text"] for r in RUNBOOKS],
        ids=[r["id"] for r in RUNBOOKS],
        metadatas=[{"type": r["type"], "domain": "docker"} for r in RUNBOOKS],
    )

    print(f"✓ {len(RUNBOOKS)} runbooks cargados en '{COLLECTION_NAME}' ({CHROMA_HOST}).")
    print("  Tipos cargados:", [r["type"] for r in RUNBOOKS])


if __name__ == "__main__":
    seed()
