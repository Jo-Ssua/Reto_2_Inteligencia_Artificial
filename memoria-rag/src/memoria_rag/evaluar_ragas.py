"""Evalúa el RAG del recetario con RAGAS y registra los resultados en LangSmith.

Uso:
    python -m memoria_rag.evaluar_ragas
    python -m memoria_rag.evaluar_ragas --sin-langsmith
    python -m memoria_rag.evaluar_ragas --k 4
"""
import argparse
import asyncio
from collections import defaultdict
from pathlib import Path

from . import compat  # noqa: F401  (debe ir antes que ragas)

from ragas import EvaluationDataset, evaluate
from ragas.dataset_schema import SingleTurnSample

from .documentos import ingestar_pdf
from .rag import RAGDocumentos
from .ragas_utils import crear_embeddings_ragas, crear_llm_ragas, crear_metricas
from .trazas import configurar_langsmith, langsmith_activo

BASE_DIR = Path(__file__).resolve().parents[2]
PDF_POR_DEFECTO = BASE_DIR / "Receta Ajiaco Santafereño.pdf"
DATASET_LANGSMITH = "ragas-ajiaco"
RUTA_RESULTADOS = BASE_DIR / "datos" / "evaluacion_ragas.csv"

EJEMPLOS = [
    {
        "inputs": {"pregunta": "¿Cuánto tiempo toma preparar el ajiaco y para cuántas personas es?"},
        "outputs": {"referencia": "Toma 1 hora y 30 minutos y la receta es para 4 personas."},
    },
    {
        "inputs": {"pregunta": "¿Qué tres tipos de papa lleva el ajiaco y qué función cumple cada una?"},
        "outputs": {"referencia": "Lleva papa sabanera, que mantiene la forma; papa pastusa, que da textura; y papa criolla, que se deshace para espesar el caldo."},
    },
    {
        "inputs": {"pregunta": "¿Cuándo se agregan las guascas y por qué?"},
        "outputs": {"referencia": "Se añade la mitad de las guascas frescas picadas 10 minutos antes de apagar la olla, o hacia el final, para conservar su aroma fresco."},
    },
    {
        "inputs": {"pregunta": "¿Con qué se acompaña el ajiaco al servirlo?"},
        "outputs": {"referencia": "Se acompaña con crema de leche, alcaparras y tajadas de aguacate."},
    },
    {
        "inputs": {"pregunta": "¿Cuánta agua se usa y cuánto tiempo se cocina el pollo?"},
        "outputs": {"referencia": "Se usan 3 litros de agua y el pollo se cocina a fuego medio-alto durante 35 minutos."},
    },
    {
        "inputs": {"pregunta": "¿Qué se hace con la cebolla larga en la preparación?"},
        "outputs": {"referencia": "Se agrega entera durante la cocción de la base y luego se retira y se descarta."},
    },
    {
        "inputs": {"pregunta": "¿En qué orden se incorporan las papas y cuánto tiempo se cocinan?"},
        "outputs": {"referencia": "Primero se agregan la papa sabanera en rodajas finas y la pastusa en cubos, se cocinan 15 minutos y luego se añade la papa criolla en rodajas."},
    },
]


def preparar_rag(k: int) -> RAGDocumentos:
    if not PDF_POR_DEFECTO.exists():
        raise FileNotFoundError(f"No se encontró el PDF: {PDF_POR_DEFECTO}")
    ingestar_pdf(PDF_POR_DEFECTO)
    return RAGDocumentos()


def generar_salidas(rag: RAGDocumentos, k: int) -> list[dict]:
    salidas = []
    for ejemplo in EJEMPLOS:
        salida = rag.responder(ejemplo["inputs"]["pregunta"], k=k)
        salidas.append({
            "pregunta": ejemplo["inputs"]["pregunta"],
            "respuesta": salida["respuesta"],
            "contextos": salida["contextos"],
            "referencia": ejemplo["outputs"]["referencia"],
            "fuentes": salida["fuentes"],
        })
    return salidas


def guardar_csv(filas: list[dict], metricas: list[str]) -> None:
    import csv

    RUTA_RESULTADOS.parent.mkdir(parents=True, exist_ok=True)
    with RUTA_RESULTADOS.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(
            archivo, fieldnames=["pregunta", "respuesta", *metricas]
        )
        escritor.writeheader()
        for fila in filas:
            escritor.writerow({clave: fila.get(clave) for clave in escritor.fieldnames})
    print(f"\nResultados guardados en {RUTA_RESULTADOS}")


def evaluar_sin_langsmith(salidas: list[dict], metricas: list) -> None:
    muestras = [
        SingleTurnSample(
            user_input=fila["pregunta"],
            response=fila["respuesta"],
            retrieved_contexts=fila["contextos"],
            reference=fila["referencia"],
        )
        for fila in salidas
    ]
    resultados = evaluate(
        dataset=EvaluationDataset(samples=muestras),
        metrics=metricas,
        llm=crear_llm_ragas(),
        embeddings=crear_embeddings_ragas(),
        raise_exceptions=False,
        show_progress=True,
    )
    tabla = resultados.to_pandas()
    for indice, fila in enumerate(salidas):
        fila.update(tabla.iloc[indice].to_dict())
    nombres = [metrica.name for metrica in metricas]
    print("\n=== Promedios RAGAS ===")
    for nombre in nombres:
        print(f"{nombre}: {tabla[nombre].mean():.3f}")
    guardar_csv(salidas, nombres)


async def evaluar_con_langsmith(salidas: list[dict], metricas: list) -> None:
    from langsmith import Client, aevaluate

    client = Client()
    if not client.has_dataset(dataset_name=DATASET_LANGSMITH):
        dataset = client.create_dataset(
            DATASET_LANGSMITH,
            description="Preguntas sobre la receta de ajiaco santafereño para evaluar el RAG.",
        )
        client.create_examples(
            dataset_id=dataset.id,
            examples=[
                {"inputs": e["inputs"], "outputs": e["outputs"]} for e in EJEMPLOS
            ],
        )
    else:
        print(f"Reutilizando el dataset de LangSmith '{DATASET_LANGSMITH}'.")

    por_pregunta = {fila["pregunta"]: fila for fila in salidas}

    async def objetivo(inputs: dict) -> dict:
        fila = por_pregunta[inputs["pregunta"]]
        return {
            "respuesta": fila["respuesta"],
            "contextos": fila["contextos"],
            "fuentes": fila["fuentes"],
        }

    def crear_evaluador(metrica):
        async def evaluador(inputs: dict, outputs: dict, reference_outputs: dict):
            muestra = SingleTurnSample(
                user_input=inputs["pregunta"],
                response=outputs["respuesta"],
                retrieved_contexts=outputs["contextos"],
                reference=reference_outputs["referencia"],
            )
            try:
                puntaje = await metrica.single_turn_ascore(muestra)
            except Exception as error:  # noqa: BLE001
                return {"key": metrica.name, "score": None, "comment": str(error)[:300]}
            return {"key": metrica.name, "score": float(puntaje)}
        return evaluador

    resultados = await aevaluate(
        objetivo,
        data=DATASET_LANGSMITH,
        evaluators=[crear_evaluador(metrica) for metrica in metricas],
        experiment_prefix=DATASET_LANGSMITH,
        description="Evaluación RAGAS del RAG sobre la receta de ajiaco.",
        max_concurrency=4,
        error_handling="log",
    )

    acumulado: dict[str, list[float]] = defaultdict(list)
    async for fila in resultados:
        valores = {}
        for evaluacion in fila["evaluation_results"]["results"]:
            if evaluacion.score is not None:
                acumulado[evaluacion.key].append(float(evaluacion.score))
                valores[evaluacion.key] = evaluacion.score
        pregunta = fila["example"].inputs.get("pregunta", "")
        if pregunta in por_pregunta:
            por_pregunta[pregunta].update(valores)

    nombres = [metrica.name for metrica in metricas]
    print("\n=== Promedios RAGAS ===")
    for nombre in nombres:
        valores = acumulado.get(nombre, [])
        promedio = sum(valores) / len(valores) if valores else float("nan")
        print(f"{nombre}: {promedio:.3f}")
    print(f"\nExperimento en LangSmith: {resultados.url}")
    guardar_csv(salidas, nombres)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evalúa el RAG con RAGAS y LangSmith.")
    parser.add_argument("--k", type=int, default=4, help="Fragmentos recuperados por pregunta.")
    parser.add_argument(
        "--sin-langsmith",
        action="store_true",
        help="Calcula RAGAS localmente sin registrar el experimento en LangSmith.",
    )
    args = parser.parse_args()

    configurar_langsmith()
    rag = preparar_rag(args.k)
    print(f"Generando respuestas para {len(EJEMPLOS)} preguntas...")
    salidas = generar_salidas(rag, args.k)
    metricas = crear_metricas(rag.funcion_emb)

    if langsmith_activo() and not args.sin_langsmith:
        asyncio.run(evaluar_con_langsmith(salidas, metricas))
    else:
        if not args.sin_langsmith:
            print("LangSmith no está activo; se evalúa solo con RAGAS en local.")
        evaluar_sin_langsmith(salidas, metricas)


if __name__ == "__main__":
    main()
