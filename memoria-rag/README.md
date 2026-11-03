# Memoria RAG

Chat con memoria a corto, medio y largo plazo, más un RAG sobre documentos PDF
que se evalúa con **RAGAS** y se traza en **LangSmith**.

En este repositorio el documento de prueba es `Receta Ajiaco Santafereño.pdf`,
pero puedes ingestar cualquier PDF.

## Cómo funciona

1. `documentos.py` extrae el texto del PDF, lo divide en fragmentos (chunks) y
   los guarda como embeddings en **ChromaDB** (`datos/chroma`, colección
   `documentos`).
2. `rag.py` busca los fragmentos más parecidos a una pregunta y genera la
   respuesta con el LLM usando solo ese contexto.
3. `evaluar_ragas.py` hace 7 preguntas sobre la receta, genera sus respuestas y
   calcula 4 métricas de **RAGAS**:
   - `faithfulness`
   - `answer_relevancy`
   - `context_precision`
   - `context_recall`
4. Cada ejecución se registra en **LangSmith** como experimento y las llamadas
   del RAG quedan trazadas.

Se usa **un solo modelo LLM**: `claude-sonnet-5-5`, definido en
`src/memoria_rag/llm.py`. Tanto el RAG como RAGAS usan ese mismo modelo.
Los embeddings son locales (`paraphrase-multilingual-MiniLM-L12-v2`) y no
consumen API.

## Requisitos

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- Una clave de Anthropic
- Una clave de LangSmith (opcional si se evalúa sin LangSmith)

## Instalación

```bash
uv sync
```

## Configuración (`.env`)

Crea un archivo `.env` en la raíz del proyecto:

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-5-5

LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_AGENT_ID=ragas
LANGSMITH_AGENT_ENVIRONMENT=local
```

Con `LANGSMITH_AGENT_ID` y `LANGSMITH_AGENT_ENVIRONMENT` el proyecto de
LangSmith se deriva automáticamente como `ragas-local`.

## Cómo correrlo

### 1. Ingestar el PDF (opcional)

La evaluación carga el PDF automáticamente, pero puedes hacerlo a mano:

```bash
.venv/bin/python -m memoria_rag.documentos "Receta Ajiaco Santafereño.pdf"
```

### 2. Evaluar con RAGAS y LangSmith

```bash
.venv/bin/python -m memoria_rag.evaluar_ragas
```

Esto ejecuta:

- 7 preguntas × 1 respuesta RAG cada una (7 llamadas al LLM)
- 7 preguntas × 4 métricas de RAGAS

### 3. Evaluar solo con RAGAS (sin subir a LangSmith)

```bash
.venv/bin/python -m memoria_rag.evaluar_ragas --sin-langsmith
```

### 4. Cambiar cuántos fragmentos recupera

```bash
.venv/bin/python -m memoria_rag.evaluar_ragas --k 4
```

### 5. Chat con memoria

```bash
uv run memoria-rag
```

## Dónde ver los resultados

1. **CSV local**: `datos/evaluacion_ragas.csv`
   Contiene la pregunta, la respuesta y las 4 métricas por pregunta.

2. **LangSmith (experimento)**:
   Al ejecutar la evaluación se imprime una URL parecida a:

   ```
   https://smith.langchain.com/.../datasets/.../compare?selectedSessions=...
   ```

   Ahí ves cada pregunta con sus puntajes de RAGAS.
   El proyecto de trazas es `ragas-local`.

3. **ChromaDB**:
   La base vectorial queda en `datos/chroma/`.

## Ejemplo de resultados

```
faithfulness:       0.895
answer_relevancy:   0.804
context_precision:  0.607
context_recall:     1.000
```

## Estructura del proyecto

```
src/memoria_rag/
├── almacen.py          # Cliente de ChromaDB y embeddings
├── compat.py           # Compatibilidad RAGAS / Python 3.14
├── documentos.py       # Extracción, chunking e ingesta de PDF
├── evaluar_ragas.py    # Evaluación con RAGAS + LangSmith
├── gestor.py           # Coordinación de las memorias
├── llm.py              # Llamadas a Anthropic
├── memoria_corto.py    # Memoria a corto plazo
├── memoria_medio.py    # Memoria a medio plazo
├── memoria_largo.py    # Memoria a largo plazo
├── rag.py              # Recuperación y respuesta del RAG
├── ragas_utils.py      # Adaptadores de LLM/embeddings para RAGAS
└── trazas.py           # Configuración de LangSmith
```

`datos/` y `.env` están ignorados por Git.
