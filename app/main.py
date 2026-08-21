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
                ("tenants", "delivery_inside_cairo", "NUMERIC(10,2) DEFAULT 35"),
                ("tenants", "delivery_outside_cairo", "NUMERIC(10,2) DEFAULT 60"),
                ("tenants", "free_delivery_above", "NUMERIC(10,2)"),
                ("tenants", "payment_methods", "JSONB"),
                ("tenants", "order_api_config", "JSONB"),
                ("tenants", "style_profile", "JSONB"),
                ("tenants", "knowledge_base", "JSONB"),
                ("tenants", "knowledge_built_at", "TIMESTAMP"),
                ("tenants", "ig_user_id", "VARCHAR(64)"),
                ("tenants", "ig_access_token", "TEXT"),
                ("tenants", "wa_phone_number_id", "VARCHAR(64)"),
                ("tenants", "wa_access_token", "TEXT"),
                ("tenants", "wa_waba_id", "VARCHAR(64)"),
                ("customers", "channel", "VARCHAR(20) DEFAULT 'messenger'"),
                ("customers", "governorate", "VARCHAR(100)"),
                ("customers", "city", "VARCHAR(100)"),
                ("customers", "area", "VARCHAR(100)"),
                ("customers", "address_detail", "TEXT"),
                ("messages", "channel", "VARCHAR(20) DEFAULT 'messenger'"),
                ("messages", "media_urls", "JSON"),
                ("orders", "api_status", "VARCHAR(20)"),
                ("orders", "api_response", "TEXT"),
                ("orders", "api_status_code", "INTEGER"),
                ("orders", "api_called_at", "TIMESTAMP"),
                ("orders", "api_external_id", "VARCHAR(100)"),
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
    description="AI-powered sales chatbot platform for Egyptian Facebook/Instagram/WhatsApp pages. "
    "Handles customer conversations in Egyptian Arabic/English via Messenger.",
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
