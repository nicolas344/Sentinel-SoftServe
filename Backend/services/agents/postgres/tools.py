"""
Tools del agente PostgreSQL.

Todas son read-only: consultan vistas del sistema (pg_stat_*) sin modificar nada.
Usan psycopg2 con un rol de solo lectura (pg_monitor en PostgreSQL 10+).

Si la base de datos no está accesible, las tools devuelven un mensaje descriptivo
para que el agente pueda seguir razonando con la información del incidente.

Variables de entorno requeridas:
  POSTGRES_DSN — DSN completo, ej: postgresql://user:pass@host:5432/dbname
  o bien las variables individuales:
  POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
"""

import json
import logging
import os
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

def _get_dsn() -> tuple[Optional[str], Optional[str]]:
    """
    Construye el DSN y verifica la conexión. Reintenta en cada llamada.
    Retorna (dsn, None) si OK, o (None, error_str) si falla.
    """
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        user = os.getenv("POSTGRES_USER", "sentinel")
        password = os.getenv("POSTGRES_PASSWORD", "")
        db = os.getenv("POSTGRES_DB", "sentinel_demo")
        dsn = f"postgresql://{user}:{password}@{host}:{port}/{db}"

    try:
        import psycopg2  # type: ignore
        conn = psycopg2.connect(dsn, connect_timeout=5)
        conn.close()
        logger.info("[pg.tools] Conexión a PostgreSQL verificada.")
        return dsn, None
    except Exception as e:
        logger.warning(f"[pg.tools] PostgreSQL no disponible: {e}")
        return None, str(e)


def _unavailable(tool_name: str, error: str = "") -> str:
    return (
        f"Tool '{tool_name}' no disponible: no se pudo conectar a PostgreSQL "
        f"({error or 'host inaccesible o credenciales incorrectas'}). "
        f"Razona con la información del incidente que ya tienes en contexto."
    )


def _query(dsn: str, sql: str, params=None) -> list[dict]:
    """Ejecuta una query y retorna filas como lista de dicts."""
    import psycopg2  # type: ignore
    import psycopg2.extras  # type: ignore

    conn = psycopg2.connect(dsn, connect_timeout=5)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


# ── Tools expuestas al LLM ────────────────────────────────────────────────────

@tool
def pg_stat_activity(datname: str = "") -> str:
    """Consulta pg_stat_activity: muestra las conexiones activas, queries en
    curso, su estado (active/idle/idle in transaction), duración y si están
    esperando un lock. Filtra por base de datos si se especifica datname.
    Úsalo para diagnosticar conexiones agotadas o queries bloqueadas."""
    dsn, err = _get_dsn()
    if dsn is None:
        return _unavailable("pg_stat_activity", err or "")

    try:
        where = "WHERE datname = %(datname)s" if datname else "WHERE datname NOT IN ('template0', 'template1', '')"
        rows = _query(dsn, f"""
            SELECT
                datname,
                state,
                wait_event_type,
                wait_event,
                COUNT(*)                                        AS conexiones,
                MAX(EXTRACT(EPOCH FROM (now() - query_start))) AS max_duracion_s,
                MAX(EXTRACT(EPOCH FROM (now() - state_change))) AS max_estado_s
            FROM pg_stat_activity
            {where}
            GROUP BY datname, state, wait_event_type, wait_event
            ORDER BY conexiones DESC
            LIMIT 20
        """, {"datname": datname} if datname else None)

        total = _query(dsn, f"""
            SELECT
                datname,
                COUNT(*) AS total_conexiones,
                (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_connections
            FROM pg_stat_activity
            {where}
            GROUP BY datname
        """, {"datname": datname} if datname else None)

        return json.dumps({"resumen_por_estado": rows, "totales": total}, indent=2, default=str)
    except Exception as e:
        return f"Error consultando pg_stat_activity: {e}"


@tool
def pg_stat_database(datname: str = "") -> str:
    """Consulta pg_stat_database: estadísticas acumuladas de la base de datos —
    transacciones commits/rollbacks, deadlocks, lecturas de disco vs cache
    (para calcular cache hit ratio), tuplas insertadas/actualizadas/eliminadas.
    Úsalo para diagnosticar deadlocks, bajo cache hit ratio o crecimiento anormal."""
    dsn, err = _get_dsn()
    if dsn is None:
        return _unavailable("pg_stat_database", err or "")

    try:
        where = "WHERE datname = %(datname)s" if datname else "WHERE datname NOT IN ('template0', 'template1', '')"
        rows = _query(dsn, f"""
            SELECT
                datname,
                numbackends                                              AS conexiones_activas,
                xact_commit                                              AS commits,
                xact_rollback                                            AS rollbacks,
                deadlocks,
                blks_read                                                AS lecturas_disco,
                blks_hit                                                 AS lecturas_cache,
                CASE
                    WHEN (blks_hit + blks_read) > 0
                    THEN ROUND(blks_hit::numeric / (blks_hit + blks_read) * 100, 2)
                    ELSE NULL
                END                                                      AS cache_hit_ratio_pct,
                tup_inserted                                             AS inserts,
                tup_updated                                              AS updates,
                tup_deleted                                              AS deletes,
                pg_size_pretty(pg_database_size(datname))                AS tamano
            FROM pg_stat_database
            {where}
            ORDER BY deadlocks DESC, conexiones_activas DESC
        """, {"datname": datname} if datname else None)

        return json.dumps(rows, indent=2, default=str)
    except Exception as e:
        return f"Error consultando pg_stat_database: {e}"


@tool
def pg_stat_replication() -> str:
    """Consulta pg_stat_replication: estado de las réplicas conectadas al
    primario — lag de escritura, flush y replay en bytes y segundos.
    Solo retorna datos si el servidor es un primario con réplicas.
    Úsalo para diagnosticar PostgresReplicationLag."""
    dsn, err = _get_dsn()
    if dsn is None:
        return _unavailable("pg_stat_replication", err or "")

    try:
        rows = _query(dsn, """
            SELECT
                client_addr,
                state,
                sync_state,
                EXTRACT(EPOCH FROM write_lag)  AS write_lag_s,
                EXTRACT(EPOCH FROM flush_lag)  AS flush_lag_s,
                EXTRACT(EPOCH FROM replay_lag) AS replay_lag_s,
                pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn)   AS sent_lag_bytes,
                pg_wal_lsn_diff(sent_lsn, replay_lsn)              AS replay_lag_bytes
            FROM pg_stat_replication
        """)

        if not rows:
            return "No hay réplicas conectadas o este servidor no es un primario."

        return json.dumps(rows, indent=2, default=str)
    except Exception as e:
        return f"Error consultando pg_stat_replication: {e}"


@tool
def pg_locks(datname: str = "") -> str:
    """Consulta pg_locks junto a pg_stat_activity para detectar locks activos,
    transacciones bloqueadas y cadenas de bloqueo. Úsalo para diagnosticar
    deadlocks o transacciones largas que bloquean otras operaciones."""
    dsn, err = _get_dsn()
    if dsn is None:
        return _unavailable("pg_locks", err or "")

    try:
        where = "AND a.datname = %(datname)s" if datname else ""
        rows = _query(dsn, f"""
            SELECT
                a.datname,
                l.relation::regclass   AS tabla,
                l.mode                 AS modo_lock,
                l.granted,
                a.pid,
                a.state,
                a.wait_event_type,
                a.wait_event,
                EXTRACT(EPOCH FROM (now() - a.query_start)) AS duracion_s,
                LEFT(a.query, 200)     AS query
            FROM pg_locks l
            JOIN pg_stat_activity a ON l.pid = a.pid
            WHERE l.relation IS NOT NULL
              AND a.datname NOT IN ('template0', 'template1', '')
              {where}
            ORDER BY granted ASC, duracion_s DESC NULLS LAST
            LIMIT 20
        """, {"datname": datname} if datname else None)

        if not rows:
            return "No hay locks activos en este momento."

        bloqueados = [r for r in rows if not r.get("granted")]
        return json.dumps({
            "total_locks": len(rows),
            "esperando_lock": len(bloqueados),
            "detalle": rows,
        }, indent=2, default=str)
    except Exception as e:
        return f"Error consultando pg_locks: {e}"


def all_tools() -> list:
    """Lista de tools que el PostgresAgent expone al LLM."""
    return [pg_stat_activity, pg_stat_database, pg_stat_replication, pg_locks]
