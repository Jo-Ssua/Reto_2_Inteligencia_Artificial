"""Servidor MCP para leer una página web y responder preguntas sobre ella."""

import re
import urllib.request
from html.parser import HTMLParser

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("web")

MAX_CHARS = 20_000
USER_AGENT = "Mozilla/5.0 (compatible; mi-servidor/0.1)"


class _Extractor(HTMLParser):
    """Convierte HTML en texto visible, ignorando script/style."""

    BLOQUES = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__()
        self.partes: list[str] = []
        self.omitir = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style", "noscript"):
            self.omitir += 1
        elif tag in self.BLOQUES:
            self.partes.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self.omitir:
            self.omitir -= 1
        elif tag in self.BLOQUES:
            self.partes.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.omitir:
            self.partes.append(data)

    def texto(self) -> str:
        crudo = "".join(self.partes)
        lineas = (re.sub(r"\s+", " ", l).strip() for l in crudo.splitlines())
        return "\n".join(l for l in lineas if l)


def _descargar(url: str) -> str:
    if not re.match(r"^https?://", url, re.IGNORECASE):
        raise ValueError("La URL debe empezar por http:// o https://")
    peticion = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(peticion, timeout=20) as respuesta:
        charset = respuesta.headers.get_content_charset() or "utf-8"
        html = respuesta.read(2_000_000).decode(charset, errors="replace")
    extractor = _Extractor()
    extractor.feed(html)
    return extractor.texto()


@mcp.tool()
def leer_pagina(url: str) -> str:
    """Devuelve el texto visible de una página web (máx. 20000 caracteres)."""
    return _descargar(url)[:MAX_CHARS]


@mcp.tool()
def buscar_en_pagina(url: str, consulta: str) -> list[str]:
    """Devuelve los párrafos de la página relevantes para la consulta."""
    terminos = [t for t in re.findall(r"\w+", consulta.lower()) if len(t) > 2]
    parrafos = [p for p in _descargar(url).splitlines() if len(p) > 40]
    encontrados = [p for p in parrafos if any(t in p.lower() for t in terminos)]
    return encontrados[:10]


if __name__ == "__main__":
    mcp.run()  # usa stdio por defecto
