import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Tone } from "../lib/labels";
import { IconX } from "./icons";

/* ---------------- Badge ---------------- */

export function Badge({
  tone = "neutral",
  dot = false,
  children,
  className = "",
  style,
}: {
  tone?: Tone;
  dot?: boolean;
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <span className={`rq-badge rq-badge-${tone} ${dot ? "rq-badge-dot" : ""} ${className}`} style={style}>
      {children}
    </span>
  );
}

/* ---------------- Button ---------------- */

type ButtonVariant = "default" | "primary" | "ghost" | "danger" | "success";

export function Button({
  variant = "default",
  size,
  block,
  loading,
  children,
  className = "",
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "lg";
  block?: boolean;
  loading?: boolean;
}) {
  const cls = [
    "rq-btn",
    variant !== "default" ? `rq-btn-${variant}` : "",
    size ? `rq-btn-${size}` : "",
    block ? "rq-btn-block" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button className={cls} disabled={rest.disabled || loading} {...rest}>
      {loading && <span className="rq-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />}
      {children}
    </button>
  );
}

/* ---------------- Card ---------------- */

export function Card({
  children,
  className = "",
  padded = false,
  style,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
  style?: React.CSSProperties;
}) {
  return (
    <div className={`rq-card ${padded ? "rq-card-pad" : ""} ${className}`} style={style}>
      {children}
    </div>
  );
}

export function CardHead({
  title,
  actions,
}: {
  title: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="rq-card-head">
      <div className="rq-card-title">{title}</div>
      {actions && <div className="rq-row">{actions}</div>}
    </div>
  );
}

/* ---------------- Spinner / loading ---------------- */

export function Spinner({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  return (
    <span
      className={`rq-spinner ${size === "lg" ? "rq-spinner-lg" : ""}`}
      style={size === "sm" ? { width: 14, height: 14, borderWidth: 2 } : undefined}
    />
  );
}

export function LoadingBlock({ label = "جارٍ التحميل…" }: { label?: string }) {
  return (
    <div className="rq-empty">
      <Spinner size="lg" />
      <div className="rq-empty-title">{label}</div>
    </div>
  );
}

/* ---------------- Empty state ---------------- */

export function EmptyState({
  icon,
  title,
  desc,
  action,
}: {
  icon: ReactNode;
  title: string;
  desc?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rq-empty">
      <div className="rq-empty-icon">{icon}</div>
      <div className="rq-empty-title">{title}</div>
      {desc && <div className="rq-empty-desc">{desc}</div>}
      {action && <div style={{ marginTop: 10 }}>{action}</div>}
    </div>
  );
}

/* ---------------- Progress ---------------- */

export function Progress({
  done,
  total,
  indeterminate = false,
}: {
  done: number;
  total: number;
  indeterminate?: boolean;
}) {
  const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
  return (
    <div className={`rq-progress ${indeterminate ? "rq-progress-indeterminate" : ""}`}>
      <div className="rq-progress-bar" style={{ width: `${pct}%` }} />
    </div>
  );
}

/* ---------------- Modal ---------------- */

export function Modal({
  open,
  onClose,
  title,
  children,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="rq-modal-overlay" onClick={onClose}>
      <div
        className="rq-modal"
        style={wide ? { maxWidth: 720 } : undefined}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="rq-modal-head">
          <div className="rq-modal-title">{title}</div>
          <button className="rq-btn rq-btn-ghost rq-btn-sm" onClick={onClose} aria-label="إغلاق">
            <IconX width={16} height={16} />
          </button>
        </div>
        <div className="rq-modal-body">{children}</div>
      </div>
    </div>
  );
}

/* ---------------- Toaster ---------------- */

type ToastKind = "success" | "error" | "warn" | "info";
interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

const ToastCtx = createContext<{ toast: (kind: ToastKind, message: string) => void }>({
  toast: () => undefined,
});

export function useToast() {
  return useContext(ToastCtx);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((kind: ToastKind, message: string) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, kind, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5200);
  }, []);

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div className="rq-toast-stack">
        {toasts.map((t) => (
          <div key={t.id} className={`rq-toast rq-toast-${t.kind}`}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/* ---------------- Confirm dialog ---------------- */

/* ---------------- class-name helper ---------------- */

type ClassValue = string | false | null | undefined | ClassDictionary | ClassArray;
interface ClassDictionary { [id: string]: unknown; }
interface ClassArray { [index: number]: unknown; }

export function cn(...inputs: ClassValue[]): string {
  const classes: string[] = [];
  for (const input of inputs) {
    if (!input || typeof input === "boolean") continue;
    if (typeof input === "string") { classes.push(input); continue; }
    if (Array.isArray(input)) { classes.push(cn(input)); continue; }
    if (typeof input === "object") {
      for (const [k, v] of Object.entries(input as ClassDictionary)) {
        if (typeof v === "number" || (typeof v === "string" && v !== "")) { classes.push(k); }
      }
    }
  }
  return classes.join(" ");
}

/* ---------------- Input ---------------- */

export function Input({
  className = "",
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement> & { className?: string }) {
  return <input className={cn("rq-input", className)} {...rest} />;
}

/* ---------------- Select ---------------- */

export function Select({
  className = "",
  ...rest
}: React.SelectHTMLAttributes<HTMLSelectElement> & { className?: string }) {
  return <select className={cn("rq-select", className)} {...rest} />;
}

/* ---------------- Textarea ---------------- */

export function Textarea({
  className = "",
  ...rest
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { className?: string }) {
  return <textarea className={cn("rq-textarea", className)} {...rest} />;
}

/* ---------------- Field (label + control) ---------------- */

export function Field({
  label,
  children,
  className,
  htmlFor,
  style,
}: {
  label?: ReactNode;
  children: ReactNode;
  className?: string;
  htmlFor?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div className={cn("rq-field", className)} style={style}>
      {label && <label className="rq-label" htmlFor={htmlFor}>{label}</label>}
      {children}
    </div>
  );
}

/* ---------------- Table ---------------- */

export function Table({
  columns,
  rows,
  rowKey,
  children,
}: {
  columns: { key: string; label: ReactNode; className?: string }[];
  rows: Record<string, ReactNode>[];
  rowKey: (row: Record<string, ReactNode>, i: number) => string | number;
  children?: ReactNode;
}) {
  return (
    <div className="rq-table-wrap">
      <table className="rq-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.className}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={String(rowKey(row, i))}>
              {columns.map((c) => (
                <td key={c.key}>{row[c.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {children}
    </div>
  );
}

/* ---------------- Skeleton ---------------- */

export function Skeleton({
  className = "",
  style,
  ...rest
}: React.HTMLAttributes<HTMLDivElement> & { className?: string }) {
  return (
    <div
      className={cn("rq-skeleton", "rq-surface-2", className)}
      style={style}
      {...rest}
    />
  );
}

/* ---------------- Tooltip ---------------- */

const TooltipCtx = createContext<{ text: string } | null>(null);

export function Tooltip({ text, children }: { text: string; children: ReactNode }) {
  return (
    <TooltipCtx.Provider value={{ text }}>
      <span style={{ display: "inline-flex" }}>{children}</span>
    </TooltipCtx.Provider>
  );
}

export function TooltipTrigger({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export function TooltipContent({ children }: { children?: ReactNode }) {
  return <>{children}</>;
}

/* ---------------- Breadcrumbs ---------------- */

export function Breadcrumbs({
  items,
}: {
  items: { label: ReactNode; href?: string }[];
}) {
  return (
    <nav aria-label="Breadcrumbs" className="rq-breadcrumbs rq-xs rq-faint">
      {items.map((it, i) => (
        <span key={i} className="rq-breadcrumbs-sep">
          {it.href ? <a href={it.href}>{it.label}</a> : <span>{it.label}</span>}
        </span>
      ))}
    </nav>
  );
}

/* ---------------- Confirm dialog ---------------- */

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = "تأكيد",
  danger = false,
  loading = false,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: ReactNode;
  confirmLabel?: string;
  danger?: boolean;
  loading?: boolean;
}) {
  return (
    <Modal open={open} onClose={onClose} title={title}>
      <div className="rq-stack">
        <p className="rq-dim" style={{ lineHeight: 1.9 }}>
          {message}
        </p>
        <div className="rq-row rq-gap-2" style={{ justifyContent: "flex-end" }}>
          <Button variant="ghost" onClick={onClose}>
            إلغاء
          </Button>
          <Button variant={danger ? "danger" : "primary"} onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
