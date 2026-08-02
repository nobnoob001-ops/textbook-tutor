import json
from collections import defaultdict

import numpy as np

from app import database
from app.config import TOP_K_SOURCES

_RRF_K = 60

_FTS_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "to", "of", "for", "with", "on", "in", "at", "by",
    "from", "as", "that", "which", "who", "whom", "whose", "when", "where",
    "why", "how", "and", "or", "but", "not", "no", "it", "its",
    "কী", "কি", "কেন", "কে", "কাকে", "কোথায়", "কখন", "কিভাবে", "কীভাবে",
    "কোন", "কোনো", "এর", "ও", "এবং", "আর", "হয়ে", "হয়", "আছে", "না",
    "হলে", "করলে", "করা", "করার", "জন্য", "কাছে", "থেকে", "দিয়ে", "মধ্যে",
    "হলো", "হয়েছে",
}

_STOPWORDS_FOLDED = {database.fts_fold(w) for w in _FTS_STOPWORDS} - {""}


def _build_fts_query(text: str) -> str | None:
    tokens = [
        t for t in database.fts_fold(text or "").split() if t not in _STOPWORDS_FOLDED
    ]
    if not tokens:
        return None
    return " AND ".join(f'"{t}"' for t in tokens)


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector / norm if norm > 0 else vector


def _dense_ranked(chunks: list[tuple], query_embedding: list[float]) -> list[tuple]:
    query = _normalize(np.asarray(query_embedding, dtype=np.float32))
    matrix = np.array([json.loads(chunk[3]) for chunk in chunks], dtype=np.float32)
    matrix = np.array([_normalize(row) for row in matrix], dtype=np.float32)
    scores = matrix @ query
    order = np.argsort(-scores)
    return [(chunks[int(i)][0], float(scores[int(i)])) for i in order]


def _format_results(chunks: list[tuple], score_map: dict, ordered_ids: list[int], top_k: int) -> list[dict]:
    by_id = {c[0]: c for c in chunks}
    results = []
    for cid in ordered_ids:
        if len(results) >= top_k:
            break
        if score_map.get(cid, 0.0) <= 0.0:
            continue
        chunk_id, book, content, _, page = by_id[cid]
        results.append(
            {
                "chunk_id": chunk_id,
                "book": book,
                "page": page,
                "text": content[:400],
                "score": round(score_map.get(cid, 0.0), 4),
            }
        )
    return results


def hybrid_rank(
    chunks: list[tuple],
    query_embedding: list[float],
    query_text: str | None,
    top_k: int = TOP_K_SOURCES,
) -> list[dict]:
    """Fuse dense vector search with FTS5 BM25 via Reciprocal Rank Fusion."""
    if not chunks:
        return []
    dense = _dense_ranked(chunks, query_embedding)
    score_map = dict(dense)
    rrf: dict[int, float] = {}
    for rank, (cid, _) in enumerate(dense):
        rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)

    if query_text:
        match = _build_fts_query(query_text)
        if match:
            try:
                valid = {c[0] for c in chunks}
                for rank, cid in enumerate(database.bm25_search(match)):
                    if cid in valid:
                        rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
            except Exception:
                pass

    ordered = sorted(rrf, key=lambda c: -rrf[c])
    return _format_results(chunks, score_map, ordered, top_k)


def rank_chunks(
    chunks: list[tuple],
    query_embedding: list[float],
    top_k: int = TOP_K_SOURCES,
    query_text: str | None = None,
) -> list[dict]:
    if not chunks:
        return []
    if query_text:
        return hybrid_rank(chunks, query_embedding, query_text, top_k)
    dense = _dense_ranked(chunks, query_embedding)
    score_map = dict(dense)
    return _format_results(chunks, score_map, [c[0] for c in dense], top_k)


def rank_chunks_diverse(
    chunks: list[tuple],
    query_embedding: list[float],
    top_k: int = TOP_K_SOURCES,
    query_text: str | None = None,
) -> list[dict]:
    """Rank chunks but keep the answer spread across multiple books when
    more than one book has relevant material (cross-referencing)."""
    if not chunks or top_k <= 1:
        return rank_chunks(chunks, query_embedding, top_k, query_text)
    ranked = rank_chunks(chunks, query_embedding, top_k=top_k * 4, query_text=query_text)
    buckets: dict[str, list] = defaultdict(list)
    for r in ranked:
        buckets[r["book"]].append(r)
    result = []
    while buckets and len(result) < top_k:
        for book in list(buckets):
            if buckets[book]:
                result.append(buckets[book].pop(0))
            if not buckets[book]:
                del buckets[book]
            if len(result) >= top_k:
                break
    return result


def best_match(chunks: list[tuple], query_embedding: list[float]) -> dict | None:
    ranked = rank_chunks(chunks, query_embedding, top_k=1)
    return ranked[0] if ranked else None
