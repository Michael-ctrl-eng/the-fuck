from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request
from sqlalchemy import or_, select

from .. import models
from ..audit import record_audit
from ..deps import DbDep, MembershipDep, OrgDep, UserDep, csrf_dep
from ..errors import APIError, NotFoundError, PermissionError
from ..schemas import (
    InboxItem,
    InboxResponse,
    InboxStats,
    ResolveFlagRequest,
)
from ..services.sse import broker

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


async def _page_names(db, org_id: str) -> dict[str, str]:
    rows = await db.execute(
        select(models.PageConnection).where(models.PageConnection.org_id == org_id)
    )
    return {c.id: c.page_name for c in rows.scalars().all()}


@router.get("", response_model=InboxResponse)
async def list_inbox(db: DbDep, org: OrgDep, membership: MembershipDep, cursor: str | None = None, limit: int = 30):
    limit = max(1, min(limit, 100))
    page_names = await _page_names(db, org.id)
    items: list[InboxItem] = []
    conv_page: dict[str, str] = {}
    conv_pid: dict[str, str] = {}

    async def _page_for(conv_id: str) -> str:
        if conv_id not in conv_page:
            conv = await db.get(models.Conversation, conv_id)
            conv_pid[conv_id] = conv.page_id if conv else ""
            conv_page[conv_id] = page_names.get(conv_pid[conv_id], "")
        return conv_page[conv_id]

    # pending AI responses
    resp_stmt = select(models.AiResponse).where(
        models.AiResponse.org_id == org.id,
        models.AiResponse.status == "pending_approval",
    )
    if cursor:
        try:
            last_ts, last_id = cursor.split("|", 1)
            last_dt = datetime.fromisoformat(last_ts)
        except (ValueError, AttributeError):
            raise APIError("مؤشر ترقيم غير صالح")
        resp_stmt = resp_stmt.where(
            or_(
                models.AiResponse.created_at < last_dt,
                (models.AiResponse.created_at == last_dt)
                & (models.AiResponse.id < last_id),
            )
        )
    resp_stmt = resp_stmt.order_by(models.AiResponse.created_at.desc(), models.AiResponse.id.desc()).limit(limit + 1)
    resp_rows = (await db.execute(resp_stmt)).scalars().all()
    has_more = len(resp_rows) > limit
    for r in list(resp_rows[:limit]):
        items.append(InboxItem(
            type="response", id=r.id, conversation_id=r.conversation_id,
            page_name=await _page_for(r.conversation_id),
            severity="info", summary="رد ذكي بانتظار المراجعة", text=r.text,
            created_at=r.created_at,
            payload={"status": r.status, "provider": r.provider, "model": r.model, "rationale": r.rationale},
        ))

    # open moderation flags
    flag_stmt = select(models.ModerationDecision).where(
        models.ModerationDecision.org_id == org.id,
        models.ModerationDecision.status == "open",
    )
    flag_stmt = flag_stmt.order_by(models.ModerationDecision.created_at.desc()).limit(limit + 1)
    flag_rows = (await db.execute(flag_stmt)).scalars().all()
    for f in flag_rows:
        conv = await db.get(models.Conversation, f.conversation_id)
        msg = await db.get(models.Message, f.message_id) if f.message_id else None
        items.append(InboxItem(
            type="flag", id=f.id, conversation_id=f.conversation_id,
            page_name=page_names.get(conv.page_id if conv else "", ""),
            severity=f.severity, summary=f.reason or "علامة مراجعة", text=msg.text_raw if msg else "",
            created_at=f.created_at,
            payload={"decision": f.decision, "ai_rationale": f.ai_rationale},
        ))

    items.sort(key=lambda it: it.created_at, reverse=True)
    items = items[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = f"{last.created_at.isoformat()}|{last.id}"
    return InboxResponse(items=items, next_cursor=next_cursor)


@router.get("/stats", response_model=InboxStats)
async def inbox_stats(db: DbDep, org: OrgDep, membership: MembershipDep):
    pending = (
        await db.execute(
            select(models.AiResponse).where(
                models.AiResponse.org_id == org.id,
                models.AiResponse.status == "pending_approval",
            )
        )
    ).scalars().all()
    flags = (
        await db.execute(
            select(models.ModerationDecision).where(
                models.ModerationDecision.org_id == org.id,
                models.ModerationDecision.status == "open",
            )
        )
    ).scalars().all()
    escalated = [f for f in flags if f.decision == "escalate"]
    from datetime import timezone

    today = models.utcnow().date()
    day_start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    convs_today = (
        await db.execute(
            select(models.Conversation).where(
                models.Conversation.org_id == org.id,
                models.Conversation.created_at >= day_start,
            )
        )
    ).scalars().all()
    return InboxStats(
        pending_reviews=len(pending),
        open_flags=len(flags),
        escalated=len(escalated),
        conversations_today=len(convs_today),
    )


@router.post("/flags/{flag_id}/resolve", dependencies=[csrf_dep])
async def resolve_flag(flag_id: str, body: ResolveFlagRequest, db: DbDep, org: OrgDep, membership: MembershipDep, request: Request):
    if membership.role not in ("owner", "admin", "moderator"):
        raise PermissionError()
    flag = await db.get(models.ModerationDecision, flag_id)
    if flag is None or flag.org_id != org.id:
        raise NotFoundError("العلامة غير موجودة")
    flag.status = body.decision
    flag.resolved_by = membership.user_id
    flag.resolved_at = models.utcnow()
    if body.decision == "escalated":
        flag.decision = "escalate"
        conv = await db.get(models.Conversation, flag.conversation_id)
        if conv:
            conv.is_flagged = True
    await record_audit(db, org_id=org.id, actor_id=membership.user_id, action="flag.resolve",
                       resource_type="moderation", resource_id=flag.id,
                       details={"decision": body.decision, "note": body.note},
                       ip=request.client.host if request.client else "")
    await db.commit()
    await broker.publish(org.id, "inbox.updated", {"org_id": org.id})
    return {"ok": True}
