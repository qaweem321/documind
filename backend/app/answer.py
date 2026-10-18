from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

import anthropic
from anthropic.types.beta import BetaMessageParam, BetaRequestDocumentBlockParam

from .config import Settings
from .schemas import Source

SYSTEM_PROMPT = """You answer questions about the user's documents. Each question comes with \
passages retrieved from their library, one document per passage, titled with its source and page.

Base every claim on these passages and cite the passage that supports it. When the passages don't \
answer the question, say so plainly and mention what related information they do contain; don't fill \
the gap from general knowledge. Earlier turns are context for follow-up questions only.

Write concise answers: a direct answer first, then short paragraphs or "- " bullet points when that \
helps. Don't use headings or tables."""


@dataclass(frozen=True)
class TextDelta:
    block: int
    text: str
    kind: Literal["text"] = "text"


@dataclass(frozen=True)
class CitationDelta:
    block: int
    source_index: int
    cited_text: str
    kind: Literal["citation"] = "citation"


@dataclass(frozen=True)
class AnswerError:
    message: str
    kind: Literal["error"] = "error"


AnswerEvent = TextDelta | CitationDelta | AnswerError


@dataclass(frozen=True)
class Turn:
    role: Literal["user", "assistant"]
    content: str


class Answerer(Protocol):
    def stream(
        self, question: str, history: Sequence[Turn], sources: Sequence[Source]
    ) -> AsyncIterator[AnswerEvent]: ...


def source_title(source: Source) -> str:
    return f"{source.document_title} (p. {source.page})" if source.page else source.document_title


def build_messages(
    question: str, history: Sequence[Turn], sources: Sequence[Source]
) -> list[BetaMessageParam]:
    """Earlier turns as plain text, then the new question with one citable document block per
    passage. Citations come back with a document_index, which is the passage's position here."""
    messages: list[BetaMessageParam] = [{"role": t.role, "content": t.content} for t in history]
    documents: list[BetaRequestDocumentBlockParam] = [
        {
            "type": "document",
            "source": {"type": "text", "media_type": "text/plain", "data": s.content},
            "title": source_title(s),
            "citations": {"enabled": True},
        }
        for s in sources
    ]
    messages.append({"role": "user", "content": [*documents, {"type": "text", "text": question}]})
    return messages


class ClaudeAnswerer:
    def __init__(self, settings: Settings, client: anthropic.AsyncAnthropic | None = None) -> None:
        self._settings = settings
        self._client = client or anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, max_retries=2)

    async def stream(
        self, question: str, history: Sequence[Turn], sources: Sequence[Source]
    ) -> AsyncIterator[AnswerEvent]:
        if not sources:
            yield TextDelta(0, "I couldn't find anything about that in your documents.")
            return
        try:
            async with self._client.beta.messages.stream(
                model=self._settings.claude_model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                messages=build_messages(question, history, sources),
                output_config={"effort": self._settings.claude_effort},
                # If a safety classifier declines, the API retries on Anthropic's recommended
                # fallback model within the same stream.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            yield TextDelta(event.index, event.delta.text)
                        elif event.delta.type == "citations_delta":
                            citation = event.delta.citation
                            if citation.type == "char_location":
                                yield CitationDelta(event.index, citation.document_index, citation.cited_text)
                    elif event.type == "message_delta" and event.delta.stop_reason == "refusal":
                        yield AnswerError("Claude declined to answer this question.")
                    elif event.type == "message_delta" and event.delta.stop_reason == "max_tokens":
                        yield AnswerError("The answer was cut off because it got too long.")
        except anthropic.AuthenticationError:
            yield AnswerError("The Anthropic API key is invalid. Check ANTHROPIC_API_KEY.")
        except anthropic.RateLimitError:
            yield AnswerError("Claude is rate-limited right now. Try again in a minute.")
        except anthropic.APIStatusError as error:
            yield AnswerError(f"Claude returned an error ({error.status_code}). Try again.")
        except anthropic.APIConnectionError:
            yield AnswerError("Couldn't reach the Claude API. Check the network and try again.")


class DemoAnswerer:
    """Used when no API key is set: quotes the best passages, with real citations, so search and
    the citation UI can be tried for free."""

    async def stream(
        self, question: str, history: Sequence[Turn], sources: Sequence[Source]
    ) -> AsyncIterator[AnswerEvent]:
        if not sources:
            yield TextDelta(0, "Demo mode: no passages matched this question.")
            return
        block = 0
        yield TextDelta(
            block,
            "Demo mode (no ANTHROPIC_API_KEY set): the most relevant passages instead of a written answer.\n\n",
        )
        for source in sources[:3]:
            excerpt = _first_sentences(source.content)
            block += 1
            yield TextDelta(block, f"- {source_title(source)}: “{excerpt}”")
            yield CitationDelta(block, source.index, excerpt)
            block += 1
            yield TextDelta(block, "\n")


def _first_sentences(text: str, limit: int = 280) -> str:
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat.rfind(". ", 0, limit)
    return flat[: cut + 1] if cut > 80 else flat[:limit].rsplit(" ", 1)[0] + "…"


def create_answerer(settings: Settings) -> Answerer:
    return DemoAnswerer() if settings.demo_mode else ClaudeAnswerer(settings)
