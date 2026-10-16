import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from .answer import Answerer, create_answerer
from .config import Settings, get_settings
from .db import create_pool, run_migrations
from .deps import Services
from .embeddings import Embedder, FastEmbedder
from .ingest import IngestQueue
from .rate_limit import RateLimiter
from .routes import conversations, documents
from .seed import seed_examples

log = logging.getLogger("documind")

SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
}


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response


def create_app(
    settings: Settings | None = None, embedder: Embedder | None = None, answerer: Answerer | None = None
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        applied = await run_migrations(settings.database_url)
        if applied:
            log.info("applied migrations: %s", ", ".join(applied))
        pool = create_pool(settings.database_url)
        await pool.open(wait=True)
        used_embedder = embedder or FastEmbedder(settings.embedding_model)
        ingest = IngestQueue(pool, used_embedder, settings)
        app.state.services = Services(
            settings=settings,
            pool=pool,
            embedder=used_embedder,
            answerer=answerer or create_answerer(settings),
            ingest=ingest,
            chat_limiter=RateLimiter(settings.chat_rate_limit_per_minute),
        )
        await ingest.start()
        if settings.seed_examples:
            await seed_examples(pool, ingest)
        log.info("DocuMind ready (%s)", "demo mode" if settings.demo_mode else settings.claude_model)
        try:
            yield
        finally:
            await ingest.stop()
            await pool.close()

    app = FastAPI(title="DocuMind", version="1.0.0", lifespan=lifespan)
    app.add_middleware(SecurityHeaders)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"]
    )
    app.include_router(documents.router)
    app.include_router(conversations.router)

    @app.get("/api/health")
    async def health(request: Request) -> JSONResponse:
        try:
            async with request.app.state.services.pool.connection() as conn:
                await conn.execute("SELECT 1")
            return JSONResponse({"ok": True})
        except Exception:
            return JSONResponse({"ok": False}, status_code=503)

    return app
