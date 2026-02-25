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

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import frontmatter
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from starlette.responses import StreamingResponse
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
taxonomy_data: dict = {}  # raw JSON from taxonomie-dgccrf.json
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
    global collection, system_prompt, taxonomy_data, source_index, nid_to_file
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

    # Load raw taxonomy for agent module
    for p in [
        Path(__file__).resolve().parent.parent / "taxonomie-dgccrf.json",
        Path("/usr/share/nginx/html/taxonomie-dgccrf.json"),
    ]:
        if p.exists():
            taxonomy_data = json.loads(p.read_text(encoding="utf-8"))
            log.info("Taxonomy loaded — %d domaines", len(taxonomy_data.get("domaines", [])))
            break

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


# ── RAG context retrieval ─────────────────────────────────


def _query_rag_context(
    query: str, top_k: int = 5, min_score: float = 0.4
) -> list[dict]:
    """Query ChromaDB for relevant corpus chunks to inject as context."""
    if not collection:
        return []
    try:
        raw = collection.query(query_texts=[query], n_results=top_k * 3)
    except Exception as e:
        log.warning("RAG query failed: %s", e)
        return []

    seen_keys: set[str] = set()
    results = []
    if raw["documents"] and raw["documents"][0]:
        for doc, meta, dist in zip(
            raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
        ):
            score = 1.0 - (dist / 2.0)
            if score < min_score:
                continue
            # Deduplicate by document
            key = _dedup_key(meta)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            results.append({
                "text": doc[:500],
                "score": round(score, 4),
                "source": meta.get("source", ""),
                "title": meta.get("title", ""),
            })
            if len(results) >= top_k:
                break
    return results


def _build_rag_system_prompt(
    base_prompt: str, rag_results: list[dict]
) -> str:
    """Inject RAG context into the system prompt."""
    if not rag_results:
        return base_prompt

    ctx_lines = []
    for i, r in enumerate(rag_results, 1):
        src = r["source"].upper()
        title = r["title"]
        text = r["text"].replace("\n", " ").strip()
        ctx_lines.append(f'[{i}] (source: {src}, titre: "{title}") — "{text}"')

    ctx_block = "\n".join(ctx_lines)

    # Insert CONTEXTE CORPUS section before REGLES STRICTES
    marker = "REGLES STRICTES :"
    if marker in base_prompt:
        return base_prompt.replace(
            marker,
            f"""CONTEXTE CORPUS (extraits pertinents de la base de connaissances — utilise-les pour mieux identifier la situation) :
{ctx_block}

{marker}""",
        )
    # Fallback: append at the end
    return base_prompt + f"\n\nCONTEXTE CORPUS :\n{ctx_block}"


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
    """Proxy chat to LLM with server-side API key + RAG context."""
    if not LLM_API_KEY:
        raise HTTPException(503, "LLM_API_KEY not configured on server")

    # Extract latest user message for RAG query
    user_messages = [m for m in req.messages if m.get("role") == "user"]
    latest_query = user_messages[-1]["content"] if user_messages else ""

    # Query ChromaDB for relevant context
    rag_results = _query_rag_context(latest_query) if latest_query else []

    # Build enriched system prompt
    enriched_prompt = _build_rag_system_prompt(system_prompt, rag_results)

    payload = {
        "model": LLM_MODEL,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "messages": [{"role": "system", "content": enriched_prompt}, *req.messages],
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

    # Attach RAG metadata to response
    data = resp.json()
    if rag_results:
        data["_rag_sources"] = [
            {"source": r["source"], "title": r["title"], "score": r["score"]}
            for r in rag_results
        ]

    return data


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Stream chat response via SSE — same logic as /api/chat but token-by-token."""
    if not LLM_API_KEY:
        raise HTTPException(503, "LLM_API_KEY not configured on server")

    # Extract latest user message for RAG query
    user_messages = [m for m in req.messages if m.get("role") == "user"]
    latest_query = user_messages[-1]["content"] if user_messages else ""
    rag_results = _query_rag_context(latest_query) if latest_query else []
    enriched_prompt = _build_rag_system_prompt(system_prompt, rag_results)

    payload = {
        "model": LLM_MODEL,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "stream": True,
        "messages": [{"role": "system", "content": enriched_prompt}, *req.messages],
    }

    async def event_generator():
        # Send RAG sources as first event
        if rag_results:
            sources = [
                {"source": r["source"], "title": r["title"], "score": r["score"]}
                for r in rag_results
            ]
            yield f"event: rag_sources\ndata: {json.dumps(sources, ensure_ascii=False)}\n\n"

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                LLM_ENDPOINT,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {LLM_API_KEY}",
                },
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    yield f"event: error\ndata: {json.dumps({'error': body.decode()[:500]})}\n\n"
                    return

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield f"event: chunk\ndata: {json.dumps({'text': content}, ensure_ascii=False)}\n\n"
                    except json.JSONDecodeError:
                        continue

        yield f"event: done\ndata: {{}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Agent multi-step endpoint ────────────────────────────

try:
    from api.agent import Phase, get_or_create_session, find_situation, build_actions, build_answer_prompt
except ImportError:
    from agent import Phase, get_or_create_session, find_situation, build_actions, build_answer_prompt


def _load_fiche(situation_id: str) -> str:
    """Load fiche markdown content for a situation from corpus directory."""
    if not CORPUS_DIR or not taxonomy_data:
        return ""
    info = find_situation(taxonomy_data, situation_id)
    if not info:
        return ""

    sit = info["situation"]
    ss = info["sous_domaine"]
    dom = info["domaine"]

    if sit.get("is_transversale"):
        path = CORPUS_DIR / "transversales" / f"{situation_id}.md"
    elif dom and ss:
        path = CORPUS_DIR / dom["id"] / ss["id"] / f"{situation_id}.md"
    else:
        return ""

    if path.exists():
        try:
            post = frontmatter.loads(path.read_text(encoding="utf-8"))
            return post.content
        except Exception:
            return ""
    return ""


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _parse_clarification_options(question: str) -> list[str]:
    """Extract options from a clarification question like 'X ou Y ?'."""
    q = re.sub(r"\s*\?\s*$", "", question).strip()
    if " ou " not in q:
        return []
    # Split on last " ou " to handle "A, B ou C"
    idx = q.rfind(" ou ")
    left, right = q[:idx], q[idx + 4:]
    right = right.strip().rstrip(".")
    if "," in left:
        # "A, B ou C" → find the comma-separated tail
        parts = left.rsplit(",", 1)
        prefix = parts[0]
        last_comma_part = parts[1].strip()
        # Only take what's after the last sentence structure
        options = [last_comma_part, right]
    else:
        # "X ou Y" — take just the last few words of each side
        # E.g. "en ligne ou en magasin" → ["En ligne", "En magasin"]
        left_words = left.split()
        # Take at most last 3 words from left side
        option_left = " ".join(left_words[-3:]) if len(left_words) > 3 else left
        options = [option_left, right]
    return [o.strip().capitalize() for o in options if o.strip()]


class AgentChatRequest(BaseModel):
    session_id: str | None = None
    messages: list[dict]
    temperature: float = 0.3
    max_tokens: int = 800


@app.post("/api/agent/chat")
async def agent_chat(req: AgentChatRequest):
    """Multi-step agent: classify → clarify → answer → action, streamed via SSE."""
    if not LLM_API_KEY:
        raise HTTPException(503, "LLM_API_KEY not configured on server")

    session = get_or_create_session(req.session_id)
    session.turn_count += 1

    # Get latest user message for RAG
    user_messages = [m for m in req.messages if m.get("role") == "user"]
    latest_query = user_messages[-1]["content"] if user_messages else ""
    rag_results = _query_rag_context(latest_query) if latest_query else []

    async def _llm_call_blocking(sys_prompt: str, messages: list[dict],
                                  temperature: float = 0.3, max_tokens: int = 320) -> dict:
        """Make a blocking LLM call, return parsed response."""
        payload = {
            "model": LLM_MODEL,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": sys_prompt}, *messages],
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                LLM_ENDPOINT, json=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {LLM_API_KEY}"},
            )
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, resp.text[:500])
        return resp.json()

    async def event_generator():
        # If in CLARIFY phase, user just responded — reclassify
        if session.phase == Phase.CLARIFY:
            session.phase = Phase.CLASSIFY

        # ── CLASSIFY phase ───────────────────────────────
        if session.phase == Phase.CLASSIFY:
            # RAG context is NOT injected here — it made the LLM too
            # hesitant, always returning clarification instead of committing
            # to a situation_id. RAG is used later in the ANSWER phase.
            data = await _llm_call_blocking(system_prompt, req.messages, req.temperature, 320)
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Parse JSON result
            try:
                match = re.search(r"\{[\s\S]*\}", content)
                result = json.loads(match.group(0)) if match else {}
            except (json.JSONDecodeError, AttributeError):
                yield _sse_event("error", {"error": "Classification JSON invalide"})
                yield _sse_event("done", {"session_id": session.id})
                return

            session.classify_result = result
            yield _sse_event("phase", {"phase": "classify", **result})

            # Handle hors_perimetre
            if result.get("hors_perimetre"):
                yield _sse_event("done", {"session_id": session.id})
                return

            # Handle LLM clarification question
            if result.get("question_clarification"):
                session.phase = Phase.CLARIFY
                session.candidates = result.get("candidate_situation_ids", [])
                options = _parse_clarification_options(result["question_clarification"])
                yield _sse_event("phase", {
                    "phase": "clarify",
                    "question": result["question_clarification"],
                    "candidates": session.candidates,
                    "options": options,
                })
                yield _sse_event("done", {"session_id": session.id})
                return

            # Situation found
            if result.get("situation_id"):
                session.situation_id = result["situation_id"]
                info = find_situation(taxonomy_data, session.situation_id)
                if info:
                    session.situation_label = info["situation"].get("label", "")
                    session.domaine_label = info["domaine"].get("label", "") if info["domaine"] else ""
                    session.ss_label = info["sous_domaine"].get("label", "") if info["sous_domaine"] else ""

                    # Check question_pivot
                    sc = info["situation"].get("signalconso") or {}
                    if sc.get("question_pivot") and not session.pivot_asked:
                        session.pivot_asked = True
                        session.phase = Phase.CLARIFY
                        # Extract options from url_signalement_alt keys
                        pivot_options = []
                        alt = sc.get("url_signalement_alt") or {}
                        for key in alt:
                            label = key.replace("url_signalement_", "").replace("_", " ").strip()
                            if label:
                                pivot_options.append(label.capitalize())
                        if not pivot_options:
                            pivot_options = _parse_clarification_options(sc["question_pivot"])
                        yield _sse_event("phase", {
                            "phase": "clarify",
                            "question": sc["question_pivot"],
                            "type": "pivot",
                            "situation_id": session.situation_id,
                            "options": pivot_options,
                        })
                        yield _sse_event("done", {"session_id": session.id})
                        return

                # Proceed to ANSWER
                session.phase = Phase.ANSWER
            else:
                # No situation, no clarification — inconclusive
                yield _sse_event("done", {"session_id": session.id})
                return

        # ── ANSWER phase ─────────────────────────────────
        if session.phase == Phase.ANSWER:
            # Enrich RAG with situation label
            if session.situation_label:
                answer_rag = _query_rag_context(
                    f"{session.situation_label} {latest_query}", top_k=5, min_score=0.35
                )
            else:
                answer_rag = rag_results
            session.rag_chunks = answer_rag

            # Load fiche content
            fiche_content = _load_fiche(session.situation_id) if session.situation_id else ""

            # Build answer prompt
            answer_prompt = build_answer_prompt(session, answer_rag, fiche_content)

            yield _sse_event("phase", {
                "phase": "answer",
                "situation_id": session.situation_id,
                "situation_label": session.situation_label,
            })

            # Stream LLM answer
            payload = {
                "model": LLM_MODEL,
                "temperature": req.temperature,
                "max_tokens": req.max_tokens,
                "stream": True,
                "messages": [{"role": "system", "content": answer_prompt}, *req.messages],
            }

            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST", LLM_ENDPOINT, json=payload,
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {LLM_API_KEY}"},
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        yield _sse_event("error", {"error": body.decode()[:500]})
                        yield _sse_event("done", {"session_id": session.id})
                        return

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield _sse_event("chunk", {"text": content})
                        except json.JSONDecodeError:
                            continue

            # Send source citations
            sources = [
                {"source": r["source"], "title": r["title"], "score": r["score"]}
                for r in answer_rag
            ]
            yield _sse_event("sources", {"sources": sources})

            session.phase = Phase.ACTION

        # ── ACTION phase ─────────────────────────────────
        if session.phase == Phase.ACTION and session.situation_id:
            actions = build_actions(taxonomy_data, session.situation_id)
            yield _sse_event("phase", {"phase": "action", **actions})

        yield _sse_event("done", {"session_id": session.id})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
