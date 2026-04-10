# -*- coding: utf-8 -*-
import argparse
from typing import Dict, Any, List

from topic_pipeline_common import (
    call_openai_json,
    fetch_url_text,
    get_openai_client,
    load_json,
    save_json,
    short_text_hash,
    split_long_text,
    statement_hash,
    sleep_brief,
)

# =========================
# CONFIG MÁS BARATA
# =========================
MAX_SECTIONS_PER_URL = 12
MAX_CHUNKS_PER_SECTION = 2
MAX_FACTS_PER_URL = 40
MAX_CHARS_PER_CHUNK = 2200

EXCLUDED_SECTION_KEYWORDS = [
    "vida privada",
    "personal life",
    "impacto social",
    "impact",
    "social",
    "business",
    "negocio",
    "negocios",
    "media",
    "wealth",
    "sponsorship",
    "sponsorships",
    "comparisons",
    "comparison",
    "comparación",
    "comparaciones",
    "philanthropy",
    "family",
    "relationships",
    "tax",
    "fraud",
    "condena",
    "evasión fiscal",
    "public art",
    "popularidad",
    "popularity",
    "reception",
]

SYSTEM_PROMPT = """
Eres un extractor de facts de fútbol para quizzes.
Debes extraer SOLO hechos explícitos, estables, concretos y verificables.
No inventes nada. No completes huecos. No infieras.

Devuelve JSON válido con:
{
  "candidate_facts": [
    {
      "statement": "...",
      "subtopic": "...",
      "confidence": 0.0,
      "questionability_score": 1-5,
      "stability_score": 1-5,
      "fact_type": "...",
      "evidence_quote": "fragmento corto de soporte"
    }
  ]
}

Reglas:
- Máximo 5 candidate_facts por bloque
- SOLO usa subtopics permitidos
- statement debe ser claro, autónomo y breve
- questionability_score = qué bien sirve para hacer preguntas
- stability_score = qué poco cambia con el tiempo
- Evita opiniones, rankings vagos y frases promocionales
- Evita duplicados dentro del mismo bloque
- Céntrate en fútbol: clubes, selección, títulos, récords, posición, hitos
- Evita vida privada, negocios, marketing, popularidad y controversias no deportivas
"""


def is_valid_section_heading(heading: str) -> bool:
    h = (heading or "").strip().lower()
    if not h:
        return True

    for kw in EXCLUDED_SECTION_KEYWORDS:
        if kw in h:
            return False
    return True


def build_user_prompt(
    topic_name: str,
    topic_slug: str,
    entity_type: str,
    allowed_subtopics: List[str],
    url: str,
    title: str,
    heading: str,
    text_chunk: str,
) -> str:
    return f"""
TEMA: {topic_name}
TOPIC_SLUG: {topic_slug}
ENTITY_TYPE: {entity_type}
URL: {url}
TITLE: {title}
SECTION_HEADING: {heading}

SUBTOPICS PERMITIDOS:
{", ".join(allowed_subtopics)}

TEXTO:
{text_chunk}
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrae candidate_facts por subtopic desde topic_map.")
    parser.add_argument("--topic-map", required=True, help="Ruta al topic_map.json")
    parser.add_argument("--output", required=True, help="Ruta de salida candidate_facts.json")
    parser.add_argument("--model", default="", help="Modelo OpenAI opcional")
    args = parser.parse_args()

    topic_map = load_json(args.topic_map)
    client = get_openai_client()

    topic_slug = topic_map["topic_slug"]
    topic_name = topic_map["topic_name"]
    entity_type = topic_map["entity_type"]
    source_urls = topic_map["source_urls"]
    allowed_subtopics = [x["name"] for x in topic_map["subtopics"]]

    all_candidate_facts = []
    pages_output = []

    print(f"📦 URLs a procesar: {len(source_urls)}")
    print(f"🧩 Subtopics permitidos: {', '.join(allowed_subtopics)}")

    for i, url in enumerate(source_urls, start=1):
        print(f"\n[{i}/{len(source_urls)}] Procesando {url}")
        page = fetch_url_text(url)

        page_item = {
            "url": url,
            "ok": page["ok"],
            "error": page["error"],
            "title": page["title"],
            "sections": [],
        }

        if not page["ok"]:
            pages_output.append(page_item)
            print(f"   ⚠ Error leyendo URL: {page['error']}")
            continue

        valid_sections = [
            sec for sec in page["sections"]
            if is_valid_section_heading(sec.get("heading", ""))
            and len(sec.get("text", "").strip()) >= 80
        ]

        valid_sections = valid_sections[:MAX_SECTIONS_PER_URL]
        url_candidate_count = 0

        for sec_idx, sec in enumerate(valid_sections, start=1):
            heading = sec.get("heading", "Introduction")
            section_text = sec.get("text", "").strip()

            chunks = split_long_text(section_text, max_chars=MAX_CHARS_PER_CHUNK)
            chunks = chunks[:MAX_CHUNKS_PER_SECTION]

            section_item = {
                "heading": heading,
                "chunks": []
            }

            for chunk_idx, chunk in enumerate(chunks, start=1):
                print(f"   - Sección {sec_idx}, chunk {chunk_idx}/{len(chunks)}: {heading}")

                user_prompt = build_user_prompt(
                    topic_name=topic_name,
                    topic_slug=topic_slug,
                    entity_type=entity_type,
                    allowed_subtopics=allowed_subtopics,
                    url=url,
                    title=page["title"],
                    heading=heading,
                    text_chunk=chunk,
                )

                try:
                    result = call_openai_json(
                        client=client,
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                        model=args.model or None,
                        temperature=0.1,
                    )
                except Exception as e:
                    print(f"     ⚠ Error OpenAI: {e}")
                    result = {"candidate_facts": []}

                chunk_facts = []
                for item in result.get("candidate_facts", []):
                    if url_candidate_count >= MAX_FACTS_PER_URL:
                        break

                    statement = str(item.get("statement", "")).strip()
                    subtopic = str(item.get("subtopic", "")).strip()
                    evidence_quote = str(item.get("evidence_quote", "")).strip()

                    if not statement or not subtopic:
                        continue
                    if subtopic not in allowed_subtopics:
                        continue

                    fact = {
                        "fact_id": statement_hash(topic_slug, subtopic, statement),
                        "topic_slug": topic_slug,
                        "topic_name": topic_name,
                        "entity_type": entity_type,
                        "subtopic": subtopic,
                        "fact_type": str(item.get("fact_type", subtopic)).strip() or subtopic,
                        "statement": statement,
                        "confidence": float(item.get("confidence", 0.7)),
                        "questionability_score": int(item.get("questionability_score", 3)),
                        "stability_score": int(item.get("stability_score", 3)),
                        "source_url": url,
                        "source_title": page["title"],
                        "section_heading": heading,
                        "chunk_id": short_text_hash(f"{url}|{heading}|{chunk}"),
                        "evidence_quote": evidence_quote[:280],
                    }

                    chunk_facts.append(fact)
                    all_candidate_facts.append(fact)
                    url_candidate_count += 1

                section_item["chunks"].append({
                    "chunk_index": chunk_idx,
                    "chunk_length": len(chunk),
                    "candidate_facts_count": len(chunk_facts),
                })

                sleep_brief(0.25)

                if url_candidate_count >= MAX_FACTS_PER_URL:
                    print(f"   ⏭ Límite de facts alcanzado para esta URL ({MAX_FACTS_PER_URL})")
                    break

            if section_item["chunks"]:
                page_item["sections"].append(section_item)

            if url_candidate_count >= MAX_FACTS_PER_URL:
                break

        print(f"   ✅ facts sacados de URL: {url_candidate_count}")
        pages_output.append(page_item)

    output = {
        "topic_slug": topic_slug,
        "topic_name": topic_name,
        "entity_type": entity_type,
        "allowed_subtopics": allowed_subtopics,
        "candidate_facts_count": len(all_candidate_facts),
        "candidate_facts": all_candidate_facts,
        "pages": pages_output,
    }

    save_json(args.output, output)

    print("\n✅ candidate_facts generados")
    print(f"   total: {len(all_candidate_facts)}")
    print(f"   output: {args.output}")


if __name__ == "__main__":
    main()