// Arabic display labels for every enum surfaced by the backend.

export type Tone = "neutral" | "brand" | "success" | "warn" | "danger" | "info" | "muted";

export const DIALECT_LABELS: Record<string, string> = {
  egyptian: "مصري",
  saudi: "سعودي",
  gulf: "خليجي",
  levantin: "شامي",
  levant: "شامي",
  levantine: "شامي",
  iraqi: "عراقي",
  maghrebi: "مغاربي",
  msa: "فصحى",
  mixed: "مختلط",
  arabizi: "عربيزي",
  unknown: "غير محدّد",
};

export const INTENT_LABELS: Record<string, string> = {
  question: "سؤال",
  purchase: "شراء",
  complaint: "شكوى",
  support: "دعم فني",
  praise: "إشادة",
  spam: "إعلان/سبام",
  escalation: "تصعيد",
  greeting: "تحية",
  unknown: "غير محدّد",
};

export const CONVERSATION_STATUS_LABELS: Record<string, string> = {
  fetched: "تم الجلب",
  validated: "تم التحقق",
  normalized: "تم التطبيع",
  reconstructed: "تمت إعادة البناء",
  analyzed: "تم التحليل",
  quality_checked: "تم فحص الجودة",
  dataset_ready: "جاهز للمجموعة",
  failed: "فشل",
};

export const JOB_STATUS_LABELS: Record<string, string> = {
  PENDING: "بانتظار التنفيذ",
  RUNNING: "قيد التشغيل",
  PAUSED: "متوقفة مؤقتًا",
  CANCEL_REQUESTED: "طلب إلغاء",
  CANCELLED: "ملغاة",
  COMPLETED: "مكتملة",
  PARTIAL: "جزئية",
  FAILED: "فشلت",
  DEAD: "رسالة ميتة",
};

export const JOB_KIND_LABELS: Record<string, string> = {
  page_import: "استيراد محادثات الصفحة",
  page_resync: "إعادة مزامنة الصفحة",
  memory_reindex: "إعادة فهرسة الذاكرة",
  dataset_generate: "توليد مجموعة البيانات",
};

export const STAGE_LABELS: Record<string, string> = {
  pending: "بانتظار البدء",
  fetch: "جلب المحادثات",
  validate: "التحقق من البيانات",
  normalize: "تطبيع البيانات",
  reconstruct: "إعادة بناء المحادثات",
  analyze: "التحليل اللغوي",
  quality: "فحص الجودة",
  dataset: "توليد المجموعة",
  memory: "فهرسة الذاكرة",
  complete: "اكتمال",
};

export const RESPONSE_STATUS_LABELS: Record<string, string> = {
  pending: "قيد الصياغة",
  pending_approval: "بانتظار المراجعة",
  approved: "معتمد",
  rejected: "مرفوض",
  sent: "أُرسل إلى ميتا",
  failed: "فشل",
};

export const SEVERITY_LABELS: Record<string, string> = {
  info: "معلوماتي",
  warn: "تنبيه",
  critical: "حرج",
  privacy: "خصوصية",
};

export const ROLE_LABELS: Record<string, string> = {
  owner: "مالك",
  admin: "مدير",
  moderator: "مشرف",
  viewer: "مشاهد",
};

export const ANALYSIS_KIND_LABELS: Record<string, string> = {
  dialect: "اللهجة",
  intent: "النية",
  entities: "الكيانات",
  moderation: "المراقبة",
  style: "أسلوب الصفحة",
  quality: "الجودة",
  business: "المعرفة التجارية",
};

export function toneForDialect(label: string): Tone {
  switch (label) {
    case "egyptian":
    case "saudi":
    case "gulf":
    case "levantine":
    case "iraqi":
    case "maghrebi":
    case "msa":
      return "brand";
    case "mixed":
      return "info";
    case "arabizi":
      return "warn";
    default:
      return "muted";
  }
}

export function toneForIntent(label: string): Tone {
  switch (label) {
    case "complaint":
    case "escalation":
      return "danger";
    case "spam":
      return "warn";
    case "purchase":
      return "success";
    case "praise":
      return "info";
    default:
      return "neutral";
  }
}

export function toneForConversationStatus(status: string): Tone {
  switch (status) {
    case "analyzed":
    case "quality_checked":
    case "dataset_ready":
      return "success";
    case "failed":
      return "danger";
    case "fetched":
    case "validated":
    case "normalized":
    case "reconstructed":
      return "info";
    default:
      return "muted";
  }
}

export function toneForJobStatus(status: string): Tone {
  switch (status) {
    case "COMPLETED":
      return "success";
    case "PARTIAL":
      return "info";
    case "FAILED":
    case "DEAD":
      return "danger";
    case "CANCEL_REQUESTED":
    case "CANCELLED":
      return "muted";
    case "PAUSED":
      return "warn";
    default:
      return "brand";
  }
}

export function toneForSeverity(severity: string): Tone {
  switch (severity) {
    case "critical":
      return "danger";
    case "warn":
      return "warn";
    case "privacy":
      return "info";
    default:
      return "neutral";
  }
}

export function toneForResponseStatus(status: string): Tone {
  switch (status) {
    case "sent":
    case "approved":
      return "success";
    case "rejected":
    case "failed":
      return "danger";
    case "pending_approval":
      return "warn";
    default:
      return "neutral";
  }
}
