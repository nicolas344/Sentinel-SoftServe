-- ============================================================================
-- 0002 — Endurecimiento para producción
--
-- 1. approved_by: registra quién aprobó/rechazó/pospuso la acción propuesta
--    (auditoría human-in-the-loop).
-- 2. fingerprint: clave de deduplicación que envía Alertmanager en cada
--    alerta. El índice único parcial garantiza a nivel de base de datos que
--    no existan dos incidentes ACTIVOS con el mismo fingerprint, eliminando
--    la race condition del check-then-insert en el backend.
--
-- Esta migración SÍ es segura de ejecutar sobre el proyecto Supabase
-- existente (solo agrega columnas e índices).
-- ============================================================================

alter table public.incidents add column if not exists approved_by text;
alter table public.incidents add column if not exists fingerprint text;

-- Único entre incidentes activos: un fingerprint puede repetirse en el
-- histórico (incidentes resueltos/fallidos) pero no entre los vivos.
create unique index if not exists uniq_incidents_active_fingerprint
    on public.incidents (fingerprint)
    where fingerprint is not null
      and status not in ('resolved', 'failed');
