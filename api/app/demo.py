"""Demo account + sample-data seeding for testing the full product.

Creates (idempotently) a pre-made account with a verified email and an
organization, then ingests the bundled Arabic sample conversations through
the REAL pipeline (reconstruct → analyze → quality → dataset → memory →
notify), so every screen — dashboard, conversations, inbox, jobs, pages,
settings — has genuine data to inspect. Nothing here fakes data: raw
payloads are written to storage and the production stage functions run
against them exactly as they would for a Meta import.

Usage (from the project root):

    .venv/bin/python -m api.app.demo

The demo account is never created automatically — run this explicitly.
In production deploys the seed is not executed (the demo-hint endpoint
also refuses to answer outside dev/test).
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import select

from . import models
from .config import Settings, get_settings
from .db import get_session_factory, init_db
from .security import hash_password
from .services import get_storage
from .services.pipeline.orchestrator import create_job, run_job

DEMO_EMAIL = "demo@raqib.app"
DEMO_PASSWORD = "Raqib@2026"
DEMO_FULL_NAME = "فريق رقيب التجريبي"
DEMO_ORG_NAME = "رقيب — تجريبي"
DEMO_ORG_SLUG = "demo-org"

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "sample_data"


async def seed_demo(settings: Settings | None = None) -> dict:
    """Idempotent seed: demo user + org + real pipeline runs over samples."""
    settings = settings or get_settings()
    await init_db(settings)
    factory = get_session_factory()

    summary: dict = {
        "user_created": False,
        "org": DEMO_ORG_NAME,
        "conversations": 0,
        "samples": [],
        "jobs": [],
    }

    async with factory() as session:
        # --- demo user ---------------------------------------------------
        user = (
            await session.execute(select(models.User).where(models.User.email == DEMO_EMAIL))
        ).scalar_one_or_none()
        if user is None:
            user = models.User(
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                full_name=DEMO_FULL_NAME,
                email_verified_at=models.utcnow(),
                is_active=True,
            )
            session.add(user)
            await session.flush()
            summary["user_created"] = True
        else:
            # Keep the documented demo password and verified state in sync.
            user.password_hash = hash_password(DEMO_PASSWORD)
            user.email_verified_at = user.email_verified_at or models.utcnow()
            user.is_active = True

        # --- org ----------------------------------------------------------
        org = (
            await session.execute(
                select(models.Organization).where(models.Organization.slug == DEMO_ORG_SLUG)
            )
        ).scalar_one_or_none()
        if org is None:
            org = models.Organization(name=DEMO_ORG_NAME, slug=DEMO_ORG_SLUG)
            session.add(org)
            await session.flush()
        membership = (
            await session.execute(
                select(models.OrgMembership).where(
                    models.OrgMembership.org_id == org.id,
                    models.OrgMembership.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if membership is None:
            session.add(models.OrgMembership(org_id=org.id, user_id=user.id, role="owner"))
        await session.commit()

        seeded = set((org.settings or {}).get("demo_seeded_samples") or [])
        storage = get_storage(settings)

        for path in sorted(SAMPLES_DIR.glob("*.json")):
            name = path.stem
            if name in seeded:
                summary["samples"].append({"name": name, "skipped": True})
                continue

            data = json.loads(path.read_text(encoding="utf-8"))
            conversations = data.get("conversations", [])
            sample_page = data.get("page") or {}
            page_id = str(sample_page.get("id") or f"sample-{name}")

            # page connection for the sample — reuse the sample's own page id
            # so the pipeline classifies page-sent messages correctly.
            conn = (
                await session.execute(
                    select(models.PageConnection).where(
                        models.PageConnection.org_id == org.id,
                        models.PageConnection.page_id == page_id,
                    )
                )
            ).scalar_one_or_none()
            if conn is None:
                conn = models.PageConnection(
                    org_id=org.id,
                    connected_by=user.id,
                    page_id=page_id,
                    page_name=str(sample_page.get("name") or name),
                    page_category="تجريبي",
                    is_active=True,
                )
                session.add(conn)
                await session.flush()

            # persist raw payloads exactly like the fetch stage would
            job = await create_job(
                session,
                org_id=org.id,
                kind="page_import",
                params={"page_connection_id": conn.id, "page_name": conn.page_name, "dev_sample": True},
                created_by=user.id,
                idempotency_key=f"demo-seed:{name}:{org.id}:{uuid.uuid4()}",
            )
            raw_keys: list[str] = []
            for i, conv in enumerate(conversations):
                key = f"orgs/{org.id}/raw/{job.id}/{name}_{i}.json"
                payload = {
                    "conversation": conv,
                    "page_id": conn.page_id,
                    "page_name": conn.page_name,
                    "fetched_at": models.utcnow().isoformat(),
                    "_dev_sample": True,
                }
                await storage.put_object(
                    key,
                    json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    "application/json",
                )
                raw_keys.append(key)

            # seed checkpoints so fetch/validate are skipped; the remaining
            # stages (reconstruct → analyze → quality → dataset → memory →
            # notify) run for real.
            job.checkpoint = {
                "raw_keys": raw_keys,
                "fetched_conversations": len(raw_keys),
                "processed_conversations": 0,
                "cursor": None,
                "pages": 1,
                "page_connection_id": conn.id,
                "page_name": conn.page_name,
                "completed_stages": ["fetch", "validate"],
            }
            conn.last_sync_at = models.utcnow()
            await session.commit()

            await run_job(job.id)

            summary["samples"].append({"name": name, "skipped": False, "conversations": len(raw_keys)})
            summary["conversations"] += len(raw_keys)
            summary["jobs"].append(job.id)
            seeded.add(name)
            org.settings = {**(org.settings or {}), "demo_seeded_samples": sorted(seeded)}
            await session.commit()

    return summary


async def main() -> int:
    settings = get_settings()
    summary = await seed_demo(settings)
    print("=" * 60)
    print("رقيب — تم تجهيز الحساب التجريبي")
    print("=" * 60)
    print(f"البريد الإلكتروني : {DEMO_EMAIL}")
    print(f"كلمة المرور       : {DEMO_PASSWORD}")
    print(f"المنظمة           : {summary['org']}")
    if summary["user_created"]:
        print("الحالة            : حساب جديد أُنشئ وتم توثيق بريده")
    else:
        print("الحالة            : الحساب موجود مسبقًا — تم تحديثه")
    print("-" * 60)
    if not summary["samples"]:
        print("العينات           : لا توجد عينات جديدة (مُجهزة سابقًا)")
    for s in summary["samples"]:
        if s.get("skipped"):
            print(f"العينة {s['name']:<20} : مجهزة مسبقًا (تم التخطي)")
        else:
            print(f"العينة {s['name']:<20} : {s['conversations']} محادثة عبر خط المعالجة الحقيقي")
    print(f"إجمالي المحادثات  : {summary['conversations']}")
    print("-" * 60)
    print("سجّل الدخول الآن بـ demo@raqib.app")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
