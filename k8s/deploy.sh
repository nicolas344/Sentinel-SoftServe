#!/usr/bin/env bash
# deploy.sh — Despliega Sentinel-SoftServe en Kubernetes (orden correcto)
# Uso: ./k8s/deploy.sh
# Requisito: kubectl configurado apuntando al cluster correcto

set -euo pipefail

NAMESPACE="sentinel"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── Verificaciones previas ────────────────────────────────────────────────────

info "Verificando kubectl..."
kubectl version --client 2>/dev/null || error "kubectl no encontrado en PATH"

info "Verificando contexto actual: $(kubectl config current-context)"

# ── Paso 1: Namespace ─────────────────────────────────────────────────────────

info "Paso 1/9: Creando namespace..."
kubectl apply -f "$SCRIPT_DIR/namespace.yaml"

# ── Paso 2: RBAC ─────────────────────────────────────────────────────────────

info "Paso 2/9: Configurando RBAC..."
kubectl apply -f "$SCRIPT_DIR/rbac/"

# ── Paso 3: ConfigMaps ───────────────────────────────────────────────────────

info "Paso 3/9: Aplicando ConfigMaps..."
kubectl apply -f "$SCRIPT_DIR/configmaps/"

# ── Paso 4: Secrets ──────────────────────────────────────────────────────────

info "Paso 4/9: Verificando secrets..."
MISSING_SECRETS=()
for secret in backend-secrets postgres-secrets langfuse-secrets; do
  if ! kubectl get secret "$secret" -n "$NAMESPACE" &>/dev/null; then
    MISSING_SECRETS+=("$secret")
  fi
done

if [ ${#MISSING_SECRETS[@]} -gt 0 ]; then
  warn "Faltan los siguientes secrets: ${MISSING_SECRETS[*]}"
  warn "Consulta k8s/secrets/README.md para crearlos."
  warn "Presiona ENTER para continuar de todas formas (pods quedarán en Pending) o Ctrl+C para abortar..."
  read -r
fi

# ── Paso 5: Storage (PVCs) ───────────────────────────────────────────────────

info "Paso 5/9: Creando PersistentVolumeClaims..."
kubectl apply -f "$SCRIPT_DIR/storage/"

# ── Paso 6: Capa de datos ────────────────────────────────────────────────────

info "Paso 6/9: Desplegando PostgreSQL y ChromaDB..."
kubectl apply -f "$SCRIPT_DIR/data/"

info "Esperando que PostgreSQL esté listo..."
kubectl wait --for=condition=ready pod -l app=postgres -n "$NAMESPACE" --timeout=120s || \
  warn "Timeout esperando PostgreSQL — continúa de todas formas"

# ── Paso 7: LangFuse ─────────────────────────────────────────────────────────

info "Paso 7/9: Desplegando LangFuse..."
kubectl apply -f "$SCRIPT_DIR/langfuse/"

# ── Paso 8: Observabilidad ───────────────────────────────────────────────────

info "Paso 8/9: Desplegando stack de observabilidad (Prometheus, Loki, Grafana, Alertmanager, Promtail)..."
kubectl apply -f "$SCRIPT_DIR/observability/"
kubectl apply -f "$SCRIPT_DIR/exporters/"

# ── Paso 9: Aplicación ───────────────────────────────────────────────────────

info "Paso 9/9: Desplegando Backend y Frontend..."
kubectl apply -f "$SCRIPT_DIR/backend/"
kubectl apply -f "$SCRIPT_DIR/frontend/"

# ── Ingress ───────────────────────────────────────────────────────────────────

info "Aplicando Ingress..."
kubectl apply -f "$SCRIPT_DIR/ingress/"

# ── Esperar pods principales ──────────────────────────────────────────────────

info "Esperando pods del backend..."
kubectl rollout status deployment/backend -n "$NAMESPACE" --timeout=120s || \
  warn "Backend no listo — revisa: kubectl describe pod -l app=backend -n $NAMESPACE"

info "Esperando pods del frontend..."
kubectl rollout status deployment/frontend -n "$NAMESPACE" --timeout=60s || \
  warn "Frontend no listo — revisa: kubectl describe pod -l app=frontend -n $NAMESPACE"

# ── Resumen ───────────────────────────────────────────────────────────────────

echo ""
info "=== Despliegue completado ==="
echo ""
kubectl get pods -n "$NAMESPACE" -o wide
echo ""
kubectl get svc -n "$NAMESPACE"
echo ""
kubectl get ingress -n "$NAMESPACE"
echo ""

MINIKUBE_IP=$(minikube ip 2>/dev/null || echo "127.0.0.1")

warn "Agrega las siguientes líneas a /etc/hosts:"
echo "  $MINIKUBE_IP  sentinel.local"
echo "  $MINIKUBE_IP  grafana.sentinel.local"
echo "  $MINIKUBE_IP  langfuse.sentinel.local"
echo "  $MINIKUBE_IP  prometheus.sentinel.local"
echo "  $MINIKUBE_IP  alertmanager.sentinel.local"
echo ""
info "Accesos:"
echo "  App:          http://sentinel.local"
echo "  API health:   http://sentinel.local/api/health"  # via ingress → nginx → backend (nota: nginx proxy /api/ con trailing slash)
echo "  Grafana:      http://grafana.sentinel.local  (admin / sentinel123)"
echo "  LangFuse:     http://langfuse.sentinel.local"
echo "  Prometheus:   http://prometheus.sentinel.local"
echo "  Alertmanager: http://alertmanager.sentinel.local"
echo ""
warn "Si usas Docker Desktop en lugar de Minikube, ejecuta: minikube tunnel"
