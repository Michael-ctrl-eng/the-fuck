from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — auto-create missing tables
    from sqlalchemy import text
    from app.database import engine
    try:
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id UUID PRIMARY KEY,
                    tenant_id UUID NOT NULL REFERENCES tenants(id),
                    usage_type VARCHAR(20) NOT NULL,
                    model VARCHAR(100) NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_token_usage_tenant ON token_usage(tenant_id)"))
            # Add missing columns (idempotent)
            migrations = [
                ("orders", "payment_phone_last2", "VARCHAR(10)"),
                ("orders", "payment_trx_id", "VARCHAR(50)"),
                ("tenants", "delivery_inside_dhaka", "NUMERIC(10,2) DEFAULT 80"),
                ("tenants", "delivery_outside_dhaka", "NUMERIC(10,2) DEFAULT 150"),
                ("tenants", "free_delivery_above", "NUMERIC(10,2)"),
            ]
            for table, col, coltype in migrations:
                try:
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))
                except Exception:
                    pass
    except Exception:
        pass  # DB may not be ready yet
    yield
    # Shutdown
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
