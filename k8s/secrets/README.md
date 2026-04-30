# Secrets — Sentinel-SoftServe

Los secrets **NUNCA** se commitean en git. Créalos manualmente con `kubectl create secret` antes de ejecutar `deploy.sh`.

---

## 1. backend-secrets

Contiene las variables sensibles del backend (API keys, Supabase, LangFuse).

```bash
kubectl create secret generic backend-secrets \
  --namespace=sentinel \
  --from-literal=SUPABASE_URL="https://TU-PROYECTO.supabase.co" \
  --from-literal=SUPABASE_SERVICE_KEY="TU_SUPABASE_SERVICE_ROLE_KEY" \
  --from-literal=SUPABASE_JWT_SECRET="TU_SUPABASE_JWT_SECRET" \
  --from-literal=OPENAI_API_KEY="sk-..." \
  --from-literal=LANGFUSE_PUBLIC_KEY="pk-lf-..." \
  --from-literal=LANGFUSE_SECRET_KEY="sk-lf-..."
```

---

## 2. postgres-secrets

Credenciales del PostgreSQL demo.

```bash
kubectl create secret generic postgres-secrets \
  --namespace=sentinel \
  --from-literal=POSTGRES_USER="sentinel" \
  --from-literal=POSTGRES_PASSWORD="sentinel123" \
  --from-literal=POSTGRES_DB="sentinel_demo"
```

---

## 3. langfuse-secrets

Credenciales internas de LangFuse y su base de datos.

```bash
kubectl create secret generic langfuse-secrets \
  --namespace=sentinel \
  --from-literal=POSTGRES_USER="langfuse" \
  --from-literal=POSTGRES_PASSWORD="langfuse" \
  --from-literal=POSTGRES_DB="langfuse" \
  --from-literal=NEXTAUTH_SECRET="sentinel-nextauth-secret-2024" \
  --from-literal=SALT="sentinel-salt-2024"
```

---

## Verificar que los secrets existen

```bash
kubectl get secrets -n sentinel
```

## Para producción real

En entornos de producción, usa uno de estos enfoques en lugar de `kubectl create secret` directo:

- **Sealed Secrets** (Bitnami): cifra los secrets para poder commitearlos de forma segura
- **External Secrets Operator**: sincroniza desde AWS SSM, Vault, GCP Secret Manager, etc.
- **SOPS**: cifrado de archivos con KMS/GPG

```bash
# Instalar Sealed Secrets controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/latest/download/controller.yaml

# Sellar un secret existente
kubeseal --format yaml < secret.yaml > sealed-secret.yaml
# sealed-secret.yaml SÍ puede commitearse en git
```
