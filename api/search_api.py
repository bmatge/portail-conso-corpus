#!/usr/bin/env python3
"""FastAPI search service — semantic search over ChromaDB corpus + LLM chat proxy."""

import hashlib
import os
import re
import time
import json
import logging
from typing import Optional
from pathlib import Path

import frontmatter
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
import httpx

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "../chroma_db")
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "dgccrf_corpus")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "https://albert.api.etalab.gouv.fr/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "openweight-medium")

app = FastAPI(title="Portail Conso Search API")

# CORS is handled by nginx (or serve.py in dev) — no middleware here
# to avoid duplicate Access-Control-Allow-Origin headers.

# Globals initialised at startup
collection = None
system_prompt = ""
source_index: dict[str, list[dict]] = {}  # source_id -> [{filename, title, nid}]
nid_to_file: dict[str, str] = {}  # "source:nid" -> filename


# ── Source directory discovery ────────────────────────────

SOURCE_DIRS_CONFIG = [
    ("dgccrf", "dgccrf-drupal", "sources/dgccrf"),
    ("particuliers", "particuliers-drupal", "sources/particuliers"),
    ("entreprises", "entreprises-drupal", "sources/entreprises"),
    ("inc", "inc-conso-md/content", "sources/inc"),
]

SOURCE_LABELS = {
    "dgccrf": "DGCCRF",
    "particuliers": "Service-Public Particuliers",
    "entreprises": "Service-Public Entreprises",
    "inc": "INC (Institut National de la Consommation)",
}

SOURCES_DIRS: dict[str, Path] = {}
for _src, _dev, _docker in SOURCE_DIRS_CONFIG:
    for _p in [
        Path(__file__).resolve().parent.parent / _dev,
        Path(f"/usr/share/nginx/html/{_docker}"),
    ]:
        if _p.is_dir():
            SOURCES_DIRS[_src] = _p
            break


def _build_source_index() -> tuple[dict, dict]:
    """Scan source directories and build lookup indexes."""
    idx: dict[str, list[dict]] = {}
    nid_map: dict[str, str] = {}

    for src, dirpath in SOURCES_DIRS.items():
        files = sorted(f for f in dirpath.glob("*.md") if not f.name.startswith("_"))
        entries = []
        for f in files:
            try:
                post = frontmatter.loads(f.read_text(encoding="utf-8"))
                meta = dict(post.metadata)
            except Exception:
                meta = {}
            title = meta.get("title", f.stem)
            nid = str(meta.get("nid", ""))
            entry = {"filename": f.name, "title": title, "nid": nid}
            entries.append(entry)
            if nid:
                nid_map[f"{src}:{nid}"] = f.name
        idx[src] = entries
        log.info("Source index: %s — %d files", src, len(entries))

    return idx, nid_map


# ── System prompt ─────────────────────────────────────────

def _build_system_prompt() -> str:
    """Build system prompt from taxonomie-dgccrf.json."""
    for p in [
        Path(__file__).resolve().parent.parent / "taxonomie-dgccrf.json",
        Path("/usr/share/nginx/html/taxonomie-dgccrf.json"),
    ]:
        if p.exists():
            tax = json.loads(p.read_text(encoding="utf-8"))
            break
    else:
        log.warning("taxonomie-dgccrf.json not found — using empty taxonomy")
        return "Tu es un assistant consommateur de la DGCCRF."

    lines = []
    for dom in tax.get("domaines", []):
        dom_label = dom.get("label", "")
        for ss in dom.get("sous_domaines", []):
            for sit in ss.get("situations", []):
                sid = sit.get("id", "")
                slabel = sit.get("label", "")
                lines.append(f"{sid} | {slabel} | {dom_label}")

    taxonomy_block = "\n".join(lines)
    return f"""Tu es un assistant de flechage pour les consommateurs francais, opere par la DGCCRF.

LISTE DES SITUATIONS (format : id | libelle | domaine) :
{taxonomy_block}

REGLES STRICTES :
1. Tu reponds UNIQUEMENT en JSON valide, sans aucun texte avant ou apres.
2. Si le probleme correspond clairement a une situation → retourne situation_id + confiance "haute" ou "moyenne".
3. Si tu hesites entre plusieurs situations → retourne question_clarification + candidate_situation_ids (liste des ids hesitants) + situation_id null.
4. Si hors perimetre DGCCRF → hors_perimetre: true.
5. Ne jamais inventer un situation_id absent de la liste.

FORMAT DE REPONSE OBLIGATOIRE (JSON strict) :
{{
  "situation_id": "string | null",
  "confiance": "haute | moyenne | faible",
  "question_clarification": "string | null",
  "candidate_situation_ids": [],
  "hors_perimetre": false
}}"""


# ── Auto-indexing fiches at startup ───────────────────────

CORPUS_DIR = None
for _p in [
    Path(__file__).resolve().parent.parent / "corpus",
    Path("/usr/share/nginx/html/corpus"),
]:
    if _p.is_dir():
        CORPUS_DIR = _p
        break

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
MIN_CHUNK_LENGTH = 50

_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÀ-ÜÉÈÊËÎÏÔÙÛÜŸÇŒÆa-zà-ü])")


def _chunk_text(text: str, title: str) -> list[str]:
    """Split text into overlapping chunks at sentence boundaries."""
    sentences = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]
    if not sentences:
        return []
    chunks, cur, cur_len = [], [], 0
    for s in sentences:
        if cur_len + len(s) > CHUNK_SIZE and cur:
            chunks.append(f"{title} — {' '.join(cur)}")
            overlap, ol = [], 0
            for x in reversed(cur):
                if ol + len(x) > CHUNK_OVERLAP:
                    break
                overlap.insert(0, x)
                ol += len(x)
            cur, cur_len = overlap, ol
        cur.append(s)
        cur_len += len(s)
    if cur and len(" ".join(cur)) >= MIN_CHUNK_LENGTH:
        chunks.append(f"{title} — {' '.join(cur)}")
    return chunks


def _index_fiches(coll) -> int:
    """Index corpus/ fiches into ChromaDB. Returns number of chunks added."""
    if not CORPUS_DIR:
        return 0
    files = sorted(CORPUS_DIR.rglob("*.md"))
    files = [f for f in files if not f.name.startswith("_")]
    all_chunks, all_metas, all_ids = [], [], []
    for path in files:
        try:
            post = frontmatter.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta = dict(post.metadata)
        body = post.content.strip()
        if len(body) < 100:
            continue
        taxonomy_id = meta.get("taxonomy_id", path.stem)
        title = meta.get("title", path.stem)
        fiche_path = str(path.relative_to(CORPUS_DIR))
        chunks = _chunk_text(body, title)
        doc_id = hashlib.md5(fiche_path.encode()).hexdigest()[:12]
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metas.append({
                "source": "fiches",
                "title": title,
                "taxonomy_id": taxonomy_id,
                "fiche_path": fiche_path,
                "chunk_index": i,
                "nid": "",
                "url": "",
                "content_type": "fiche",
                "date": meta.get("generated_at", ""),
            })
            all_ids.append(f"fiches_{doc_id}_{i}")
    if all_chunks:
        coll.add(documents=all_chunks, metadatas=all_metas, ids=all_ids)
    return len(all_chunks)


# ── Dedup helper ──────────────────────────────────────────

def _dedup_key(meta: dict) -> str:
    """Build a deduplication key from chunk metadata."""
    src = meta.get("source", "")
    if meta.get("fiche_path"):
        return f"fiches:{meta['fiche_path']}"
    nid = meta.get("nid", "")
    if nid:
        return f"{src}:{nid}"
    return f"{src}:{meta.get('title', '')}"


def _resolve_source_file(meta: dict) -> str:
    """Resolve a source filename from chunk metadata."""
    src = meta.get("source", "")
    if src == "fiches":
        return ""
    nid = meta.get("nid", "")
    if nid:
        filename = nid_to_file.get(f"{src}:{nid}", "")
        if filename:
            return filename
    # Fallback: try to find by title match
    for entry in source_index.get(src, []):
        if entry["title"] == meta.get("title", ""):
            return entry["filename"]
    return ""


def _deduplicate(results: list[dict]) -> list[dict]:
    """Group results by document, keep best chunk per doc, compute boosted score."""
    groups: dict[str, dict] = {}
    for r in results:
        key = r.get("_dedup_key", "")
        if key not in groups:
            groups[key] = {**r, "chunks_matched": 1}
        else:
            groups[key]["chunks_matched"] += 1

    deduped = list(groups.values())
    # Boost score: slight increase for multiple matching chunks
    for r in deduped:
        n = r["chunks_matched"]
        if n > 1:
            r["score"] = round(min(1.0, r["score"] + 0.02 * (n - 1)), 4)
    deduped.sort(key=lambda x: x["score"], reverse=True)
    return deduped


# ── Startup ───────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    global collection, system_prompt, source_index, nid_to_file
    log.info("Loading ChromaDB from %s", CHROMA_DB_PATH)
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    embed_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embed_fn)
    log.info("Collection '%s' ready — %d chunks", COLLECTION_NAME, collection.count())

    # Auto-index fiches if not already present
    try:
        fiches_check = collection.get(where={"source": "fiches"}, limit=1)
        has_fiches = bool(fiches_check and fiches_check["ids"])
    except Exception:
        has_fiches = False
    if not has_fiches and CORPUS_DIR:
        log.info("No fiches in ChromaDB — indexing corpus/ ...")
        n = _index_fiches(collection)
        log.info("Indexed %d fiche chunks", n)

    # Build source file index for linking
    source_index, nid_to_file = _build_source_index()
    log.info("Source index built — %d sources, %d nid mappings",
             len(source_index), len(nid_to_file))

    system_prompt = _build_system_prompt()
    log.info("System prompt built (%d chars)", len(system_prompt))
    if LLM_API_KEY:
        log.info("LLM chat endpoint ready — model=%s", LLM_MODEL)
    else:
        log.warning("LLM_API_KEY not set — /api/chat will return 503")


# ── Search endpoint ───────────────────────────────────────

@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=2),
    top_k: int = Query(20, ge=1, le=100),
    min_score: float = Query(0.3, ge=0.0, le=1.0),
    source: Optional[str] = Query(None, pattern=r"^(dgccrf|particuliers|entreprises|inc|fiches)$"),
    dedupe: bool = Query(True),
):
    if not collection:
        raise HTTPException(503, "ChromaDB not initialised")

    start = time.time()

    # Fetch more chunks when deduplicating so we get enough unique documents
    fetch_k = min(top_k * 3, 100) if dedupe else top_k

    kwargs = {"query_texts": [q], "n_results": fetch_k}
    if source:
        kwargs["where"] = {"source": source}

    raw = collection.query(**kwargs)

    results = []
    if raw["documents"] and raw["documents"][0]:
        for doc, meta, dist in zip(
            raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
        ):
            score = 1.0 - (dist / 2.0)
            if score < min_score:
                continue
            entry = {
                "text": doc,
                "score": round(score, 4),
                "source": meta.get("source", ""),
                "title": meta.get("title", ""),
                "url": meta.get("url", ""),
                "_dedup_key": _dedup_key(meta),
            }
            # Include fiche metadata when available
            if meta.get("taxonomy_id"):
                entry["taxonomy_id"] = meta["taxonomy_id"]
            if meta.get("fiche_path"):
                entry["fiche_path"] = meta["fiche_path"]
            # Resolve source file for linking to sources page
            source_file = _resolve_source_file(meta)
            if source_file:
                entry["source_file"] = source_file
            results.append(entry)

    if dedupe:
        results = _deduplicate(results)
        results = results[:top_k]

    # Remove internal dedup key from output
    for r in results:
        r.pop("_dedup_key", None)

    return {
        "query": q,
        "results": results,
        "total": len(results),
        "execution_time_ms": round((time.time() - start) * 1000, 1),
    }


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "collection": COLLECTION_NAME,
        "chunks": collection.count() if collection else 0,
    }


# ── Sources browsing API ─────────────────────────────────

@app.get("/api/sources")
async def list_sources():
    """List available source corpora with file counts."""
    return {
        "sources": [
            {
                "id": src,
                "label": SOURCE_LABELS.get(src, src),
                "count": len(source_index.get(src, [])),
            }
            for src in SOURCE_LABELS
            if src in source_index
        ]
    }


@app.get("/api/sources/{source_id}")
async def list_source_files(
    source_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: Optional[str] = Query(None, min_length=2),
):
    """List files in a source corpus (paginated, searchable)."""
    if source_id not in source_index:
        raise HTTPException(404, f"Source '{source_id}' not found")

    entries = source_index[source_id]

    # Optional text filter
    if q:
        q_lower = q.lower()
        entries = [e for e in entries if q_lower in e["title"].lower()]

    total = len(entries)
    start_idx = (page - 1) * page_size
    page_entries = entries[start_idx:start_idx + page_size]

    return {
        "source": source_id,
        "label": SOURCE_LABELS.get(source_id, source_id),
        "total": total,
        "page": page,
        "page_size": page_size,
        "files": page_entries,
    }


# ── LLM Chat proxy (server-side API key) ─────────────────


class ChatRequest(BaseModel):
    messages: list[dict]
    temperature: float = 0.9
    max_tokens: int = 320


@app.get("/api/chat/config")
async def chat_config():
    """Returns LLM availability and model name (never the key)."""
    return {
        "available": bool(LLM_API_KEY),
        "model": LLM_MODEL,
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Proxy chat to LLM with server-side API key."""
    if not LLM_API_KEY:
        raise HTTPException(503, "LLM_API_KEY not configured on server")

    payload = {
        "model": LLM_MODEL,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "messages": [{"role": "system", "content": system_prompt}, *req.messages],
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            LLM_ENDPOINT,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LLM_API_KEY}",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(resp.status_code, resp.text[:500])

    return resp.json()
