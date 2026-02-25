#!/usr/bin/env python3
"""FastAPI search service — semantic search over ChromaDB corpus."""

import os
import time
import logging
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "../chroma_db")
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "dgccrf_corpus")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")

app = FastAPI(title="Portail Conso Search API")

# CORS is handled by nginx (or serve.py in dev) — no middleware here
# to avoid duplicate Access-Control-Allow-Origin headers.

# Globals initialised at startup
collection = None


@app.on_event("startup")
async def startup():
    global collection
    log.info("Loading ChromaDB from %s", CHROMA_DB_PATH)
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    embed_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embed_fn)
    log.info("Collection '%s' ready — %d chunks", COLLECTION_NAME, collection.count())


@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=2),
    top_k: int = Query(20, ge=1, le=100),
    min_score: float = Query(0.3, ge=0.0, le=1.0),
    source: Optional[str] = Query(None, pattern=r"^(dgccrf|particuliers|entreprises|inc)$"),
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
            results.append({
                "text": doc,
                "score": round(score, 4),
                "source": meta.get("source", ""),
                "title": meta.get("title", ""),
                "url": meta.get("url", ""),
            })

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
