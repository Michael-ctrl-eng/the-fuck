// Raqib API types — mirrors api/app/schemas.py + models.py constants.

export type Role = "owner" | "admin" | "moderator" | "viewer";

export interface User {
  id: string;
  email: string;
  full_name: string;
  email_verified: boolean;
  created_at: string;
}

export interface Org {
  id: string;
  name: string;
  slug: string;
  role: Role;
  members_count: number;
  created_at: string;
}

export interface AuthResponse {
  user: User;
  orgs: Org[];
  csrf_token: string;
  dev_verify_url: string;
}

export interface Page {
  id: string;
  page_id: string;
  page_name: string;
  page_category: string;
  picture_url: string;
  link: string;
  followers_count: number;
  connected_at: string;
  last_sync_at: string | null;
  is_active: boolean;
  last_error: string;
  scopes: string[];
}

export type SenderType = "customer" | "page" | "staff" | "ai";

export interface Message {
  id: string;
  source_message_id: string;
  sender_type: SenderType;
  sender_id: string;
  author_name: string;
  text_raw: string;
  text_normalized: string;
  text_arabizi: string;
  is_duplicate: boolean;
  media_urls: string[];
  sequence: number;
  sent_at: string | null;
  created_at: string;
}

export type AnalysisKind =
  | "dialect"
  | "intent"
  | "entities"
  | "moderation"
  | "style"
  | "quality"
  | "business";

export interface Analysis {
  id: string;
  kind: AnalysisKind;
  provider: string;
  status: string;
  confidence: number;
  payload: Record<string, unknown>;
  model: string;
  error: string;
  created_at: string;
  updated_at: string;
}

export type ConversationStatus =
  | "fetched"
  | "validated"
  | "normalized"
  | "reconstructed"
  | "analyzed"
  | "quality_checked"
  | "dataset_ready"
  | "failed";

export type DialectLabel =
  | "egyptian"
  | "saudi"
  | "gulf"
  | "levantine"
  | "iraqi"
  | "maghrebi"
  | "msa"
  | "mixed"
  | "arabizi"
  | "unknown";

export type IntentLabel =
  | "question"
  | "purchase"
  | "complaint"
  | "support"
  | "praise"
  | "spam"
  | "escalation"
  | "greeting"
  | "unknown";

export interface ConversationListItem {
  id: string;
  page_id: string;
  page_name: string;
  source_conversation_id: string;
  status: ConversationStatus;
  dialect_label: DialectLabel;
  dialect_confidence: number;
  intent_label: IntentLabel;
  quality_score: number;
  dataset_included: boolean;
  is_flagged: boolean;
  message_count: number;
  first_message_at: string | null;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Conversation extends ConversationListItem {
  participants: string[];
  participant_names: Record<string, string>;
  messages: Message[];
  analyses: Analysis[];
  responses: AiResponse[];
}

export interface ConversationListResponse {
  items: ConversationListItem[];
  next_cursor: string | null;
}

export type ResponseStatus =
  | "pending"
  | "pending_approval"
  | "approved"
  | "rejected"
  | "sent"
  | "failed";

export interface AiResponse {
  id: string;
  conversation_id: string;
  status: ResponseStatus;
  provider: string;
  model: string;
  text: string;
  rationale: string;
  feedback: string;
  edited_text: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  sent_to_meta_at: string | null;
  error: string;
  created_at: string;
}

export interface InboxItem {
  type: "response" | "flag";
  id: string;
  conversation_id: string;
  page_name: string;
  severity: string;
  summary: string;
  text: string;
  created_at: string;
  payload: Record<string, unknown>;
}

export interface InboxResponse {
  items: InboxItem[];
  next_cursor: string | null;
}

export interface InboxStats {
  pending_reviews: number;
  open_flags: number;
  escalated: number;
  conversations_today: number;
}

export type JobStatus =
  | "PENDING"
  | "RUNNING"
  | "PAUSED"
  | "CANCEL_REQUESTED"
  | "CANCELLED"
  | "COMPLETED"
  | "PARTIAL"
  | "FAILED"
  | "DEAD";

export type JobKind = "page_import" | "page_resync" | "memory_reindex" | "dataset_generate";

export interface JobEvent {
  id: string;
  event: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface Job {
  id: string;
  org_id: string;
  kind: JobKind;
  status: JobStatus;
  stage: string;
  progress_done: number;
  progress_total: number;
  progress_message: string;
  checkpoint: Record<string, unknown>;
  params: Record<string, unknown>;
  result: Record<string, unknown>;
  error: string;
  dead_letter: boolean;
  attempts: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
  events: JobEvent[];
}

export interface JobListResponse {
  items: Job[];
  next_cursor: string | null;
}

export interface Member {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: Role;
  created_at: string;
}

export interface ApiStatus {
  app_env: string;
  version: string;
  database_backend: string;
  storage: string;
  model_provider: string;
  model_available: boolean;
  embedding_provider: string;
  embedding_available: boolean;
  knock_configured: boolean;
  rate_limiter: string;
  job_executor: string;
}

export interface DevSample {
  name: string;
  title: string;
}

export interface DevSampleListResponse {
  samples: DevSample[];
}

export interface Health {
  status: string;
  version: string;
  database: string;
  model_available: boolean;
  knock_configured: boolean;
}
