"""Embedding providers.

Default: local sentence-transformers with BAAI/bge-m3 (self-hosted, free).
Loading is lazy and guarded so the sandbox runs without the heavy torch
dependency; available() reports False there and pipeline stages degrade
honestly (memory stage skipped and recorded in the job result).
"""

from __future__ import annotations

import asyncio
import time

import structlog

from ...config import Settings

log = structlog.get_logger("raqib.ai.embeddings")


class LocalEmbeddingProvider:
    name = "sentence-transformers"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None
        self._lock = asyncio.Lock()
        self._available: bool | None = None
        self._available_at: float = 0.0

    @property
    def dim(self) -> int:
        return self.settings.embedding_dim

    async def _load(self) -> None:
        async with self._lock:
            if self._model is not None:
                return
            try:
                from sentence_transformers import SentenceTransformer

                self._model = await asyncio.to_thread(
                    SentenceTransformer, self.settings.embedding_model
                )
            except Exception as exc:  # pragma: no cover - depends on heavy deps
                log.warning("embeddings.unavailable", error=str(exc))
                self._model = False  # type: ignore[assignment]

    async def available(self) -> bool:
        if self._available is not None and time.monotonic() - self._available_at < 60:
            return self._available
        await self._load()
        self._available = self._model is not None and self._model is not False
        self._available_at = time.monotonic()
        return bool(self._available)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        await self._load()
        if not self._model:
            raise RuntimeError("embedding model unavailable")
        batch: list[str] = []
        out: list[list[float]] = []
        for text in texts:
            batch.append(text)
            if len(batch) >= self.settings.embedding_batch_size:
                out.extend(await self._encode(batch))
                batch = []
        if batch:
            out.extend(await self._encode(batch))
        return out

    async def _encode(self, batch: list[str]) -> list[list[float]]:
        vecs = await asyncio.to_thread(self._model.encode, batch, normalize_embeddings=True)
        return [list(map(float, v)) for v in vecs]
