#!/usr/bin/env python3
"""Build corpus/index.json from corpus .md files + taxonomie-dgccrf.json labels."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "corpus"
TAXONOMY_FILE = ROOT / "taxonomie-dgccrf.json"
OUTPUT_FILE = CORPUS_DIR / "index.json"


def load_taxonomy_labels(path: Path) -> dict:
    """Build lookup dicts: domaine_id->label, sous_domaine_id->label."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    dom_labels = {}
    ss_labels = {}
    for dom in data.get("domaines", []):
        dom_labels[dom["id"]] = dom["label"]
        for ss in dom.get("sous_domaines", []):
            ss_labels[ss["id"]] = ss["label"]
    return dom_labels, ss_labels


def parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter via PyYAML."""
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    return yaml.safe_load(m.group(1)) or {}


def build_index():
    dom_labels, ss_labels = load_taxonomy_labels(TAXONOMY_FILE)

    # Collect fiches grouped by domaine / sous_domaine
    tree = {}  # dom_id -> { ss_id -> [fiche, ...] }

    for md_path in sorted(CORPUS_DIR.rglob("*.md")):
        rel = md_path.relative_to(CORPUS_DIR)
        parts = rel.parts  # e.g. ('pratiques_commerciales', 'publicite_trompeuse', 'pub_prix.md')
        if len(parts) != 3:
            continue

        dom_id, ss_id, filename = parts
        text = md_path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if not fm.get("title"):
            continue

        fiche = {
            "taxonomy_id": fm.get("taxonomy_id", filename.removesuffix(".md")),
            "title": fm["title"],
            "path": str(rel),
        }

        tree.setdefault(dom_id, {}).setdefault(ss_id, []).append(fiche)

    # Build output structure with labels
    domaines = []
    for dom_id in sorted(tree.keys()):
        ss_list = []
        for ss_id in sorted(tree[dom_id].keys()):
            fiches = sorted(tree[dom_id][ss_id], key=lambda f: f["title"])
            ss_list.append({
                "id": ss_id,
                "label": ss_labels.get(ss_id, ss_id.replace("_", " ").title()),
                "fiches": fiches,
            })
        domaines.append({
            "id": dom_id,
            "label": dom_labels.get(dom_id, dom_id.replace("_", " ").title()),
            "sous_domaines": ss_list,
        })

    index = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domaines": domaines,
    }

    OUTPUT_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(len(f) for d in domaines for s in d["sous_domaines"] for f in [s["fiches"]])
    print(f"corpus/index.json: {len(domaines)} domaines, {total} fiches")


if __name__ == "__main__":
    build_index()
