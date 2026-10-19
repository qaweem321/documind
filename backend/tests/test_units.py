import asyncio

import pytest

from app.answer import AnswerEvent, DemoAnswerer, build_messages, source_title
from app.chat import SegmentBuilder, retrieval_query, sse
from app.chunking import split_pages
from app.config import Settings
from app.extract import Page, UnsupportedFile, content_type_for, extract_pages, title_from
from app.rate_limit import RateLimiter
from app.schemas import Source
from app.search import keyword_terms

from .conftest import make_pdf


def source(index: int = 0, page: int | None = 3) -> Source:
    return Source(
        index=index,
        chunk_id=1,
        document_id="00000000-0000-0000-0000-000000000001",
        document_title="Handbook",
        page=page,
        content="Laptops must be returned within 10 business days. The company sends a box.",
        score=0.5,
    )


def test_pdf_pages_keep_their_numbers() -> None:
    pages = extract_pages(make_pdf(["First page text", "Second page text"]), "application/pdf")
    assert [(p.number, p.text) for p in pages] == [(1, "First page text"), (2, "Second page text")]


def test_file_type_checks_extension_and_bytes() -> None:
    assert content_type_for("notes.MD", b"# Hi") == "text/markdown"
    with pytest.raises(UnsupportedFile, match="isn't a PDF"):
        content_type_for("fake.pdf", b"hello")
    with pytest.raises(UnsupportedFile, match="isn't supported"):
        content_type_for("image.png", b"\x89PNG")
    with pytest.raises(UnsupportedFile, match="binary"):
        content_type_for("data.txt", b"ab\x00cd")
    with pytest.raises(UnsupportedFile, match="No text found"):
        extract_pages(b"   \n", "text/plain")


def test_titles_prefer_the_first_markdown_heading() -> None:
    assert title_from("x.md", [Page(None, "# Remote Work Policy\nText")]) == "Remote Work Policy"
    assert title_from("expense_policy-2026.pdf", []) == "expense policy 2026"


def test_chunks_never_cross_pages_and_respect_the_size() -> None:
    long_text = " ".join(f"Sentence number {i} is here." for i in range(80))
    chunks = split_pages([Page(1, long_text), Page(2, "Short page.")], chunk_size=300, chunk_overlap=50)
    assert all(len(c.content) <= 300 for c in chunks)
    assert chunks[-1].page == 2 and chunks[-1].content == "Short page."
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    assert {c.page for c in chunks[:-1]} == {1}


def test_keyword_terms_or_the_words_and_drop_symbols() -> None:
    assert keyword_terms("How many days?! days & (laptop)") == "how | many | days | laptop"
    assert keyword_terms("?!") == ""


def test_keyword_terms_are_capped_by_word_count_not_characters() -> None:
    terms = keyword_terms(" ".join(f"w{i}" for i in range(500)))
    assert terms.count(" | ") == 99 and not terms.endswith(("|", " "))


def test_follow_up_questions_are_searched_with_the_previous_one() -> None:
    from app.answer import Turn

    history = [Turn("user", "What is the hotel limit?"), Turn("assistant", "$250.")]
    assert retrieval_query("And in London?", history) == "What is the hotel limit?\nAnd in London?"
    assert retrieval_query("Hi", []) == "Hi"


def test_prompt_puts_one_citable_document_per_passage_before_the_question() -> None:
    messages = build_messages("When?", [], [source(0), source(1, page=None)])
    content = messages[-1]["content"]
    assert isinstance(content, list)
    assert [block["type"] for block in content] == ["document", "document", "text"]
    assert content[0]["title"] == "Handbook (p. 3)"  # type: ignore[typeddict-item]
    assert content[0]["citations"] == {"enabled": True}  # type: ignore[typeddict-item]
    assert source_title(source(page=None)) == "Handbook"


def test_segments_group_text_and_citations_by_block() -> None:
    from app.answer import CitationDelta, TextDelta

    builder = SegmentBuilder()
    for event in [
        TextDelta(0, "Yes, "),
        TextDelta(1, "within 10 days"),
        CitationDelta(1, 2, "10 business days"),
        TextDelta(1, "!"),
    ]:
        builder.add(event)
    assert builder.text == "Yes, within 10 days!"
    assert builder.segments[1].citations[0].source_index == 2


def test_sse_format() -> None:
    assert sse("text", {"a": 1}) == 'event: text\ndata: {"a": 1}\n\n'


def test_demo_mode_quotes_passages_with_citations() -> None:
    async def collect() -> list[AnswerEvent]:
        return [e async for e in DemoAnswerer().stream("q", [], [source(0), source(1)])]

    events = asyncio.run(collect())
    citations = [e for e in events if e.kind == "citation"]
    assert [c.source_index for c in citations] == [0, 1]  # type: ignore[union-attr]
    assert "Demo mode" in events[0].text  # type: ignore[union-attr]


def test_rate_limiter_uses_a_sliding_window() -> None:
    limiter = RateLimiter(2, window_seconds=60)
    assert limiter.allow("a", now=0) and limiter.allow("a", now=1)
    assert not limiter.allow("a", now=2)
    assert limiter.allow("b", now=2)
    assert limiter.allow("a", now=61)


def test_settings_validate_and_switch_to_demo_mode_without_a_key() -> None:
    assert Settings(database_url="postgresql://x", anthropic_api_key="").demo_mode
    assert not Settings(database_url="postgresql://x", anthropic_api_key="sk-test").demo_mode
    with pytest.raises(ValueError):
        Settings(database_url="mysql://x")
