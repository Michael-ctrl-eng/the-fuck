"""Dev-mode sample ingestion.

Only mounted when APP_ENV=dev. Feeds bundled sample conversations through
the REAL pipeline (reconstruct → analyze → quality → dataset → memory) by
pre-seeding the fetch/validate checkpoints; nothing is faked — the stages
that run afterwards are the production ones.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Request
from sqlalchemy import select

from .. import models
from ..deps import DbDep, MembershipDep, OrgDep, UserDep, csrf_dep
from ..errors import NotFoundError, PermissionError
from ..schemas import DevRunSampleRequest, DevSampleListResponse
from ..services.pipeline import create_job

router = APIRouter(prefix="/api/dev", tags=["dev"])

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "sample_data"


def _sample_names() -> list[dict]:
    if not SAMPLES_DIR.exists():
        return []
    return [
        {"name": p.stem, "title": (json.loads(p.read_text(encoding="utf-8")).get("title", p.stem))}
        for p in sorted(SAMPLES_DIR.glob("*.json"))
    ]


@router.get("/samples", response_model=DevSampleListResponse)
async def list_samples(db: DbDep, org: OrgDep, membership: MembershipDep):
    return DevSampleListResponse(samples=_sample_names())


@router.post("/pipeline/run-sample", dependencies=[csrf_dep])
async def run_sample(body: DevRunSampleRequest, db: DbDep, org: OrgDep, membership: MembershipDep, request: Request):
    settings = request.app.state.settings
    if not settings.is_dev:
        raise PermissionError("غير متاح خارج بيئة التطوير")
    if membership.role not in ("owner", "admin", "moderator"):
        raise PermissionError()
    sample_file = (SAMPLES_DIR / f"{body.sample}.json").resolve()
    if not sample_file.is_relative_to(SAMPLES_DIR.resolve()) or not sample_file.exists():
        raise NotFoundError("العينة غير موجودة")
    data = json.loads(sample_file.read_text(encoding="utf-8"))
    conversations = data.get("conversations", [])

    # page connection for the sample — use the sample's own page id so the
    # pipeline classifies page-sent messages correctly (as real Meta data).
    sample_page = data.get("page") or {}
    sample_page_id = str(sample_page.get("id") or f"sample-{body.sample[:24]}")
    conn = (
        await db.execute(
            select(models.PageConnection).where(
                models.PageConnection.org_id == org.id,
                models.PageConnection.page_id == sample_page_id,
            )
        )
    ).scalar_one_or_none()
    if conn is None:
        conn = models.PageConnection(
            org_id=org.id,
            connected_by=membership.user_id,
            page_id=sample_page_id,
            page_name=body.page_name,
            page_category="تطوير",
            is_active=True,
        )
        db.add(conn)
    else:
        conn.page_name = body.page_name
    await db.flush()

    # persist raw payloads exactly like the fetch stage would
    from ..services import get_storage

    storage = get_storage(settings)
    job = await create_job(
        db, org_id=org.id, kind="page_import",
        params={"page_connection_id": conn.id, "page_name": body.page_name, "dev_sample": True},
        created_by=membership.user_id,
        idempotency_key=f"dev-sample:{body.sample}:{org.id}:{conn.id}",
    )
    raw_keys = []
    for i, conv in enumerate(conversations):
        key = f"orgs/{org.id}/raw/{job.id}/sample_{i}.json"
        payload = {
            "conversation": conv,
            "page_id": conn.page_id,
            "page_name": body.page_name,
            "fetched_at": models.utcnow().isoformat(),
            "_dev_sample": True,
        }
        await storage.put_object(key, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json")
        raw_keys.append(key)

    # seed checkpoints so fetch/validate are skipped; the rest runs for real
    job.checkpoint = {
        "raw_keys": raw_keys,
        "fetched_conversations": len(raw_keys),
        "processed_conversations": 0,
        "cursor": None,
        "pages": 1,
        "page_connection_id": conn.id,
        "page_name": body.page_name,
        "completed_stages": ["fetch", "validate"],
    }
    await db.commit()

    from ..routers.pages import _enqueue

    _enqueue(job.id)
    return {"job_id": job.id, "conversations": len(raw_keys), "page_id": conn.id}
