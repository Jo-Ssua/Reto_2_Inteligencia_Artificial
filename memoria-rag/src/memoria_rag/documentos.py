"""Ingesta de documentos PDF en la base vectorial de ChromaDB."""
import hashlib
import re
import textwrap
from pathlib import Path

from pypdf import PdfReader

from .almacen import crear_cliente, funcion_embeddings, obtener_coleccion

COLECCION_DOCUMENTOS = "documentos"
TAMANO_CHUNK = 700
SOLAPE_CHUNK = 120


def extraer_paginas(ruta: str | Path) -> list[dict]:
    """Extrae el texto de cada página del PDF."""
    lector = PdfReader(str(ruta))
    paginas = []
    for numero, pagina in enumerate(lector.pages, start=1):
        texto = pagina.extract_text() or ""
        texto = re.sub(r"[ \t]+", " ", texto)
        texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
        if texto:
            paginas.append({"pagina": numero, "texto": texto})
    return paginas


def _unidades(texto: str, tamano: int) -> list[str]:
    """Divide el texto en párrafos, frases o líneas que quepan en un chunk."""
    unidades: list[str] = []
    for parrafo in re.split(r"\n\s*\n", texto):
        parrafo = parrafo.strip()
        if not parrafo:
            continue
        if len(parrafo) <= tamano:
            unidades.append(parrafo)
            continue
        for linea in parrafo.splitlines():
            linea = linea.strip()
            if not linea:
                continue
            if len(linea) <= tamano:
                unidades.append(linea)
                continue
            for frase in re.split(r"(?<=[.!?:;])\s+", linea):
                if len(frase) <= tamano:
                    unidades.append(frase.strip())
                else:
                    unidades.extend(textwrap.wrap(
                        frase, width=tamano, break_long_words=False,
                        break_on_hyphens=False, replace_whitespace=False,
                    ))
    return unidades


def dividir_en_chunks(texto: str, tamano: int = TAMANO_CHUNK,
                     solape: int = SOLAPE_CHUNK) -> list[str]:
    """Acumula unidades de texto hasta `tamano` caracteres, con solape entre chunks."""
    chunks: list[str] = []
    actual = ""
    for unidad in _unidades(texto, tamano):
        if actual and len(actual) + len(unidad) + 1 > tamano:
            chunks.append(actual.strip())
            cola = actual[-solape:] if solape < len(actual) else actual
            corte = cola.find(" ")
            if corte > 0:
                cola = cola[corte + 1:]
            actual = f"{cola}\n{unidad}"
        else:
            actual = f"{actual}\n{unidad}" if actual else unidad
    if actual.strip():
        chunks.append(actual.strip())
    return [chunk for chunk in chunks if len(chunk) >= 25]


def _slug(ruta: Path) -> str:
    return hashlib.sha1(str(ruta.resolve()).encode()).hexdigest()[:10]


def ingestar_pdf(ruta: str | Path, ruta_chroma: str = "datos/chroma",
                 nombre_coleccion: str = COLECCION_DOCUMENTOS,
                 funcion_emb=None, cliente=None) -> dict:
    """Extrae, fragmenta y guarda el PDF en ChromaDB. Reemplaza la versión anterior."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el PDF: {ruta}")

    cliente = cliente or crear_cliente(ruta_chroma)
    coleccion = obtener_coleccion(cliente, nombre_coleccion, funcion_emb)

    fuente = ruta.name
    if coleccion.count() > 0:
        coleccion.delete(where={"fuente": fuente})

    slug = _slug(ruta)
    ids, documentos, metadatos = [], [], []
    for pagina in extraer_paginas(ruta):
        for indice, chunk in enumerate(dividir_en_chunks(pagina["texto"])):
            ids.append(f"{slug}-p{pagina['pagina']}-c{indice}")
            documentos.append(chunk)
            metadatos.append({
                "fuente": fuente,
                "ruta": str(ruta),
                "pagina": pagina["pagina"],
                "chunk": indice,
            })

    if documentos:
        coleccion.add(ids=ids, documents=documentos, metadatas=metadatos)

    return {
        "fuente": fuente,
        "coleccion": nombre_coleccion,
        "chunks": len(documentos),
        "total_coleccion": coleccion.count(),
    }


def recuperar_documentos(coleccion, consulta: str, k: int = 4) -> dict:
    """Busca los fragmentos más similares a la consulta."""
    total = coleccion.count()
    if total == 0:
        return {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}
    return coleccion.query(query_texts=[consulta], n_results=min(k, total))


def main() -> None:
    import sys

    ruta_pdf = sys.argv[1] if len(sys.argv) > 1 else "Receta Ajiaco Santafereño.pdf"
    resultado = ingestar_pdf(ruta_pdf)
    print(f"PDF '{resultado['fuente']}' ingestado: {resultado['chunks']} chunks "
          f"({resultado['total_coleccion']} en la colección '{resultado['coleccion']}').")


if __name__ == "__main__":
    main()
