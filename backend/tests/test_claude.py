"""The Claude answerer against the real SDK, with the HTTP layer replaced by a recorded stream."""

import asyncio
import json
from typing import Any

import anthropic
import httpx2

from app.answer import AnswerEvent, ClaudeAnswerer
from app.config import Settings
from app.schemas import Source

SOURCE = Source(
    index=0,
    chunk_id=1,
    document_id="00000000-0000-0000-0000-000000000001",
    document_title="Remote Work Policy",
    page=None,
    content="Laptops must be returned within 10 business days after your last day.",
    score=0.5,
)


def sse_body(events: list[dict[str, Any]]) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def stream_events(stop_reason: str = "end_turn") -> list[dict[str, Any]]:
    citation = {
        "type": "char_location",
        "cited_text": "Laptops must be returned within 10 business days",
        "document_index": 0,
        "document_title": "Remote Work Policy",
        "start_char_index": 0,
        "end_char_index": 48,
    }
    return [
        {
            "type": "message_start",
            "message": {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "claude-opus-5-5",
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 0},
            },
        },
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Within "}},
        {"type": "content_block_stop", "index": 0},
        {
            "type": "content_block_start",
            "index": 1,
            "content_block": {"type": "text", "text": "", "citations": []},
        },
        {
            "type": "content_block_delta",
            "index": 1,
            "delta": {"type": "citations_delta", "citation": citation},
        },
        {
            "type": "content_block_delta",
            "index": 1,
            "delta": {"type": "text_delta", "text": "10 business days"},
        },
        {"type": "content_block_stop", "index": 1},
        {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": 9},
        },
        {"type": "message_stop"},
    ]


def run(handler: Any, settings: Settings | None = None) -> tuple[list[AnswerEvent], list[httpx2.Request]]:
    requests: list[httpx2.Request] = []

    def record(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        response: httpx2.Response = handler(request)
        return response

    client = anthropic.AsyncAnthropic(
        api_key="sk-test",
        max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(record)),
    )
    answerer = ClaudeAnswerer(
        settings or Settings(database_url="postgresql://x", anthropic_api_key="sk-test"), client
    )

    async def collect() -> list[AnswerEvent]:
        return [e async for e in answerer.stream("When do I return my laptop?", [], [SOURCE])]

    return asyncio.run(collect()), requests


def streamed(events: list[dict[str, Any]]) -> Any:
    return lambda _request: httpx2.Response(
        200, headers={"content-type": "text/event-stream"}, content=sse_body(events)
    )


def test_streams_text_and_maps_citations_to_passages() -> None:
    events, requests = run(streamed(stream_events()))
    assert [(e.kind, getattr(e, "block", None)) for e in events] == [
        ("text", 0),
        ("citation", 1),
        ("text", 1),
    ]
    citation = events[1]
    assert citation.source_index == 0  # type: ignore[union-attr]

    body = json.loads(requests[0].content)
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert body["output_config"] == {"effort": "medium"}
    assert body["stream"] is True
    document = body["messages"][-1]["content"][0]
    assert document["type"] == "document" and document["citations"] == {"enabled": True}
    assert requests[0].headers["anthropic-beta"] == "server-side-fallback-2026-07-01"


def test_reports_refusals() -> None:
    events, _ = run(streamed(stream_events(stop_reason="refusal")))
    assert events[-1].kind == "error"
    assert "declined" in events[-1].message  # type: ignore[union-attr]


def test_turns_api_errors_into_readable_messages() -> None:
    error = {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}
    events, _ = run(lambda _r: httpx2.Response(401, json=error))
    assert [e.kind for e in events] == ["error"]
    assert "API key is invalid" in events[0].message  # type: ignore[union-attr]


def test_no_passages_means_no_api_call() -> None:
    answerer = ClaudeAnswerer(Settings(database_url="postgresql://x", anthropic_api_key="sk-test"))

    async def collect() -> list[AnswerEvent]:
        return [e async for e in answerer.stream("q", [], [])]

    events = asyncio.run(collect())
    assert events[0].text.startswith("I couldn't find")  # type: ignore[union-attr]
