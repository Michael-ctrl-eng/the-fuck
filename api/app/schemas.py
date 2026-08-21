from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)
    org_name: str = Field(min_length=1, max_length=160)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    email_verified: bool = False
    created_at: datetime


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    role: str = "viewer"
    members_count: int = 0
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserOut
    orgs: list[OrgOut]
    csrf_token: str = ""
    dev_verify_url: str = ""


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class CreateOrgRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class SwitchOrgRequest(BaseModel):
    org_id: str


class MemberInviteRequest(BaseModel):
    email: EmailStr
    role: Literal["admin", "moderator", "viewer"]


class MemberRoleUpdate(BaseModel):
    role: Literal["admin", "moderator", "viewer"]


class MemberOut(BaseModel):
    id: str
    user_id: str
    email: str
    full_name: str
    role: str
    created_at: datetime


# --------------------------------------------------------------------------
# Meta / Pages
# --------------------------------------------------------------------------


class MetaAuthUrlResponse(BaseModel):
    url: str


class PageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    page_id: str
    page_name: str
    page_category: str
    picture_url: str
    link: str
    followers_count: int
    connected_at: datetime
    last_sync_at: datetime | None
    is_active: bool
    last_error: str
    scopes: list[str] = []


class PageSyncResponse(BaseModel):
    job_id: str


class DisconnectResponse(BaseModel):
    ok: bool = True


# --------------------------------------------------------------------------
# Conversations
# --------------------------------------------------------------------------


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_message_id: str
    sender_type: str
    sender_id: str
    author_name: str
    text_raw: str
    text_normalized: str
    text_arabizi: str
    is_duplicate: bool
    media_urls: list[str] = []
    audio_urls: list[str] = []
    transcribed_text: str = ""
    sequence: int
    sent_at: datetime | None
    created_at: datetime


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    provider: str
    status: str
    confidence: float
    payload: dict[str, Any]
    model: str
    error: str
    created_at: datetime
    updated_at: datetime


class ConversationListItem(BaseModel):
    id: str
    page_id: str
    page_name: str
    source_conversation_id: str
    status: str
    dialect_label: str
    dialect_confidence: float
    intent_label: str
    quality_score: float
    dataset_included: bool
    is_flagged: bool
    message_count: int
    first_message_at: datetime | None
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConversationOut(ConversationListItem):
    participants: list[str] = []
    participant_names: dict[str, str] = {}
    messages: list[MessageOut] = []
    analyses: list[AnalysisOut] = []
    responses: list["ResponseOut"] = []


class ConversationListResponse(BaseModel):
    items: list[ConversationListItem]
    next_cursor: str | None


class AnalyzeRequest(BaseModel):
    force: bool = False


class ResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    status: str
    provider: str
    model: str
    text: str
    rationale: str
    feedback: str
    edited_text: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    sent_to_meta_at: datetime | None
    error: str
    created_at: datetime


class DraftResponseRequest(BaseModel):
    instructions: str = Field(default="", max_length=4000)


class ReviewResponseRequest(BaseModel):
    decision: Literal["approve", "edit", "reject"]
    edited_text: str = Field(default="", max_length=8000)
    note: str = Field(default="", max_length=2000)


# --------------------------------------------------------------------------
# Inbox
# --------------------------------------------------------------------------


class InboxItem(BaseModel):
    type: str  # response | flag
    id: str
    conversation_id: str
    page_name: str
    severity: str
    summary: str
    text: str
    created_at: datetime
    payload: dict[str, Any] = {}


class InboxResponse(BaseModel):
    items: list[InboxItem]
    next_cursor: str | None


class InboxStats(BaseModel):
    pending_reviews: int
    open_flags: int
    escalated: int
    conversations_today: int


class ResolveFlagRequest(BaseModel):
    decision: Literal["approved", "dismissed", "escalated"]
    note: str = Field(default="", max_length=2000)


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------


class JobEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event: str
    payload: dict[str, Any]
    created_at: datetime


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    kind: str
    status: str
    stage: str
    progress_done: int
    progress_total: int
    progress_message: str
    checkpoint: dict[str, Any]
    params: dict[str, Any]
    result: dict[str, Any]
    error: str
    dead_letter: bool
    attempts: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime
    events: list[JobEventOut] = []


class JobListResponse(BaseModel):
    items: list[JobOut]
    next_cursor: str | None


class JobActionResponse(BaseModel):
    job: JobOut


# --------------------------------------------------------------------------
# Dashboard / misc
# --------------------------------------------------------------------------


class DashboardStats(BaseModel):
    pages: int
    conversations: int
    pending_reviews: int
    open_flags: int
    escalated: int
    dataset_rows: int
    active_jobs: int
    last_sync_at: datetime | None


class DatasetExportResponse(BaseModel):
    count: int
    sample: list[dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    model_available: bool = False
    knock_configured: bool = False


class ApiStatusResponse(BaseModel):
    app_env: str
    version: str
    database_backend: str
    storage: str
    model_provider: str
    model_available: bool
    embedding_provider: str
    embedding_available: bool
    knock_configured: bool
    rate_limiter: str
    job_executor: str


class DevSampleListResponse(BaseModel):
    samples: list[dict[str, Any]]


class DevRunSampleRequest(BaseModel):
    sample: str
    page_name: str = "صفحة تجريبية"
