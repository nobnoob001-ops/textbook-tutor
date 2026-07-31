import json

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
