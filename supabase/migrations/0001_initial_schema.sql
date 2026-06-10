-- ============================================================================
-- 0001 — Esquema baseline de Sentinel
--
-- Reconstruido a partir del uso real en el código del backend (routers/ y
-- services/). Si tu proyecto Supabase ya tiene estas tablas creadas desde el
-- dashboard, NO ejecutes esta migración ahí: valida con
--   supabase db pull
-- que el esquema remoto coincida, y usa este archivo como referencia para
-- instalaciones nuevas (self-hosted / otros entornos).
-- ============================================================================

create extension if not exists "pgcrypto";

-- ── incidents ───────────────────────────────────────────────────────────────
create table if not exists public.incidents (
    id                      uuid primary key default gen_random_uuid(),
    title                   text not null,
    target                  text not null,
    severity                text not null check (severity in ('critical', 'high', 'medium', 'low')),
    status                  text not null default 'detected' check (status in (
                                'detected', 'investigating', 'analyzed', 'awaiting_approval',
                                'executing_solution', 'verifying', 'resolved', 'failed'
                            )),
    source_type             text not null default 'container' check (source_type in ('container', 'database', 'manual')),
    container_runtime       text check (container_runtime in ('docker', 'podman', 'kubernetes')),
    incident_type           text,
    logs                    text,
    server_name             text,
    agent_reasoning         text,
    proposed_action         text,
    action_result           text,
    action_error            text,
    metrics_snapshot        jsonb,
    post_mortem_md          text,
    post_mortem_updated_at  timestamptz,
    executed_at             timestamptz,
    resolved_at             timestamptz,
    created_at              timestamptz not null default now(),
    updated_at              timestamptz
);

create index if not exists idx_incidents_status     on public.incidents (status);
create index if not exists idx_incidents_target     on public.incidents (target);
create index if not exists idx_incidents_created_at on public.incidents (created_at desc);

-- ── incident_events (timeline append-only de transiciones de estado) ───────
create table if not exists public.incident_events (
    id          uuid primary key default gen_random_uuid(),
    incident_id uuid not null references public.incidents (id) on delete cascade,
    status      text not null,
    created_at  timestamptz not null default now()
);

create index if not exists idx_incident_events_incident_id
    on public.incident_events (incident_id, created_at);

-- ── Realtime (el frontend escucha cambios en incidents) ────────────────────
do $$
begin
    alter publication supabase_realtime add table public.incidents;
exception
    when duplicate_object then null;
    when undefined_object then null;
end $$;
