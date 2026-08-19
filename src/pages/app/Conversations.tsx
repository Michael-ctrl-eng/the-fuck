import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Link, useNavigate } from "react-router-dom";
import { Badge, Button, Card, EmptyState, Input, LoadingBlock, Select } from "../../components/ui";
import { IconChat, IconFlag, IconSearch } from "../../components/icons";
import { api } from "../../lib/api";
import {
  CONVERSATION_STATUS_LABELS,
  DIALECT_LABELS,
  INTENT_LABELS,
  toneForConversationStatus,
  toneForDialect,
  toneForIntent,
} from "../../lib/labels";
import { formatPercent, relativeTime } from "../../lib/format";
import type { ConversationListItem, ConversationListResponse, Page } from "../../lib/types";

function useDebounced<T>(value: T, delay = 400): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

const DIALECT_OPTIONS = Object.entries(DIALECT_LABELS);
const INTENT_OPTIONS = Object.entries(INTENT_LABELS);

export default function Conversations() {
  const navigate = useNavigate();
  const [pageId, setPageId] = useState("");
  const [dialect, setDialect] = useState("");
  const [intent, setIntent] = useState("");
  const [status, setStatus] = useState("");
  const [flagged, setFlagged] = useState(false);
  const [dataset, setDataset] = useState(false);
  const [q, setQ] = useState("");
  const debouncedQ = useDebounced(q, 450);

  const { data: pages } = useQuery({
    queryKey: ["pages"],
    queryFn: () => api<Page[]>("/api/pages"),
    staleTime: 60_000,
  });

  const filters = useMemo(() => {
    const params = new URLSearchParams();
    if (pageId) params.set("page_id", pageId);
    if (dialect) params.set("dialect", dialect);
    if (intent) params.set("intent", intent);
    if (status) params.set("status", status);
    if (flagged) params.set("flagged", "true");
    if (dataset) params.set("dataset", "true");
    if (debouncedQ.trim()) params.set("q", debouncedQ.trim());
    params.set("limit", "50");
    return params.toString();
  }, [pageId, dialect, intent, status, flagged, dataset, debouncedQ]);

  const queryKey = ["conversations", filters];
  const { data, isLoading, isFetching } = useQuery({
    queryKey,
    queryFn: () => api<ConversationListResponse>(`/api/conversations?${filters}`),
    placeholderData: (prev: ConversationListResponse | undefined) => prev,
  });

  const items = data?.items ?? [];
  const [extra, setExtra] = useState<ConversationListItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  // reset pagination when filters change
  useEffect(() => {
    setExtra([]);
    setNextCursor(null);
  }, [filters]);

  const all = useMemo(() => [...items, ...extra], [items, extra]);
  const hasMore = (nextCursor ?? data?.next_cursor ?? null) !== null;

  const loadMore = async () => {
    const cursor = nextCursor ?? data?.next_cursor ?? null;
    if (!cursor) return;
    const params = new URLSearchParams(filters);
    params.set("cursor", cursor);
    const resp = await api<ConversationListResponse>(`/api/conversations?${params.toString()}`);
    setExtra((prev) => [...prev, ...resp.items]);
    setNextCursor(resp.next_cursor);
  };

  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: all.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 96,
    overscan: 8,
  });

  return (
    <div className="rq-page">
      <div className="rq-page-head">
        <div>
          <h1 className="rq-page-title">المحادثات</h1>
          <p className="rq-page-sub">
            كل المحادثات المستوردة والمحلَّلة من صفحاتك — رتّب وصفِّ ثم افتح أي حوار للرد عليه.
          </p>
        </div>
      </div>

      <div className="rq-filterbar">
        <div className="rq-search">
          <IconSearch />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="ابحث في النصوظ…"
          />
        </div>
        <Select value={pageId} onChange={(e) => setPageId(e.target.value)} aria-label="الصفحة">
          <option value="">كل الصفحات</option>
          {(pages ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.page_name}
            </option>
          ))}
        </Select>
        <Select value={dialect} onChange={(e) => setDialect(e.target.value)} aria-label="اللهجة">
          <option value="">كل اللهجات</option>
          {DIALECT_OPTIONS.map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
          </Select>
        <Select value={intent} onChange={(e) => setIntent(e.target.value)} aria-label="النية">
          <option value="">كل النوايا</option>
          {INTENT_OPTIONS.map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
        <Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="الحالة">
          <option value="">كل الحالات</option>
          {Object.entries(CONVERSATION_STATUS_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
        <label className="rq-check">
          <input type="checkbox" checked={flagged} onChange={(e) => setFlagged(e.target.checked)} />
          مرفوعة
        </label>
        <label className="rq-check">
          <input type="checkbox" checked={dataset} onChange={(e) => setDataset(e.target.checked)} />
          في المجموعة
        </label>
      </div>

      {isLoading ? (
        <LoadingBlock label="جارٍ جلب المحادثات…" />
      ) : all.length === 0 ? (
        <Card>
          <EmptyState
            icon={<IconChat width={26} height={26} />}
            title="لا توجد محادثات مطابقة"
            desc="اربط صفحتك وشغّل مزامنة، أو عدّل عوامل التصفية أعلاه."
            action={
              <Link to="/app/pages" className="rq-btn rq-btn-primary rq-btn-sm">
                إدارة الصفحات
              </Link>
            }
          />
        </Card>
      ) : (
        <Card>
          <div
            ref={parentRef}
            style={{ height: "min(72vh, 760px)", overflowY: "auto", position: "relative", padding: "8px 10px" }}
          >
            <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
              {virtualizer.getVirtualItems().map((vi) => {
                const c = all[vi.index];
                if (!c) return null;
                return (
                  <div
                    key={c.id}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      transform: `translateY(${vi.start}px)`,
                      padding: "5px 4px",
                    }}
                  >
                    <button
                      type="button"
                      className="rq-conv-row"
                      onClick={() => navigate(`/app/conversations/${c.id}`)}
                    >
                      <div className="rq-conv-main">
                        <div className="rq-conv-title">
                          {c.page_name || "صفحة"}
                          <Badge tone={toneForIntent(c.intent_label)}>
                            {INTENT_LABELS[c.intent_label] ?? c.intent_label}
                          </Badge>
                          {c.is_flagged && (
                            <Badge tone="danger" dot>
                              <IconFlag width={11} height={11} />
                            </Badge>
                          )}
                          {c.dataset_included && <Badge tone="success">في المجموعة</Badge>}
                        </div>
                        <div className="rq-conv-snippet">
                          <Badge tone={toneForDialect(c.dialect_label)} className="rq-xs">
                            {DIALECT_LABELS[c.dialect_label] ?? c.dialect_label}
                            {c.dialect_confidence > 0 && ` · ${formatPercent(c.dialect_confidence)}٪`}
                          </Badge>
                          <span style={{ marginInlineStart: 8 }}>
                            جودة {formatPercent(c.quality_score)}٪ · {c.message_count} رسالة
                          </span>
                        </div>
                      </div>
                      <div className="rq-conv-meta">
                        <div className="rq-conv-time">{relativeTime(c.updated_at)}</div>
                        <Badge tone={toneForConversationStatus(c.status)}>
                          {CONVERSATION_STATUS_LABELS[c.status] ?? c.status}
                        </Badge>
                      </div>
                    </button>
                  </div>
                );
              })}
            </div>
            {isFetching && (
              <div className="rq-row" style={{ justifyContent: "center", padding: 12 }}>
                <span className="rq-spinner" />
              </div>
            )}
          </div>
          {all.length > 0 && hasMore && (
            <div className="rq-row rq-gap-1" style={{ justifyContent: "center", padding: 14 }}>
              <Button variant="ghost" size="sm" onClick={() => void loadMore()}>
                تحميل المزيد
              </Button>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
