from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from ..chat import NEW_CHAT_TITLE, answer_question
from ..deps import Services, services
from ..schemas import (
    AskRequest,
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    ConversationUpdate,
    MessageOut,
)

router = APIRouter(prefix="/api/conversations")
Deps = Annotated[Services, Depends(services)]

COLUMNS = "id, title, document_ids, created_at, updated_at"


@router.get("")
async def list_conversations(deps: Deps) -> list[ConversationOut]:
    async with deps.pool.connection() as conn:
        rows = await (
            await conn.execute(f"SELECT {COLUMNS} FROM conversations ORDER BY updated_at DESC LIMIT 200")
        ).fetchall()
    return [ConversationOut.model_validate(r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(body: ConversationCreate, deps: Deps) -> ConversationOut:
    async with deps.pool.connection() as conn:
        row = await (
            await conn.execute(
                f"INSERT INTO conversations (title, document_ids) VALUES (%s, %s) RETURNING {COLUMNS}",
                (body.title or NEW_CHAT_TITLE, body.document_ids or None),
            )
        ).fetchone()
    return ConversationOut.model_validate(row)


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: UUID, deps: Deps) -> ConversationDetail:
    async with deps.pool.connection() as conn:
        conversation = await (
            await conn.execute(f"SELECT {COLUMNS} FROM conversations WHERE id = %s", (conversation_id,))
        ).fetchone()
        if conversation is None:
            raise HTTPException(404, "Conversation not found")
        messages = await (
            await conn.execute(
                "SELECT id, role, content, segments, sources, created_at FROM messages "
                "WHERE conversation_id = %s ORDER BY created_at",
                (conversation_id,),
            )
        ).fetchall()
    return ConversationDetail.model_validate(
        {**conversation, "messages": [MessageOut.model_validate(m) for m in messages]}
    )


@router.patch("/{conversation_id}")
async def update_conversation(conversation_id: UUID, body: ConversationUpdate, deps: Deps) -> ConversationOut:
    fields = body.model_dump(exclude_unset=True)
    async with deps.pool.connection() as conn:
        row = await (
            await conn.execute(
                f"UPDATE conversations SET title = COALESCE(%s, title), "
                f"document_ids = CASE WHEN %s THEN %s ELSE document_ids END "
                f"WHERE id = %s RETURNING {COLUMNS}",
                (
                    fields.get("title"),
                    "document_ids" in fields,
                    fields.get("document_ids") or None,
                    conversation_id,
                ),
            )
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Conversation not found")
    return ConversationOut.model_validate(row)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: UUID, deps: Deps) -> None:
    async with deps.pool.connection() as conn:
        result = await conn.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
    if result.rowcount == 0:
        raise HTTPException(404, "Conversation not found")


@router.post("/{conversation_id}/messages")
async def ask(conversation_id: UUID, body: AskRequest, request: Request, deps: Deps) -> StreamingResponse:
    client = request.client.host if request.client else "unknown"
    if not deps.chat_limiter.allow(client):
        raise HTTPException(429, "Too many questions. Wait a minute and try again.")
    async with deps.pool.connection() as conn:
        conversation = await (
            await conn.execute("SELECT document_ids FROM conversations WHERE id = %s", (conversation_id,))
        ).fetchone()
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    stream = answer_question(
        deps.pool,
        deps.embedder,
        deps.answerer,
        deps.settings,
        conversation_id,
        conversation["document_ids"],
        body.content.strip(),
    )
    # no-transform / X-Accel-Buffering: proxies must pass events through as they arrive.
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"cache-control": "no-cache, no-transform", "x-accel-buffering": "no"},
    )
