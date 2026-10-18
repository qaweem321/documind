from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read from environment variables (and backend/.env). Invalid values stop the app at startup."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(pattern=r"^postgres(ql)?://")
    # Without a key DocuMind runs in demo mode: search still works, answers quote the best passages.
    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-5-5"
    claude_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    # Must produce 384-dimensional vectors (the column size in migrations/001_init.sql).
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    max_upload_mb: int = Field(default=20, ge=1, le=100)
    chunk_size: int = Field(default=500, ge=200, le=4000)
    chunk_overlap: int = Field(default=100, ge=0, le=1000)
    top_k: int = Field(default=8, ge=1, le=30)
    history_turns: int = Field(default=6, ge=0, le=20)
    chat_rate_limit_per_minute: int = Field(default=20, ge=1)
    cors_origins: list[str] = ["http://localhost:3600"]
    seed_examples: bool = False

    @field_validator("anthropic_api_key")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        return value or None

    @property
    def demo_mode(self) -> bool:
        return self.anthropic_api_key is None


@lru_cache
def get_settings() -> Settings:
    return Settings()
