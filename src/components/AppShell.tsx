import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { api } from "../lib/api";
import { ROLE_LABELS } from "../lib/labels";
import { initials } from "../lib/format";
import type { ApiStatus, InboxStats } from "../lib/types";
import { Badge, Button, LoadingBlock, Select, useToast } from "./ui";
import {
  IconAnalytics,
  IconChat,
  IconEval,
  IconGear,
  IconHome,
  IconInbox,
  IconJobs,
  IconKnowledge,
  IconLogout,
  IconMemory,
  IconPages,
  IconTraining,
} from "./icons";

/* ── Inline sun / moon icons (not in icons.tsx) ── */

function IconSun(props: any) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width={props.width || 20} height={props.height || 20} stroke="currentColor" strokeWidth={2} strokeLinecap="square" strokeLinejoin="miter" fill="none" aria-hidden>
      <path d="M12 2 V5 M12 19 V22 M4.22 4.22 L6.34 6.34 M17.66 17.66 L19.78 19.78 M2 12 H5 M19 12 H22 M4.22 19.78 L6.34 17.66 M17.66 6.34 L19.78 4.22" />
      <rect x="8" y="8" width="8" height="8" rx="0" />
    </svg>
  );
}

function IconMoon(props: any) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width={props.width || 20} height={props.height || 20} stroke="currentColor" strokeWidth={2} strokeLinecap="square" strokeLinejoin="miter" fill="none" aria-hidden>
      <path d="M20 14 A8 8 0 1 1 10 4 A6 6 0 0 0 20 14Z" />
    </svg>
  );
}

/* ── Navigation ── */

const NAV_ITEMS = [
  { to: "/app/dashboard", label: "لوحة التحكم", icon: IconHome },
  { to: "/app/inbox", label: "صندوق المراجعة", icon: IconInbox, badgeKey: "pending_reviews" },
  { to: "/app/conversations", label: "المحادثات", icon: IconChat },
  { to: "/app/pages", label: "الصفحات", icon: IconPages },
  { to: "/app/jobs", label: "الوظائف", icon: IconJobs },
  { to: "/app/memory", label: "الذاكرة", icon: IconMemory },
  { to: "/app/knowledge", label: "المعرفة", icon: IconKnowledge },
  { to: "/app/training", label: "التدريب", icon: IconTraining },
  { to: "/app/evaluation", label: "التقييم", icon: IconEval },
  { to: "/app/analytics", label: "التحليلات", icon: IconAnalytics },
  { to: "/app/settings", label: "الإعدادات", icon: IconGear },
] as const;

const TITLES: Record<string, string> = {
  "/app/dashboard": "لوحة التحكم",
  "/app/inbox": "صندوق المراجعة",
  "/app/conversations": "المحادثات",
  "/app/pages": "الصفحات",
  "/app/jobs": "الوظائف",
  "/app/memory": "الذاكرة",
  "/app/knowledge": "المعرفة",
  "/app/training": "التدريب",
  "/app/evaluation": "التقييم",
  "/app/analytics": "التحليلات",
  "/app/settings": "الإعدادات",
};

const MOBILE_NAV = [
  { to: "/app/dashboard", label: "لوحة التحكم", icon: IconHome },
  { to: "/app/inbox", label: "المراجعة", icon: IconInbox },
  { to: "/app/conversations", label: "المحادثات", icon: IconChat },
  { to: "/app/pages", label: "الصفحات", icon: IconPages },
  { to: "/app/settings", label: "الإعدادات", icon: IconGear },
] as const;

/* ── RequireAuth ── */

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { loading, isAuthenticated } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="rq-empty" style={{ minHeight: "100vh" }}>
        <LoadingBlock label="جارٍ التحقق من الجلسة…" />
      </div>
    );
  }
  if (!isAuthenticated) {
    const returnTo = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/auth?returnTo=${returnTo}`} replace />;
  }
  return <>{children}</>;
}

/* ── StatusPill ── */

function StatusPill() {
  const { data } = useQuery({
    queryKey: ["api-status"],
    queryFn: () => api<ApiStatus>("/api/status"),
    staleTime: 60_000,
    refetchInterval: 120_000,
    retry: false,
  });
  if (!data) return null;
  const ok = data.model_available;
  return (
    <span className="rq-status-pill" title={`مزوّد النموذج: ${data.model_provider}`}>
      <span className={`rq-status-dot ${ok ? "rq-status-dot-ok" : "rq-status-dot-off"}`} />
      {ok ? "النموذج جاهز" : "النموذج غير متصل"}
    </span>
  );
}

/* ── Theme Toggle ── */

function ThemeToggle() {
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("rq-theme") as "dark" | "light") || "dark";
    }
    return "dark";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("rq-theme", theme);
  }, [theme]);

  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  return (
    <button
      className="rq-btn rq-btn-ghost rq-btn-sm"
      onClick={toggle}
      aria-label={theme === "dark" ? "الوضع الفاتح" : "الوضع الداكن"}
      title={theme === "dark" ? "الوضع الفاتح" : "الوضع الداكن"}
    >
      {theme === "dark" ? <IconSun width={16} height={16} /> : <IconMoon width={16} height={16} />}
    </button>
  );
}

/* ── Mobile bottom nav ── */

function MobileNav() {
  const location = useLocation();
  const { data: inboxStats } = useQuery({
    queryKey: ["inbox-stats"],
    queryFn: () => api<InboxStats>("/api/inbox/stats"),
    refetchInterval: 30_000,
    retry: false,
  });
  const inboxBadge = (inboxStats?.pending_reviews ?? 0) + (inboxStats?.open_flags ?? 0);

  return (
    <nav className="rq-mobile-nav">
      {MOBILE_NAV.map((item) => {
        const Icon = item.icon;
        const badge =
          "badgeKey" in item && item.badgeKey === "pending_reviews" ? inboxBadge : 0;
        const active = location.pathname === item.to || location.pathname.startsWith(item.to + "/");
        return (
          <NavLink
            key={item.to}
            to={item.to}
            className={`rq-mobile-nav-item ${active ? "rq-mobile-nav-item-active" : ""}`}
          >
            <Icon width={18} height={18} />
            <span>{item.label}</span>
            {badge > 0 && <span className="rq-nav-badge">{badge}</span>}
          </NavLink>
        );
      })}
    </nav>
  );
}

/* ── Main AppShell ── */

export function AppShell() {
  const { data, role, orgId, switchOrg, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const { toast } = useToast();

  const { data: inboxStats } = useQuery({
    queryKey: ["inbox-stats"],
    queryFn: () => api<InboxStats>("/api/inbox/stats"),
    refetchInterval: 30_000,
    retry: false,
  });

  const pendingCount = inboxStats?.pending_reviews ?? 0;
  const openFlags = inboxStats?.open_flags ?? 0;
  const inboxBadge = pendingCount + openFlags;

  const title = TITLES[location.pathname] ?? "رقيب";

  const onSwitchOrg = async (orgId: string) => {
    try {
      await switchOrg(orgId);
      toast("success", "تم التبديل إلى المنظمة الجديدة");
      navigate("/app/dashboard");
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "تعذّر تبديل المنظمة");
    }
  };

  const onLogout = async () => {
    await logout();
    navigate("/auth");
  };

  const currentOrg = data?.orgs.find((o) => o.id === orgId) ?? data?.orgs[0];

  return (
    <div className="rq-shell">
      <aside className="rq-sidebar">
        <div className="rq-brand">
          <div className="rq-brand-mark">ر</div>
          <div>
            <div className="rq-brand-name">رقيب</div>
          </div>
        </div>

        {data && data.orgs.length > 0 && (
          <div className="rq-org-switch">
            <div className="rq-org-label">المنظمة الحالية</div>
            {data.orgs.length === 1 ? (
              <div className="rq-row rq-gap-2" style={{ justifyContent: "space-between" }}>
                <span className="rq-org-name">{currentOrg?.name}</span>
                <span className="rq-org-role">{currentOrg ? ROLE_LABELS[currentOrg.role] : ""}</span>
              </div>
            ) : (
              <Select
                className="rq-select rq-xs"
                value={currentOrg?.id ?? ""}
                onChange={(e) => void onSwitchOrg(e.target.value)}
                aria-label="تبديل المنظمة"
              >
                {data.orgs.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name} — {ROLE_LABELS[o.role]}
                  </option>
                ))}
              </Select>
            )}
          </div>
        )}

        <nav className="rq-nav">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const badge =
              "badgeKey" in item && item.badgeKey === "pending_reviews" ? inboxBadge : 0;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `rq-nav-item ${isActive ? "rq-nav-item-active" : ""}`}
              >
                <Icon width={16} height={16} />
                <span>{item.label}</span>
                {badge > 0 && <span className="rq-nav-badge">{badge}</span>}
              </NavLink>
            );
          })}
        </nav>

        <div className="rq-sidebar-foot">
          <div className="rq-user-chip">
            <div className="rq-avatar">{data ? initials(data.user.full_name || data.user.email) : ""}</div>
            <div className="rq-grow" style={{ minWidth: 0 }}>
              <div className="rq-org-name" style={{ fontSize: 13 }}>
                {data?.user.full_name || data?.user.email}
              </div>
              <div className="rq-xs rq-faint" style={{ direction: "ltr", textAlign: "right" }}>
                {data?.user.email}
              </div>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={() => void onLogout()}>
            <IconLogout width={16} height={16} />
            تسجيل الخروج
          </Button>
        </div>
      </aside>

      <div className="rq-main">
        <header className="rq-topbar rq-glass">
          <div className="rq-topbar-title">{title}</div>
          <div className="rq-topbar-actions">
            <StatusPill />
            <ThemeToggle />
            {role && <Badge tone="brand">{ROLE_LABELS[role]}</Badge>}
          </div>
        </header>
        <main className="rq-content">
          <Outlet />
        </main>
      </div>

      <MobileNav />
    </div>
  );
}

export default function AppShellWithAuth() {
  return (
    <RequireAuth>
      <AppShell />
    </RequireAuth>
  );
}

/* ── Brand exports ── */

export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <div
      className="rq-brand-mark"
      style={{ width: size, height: size, fontSize: size * 0.52 }}
    >
      ر
    </div>
  );
}

export function ProductLogo() {
  return (
    <div className="rq-brand" style={{ padding: 0 }}>
      <LogoMark />
      <div>
        <div className="rq-brand-name">رقيب</div>
        <div className="rq-brand-tag">راقب · تعلّم · ارتَقِ</div>
      </div>
    </div>
  );
}
