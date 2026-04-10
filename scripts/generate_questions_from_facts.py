import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")

if not OPENAI_API_KEY:
    raise RuntimeError("Falta OPENAI_API_KEY en el archivo .env")

client = OpenAI(api_key=OPENAI_API_KEY)

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "imports" / "generated_from_facts"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_system_prompt() -> str:
    return """
Eres un generador experto de preguntas de fútbol en español para un banco global de quizzes.

Tu misión:
- generar preguntas SOLO a partir de safe_facts proporcionados
- no inventar datos fuera de esos hechos
- hacer preguntas autocontenidas
- evitar preguntas demasiado obvias o demasiado de ficha
- priorizar dificultad medium/hard
- crear distractores plausibles y del mismo tipo semántico

REGLAS CRÍTICAS:
- usa exclusivamente los safe_facts proporcionados
- no completes huecos con tu memoria
- si un hecho no da para una buena pregunta, no fuerces
- cada pregunta debe tener 4 opciones
- una sola correcta
- toda pregunta debe ser autocontenida
- las 4 opciones deben ser del mismo tipo semántico
- NO pongas distractores absurdos
- NO pongas como distractor una competición si la respuesta correcta es un rival
- NO pongas como distractor un estadio si la respuesta correcta es un equipo
- máximo 15-20% easy
- mayoría medium/hard
- evita que más de 2 preguntas del lote sean simple “ficha de club” (fecha fundación, capacidad, nombre del estadio)

TIPOS DE PREGUNTAS PREFERIDAS:
- rivales de debuts
- temporadas concretas
- ascensos concretos
- resultados de partidos de estreno
- secuencias cronológicas
- comparaciones entre hitos
- identificación de contexto histórico
- preguntas que mezclen dos safe_facts compatibles

TIPOS DE PREGUNTAS MENOS DESEABLES:
- fecha pura sin contexto
- capacidad pura
- nombre del estadio sin giro
- preguntas demasiado escolares

DISTRACTORES:
- deben ser plausibles
- deben pertenecer a la misma familia que la respuesta correcta
- si la correcta es una fecha, las otras opciones deben ser fechas plausibles
- si la correcta es un rival, las otras opciones deben ser otros rivales o clubes plausibles del mismo universo
- si la correcta es una temporada, las otras deben ser temporadas cercanas o plausibles
- evita opciones ridículas o de tipo incorrecto

TAGS:
- conserva y amplía tags útiles del fact
- usa tags consistentes y reutilizables

Devuelve SOLO JSON válido.
""".strip()


def build_user_prompt(payload: Dict[str, Any], count: int) -> str:
    topic = payload.get("topic", "tema")
    topic_slug = payload.get("topic_slug", "tema")
    safe_facts = payload.get("safe_facts", [])

    return f"""
Genera aproximadamente {count} preguntas SOLO a partir de estos safe_facts.

Topic: {topic}
Topic slug: {topic_slug}

Safe facts:
{json.dumps(safe_facts, ensure_ascii=False)}

Devuelve SOLO JSON con este formato:

{{
  "theme": "{topic}",
  "theme_slug": "{topic_slug}",
  "questions": [
    {{
      "id": "string",
      "question": "string",
      "options": ["string", "string", "string", "string"],
      "correctIndex": 0,
      "difficulty": "easy | medium | hard",
      "tags": ["string", "string", "string"],
      "source_fact_ids": ["string"],
      "source_notes": ["string"]
    }}
  ]
}}

REGLAS:
- preguntas autocontenidas
- 4 opciones
- 1 correcta
- distractores plausibles y del mismo tipo
- no inventes datos fuera de los safe_facts
- mayoría medium/hard
- máximo 20% easy
- usa source_fact_ids con los fact_id usados
- source_notes cortas
- ids tipo: {topic_slug}_q_001
- si hay pocos safe_facts, genera menos preguntas antes que inventar
- evita que más de 2 preguntas del lote sean pura ficha
- intenta que al menos la mitad del lote sea de rivales, temporadas, ascensos, debuts o comparaciones históricas
Devuelve SOLO JSON.
""".strip()


def call_openai_for_questions(payload: Dict[str, Any], count: int) -> Dict[str, Any]:
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": build_user_prompt(payload, count)},
        ],
        text={"format": {"type": "json_object"}},
    )
    return json.loads(response.output_text)


def enrich_output(original_payload: Dict[str, Any], generated_payload: Dict[str, Any]) -> Dict[str, Any]:
    topic = original_payload.get("topic")
    topic_slug = original_payload.get("topic_slug")
    safe_facts = original_payload.get("safe_facts", [])
    questions = generated_payload.get("questions", [])

    return {
        "theme": topic,
        "theme_slug": topic_slug,
        "generated_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "safe_fact_count_used_as_input": len(safe_facts),
        "question_count": len(questions),
        "questions": questions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generar preguntas a partir de safe_facts")
    parser.add_argument("--file", required=True, help="Ruta al JSON de facts")
    parser.add_argument("--count", type=int, default=12, help="Número aproximado de preguntas a generar")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        raise FileNotFoundError(f"No existe el fichero: {file_path}")

    payload = load_json(file_path)
    safe_facts = payload.get("safe_facts", [])

    if not safe_facts:
        raise ValueError("El fichero no contiene safe_facts para generar preguntas")

    print(f"🧠 Generando preguntas desde {len(safe_facts)} safe_facts...")

    generated_payload = call_openai_for_questions(payload, args.count)
    final_payload = enrich_output(payload, generated_payload)

    topic_slug = payload.get("topic_slug", "tema")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"{topic_slug}_questions_{timestamp}.json"

    save_json(out_path, final_payload)

    print(f"✅ Preguntas guardadas en: {out_path}")


if __name__ == "__main__":
    main()