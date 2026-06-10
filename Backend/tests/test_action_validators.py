"""
Tests de los validadores de comandos de routers/actions.py.

Esta es la superficie de seguridad más crítica del backend: todo comando que
el ingeniero aprueba pasa por estos validadores antes de ejecutarse vía
subprocess/SDK. Cubren los casos permitidos y los intentos de inyección.
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-min-32-characters-long")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

from routers.actions import (  # noqa: E402
    _user_identity,
    _validate_container_command,
    _validate_kubernetes_command,
    _validate_pg_command,
)

# ── Contenedores (docker / podman) ───────────────────────────────────────────

class TestContainerValidator:
    @pytest.mark.parametrize("command", [
        "docker restart mi-app",
        "docker logs mi-app",
        "podman restart demo_crash",
        "podman logs web.1",
    ])
    def test_allows_whitelisted_commands(self, command):
        tokens = _validate_container_command(command)
        assert len(tokens) == 3

    @pytest.mark.parametrize("command", [
        "docker rm mi-app",                          # subcomando destructivo
        "docker exec mi-app sh",                     # exec arbitrario
        "docker restart",                            # falta target
        "docker restart app extra",                  # tokens de más
        "kubectl restart mi-app",                    # binario no permitido
        "rm -rf /",                                  # binario arbitrario
        "docker restart app; rm -rf /",              # inyección con ;
        "docker restart $(whoami)",                  # command substitution
        "docker restart `id`",                       # backticks
        "docker restart app && docker rm app",       # encadenamiento
        "docker restart ../etc/passwd",              # path traversal en nombre
        "docker restart -f",                         # flag en lugar de nombre
    ])
    def test_rejects_dangerous_commands(self, command):
        with pytest.raises(HTTPException) as exc:
            _validate_container_command(command)
        assert exc.value.status_code == 400


# ── PostgreSQL ────────────────────────────────────────────────────────────────

class TestPgValidator:
    @pytest.mark.parametrize("command,expected_func", [
        ("pg_stat_activity sentinel_demo", "pg_stat_activity"),
        ("pg_cancel_backend sentinel_demo", "pg_cancel_backend"),
        ("pg_terminate_backend sentinel_demo", "pg_terminate_backend"),
    ])
    def test_allows_whitelisted_functions(self, command, expected_func):
        func, datname = _validate_pg_command(command)
        assert func == expected_func
        assert datname == "sentinel_demo"

    @pytest.mark.parametrize("command", [
        "drop_database sentinel_demo",               # función no permitida
        "pg_terminate_backend",                      # falta datname
        "pg_terminate_backend db extra",             # tokens de más
        "pg_terminate_backend db;drop",              # caracteres inválidos
        "pg_terminate_backend 'db'--",               # intento de SQL injection
    ])
    def test_rejects_dangerous_commands(self, command):
        with pytest.raises(HTTPException) as exc:
            _validate_pg_command(command)
        assert exc.value.status_code == 400


# ── Kubernetes ────────────────────────────────────────────────────────────────

class TestKubernetesValidator:
    @pytest.mark.parametrize("command", [
        "kubectl rollout restart deployment/web",
        "kubectl rollout restart deployment/web -n staging",
        "kubectl delete pod web-abc123",
        "kubectl delete pod web-abc123 -n default",
        "kubectl scale deployment/web --replicas=3",
        "kubectl scale deployment/web --replicas=0 -n prod",
    ])
    def test_allows_whitelisted_commands(self, command):
        tokens = _validate_kubernetes_command(command)
        assert tokens[0] == "kubectl"

    @pytest.mark.parametrize("command", [
        "kubectl delete namespace prod",             # recurso no permitido
        "kubectl delete pod web; rm -rf /",          # metacaracteres
        "kubectl exec web -- sh",                    # exec arbitrario
        "kubectl apply -f evil.yaml",                # apply arbitrario
        "kubectl scale deployment/web --replicas=99",  # fuera de rango
        "kubectl scale deployment/web --replicas=-1",  # negativo
        "kubectl rollout restart statefulset/db",    # solo deployment
        "kubectl delete pod web -n ns | tee /tmp/x",  # pipe
        "kubectl delete pod $(whoami)",              # command substitution
        "docker restart app",                        # binario incorrecto
    ])
    def test_rejects_dangerous_commands(self, command):
        with pytest.raises(HTTPException) as exc:
            _validate_kubernetes_command(command)
        assert exc.value.status_code == 400


# ── Auditoría ─────────────────────────────────────────────────────────────────

class TestUserIdentity:
    def test_prefers_email(self):
        assert _user_identity({"email": "ing@empresa.com", "sub": "uuid-1"}) == "ing@empresa.com"

    def test_falls_back_to_sub(self):
        assert _user_identity({"sub": "uuid-1"}) == "uuid-1"

    def test_unknown_when_empty(self):
        assert _user_identity({}) == "unknown"
