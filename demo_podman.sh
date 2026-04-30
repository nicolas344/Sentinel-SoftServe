#!/usr/bin/env bash
# ── Demo Sentinel: Incidente Podman ──────────────────────────────────────────
# Ejecutar desde el servidor Linux: bash demo_podman.sh
set -euo pipefail

BACKEND="http://localhost:8000"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV1c3p1cGRlY2l0cXpqdXp0cWVvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NDM3OTcsImV4cCI6MjA4NzAxOTc5N30.mgpAaQviU-dMWohAPwggO3mOJrcWrUR7WlbwQAcLmIk"
SUPABASE_URL="https://euszupdecitqzjuztqeo.supabase.co"
CONTAINER="test-app"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SENTINEL — Demo Podman"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 0. Asegurar que el contenedor existe y está corriendo
echo ""
echo "[0/5] Preparando contenedor '$CONTAINER'..."
if ! podman ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "    Creando contenedor de demo..."
  podman run -d --name "$CONTAINER" docker.io/library/nginx:alpine > /dev/null
fi
podman start "$CONTAINER" > /dev/null 2>&1 || true
echo "    ✓ Contenedor corriendo"

# 1. Token
echo ""
echo "[1/5] Obteniendo token de autenticación..."
TOKEN=$(curl -s -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
  -H "apikey: $ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"ricomontesinonicolas@gmail.com","password":"Motoraton_147"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "    ✓ Autenticado"

# 2. Detener el contenedor (crash real)
echo ""
echo "[2/5] Simulando crash — deteniendo '$CONTAINER'..."
podman stop "$CONTAINER" > /dev/null
echo "    ✓ Contenedor detenido ($(podman ps -a --filter "name=^${CONTAINER}$" --format '{{.Status}}'))"

# 3. Alerta
echo ""
echo "[3/5] Disparando alerta: PodmanContainerCrashed..."
curl -s -X POST "$BACKEND/api/alerts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "PodmanContainerCrashed",
        "severity": "high",
        "name": "'"$CONTAINER"'",
        "container_runtime": "podman",
        "source_type": "container"
      },
      "annotations": {
        "summary": "Contenedor Podman '"$CONTAINER"' caído",
        "description": "El contenedor '"$CONTAINER"' terminó de forma inesperada."
      },
      "startsAt": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"
    }]
  }' > /dev/null
echo "    ✓ Alerta enviada — el agente está investigando..."

# 4. Esperar awaiting_approval (máx 90s)
echo ""
echo "[4/5] Esperando análisis del agente..."
INCIDENT_ID=""
for i in $(seq 1 18); do
  sleep 5
  RESULT=$(curl -s "$BACKEND/api/incidents/" -H "Authorization: Bearer $TOKEN" \
    | python3 -c "
import sys,json
data = json.load(sys.stdin)
pm = [i for i in data if (i.get('container_runtime') or '') == 'podman'
      and (i.get('target') or '') == 'test-app'
      and i.get('status') in ('awaiting_approval','resolved','failed','executing_solution','verifying')]
print(pm[0]['id'] + '|' + pm[0]['status'] + '|' + (pm[0].get('proposed_action') or '') if pm else '')
" 2>/dev/null)
  if [ -n "$RESULT" ]; then
    INCIDENT_ID=$(echo "$RESULT" | cut -d'|' -f1)
    STATUS=$(echo "$RESULT" | cut -d'|' -f2)
    ACTION=$(echo "$RESULT" | cut -d'|' -f3)
    printf "\r    ✓ Incidente listo en %ds — status: %s\n" $((i*5)) "$STATUS"
    break
  fi
  printf "\r    ... %ds" $((i*5))
done

if [ -z "$INCIDENT_ID" ]; then
  echo "    ✗ Timeout: el agente tardó más de 90s. Revisa los logs del backend."
  exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Incidente:  $INCIDENT_ID"
echo "  Acción:     $ACTION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  >>> APRUEBA LA ACCIÓN EN EL DASHBOARD <<<"
echo "      http://localhost:5173"
echo ""
read -r -p "  Presiona ENTER cuando hayas aprobado en el dashboard..."

# 5. Confirmar resolución
echo ""
echo "[5/5] Verificando resolución..."
for i in $(seq 1 12); do
  sleep 5
  FINAL=$(curl -s "$BACKEND/api/incidents/$INCIDENT_ID" -H "Authorization: Bearer $TOKEN" \
    | python3 -c "import sys,json; i=json.load(sys.stdin); print(i.get('status',''))" 2>/dev/null)
  if [ "$FINAL" = "resolved" ] || [ "$FINAL" = "failed" ]; then
    echo "    ✓ Estado final: $FINAL"
    break
  fi
  printf "\r    ... esperando resolución %ds" $((i*5))
done

echo ""
echo "  Estado contenedor en Podman:"
podman ps --filter "name=^${CONTAINER}$" --format "    {{.Names}}  {{.Status}}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Demo Podman completado"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
