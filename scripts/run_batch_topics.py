# -*- coding: utf-8 -*-
import sys
import json
import shlex
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_urls_file(topic: Dict[str, Any]) -> str:
    topic_slug = topic["topic_slug"]
    urls = topic["urls"]

    out_path = PROJECT_ROOT / "inputs" / "urls" / f"{topic_slug}_urls.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = {"urls": urls}
    save_json(str(out_path), data)
    return str(out_path)


def run_cmd(cmd: List[str]) -> int:
    print("\n" + "=" * 90)
    print("▶ Ejecutando:")
    print("  " + " ".join(shlex.quote(c) for c in cmd))
    print("=" * 90)

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Lanza varios temas seguidos usando run_topic_pipeline.py")
    parser.add_argument("--batch-file", required=True, help="JSON con lista de temas")
    parser.add_argument("--skip-import", action="store_true", help="No importar al final")
    parser.add_argument("--continue-on-error", action="store_true", help="Seguir con el siguiente tema si uno falla")
    parser.add_argument("--similarity-threshold", type=float, default=0.80)
    parser.add_argument("--min-questionability", type=float, default=4.0)
    parser.add_argument("--min-stability", type=float, default=4.0)
    parser.add_argument("--max-per-subtopic", type=int, default=3)
    args = parser.parse_args()

    python_exe = sys.executable
    batch = load_json(args.batch_file)

    topics = batch["topics"] if isinstance(batch, dict) and "topics" in batch else batch
    if not isinstance(topics, list) or not topics:
        raise RuntimeError("El batch-file debe contener una lista de topics o {'topics': [...]}")

    summary = []

    for idx, topic in enumerate(topics, start=1):
        topic_name = topic["topic_name"]
        topic_slug = topic["topic_slug"]

        print("\n" + "#" * 90)
        print(f"### [{idx}/{len(topics)}] {topic_name} ({topic_slug})")
        print("#" * 90)

        urls_file = ensure_urls_file(topic)

        cmd = [
            python_exe,
            "scripts/run_topic_pipeline.py",
            "--topic-name", topic_name,
            "--topic-slug", topic_slug,
            "--urls-file", urls_file,
            "--similarity-threshold", str(args.similarity_threshold),
            "--min-questionability", str(args.min_questionability),
            "--min-stability", str(args.min_stability),
            "--max-per-subtopic", str(args.max_per_subtopic),
        ]

        if args.skip_import:
            cmd.append("--skip-import")

        code = run_cmd(cmd)

        summary.append({
            "topic_name": topic_name,
            "topic_slug": topic_slug,
            "status": "ok" if code == 0 else f"error_{code}",
            "urls_file": urls_file,
        })

        if code != 0 and not args.continue_on_error:
            print(f"\n❌ Parado por error en {topic_slug}")
            break

    print("\n" + "#" * 90)
    print("RESUMEN FINAL")
    print("#" * 90)

    for item in summary:
        print(f"- {item['topic_slug']}: {item['status']}")

    save_json(str(PROJECT_ROOT / "outputs" / "batch_summary.json"), summary)
    print("\n✅ Resumen guardado en outputs/batch_summary.json")


if __name__ == "__main__":
    main()