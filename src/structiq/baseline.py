"""
The flat-RAG baseline — deliberately the WEAK contrast for the demo.

Flat semantic retrieval over IS 456 text returns clause *paragraphs* that look relevant,
but it cannot connect "beam B3 has 2-T10" to "0.85·b·d/fy" and produce a verdict. That
gap is exactly what the graph traversal closes.

Uses ChromaDB + sentence-transformers when available; otherwise falls back to a keyword
match over the seeded clause text so the contrast panel still has something to show.
"""
from __future__ import annotations

import os
from typing import Optional

from . import standards

_COLLECTION = None
_CHUNKS: list[str] = []


def _seed_chunks() -> list[str]:
    out = []
    for c in standards.SEED_CLAUSES:
        out.append(f"IS 456 Clause {c.clause_id} {c.title}. {c.applicability}. "
                   f"Formula: {c.formula}.")
    return out


def _ensure_index(pdf_path: Optional[str] = None) -> None:
    global _COLLECTION, _CHUNKS
    if _CHUNKS:
        return
    _CHUNKS = _seed_chunks()
    if pdf_path:
        _CHUNKS += standards.enrich_from_pdf(pdf_path)

    try:
        import chromadb
        from chromadb.utils import embedding_functions

        client = chromadb.Client()
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2")
        col = client.get_or_create_collection("is456", embedding_function=ef)
        if col.count() == 0:
            col.add(documents=_CHUNKS, ids=[f"c{i}" for i in range(len(_CHUNKS))])
        _COLLECTION = col
    except Exception:
        _COLLECTION = None  # fall back to keyword search


def query(q: str, k: int = 3, pdf_path: Optional[str] = None) -> dict:
    """Return the top-k raw chunks flat-RAG would surface — no verdict, by design."""
    _ensure_index(pdf_path or os.environ.get("IS456_PDF"))

    if _COLLECTION is not None:
        res = _COLLECTION.query(query_texts=[q], n_results=k)
        hits = res.get("documents", [[]])[0]
    else:
        ql = q.lower()
        scored = sorted(_CHUNKS, key=lambda c: -sum(w in c.lower() for w in ql.split()))
        hits = scored[:k]

    return {
        "query": q,
        "mode": "vector" if _COLLECTION is not None else "keyword-fallback",
        "hits": hits,
        "note": "Flat retrieval returns clause text but cannot bind it to a specific "
                "member's rebar or return a pass/fail verdict.",
    }
