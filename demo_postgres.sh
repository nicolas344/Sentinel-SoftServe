#!/usr/bin/env bash
# ── Demo Sentinel: Incidente PostgreSQL ──────────────────────────────────────
# Ejecutar desde el Mac: bash demo_postgres.sh
set -euo pipefail

BACKEND="http://100.118.123.112:8000"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV1c3p1cGRlY2l0cXpqdXp0cWVvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NDM3OTcsImV4cCI6MjA4NzAxOTc5N30.mgpAaQviU-dMWohAPwggO3mOJrcWrUR7WlbwQAcLmIk"
SUPABASE_URL="https://euszupdecitqzjuztqeo.supabase.co"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SENTINEL — Demo PostgreSQL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Token
echo ""
echo "[1/4] Obteniendo token de autenticación..."
TOKEN=$(curl -s -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
  -H "apikey: $ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"ricomontesinonicolas@gmail.com","password":"Motoraton_147"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "    ✓ Autenticado"

# 2. Alerta
echo ""
echo "[2/4] Disparando alerta: PostgresConnectionsExhausted..."
curl -s -X POST "$BACKEND/api/alerts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "PostgresConnectionsExhausted",
        "severity": "critical",
        "datname": "sentinel_demo",
        "source_type": "database"
      },
      "annotations": {
        "summary": "BD sentinel_demo sin conexiones disponibles",
        "description": "El pool de conexiones de sentinel_demo está al 100%. Queries nuevas bloqueadas."
      },
      "startsAt": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"
    }]
  }' > /dev/null
echo "    ✓ Alerta enviada — el agente está investigando..."

# 3. Esperar awaiting_approval (máx 90s)
echo ""
echo "[3/4] Esperando análisis del agente..."
INCIDENT_ID=""
for i in $(seq 1 18); do
  sleep 5
  RESULT=$(curl -s "$BACKEND/api/incidents/" -H "Authorization: Bearer $TOKEN" \
    | python3 -c "
import sys,json
data = json.load(sys.stdin)
pg = [i for i in data if 'postgres/sentinel_demo' == (i.get('target') or '') and i.get('status') in ('awaiting_approval','resolved','failed','executing_solution','verifying')]
print(pg[0]['id'] + '|' + pg[0]['status'] + '|' + (pg[0].get('proposed_action') or '') if pg else '')
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
echo "      http://100.118.123.112:5173"
echo ""
read -r -p "  Presiona ENTER cuando hayas aprobado en el dashboard..."

# 4. Ejecutar (por si se aprueba via curl en lugar del UI)
echo ""
echo "[4/4] Verificando resolución..."
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
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Demo PostgreSQL completado"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
