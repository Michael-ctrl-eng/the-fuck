"""Ollama LLM provider — real HTTP client for the self-hosted Ollama server.

Models are pulled by the operator (the docker-compose entrypoint pulls
qwen2.5:7b-instruct-q4_K_M and qwen2.5:3b-instruct-q4_K_M). Availability is
probed via GET /api/tags and cached briefly so pipeline stages do not
hammer the server.
"""

from __future__ import annotations

import asyncio
import json
import time

import httpx
import structlog

from ...config import Settings
from .base import CompletionResult, ModelUnavailableError

log = structlog.get_logger("raqib.ai.ollama")


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: httpx.AsyncClient | None = None
        self._available_at: float = 0.0
        self._available: bool | None = None
        self._check_lock = asyncio.Lock()

    def _client_or(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.ollama_url.rstrip("/"),
                timeout=httpx.Timeout(self.settings.meta_http_timeout, connect=5.0),
            )
        return self._client

    def _pick_model(self, tags: list[dict]) -> str | None:
        names = {m.get("name", "") for m in tags}
        for candidate in self.settings.ollama_models:
            if candidate in names:
                return candidate
            short = candidate.split(":")[0]
            for name in names:
                if name.split(":")[0] == short:
                    return name
        return None

    async def available(self) -> bool:
        now = time.monotonic()
        if self._available is not None and now - self._available_at < 30:
            return self._available
        async with self._check_lock:
            if time.monotonic() - self._available_at < 30:
                return bool(self._available)
            try:
                resp = await self._client_or().get("/api/tags")
                if resp.status_code == 200:
                    tags = resp.json().get("models", [])
                    self._available = self._pick_model(tags) is not None
                else:
                    self._available = False
            except httpx.HTTPError as exc:
                log.warning("ollama.unavailable", error=str(exc))
                self._available = False
            self._available_at = time.monotonic()
            return bool(self._available)

    async def complete(
        self,
        *,
        system: str,
        user: str,
        images: list[str] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        json_mode: bool = False,
        kind: str = "generic",
    ) -> CompletionResult:
        if not await self.available():
            raise ModelUnavailableError(
                "Ollama غير متاح — تأكد من تشغيله وسحب نموذج Qwen2.5"
            )
        tags = (await self._client_or().get("/api/tags")).json().get("models", [])
        model = self._pick_model(tags)
        if model is None:
            raise ModelUnavailableError("لم يُعثر على نموذج Qwen2.5 في Ollama")
            
        user_msg = {"role": "user", "content": user}
        if images:
            user_msg["images"] = images
            
        body: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                user_msg,
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "stop": ["<|im_end|>"],
            },
        }
        if json_mode:
            body["format"] = "json"
        try:
            resp = await self._client_or().post("/api/chat", json=body)
            if resp.status_code >= 400:
                raise ModelUnavailableError(
                    f"Ollama استجاب بخطأ {resp.status_code}: {resp.text[:300]}"
                )
            data = resp.json()
            content = data.get("message", {}).get("content", "").strip()
            return CompletionResult(
                text=content,
                model=model,
                provider=self.name,
                prompt_tokens=int(data.get("prompt_eval_count") or 0),
                completion_tokens=int(data.get("eval_count") or 0),
            )
        except httpx.HTTPError as exc:
            log.warning("ollama.complete_error", error=str(exc), kind=kind)
            raise ModelUnavailableError(f"تعذر الاتصال بـ Ollama: {exc}") from exc

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
