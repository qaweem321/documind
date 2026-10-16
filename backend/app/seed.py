import logging
from pathlib import Path

from .extract import content_type_for, title_from
from .ingest import IngestQueue, Pool, sha256

log = logging.getLogger(__name__)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


async def seed_examples(pool: Pool, ingest: IngestQueue) -> int:
    """Adds the sample handbook in examples/ when the library is empty (SEED_EXAMPLES=true)."""
    async with pool.connection() as conn:
        if await (await conn.execute("SELECT 1 FROM documents LIMIT 1")).fetchone():
            return 0
        added = 0
        for path in sorted(EXAMPLES.glob("*.md")):
            data = path.read_bytes()
            row = await (
                await conn.execute(
                    "INSERT INTO documents (title, filename, content_type, sha256, size_bytes) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (
                        title_from(path.name, []),
                        path.name,
                        content_type_for(path.name, data),
                        sha256(data),
                        len(data),
                    ),
                )
            ).fetchone()
            assert row is not None
            await conn.execute(
                "INSERT INTO document_files (document_id, data) VALUES (%s, %s)", (row["id"], data)
            )
            ingest.put(row["id"])
            added += 1
    log.info("seeded %d example documents", added)
    return added
