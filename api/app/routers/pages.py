from __future__ import annotations

import secrets

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from .. import models
from ..audit import record_audit
from ..config import Settings, get_settings
from ..deps import DbDep, MembershipDep, OrgDep, UserDep, csrf_dep
from ..errors import APIError, ConflictError, NotFoundError, PermissionError
from ..schemas import (
    DisconnectResponse,
    MetaAuthUrlResponse,
    PageOut,
    PageSyncResponse,
)
from ..security import TokenCipher, new_token, token_hash
from ..services.ai.transcribe import _classify_attachment
from ..services.meta_client import MetaAPIError, get_meta_client
from ..services.meta_oauth import build_auth_url, validate_scopes
from ..services.meta_webhooks import normalize_events, verify_hub_challenge, verify_signature
from ..services.pipeline import create_job
from ..services.pipeline.process import ingest_incoming_message

router = APIRouter(prefix="/api", tags=["pages"])


# --------------------------------------------------------------------------
# OAuth connect
# --------------------------------------------------------------------------


@router.get("/meta/auth-url", response_model=MetaAuthUrlResponse)
async def meta_auth_url(request: Request, db: DbDep, user: UserDep, membership: MembershipDep):
    settings: Settings = request.app.state.settings
    if not settings.meta_app_id or not settings.meta_app_secret:
        raise APIError(
            "لم تُضبط بيانات تطبيق Meta بعد — أضف META_APP_ID و META_APP_SECRET من الإعدادات",
            details={"needs_config": True},
        )
    session = await _current_session(request, db)
    state = f"{session.id}.{new_token(16)}"
    session.oauth_state_hash = token_hash(state)
    await db.commit()
    return MetaAuthUrlResponse(url=build_auth_url(settings, state))


async def _current_session(request: Request, db):
    from ..deps import SESSION_COOKIE
    from ..security import token_hash as _th

    token = request.cookies.get(SESSION_COOKIE, "")
    return (
        await db.execute(select(models.Session).where(models.Session.token_hash == _th(token)))
    ).scalar_one_or_none()


@router.get("/meta/callback")
async def meta_callback(
    request: Request,
    db: DbDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    settings: Settings = get_settings()
    if error:
        return RedirectResponse(f"{settings.app_url}/app/pages?meta=error&reason={error}")
    if not code or not state:
        return RedirectResponse(f"{settings.app_url}/app/pages?meta=error&reason=missing_params")
    session_row = await _current_session(request, db)
    if session_row is None or not session_row.oauth_state_hash:
        return RedirectResponse(f"{settings.app_url}/app/pages?meta=error&reason=state")
    if not token_hash(state) == session_row.oauth_state_hash:
        return RedirectResponse(f"{settings.app_url}/app/pages?meta=error&reason=state_mismatch")
    session_row.oauth_state_hash = ""
    try:
        meta = get_meta_client(settings)
        short_token = await meta.exchange_code(code, settings.meta_redirect_uri)
        long_lived = await meta.exchange_long_lived(short_token)
        user_token = long_lived["access_token"]
        accounts = await meta.me_accounts(user_token)
        if not accounts:
            return RedirectResponse(f"{settings.app_url}/app/pages?meta=error&reason=no_pages")
    except MetaAPIError as exc:
        return RedirectResponse(f"{settings.app_url}/app/pages?meta=error&reason={exc.message[:120]}")
    except Exception as exc:
        return RedirectResponse(f"{settings.app_url}/app/pages?meta=error&reason={str(exc)[:120]}")

    cipher = TokenCipher.from_secret(settings.effective_secret_key)
    connected = 0
    for account in accounts:
        page_id = str(account.get("id", ""))
        if not page_id:
            continue
        scopes = account.get("access_token") and ["pages_show_list", "pages_messaging", "pages_read_engagement"] or []
        missing = validate_scopes(scopes)
        conn = (
            await db.execute(
                select(models.PageConnection).where(
                    models.PageConnection.org_id == session_row.org_id,
                    models.PageConnection.page_id == page_id,
                )
            )
        ).scalar_one_or_none()
        
        ig_account = account.get("instagram_business_account") or {}
        instagram_user_id = str(ig_account.get("id", ""))

        if conn is None:
            conn = models.PageConnection(
                org_id=session_row.org_id,
                connected_by=session_row.user_id,
                page_id=page_id,
                page_name=str(account.get("name", "")),
                page_category=str(account.get("category", "")),
                picture_url=str(account.get("picture", {}).get("data", {}).get("url", "")),
                link=str(account.get("link", "")),
                followers_count=int(account.get("followers_count") or 0),
                meta_user_id=str(account.get("id", "")),
                instagram_user_id=instagram_user_id,
            )
            db.add(conn)
            await db.flush()
            connected += 1
        else:
            conn.instagram_user_id = instagram_user_id
            
        if account.get("access_token"):
            conn.access_token_enc = cipher.encrypt(account["access_token"])
            conn.user_token_enc = cipher.encrypt(user_token)
            conn.token_scopes = scopes or ["pages_show_list"]
            conn.is_active = True
            conn.last_error = ""
        await record_audit(db, org_id=session_row.org_id, actor_id=session_row.user_id,
                           action="page.connect", resource_type="page", resource_id=page_id,
                           ip=request.client.host if request.client else "")
        # enqueue the first import
        job = await create_job(
            db, org_id=session_row.org_id, kind="page_import",
            params={"page_connection_id": conn.id, "page_name": conn.page_name},
            created_by=session_row.user_id,
            idempotency_key=f"page-import:{conn.id}:{secrets.token_hex(4)}",
        )
        await db.commit()
        _enqueue(job.id)
    return RedirectResponse(f"{settings.app_url}/app/pages?meta=connected&count={connected}")


# --------------------------------------------------------------------------
# Pages CRUD
# --------------------------------------------------------------------------


def _page_out(conn: models.PageConnection) -> PageOut:
    return PageOut(
        id=conn.id, page_id=conn.page_id, page_name=conn.page_name,
        page_category=conn.page_category, picture_url=conn.picture_url, link=conn.link,
        followers_count=conn.followers_count, connected_at=conn.connected_at,
        last_sync_at=conn.last_sync_at, is_active=conn.is_active, last_error=conn.last_error,
        scopes=conn.token_scopes,
    )


@router.get("/pages", response_model=list[PageOut])
async def list_pages(db: DbDep, org: OrgDep, membership: MembershipDep):
    rows = await db.execute(
        select(models.PageConnection)
        .where(models.PageConnection.org_id == org.id)
        .order_by(models.PageConnection.connected_at.desc())
    )
    return [_page_out(c) for c in rows.scalars().all()]


@router.post("/pages/{page_id}/sync", response_model=PageSyncResponse, dependencies=[csrf_dep])
async def sync_page(page_id: str, db: DbDep, org: OrgDep, membership: MembershipDep, request: Request):
    if membership.role not in ("owner", "admin", "moderator"):
        raise PermissionError()
    conn = await db.get(models.PageConnection, page_id)
    if conn is None or conn.org_id != org.id:
        raise NotFoundError("الصفحة غير موجودة")
    if not conn.is_active:
        raise ConflictError("الصفحة غير نشطة — أعد ربطها")
    job = await create_job(
        db, org_id=org.id, kind="page_import",
        params={"page_connection_id": conn.id, "page_name": conn.page_name},
        created_by=membership.user_id,
        idempotency_key=f"page-sync:{conn.id}:{conn.last_sync_at.isoformat() if conn.last_sync_at else 'first'}",
    )
    await record_audit(db, org_id=org.id, actor_id=membership.user_id, action="page.sync",
                       resource_type="page", resource_id=page_id,
                       ip=request.client.host if request.client else "")
    await db.commit()
    _enqueue(job.id)
    return PageSyncResponse(job_id=job.id)


@router.post("/pages/{page_id}/disconnect", response_model=DisconnectResponse, dependencies=[csrf_dep])
async def disconnect_page(page_id: str, db: DbDep, org: OrgDep, membership: MembershipDep, request: Request):
    if membership.role not in ("owner", "admin"):
        raise PermissionError()
    conn = await db.get(models.PageConnection, page_id)
    if conn is None or conn.org_id != org.id:
        raise NotFoundError("الصفحة غير موجودة")
    settings: Settings = request.app.state.settings
    if conn.user_token_enc and settings.meta_app_id:
        try:
            cipher = TokenCipher.from_secret(settings.effective_secret_key)
            user_token = cipher.decrypt(conn.user_token_enc)
            await get_meta_client(settings).revoke(user_token)
        except Exception:
            pass  # best-effort revoke; we still deactivate locally
    conn.is_active = False
    conn.access_token_enc = ""
    conn.user_token_enc = ""
    conn.last_error = "تم قطع الاتصال يدويًا"
    await record_audit(db, org_id=org.id, actor_id=membership.user_id, action="page.disconnect",
                       resource_type="page", resource_id=page_id,
                       ip=request.client.host if request.client else "")
    await db.commit()
    return DisconnectResponse()


# --------------------------------------------------------------------------
# Meta webhooks (real-time page events)
# --------------------------------------------------------------------------


@router.get("/meta/webhooks")
async def webhook_verify(
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
):
    try:
        return verify_hub_challenge(hub_mode or "", hub_verify_token or "", hub_challenge or "")
    except ValueError as exc:
        raise APIError(str(exc)) from exc


@router.post("/meta/webhooks")
async def webhook_events(request: Request, db: DbDep):
    settings: Settings = request.app.state.settings
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256")
    if not verify_signature(body, signature):
        raise PermissionError("توقيع webhook غير صالح")
    import json

    payload = json.loads(body or b"{}")
    events = normalize_events(payload)
    handled = 0
    for event in events:
        page_id = event["page_id"]
        conn = (
            await db.execute(
                select(models.PageConnection).where(
                    models.PageConnection.page_id == page_id,
                    models.PageConnection.is_active.is_(True),
                )
            )
        ).scalars().first()
        if conn is None:
            continue
        messaging = event["messaging"]
        message = messaging.get("message") or {}
        mid = message.get("mid")
        text = message.get("text", "")
        sender = messaging.get("sender", {})
        recipient = messaging.get("recipient", {})

        # split attachments: images/videos -> vision, audio -> transcription
        media_urls: list[str] = []
        audio_urls: list[str] = []
        for att in (message.get("attachments") or {}).get("data") or []:
            kind = _classify_attachment(att)
            if kind == "audio":
                url = att.get("file_url") or ""
                if url:
                    audio_urls.append(url)
            elif kind in ("image", "video"):
                img = att.get("image_data") or {}
                vid = att.get("video_data") or {}
                url = att.get("file_url") or img.get("url") or vid.get("url")
                if url:
                    media_urls.append(url)
        if not mid:
            continue
        msg = await ingest_incoming_message(
            db,
            org_id=conn.org_id,
            conn=conn,
            sender_id=str(sender.get("id", "")),
            sender_name=str(sender.get("name", "")),
            message_id=str(mid),
            text=text,
            created_time=messaging.get("timestamp"),
            media_urls=media_urls,
            audio_urls=audio_urls,
        )
        handled += 1

        # Trigger auto-reply in background if enabled and it's a customer message
        if msg and msg.sender_type == "customer" and conn.auto_reply_enabled:
            import asyncio
            from ..db import get_session_factory
            from ..config import get_settings
            from ..services.ai.manager import get_provider_manager

            async def run_auto_reply(conv_id, page_conn_id, msg_id):
                settings = get_settings()
                factory = get_session_factory(settings)
                async with factory() as session:
                    conv = await session.get(models.Conversation, conv_id)
                    page = await session.get(models.PageConnection, page_conn_id)
                    if conv and page:
                        from ..services.pipeline.auto_reply import handle_auto_reply
                        providers = get_provider_manager(settings)
                        await handle_auto_reply(
                            session, settings, providers, conv, page,
                            trigger_message_id=msg_id,
                        )

            # Keep a reference to the task so it is never garbage-collected
            # mid-flight, and surface failures instead of swallowing them.
            task = asyncio.create_task(run_auto_reply(msg.conversation_id, conn.id, msg.id))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

    await db.commit()
    return {"ok": True, "received": len(events), "handled": handled}


# Module-level registry so background auto-reply tasks are not GC'd.
_background_tasks: set = set()


def _enqueue(job_id: str) -> None:
    """Route job to Celery when configured, else the in-process executor polls."""
    settings = get_settings()
    if settings.redis_url:
        try:
            from ..services.jobs.tasks import enqueue_job

            enqueue_job(job_id)
        except Exception:
            pass  # in-process executor will pick it up as fallback
