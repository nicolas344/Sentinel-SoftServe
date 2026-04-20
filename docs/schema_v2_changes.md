# Schema v2 — Cambios realizados

> Rama: `feature/supabase-schema-v2`
> Fecha: 2026-04-20
> Autor: Nicolas Rico

---

## Por qué se hicieron estos cambios

El schema original solo soportaba Docker. Para integrar Podman y PostgreSQL en Sprint 2
necesitábamos un schema más genérico que maneje múltiples fuentes de incidentes.

---

## 1. Migración Supabase

Archivo: `supabase/migrations/20260420_schema_v2.sql`

**Ejecutar una sola vez en Supabase Dashboard → SQL Editor.**

| Cambio | Detalle |
|--------|---------|
| `container_name` → `target` | Renombrado para ser genérico (sirve para containers, DBs, etc.) |
| `source_type` TEXT | Nueva columna: `'container'` / `'database'` / `'manual'` |
| `container_runtime` TEXT | Nueva columna: `'docker'` / `'podman'` / `NULL` |
| `resolved_at` TIMESTAMPTZ | Timestamp de resolución — habilita cálculo de MTTR |
| `metrics_snapshot` JSONB | Snapshot de métricas al momento del incidente (para US-06b) |
| Trigger `updated_at` | Antes se actualizaba manual en código, ahora es automático |
| 6 indexes | `status`, `source_type`, `container_runtime`, `severity`, `created_at`, `target+status` |
| RLS policy | SELECT para usuarios autenticados |

---

## 2. Backend

### `Backend/models/incident.py`
- Renombrado `container_name` → `target`
- Eliminado `exit_code` (no existía en la DB — inconsistencia)
- Agregados: `source_type`, `container_runtime`, `resolved_at`, `metrics_snapshot`
- Agregados type aliases: `SourceType`, `RuntimeType`, `SeverityType`, `StatusType`

### `Backend/services/alert_processor.py`
- Renombrado `container_name` → `target` en todo el archivo
- `SEVERITY_MAP` extendido con alertas de **Podman** (8) y **PostgreSQL** (6)
- `_extract_container_id()` ahora recibe `runtime` para manejar IDs de Podman (sin prefijo `/docker/`)
- `process_prometheus_alert()` extrae `source_type` y `container_runtime` de los labels de la alerta
- Retorna 6 valores en la tupla (antes 5) — agrega `container_runtime`
- `_resolve_incident()` ahora guarda `resolved_at` al cerrar el incidente

### `Backend/routers/alerts.py`
- Desempaqueta el nuevo sexto valor `container_runtime`
- Pasa `labels={"container_runtime": container_runtime}` al engine para que el Supervisor enrute al agente correcto

### `Backend/routers/incidents.py`
- `container_name` → `target` en `CreateIncidentManual`
- `list_incidents` ahora acepta filtros opcionales: `source_type`, `container_runtime`, `severity`, `status`
- `create_incident` agrega `source_type` al incident dict

### `Backend/services/langgraph_engine.py`
- Acepta nuevo kwarg `labels: dict | None = None`
- Pasa `labels` al `IncidentContext` para que `DockerAgent.matches()` / `PodmanAgent.matches()` funcionen correctamente

---

## 3. Frontend

### `Frontend/src/pages/Dashboard.jsx`
- `incident.container_name` → `incident.target` en la lista de incidentes
- `selected.container_name` → `selected.target` en el panel de detalle
- Label "Contenedor" → "Recurso" en la MetaCard del detalle
- Nuevo componente `RuntimeBadge` que muestra badge según runtime/source:
  - `docker` → azul
  - `podman` → morado
  - `database` → ámbar
- `RuntimeBadge` aparece en la lista y en el panel de detalle

### `Frontend/src/components/CreateIncidentModal.jsx`
- Estado `containerName` → `target`
- Nuevo estado `sourceType` (default: `'manual'`)
- Nuevo selector de tipo de recurso: Manual / Contenedor / Base de datos
- Campo "Contenedor / Servicio" → "Recurso" con placeholder dinámico según `sourceType`
- Payload del POST incluye `target` y `source_type`

---

## Cómo probar los cambios

```bash
# 1. Asegurarse de estar en la branch correcta
git checkout feature/supabase-schema-v2

# 2. Levantar el stack
docker compose up -d

# 3. Verificar que el backend arranca sin errores
docker compose logs -f backend

# 4. Crear un incidente manual desde el Dashboard
#    → debe verse el badge de runtime en la lista
#    → el campo se llama "Recurso" en el modal

# 5. Simular un crash de Docker para verificar el pipeline automático
docker run -d --name test-crash alpine sh -c "sleep 2 && exit 1"
# ~20s después debe aparecer el incidente con container_runtime: "docker"
```

---

## Siguiente paso

Hacer el PR de esta branch → `main` y ejecutar la migración SQL en Supabase.
