import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Badge, Button, Card, CardHead, ConfirmDialog, EmptyState, LoadingBlock, useToast } from "../../components/ui";
import { IconFlag, IconLink, IconPages, IconRefresh, IconSpark } from "../../components/icons";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { formatCompact, relativeTime } from "../../lib/format";
import type { DevSample, DevSampleListResponse, Page } from "../../lib/types";

export default function Pages() {
  const [params] = useSearchParams();
  const { role } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [connectBusy, setConnectBusy] = useState(false);
  const [needsConfig, setNeedsConfig] = useState(false);
  const [disconnectTarget, setDisconnectTarget] = useState<Page | null>(null);

  const metaNotice = params.get("meta");
  const metaCount = params.get("count");

  const canSync = role === "owner" || role === "admin" || role === "moderator";
  const canDisconnect = role === "owner" || role === "admin";

  const { data: pages, isLoading } = useQuery({
    queryKey: ["pages"],
    queryFn: () => api<Page[]>("/api/pages"),
    refetchInterval: 20_000,
  });

  // Dev-only samples (404 in production → hidden).
  const { data: samples } = useQuery({
    queryKey: ["dev-samples"],
    queryFn: () => api<DevSampleListResponse>("/api/dev/samples"),
    retry: false,
    staleTime: 60_000,
  });

  const startConnect = async () => {
    setConnectBusy(true);
    setNeedsConfig(false);
    try {
      const resp = await api<{ url: string }>("/api/meta/auth-url");
      window.location.href = resp.url;
    } catch (err) {
      setConnectBusy(false);
      if (err instanceof ApiError && err.details?.needs_config) {
        setNeedsConfig(true);
      } else {
        toast("error", err instanceof ApiError ? err.message : "تعذّر بدء الاتصال بميتا");
      }
    }
  };

  const sync = useMutation({
    mutationFn: (pageId: string) => api<{ job_id: string }>(`/api/pages/${pageId}/sync`, { method: "POST" }),
    onSuccess: () => {
      toast("success", "بدأت مزامنة الصفحة — تابع تقدمها في الوظائف");
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["pages"] });
    },
    onError: (err) => toast("error", err instanceof ApiError ? err.message : "تعذّر بدء المزامنة"),
  });

  const disconnect = useMutation({
    mutationFn: (pageId: string) => api(`/api/pages/${pageId}/disconnect`, { method: "POST" }),
    onSuccess: () => {
      toast("success", "تم قطع الاتصال وإبطال الرموز");
      setDisconnectTarget(null);
      queryClient.invalidateQueries({ queryKey: ["pages"] });
    },
    onError: (err) => toast("error", err instanceof ApiError ? err.message : "تعذّر قطع الاتصال"),
  });

  const runSample = useMutation({
    mutationFn: (sample: DevSample) =>
      api<{ job_id: string; conversations: number }>("/api/dev/pipeline/run-sample", {
        method: "POST",
        body: { sample: sample.name, page_name: sample.title },
      }),
    onSuccess: (resp) => {
      toast("success", `بدأ تشغيل العينة: ${resp.conversations} محادثة عبر خط الأنابيب الحقيقي`);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({ queryKey: ["pages"] });
    },
    onError: (err) => toast("error", err instanceof ApiError ? err.message : "تعذّر تشغيل العينة"),
  });

  return (
    <div className="rq-page">
      <div className="rq-page-head">
        <div>
          <h1 className="rq-page-title">الصفحات</h1>
          <p className="rq-page-sub">
            اربط صفحات ميتا عبر OAuth حقيقي ليبدأ رقيب باستيراد محادثاتها وتحليلها فورًا.
          </p>
        </div>
        <Button variant="primary" loading={connectBusy} onClick={() => void startConnect()}>
          <IconLink width={17} height={17} />
          ربط صفحة عبر ميتا
        </Button>
      </div>

      {metaNotice && (
        <div className={`${metaNotice === "connected" ? "rq-form-success" : "rq-form-error"} rq-mb`}>
          {metaNotice === "connected"
            ? `تم ربط ${metaCount ?? ""} صفحة بنجاح، وبدأ الاستيراد تلقائيًا.`
            : `فشل اتصال ميتا: ${metaNotice}`}
        </div>
      )}

      {needsConfig && (
        <Card className="rq-mb">
          <div className="rq-card-body rq-stack rq-gap-2">
            <div className="rq-row rq-gap-1">
              <IconFlag className="rq-gold" style={{ width: 20, height: 20 }} />
              <div className="rq-card-title">مطلوب إعداد تطبيق ميتا أولًا</div>
            </div>
            <p className="rq-dim rq-small" style={{ lineHeight: 1.9 }}>
              لربط صفحة حقيقية، أنشئ تطبيقًا في Meta for Developers وأضف هذه المفاتيح إلى إعدادات
              البيئة لديك (لن نطلبها منك في الواجهة أبدًا):
            </p>
            <div className="rq-grid rq-grid-2 rq-gap-2">
              {[
                ["META_APP_ID", "معرّف تطبيق ميتا"],
                ["META_APP_SECRET", "سر التطبيق"],
                ["META_REDIRECT_URI", "رابط إعادة التوجيه (https://…/api/meta/callback)"],
                ["META_WEBHOOK_VERIFY_TOKEN", "رمز التحقق من الويب هوك (اختياري)"],
              ].map(([k, v]) => (
                <div key={k} className="rq-panel" style={{ padding: "10px 14px" }}>
                  <div className="rq-xs rq-mono rq-gold">{k}</div>
                  <div className="rq-xs rq-faint">{v}</div>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}

      {/* dev samples */}
      {samples && samples.samples.length > 0 && (
        <Card className="rq-mb">
          <CardHead
            title="تجربة سريعة (وضع التطوير)"
            actions={<Badge tone="info">بيئة التطوير فقط</Badge>}
          />
          <div className="rq-card-body">
            <p className="rq-dim rq-small rq-mb">
              هذه العينات تمرّ عبر خط الأنابيب الحقيقي نفسه (إعادة بناء ← تحليل ← جودة ← مجموعة ← ذاكرة)
              لتستكشف رقيب قبل ربط صفحة فعلية.
            </p>
            <div className="rq-grid rq-grid-3">
              {samples.samples.map((s) => (
                <div key={s.name} className="rq-panel" style={{ padding: 14 }}>
                  <div className="rq-card-title" style={{ fontSize: 13.5 }}>
                    {s.title}
                  </div>
                  <div className="rq-xs rq-faint rq-mb-sm rq-mt-sm">{s.name}</div>
                  <Button
                    variant="ghost"
                    size="sm"
                    loading={runSample.isPending}
                    onClick={() => runSample.mutate(s)}
                  >
                    <IconSpark width={14} height={14} /> تشغيل العينة
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}

      {isLoading ? (
        <LoadingBlock />
      ) : !pages || pages.length === 0 ? (
        <Card>
          <EmptyState
            icon={<IconPages width={26} height={26} />}
            title="لا صفحات مرتبطة بعد"
            desc="اربط صفحتك عبر ميتا — سنستورد محادثاتها ونحللها ونقترح الردود تلقائيًا."
            action={
              <Button variant="primary" loading={connectBusy} onClick={() => void startConnect()}>
                <IconLink width={17} height={17} />
                ربط أول صفحة
              </Button>
            }
          />
        </Card>
      ) : (
        <Card>
          <div className="rq-table-wrap" style={{ overflowX: "auto" }}>
            <table className="rq-table">
              <thead>
                <tr>
                  <th>الصفحة</th>
                  <th>المتابعون</th>
                  <th>الحالة</th>
                  <th>آخر مزامنة</th>
                  <th>الصلاحيات</th>
                  <th className="rq-text-end">إجراءات</th>
                </tr>
              </thead>
              <tbody>
                {pages.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <div className="rq-row rq-gap-3">
                        {p.picture_url ? (
                          <img className="rq-page-avatar" src={p.picture_url} alt={p.page_name} />
                        ) : (
                          <div className="rq-page-avatar">{p.page_name.slice(0, 1)}</div>
                        )}
                        <div>
                          <div className="rq-card-title" style={{ fontSize: 14 }}>
                            {p.page_name}
                          </div>
                          <div className="rq-xs rq-faint">{p.page_category}</div>
                        </div>
                      </div>
                    </td>
                    <td className="rq-dim">{formatCompact(p.followers_count)}</td>
                    <td>
                      <Badge tone={p.is_active ? "success" : "danger"} dot>
                        {p.is_active ? "نشطة" : "غير نشطة"}
                      </Badge>
                      {p.last_error && (
                        <div className="rq-xs rq-faint" title={p.last_error}>
                          {p.last_error.slice(0, 40)}
                        </div>
                      )}
                    </td>
                    <td className="rq-xs rq-dim">
                      {p.last_sync_at ? relativeTime(p.last_sync_at) : "لم تتم بعد"}
                    </td>
                    <td>
                      <div className="rq-row rq-wrap rq-gap-1">
                        {p.scopes.map((s) => (
                          <Badge key={s} tone="muted" className="rq-xs">
                            {s}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td>
                      <div className="rq-row rq-gap-1" style={{ justifyContent: "flex-end" }}>
                        {canSync && (
                          <Button
                            variant="ghost"
                            size="sm"
                            loading={sync.isPending}
                            disabled={!p.is_active}
                            onClick={() => sync.mutate(p.id)}
                          >
                            <IconRefresh width={14} height={14} /> مزامنة
                          </Button>
                        )}
                        {canDisconnect && (
                          <Button variant="danger" size="sm" onClick={() => setDisconnectTarget(p)}>
                            قطع الاتصال
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <ConfirmDialog
        open={disconnectTarget !== null}
        onClose={() => setDisconnectTarget(null)}
        onConfirm={() => disconnectTarget && disconnect.mutate(disconnectTarget.id)}
        title="قطع الاتصال بالصفحة"
        message={
          <>
            سيتم إبطال رمز الصفحة لدى ميتا وإيقاف المزامنة. المحادثات والتحليلات السابقة
            <strong> ستبقى محفوظة</strong>. متابعة؟
          </>
        }
        confirmLabel="قطع الاتصال"
        danger
        loading={disconnect.isPending}
      />
    </div>
  );
}
