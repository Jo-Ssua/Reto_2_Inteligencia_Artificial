# mi-servidor

Servidores MCP para VS Code (Copilot Chat en modo **Agent**):

- **notas**: guarda y busca notas en `notas.json`.
- **web**: descarga una página y expone su texto para que el asistente responda preguntas sobre ella.
- **memory** (oficial, vía `npx`) y **fetch** (vía `uvx`), configurables en `.vscode/mcp.json`.

## Servidor `web`

`src/mi_servidor/web.py` implementa dos herramientas:

| Herramienta | Qué hace |
| --- | --- |
| `leer_pagina(url)` | Descarga la URL y devuelve el texto visible (sin `script`/`style`), máx. 20 000 caracteres. |
| `buscar_en_pagina(url, consulta)` | Devuelve hasta 10 párrafos que contienen palabras de la consulta. |

El servidor **no** usa un LLM: solo entrega el contenido de la página. Es Copilot (el cliente MCP) quien lee ese texto y redacta la respuesta.

### Cómo funciona

1. Se pide al asistente algo como «¿de qué habla https://example.com?».
2. Copilot llama a `leer_pagina` (o `buscar_en_pagina`) por stdio.
3. El servidor descarga el HTML con `urllib`, lo convierte a texto con `HTMLParser` y lo devuelve.
4. Copilot responde usando ese texto.

Limitaciones: no ejecuta JavaScript, por lo que páginas renderizadas en el navegador pueden devolver poco contenido; solo acepta `http://` y `https://`.

## Cómo correrlo

Requisitos: `uv` y VS Code con GitHub Copilot Chat.

```bash
uv sync                     # instala dependencias en .venv
uv run src/mi_servidor/web.py   # arranca el servidor por stdio (queda esperando)
```

En VS Code:

1. Abre esta carpeta como workspace.
2. En `.vscode/mcp.json`, pulsa **Start** sobre `web` (o `Ctrl+Shift+P` → *MCP: List Servers* → `web` → *Start*).
3. En el chat, modo **Agent**, prueba:
   - `Lee https://example.com y resúmelo.`
   - `Busca en https://es.wikipedia.org/wiki/Protocolo_de_contexto_de_modelo qué es MCP.`

Para depurar las herramientas sin Copilot:

```bash
uv run mcp dev src/mi_servidor/web.py
```

## Servidor `notas`

```bash
uv run src/mi_servidor/server.py
```

Herramientas: `guardar_nota`, `listar_notas`, `buscar_notas`. Datos en `notas.json` (misma carpeta que `server.py`).
