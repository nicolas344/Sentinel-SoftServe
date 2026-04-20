"""
Cliente ChromaDB compartido.

Import lazy para evitar el problema pydantic v1 + Python 3.14 documentado
en langgraph_engine. Ningún módulo superior debería importar chromadb
directamente; todo pasa por este helper.
"""

import logging
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_client = None


def get_client():
    """Conexión HTTP a ChromaDB (singleton a nivel de proceso)."""
    global _client
    if _client is not None:
        return _client

    import chromadb

    chroma_url = os.getenv("CHROMA_HOST", "http://localhost:8001")
    parsed = urlparse(chroma_url)
    _client = chromadb.HttpClient(host=parsed.hostname, port=parsed.port or 8001)
    return _client


def get_or_create_collection(name: str):
    """Devuelve la colección o la crea si no existe."""
    return get_client().get_or_create_collection(name)
