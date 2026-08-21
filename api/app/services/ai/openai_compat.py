"""OpenAI-compatible provider — works with Groq, Together, Fireworks, etc.

All these providers offer free tiers with fast inference:
- Groq: llama-3.3-70b, gemma2-9b (free, 30 RPM)
- Together: llama-3.3-70b, qwen-2.5-72b (free $25 credit)
- Fireworks: mixtral-8x7b (free tier)

Uses the standard OpenAI chat completions API format.
"""

from __future__ import annotations

import asyncio
import json
import time

import httpx
import structlog

from ...config import Settings
from .base import CompletionResult, ModelUnavailableError

log = structlog.get_logger("raqib.ai.openai_compat")


class OpenAICompatProvider:
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._api_key = settings.openai_api_key
        self._base_url = settings.openai_api_base.rstrip("/") if settings.openai_api_base else ""
        self._model = settings.openai_model
        self._client: httpx.AsyncClient | None = None
        self._available_at: float = 0.0
        self._available: bool | None = None
        self._check_lock = asyncio.Lock()

    def _client_or(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(60.0, connect=10.0),
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def available(self) -> bool:
        if not self._api_key or not self._base_url:
            return False
        now = time.monotonic()
        if self._available is not None and now - self._available_at < 60:
            return self._available
        async with self._check_lock:
            if time.monotonic() - self._available_at < 60:
                return bool(self._available)
            try:
                # Quick health check: list models (most providers support this)
                resp = await self._client_or().get("/models")
                self._available = resp.status_code == 200
            except httpx.HTTPError:
                self._available = False
            self._available_at = time.monotonic()
            if self._available:
                log.info("openai.available", base_url=self._base_url, model=self._model)
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
        if not self._api_key:
            raise ModelUnavailableError("OPENAI_API_KEY غير مضبوط")

        messages: list[dict] = [
            {"role": "system", "content": system},
        ]

        # Build user content (text + optional images)
        user_content: list[dict] = [{"type": "text", "text": user}]
        if images:
            for img_b64 in images[:5]:
                if img_b64.startswith("data:"):
                    header, data = img_b64.split(",", 1)
                    mime = header.split(":")[1].split(";")[0]
                else:
                    data = img_b64
                    mime = "image/jpeg"
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{data}"},
                })

        messages.append({"role": "user", "content": user_content})

        body: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if json_mode:
            body["response_format"] = {"type": "json_object"}

        try:
            resp = await self._client_or().post("/chat/completions", json=body)
            if resp.status_code == 429:
                await asyncio.sleep(2)
                resp = await self._client_or().post("/chat/completions", json=body)
            resp.raise_for_status()
            data = resp.json()

            choices = data.get("choices", [])
            if not choices:
                raise ModelUnavailableError("الموديل أرجع استجابة فارغة")

            text = choices[0].get("message", {}).get("content", "").strip()
            if not text:
                raise ModelUnavailableError("الموديل أرجع نص فارغ")

            usage = data.get("usage", {})

            return CompletionResult(
                text=text,
                model=self._model,
                provider="openai",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                raise ModelUnavailableError("OpenAI API key غير صالح")
            if status == 429:
                raise ModelUnavailableError("تم تجاوز حد الطلبات — انتظر ثانية")
            raise ModelUnavailableError(f"OpenAI خطأ {status}: {str(exc)[:200]}")
        except httpx.HTTPError as exc:
            raise ModelUnavailableError(f"OpenAI: فشل الاتصال: {str(exc)[:200]}")
