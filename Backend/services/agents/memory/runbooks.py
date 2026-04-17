"""
Runbooks: conocimiento estático, curado por humanos.

Convención de colección: runbooks-<dominio> (ej. runbooks-docker).
El seeding se hace con scripts/seed_chromadb.py por dominio.
"""

import logging

from services.agents.memory.chroma_client import get_or_create_collection

logger = logging.getLogger(__name__)


def query_runbooks(collection_name: str, query: str, k: int = 3) -> list[str]:
    """
    Busca los k runbooks más relevantes para una query.
    Devuelve solo el texto (los LLMs no necesitan metadata de runbooks).
    """
    try:
        collection = get_or_create_collection(collection_name)
        results = collection.query(query_texts=[query], n_results=k)
        return results.get("documents", [[]])[0] or []
    except Exception as e:
        logger.warning(f"[memory.runbooks] Falla al consultar '{collection_name}': {e}")
        return []
