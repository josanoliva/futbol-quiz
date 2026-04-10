# -*- coding: utf-8 -*-
import os
import re
import json
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

# Cargar .env desde la raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


ENTITY_SUBTOPICS = {
    "player": [
        "identity",
        "birth",
        "position",
        "clubs",
        "transfers",
        "national_team",
        "titles",
        "records",
        "captaincy",
        "milestones",
        "awards",
        "retirement_or_late_career"
    ],
    "club": [
        "identity",
        "foundation",
        "city",
        "stadium",
        "colors",
        "nicknames",
        "titles",
        "historic_players",
        "historic_coaches",
        "presidents",
        "rivalries",
        "milestones"
    ],
    "competition": [
        "identity",
        "origin",
        "format",
        "participants",
        "trophy",
        "records",
        "winners",
        "finals",
        "milestones",
        "name_changes"
    ],
    "national_team": [
        "identity",
        "federation",
        "confederation",
        "stadium_or_home_venues",
        "titles",
        "historic_players",
        "historic_coaches",
        "records",
        "milestones"
    ],
    "coach": [
        "identity",
        "birth",
        "playing_career",
        "clubs_coached",
        "national_teams_coached",
        "titles",
        "style",
        "records",
        "milestones"
    ],
    "other": [
        "identity",
        "background",
        "milestones",
        "records"
    ]
}


BAD_SECTION_KEYWORDS = {
    "referencias",
    "references",
    "bibliografía",
    "bibliografia",
    "bibliography",
    "filmografía",
    "filmografia",
    "filmography",
    "enlaces externos",
    "external links",
    "notas",
    "notes",
    "véase también",
    "vease tambien",
    "see also",
    "fuentes",
    "sources",
    "citas",
    "citations",
    "further reading",
    "lecturas adicionales",
    "publicaciones",
    "discografía",
    "discografia",
    "discography",
    "palmarés detallado",
    "palmares detallado",
    "estadísticas",
    "estadisticas",
    "statistics",
    "career statistics",
    "estadísticas de carrera",
    "estadisticas de carrera"
}


BAD_TEXT_PATTERNS = [
    r"\[\d+\]",                      # [1] [23]
    r"https?://",                    # muchos enlaces
    r"\bISBN\b",
    r"\bDOI\b",
    r"\bISSN\b",
    r"\barchivado\b",
    r"\brecuperado\b",
    r"\bretrieved\b",
    r"\beditado el\b",
    r"\bconsultado el\b",
    r"\burl\b",
]


def ensure_dir(path: str) -> None:
    if path:
        os.makedirs(path, exist_ok=True)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def load_urls_input(path: str) -> List[str]:
    data = load_json(path)

    if isinstance(data, list):
        urls = [x.strip() for x in data if isinstance(x, str) and x.strip()]
        return dedupe_keep_order(urls)

    if isinstance(data, dict):
        if "urls" in data and isinstance(data["urls"], list):
            urls = [x.strip() for x in data["urls"] if isinstance(x, str) and x.strip()]
            return dedupe_keep_order(urls)

    raise ValueError(
        f"Formato no soportado en {path}. Usa una lista de URLs o {{'urls': [...]}}"
    )


def dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            f"No se encontró OPENAI_API_KEY. Revisa tu .env en: {PROJECT_ROOT / '.env'}"
        )
    return OpenAI(api_key=api_key)


def call_openai_json(
    client: OpenAI,
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    model = model or DEFAULT_MODEL

    response = client.responses.create(
        model=model,
        temperature=temperature,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_object"
            }
        }
    )

    text = response.output_text.strip()
    return json.loads(text)


def fetch_url_text(url: str, timeout: int = 20) -> Dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }

    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        return {
            "url": url,
            "ok": False,
            "error": str(e),
            "title": "",
            "text": "",
            "sections": []
        }

    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "svg", "img", "footer", "nav", "aside"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = clean_text(soup.title.string)

    sections = extract_sections(soup)
    text = "\n\n".join(
        f"{sec['heading']}\n{sec['text']}".strip()
        for sec in sections
        if sec["text"].strip()
    ).strip()

    text = clean_text(text)

    return {
        "url": url,
        "ok": True,
        "error": None,
        "title": title,
        "text": text,
        "sections": sections
    }


def is_bad_heading(heading: str) -> bool:
    h = clean_text(heading).lower()
    if not h:
        return False

    for bad in BAD_SECTION_KEYWORDS:
        if bad in h:
            return True
    return False


def looks_like_reference_dump(text: str) -> bool:
    t = clean_text(text)
    if not t:
        return False

    t_lower = t.lower()

    # demasiadas señales típicas de referencias
    pattern_hits = 0
    for pat in BAD_TEXT_PATTERNS:
        if re.search(pat, t_lower, flags=re.IGNORECASE):
            pattern_hits += 1

    # demasiados corchetes tipo cita
    bracket_refs = len(re.findall(r"\[\d+\]", t))

    # demasiados enlaces
    links = len(re.findall(r"https?://", t, flags=re.IGNORECASE))

    # líneas muy cortas concatenadas suelen ser basura de refs/índices
    words = t.split()
    avg_word_len = (sum(len(w) for w in words) / len(words)) if words else 0

    if pattern_hits >= 3:
        return True
    if bracket_refs >= 5:
        return True
    if links >= 3:
        return True
    if len(t) > 250 and avg_word_len < 4:
        return True

    return False


def extract_sections(soup: BeautifulSoup) -> List[Dict[str, str]]:
    sections: List[Dict[str, str]] = []
    current_heading = "Introduction"
    current_lines: List[str] = []

    content_root = soup.body if soup.body else soup

    def flush_section() -> None:
        nonlocal current_lines, current_heading, sections

        if not current_lines:
            return

        heading_clean = clean_text(current_heading)
        text_clean = clean_text("\n".join(current_lines))

        current_lines = []

        if not text_clean:
            return
        if len(text_clean) < 80:
            return
        if is_bad_heading(heading_clean):
            return
        if looks_like_reference_dump(text_clean):
            return

        sections.append({
            "heading": heading_clean,
            "text": text_clean
        })

    for node in content_root.find_all(["h1", "h2", "h3", "p", "li"]):
        name = node.name.lower()

        if name in {"h1", "h2", "h3"}:
            flush_section()
            next_heading = node.get_text(" ", strip=True) or current_heading
            current_heading = next_heading
            continue

        txt = node.get_text(" ", strip=True)
        txt = clean_text(txt)

        if len(txt) < 40:
            continue

        # evita líneas sueltas con demasiada pinta de referencia
        if looks_like_reference_dump(txt):
            continue

        current_lines.append(txt)

    flush_section()

    # fallback si no hay secciones útiles
    if not sections:
        all_text = clean_text(content_root.get_text("\n", strip=True))
        if all_text and len(all_text) >= 120 and not looks_like_reference_dump(all_text):
            sections.append({"heading": "Introduction", "text": all_text})

    return sections


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text, flags=re.UNICODE)
    return text.strip()


def split_long_text(text: str, max_chars: int = 3500) -> List[str]:
    text = clean_text(text)
    if len(text) <= max_chars:
        return [text] if text else []

    sentences = re.split(r"(?<=[\.\!\?])\s+", text)
    chunks = []
    current = ""

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        if len(current) + len(sent) + 1 <= max_chars:
            current = f"{current} {sent}".strip()
        else:
            if current:
                chunks.append(current)
            current = sent

    if current:
        chunks.append(current)

    return chunks


def normalize_statement(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[\"'“”‘’´`]", "", text)
    text = re.sub(r"[\(\)\[\]\{\}:;,\.\!\?]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def statement_hash(topic_slug: str, subtopic: str, statement: str) -> str:
    base = f"{topic_slug}|{subtopic}|{normalize_statement(statement)}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def short_text_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def similarity_ratio(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, normalize_statement(a), normalize_statement(b)).ratio()


def pick_best_candidate(group: List[Dict[str, Any]]) -> Dict[str, Any]:
    def score(item: Dict[str, Any]) -> tuple:
        return (
            int(item.get("support_count", 1)),
            float(item.get("confidence", 0.0)),
            len(item.get("statement", "")),
        )

    return sorted(group, key=score, reverse=True)[0]


def sleep_brief(seconds: float = 0.6) -> None:
    time.sleep(seconds)