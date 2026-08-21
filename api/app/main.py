from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .config import Settings, get_settings
from .db import init_db
from .errors import APIError, error_payload
from .logging import setup_logging
from .metrics import HTTP_DURATION, HTTP_REQUESTS

log = structlog.get_logger("raqib.main")

DIST_DIR = Path(__file__).resolve().parents[2] / "dist"


class SpaStaticFiles(StaticFiles):
    """Serve the SPA build with index.html fallback for client routes."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except (StarletteHTTPException, FileNotFoundError):
            if path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        await init_db(settings)
        executor = None
        if not settings.redis_url:
            from .services.jobs import get_executor

            executor = get_executor()
            await executor.start()
        from .services.ai.transcribe import prewarm_whisper

        app.state.prewarm_task = asyncio.create_task(prewarm_whisper(settings))
        yield
        app.state.prewarm_task.cancel()
        if executor is not None:
            await executor.stop()
        from .services.rate_limit import get_rate_limiter

        await get_rate_limiter(settings).close()
        from .services.notify import get_notifier

        try:
            await get_notifier(settings).close()
        except Exception:
            pass

    app = FastAPI(
        title="رقيب API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings

    @app.middleware("http")
    async def metrics_and_logging(request: Request, call_next):
        started = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - started
        route = request.scope.get("route")
        path = route.path if route else request.url.path
        HTTP_REQUESTS.labels(method=request.method, path=path, status=response.status_code).inc()
        HTTP_DURATION.labels(method=request.method, path=path).observe(duration)
        if not path.startswith("/metrics"):
            log.info(
                "http.request",
                method=request.method, path=request.url.path, status=response.status_code,
                duration_ms=round(duration * 1000, 1),
            )
        return response

    # routers
    from .routers import auth, conversations, dev, inbox, jobs, org, pages, sse, status, owner_chat

    app.include_router(auth.router)
    app.include_router(org.router)
    app.include_router(pages.router)
    app.include_router(conversations.router)
    app.include_router(inbox.router)
    app.include_router(jobs.router)
    app.include_router(sse.router)
    app.include_router(status.router)
    app.include_router(owner_chat.router)
    if settings.is_dev:
        app.include_router(dev.router)

    # error handling
    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):
        headers = {}
        if getattr(exc, "retry_after", None):
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(status_code=exc.status_code, content=error_payload(exc), headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "بيانات الطلب غير صالحة",
                    "details": exc.errors()[:5],
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404 and not request.url.path.startswith("/api"):
            return RedirectResponse("/")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "http_error", "message": str(exc.detail)}},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        log.exception("unhandled_error", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "حدث خطأ داخلي"}},
        )

    # SPA static serving (when a production build exists)
    if DIST_DIR.exists():
        app.mount("/", SpaStaticFiles(directory=str(DIST_DIR), html=True), name="spa")

    return app


app = create_app()
