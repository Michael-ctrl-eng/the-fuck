"""Tenant-scoped semantic memory search.

Production: pgvector cosine similarity (HNSW index created by migration).
SQLite sandbox: in-process cosine similarity over the JSON column. Both
paths return the same shape; the DB is the source of truth either way.
"""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .. import metrics


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def search_memory(
    db: AsyncSession,
    org_id: str,
    query_vector: list[float],
    *,
    limit: int = 10,
    min_score: float = 0.35,
    dialect: str | None = None,
    intent: str | None = None,
) -> list[dict[str, Any]]:
    metrics.RETRIEVAL_CALLS.inc()
    if db.bind and db.bind.dialect.name == "postgresql":
        sql = text(
            """
            SELECT id, chunk_text, conversation_id,
                   1 - (embedding <=> :qv) AS score
            FROM memory_chunks
            WHERE org_id = :org_id
              AND embedding IS NOT NULL
              AND 1 - (embedding <=> :qv) >= :min_score
              AND (:dialect IS NULL OR TRUE)
            ORDER BY embedding <=> :qv
            LIMIT :limit
            """
        )
        rows = await db.execute(
            sql,
            {"qv": query_vector, "org_id": org_id, "min_score": min_score, "limit": limit},
        )
        return [dict(r._mapping) for r in rows]

    # SQLite fallback: load chunks and score in Python.
    from sqlalchemy import select

    from .. import models

    rows = await db.execute(
        select(models.MemoryChunk).where(
            models.MemoryChunk.org_id == org_id,
            models.MemoryChunk.embedding.is_not(None),
        )
    )
    scored = []
    for chunk in rows.scalars().all():
        score = _cosine(query_vector, chunk.embedding or [])
        if score >= min_score:
            scored.append(
                {
                    "id": chunk.id,
                    "chunk_text": chunk.chunk_text,
                    "conversation_id": chunk.conversation_id,
                    "score": round(score, 4),
                }
            )
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:limit]
