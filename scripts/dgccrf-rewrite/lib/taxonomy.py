"""Parser pour taxonomie-dgccrf.json — modèles Pydantic + traversal."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


# ── Modèles ──────────────────────────────────────────────────────────────────


class Sortie(BaseModel):
    type: str
    priorite: int | None = None
    url: str | None = None
    label: str | None = None
    condition: str | None = None
    note: str | None = None


class SignalConso(BaseModel):
    category: str | None = None
    category_alt: str | None = None
    subcategory_hints: list[str] = []
    url_signalement: str | None = None
    url_signalement_alt: dict[str, str] | None = None
    urls_complementaires: dict[str, str] | None = None
    question_pivot: str | None = None
    note: str | None = None
    canal_principal_si_hors_sc: str | None = None
    urgence: bool = False


class Situation(BaseModel):
    id: str
    label: str
    exemples: list[str] = []
    sorties: list[Sortie] = []
    signalconso: SignalConso | None = None
    # Back-references, populated by load_taxonomy
    sous_domaine_id: str = ""
    domaine_id: str = ""
    is_transversale: bool = False


class Mediateur(BaseModel):
    label: str
    url: str


class SousDomaine(BaseModel):
    id: str
    label: str
    situations: list[Situation] = []
    mediateur: Mediateur | None = None
    # Back-reference
    domaine_id: str = ""


class Domaine(BaseModel):
    id: str
    label: str
    description: str = ""
    icone: str = ""
    couleur: str = ""
    sous_domaines: list[SousDomaine] = []


class TypeSortie(BaseModel):
    label: str
    description: str
    url: str


class Taxonomy(BaseModel):
    domaines: list[Domaine]
    situations_transversales: list[Situation]
    types_sortie: dict[str, TypeSortie]
    signalconso_categories: dict  # raw dict for URL lookup

    # ── Accessors ────────────────────────────────────────────────────────

    def all_domaines(self) -> list[Domaine]:
        return self.domaines

    def all_sous_domaines(self) -> list[SousDomaine]:
        return [sd for d in self.domaines for sd in d.sous_domaines]

    def all_situations(self) -> list[Situation]:
        sits = [
            s
            for d in self.domaines
            for sd in d.sous_domaines
            for s in sd.situations
        ]
        sits.extend(self.situations_transversales)
        return sits

    def all_items(self) -> list[tuple[str, str, Domaine | SousDomaine | Situation]]:
        """Returns (level, id, object) for every item."""
        items: list[tuple[str, str, Domaine | SousDomaine | Situation]] = []
        for d in self.domaines:
            items.append(("domaine", d.id, d))
            for sd in d.sous_domaines:
                items.append(("sous_domaine", sd.id, sd))
                for s in sd.situations:
                    items.append(("situation", s.id, s))
        for s in self.situations_transversales:
            items.append(("situation", s.id, s))
        return items

    def get_by_id(self, item_id: str) -> Domaine | SousDomaine | Situation | None:
        for d in self.domaines:
            if d.id == item_id:
                return d
            for sd in d.sous_domaines:
                if sd.id == item_id:
                    return sd
                for s in sd.situations:
                    if s.id == item_id:
                        return s
        for s in self.situations_transversales:
            if s.id == item_id:
                return s
        return None

    def get_domaine_for(self, item: SousDomaine | Situation) -> Domaine | None:
        domaine_id = item.domaine_id if hasattr(item, "domaine_id") else ""
        for d in self.domaines:
            if d.id == domaine_id:
                return d
        return None

    def get_sous_domaine_for(self, item: Situation) -> SousDomaine | None:
        for d in self.domaines:
            for sd in d.sous_domaines:
                if sd.id == item.sous_domaine_id:
                    return sd
        return None

    def resolve_sortie_url(self, sortie: Sortie) -> str:
        """Resolve full URL: sortie.url > types_sortie[type].url."""
        if sortie.url:
            return sortie.url
        ts = self.types_sortie.get(sortie.type)
        if ts:
            return ts.url
        return ""

    def resolve_sortie_label(self, sortie: Sortie) -> str:
        """Resolve label: sortie.label > types_sortie[type].label."""
        if sortie.label:
            return sortie.label
        ts = self.types_sortie.get(sortie.type)
        if ts:
            return ts.label
        return sortie.type

    def item_count(self) -> dict[str, int]:
        return {
            "domaines": len(self.domaines),
            "sous_domaines": len(self.all_sous_domaines()),
            "situations": len(self.all_situations()),
            "total": len(self.all_items()),
        }


# ── Loader ───────────────────────────────────────────────────────────────────


def load_taxonomy(path: Path) -> Taxonomy:
    """Parse taxonomie-dgccrf.json into a fully cross-referenced Taxonomy."""
    with open(path) as f:
        raw = json.load(f)

    # Types de sortie
    types_sortie = {
        k: TypeSortie(**v) for k, v in raw.get("types_sortie", {}).items()
    }

    # SignalConso categories (raw dict)
    sc_categories = raw.get("signalconso_categories", {})

    # Domaines → sous-domaines → situations
    domaines = []
    for d_raw in raw.get("domaines", []):
        sous_domaines = []
        for sd_raw in d_raw.get("sous_domaines", []):
            situations = []
            for s_raw in sd_raw.get("situations", []):
                sit = Situation(
                    **s_raw,
                    sous_domaine_id=sd_raw["id"],
                    domaine_id=d_raw["id"],
                )
                situations.append(sit)

            mediateur = None
            if "mediateur" in sd_raw:
                mediateur = Mediateur(**sd_raw["mediateur"])

            sd = SousDomaine(
                id=sd_raw["id"],
                label=sd_raw["label"],
                situations=situations,
                mediateur=mediateur,
                domaine_id=d_raw["id"],
            )
            sous_domaines.append(sd)

        domaine = Domaine(
            id=d_raw["id"],
            label=d_raw["label"],
            description=d_raw.get("description", ""),
            icone=d_raw.get("icone", ""),
            couleur=d_raw.get("couleur", ""),
            sous_domaines=sous_domaines,
        )
        domaines.append(domaine)

    # Situations transversales
    transversales = []
    for s_raw in raw.get("situations_transversales", []):
        sit = Situation(**s_raw, is_transversale=True)
        transversales.append(sit)

    return Taxonomy(
        domaines=domaines,
        situations_transversales=transversales,
        types_sortie=types_sortie,
        signalconso_categories=sc_categories,
    )
