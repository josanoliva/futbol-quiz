# -*- coding: utf-8 -*-
import argparse
from collections import defaultdict
from typing import Dict, Any, List

from topic_pipeline_common import (
    load_json,
    normalize_statement,
    pick_best_candidate,
    save_json,
    similarity_ratio,
    statement_hash,
)


def group_candidates(candidates: List[Dict[str, Any]], similarity_threshold: float = 0.88) -> List[List[Dict[str, Any]]]:
    groups: List[List[Dict[str, Any]]] = []

    for cand in candidates:
        placed = False
        for group in groups:
            representative = group[0]
            if representative["subtopic"] != cand["subtopic"]:
                continue

            sim = similarity_ratio(representative["statement"], cand["statement"])
            if sim >= similarity_threshold:
                group.append(cand)
                placed = True
                break

        if not placed:
            groups.append([cand])

    return groups


def consolidate_group(topic_slug: str, topic_name: str, entity_type: str, group: List[Dict[str, Any]]) -> Dict[str, Any]:
    best = pick_best_candidate(group)

    source_urls = []
    source_titles = []
    evidence_quotes = []

    for item in group:
        url = item.get("source_url", "")
        title = item.get("source_title", "")
        evidence = item.get("evidence_quote", "")

        if url and url not in source_urls:
            source_urls.append(url)
        if title and title not in source_titles:
            source_titles.append(title)
        if evidence and evidence not in evidence_quotes:
            evidence_quotes.append(evidence)

    confidence_values = [float(x.get("confidence", 0.7)) for x in group]
    questionability_values = [int(x.get("questionability_score", 3)) for x in group]
    stability_values = [int(x.get("stability_score", 3)) for x in group]

    confidence_avg = round(sum(confidence_values) / max(len(confidence_values), 1), 4)
    questionability_avg = round(sum(questionability_values) / max(len(questionability_values), 1), 2)
    stability_avg = round(sum(stability_values) / max(len(stability_values), 1), 2)

    statement = best["statement"]
    subtopic = best["subtopic"]

    return {
        "fact_id": statement_hash(topic_slug, subtopic, statement),
        "topic_slug": topic_slug,
        "topic_name": topic_name,
        "entity_type": entity_type,
        "subtopic": subtopic,
        "fact_type": best.get("fact_type", subtopic),
        "statement": statement,
        "confidence": confidence_avg,
        "questionability_score": questionability_avg,
        "stability_score": stability_avg,
        "support_count": len(group),
        "source_urls": source_urls,
        "source_titles": source_titles,
        "evidence_quotes": evidence_quotes[:5],
        "source_chunks": sorted(list({
            f"{x.get('source_url', '')}|{x.get('section_heading', '')}|{x.get('chunk_id', '')}"
            for x in group
        })),
        "section_headings": sorted(list({
            x.get("section_heading", "")
            for x in group
            if x.get("section_heading")
        })),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolida candidate_facts en final_facts.")
    parser.add_argument("--input", required=True, help="Ruta candidate_facts.json")
    parser.add_argument("--output", required=True, help="Ruta final_facts.json")
    parser.add_argument("--similarity-threshold", type=float, default=0.88, help="Umbral 0-1")
    parser.add_argument("--min-questionability", type=float, default=3.5, help="Filtro mínimo")
    parser.add_argument("--min-stability", type=float, default=3.5, help="Filtro mínimo")
    parser.add_argument("--max-per-subtopic", type=int, default=4, help="Máximo final por subtopic")
    args = parser.parse_args()

    data = load_json(args.input)

    topic_slug = data["topic_slug"]
    topic_name = data["topic_name"]
    entity_type = data["entity_type"]
    candidate_facts = data.get("candidate_facts", [])

    print(f"📦 Candidate facts de entrada: {len(candidate_facts)}")

    # Deduplicado exacto previo
    exact_map = {}
    for cand in candidate_facts:
        key = (cand.get("subtopic", ""), normalize_statement(cand.get("statement", "")))
        current = exact_map.get(key)
        if not current:
            exact_map[key] = cand
        else:
            # mantener el de mayor confianza
            if float(cand.get("confidence", 0)) > float(current.get("confidence", 0)):
                exact_map[key] = cand

    deduped = list(exact_map.values())
    print(f"🧹 Tras deduplicado exacto: {len(deduped)}")

    groups = group_candidates(deduped, similarity_threshold=args.similarity_threshold)
    print(f"🧠 Grupos de consolidación: {len(groups)}")

    consolidated = [
        consolidate_group(topic_slug, topic_name, entity_type, group)
        for group in groups
    ]

    # filtros mínimos
    filtered = [
        x for x in consolidated
        if float(x.get("questionability_score", 0)) >= args.min_questionability
        and float(x.get("stability_score", 0)) >= args.min_stability
    ]

    print(f"✅ Tras filtros de calidad: {len(filtered)}")

    # limitar por subtopic para asegurar variedad
    by_subtopic = defaultdict(list)
    for item in filtered:
        by_subtopic[item["subtopic"]].append(item)

    final_facts = []
    for subtopic, items in by_subtopic.items():
        items_sorted = sorted(
            items,
            key=lambda x: (
                int(x.get("support_count", 1)),
                float(x.get("questionability_score", 0)),
                float(x.get("stability_score", 0)),
                float(x.get("confidence", 0)),
            ),
            reverse=True,
        )
        final_facts.extend(items_sorted[:args.max_per_subtopic])

    final_facts = sorted(
        final_facts,
        key=lambda x: (
            int(x.get("support_count", 1)),
            float(x.get("questionability_score", 0)),
            float(x.get("stability_score", 0)),
            float(x.get("confidence", 0)),
        ),
        reverse=True,
    )

    output = {
        "topic_slug": topic_slug,
        "topic_name": topic_name,
        "entity_type": entity_type,
        "candidate_facts_count": len(candidate_facts),
        "deduped_candidates_count": len(deduped),
        "consolidated_groups_count": len(groups),
        "final_facts_count": len(final_facts),
        "final_facts": final_facts,
    }

    save_json(args.output, output)

    print("\n✅ final_facts generados")
    print(f"   total final_facts: {len(final_facts)}")
    print(f"   output: {args.output}")

    print("\n📚 Resumen por subtopic:")
    subtopic_counts = defaultdict(int)
    for item in final_facts:
        subtopic_counts[item["subtopic"]] += 1

    for subtopic, count in sorted(subtopic_counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"   - {subtopic}: {count}")


if __name__ == "__main__":
    main()