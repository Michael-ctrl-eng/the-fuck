from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from .. import models
from ..audit import record_audit
from ..config import get_settings
from ..deps import DbDep, MembershipDep, OrgDep, UserDep, csrf_dep
from ..errors import APIError, ConflictError, NotFoundError, PermissionError
from ..schemas import (
    AnalyzeRequest,
    ConversationListItem,
    ConversationListResponse,
    ConversationOut,
    DraftResponseRequest,
    MessageOut,
    AnalysisOut,
    ResponseOut,
    ReviewResponseRequest,
)
from ..services.ai.manager import get_provider_manager
from ..services.meta_client import MetaAPIError, get_meta_client
from ..services.pipeline.responder import ResponderDeps, draft_response

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _conv_item(conv: models.Conversation, page_name: str = "") -> ConversationListItem:
    return ConversationListItem(
        id=conv.id,
        page_id=conv.page_id,
        page_name=page_name,
        source_conversation_id=conv.source_conversation_id,
        status=conv.status,
        dialect_label=conv.dialect_label,
        dialect_confidence=round(conv.dialect_confidence, 3),
        intent_label=conv.intent_label,
        quality_score=round(conv.quality_score, 3),
        dataset_included=conv.dataset_included,
        is_flagged=conv.is_flagged,
        message_count=len(conv.messages),
        first_message_at=conv.first_message_at,
        last_message_at=conv.last_message_at,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


async def _load_page_names(db, org_id: str) -> dict[str, str]:
    rows = await db.execute(
        select(models.PageConnection).where(models.PageConnection.org_id == org_id)
    )
    return {c.id: c.page_name for c in rows.scalars().all()}


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    db: DbDep,
    org: OrgDep,
    membership: MembershipDep,
    page_id: str | None = None,
    status: str | None = None,
    dialect: str | None = None,
    intent: str | None = None,
    q: str | None = None,
    dataset: bool | None = None,
    flagged: bool | None = None,
    cursor: str | None = None,
    limit: int = 30,
):
    limit = max(1, min(limit, 100))
    stmt = select(models.Conversation).options(
        selectinload(models.Conversation.messages)
    ).where(models.Conversation.org_id == org.id)
    if page_id:
        stmt = stmt.where(models.Conversation.page_id == page_id)
    if status:
        stmt = stmt.where(models.Conversation.status == status)
    if dialect:
        stmt = stmt.where(models.Conversation.dialect_label == dialect)
    if intent:
        stmt = stmt.where(models.Conversation.intent_label == intent)
    if dataset is not None:
        stmt = stmt.where(models.Conversation.dataset_included == dataset)
    if flagged is not None:
        stmt = stmt.where(models.Conversation.is_flagged == flagged)
    if cursor:
        try:
            last_ts, last_id = cursor.split("|", 1)
            last_dt = datetime.fromisoformat(last_ts)
        except (ValueError, AttributeError):
            raise APIError("مؤشر ترقيم غير صالح")
        stmt = stmt.where(
            or_(
                models.Conversation.updated_at < last_dt,
                (models.Conversation.updated_at == last_dt)
                & (models.Conversation.id < last_id),
            )
        )
    if q:
        # SQLite-safe search: messages belong to the org's conversations
        conv_sub = select(models.Conversation.id).where(models.Conversation.org_id == org.id)
        sub = (
            select(models.Message.conversation_id)
            .where(
                models.Message.conversation_id.in_(conv_sub),
                or_(
                    models.Message.text_normalized.ilike(f"%{q}%"),
                    models.Message.text_raw.ilike(f"%{q}%"),
                ),
            )
        )
        stmt = stmt.where(models.Conversation.id.in_(sub))

    stmt = stmt.order_by(models.Conversation.updated_at.desc(), models.Conversation.id.desc()).limit(limit + 1)
    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    items = list(rows[:limit])
    page_names = await _load_page_names(db, org.id)
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = f"{last.updated_at.isoformat()}|{last.id}"
    return ConversationListResponse(
        items=[_conv_item(c, page_names.get(c.page_id, "")) for c in items],
        next_cursor=next_cursor,
    )


async def _get_conv(db, org_id: str, conv_id: str) -> models.Conversation:
    conv = await db.get(models.Conversation, conv_id)
    if conv is None or conv.org_id != org_id:
        raise NotFoundError("المحادثة غير موجودة")
    return conv


@router.get("/{conv_id}", response_model=ConversationOut)
async def get_conversation(conv_id: str, db: DbDep, org: OrgDep, membership: MembershipDep):
    conv = await db.get(
        models.Conversation,
        conv_id,
        options=[
            selectinload(models.Conversation.messages),
            selectinload(models.Conversation.analyses),
            selectinload(models.Conversation.responses),
        ],
    )
    if conv is None or conv.org_id != org.id:
        raise NotFoundError("المحادثة غير موجودة")
    # Guard against identity-map reuse: if this instance was already loaded
    # in this session, db.get won't re-apply the eager options, so force-load.
    await db.refresh(conv, attribute_names=["messages", "analyses", "responses"])
    page = await db.get(models.PageConnection, conv.page_id)
    out = ConversationOut(
        **_conv_item(conv, page.page_name if page else "").model_dump(),
        participants=conv.participants,
        participant_names=conv.participant_names,
        messages=[MessageOut.model_validate(m) for m in conv.messages],
        analyses=[AnalysisOut.model_validate(a) for a in conv.analyses],
        responses=[ResponseOut.model_validate(r) for r in conv.responses],
    )
    return out


@router.post("/{conv_id}/analyze", response_model=ConversationOut, dependencies=[csrf_dep])
async def analyze_conversation(conv_id: str, body: AnalyzeRequest, db: DbDep, org: OrgDep, membership: MembershipDep):
    if membership.role not in ("owner", "admin", "moderator"):
        raise PermissionError()
    conv = await _get_conv(db, org.id, conv_id)
    from ..services.pipeline.analyze import analyze_single
    from ..services.pipeline.context import StageContext
    from ..services import get_storage, get_rate_limiter
    from ..services.sse import broker
    from ..services.notify import get_notifier
    from ..services.ai.manager import get_provider_manager
    from ..services.meta_client import get_meta_client

    settings = get_settings()

    class _ManualJob:
        """Minimal job facade for the manual single-conversation analysis path."""
        org_id = org.id
        id = ""
        kind = "manual_analyze"
        status = "RUNNING"
        checkpoint: dict = {}
        params: dict = {}
        result: dict = {}
        progress_done = 0
        progress_total = 0
        progress_message = ""
        stage = "analyze"
        updated_at = models.utcnow()

    fake_job = _ManualJob()
    ctx = StageContext(
        session=db, job=fake_job, settings=settings,
        meta=get_meta_client(settings), storage=get_storage(settings),
        providers=get_provider_manager(settings), notifier=get_notifier(settings),
        limiter=get_rate_limiter(settings), broker=broker,
    )
    await analyze_single(ctx, conv, force=body.force)
    await db.commit()
    # Drop the analyzed instance from the session so get_conversation loads a
    # fresh one with its eager relationships (identity-map reuse would skip
    # the eager loads and trigger async lazy-load errors).
    db.expunge(conv)
    return await get_conversation(conv_id, db, org, membership)


@router.post("/{conv_id}/responses", response_model=ResponseOut, dependencies=[csrf_dep])
async def draft_conversation_response(
    conv_id: str, body: DraftResponseRequest, db: DbDep, org: OrgDep, membership: MembershipDep, request: Request,
):
    if membership.role not in ("owner", "admin", "moderator"):
        raise PermissionError()
    conv = await _get_conv(db, org.id, conv_id)
    settings = get_settings()
    deps = ResponderDeps(
        session=db, settings=settings,
        providers=get_provider_manager(settings), org_id=org.id,
    )
    from ..services.ai.base import ModelUnavailableError

    try:
        resp = await draft_response(deps, conv, instructions=body.instructions)
    except ModelUnavailableError:
        # draft_response already persisted a failed response row with a
        # clear message; surface it so the UI can show why.
        resp = (
            await db.execute(
                select(models.AiResponse)
                .where(models.AiResponse.conversation_id == conv.id)
                .order_by(models.AiResponse.created_at.desc())
            )
        ).scalars().first()
    if resp is None:
        raise ConflictError("تعذر إنشاء مسودة الرد")
    await record_audit(db, org_id=org.id, actor_id=membership.user_id, action="response.draft",
                       resource_type="response", resource_id=resp.id,
                       ip=request.client.host if request.client else "")
    await db.commit()
    return ResponseOut.model_validate(resp)


@router.post("/{conv_id}/responses/{response_id}/review", response_model=ResponseOut, dependencies=[csrf_dep])
async def review_response(
    conv_id: str, response_id: str, body: ReviewResponseRequest,
    db: DbDep, org: OrgDep, membership: MembershipDep, request: Request,
):
    if membership.role not in ("owner", "admin", "moderator"):
        raise PermissionError()
    conv = await _get_conv(db, org.id, conv_id)
    resp = await db.get(models.AiResponse, response_id)
    if resp is None or resp.conversation_id != conv.id or resp.org_id != org.id:
        raise NotFoundError("الرد غير موجود")
    if body.decision == "approve":
        resp.status = "approved"
        resp.feedback = "approve"
    elif body.decision == "edit":
        if not body.edited_text.strip():
            raise ConflictError("أدخل النص المعدَّل")
        resp.edited_text = body.edited_text.strip()
        resp.status = "approved"
        resp.feedback = "edit"
    else:
        resp.status = "rejected"
        resp.feedback = "reject"
    resp.reviewed_by = membership.user_id
    resp.reviewed_at = models.utcnow()
    await record_audit(db, org_id=org.id, actor_id=membership.user_id, action="response.review",
                       resource_type="response", resource_id=resp.id,
                       details={"decision": body.decision, "note": body.note},
                       ip=request.client.host if request.client else "")
    await db.commit()
    return ResponseOut.model_validate(resp)


@router.post("/{conv_id}/responses/{response_id}/send", response_model=ResponseOut, dependencies=[csrf_dep])
async def send_response(
    conv_id: str, response_id: str, db: DbDep, org: OrgDep, membership: MembershipDep, request: Request,
):
    if membership.role not in ("owner", "admin", "moderator"):
        raise PermissionError()
    conv = await _get_conv(db, org.id, conv_id)
    resp = await db.get(models.AiResponse, response_id)
    if resp is None or resp.conversation_id != conv.id or resp.org_id != org.id:
        raise NotFoundError("الرد غير موجود")
    if resp.status != "approved":
        raise ConflictError("يجب اعتماد الرد قبل إرساله")
    page = await db.get(models.PageConnection, conv.page_id)
    if page is None or not page.is_active or not page.access_token_enc:
        raise ConflictError("الصفحة غير مرتبطة بميتا — لا يمكن الإرسال")
    settings = get_settings()
    from ..security import TokenCipher

    try:
        token = TokenCipher.from_secret(settings.effective_secret_key).decrypt(page.access_token_enc)
    except Exception:
        raise ConflictError("تعذر فك تشفير رمز الصفحة — أعد ربط الصفحة من الإعدادات")
    text = resp.edited_text or resp.text
    try:
        await get_meta_client(settings).send_message(token, conv.source_conversation_id, text)
        resp.status = "sent"
        resp.sent_to_meta_at = models.utcnow()
    except MetaAPIError as exc:
        resp.status = "failed"
        resp.error = exc.message
    await record_audit(db, org_id=org.id, actor_id=membership.user_id, action="response.send",
                       resource_type="response", resource_id=resp.id,
                       details={"outcome": resp.status},
                       ip=request.client.host if request.client else "")
    await db.commit()
    return ResponseOut.model_validate(resp)
