#!/usr/bin/env python3
"""FastAPI search service — semantic search over ChromaDB corpus + LLM chat proxy."""

import os
import time
import json
import logging
from typing import Optional
from pathlib import Path

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


def _build_system_prompt() -> str:
    """Build system prompt from taxonomie-dgccrf.json."""
    # Try several paths (dev vs Docker)
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


@app.on_event("startup")
async def startup():
    global collection, system_prompt
    log.info("Loading ChromaDB from %s", CHROMA_DB_PATH)
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    embed_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embed_fn)
    log.info("Collection '%s' ready — %d chunks", COLLECTION_NAME, collection.count())

    system_prompt = _build_system_prompt()
    log.info("System prompt built (%d chars)", len(system_prompt))
    if LLM_API_KEY:
        log.info("LLM chat endpoint ready — model=%s", LLM_MODEL)
    else:
        log.warning("LLM_API_KEY not set — /api/chat will return 503")


@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=2),
    top_k: int = Query(20, ge=1, le=100),
    min_score: float = Query(0.3, ge=0.0, le=1.0),
    source: Optional[str] = Query(None, pattern=r"^(dgccrf|particuliers|entreprises|inc|fiches)$"),
):
    if not collection:
        raise HTTPException(503, "ChromaDB not initialised")

    start = time.time()

    kwargs = {"query_texts": [q], "n_results": top_k}
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
            }
            # Include fiche metadata when available
            if meta.get("taxonomy_id"):
                entry["taxonomy_id"] = meta["taxonomy_id"]
            if meta.get("fiche_path"):
                entry["fiche_path"] = meta["fiche_path"]
            results.append(entry)

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
