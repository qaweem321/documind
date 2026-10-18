from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class Model(BaseModel):
    """camelCase in JSON for the TypeScript frontend, snake_case in Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, serialize_by_alias=True)


class DocumentOut(Model):
    id: UUID
    title: str
    filename: str
    content_type: str
    size_bytes: int
    page_count: int | None
    chunk_count: int
    status: Literal["processing", "ready", "failed"]
    error: str | None
    created_at: datetime


class UploadResult(Model):
    document: DocumentOut | None = None
    filename: str
    duplicate: bool = False
    error: str | None = None


class Source(Model):
    """A passage retrieved for a question. `index` is its position in the prompt; citations refer to it."""

    index: int
    chunk_id: int
    document_id: UUID
    document_title: str
    page: int | None
    content: str
    score: float


class SearchRequest(Model):
    query: str = Field(min_length=1, max_length=2000)
    document_ids: list[UUID] | None = None
    k: int = Field(default=8, ge=1, le=30)


class Citation(Model):
    source_index: int
    cited_text: str


class Segment(Model):
    text: str
    citations: list[Citation] = []


class MessageOut(Model):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    segments: list[Segment] | None = None
    sources: list[Source] | None = None
    created_at: datetime


class ConversationOut(Model):
    id: UUID
    title: str
    document_ids: list[UUID] | None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class ConversationCreate(Model):
    title: str | None = Field(default=None, max_length=200)
    document_ids: list[UUID] | None = None


class ConversationUpdate(Model):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    document_ids: list[UUID] | None = None


class AskRequest(Model):
    content: str = Field(min_length=1, max_length=4000)


class AppConfig(Model):
    demo_mode: bool
    model: str | None
    max_upload_mb: int
    accepted_extensions: list[str]
