from __future__ import annotations

import re
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from .. import models
from ..audit import record_audit
from ..config import get_settings
from ..deps import DbDep, SettingsDep, UserDep, get_current_user, get_session_record
from ..errors import AuthError, ConflictError, NotFoundError
from ..schemas import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    MemberOut,
    OrgOut,
    RegisterRequest,
    SwitchOrgRequest,
    UserOut,
    VerifyEmailRequest,
)
from ..security import hash_password, new_token, token_hash, verify_password
from ..session import clear_session_cookies, create_session, set_session_cookies
from ..services.notify import get_notifier

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
    return slug or "org"


async def _user_payload(db, user: models.User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        email_verified=user.email_verified_at is not None,
        created_at=user.created_at,
    )


async def _orgs_payload(db, user: models.User) -> list[OrgOut]:
    rows = await db.execute(
        select(models.OrgMembership)
        .where(models.OrgMembership.user_id == user.id)
        .order_by(models.OrgMembership.created_at)
    )
    orgs = []
    for m in rows.scalars().all():
        org = await db.get(models.Organization, m.org_id)
        if org is None:
            continue
        count = (
            await db.execute(
                select(models.OrgMembership).where(models.OrgMembership.org_id == org.id)
            )
        ).scalars().all()
        orgs.append(OrgOut(
            id=org.id, name=org.name, slug=org.slug, role=m.role,
            members_count=len(count), created_at=org.created_at,
        ))
    return orgs


def _auth_response(user: models.User, orgs: list[OrgOut], csrf: str = "", dev_verify_url: str = "") -> AuthResponse:
    return AuthResponse(
        user=UserOut(
            id=user.id, email=user.email, full_name=user.full_name,
            email_verified=user.email_verified_at is not None, created_at=user.created_at,
        ),
        orgs=orgs,
        csrf_token=csrf,
        dev_verify_url=dev_verify_url,
    )


@router.get("/demo")
async def demo_hint(settings: SettingsDep):
    """Dev/test only: expose the pre-made demo account for one-click testing.

    Never answers in production; the seed itself (api/app/demo.py) is an
    explicit CLI step that is not part of any deploy.
    """
    if settings.is_prod:
        raise NotFoundError("غير متاح في بيئة الإنتاج")
    from ..demo import DEMO_EMAIL, DEMO_ORG_NAME, DEMO_PASSWORD

    return {"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "org": DEMO_ORG_NAME}


@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest, request: Request, response: Response, db: DbDep, settings: SettingsDep):
    existing = (
        await db.execute(select(models.User).where(models.User.email == body.email.lower()))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("هذا البريد مسجّل مسبقًا — سجّل الدخول")
    user = models.User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
    )
    db.add(user)
    await db.flush()
    org = models.Organization(
        name=body.org_name.strip(),
        slug=f"{_slugify(body.org_name)}-{secrets.token_hex(3)}",
    )
    db.add(org)
    await db.flush()
    db.add(models.OrgMembership(org_id=org.id, user_id=user.id, role="owner"))

    session_token, csrf = await create_session(db, user=user, org_id=org.id, request=request)
    await record_audit(db, org_id=org.id, actor_id=user.id, action="user.register",
                       resource_type="user", resource_id=user.id, ip=request.client.host if request.client else "")

    # email verification (real token; delivered via Knock, or dev log/URL)
    raw_verify = new_token(24)
    verify = models.EmailVerification(
        user_id=user.id,
        token_hash=token_hash(raw_verify),
        expires_at=models.utcnow() + timedelta(days=2),
    )
    db.add(verify)
    await db.flush()
    verify_url = f"{settings.app_url}/verify-email?token={raw_verify}"
    notifier = get_notifier(settings)
    await notifier.send_verification(user_id=user.id, email=user.email, verify_url=verify_url)

    await db.commit()
    set_session_cookies(response, session_token, csrf, settings)
    payload = _auth_response(user, await _orgs_payload(db, user), csrf)
    if not settings.is_prod and not notifier.configured:
        # sandbox/CI: the real verification link is delivered via console
        payload.dev_verify_url = verify_url
    return payload


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, request: Request, response: Response, db: DbDep, settings: SettingsDep):
    user = (
        await db.execute(select(models.User).where(models.User.email == body.email.lower()))
    ).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise AuthError("البريد أو كلمة المرور غير صحيحة")
    if not user.is_active:
        raise AuthError("الحساب معطّل")
    membership = (
        await db.execute(
            select(models.OrgMembership).where(models.OrgMembership.user_id == user.id)
        )
    ).scalars().first()
    org_id = membership.org_id if membership else None
    if org_id is None:
        org = models.Organization(name=user.full_name or "منظمتي", slug=_slugify(user.full_name or "org") + secrets.token_hex(3))
        db.add(org)
        await db.flush()
        db.add(models.OrgMembership(org_id=org.id, user_id=user.id, role="owner"))
        org_id = org.id
    session_token, csrf = await create_session(db, user=user, org_id=org_id, request=request)
    await record_audit(db, org_id=org_id, actor_id=user.id, action="user.login",
                       resource_type="user", resource_id=user.id, ip=request.client.host if request.client else "")
    await db.commit()
    set_session_cookies(response, session_token, csrf, settings)
    return _auth_response(user, await _orgs_payload(db, user), csrf)


@router.post("/logout")
async def logout(request: Request, response: Response, db: DbDep, settings: SettingsDep):
    session = await get_session_record(request, db)
    session.revoked_at = models.utcnow()
    await db.commit()
    clear_session_cookies(response, settings)
    return {"ok": True}


@router.get("/me", response_model=AuthResponse)
async def me(request: Request, db: DbDep, user: UserDep):
    session = await get_session_record(request, db)
    return _auth_response(user, await _orgs_payload(db, user))


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, db: DbDep, user: UserDep):
    row = (
        await db.execute(
            select(models.EmailVerification).where(models.EmailVerification.token_hash == token_hash(body.token))
        )
    ).scalar_one_or_none()
    if row is None or row.used_at is not None:
        raise NotFoundError("رمز التحقق غير صالح")
    if row.user_id != user.id:
        raise AuthError("رمز التحقق لا يخص هذا الحساب")
    if row.expires_at is not None and row.expires_at < models.utcnow():
        raise AuthError("انتهت صلاحية رمز التحقق — اطلب رمزًا جديدًا")
    row.used_at = models.utcnow()
    user.email_verified_at = models.utcnow()
    await db.commit()
    return {"ok": True, "verified": True}


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, db: DbDep, user: UserDep, request: Request):
    if not verify_password(body.current_password, user.password_hash):
        raise AuthError("كلمة المرور الحالية غير صحيحة")
    current = await get_session_record(request, db)
    user.password_hash = hash_password(body.new_password)
    # revoke all OTHER sessions — keep the current one logged in
    rows = await db.execute(select(models.Session).where(models.Session.user_id == user.id))
    for s in rows.scalars().all():
        if current is not None and s.id == current.id:
            continue
        s.revoked_at = models.utcnow()
    await db.commit()
    return {"ok": True}


@router.post("/switch-org", response_model=AuthResponse)
async def switch_org(body: SwitchOrgRequest, request: Request, db: DbDep, user: UserDep, settings: SettingsDep):
    session = await get_session_record(request, db)
    membership = (
        await db.execute(
            select(models.OrgMembership).where(
                models.OrgMembership.org_id == body.org_id,
                models.OrgMembership.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise AuthError("ليست لديك عضوية في هذه المنظمة")
    session.org_id = body.org_id
    await db.commit()
    return _auth_response(user, await _orgs_payload(db, user))
