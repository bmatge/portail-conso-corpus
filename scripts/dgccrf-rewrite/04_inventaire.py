#!/usr/bin/env python3
"""Phase 4 : Inventaire de couverture — évalue les sources disponibles par item taxonomique."""

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from tqdm import tqdm

from lib.chroma_utils import ChromaManager
from lib.config import load_config
from lib.taxonomy import Domaine, Situation, SousDomaine, load_taxonomy

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def build_query(item, level: str, taxonomy) -> str:
    """Build a semantic query string for ChromaDB retrieval."""
    if level == "domaine":
        return f"{item.label}. {item.description}"
    elif level == "sous_domaine":
        domaine = taxonomy.get_domaine_for(item)
        d_label = domaine.label if domaine else ""
        return f"{item.label}. {d_label}"
    else:
        # situation
        exemples = " ".join(item.exemples[:3]) if item.exemples else ""
        sd = taxonomy.get_sous_domaine_for(item)
        sd_label = sd.label if sd else ""
        domaine = taxonomy.get_domaine_for(item)
        d_label = domaine.label if domaine else ""
        return f"{item.label}. {exemples}. {sd_label}. {d_label}"


def assess_coverage(results: list[dict]) -> dict:
    """Assess coverage from retrieval results."""
    if not results:
        return {"coverage": "none", "total_chunks": 0, "sources": {}, "top_sources": []}

    sources = Counter(r["source"] for r in results)
    distinct_sources = len(sources)
    total = len(results)

    if total >= 5 and distinct_sources >= 2:
        coverage = "good"
    elif total >= 3:
        coverage = "partial"
    elif total >= 1:
        coverage = "low"
    else:
        coverage = "none"

    # Top 5 sources (unique by title)
    seen_titles = set()
    top_sources = []
    for r in sorted(results, key=lambda x: x["score"], reverse=True):
        if r["title"] not in seen_titles:
            seen_titles.add(r["title"])
            top_sources.append({
                "title": r["title"],
                "source": r["source"],
                "url": r["url"],
                "score": round(r["score"], 3),
            })
            if len(top_sources) >= 5:
                break

    return {
        "coverage": coverage,
        "total_chunks": total,
        "sources": dict(sources),
        "top_sources": top_sources,
    }


def main():
    parser = argparse.ArgumentParser(description="Phase 4 : Inventaire de couverture")
    parser.add_argument("--config", default=None)
    parser.add_argument("--situation", help="Évaluer une seule situation par ID")
    parser.add_argument("--domaine", help="Évaluer un seul domaine par ID")
    parser.add_argument("--level", choices=["domaine", "sous_domaine", "situation"])
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    taxonomy = load_taxonomy(cfg.paths.taxonomy_file)

    chroma = ChromaManager(
        db_path=cfg.paths.chroma_db_path,
        model_name=cfg.embeddings.model_name,
        collection_name=cfg.retrieval.collection_name,
    )

    total_docs = chroma.count()
    if total_docs == 0:
        print("Erreur : la collection ChromaDB est vide. Lancez d'abord 03_index_chroma.py", file=sys.stderr)
        sys.exit(1)
    log.info(f"Collection: {total_docs} documents")

    # Build item list
    items: list[tuple[str, str, object]] = []

    if args.situation:
        obj = taxonomy.get_by_id(args.situation)
        if not obj:
            print(f"Situation '{args.situation}' introuvable", file=sys.stderr)
            sys.exit(1)
        items = [("situation", args.situation, obj)]
    elif args.domaine:
        obj = taxonomy.get_by_id(args.domaine)
        if not obj:
            print(f"Domaine '{args.domaine}' introuvable", file=sys.stderr)
            sys.exit(1)
        items = [("domaine", args.domaine, obj)]
    else:
        for level, item_id, obj in taxonomy.all_items():
            if args.level and level != args.level:
                continue
            items.append((level, item_id, obj))

    log.info(f"Évaluation de {len(items)} items...")

    # Process
    inventory = []
    coverage_summary = Counter()

    for level, item_id, obj in tqdm(items, desc="Inventaire"):
        query = build_query(obj, level, taxonomy)
        results = chroma.query(
            query,
            top_k=cfg.retrieval.top_k,
            min_score=cfg.retrieval.min_score,
        )
        assessment = assess_coverage(results)
        coverage_summary[assessment["coverage"]] += 1

        parent_ids = []
        if level == "situation" and hasattr(obj, "sous_domaine_id") and obj.sous_domaine_id:
            parent_ids = [obj.sous_domaine_id, obj.domaine_id]
        elif level == "sous_domaine" and hasattr(obj, "domaine_id"):
            parent_ids = [obj.domaine_id]

        entry = {
            "id": item_id,
            "level": level,
            "label": obj.label,
            "parent_ids": parent_ids,
            **assessment,
        }
        inventory.append(entry)

        if args.verbose:
            emoji = {"good": "✓", "partial": "~", "low": "!", "none": "✗"}
            print(f"  {emoji.get(assessment['coverage'], '?')} [{level}] {item_id}: "
                  f"{assessment['coverage']} ({assessment['total_chunks']} chunks, "
                  f"sources: {assessment['sources']})")

    # Write report
    output_dir = cfg.paths.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now().isoformat(),
        "collection_docs": total_docs,
        "total_items": len(items),
        "coverage_summary": dict(coverage_summary),
        "items": inventory,
    }
    report_path = output_dir / "_inventaire.json"
    with open(report_path, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Couverture ({len(items)} items) :")
    for cov in ["good", "partial", "low", "none"]:
        count = coverage_summary.get(cov, 0)
        pct = count / len(items) * 100 if items else 0
        bar = "█" * int(pct / 2)
        print(f"  {cov:8s}: {count:3d} ({pct:5.1f}%) {bar}")

    print(f"\nRapport écrit : {report_path}")

    # Show worst items
    none_items = [i for i in inventory if i["coverage"] == "none"]
    low_items = [i for i in inventory if i["coverage"] == "low"]
    if none_items:
        print(f"\nItems sans source ({len(none_items)}) :")
        for i in none_items[:10]:
            print(f"  [{i['level']}] {i['id']}: {i['label'][:60]}")
    if low_items:
        print(f"\nItems à faible couverture ({len(low_items)}) :")
        for i in low_items[:10]:
            print(f"  [{i['level']}] {i['id']}: {i['label'][:60]}")


if __name__ == "__main__":
    main()
