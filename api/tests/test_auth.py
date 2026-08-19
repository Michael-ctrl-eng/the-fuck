from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from .conftest import csrf_headers, login, register


@pytest.mark.asyncio
async def test_register_login_me_logout(client):
    data = await register(client)
    assert data["user"]["email"] == "user@example.com"
    assert data["orgs"][0]["role"] == "owner"
    assert data["csrf_token"]
    # session cookie set (httpOnly) + csrf cookie (readable by JS)
    assert client.cookies.get("raqib_sid")
    assert client.cookies.get("raqib_csrf")

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "user@example.com"

    # logout revokes the session
    out = await client.post("/api/auth/logout")
    assert out.status_code == 200
    me2 = await client.get("/api/auth/me")
    assert me2.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await register(client)
    resp = await client.post("/api/auth/login", json={"email": "user@example.com", "password": "wrong-pass"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_register_conflict(client):
    await register(client)
    resp = await client.post("/api/auth/register", json={
        "email": "user@example.com", "password": "StrongPass123",
        "full_name": "x", "org_name": "y",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_csrf_enforced(client):
    await register(client)
    # mutating request without CSRF header → 403
    resp = await client.post("/api/orgs", json={"name": "منظمة جديدة"})
    assert resp.status_code == 403
    # with header → 200
    resp = await client.post("/api/orgs", json={"name": "منظمة جديدة"}, headers=csrf_headers(client))
    assert resp.status_code == 200
    assert resp.json()["role"] == "owner"


@pytest.mark.asyncio
async def test_verify_email_flow(client):
    data = await register(client, email="verify@example.com")
    # dev mode surfaces the real verification link
    url = data.get("dev_verify_url")
    assert url, "dev_verify_url expected in dev/test mode"
    token = parse_qs(urlparse(url).query)["token"][0]
    resp = await client.post("/api/auth/verify-email", json={"token": token})
    assert resp.status_code == 200
    me = await client.get("/api/auth/me")
    assert me.json()["user"]["email_verified"] is True
    # token cannot be reused
    resp2 = await client.post("/api/auth/verify-email", json={"token": token})
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_change_password_revokes_other_sessions(client):
    await register(client)
    await login(client, email="user@example.com")
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "StrongPass123", "new_password": "NewStrong456"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200
    bad = await client.post("/api/auth/login", json={"email": "user@example.com", "password": "StrongPass123"})
    assert bad.status_code == 401
    good = await client.post("/api/auth/login", json={"email": "user@example.com", "password": "NewStrong456"})
    assert good.status_code == 200
