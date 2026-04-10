# -*- coding: utf-8 -*-
import os
import sys
import json
import shlex
import argparse
import subprocess
from pathlib import Path
from typing import List

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run_cmd(cmd: List[str]) -> None:
    print("\n" + "=" * 80)
    print("▶ Ejecutando:")
    print("  " + " ".join(shlex.quote(c) for c in cmd))
    print("=" * 80)
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        raise RuntimeError(f"Comando fallido con código {result.returncode}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lanza todo el pipeline de un tema.")
    parser.add_argument("--topic-name", required=True, help="Nombre visible del tema")
    parser.add_argument("--topic-slug", required=True, help="Slug del tema")
    parser.add_argument("--urls-file", required=True, help="JSON con URLs")
    parser.add_argument("--similarity-threshold", type=float, default=0.80)
    parser.add_argument("--min-questionability", type=float, default=4.0)
    parser.add_argument("--min-stability", type=float, default=4.0)
    parser.add_argument("--max-per-subtopic", type=int, default=3)
    parser.add_argument("--skip-import", action="store_true", help="No importar al final")
    args = parser.parse_args()

    python_exe = sys.executable

    topic_slug = args.topic_slug
    topic_name = args.topic_name

    topic_maps_dir = PROJECT_ROOT / "outputs" / "topic_maps"
    candidate_dir = PROJECT_ROOT / "outputs" / "candidate_facts"
    final_dir = PROJECT_ROOT / "outputs" / "final_facts"
    generated_dir = PROJECT_ROOT / "outputs" / "generated_questions"
    validated_dir = PROJECT_ROOT / "imports" / "validated"

    ensure_dir(topic_maps_dir)
    ensure_dir(candidate_dir)
    ensure_dir(final_dir)
    ensure_dir(generated_dir)
    ensure_dir(validated_dir)

    topic_map_path = topic_maps_dir / f"{topic_slug}_topic_map.json"
    candidate_path = candidate_dir / f"{topic_slug}_candidate_facts.json"
    final_path = final_dir / f"{topic_slug}_final_facts.json"
    questions_path = generated_dir / f"{topic_slug}_questions.json"
    validated_path = validated_dir / f"{topic_slug}_questions_validated.json"

    # 1) topic map
    run_cmd([
        python_exe,
        "scripts/generate_topic_map.py",
        "--input", args.urls_file,
        "--output", str(topic_map_path),
        "--topic-name", topic_name,
        "--topic-slug", topic_slug,
    ])

    # 2) candidate facts
    run_cmd([
        python_exe,
        "scripts/extract_candidate_facts_by_subtopic.py",
        "--topic-map", str(topic_map_path),
        "--output", str(candidate_path),
    ])

    # 3) consolidate facts
    run_cmd([
        python_exe,
        "scripts/consolidate_facts.py",
        "--input", str(candidate_path),
        "--output", str(final_path),
        "--similarity-threshold", str(args.similarity_threshold),
        "--min-questionability", str(args.min_questionability),
        "--min-stability", str(args.min_stability),
        "--max-per-subtopic", str(args.max_per_subtopic),
    ])

    # 4) generate questions
    run_cmd([
        python_exe,
        "scripts/generate_questions_from_final_facts.py",
        "--input", str(final_path),
        "--output", str(questions_path),
    ])

    # 5) validate
    run_cmd([
        python_exe,
        "scripts/validate_questions.py",
        "--file", str(questions_path),
    ])

    # El validador guarda en imports/validated con sufijo _validated.json
    generated_validated_name = f"{topic_slug}_questions_validated.json"
    legacy_validated_name = f"{topic_slug}_questions_validated.json"

    # Intentamos localizar el archivo real creado por validate_questions.py
    candidates = [
        validated_dir / f"{topic_slug}_questions_validated.json",
        validated_dir / f"{topic_slug}_questions.json".replace(".json", "_validated.json"),
        validated_dir / f"{topic_slug}_questions_validated.json",
    ]

    actual_validated = None
    for cand in candidates:
        if cand.exists():
            actual_validated = cand
            break

    # fallback más robusto: buscar por prefijo
    if actual_validated is None:
        matching = sorted(validated_dir.glob(f"{topic_slug}*validated.json"))
        if matching:
            actual_validated = matching[-1]

    if actual_validated is None:
        raise RuntimeError("No se encontró el JSON validado generado por validate_questions.py")

    print(f"\n✅ Archivo validado localizado: {actual_validated}")

    # 6) import
    if not args.skip_import:
        run_cmd([
            python_exe,
            "scripts/import_validated_questions.py",
            "--file", str(actual_validated),
        ])
    else:
        print("\n⏭ Import saltado por --skip-import")

    print("\n" + "#" * 80)
    print("✅ PIPELINE COMPLETO TERMINADO")
    print(f"   Tema: {topic_name}")
    print(f"   Slug: {topic_slug}")
    print(f"   Topic map: {topic_map_path}")
    print(f"   Candidate facts: {candidate_path}")
    print(f"   Final facts: {final_path}")
    print(f"   Questions: {questions_path}")
    print(f"   Validated: {actual_validated}")
    print("#" * 80)


if __name__ == "__main__":
    main()