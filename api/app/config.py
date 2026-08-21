from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_KEY = "dev-insecure-secret-key-change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- environment -------------------------------------------------------
    app_env: str = "dev"  # dev | test | prod
    app_name: str = "raqib"
    app_url: str = "http://localhost:5173"

    # --- auth / sessions ---------------------------------------------------
    secret_key: str = ""
    session_ttl_hours: int = 168
    csrf_enabled: bool = True

    # --- database ----------------------------------------------------------
    database_url: str = ""
    db_backend: str = ""  # auto | postgres | sqlite
    sqlite_path: str = "./data/raqib.db"

    # --- redis / jobs ------------------------------------------------------
    redis_url: str = ""  # empty => in-process executor + in-memory rate limiter

    # --- storage -----------------------------------------------------------
    storage_dir: str = "./storage"
    max_attachment_bytes: int = 20 * 1024 * 1024

    # --- store scraping (product availability / price / shipping) -----------
    store_url: str = ""  # e.g. https://my-store.com (salla/zid/shopify) — used by scraper
    store_search_timeout: float = 15.0

    # --- Meta Graph API ----------------------------------------------------
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_api_version: str = "v21.0"
    meta_redirect_uri: str = ""
    meta_webhook_verify_token: str = ""
    meta_http_timeout: float = 30.0
    meta_page_fields: str = (
        "id,name,access_token,link,category,verification_status,"
        "followers_count,picture,instagram_business_account"
    )

    # --- AI ------------------------------------------------------------------
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b-instruct-q4_K_M"
    ollama_fallback_model: str = "qwen2.5:3b-instruct-q4_K_M"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    embedding_batch_size: int = 16

    # --- Speech-to-text (voice notes) ----------------------------------------
    # faster-whisper model: tiny | base | small | medium | large-v3
    # larger models understand Egyptian Arabic + English code-switching better
    # but are slower; medium is the sweet spot for CPU/laptops.
    whisper_model: str = "medium"
    whisper_device: str = "auto"  # auto | cpu | cuda
    whisper_compute_type: str = "auto"  # auto | int8 | float16 | float32
    whisper_language: str = ""  # empty => auto-detect (Arabic + English mixed)
    whisper_max_audio_seconds: int = 900  # cap per voice note (15 min)
    whisper_download_timeout: float = 30.0  # seconds to download the audio file
    whisper_max_audio_bytes: int = 50 * 1024 * 1024  # hard size cap (50 MB)
    whisper_concurrency: int = 2  # parallel transcriptions across pages
    whisper_beam_size: int = 1  # 1 = fastest, 5 = most accurate

    # --- Knock notifications -------------------------------------------------
    knock_api_key: str = ""
    knock_signing_key: str = ""
    knock_workflow_verify: str = "raqib-verify-email"
    knock_workflow_import: str = "raqib-import-done"
    knock_workflow_escalation: str = "raqib-escalation"
    knock_workflow_review: str = "raqib-review-queue"

    # --- observability -------------------------------------------------------
    log_level: str = "INFO"

    # -------------------------------------------------------------------------
    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def effective_secret_key(self) -> str:
        if self.secret_key:
            return self.secret_key
        if self.is_prod:
            raise RuntimeError("SECRET_KEY is required in production")
        return DEV_SECRET_KEY

    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        if self.db_backend == "postgres":
            return "postgresql+asyncpg://raqib:raqib@localhost:5432/raqib"
        return f"sqlite+aiosqlite:///{self.sqlite_path}"

    @property
    def is_sqlite(self) -> bool:
        return self.effective_database_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.effective_database_url.startswith("postgresql")

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir).resolve()

    @property
    def sqlite_file(self) -> Path:
        return Path(self.sqlite_path).resolve()

    @property
    def ollama_models(self) -> list[str]:
        return [self.ollama_model, self.ollama_fallback_model]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
