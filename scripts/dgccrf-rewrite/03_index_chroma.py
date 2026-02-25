#!/usr/bin/env python3
"""Phase 3 : Indexation des 4 corpus + fiches générées dans ChromaDB."""

import argparse
import hashlib
import logging
import sys
from pathlib import Path

from tqdm import tqdm

from lib.chroma_utils import ChromaManager
from lib.config import load_config
from lib.text_utils import (
    chunk_text,
    clean_inc_body,
    extract_source_metadata,
    parse_md_file,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Sources and their config keys
SOURCES = {
    "dgccrf": "dgccrf_corpus_dir",
    "particuliers": "particuliers_corpus_dir",
    "entreprises": "entreprises_corpus_dir",
    "inc": "inc_corpus_dir",
}


def index_source(
    chroma: ChromaManager,
    source_name: str,
    corpus_dir: Path,
    cfg,
    dry_run: bool = False,
) -> dict:
    """Index a single source corpus. Returns stats dict."""
    files = sorted(corpus_dir.rglob("*.md"))
    # Exclude metadata files
    files = [f for f in files if not f.name.startswith("_")]

    # For INC, apply skip directories
    if source_name == "inc":
        skip_lower = {d.lower() for d in cfg.inc_cleaning.skip_directories}
        files = [
            f for f in files
            if not any(
                part.lower() in skip_lower
                for part in f.relative_to(corpus_dir).parts[:-1]
            )
        ]

    markers = cfg.inc_cleaning.boilerplate_markers
    bp_threshold = cfg.inc_cleaning.boilerplate_threshold

    stats = {"files": 0, "chunks": 0, "skipped": 0}

    all_chunks = []
    all_metadatas = []
    all_ids = []

    for path in tqdm(files, desc=f"  {source_name}", leave=False):
        try:
            meta, body = parse_md_file(path)
        except Exception as e:
            log.warning(f"Skipping {path.name}: {e}")
            stats["skipped"] += 1
            continue

        # For INC: clean body
        if source_name == "inc":
            body, _ = clean_inc_body(body, markers, bp_threshold)

        if len(body) < cfg.inc_cleaning.min_content_length:
            stats["skipped"] += 1
            continue

        # Normalize metadata
        src_meta = extract_source_metadata(meta, source_name)
        title = src_meta["title"] or path.stem

        # Chunk
        chunks = chunk_text(
            body,
            title,
            chunk_size=cfg.chunking.chunk_size,
            chunk_overlap=cfg.chunking.chunk_overlap,
            min_chunk_length=cfg.chunking.min_chunk_length,
        )

        if not chunks:
            stats["skipped"] += 1
            continue

        # Build IDs and metadata — use filename stem for uniqueness (NIDs can repeat)
        doc_id = hashlib.md5(path.name.encode()).hexdigest()[:12]
        for i, chunk in enumerate(chunks):
            chunk_id = f"{source_name}_{doc_id}_{i}"
            chunk_meta = {
                "source": source_name,
                "title": title,
                "nid": src_meta["id"],
                "url": src_meta["url"],
                "content_type": src_meta["content_type"],
                "chunk_index": i,
                "date": src_meta["date"],
            }
            all_chunks.append(chunk)
            all_metadatas.append(chunk_meta)
            all_ids.append(chunk_id)

        stats["files"] += 1

    stats["chunks"] = len(all_chunks)

    if dry_run:
        log.info(f"  [DRY-RUN] {source_name}: {stats['files']} files, {stats['chunks']} chunks")
        return stats

    if all_chunks:
        chroma.add_documents(all_chunks, all_metadatas, all_ids)

    return stats


def index_fiches(
    chroma: ChromaManager,
    fiches_dir: Path,
    cfg,
    dry_run: bool = False,
) -> dict:
    """Index generated fiches from corpus/ directory. Returns stats dict."""
    files = sorted(fiches_dir.rglob("*.md"))
    files = [f for f in files if not f.name.startswith("_")]

    stats = {"files": 0, "chunks": 0, "skipped": 0}
    all_chunks = []
    all_metadatas = []
    all_ids = []

    for path in tqdm(files, desc="  fiches", leave=False):
        try:
            meta, body = parse_md_file(path)
        except Exception as e:
            log.warning(f"Skipping {path.name}: {e}")
            stats["skipped"] += 1
            continue

        taxonomy_id = meta.get("taxonomy_id", path.stem)
        title = meta.get("title", path.stem)
        fiche_path = str(path.relative_to(fiches_dir))

        if len(body) < 100:
            stats["skipped"] += 1
            continue

        chunks = chunk_text(
            body, title,
            chunk_size=cfg.chunking.chunk_size,
            chunk_overlap=cfg.chunking.chunk_overlap,
            min_chunk_length=cfg.chunking.min_chunk_length,
        )

        if not chunks:
            stats["skipped"] += 1
            continue

        doc_id = hashlib.md5(fiche_path.encode()).hexdigest()[:12]
        for i, chunk in enumerate(chunks):
            chunk_id = f"fiches_{doc_id}_{i}"
            chunk_meta = {
                "source": "fiches",
                "title": title,
                "taxonomy_id": taxonomy_id,
                "fiche_path": fiche_path,
                "chunk_index": i,
                "nid": "",
                "url": "",
                "content_type": "fiche",
                "date": meta.get("generated_at", ""),
            }
            all_chunks.append(chunk)
            all_metadatas.append(chunk_meta)
            all_ids.append(chunk_id)

        stats["files"] += 1

    stats["chunks"] = len(all_chunks)

    if dry_run:
        log.info(f"  [DRY-RUN] fiches: {stats['files']} files, {stats['chunks']} chunks")
        return stats

    if all_chunks:
        chroma.add_documents(all_chunks, all_metadatas, all_ids)

    return stats


ALL_SOURCES = list(SOURCES.keys()) + ["fiches"]


def main():
    parser = argparse.ArgumentParser(description="Phase 3 : Indexation ChromaDB")
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    parser.add_argument("--reset", action="store_true", help="Supprimer et recréer la collection")
    parser.add_argument("--source", choices=ALL_SOURCES, help="Indexer une seule source")
    parser.add_argument("--dry-run", action="store_true", help="Compter sans indexer")
    args = parser.parse_args()

    cfg = load_config(args.config)

    log.info(f"ChromaDB path: {cfg.paths.chroma_db_path}")
    log.info(f"Embedding model: {cfg.embeddings.model_name}")

    # Ensure output dir exists
    cfg.paths.chroma_db_path.parent.mkdir(parents=True, exist_ok=True)

    chroma = ChromaManager(
        db_path=cfg.paths.chroma_db_path,
        model_name=cfg.embeddings.model_name,
        collection_name=cfg.retrieval.collection_name,
    )

    if args.reset:
        log.info("Resetting collection...")
        chroma.reset_collection(cfg.retrieval.collection_name)

    # Determine sources to index
    if args.source == "fiches":
        sources_to_index = {}
        do_fiches = True
    elif args.source:
        sources_to_index = {args.source: SOURCES[args.source]}
        do_fiches = False
    else:
        sources_to_index = SOURCES
        do_fiches = True

    total_stats = {"files": 0, "chunks": 0, "skipped": 0}

    for source_name, dir_key in sources_to_index.items():
        corpus_dir = getattr(cfg.paths, dir_key)
        if not corpus_dir.exists():
            log.warning(f"Répertoire introuvable: {corpus_dir} — skip {source_name}")
            continue

        log.info(f"Indexation {source_name} depuis {corpus_dir}...")
        stats = index_source(chroma, source_name, corpus_dir, cfg, dry_run=args.dry_run)
        log.info(f"  → {stats['files']} fichiers, {stats['chunks']} chunks, {stats['skipped']} skipped")

        for k in total_stats:
            total_stats[k] += stats[k]

    # Index generated fiches
    if do_fiches:
        fiches_dir = cfg.paths.fiches_dir
        if fiches_dir.exists():
            log.info(f"Indexation fiches depuis {fiches_dir}...")
            stats = index_fiches(chroma, fiches_dir, cfg, dry_run=args.dry_run)
            log.info(f"  → {stats['files']} fichiers, {stats['chunks']} chunks, {stats['skipped']} skipped")
            for k in total_stats:
                total_stats[k] += stats[k]
        else:
            log.warning(f"Répertoire fiches introuvable: {fiches_dir}")

    print(f"\n{'='*60}")
    print(f"Total: {total_stats['files']} fichiers, {total_stats['chunks']} chunks")

    if not args.dry_run:
        coll_stats = chroma.collection_stats()
        print(f"Collection: {coll_stats['total']} documents")
        if coll_stats.get("by_source"):
            for source, count in sorted(coll_stats["by_source"].items()):
                print(f"  {source}: {count}")


if __name__ == "__main__":
    main()
