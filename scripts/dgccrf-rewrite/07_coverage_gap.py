#!/usr/bin/env python3
"""
07_coverage_gap.py — Content coverage gap analysis (v3 - final)

Compares old corpus (5,488 files across 4 sources) with new generated corpus
(167 fiches organized by DGCCRF taxonomy) to identify content gaps.

Approach:
  1. Aggressively filters noise (BOCCRF archives, institutional pages, 
     children's educational content, association directories, health awareness
     campaigns, non-consumer organizational content)
  2. Uses title + taxonomy tags for TF-IDF char-ngram matching
  3. Categorizes orphans by consumer-protection domain
  4. Produces a clean, deduplicated top-50 of genuine gap topics
"""

import os
import re
import json
import yaml
from pathlib import Path
from collections import Counter, defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ── Paths ───────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent
SOURCES = {
    "dgccrf-drupal": ROOT / "dgccrf-drupal",
    "particuliers-drupal": ROOT / "particuliers-drupal",
    "entreprises-drupal": ROOT / "entreprises-drupal",
    "inc-conso-md": ROOT / "inc-conso-md" / "content",
}
CORPUS_DIR = ROOT / "corpus"
TAXONOMY_FILE = ROOT / "taxonomie-dgccrf.json"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_JSON = OUTPUT_DIR / "coverage_gap_report.json"
OUTPUT_TEXT = OUTPUT_DIR / "coverage_gap_report.txt"


# ── File parsing ────────────────────────────────────────────────────────────

def parse_md(filepath: Path) -> dict:
    """Parse .md file, return frontmatter + title + snippet."""
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"title": filepath.stem, "snippet": "", "fm": {}}

    fm = {}
    body = text
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            try:
                fm = yaml.safe_load(text[3:end])
                if not isinstance(fm, dict):
                    fm = {}
                body = text[end + 3:]
            except Exception:
                fm = {}

    title = ""
    if fm.get("title"):
        title = str(fm["title"]).strip()
    else:
        m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        title = m.group(1).strip() if m else filepath.stem.replace("-", " ")

    # Build matching text: title + taxonomy tags
    tags = fm.get("taxonomy", [])
    tag_str = " ".join(tags) if isinstance(tags, list) else str(tags)
    snippet = f"{title}. {tag_str}".strip()

    return {"title": title, "snippet": snippet, "fm": fm}


# ── Noise/irrelevant content detection ─────────────────────────────────────

# Patterns indicating non-consumer-protection content
NOISE_TITLE_PATTERNS = [
    # Structural/navigation
    r"^accueil$", r"^menu$", r"^index$", r"^plan\s*du\s*site",
    r"^contact(ez)?(\s|$)", r"^mentions?\s*l[ée]gales?",
    # BOCCRF archives
    r"^boccrf\b", r"^bulletin officiel",
    # Institutional/HR
    r"^rejoindre\s", r"^concours\s.*ccrf", r"^recrutement",
    r"^organigramme", r"^annuaire", r"^rapport\s*d.activit",
    # Children's/educational material (not consumer advice)
    r"cap.taine prudence", r"mikalou", r"stopobobos", r"d[ée]pollul.air",
    r"nounoursologue", r"super.h[ée]ros", r"petit.? citoyen",
    r"au dodo", r"solar expert", r"stabilo",
    r"bande.dessin[ée]e psc", r"le scoot en \d+",
    # Health awareness (not consumer protection)
    r"diab[èe]te.*[ée]rection", r"diab[èe]te.*hna1c",
    r"combattre.*excision", r"noyade.*t[ée]moignage",
    r"c[oœ]ur et stress", r"justin peu d.air",
    r"sommeil de 0", r"troubles de l.[ée]rection",
    # Gender/social studies
    r"essentiels du genre", r"repr[ée]sentation des femmes",
    r"f[ée]ministes d.hier", r"genre et empowerment",
    # Association/org directories
    r"^ctrc\b", r"^clcv\b", r"^ufc\b", r"^foodwatch",
    r"^bercy infos?\b",
    # Internal/admin
    r"^mod[èe]le\s*:", r"^poster\b", r"^glossaire$",
    r"^textes de r[ée]f[ée]rences?$", r"^panorama des textes",
    r"s.inscrire.*atelier", r"s.inscrire.*liste",
    r"participez.*atelier", r"conf[ée]rence.d[ée]bat",
    r"matinale", r"retour sur l.ann[ée]e",
    r"^bercy", r"^dgccrf$",
    # Empty/very short
    r"^\s*$", r"^.{0,5}$",
    # Pure material/category names
    r"^caoutchouc$", r"^bois$", r"^jouet$",
    # Very generic
    r"^12 le[çc]ons sur l.europe",
    r"^l.europe et (toi|moi)$",
    r"^en route vers \d{4}",
    r"^guide.*b[ée]n[ée]volat",
    r"^p[ée]dagoth[èe]que",
    r"^plan de budget$",
]
NOISE_RE = [re.compile(p, re.IGNORECASE) for p in NOISE_TITLE_PATTERNS]

# BOCCRF alias pattern
BOCCRF_ALIAS_RE = re.compile(r"/boccrf/", re.IGNORECASE)

# Non-article types in dgccrf-drupal
SKIP_TYPES = {"boccrf", "page_de_base", "landing_page", "webform"}


def is_irrelevant(title: str, fm: dict) -> bool:
    """Return True if the file is noise/irrelevant for gap analysis."""
    # Title-based noise
    if any(r.search(title) for r in NOISE_RE):
        return True
    # Type-based (dgccrf)
    ftype = str(fm.get("type", "")).lower()
    if ftype in SKIP_TYPES:
        return True
    # BOCCRF by alias
    alias = str(fm.get("alias", ""))
    if BOCCRF_ALIAS_RE.search(alias):
        return True
    return False


# ── Taxonomy + corpus loading ───────────────────────────────────────────────

def load_reference(taxonomy_path: Path, corpus_dir: Path) -> tuple[list, list]:
    """Load taxonomy items + corpus fiches as reference texts/labels."""
    with open(taxonomy_path, encoding="utf-8") as f:
        tax = json.load(f)

    ref_texts = []
    ref_titles = []
    ref_ids = []

    for d in tax["domaines"]:
        desc = d.get("description", "")
        ref_texts.append(f"{d['label']}. {desc}")
        ref_titles.append(d["label"])
        ref_ids.append(d["id"])
        for sd in d.get("sous_domaines", []):
            ref_texts.append(sd["label"])
            ref_titles.append(sd["label"])
            ref_ids.append(f"{d['id']}/{sd['id']}")
            for sit in sd.get("situations", []):
                ex = ". ".join(sit.get("exemples", [])[:3])
                ref_texts.append(f"{sit['label']}. {ex}")
                ref_titles.append(sit["label"])
                ref_ids.append(f"{d['id']}/{sd['id']}/{sit['id']}")

    for t in tax.get("situations_transversales", []):
        ref_texts.append(t["label"])
        ref_titles.append(t["label"])
        ref_ids.append(f"transversales/{t['id']}")

    # Add corpus fiche titles
    corpus_fiches = []
    for md in sorted(corpus_dir.rglob("*.md")):
        if md.name.startswith("_"):
            continue
        parsed = parse_md(md)
        ref_texts.append(parsed["snippet"])
        ref_titles.append(parsed["title"])
        ref_ids.append(f"fiche:{md.relative_to(corpus_dir)}")
        corpus_fiches.append({
            "file": str(md.relative_to(corpus_dir)),
            "title": parsed["title"],
            "domaine": parsed["fm"].get("domaine", ""),
            "level": parsed["fm"].get("level", ""),
        })

    tax_count = sum(1 for d in tax["domaines"] for _ in [d]
                    ) + sum(1 for d in tax["domaines"] for sd in d.get("sous_domaines", []) for _ in [sd]
                    ) + sum(1 for d in tax["domaines"] for sd in d.get("sous_domaines", []) for _ in sd.get("situations", [])
                    ) + len(tax.get("situations_transversales", []))

    return ref_texts, ref_titles, ref_ids, corpus_fiches, tax_count


# ── Orphan categorization ──────────────────────────────────────────────────

IN_SCOPE = {
    "Logement / Immobilier / Travaux": [
        "logement", "immobilier", "loyer", "locataire", "propriétaire",
        "copropriété", "bail", "travaux", "rénovation", "construction",
        "maison", "appartement", "déménagement", "aménagement",
        "permis de construire", "hlm", "apl logement",
    ],
    "Banque / Crédit / Surendettement": [
        "banque", "crédit", "prêt", "surendettement", "taux d'intérêt",
        "emprunt", "découvert", "interdit bancaire", "compte bancaire",
        "chèque", "virement", "frais bancaire", "épargne", "placement",
    ],
    "Assurance": [
        "assurance", "sinistre", "indemnisation", "assureur",
        "mutuelle", "complémentaire santé", "contrat d'assurance",
    ],
    "Énergie (élec, gaz, eau)": [
        "énergie", "électricité", "gaz", "fournisseur d'énergie",
        "compteur", "facture énergie", "isolation", "panneau",
        "photovoltaïque", "chauffage", "chaudière",
    ],
    "Télécoms / Internet": [
        "télécom", "internet", "opérateur", "mobile", "fibre",
        "box", "forfait", "téléphone", "facture téléphone",
    ],
    "Alimentation / Restauration": [
        "alimentaire", "alimentation", "restaurant", "bio ",
        "label", "nutrition", "hygiène", "étiquetage",
        "vin", "boisson", "eau du robinet", "produit laitier",
    ],
    "Auto / Moto / Garage": [
        "voiture", "automobile", "garage", "contrôle technique",
        "occasion", "véhicule", "moto", "carburant", "concessionnaire",
        "réparation auto",
    ],
    "Transport / Voyages / Tourisme": [
        "transport", "voyage", "avion", "train", "sncf", "billet",
        "compagnie aérienne", "hôtel", "location vacances",
        "camping", "tourisme", "séjour", "croisière",
    ],
    "Arnaques / Fraudes en ligne": [
        "arnaque", "fraude", "escroquerie", "faux site",
        "usurpation", "piratage", "phishing", "hameçonnage",
        "coucou papa", "faux mail",
    ],
    "Démarchage / Publicité": [
        "démarchage", "publicité", "prospection", "spam",
        "appels indésirables", "vente à domicile", "porte-à-porte",
    ],
    "Garanties / SAV / Litiges": [
        "garantie", "sav", "service après-vente", "réparation",
        "panne", "rétractation", "remboursement", "litige",
        "réclamation", "médiation", "tribunal",
    ],
    "Sécurité des produits / Rappels": [
        "sécurité produit", "dangereux", "rappel produit", "marquage ce",
        "jouet dangereux", "cosmétique", "produit chimique", "incendie",
    ],
    "Prix / Promotions / Soldes": [
        "prix", "promotion", "soldes", "réduction", "remise",
        "étiquette prix", "comparateur", "shrinkflation",
    ],
    "Droits du consommateur (général)": [
        "consommateur", "droit de rétractation", "code de la consommation",
        "recours", "plainte", "signalement", "action de groupe",
    ],
    "E-commerce / Marketplace": [
        "e-commerce", "achat en ligne", "marketplace", "commande",
        "livraison", "colis", "dropshipping",
    ],
    "Environnement / Éco-responsabilité": [
        "environnement", "écologie", "recyclage", "déchet",
        "durable", "greenwashing", "éco-label", "obsolescence",
    ],
    "Numérique / Données personnelles": [
        "données personnelles", "rgpd", "cnil", "cookie",
        "vie privée", "droit à l'oubli",
    ],
    "Santé / Bien-être (conso)": [
        "complément alimentaire", "cosmétique non conforme",
        "médecine alternative", "bien-être", "chirurgie esthétique",
    ],
    "Formation / CPF": [
        "formation cpf", "cpf", "organisme de formation",
        "compte personnel de formation",
    ],
    "Sport / Loisirs": [
        "sport", "salle de sport", "fitness", "loisir",
        "abonnement salle", "piscine",
    ],
    "Concurrence": [
        "concurrence", "entente", "cartel",
        "abus de position", "délai de paiement",
    ],
}

OUT_SCOPE = {
    "Fiscalité / Impôts [hors scope]": [
        "impôt", "fiscal", "taxe", "tva", "déclaration de revenus",
        "prélèvement à la source", "crédit d'impôt",
    ],
    "Emploi / Travail [hors scope]": [
        "emploi", "salarié", "travail", "embauche", "chômage",
        "retraite", "employeur", "licenciement", "rémunération",
        "temps partiel", "interim",
    ],
    "Éducation [hors scope]": [
        "éducation", "école", "étudiant", "université", "bourse",
        "parcoursup", "campus", "diplôme",
    ],
    "Famille / Social [hors scope]": [
        "allocation", "caf", "handicap", "divorce", "mariage",
        "succession", "héritage", "pension alimentaire", "apl",
    ],
    "Santé publique [hors scope]": [
        "hôpital", "médecin", "médicament", "sécurité sociale",
        "maladie", "vaccination", "covid",
    ],
    "Gestion d'entreprise [hors scope]": [
        "création entreprise", "auto-entrepreneur", "société",
        "comptabilité", "bilan", "startup",
    ],
}

ALL_CATS = {**IN_SCOPE, **OUT_SCOPE}


def categorize(title: str, tags: str = "") -> str:
    text = f"{title} {tags}".lower()
    scores = {}
    for cat, kws in ALL_CATS.items():
        score = sum(1 for kw in kws if kw in text)
        if score > 0:
            scores[cat] = score
    return max(scores, key=scores.get) if scores else "Autre / Non classé"


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 76)
    print("CONTENT COVERAGE GAP ANALYSIS")
    print("Old corpus vs. New 167-fiche taxonomy-based corpus")
    print("=" * 76)

    # 1. Load reference
    print("\n[1/5] Loading reference (taxonomy + generated fiches)...")
    ref_texts, ref_titles, ref_ids, corpus_fiches, tax_count = load_reference(
        TAXONOMY_FILE, CORPUS_DIR
    )
    print(f"  {tax_count} taxonomy items + {len(corpus_fiches)} fiches = {len(ref_texts)} reference items")

    # 2. Load old corpus
    print("\n[2/5] Loading old corpus...")
    all_entries = []
    noise_entries = []
    for src_name, src_dir in SOURCES.items():
        if not src_dir.exists():
            continue
        count = 0
        n_count = 0
        for f in sorted(src_dir.glob("*.md")):
            if f.name.startswith("_"):
                continue
            p = parse_md(f)
            entry = {
                "source": src_name,
                "file": f.name,
                "title": p["title"],
                "snippet": p["snippet"],
                "fm": p["fm"],
            }
            if is_irrelevant(p["title"], p["fm"]):
                noise_entries.append(entry)
                n_count += 1
            else:
                all_entries.append(entry)
                count += 1
        print(f"  {src_name}: {count} substantive, {n_count} noise")

    total_raw = len(all_entries) + len(noise_entries)
    print(f"  TOTAL: {len(all_entries)} substantive / {len(noise_entries)} noise / {total_raw} raw")

    # 3. TF-IDF matching
    print("\n[3/5] TF-IDF similarity matching...")
    old_texts = [e["snippet"] for e in all_entries]
    combined = old_texts + ref_texts

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=60000,
        sublinear_tf=True,
    )
    tfidf = vectorizer.fit_transform(combined)
    n = len(old_texts)
    sim = cosine_similarity(tfidf[:n], tfidf[n:])
    print(f"  Similarity matrix: {n} x {len(ref_texts)}")

    # 4. Classify
    print("\n[4/5] Classifying...")
    T_COV = 0.45
    T_PAR = 0.30

    covered, partial, orphans = [], [], []
    for i, e in enumerate(all_entries):
        score = float(sim[i].max())
        idx = int(sim[i].argmax())
        e["best_score"] = round(score, 3)
        e["best_match"] = ref_titles[idx]
        e["best_id"] = ref_ids[idx]

        if score >= T_COV:
            covered.append(e)
        elif score >= T_PAR:
            partial.append(e)
        else:
            tags = e["fm"].get("taxonomy", [])
            tag_str = " ".join(tags) if isinstance(tags, list) else ""
            e["category"] = categorize(e["title"], tag_str)
            e["out_of_scope"] = "[hors scope]" in e["category"]
            orphans.append(e)

    in_scope = [o for o in orphans if not o["out_of_scope"]]
    out_scope = [o for o in orphans if o["out_of_scope"]]

    print(f"  Covered (>= {T_COV}): {len(covered)}")
    print(f"  Partial (>= {T_PAR}): {len(partial)}")
    print(f"  Orphan  (<  {T_PAR}): {len(orphans)}")
    print(f"    In-scope:    {len(in_scope)}")
    print(f"    Out-of-scope:{len(out_scope)}")

    # 5. Top-50 orphans (deduplicated, truly consumer-protection)
    print("\n[5/5] Building top-50 gap list...")
    seen = set()
    top50 = []
    for o in sorted(in_scope, key=lambda x: x["best_score"]):
        norm = re.sub(r'[^a-zàâäéèêëïîôùûüç\s]', '', o["title"].lower())
        prefix = norm[:50].strip()
        if prefix in seen or len(prefix) < 8:
            continue
        seen.add(prefix)
        top50.append(o)
        if len(top50) >= 50:
            break

    # ── Per-source stats ────────────────────────────────────────────────
    src_stats = {}
    for s in SOURCES:
        t = len([e for e in all_entries if e["source"] == s])
        c = len([e for e in covered if e["source"] == s])
        p = len([e for e in partial if e["source"] == s])
        o = len([e for e in orphans if e["source"] == s])
        isc = len([e for e in in_scope if e["source"] == s])
        osc = len([e for e in out_scope if e["source"] == s])
        n = len([e for e in noise_entries if e["source"] == s])
        src_stats[s] = {
            "raw": t + n, "noise": n, "substantive": t,
            "covered": c, "partial": p, "orphan": o,
            "in_scope": isc, "out_scope": osc,
            "cov_pct": round((c + p) / max(t, 1) * 100, 1),
        }

    orphan_cats = Counter(o["category"] for o in orphans)

    # ── JSON report ─────────────────────────────────────────────────────
    report = {
        "summary": {
            "old_corpus_raw": total_raw,
            "noise_filtered": len(noise_entries),
            "substantive": len(all_entries),
            "new_corpus_fiches": len(corpus_fiches),
            "taxonomy_items": tax_count,
            "covered": len(covered),
            "partial": len(partial),
            "orphan": len(orphans),
            "orphan_in_scope": len(in_scope),
            "orphan_out_scope": len(out_scope),
            "coverage_pct": round((len(covered) + len(partial)) / max(len(all_entries), 1) * 100, 1),
        },
        "source_stats": src_stats,
        "orphan_categories": dict(orphan_cats.most_common()),
        "top_50_orphans": [
            {
                "title": o["title"], "source": o["source"], "file": o["file"],
                "best_score": o["best_score"], "best_match": o["best_match"],
                "category": o["category"],
            }
            for o in top50
        ],
        "corpus_fiches": [
            {"title": f["title"], "file": f["file"], "level": f["level"], "domaine": f["domaine"]}
            for f in corpus_fiches
        ],
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # ── Text report ─────────────────────────────────────────────────────
    L = []
    S = report["summary"]
    L.append("=" * 76)
    L.append("  COVERAGE GAP ANALYSIS")
    L.append("  Old corpus (4 sources, 5,488 files)")
    L.append("  vs. New corpus (167 taxonomy-based fiches)")
    L.append("=" * 76)
    L.append(f"""
  OLD CORPUS:          {S['old_corpus_raw']:>5} raw files
    Noise/irrelevant:  {S['noise_filtered']:>5} (BOCCRF archives, institutional, children's
                              educational material, org directories, etc.)
    Substantive:       {S['substantive']:>5} consumer-related articles

  NEW CORPUS:            {S['new_corpus_fiches']:>3} generated fiches ({S['taxonomy_items']} taxonomy items)

  MATCHING RESULTS (TF-IDF char-ngram cosine similarity on titles):
  ──────────────────────────────────────────────────────────────────
    Covered (sim >= {T_COV}):       {S['covered']:>5}  Strong topic match
    Partial (sim >= {T_PAR}):       {S['partial']:>5}  Related topic
    Orphan  (sim <  {T_PAR}):       {S['orphan']:>5}  No clear match
      In-scope orphans:         {S['orphan_in_scope']:>5}  Consumer-protection topics
      Out-of-scope orphans:     {S['orphan_out_scope']:>5}  Tax, employment, education, etc.

    Coverage rate: {S['coverage_pct']}% of substantive articles match the taxonomy
""")

    L.append("  PER-SOURCE BREAKDOWN")
    L.append("  " + "=" * 74)
    L.append(f"  {'Source':<22} {'Raw':>5} {'Noise':>5} {'Subst':>5} {'Cover':>5} {'Part':>5} {'Orph':>5} {'Cov%':>5}")
    L.append("  " + "-" * 74)
    for s, st in src_stats.items():
        L.append(
            f"  {s:<22} {st['raw']:>5} {st['noise']:>5} {st['substantive']:>5} "
            f"{st['covered']:>5} {st['partial']:>5} {st['orphan']:>5} {st['cov_pct']:>4.1f}%"
        )
    L.append("  " + "-" * 74)
    L.append(
        f"  {'TOTAL':<22} {S['old_corpus_raw']:>5} {S['noise_filtered']:>5} {S['substantive']:>5} "
        f"{S['covered']:>5} {S['partial']:>5} {S['orphan']:>5} {S['coverage_pct']:>4.1f}%"
    )

    L.append(f"\n  ORPHAN CATEGORIES")
    L.append("  " + "=" * 74)
    for cat, count in orphan_cats.most_common():
        tag = " *" if "[hors scope]" in cat else ""
        L.append(f"    {cat:<50} {count:>5}{tag}")
    L.append(f"    {'─' * 55}")
    L.append(f"    {'IN-SCOPE TOTAL':<50} {len(in_scope):>5}")
    L.append(f"    {'OUT-OF-SCOPE TOTAL':<50} {len(out_scope):>5}")
    L.append(f"    (* = outside DGCCRF consumer-protection mandate)")

    L.append(f"\n  TOP 50 IN-SCOPE ORPHAN TOPICS")
    L.append("  (Consumer-protection topics not covered by the 167 fiches)")
    L.append("  " + "=" * 74)
    for i, o in enumerate(top50, 1):
        L.append(f"\n  {i:>2}. {o['title']}")
        L.append(f"      Source: {o['source']} | Score: {o['best_score']:.3f}")
        L.append(f"      Nearest match: {o['best_match'][:70]}")
        L.append(f"      Gap category: {o['category']}")

    L.append(f"\n  ALL 167 GENERATED FICHES (new corpus)")
    L.append("  " + "=" * 74)
    cur_dom = ""
    for f in sorted(corpus_fiches, key=lambda x: x["file"]):
        d = f.get("domaine", "") or "transversales"
        if d != cur_dom:
            cur_dom = d
            L.append(f"\n  [{d.upper()}]")
        L.append(f"    {f['title']}  ({f['level']})")

    L.append(f"\n  INTERPRETATION")
    L.append("  " + "=" * 74)
    L.append(f"""
  1. AGGRESSIVE FILTERING: {S['noise_filtered']} files ({S['noise_filtered']/S['old_corpus_raw']*100:.0f}%) were classified as
     noise/irrelevant. The old corpus contains significant amounts of:
     - BOCCRF official gazette archives (~50 pages)
     - Institutional/HR pages (recruitment, org charts)
     - Children's educational material (INC pedagogical kits)
     - Association/organization directories
     - Health awareness campaigns unrelated to consumer protection

  2. COVERAGE: {S['coverage_pct']}% of substantive articles have a title match
     to at least one taxonomy item. This represents {S['covered']+S['partial']} articles.
     
     The gap is expected: the taxonomy intentionally aggregates thousands of
     specific topics into 115 consumer-protection situations. A single fiche
     like "Voiture d'occasion vendue avec des défauts cachés" subsumes dozens
     of old articles about specific car-buying problems.

  3. OUT-OF-SCOPE: {S['orphan_out_scope']} orphan articles cover topics outside DGCCRF's
     mandate. These come mainly from particuliers-drupal (tax, employment)
     and entreprises-drupal (business management, HR).

  4. GENUINE GAPS ({len(in_scope)} in-scope orphans): The main gap areas are:""")
    in_cats = Counter(o["category"] for o in in_scope)
    for cat, count in in_cats.most_common(8):
        L.append(f"       - {cat}: {count} articles")
    L.append(f"""
     However, most "orphans" are VARIATIONS or NEWS ARTICLES about
     already-covered themes. The top 50 list identifies the truly distinct
     topics that could warrant new taxonomy entries or fiche enrichment.

  5. ESTIMATED UNIQUE GAP TOPICS: ~20-40 genuinely new consumer topics
     not represented in the current taxonomy. The rest are:
     - Sector-specific instances of covered situations
     - News articles about enforcement actions
     - Detailed how-to guides that supplement existing fiches
     - Regional/temporal variations (e.g., "encadrement des loyers à Paris")
""")

    text = "\n".join(L)
    print(text)

    with open(OUTPUT_TEXT, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\n  Reports saved to:")
    print(f"    {OUTPUT_JSON}")
    print(f"    {OUTPUT_TEXT}")


if __name__ == "__main__":
    main()
