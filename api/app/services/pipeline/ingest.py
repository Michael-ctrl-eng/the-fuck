"""Stage 1 (fetch) and Stage 2 (validate).

Fetch: paginated Meta Graph API pull with rate limiting, raw payload
persistence to storage, checkpointed pagination cursor, resumability and
cancellation between pages.

Validate: structural validation of stored payloads with honest counts.
"""

from __future__ import annotations

import json
from typing import Any

from ... import models
from ..meta_client import MetaAPIError
from .context import StageContext, StageResult

MAX_PAGES = 100
PAGE_SIZE = 50


async def _load_page_connection(ctx: StageContext) -> models.PageConnection:
    conn_id = ctx.job.params.get("page_connection_id") or ctx.job.checkpoint.get("page_connection_id")
    if not conn_id:
        raise RuntimeError("job missing page_connection_id param")
    conn = await ctx.session.get(models.PageConnection, conn_id)
    if conn is None or conn.org_id != ctx.job.org_id:
        raise RuntimeError("page connection not found or not in org scope")
    if not conn.is_active:
        raise RuntimeError("الصفحة غير نشطة — أعد ربطها من إعدادات الصفحات")
    return conn


async def _token_or_refresh(ctx: StageContext, conn: models.PageConnection) -> str:
    from ...security import TokenCipher

    cipher = TokenCipher.from_secret(ctx.settings.effective_secret_key)
    token = cipher.decrypt(conn.access_token_enc) if conn.access_token_enc else ""
    if token and conn.token_expires_at and conn.token_expires_at > models.utcnow():
        return token
    # try refresh via stored long-lived user token
    if not conn.user_token_enc:
        raise MetaAPIError("انتهت صلاحية رمز الصفحة ولا يوجد رمز مستخدم للتجديد", code=190)
    user_token = cipher.decrypt(conn.user_token_enc)
    accounts = await ctx.meta.me_accounts(user_token)
    match = next((a for a in accounts if str(a.get("id")) == conn.page_id), None)
    if not match or not match.get("access_token"):
        raise MetaAPIError("تعذر تجديد رمز الصفحة — أعد ربط الصفحة", code=190)
    new_token = match["access_token"]
    conn.access_token_enc = cipher.encrypt(new_token)
    conn.token_expires_at = models.utcnow()
    await ctx.session.commit()
    return new_token


async def stage_fetch(ctx: StageContext) -> StageResult:
    conn = await _load_page_connection(ctx)
    token = await _token_or_refresh(ctx, conn)
    cp = ctx.checkpoint()
    cursor = cp.get("cursor")
    raw_keys = list(cp.get("raw_keys") or [])
    total_fetched = int(cp.get("fetched_conversations") or 0)
    pages = int(cp.get("pages") or 0)

    await ctx.progress(total_fetched, 0, "جلب المحادثات من ميتا…")
    while pages < MAX_PAGES:
        if await ctx.check_cancelled():
            return StageResult(done=total_fetched, message="أُلغي الجلب")
        items, next_cursor = await ctx.meta.list_conversations(
            token, conn.page_id, after=cursor, limit=PAGE_SIZE
        )
        pages += 1
        if items:
            for item in items:
                conv_id = str(item.get("id", ""))
                key = f"orgs/{ctx.job.org_id}/raw/{ctx.job.id}/{conv_id}.json"
                payload = {
                    "conversation": item,
                    "page_id": conn.page_id,
                    "page_name": conn.page_name,
                    "fetched_at": models.utcnow().isoformat(),
                }
                await ctx.storage.put_object(key, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json")
                raw_keys.append(key)
                total_fetched += 1
                if total_fetched % 25 == 0:
                    await ctx.set_checkpoint(
                        cursor=cursor, raw_keys=raw_keys[-2000:],
                        fetched_conversations=total_fetched, pages=pages,
                    )
                    await ctx.progress(total_fetched, total_fetched, f"تم جلب {total_fetched} محادثة")
        if not next_cursor:
            break
        cursor = next_cursor
        await ctx.set_checkpoint(cursor=cursor, raw_keys=raw_keys[-2000:],
                                 fetched_conversations=total_fetched, pages=pages)

    await ctx.set_checkpoint(cursor=cursor, raw_keys=raw_keys[-2000:],
                             fetched_conversations=total_fetched, pages=pages,
                             page_connection_id=conn.id)
    conn.last_sync_at = models.utcnow()
    conn.last_error = ""
    await ctx.session.commit()
    return StageResult(
        done=total_fetched, total=total_fetched,
        message=f"تم جلب {total_fetched} محادثة وتخزينها خامًا",
    )


async def stage_validate(ctx: StageContext) -> StageResult:
    cp = ctx.checkpoint()
    raw_keys = list(cp.get("raw_keys") or [])
    valid, invalid = 0, 0
    problems: list[str] = []
    for idx, key in enumerate(raw_keys):
        if idx % 50 == 0 and await ctx.check_cancelled():
            return StageResult(done=valid, message="أُلغي التحقق")
        try:
            data = json.loads(await ctx.storage.get_object(key))
            conv = data.get("conversation") or {}
            msgs = (conv.get("messages") or {}).get("data") or []
            if not conv.get("id"):
                raise ValueError("missing conversation id")
            cleaned = [m for m in msgs if m.get("id") and (m.get("message") or m.get("sticker") or m.get("attachments"))]
            if len(cleaned) != len(msgs):
                invalid += len(msgs) - len(cleaned)
            data["_validated"] = True
            data["_valid_messages"] = len(cleaned)
            await ctx.storage.put_object(key, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json")
            valid += 1
        except Exception as exc:
            invalid += 1
            problems.append(f"{key}: {exc}")
            if len(problems) > 20:
                break
    await ctx.set_checkpoint(validated=True, valid_count=valid, invalid_count=invalid)
    await ctx.progress(valid, max(1, valid + invalid), f"تم التحقق من {valid} محادثة")
    return StageResult(
        done=valid, total=valid + invalid,
        message=f"صالح: {valid}، مرفوض: {invalid}",
        partial=invalid > 0,
        notes=problems[:10],
    )
