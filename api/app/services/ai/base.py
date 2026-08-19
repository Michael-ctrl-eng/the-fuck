"""AI provider abstractions.

The product ships with self-hosted providers (Ollama for chat, local
sentence-transformers for embeddings). Every consumer talks to the
LLMProvider / EmbeddingProvider protocols so a free-tier cloud provider
can be dropped in later without changing pipeline code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class ModelUnavailableError(RuntimeError):
    """Raised when no usable model provider is available."""

    def __init__(self, message: str = "النموذج الذكي غير متاح حاليًا") -> None:
        super().__init__(message)
        self.message = message


@dataclass
class CompletionResult:
    text: str
    model: str = ""
    provider: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    meta: dict = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def available(self) -> bool: ...

    async def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        json_mode: bool = False,
        kind: str = "generic",
    ) -> CompletionResult: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    dim: int

    async def available(self) -> bool: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class UnavailableLLM:
    name = "none"

    async def available(self) -> bool:
        return False

    async def complete(self, **kwargs) -> CompletionResult:
        raise ModelUnavailableError()


class UnavailableEmbeddings:
    name = "none"
    dim = 0

    async def available(self) -> bool:
        return False

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise ModelUnavailableError("محرك التضمين غير متاح")
