#!/usr/bin/env python3
"""
Seed de runbooks para el PostgresAgent en ChromaDB.

Ejecutar desde el directorio Backend/:
    python scripts/seed_postgres_runbooks.py

Carga los runbooks en la colección 'runbooks-postgres'.
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
COLLECTION_NAME = "runbooks-postgres"

RUNBOOKS = [
    {
        "id": "pg-runbook-connections-001",
        "type": "connection_exhaustion",
        "text": """RUNBOOK: Conexiones agotadas — PostgresConnectionsExhausted

TIPO: connection_exhaustion

SEÑALES:
- pg_stat_activity_count / pg_settings_max_connections > 0.9
- Errores en la aplicación: "too many connections" o "FATAL: connection limit exceeded"
- Nuevas conexiones son rechazadas inmediatamente
- pg_stat_activity muestra muchas conexiones en estado 'idle' o 'idle in transaction'

DIAGNÓSTICO:
PostgreSQL tiene un límite fijo de conexiones simultáneas (max_connections).
Cuando se alcanza, rechaza nuevas conexiones. Las causas más comunes son:
- Connection pool mal configurado (pool demasiado grande o sin límite)
- Conexiones que no se cierran correctamente (leaks en la aplicación)
- Pico de tráfico real que supera la capacidad configurada
- Muchas conexiones 'idle in transaction' que bloquean el pool

ACCIONES RECOMENDADAS:
1. Ver cuántas conexiones hay y en qué estado:
   SELECT state, COUNT(*) FROM pg_stat_activity GROUP BY state ORDER BY count DESC;
2. Ver las conexiones más antiguas:
   SELECT pid, datname, state, query_start, query FROM pg_stat_activity
   ORDER BY query_start ASC NULLS LAST LIMIT 10;
3. Terminar conexiones idle inactivas (> 10 minutos):
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity
   WHERE state = 'idle' AND query_start < now() - interval '10 minutes';
4. Si hay muchas 'idle in transaction': revisar si la aplicación cierra transacciones correctamente
5. Aumentar max_connections en postgresql.conf (requiere reinicio):
   max_connections = 200  -- o el valor apropiado
6. Implementar o ajustar PgBouncer como connection pooler (solución a largo plazo)

URGENCIA: CRÍTICA — nuevas conexiones rechazadas, servicio degradado o caído""",
    },
    {
        "id": "pg-runbook-long-transaction-001",
        "type": "long_running_transaction",
        "text": """RUNBOOK: Transacción larga — PostgresLongRunningTransaction

TIPO: long_running_transaction

SEÑALES:
- pg_stat_activity muestra queries con state='active' por más de 5 minutos
- Bloqueos en cascada: otras queries en estado 'idle in transaction (aborted)'
- Latencias elevadas en el servicio sin error aparente
- pg_locks muestra filas en granted=false esperando a la transacción larga

DIAGNÓSTICO:
Una transacción muy larga puede bloquear VACUUM, AUTOVACUUM y otras operaciones
de mantenimiento. También puede mantener locks que impidan que otras queries
progresen. Las causas comunes son:
- Query pesada sin optimizar (full table scan en tabla grande)
- Transacción abierta que la aplicación olvidó commitear
- Deadlock que se resolvió dejando una transacción abortada abierta
- Backup lógico (pg_dump) corriendo durante horas

ACCIONES RECOMENDADAS:
1. Identificar la transacción larga:
   SELECT pid, datname, state, wait_event_type, wait_event,
          EXTRACT(EPOCH FROM (now() - query_start)) AS duracion_s,
          LEFT(query, 300) AS query
   FROM pg_stat_activity
   WHERE state = 'active' AND query_start < now() - interval '5 minutes'
   ORDER BY duracion_s DESC;
2. Ver si está bloqueando otras:
   SELECT blocking.pid AS bloqueante, blocked.pid AS bloqueado,
          LEFT(blocked.query, 200) AS query_bloqueada
   FROM pg_stat_activity blocking
   JOIN pg_stat_activity blocked ON blocking.pid = ANY(pg_blocking_pids(blocked.pid));
3. Si es seguro cancelar (no es un backup): cancelar la query sin matar la conexión:
   SELECT pg_cancel_backend(<pid>);
4. Si pg_cancel_backend no funciona: terminar la conexión:
   SELECT pg_terminate_backend(<pid>);
5. Revisar el plan de ejecución de la query para optimizarla:
   EXPLAIN ANALYZE <query>;
6. Configurar statement_timeout en postgresql.conf para limitar queries largas

URGENCIA: ALTA — puede estar bloqueando operaciones críticas y AUTOVACUUM""",
    },
    {
        "id": "pg-runbook-deadlock-001",
        "type": "deadlock",
        "text": """RUNBOOK: Deadlock — PostgresDeadLocks

TIPO: deadlock

SEÑALES:
- rate(pg_stat_database_deadlocks[5m]) > 0
- Errores en la aplicación: "ERROR: deadlock detected"
- pg_stat_database muestra xact_rollback aumentando
- Los logs de PostgreSQL muestran "DETAIL: Process X waits for ShareLock on transaction Y"

DIAGNÓSTICO:
Un deadlock ocurre cuando dos o más transacciones se esperan mutuamente en un
ciclo. PostgreSQL lo detecta automáticamente y cancela una de ellas (la víctima).
Los deadlocks son síntoma de un problema de diseño en la aplicación. Causas:
- Acceso a múltiples tablas/filas en orden diferente desde distintas transacciones
- Uso de SELECT FOR UPDATE sin un orden consistente
- Transacciones que hacen múltiples operaciones en orden no determinista

ACCIONES RECOMENDADAS:
1. Ver el historial de deadlocks por BD:
   SELECT datname, deadlocks FROM pg_stat_database WHERE deadlocks > 0 ORDER BY deadlocks DESC;
2. Revisar los logs de PostgreSQL (contienen el detalle completo del deadlock):
   En docker: docker logs sentinel-postgres-demo 2>&1 | grep -A5 "deadlock"
3. Identificar las tablas involucradas revisando los logs — buscar "DETAIL: Process"
4. Asegurar que la aplicación accede a tablas y filas SIEMPRE en el mismo orden
5. Reducir el tamaño de las transacciones: cuanto más corta, menos riesgo de deadlock
6. Usar SELECT FOR UPDATE en el orden correcto y de forma consistente
7. Si los deadlocks son frecuentes: revisar si se pueden reemplazar con optimistic locking

URGENCIA: ALTA — aunque PostgreSQL resuelve el deadlock automáticamente, indica
un problema de concurrencia que puede degradar el rendimiento y causar errores al usuario""",
    },
    {
        "id": "pg-runbook-replication-lag-001",
        "type": "replication_lag",
        "text": """RUNBOOK: Lag de replicación — PostgresReplicationLag

TIPO: replication_lag

SEÑALES:
- pg_replication_lag > 30 segundos
- pg_stat_replication muestra replay_lag_s elevado
- La réplica está atrasada respecto al primario
- Queries en la réplica retornan datos desactualizados

DIAGNÓSTICO:
El lag de replicación ocurre cuando la réplica no puede aplicar los WAL del
primario a la misma velocidad que se generan. Las causas comunes son:
- La réplica está bajo alta carga de CPU o I/O (queries pesadas analíticas)
- El primario genera WAL a una velocidad mayor de lo que la réplica puede aplicar
- Problemas de red entre primario y réplica
- La réplica tiene un hot standby query bloqueando la aplicación de WAL

ACCIONES RECOMENDADAS:
1. Ver el lag actual en el primario:
   SELECT client_addr, state, replay_lag, write_lag, flush_lag
   FROM pg_stat_replication;
2. Verificar si hay queries en la réplica bloqueando la aplicación de WAL:
   En la réplica: SELECT pid, query, state FROM pg_stat_activity WHERE wait_event_type = 'Lock';
3. Si queries analíticas causan el lag: configurar max_standby_streaming_delay
4. Si es problema de red: revisar latencia y bandwidth entre nodos
5. Si el primario genera WAL muy rápido: revisar si hay operaciones masivas de escritura
6. Aumentar wal_receiver_timeout si la conexión se cae frecuentemente
7. Verificar espacio en disco de la réplica (si se llena, deja de aplicar WAL)

URGENCIA: CRÍTICA — si el primario falla, se pueden perder datos no replicados""",
    },
    {
        "id": "pg-runbook-cache-hit-001",
        "type": "low_cache_hit",
        "text": """RUNBOOK: Bajo cache hit ratio — PostgresLowCacheHitRatio

TIPO: low_cache_hit

SEÑALES:
- Cache hit ratio < 90%: blks_hit / (blks_hit + blks_read) < 0.9
- I/O de disco elevado en el servidor
- Queries que normalmente son rápidas empiezan a ser lentas
- pg_stat_database muestra blks_read aumentando significativamente

DIAGNÓSTICO:
PostgreSQL usa shared_buffers como cache en memoria. Si el cache hit ratio baja,
significa que está leyendo muchos datos desde disco en vez de desde memoria.
Las causas comunes son:
- shared_buffers demasiado pequeño para el tamaño del dataset activo
- Queries que hacen full table scan en tablas grandes (no usan índices)
- Dataset activo creció y superó el tamaño del cache configurado
- Tablas con muchos dead tuples (necesitan VACUUM)

ACCIONES RECOMENDADAS:
1. Ver el cache hit ratio por tabla:
   SELECT schemaname, tablename,
          ROUND(heap_blks_hit::numeric / NULLIF(heap_blks_hit + heap_blks_read, 0) * 100, 2) AS cache_hit_pct,
          heap_blks_read AS lecturas_disco
   FROM pg_statio_user_tables
   ORDER BY lecturas_disco DESC LIMIT 20;
2. Identificar queries que hacen muchos seq scan (no usan índices):
   SELECT schemaname, tablename, seq_scan, idx_scan
   FROM pg_stat_user_tables
   ORDER BY seq_scan DESC LIMIT 10;
3. Si hay tablas con muchos seq_scan: revisar si faltan índices con EXPLAIN ANALYZE
4. Aumentar shared_buffers en postgresql.conf (recomendado: 25% de la RAM disponible):
   shared_buffers = 512MB  -- ajustar según RAM disponible
5. Aumentar effective_cache_size para que el planner asuma más cache disponible
6. Ejecutar VACUUM ANALYZE en tablas con muchos dead tuples

URGENCIA: MEDIA — el servicio sigue operativo pero con latencias más altas de lo normal""",
    },
    {
        "id": "pg-runbook-size-growth-001",
        "type": "database_growth",
        "text": """RUNBOOK: Crecimiento acelerado — PostgresDatabaseSizeGrowth

TIPO: database_growth

SEÑALES:
- rate(pg_database_size_bytes[1h]) > 100MB/h
- El disco del servidor de BD está llenándose más rápido de lo normal
- pg_database_size crece de forma no esperada

DIAGNÓSTICO:
El crecimiento acelerado puede indicar inserts masivos legítimos, una operación
que genera muchos datos temporales, o acumulación de dead tuples por falta de VACUUM.
Las causas más comunes son:
- Insert masivo o ETL corriendo en segundo plano
- Tabla de logs o eventos sin rotación/archivado
- Falta de AUTOVACUUM: dead tuples acumulados inflan las tablas
- Índices bloated que crecen de forma descontrolada

ACCIONES RECOMENDADAS:
1. Ver qué tablas están creciendo más:
   SELECT schemaname, tablename,
          pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS tamano_total,
          pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS tamano_datos,
          n_dead_tup AS dead_tuples
   FROM pg_stat_user_tables
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;
2. Verificar si hay un proceso de insert masivo corriendo:
   SELECT datname, state, LEFT(query, 200), query_start FROM pg_stat_activity
   WHERE state = 'active' ORDER BY query_start ASC;
3. Si hay muchos dead tuples: ejecutar VACUUM manualmente:
   VACUUM ANALYZE <nombre_tabla>;
4. Si es una tabla de logs: implementar particionamiento por fecha y archivado
5. Verificar que AUTOVACUUM esté habilitado y configurado correctamente:
   SHOW autovacuum;
6. Si el disco está al límite: identificar y eliminar datos obsoletos con cuidado,
   o ampliar el almacenamiento

URGENCIA: MEDIA — si no se atiende puede llegar a llenar el disco y crashear la BD""",
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
        metadatas=[{"type": r["type"], "domain": "postgres"} for r in RUNBOOKS],
    )

    print(f"✓ {len(RUNBOOKS)} runbooks cargados en '{COLLECTION_NAME}' ({CHROMA_HOST}).")
    print("  Tipos cargados:", [r["type"] for r in RUNBOOKS])


if __name__ == "__main__":
    seed()
