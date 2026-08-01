import json
from collections import defaultdict

import numpy as np

from app.config import TOP_K_SOURCES


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector / norm if norm > 0 else vector


def rank_chunks(
    chunks: list[tuple], query_embedding: list[float], top_k: int = TOP_K_SOURCES
) -> list[dict]:
    if not chunks:
        return []
    query = _normalize(np.asarray(query_embedding, dtype=np.float32))
    matrix = np.array(
        [json.loads(chunk[3]) for chunk in chunks], dtype=np.float32
    )
    matrix = np.array([_normalize(row) for row in matrix], dtype=np.float32)
    scores = matrix @ query
    order = np.argsort(-scores)

    results = []
    for idx in order:
        if len(results) >= top_k:
            break
        if float(scores[idx]) <= 0.0:
            continue
        chunk_id, book, content, _, page = chunks[int(idx)]
        results.append(
            {
                "chunk_id": chunk_id,
                "book": book,
                "page": page,
                "text": content[:400],
                "score": round(float(scores[idx]), 4),
            }
        )
    return results


def rank_chunks_diverse(
    chunks: list[tuple], query_embedding: list[float], top_k: int = TOP_K_SOURCES
) -> list[dict]:
    """Rank chunks but keep the answer spread across multiple books when
    more than one book has relevant material (cross-referencing)."""
    if not chunks or top_k <= 1:
        return rank_chunks(chunks, query_embedding, top_k)
    ranked = rank_chunks(chunks, query_embedding, top_k=top_k * 4)
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
