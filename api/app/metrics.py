from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "raqib_http_requests_total",
    "HTTP requests",
    ["method", "path", "status"],
)
HTTP_DURATION = Histogram(
    "raqib_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

JOBS_TOTAL = Counter(
    "raqib_jobs_total",
    "Jobs created",
    ["kind", "status"],
)
JOBS_ACTIVE = Gauge("raqib_jobs_active", "Jobs currently active")
JOBS_DEAD = Gauge("raqib_jobs_dead", "Jobs in dead-letter state")

PIPELINE_STAGE_DURATION = Histogram(
    "raqib_pipeline_stage_duration_seconds",
    "Pipeline stage duration",
    ["kind", "stage"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
)
PIPELINE_ITEMS = Counter(
    "raqib_pipeline_items_total",
    "Items processed per stage",
    ["kind", "stage", "outcome"],
)

AI_INVOCATIONS = Counter(
    "raqib_ai_invocations_total",
    "LLM invocations",
    ["provider", "kind", "status"],
)
AI_LATENCY = Histogram(
    "raqib_ai_latency_seconds",
    "LLM invocation latency",
    ["provider"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

EMBEDDINGS_TOTAL = Counter(
    "raqib_embeddings_total",
    "Embedding vectors computed",
    ["provider", "status"],
)

META_API_CALLS = Counter(
    "raqib_meta_api_calls_total",
    "Meta Graph API calls",
    ["endpoint", "status"],
)
META_API_LATENCY = Histogram(
    "raqib_meta_api_latency_seconds",
    "Meta Graph API latency",
    ["endpoint"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

MESSAGES_INGESTED = Counter(
    "raqib_messages_ingested_total",
    "Messages ingested from Meta",
    ["outcome"],
)
CONVERSATIONS_INGESTED = Counter(
    "raqib_conversations_ingested_total",
    "Conversations ingested",
    ["outcome"],
)
RETRIEVAL_CALLS = Counter(
    "raqib_retrieval_calls_total",
    "Semantic memory retrieval calls",
)
