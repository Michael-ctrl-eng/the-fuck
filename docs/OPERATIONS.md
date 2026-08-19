# Operations — رقيب (Raqib) Production Runbook

Everything in this runbook is self-hosted and zero-cost. The **only external API key**
is Knock (`KNOCK_API_KEY`, `KNOCK_SIGNING_KEY`).

## 1. Services

| Service | Role | Port (default) |
|---|---|---|
| PostgreSQL 16 + pgvector | Primary database + vector index | 5432 |
| Redis | Celery broker, rate limiting, caches | 6379 |
| API (uvicorn) | FastAPI app | 8000 |
| Worker (celery) | Async pipeline execution | — |
| Ollama | Local LLM inference | 11434 |
| (optional) Vite dev server | Frontend in development | 5173 |

## 2. Database

```bash
# Ubuntu/Debian example
sudo apt install postgresql-16 postgresql-16-pgvector
sudo -u postgres psql -c "CREATE USER raqib WITH PASSWORD 'STRONG_DB_PASSWORD';"
sudo -u postgres psql -c "CREATE DATABASE raqib OWNER raqib;"
sudo -u postgres psql -d raqib -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Point the app at it:

```bash
export DATABASE_URL="postgresql+asyncpg://raqib:STRONG_DB_PASSWORD@127.0.0.1:5432/raqib"
export SECRET_KEY="$(openssl rand -hex 32)"   # REQUIRED in prod; also encrypts Meta tokens
```

Apply migrations:

```bash
.venv/bin/alembic -c api/alembic.ini upgrade head
```

## 3. Redis + Celery

```bash
export REDIS_URL="redis://127.0.0.1:6379/0"
.venv/bin/celery -A api.app.services.jobs.celery_app worker --loglevel=INFO --concurrency=2
```

- Job state lives in Postgres (`jobs`, `job_events`); Redis is only the broker + rate
  limiter, so a Redis restart never loses job progress.
- Checkpoints make workers resumable after crash; `PARTIAL`/`FAILED` jobs can be
  retried or reprocessed from the dead-letter list in the Jobs UI.
- Without `REDIS_URL` the API runs an in-process executor — fine for dev, not for prod.

## 4. Ollama (LLM) + embeddings

```bash
# Install Ollama, then pull the models
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull qwen2.5:3b-instruct-q4_K_M     # interactive-path fallback
```

```bash
export OLLAMA_URL="http://127.0.0.1:11434"
export OLLAMA_MODEL="qwen2.5:7b-instruct-q4_K_M"
export OLLAMA_FALLBACK_MODEL="qwen2.5:3b-instruct-q4_K_M"
```

Embeddings (`BAAI/bge-m3`) download from Hugging Face on first worker start
(~2 GB, one-time). Set `EMBEDDING_MODEL` to a lighter sentence-transformers model
if RAM is constrained. If Ollama is unreachable, the pipeline degrades gracefully to
deterministic Arabic lexical analysis — nothing blocks, quality is reduced.

`api/requirements-ai.txt` (sentence-transformers, camel-tools) is optional for the
CPU/AI features; core API runs on `api/requirements.txt` alone.

## 5. Meta app

1. Create an app at developers.facebook.com (Business type recommended).
2. Add **Facebook Login for Business** + **Messenger** products; configure the OAuth
   redirect URI to `{APP_URL}/api/auth/meta/callback`.
3. Request the scopes listed in `docs/META_INTEGRATION.md` (§1). `pages_messaging`
   needs app review for production; test mode works with approved testers.
4. Configure webhooks (optional): callback URL `{APP_URL}/api/webhooks/meta`,
   verify token = `META_WEBHOOK_VERIFY_TOKEN`, subscribe to `messages`.

```bash
export META_APP_ID="..."
export META_APP_SECRET="..."
export META_REDIRECT_URI="https://your-domain.example/api/auth/meta/callback"
export META_WEBHOOK_VERIFY_TOKEN="random-string"   # optional
export APP_URL="https://your-domain.example"
```

## 6. Knock (the only external key)

1. Create a free Knock account; add the four workflows (names configurable):
   `raqib-verify-email`, `raqib-import-done`, `raqib-escalation`, `raqib-review-queue`.
2. Paste `KNOCK_API_KEY` and `KNOCK_SIGNING_KEY` into the project's Keys/API keys UI
   (never commit them). Without them, Raqib runs fully but silently skips email/
   notification sends.

## 7. API server

```bash
export APP_ENV="prod"
export APP_URL="https://your-domain.example"
.venv/bin/uvicorn api.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Behind a reverse proxy (Caddy/Nginx) for TLS. The app serves the built SPA
(`dist/`) at `/` itself when present, so one origin handles both API and UI.

Health: `/health` (liveness), `/ready` (DB/Redis checks), `/metrics` (Prometheus).

## 8. Frontend build

```bash
bun install
bun run build      # -> dist/ (served by the API in prod)
```

## 9. Backups & maintenance

- `pg_dump` the Postgres DB (conversations, decisions, jobs — all business state).
- `storage/` contains raw payloads/attachments; back it up or migrate to MinIO/S3
  through the `StorageProvider` interface (paths in `stored_objects` stay valid).
- Rotate `SECRET_KEY` by re-encrypting stored tokens; never change it silently —
  tokens become undecryptable.
- Watch `/metrics` (request latency, job durations, rate-limit drop counts) and the
  DB-backed `error_events` table for silent failures.

## 10. Verification checklist

- [ ] `bun tsc -b --noEmit` passes
- [ ] `bun run build` succeeds
- [ ] `.venv/bin/python -m pytest -q` passes (35 tests)
- [ ] `/health` and `/ready` return 200
- [ ] Connect a real Page → run an import → conversations appear with dialect/analysis
- [ ] Flagged conversation appears in the inbox → approve/edit a reply → send succeeds
- [ ] Knock receives verify-email on registration (if keys configured)
