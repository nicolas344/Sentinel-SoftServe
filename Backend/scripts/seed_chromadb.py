#!/usr/bin/env python3
"""
Seed inicial de ChromaDB con runbooks operacionales para Sentinel.

Ejecutar UNA SOLA VEZ desde el directorio Backend/:
    python scripts/seed_chromadb.py

Si ChromaDB ya tenía datos previos, los elimina y recarga desde cero.
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
    client = chromadb.HttpClient(host=parsed.hostname, port=parsed.port or 8001)

    # Eliminar colección previa para seed limpio
    try:
        client.delete_collection("runbooks")
        print("Colección 'runbooks' previa eliminada.")
    except Exception:
        pass

    collection = client.create_collection("runbooks")

    collection.add(
        documents=[r["text"] for r in RUNBOOKS],
        ids=[r["id"] for r in RUNBOOKS],
        metadatas=[{"type": r["type"]} for r in RUNBOOKS],
    )

    print(f"✓ {len(RUNBOOKS)} runbooks cargados en ChromaDB ({CHROMA_HOST}).")
    print("  Tipos cargados:", [r["type"] for r in RUNBOOKS])


if __name__ == "__main__":
    seed()
