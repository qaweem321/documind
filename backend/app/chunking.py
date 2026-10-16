from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .extract import Page


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    page: int | None
    content: str


def split_pages(pages: list[Page], chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    """Splits each page on its own, so every chunk keeps the page number it came from (citations
    show "p. 4"). Separators prefer paragraph, then line, then sentence boundaries."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=min(chunk_overlap, chunk_size // 2),
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator="end",
    )
    chunks: list[Chunk] = []
    for page in pages:
        for piece in splitter.split_text(page.text):
            text = piece.strip()
            if text:
                chunks.append(Chunk(len(chunks), page.number, text))
    return chunks
