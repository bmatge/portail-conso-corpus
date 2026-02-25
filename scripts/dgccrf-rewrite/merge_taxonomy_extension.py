#!/usr/bin/env python3
"""
Merge taxonomy extension proposal into the existing taxonomie-dgccrf.json.

- Adds new type_sortie 'information'
- Adds 4 new domaines (logement, banque_finance, droits_consommateur, services_funeraires)
- Extends existing domaines with new sous_domaines and new situations
- Updates meta counts, version, date, description
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path("/Users/bertrand/Documents/GitHub/portail-conso-corpus")
TAXONOMY_PATH = BASE_DIR / "taxonomie-dgccrf.json"
EXTENSION_PATH = BASE_DIR / "scripts" / "dgccrf-rewrite" / "output" / "taxonomy_extension_proposal.json"

# Icon and color mapping for new domaines
DOMAINE_STYLES = {
    "logement": {
        "icone": "fr-icon-home-4-fill",
        "couleur": "#6A6AF4",
    },
    "banque_finance": {
        "icone": "fr-icon-bank-fill",
        "couleur": "#009081",
    },
    "droits_consommateur": {
        "icone": "fr-icon-scales-fill",
        "couleur": "#A558A0",
    },
    "services_funeraires": {
        "icone": "fr-icon-heart-fill",
        "couleur": "#7B4F8E",
    },
}


def build_situation(sit_data: dict) -> dict:
    """Build a situation dict in the canonical format."""
    situation = {
        "id": sit_data["id"],
        "label": sit_data["label"],
        "exemples": sit_data["exemples"],
        "sorties": sit_data["sorties"],
    }
    # Only include signalconso if present in the proposal
    if "signalconso" in sit_data:
        situation["signalconso"] = sit_data["signalconso"]
    return situation


def build_sous_domaine(sd_data: dict) -> dict:
    """Build a sous_domaine dict in the canonical format."""
    return {
        "id": sd_data["id"],
        "label": sd_data["label"],
        "situations": [build_situation(s) for s in sd_data["situations"]],
    }


def build_domaine(dom_data: dict) -> dict:
    """Build a domaine dict in the canonical format, using DOMAINE_STYLES."""
    dom_id = dom_data["id"]
    style = DOMAINE_STYLES.get(dom_id, {"icone": "fr-icon-question-fill", "couleur": "#666666"})
    return {
        "id": dom_id,
        "label": dom_data["label"],
        "icone": style["icone"],
        "description": dom_data["description"],
        "couleur": style["couleur"],
        "sous_domaines": [build_sous_domaine(sd) for sd in dom_data["sous_domaines"]],
    }


def main():
    # 1. Read both files
    print("Reading existing taxonomy...")
    with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
        taxonomy = json.load(f)

    print("Reading extension proposal...")
    with open(EXTENSION_PATH, "r", encoding="utf-8") as f:
        extension = json.load(f)

    # Track changes for summary
    added_domaines = []
    added_sous_domaines = []
    added_situations_to_existing = []

    # 2. Add new type_sortie
    new_type = extension["new_type_sortie"]
    for type_id, type_data in new_type.items():
        if type_id not in taxonomy["types_sortie"]:
            taxonomy["types_sortie"][type_id] = type_data
            print(f"  + Added type_sortie: {type_id} ({type_data['label']})")
        else:
            print(f"  = type_sortie '{type_id}' already exists, skipping")

    # 3. Add new domaines
    existing_domaine_ids = {d["id"] for d in taxonomy["domaines"]}
    for dom_data in extension["new_domaines"]:
        if dom_data["id"] in existing_domaine_ids:
            print(f"  ! Domaine '{dom_data['id']}' already exists, skipping")
            continue
        new_dom = build_domaine(dom_data)
        taxonomy["domaines"].append(new_dom)
        n_sd = len(new_dom["sous_domaines"])
        n_sit = sum(len(sd["situations"]) for sd in new_dom["sous_domaines"])
        added_domaines.append((new_dom["id"], new_dom["label"], n_sd, n_sit))
        print(f"  + Added domaine: {new_dom['id']} ({n_sd} sous-domaines, {n_sit} situations)")

    # 4. Extend existing domaines
    # Build index for quick lookup
    domaine_index = {d["id"]: d for d in taxonomy["domaines"]}

    for dom_id, ext_data in extension["extended_domaines"].items():
        if dom_id not in domaine_index:
            print(f"  ! Extended domaine '{dom_id}' not found in taxonomy, skipping")
            continue

        domaine = domaine_index[dom_id]
        existing_sd_ids = {sd["id"] for sd in domaine["sous_domaines"]}

        # 4a. Add new sous_domaines
        for sd_data in ext_data.get("new_sous_domaines", []):
            if sd_data["id"] in existing_sd_ids:
                print(f"  ! Sous-domaine '{sd_data['id']}' already exists in {dom_id}, skipping")
                continue
            new_sd = build_sous_domaine(sd_data)
            domaine["sous_domaines"].append(new_sd)
            n_sit = len(new_sd["situations"])
            added_sous_domaines.append((dom_id, new_sd["id"], new_sd["label"], n_sit))
            print(f"  + Added sous-domaine: {dom_id}/{new_sd['id']} ({n_sit} situations)")

        # 4b. Extend existing sous_domaines with new situations
        # Rebuild index after adding new sous_domaines
        sd_index = {sd["id"]: sd for sd in domaine["sous_domaines"]}

        for sd_id, sd_ext in ext_data.get("extended_sous_domaines", {}).items():
            if sd_id not in sd_index:
                print(f"  ! Sous-domaine '{sd_id}' not found in {dom_id}, skipping")
                continue

            sous_domaine = sd_index[sd_id]
            existing_sit_ids = {s["id"] for s in sous_domaine["situations"]}

            for sit_data in sd_ext.get("new_situations", []):
                if sit_data["id"] in existing_sit_ids:
                    print(f"  ! Situation '{sit_data['id']}' already exists in {dom_id}/{sd_id}, skipping")
                    continue
                new_sit = build_situation(sit_data)
                sous_domaine["situations"].append(new_sit)
                added_situations_to_existing.append((dom_id, sd_id, new_sit["id"], new_sit["label"]))
                print(f"  + Added situation: {dom_id}/{sd_id}/{new_sit['id']}")

    # 5. Update meta counts
    total_domaines = len(taxonomy["domaines"])
    total_sd = sum(len(d["sous_domaines"]) for d in taxonomy["domaines"])
    total_sit = sum(
        len(sd["situations"])
        for d in taxonomy["domaines"]
        for sd in d["sous_domaines"]
    )
    total_types = len(taxonomy["types_sortie"])

    taxonomy["meta"]["contenu"]["domaines"] = total_domaines
    taxonomy["meta"]["contenu"]["sous_domaines"] = total_sd
    taxonomy["meta"]["contenu"]["situations"] = total_sit
    taxonomy["meta"]["contenu"]["types_sortie"] = total_types

    # 6. Update version and date
    taxonomy["meta"]["version"] = "3.0"
    taxonomy["meta"]["date"] = "2026-02"

    # 7. Add note to description
    desc = taxonomy["meta"]["description"]
    extension_note = (
        " v3.0 : extension majeure — ajout de 4 domaines (logement, banque/finance, "
        "droits du consommateur, services funéraires), 16 sous-domaines et 80 situations "
        "pour couvrir les articles orphelins identifiés par l'analyse de couverture."
    )
    if "v3.0" not in desc:
        taxonomy["meta"]["description"] = desc + extension_note

    # 8. Write result
    print(f"\nWriting merged taxonomy to {TAXONOMY_PATH}...")
    with open(TAXONOMY_PATH, "w", encoding="utf-8") as f:
        json.dump(taxonomy, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # 9. Print summary
    print("\n" + "=" * 70)
    print("MERGE SUMMARY")
    print("=" * 70)

    print(f"\nNew type_sortie: information")

    print(f"\nNew domaines ({len(added_domaines)}):")
    for dom_id, dom_label, n_sd, n_sit in added_domaines:
        print(f"  {dom_id}: \"{dom_label}\" ({n_sd} sous-domaines, {n_sit} situations)")

    print(f"\nNew sous-domaines in existing domaines ({len(added_sous_domaines)}):")
    for dom_id, sd_id, sd_label, n_sit in added_sous_domaines:
        print(f"  {dom_id}/{sd_id}: \"{sd_label}\" ({n_sit} situations)")

    print(f"\nNew situations in existing sous-domaines ({len(added_situations_to_existing)}):")
    for dom_id, sd_id, sit_id, sit_label in added_situations_to_existing:
        print(f"  {dom_id}/{sd_id}/{sit_id}")

    total_new_sit = (
        sum(n for _, _, _, n in added_domaines)
        + sum(n for _, _, _, n in added_sous_domaines)
        + len(added_situations_to_existing)
    )

    print(f"\n--- TOTALS ---")
    print(f"  Domaines:       {total_domaines} (was 8)")
    print(f"  Sous-domaines:  {total_sd} (was 44)")
    print(f"  Situations:     {total_sit} (was 112)")
    print(f"  Types sortie:   {total_types} (was 16)")
    print(f"  New situations added: {total_new_sit}")

    # 10. Validate the written file
    print("\n--- VALIDATION ---")
    with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
        try:
            validated = json.load(f)
            print("  JSON: valid")
            v_dom = len(validated["domaines"])
            v_sd = sum(len(d["sous_domaines"]) for d in validated["domaines"])
            v_sit = sum(
                len(sd["situations"])
                for d in validated["domaines"]
                for sd in d["sous_domaines"]
            )
            print(f"  Domaines:      {v_dom}")
            print(f"  Sous-domaines: {v_sd}")
            print(f"  Situations:    {v_sit}")
            print(f"  Types sortie:  {len(validated['types_sortie'])}")
            assert v_dom == total_domaines, f"Domaines mismatch: {v_dom} != {total_domaines}"
            assert v_sd == total_sd, f"Sous-domaines mismatch: {v_sd} != {total_sd}"
            assert v_sit == total_sit, f"Situations mismatch: {v_sit} != {total_sit}"
            print("  Counts: consistent")
            print(f"  Version: {validated['meta']['version']}")
            print(f"  Date:    {validated['meta']['date']}")
        except json.JSONDecodeError as e:
            print(f"  JSON: INVALID - {e}")
            sys.exit(1)
        except AssertionError as e:
            print(f"  Counts: INCONSISTENT - {e}")
            sys.exit(1)

    print("\nDone.")


if __name__ == "__main__":
    main()
