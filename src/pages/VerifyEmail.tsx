import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { LogoMark } from "../components/AppShell";
import { IconCheck, IconShield, IconWarning } from "../components/icons";
import { Button } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../hooks/useAuth";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const { isAuthenticated, loading } = useAuth();
  const [state, setState] = useState<"working" | "ok" | "error">("working");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (loading) return;
    if (!isAuthenticated) return;
    if (!token) {
      setState("error");
      setMessage("رابط التحقق غير صالح — لا يوجد رمز في الرابط");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const resp = await api<{ ok: boolean; verified: boolean }>("/api/auth/verify-email", {
          method: "POST",
          body: { token },
        });
        if (!cancelled && resp.verified) {
          setState("ok");
          setMessage("تم التحقق من بريدك الإلكتروني بنجاح");
        }
      } catch (err) {
        if (!cancelled) {
          setState("error");
          setMessage(err instanceof ApiError ? err.message : "تعذّر التحقق من البريد");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, isAuthenticated, loading]);

  if (!isAuthenticated && !loading) {
    return (
      <div className="rq-auth-main" style={{ minHeight: "100vh", background: "var(--bg)" }}>
        <div className="rq-auth-card" style={{ textAlign: "center" }}>
          <div className="rq-empty">
            <div className="rq-empty-icon">
              <IconShield width={26} height={26} />
            </div>
            <div className="rq-empty-title">سجّل الدخول أولًا للتحقق من بريدك</div>
            <div className="rq-empty-desc">
              أتمم تسجيل الدخول ثم سنعاود التحقق تلقائيًا بنفس الرابط.
            </div>
            <Link to={`/auth?returnTo=${encodeURIComponent(`/verify-email?token=${token}`)}`}>
              <Button variant="primary">الانتقال لتسجيل الدخول</Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rq-auth-main" style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <div className="rq-auth-card" style={{ textAlign: "center" }}>
        <div className="rq-empty" style={{ paddingTop: 20 }}>
          <LogoMark size={56} />
          <div className="rq-empty-title rq-mt-2">
            {state === "working" && "جارٍ التحقق…"}
            {state === "ok" && "تم التحقق بنجاح"}
            {state === "error" && "تعذّر التحقق"}
          </div>
          <div className="rq-empty-desc">
            {state === "working" && "نستعلم عن رمز التحقق الخاص بك…"}
            {state === "ok" && message}
            {state === "error" && message}
          </div>
          {state === "ok" && (
            <div className="rq-mt-3">
              <IconCheck width={30} height={30} className="rq-gold" />
            </div>
          )}
          {state === "error" && (
            <div className="rq-mt-3">
              <IconWarning width={30} height={30} className="rq-gold" />
            </div>
          )}
          {state !== "working" && (
            <Link to="/app/dashboard">
              <Button variant="primary" style={{ marginTop: 10 }}>
                الذهاب إلى لوحة التحكم
              </Button>
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
