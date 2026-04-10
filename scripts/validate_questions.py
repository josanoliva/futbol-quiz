import argparse
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "imports" / "validated"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------
# Helpers
# -----------------------

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


# -----------------------
# Detectores semánticos
# -----------------------

TEAM_HINTS = [
    "cf", "cd", "fc", "ud", "real", "deportivo", "balompié", "balompie",
    "sporting", "athletic", "atlético", "atletico", "castellón", "castellon",
    "lloret", "huesca", "eibar", "zaragoza", "barcelona", "madrid"
]

STADIUM_HINTS = [
    "estadio", "campo", "alcoraz", "bernabéu", "bernabeu",
    "camp nou", "anxo carro", "rico perez"
]

COMPETITION_HINTS = [
    "liga", "división", "division", "copa", "playoff", "play-offs",
    "segunda", "primera", "tercera", "regional"
]

DATE_WORDS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]

ORDINAL_HINTS = [
    "primera ronda", "segunda ronda", "tercera ronda"
]


def looks_like_team(text: str) -> bool:
    t = normalize(text)
    if any(k in t for k in TEAM_HINTS):
        return True
    # varias palabras en mayúsculas tipo nombres de equipo suelen llegar ya con nombre propio,
    # pero aquí trabajamos en minúsculas; dejamos una detección básica adicional
    return False


def looks_like_stadium(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in STADIUM_HINTS)


def looks_like_competition(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in COMPETITION_HINTS)


def looks_like_score(text: str) -> bool:
    t = normalize(text)
    return bool(re.fullmatch(r"\d+\s*-\s*\d+", t))


def looks_like_season(text: str) -> bool:
    t = normalize(text)
    return bool(re.fullmatch(r"(19|20)\d{2}/\d{2}", t)) or bool(re.fullmatch(r"(19|20)\d{2}-(19|20)?\d{2}", t))


def looks_like_full_date(text: str) -> bool:
    t = normalize(text)
    return any(month in t for month in DATE_WORDS) or bool(re.search(r"\b(19|20)\d{2}\b", t))


def looks_like_boolean_style(text: str) -> bool:
    t = normalize(text)
    return t in ["ninguno de los anteriores", "todos los anteriores", "verdadero", "falso"]


def detect_option_type(text: str) -> str:
    t = normalize(text)

    if looks_like_score(t):
        return "score"
    if looks_like_season(t):
        return "season"
    if looks_like_full_date(t):
        return "date"
    if looks_like_stadium(t):
        return "stadium"
    if looks_like_competition(t):
        return "competition"
    if looks_like_team(t):
        return "team"
    if looks_like_boolean_style(t):
        return "boolean"
    return "other"


# -----------------------
# Tipo esperado según la pregunta
# -----------------------

def infer_expected_answer_type(question_text: str) -> str:
    q = normalize(question_text)

    if "¿en qué temporada" in q or "que temporada" in q:
        return "season"

    if "¿en qué fecha" in q or "que fecha" in q:
        return "date"

    if "¿qué resultado" in q or "como termino" in q or "cómo terminó" in q:
        return "score"

    if "¿contra qué rival" in q or "que rival" in q or "visitó" in q:
        return "team"

    if "¿dónde" in q or "qué estadio" in q or "cual es ese estadio" in q or "cuál es ese estadio" in q:
        return "stadium"

    if "¿qué combinación" in q:
        return "compound"

    if "¿cuál de estos hitos" in q or "que ocurrio antes" in q or "que hecho ocurrio en medio" in q or "más tardío cronológicamente" in q:
        return "event"

    return "generic"


# -----------------------
# Reglas de validación
# -----------------------

def validate_options_count(options: List[str], issues: List[str]) -> int:
    penalty = 0
    if len(options) != 4:
        issues.append(f"Número de opciones incorrecto: {len(options)}")
        penalty += 40
    return penalty


def validate_duplicates(options: List[str], issues: List[str]) -> int:
    penalty = 0
    normalized = [normalize(o) for o in options]
    if len(set(normalized)) < len(normalized):
        issues.append("Opciones duplicadas")
        penalty += 35
    return penalty


def validate_correct_index(q: Dict, issues: List[str]) -> int:
    penalty = 0
    options = q.get("options", [])
    correct_index = q.get("correctIndex")
    if not isinstance(correct_index, int) or correct_index < 0 or correct_index >= len(options):
        issues.append("correctIndex inválido")
        penalty += 50
    return penalty


def validate_question_length(question_text: str, issues: List[str]) -> int:
    penalty = 0
    if len(question_text.strip()) < 35:
        issues.append("Pregunta demasiado corta")
        penalty += 12
    return penalty


def validate_too_easy(q: Dict, issues: List[str]) -> int:
    penalty = 0
    question_text = normalize(q.get("question", ""))

    very_basic_patterns = [
        "¿dónde disputa sus partidos como local",
        "¿en qué fecha fue fundada",
        "¿qué capacidad tiene",
        "¿cómo se llama el estadio",
    ]

    if any(p in question_text for p in very_basic_patterns):
        issues.append("Pregunta de ficha demasiado básica")
        penalty += 12

    if q.get("difficulty") == "easy":
        penalty += 4

    return penalty


def validate_semantic_consistency(q: Dict, issues: List[str]) -> int:
    penalty = 0
    question_text = q.get("question", "")
    options = q.get("options", [])

    expected_type = infer_expected_answer_type(question_text)
    option_types = [detect_option_type(o) for o in options]
    counts: Dict[str, int] = {}
    for t in option_types:
        counts[t] = counts.get(t, 0) + 1

    dominant_type = max(counts, key=counts.get) if counts else "other"

    # Si esperamos algo específico, pedimos coherencia
    if expected_type in ["team", "stadium", "score", "season", "date"]:
        wrong = [o for o, t in zip(options, option_types) if t != expected_type]
        if len(wrong) >= 2:
            issues.append(f"Opciones de tipo incorrecto para la pregunta. Esperado: {expected_type}. Tipos: {option_types}")
            penalty += 35
        elif len(wrong) == 1:
            issues.append(f"Una opción parece de tipo incorrecto. Esperado: {expected_type}. Tipos: {option_types}")
            penalty += 12

    # Para preguntas de evento/cronología permitimos texto compuesto,
    # pero no booleanos raros salvo que tenga sentido
    elif expected_type == "event":
        boolean_options = [o for o, t in zip(options, option_types) if t == "boolean"]
        if boolean_options:
            issues.append("Opción tipo 'ninguno/todos' en pregunta cronológica")
            penalty += 15

    # Para combinación aceptamos compound/other, pero buscamos uniformidad mínima
    elif expected_type == "compound":
        if len(set(option_types)) > 2:
            issues.append(f"Demasiada mezcla semántica en opciones: {option_types}")
            penalty += 18

    else:
        # caso genérico: si hay 3 o 4 tipos distintos, mala señal
        if len(set(option_types)) >= 3:
            issues.append(f"Opciones muy heterogéneas: {option_types}")
            penalty += 20

    # Castigo específico a opciones muy absurdas según contexto
    qn = normalize(question_text)
    for option, otype in zip(options, option_types):
        o = normalize(option)

        if ("rival" in qn or "visitó" in qn) and otype in ["stadium", "competition"]:
            issues.append(f"Opción absurda para un rival: {option}")
            penalty += 18

        if ("estadio" in qn or "dónde disputa sus partidos" in qn) and otype in ["team", "competition"]:
            issues.append(f"Opción absurda para un estadio/lugar: {option}")
            penalty += 18

        if ("resultado" in qn or "terminó" in qn) and otype != "score":
            issues.append(f"Opción absurda para un resultado: {option}")
            penalty += 18

        if ("temporada" in qn) and otype not in ["season", "date"]:
            issues.append(f"Opción absurda para una temporada/fecha: {option}")
            penalty += 18

    return penalty


def validate_question(q: Dict) -> Dict:
    issues: List[str] = []
    score = 100

    question_text = q.get("question", "")
    options = q.get("options", [])

    score -= validate_options_count(options, issues)
    score -= validate_duplicates(options, issues)
    score -= validate_correct_index(q, issues)
    score -= validate_question_length(question_text, issues)
    score -= validate_too_easy(q, issues)
    score -= validate_semantic_consistency(q, issues)

    score = max(score, 0)

    # Más exigente que antes
    is_valid = score >= 70

    return {
        "score": score,
        "issues": issues,
        "is_valid": is_valid
    }


# -----------------------
# MAIN
# -----------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="JSON de preguntas")
    args = parser.parse_args()

    file_path = Path(args.file)

    if not file_path.exists():
        raise FileNotFoundError("No existe el archivo")

    data = load_json(file_path)
    questions = data.get("questions", [])

    results = []
    for q in questions:
        validation = validate_question(q)
        results.append({
            **q,
            "validation": validation
        })

    final = {
        "theme": data.get("theme"),
        "theme_slug": data.get("theme_slug"),
        "generated_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "total": len(results),
        "valid": sum(1 for r in results if r["validation"]["is_valid"]),
        "questions": results
    }

    out_path = OUT_DIR / f"{file_path.stem}_validated.json"
    save_json(out_path, final)

    print(f"✅ Validación guardada en: {out_path}")
    print(f"✔ válidas: {final['valid']} / {final['total']}")


if __name__ == "__main__":
    main()