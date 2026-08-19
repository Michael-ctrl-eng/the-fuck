# رقيب — Raqib

**Arabic-first AI Page moderation & conversation-learning platform.**

Raqib is a self-hosted AI operating system for managing, understanding, learning from,
and responding to real Facebook Page conversations — built for Arabic, dialects, and
human-in-the-loop moderation. Zero monthly cost: everything is self-hosted except a
single optional external key for notifications (Knock).

## What it does

- **Real Meta OAuth2** Page connection (server-side token encryption, refresh, revoke).
- **Real conversation ingestion** — paginated Graph API sync into a resumable,
  cancellable job pipeline (validate → normalize → dedupe → reconstruct).
- **Arabic NLP** — normalization, dialect detection (MSA/Egyptian/Saudi/Gulf/Levantine/
  Iraqi/Maghrebi/mixed/arabizi), intent/entity extraction, moderation with word-boundary
  matching and light Arabic stemming.
- **Local AI** — Ollama (Qwen2.5) for analysis and drafting, bge-m3 embeddings in
  pgvector for memory retrieval. Deterministic offline fallback when Ollama is down.
- **Human-in-the-loop inbox** — approve / edit / reject AI-drafted replies; every
  outbound send goes through the real Meta Graph API.
- **Honest learning loop** — approved feedback writes to knowledge items, dataset rows,
  and memory; dataset export for downstream fine-tuning. No fake training.
- **Team workspace** — organizations, roles (owner/admin/moderator/viewer), audit log,
  SSE live job/inbox updates, Prometheus metrics.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, TypeScript, TanStack Query, `@tanstack/react-virtual`, custom RTL design system |
| API | FastAPI (Python 3.12), Pydantic v2, SQLAlchemy 2.0 async, Alembic |
| Database | PostgreSQL 16 + pgvector (SQLite fallback for dev/tests) |
| Jobs | Celery + Redis (in-process executor fallback for dev) |
| AI | Ollama `qwen2.5:7b-instruct-q4_K_M` (+3B fallback), sentence-transformers `BAAI/bge-m3` |
| Arabic NLP | camel-tools + first-party normalization/dialect/moderation modules |
| Notifications | Knock (the only external API key) |
| Observability | structlog, `/health`, `/ready`, `/metrics` (Prometheus), DB audit + error events |

## Repository layout

```
api/                 FastAPI backend
  app/routers/       auth, org, pages, conversations, inbox, jobs, sse, status, dev
  app/services/      pipeline/*, ai/*, jobs/*, arabic, meta_*, notify, storage, search
  app/models.py      SQLAlchemy models (17 tables)
  alembic/           migrations
  sample_data/       realistic Arabic sample conversations (dev seeding)
  tests/             35 tests (auth, API, Arabic NLP, jobs, pipeline)
src/                 React frontend
  lib/               API client, types, Arabic labels, formatting
  hooks/             auth + SSE live updates
  components/        app shell, custom icons, UI primitives
  pages/             landing, auth, dashboard, inbox, conversations, pages, jobs, settings
docs/                architecture audit, Meta integration, operations guide
scripts/dev.sh       dev orchestrator (API + Vite)
```

## Quick start (development)

```bash
# 1. Backend
python3 -m venv .venv
.venv/bin/pip install -r api/requirements.txt      # core
.venv/bin/pip install -r api/requirements-ai.txt   # optional: embeddings + camel-tools
cp .env.local.example .env.local                    # or set env vars (see below)

# 2. Frontend
bun install          # or npm install

# 3. Run
sh ./scripts/dev.sh  # starts API on :8000 and Vite on :5173 (proxies /api)
```

Dev defaults need nothing external: SQLite + in-process jobs + deterministic offline
analysis. Add real capabilities via env vars:

| Env var | Purpose | Required for |
|---|---|---|
| `DATABASE_URL` | PostgreSQL async URL (`postgresql+asyncpg://…`) | production persistence + pgvector |
| `REDIS_URL` | Celery broker + rate limiting | real background jobs |
| `OLLAMA_URL` | Ollama endpoint (default `http://127.0.0.1:11434`) | LLM analysis/drafting |
| `OLLAMA_MODEL` / `OLLAMA_FALLBACK_MODEL` | Qwen2.5 tags | LLM |
| `EMBEDDING_MODEL` | bge-m3 or any sentence-transformers model | memory/retrieval |
| `META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI` | Meta app credentials | real Page connect + import |
| `KNOCK_API_KEY`, `KNOCK_SIGNING_KEY` | Knock (the only external key) | email + notification workflows |
| `SECRET_KEY` | Strong random key | production session + token encryption |
| `APP_URL` | Public origin | OAuth redirects, links, webhooks |

See `docs/OPERATIONS.md` for the full production runbook (Postgres 16 + pgvector,
Redis, Celery worker, Ollama model pull, systemd/docker guidance) and
`docs/META_INTEGRATION.md` for Meta-specific setup and known API limitations.

## Demo account (test everything with one login)

A pre-made account with a verified email, an organization, and **real** data
ingested through the actual pipeline (14 Arabic conversations across
Egyptian/Gulf/Levantine samples, with dialect/intent/moderation analysis,
dataset rows, and open inbox flags) is one command away:

```bash
.venv/bin/python -m api.app.demo
```

| Field | Value |
|---|---|
| Email | `demo@raqib.app` |
| Password | `Raqib@2026` |
| Org | رقيب — تجريبي (owner) |

The seeder is idempotent (re-running updates the password and skips samples
already ingested) and never runs automatically — not part of any deploy. In
**dev/test** the login page shows a "حساب تجريبي" card with one-click
credential fill (`GET /api/auth/demo`); production always refuses it.

## Verification

```bash
bun tsc -b --noEmit          # frontend typecheck
bun run build                # production bundle
.venv/bin/python -m pytest -q  # backend tests (35)
```

## Documentation

- `docs/ARCHITECTURE_AUDIT.md` — full architecture audit (strengths, debt, security, scalability, migration)
- `docs/META_INTEGRATION.md` — Meta Graph API integration, permissions, webhooks, limitations
- `docs/OPERATIONS.md` — production deployment runbook
