import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ProductLogo } from "../components/AppShell";
import { IconEye, IconLock, IconShield, IconSpark } from "../components/icons";
import { Button, Field, Input } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { ApiError, get } from "../lib/api";

interface DemoHint {
  email: string;
  password: string;
  org: string;
}

export default function AuthPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { login, register } = useAuth();

  const returnTo = params.get("returnTo") || "/app";
  const initialMode = params.get("mode") === "register" ? "register" : "login";
  const [mode, setMode] = useState<"login" | "register">(initialMode);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [error, setError] = useState("");
  const [devUrl, setDevUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [demo, setDemo] = useState<DemoHint | null>(null);

  // Dev/test only: surface the pre-made demo account (404 in production).
  useEffect(() => {
    let cancelled = false;
    get<DemoHint>("/api/auth/demo")
      .then((hint) => {
        if (!cancelled) setDemo(hint);
      })
      .catch(() => {
        if (!cancelled) setDemo(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const switchMode = (m: "login" | "register") => {
    setMode(m);
    setError("");
    setDevUrl("");
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setDevUrl("");
    setBusy(true);
    try {
      if (mode === "login") {
        if (!email.trim() || !password) {
          setError("أدخل البريد وكلمة المرور");
          setBusy(false);
          return;
        }
        await login(email.trim(), password.trim());
        navigate(returnTo, { replace: true });
      } else {
        if (!email.trim() || password.length < 8 || !fullName.trim() || !orgName.trim()) {
          setError("أكمل جميع الحقول (كلمة المرور ٨ أحرف على الأقل)");
          setBusy(false);
          return;
        }
        const resp = await register({
          email: email.trim(),
          password,
          full_name: fullName.trim(),
          org_name: orgName.trim(),
        });
        if (resp.dev_verify_url) {
          setDevUrl(resp.dev_verify_url);
        }
        navigate(returnTo, { replace: true });
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "حدث خطأ غير متوقع");
      setBusy(false);
    }
  };

  return (
    <div className="rq-auth">
      <aside className="rq-auth-side">
        <div className="rq-pattern" />
        <ProductLogo />
        <blockquote className="rq-auth-quote">
          «الذي يراقب <span className="rq-gold">محادثاتِك</span> ويفهم لهجاتِها، ويعلّمُك من حواراتِك،
          ويصوغُ ردودَك بأسلوبك — هو رقيبٌ أمينٌ لا يُرسل شيئًا إلا بإذنك.»
        </blockquote>
        <div className="rq-auth-points">
          <div className="rq-auth-point">
            <IconShield />
            مراقبة تلقائية للإساءة والاحتيال وبيانات الخصوصية
          </div>
          <div className="rq-auth-point">
            <IconEye />
            كشف اللهجات والنية والكيانات في كل محادثة
          </div>
          <div className="rq-auth-point">
            <IconSpark />
            ردود ذكية بأسلوب صفحتك — بانتظار موافقتك دائمًا
          </div>
          <div className="rq-auth-point">
            <IconLock />
            مجاني ومحلي بالكامل، بلا بطاقة ائتمان
          </div>
        </div>
      </aside>

      <main className="rq-auth-main">
        <div className="rq-auth-card">
          <h1 className="rq-auth-title">{mode === "login" ? "أهلًا بعودتك" : "أنشئ منظمتك"}</h1>
          <p className="rq-auth-sub">
            {mode === "login"
              ? "سجّل الدخول لتراقب محادثات صفحاتك وتتعلم منها"
              : "ابدأ مجانًا — حساب واحد، منظمة واحدة، ولا رسوم إطلاقًا"}
          </p>

          <div className="rq-auth-tabs">
            <button
              className={`rq-auth-tab ${mode === "login" ? "rq-auth-tab-active" : ""}`}
              onClick={() => switchMode("login")}
              type="button"
            >
              تسجيل الدخول
            </button>
            <button
              className={`rq-auth-tab ${mode === "register" ? "rq-auth-tab-active" : ""}`}
              onClick={() => switchMode("register")}
              type="button"
            >
              حساب جديد
            </button>
          </div>

          <form className="rq-stack" onSubmit={onSubmit}>
            {mode === "register" && (
              <>
                <Field label="الاسم الكامل" htmlFor="full_name">
                  <Input
                    id="full_name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="مثال: أحمد العلي"
                    autoComplete="name"
                  />
                </Field>
                <Field label="اسم المنظمة / النشاط" htmlFor="org_name">
                  <Input
                    id="org_name"
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    placeholder="مثال: متجر النخبة"
                    autoComplete="organization"
                  />
                </Field>
              </>
            )}
            <Field label="البريد الإلكتروني" htmlFor="email">
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                dir="ltr"
                className="rq-text-end"
              />
            </Field>
            <Field label="كلمة المرور" htmlFor="password">
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === "register" ? "٨ أحرف على الأقل" : "••••••••"}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
              />
            </Field>

            {error && <div className="rq-form-error">{error}</div>}
            {devUrl && (
              <div className="rq-form-success rq-stack rq-gap-2">
                <div>تم إنشاء الحساب. في بيئة التطوير، رابط التحقق من البريد:</div>
                <a href={devUrl} target="_blank" rel="noreferrer" className="rq-xs rq-mono">
                  {devUrl}
                </a>
              </div>
            )}

            <Button type="submit" variant="primary" size="lg" block loading={busy}>
              {mode === "login" ? "تسجيل الدخول" : "إنشاء الحساب مجانًا"}
            </Button>
          </form>

          {demo && mode === "login" && (
            <div className="rq-demo-card">
              <div className="rq-demo-card-title">
                <IconSpark />
                حساب تجريبي جاهز للاختبار
              </div>
              <div className="rq-demo-row">
                <span className="rq-demo-key">البريد</span>
                <span className="rq-mono">{demo.email}</span>
              </div>
              <div className="rq-demo-row">
                <span className="rq-demo-key">كلمة المرور</span>
                <span className="rq-mono">{demo.password}</span>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                block
                onClick={() => {
                  setEmail(demo.email);
                  setPassword(demo.password);
                  setError("");
                }}
              >
                تعبئة البيانات تلقائيًا
              </Button>
            </div>
          )}

          <div className="rq-xs rq-faint" style={{ marginTop: 18, textAlign: "center" }}>
            بالدخول أنت توافق على أن بياناتك تبقى ملكك وتُعالَج محليًا داخل منظمتك.
          </div>
          <div className="rq-xs" style={{ marginTop: 10, textAlign: "center" }}>
            <Link to="/" className="rq-faint">
              ← العودة للرئيسية
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
