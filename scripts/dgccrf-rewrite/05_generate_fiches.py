#!/usr/bin/env python3
"""Phase 5 : Génération des fiches via LLM avec RAG (retrieve → augment → generate)."""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import frontmatter as fm
from tqdm import tqdm

from lib.chroma_utils import ChromaManager
from lib.config import load_config
from lib.llm_client import LLMClient
from lib.prompt_builder import PromptBuilder
from lib.taxonomy import Domaine, Situation, SousDomaine, load_taxonomy

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def get_output_path(item, level: str, taxonomy, fiches_dir: Path) -> Path:
    """Determine the output path for a fiche.

    Structure: corpus/{domaine}/{sous_domaine}/{situation}.md
    - Domaine  → corpus/{domaine_id}/_index.md
    - Sous-domaine → corpus/{domaine_id}/{sd_id}/_index.md
    - Situation → corpus/{domaine_id}/{sd_id}/{situation_id}.md
    - Transversale → corpus/transversales/{situation_id}.md
    """
    if level == "domaine":
        return fiches_dir / item.id / "_index.md"
    elif level == "sous_domaine":
        domaine = taxonomy.get_domaine_for(item)
        d_id = domaine.id if domaine else "unknown"
        return fiches_dir / d_id / item.id / "_index.md"
    else:
        # situation
        if item.is_transversale:
            return fiches_dir / "transversales" / f"{item.id}.md"
        sd = taxonomy.get_sous_domaine_for(item)
        domaine = taxonomy.get_domaine_for(item)
        d_id = domaine.id if domaine else "unknown"
        sd_id = sd.id if sd else "unknown"
        return fiches_dir / d_id / sd_id / f"{item.id}.md"


def build_query(item, level: str, taxonomy) -> str:
    """Build a semantic query for ChromaDB retrieval."""
    if level == "domaine":
        return f"{item.label}. {item.description}"
    elif level == "sous_domaine":
        domaine = taxonomy.get_domaine_for(item)
        d_label = domaine.label if domaine else ""
        child_labels = " ".join(s.label for s in item.situations[:5])
        return f"{item.label}. {d_label}. {child_labels}"
    else:
        exemples = " ".join(item.exemples[:3]) if item.exemples else ""
        sd = taxonomy.get_sous_domaine_for(item)
        sd_label = sd.label if sd else ""
        return f"{item.label}. {exemples}. {sd_label}"


def max_tokens_for_level(level: str, cfg) -> int:
    """Get max tokens for a given level."""
    return {
        "domaine": cfg.llm.max_tokens_domaine,
        "sous_domaine": cfg.llm.max_tokens_sous_domaine,
        "situation": cfg.llm.max_tokens_situation,
    }.get(level, cfg.llm.max_tokens_situation)


def generate_one(
    item,
    level: str,
    taxonomy,
    chroma: ChromaManager,
    prompt_builder: PromptBuilder,
    llm: LLMClient,
    cfg,
    fiches_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Generate a single fiche. Returns log entry."""
    item_id = item.id
    output_path = get_output_path(item, level, taxonomy, fiches_dir)

    # Retrieve sources
    query = build_query(item, level, taxonomy)
    dgccrf_sources, other_sources = chroma.query_with_boost(
        query,
        top_k=cfg.retrieval.top_k,
        min_score=cfg.retrieval.min_score,
        boost_source="dgccrf",
        boost_factor=cfg.retrieval.dgccrf_weight,
        max_chars=cfg.retrieval.max_source_chars,
    )

    # Build prompt
    if level == "domaine":
        system_prompt, user_prompt = prompt_builder.build_domaine_prompt(
            item, dgccrf_sources, other_sources
        )
    elif level == "sous_domaine":
        domaine = taxonomy.get_domaine_for(item)
        system_prompt, user_prompt = prompt_builder.build_sous_domaine_prompt(
            item, domaine, dgccrf_sources, other_sources
        )
    else:
        sd = taxonomy.get_sous_domaine_for(item)
        domaine = taxonomy.get_domaine_for(item)
        system_prompt, user_prompt = prompt_builder.build_situation_prompt(
            item, sd, domaine, dgccrf_sources, other_sources
        )

    max_tokens = max_tokens_for_level(level, cfg)

    # Log entry
    log_entry = {
        "item_id": item_id,
        "level": level,
        "timestamp": datetime.now().isoformat(),
        "output_path": str(output_path),
        "sources_dgccrf": len(dgccrf_sources),
        "sources_other": len(other_sources),
        "status": "dry_run" if dry_run else "pending",
    }

    if dry_run:
        info = llm.chat_dry_run(system_prompt, user_prompt, max_tokens)
        log_entry["dry_run_info"] = info
        return log_entry

    # Generate
    try:
        response = llm.chat(system_prompt, user_prompt, max_tokens)
    except Exception as e:
        log_entry["status"] = "error"
        log_entry["error"] = str(e)
        log.error(f"Error generating {item_id}: {e}")
        return log_entry

    # Build output with frontmatter
    source_refs = [
        f"{s['source']}:{s.get('nid') or s['title'][:30]}"
        for s in dgccrf_sources + other_sources
    ]

    fiche_meta = {
        "title": item.label,
        "taxonomy_id": item_id,
        "level": level,
        "domaine": item.domaine_id if hasattr(item, "domaine_id") else item_id,
        "generated_at": datetime.now().isoformat(),
        "model": response.model,
        "tokens": response.total_tokens,
        "sources_count": len(source_refs),
    }
    if level == "situation" and hasattr(item, "sous_domaine_id"):
        fiche_meta["sous_domaine"] = item.sous_domaine_id

    post = fm.Post(response.content, **fiche_meta)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(fm.dumps(post))

    log_entry.update({
        "status": "ok",
        "model": response.model,
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
        "total_tokens": response.total_tokens,
        "duration_seconds": response.duration_seconds,
        "sources_used": source_refs[:10],
    })

    return log_entry


def main():
    parser = argparse.ArgumentParser(description="Phase 5 : Génération des fiches LLM")
    parser.add_argument("--config", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Prévisualiser les prompts sans appeler le LLM")
    parser.add_argument("--situation", help="Générer une seule situation par ID")
    parser.add_argument("--sous-domaine", help="Générer un seul sous-domaine par ID")
    parser.add_argument("--domaine", help="Générer un seul domaine par ID")
    parser.add_argument("--level", choices=["domaine", "sous_domaine", "situation"])
    parser.add_argument("--resume", action="store_true", help="Sauter les fiches déjà existantes")
    parser.add_argument("--force", action="store_true", help="Écraser les fiches existantes")
    parser.add_argument("--bottom-up", action="store_true", default=True,
                        help="Générer situations → sous-domaines → domaines (défaut)")
    parser.add_argument("--top-down", action="store_true", help="Générer domaines → sous-domaines → situations")
    args = parser.parse_args()

    cfg = load_config(args.config)

    # Check API key
    if not args.dry_run and not cfg.llm.api_key:
        print("Erreur : LLM_API_KEY non défini. Exportez la variable d'environnement.", file=sys.stderr)
        sys.exit(1)

    taxonomy = load_taxonomy(cfg.paths.taxonomy_file)
    fiches_dir = cfg.paths.fiches_dir
    log_path = cfg.paths.output_dir / "_generation_log.jsonl"

    log.info(f"Taxonomie : {taxonomy.item_count()}")
    log.info(f"Sortie : {fiches_dir}")
    log.info(f"Modèle : {cfg.llm.model} @ {cfg.llm.endpoint}")

    # Init components
    chroma = ChromaManager(
        db_path=cfg.paths.chroma_db_path,
        model_name=cfg.embeddings.model_name,
        collection_name=cfg.retrieval.collection_name,
    )

    if chroma.count() == 0:
        print("Erreur : la collection ChromaDB est vide. Lancez d'abord 03_index_chroma.py", file=sys.stderr)
        sys.exit(1)

    prompt_builder = PromptBuilder(cfg.paths.prompts_dir, taxonomy)

    llm = LLMClient(
        endpoint=cfg.llm.endpoint,
        api_key=cfg.llm.api_key or "dry-run",
        model=cfg.llm.model,
        temperature=cfg.llm.temperature,
        timeout=cfg.llm.timeout,
        rate_limit_rpm=cfg.llm.rate_limit_rpm,
        retry_count=cfg.llm.retry_count,
        retry_delay=cfg.llm.retry_delay,
    )

    # Build item list
    items: list[tuple[str, object]] = []

    if args.situation:
        obj = taxonomy.get_by_id(args.situation)
        if not obj:
            print(f"Situation '{args.situation}' introuvable", file=sys.stderr)
            sys.exit(1)
        items = [("situation", obj)]
    elif args.sous_domaine:
        obj = taxonomy.get_by_id(args.sous_domaine)
        if not obj:
            print(f"Sous-domaine '{args.sous_domaine}' introuvable", file=sys.stderr)
            sys.exit(1)
        items = [("sous_domaine", obj)]
    elif args.domaine:
        obj = taxonomy.get_by_id(args.domaine)
        if not obj:
            print(f"Domaine '{args.domaine}' introuvable", file=sys.stderr)
            sys.exit(1)
        items = [("domaine", obj)]
    else:
        all_items = taxonomy.all_items()
        if args.level:
            all_items = [(l, i, o) for l, i, o in all_items if l == args.level]

        # Order: bottom-up (default) or top-down
        if args.top_down:
            order = {"domaine": 0, "sous_domaine": 1, "situation": 2}
        else:
            order = {"situation": 0, "sous_domaine": 1, "domaine": 2}

        all_items.sort(key=lambda x: order.get(x[0], 99))
        items = [(l, o) for l, _, o in all_items]

    log.info(f"{len(items)} fiches à générer")

    # Generate
    fiches_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    stats = {"ok": 0, "error": 0, "skipped": 0, "dry_run": 0}
    total_tokens = 0

    with open(log_path, "a") as log_file:
        for level, item in tqdm(items, desc="Génération"):
            output_path = get_output_path(item, level, taxonomy, fiches_dir)

            # Resume: skip existing
            if args.resume and output_path.exists() and not args.force:
                stats["skipped"] += 1
                continue

            entry = generate_one(
                item, level, taxonomy, chroma, prompt_builder, llm, cfg,
                fiches_dir, dry_run=args.dry_run,
            )

            log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            log_file.flush()

            status = entry.get("status", "error")
            stats[status] = stats.get(status, 0) + 1
            total_tokens += entry.get("total_tokens", 0)

            if args.dry_run and args.situation:
                # Show full prompt preview for single item dry-run
                info = entry.get("dry_run_info", {})
                print(f"\n{'='*60}")
                print(f"[DRY-RUN] {item.id} ({level})")
                print(f"Model: {info.get('model')}, Max tokens: {info.get('max_tokens')}")
                print(f"System prompt: {info.get('system_chars')} chars")
                print(f"User prompt: {info.get('user_chars')} chars")
                print(f"Estimated tokens: ~{info.get('estimated_tokens')}")
                print(f"\n--- User prompt preview ---")
                print(info.get("user_prompt_preview", ""))

    # Summary
    print(f"\n{'='*60}")
    print(f"Résultats : {stats}")
    if total_tokens:
        print(f"Tokens utilisés : {total_tokens:,}")
    print(f"Log : {log_path}")


if __name__ == "__main__":
    main()
