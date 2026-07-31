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
        [json.loads(embedding) for _, _, _, embedding in chunks], dtype=np.float32
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
        _, book, content, _ = chunks[int(idx)]
        results.append(
            {
                "book": book,
                "text": content[:400],
                "score": round(float(scores[idx]), 4),
            }
        )
    return results
