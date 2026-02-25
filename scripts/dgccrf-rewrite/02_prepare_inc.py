#!/usr/bin/env python3
"""Phase 2 : Nettoyage du corpus INC — supprime le boilerplate, normalise, produit un manifeste."""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from lib.config import load_config
from lib.text_utils import (
    clean_inc_body,
    clean_inc_description,
    is_boilerplate_dominated,
    parse_md_file,
)


def scan_inc_files(inc_dir: Path, skip_dirs: list[str]) -> list[Path]:
    """Collect all .md files, excluding skip directories."""
    files = []
    skip_lower = {d.lower() for d in skip_dirs}
    for p in sorted(inc_dir.rglob("*.md")):
        # Check if any parent directory is in the skip list
        parts_lower = [part.lower() for part in p.relative_to(inc_dir).parts]
        if any(part in skip_lower for part in parts_lower[:-1]):
            continue
        files.append(p)
    return files


def process_file(
    path: Path,
    markers: list[str],
    bp_threshold: int,
    min_length: int,
) -> dict:
    """Process a single INC file. Returns a result dict."""
    result = {
        "filename": path.name,
        "relative_path": str(path),
        "status": "accepted",
        "reject_reason": None,
        "title": "",
        "source_url": "",
        "date": "",
        "original_length": 0,
        "cleaned_length": 0,
        "cleanings_applied": [],
    }

    try:
        meta, body = parse_md_file(path)
    except Exception as e:
        result["status"] = "rejected"
        result["reject_reason"] = f"parse_error: {e}"
        return result

    result["title"] = meta.get("title", "")
    result["source_url"] = meta.get("source", "")
    result["date"] = str(meta.get("date", ""))
    result["original_length"] = len(body)

    # Clean description
    if "description" in meta:
        meta["description"] = clean_inc_description(str(meta.get("description", "")))

    # Check boilerplate domination before cleaning
    if is_boilerplate_dominated(body, markers, bp_threshold):
        result["status"] = "rejected"
        result["reject_reason"] = "boilerplate_dominated"
        return result

    # Clean body
    cleaned, applied = clean_inc_body(body, markers, bp_threshold)
    result["cleanings_applied"] = applied
    result["cleaned_length"] = len(cleaned)

    # Check minimum length after cleaning
    if len(cleaned) < min_length:
        result["status"] = "rejected"
        result["reject_reason"] = f"too_short ({len(cleaned)} < {min_length})"
        return result

    # Store cleaned content for optional save
    result["_cleaned_body"] = cleaned
    result["_cleaned_meta"] = meta

    return result


def main():
    parser = argparse.ArgumentParser(description="Phase 2 : Nettoyage corpus INC")
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    parser.add_argument("--stats", action="store_true", help="Afficher les stats sans sauvegarder")
    parser.add_argument("--save-cleaned", action="store_true", help="Sauvegarder les versions nettoyées")
    parser.add_argument("--verbose", action="store_true", help="Détails par fichier")
    args = parser.parse_args()

    cfg = load_config(args.config)
    inc_dir = cfg.paths.inc_corpus_dir
    output_dir = cfg.paths.output_dir / "corpus_inc"
    cleaned_dir = output_dir / "cleaned"

    if not inc_dir.exists():
        print(f"Erreur : répertoire INC introuvable : {inc_dir}", file=sys.stderr)
        sys.exit(1)

    markers = cfg.inc_cleaning.boilerplate_markers
    bp_threshold = cfg.inc_cleaning.boilerplate_threshold
    min_length = cfg.inc_cleaning.min_content_length
    skip_dirs = cfg.inc_cleaning.skip_directories

    # Scan files
    files = scan_inc_files(inc_dir, skip_dirs)
    print(f"[INC] {len(files)} fichiers .md trouvés (après exclusion de {skip_dirs})")

    # Process
    results = []
    accepted = 0
    rejected = 0
    reject_reasons = Counter()
    cleaning_stats = Counter()

    for path in files:
        r = process_file(path, markers, bp_threshold, min_length)
        results.append(r)

        if r["status"] == "accepted":
            accepted += 1
            for c in r["cleanings_applied"]:
                cleaning_stats[c] += 1
        else:
            rejected += 1
            reject_reasons[r["reject_reason"]] += 1

        if args.verbose and r["status"] == "rejected":
            print(f"  ✗ {r['filename']} — {r['reject_reason']}")

    # Stats
    print(f"\n{'='*60}")
    print(f"Résultats : {accepted} acceptés, {rejected} rejetés sur {len(files)}")
    print(f"Taux d'acceptation : {accepted/len(files)*100:.1f}%")

    if reject_reasons:
        print(f"\nMotifs de rejet :")
        for reason, count in reject_reasons.most_common():
            print(f"  {reason}: {count}")

    if cleaning_stats:
        print(f"\nNettoyages appliqués :")
        for cleaning, count in cleaning_stats.most_common():
            print(f"  {cleaning}: {count} fichiers")

    # Size distribution of accepted files
    accepted_lengths = [r["cleaned_length"] for r in results if r["status"] == "accepted"]
    if accepted_lengths:
        print(f"\nDistribution des tailles (acceptés) :")
        print(f"  Min: {min(accepted_lengths):,} chars")
        print(f"  Max: {max(accepted_lengths):,} chars")
        print(f"  Moyenne: {sum(accepted_lengths)//len(accepted_lengths):,} chars")

    if args.stats:
        print("\n(Mode --stats : pas de sauvegarde)")
        return

    # Save manifest
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": "inc",
        "generated_at": datetime.now().isoformat(),
        "total_scanned": len(files),
        "accepted": accepted,
        "rejected": rejected,
        "rejected_by_reason": dict(reject_reasons),
        "cleaning_stats": dict(cleaning_stats),
        "files": [
            {
                "filename": r["filename"],
                "title": r["title"],
                "source_url": r["source_url"],
                "date": r["date"],
                "cleaned_length": r["cleaned_length"],
                "cleanings_applied": r["cleanings_applied"],
            }
            for r in results
            if r["status"] == "accepted"
        ],
    }
    manifest_path = output_dir / "_corpus_inc.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nManifeste écrit : {manifest_path}")

    # Save cleaned files
    if args.save_cleaned:
        cleaned_dir.mkdir(parents=True, exist_ok=True)
        saved = 0
        for r in results:
            if r["status"] != "accepted":
                continue
            cleaned_body = r.get("_cleaned_body", "")
            cleaned_meta = r.get("_cleaned_meta", {})
            if not cleaned_body:
                continue

            # Rebuild file with cleaned frontmatter + body
            import frontmatter as fm

            post = fm.Post(cleaned_body, **cleaned_meta)
            out_path = cleaned_dir / r["filename"]
            with open(out_path, "w") as f:
                f.write(fm.dumps(post))
            saved += 1

        print(f"Fichiers nettoyés sauvegardés : {saved} dans {cleaned_dir}")


if __name__ == "__main__":
    main()
