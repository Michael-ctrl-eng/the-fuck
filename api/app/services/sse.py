"""Server-Sent Events broker.

In-process asyncio pub/sub is the default (single API process, sandbox).
Production deploys run one API process per worker; the broker is per-process
and documented as such in docs/SETUP.md (a Redis pub/sub broker can be
swapped in without touching API code).
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def publish(self, org_id: str, event: str, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False, default=str)
        async with self._lock:
            queues = list(self._subscribers.get(org_id, ()))
        for q in queues:
            try:
                q.put_nowait(f"event: {event}\ndata: {data}\n\n")
            except asyncio.QueueFull:
                # A stalled client must never break publishers (jobs, routers).
                # Drop the event for this subscriber instead of crashing them.
                self.unsubscribe(org_id, q)

    def subscribe(self, org_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers[org_id].add(q)
        return q

    def unsubscribe(self, org_id: str, q: asyncio.Queue) -> None:
        self._subscribers.get(org_id, set()).discard(q)

    def subscriber_count(self) -> int:
        return sum(len(v) for v in self._subscribers.values())


broker = EventBroker()
