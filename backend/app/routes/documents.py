from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status

from ..deps import Services, services
from ..extract import SUPPORTED, UnsupportedFile, content_type_for, title_from
from ..ingest import sha256
from ..schemas import DocumentOut, SearchRequest, Source, UploadResult
from ..search import hybrid_search

router = APIRouter(prefix="/api")
Deps = Annotated[Services, Depends(services)]

DOCUMENT_COLUMNS = (
    "id, title, filename, content_type, size_bytes, page_count, chunk_count, status, error, created_at"
)
MAX_FILES = 20


@router.get("/documents")
async def list_documents(deps: Deps) -> list[DocumentOut]:
    async with deps.pool.connection() as conn:
        rows = await (
            await conn.execute(f"SELECT {DOCUMENT_COLUMNS} FROM documents ORDER BY created_at DESC")
        ).fetchall()
    return [DocumentOut.model_validate(r) for r in rows]


@router.post("/documents")
async def upload_documents(files: list[UploadFile], deps: Deps) -> list[UploadResult]:
    """Saves each file and queues it for processing; one bad file doesn't fail the others.
    The same file uploaded twice (same SHA-256) returns the existing document."""
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"Upload at most {MAX_FILES} files at a time.")
    limit = deps.settings.max_upload_mb * 1024 * 1024
    results: list[UploadResult] = []
    for file in files:
        name = (file.filename or "upload").rsplit("/", 1)[-1][:255]
        data = await file.read(limit + 1)
        if len(data) > limit:
            results.append(
                UploadResult(filename=name, error=f"Larger than {deps.settings.max_upload_mb} MB.")
            )
            continue
        try:
            content_type = content_type_for(name, data)
        except UnsupportedFile as error:
            results.append(UploadResult(filename=name, error=str(error)))
            continue
        async with deps.pool.connection() as conn, conn.transaction():
            row = await (
                await conn.execute(
                    "INSERT INTO documents (title, filename, content_type, sha256, size_bytes) "
                    "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (sha256) DO NOTHING "
                    f"RETURNING {DOCUMENT_COLUMNS}",
                    (title_from(name, []), name, content_type, sha256(data), len(data)),
                )
            ).fetchone()
            if row is None:
                existing = await (
                    await conn.execute(
                        f"SELECT {DOCUMENT_COLUMNS} FROM documents WHERE sha256 = %s", (sha256(data),)
                    )
                ).fetchone()
                results.append(
                    UploadResult(filename=name, duplicate=True, document=DocumentOut.model_validate(existing))
                )
                continue
            await conn.execute(
                "INSERT INTO document_files (document_id, data) VALUES (%s, %s)", (row["id"], data)
            )
        results.append(UploadResult(filename=name, document=DocumentOut.model_validate(row)))
        deps.ingest.put(row["id"])
    return results


@router.get("/documents/{document_id}")
async def get_document(document_id: UUID, deps: Deps) -> DocumentOut:
    async with deps.pool.connection() as conn:
        row = await (
            await conn.execute(f"SELECT {DOCUMENT_COLUMNS} FROM documents WHERE id = %s", (document_id,))
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Document not found")
    return DocumentOut.model_validate(row)


@router.get("/documents/{document_id}/file")
async def download_document(document_id: UUID, deps: Deps) -> Response:
    async with deps.pool.connection() as conn:
        row = await (
            await conn.execute(
                "SELECT d.filename, d.content_type, f.data FROM documents d "
                "JOIN document_files f ON f.document_id = d.id WHERE d.id = %s",
                (document_id,),
            )
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Document not found")
    # Served as a download, never rendered inline, so an uploaded HTML-ish file can't run scripts.
    return Response(
        bytes(row["data"]),
        media_type=str(row["content_type"]),
        headers={"content-disposition": f"attachment; filename*=UTF-8''{_quote(str(row['filename']))}"},
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: UUID, deps: Deps) -> None:
    async with deps.pool.connection() as conn:
        result = await conn.execute("DELETE FROM documents WHERE id = %s", (document_id,))
    if result.rowcount == 0:
        raise HTTPException(404, "Document not found")


@router.post("/search")
async def search(body: SearchRequest, deps: Deps) -> list[Source]:
    async with deps.pool.connection() as conn:
        return await hybrid_search(conn, deps.embedder, body.query, body.k, body.document_ids)


@router.get("/config")
async def config(deps: Deps) -> dict[str, object]:
    s = deps.settings
    return {
        "demoMode": s.demo_mode,
        "model": None if s.demo_mode else s.claude_model,
        "maxUploadMb": s.max_upload_mb,
        "acceptedExtensions": sorted(SUPPORTED),
    }


def _quote(name: str) -> str:
    from urllib.parse import quote

    return quote(name, safe="")
