import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge, Button, Card, EmptyState, LoadingBlock, Progress, useToast } from "../../components/ui";
import { IconJobs, IconPause, IconPlay, IconRefresh, IconX } from "../../components/icons";
import { api, ApiError } from "../../lib/api";
import {
  JOB_KIND_LABELS,
  JOB_STATUS_LABELS,
  STAGE_LABELS,
  toneForJobStatus,
} from "../../lib/labels";
import { formatDateTime, relativeTime } from "../../lib/format";
import type { Job, JobListResponse } from "../../lib/types";

const TERMINAL = ["CANCELLED", "COMPLETED", "PARTIAL", "FAILED", "DEAD"];

function JobActions({ job }: { job: Job }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["jobs"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const act = useMutation({
    mutationFn: (action: "pause" | "resume" | "cancel" | "retry") =>
      api(`/api/jobs/${job.id}/${action}`, { method: "POST" }),
    onSuccess: () => {
      toast("success", "تم تحديث حالة الوظيفة");
      invalidate();
    },
    onError: (err) => toast("error", err instanceof ApiError ? err.message : "تعذّر تنفيذ الإجراء"),
  });

  const can = {
    pause: job.status === "RUNNING",
    resume: job.status === "PAUSED",
    cancel: ["PENDING", "RUNNING", "PAUSED"].includes(job.status),
    retry: job.status === "FAILED" || job.status === "DEAD",
  };

  return (
    <div className="rq-row rq-wrap rq-gap-2">
      {can.pause && (
        <Button variant="ghost" size="sm" loading={act.isPending} onClick={() => act.mutate("pause")}>
          <IconPause width={14} height={14} /> إيقاف مؤقت
        </Button>
      )}
      {can.resume && (
        <Button variant="success" size="sm" loading={act.isPending} onClick={() => act.mutate("resume")}>
          <IconPlay width={14} height={14} /> استئناف
        </Button>
      )}
      {can.cancel && (
        <Button variant="danger" size="sm" loading={act.isPending} onClick={() => act.mutate("cancel")}>
          <IconX width={14} height={14} /> إلغاء
        </Button>
      )}
      {can.retry && (
        <Button variant="ghost" size="sm" loading={act.isPending} onClick={() => act.mutate("retry")}>
          <IconRefresh width={14} height={14} /> إعادة المحاولة
        </Button>
      )}
    </div>
  );
}

function JobDetail({ job }: { job: Job }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen((v) => !v)}>
        {open ? "إخفاء التفاصيل" : "التفاصيل"}
      </Button>
      {open && (
        <div className="rq-grid rq-grid-3 rq-mt-3 rq-gap-2">
          <div className="rq-insight">
            <div className="rq-insight-key">المعاملات</div>
            <pre className="rq-xs rq-faint rq-mono" style={{ direction: "ltr", textAlign: "right", whiteSpace: "pre-wrap", margin: 0 }}>
              {JSON.stringify(job.params, null, 2) || "{}"}
            </pre>
          </div>
          <div className="rq-insight">
            <div className="rq-insight-key">نقطة التفتيش</div>
            <pre className="rq-xs rq-faint rq-mono" style={{ direction: "ltr", textAlign: "right", whiteSpace: "pre-wrap", margin: 0 }}>
              {JSON.stringify(job.checkpoint, null, 2) || "{}"}
            </pre>
          </div>
          <div className="rq-insight">
            <div className="rq-insight-key">النتيجة</div>
            <pre className="rq-xs rq-faint rq-mono" style={{ direction: "ltr", textAlign: "right", whiteSpace: "pre-wrap", margin: 0 }}>
              {JSON.stringify(job.result, null, 2) || "{}"}
            </pre>
          </div>
          {job.error && (
            <div className="rq-form-error rq-xs" style={{ gridColumn: "1 / -1" }}>
              {job.error}
            </div>
          )}
          {job.events.length > 0 && (
            <div className="rq-insight" style={{ gridColumn: "1 / -1" }}>
              <div className="rq-insight-key">سجل الأحداث              </div>
              <div className="rq-stack rq-gap-1 rq-mt-1">
                {job.events.map((e) => (
                  <div key={e.id} className="rq-row rq-xs rq-dim rq-gap-2">
                    <Badge tone="muted" className="rq-xs">{e.event}</Badge>
                    <span>{relativeTime(e.created_at)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

export default function Jobs() {
  const { data, isLoading } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<JobListResponse>("/api/jobs?limit=100"),
    refetchInterval: 15_000,
  });

  const running = (data?.items ?? []).filter((j) => ["PENDING", "RUNNING", "CANCEL_REQUESTED"].includes(j.status)).length;

  return (
    <div className="rq-page">
      <div className="rq-page-head">
        <div>
          <h1 className="rq-page-title">الوظائف</h1>
          <p className="rq-page-sub">
            خط الأنابيب كله هنا: استيراد، تحليل، جودة، مجموعة، وذاكرة — بحالات واضحة ونقاط تفتيش
            قابلة للاستئناف، وتتحدث لحظيًا.
          </p>
        </div>
        {running > 0 && (
          <Badge tone="brand" dot>
            {running} وظيفة قيد التشغيل
          </Badge>
        )}
      </div>

      {isLoading ? (
        <LoadingBlock />
      ) : !data || data.items.length === 0 ? (
        <Card>
          <EmptyState
            icon={<IconJobs width={26} height={26} />}
            title="لا وظائف بعد"
            desc="اربط صفحة أو شغّل مزامنة لتنشأ وظيفة استيراد تظهر هنا مع تقدمها لحظيًا."
          />
        </Card>
      ) : (
        <div className="rq-stack rq-gap-3">
          {data.items.map((job) => {
            const terminal = TERMINAL.includes(job.status);
            return (
              <Card key={job.id} className="rq-job-row" style={{ gridTemplateColumns: "1fr", alignItems: "stretch" }}>
                <div className="rq-row rq-row-between rq-wrap rq-gap-3">
                  <div className="rq-grow" style={{ minWidth: 0 }}>
                    <div className="rq-row rq-wrap rq-gap-2">
                      <span className="rq-card-title" style={{ fontSize: 14.5 }}>
                        {JOB_KIND_LABELS[job.kind] ?? job.kind}
                      </span>
                      <Badge tone={toneForJobStatus(job.status)} dot>
                        {JOB_STATUS_LABELS[job.status] ?? job.status}
                      </Badge>
                      {job.dead_letter && <Badge tone="danger">رسالة ميتة — أعد المحاولة</Badge>}
                    </div>
                    <div className="rq-xs rq-faint rq-mt-sm">
                      المرحلة: {STAGE_LABELS[job.stage] ?? job.stage} · المحاولات: {job.attempts} · أنشئت{" "}
                      {relativeTime(job.created_at)}
                      {job.completed_at ? ` · اكتملت ${formatDateTime(job.completed_at)}` : ""}
                    </div>
                  </div>
                  <JobActions job={job} />
                </div>

                <div className="rq-row rq-row-between rq-wrap rq-gap-3">
                  <div className="rq-grow" style={{ minWidth: 200 }}>
                    <div className="rq-xs rq-dim rq-mb-sm">{job.progress_message || "…"}</div>
                    <Progress
                      done={job.progress_done}
                      total={job.progress_total}
                      indeterminate={!terminal && job.status !== "PAUSED" && job.progress_total === 0}
                    />
                  </div>
                  <div className="rq-row rq-gap-2">
                    <span className="rq-xs rq-faint">
                      {job.progress_done}/{job.progress_total || "∞"}
                    </span>
                    <JobDetail job={job} />
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
