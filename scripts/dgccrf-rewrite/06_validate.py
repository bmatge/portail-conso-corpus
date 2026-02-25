#!/usr/bin/env python3
"""Phase 6 : Validation des fiches générées — structure, URLs, complétude."""

import argparse
import json
import logging
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

import frontmatter as fm

from lib.config import load_config
from lib.taxonomy import Domaine, Situation, SousDomaine, load_taxonomy

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

EXPECTED_SECTIONS = {
    "domaine": [
        "en bref",
        "ce que couvre ce domaine",
        "vos droits essentiels",
        "que faire en cas de probleme",
        "les services a connaitre",
        "pour aller plus loin",
    ],
    "sous_domaine": [
        "en bref",
        "de quoi s'agit-il",
        "quels sont vos droits",
        "les situations les plus frequentes",
        "que faire concretement",
        "ou signaler",
        "pour aller plus loin",
    ],
    "situation": [
        "en bref",
        "de quoi s'agit-il",
        "quels sont vos droits",
        "que faire concretement",
        "exemples",
        "ou signaler",
        "pour aller plus loin",
    ],
}

MIN_WORDS = {"domaine": 800, "sous_domaine": 1000, "situation": 800}


def normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, strip accents, strip punctuation."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_h2_sections(body: str) -> list[str]:
    """Extract normalized H2 section names from markdown body."""
    sections = []
    for match in re.finditer(r"^##\s+(.+)$", body, re.MULTILINE):
        sections.append(normalize(match.group(1)))
    return sections


def validate_fiche(
    path: Path, level: str, item, taxonomy, fiches_dir: Path
) -> dict:
    """Validate a single fiche. Returns result dict."""
    result = {
        "id": item.id,
        "level": level,
        "path": str(path),
        "status": "ok",
        "checks": [],
    }

    # Read file
    try:
        text = path.read_text()
        post = fm.loads(text)
        body = post.content
    except Exception as e:
        result["status"] = "error"
        result["checks"].append({"check": "readable", "passed": False, "detail": str(e)})
        return result

    # 1. Expected sections
    actual_sections = extract_h2_sections(body)
    expected = EXPECTED_SECTIONS.get(level, [])
    missing_sections = []
    for exp in expected:
        # Fuzzy match: normalize expected too before substring check
        norm_exp = normalize(exp)
        if not any(norm_exp in s for s in actual_sections):
            missing_sections.append(exp)

    result["checks"].append({
        "check": "sections_present",
        "passed": len(missing_sections) == 0,
        "detail": f"Missing: {', '.join(missing_sections)}" if missing_sections else "All present",
    })

    # 2. URLs integrated (for situation and sous_domaine)
    if level == "situation" and isinstance(item, Situation):
        missing_urls = []
        for sortie in item.sorties:
            url = taxonomy.resolve_sortie_url(sortie)
            if url and url not in body:
                missing_urls.append(f"{sortie.type}: {url}")
        result["checks"].append({
            "check": "urls_integrated",
            "passed": len(missing_urls) == 0,
            "detail": f"Missing: {', '.join(missing_urls[:5])}" if missing_urls else "All present",
        })

    # 3. Mediateur mentioned
    if level in ("situation", "sous_domaine"):
        sd = item if level == "sous_domaine" else taxonomy.get_sous_domaine_for(item)
        if sd and sd.mediateur:
            has_mediateur = sd.mediateur.url in body or sd.mediateur.label.lower() in body.lower()
            result["checks"].append({
                "check": "mediateur_mentioned",
                "passed": has_mediateur,
                "detail": f"Looking for: {sd.mediateur.label}" if not has_mediateur else "Found",
            })

    # 4. SignalConso URL
    if level == "situation" and isinstance(item, Situation) and item.signalconso:
        sc = item.signalconso
        has_sc_url = False
        if sc.url_signalement and sc.url_signalement in body:
            has_sc_url = True
        if sc.url_signalement_alt:
            for url in sc.url_signalement_alt.values():
                if url in body:
                    has_sc_url = True
        if sc.category:
            # Check if category-level URL from signalconso_categories is present
            cat_info = taxonomy.signalconso_categories.get(sc.category, {})
            if cat_info.get("url_signalement") and cat_info["url_signalement"] in body:
                has_sc_url = True

        result["checks"].append({
            "check": "signalconso_url",
            "passed": has_sc_url,
            "detail": "SignalConso URL found" if has_sc_url else "No SignalConso URL found",
        })

    # 5. Links to children
    if level == "domaine" and isinstance(item, Domaine):
        missing_links = []
        for sd in item.sous_domaines:
            if sd.id not in body:
                missing_links.append(sd.id)
        result["checks"].append({
            "check": "child_links",
            "passed": len(missing_links) == 0,
            "detail": f"Missing links to: {', '.join(missing_links[:5])}" if missing_links else "All linked",
        })
    elif level == "sous_domaine" and isinstance(item, SousDomaine):
        missing_links = []
        for s in item.situations:
            if s.id not in body:
                missing_links.append(s.id)
        result["checks"].append({
            "check": "child_links",
            "passed": len(missing_links) == 0,
            "detail": f"Missing links to: {', '.join(missing_links[:5])}" if missing_links else "All linked",
        })

    # 6. No HTML
    html_tags = re.findall(r"<(?:div|span|p|a|br|img|table|tr|td|th)\b", body, re.IGNORECASE)
    result["checks"].append({
        "check": "no_html",
        "passed": len(html_tags) == 0,
        "detail": f"HTML tags found: {len(html_tags)}" if html_tags else "Clean markdown",
    })

    # 7. Minimum length
    word_count = len(body.split())
    min_words = MIN_WORDS.get(level, 200)
    result["checks"].append({
        "check": "min_length",
        "passed": word_count >= min_words,
        "detail": f"{word_count} words (min: {min_words})",
    })

    # 8. [À COMPLÉTER] markers
    markers = re.findall(r"\[À COMPLÉTER\]|\[A COMPLETER\]", body, re.IGNORECASE)
    result["checks"].append({
        "check": "a_completer_count",
        "passed": len(markers) == 0,
        "detail": f"{len(markers)} markers" if markers else "None",
    })

    # Aggregate status
    failed_checks = [c for c in result["checks"] if not c["passed"]]
    critical = {"sections_present", "readable", "min_length"}
    has_critical = any(c["check"] in critical for c in failed_checks)

    if has_critical:
        result["status"] = "error"
    elif failed_checks:
        result["status"] = "warning"

    return result


def main():
    parser = argparse.ArgumentParser(description="Phase 6 : Validation des fiches")
    parser.add_argument("--config", default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--level", choices=["domaine", "sous_domaine", "situation"])
    args = parser.parse_args()

    cfg = load_config(args.config)
    taxonomy = load_taxonomy(cfg.paths.taxonomy_file)
    fiches_dir = cfg.paths.fiches_dir

    if not fiches_dir.exists():
        print(f"Erreur : répertoire des fiches introuvable : {fiches_dir}", file=sys.stderr)
        sys.exit(1)

    # Build expected files
    all_items = taxonomy.all_items()
    if args.level:
        all_items = [(l, i, o) for l, i, o in all_items if l == args.level]

    results = []
    missing = []
    status_counts = Counter()
    level_stats = {}
    a_completer_total = 0

    for level, item_id, item in all_items:
        from lib.taxonomy import Situation as SitType
        path = None

        if level == "domaine":
            path = fiches_dir / item.id / "_index.md"
        elif level == "sous_domaine":
            domaine = taxonomy.get_domaine_for(item)
            d_id = domaine.id if domaine else "unknown"
            path = fiches_dir / d_id / item.id / "_index.md"
        else:
            if isinstance(item, SitType) and item.is_transversale:
                path = fiches_dir / "transversales" / f"{item.id}.md"
            else:
                sd = taxonomy.get_sous_domaine_for(item)
                domaine = taxonomy.get_domaine_for(item)
                d_id = domaine.id if domaine else "unknown"
                sd_id = sd.id if sd else "unknown"
                path = fiches_dir / d_id / sd_id / f"{item.id}.md"

        if not path.exists():
            missing.append({"id": item_id, "level": level, "expected_path": str(path)})
            continue

        result = validate_fiche(path, level, item, taxonomy, fiches_dir)
        results.append(result)

        status_counts[result["status"]] += 1
        level_stats.setdefault(level, Counter())[result["status"]] += 1

        # Count [À COMPLÉTER]
        for c in result["checks"]:
            if c["check"] == "a_completer_count" and not c["passed"]:
                count = int(re.search(r"(\d+)", c["detail"]).group(1)) if re.search(r"(\d+)", c["detail"]) else 0
                a_completer_total += count

        if args.verbose:
            emoji = {"ok": "✓", "warning": "~", "error": "✗"}
            failed = [c for c in result["checks"] if not c["passed"]]
            if failed:
                print(f"  {emoji.get(result['status'], '?')} [{level}] {item_id}:")
                for c in failed:
                    print(f"    - {c['check']}: {c['detail']}")

    # Write report
    report = {
        "generated_at": datetime.now().isoformat(),
        "total_expected": len(all_items),
        "total_found": len(results),
        "missing_count": len(missing),
        "missing": missing,
        "summary": dict(status_counts),
        "by_level": {k: dict(v) for k, v in level_stats.items()},
        "a_completer_total": a_completer_total,
        "fiches": results,
    }

    report_path = cfg.paths.output_dir / "_validation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Validation : {len(results)} fiches trouvées sur {len(all_items)} attendues")
    if missing:
        print(f"  Manquantes : {len(missing)}")

    print(f"\nStatut global :")
    for status in ["ok", "warning", "error"]:
        count = status_counts.get(status, 0)
        pct = count / len(results) * 100 if results else 0
        emoji = {"ok": "✓", "warning": "~", "error": "✗"}[status]
        print(f"  {emoji} {status:8s}: {count:3d} ({pct:.1f}%)")

    if level_stats:
        print(f"\nPar niveau :")
        for level_name in ["domaine", "sous_domaine", "situation"]:
            if level_name in level_stats:
                s = level_stats[level_name]
                total = sum(s.values())
                print(f"  {level_name}: {total} fiches — {dict(s)}")

    if a_completer_total:
        print(f"\n  [À COMPLÉTER] : {a_completer_total} marqueurs au total")

    print(f"\nRapport : {report_path}")


if __name__ == "__main__":
    main()
