import argparse
import json
import os
import re
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
SUGGESTED_DIR = BASE_DIR / "imports" / "suggested_topics"
GENERATED_DIR = BASE_DIR / "imports" / "generated"

SUGGESTED_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[áàäâ]", "a", text)
    text = re.sub(r"[éèëê]", "e", text)
    text = re.sub(r"[íìïî]", "i", text)
    text = re.sub(r"[óòöô]", "o", text)
    text = re.sub(r"[úùüû]", "u", text)
    text = re.sub(r"ñ", "n", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def write_json_file(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_system_prompt_for_suggest() -> str:
    return """
Eres un planificador experto de quizzes de fútbol en español para un portal de gran escala.

Tu misión:
- proponer temas y subtemas con potencial de tráfico y reutilización
- evitar temas demasiado obvios y saturados
- priorizar España y Sudamérica, sin olvidar Europa
- pensar en crecimiento del banco global de preguntas

QUÉ CONSIDERAR "BUEN TEMA":
- permite preguntas autocontenidas
- permite preguntas medium/hard
- da pie a reutilización entre quizzes
- tiene suficiente material histórico o competitivo
- puede alimentar varios quizzes ya existentes o futuros

PRIORIZA TEMAS COMO:
- debuts de jugadores
- primeros años de leyendas
- primeros goles / primeras convocatorias
- finales concretas
- remontadas
- capitanes de una era
- cambios de dorsal
- partidos raros pero verificables
- etapas juveniles o pre-explosión
- noches históricas de clubes
- subtemas poco trillados

EVITA:
- temas demasiado genéricos tipo "Historia del fútbol"
- temas flojos o demasiado obvios
- propuestas sin reutilización
- propuestas imposibles de verificar

Devuelve SOLO JSON válido.
""".strip()


def build_user_prompt_for_suggest(count: int) -> str:
    return f"""
Propón {count} temas o subtemas de fútbol para quizzes en español.

Formato de salida:
{{
  "mode": "suggest",
  "topics": [
    {{
      "topic": "string",
      "slug": "string",
      "category": "Clubes | Jugadores | Selecciones | Competiciones | Historia | Subtemas",
      "why_it_is_good": "string",
      "difficulty_profile": "string",
      "reuse_tags": ["string", "string"],
      "sample_question_angles": ["string", "string", "string"]
    }}
  ]
}}

Reglas:
- temas más escondidos y menos obvios
- mezcla España, Sudamérica y Europa
- al menos 60% deben poder generar preguntas medium/hard de verdad
- los sample_question_angles deben ser concretos y no genéricos
- usa slugs en minúsculas con guiones
Devuelve SOLO JSON.
""".strip()


def build_system_prompt_for_topics() -> str:
    return """
Eres un generador experto de preguntas de fútbol en español para un banco global de preguntas.

MISIÓN:
Crear preguntas buenas, autocontenidas, útiles para reutilización y NO demasiado obvias.

MUY IMPORTANTE:
- evitar preguntas flojas o demasiado fáciles
- máximo 20% easy
- la mayoría deben ser medium o hard
- toda pregunta debe ser autocontenida
- toda pregunta debe poder vivir fuera del contexto del quiz original

BUSCA ÁNGULOS COMO:
- debut en club / selección / competición
- rival, estadio o torneo del debut
- primeros años de carrera
- primer gol / primera asistencia / primera titularidad
- etapa con 15, 16 o 17 años
- cambio de dorsal
- entrenador que le hizo debutar
- finales concretas
- eliminatorias históricas
- capitanes de una era
- detalles competitivos verificables
- rivales concretos en partidos grandes

EVITA:
- "¿de qué país es Messi?"
- "¿qué club ganó más Champions?"
- preguntas demasiado evidentes salvo que sean pocas y muy justificadas
- preguntas ambiguas
- preguntas que dependan de una formulación poco precisa
- inventarte datos

CALIDAD:
- 4 opciones
- 1 correcta
- 3 distractores plausibles
- dificultad realista
- tags maestros consistentes
- si un detalle es demasiado dudoso, baja un poco la complejidad pero mantén interés

TAGS:
Usa tags consistentes de este tipo:
- entidad principal: messi, real-madrid, fc-barcelona, argentina, champions-league, etc.
- tipo de objeto: jugadores, clubes, selecciones, competiciones, entrenadores
- contenido: debut, goles, finales, historia, remontadas, capitanes, fichajes, dorsales, records
- tiempo: anos-1990, anos-2000, anos-2010, anos-2020, era-moderna
- contexto geográfico cuando ayude: espana, argentina, brasil, italia, inglaterra, europa

Devuelve SOLO JSON válido.
""".strip()


def build_user_prompt_for_topics(topics: List[str], count_per_topic: int) -> str:
    topics_str = ", ".join(topics)
    return f"""
Genera preguntas para estos temas: {topics_str}

Quiero aproximadamente {count_per_topic} preguntas por tema.

Formato de salida:
{{
  "mode": "topics",
  "batches": [
    {{
      "theme": "string",
      "theme_slug": "string",
      "questions": [
        {{
          "id": "string",
          "question": "string",
          "options": ["string", "string", "string", "string"],
          "correctIndex": 0,
          "difficulty": "easy | medium | hard",
          "tags": ["string", "string", "string"],
          "sourceNotes": ["string", "string"]
        }}
      ]
    }}
  ]
}}

REGLAS:
- preguntas autocontenidas
- evitar demasiadas fáciles
- priorizar medium/hard
- priorizar ángulos raros pero verificables
- mezclar historia, debuts, detalles competitivos, primeras veces, partidos relevantes y contexto de carrera
- cada pregunta debe tener al menos 4 tags
- ids únicas y legibles, por ejemplo: messi_auto_001
- sourceNotes cortas, por ejemplo: ["UEFA history", "club history"]
Devuelve SOLO JSON.
""".strip()


def call_responses_api(system_prompt: str, user_prompt: str) -> str:
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={"format": {"type": "json_object"}},
    )
    return response.output_text


def run_suggest(count: int) -> Path:
    raw = call_responses_api(
        build_system_prompt_for_suggest(),
        build_user_prompt_for_suggest(count),
    )
    payload = json.loads(raw)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = SUGGESTED_DIR / f"suggested_topics_{timestamp}.json"
    write_json_file(out_path, payload)
    return out_path


def run_topics(topics: List[str], count_per_topic: int) -> List[Path]:
    raw = call_responses_api(
        build_system_prompt_for_topics(),
        build_user_prompt_for_topics(topics, count_per_topic),
    )
    payload = json.loads(raw)

    written_files: List[Path] = []
    batches = payload.get("batches", [])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for batch in batches:
        theme = batch.get("theme", "tema")
        theme_slug = batch.get("theme_slug") or slugify(theme)
        questions = batch.get("questions", [])

        out_payload = {
            "theme": theme,
            "theme_slug": theme_slug,
            "generated_at": timestamp,
            "question_count": len(questions),
            "questions": questions,
        }

        out_path = GENERATED_DIR / f"{theme_slug}_{timestamp}.json"
        write_json_file(out_path, out_payload)
        written_files.append(out_path)

    return written_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generador de preguntas de fútbol con OpenAI")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["suggest", "topics"],
        help="Modo de uso: suggest o topics",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=20,
        help="Número de temas a sugerir en modo suggest",
    )
    parser.add_argument(
        "--topics",
        type=str,
        default="",
        help='Lista separada por comas. Ejemplo: "messi,champions-league,boca-juniors"',
    )
    parser.add_argument(
        "--count-per-topic",
        type=int,
        default=25,
        help="Preguntas aproximadas por tema en modo topics",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mode == "suggest":
        out_path = run_suggest(args.count)
        print(f"✅ Temas sugeridos guardados en: {out_path}")
        return

    if args.mode == "topics":
        if not args.topics.strip():
          raise ValueError("En modo topics debes pasar --topics")

        topics = [t.strip() for t in args.topics.split(",") if t.strip()]
        files = run_topics(topics, args.count_per_topic)

        print("✅ Lotes generados:")
        for file in files:
            print(f" - {file}")
        return


if __name__ == "__main__":
    main()