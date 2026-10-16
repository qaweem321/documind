import re
from typing import Any, Literal
from uuid import UUID

from pgvector import Vector
from psycopg import AsyncConnection

from .embeddings import Embedder
from .schemas import Source

# Candidates taken from each method before fusing, and the Reciprocal Rank Fusion constant.
CANDIDATES = 40
RRF_K = 60

# One round trip: the nearest chunks by meaning (pgvector, HNSW) and the best keyword matches
# (Postgres full-text), fused by Reciprocal Rank Fusion. Each list contributes 1 / (60 + rank),
# so a chunk near the top of both lists beats one that only one method liked, and the two
# scores never need to be on the same scale.
HYBRID_SQL = """
WITH scope AS (
    SELECT id FROM documents
    WHERE status = 'ready' AND (%(document_ids)s::uuid[] IS NULL OR id = ANY(%(document_ids)s::uuid[]))
),
semantic AS (
    SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> %(embedding)s) AS rank
    FROM chunks c
    WHERE c.document_id IN (SELECT id FROM scope)
    ORDER BY c.embedding <=> %(embedding)s
    LIMIT %(semantic_candidates)s
),
keyword AS (
    SELECT c.id, row_number() OVER (ORDER BY ts_rank_cd(c.tsv, q) DESC) AS rank
    FROM chunks c, to_tsquery('english', %(terms)s) q
    WHERE %(terms)s <> '' AND c.tsv @@ q AND c.document_id IN (SELECT id FROM scope)
    ORDER BY ts_rank_cd(c.tsv, q) DESC
    LIMIT %(keyword_candidates)s
),
fused AS (
    SELECT id, sum(1.0 / (%(rrf_k)s + rank)) AS score, min(semantic_rank) AS semantic_rank
    FROM (
        SELECT id, rank, rank AS semantic_rank FROM semantic
        UNION ALL
        SELECT id, rank, NULL FROM keyword
    ) ranked
    GROUP BY id
)
SELECT c.id AS chunk_id, c.document_id, d.title AS document_title, c.page, c.content, f.score
FROM fused f
JOIN chunks c ON c.id = f.id
JOIN documents d ON d.id = c.document_id
ORDER BY f.score DESC, f.semantic_rank NULLS LAST, c.id
LIMIT %(k)s
"""


def keyword_terms(query: str) -> str:
    """Any of the query's words may match ("refund | policy | days"). Questions rarely contain
    every word of the passage that answers them, so AND would miss too much. Postgres drops
    stop words and stems the rest."""
    words = re.findall(r"[A-Za-z0-9]+", query.lower())
    return " | ".join(dict.fromkeys(words))[:2000]


async def hybrid_search(
    conn: AsyncConnection[dict[str, Any]],
    embedder: Embedder,
    query: str,
    k: int,
    document_ids: list[UUID] | None = None,
    mode: Literal["hybrid", "semantic", "keyword"] = "hybrid",
) -> list[Source]:
    """`mode` turns one method off; used by the retrieval evaluation to compare them."""
    embedding = await embedder.embed_query(query)
    cursor = await conn.execute(
        HYBRID_SQL,
        {
            "embedding": Vector(embedding),
            "terms": keyword_terms(query),
            "document_ids": document_ids,
            "semantic_candidates": 0 if mode == "keyword" else CANDIDATES,
            "keyword_candidates": 0 if mode == "semantic" else CANDIDATES,
            "rrf_k": RRF_K,
            "k": k,
        },
    )
    rows = await cursor.fetchall()
    return [Source(index=i, **row) for i, row in enumerate(rows)]
