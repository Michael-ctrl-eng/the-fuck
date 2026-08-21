"""Stage: Build per-page personality (style profile + knowledge base).

Runs after analyze — extracts the page's speaking style, product catalog,
FAQ, and shipping rules from its conversation history. This is what makes
the AI agent sound exactly like the page, not generic.
"""

from __future__ import annotations

from ... import models
from ...config import Settings
from ..page_personality import build_and_persist_personality
from .context import StageContext, StageResult


async def stage_personality(ctx: StageContext) -> StageResult:
    """Build style profile + knowledge base for each page connection."""
    from sqlalchemy import select

    conn_id = ctx.job.params.get("page_connection_id")

    # Get page connections to build personality for
    if conn_id:
        rows = await ctx.session.execute(
            select(models.PageConnection).where(models.PageConnection.id == conn_id)
        )
    else:
        rows = await ctx.session.execute(
            select(models.PageConnection).where(models.PageConnection.org_id == ctx.job.org_id)
        )

    pages = list(rows.scalars().all())
    done = 0
    for page in pages:
        if await ctx.check_cancelled():
            return StageResult(done=done, total=len(pages), message="تم إلغاء بناء الأسلوب")
        try:
            await build_and_persist_personality(ctx.session, page, ctx.settings)
            done += 1
            await ctx.progress(done, len(pages), f"بناء أسلوب {page.page_name}")
        except Exception as exc:
            await ctx.note(f"فشل بناء أسلوب {page.page_name}: {exc}")
            ctx.session.rollback()
            done += 1

    await ctx.session.commit()
    return StageResult(
        done=done,
        total=len(pages),
        message=f"تم بناء أسلوب {done}/{len(pages)} صفحة",
    )
