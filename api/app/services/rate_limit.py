"""Distributed rate limiting.

Redis token bucket when REDIS_URL is configured; otherwise an in-process
sliding-window limiter (sandbox / single-process dev). Both implement the
same acquire() contract.
"""

from __future__ import annotations

import asyncio
import time
from typing import Protocol

from ..config import Settings, get_settings


class RateLimiter(Protocol):
    async def acquire(self, key: str, limit: int, window_seconds: int = 60) -> None:
        """Block until a slot is available, then consume it."""
        ...

    async def close(self) -> None: ...


class MemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def acquire(self, key: str, limit: int, window_seconds: int = 60) -> None:
        lock = self._locks.setdefault(key, asyncio.Lock())
        now = time.monotonic()
        async with lock:
            while True:
                window = self._hits.setdefault(key, [])
                window[:] = [t for t in window if t > now - window_seconds]
                if len(window) < limit:
                    window.append(now)
                    return
                await asyncio.sleep(max(0.05, (window[0] + window_seconds - now)))

    async def close(self) -> None:
        self._hits.clear()


class RedisRateLimiter:
    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(url, decode_responses=True)

    async def acquire(self, key: str, limit: int, window_seconds: int = 60) -> None:
        redis_down = 0
        while True:
            try:
                async with self._redis.pipeline() as p:
                    count = await p.incr(f"rl:{key}").expire(f"rl:{key}", window_seconds).execute()
                redis_down = 0
                if int(count[0]) <= limit:
                    return
                ttl = await self._redis.ttl(f"rl:{key}")
                await asyncio.sleep(min(max(0.1, ttl if ttl > 0 else window_seconds), 5.0))
            except Exception:
                # Redis unavailable → fail open after a few short retries so
                # requests never hang on a Redis outage.
                redis_down += 1
                if redis_down >= 3:
                    return
                await asyncio.sleep(0.1 * redis_down)

    async def close(self) -> None:
        await self._redis.aclose()


_limiter: RateLimiter | None = None


def get_rate_limiter(settings: Settings | None = None) -> RateLimiter:
    global _limiter
    if _limiter is None:
        s = settings or get_settings()
        if s.redis_url:
            _limiter = RedisRateLimiter(s.redis_url)
        else:
            _limiter = MemoryRateLimiter()
    return _limiter
