import type { CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Badge, Card, CardHead, EmptyState, LoadingBlock, Progress } from "../../components/ui";
import {
  IconBrain,
  IconChat,
  IconDatabase,
  IconEye,
  IconInbox,
  IconPages,
  IconPlus,
  IconSpark,
  IconWarning,
} from "../../components/icons";
import { api } from "../../lib/api";
import {
  JOB_KIND_LABELS,
  JOB_STATUS_LABELS,
  toneForJobStatus,
} from "../../lib/labels";
import { relativeTime } from "../../lib/format";
import type {
  ApiStatus,
  ConversationListItem,
  InboxStats,
  Job,
  Page,
} from "../../lib/types";

function StatCard({
  label,
  value,
  hint,
  glow,
}: {
  label: string;
  value: string;
  hint?: string;
  glow?: string;
}) {
  return (
    <Card
      className="rq-stat"
      style={{ "--stat-glow": glow ?? "var(--gold-dim)" } as CSSProperties}
    >
      <div className="rq-stat-label">{label}</div>
      <div className="rq-stat-value">{value}</div>
      {hint && <div className="rq-stat-hint">{hint}</div>}
    </Card>
  );
}

export default function Dashboard() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["inbox-stats"],
    queryFn: () => api<InboxStats>("/api/inbox/stats"),
    refetchInterval: 30_000,
  });
  const { data: pages } = useQuery({
    queryKey: ["pages"],
    queryFn: () => api<Page[]>("/api/pages"),
    staleTime: 30_000,
  });
  const { data: convs, isLoading: convsLoading } = useQuery({
    queryKey: ["conversations", { limit: 100 }],
    queryFn: () =>
      api<{ items: ConversationListItem[]; next_cursor: string | null }>(
        "/api/conversations?limit=100",
      ),
    staleTime: 30_000,
  });
  const { data: dataset } = useQuery({
    queryKey: ["conversations", { dataset: true }],
    queryFn: () =>
      api<{ items: ConversationListItem[]; next_cursor: string | null }>(
        "/api/conversations?dataset=true&limit=100",
      ),
    staleTime: 60_000,
  });
  const { data: jobs } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<{ items: Job[]; next_cursor: string | null }>("/api/jobs?limit=50"),
    refetchInterval: 20_000,
  });
  const { data: apiStatus } = useQuery({
    queryKey: ["api-status"],
    queryFn: () => api<ApiStatus>("/api/status"),
    staleTime: 60_000,
  });

  const activeJobs = (jobs?.items ?? []).filter((j) =>
    ["PENDING", "RUNNING", "PAUSED", "CANCEL_REQUESTED"].includes(j.status),
  );
  const lastSync = pages
    ? pages
        .map((p) => p.last_sync_at)
        .filter((x): x is string => Boolean(x))
        .sort()
        .pop() ?? null
    : null;

  const recentConvs = convs?.items.slice(0, 5) ?? [];
  const recentJobs = jobs?.items.slice(0, 5) ?? [];

  return (
    <div className="rq-page">
      <div className="rq-page-head">
        <div>
          <h1 className="rq-page-title">لوحة التحكم</h1>
          <p className="rq-page-sub">
            نظرة حيّة على صفحاتك ومحادثاتك وصندوق المراجعة — كل الأرقام من خادمك مباشرة.
          </p>
        </div>
        <Link to="/app/pages" className="rq-btn rq-btn-primary">
          <IconPlus width={17} height={17} />
          ربط صفحة جديدة
        </Link>
      </div>

      <div className="rq-grid rq-grid-4 rq-mb">
        <StatCard
          label="الصفحات المرتبطة"
          value={pages ? String(pages.length) : "—"}
          hint={lastSync ? `آخر مزامنة ${relativeTime(lastSync)}` : "لم تتم مزامنة بعد"}
          glow="rgba(212,169,78,0.16)"
        />
        <StatCard
          label="المحادثات المستوردة"
          value={convsLoading || !convs ? "—" : convs.next_cursor ? `${convs.items.length}+` : String(convs.items.length)}
          hint={convs && convs.items.length > 0 ? "أحدثها مُحدّثة" : "لم تُستورد محادثات بعد"}
          glow="rgba(91,155,213,0.14)"
        />
        <StatCard
          label="بانتظار المراجعة"
          value={statsLoading || !stats ? "—" : String(stats.pending_reviews)}
          hint="ردود ذكية تحتاج قرارك"
          glow="rgba(226,169,60,0.16)"
        />
        <StatCard
          label="علامات مراجعة مفتوحة"
          value={statsLoading || !stats ? "—" : String(stats.open_flags)}
          hint={stats ? `${stats.escalated} متصاعدة` : ""}
          glow="rgba(226,87,76,0.15)"
        />
        <StatCard
          label="صفوف مجموعة التعلّم"
          value={dataset ? String(dataset.items.length) : "—"}
          hint="محادثات مؤهلة لتعلّم ردودك"
          glow="rgba(67,191,143,0.14)"
        />
        <StatCard
          label="محادثات اليوم"
          value={statsLoading || !stats ? "—" : String(stats.conversations_today)}
          hint="وصلت اليوم عبر المزامنة"
        />
        <StatCard
          label="وظائف نشطة"
          value={String(activeJobs.length)}
          hint="استيراد · تحليل · فهرسة"
          glow="rgba(212,169,78,0.14)"
        />
        <StatCard
          label="حالة النموذج المحلي"
          value={apiStatus ? (apiStatus.model_available ? "متصل" : "غير متصل") : "—"}
          hint={apiStatus ? apiStatus.model_provider : ""}
          glow={apiStatus?.model_available ? "rgba(67,191,143,0.16)" : "rgba(226,169,60,0.16)"}
        />
      </div>

      <div className="rq-grid rq-grid-2">
        <Card>
          <CardHead
            title="آخر الوظائف"
            actions={
              <Link to="/app/jobs" className="rq-btn rq-btn-ghost rq-btn-sm">
                عرض الكل
              </Link>
            }
          />
          {jobs ? (
            recentJobs.length === 0 ? (
              <EmptyState
                icon={<IconEye width={26} height={26} />}
                title="لا وظائف بعد"
                desc="عند ربط صفحة أو تشغيل مزامنة ستظهر العمليات هنا مع تقدمها لحظيًا."
                action={
                  <Link to="/app/pages" className="rq-btn rq-btn-primary rq-btn-sm">
                    ربط صفحة
                  </Link>
                }
              />
            ) : (
              <div className="rq-stack rq-p-4 rq-gap-3">
                {recentJobs.map((job) => (
                  <Link key={job.id} to={`/app/jobs`} style={{ color: "inherit" }}>
                    <div className="rq-row rq-row-between">
                      <div className="rq-grow" style={{ minWidth: 0 }}>
                        <div className="rq-row rq-wrap rq-gap-2">
                          <span className="rq-card-title" style={{ fontSize: 13.5 }}>
                            {JOB_KIND_LABELS[job.kind] ?? job.kind}
                          </span>
                          <Badge tone={toneForJobStatus(job.status)} dot>
                            {JOB_STATUS_LABELS[job.status] ?? job.status}
                          </Badge>
                        </div>
                        <div className="rq-xs rq-faint rq-mt-sm">
                          {job.progress_message || job.stage}
                        </div>
                      </div>
                      <div style={{ width: 140 }}>
                        <Progress
                          done={job.progress_done}
                          total={job.progress_total}
                          indeterminate={job.status === "RUNNING" && job.progress_total === 0}
                        />
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )
          ) : (
            <LoadingBlock />
          )}
        </Card>

        <Card>
          <CardHead
            title="أحدث المحادثات"
            actions={
              <Link to="/app/conversations" className="rq-btn rq-btn-ghost rq-btn-sm">
                عرض الكل
              </Link>
            }
          />
          {convs ? (
            recentConvs.length === 0 ? (
              <EmptyState
                icon={<IconChat width={26} height={26} />}
                title="لا محادثات بعد"
                desc="اربط صفحتك أو شغّل مزامنة لتبدأ الرحلة: جلب، تحليل لهجات، مراقبة، وردود ذكية."
                action={
                  <Link to="/app/pages" className="rq-btn rq-btn-primary rq-btn-sm">
                    ربط صفحة
                  </Link>
                }
              />
            ) : (
               <div className="rq-stack rq-p-1 rq-gap-1 rq-mb">
                {recentConvs.map((c) => (
                  <Link
                    key={c.id}
                    to={`/app/conversations/${c.id}`}
                    className="rq-conv-row"
                    style={{ gridTemplateColumns: "1fr auto", padding: "12px 14px" }}
                  >
                    <div className="rq-grow" style={{ minWidth: 0 }}>
                      <div className="rq-conv-title" style={{ fontSize: 13.5 }}>
                        {c.page_name || "صفحة"}
                        {c.is_flagged && (
                          <Badge tone="danger" dot>
                            <IconWarning width={11} height={11} />
                          </Badge>
                        )}
                      </div>
                      <div className="rq-conv-snippet rq-xs">
                        {c.dialect_label} · {c.intent_label} · جودة {Math.round(c.quality_score * 100)}٪
                      </div>
                    </div>
                    <div className="rq-conv-time">{relativeTime(c.updated_at)}</div>
                  </Link>
                ))}
              </div>
            )
          ) : (
            <LoadingBlock />
          )}
        </Card>
      </div>

      {/* AI pipeline status */}
      <Card className="rq-mt">
        <CardHead
          title="حالة البنية التحتية"
          actions={
            apiStatus ? (
              <Badge tone={apiStatus.model_available ? "success" : "warn"} dot>
                {apiStatus.model_available ? "مزوّد النموذج جاهز" : "النموذج غير متاح الآن"}
              </Badge>
            ) : undefined
          }
        />
        <div className="rq-card-body">
          {apiStatus ? (
            <div className="rq-grid rq-grid-4">
              <div className="rq-insight">
                <div className="rq-insight-key">
                  <IconBrain width={15} height={15} /> النموذج
                </div>
                <div className="rq-insight-val">
                  {apiStatus.model_available ? "متاح" : "غير متاح"}
                </div>
                <div className="rq-insight-note">{apiStatus.model_provider}</div>
              </div>
              <div className="rq-insight">
                <div className="rq-insight-key">
                  <IconDatabase width={15} height={15} /> التضمين
                </div>
                <div className="rq-insight-val">
                  {apiStatus.embedding_available ? "متاح" : "غير متاح"}
                </div>
                <div className="rq-insight-note">{apiStatus.embedding_provider}</div>
              </div>
              <div className="rq-insight">
                <div className="rq-insight-key">
                  <IconSpark width={15} height={15} /> التنبيهات
                </div>
                <div className="rq-insight-val">{apiStatus.knock_configured ? "مفعّلة" : "معطّلة"}</div>
                <div className="rq-insight-note">Knock — مفتاح اختياري</div>
              </div>
              <div className="rq-insight">
                <div className="rq-insight-key">
                  <IconInbox width={15} height={15} /> الوظائف
                </div>
                <div className="rq-insight-val">{apiStatus.job_executor}</div>
                <div className="rq-insight-note">قاعدة بيانات: {apiStatus.database_backend}</div>
              </div>
            </div>
          ) : (
            <LoadingBlock />
          )}
        </div>
      </Card>

      {/* pages overview */}
      <Card className="rq-mt">
        <CardHead
          title="الصفحات المرتبطة"
          actions={
            <Link to="/app/pages" className="rq-btn rq-btn-ghost rq-btn-sm">
              إدارة الصفحات
            </Link>
          }
        />
        {pages ? (
          pages.length === 0 ? (
            <EmptyState
              icon={<IconPages width={26} height={26} />}
              title="لم تربط أي صفحة بعد"
              desc="اربط صفحتك عبر ميتا بخطوتين، وسيبدأ رقيب باستيراد محادثاتها فورًا."
              action={
                <Link to="/app/pages" className="rq-btn rq-btn-primary rq-btn-sm">
                  ربط صفحة ميتا
                </Link>
              }
            />
          ) : (
            <div className="rq-table-wrap">
              <table className="rq-table">
                <thead>
                  <tr>
                    <th>الصفحة</th>
                    <th>الحالة</th>
                    <th>آخر مزامنة</th>
                  </tr>
                </thead>
                <tbody>
                  {pages.map((p) => (
                    <tr key={p.id}>
                      <td>
                         <div className="rq-row rq-gap-3">
                          {p.picture_url ? (
                            <img
                              className="rq-page-avatar"
                              style={{ width: 40, height: 40 }}
                              src={p.picture_url}
                              alt={p.page_name}
                            />
                          ) : (
                            <div className="rq-page-avatar" style={{ width: 40, height: 40 }}>
                              {p.page_name.slice(0, 1)}
                            </div>
                          )}
                          <div>
                            <div className="rq-card-title" style={{ fontSize: 13.5 }}>
                              {p.page_name}
                            </div>
                            <div className="rq-xs rq-faint">{p.page_category}</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <Badge tone={p.is_active ? "success" : "danger"} dot>
                          {p.is_active ? "نشطة" : "غير نشطة"}
                        </Badge>
                      </td>
                      <td className="rq-xs rq-dim">{p.last_sync_at ? relativeTime(p.last_sync_at) : "لم تتم بعد"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : (
          <LoadingBlock />
        )}
      </Card>
    </div>
  );
}
