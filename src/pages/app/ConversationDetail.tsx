import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Badge, Button, Card, CardHead, EmptyState, Input, LoadingBlock, Textarea, useToast } from "../../components/ui";
import {
  IconBrain,
  IconCheck,
  IconEdit,
  IconEye,
  IconReject,
  IconRefresh,
  IconSend,
  IconSpark,
  IconWarning,
} from "../../components/icons";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import {
  ANALYSIS_KIND_LABELS,
  CONVERSATION_STATUS_LABELS,
  DIALECT_LABELS,
  INTENT_LABELS,
  RESPONSE_STATUS_LABELS,
  toneForConversationStatus,
  toneForDialect,
  toneForIntent,
  toneForResponseStatus,
} from "../../lib/labels";
import { formatDateTime, formatPercent, relativeTime } from "../../lib/format";
import type { Analysis, AnalysisKind, Conversation, AiResponse, Message } from "../../lib/types";

function MessageBubble({ msg }: { msg: Message }) {
  const isPage = msg.sender_type === "page";
  const author = msg.author_name || (isPage ? "الصفحة" : "العميل");
  return (
    <div className={`rq-msg ${isPage ? "rq-msg-page" : "rq-msg-customer"} ${msg.is_duplicate ? "rq-msg-dup" : ""}`}>
      <div className="rq-msg-head">
        <span className="rq-msg-author">{author}</span>
        {msg.is_duplicate && <span className="rq-msg-dup-tag">مكررة</span>}
        <span>{msg.sent_at ? relativeTime(msg.sent_at) : ""}</span>
      </div>
      <div className="rq-msg-bubble">{msg.text_raw || msg.text_normalized}</div>
      {msg.text_arabizi && msg.text_arabizi !== (msg.text_raw || msg.text_normalized) && (
        <div className="rq-xs rq-faint rq-mt-sm" style={{ alignSelf: isPage ? "flex-start" : "flex-end" }}>
          عربيزي ← <span className="rq-mono">{msg.text_arabizi}</span>
        </div>
      )}
    </div>
  );
}

function EntityList({ label, values }: { label: string; values: unknown }) {
  const list = Array.isArray(values) ? values : [];
  if (list.length === 0) return null;
  return (
    <div className="rq-insight">
      <div className="rq-insight-key">{label}</div>
      <div className="rq-insight-val rq-xs rq-mono" style={{ direction: "ltr", textAlign: "right", fontWeight: 600 }}>
        {list.slice(0, 4).map((v) => String(v)).join("، ")}
        {list.length > 4 ? ` +${list.length - 4}` : ""}
      </div>
    </div>
  );
}

function AnalysisPanel({ analyses }: { analyses: Analysis[] }) {
  const byKind = useMemo(() => {
    const map = new Map<AnalysisKind, Analysis>();
    for (const a of analyses) map.set(a.kind, a);
    return map;
  }, [analyses]);

  const dialect = byKind.get("dialect")?.payload as Record<string, unknown> | undefined;
  const intent = byKind.get("intent")?.payload as Record<string, unknown> | undefined;
  const entities = byKind.get("entities")?.payload as Record<string, unknown> | undefined;
  const moderation = byKind.get("moderation")?.payload as Record<string, unknown> | undefined;
  const style = byKind.get("style")?.payload as Record<string, unknown> | undefined;
  const quality = byKind.get("quality")?.payload as Record<string, unknown> | undefined;

  return (
    <Card>
      <CardHead title="التحليل اللغوي" actions={<Badge tone="brand">مزوّد: حتمي + نموذج محلي</Badge>} />
      <div className="rq-card-body">
        {analyses.length === 0 ? (
          <EmptyState
            icon={<IconBrain width={26} height={26} />}
            title="لم يُحلَّل بعد"
            desc="شغّل التحليل ليكتشف رقيب اللهجة والنية والكيانات وجودة المحادثة."
          />
        ) : (
          <div className="rq-insight-grid">
            {dialect && (
              <div className="rq-insight">
                <div className="rq-insight-key">{ANALYSIS_KIND_LABELS.dialect}</div>
                <div className="rq-insight-val">
                  {DIALECT_LABELS[String(dialect.label ?? "unknown")] ?? String(dialect.label ?? "غير محدّد")}
                </div>
                <div className="rq-insight-note">
                  ثقة {formatPercent(Number(dialect.confidence ?? 0))}٪
                  {dialect.reason ? ` — ${String(dialect.reason)}` : ""}
                </div>
              </div>
            )}
            {intent && (
              <div className="rq-insight">
                <div className="rq-insight-key">{ANALYSIS_KIND_LABELS.intent}</div>
                <div className="rq-insight-val">
                  {INTENT_LABELS[String(intent.label ?? "unknown")] ?? String(intent.label ?? "غير محدّد")}
                </div>
                <div className="rq-insight-note">
                  ثقة {formatPercent(Number(intent.confidence ?? 0))}٪
                </div>
              </div>
            )}
            {quality && (
              <div className="rq-insight">
                <div className="rq-insight-key">{ANALYSIS_KIND_LABELS.quality}</div>
                <div className="rq-insight-val">{formatPercent(Number(quality.score ?? 0))}٪</div>
                <div className="rq-insight-note">
                  {String(quality.reasons ?? quality.summary ?? "")}
                </div>
              </div>
            )}
            {moderation && (
              <div className="rq-insight">
                <div className="rq-insight-key">{ANALYSIS_KIND_LABELS.moderation}</div>
                <div className="rq-insight-val">
                  {String(moderation.flagged ? "توجد ملاحظات" : "لا توجد ملاحظات")}
                </div>
                <div className="rq-insight-note">{String(moderation.reason ?? "")}</div>
              </div>
            )}
            {style && (
              <div className="rq-insight">
                <div className="rq-insight-key">{ANALYSIS_KIND_LABELS.style}</div>
                <div className="rq-insight-val">
                  {String(style.tone ?? "غير محدّد")} · {String(style.avg_length ?? "")}
                </div>
                <div className="rq-insight-note">
                  {style.greeting_pattern ? `تحية: ${String(style.greeting_pattern)}` : ""}
                  {style.signoff_pattern ? ` · ختام: ${String(style.signoff_pattern)}` : ""}
                </div>
              </div>
            )}
            {entities && (
              <>
                <EntityList label="هواتف" values={entities.phones} />
                <EntityList label="بريد" values={entities.emails} />
                <EntityList label="روابط" values={entities.urls} />
                <EntityList label="وسوم" values={entities.hashtags} />
                <EntityList label="أسعار" values={entities.prices} />
              </>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

function ResponseCard({
  convId,
  resp,
  canAct,
}: {
  convId: string;
  resp: AiResponse;
  canAct: boolean;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [edited, setEdited] = useState("");
  const [note, setNote] = useState("");

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["conversation", convId] });
    queryClient.invalidateQueries({ queryKey: ["inbox"] });
    queryClient.invalidateQueries({ queryKey: ["inbox-stats"] });
  };

  const review = useMutation({
    mutationFn: (body: { decision: string; edited_text?: string; note?: string }) =>
      api(`/api/conversations/${convId}/responses/${resp.id}/review`, { method: "POST", body }),
    onSuccess: () => {
      toast("success", resp.status === "pending_approval" ? "تم تحديث حالة الرد" : "تم تحديث الرد");
      invalidate();
    },
    onError: (err) => toast("error", err instanceof ApiError ? err.message : "تعذّرت المراجعة"),
  });

  const send = useMutation({
    mutationFn: () => api(`/api/conversations/${convId}/responses/${resp.id}/send`, { method: "POST" }),
    onSuccess: () => {
      toast("success", "أُرسل الرد إلى ميتا");
      invalidate();
    },
    onError: (err) => toast("error", err instanceof ApiError ? err.message : "تعذّر الإرسال"),
  });

  const displayText = resp.edited_text || resp.text;

  return (
    <div className="rq-inbox-item">
      <div className="rq-inbox-item-head">
        <Badge tone={toneForResponseStatus(resp.status)} dot>
          {RESPONSE_STATUS_LABELS[resp.status] ?? resp.status}
        </Badge>
        <span className="rq-xs rq-faint">{relativeTime(resp.created_at)}</span>
        <span className="rq-grow" />
        {resp.model && <span className="rq-xs rq-faint rq-mono">{resp.model}</span>}
      </div>

      <div className="rq-inbox-text">{displayText}</div>

      {resp.rationale && (
        <div className="rq-xs rq-dim">
          <strong className="rq-gold">التبرير: </strong>
          {resp.rationale}
        </div>
      )}
      {resp.error && (
        <div className="rq-form-error rq-xs">
          <IconWarning width={13} height={13} style={{ verticalAlign: "-2px", marginInlineEnd: 6 }} />
          {resp.error}
        </div>
      )}

      {resp.status === "pending_approval" && canAct && (
        <>
          {editing ? (
            <>
              <Textarea
                value={edited || resp.text}
                onChange={(e) => setEdited(e.target.value)}
                placeholder="عدّل نص الرد…"
                style={{ minHeight: 110 }}
              />
              <Input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="ملاحظة (اختياري)"
              />
              <div className="rq-row rq-wrap rq-gap-1">
                <Button
                  variant="success"
                  size="sm"
                  loading={review.isPending}
                  onClick={() =>
                    review.mutate({ decision: "edit", edited_text: (edited || resp.text).trim(), note })
                  }
                >
                  <IconCheck width={15} height={15} /> اعتماد النص المعدَّل
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
                  إلغاء
                </Button>
              </div>
            </>
          ) : (
            <div className="rq-row rq-wrap rq-gap-2">
              <Button variant="success" size="sm" loading={review.isPending} onClick={() => review.mutate({ decision: "approve", note })}>
                <IconCheck width={15} height={15} /> اعتماد
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
                <IconEdit width={15} height={15} /> تعديل
              </Button>
              <Button variant="danger" size="sm" loading={review.isPending} onClick={() => review.mutate({ decision: "reject", note })}>
                <IconReject width={15} height={15} /> رفض
              </Button>
            </div>
          )}
        </>
      )}

      {resp.status === "approved" && canAct && (
        <div className="rq-row rq-gap-2">
          <Button variant="primary" size="sm" loading={send.isPending} onClick={() => send.mutate()}>
            <IconSend width={15} height={15} /> إرسال إلى ميتا
          </Button>
        </div>
      )}

      {resp.reviewed_at && (
        <div className="rq-xs rq-faint">
          رُوجع في {formatDateTime(resp.reviewed_at)}
          {resp.sent_to_meta_at ? ` · أُرسل في ${formatDateTime(resp.sent_to_meta_at)}` : ""}
        </div>
      )}
    </div>
  );
}

export default function ConversationDetail() {
  const { id = "" } = useParams();
  const { role } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [instructions, setInstructions] = useState("");

  const canAct = role === "owner" || role === "admin" || role === "moderator";

  const { data: conv, isLoading } = useQuery({
    queryKey: ["conversation", id],
    queryFn: () => api<Conversation>(`/api/conversations/${id}`),
    refetchInterval: 15_000,
  });

  const analyze = useMutation({
    mutationFn: () => api(`/api/conversations/${id}/analyze`, { method: "POST", body: { force: false } }),
    onSuccess: () => {
      toast("success", "اكتمل التحليل اللغوي للمحادثة");
      queryClient.invalidateQueries({ queryKey: ["conversation", id] });
    },
    onError: (err) => toast("error", err instanceof ApiError ? err.message : "تعذّر التحليل"),
  });

  const draft = useMutation({
    mutationFn: () =>
      api<AiResponse>(`/api/conversations/${id}/responses`, { method: "POST", body: { instructions } }),
    onSuccess: (resp) => {
      if (resp.status === "failed") {
        toast("error", resp.error || "تعذّرت صياغة الرد — النموذج غير متاح");
      } else {
        toast("success", "صيغ ردّك وأصبح بانتظار مراجعتك");
      }
      setInstructions("");
      queryClient.invalidateQueries({ queryKey: ["conversation", id] });
      queryClient.invalidateQueries({ queryKey: ["inbox"] });
      queryClient.invalidateQueries({ queryKey: ["inbox-stats"] });
    },
    onError: (err) => toast("error", err instanceof ApiError ? err.message : "تعذّرت الصياغة"),
  });

  if (isLoading) return <LoadingBlock label="جارٍ تحميل المحادثة…" />;
  if (!conv) {
    return (
      <div className="rq-page">
        <Card>
          <EmptyState
            icon={<IconEye width={26} height={26} />}
            title="المحادثة غير موجودة"
            desc="قد لا تكون ضمن منظمتك الحالية."
            action={
              <Link to="/app/conversations" className="rq-btn rq-btn-ghost rq-btn-sm">
                العودة للمحادثات
              </Link>
            }
          />
        </Card>
      </div>
    );
  }

  const customerMessages = conv.messages.filter((m) => m.sender_type === "customer");
  const lastCustomer = customerMessages[customerMessages.length - 1];

  return (
    <div className="rq-page">
      <div className="rq-page-head">
        <div>
            <div className="rq-row rq-gap-1 rq-mt-1">
            <Link to="/app/conversations" className="rq-btn rq-btn-ghost rq-btn-sm">
              ← المحادثات
            </Link>
            <Badge tone={toneForConversationStatus(conv.status)}>
              {CONVERSATION_STATUS_LABELS[conv.status] ?? conv.status}
            </Badge>
            {conv.is_flagged && (
              <Badge tone="danger" dot>
                مرفوعة للمراجعة
              </Badge>
            )}
          </div>
          <h1 className="rq-page-title">{conv.page_name || "صفحة"}</h1>
          <p className="rq-page-sub">
            <Badge tone={toneForDialect(conv.dialect_label)}>
              {DIALECT_LABELS[conv.dialect_label] ?? conv.dialect_label}
              {conv.dialect_confidence > 0 ? ` · ثقة ${formatPercent(conv.dialect_confidence)}٪` : ""}
            </Badge>
            <Badge tone={toneForIntent(conv.intent_label)} className="rq-mt-sm" style={{ marginInlineStart: 6 }}>
              {INTENT_LABELS[conv.intent_label] ?? conv.intent_label}
            </Badge>
            <span style={{ marginInlineStart: 10 }} className="rq-dim rq-small">
              جودة {formatPercent(conv.quality_score)}٪ · {conv.message_count} رسالة ·{" "}
              {conv.updated_at ? relativeTime(conv.updated_at) : ""}
            </span>
          </p>
        </div>
        {canAct && (
          <Button variant="ghost" loading={analyze.isPending} onClick={() => analyze.mutate()}>
            <IconRefresh width={16} height={16} />
            إعادة التحليل
          </Button>
        )}
      </div>

      <div className="rq-grid rq-grid-2">
        <div className="rq-stack rq-gap-2">
          <Card>
            <CardHead
              title={`المحادثة (${conv.messages.length})`}
               actions={
                <div className="rq-row rq-xs rq-faint rq-gap-2">
                  <span>{formatDateTime(conv.first_message_at)}</span>
                  <span>←</span>
                  <span>{formatDateTime(conv.last_message_at)}</span>
                </div>
              }
            />
            <div className="rq-card-body">
              {conv.messages.length === 0 ? (
                <EmptyState icon={<IconEye width={26} height={26} />} title="لا رسائل في هذه المحادثة" />
              ) : (
                <div className="rq-thread">
                  {conv.messages.map((m) => (
                    <MessageBubble key={m.id} msg={m} />
                  ))}
                </div>
              )}
            </div>
          </Card>

          {/* responses */}
          <Card>
            <CardHead
              title="الردود الذكية"
              actions={
                <Badge tone={conv.responses.some((r) => r.status === "pending_approval") ? "warn" : "brand"} dot>
                  {conv.responses.filter((r) => r.status === "pending_approval").length} بانتظار المراجعة
                </Badge>
              }
            />
            <div className="rq-card-body rq-stack rq-gap-1">
              {canAct && (
                <div className="rq-panel" style={{ padding: 14 }}>
                   <div className="rq-label rq-mb-sm">صياغة رد جديد بأسلوب صفحتك</div>
                   <Textarea
                     value={instructions}
                     onChange={(e) => setInstructions(e.target.value)}
                     placeholder="توجيهات اختيارية: اذكر العرض، السعر، سياسة الشحن… (سيُستخدم أسلوب صفحتك ومعرفتها تلقائيًا)"
                     style={{ minHeight: 80 }}
                   />
                   <div className="rq-row rq-gap-2" style={{ justifyContent: "flex-end", marginTop: 10 }}>
                    <Button
                      variant="primary"
                      size="sm"
                      loading={draft.isPending}
                      onClick={() => draft.mutate()}
                    >
                      <IconSpark width={15} height={15} />
                      صياغة الرد
                    </Button>
                  </div>
                </div>
              )}

              {conv.responses.length === 0 ? (
                <EmptyState
                  icon={<IconSpark width={24} height={24} />}
                  title="لا ردود بعد"
                  desc="صُغ أول رد ليصبح جاهزًا لمراجعتك واعتمادك."
                />
              ) : (
                conv.responses.map((r) => (
                  <ResponseCard key={r.id} convId={conv.id} resp={r} canAct={canAct} />
                ))
              )}
            </div>
          </Card>
        </div>

        <div className="rq-stack rq-gap-2">
          <AnalysisPanel analyses={conv.analyses} />

          <Card>
            <CardHead title="ملخص المحادثة" />
            <div className="rq-card-body rq-stack rq-gap-1">
              <div className="rq-insight">
                <div className="rq-insight-key">آخر رسالة من العميل</div>
                <div className="rq-insight-val rq-small" style={{ fontWeight: 600, lineHeight: 1.9 }}>
                  {lastCustomer ? lastCustomer.text_raw || lastCustomer.text_normalized : "—"}
                </div>
                <div className="rq-insight-note">
                  {lastCustomer?.sent_at ? formatDateTime(lastCustomer.sent_at) : ""}
                </div>
              </div>
              <div className="rq-insight">
                <div className="rq-insight-key">المشاركون</div>
                <div className="rq-insight-val rq-small" style={{ fontWeight: 600 }}>
                  {Object.values(conv.participant_names || {}).join("، ") || "—"}
                </div>
              </div>
              {conv.dataset_included && (
                <Badge tone="success">ضمن مجموعة التعلّم — ستُستخدم لتحسين ردودك</Badge>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
