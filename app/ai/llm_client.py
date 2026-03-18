from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Fallback free models on OpenRouter (ordered by reliability)
FALLBACK_MODELS = [
    "google/gemma-3-27b-it:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-3-4b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "qwen/qwen3-4b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]


async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Call OpenRouter chat completion API with fallback models."""
    models_to_try = [model or settings.OPENROUTER_MODEL] + [
        m for m in FALLBACK_MODELS if m != (model or settings.OPENROUTER_MODEL)
    ]

    last_error = None
    for current_model in models_to_try:
        try:
            return await _call_openrouter(
                messages, current_model, temperature, max_tokens
            )
        except Exception as e:
            last_error = e
            logger.warning(f"Model {current_model} failed: {e}, trying next...")
            await asyncio.sleep(3)

    raise RuntimeError(f"All models failed. Last error: {last_error}")


async def _call_openrouter(
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Make a single API call to OpenRouter."""
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://mama-sales-agent.local",
        "X-Title": "Mama Sales Agent",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )

        if response.status_code == 429:
            # Rate limited — wait and raise to try fallback
            retry_after = int(response.headers.get("Retry-After", "5"))
            logger.warning(f"Rate limited on {model}, waiting {retry_after}s")
            await asyncio.sleep(retry_after)
            raise RuntimeError(f"Rate limited on {model}")

        if response.status_code != 200:
            raise RuntimeError(
                f"OpenRouter error {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("No choices in response")

        content = choices[0]["message"]["content"]
        if content is None:
            raise RuntimeError(f"Model {model} returned null content")

        return content
