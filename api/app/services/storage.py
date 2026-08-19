"""StorageProvider abstraction.

Default implementation is local disk behind an S3/MinIO-shaped interface
(put_object/get_object/delete_object), so the backend can be swapped to
MinIO/S3 later without touching callers. All methods are async and run
blocking disk I/O in a worker thread so the event loop never stalls.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from ..config import Settings, get_settings


class StorageProvider:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._root_resolved = self.root.resolve()

    def _path(self, key: str) -> Path:
        # keys are always relative paths like "orgs/<org>/raw/<name>.json"
        p = (self.root / key).resolve()
        try:
            p.relative_to(self._root_resolved)
        except ValueError:
            raise ValueError(f"invalid storage key: {key}")
        return p

    async def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
        p = self._path(key)

        def _write() -> dict:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            return {
                "key": key,
                "provider": "local",
                "content_type": content_type,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }

        return await asyncio.to_thread(_write)

    async def get_object(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path(key).read_bytes)

    async def delete_object(self, key: str) -> None:
        p = self._path(key)

        def _unlink() -> None:
            try:
                p.unlink()
            except FileNotFoundError:
                pass

        await asyncio.to_thread(_unlink)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._path(key).exists)

    async def stat(self, key: str) -> dict | None:
        p = self._path(key)

        def _stat() -> dict | None:
            try:
                return {"key": key, "size_bytes": p.stat().st_size}
            except FileNotFoundError:
                return None

        return await asyncio.to_thread(_stat)


_local: StorageProvider | None = None


def get_storage(settings: Settings | None = None) -> StorageProvider:
    global _local
    if _local is None:
        _local = StorageProvider((settings or get_settings()).storage_path)
    return _local