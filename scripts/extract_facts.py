import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
import trafilatura
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")

if not OPENAI_API_KEY:
    raise RuntimeError("Falta OPENAI_API_KEY en el archivo .env")

client = OpenAI(api_key=OPENAI_API_KEY)

BASE_DIR = Path(__file__).resolve().parent.parent
FACTS_DIR = BASE_DIR / "imports" / "facts"
DEBUG_DIR = BASE_DIR / "imports" / "facts_debug"

FACTS_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------
# UTIL
# ---------------------------

def slugify(text: str) -> str:
    text = text.strip().lower()
    replacements = {
        "á": "a", "à": "a", "ä": "a", "â": "a",
        "é": "e", "è": "e", "ë": "e", "ê": "e",
        "í": "i", "ì": "i", "ï": "i", "î": "i",
        "ó": "o", "ò": "o", "ö": "o", "ô": "o",
        "ú": "u", "ù": "u", "ü": "u", "û": "u",
        "ñ": "n"
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def fetch_url_text(url: str, timeout: int = 20) -> Dict[str, Any]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; FutbolQuizBot/1.0)"
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        downloaded = response.text
        extracted = trafilatura.extract(
            downloaded,
            include_links=False,
            include_images=False,
            favor_precision=False,
            favor_recall=True,
        )

        if not extracted or len(extracted.strip()) < 300:
            text_fallback = re.sub(r"<[^>]+>", " ", downloaded)
            text_fallback = re.sub(r"\s+", " ", text_fallback).strip()
            extracted = text_fallback[:50000]

        return {
            "url": url,
            "ok": True,
            "status_code": response.status_code,
            "text": extracted or ""
        }
    except Exception as e:
        return {
            "url": url,
            "ok": False,
            "status_code": None,
            "text": "",
            "error": str(e)
        }


# ---------------------------
# PROMPTS
# ---------------------------

def build_system_prompt() -> str:
    return """
Eres un extractor de hechos de fútbol en español.

Tu trabajo es extraer SOLO hechos razonablemente respaldados por el texto.
Debes ser prudente, pero no excesivamente conservador.

Reglas:
- extrae hechos concretos y útiles
- usa frases cercanas al texto fuente
- no inventes
- no completes huecos
- incluye una cita breve exacta en evidence_quote
- si el hecho es especialmente delicado (primer gol, debut, primer entrenador, primera victoria histórica, minuto exacto), márcalo con needs_manual_review = true
- prioriza hechos útiles para generar preguntas después

Tipos de hechos útiles:
- fundacion
- estadio
- debut
- primer_gol
- rival
- final
- eliminatoria
- entrenador
- ascenso
- titulo
- historia
- traspaso
- capitania
- record
- otro

Devuelve SOLO JSON válido.
""".strip()


def build_user_prompt(topic: str, sources: List[Dict[str, Any]]) -> str:
    safe_sources = []
    for src in sources:
        if src.get("ok") and src.get("text"):
            trimmed_text = src["text"][:15000]
            safe_sources.append({
                "url": src["url"],
                "text": trimmed_text
            })

    return f"""
Extrae hechos verificables sobre este tema: {topic}

Fuentes:
{json.dumps(safe_sources, ensure_ascii=False)}

Devuelve SOLO JSON con este formato:

{{
  "facts": [
    {{
      "fact_id": "string",
      "fact_type": "fundacion | estadio | debut | primer_gol | rival | final | eliminatoria | entrenador | ascenso | titulo | historia | traspaso | capitania | record | otro",
      "statement": "string",
      "evidence_quote": "string",
      "source_url": "string",
      "confidence": 0.0,
      "needs_manual_review": true,
      "tags": ["string", "string"]
    }}
  ]
}}

Reglas:
- mejor 8-20 hechos buenos que muchos dudosos
- si el texto sí respalda bien un hecho, inclúyelo
- confidence entre 0.5 y 0.95
- usa needs_manual_review = false solo cuando el hecho es bastante claro y poco conflictivo
- usa tags útiles y canónicos
- si hay varios debuts en contextos distintos, se pueden incluir todos
- si hay títulos en contextos distintos, se pueden incluir todos
- si hay capitanías en contextos distintos, se pueden incluir todos
- no mezcles hechos distintos como si fueran conflicto
Devuelve SOLO JSON.
""".strip()


def extract_facts_with_openai(topic: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": build_user_prompt(topic, sources)},
        ],
        text={"format": {"type": "json_object"}},
    )
    return json.loads(response.output_text)


# ---------------------------
# SUBKEY / CONFLICTS
# ---------------------------

SENSITIVE_FACT_TYPES = {
    "primer_gol",
    "debut",
    "entrenador",
    "rival",
    "final",
    "eliminatoria",
    "ascenso",
}

def extract_years(text: str) -> List[str]:
    return re.findall(r"\b(19\d{2}|20\d{2})\b", text)


def infer_context_tokens(text: str) -> List[str]:
    t = normalize_text(text)
    candidates = [
        "sevilla f. c. b", "sevilla b", "sevilla atletico", "sevilla atlético",
        "sevilla", "real madrid", "madridista", "espana", "españa",
        "seleccion absoluta", "selección absoluta", "seleccion", "selección",
        "primera division", "primera división", "segunda division", "segunda división",
        "segunda division b", "segunda división b", "champions", "liga de campeones",
        "eurocopa", "mundial", "olympiakos", "celta de vigo", "deportivo de la coruna",
        "deportivo de la coruña", "monterrey", "psg"
    ]
    found = [c for c in candidates if c in t]
    return found


def infer_subkey(fact: Dict[str, Any]) -> str:
    statement = normalize_text(fact.get("statement", ""))
    evidence = normalize_text(fact.get("evidence_quote", ""))
    fact_type = fact.get("fact_type", "otro")

    merged = f"{statement} {evidence}"
    years = extract_years(merged)
    ctx = infer_context_tokens(merged)
    ctx_part = "-".join(slugify(x) for x in ctx[:3]) if ctx else "generic"
    years_part = "-".join(years[:2]) if years else "na"

    if fact_type == "debut":
        return f"debut-{ctx_part}-{years_part}"

    if fact_type == "primer_gol":
        return f"primer-gol-{ctx_part}-{years_part}"

    if fact_type == "entrenador":
        if "debut" in merged:
            return f"entrenador-debut-{ctx_part}-{years_part}"
        if "banquillo" in merged:
            return f"entrenador-banquillo-{ctx_part}-{years_part}"
        return f"entrenador-{ctx_part}-{years_part}"

    if fact_type == "titulo":
        if "real madrid" in merged or "madridista" in merged:
            return f"titulo-real-madrid-{years_part}"
        if "espana" in merged or "españa" in merged or "seleccion" in merged or "selección" in merged:
            return f"titulo-seleccion-{years_part}"
        return f"titulo-{ctx_part}-{years_part}"

    if fact_type == "capitania":
        if "real madrid" in merged:
            return f"capitania-real-madrid-{years_part}"
        if "espana" in merged or "españa" in merged or "seleccion" in merged or "selección" in merged:
            return f"capitania-seleccion-{years_part}"
        return f"capitania-{ctx_part}-{years_part}"

    if fact_type == "traspaso":
        return f"traspaso-{ctx_part}-{years_part}"

    if fact_type == "record":
        return f"record-{ctx_part}-{years_part}"

    if fact_type == "historia":
        if "sociedad anonima deportiva" in merged or "sociedad anónima deportiva" in merged or "sad" in merged:
            return f"historia-sad-{years_part}"
        if "capitan" in merged or "capitán" in merged:
            return f"historia-capitania-{ctx_part}-{years_part}"
        if "transferido" in merged or "traspasado" in merged:
            return f"historia-traspaso-{ctx_part}-{years_part}"
        return f"historia-{ctx_part}-{years_part}"

    if fact_type == "rival":
        return f"rival-{ctx_part}-{years_part}"

    if fact_type == "estadio":
        if "inaugur" in merged:
            return "estadio-inauguracion"
        if "capacidad" in merged:
            return "estadio-capacidad"
        return "estadio-actual"

    if fact_type == "fundacion":
        return "fundacion"

    if fact_type == "ascenso":
        return f"ascenso-{ctx_part}-{years_part}"

    if fact_type == "final":
        return f"final-{ctx_part}-{years_part}"

    if fact_type == "eliminatoria":
        return f"eliminatoria-{ctx_part}-{years_part}"

    return f"{fact_type}-{ctx_part}-{years_part}"


def detect_conflicts(facts: List[Dict[str, Any]], source_count: int) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []

    for fact in facts:
        fact["conflict"] = False
        enriched.append(fact)

    if source_count <= 1:
        return enriched

    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    for fact in enriched:
        key = (fact.get("fact_type", "otro"), infer_subkey(fact))
        grouped.setdefault(key, []).append(fact)

    reviewed: List[Dict[str, Any]] = []

    for _, items in grouped.items():
        if len(items) == 1:
            reviewed.append(items[0])
            continue

        normalized_statements = list(set(normalize_text(i.get("statement", "")) for i in items if i.get("statement")))

        if len(normalized_statements) > 1:
            values = [i.get("statement", "") for i in items]
            for item in items:
                item["conflict"] = True
                item["needs_manual_review"] = True
                item["conflict_values"] = values
                item["review_reason"] = "Conflicto entre fuentes sobre el mismo subhecho"
                reviewed.append(item)
        else:
            for item in items:
                reviewed.append(item)

    return reviewed


# ---------------------------
# TAGS
# ---------------------------

def canonical_tags(topic_slug: str, fact_type: str, existing_tags: List[str], statement: str = "") -> List[str]:
    tags = [topic_slug]
    tags.extend(existing_tags or [])

    type_map = {
        "fundacion": ["historia"],
        "estadio": ["estadios"],
        "debut": ["debut"],
        "primer_gol": ["goles", "primer-gol"],
        "rival": ["rivales"],
        "final": ["finales"],
        "eliminatoria": ["eliminatorias"],
        "entrenador": ["entrenadores"],
        "ascenso": ["ascenso"],
        "titulo": ["titulos"],
        "historia": ["historia"],
        "traspaso": ["fichajes", "traspasos"],
        "capitania": ["capitanes"],
        "record": ["records"],
        "otro": [],
    }

    tags.extend(type_map.get(fact_type, []))

    merged = normalize_text(statement)

    # jugadores / clubes / selecciones
    if topic_slug in ["sergio-ramos", "messi", "cristiano-ronaldo", "xavi", "iniesta"]:
        tags.append("jugadores")
    else:
        tags.append("clubes")

    # contextos frecuentes
    if "real madrid" in merged or "madridista" in merged:
        tags.append("real-madrid")
    if "sevilla" in merged:
        tags.append("sevilla")
    if "espana" in merged or "españa" in merged or "seleccion" in merged or "selección" in merged:
        tags.append("espana")
        tags.append("selecciones")
    if "champions" in merged or "liga de campeones" in merged:
        tags.append("champions-league")
    if "eurocopa" in merged:
        tags.append("eurocopa")
    if "mundial" in merged:
        tags.append("mundial")
    if "psg" in merged:
        tags.append("psg")
    if "monterrey" in merged:
        tags.append("monterrey")

    # años
    if re.search(r"\b200[0-9]\b", merged):
        tags.append("anos-2000")
    if re.search(r"\b201[0-9]\b", merged):
        tags.append("anos-2010")
    if re.search(r"\b202[0-9]\b", merged):
        tags.append("anos-2020")

    clean = []
    seen = set()
    for tag in tags:
        tag = slugify(str(tag))
        if tag and tag not in seen:
            seen.add(tag)
            clean.append(tag)

    return clean


# ---------------------------
# SAVE / DEBUG
# ---------------------------

def save_debug_sources(topic_slug: str, sources: List[Dict[str, Any]], timestamp: str) -> None:
    debug_path = DEBUG_DIR / f"{topic_slug}_sources_{timestamp}.json"
    debug_payload = []

    for src in sources:
        debug_payload.append({
            "url": src.get("url"),
            "ok": src.get("ok"),
            "status_code": src.get("status_code"),
            "text_length": len(src.get("text", "")),
            "preview": src.get("text", "")[:1500],
            "error": src.get("error")
        })

    debug_path.write_text(
        json.dumps(debug_payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def save_facts_file(topic: str, reviewed_facts: List[Dict[str, Any]]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    topic_slug = slugify(topic)

    enriched = []
    for fact in reviewed_facts:
        fact_type = fact.get("fact_type", "otro")
        statement = fact.get("statement", "")

        if fact_type in SENSITIVE_FACT_TYPES and "needs_manual_review" not in fact:
            fact["needs_manual_review"] = True

        enriched_fact = {
            **fact,
            "tags": canonical_tags(topic_slug, fact_type, fact.get("tags", []), statement),
        }
        enriched.append(enriched_fact)

    safe_facts = [
        f for f in enriched
        if not f.get("needs_manual_review", True) and not f.get("conflict", False)
    ]

    review_facts = [
        f for f in enriched
        if f.get("needs_manual_review", True) or f.get("conflict", False)
    ]

    final_payload = {
        "topic": topic,
        "topic_slug": topic_slug,
        "generated_at": timestamp,
        "safe_count": len(safe_facts),
        "review_count": len(review_facts),
        "safe_facts": safe_facts,
        "review_facts": review_facts,
    }

    out_path = FACTS_DIR / f"{topic_slug}_facts_{timestamp}.json"
    out_path.write_text(
        json.dumps(final_payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return out_path


# ---------------------------
# MAIN
# ---------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Extraer hechos verificables desde URLs")
    parser.add_argument("--topic", required=True, help='Tema, por ejemplo: "sergio-ramos"')
    parser.add_argument("--urls", required=True, help='Lista de URLs separadas por coma')
    args = parser.parse_args()

    urls = [u.strip() for u in args.urls.split(",") if u.strip()]
    if not urls:
        raise ValueError("Debes pasar al menos una URL en --urls")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    topic_slug = slugify(args.topic)

    print(f"🔎 Extrayendo textos para el tema: {args.topic}")

    sources = []
    for url in urls:
        result = fetch_url_text(url)
        sources.append(result)

        if result["ok"]:
            print(f"✅ Fuente leída: {url}")
            print(f"   Longitud texto: {len(result.get('text', ''))}")
        else:
            print(f"❌ Error leyendo {url}: {result.get('error', 'desconocido')}")

    save_debug_sources(topic_slug, sources, timestamp)

    usable_sources = [
        s for s in sources
        if s.get("ok") and s.get("text") and len(s.get("text", "")) > 200
    ]
    if not usable_sources:
        raise RuntimeError("No se pudo extraer texto útil de ninguna URL")

    print("🧠 Extrayendo hechos con OpenAI...")
    payload = extract_facts_with_openai(args.topic, usable_sources)

    raw_facts = payload.get("facts", [])
    reviewed_facts = detect_conflicts(raw_facts, source_count=len(usable_sources))

    out_path = save_facts_file(args.topic, reviewed_facts)
    print(f"✅ Hechos guardados en: {out_path}")


if __name__ == "__main__":
    main()