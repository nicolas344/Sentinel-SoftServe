"""
Sentinel Remote Agent
Corre en servidores remotos y envía eventos Docker al backend de Sentinel.

Configuración via variables de entorno (archivo .env):
  SENTINEL_BACKEND_URL  — URL del backend (ej: https://sentinel.ejemplo.com)
  SENTINEL_AGENT_KEY    — API Key compartida con el backend
  SERVER_NAME           — Nombre identificador de este servidor (opcional)
"""

import os
import time
import socket
import logging
import docker
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("SENTINEL_BACKEND_URL", "http://localhost:8000")
AGENT_KEY = os.getenv("SENTINEL_AGENT_KEY")
SERVER_NAME = os.getenv("SERVER_NAME", socket.gethostname())

WATCHED_ACTIONS = ("die", "oom")
INTENTIONAL_EXIT_CODES = {"0", "130", "143"}
LOG_TAIL_LINES = 100

RETRY_DELAYS = [5, 15, 30]  # segundos entre reintentos


def get_docker_client() -> docker.DockerClient:
    try:
        return docker.from_env()
    except docker.errors.DockerException:
        fallback = f'unix://{os.path.expanduser("~")}/.docker/run/docker.sock'
        return docker.DockerClient(base_url=fallback)


def fetch_logs(client: docker.DockerClient, container_id: str) -> str:
    try:
        container = client.containers.get(container_id)
        raw = container.logs(tail=LOG_TAIL_LINES, timestamps=True)
        return raw.decode("utf-8", errors="replace")
    except docker.errors.NotFound:
        logger.warning(f"Contenedor {container_id} ya eliminado — logs no disponibles")
        return ""
    except Exception as e:
        logger.error(f"Error obteniendo logs: {e}")
        return ""


def send_event(event: dict) -> bool:
    """
    Envía el evento al backend de Sentinel.
    Retorna True si fue exitoso, False si falló.
    """
    url = f"{BACKEND_URL}/api/docker/events"
    headers = {"X-Agent-Key": AGENT_KEY}

    for attempt, delay in enumerate(RETRY_DELAYS, start=1):
        try:
            response = requests.post(url, json=event, headers=headers, timeout=10)
            if response.status_code == 200:
                logger.info(f"Evento enviado correctamente: {event.get('Action')} — {event.get('server_name')}")
                return True
            else:
                logger.warning(f"Backend respondió {response.status_code}: {response.text}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"Intento {attempt}/{len(RETRY_DELAYS)} — backend no disponible, reintentando en {delay}s...")
            time.sleep(delay)
        except Exception as e:
            logger.error(f"Error inesperado enviando evento: {e}")
            break

    logger.error("No se pudo enviar el evento al backend después de todos los reintentos")
    return False


def monitor():
    if not AGENT_KEY:
        logger.error("SENTINEL_AGENT_KEY no configurada — el agente no puede autenticarse")
        return

    logger.info(f"Sentinel Agent iniciado — servidor: {SERVER_NAME}")
    logger.info(f"Backend: {BACKEND_URL}")

    client = get_docker_client()
    logger.info("Conectado al Docker daemon — escuchando eventos...")

    for event in client.events(decode=True):
        if event.get("Type") != "container":
            continue
        if event.get("Action") not in WATCHED_ACTIONS:
            continue

        attrs = event.get("Actor", {}).get("Attributes", {})
        container_id = event.get("Actor", {}).get("ID", "")
        exit_code = attrs.get("exitCode", "unknown")

        if exit_code in INTENTIONAL_EXIT_CODES:
            logger.info(f"Contenedor detenido intencionalmente (exit {exit_code}) — ignorado")
            continue

        logs = fetch_logs(client, container_id)

        payload = {
            "Type": event["Type"],
            "Action": event["Action"],
            "Actor": event["Actor"],
            "time": event.get("time"),
            "server_name": SERVER_NAME,
            "logs_override": logs,
        }

        send_event(payload)


if __name__ == "__main__":
    monitor()
