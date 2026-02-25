"""Assemblage prompt 3 couches × 3 niveaux pour la génération de fiches."""

from __future__ import annotations

from pathlib import Path

from lib.taxonomy import Domaine, Situation, SousDomaine, Taxonomy


class PromptBuilder:
    """Assemble system + template + contexte dynamique pour chaque niveau."""

    def __init__(self, prompts_dir: Path, taxonomy: Taxonomy):
        self.taxonomy = taxonomy
        self.system_prompt = (prompts_dir / "system.md").read_text()
        self.template_domaine = (prompts_dir / "template_domaine.md").read_text()
        self.template_sous_domaine = (prompts_dir / "template_sous_domaine.md").read_text()
        self.template_situation = (prompts_dir / "template_situation.md").read_text()
        self.checklist = (prompts_dir / "checklist.md").read_text()

    def build_domaine_prompt(
        self,
        domaine: Domaine,
        sources_dgccrf: list[dict],
        sources_other: list[dict],
    ) -> tuple[str, str]:
        """Returns (system_prompt, user_prompt) for a domaine fiche."""
        # Taxonomic context
        sd_list = []
        for sd in domaine.sous_domaines:
            sits = ", ".join(s.label for s in sd.situations[:3])
            sd_list.append(
                f"- **{sd.label}** (id: `{sd.id}`): {len(sd.situations)} situations. "
                f"Exemples : {sits}..."
            )

        context = f"""## Contexte taxonomique

**Domaine** : {domaine.label}
**ID** : `{domaine.id}`
**Description** : {domaine.description}
**Icône** : {domaine.icone}

### Sous-domaines ({len(domaine.sous_domaines)})

{chr(10).join(sd_list)}
"""

        sources = self._format_sources(sources_dgccrf, sources_other)

        user_prompt = f"""{self.template_domaine}

{context}

{sources}

{self.checklist}"""

        return self.system_prompt, user_prompt

    def build_sous_domaine_prompt(
        self,
        sous_domaine: SousDomaine,
        domaine: Domaine,
        sources_dgccrf: list[dict],
        sources_other: list[dict],
    ) -> tuple[str, str]:
        """Returns (system_prompt, user_prompt) for a sous-domaine fiche."""
        # Situations list
        sit_list = []
        for s in sous_domaine.situations:
            exemples = ", ".join(s.exemples[:2]) if s.exemples else ""
            sit_list.append(
                f"- **{s.label}** (id: `{s.id}`)"
                + (f" — ex: {exemples}" if exemples else "")
            )

        # Collect all sortie types used in this sous-domaine
        sortie_types = set()
        for s in sous_domaine.situations:
            for sortie in s.sorties:
                sortie_types.add(sortie.type)

        sorties_text = self._format_sortie_types(sortie_types)

        # Mediateur
        mediateur_text = ""
        if sous_domaine.mediateur:
            mediateur_text = (
                f"\n### Médiateur sectoriel\n"
                f"- **{sous_domaine.mediateur.label}** : {sous_domaine.mediateur.url}\n"
            )

        context = f"""## Contexte taxonomique

**Sous-domaine** : {sous_domaine.label}
**ID** : `{sous_domaine.id}`
**Domaine parent** : {domaine.label} (`{domaine.id}`)

### Situations ({len(sous_domaine.situations)})

{chr(10).join(sit_list)}

### Sorties disponibles dans ce sous-domaine

{sorties_text}
{mediateur_text}
"""

        sources = self._format_sources(sources_dgccrf, sources_other)

        user_prompt = f"""{self.template_sous_domaine}

{context}

{sources}

{self.checklist}"""

        return self.system_prompt, user_prompt

    def build_situation_prompt(
        self,
        situation: Situation,
        sous_domaine: SousDomaine | None,
        domaine: Domaine | None,
        sources_dgccrf: list[dict],
        sources_other: list[dict],
    ) -> tuple[str, str]:
        """Returns (system_prompt, user_prompt) for a situation fiche."""
        # Sorties
        sorties_lines = []
        for s in situation.sorties:
            label = self.taxonomy.resolve_sortie_label(s)
            url = self.taxonomy.resolve_sortie_url(s)
            line = f"- **Priorité {s.priorite or '-'}** : {label}"
            if url:
                line += f" — {url}"
            if s.note:
                line += f" ({s.note})"
            if s.condition:
                line += f" [condition : {s.condition}]"
            sorties_lines.append(line)

        # SignalConso
        sc_text = ""
        if situation.signalconso:
            sc = situation.signalconso
            sc_lines = []
            if sc.category:
                sc_lines.append(f"- Catégorie : `{sc.category}`")
            if sc.category_alt:
                sc_lines.append(f"- Catégorie alternative : `{sc.category_alt}`")
            if sc.url_signalement:
                sc_lines.append(f"- URL de signalement direct : {sc.url_signalement}")
            if sc.url_signalement_alt:
                for key, url in sc.url_signalement_alt.items():
                    label = key.replace("url_signalement_", "").replace("_", " ").capitalize()
                    sc_lines.append(f"- URL {label} : {url}")
            if sc.question_pivot:
                sc_lines.append(f"- **Question pivot** : {sc.question_pivot}")
            if sc.note:
                sc_lines.append(f"- Note : {sc.note}")
            if sc.urgence:
                sc_lines.append(f"- ⚠️ SITUATION URGENTE")
            sc_text = "\n### Mapping SignalConso\n\n" + "\n".join(sc_lines)

        # Mediateur
        mediateur_text = ""
        if sous_domaine and sous_domaine.mediateur:
            mediateur_text = (
                f"\n### Médiateur sectoriel\n"
                f"- **{sous_domaine.mediateur.label}** : {sous_domaine.mediateur.url}\n"
            )

        # Exemples from taxonomy
        exemples_text = ""
        if situation.exemples:
            exemples_text = "\n### Exemples fournis par la taxonomie\n\n" + "\n".join(
                f"- {e}" for e in situation.exemples
            )

        sd_label = sous_domaine.label if sous_domaine else "(transversale)"
        d_label = domaine.label if domaine else "(transversale)"

        context = f"""## Contexte taxonomique

**Situation** : {situation.label}
**ID** : `{situation.id}`
**Sous-domaine** : {sd_label}
**Domaine** : {d_label}

### Sorties (par priorité)

{chr(10).join(sorties_lines) if sorties_lines else "Aucune sortie définie."}
{sc_text}
{mediateur_text}
{exemples_text}
"""

        sources = self._format_sources(sources_dgccrf, sources_other)

        user_prompt = f"""{self.template_situation}

{context}

{sources}

{self.checklist}"""

        return self.system_prompt, user_prompt

    # ── Helpers ──────────────────────────────────────────────────────────

    def _format_sources(
        self,
        sources_dgccrf: list[dict],
        sources_other: list[dict],
    ) -> str:
        """Format retrieved sources as Markdown."""
        parts = []

        if sources_dgccrf:
            parts.append("## Sources DGCCRF\n")
            for i, s in enumerate(sources_dgccrf, 1):
                parts.append(f"### Source DGCCRF {i} — {s['title']}")
                if s.get("url"):
                    parts.append(f"URL : {s['url']}")
                parts.append(f"> {s['text'][:3000]}")
                parts.append("")
        else:
            parts.append("## Sources DGCCRF\n\nAucune source DGCCRF trouvée.\n")

        if sources_other:
            parts.append("## Sources complémentaires (INC, Particuliers, Entreprises)\n")
            for i, s in enumerate(sources_other, 1):
                parts.append(f"### Source {i} [{s['source']}] — {s['title']}")
                if s.get("url"):
                    parts.append(f"URL : {s['url']}")
                parts.append(f"> {s['text'][:3000]}")
                parts.append("")
        else:
            parts.append("## Sources complémentaires\n\nAucune source complémentaire trouvée.\n")

        return "\n".join(parts)

    def _format_sortie_types(self, sortie_types: set[str]) -> str:
        """Format a set of sortie types with resolved labels and URLs."""
        lines = []
        for st in sorted(sortie_types):
            ts = self.taxonomy.types_sortie.get(st)
            if ts:
                lines.append(f"- **{ts.label}** : {ts.url}")
            else:
                lines.append(f"- {st}")
        return "\n".join(lines) if lines else "Aucune sortie définie."
