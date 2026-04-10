import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")

if not OPENAI_API_KEY:
    raise RuntimeError("Falta OPENAI_API_KEY en el archivo .env")

client = OpenAI(api_key=OPENAI_API_KEY)

BASE_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = BASE_DIR / "imports" / "generated"
REVIEWED_DIR = BASE_DIR / "imports" / "reviewed"

REVIEWED_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_question_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


def local_duplicate_groups(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detección MUY simple de duplicados exactos/casi exactos dentro del mismo lote.
    Esto NO sustituye al dedupe del importador.
    """
    seen: Dict[str, List[str]] = {}
    for q in questions:
        key = normalize_question_text(q.get("question", ""))
        seen.setdefault(key, []).append(q.get("id", ""))

    duplicates = []
    for key, ids in seen.items():
        if len(ids) > 1:
            duplicates.append({
                "normalized_question": key,
                "question_ids": ids
            })
    return duplicates


def build_system_prompt() -> str:
    return """
Eres un revisor experto de preguntas de fútbol en español para un banco global de quizzes.

Tu trabajo NO es crear preguntas nuevas salvo cuando debas proponer una corrección.
Tu trabajo es REVISAR la calidad de cada pregunta.

Debes revisar:

1. Exactitud factual:
- si parece correcta
- si parece incorrecta
- si es dudosa / necesitaría verificación externa

2. Calidad:
- si es demasiado obvia
- si es ambigua
- si está mal redactada
- si no es autocontenida
- si los distractores son flojos
- si la dificultad declarada no encaja

3. Reutilización:
- si la pregunta sirve fuera del quiz original
- si necesita más contexto en el enunciado

4. Tags:
- si faltan tags importantes
- si los tags son inconsistentes

Reglas:
- sé exigente
- penaliza preguntas demasiado fáciles
- penaliza preguntas plausibles pero dudosas
- si una pregunta es incorrecta o ambigua, sugiere una versión mejor
- no inventes seguridad total si no la tienes

Tu salida debe ser JSON válido.
""".strip()


def build_user_prompt(payload: Dict[str, Any]) -> str:
    return f"""
Revisa este lote de preguntas.

Contexto del lote:
- theme: {payload.get("theme", payload.get("theme_slug", "desconocido"))}
- generated_at: {payload.get("generated_at", "desconocido")}

Preguntas:
{json.dumps(payload.get("questions", []), ensure_ascii=False)}

Devuelve SOLO JSON con este formato:

{{
  "summary": {{
    "total_questions": 0,
    "accepted_count": 0,
    "needs_review_count": 0,
    "rejected_count": 0
  }},
  "reviews": [
    {{
      "id": "string",
      "verdict": "accepted | needs_review | rejected",
      "confidence": 0.0,
      "issues": ["string"],
      "suggested_question": "string or null",
      "suggested_options": ["string", "string", "string", "string"] or null,
      "suggested_correctIndex": 0 or null,
      "suggested_difficulty": "easy | medium | hard" or null,
      "suggested_tags": ["string", "string"] or null,
      "notes": "string"
    }}
  ]
}}

Criterios:
- accepted = sólida y publicable
- needs_review = probablemente utilizable, pero con dudas o ajustes
- rejected = incorrecta, floja, demasiado obvia o demasiado dudosa
- confidence entre 0 y 1
- si la pregunta es incorrecta o ambigua, intenta corregirla
- si está bien, suggested_* puede ser null
- sé duro con preguntas obvias
Devuelve SOLO JSON.
""".strip()


def call_review_model(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={"format": {"type": "json_object"}},
    )
    return json.loads(response.output_text)


def apply_review(
    original_questions: List[Dict[str, Any]],
    reviews: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    review_map = {r["id"]: r for r in reviews}
    reviewed_questions = []

    for q in original_questions:
        qid = q.get("id")
        review = review_map.get(qid, None)

        item = {
            **q,
            "review": review or {
                "verdict": "needs_review",
                "confidence": 0.0,
                "issues": ["missing_review"],
                "suggested_question": None,
                "suggested_options": None,
                "suggested_correctIndex": None,
                "suggested_difficulty": None,
                "suggested_tags": None,
                "notes": "No se encontró review para esta pregunta"
            }
        }

        reviewed_questions.append(item)

    return reviewed_questions


def build_output_payload(
    original_payload: Dict[str, Any],
    review_payload: Dict[str, Any]
) -> Dict[str, Any]:
    questions = original_payload.get("questions", [])
    reviews = review_payload.get("reviews", [])
    summary = review_payload.get("summary", {})

    reviewed_questions = apply_review(questions, reviews)
    duplicate_groups = local_duplicate_groups(questions)

    accepted = [q for q in reviewed_questions if q["review"]["verdict"] == "accepted"]
    needs_review = [q for q in reviewed_questions if q["review"]["verdict"] == "needs_review"]
    rejected = [q for q in reviewed_questions if q["review"]["verdict"] == "rejected"]

    return {
        "theme": original_payload.get("theme"),
        "theme_slug": original_payload.get("theme_slug"),
        "generated_at": original_payload.get("generated_at"),
        "reviewed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "question_count": len(questions),
        "review_summary": summary,
        "local_duplicate_groups": duplicate_groups,
        "accepted_questions": accepted,
        "needs_review_questions": needs_review,
        "rejected_questions": rejected,
        "all_reviewed_questions": reviewed_questions
    }


def review_file(file_path: Path) -> Path:
    payload = load_json(file_path)

    review_payload = call_review_model(
        build_system_prompt(),
        build_user_prompt(payload)
    )

    output_payload = build_output_payload(payload, review_payload)

    reviewed_name = f"{file_path.stem}_reviewed.json"
    out_path = REVIEWED_DIR / reviewed_name
    save_json(out_path, output_payload)

    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Revisar lotes de preguntas generadas")
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Ruta del JSON generado a revisar",
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        raise FileNotFoundError(f"No existe el fichero: {file_path}")

    out_path = review_file(file_path)
    print(f"✅ Review guardada en: {out_path}")


if __name__ == "__main__":
    main()