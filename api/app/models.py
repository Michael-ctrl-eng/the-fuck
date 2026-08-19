"""رقيب — SQLAlchemy 2.0 async data model.

All multi-tenant tables carry an organization id and every query in the
application is scoped by the authenticated organization.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# --------------------------------------------------------------------------
# Shared constants
# --------------------------------------------------------------------------

ORG_ROLES = ("owner", "admin", "moderator", "viewer")

JOB_STATES = (
    "PENDING",
    "RUNNING",
    "PAUSED",
    "CANCEL_REQUESTED",
    "CANCELLED",
    "COMPLETED",
    "PARTIAL",
    "FAILED",
    "DEAD",
)
JOB_KINDS = ("page_import", "page_resync", "memory_reindex", "dataset_generate")
JOB_TERMINAL = ("CANCELLED", "COMPLETED", "PARTIAL", "FAILED", "DEAD")

CONVERSATION_STATUSES = (
    "fetched",
    "validated",
    "normalized",
    "reconstructed",
    "analyzed",
    "quality_checked",
    "dataset_ready",
    "failed",
)

ANALYSIS_KINDS = ("dialect", "intent", "entities", "moderation", "style", "quality", "business")
ANALYSIS_STATUSES = ("pending", "running", "completed", "failed", "skipped", "unavailable")
ANALYSIS_PROVIDERS = ("deterministic", "ollama", "none")

RESPONSE_STATUSES = (
    "pending",
    "pending_approval",
    "approved",
    "rejected",
    "sent",
    "failed",
)

SENDER_TYPES = ("customer", "page", "staff", "ai")

DECISION_STATUSES = ("open", "approved", "dismissed", "escalated")


def uuid_str() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AwareDateTime(TypeDecorator):
    """UTC-normalized datetime column.

    SQLite cannot persist tz-aware datetimes, so we store naive UTC and
    always read back timezone-aware UTC datetimes — consistent behaviour
    on both SQLite (sandbox) and PostgreSQL (production).
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        if value is not None and getattr(value, "tzinfo", None) is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        if value is not None and getattr(value, "tzinfo", None) is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class EmbeddingVector(TypeDecorator):
    """pgvector Vector(embedding_dim) on PostgreSQL, JSON list elsewhere.

    Keeps the schema usable in the SQLite sandbox while production uses
    real pgvector (HNSW) indexes created by the Alembic migrations.
    """

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 1024, *args: Any, **kwargs: Any) -> None:
        self.dim = dim
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector

                return dialect.type_descriptor(Vector(self.dim))
            except ImportError:  # pragma: no cover - pgvector not installed
                pass
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:  # noqa: ARG002
        return value

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:  # noqa: ARG002
        return value


# --------------------------------------------------------------------------
# Auth / org
# --------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)

    memberships: Mapped[list["OrgMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)

    memberships: Mapped[list["OrgMembership"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )


class OrgMembership(Base):
    __tablename__ = "org_memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_org_membership"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="memberships")
    org: Mapped[Organization] = relationship(back_populates="memberships")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    oauth_state_hash: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(AwareDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)


class EmailVerification(Base):
    __tablename__ = "email_verifications"
    __table_args__ = (Index("ix_email_verifications_user", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(AwareDateTime)
    used_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_org_created", "org_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    actor_id: Mapped[str] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(40), default="")
    resource_id: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)


class ErrorEvent(Base):
    __tablename__ = "error_events"
    __table_args__ = (Index("ix_error_org_created", "org_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    job_id: Mapped[str] = mapped_column(String(36), nullable=True)
    stage: Mapped[str] = mapped_column(String(60), default="")
    kind: Mapped[str] = mapped_column(String(60), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    traceback: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)


# --------------------------------------------------------------------------
# Meta Pages
# --------------------------------------------------------------------------


class PageConnection(Base):
    __tablename__ = "page_connections"
    __table_args__ = (
        UniqueConstraint("org_id", "page_id", name="uq_page_org_page"),
        Index("ix_pages_org", "org_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    connected_by: Mapped[str] = mapped_column(String(36), nullable=True)
    page_id: Mapped[str] = mapped_column(String(40))
    page_name: Mapped[str] = mapped_column(String(200), default="")
    page_category: Mapped[str] = mapped_column(String(120), default="")
    picture_url: Mapped[str] = mapped_column(String(500), default="")
    link: Mapped[str] = mapped_column(String(500), default="")
    followers_count: Mapped[int] = mapped_column(Integer, default=0)
    platform: Mapped[str] = mapped_column(String(20), default="facebook")
    instagram_user_id: Mapped[str] = mapped_column(String(40), default="")
    # Encrypted at rest; never exposed to the frontend.
    access_token_enc: Mapped[str] = mapped_column(Text, default="")
    user_token_enc: Mapped[str] = mapped_column(Text, default="")
    token_scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    token_expires_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    meta_user_id: Mapped[str] = mapped_column(String(40), default="")
    connected_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
    last_sync_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_reply_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_error: Mapped[str] = mapped_column(String(500), default="")

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )


# --------------------------------------------------------------------------
# Conversations & messages
# --------------------------------------------------------------------------


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("org_id", "source_conversation_id", name="uq_conv_source"),
        Index("ix_conv_org_status", "org_id", "status"),
        Index("ix_conv_org_dialect", "org_id", "dialect_label"),
        Index("ix_conv_org_updated", "org_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    page_id: Mapped[str] = mapped_column(ForeignKey("page_connections.id", ondelete="CASCADE"))
    source_conversation_id: Mapped[str] = mapped_column(String(64))
    platform: Mapped[str] = mapped_column(String(20), default="facebook")
    status: Mapped[str] = mapped_column(String(24), default="fetched")
    participants: Mapped[list[str]] = mapped_column(JSON, default=list)
    participant_names: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    dialect_label: Mapped[str] = mapped_column(String(24), default="unknown")
    dialect_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    intent_label: Mapped[str] = mapped_column(String(40), default="unknown")
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    dataset_included: Mapped[bool] = mapped_column(Boolean, default=False)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    first_message_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow, onupdate=utcnow)

    page: Mapped[PageConnection] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.sequence"
    )
    analyses: Mapped[list["AnalysisResult"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    responses: Mapped[list["AiResponse"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "source_message_id", name="uq_msg_source"),
        Index("ix_msg_conv_seq", "conversation_id", "sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    source_message_id: Mapped[str] = mapped_column(String(64))
    sender_type: Mapped[str] = mapped_column(String(12), default="customer")
    sender_id: Mapped[str] = mapped_column(String(64), default="")
    author_name: Mapped[str] = mapped_column(String(200), default="")
    text_raw: Mapped[str] = mapped_column(Text, default="")
    text_normalized: Mapped[str] = mapped_column(Text, default="")
    text_arabizi: Mapped[str] = mapped_column(Text, default="")
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[str] = mapped_column(String(36), nullable=True)
    media_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        UniqueConstraint("conversation_id", "kind", name="uq_analysis_conv_kind"),
        Index("ix_analysis_conv", "conversation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(24))
    provider: Mapped[str] = mapped_column(String(24), default="none")
    status: Mapped[str] = mapped_column(String(24), default="pending")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    model: Mapped[str] = mapped_column(String(120), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime, default=utcnow, onupdate=utcnow
    )

    conversation: Mapped[Conversation] = relationship(back_populates="analyses")


class ModerationDecision(Base):
    __tablename__ = "moderation_decisions"
    __table_args__ = (Index("ix_mod_org_status", "org_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    severity: Mapped[str] = mapped_column(String(12), default="info")  # info|warn|critical
    decision: Mapped[str] = mapped_column(String(12), default="flag")  # flag|escalate|approve|skip
    status: Mapped[str] = mapped_column(String(16), default="open")  # DECISION_STATUSES
    reason: Mapped[str] = mapped_column(String(240), default="")
    ai_rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    resolved_by: Mapped[str] = mapped_column(String(36), nullable=True)


class AiResponse(Base):
    __tablename__ = "ai_responses"
    __table_args__ = (
        Index("ix_resp_org_status", "org_id", "status"),
        Index("ix_resp_conv", "conversation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    provider: Mapped[str] = mapped_column(String(24), default="none")
    model: Mapped[str] = mapped_column(String(120), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    feedback: Mapped[str] = mapped_column(String(16), default="")  # approve|edit|reject
    edited_text: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[str] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    sent_to_meta_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="responses")


class KnowledgeItem(Base):
    """Business knowledge extracted from conversations (KB for the responder)."""

    __tablename__ = "knowledge_items"
    __table_args__ = (Index("ix_kb_org", "org_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    topic: Mapped[str] = mapped_column(String(120), default="")
    kind: Mapped[str] = mapped_column(String(24), default="fact")  # fact|policy|product|faq
    content: Mapped[str] = mapped_column(Text, default="")
    source_conversation_id: Mapped[str] = mapped_column(String(36), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)


# --------------------------------------------------------------------------
# Datasets / memory
# --------------------------------------------------------------------------


class DatasetRow(Base):
    __tablename__ = "dataset_rows"
    __table_args__ = (
        UniqueConstraint("org_id", "conversation_id", name="uq_dataset_conv"),
        Index("ix_dataset_org", "org_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    dialect_label: Mapped[str] = mapped_column(String(24), default="unknown")
    intent_label: Mapped[str] = mapped_column(String(40), default="unknown")
    sample: Mapped[str] = mapped_column(Text, default="")
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)


class MemoryChunk(Base):
    __tablename__ = "memory_chunks"
    __table_args__ = (Index("ix_mem_org_conv", "org_id", "conversation_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingVector(), nullable=True)
    source: Mapped[str] = mapped_column(String(24), default="conversation")
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("org_id", "idempotency_key", name="uq_job_idempotency"),
        Index("ix_jobs_org_status", "org_id", "status"),
        Index("ix_jobs_org_created", "org_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), default="PENDING")
    stage: Mapped[str] = mapped_column(String(60), default="pending")
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    progress_message: Mapped[str] = mapped_column(String(240), default="")
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    dead_letter: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), default="")
    created_by: Mapped[str] = mapped_column(String(36), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow, onupdate=utcnow)

    events: Mapped[list["JobEvent"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobEvent.created_at"
    )


class JobEvent(Base):
    __tablename__ = "job_events"
    __table_args__ = (Index("ix_job_events_job", "job_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    event: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)

    job: Mapped[Job] = relationship(back_populates="events")


class StoredObject(Base):
    __tablename__ = "stored_objects"
    __table_args__ = (Index("ix_stored_org", "org_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(255), unique=True)
    provider: Mapped[str] = mapped_column(String(24), default="local")
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)


class OwnerMessage(Base):
    __tablename__ = "owner_messages"
    __table_args__ = (Index("ix_owner_msg_org_created", "org_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(1000), default="")
    parsed_action: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    agent_response: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
