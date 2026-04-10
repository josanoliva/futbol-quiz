import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.local")

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")

if not SUPABASE_URL:
    raise RuntimeError("Falta NEXT_PUBLIC_SUPABASE_URL en .env o .env.local")

if not SUPABASE_KEY:
    raise RuntimeError("Falta SUPABASE_SERVICE_ROLE_KEY en .env o .env.local")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_question(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def get_headers() -> Dict[str, str]:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def fetch_existing_questions() -> Dict[str, Dict[str, Any]]:
    existing: Dict[str, Dict[str, Any]] = {}
    page_size = 1000
    offset = 0

    while True:
        url = f"{SUPABASE_URL}/rest/v1/questions"
        params = {
            "select": "id,question",
            "offset": offset,
            "limit": page_size,
        }

        response = requests.get(url, headers=get_headers(), params=params, timeout=30)
        response.raise_for_status()

        rows = response.json()
        if not rows:
            break

        for row in rows:
            q = row.get("question", "")
            if q:
                existing[normalize_question(q)] = row

        if len(rows) < page_size:
            break

        offset += page_size

    return existing


def map_question_for_db(q: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "question": q["question"],
        "options": q["options"],
        "correct_index": q["correctIndex"],
        "difficulty": q["difficulty"],
        "tags": q.get("tags", []),
        "source": ", ".join(q.get("source_fact_ids", [])) if q.get("source_fact_ids") else None,
    }


def insert_questions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return []

    url = f"{SUPABASE_URL}/rest/v1/questions"
    response = requests.post(url, headers=get_headers(), json=rows, timeout=60)
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Importar preguntas válidas a Supabase evitando duplicados")
    parser.add_argument("--file", required=True, help="Ruta al JSON validated")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {file_path}")

    payload = load_json(file_path)
    questions = payload.get("questions", [])

    valid_questions = [
        q for q in questions
        if q.get("validation", {}).get("is_valid", False)
    ]

    print(f"📦 Preguntas válidas detectadas: {len(valid_questions)}")

    existing = fetch_existing_questions()
    print(f"🧠 Preguntas ya existentes en BD: {len(existing)}")

    to_insert: List[Dict[str, Any]] = []
    skipped = 0

    for q in valid_questions:
        normalized = normalize_question(q["question"])
        if normalized in existing:
            skipped += 1
            continue
        to_insert.append(map_question_for_db(q, payload))

    print(f"⏭ Duplicadas saltadas: {skipped}")
    print(f"✅ Nuevas a insertar: {len(to_insert)}")

    if not to_insert:
        print("Nada nuevo que insertar.")
        return

    inserted = insert_questions(to_insert)
    print(f"🚀 Insertadas en Supabase: {len(inserted)}")


if __name__ == "__main__":
    main()