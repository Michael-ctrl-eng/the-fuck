import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_tenant
from app.models.crawl_job import CrawlJob
from app.schemas.webhook import CrawlRequest, CrawlJobResponse

router = APIRouter(prefix="/api/tenants/{tenant_id}/crawl", tags=["Crawling"])


@router.post("", response_model=CrawlJobResponse, status_code=201)
async def start_crawl(
    req: CrawlRequest,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    job = CrawlJob(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        url=req.url,
        status="pending",
    )
    db.add(job)
    await db.flush()

    # Trigger async crawl task
    try:
        from app.tasks.crawl_tasks import run_crawl_pipeline
        task = run_crawl_pipeline.delay(str(job.id), str(tenant.id), req.url, req.depth)
        job.celery_task_id = task.id
        await db.flush()
    except Exception:
        # Celery not available — job stays in pending, can be processed later
        pass

    return CrawlJobResponse(
        id=str(job.id),
        url=job.url,
        status=job.status,
        pages_found=job.pages_found,
        products_extracted=job.products_extracted,
        error_message=job.error_message,
        created_at=str(job.created_at),
    )


@router.get("/jobs", response_model=list[CrawlJobResponse])
async def list_crawl_jobs(
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CrawlJob)
        .where(CrawlJob.tenant_id == tenant.id)
        .order_by(CrawlJob.created_at.desc())
        .limit(20)
    )
    jobs = result.scalars().all()
    return [
        CrawlJobResponse(
            id=str(j.id),
            url=j.url,
            status=j.status,
            pages_found=j.pages_found,
            products_extracted=j.products_extracted,
            error_message=j.error_message,
            created_at=str(j.created_at),
        )
        for j in jobs
    ]


@router.get("/jobs/{job_id}", response_model=CrawlJobResponse)
async def get_crawl_job(
    job_id: uuid.UUID,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CrawlJob).where(
            CrawlJob.id == job_id, CrawlJob.tenant_id == tenant.id
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return CrawlJobResponse(
        id=str(job.id),
        url=job.url,
        status=job.status,
        pages_found=job.pages_found,
        products_extracted=job.products_extracted,
        error_message=job.error_message,
        created_at=str(job.created_at),
    )
