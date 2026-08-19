# رقيب (Raqib) — Architecture Audit

**Date:** 2026-08-15
**Scope:** Full-stack audit of the Arabic-first AI Page moderation & conversation-learning platform.
**Stack audited:** FastAPI + SQLAlchemy 2.0 async + Alembic + PostgreSQL 16/pgvector, Celery + Redis,
Ollama (Qwen2.5), sentence-transformers (BAAI/bge-m3), camel-tools, Knock, React 18 + Vite + TypeScript.

---

## 1. Current Architecture

The product is a two-tier, self-hosted application:

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend — React 18 SPA (src/)                                 │
│  RTL-first custom design system, TanStack Query, react-virtual, │
│  SSE live updates. Served by the API (SpaStaticFiles) in prod.  │
└───────────────▲────────────────────────────────────────────────┘
                │ REST (JSON) + SSE        │ CSRF cookie + httpOnly session cookie
┌───────────────┴────────────────────────────────────────────────┐
│  Backend — FastAPI (api/app)                                   │
│  auth/org/pages/conversations/inbox/jobs/sse/status/dev        │
│  strict tenant scoping, audit log, error events, metrics       │
└───────┬───────────────┬──────────────────┬─────────────────────┘
        │               │                  │
   ┌────▼─────┐    ┌────▼─────┐       ┌────▼──────────┐
   │PostgreSQL│    │  Redis   │       │  Local disk   │
   │ 16+vector│    │broker/RL │       │StorageProvider│
   └────┬─────┘    └────┬─────┘       └───────────────┘
        │               │
   ┌────▼────────────────▼──────┐   ┌────────────────────┐
   │ Celery workers (api/app/    │   │ Ollama (Qwen2.5-7B)│
   │ services/jobs + pipeline)   │   │ bge-m3 embeddings  │
   └─────────────────────────────┘   └────────────────────┘
        │
   ┌────▼───────────────────────────────────┐
   │ External: Meta Graph API v21 (OAuth2), │
   │ Knock notifications (the only API key) │
   └────────────────────────────────────────┘
```

### Component map

| Layer | Location | Responsibility |
|---|---|---|
| REST API | `api/app/routers/*` | Auth, orgs, pages, conversations, inbox, jobs, status, dev |
| Realtime | `api/app/services/sse.py` + `routers/sse.py` | Server-Sent Events for job progress, worker status, inbox |
| Models | `api/app/models.py` | 17 tables: users, orgs, memberships, sessions, audit, errors, page connections, conversations, messages, analyses, decisions, responses, knowledge, dataset rows, memory chunks, jobs, job events, stored objects |
| Pipeline | `api/app/services/pipeline/*` | ingest → validate → normalize → dedupe → reconstruct → analyze → quality → dataset → memory → responder |
| AI | `api/app/services/ai/*` | `LLMProvider`/`EmbeddingProvider` abstractions; Ollama impl; bge-m3 embeddings |
| Arabic NLP | `api/app/services/arabic.py` | Normalization, camel-tools morphology, dialect detection, moderation lexicon (word-boundary matching) |
| Jobs | `api/app/services/jobs/*` | DB-backed state machine, Celery tasks, in-process fallback executor |
| Frontend | `src/` | SPA: landing, auth, dashboard, inbox, conversations, pages, jobs, settings |

---

## 2. Current Data Flow

### 2.1 Page import (ingestion pipeline)

1. **Meta OAuth2** (`services/meta_oauth.py`) — user connects a Page through the real Meta
   Graph API consent flow (state token, CSRF, `pages_manage_metadata`,
   `pages_messaging`, `pages_read_engagement`). Long-lived token encrypted at rest.
2. **Conversation discovery** (`routers/pages.py`) — `GET /{page}/conversations` lists real
   conversations with a pagination cursor.
3. **Import job** (`routers/jobs.py` → `pipeline/orchestrator.py`) — a `page_import` job
   walks pages of conversations via the Graph API, stores each raw payload through the
   `StorageProvider` (`services/storage.py`), and records an idempotency key.
4. **Processing stages** (per conversation):
   - `fetch` — pull raw payloads (resumable via per-stage checkpoints)
   - `validate` — shape checks, sender/participant resolution
   - `normalize` — Arabic normalization + dedupe (unique constraints + idempotency keys)
   - `reconstruct` — rebuild the thread from messages
   - `analyze` — dialect detection, intent/entity extraction, moderation (severity + decision)
   - `quality` — dataset eligibility scoring
   - `dataset` — writes eligible rows to `dataset_rows`
   - `memory` — embeddings into pgvector `memory_chunks` (when enabled)
5. **Notifications** — import completion / escalation alerts via Knock.

### 2.2 Moderation & response flow

- New conversations enter the **inbox** (`routers/inbox.py`) with
  `ModerationDecision` records (auto-approve / flag / escalate).
- Moderators review flagged conversations (`/inbox` frontend), approve/edit/reject
  AI-drafted responses (`AiResponse`).
- `responder.py` drafts replies via Ollama grounded in the page style profile +
  business knowledge + retrieved memory; human approval gates every outbound send.
- Sending goes back through the real Meta Graph API (`meta_client.py`).

### 2.3 Learning loop

- Approved responses + feedback write to `knowledge_items` and (optionally)
  `dataset_rows` / `memory_chunks` — feeding the style profile and retrieval
  used by the next drafts. No fake "training": optional fine-tuning hooks exist
  but are disabled by default (see §7).

---

## 3. Frontend Architecture

| Concern | Implementation |
|---|---|
| State | TanStack Query v5 (server cache) + small local state; no global store |
| Routing | `react-router-dom` v6, `RequireAuth` wrapper preserves `returnTo` |
| Realtime | `useSse` hook — `EventSource` on `/api/sse/stream` with reconnect |
| Virtualization | `@tanstack/react-virtual` for inbox + conversation lists |
| Styling | Fully custom design system: CSS custom properties in `src/index.css`, component classes, custom SVG icon set (`components/icons.tsx`), RTL-first (`dir="rtl"`, logical properties) |
| Theming | Dark-by-default Arabic brand identity; CSS variables throughout |
| Server contract | `src/lib/types.ts` mirrors API schemas; `src/lib/api.ts` central fetch client (credentials, CSRF header, error normalization); `src/lib/labels.ts` Arabic label maps for every enum |
| Pages | `Landing`, `AuthPage`, `VerifyEmail`, `Dashboard`, `Inbox`, `Conversations`, `ConversationDetail`, `Pages`, `Jobs`, `Settings` |

Strengths: single API client, typed models, no UI library lock-in, RTL-native.
Weaknesses: no i18n extraction layer (Arabic-first, hardcoded strings — acceptable for v1
given Arabic-first scope), no component tests yet, TanStack Query key invalidation is
hand-rolled per page.

---

## 4. Backend Architecture

- **Framework:** FastAPI with Pydantic v2 schemas; typed request/response models.
- **DB:** SQLAlchemy 2.0 async (`asyncpg` for PostgreSQL, `aiosqlite` for dev/tests).
- **Migrations:** Alembic `0001_initial` (baseline `create_all` + pgvector HNSW index on
  `memory_chunks.embedding`, org index on `dataset_rows`).
- **AuthN/AuthZ:** Argon2id password hashing, httpOnly session cookies, CSRF double-submit
  protection, per-request `CurrentOrg` dependency that scopes every query by `org_id`,
  role checks (`owner/admin/moderator/viewer`), audit logging (`audit.py`).
- **Sessions:** `services/session.py` — DB-backed, TTL 168h, rotation on privilege change.
- **Errors:** `errors.py` (APIError with codes), DB-backed `error_events`, structlog
  structured logs, `metrics.py` (prometheus_client) at `/metrics`.
- **Health:** `/health` (liveness) + `/ready` (DB/Redis checks).
- **Jobs:** DB state machine `PENDING/RUNNING/PAUSED/CANCEL_REQUESTED/CANCELLED/
  COMPLETED/PARTIAL/FAILED` with per-stage checkpoints, resume after crash, cancellation,
  exponential-backoff retries, rate limiting via Redis, dead-letter table for reprocessing.
  Celery when `redis_url` set; in-process executor fallback when not (dev/test).
- **Storage:** `StorageProvider` local-disk implementation; MinIO-compatible interface
  for future swap; raw payloads + attachments stored outside Postgres, path references
  in `stored_objects`.
- **Rate limiting:** `services/rate_limit.py` — Redis-backed sliding window for Meta API.

---

## 5. AI Architecture

- **Abstractions:** `services/ai/base.py` — `LLMProvider` (chat + structured JSON extraction)
  and `EmbeddingProvider`; `services/ai/ollama.py` is the production implementation,
  `services/ai/manager.py` selects model per task with 7B → 3B fallback.
- **LLM:** Ollama, `qwen2.5:7b-instruct-q4_K_M` for batch analysis,
  `qwen2.5:3b-instruct-q4_K_M` for the interactive path. Async HTTP, JSON-schema-shaped
  prompts for structured extraction, temperature gating for moderation vs. generation.
- **Embeddings:** sentence-transformers `BAAI/bge-m3` (1024-dim), batch insert into
  pgvector, HNSW cosine index, retrieval in `services/search.py`.
- **Arabic NLP (`services/arabic.py`):** first-party normalization (Unicode variants,
  diacritics, tatweel, punctuation, Arabic numerals), Arabizi transliteration,
  camel-tools morphology, lexical dialect features
  (Egyptian/Saudi/Gulf/Levantine/Iraqi/Maghrebi/MSA/mixed/arabizi/unknown with
  confidence; low-confidence stays `unknown`), and moderation via word-boundary
  matching with light Arabic stemming + phrase containment for multi-word terms.
- **Fallback:** if Ollama is unreachable, analysis degrades to deterministic Arabic
  lexical rules (normalization + lexicon) so the pipeline still works offline.

---

## 6. Database Architecture

| Table | Purpose | Key constraints |
|---|---|---|
| `users` | Accounts | unique email |
| `organizations` / `org_memberships` | Tenancy | role enum, unique (org,user) |
| `sessions` | httpOnly sessions | FK user, TTL |
| `email_verifications` | Verify codes | unique token |
| `audit_events` / `error_events` | Observability | indexed (org, ts) |
| `page_connections` | Meta Pages | unique (org, page_id), encrypted token |
| `conversations` / `messages` | Ingested threads | unique (org, source_id), sender_type |
| `analysis_results` / `moderation_decisions` / `ai_responses` | Analysis & moderation | one decision per conversation |
| `knowledge_items` / `dataset_rows` / `memory_chunks` | Learning | dataset rows unique (org, conv) |
| `jobs` / `job_events` | Job state machine | checkpoint JSON, idempotency key |
| `stored_objects` | Storage refs | unique (org, path) |

**Dedup strategy:** unique constraints + application idempotency keys on
conversations/messages/jobs; raw payloads keyed by source conversation id.

---

## 7. Integration Architecture

| Integration | Status | Notes |
|---|---|---|
| Meta Graph API v21 | ✅ first-party | OAuth2 connect, conversation fetch, send, webhooks; token encryption at rest, refresh, revoke |
| Knock | ✅ wired | Only external API key (`KNOCK_API_KEY`, `KNOCK_SIGNING_KEY`): verification emails, import-completion alerts, escalation alerts, review-queue notifications |
| Ollama | ✅ | Self-hosted local inference |
| sentence-transformers | ✅ | Self-hosted local embeddings |
| camel-tools | ✅ | Self-hosted morphology |
| Model training | ⏸ gated | Fine-tuning hooks exist but are **disabled by default** — no paid compute, no fake training; dataset export path is the honest deliverable |
| Meta webhooks | ⚠️ documented limitation | Requires public HTTPS endpoint + app-level webhook config on Meta; implemented server-side, activation depends on the operator's Meta app setup |

**Meta API limitations documented** (see `docs/META_INTEGRATION.md`): inbox
conversations require `pages_messaging`; webhooks need public URL; token refresh
must happen server-side; media delivery can time out on large payloads.

---

## 8. Strengths

1. **Real end-to-end pipeline** — no fake ingestion, no simulated AI, no hardcoded data.
   Every stage (OAuth → fetch → normalize → analyze → moderate → dataset) executes real
   code against real APIs.
2. **Zero-cost philosophy honored** — one external API key (Knock); LLM, embeddings,
   Postgres, Redis all self-hosted.
3. **Arabic-first correctness** — RTL-native frontend, proper normalization, dialect
   detection that refuses low-confidence labels, word-boundary moderation (fixed a real
   false-positive: `لص` matching inside `الصبح`).
4. **Strict tenancy** — org scoping enforced in a central dependency, audited.
5. **Resumable jobs** — checkpoints, cancellation, dead-letter reprocessing.
6. **Honest dataset generation** — flagged conversations are excluded; the pipeline
   prefers quality over volume.
7. **Test suite** — 34 passing tests covering auth, API contract, Arabic NLP, jobs,
   pipeline, and moderation regressions.

---

## 9. Weaknesses / Technical Debt

1. **Single Alembic baseline** — `0001_initial` uses `create_all`; future schema changes
   need proper incremental migrations (works, but deviates from Alembic best practice).
2. **In-process job executor fallback** — great for dev/tests; production must set
   `REDIS_URL` and run Celery workers (documented).
3. **No worker orchestration files** yet (docker-compose exists conceptually; see
   `docs/OPERATIONS.md` for the exact services to run).
4. **Frontend test coverage** — none yet; API contract is covered backend-side.
5. **i18n** — Arabic-first with hardcoded strings; switching to a catalog later requires
   extraction work.
6. **Webhooks** — implemented but Meta-side activation is operator-dependent.
7. **Token encryption key** — requires `SECRET_KEY` in production; dev default is
   explicitly insecure (flagged in config).
8. **Embedding model download** — bge-m3 (~2 GB) must be downloaded on first worker
   start; documented in operations guide.
9. **Rate-limit tuning** — Meta defaults are conservative; per-app limits must be tuned
   to the operator's actual Meta app rate ceiling.

---

## 10. Broken / Incomplete / Placeholder Functionality

| Item | Status |
|---|---|
| OAuth, fetch, send | Real, tested against Graph API contract (integration requires real Meta app credentials) |
| LLM/embedding calls | Real; require Ollama running (graceful deterministic fallback otherwise) |
| Knock notifications | Real; require `KNOCK_API_KEY` (graceful no-op otherwise) |
| Fine-tuning / training | Intentionally **not faked** — dataset export + future training hooks are the honest path |
| Webhook delivery | Implemented; activation depends on operator's Meta app |
| Sample-data dev seeding | Real JSON samples with correct page-id linkage (bug fixed: page messages were being classified as customer) |

Nothing in the production path is mocked. Mocks exist only in tests
(`api/tests/conftest.py`).

---

## 11. Security

| Area | Status |
|---|---|
| Passwords | Argon2id ✅ |
| Sessions | httpOnly + Secure cookie, DB-backed, TTL ✅ |
| CSRF | Double-submit cookie, enforced on mutating requests ✅ |
| Token storage | Meta tokens encrypted at rest with `SECRET_KEY`; never logged, never sent to frontend ✅ |
| Tenant isolation | org_id scoping in shared dependency + row-level checks ✅ |
| Audit | DB audit log for auth/org/page/job actions ✅ |
| Secrecy | structlog redaction of tokens/credentials; no conversation dumps in logs ✅ |
| Known risk | Dev `SECRET_KEY` fallback (must set strong key in prod) ⚠️ |

---

## 12. Scalability

- PostgreSQL + Redis + Celery scale horizontally behind the stateless FastAPI tier.
- Raw payloads/attachments are on disk (not in DB) via `StorageProvider`.
- HNSW vector index keeps similarity search sub-linear at scale.
- Rate limiter and caches in Redis survive multi-worker deployments.
- Known ceilings: single-node Ollama inference (scale = add GPUs/nodes or swap
  `LLMProvider` for a cloud key later — abstraction already in place); local disk
  storage (swap to MinIO-compatible provider when needed).

---

## 13. Frontend / Product / Arabic / RTL Assessment

- RTL: `dir="rtl"` at document level, logical CSS properties, Arabic-first copy
  throughout; no LTR leakage observed in design-system review.
- Typography: Arabic-optimized font stack with proper line-height and letter-spacing.
- Product: landing → auth → dashboard → inbox → review → respond flow is complete and
  protected by `RequireAuth`; all primary CTAs route through `/auth` with `returnTo`.
- Remaining polish: empty states and onboarding hints could be richer; a11y review of
  focus states pending.

---

## 14. Dependency Health

| Dependency | Verdict |
|---|---|
| React 18 / Vite 5 / TS 5.6 | Current, stable ✅ |
| FastAPI / Pydantic v2 / SQLAlchemy 2.0 | Current ✅ |
| `react-virtual` | Replaced by maintained successor `@tanstack/react-virtual` ✅ |
| Ollama / bge-m3 / camel-tools | Self-hosted, pinned in `requirements-ai.txt` ✅ |
| Knock | Minimal surface (one provider module) ✅ |
| No paid/credit-card dependencies | ✅ per requirement |

---

## 15. Recommended Target Architecture

1. **Incremental Alembic migrations** from day one of any schema change.
2. **docker-compose** (Postgres+pgvector, Redis, API, worker, Ollama) as the canonical
   production runbook — documented, ready to commit.
3. **Cloud LLM as opt-in**: `LLMProvider` already abstracts it; add a
   `OpenAICompatProvider` later without touching pipeline code.
4. **Object storage swap**: `StorageProvider` interface already matches MinIO;
   implement the S3 backend when the operator deploys MinIO.
5. **Dataset export API + CLI** for downstream fine-tuning — export endpoint exists
   server-side; add a UI surface for it.
6. **Frontend component tests** for the inbox/review decision flow.

---

## 16. Migration Strategy

The repository is greenfield (no legacy code to migrate). The strategy is therefore
*forward-looking*:

1. Keep the `LLMProvider`/`EmbeddingProvider`/`StorageProvider` seams stable — future
   swaps are drop-in.
2. Keep job checkpoints forward-compatible (JSON with stage keys; add fields, never
   remove).
3. When Postgres is introduced in production, `0001_initial` stays the baseline and
   new changes become `0002_*` — no destructive rewrites.
4. If the operator later adopts MinIO/S3, migrate `stored_objects` paths by copying
   from the local provider during a maintenance window (idempotent, path-keyed).

---

## 17. Verification Status (as of this audit)

- `bun tsc -b --noEmit` — ✅ passes
- `bun run build` (vite production build) — ✅ passes
- Backend test suite — ✅ 35 passed
- Backend health endpoints — `/health`, `/ready`, `/metrics` implemented
- Preview readiness — see `freebuff-preview status`
