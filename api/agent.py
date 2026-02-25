"""Agent multi-étapes — sessions, phases, prompts d'orientation consommateur."""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger(__name__)


class Phase(str, Enum):
    CLASSIFY = "classify"
    CLARIFY = "clarify"
    ANSWER = "answer"
    ACTION = "action"


@dataclass
class Session:
    id: str
    phase: Phase = Phase.CLASSIFY
    situation_id: str | None = None
    situation_label: str = ""
    domaine_label: str = ""
    ss_label: str = ""
    candidates: list[str] = field(default_factory=list)
    rag_chunks: list[dict] = field(default_factory=list)
    turn_count: int = 0
    pivot_asked: bool = False
    clarify_question: str = ""
    classify_result: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)


# ── Session store (in-memory, TTL 1h) ───────────────────

_sessions: dict[str, Session] = {}
SESSION_TTL = 3600


def get_or_create_session(session_id: str | None = None) -> Session:
    """Get existing session or create a new one."""
    _cleanup_expired()
    if session_id and session_id in _sessions:
        s = _sessions[session_id]
        s.last_active = time.time()
        return s
    s = Session(id=str(uuid.uuid4()))
    _sessions[s.id] = s
    return s


def _cleanup_expired():
    now = time.time()
    expired = [k for k, v in _sessions.items() if now - v.last_active > SESSION_TTL]
    for k in expired:
        del _sessions[k]


# ── Taxonomy helpers ─────────────────────────────────────


def find_situation(taxonomy: dict, situation_id: str) -> dict | None:
    """Find situation + parent info in raw taxonomy dict."""
    for dom in taxonomy.get("domaines", []):
        for ss in dom.get("sous_domaines", []):
            for sit in ss.get("situations", []):
                if sit.get("id") == situation_id:
                    return {
                        "situation": sit,
                        "sous_domaine": ss,
                        "domaine": dom,
                    }
    for sit in taxonomy.get("situations_transversales", []):
        if sit.get("id") == situation_id:
            return {"situation": sit, "sous_domaine": None, "domaine": None}
    return None


def build_actions(taxonomy: dict, situation_id: str) -> dict:
    """Build action card data from taxonomy."""
    info = find_situation(taxonomy, situation_id)
    if not info:
        return {"actions": [], "signalconso": None, "mediateur": None}

    sit = info["situation"]
    ss = info["sous_domaine"]
    types_sortie = taxonomy.get("types_sortie", {})

    actions = []
    for sortie in sit.get("sorties", []):
        s_type = sortie.get("type", "")
        type_info = types_sortie.get(s_type, {})
        url = sortie.get("url") or type_info.get("url", "")
        label = sortie.get("label") or type_info.get("label", s_type)
        actions.append({
            "type": s_type,
            "label": label,
            "url": url,
            "priorite": sortie.get("priorite", 3),
            "note": sortie.get("note", ""),
            "condition": sortie.get("condition", ""),
        })

    sc = sit.get("signalconso")
    sc_data = None
    if sc:
        sc_data = {
            "url": sc.get("url_signalement", ""),
            "category": sc.get("category", ""),
            "note": sc.get("note", ""),
            "urgence": sc.get("urgence", False),
        }

    med = ss.get("mediateur") if ss else None
    med_data = None
    if med:
        med_data = {"label": med.get("label", ""), "url": med.get("url", "")}

    return {
        "actions": sorted(actions, key=lambda a: a.get("priorite", 3)),
        "signalconso": sc_data,
        "mediateur": med_data,
    }


# ── Prompt builders ──────────────────────────────────────


def build_answer_prompt(
    session: Session,
    rag_chunks: list[dict],
    fiche_content: str = "",
) -> str:
    """Build the ANSWER phase system prompt — markdown response with citations."""
    ctx_lines = []
    for i, r in enumerate(rag_chunks, 1):
        src = r.get("source", "").upper()
        title = r.get("title", "")
        text = r.get("text", "").replace("\n", " ").strip()[:400]
        ctx_lines.append(f'[{i}] (source: {src}, titre: "{title}") — "{text}"')
    ctx_block = "\n".join(ctx_lines) if ctx_lines else "(aucune source complementaire)"

    fiche_block = ""
    if fiche_content:
        fiche_block = f"""
FICHE DE REFERENCE (situation identifiee) :
---
{fiche_content[:3000]}
---
"""

    return f"""Tu es un conseiller en consommation de la DGCCRF. L'utilisateur a un probleme identifie comme :
**{session.situation_label}**
Domaine : {session.domaine_label} > {session.ss_label}

{fiche_block}
SOURCES COMPLEMENTAIRES DU CORPUS :
{ctx_block}

INSTRUCTIONS :
- Reponds en francais, en markdown structure (titres ##, listes, gras)
- Sois concret, pratique et actionnable
- Mentionne les droits du consommateur applicables (articles de loi si pertinent)
- Cite les sources avec [1], [2], etc. quand tu t'appuies dessus
- Ne donne PAS de conseil juridique personnalise
- Utilise un ton bienveillant et professionnel
- Termine par un resume des prochaines etapes concretes
- Maximum 400 mots"""
