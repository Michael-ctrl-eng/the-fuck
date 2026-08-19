from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Must be set before importing the app (settings are cached).
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{ROOT / 'data' / 'test_raqib.db'}")
os.environ.setdefault("OLLAMA_URL", "http://127.0.0.1:1")  # unreachable → model unavailable
os.environ.setdefault("STORAGE_DIR", str(ROOT / "data" / "test_storage"))
os.environ.setdefault("SQLITE_PATH", str(ROOT / "data" / "test_raqib.db"))

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.app.config import get_settings
from api.app.db import dispose_db, init_db

pytest_plugins = []


@pytest_asyncio.fixture
async def _db():
    """Fresh SQLite database + storage for every test."""
    import shutil

    from api.app import models  # noqa: F401 — register tables before create_all

    settings = get_settings()
    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    db_file = ROOT / "data" / "test_raqib.db"
    if db_file.exists():
        db_file.unlink()
    storage = ROOT / "data" / "test_storage"
    if storage.exists():
        shutil.rmtree(storage)
    await init_db(settings)
    yield
    await dispose_db()


@pytest_asyncio.fixture
async def db(_db):
    from api.app.db import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def app(_db):
    from api.app.main import create_app

    return create_app(get_settings())


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def csrf_headers(client: AsyncClient) -> dict:
    token = client.cookies.get("raqib_csrf", "")
    return {"X-CSRF-Token": token} if token else {}


async def register(client: AsyncClient, email="user@example.com", password="StrongPass123", name="مستخدم تجريبي", org="منظمة تجريبية") -> dict:
    resp = await client.post("/api/auth/register", json={
        "email": email, "password": password, "full_name": name, "org_name": org,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


async def login(client: AsyncClient, email="user@example.com", password="StrongPass123") -> dict:
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()
