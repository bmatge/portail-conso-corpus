#!/usr/bin/env python3
"""Phase 7 : Réécriture enrichie des fiches avec modèle amélioré, maillage et faux amis."""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

import frontmatter as fm
from tqdm import tqdm

from lib.chroma_utils import ChromaManager
from lib.config import load_config
from lib.llm_client import LLMClient
from lib.prompt_builder import PromptBuilder
from lib.similarity import TaxonomySimilarity
from lib.taxonomy import Domaine, Situation, SousDomaine, load_taxonomy

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────


def get_output_path(item, level: str, taxonomy, fiches_dir: Path) -> Path:
    """Determine the output path for a fiche (same logic as 05_generate)."""
    if level == "domaine":
        return fiches_dir / item.id / "_index.md"
    elif level == "sous_domaine":
        domaine = taxonomy.get_domaine_for(item)
        d_id = domaine.id if domaine else "unknown"
        return fiches_dir / d_id / item.id / "_index.md"
    else:
        if item.is_transversale:
            return fiches_dir / "transversales" / f"{item.id}.md"
        sd = taxonomy.get_sous_domaine_for(item)
        domaine = taxonomy.get_domaine_for(item)
        d_id = domaine.id if domaine else "unknown"
        sd_id = sd.id if sd else "unknown"
        return fiches_dir / d_id / sd_id / f"{item.id}.md"


def load_validation_report(report_path: Path) -> dict[str, dict]:
    """Load validation report indexed by item_id."""
    if not report_path.exists():
        log.warning(f"Validation report not found: {report_path}")
        return {}
    with open(report_path) as f:
        data = json.load(f)
    return {fiche["id"]: fiche for fiche in data.get("fiches", [])}


def get_validation_errors(item_id: str, report: dict) -> list[dict]:
    """Extract failed checks for a specific item."""
    fiche = report.get(item_id, {})
    return [c for c in fiche.get("checks", []) if not c.get("passed")]


def read_existing_fiche(path: Path) -> tuple[dict, str]:
    """Read existing fiche, return (frontmatter_meta, body)."""
    if not path.exists():
        return {}, ""
    post = fm.load(path)
    return dict(post.metadata), post.content


def word_count(text: str) -> int:
    """Count words in text."""
    return len(text.split())


# ── Multi-query ────────────────────────────────────────────────────────────


def build_multi_queries(item, level: str, taxonomy) -> dict[str, str]:
    """Build section-targeted queries for richer context retrieval."""
    queries = {}

    if level == "situation":
        base = item.label
        sd = taxonomy.get_sous_domaine_for(item)
        sd_label = sd.label if sd else ""
        exemples = " ".join(item.exemples[:3]) if item.exemples else ""

        queries["general"] = f"{base}. {exemples}. {sd_label}"
        queries["droits"] = (
            f"droits du consommateur {base} {sd_label} "
            f"obligations professionnel délais recours loi"
        )
        queries["procedures"] = (
            f"que faire {base} étapes démarches procédure signalement "
            f"réclamation {sd_label}"
        )
        queries["exemples"] = (
            f"{base} {exemples} cas concret exemple situation réelle "
            f"jurisprudence"
        )

    elif level == "sous_domaine":
        child_labels = " ".join(s.label for s in item.situations[:5])
        domaine = taxonomy.get_domaine_for(item)
        d_label = domaine.label if domaine else ""

        queries["general"] = f"{item.label}. {d_label}. {child_labels}"
        queries["droits"] = (
            f"droits consommateur {item.label} {d_label} "
            f"obligations délais réglementation"
        )
        queries["procedures"] = (
            f"démarches procédure {item.label} signalement médiation "
            f"recours"
        )

    elif level == "domaine":
        queries["general"] = f"{item.label}. {item.description}"
        queries["droits"] = (
            f"droits consommateur {item.label} principes essentiels "
            f"réglementation"
        )

    return queries


# ── Prompt assembly ────────────────────────────────────────────────────────


def format_validation_errors(errors: list[dict], existing_wc: int) -> str:
    """Format validation failures as actionable correction instructions."""
    if not errors:
        return "Aucun problème identifié. Enrichis néanmoins le contenu."

    lines = []
    for err in errors:
        check = err.get("check", "")
        detail = err.get("detail", "")

        if check == "min_length":
            lines.append(
                f"- **LONGUEUR INSUFFISANTE** : la fiche fait {existing_wc} mots, "
                f"le minimum est indiqué dans le système. Développe chaque section "
                f"en profondeur."
            )
        elif check == "urls_integrated":
            lines.append(
                f"- **URLs MANQUANTES** : {detail}. Intègre TOUTES les URLs "
                f"de sortie dans la section 'Où signaler'."
            )
        elif check == "signalconso_url":
            lines.append(
                f"- **URL SIGNALCONSO MANQUANTE** : intègre l'URL de signalement "
                f"direct SignalConso dans 'Où signaler'."
            )
        elif check == "mediateur_mentioned":
            lines.append(
                f"- **MÉDIATEUR MANQUANT** : mentionne le médiateur sectoriel "
                f"avec son URL dans 'Où signaler'."
            )
        elif check == "a_completer_count":
            lines.append(
                f"- **PLACEHOLDERS** : {detail}. Remplace les `[À COMPLÉTER]` "
                f"par du contenu réel issu des sources."
            )
        elif check == "sections_present":
            lines.append(
                f"- **SECTIONS MANQUANTES** : {detail}. Ajoute les sections manquantes."
            )
        elif check == "child_links":
            lines.append(
                f"- **LIENS ENFANTS MANQUANTS** : {detail}. Ajoute les liens "
                f"vers toutes les fiches enfants."
            )
        else:
            lines.append(f"- **{check.upper()}** : {detail}")

    return "\n".join(lines)


def format_sujets_proches(
    sujets: list[dict], similarity: TaxonomySimilarity, from_item_id: str
) -> str:
    """Format related topics with relative paths for prompt injection."""
    if not sujets:
        return "Aucun sujet proche identifié."

    lines = []
    for s in sujets:
        rel_path = similarity.get_relative_path(from_item_id, s["id"])
        lines.append(
            f"- **{s['label']}** (id: `{s['id']}`, {s['level']}) "
            f"— chemin : `{rel_path}` (similarité : {s['score']})"
        )
    return "\n".join(lines)


def format_faux_amis(
    faux_amis: list[dict], similarity: TaxonomySimilarity, from_item_id: str
) -> str:
    """Format look-alike situations with differentiation hints."""
    if not faux_amis:
        return "Aucun faux ami identifié."

    lines = []
    for fa in faux_amis:
        rel_path = similarity.get_relative_path(from_item_id, fa["id"])
        sorties_info = ", ".join(fa.get("sorties_diff", [])) or "recours similaires"
        lines.append(
            f"- **{fa['label']}** (id: `{fa['id']}`) "
            f"— chemin : `{rel_path}` (similarité : {fa['score']}). "
            f"Différences de recours : {sorties_info}"
        )
    return "\n".join(lines)


def build_rewrite_prompt(
    item,
    level: str,
    taxonomy,
    existing_body: str,
    validation_errors: list[dict],
    sujets_proches: list[dict],
    faux_amis: list[dict],
    dgccrf_sources: list[dict],
    other_sources: list[dict],
    similarity: TaxonomySimilarity,
    prompts_dir: Path,
    prompt_builder: PromptBuilder,
) -> tuple[str, str]:
    """Build the full rewrite prompt (system + user)."""

    # System prompt
    system_prompt = (prompts_dir / "rewrite_system.md").read_text()

    # Level-specific template
    template_map = {
        "situation": "rewrite_situation.md",
        "sous_domaine": "rewrite_sous_domaine.md",
        "domaine": "rewrite_domaine.md",
    }
    template = (prompts_dir / template_map[level]).read_text()

    # Taxonomic context — reuse PromptBuilder's logic for context generation
    if level == "domaine":
        _, original_user = prompt_builder.build_domaine_prompt(
            item, dgccrf_sources, other_sources
        )
    elif level == "sous_domaine":
        domaine = taxonomy.get_domaine_for(item)
        _, original_user = prompt_builder.build_sous_domaine_prompt(
            item, domaine, dgccrf_sources, other_sources
        )
    else:
        sd = taxonomy.get_sous_domaine_for(item)
        domaine = taxonomy.get_domaine_for(item)
        _, original_user = prompt_builder.build_situation_prompt(
            item, sd, domaine, dgccrf_sources, other_sources
        )

    # Extract the taxonomic context section from the original prompt
    # (everything between the template and the sources)
    # For simplicity, we reuse the full original user prompt which has context+sources
    # and prepend our rewrite-specific sections

    # Checklist
    checklist = (prompts_dir / "rewrite_checklist.md").read_text()

    # Format rewrite-specific sections
    existing_wc = word_count(existing_body)
    errors_text = format_validation_errors(validation_errors, existing_wc)
    sujets_text = format_sujets_proches(sujets_proches, similarity, item.id)
    faux_amis_text = format_faux_amis(faux_amis, similarity, item.id)

    # Assemble user prompt
    user_prompt = f"""{template}

{original_user}

---

## Fiche actuelle à améliorer ({existing_wc} mots)

{existing_body}

---

## Problèmes identifiés à corriger

{errors_text}

---

## Sujets proches à intégrer dans la section "Sujets proches"

{sujets_text}

---

## Faux amis à intégrer dans la section "À ne pas confondre"

{faux_amis_text}

---

{checklist}"""

    return system_prompt, user_prompt


# ── Inline validation ──────────────────────────────────────────────────────


MIN_WORDS = {
    "situation": 1000,
    "sous_domaine": 1200,
    "domaine": 1000,
}

EXPECTED_SECTIONS = {
    "situation": [
        "en bref", "de quoi s'agit-il", "quels sont vos droits",
        "que faire concretement", "exemples", "ou signaler",
        "sujets proches", "a ne pas confondre", "pour aller plus loin",
    ],
    "sous_domaine": [
        "en bref", "de quoi s'agit-il", "quels sont vos droits",
        "les situations les plus frequentes", "que faire concretement",
        "ou signaler", "sujets proches", "a ne pas confondre",
        "pour aller plus loin",
    ],
    "domaine": [
        "en bref", "ce que couvre ce domaine", "vos droits essentiels",
        "que faire en cas de probleme", "les services a connaitre",
        "sujets proches", "a ne pas confondre", "pour aller plus loin",
    ],
}


def normalize_heading(text: str) -> str:
    """Normalize a heading for fuzzy matching."""
    import unicodedata
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9 ]", "", text)
    return text.strip()


def validate_rewrite_inline(body: str, level: str) -> list[str]:
    """Quick inline validation. Returns list of issues (empty = ok)."""
    issues = []

    # Word count
    wc = word_count(body)
    min_wc = MIN_WORDS.get(level, 800)
    if wc < min_wc:
        issues.append(f"Longueur insuffisante : {wc} mots (min {min_wc})")

    # Section presence
    h2_pattern = re.compile(r"^## (.+)$", re.MULTILINE)
    found_sections = [normalize_heading(m.group(1)) for m in h2_pattern.finditer(body)]
    expected = EXPECTED_SECTIONS.get(level, [])

    for expected_section in expected:
        if not any(expected_section in found for found in found_sections):
            issues.append(f"Section manquante : {expected_section}")

    return issues


# ── Rewrite logic ──────────────────────────────────────────────────────────


def max_tokens_for_level(level: str, cfg) -> int:
    """Get max tokens for a given level from rewrite config."""
    return {
        "domaine": cfg.rewrite.max_tokens_domaine,
        "sous_domaine": cfg.rewrite.max_tokens_sous_domaine,
        "situation": cfg.rewrite.max_tokens_situation,
    }.get(level, cfg.rewrite.max_tokens_situation)


def rewrite_one(
    item,
    level: str,
    taxonomy,
    chroma: ChromaManager,
    prompt_builder: PromptBuilder,
    llm: LLMClient,
    similarity: TaxonomySimilarity,
    validation_report: dict,
    cfg,
    fiches_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Rewrite a single fiche. Returns log entry."""
    item_id = item.id
    output_path = get_output_path(item, level, taxonomy, fiches_dir)

    # Read existing fiche
    existing_meta, existing_body = read_existing_fiche(output_path)
    previous_wc = word_count(existing_body)

    # Validation errors
    errors = get_validation_errors(item_id, validation_report)

    # Sujets proches & faux amis
    sujets_proches = similarity.get_sujets_proches(
        item_id,
        top_k=cfg.rewrite.sujets_proches_top_k,
        min_score=cfg.rewrite.sujets_proches_min_score,
    )
    faux_amis = similarity.get_faux_amis(
        item_id,
        top_k=cfg.rewrite.faux_amis_top_k,
        similarity_range=tuple(cfg.rewrite.faux_amis_similarity_range),
    )

    # Multi-query ChromaDB
    queries = build_multi_queries(item, level, taxonomy)
    dgccrf_sources, other_sources = chroma.multi_query(
        queries,
        top_k_per_query=cfg.rewrite.top_k_per_query,
        min_score=cfg.retrieval.min_score,
        boost_source="dgccrf",
        boost_factor=cfg.retrieval.dgccrf_weight,
        max_chars=cfg.rewrite.max_source_chars,
    )

    # Build prompt
    system_prompt, user_prompt = build_rewrite_prompt(
        item, level, taxonomy,
        existing_body, errors,
        sujets_proches, faux_amis,
        dgccrf_sources, other_sources,
        similarity,
        cfg.paths.prompts_dir, prompt_builder,
    )

    max_tokens = max_tokens_for_level(level, cfg)

    # Log entry
    log_entry = {
        "item_id": item_id,
        "level": level,
        "timestamp": datetime.now().isoformat(),
        "output_path": str(output_path),
        "previous_word_count": previous_wc,
        "sources_dgccrf": len(dgccrf_sources),
        "sources_other": len(other_sources),
        "sujets_proches_count": len(sujets_proches),
        "faux_amis_count": len(faux_amis),
        "validation_errors_count": len(errors),
        "status": "dry_run" if dry_run else "pending",
    }

    if dry_run:
        info = llm.chat_dry_run(system_prompt, user_prompt, max_tokens)
        log_entry["dry_run_info"] = info
        return log_entry

    # Call LLM
    try:
        response = llm.chat(system_prompt, user_prompt, max_tokens)
    except Exception as e:
        log_entry["status"] = "error"
        log_entry["error"] = str(e)
        log.error(f"Error rewriting {item_id}: {e}")
        return log_entry

    # Inline validation
    inline_issues = validate_rewrite_inline(response.content, level)
    new_wc = word_count(response.content)

    if inline_issues:
        log.warning(f"{item_id}: {len(inline_issues)} inline issue(s): {inline_issues}")

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
        "rewritten": True,
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
        "new_word_count": new_wc,
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
        "total_tokens": response.total_tokens,
        "duration_seconds": response.duration_seconds,
        "inline_issues": inline_issues,
        "sources_used": source_refs[:10],
    })

    return log_entry


# ── Main ───────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Phase 7 : Réécriture enrichie des fiches"
    )
    parser.add_argument("--config", default=None)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Prévisualiser les prompts sans appeler le LLM",
    )
    parser.add_argument("--situation", help="Réécrire une seule situation par ID")
    parser.add_argument("--sous-domaine", help="Réécrire un seul sous-domaine par ID")
    parser.add_argument("--domaine", help="Réécrire un seul domaine par ID")
    parser.add_argument(
        "--level", choices=["domaine", "sous_domaine", "situation"],
        help="Filtrer par niveau",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Sauter les fiches déjà réécrites (model contient le modèle de réécriture)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Écraser même les fiches déjà réécrites",
    )
    parser.add_argument(
        "--errors-only", action="store_true",
        help="Ne réécrire que les fiches en erreur dans le rapport de validation",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)

    # Check API key
    if not args.dry_run and not cfg.llm.api_key:
        print(
            "Erreur : LLM_API_KEY non défini. Exportez la variable d'environnement.",
            file=sys.stderr,
        )
        sys.exit(1)

    taxonomy = load_taxonomy(cfg.paths.taxonomy_file)
    fiches_dir = cfg.paths.fiches_dir
    log_path = cfg.paths.output_dir / "_rewrite_log.jsonl"

    log.info(f"Taxonomie : {taxonomy.item_count()}")
    log.info(f"Corpus : {fiches_dir}")
    log.info(f"Modèle réécriture : {cfg.rewrite.model}")

    # Load validation report
    report_path = cfg.paths.output_dir / "_validation_report.json"
    validation_report = load_validation_report(report_path)
    log.info(f"Rapport de validation : {len(validation_report)} fiches chargées")

    # Init ChromaDB
    chroma = ChromaManager(
        db_path=cfg.paths.chroma_db_path,
        model_name=cfg.embeddings.model_name,
        collection_name=cfg.retrieval.collection_name,
    )

    if chroma.count() == 0:
        print(
            "Erreur : la collection ChromaDB est vide. "
            "Lancez d'abord 03_index_chroma.py",
            file=sys.stderr,
        )
        sys.exit(1)

    # Init prompt builder (reuses original for taxonomic context generation)
    prompt_builder = PromptBuilder(cfg.paths.prompts_dir, taxonomy)

    # Init LLM client with rewrite model
    llm = LLMClient(
        endpoint=cfg.llm.endpoint,
        api_key=cfg.llm.api_key or "dry-run",
        model=cfg.rewrite.model,
        temperature=cfg.rewrite.temperature,
        timeout=cfg.rewrite.timeout,
        rate_limit_rpm=cfg.rewrite.rate_limit_rpm,
        retry_count=cfg.llm.retry_count,
        retry_delay=cfg.llm.retry_delay,
    )

    # Init similarity engine
    log.info("Calcul de la matrice de similarité taxonomique...")
    similarity = TaxonomySimilarity(taxonomy, chroma.embed_fn)
    log.info("Matrice prête.")

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

        # Bottom-up order: situations → sous-domaines → domaines
        order = {"situation": 0, "sous_domaine": 1, "domaine": 2}
        all_items.sort(key=lambda x: order.get(x[0], 99))
        items = [(l, o) for l, _, o in all_items]

    # Filter: errors-only
    if args.errors_only:
        error_ids = {
            fid for fid, fdata in validation_report.items()
            if fdata.get("status") in ("error", "warning")
        }
        items = [(l, o) for l, o in items if o.id in error_ids]
        log.info(f"Mode --errors-only : {len(items)} fiches en erreur à réécrire")

    # Filter: resume (skip already rewritten)
    if args.resume and not args.force:
        filtered = []
        skipped = 0
        for level, item in items:
            path = get_output_path(item, level, taxonomy, fiches_dir)
            if path.exists():
                try:
                    post = fm.load(path)
                    model = post.metadata.get("model", "")
                    if cfg.rewrite.model in model:
                        skipped += 1
                        continue
                except Exception:
                    pass
            filtered.append((level, item))
        items = filtered
        if skipped:
            log.info(f"Resume : {skipped} fiches déjà réécrites, ignorées")

    log.info(f"{len(items)} fiches à réécrire")

    # Rewrite loop
    fiches_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    stats = {"ok": 0, "error": 0, "dry_run": 0}
    total_tokens = 0

    with open(log_path, "a") as log_file:
        for level, item in tqdm(items, desc="Réécriture"):
            entry = rewrite_one(
                item, level, taxonomy, chroma, prompt_builder, llm,
                similarity, validation_report, cfg, fiches_dir,
                dry_run=args.dry_run,
            )

            log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            log_file.flush()

            status = entry.get("status", "error")
            stats[status] = stats.get(status, 0) + 1
            total_tokens += entry.get("total_tokens", 0)

            if args.dry_run and (args.situation or args.sous_domaine or args.domaine):
                info = entry.get("dry_run_info", {})
                print(f"\n{'='*60}")
                print(f"[DRY-RUN] {item.id} ({level})")
                print(f"Model: {info.get('model')}, Max tokens: {info.get('max_tokens')}")
                print(f"System prompt: {info.get('system_chars')} chars")
                print(f"User prompt: {info.get('user_chars')} chars")
                print(f"Estimated tokens: ~{info.get('estimated_tokens')}")
                print(f"Previous word count: {entry.get('previous_word_count', '?')}")
                print(f"Sujets proches: {entry.get('sujets_proches_count', 0)}")
                print(f"Faux amis: {entry.get('faux_amis_count', 0)}")
                print(f"Validation errors: {entry.get('validation_errors_count', 0)}")
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
