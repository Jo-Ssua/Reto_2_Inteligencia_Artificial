"""RAG sobre los documentos PDF almacenados en ChromaDB."""
from .trazas import configurar_langsmith

configurar_langsmith()

from langsmith import traceable  # noqa: E402

from .almacen import crear_cliente, funcion_embeddings, obtener_coleccion  # noqa: E402
from .documentos import COLECCION_DOCUMENTOS  # noqa: E402
from .llm import llamar_llm  # noqa: E402

SISTEMA_RAG = (
    "Usted responde preguntas usando únicamente el contexto entregado. "
    "Si la respuesta no está en el contexto, diga que no encontró esa información. "
    "Responda en español, de forma clara y concisa, sin inventar datos. "
    "Cuando sea útil, indique la página de la fuente.\n\n"
    "Contexto:\n{contexto}"
)


class RAGDocumentos:
    def __init__(self, ruta: str = "datos/chroma",
                 nombre_coleccion: str = COLECCION_DOCUMENTOS,
                 funcion_emb=None):
        self.funcion_emb = funcion_emb or funcion_embeddings()
        cliente = crear_cliente(ruta)
        self.coleccion = obtener_coleccion(cliente, nombre_coleccion, self.funcion_emb)

    @traceable(name="rag_recuperar", run_type="retriever")
    def recuperar(self, pregunta: str, k: int = 4) -> dict:
        total = self.coleccion.count()
        if total == 0:
            raise RuntimeError(
                "La colección de documentos está vacía. Ejecute: "
                "python -m memoria_rag.documentos <archivo.pdf>"
            )
        resultado = self.coleccion.query(query_texts=[pregunta], n_results=min(k, total))
        return {
            "contextos": resultado["documents"][0],
            "metadatos": resultado["metadatas"][0],
            "distancias": resultado["distances"][0],
        }

    @traceable(name="rag_responder", run_type="chain")
    def responder(self, pregunta: str, k: int = 4) -> dict:
        recuperado = self.recuperar(pregunta, k)
        contextos = recuperado["contextos"]
        metadatos = recuperado["metadatos"]

        bloques = [
            f"[Página {meta.get('pagina', '?')}] {texto}"
            for texto, meta in zip(contextos, metadatos)
        ]
        sistema = SISTEMA_RAG.format(contexto="\n\n".join(bloques) or "(sin contexto)")
        respuesta = llamar_llm(sistema, [{"role": "user", "content": pregunta}])

        return {
            "pregunta": pregunta,
            "respuesta": respuesta,
            "contextos": contextos,
            "fuentes": [
                {"fuente": meta.get("fuente"), "pagina": meta.get("pagina")}
                for meta in metadatos
            ],
            "distancias": recuperado["distancias"],
        }
