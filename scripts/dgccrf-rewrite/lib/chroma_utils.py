"""ChromaDB helpers — collection unique, indexation par batch, query avec boost."""

from __future__ import annotations

import logging
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

log = logging.getLogger(__name__)


class ChromaManager:
    """Manages a single ChromaDB collection for all source corpora."""

    def __init__(self, db_path: Path, model_name: str, collection_name: str):
        self.client = chromadb.PersistentClient(path=str(db_path))
        self.embed_fn = SentenceTransformerEmbeddingFunction(
            model_name=model_name,
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def reset_collection(self, collection_name: str):
        """Delete and recreate the collection."""
        try:
            self.client.delete_collection(collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        chunks: list[str],
        metadatas: list[dict],
        ids: list[str],
        batch_size: int = 100,
    ) -> int:
        """Upsert chunks in batches. Returns number of chunks added."""
        total = len(chunks)
        for i in range(0, total, batch_size):
            end = min(i + batch_size, total)
            self.collection.upsert(
                documents=chunks[i:end],
                metadatas=metadatas[i:end],
                ids=ids[i:end],
            )
        return total

    def query(
        self,
        query_text: str,
        top_k: int = 20,
        min_score: float = 0.3,
        where: dict | None = None,
    ) -> list[dict]:
        """Query the collection. Returns list of {text, score, source, title, url}."""
        kwargs = {
            "query_texts": [query_text],
            "n_results": top_k,
        }
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)

        items = []
        if not results["documents"] or not results["documents"][0]:
            return items

        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity score: 1 - (distance / 2)
            score = 1.0 - (dist / 2.0)
            if score < min_score:
                continue
            items.append({
                "text": doc,
                "score": score,
                "source": meta.get("source", ""),
                "title": meta.get("title", ""),
                "url": meta.get("url", ""),
                "nid": meta.get("nid", ""),
                "chunk_index": meta.get("chunk_index", 0),
            })

        return items

    def query_with_boost(
        self,
        query_text: str,
        top_k: int = 20,
        min_score: float = 0.3,
        boost_source: str = "dgccrf",
        boost_factor: float = 1.5,
        max_chars: int = 15000,
    ) -> tuple[list[dict], list[dict]]:
        """
        Query and return results split by source, with DGCCRF boosted.
        Returns: (dgccrf_results, other_results), truncated to max_chars total.
        """
        # Over-fetch to have headroom for boosting
        results = self.query(query_text, top_k=top_k * 2, min_score=min_score)

        # Apply boost and separate
        for r in results:
            if r["source"] == boost_source:
                r["adjusted_score"] = r["score"] * boost_factor
            else:
                r["adjusted_score"] = r["score"]

        # Sort by adjusted score
        results.sort(key=lambda r: r["adjusted_score"], reverse=True)

        # Truncate to max_chars
        dgccrf_results = []
        other_results = []
        total_chars = 0

        for r in results:
            text_len = len(r["text"])
            if total_chars + text_len > max_chars:
                continue
            total_chars += text_len

            if r["source"] == boost_source:
                dgccrf_results.append(r)
            else:
                other_results.append(r)

            if len(dgccrf_results) + len(other_results) >= top_k:
                break

        return dgccrf_results, other_results

    def count(self) -> int:
        return self.collection.count()

    def collection_stats(self) -> dict:
        """Return count by source."""
        total = self.count()
        stats = {"total": total, "by_source": {}}

        # Sample to get source distribution (ChromaDB doesn't have GROUP BY)
        if total == 0:
            return stats

        # Get all metadata (may be slow for very large collections)
        try:
            all_meta = self.collection.get(include=["metadatas"])
            from collections import Counter
            sources = Counter(m.get("source", "unknown") for m in all_meta["metadatas"])
            stats["by_source"] = dict(sources)
        except Exception as e:
            log.warning(f"Could not compute stats: {e}")

        return stats
