from dataclasses import dataclass

from fastapi import Request

from .answer import Answerer
from .config import Settings
from .embeddings import Embedder
from .ingest import IngestQueue, Pool
from .rate_limit import RateLimiter


@dataclass
class Services:
    settings: Settings
    pool: Pool
    embedder: Embedder
    answerer: Answerer
    ingest: IngestQueue
    chat_limiter: RateLimiter


def services(request: Request) -> Services:
    found: Services = request.app.state.services
    return found
