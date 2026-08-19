from __future__ import annotations

from typing import Annotated, Awaitable, Callable

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .config import Settings, get_settings
from .db import get_session_factory
from .errors import AuthError, PermissionError
from .security import constant_time_eq, token_hash

SESSION_COOKIE = "raqib_sid"
CSRF_COOKIE = "raqib_csrf"

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db() -> AsyncSession:  # pragma: no cover - thin wrapper
    factory = get_session_factory()
    async with factory() as session:
        yield session


DbDep = Annotated[AsyncSession, Depends(get_db)]


def _session_token(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        raise AuthError()
    return token


async def get_current_user(request: Request, db: DbDep) -> models.User:
    token = _session_token(request)
    row = await db.execute(
        select(models.Session).where(
            models.Session.token_hash == token_hash(token),
            models.Session.revoked_at.is_(None),
        )
    )
    session = row.scalar_one_or_none()
    if session is None or session.expires_at is None:
        raise AuthError()
    now = models.utcnow()
    if session.expires_at < now:
        raise AuthError("انتهت الجلسة، سجّل الدخول مجددًا")
    user = await db.get(models.User, session.user_id)
    if user is None or not user.is_active:
        raise AuthError()
    return user


UserDep = Annotated[models.User, Depends(get_current_user)]


async def get_session_record(request: Request, db: DbDep) -> models.Session:
    token = _session_token(request)
    row = await db.execute(
        select(models.Session).where(
            models.Session.token_hash == token_hash(token),
            models.Session.revoked_at.is_(None),
        )
    )
    session = row.scalar_one_or_none()
    if session is None:
        raise AuthError()
    return session


async def get_current_membership(
    request: Request, db: DbDep, user: UserDep
) -> models.OrgMembership:
    token = _session_token(request)
    row = await db.execute(
        select(models.Session).where(
            models.Session.token_hash == token_hash(token),
            models.Session.revoked_at.is_(None),
        )
    )
    session = row.scalar_one_or_none()
    if session is None:
        raise AuthError()
    membership = (
        await db.execute(
            select(models.OrgMembership).where(
                models.OrgMembership.org_id == session.org_id,
                models.OrgMembership.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise AuthError()
    return membership


MembershipDep = Annotated[models.OrgMembership, Depends(get_current_membership)]


async def get_current_org(
    db: DbDep, membership: MembershipDep
) -> models.Organization:
    org = await db.get(models.Organization, membership.org_id)
    if org is None:
        raise AuthError()
    return org


OrgDep = Annotated[models.Organization, Depends(get_current_org)]


def require_role(*roles: str) -> Callable[..., Awaitable[models.OrgMembership]]:
    async def _check(membership: MembershipDep) -> models.OrgMembership:
        if membership.role not in roles:
            raise PermissionError()
        return membership

    return _check


def check_csrf(request: Request) -> None:
    settings = get_settings()
    if not settings.csrf_enabled:
        return
    header = request.headers.get("x-csrf-token", "")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    if not header or not cookie or not constant_time_eq(header, cookie):
        raise PermissionError("رمز CSRF غير صالح — أعد تحميل الصفحة")


def csrf_guard(request: Request) -> None:
    check_csrf(request)


# Reusable dependency for `dependencies=[...]` on mutating routes.
csrf_dep = Depends(csrf_guard)
