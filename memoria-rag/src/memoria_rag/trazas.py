"""Configuración de trazabilidad con LangSmith."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def langsmith_activo() -> bool:
    return os.environ.get("LANGSMITH_TRACING", "").lower() in {"1", "true", "yes"}


def configurar_langsmith() -> str:
    """Devuelve el proyecto de LangSmith sin chocar con la dirección de agente.

    Si el SDK ya tiene un agente (LANGSMITH_AGENT_ID/ENVIRONMENT), deriva el
    proyecto de ahí y no define LANGSMITH_PROJECT para evitar el conflicto.
    """
    agente = os.environ.get("LANGSMITH_AGENT_ID")
    entorno = os.environ.get("LANGSMITH_AGENT_ENVIRONMENT", "local")
    if agente:
        return os.environ.get("LANGSMITH_PROJECT") or f"{agente}-{entorno.lower()}"
    return os.environ.setdefault("LANGSMITH_PROJECT", "memoria-rag")
