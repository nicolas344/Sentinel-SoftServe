#!/usr/bin/env bash
# ── Demo Sentinel: Incidente Kubernetes ──────────────────────────────────────
# Ejecutar desde el directorio raíz del repo: bash demo_kubernetes.sh
set -euo pipefail

BACKEND="http://localhost:8000"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV1c3p1cGRlY2l0cXpqdXp0cWVvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NDM3OTcsImV4cCI6MjA4NzAxOTc5N30.mgpAaQviU-dMWohAPwggO3mOJrcWrUR7WlbwQAcLmIk"
SERVICE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV1c3p1cGRlY2l0cXpqdXp0cWVvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTQ0Mzc5NywiZXhwIjoyMDg3MDE5Nzk3fQ.6cPnJBvaEctDVJ1NhUahfbf7xWYK69NlyoT43HkR3MI"
SUPABASE_URL="https://euszupdecitqzjuztqeo.supabase.co"
POD="crash-test"
NAMESPACE="default"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SENTINEL — Demo Kubernetes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 0. Limpiar incidentes activos del target
echo ""
echo "[0/6] Limpiando incidentes previos del target '$POD'..."
CLOSED=$(curl -s -X PATCH \
  "$SUPABASE_URL/rest/v1/incidents?target=eq.$POD&container_runtime=eq.kubernetes&status=in.(detected,investigating,analyzed,awaiting_approval,executing_solution,verifying)" \
  -H "apikey: $SERVICE_KEY" \
  -H "Authorization: Bearer $SERVICE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{"status":"failed","action_error":"[RESET] Cerrado por script de demo"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))" 2>/dev/null || echo "0")
echo "    ✓ ${CLOSED} incidente(s) anterior(es) cerrado(s)"

# 1. Desplegar pod crasheante
echo ""
echo "[1/6] Desplegando pod '$POD' que crashea en bucle..."
kubectl delete pod "$POD" --ignore-not-found=true --grace-period=0 2>/dev/null || true
sleep 3
kubectl run "$POD" \
  --image=busybox:latest \
  --restart=Always \
  --namespace="$NAMESPACE" \
  -- /bin/sh -c "echo 'sentinel kubernetes crash test'; sleep 2; exit 1"
echo "    ✓ Pod creado — esperando CrashLoopBackOff (15s)..."
sleep 15
echo "    Estado: $(kubectl get pod $POD -n $NAMESPACE --no-headers 2>/dev/null | awk '{print $3, "restarts:", $4}')"

# 2. Token de autenticación
echo ""
echo "[2/6] Obteniendo token de autenticación..."
TOKEN=$(curl -s -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
  -H "apikey: $ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"ricomontesinonicolas@gmail.com","password":"Motoraton_147"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "    ✓ Autenticado"

# 3. Verificar backend
echo ""
echo "[3/6] Verificando backend..."
HEALTH=$(curl -s "$BACKEND/api/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "error")
echo "    Backend: $HEALTH"
if [ "$HEALTH" != "healthy" ]; then
  echo "    ✗ Backend no disponible. Asegúrate de que docker compose está corriendo."
  exit 1
fi

# 4. Disparar alerta KubePodCrashLoopBackOff
echo ""
echo "[4/6] Disparando alerta: KubePodCrashLoopBackOff..."
RESTARTS=$(kubectl get pod "$POD" -n "$NAMESPACE" --no-headers 2>/dev/null | awk '{print $4}' || echo "3")
curl -s -X POST "$BACKEND/api/alerts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "KubePodCrashLoopBackOff",
        "severity": "critical",
        "name": "'"$POD"'",
        "pod": "'"$POD"'",
        "namespace": "'"$NAMESPACE"'",
        "container": "crash",
        "container_runtime": "kubernetes",
        "source_type": "container"
      },
      "annotations": {
        "summary": "CrashLoopBackOff: '"$POD"' ('"$NAMESPACE"')",
        "description": "El contenedor crash del pod '"$POD"' en el namespace '"$NAMESPACE"' está en CrashLoopBackOff. Reinicios: '"$RESTARTS"'. El proceso muere con exit code 1 de forma continua."
      },
      "startsAt": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"
    }]
  }' > /dev/null
echo "    ✓ Alerta enviada — KubernetesAgent investigando..."

# 5. Esperar análisis del agente (max 120s)
echo ""
echo "[5/6] Esperando análisis del KubernetesAgent..."
INCIDENT_ID=""
for i in $(seq 1 24); do
  sleep 5
  RESULT=$(curl -s "$BACKEND/api/incidents/" -H "Authorization: Bearer $TOKEN" \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
k8s = [i for i in data
       if (i.get('container_runtime') or '') == 'kubernetes'
       and (i.get('target') or '') == '$POD'
       and i.get('status') in ('awaiting_approval','analyzed','resolved','failed','executing_solution','verifying')]
if k8s:
    i = k8s[0]
    print(i['id'] + '|' + i['status'] + '|' + (i.get('proposed_action') or '') + '|' + (i.get('incident_type') or ''))
" 2>/dev/null)
  if [ -n "$RESULT" ]; then
    INCIDENT_ID=$(echo "$RESULT" | cut -d'|' -f1)
    STATUS=$(echo "$RESULT"   | cut -d'|' -f2)
    ACTION=$(echo "$RESULT"   | cut -d'|' -f3)
    ITYPE=$(echo "$RESULT"    | cut -d'|' -f4)
    printf "\r    ✓ Incidente listo en %ds\n" $((i*5))
    break
  fi
  printf "\r    ... %ds (agente investigando)" $((i*5))
done

if [ -z "$INCIDENT_ID" ]; then
  echo ""
  echo "    ✗ Timeout: el agente tardó más de 120s."
  echo "      Revisa: docker logs sentinel-backend | grep -i kubernetes"
  exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Incidente ID:    $INCIDENT_ID"
echo "  Tipo detectado:  $ITYPE"
echo "  Estado:          $STATUS"
echo "  Acción propuesta: $ACTION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$STATUS" = "awaiting_approval" ]; then
  echo ""
  echo "  >>> APRUEBA LA ACCIÓN EN EL DASHBOARD <<<"
  echo "      http://localhost:5173"
  echo ""
  read -r -p "  Presiona ENTER cuando hayas aprobado en el dashboard..."

  # 6. Verificar resolución
  echo ""
  echo "[6/6] Verificando resolución..."
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
fi

echo ""
echo "  Estado pod en Kubernetes:"
kubectl get pod "$POD" -n "$NAMESPACE" 2>/dev/null | tail -1 | awk '{printf "    %-20s %-20s restarts: %s\n", $1, $3, $4}'

echo ""
echo "[Cleanup] Eliminando pod '$POD'..."
kubectl delete pod "$POD" --ignore-not-found=true --grace-period=0 2>/dev/null && echo "    ✓ Pod eliminado"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Demo Kubernetes completado"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
