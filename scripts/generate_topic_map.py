# -*- coding: utf-8 -*-
import argparse
from typing import Dict, Any, List

from topic_pipeline_common import (
    ENTITY_SUBTOPICS,
    call_openai_json,
    fetch_url_text,
    get_openai_client,
    load_urls_input,
    save_json,
    slugify,
    split_long_text,
    sleep_brief,
)


SYSTEM_PROMPT = """
Eres un clasificador experto de contenido de fútbol para construir quizzes.
Tu trabajo es:
1) detectar el tipo principal de entidad del tema
2) proponer subtemas útiles para generar preguntas de quiz
3) basarte SOLO en la información disponible

Devuelve JSON válido con:
- topic_name
- entity_type
- confidence (0 a 1)
- suggested_subtopics: array de objetos {name, priority, reason}
- notes

Tipos permitidos:
- player
- club
- competition
- national_team
- coach
- other

Reglas:
- Prioriza subtemas útiles para preguntas objetivas y estables
- No inventes datos
- Máximo 12 subtemas
"""


def build_user_prompt(topic_name: str, url_summaries: List[Dict[str, Any]]) -> str:
    allowed = {
        k: v for k, v in ENTITY_SUBTOPICS.items()
    }

    text = [
        f"TEMA PRINCIPAL: {topic_name}",
        "",
        "SUBTEMAS PERMITIDOS POR TIPO DE ENTIDAD:",
    ]
    for entity_type, subtopics in allowed.items():
        text.append(f"- {entity_type}: {', '.join(subtopics)}")

    text.append("")
    text.append("RESUMEN DE URLS:")
    for item in url_summaries:
        text.append(f"URL: {item['url']}")
        text.append(f"TITLE: {item['title']}")
        text.append(f"SNIPPET: {item['snippet']}")
        text.append("")

    return "\n".join(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera un topic_map a partir de URLs.")
    parser.add_argument("--input", required=True, help="JSON con lista de URLs")
    parser.add_argument("--output", required=True, help="Ruta de salida topic_map.json")
    parser.add_argument("--topic-name", required=True, help="Nombre visible del tema")
    parser.add_argument("--topic-slug", default="", help="Slug manual. Si no, se deriva del nombre.")
    parser.add_argument("--model", default="", help="Modelo OpenAI opcional")
    args = parser.parse_args()

    topic_name = args.topic_name.strip()
    topic_slug = args.topic_slug.strip() or slugify(topic_name)

    urls = load_urls_input(args.input)
    client = get_openai_client()

    url_summaries = []
    fetched_pages = []

    print(f"📦 URLs detectadas: {len(urls)}")

    for idx, url in enumerate(urls, start=1):
        print(f"[{idx}/{len(urls)}] Leyendo {url}")
        page = fetch_url_text(url)
        fetched_pages.append(page)

        snippet = ""
        if page["ok"]:
            chunks = split_long_text(page["text"], max_chars=700)
            snippet = chunks[0] if chunks else ""
            snippet = snippet[:700]

        url_summaries.append({
            "url": url,
            "title": page.get("title", ""),
            "snippet": snippet,
            "ok": page.get("ok", False),
            "error": page.get("error"),
        })

        sleep_brief(0.2)

    valid_summaries = [x for x in url_summaries if x["ok"]]
    if not valid_summaries:
        raise RuntimeError("No se pudo leer ninguna URL correctamente.")

    user_prompt = build_user_prompt(topic_name, valid_summaries)

    result = call_openai_json(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=args.model or None,
        temperature=0.1,
    )

    entity_type = result.get("entity_type", "other")
    allowed_subtopics = ENTITY_SUBTOPICS.get(entity_type, ENTITY_SUBTOPICS["other"])

    suggested_subtopics = result.get("suggested_subtopics", [])
    cleaned_subtopics = []

    seen = set()
    for item in suggested_subtopics:
        name = str(item.get("name", "")).strip()
        if name not in allowed_subtopics:
            continue
        if name in seen:
            continue
        seen.add(name)
        cleaned_subtopics.append({
            "name": name,
            "priority": int(item.get("priority", 3)),
            "reason": str(item.get("reason", "")).strip()
        })

    # fallback por si el modelo devuelve poco
    if not cleaned_subtopics:
        cleaned_subtopics = [
            {"name": name, "priority": 3, "reason": "Fallback por tipo de entidad"}
            for name in allowed_subtopics[:8]
        ]

    topic_map = {
        "topic_slug": topic_slug,
        "topic_name": topic_name,
        "entity_type": entity_type,
        "entity_confidence": float(result.get("confidence", 0.7)),
        "notes": result.get("notes", ""),
        "source_urls": urls,
        "subtopics": cleaned_subtopics,
        "url_summaries": url_summaries,
    }

    save_json(args.output, topic_map)

    print("\n✅ topic_map generado")
    print(f"   topic_slug: {topic_slug}")
    print(f"   entity_type: {entity_type}")
    print(f"   subtopics: {len(cleaned_subtopics)}")
    print(f"   output: {args.output}")


if __name__ == "__main__":
    main()