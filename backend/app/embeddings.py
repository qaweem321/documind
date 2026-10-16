import asyncio
import hashlib
import math
import re
from collections.abc import Sequence
from typing import Any, Protocol

DIMENSIONS = 384
BATCH_SIZE = 64


class Embedder(Protocol):
    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...


class FastEmbedder:
    """Local ONNX embeddings (fastembed): no API key, no per-call cost. The model downloads once
    (about 130 MB) and is loaded on first use. Inference runs in a worker thread so it doesn't
    block the event loop."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: Any = None
        self._lock = asyncio.Lock()

    async def _get_model(self) -> Any:
        async with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding

                self._model = await asyncio.to_thread(TextEmbedding, self.model_name)
            return self._model

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        model = await self._get_model()
        vectors = await asyncio.to_thread(lambda: list(model.embed(list(texts), batch_size=BATCH_SIZE)))
        return [v.tolist() for v in vectors]

    async def embed_query(self, text: str) -> list[float]:
        model = await self._get_model()
        vectors = await asyncio.to_thread(lambda: list(model.query_embed(text)))
        return list(vectors[0].tolist())


class HashEmbedder:
    """Deterministic bag-of-words vectors for tests: texts that share words are close, and no
    model download is needed."""

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> list[float]:
        vector = [0.0] * DIMENSIONS
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            bucket = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "big") % DIMENSIONS
            vector[bucket] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]
