"""Provider manager — resolves the best available providers at runtime."""

from __future__ import annotations

import structlog

from ...config import Settings
from .base import (
    EmbeddingProvider,
    LLMProvider,
    ModelUnavailableError,
    UnavailableEmbeddings,
    UnavailableLLM,
)
from .embeddings import LocalEmbeddingProvider
from .ollama import OllamaProvider

log = structlog.get_logger("raqib.ai.manager")


class ProviderManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._llm: LLMProvider | None = None
        self._embeddings: EmbeddingProvider | None = None

    def llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = OllamaProvider(self.settings)
        return self._llm

    def embeddings(self) -> EmbeddingProvider:
        if self._embeddings is None:
            self._embeddings = LocalEmbeddingProvider(self.settings)
        return self._embeddings

    async def llm_available(self) -> bool:
        try:
            return await self.llm().available()
        except Exception:  # pragma: no cover
            return False

    async def embeddings_available(self) -> bool:
        try:
            return await self.embeddings().available()
        except Exception:  # pragma: no cover
            return False

    def describe(self) -> dict:
        return {
            "model_provider": self.llm().name,
            "embedding_provider": self.embeddings().name,
        }


_manager: ProviderManager | None = None


def get_provider_manager(settings: Settings) -> ProviderManager:
    global _manager
    if _manager is None:
        _manager = ProviderManager(settings)
    return _manager
