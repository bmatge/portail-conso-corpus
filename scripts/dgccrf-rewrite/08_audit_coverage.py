#!/usr/bin/env python3
"""Phase 8 : Audit de couverture — identifie les sujets consommation manquants de la taxonomie."""

import argparse
import json
import logging
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import frontmatter as fm
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from lib.chroma_utils import ChromaManager
from lib.config import load_config
from lib.taxonomy import load_taxonomy

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


# ── Noise filtering ──────────────────────────────────────────────────────


OUT_OF_SCOPE_KEYWORDS = [
    "impôt", "impots", "fiscal", "fiscalité", "taxe foncière",
    "taxe habitation", "déclaration revenus", "prélèvement à la source",
    "emploi", "chômage", "pôle emploi", "france travail", "licenciement",
    "contrat de travail", "droit du travail", "salarié",
    "retraite", "pension", "caisse retraite",
    "scolarité", "université", "bourse étudiant", "parcoursup",
    "carte identité", "passeport", "permis conduire",
    "élection", "vote", "carte électorale",
    "sécurité sociale", "carte vitale", "ameli",
]


def is_out_of_scope(title: str, body: str) -> bool:
    """Check if an article is out of consumer protection scope."""
    text = (title + " " + body[:500]).lower()
    matches = sum(1 for kw in OUT_OF_SCOPE_KEYWORDS if kw in text)
    return matches >= 2


# ── Corpus loading ───────────────────────────────────────────────────────


def load_corpus_articles(source_dirs: dict[str, Path], verbose: bool = False) -> list[dict]:
    """Load all .md articles from source directories.

    Returns: [{source, file, title, snippet, path}]
    """
    articles = []

    for source_name, source_dir in source_dirs.items():
        if not source_dir.exists():
            log.warning(f"Source dir missing: {source_dir}")
            continue

        md_files = list(source_dir.rglob("*.md"))
        loaded = 0

        for md_file in md_files:
            try:
                post = fm.load(md_file)
                title = post.metadata.get("title", "") or post.metadata.get("titre", "")
                if not title:
                    # Try to extract from first H1
                    match = re.match(r"^#\s+(.+)", post.content)
                    title = match.group(1) if match else md_file.stem

                body = post.content.strip()
                if len(body) < 100:
                    continue

                articles.append({
                    "source": source_name,
                    "file": str(md_file.relative_to(source_dir)),
                    "title": title.strip(),
                    "snippet": body[:500],
                    "path": str(md_file),
                })
                loaded += 1

            except Exception:
                continue

        if verbose:
            log.info(f"  {source_name}: {loaded} articles chargés depuis {source_dir}")

    return articles


# ── Embedding ────────────────────────────────────────────────────────────


def embed_taxonomy_items(taxonomy, embed_fn) -> tuple[np.ndarray, list[dict]]:
    """Embed all taxonomy items. Returns (embeddings_matrix, items_list)."""
    items = []
    texts = []

    for level, item_id, item in taxonomy.all_items():
        if level == "situation":
            exemples = ". ".join(item.exemples[:3]) if item.exemples else ""
            text = f"{item.label}. {exemples}"
        elif level == "sous_domaine":
            sit_labels = ", ".join(s.label for s in item.situations[:5])
            text = f"{item.label}. {sit_labels}"
        elif level == "domaine":
            text = f"{item.label}. {item.description}"
        else:
            text = item.label

        items.append({"id": item_id, "label": item.label, "level": level})
        texts.append(text)

    embeddings = np.array(embed_fn(texts))
    return embeddings, items


def embed_articles(articles: list[dict], embed_fn, batch_size: int = 100) -> np.ndarray:
    """Embed article titles+snippets. Returns embeddings matrix."""
    texts = [f"{a['title']}. {a['snippet'][:300]}" for a in articles]

    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_emb = embed_fn(batch)
        all_embeddings.extend(batch_emb)

    return np.array(all_embeddings)


# ── Orphan detection ─────────────────────────────────────────────────────


def find_orphans(
    article_embeddings: np.ndarray,
    taxonomy_embeddings: np.ndarray,
    articles: list[dict],
    taxonomy_items: list[dict],
    threshold: float = 0.45,
) -> list[dict]:
    """Find articles that don't match any taxonomy item.

    Returns articles with max_similarity < threshold, annotated with
    their nearest taxonomy item.
    """
    # Compute similarity: articles x taxonomy
    sim_matrix = cosine_similarity(article_embeddings, taxonomy_embeddings)
    max_sims = sim_matrix.max(axis=1)
    best_indices = sim_matrix.argmax(axis=1)

    orphans = []
    for i, (max_sim, best_idx) in enumerate(zip(max_sims, best_indices)):
        if max_sim < threshold:
            article = articles[i].copy()
            article["max_similarity"] = round(float(max_sim), 3)
            article["nearest_item"] = taxonomy_items[best_idx]
            orphans.append(article)

    return orphans


# ── Clustering ───────────────────────────────────────────────────────────


def cluster_orphans(
    orphans: list[dict],
    orphan_embeddings: np.ndarray,
    min_cluster_size: int = 5,
) -> list[dict]:
    """Cluster orphan articles. Returns list of clusters.

    Tries HDBSCAN first, falls back to KMeans.
    """
    if len(orphans) < min_cluster_size:
        log.warning(f"Too few orphans ({len(orphans)}) to cluster")
        return []

    labels = None

    # Try HDBSCAN
    try:
        import hdbscan
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            metric="euclidean",
        )
        labels = clusterer.fit_predict(orphan_embeddings)
        method = "hdbscan"
        log.info(f"HDBSCAN: {len(set(labels)) - (1 if -1 in labels else 0)} clusters, "
                 f"{(labels == -1).sum()} noise points")
    except ImportError:
        log.info("HDBSCAN not available, falling back to KMeans")

    # Fallback: KMeans
    if labels is None:
        from sklearn.cluster import KMeans
        k = max(2, int(np.sqrt(len(orphans) / 2)))
        k = min(k, len(orphans) // min_cluster_size)
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(orphan_embeddings)
        method = "kmeans"
        log.info(f"KMeans: {k} clusters")

    # Group by cluster
    clusters_dict: dict[int, list[int]] = {}
    for i, label in enumerate(labels):
        if label == -1:
            continue  # noise
        clusters_dict.setdefault(label, []).append(i)

    # Build cluster objects
    clusters = []
    for cluster_id, indices in sorted(clusters_dict.items()):
        if len(indices) < min_cluster_size:
            continue

        cluster_embeddings = orphan_embeddings[indices]
        centroid = cluster_embeddings.mean(axis=0)

        # Find representative articles (closest to centroid)
        dists = np.linalg.norm(cluster_embeddings - centroid, axis=1)
        sorted_idx = np.argsort(dists)
        representatives = [indices[j] for j in sorted_idx[:5]]

        clusters.append({
            "cluster_id": cluster_id,
            "size": len(indices),
            "indices": indices,
            "centroid": centroid,
            "representative_indices": representatives,
            "method": method,
        })

    return clusters


# ── Cluster analysis ─────────────────────────────────────────────────────


def analyze_clusters(
    clusters: list[dict],
    orphans: list[dict],
    taxonomy_embeddings: np.ndarray,
    taxonomy_items: list[dict],
) -> list[dict]:
    """Analyze each cluster: description, nearest taxonomy item, priority.

    Returns enriched cluster data sorted by priority_score descending.
    """
    results = []

    for cluster in clusters:
        indices = cluster["indices"]
        centroid = cluster["centroid"]
        size = cluster["size"]

        # Nearest taxonomy item to centroid
        centroid_2d = centroid.reshape(1, -1)
        sims = cosine_similarity(centroid_2d, taxonomy_embeddings)[0]
        best_tax_idx = sims.argmax()
        best_sim = float(sims[best_tax_idx])

        nearest = taxonomy_items[best_tax_idx]

        # TF-IDF keywords from cluster titles
        cluster_titles = [orphans[i]["title"] for i in indices]
        keywords = extract_keywords(cluster_titles)

        # Representative articles
        sample_articles = [
            {
                "title": orphans[i]["title"],
                "source": orphans[i]["source"],
                "file": orphans[i]["file"],
            }
            for i in cluster["representative_indices"]
        ]

        # Priority score: log(size) * (1 - similarity_to_taxonomy)
        distance = 1.0 - best_sim
        priority = np.log1p(size) * distance

        # Suggested placement
        suggested_domaine = nearest.get("id", "")
        if nearest.get("level") == "situation":
            # Find the parent
            for item in taxonomy_items:
                if item["level"] == "sous_domaine" and item["id"] in suggested_domaine:
                    suggested_domaine = item["id"]
                    break

        results.append({
            "cluster_id": cluster["cluster_id"],
            "size": size,
            "method": cluster["method"],
            "description": ", ".join(keywords[:8]),
            "keywords": keywords[:10],
            "sample_articles": sample_articles,
            "nearest_taxonomy_item": {
                "id": nearest["id"],
                "label": nearest["label"],
                "level": nearest["level"],
                "similarity": round(best_sim, 3),
            },
            "priority_score": round(float(priority), 2),
        })

    results.sort(key=lambda c: c["priority_score"], reverse=True)
    return results


def extract_keywords(titles: list[str], top_n: int = 10) -> list[str]:
    """Extract top TF-IDF keywords from a list of titles."""
    if not titles:
        return []

    try:
        vectorizer = TfidfVectorizer(
            max_features=200,
            stop_words=None,  # French stopwords handled manually
            ngram_range=(1, 2),
            min_df=1,
        )
        tfidf_matrix = vectorizer.fit_transform(titles)
        feature_names = vectorizer.get_feature_names_out()

        # Aggregate TF-IDF scores across documents
        mean_scores = tfidf_matrix.mean(axis=0).A1
        top_indices = mean_scores.argsort()[-top_n:][::-1]

        # Filter French stopwords
        stopwords = {
            "de", "du", "la", "le", "les", "des", "un", "une", "et", "en",
            "à", "au", "aux", "ce", "cette", "ces", "son", "sa", "ses",
            "pour", "par", "sur", "dans", "avec", "que", "qui", "est",
            "sont", "pas", "ne", "ou", "il", "elle", "on", "nous", "vous",
            "se", "si", "tout", "tous", "être", "avoir", "faire",
        }
        keywords = [
            feature_names[i] for i in top_indices
            if feature_names[i] not in stopwords
        ]
        return keywords[:top_n]

    except Exception:
        return []


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Phase 8 : Audit de couverture — sujets manquants de la taxonomie"
    )
    parser.add_argument("--config", default=None)
    parser.add_argument(
        "--threshold", type=float, default=0.45,
        help="Seuil de similarité pour considérer un article orphelin (défaut: 0.45)",
    )
    parser.add_argument(
        "--min-cluster-size", type=int, default=5,
        help="Taille min d'un cluster (défaut: 5)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Afficher les détails de chargement",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    taxonomy = load_taxonomy(cfg.paths.taxonomy_file)

    log.info(f"Taxonomie : {taxonomy.item_count()}")

    # Init ChromaDB (for embedding function only)
    chroma = ChromaManager(
        db_path=cfg.paths.chroma_db_path,
        model_name=cfg.embeddings.model_name,
        collection_name=cfg.retrieval.collection_name,
    )

    embed_fn = chroma.embed_fn

    # Step 1: Embed taxonomy
    log.info("Embedding des items de la taxonomie...")
    tax_embeddings, tax_items = embed_taxonomy_items(taxonomy, embed_fn)
    log.info(f"  {len(tax_items)} items embarqués")

    # Step 2: Load corpus articles
    log.info("Chargement des articles source...")
    source_dirs = {
        "dgccrf": cfg.paths.dgccrf_corpus_dir,
        "inc": cfg.paths.inc_corpus_dir,
        "particuliers": cfg.paths.particuliers_corpus_dir,
        "entreprises": cfg.paths.entreprises_corpus_dir,
    }
    articles = load_corpus_articles(source_dirs, verbose=args.verbose)
    log.info(f"  {len(articles)} articles chargés")

    # Step 3: Filter noise
    log.info("Filtrage des articles hors-sujet...")
    filtered = [a for a in articles if not is_out_of_scope(a["title"], a["snippet"])]
    noise_count = len(articles) - len(filtered)
    log.info(f"  {noise_count} articles hors-sujet filtrés, {len(filtered)} restants")
    articles = filtered

    # Step 4: Embed articles
    log.info("Embedding des articles...")
    article_embeddings = embed_articles(articles, embed_fn)
    log.info(f"  {len(articles)} articles embarqués")

    # Step 5: Find orphans
    log.info(f"Recherche des orphelins (seuil: {args.threshold})...")
    orphans = find_orphans(
        article_embeddings, tax_embeddings,
        articles, tax_items,
        threshold=args.threshold,
    )
    log.info(f"  {len(orphans)} articles orphelins identifiés")

    if not orphans:
        log.info("Aucun orphelin trouvé — la taxonomie couvre bien le corpus.")
        report = {
            "generated_at": datetime.now().isoformat(),
            "parameters": {
                "threshold": args.threshold,
                "min_cluster_size": args.min_cluster_size,
            },
            "summary": {
                "total_articles": len(articles) + noise_count,
                "noise_filtered": noise_count,
                "substantive_articles": len(articles),
                "orphans_found": 0,
                "clusters_found": 0,
            },
            "clusters": [],
        }
    else:
        # Step 6: Embed orphans (reuse from article embeddings)
        orphan_indices = []
        for orphan in orphans:
            for i, article in enumerate(articles):
                if article["path"] == orphan["path"]:
                    orphan_indices.append(i)
                    break
        orphan_embeddings = article_embeddings[orphan_indices]

        # Step 7: Cluster
        log.info(f"Clustering des {len(orphans)} orphelins...")
        clusters = cluster_orphans(orphans, orphan_embeddings, args.min_cluster_size)
        log.info(f"  {len(clusters)} clusters identifiés")

        # Step 8: Analyze
        log.info("Analyse des clusters...")
        analysis = analyze_clusters(clusters, orphans, tax_embeddings, tax_items)

        # Build report
        unclustered = len(orphans) - sum(c["size"] for c in clusters)
        report = {
            "generated_at": datetime.now().isoformat(),
            "parameters": {
                "threshold": args.threshold,
                "min_cluster_size": args.min_cluster_size,
            },
            "summary": {
                "total_articles": len(articles) + noise_count,
                "noise_filtered": noise_count,
                "substantive_articles": len(articles),
                "orphans_found": len(orphans),
                "clusters_found": len(analysis),
                "unclustered_noise": unclustered,
            },
            "source_distribution": dict(Counter(o["source"] for o in orphans)),
            "clusters": analysis,
        }

    # Write report
    output_path = cfg.paths.output_dir / "_audit_coverage.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Console summary
    print(f"\n{'='*60}")
    print(f"Audit de couverture")
    print(f"{'='*60}")
    summary = report["summary"]
    print(f"Articles total : {summary['total_articles']}")
    print(f"  Bruit filtré : {summary['noise_filtered']}")
    print(f"  Substantifs  : {summary['substantive_articles']}")
    print(f"  Orphelins    : {summary['orphans_found']}")
    print(f"  Clusters     : {summary['clusters_found']}")
    print(f"  Non-clusterisés : {summary.get('unclustered_noise', 0)}")

    if report["clusters"]:
        print(f"\nTop 10 clusters par priorité :")
        for c in report["clusters"][:10]:
            print(
                f"  [{c['priority_score']:.1f}] {c['description'][:60]} "
                f"({c['size']} articles, "
                f"proche de: {c['nearest_taxonomy_item']['label'][:40]})"
            )

    print(f"\nRapport : {output_path}")


if __name__ == "__main__":
    main()
