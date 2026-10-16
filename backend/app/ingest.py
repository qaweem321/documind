import asyncio
import hashlib
import logging
from typing import Any
from uuid import UUID

from pgvector import Vector
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from .chunking import split_pages
from .config import Settings
from .embeddings import BATCH_SIZE, Embedder
from .extract import UnsupportedFile, extract_pages, title_from

log = logging.getLogger(__name__)

Pool = AsyncConnectionPool[AsyncConnection[dict[str, Any]]]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def process_document(pool: Pool, embedder: Embedder, settings: Settings, document_id: UUID) -> None:
    """Extracts, splits and embeds one document, then stores its chunks in one transaction.
    Any earlier partial chunks are replaced, so a document can safely be processed again."""
    async with pool.connection() as conn:
        row = await (
            await conn.execute(
                "SELECT d.filename, d.content_type, f.data FROM documents d JOIN document_files f ON f.document_id = d.id "
                "WHERE d.id = %s",
                (document_id,),
            )
        ).fetchone()
    if row is None:
        return  # deleted while queued
    try:
        pages = extract_pages(bytes(row["data"]), str(row["content_type"]))
        chunks = split_pages(pages, settings.chunk_size, settings.chunk_overlap)
        vectors: list[list[float]] = []
        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start : start + BATCH_SIZE]
            vectors.extend(await embedder.embed_documents([c.content for c in batch]))
    except UnsupportedFile as error:
        await _fail(pool, document_id, str(error))
        return
    except Exception:
        log.exception("processing document %s failed", document_id)
        await _fail(pool, document_id, "Processing failed. Try uploading the file again.")
        return

    page_count = max((p.number or 0 for p in pages), default=0) or None
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
        async with conn.cursor().copy(
            "COPY chunks (document_id, ordinal, page, content, embedding) FROM STDIN WITH (FORMAT BINARY)"
        ) as copy:
            copy.set_types(["uuid", "int4", "int4", "text", "vector"])
            for chunk, vector in zip(chunks, vectors, strict=True):
                await copy.write_row((document_id, chunk.ordinal, chunk.page, chunk.content, Vector(vector)))
        await conn.execute(
            "UPDATE documents SET status = 'ready', error = NULL, chunk_count = %s, page_count = %s, title = %s "
            "WHERE id = %s",
            (len(chunks), page_count, title_from(str(row["filename"]), pages), document_id),
        )
    log.info("document %s ready: %d chunks", document_id, len(chunks))


async def _fail(pool: Pool, document_id: UUID, message: str) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE documents SET status = 'failed', error = %s WHERE id = %s", (message, document_id)
        )


class IngestQueue:
    """Processes uploads one at a time in the background, so the upload request returns at once
    and embedding (CPU-heavy) never runs for several files in parallel. Documents still marked
    "processing" at startup (the app stopped mid-way) are queued again."""

    def __init__(self, pool: Pool, embedder: Embedder, settings: Settings) -> None:
        self._pool, self._embedder, self._settings = pool, embedder, settings
        self._queue: asyncio.Queue[UUID] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute("SELECT id FROM documents WHERE status = 'processing'")
            ).fetchall()
        for row in rows:
            self.put(row["id"])
        self._task = asyncio.create_task(self._run())

    def put(self, document_id: UUID) -> None:
        self._queue.put_nowait(document_id)

    async def join(self) -> None:
        await self._queue.join()

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _run(self) -> None:
        while True:
            document_id = await self._queue.get()
            try:
                await process_document(self._pool, self._embedder, self._settings, document_id)
            except Exception:
                log.exception("ingest worker error for %s", document_id)
            finally:
                self._queue.task_done()
