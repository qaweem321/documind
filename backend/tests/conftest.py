import os
import time
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.answer import AnswerEvent, CitationDelta, TextDelta, Turn
from app.config import Settings
from app.embeddings import HashEmbedder
from app.main import create_app
from app.schemas import Source

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://documind:documind@localhost:5434/documind_test"
)


class FakeAnswerer:
    """Answers from the first passage with one citation, and records what it was asked."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Turn], list[Source]]] = []

    async def stream(
        self, question: str, history: Sequence[Turn], sources: Sequence[Source]
    ) -> AsyncIterator[AnswerEvent]:
        self.calls.append((question, list(history), list(sources)))
        yield TextDelta(0, "Answer: ")
        if sources:
            yield TextDelta(1, "it's in the documents")
            yield CitationDelta(1, sources[0].index, sources[0].content[:40])
        yield TextDelta(2, ".")


def make_pdf(pages: list[str]) -> bytes:
    """A minimal valid PDF with one line of text per page."""
    objects: list[bytes] = []
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font = 3 + 2 * len(pages)
    for i, text in enumerate(pages):
        content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 {font} 0 R >> >> >>".encode()
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL, anthropic_api_key="sk-test", chunk_size=300, chunk_overlap=50
    )


@pytest.fixture
def answerer() -> FakeAnswerer:
    return FakeAnswerer()


@pytest.fixture
def client(settings: Settings, answerer: FakeAnswerer) -> Iterator[TestClient]:
    app = create_app(settings, embedder=HashEmbedder(), answerer=answerer)
    with TestClient(app) as test_client:
        with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
            conn.execute("TRUNCATE documents, conversations CASCADE")
        yield test_client


def wait_until_processed(client: TestClient, document_id: str, timeout: float = 10.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        document: dict[str, Any] = client.get(f"/api/documents/{document_id}").json()
        if document["status"] != "processing":
            return document
        time.sleep(0.05)
    raise AssertionError("document was not processed in time")


def upload(client: TestClient, name: str, data: bytes) -> dict[str, Any]:
    response = client.post("/api/documents", files=[("files", (name, data))])
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()[0]
    return result


def parse_sse(body: str) -> list[tuple[str, Any]]:
    import json

    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events
