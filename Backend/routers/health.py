import os
import time

import requests
from fastapi import APIRouter

from db.supabase_client import supabase

router = APIRouter(prefix="/api", tags=["health"])

_SERVICES = {
    "prometheus":   os.getenv("PROMETHEUS_URL",   "http://localhost:9090"),
    "loki":         os.getenv("LOKI_URL",         "http://localhost:3100"),
    "chromadb":     os.getenv("CHROMA_HOST",      "http://localhost:8001"),
    "alertmanager": os.getenv("ALERTMANAGER_URL", "http://localhost:9093"),
    "langfuse":     os.getenv("LANGFUSE_HOST",    "http://localhost:3001"),
}


def _ping(name: str, url: str) -> dict:
    start = time.monotonic()
    try:
        requests.get(url, timeout=3)
        latency_ms = round((time.monotonic() - start) * 1000)
        # Any HTTP response (even 401/404) means the service is reachable
        return {"status": "ok", "url": url, "latency_ms": latency_ms}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "url": url, "error": "Connection refused"}
    except requests.exceptions.Timeout:
        return {"status": "error", "url": url, "error": "Timeout (3s)"}
    except Exception as exc:
        return {"status": "error", "url": url, "error": str(exc)}


def _check_supabase() -> dict:
    try:
        supabase.table("incidents").select("id").limit(1).execute()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@router.get("/health")
async def integration_health():
    results = {name: _ping(name, url) for name, url in _SERVICES.items()}
    results["supabase"] = _check_supabase()

    error_count = sum(1 for v in results.values() if v["status"] == "error")
    if error_count == 0:
        aggregate = "healthy"
    elif error_count <= 2:
        aggregate = "degraded"
    else:
        aggregate = "critical"

    return {"status": aggregate, "services": results}
