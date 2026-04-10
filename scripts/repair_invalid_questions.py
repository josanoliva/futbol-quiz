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
OUT_DIR = BASE_DIR / "imports" / "repaired"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def index_safe_facts_by_id(facts_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    safe_facts = facts_payload.get("safe_facts", [])
    return {fact["fact_id"]: fact for fact in safe_facts if "fact_id" in fact}


def build_system_prompt() -> str:
    return """
Eres un reparador experto de preguntas de fútbol en español.

Tu trabajo:
- rehacer SOLO preguntas inválidas o flojas
- mantener fidelidad total a los hechos fuente
- mejorar sobre todo:
  - distractores
  - coherencia semántica de opciones
  - calidad de redacción
  - dificultad realista

REGLAS CRÍTICAS:
- NO inventes datos fuera de los safe_facts dados
- conserva source_fact_ids
- conserva el enfoque general de la pregunta si es salvable
- si la pregunta original era mala, puedes reescribirla entera
- las 4 opciones deben ser del mismo tipo semántico
- evita distractores absurdos
- evita que la correcta sea demasiado obvia
- la pregunta debe ser autocontenida
- mayoría medium/hard
- si no puedes arreglar una pregunta de forma fiable, genera una nueva basada en los mismos safe_facts

Devuelve SOLO JSON válido.
""".strip()


def build_user_prompt(
    theme: str,
    invalid_questions: List[Dict[str, Any]],
    fact_index: Dict[str, Dict[str, Any]],
) -> str:
    repair_items = []

    for q in invalid_questions:
        source_fact_ids = q.get("source_fact_ids", [])
        linked_facts = [fact_index[fid] for fid in source_fact_ids if fid in fact_index]

        repair_items.append({
            "original_question": {
                "id": q.get("id"),
                "question": q.get("question"),
                "options": q.get("options"),
                "correctIndex": q.get("correctIndex"),
                "difficulty": q.get("difficulty"),
                "tags": q.get("tags"),
                "source_fact_ids": source_fact_ids,
                "source_notes": q.get("source_notes", []),
                "validation": q.get("validation", {}),
            },
            "linked_safe_facts": linked_facts,
        })

    return f"""
Tema: {theme}

Repara estas preguntas inválidas o flojas.

Datos:
{json.dumps(repair_items, ensure_ascii=False)}

Devuelve SOLO JSON con este formato:

{{
  "repaired_questions": [
    {{
      "id": "string",
      "question": "string",
      "options": ["string", "string", "string", "string"],
      "correctIndex": 0,
      "difficulty": "easy | medium | hard",
      "tags": ["string", "string"],
      "source_fact_ids": ["string"],
      "source_notes": ["string"]
    }}
  ]
}}

Reglas:
- devuelve una pregunta reparada por cada pregunta original inválida
- mantén el mismo id
- mantén source_fact_ids
- mantén source_notes si siguen teniendo sentido
- puedes mejorar tags
- evita preguntas de ficha demasiado básicas si hay margen
- NO inventes hechos fuera de linked_safe_facts
- las 4 opciones deben ser coherentes entre sí
Devuelve SOLO JSON.
""".strip()


def call_openai_repair(
    theme: str,
    invalid_questions: List[Dict[str, Any]],
    fact_index: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": build_user_prompt(theme, invalid_questions, fact_index)},
        ],
        text={"format": {"type": "json_object"}},
    )
    return json.loads(response.output_text)


def merge_repaired_questions(
    original_questions: List[Dict[str, Any]],
    repaired_questions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    repaired_by_id = {q["id"]: q for q in repaired_questions if "id" in q}
    merged = []

    for q in original_questions:
        qid = q.get("id")
        if qid in repaired_by_id:
            repaired = repaired_by_id[qid]
            merged.append(repaired)
        else:
            clean_original = dict(q)
            clean_original.pop("validation", None)
            merged.append(clean_original)

    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Reparar preguntas inválidas usando safe_facts")
    parser.add_argument("--validated", required=True, help="Ruta al JSON validated")
    parser.add_argument("--facts", required=True, help="Ruta al JSON facts")
    args = parser.parse_args()

    validated_path = Path(args.validated)
    facts_path = Path(args.facts)

    if not validated_path.exists():
        raise FileNotFoundError(f"No existe el archivo validated: {validated_path}")
    if not facts_path.exists():
        raise FileNotFoundError(f"No existe el archivo facts: {facts_path}")

    validated_payload = load_json(validated_path)
    facts_payload = load_json(facts_path)

    theme = validated_payload.get("theme", "tema")
    questions = validated_payload.get("questions", [])
    invalid_questions = [
        q for q in questions
        if not q.get("validation", {}).get("is_valid", False)
    ]

    if not invalid_questions:
        print("✅ No hay preguntas inválidas que reparar.")
        return

    fact_index = index_safe_facts_by_id(facts_payload)

    print(f"🛠 Reparando {len(invalid_questions)} preguntas inválidas...")
    repaired_payload = call_openai_repair(theme, invalid_questions, fact_index)
    repaired_questions = repaired_payload.get("repaired_questions", [])

    merged_questions = merge_repaired_questions(questions, repaired_questions)

    final_payload = {
        "theme": validated_payload.get("theme"),
        "theme_slug": validated_payload.get("theme_slug"),
        "generated_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "question_count": len(merged_questions),
        "questions": merged_questions,
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    theme_slug = validated_payload.get("theme_slug", "tema")
    out_path = OUT_DIR / f"{theme_slug}_repaired_{timestamp}.json"

    save_json(out_path, final_payload)

    print(f"✅ Preguntas reparadas guardadas en: {out_path}")


if __name__ == "__main__":
    main()