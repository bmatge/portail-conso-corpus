"""Utilitaires texte : parsing frontmatter, nettoyage INC, chunking."""

from __future__ import annotations

import re
from pathlib import Path

import frontmatter


# ── Frontmatter ──────────────────────────────────────────────────────────────


def parse_md_file(path: Path) -> tuple[dict, str]:
    """Parse a .md file with YAML frontmatter. Returns (metadata, body)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    post = frontmatter.loads(text)
    meta = dict(post.metadata)
    body = post.content.strip()

    # Normalize INC tags from string repr to list
    if isinstance(meta.get("tags"), str):
        try:
            meta["tags"] = eval(meta["tags"])  # "['INC-Conso']" -> list
        except Exception:
            meta["tags"] = [meta["tags"]]

    return meta, body


def extract_source_metadata(meta: dict, source_type: str) -> dict:
    """Normalize metadata across source formats into a common schema."""
    if source_type == "inc":
        return {
            "source": "inc",
            "title": meta.get("title", ""),
            "id": "",
            "url": meta.get("source", ""),
            "content_type": "",
            "date": str(meta.get("date", "")),
            "taxonomy_terms": meta.get("tags", []),
        }
    else:
        # Drupal sources (dgccrf, particuliers, entreprises)
        return {
            "source": source_type,
            "title": meta.get("title", ""),
            "id": str(meta.get("nid", "")),
            "url": meta.get("alias", ""),
            "content_type": meta.get("type", ""),
            "date": meta.get("changed", meta.get("created", "")),
            "taxonomy_terms": meta.get("taxonomy", []),
        }


# ── Nettoyage INC ────────────────────────────────────────────────────────────


# Ligne purement image INC
_IMAGE_LINE_RE = re.compile(
    r"^\s*!\[.*?\]\(https?://.*?inc-conso\.fr/sites/default/.*?\)\s*$",
    re.MULTILINE,
)

# JSON résiduel dans descriptions
_JSON_MEDIA_RE = re.compile(r'\[\[\{.*?"type"\s*:\s*"media".*?\}\]\]', re.DOTALL)

# Lignes bruit : noms de réseaux sociaux isolés, tirets seuls
_NOISE_LINE_RE = re.compile(
    r"^\s*[-*]\s*$|^\s*(youtube|facebook|linkedin|twitter|instagram|tiktok)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Blanks excessifs
_MULTI_BLANK_RE = re.compile(r"\n{3,}")


def clean_inc_description(desc: str) -> str:
    """Strip [[{"type":"media",...}]] JSON from description field."""
    if not desc:
        return ""
    return _JSON_MEDIA_RE.sub("", desc).strip()


def remove_duplicate_h1(body: str) -> str:
    """If the body starts with two identical H1 lines, remove the second."""
    lines = body.split("\n")
    h1_indices = []
    for i, line in enumerate(lines):
        if line.startswith("# ") and not line.startswith("## "):
            h1_indices.append(i)
        if len(h1_indices) == 2:
            break

    if len(h1_indices) == 2:
        i1, i2 = h1_indices
        if lines[i1].strip() == lines[i2].strip():
            lines.pop(i2)
            # Remove potential blank line left behind
            if i2 < len(lines) and lines[i2].strip() == "":
                lines.pop(i2)

    return "\n".join(lines)


def is_boilerplate_dominated(
    body: str, markers: list[str], threshold: int
) -> bool:
    """Check if body is dominated by cookie/boilerplate markers."""
    body_lower = body.lower()
    count = sum(1 for m in markers if m.lower() in body_lower)
    return count >= threshold


def clean_inc_body(
    body: str, markers: list[str], threshold: int
) -> tuple[str, list[str]]:
    """
    Clean INC markdown body.
    Returns (cleaned_text, list_of_applied_cleanings).
    """
    applied = []

    # 1. Remove duplicate H1
    new = remove_duplicate_h1(body)
    if new != body:
        applied.append("duplicate_h1")
    body = new

    # 2. Remove image-only lines
    new = _IMAGE_LINE_RE.sub("", body)
    if new != body:
        applied.append("inc_images")
    body = new

    # 3. Remove noise lines
    new = _NOISE_LINE_RE.sub("", body)
    if new != body:
        applied.append("noise_lines")
    body = new

    # 4. Remove boilerplate cookie blocks
    # Strategy: find paragraphs containing multiple markers and remove them
    paragraphs = re.split(r"\n\n+", body)
    clean_paragraphs = []
    removed_bp = False
    for para in paragraphs:
        para_lower = para.lower()
        marker_count = sum(1 for m in markers if m.lower() in para_lower)
        if marker_count >= 2:
            removed_bp = True
            continue
        clean_paragraphs.append(para)
    if removed_bp:
        applied.append("boilerplate_blocks")
    body = "\n\n".join(clean_paragraphs)

    # 5. Normalize blank lines
    body = _MULTI_BLANK_RE.sub("\n\n", body).strip()

    return body, applied


# ── Chunking ─────────────────────────────────────────────────────────────────


# French sentence splitting
_ABBREVIATIONS = {"m.", "mme.", "art.", "al.", "cf.", "p.", "n°.", "etc."}

_SENTENCE_SPLIT_RE = re.compile(
    r"(?<=[.!?…])\s+(?=[A-ZÀ-ÜÉÈÊËÎÏÔÙÛÜŸÇŒÆa-zà-ü])"
)


def sentence_split(text: str) -> list[str]:
    """Split French text into sentences."""
    # Rough but effective: split on punctuation followed by space + letter
    raw_sentences = _SENTENCE_SPLIT_RE.split(text)
    # Merge very short fragments back (likely abbreviations)
    sentences = []
    for s in raw_sentences:
        s = s.strip()
        if not s:
            continue
        if sentences and len(sentences[-1]) < 20:
            sentences[-1] += " " + s
        else:
            sentences.append(s)
    return sentences


def chunk_text(
    text: str,
    title: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    min_chunk_length: int = 50,
) -> list[str]:
    """
    Split text into overlapping chunks at sentence boundaries.
    Each chunk is prefixed with the document title.
    """
    sentences = sentence_split(text)
    if not sentences:
        return []

    chunks = []
    current_sentences: list[str] = []
    current_len = 0

    for sent in sentences:
        sent_len = len(sent)

        if current_len + sent_len > chunk_size and current_sentences:
            # Emit current chunk
            chunk_text_raw = " ".join(current_sentences)
            chunks.append(f"{title} — {chunk_text_raw}")

            # Overlap: keep last sentences up to chunk_overlap chars
            overlap_sentences = []
            overlap_len = 0
            for s in reversed(current_sentences):
                if overlap_len + len(s) > chunk_overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_len += len(s)

            current_sentences = overlap_sentences
            current_len = overlap_len

        current_sentences.append(sent)
        current_len += sent_len

    # Emit final chunk
    if current_sentences:
        chunk_text_raw = " ".join(current_sentences)
        if len(chunk_text_raw) >= min_chunk_length:
            chunks.append(f"{title} — {chunk_text_raw}")

    return chunks
