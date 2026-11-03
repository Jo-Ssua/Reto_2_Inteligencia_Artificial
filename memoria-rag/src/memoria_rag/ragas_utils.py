"""Adaptadores para usar el LLM y los embeddings del proyecto con RAGAS."""
from . import compat  # noqa: F401  # antes de importar ragas
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.llms import LLM
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

from .almacen import funcion_embeddings
from .llm import llamar_llm

SISTEMA_EVALUACION = (
    "Usted es un evaluador experto de sistemas RAG. "
    "Siga exactamente el formato solicitado y responda solo lo pedido."
)


class LLMAnthropic(LLM):
    """Envoltorio mínimo para que RAGAS use el LLM de Anthropic del proyecto."""

    @property
    def _llm_type(self) -> str:
        return "anthropic-memoria-rag"

    def _call(self, prompt: str, stop=None, run_manager=None, **kwargs) -> str:
        return llamar_llm(
            SISTEMA_EVALUACION,
            [{"role": "user", "content": prompt}],
            max_tokens=2048,
        )


class EmbeddingsLocales(Embeddings):
    """Reutiliza el modelo de sentence-transformers de ChromaDB."""

    def __init__(self, funcion_emb=None):
        self.funcion = funcion_emb or funcion_embeddings()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [list(vector) for vector in self.funcion(list(texts))]

    def embed_query(self, text: str) -> list[float]:
        return list(self.funcion([text])[0])


def crear_llm_ragas() -> LangchainLLMWrapper:
    return LangchainLLMWrapper(LLMAnthropic())


def crear_embeddings_ragas(funcion_emb=None) -> LangchainEmbeddingsWrapper:
    return LangchainEmbeddingsWrapper(EmbeddingsLocales(funcion_emb))


def crear_metricas(funcion_emb=None) -> list:
    """Métricas de RAGAS que no requieren respuesta de referencia."""
    llm = crear_llm_ragas()
    embeddings = crear_embeddings_ragas(funcion_emb)
    metricas = [faithfulness, answer_relevancy, context_precision, context_recall]
    for metrica in metricas:
        metrica.llm = llm
        if hasattr(metrica, "embeddings"):
            metrica.embeddings = embeddings
    return metricas
