"""Retrieval evaluation: does search put the passage that answers a question near the top?

Loads examples/*.md with the real embedding model into the database in DATABASE_URL (use a
scratch database: its documents are replaced), then asks each question below and checks
whether a passage containing the expected text is ranked first (hit@1) or in the top 5
(recall@5), for keyword-only, semantic-only and hybrid search.

    DATABASE_URL=postgresql://documind:documind@localhost:5434/documind_test uv run python -m evals.retrieval
"""

import asyncio
import os
from pathlib import Path

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.config import Settings
from app.db import create_pool, run_migrations
from app.embeddings import FastEmbedder
from app.ingest import process_document, sha256
from app.search import hybrid_search

# (question, text the answering passage must contain). Phrased the way people ask, mostly
# without the policy's own wording.
CASES = [
    ("Can I work from Spain for two months?", "more than 30 days"),
    ("Do I need permission for a one week holiday abroad?", "Short trips abroad"),
    ("How much money do I get to set up my desk at home?", "$1,500"),
    ("Will the company pay for my internet?", "$60 a month"),
    ("What happens to my laptop when I quit?", "returned within 10 business days"),
    ("Can I rent a desk in a shared office?", "coworking space"),
    ("When are meetings supposed to happen?", "core hours"),
    ("How long do I have to file a receipt?", "within 60 days"),
    ("Who signs off on a $5,000 purchase?", "above $2,000"),
    ("Can I fly business class to Tokyo?", "longer than 8 hours"),
    ("What is the nightly hotel cap in London?", "$350 a night"),
    ("Is wine at dinner covered?", "Alcohol is not reimbursed"),
    ("How much is the food allowance on a trip?", "$90 a day"),
    ("Do I need a receipt for a $40 taxi?", "under $75"),
    ("What should I do if I clicked a phishing link?", "#security-incidents"),
    ("Can I keep a copy of the customer database on my laptop for debugging?", "anonymized staging database"),
    ("How long does production database access last?", "24 hours"),
    ("Which accounts need a hardware key?", "Hardware security keys"),
    ("Can I read work email on my own phone?", "Personal"),
    ("How fast must my screen lock?", "five minutes"),
]

MODES = ("keyword", "semantic", "hybrid")


async def main() -> None:
    url = os.environ["DATABASE_URL"]
    settings = Settings(database_url=url, chunk_size=int(os.environ.get("CHUNK_SIZE", "500")))
    await run_migrations(url)
    pool = create_pool(url)
    await pool.open(wait=True)
    embedder = FastEmbedder(settings.embedding_model)
    async with pool.connection() as conn:
        await conn.execute("TRUNCATE documents CASCADE")
        for path in sorted((Path(__file__).parent.parent / "examples").glob("*.md")):
            data = path.read_bytes()
            row = await (
                await conn.execute(
                    "INSERT INTO documents (title, filename, content_type, sha256, size_bytes) "
                    "VALUES (%s, %s, 'text/markdown', %s, %s) RETURNING id",
                    (path.stem, path.name, sha256(data), len(data)),
                )
            ).fetchone()
            assert row is not None
            await conn.execute(
                "INSERT INTO document_files (document_id, data) VALUES (%s, %s)", (row["id"], data)
            )
    async with pool.connection() as conn:
        ids = [r["id"] for r in await (await conn.execute("SELECT id FROM documents")).fetchall()]
    for document_id in ids:
        await process_document(pool, embedder, settings, document_id)

    print(f"{len(CASES)} questions over {len(ids)} documents\n")
    print(f"{'mode':<10}{'hit@1':>8}{'recall@5':>10}")
    async with await AsyncConnection.connect(url, row_factory=dict_row) as conn:
        from pgvector.psycopg import register_vector_async

        await register_vector_async(conn)
        for mode in MODES:
            hits = recalls = 0
            for question, expected in CASES:
                results = await hybrid_search(conn, embedder, question, 5, mode=mode)  # type: ignore[arg-type]
                ranks = [i for i, r in enumerate(results) if expected in r.content]
                hits += bool(ranks and ranks[0] == 0)
                if os.environ.get("VERBOSE") and not (ranks and ranks[0] == 0):
                    print(f"  {mode} miss: {question!r} -> {results[0].content[:70]!r}")
                recalls += bool(ranks)
            print(f"{mode:<10}{hits / len(CASES):>8.0%}{recalls / len(CASES):>10.0%}")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
