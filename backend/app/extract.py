import io
from dataclasses import dataclass
from pathlib import PurePath

from pypdf import PdfReader
from pypdf.errors import PdfReadError

SUPPORTED = {
    ".pdf": "application/pdf",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
}


class UnsupportedFile(ValueError):
    pass


@dataclass(frozen=True)
class Page:
    number: int | None  # 1-based for PDFs; None for text files
    text: str


def content_type_for(filename: str, data: bytes) -> str:
    """Decides the type from the extension and checks the bytes agree, so a renamed file is caught."""
    suffix = PurePath(filename).suffix.lower()
    content_type = SUPPORTED.get(suffix)
    if content_type is None:
        raise UnsupportedFile(
            f"{suffix or 'Files without an extension'} isn't supported. Upload PDF, Markdown or text."
        )
    if content_type == "application/pdf" and not data.startswith(b"%PDF-"):
        raise UnsupportedFile("This file has a .pdf name but isn't a PDF.")
    if content_type != "application/pdf" and b"\x00" in data[:4096]:
        raise UnsupportedFile("This looks like a binary file, not text.")
    return content_type


def extract_pages(data: bytes, content_type: str) -> list[Page]:
    if content_type == "application/pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
            pages = [Page(i + 1, (page.extract_text() or "").strip()) for i, page in enumerate(reader.pages)]
        except PdfReadError as error:
            raise UnsupportedFile(f"Couldn't read this PDF: {error}") from error
    else:
        pages = [Page(None, data.decode("utf-8", errors="replace").strip())]
    pages = [p for p in pages if p.text]
    if not pages:
        raise UnsupportedFile("No text found. Scanned PDFs need OCR first.")
    return pages


def title_from(filename: str, pages: list[Page]) -> str:
    """A Markdown file's first heading, else the file name without its extension."""
    first_line = pages[0].text.lstrip().splitlines()[0] if pages else ""
    if first_line.startswith("# "):
        return first_line[2:].strip()[:200]
    return PurePath(filename).stem.replace("_", " ").replace("-", " ").strip()[:200] or filename
