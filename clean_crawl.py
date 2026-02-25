#!/usr/bin/env python3
"""
Nettoyage post-crawl : supprime les fichiers .md sans vrai contenu
==================================================================
Détecte et supprime les pages qui ne contiennent que du boilerplate
(bandeau cookies, liens réseaux sociaux, etc.)

Usage :
    python clean_crawl.py ./inc-conso-md              # simulation (dry-run)
    python clean_crawl.py ./inc-conso-md --force       # suppression réelle
    python clean_crawl.py ./inc-conso-md --min-length 500  # seuil personnalisé
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


# ── Configuration ────────────────────────────────────────────────────────────

# Longueur minimale du contenu utile (hors front matter + titre)
DEFAULT_MIN_LENGTH = 300

# Phrases typiques du boilerplate inc-conso.fr
BOILERPLATE_MARKERS = [
    "ce site utilise et partage avec des tiers",
    "cookies et autres traceurs",
    "paramétrer votre choix",
    "gérer les cookies",
    "le dépôt de ces cookies est soumis",
    "politique cookies",
    "mesure d'audience",
    "partage de contenu sur les réseaux sociaux",
    "vous pouvez indiquer votre choix catégorie par catégorie",
    "accepter ou de refuser globalement",
]

# Lignes « bruit » : noms de réseaux sociaux isolés, tirets seuls
NOISE_LINE_RE = re.compile(
    r"^\s*[-*]\s*$|^\s*(youtube|facebook|linkedin|twitter|instagram|tiktok)\s*$",
    re.IGNORECASE,
)


# ── Analyse ──────────────────────────────────────────────────────────────────

def extract_body(md_text: str) -> str:
    """Retire le front matter YAML et le titre H1, retourne le corps."""
    body = re.sub(r"^---\n.*?\n---\n*", "", md_text, flags=re.DOTALL)
    body = re.sub(r"^#\s+.*\n*", "", body)
    return body.strip()


def analyze_file(md_text: str, min_length: int) -> tuple[bool, str]:
    """
    Retourne (garder: bool, raison: str).
    """
    body = extract_body(md_text)

    # 1. Trop court
    if len(body) < min_length:
        return False, f"trop court ({len(body)} car.)"

    # 2. Dominé par le boilerplate cookies
    body_lower = body.lower()
    boilerplate_hits = sum(1 for m in BOILERPLATE_MARKERS if m in body_lower)
    if boilerplate_hits >= 4:
        return False, f"boilerplate cookies ({boilerplate_hits} marqueurs)"

    # 3. Après retrait des lignes bruit, reste-t-il du contenu ?
    cleaned = NOISE_LINE_RE.sub("", body).strip()
    # Retirer aussi les blocs boilerplate connus
    for marker in BOILERPLATE_MARKERS:
        cleaned = re.sub(re.escape(marker), "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    if len(cleaned) < min_length:
        return False, f"contenu réel trop court ({len(cleaned)} car. après nettoyage)"

    return True, "ok"


# ── Nettoyage ────────────────────────────────────────────────────────────────

def clean(directory: str, min_length: int, force: bool):
    output_path = Path(directory)
    if not output_path.exists():
        print(f"❌ Dossier introuvable : {directory}")
        sys.exit(1)

    dry_run = not force
    md_files = sorted(output_path.rglob("*.md"))
    # Ignorer les fichiers internes (_urls.json, _errors.json, etc.)
    md_files = [f for f in md_files if not f.name.startswith("_")]
    total = len(md_files)

    print("=" * 60)
    mode = "SIMULATION" if dry_run else "SUPPRESSION"
    print(f"🧹 Nettoyage post-crawl [{mode}]")
    print(f"   📁 Dossier       : {output_path.resolve()}")
    print(f"   📄 Fichiers .md  : {total}")
    print(f"   📏 Seuil min     : {min_length} caractères")
    print("=" * 60)

    kept = 0
    removed = 0
    removed_files = []

    for md_file in md_files:
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()

        is_ok, reason = analyze_file(content, min_length)
        rel = md_file.relative_to(output_path)

        if is_ok:
            kept += 1
        else:
            removed += 1
            removed_files.append({"file": str(rel), "reason": reason})
            print(f"   🗑️  {rel}  →  {reason}")
            if not dry_run:
                md_file.unlink()

    # Supprimer les dossiers vides
    if not dry_run:
        for d in sorted(output_path.rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()

    # Rapport JSON
    report = {
        "date": datetime.now().isoformat(),
        "mode": mode,
        "min_length": min_length,
        "total_scanned": total,
        "kept": kept,
        "removed": removed,
        "removed_files": removed_files,
    }
    report_file = output_path / "_cleanup_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'─' * 60}")
    print(f"📊 Résultat ({mode}) :")
    print(f"   ✅ Conservées  : {kept}")
    print(f"   🗑️  Supprimées  : {removed}")
    print(f"   📝 Rapport     : {report_file}")
    if dry_run:
        print(f"\n   💡 Pour supprimer réellement, relancez avec --force")
    print("─" * 60)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Nettoie les pages .md vides ou boilerplate après un crawl",
    )
    parser.add_argument(
        "directory",
        help="Dossier contenant les fichiers .md du crawl",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Supprimer réellement les fichiers (sinon dry-run)",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=DEFAULT_MIN_LENGTH,
        help=f"Longueur min du contenu utile en caractères (défaut: {DEFAULT_MIN_LENGTH})",
    )
    args = parser.parse_args()
    clean(args.directory, args.min_length, args.force)


if __name__ == "__main__":
    main()