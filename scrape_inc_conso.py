#!/usr/bin/env python3
"""
Aspirateur de site inc-conso.fr → Markdown
==========================================
Parcourt toutes les pages du sitemap, extrait le contenu principal
(sans header/footer/nav) et le sauvegarde en fichiers .md

Dépendances :
    pip install trafilatura lxml requests

Usage :
    python scrape_inc_conso.py                    # lance l'aspiration complète
    python scrape_inc_conso.py --limit 10         # limite à 10 pages (test)
    python scrape_inc_conso.py --delay 2          # 2s entre chaque requête
    python scrape_inc_conso.py --output ./mon_dossier
    python scrape_inc_conso.py --resume            # reprend là où on s'est arrêté
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from lxml import etree

import trafilatura
from trafilatura.settings import use_config

# ── Configuration ────────────────────────────────────────────────────────────

SITE_URL = "https://www.inc-conso.fr"
SITEMAP_INDEX_URL = f"{SITE_URL}/sitemap.xml"
DEFAULT_OUTPUT_DIR = "./inc-conso-md"
DEFAULT_DELAY = 1.0  # secondes entre chaque requête (politesse)
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ContentArchiver/1.0"

# Namespace XML pour les sitemaps
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_session() -> requests.Session:
    """Crée une session HTTP réutilisable."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
    })
    return session


def url_to_filepath(url: str, output_dir: str) -> Path:
    """
    Convertit une URL en chemin de fichier .md en préservant la structure.
    Ex: https://www.inc-conso.fr/content/mon-article → content/mon-article.md
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")

    if not path:
        path = "index"

    # Nettoyer les caractères problématiques
    path = re.sub(r'[<>:"|?*]', "_", path)

    # Ajouter .md si pas déjà une extension
    if not path.endswith(".md"):
        path += ".md"

    return Path(output_dir) / path


def load_progress(output_dir: str) -> set:
    """Charge la liste des URLs déjà traitées (pour --resume)."""
    progress_file = Path(output_dir) / ".progress.json"
    if progress_file.exists():
        with open(progress_file, "r") as f:
            data = json.load(f)
            return set(data.get("done", []))
    return set()


def save_progress(output_dir: str, done_urls: set):
    """Sauvegarde la progression."""
    progress_file = Path(output_dir) / ".progress.json"
    with open(progress_file, "w") as f:
        json.dump({
            "done": list(done_urls),
            "last_update": datetime.now().isoformat(),
            "count": len(done_urls),
        }, f, indent=2)


# ── Étape 1 : Récupérer toutes les URLs depuis le sitemap ───────────────────

def fetch_sitemap_index(session: requests.Session) -> list[str]:
    """Récupère la liste des sous-sitemaps depuis le sitemap index."""
    print(f"📥 Récupération du sitemap index : {SITEMAP_INDEX_URL}")
    resp = session.get(SITEMAP_INDEX_URL, timeout=30)
    resp.raise_for_status()

    root = etree.fromstring(resp.content)
    sitemap_urls = [loc.text for loc in root.findall(".//sm:sitemap/sm:loc", NS)]
    print(f"   → {len(sitemap_urls)} sous-sitemaps trouvés")
    return sitemap_urls


def fetch_urls_from_sitemap(session: requests.Session, sitemap_url: str) -> list[dict]:
    """Récupère les URLs et métadonnées d'un sous-sitemap."""
    resp = session.get(sitemap_url, timeout=30)
    resp.raise_for_status()

    root = etree.fromstring(resp.content)
    urls = []
    for url_elem in root.findall(".//sm:url", NS):
        loc = url_elem.find("sm:loc", NS)
        lastmod = url_elem.find("sm:lastmod", NS)
        if loc is not None and loc.text:
            urls.append({
                "url": loc.text,
                "lastmod": lastmod.text if lastmod is not None else None,
            })
    return urls


def collect_all_urls(session: requests.Session, delay: float) -> list[dict]:
    """Parcourt tous les sous-sitemaps et collecte toutes les URLs."""
    sitemap_urls = fetch_sitemap_index(session)
    all_urls = []

    for i, sitemap_url in enumerate(sitemap_urls, 1):
        print(f"   📄 Sous-sitemap {i}/{len(sitemap_urls)} : {sitemap_url}")
        try:
            urls = fetch_urls_from_sitemap(session, sitemap_url)
            all_urls.extend(urls)
            print(f"      → {len(urls)} URLs")
        except Exception as e:
            print(f"      ⚠️  Erreur : {e}")
        time.sleep(delay * 0.3)  # délai réduit pour les sitemaps (léger)

    print(f"\n📊 Total : {len(all_urls)} URLs collectées")
    return all_urls


# ── Étape 2 : Extraire le contenu et convertir en Markdown ──────────────────

def extract_to_markdown(session: requests.Session, url: str) -> dict | None:
    """
    Télécharge une page et extrait le contenu principal en Markdown.
    Retourne un dict avec le contenu, le titre, et les métadonnées.
    """
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return {"error": str(e), "url": url}

    # Configuration trafilatura pour une extraction optimale
    config = use_config()
    config.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")

    # Extraire le contenu principal (sans nav, header, footer, sidebar...)
    content = trafilatura.extract(
        html,
        output_format="markdown",
        include_links=True,
        include_images=True,
        include_tables=True,
        include_comments=False,
        favor_recall=True,  # préfère récupérer plus de contenu
        config=config,
    )

    # Extraire aussi les métadonnées
    metadata = trafilatura.extract_metadata(html)

    if not content:
        return {"error": "Aucun contenu extrait", "url": url}

    result = {
        "url": url,
        "content": content,
        "title": metadata.title if metadata else None,
        "author": metadata.author if metadata else None,
        "date": metadata.date if metadata else None,
        "description": metadata.description if metadata else None,
        "categories": metadata.categories if metadata else None,
        "tags": metadata.tags if metadata else None,
    }

    return result


def build_markdown_file(data: dict) -> str:
    """Construit le fichier Markdown final avec front matter YAML."""
    lines = ["---"]

    if data.get("title"):
        # Échapper les guillemets dans le titre
        title = data["title"].replace('"', '\\"')
        lines.append(f'title: "{title}"')
    if data.get("url"):
        lines.append(f'source: "{data["url"]}"')
    if data.get("date"):
        lines.append(f"date: {data['date']}")
    if data.get("author"):
        lines.append(f'author: "{data["author"]}"')
    if data.get("description"):
        desc = data["description"].replace('"', '\\"')
        lines.append(f'description: "{desc}"')
    if data.get("categories"):
        lines.append(f'categories: "{data["categories"]}"')
    if data.get("tags"):
        lines.append(f'tags: "{data["tags"]}"')

    lines.append(f'scraped_at: "{datetime.now().isoformat()}"')
    lines.append("---\n")

    if data.get("title"):
        lines.append(f"# {data['title']}\n")

    lines.append(data.get("content", ""))

    return "\n".join(lines)


# ── Pipeline principal ───────────────────────────────────────────────────────

def run(output_dir: str, delay: float, limit: int | None, resume: bool):
    """Lance l'aspiration complète."""
    session = get_session()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Collecter les URLs
    print("=" * 60)
    print("🕷️  Aspirateur inc-conso.fr → Markdown")
    print("=" * 60)

    all_urls = collect_all_urls(session, delay)

    if not all_urls:
        print("❌ Aucune URL trouvée. Vérifiez la connexion.")
        sys.exit(1)

    # Sauvegarder la liste complète des URLs (utile pour référence)
    urls_file = output_path / "_urls.json"
    with open(urls_file, "w") as f:
        json.dump(all_urls, f, indent=2, ensure_ascii=False)
    print(f"💾 Liste des URLs sauvegardée : {urls_file}")

    # Mode resume : charger la progression
    done_urls = set()
    if resume:
        done_urls = load_progress(output_dir)
        if done_urls:
            print(f"🔄 Reprise : {len(done_urls)} URLs déjà traitées, on continue.")

    # Appliquer la limite
    urls_to_process = all_urls
    if limit:
        urls_to_process = all_urls[:limit]
        print(f"⚠️  Mode limité : {limit} pages seulement")

    # Filtrer les URLs déjà faites
    urls_to_process = [u for u in urls_to_process if u["url"] not in done_urls]
    total = len(urls_to_process)

    if total == 0:
        print("✅ Toutes les URLs ont déjà été traitées !")
        return

    print(f"\n🚀 Lancement de l'extraction de {total} pages...\n")

    success = 0
    errors = 0
    error_log = []

    for i, url_data in enumerate(urls_to_process, 1):
        url = url_data["url"]
        progress_pct = (i / total) * 100
        print(f"[{i}/{total}] ({progress_pct:.0f}%) {url[:80]}...", end=" ")

        result = extract_to_markdown(session, url)

        if result and "error" not in result and result.get("content"):
            # Construire le fichier .md
            md_content = build_markdown_file(result)
            filepath = url_to_filepath(url, output_dir)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(md_content)

            success += 1
            title_preview = (result.get("title") or "")[:40]
            print(f"✅ {title_preview}")
        else:
            errors += 1
            err_msg = result.get("error", "Inconnu") if result else "Aucun résultat"
            print(f"❌ {err_msg}")
            error_log.append({"url": url, "error": err_msg})

        # Sauvegarder la progression
        done_urls.add(url)
        if i % 25 == 0:
            save_progress(output_dir, done_urls)

        # Politesse : attendre entre chaque requête
        if i < total:
            time.sleep(delay)

    # Sauvegarder la progression finale
    save_progress(output_dir, done_urls)

    # Sauvegarder le log d'erreurs
    if error_log:
        err_file = output_path / "_errors.json"
        with open(err_file, "w") as f:
            json.dump(error_log, f, indent=2, ensure_ascii=False)

    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ")
    print("=" * 60)
    print(f"   ✅ Pages extraites : {success}")
    print(f"   ❌ Erreurs         : {errors}")
    print(f"   📁 Dossier         : {output_path.resolve()}")
    if error_log:
        print(f"   📝 Log erreurs     : {output_path / '_errors.json'}")
    print("=" * 60)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Aspire le contenu de inc-conso.fr en fichiers Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python scrape_inc_conso.py                     # aspiration complète
  python scrape_inc_conso.py --limit 20          # test sur 20 pages
  python scrape_inc_conso.py --delay 2           # 2s entre chaque requête
  python scrape_inc_conso.py --resume             # reprendre après interruption
  python scrape_inc_conso.py --output ~/Bureau/inc-conso
        """,
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Dossier de sortie (défaut: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Délai en secondes entre chaque requête (défaut: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Nombre max de pages à traiter (pour tester)",
    )
    parser.add_argument(
        "--resume", "-r",
        action="store_true",
        help="Reprendre une extraction interrompue",
    )

    args = parser.parse_args()
    run(args.output, args.delay, args.limit, args.resume)


if __name__ == "__main__":
    main()