from __future__ import annotations

from datetime import timedelta

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .config import Settings
from .deps import CSRF_COOKIE, SESSION_COOKIE
from .security import new_token, token_hash


async def create_session(
    db: AsyncSession,
    *,
    user: models.User,
    org_id: str,
    request,
) -> tuple[str, str]:
    """Create a session row; returns (session_token, csrf_token)."""
    token = new_token(32)
    csrf = new_token(24)
    session = models.Session(
        user_id=user.id,
        org_id=org_id,
        token_hash=token_hash(token),
        csrf_token=token_hash(csrf),
        user_agent=str(request.headers.get("user-agent", ""))[:250],
        ip=str(request.client.host if request.client else "")[:60],
        expires_at=models.utcnow() + timedelta(hours=request.app.state.settings.session_ttl_hours),
    )
    db.add(session)
    await db.flush()
    return token, csrf


def set_session_cookies(response: Response, session_token: str, csrf_token: str, settings: Settings) -> None:
    secure = settings.is_prod
    ttl = settings.session_ttl_hours * 3600
    response.set_cookie(
        SESSION_COOKIE, session_token, httponly=True, samesite="lax",
        secure=secure, path="/", max_age=ttl,
    )
    response.set_cookie(
        CSRF_COOKIE, csrf_token, httponly=False, samesite="lax",
        secure=secure, path="/", max_age=ttl,
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
