from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from .. import __version__
from ..config import get_settings
from ..db import get_session_factory
from ..deps import DbDep, OrgDep
from ..schemas import ApiStatusResponse, HealthResponse
from ..services.ai.manager import get_provider_manager
from ..services.notify import get_notifier

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready():
    settings = get_settings()
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        db_ok = "ok"
    except Exception:
        db_ok = "error"
    providers = get_provider_manager(settings)
    body = HealthResponse(
        status=db_ok,
        version=__version__,
        database=settings.effective_database_url.split("://")[0],
        model_available=await providers.llm_available(),
        knock_configured=get_notifier(settings).configured,
    )
    if db_ok != "ok":
        return JSONResponse(status_code=503, content=body.model_dump())
    return body


@router.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/api/status", response_model=ApiStatusResponse)
async def api_status(request: Request, db: DbDep, org: OrgDep):
    settings = request.app.state.settings
    providers = get_provider_manager(settings)
    return ApiStatusResponse(
        app_env=settings.app_env,
        version=__version__,
        database_backend="sqlite" if settings.is_sqlite else "postgresql",
        storage=str(settings.storage_path),
        model_provider=providers.llm().name,
        model_available=await providers.llm_available(),
        embedding_provider=providers.embeddings().name,
        embedding_available=await providers.embeddings_available(),
        knock_configured=get_notifier(settings).configured,
        rate_limiter="redis" if settings.redis_url else "in-memory",
        job_executor="celery" if settings.redis_url else "in-process",
    )
