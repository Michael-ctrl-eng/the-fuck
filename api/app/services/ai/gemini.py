"""Google Gemini free-tier provider — gemini-2.0-flash (15 RPM, 1M tokens/day).

Uses the official `google-genai` SDK (lightweight, pure async).
Free API key: https://aistudio.google.com/apikey
"""

from __future__ import annotations

import asyncio
import json
import time

import httpx
import structlog

from ...config import Settings
from .base import CompletionResult, ModelUnavailableError

log = structlog.get_logger("raqib.ai.gemini")

# Gemini API key → models mapping
GEMINI_MODELS = {
    "flash": "gemini-2.0-flash",
    "flash-lite": "gemini-2.0-flash-lite",
    "pro": "gemini-2.5-pro",
}


class GeminiProvider:
    name = "gemini"
    BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._api_key = settings.gemini_api_key
        self._model_name = settings.gemini_model
        self._client: httpx.AsyncClient | None = None
        self._available_at: float = 0.0
        self._available: bool | None = None
        self._check_lock = asyncio.Lock()

    def _model_id(self) -> str:
        return GEMINI_MODELS.get(self._model_name, self._model_name)

    def _client_or(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE,
                timeout=httpx.Timeout(60.0, connect=10.0),
                headers={"x-goog-api-key": self._api_key},
            )
        return self._client

    async def available(self) -> bool:
        if not self._api_key:
            return False
        now = time.monotonic()
        if self._available is not None and now - self._available_at < 60:
            return self._available
        async with self._check_lock:
            if time.monotonic() - self._available_at < 60:
                return bool(self._available)
            try:
                resp = await self._client_or().get(
                    f"/models/{self._model_id()}",
                )
                self._available = resp.status_code == 200
            except httpx.HTTPError:
                self._available = False
            self._available_at = time.monotonic()
            if self._available:
                log.info("gemini.available", model=self._model_id())
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
            raise ModelUnavailableError("GEMINI_API_KEY غير مضبوط — احصل على مفتاح مجاني من aistudio.google.com")

        model_id = self._model_id()
        contents = []

        # System instruction (Gemini supports it via systemInstruction)
        system_instruction = {"parts": [{"text": system}]}

        # Build user content
        parts: list[dict] = [{"text": user}]

        # Add images as inline_data (base64) if provided
        if images:
            import base64
            for img_b64 in images[:5]:
                if img_b64.startswith("data:"):
                    # data URI: extract mime + data
                    header, data = img_b64.split(",", 1)
                    mime = header.split(":")[1].split(";")[0]
                else:
                    # raw base64
                    data = img_b64
                    mime = "image/jpeg"
                parts.append({
                    "inline_data": {
                        "mime_type": mime,
                        "data": data,
                    }
                })

        contents.append({"role": "user", "parts": parts})

        body: dict = {
            "contents": contents,
            "systemInstruction": system_instruction,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        try:
            resp = await self._client_or().post(
                f"/models/{model_id}:generateContent",
                json=body,
            )
            if resp.status_code == 429:
                # Rate limited — retry after a brief delay
                await asyncio.sleep(2)
                resp = await self._client_or().post(
                    f"/models/{model_id}:generateContent",
                    json=body,
                )
            resp.raise_for_status()
            data = resp.json()

            # Extract text from candidates
            candidates = data.get("candidates", [])
            if not candidates:
                raise ModelUnavailableError("Gemini أرجع استجابة فارغة")

            text_parts = []
            for part in candidates[0].get("content", {}).get("parts", []):
                if "text" in part:
                    text_parts.append(part["text"])
            text = "\n".join(text_parts).strip()

            if not text:
                raise ModelUnavailableError("Gemini أرجع نص فارغ")

            # Token counts
            usage = data.get("usageMetadata", {})

            return CompletionResult(
                text=text,
                model=model_id,
                provider="gemini",
                prompt_tokens=usage.get("promptTokenCount", 0),
                completion_tokens=usage.get("candidatesTokenCount", 0),
            )

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 403:
                raise ModelUnavailableError("Gemini API key غير صالح أو انتهت الصلاحية")
            if status == 429:
                raise ModelUnavailableError("Gemini: تم تجاوز حد الطلبات — انتظر ثانية وأعد المحاولة")
            raise ModelUnavailableError(f"Gemini خطأ {status}: {str(exc)[:200]}")
        except httpx.HTTPError as exc:
            raise ModelUnavailableError(f"Gemini: فشل الاتصال: {str(exc)[:200]}")
