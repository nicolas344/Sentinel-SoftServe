-- =============================================================================
-- Migración v2 — Sprint 2
-- Prepara el schema de incidents para soporte multi-plataforma
-- (Docker, Podman, PostgreSQL) y habilita cálculo de MTTR.
--
-- EJECUTAR EN: Supabase Dashboard → SQL Editor
-- ORDEN: ejecutar de arriba hacia abajo, una sola vez.
-- =============================================================================

-- 1. Renombrar container_name → target
--    Hace el campo semántico para cualquier tipo de fuente.
--    Afecta: backend (alert_processor, routers, models) y frontend (Dashboard).
ALTER TABLE incidents RENAME COLUMN container_name TO target;

-- 2. source_type — origen del incidente
--    'container' : Docker o Podman
--    'database'  : PostgreSQL (y futuras DB)
--    'manual'    : creado manualmente desde el Dashboard
ALTER TABLE incidents
ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'container'
  CHECK (source_type IN ('container', 'database', 'manual'));

-- 3. container_runtime — runtime del contenedor
--    NULL cuando source_type = 'database' (no aplica)
ALTER TABLE incidents
ADD COLUMN IF NOT EXISTS container_runtime TEXT DEFAULT 'docker'
  CHECK (container_runtime IN ('docker', 'podman') OR container_runtime IS NULL);

-- 4. resolved_at — timestamp de resolución
--    Permite calcular MTTR: resolved_at - created_at
--    Necesario para post-mortem (HU-14)
ALTER TABLE incidents
ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;

-- 5. metrics_snapshot — snapshot puntual de métricas al momento del incidente
--    Contenedores : { cpu_pct, mem_mb, mem_limit_mb, restart_count }
--    PostgreSQL   : { active_connections, max_connections, deadlocks, cache_hit_ratio }
--    Habilita US-06b (visualización de métricas en el panel de detalle)
ALTER TABLE incidents
ADD COLUMN IF NOT EXISTS metrics_snapshot JSONB;

-- 6. Trigger: updated_at automático
--    Antes se actualizaba manualmente en el código — ahora es automático.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS incidents_set_updated_at ON incidents;
CREATE TRIGGER incidents_set_updated_at
  BEFORE UPDATE ON incidents
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 7. Indexes para queries frecuentes
CREATE INDEX IF NOT EXISTS idx_incidents_status
  ON incidents(status);

CREATE INDEX IF NOT EXISTS idx_incidents_source_type
  ON incidents(source_type);

CREATE INDEX IF NOT EXISTS idx_incidents_container_runtime
  ON incidents(container_runtime);

CREATE INDEX IF NOT EXISTS idx_incidents_severity
  ON incidents(severity);

CREATE INDEX IF NOT EXISTS idx_incidents_created_at
  ON incidents(created_at DESC);

-- Index compuesto para deduplicación (query más frecuente en alert_processor.py)
CREATE INDEX IF NOT EXISTS idx_incidents_target_active
  ON incidents(target, status)
  WHERE status IN ('detected', 'investigating');

-- 8. RLS — asegurar acceso correcto para Realtime y frontend
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;

-- Usuarios autenticados pueden leer todos los incidentes
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'incidents'
      AND policyname = 'Usuarios autenticados pueden ver incidentes'
  ) THEN
    CREATE POLICY "Usuarios autenticados pueden ver incidentes"
      ON incidents FOR SELECT
      TO authenticated
      USING (true);
  END IF;
END $$;

-- =============================================================================
-- Schema final de la tabla incidents:
--
-- id                UUID PK
-- title             TEXT NOT NULL
-- target            TEXT NOT NULL          (era container_name)
-- severity          TEXT NOT NULL
-- status            TEXT NOT NULL
-- source_type       TEXT DEFAULT 'container'
-- container_runtime TEXT DEFAULT 'docker'
-- logs              TEXT
-- server_name       TEXT
-- incident_type     TEXT
-- agent_reasoning   TEXT
-- resolved_at       TIMESTAMPTZ
-- metrics_snapshot  JSONB
-- created_at        TIMESTAMPTZ DEFAULT NOW()
-- updated_at        TIMESTAMPTZ (auto via trigger)
-- =============================================================================
