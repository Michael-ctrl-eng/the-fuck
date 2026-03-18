from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    from app.database import engine
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered sales chatbot platform for Bangladeshi Facebook pages. "
    "Handles customer conversations in Bangla/Banglish/English via Messenger.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Mount static files for dashboard
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="dashboard/templates")

# Register API routes
from app.api.router import api_router  # noqa: E402

app.include_router(api_router)

# Register dashboard routes
from app.api.dashboard import dashboard_router  # noqa: E402

app.include_router(dashboard_router)


# Redirect root to dashboard
from fastapi.responses import RedirectResponse  # noqa: E402


@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/dashboard")
