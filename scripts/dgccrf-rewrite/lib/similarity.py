"""Calcul de similarité entre items de la taxonomie — sujets proches & faux amis."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from lib.taxonomy import Domaine, Situation, SousDomaine, Taxonomy

log = logging.getLogger(__name__)


class TaxonomySimilarity:
    """Pré-calcule la matrice de similarité entre tous les items de la taxonomie."""

    def __init__(self, taxonomy: Taxonomy, embed_fn):
        self.taxonomy = taxonomy
        self.embed_fn = embed_fn

        # Build item index: [(level, id, item, text_for_embedding)]
        self._items: list[tuple[str, str, Domaine | SousDomaine | Situation, str]] = []
        self._id_to_idx: dict[str, int] = {}
        self._sim_matrix: np.ndarray | None = None

        self._build_index()
        self._compute_similarity()

    # ── Index construction ──────────────────────────────────────────────

    def _build_index(self):
        """Build a flat list of (level, id, item, embed_text) for all taxonomy items."""
        for level, item_id, item in self.taxonomy.all_items():
            text = self._item_to_text(level, item)
            idx = len(self._items)
            self._items.append((level, item_id, item, text))
            self._id_to_idx[item_id] = idx

    def _item_to_text(self, level: str, item) -> str:
        """Build the text representation of an item for embedding."""
        if level == "situation":
            exemples = ". ".join(item.exemples[:3]) if item.exemples else ""
            sd = self.taxonomy.get_sous_domaine_for(item)
            sd_label = sd.label if sd else ""
            return f"{item.label}. {exemples}. {sd_label}".strip()

        elif level == "sous_domaine":
            sit_labels = ", ".join(s.label for s in item.situations[:5])
            return f"{item.label}. Situations : {sit_labels}".strip()

        elif level == "domaine":
            return f"{item.label}. {item.description}".strip()

        return item.label

    # ── Embedding & similarity ──────────────────────────────────────────

    def _compute_similarity(self):
        """Embed all items and compute pairwise cosine similarity."""
        texts = [t for _, _, _, t in self._items]
        if not texts:
            self._sim_matrix = np.array([])
            return

        log.info(f"Embedding {len(texts)} taxonomy items for similarity...")
        embeddings = self.embed_fn(texts)
        emb_matrix = np.array(embeddings)
        self._sim_matrix = cosine_similarity(emb_matrix)
        log.info("Similarity matrix computed: %s", self._sim_matrix.shape)

    # ── Branch helpers ──────────────────────────────────────────────────

    def _get_branch_ids(self, item_id: str) -> set[str]:
        """Return all item IDs in the same branch (sous-domaine subtree)."""
        idx = self._id_to_idx.get(item_id)
        if idx is None:
            return set()

        level, _, item, _ = self._items[idx]
        branch = {item_id}

        if level == "situation":
            # Exclude same sous-domaine and its other situations
            sd = self.taxonomy.get_sous_domaine_for(item)
            if sd:
                branch.add(sd.id)
                for s in sd.situations:
                    branch.add(s.id)
        elif level == "sous_domaine":
            # Exclude same domaine and its sous-domaines + situations
            d = self.taxonomy.get_domaine_for(item)
            if d:
                branch.add(d.id)
                for sd in d.sous_domaines:
                    branch.add(sd.id)
                    for s in sd.situations:
                        branch.add(s.id)
        elif level == "domaine":
            # Exclude all children
            for sd in item.sous_domaines:
                branch.add(sd.id)
                for s in sd.situations:
                    branch.add(s.id)

        return branch

    def _get_sortie_types(self, item) -> set[str]:
        """Extract the set of sortie types for an item."""
        if isinstance(item, Situation):
            return {s.type for s in item.sorties}
        elif isinstance(item, SousDomaine):
            types = set()
            for sit in item.situations:
                for s in sit.sorties:
                    types.add(s.type)
            return types
        return set()

    # ── Public API ──────────────────────────────────────────────────────

    def get_sujets_proches(
        self,
        item_id: str,
        top_k: int = 5,
        min_score: float = 0.55,
    ) -> list[dict]:
        """Return related items from other taxonomy branches.

        Excludes items from the same sous-domaine subtree.
        Returns items sorted by descending similarity.
        """
        idx = self._id_to_idx.get(item_id)
        if idx is None:
            log.warning(f"Item {item_id} not found in taxonomy")
            return []

        if self._sim_matrix is None or self._sim_matrix.size == 0:
            return []

        branch_ids = self._get_branch_ids(item_id)
        scores = self._sim_matrix[idx]

        candidates = []
        for i, score in enumerate(scores):
            if i == idx:
                continue
            other_level, other_id, other_item, _ = self._items[i]
            if other_id in branch_ids:
                continue
            if score < min_score:
                continue
            candidates.append({
                "id": other_id,
                "label": other_item.label,
                "level": other_level,
                "score": round(float(score), 3),
                "domaine_id": self._get_domaine_id(other_level, other_item),
                "sous_domaine_id": self._get_sous_domaine_id(other_level, other_item),
            })

        # Sort by score descending
        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates[:top_k]

    def get_faux_amis(
        self,
        item_id: str,
        top_k: int = 3,
        similarity_range: tuple[float, float] = (0.45, 0.80),
    ) -> list[dict]:
        """Return look-alike items that are actually different problems.

        Selects items in the similarity range that:
        - Are in a different sous-domaine or domaine
        - Have different sortie types (different recourse paths)

        Returns items sorted by "confusion potential" (similarity * structural distance).
        """
        idx = self._id_to_idx.get(item_id)
        if idx is None:
            log.warning(f"Item {item_id} not found in taxonomy")
            return []

        if self._sim_matrix is None or self._sim_matrix.size == 0:
            return []

        level, _, item, _ = self._items[idx]
        my_sorties = self._get_sortie_types(item)
        my_domaine_id = self._get_domaine_id(level, item)
        my_sd_id = self._get_sous_domaine_id(level, item)

        scores = self._sim_matrix[idx]
        lo, hi = similarity_range

        candidates = []
        for i, score in enumerate(scores):
            if i == idx:
                continue
            if not (lo <= score <= hi):
                continue

            other_level, other_id, other_item, _ = self._items[i]
            other_domaine_id = self._get_domaine_id(other_level, other_item)
            other_sd_id = self._get_sous_domaine_id(other_level, other_item)

            # Must be in a different sous-domaine at least
            if my_sd_id and other_sd_id and my_sd_id == other_sd_id:
                continue

            # Structural distance: 2 if different domaine, 1 if different sous-domaine
            if my_domaine_id != other_domaine_id:
                structural_dist = 2
            else:
                structural_dist = 1

            # Check sortie difference
            other_sorties = self._get_sortie_types(other_item)
            sorties_diff = my_sorties.symmetric_difference(other_sorties)
            # Prefer items with genuinely different recourse paths
            if not sorties_diff and my_sorties:
                continue

            confusion = float(score) * (1 + structural_dist)

            candidates.append({
                "id": other_id,
                "label": other_item.label,
                "level": other_level,
                "score": round(float(score), 3),
                "domaine_id": other_domaine_id,
                "sous_domaine_id": other_sd_id,
                "sorties_diff": sorted(sorties_diff),
                "confusion_potential": round(confusion, 3),
            })

        # Sort by confusion potential descending
        candidates.sort(key=lambda c: c["confusion_potential"], reverse=True)
        return candidates[:top_k]

    # ── Path helpers ────────────────────────────────────────────────────

    def get_relative_path(self, from_item_id: str, to_item_id: str) -> str:
        """Compute the relative markdown path from one fiche to another.

        Returns a relative path like '../../numerique_cyber/arnaques_ligne/phishing.md'
        """
        from_idx = self._id_to_idx.get(from_item_id)
        to_idx = self._id_to_idx.get(to_item_id)
        if from_idx is None or to_idx is None:
            return ""

        from_level, _, from_item, _ = self._items[from_idx]
        to_level, _, to_item, _ = self._items[to_idx]

        from_path = self._item_to_corpus_path(from_level, from_item)
        to_path = self._item_to_corpus_path(to_level, to_item)

        if not from_path or not to_path:
            return ""

        # Compute relative path from parent of from_path to to_path
        try:
            from_dir = Path(from_path).parent
            rel = Path(to_path).relative_to(Path())
            from_dir_rel = Path(from_path).parent
            # Use PurePosixPath for relative computation
            from pathlib import PurePosixPath
            from_parts = PurePosixPath(from_path).parent.parts
            to_parts = PurePosixPath(to_path).parts

            # Find common prefix
            common = 0
            for a, b in zip(from_parts, to_parts):
                if a == b:
                    common += 1
                else:
                    break

            ups = len(from_parts) - common
            remainder = to_parts[common:]
            return "/".join([".."] * ups + list(remainder))
        except Exception:
            return str(to_path)

    def _item_to_corpus_path(self, level: str, item) -> str:
        """Return the corpus-relative path for an item."""
        if level == "domaine":
            return f"{item.id}/_index.md"
        elif level == "sous_domaine":
            domaine = self.taxonomy.get_domaine_for(item)
            if domaine:
                return f"{domaine.id}/{item.id}/_index.md"
            return f"{item.id}/_index.md"
        elif level == "situation":
            if item.is_transversale:
                return f"transversales/{item.id}.md"
            sd = self.taxonomy.get_sous_domaine_for(item)
            domaine = self.taxonomy.get_domaine_for(item)
            if sd and domaine:
                return f"{domaine.id}/{sd.id}/{item.id}.md"
            return f"{item.id}.md"
        return ""

    def _get_domaine_id(self, level: str, item) -> str:
        if level == "domaine":
            return item.id
        return getattr(item, "domaine_id", "")

    def _get_sous_domaine_id(self, level: str, item) -> str:
        if level == "sous_domaine":
            return item.id
        if level == "situation":
            return getattr(item, "sous_domaine_id", "")
        return ""
