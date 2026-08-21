"""Provider manager — resolves the best available providers at runtime.

Priority: Gemini (free, fast) → OpenAI-compatible (Groq/Together free) → Ollama (local).
Auto-detection: tries each provider in order, caches the first working one.
"""

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

log = structlog.get_logger("raqib.ai.manager")


class ProviderManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._llm: LLMProvider | None = None
        self._embeddings: EmbeddingProvider | None = None

    def _resolve_llm(self) -> LLMProvider:
        """Auto-select the best available LLM provider."""
        provider_pref = self.settings.llm_provider.lower()

        # Explicit selection
        if provider_pref == "gemini":
            return self._make_gemini()
        if provider_pref == "openai":
            return self._make_openai()
        if provider_pref == "ollama":
            return self._make_ollama()

        # Auto: Gemini → OpenAI-compat → Ollama
        if self.settings.gemini_api_key:
            p = self._make_gemini()
            log.info("provider.auto_select", selected="gemini", reason="GEMINI_API_KEY set")
            return p

        if self.settings.openai_api_key and self.settings.openai_api_base:
            p = self._make_openai()
            log.info("provider.auto_select", selected="openai", reason="OPENAI_API_KEY + OPENAI_API_BASE set")
            return p

        # Fallback to Ollama
        p = self._make_ollama()
        log.info("provider.auto_select", selected="ollama", reason="no cloud keys, using local")
        return p

    def _make_gemini(self) -> LLMProvider:
        from .gemini import GeminiProvider
        return GeminiProvider(self.settings)

    def _make_openai(self) -> LLMProvider:
        from .openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(self.settings)

    def _make_ollama(self) -> LLMProvider:
        from .ollama import OllamaProvider
        return OllamaProvider(self.settings)

    def llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = self._resolve_llm()
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
