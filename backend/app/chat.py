import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from psycopg.types.json import Jsonb

from .answer import Answerer, AnswerError, CitationDelta, TextDelta, Turn
from .config import Settings
from .embeddings import Embedder
from .ingest import Pool
from .schemas import Citation, Segment, Source
from .search import hybrid_search

NEW_CHAT_TITLE = "New chat"


def sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def retrieval_query(question: str, history: list[Turn]) -> str:
    """Follow-ups like "and for contractors?" only make sense with the previous question, so it
    is searched together with the new one."""
    previous = next((t.content for t in reversed(history) if t.role == "user"), None)
    return f"{previous}\n{question}" if previous else question


class SegmentBuilder:
    """Collects streamed text and citations into segments: one per content block, each with the
    citations that support it."""

    def __init__(self) -> None:
        self._blocks: dict[int, Segment] = {}

    def add(self, event: TextDelta | CitationDelta) -> None:
        segment = self._blocks.setdefault(event.block, Segment(text=""))
        if isinstance(event, TextDelta):
            segment.text += event.text
        else:
            segment.citations.append(Citation(source_index=event.source_index, cited_text=event.cited_text))

    @property
    def segments(self) -> list[Segment]:
        return [self._blocks[k] for k in sorted(self._blocks)]

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.segments)


async def answer_question(
    pool: Pool,
    embedder: Embedder,
    answerer: Answerer,
    settings: Settings,
    conversation_id: UUID,
    document_ids: list[UUID] | None,
    question: str,
) -> AsyncIterator[str]:
    """The server-sent event stream for one question: `sources`, then `text` and `citation`
    events as Claude writes, then `done` (or `error`). The answer is saved even if the browser
    disconnects halfway."""
    async with pool.connection() as conn:
        rows = await (
            await conn.execute(
                "SELECT role, content FROM ("
                "  SELECT role, content, created_at FROM messages WHERE conversation_id = %s"
                "  ORDER BY created_at DESC LIMIT %s"
                ") recent ORDER BY created_at",
                (conversation_id, settings.history_turns * 2),
            )
        ).fetchall()
        history = [Turn(r["role"], str(r["content"])) for r in rows]
        await conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (%s, 'user', %s)",
            (conversation_id, question),
        )
        await conn.execute(
            "UPDATE conversations SET updated_at = now(), title = CASE WHEN title = %s THEN %s ELSE title END "
            "WHERE id = %s",
            (NEW_CHAT_TITLE, _title_from(question), conversation_id),
        )
        sources = await hybrid_search(
            conn, embedder, retrieval_query(question, history), settings.top_k, document_ids
        )

    yield sse("sources", [s.model_dump(mode="json") for s in sources])
    builder = SegmentBuilder()
    error: str | None = None
    try:
        async for event in answerer.stream(question, history, sources):
            if isinstance(event, AnswerError):
                error = event.message
                yield sse("error", {"message": event.message})
                continue
            builder.add(event)
            if isinstance(event, TextDelta):
                yield sse("text", {"block": event.block, "text": event.text})
            else:
                yield sse(
                    "citation",
                    {"block": event.block, "sourceIndex": event.source_index, "citedText": event.cited_text},
                )
    finally:
        # Shielded: if the client disconnects, the partial answer is still stored.
        message_id = await asyncio.shield(_save_answer(pool, conversation_id, builder, sources, error))
    yield sse("done", {"messageId": str(message_id)})


async def _save_answer(
    pool: Pool, conversation_id: UUID, builder: SegmentBuilder, sources: list[Source], error: str | None
) -> UUID:
    text = builder.text or (f"({error})" if error else "")
    async with pool.connection() as conn:
        row = await (
            await conn.execute(
                "INSERT INTO messages (conversation_id, role, content, segments, sources) "
                "VALUES (%s, 'assistant', %s, %s, %s) RETURNING id",
                (
                    conversation_id,
                    text,
                    Jsonb([s.model_dump(mode="json") for s in builder.segments]),
                    Jsonb([s.model_dump(mode="json") for s in sources]),
                ),
            )
        ).fetchone()
        await conn.execute("UPDATE conversations SET updated_at = now() WHERE id = %s", (conversation_id,))
    assert row is not None
    message_id: UUID = row["id"]
    return message_id


def _title_from(question: str) -> str:
    flat = " ".join(question.split())
    return flat if len(flat) <= 60 else flat[:57].rsplit(" ", 1)[0] + "..."
