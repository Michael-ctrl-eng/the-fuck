import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Link } from "react-router-dom";
import { Badge, Button, Card, EmptyState, Input, LoadingBlock, Textarea, useToast } from "../../components/ui";
import { IconChat, IconEdit, IconReject, IconCheck, IconWarning } from "../../components/icons";
import { api, ApiError } from "../../lib/api";
import { SEVERITY_LABELS, toneForSeverity } from "../../lib/labels";
import { relativeTime } from "../../lib/format";
import type { InboxItem, InboxResponse } from "../../lib/types";

type Tab = "all" | "responses" | "flags";

function ReviewResponse({ item, onDone }: { item: InboxItem; onDone: () => void }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [decision, setDecision] = useState<"approve" | "edit" | "reject" | null>(null);
  const [edited, setEdited] = useState("");
  const [note, setNote] = useState("");

  const mutation = useMutation({
    mutationFn: (body: { decision: string; edited_text?: string; note?: string }) =>
      api(`/api/conversations/${item.conversation_id}/responses/${item.id}/review`, {
        method: "POST",
        body,
      }),
    onSuccess: () => {
      toast("success", decision === "reject" ? "تم رفض الرد" : "تم اعتماد الرد");
      queryClient.invalidateQueries({ queryKey: ["inbox"] });
      queryClient.invalidateQueries({ queryKey: ["inbox-stats"] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      onDone();
    },
    onError: (err) => {
      toast("error", err instanceof ApiError ? err.message : "تعذّرت المراجعة");
    },
  });

  const rationale = item.payload.rationale as string | undefined;
  const model = item.payload.model as string | undefined;

  const submit = (d: "approve" | "edit" | "reject") => {
    if (d === "edit" && !edited.trim()) {
      toast("warn", "أدخل النص المعدَّل أولًا");
      return;
    }
    setDecision(d);
    mutation.mutate(
      d === "edit" ? { decision: d, edited_text: edited.trim(), note } : { decision: d, note },
    );
  };

  return (
    <div className="rq-stack rq-gap-2">
      <div className="rq-inbox-text">{item.text}</div>
      {rationale && (
        <div className="rq-xs rq-dim">
          <strong className="rq-gold">التبرير: </strong>
          {rationale}
        </div>
      )}
      {model && (
        <div className="rq-xs rq-faint">
          النموذج: <span className="rq-mono">{model}</span>
        </div>
      )}

      {decision === "edit" && (
        <>
          <Textarea
            value={edited}
            onChange={(e) => setEdited(e.target.value)}
            placeholder="اكتب النص المعدَّل هنا…"
            style={{ minHeight: 110 }}
          />
          <Input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="ملاحظة للمراجعين (اختياري)"
          />
        </>
      )}

      <div className="rq-row rq-wrap rq-gap-1">
        {decision === null ? (
          <>
            <Button variant="success" size="sm" onClick={() => submit("approve")} loading={mutation.isPending}>
              <IconCheck width={15} height={15} /> اعتماد
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setDecision("edit")}>
              <IconEdit width={15} height={15} /> تعديل ثم اعتماد
            </Button>
            <Button variant="danger" size="sm" onClick={() => submit("reject")} loading={mutation.isPending}>
              <IconReject width={15} height={15} /> رفض
            </Button>
          </>
        ) : (
          <div className="rq-row rq-gap-1">
            {decision === "edit" && (
              <Button variant="success" size="sm" onClick={() => submit("edit")} loading={mutation.isPending}>
                <IconCheck width={15} height={15} /> اعتماد النص المعدَّل
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={() => setDecision(null)}>
              إلغاء
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function ResolveFlag({ item, onDone }: { item: InboxItem; onDone: () => void }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");

  const mutation = useMutation({
    mutationFn: (decision: "approved" | "dismissed" | "escalated") =>
      api(`/api/inbox/flags/${item.id}/resolve`, { method: "POST", body: { decision, note } }),
    onSuccess: () => {
      toast("success", "تم تحديث العلامة");
      queryClient.invalidateQueries({ queryKey: ["inbox"] });
      queryClient.invalidateQueries({ queryKey: ["inbox-stats"] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      onDone();
    },
    onError: (err) => {
      toast("error", err instanceof ApiError ? err.message : "تعذّر تحديث العلامة");
    },
  });

  const rationale = item.payload.ai_rationale as string | undefined;

  return (
    <div className="rq-stack rq-gap-2">
      <div className="rq-inbox-text">{item.text || "—"}</div>
      {rationale && (
        <div className="rq-xs rq-dim">
          <strong className="rq-gold">تبرير الذكاء الاصطناعي: </strong>
          {rationale}
        </div>
      )}
      <Input
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="ملاحظة (اختياري)"
      />
      <div className="rq-row rq-wrap rq-gap-1">
        <Button variant="success" size="sm" onClick={() => mutation.mutate("approved")} loading={mutation.isPending}>
          <IconCheck width={15} height={15} /> لا يوجد مخالفة
        </Button>
        <Button variant="ghost" size="sm" onClick={() => mutation.mutate("dismissed")} loading={mutation.isPending}>
          تجاهل
        </Button>
        <Button variant="danger" size="sm" onClick={() => mutation.mutate("escalated")} loading={mutation.isPending}>
          <IconWarning width={15} height={15} /> تصعيد
        </Button>
      </div>
    </div>
  );
}

export default function Inbox() {
  const [tab, setTab] = useState<Tab>("all");
  const { data, isLoading } = useQuery({
    queryKey: ["inbox"],
    queryFn: () => api<InboxResponse>("/api/inbox?limit=100"),
    refetchInterval: 20_000,
  });

  const items = useMemo(() => {
    if (!data) return [];
    const list = data.items;
    if (tab === "responses") return list.filter((i) => i.type === "response");
    if (tab === "flags") return list.filter((i) => i.type === "flag");
    return list;
  }, [data, tab]);

  const counts = useMemo(() => {
    const list = data?.items ?? [];
    return {
      all: list.length,
      responses: list.filter((i) => i.type === "response").length,
      flags: list.filter((i) => i.type === "flag").length,
    };
  }, [data]);

  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 220,
    overscan: 5,
  });

  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const visible = items.filter((i) => !dismissed.has(i.id));

  return (
    <div className="rq-page">
      <div className="rq-page-head">
        <div>
          <h1 className="rq-page-title">صندوق المراجعة</h1>
          <p className="rq-page-sub">
            كل ما يحتاج قرارًا بشريًا: ردود ذكية بانتظار اعتمادك، وعلامات مراقبة تتطلب نظرك.
          </p>
        </div>
      </div>

      <div className="rq-tabs rq-mb">
        {(
          [
            ["all", "الكل"],
            ["responses", "الردود"],
            ["flags", "العلامات"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            className={`rq-tab ${tab === key ? "rq-tab-active" : ""}`}
            onClick={() => setTab(key)}
          >
            {label}
            <span className="rq-tab-count">{counts[key]}</span>
          </button>
        ))}
      </div>

      {isLoading ? (
        <LoadingBlock />
      ) : visible.length === 0 ? (
        <Card>
          <EmptyState
            icon={<IconChat width={26} height={26} />}
            title="الصندوق فارغ — عمل رائع"
            desc="لا توجد ردود أو علامات بانتظار المراجعة الآن. ستظهر هنا فور وصول محادثات جديدة."
          />
        </Card>
      ) : (
        <Card>
          <div
            ref={parentRef}
            style={{ height: "min(70vh, 720px)", overflowY: "auto", position: "relative" }}
          >
            <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
              {virtualizer.getVirtualItems().map((vi) => {
                const item = visible[vi.index];
                if (!item) return null;
                return (
                  <div
                    key={item.id}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      transform: `translateY(${vi.start}px)`,
                      padding: "10px 14px",
                    }}
                  >
                    <div className="rq-inbox-item">
                      <div className="rq-inbox-item-head">
                        <Badge tone={item.type === "response" ? "brand" : toneForSeverity(item.severity)} dot>
                          {item.type === "response" ? "رد ذكي" : SEVERITY_LABELS[item.severity] ?? item.severity}
                        </Badge>
                        <span className="rq-card-title" style={{ fontSize: 13.5 }}>
                          {item.summary}
                        </span>
                        <span className="rq-grow" />
                        <span className="rq-xs rq-faint">{relativeTime(item.created_at)}</span>
                      </div>
                      <div className="rq-xs rq-dim">
                        الصفحة: <strong>{item.page_name || "—"}</strong>
                        {" · "}
                        <Link to={`/app/conversations/${item.conversation_id}`} className="rq-gold">
                          فتح المحادثة
                        </Link>
                      </div>
                      {item.type === "response" ? (
                        <ReviewResponse
                          item={item}
                          onDone={() => {
                            setDismissed((prev) => new Set(prev).add(item.id));
                          }}
                        />
                      ) : (
                        <ResolveFlag
                          item={item}
                          onDone={() => {
                            setDismissed((prev) => new Set(prev).add(item.id));
                          }}
                        />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
