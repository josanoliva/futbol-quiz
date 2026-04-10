# -*- coding: utf-8 -*-
import os
import re
import json
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

# Cargar .env desde la raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(f"No se encontró OPENAI_API_KEY en {PROJECT_ROOT / '.env'}")
    return OpenAI(api_key=api_key)


def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def question_hash(question: str) -> str:
    base = normalize_text(question)
    import hashlib
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def is_fact_good_for_question(fact: Dict[str, Any]) -> bool:
    statement = str(fact.get("statement", "")).strip()
    subtopic = str(fact.get("subtopic", "")).strip()
    questionability = float(fact.get("questionability_score", 0))
    stability = float(fact.get("stability_score", 0))

    if not statement:
        return False
    if questionability < 4.0:
        return False
    if stability < 4.0:
        return False

    # Evitar facts demasiado raros o poco útiles
    bad_patterns = [
        r"\bpartido\s+\d+\b",
        r"\bpor\s+\d+\s+millones\b",
        r"\bnecesitó\s+\d+\b",
        r"\bpor\s+cinco\s+años\s+más\b",
        r"\balternó\b",
        r"\besta\s+temporada\b",
    ]

    text = statement.lower()
    for pat in bad_patterns:
        if re.search(pat, text):
            return False

    # Algunos subtopics valen menos si el fact es muy enrevesado
    if subtopic in {"awards", "records"} and len(statement) > 180:
        return False

    return True


SYSTEM_PROMPT = """
Eres un generador de preguntas de quiz de fútbol en español.

Tu tarea:
- crear UNA sola pregunta de opción múltiple a partir de un fact
- devolver JSON válido
- la respuesta correcta debe ir SIEMPRE en la opción 0
- exactamente 4 opciones
- pregunta clara, natural y objetiva
- distractores plausibles, del mismo tipo semántico
- NO inventes hechos fuera de lo razonable
- NO hagas preguntas rebuscadas
- si el fact no da para una buena pregunta, devuelve is_usable = false

Formato JSON de salida:
{
  "is_usable": true,
  "question": "...",
  "options": ["correcta", "distractor1", "distractor2", "distractor3"],
  "correctIndex": 0,
  "difficulty": "easy|medium|hard",
  "question_type": "...",
  "explanation": "..."
}

Reglas:
- idioma: español
- evitar preguntas ambiguas
- evitar opciones ridículas
- evitar "todas las anteriores" o similares
- si el fact trata una fecha, puedes preguntar por año o fecha completa según convenga
- si el fact trata un club, competición, posición o selección, los distractores deben ser realistas
"""


def build_user_prompt(topic_name: str, fact: Dict[str, Any]) -> str:
    return f"""
TEMA: {topic_name}

FACT:
- subtopic: {fact.get('subtopic', '')}
- fact_type: {fact.get('fact_type', '')}
- statement: {fact.get('statement', '')}
- confidence: {fact.get('confidence', '')}
- questionability_score: {fact.get('questionability_score', '')}
- stability_score: {fact.get('stability_score', '')}

FUENTES:
{json.dumps(fact.get('source_urls', []), ensure_ascii=False)}

Devuelve UNA pregunta buena si este fact sirve para quiz.
""".strip()


def call_openai_json(client: OpenAI, system_prompt: str, user_prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
    model = model or DEFAULT_MODEL

    response = client.responses.create(
        model=model,
        temperature=0.2,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={"format": {"type": "json_object"}}
    )

    text = response.output_text.strip()
    return json.loads(text)


def clean_question_output(item: Dict[str, Any], topic_slug: str, topic_name: str, fact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not item.get("is_usable", False):
        return None

    question = str(item.get("question", "")).strip()
    options = item.get("options", [])
    correct_index = int(item.get("correctIndex", 0))
    difficulty = str(item.get("difficulty", "medium")).strip().lower()
    question_type = str(item.get("question_type", fact.get("fact_type", fact.get("subtopic", "generic")))).strip()
    explanation = str(item.get("explanation", "")).strip()

    if not question:
        return None
    if not isinstance(options, list) or len(options) != 4:
        return None

    options = [str(x).strip() for x in options]
    if any(not x for x in options):
        return None

    # respuesta correcta siempre en índice 0
    if correct_index != 0:
        return None

    # quitar duplicadas
    norm_options = [normalize_text(x) for x in options]
    if len(set(norm_options)) != 4:
        return None

    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"

    return {
        "question": question,
        "options": options,
        "correctIndex": 0,
        "difficulty": difficulty,
        "tags": [
            topic_slug,
            topic_name,
            str(fact.get("subtopic", "")),
            str(question_type),
        ],
        "source": "final_facts_pipeline",
        "topic_slug": topic_slug,
        "topic_name": topic_name,
        "fact_id": fact.get("fact_id"),
        "question_type": question_type,
        "fact_statement": fact.get("statement", ""),
        "explanation": explanation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera preguntas desde final_facts.")
    parser.add_argument("--input", required=True, help="Ruta a final_facts.json")
    parser.add_argument("--output", required=True, help="Ruta salida questions.json")
    parser.add_argument("--model", default="", help="Modelo OpenAI opcional")
    parser.add_argument("--max-facts", type=int, default=9999, help="Máximo de facts a procesar")
    args = parser.parse_args()

    data = load_json(args.input)
    client = get_openai_client()

    topic_slug = data["topic_slug"]
    topic_name = data["topic_name"]
    final_facts = data.get("final_facts", [])

    usable_facts = [f for f in final_facts if is_fact_good_for_question(f)]
    usable_facts = usable_facts[:args.max_facts]

    print(f"📦 Final facts de entrada: {len(final_facts)}")
    print(f"✅ Facts aptos para pregunta: {len(usable_facts)}")

    generated_questions: List[Dict[str, Any]] = []
    seen_questions = set()

    for idx, fact in enumerate(usable_facts, start=1):
        print(f"[{idx}/{len(usable_facts)}] Generando desde fact: {fact.get('subtopic')} | {fact.get('statement')[:90]}")

        user_prompt = build_user_prompt(topic_name, fact)

        try:
            result = call_openai_json(
                client=client,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model=args.model or None,
            )
        except Exception as e:
            print(f"   ⚠ Error OpenAI: {e}")
            continue

        cleaned = clean_question_output(result, topic_slug, topic_name, fact)
        if not cleaned:
            print("   ⏭ Fact descartado o salida inválida")
            continue

        qhash = question_hash(cleaned["question"])
        if qhash in seen_questions:
            print("   ⏭ Pregunta duplicada")
            continue

        seen_questions.add(qhash)
        generated_questions.append(cleaned)

    output = {
        "topic_slug": topic_slug,
        "topic_name": topic_name,
        "questions_count": len(generated_questions),
        "questions": generated_questions,
    }

    save_json(args.output, output)

    print("\n✅ Preguntas generadas")
    print(f"   total: {len(generated_questions)}")
    print(f"   output: {args.output}")


if __name__ == "__main__":
    main()