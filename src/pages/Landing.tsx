import { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import { LogoMark } from "../components/AppShell";

/* ═══════════════════════════════════════════
   HOOKS
   ═══════════════════════════════════════════ */

function useTypewriter(text: string, speed = 38, startDelay = 600) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => {
      let i = 0;
      const id = setInterval(() => {
        setDisplayed(text.slice(0, i + 1));
        i++;
        if (i >= text.length) {
          clearInterval(id);
          setDone(true);
        }
      }, speed);
      return () => clearInterval(id);
    }, startDelay);
    return () => clearTimeout(timer);
  }, [text, speed, startDelay]);
  return { displayed, done };
}

function useReveal(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { threshold },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, visible };
}

function useActiveStep(count: number) {
  const refs = useRef<(HTMLDivElement | null)[]>([]);
  const [active, setActive] = useState(0);

  const setRef = useCallback(
    (index: number) => (el: HTMLDivElement | null) => {
      refs.current[index] = el;
    },
    [],
  );

  useEffect(() => {
    const elements = refs.current.filter(Boolean) as HTMLElement[];
    if (!elements.length) return;

    const obs = new IntersectionObserver(
      (entries) => {
        let maxRatio = 0;
        let maxIdx = 0;
        entries.forEach((entry) => {
          const idx = elements.indexOf(entry.target as HTMLElement);
          if (idx !== -1 && entry.intersectionRatio > maxRatio) {
            maxRatio = entry.intersectionRatio;
            maxIdx = idx;
          }
        });
        if (maxRatio > 0.3) setActive(maxIdx);
      },
      { threshold: [0.3, 0.5, 0.7] },
    );
    elements.forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, [count]);

  return { active, setRef };
}

/* ═══════════════════════════════════════════
   REVEAL WRAPPER
   ═══════════════════════════════════════════ */

function Reveal({
  children,
  className,
  id,
  style,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  id?: string;
  style?: React.CSSProperties;
  delay?: number;
}) {
  const { ref, visible } = useReveal();
  return (
    <div
      ref={ref}
      id={id}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(20px)",
        transition: `opacity 600ms var(--ease), transform 600ms var(--ease)`,
        transitionDelay: `${delay}ms`,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/* ═══════════════════════════════════════════
   SHARED STYLES
   ═══════════════════════════════════════════ */

const tintDot = (delay = 0): React.CSSProperties => ({
  display: "inline-block",
  width: 48,
  height: 3,
  background: "var(--c-primary)",
  borderRadius: 2,
  marginBottom: "var(--s-4)",
  animationDelay: `${delay}ms`,
});

const glassCard: React.CSSProperties = {
  borderRadius: "var(--radius-xl)",
  background: "rgba(20,20,20,0.3)",
  backdropFilter: "blur(12px)",
  WebkitBackdropFilter: "blur(12px)",
  border: "1px solid rgba(245,245,244,0.08)",
  boxShadow: "inset 0 0 6px 2px rgba(20,20,20,0.5)",
};

const sectionPad: React.CSSProperties = {
  padding: "var(--s-20) var(--s-6)",
};

const sectionPadLarge: React.CSSProperties = {
  padding: "var(--s-24) var(--s-6)",
};

/* ═══════════════════════════════════════════
   LANDING PAGE
   ═══════════════════════════════════════════ */

export default function Landing() {
  const heroHeadline = useTypewriter("راقب. تعلّم. ارتَقِ.");
  const { active: activeStep, setRef: stepRef } = useActiveStep(6);

  const [heroVisible, setHeroVisible] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setHeroVisible(true), 100);
    return () => clearTimeout(t);
  }, []);

  const steps = [
    { idx: "01", name: "اربط", desc: "اتصل بصفحتك على فيسبوك" },
    { idx: "02", name: "استورد", desc: "جلب المحادثات والبيانات" },
    { idx: "03", name: "حلّل", desc: "فهم اللهجات والنيات" },
    { idx: "04", name: "تعلّم", desc: "بناء ذاكرة ذكية" },
    { idx: "05", name: "رد", desc: "اقتراحات بأسلوب صفحتك" },
    { idx: "06", name: "تطوّر", desc: "تحسين مستمر بالبيانات" },
  ];

  return (
    <div
      className="rq-landing"
      style={{
        background: `
          radial-gradient(1200px 600px at 85% -10%, rgba(37,99,235,0.08), transparent 60%),
          radial-gradient(900px 500px at -10% 30%, rgba(56,189,248,0.04), transparent 55%),
          var(--background)
        `,
        overflowX: "hidden",
      }}
    >
      {/* ═══ 1 · STICKY NAVBAR ═══ */}
      <nav
        style={{
          position: "sticky",
          top: 0,
          zIndex: 9999,
          height: 64,
          background: "rgba(0,0,0,0.5)",
          backdropFilter: "blur(8px)",
          WebkitBackdropFilter: "blur(8px)",
          borderBottom: "1px solid rgba(245,245,244,0.08)",
          display: "flex",
          alignItems: "center",
        }}
      >
        <div
          className="rq-container"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
            padding: "0 var(--s-6)",
          }}
        >
          <Link to="/" aria-label="رقيب — الرئيسية">
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--s-2)",
              }}
            >
              <LogoMark size={32} />
              <span
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: "1.25rem",
                  fontWeight: 700,
                  color: "var(--c-text)",
                }}
              >
                رقيب
              </span>
            </div>
          </Link>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--s-8)",
            }}
          >
            {["المميزات", "كيف يعمل", "الخصوصية"].map((label) => (
              <a
                key={label}
                href={`#${label === "المميزات" ? "features" : label === "كيف يعمل" ? "how" : "privacy"}`}
                style={{
                  color: "var(--c-text-3)",
                  fontSize: "var(--font-sm)",
                  fontWeight: 700,
                  transition: "color 200ms",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.color = "var(--c-text)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.color = "var(--c-text-3)")
                }
              >
                {label}
              </a>
            ))}
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--s-3)",
            }}
          >
            <Link
              to="/auth?returnTo=/app"
              style={{
                color: "var(--c-text-3)",
                fontSize: "var(--font-sm)",
                fontWeight: 700,
                padding: "8px 16px",
                borderRadius: "var(--radius-full)",
                transition: "color 200ms",
              }}
            >
              دخول
            </Link>
            <Link
              to="/auth?mode=register&returnTo=/app"
              className="rq-btn rq-btn-primary"
              style={{
                borderRadius: "var(--radius-full)",
                padding: "8px 24px",
              }}
            >
              ابدأ مجانًا
            </Link>
          </div>
        </div>
      </nav>

      {/* ═══ 2 · HERO ═══ */}
      <section
        style={{
          minHeight: "100svh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Animated gradient background */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            overflow: "hidden",
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              position: "absolute",
              top: "20%",
              left: "10%",
              width: 600,
              height: 600,
              borderRadius: "50%",
              background:
                "radial-gradient(circle, rgba(37,99,235,0.12) 0%, transparent 70%)",
              filter: "blur(60px)",
              animation: "rq-hero-drift-1 12s ease-in-out infinite alternate",
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: "10%",
              right: "15%",
              width: 500,
              height: 500,
              borderRadius: "50%",
              background:
                "radial-gradient(circle, rgba(56,189,248,0.08) 0%, transparent 70%)",
              filter: "blur(80px)",
              animation: "rq-hero-drift-2 15s ease-in-out infinite alternate",
            }}
          />
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              width: 400,
              height: 400,
              borderRadius: "50%",
              background:
                "radial-gradient(circle, rgba(29,78,216,0.06) 0%, transparent 70%)",
              filter: "blur(70px)",
              animation: "rq-hero-drift-3 10s ease-in-out infinite alternate",
            }}
          />
          {/* CSS particle dots */}
          {Array.from({ length: 30 }).map((_, i) => (
            <div
              key={i}
              style={{
                position: "absolute",
                width: 2,
                height: 2,
                borderRadius: "50%",
                background: "rgba(245,245,244,0.15)",
                top: `${10 + (i * 37) % 80}%`,
                left: `${5 + (i * 29) % 90}%`,
                animation: `rq-particle-float ${6 + (i % 5) * 2}s ease-in-out infinite alternate`,
                animationDelay: `${(i * 200) % 3000}ms`,
              }}
            />
          ))}
        </div>

        {/* Center card */}
        <div
          style={{
            ...glassCard,
            padding: "var(--s-10) var(--s-10)",
            maxWidth: 720,
            width: "90%",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
            gap: "var(--s-5)",
            position: "relative",
            zIndex: 2,
            opacity: heroVisible ? 1 : 0,
            transform: heroVisible ? "translateY(0)" : "translateY(30px)",
            transition: "opacity 800ms var(--ease), transform 800ms var(--ease)",
          }}
        >
          <span
            style={{
              fontSize: 12,
              fontWeight: 800,
              letterSpacing: "0.1em",
              color: "var(--c-text-3)",
              textTransform: "uppercase" as const,
            }}
          >
            PIXEL / AI
          </span>

          <h1
            style={{
              fontFamily: "var(--font-display)",
              fontSize: "clamp(3rem, 8vw, 7rem)",
              fontWeight: 500,
              letterSpacing: "-0.05em",
              lineHeight: 1.1,
              margin: 0,
              color: "var(--c-text)",
            }}
          >
            {heroHeadline.displayed}
            {!heroHeadline.done && (
              <span
                style={{
                  display: "inline-block",
                  width: 3,
                  height: "0.85em",
                  background: "var(--c-primary)",
                  marginLeft: 2,
                  animation: "rq-spin 1s steps(2) infinite",
                  verticalAlign: "middle",
                }}
              />
            )}
          </h1>

          <p
            style={{
              fontSize: 18,
              color: "var(--c-text-2)",
              maxWidth: "50ch",
              lineHeight: 1.8,
              margin: 0,
            }}
          >
            رقيب منظومة ذكاء اصطناعي عربية لمراقبة محادثات صفحات فيسبوك
          </p>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--s-4)",
              marginTop: "var(--s-2)",
              flexWrap: "wrap",
              justifyContent: "center",
            }}
          >
            <Link
              to="/auth?mode=register&returnTo=/app"
              style={{
                background:
                  "linear-gradient(135deg, rgba(37,99,235,0.8), var(--c-primary))",
                color: "#fff",
                borderRadius: "var(--radius-full)",
                padding: "12px 32px",
                fontWeight: 700,
                fontSize: "var(--font-sm)",
                border: "none",
                cursor: "pointer",
                boxShadow: "0 10px 26px -10px rgba(37,99,235,0.55)",
                transition: "transform 200ms var(--ease), box-shadow 200ms",
                textDecoration: "none",
                display: "inline-flex",
                alignItems: "center",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "scale(1.05)";
                e.currentTarget.style.boxShadow =
                  "0 16px 36px -10px rgba(37,99,235,0.7)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "scale(1)";
                e.currentTarget.style.boxShadow =
                  "0 10px 26px -10px rgba(37,99,235,0.55)";
              }}
            >
              ابدأ مجانًا
            </Link>
            <a
              href="#how"
              style={{
                color: "var(--c-text-3)",
                fontSize: "var(--font-sm)",
                fontWeight: 700,
                transition: "color 200ms",
                textDecoration: "none",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.color = "var(--c-primary)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.color = "var(--c-text-3)")
              }
            >
              كيف يعمل؟
            </a>
          </div>
        </div>

        {/* Bouncing arrow */}
        <div
          style={{
            position: "absolute",
            bottom: "var(--s-8)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "var(--s-2)",
            zIndex: 2,
            opacity: heroVisible ? 1 : 0,
            transition: "opacity 1200ms var(--ease) 400ms",
          }}
        >
          <span
            style={{
              fontSize: 12,
              color: "var(--c-text-3)",
            }}
          >
            اكتشف المزيد
          </span>
          <span
            style={{
              fontSize: 20,
              color: "var(--c-text-3)",
              animation: "rq-bounce-arrow 2s ease-in-out infinite",
            }}
          >
            ↓
          </span>
        </div>
      </section>

      {/* ═══ 3 · LARGE STATEMENT ═══ */}
      <Reveal>
        <section style={sectionPadLarge}>
          <div
            className="rq-container"
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-start",
            }}
          >
            <div style={tintDot()} />
            <span
              style={{
                fontSize: 14,
                fontWeight: 700,
                color: "var(--c-text-3)",
                letterSpacing: "0.02em",
                marginBottom: "var(--s-4)",
              }}
            >
              المرحلة الأولى
            </span>
            <h2
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "clamp(2.25rem, 5vw, 3.75rem)",
                fontWeight: 500,
                letterSpacing: "-0.05em",
                lineHeight: 1.2,
                margin: 0,
                marginBottom: "var(--s-6)",
              }}
            >
              الصفحة تعرف كيف تتكلم.
            </h2>
            <p
              style={{
                fontSize: "clamp(1rem, 2vw, 1.125rem)",
                lineHeight: 1.85,
                color: "var(--c-text-2)",
                maxWidth: "40ch",
                marginInlineStart: "auto",
              }}
            >
              رقيب يفهم لهجة عميلك ونيته ويُشير ردًا بأسلوب صفحتك — من
              اللهجة المصرية للخليجية.
            </p>
          </div>
        </section>
      </Reveal>

      {/* ═══ 4 · WORKFLOW TIMELINE ═══ */}
      <section
        id="how"
        style={{
          ...sectionPadLarge,
          position: "relative",
        }}
      >
        <Reveal>
          <div className="rq-container">
            <div style={{ ...tintDot(), marginInlineStart: "auto" }} />
            <span
              style={{
                fontSize: 14,
                fontWeight: 700,
                color: "var(--c-text-3)",
                letterSpacing: "0.02em",
                marginBottom: "var(--s-4)",
                display: "block",
                textAlign: "center",
              }}
            >
              كيف يعمل
            </span>
            <h2
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "clamp(2.25rem, 5vw, 3.75rem)",
                fontWeight: 500,
                letterSpacing: "-0.05em",
                lineHeight: 1.2,
                margin: 0,
                textAlign: "center",
                marginBottom: "var(--s-16)",
              }}
            >
              من الاتصال إلى الذكاء
            </h2>
          </div>
        </Reveal>

        {/* Desktop: two-column */}
        <div
          className="rq-container"
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "var(--s-12)",
            alignItems: "flex-start",
            position: "relative",
          }}
        >
          {/* Left: steps */}
          <div
            style={{
              position: "sticky",
              top: 128,
              display: "flex",
              flexDirection: "column",
              gap: 0,
              position: "relative",
            }}
          >
            {/* Vertical line */}
            <div
              style={{
                position: "absolute",
                top: 0,
                bottom: 0,
                right: 19,
                width: 3,
                background: "var(--c-border)",
                borderRadius: 2,
                zIndex: 0,
              }}
            />
            {steps.map((step, i) => {
              const isActive = activeStep === i;
              return (
                <div
                  key={step.idx}
                  ref={stepRef(i)}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "var(--s-4)",
                    padding: "var(--s-5) 0",
                    position: "relative",
                    zIndex: 1,
                  }}
                >
                  {/* Step number circle */}
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: "50%",
                      background: isActive
                        ? "var(--c-primary)"
                        : "var(--c-surface-2)",
                      border: `2px solid ${
                        isActive
                          ? "var(--c-primary)"
                          : "var(--c-border-strong)"
                      }`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 12,
                      fontWeight: 800,
                      color: isActive ? "#fff" : "var(--c-text-3)",
                      flexShrink: 0,
                      transition:
                        "background 300ms var(--ease), border-color 300ms, color 300ms",
                    }}
                  >
                    {step.idx}
                  </div>
                  <div
                    style={{
                      paddingTop: 4,
                      transition: "opacity 300ms",
                      opacity: isActive ? 1 : 0.5,
                    }}
                  >
                    <div
                      style={{
                        fontFamily: "var(--font-display)",
                        fontSize: "1.25rem",
                        fontWeight: 700,
                        color: isActive
                          ? "var(--c-primary)"
                          : "var(--c-text-2)",
                        marginBottom: 4,
                        transition: "color 300ms",
                      }}
                    >
                      {step.name}
                    </div>
                    <div
                      style={{
                        fontSize: "var(--font-sm)",
                        color: "var(--c-text-3)",
                        maxHeight: isActive ? 60 : 0,
                        overflow: "hidden",
                        transition: "max-height 400ms var(--ease)",
                      }}
                    >
                      {step.desc}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Right: visual for active step */}
          <div
            style={{
              position: "sticky",
              top: 128,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              minHeight: 400,
            }}
          >
            <div
              style={{
                ...glassCard,
                width: "100%",
                maxWidth: 460,
                padding: "var(--s-8)",
                display: "flex",
                flexDirection: "column",
                gap: "var(--s-4)",
              }}
            >
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: "var(--radius-md)",
                  background: "var(--c-primary-dim)",
                  border: "1px solid rgba(37,99,235,0.3)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 20,
                }}
              >
                {["🔗", "📥", "🧠", "💡", "💬", "🚀"][activeStep]}
              </div>
              <h3
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: "1.5rem",
                  fontWeight: 700,
                  margin: 0,
                  color: "var(--c-text)",
                }}
              >
                {steps[activeStep].name}
              </h3>
              <p
                style={{
                  fontSize: "var(--font-sm)",
                  color: "var(--c-text-2)",
                  lineHeight: 1.85,
                  margin: 0,
                }}
              >
                {steps[activeStep].desc}
              </p>
              <div
                style={{
                  marginTop: "var(--s-4)",
                  background: "var(--c-surface-2)",
                  borderRadius: "var(--radius-md)",
                  padding: "var(--s-4)",
                  fontSize: "var(--font-sm)",
                  color: "var(--c-text-3)",
                  lineHeight: 1.8,
                }}
              >
                {activeStep === 0 && "اتصل بصفحتك بضغطة واحدة — OAuth آمن بدون كلمات مرور."}
                {activeStep === 1 && "يجلب المحادثات الأخيرة ويرتبها حسب الأولوية والنشاط."}
                {activeStep === 2 && "يفهم كل لهجة عربية — مصري وسعودي وشامي وخليجي."}
                {activeStep === 3 && "يتعلّم من ردودك ويحفظ سياق كل عميل ومحادثة."}
                {activeStep === 4 && "يقترح ردود جاهزة بأسلوب صفحتك، جاهزة للمراجعة."}
                {activeStep === 5 && "كل رد تعتمده يجعل النظام أذكى — تعلّم مستمر."}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ 5 · FEATURE BENTO GRID ═══ */}
      <section id="features" style={sectionPadLarge}>
        <Reveal>
          <div className="rq-container">
            <div style={tintDot()} />
            <h2
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "clamp(2.25rem, 5vw, 3.75rem)",
                fontWeight: 500,
                letterSpacing: "-0.05em",
                lineHeight: 1.2,
                margin: 0,
                marginBottom: "var(--s-12)",
              }}
            >
              لماذا رقيب؟
            </h2>
          </div>
        </Reveal>

        <div
          className="rq-container"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(8, 1fr)",
            gap: "var(--s-4)",
          }}
        >
          {/* Card 1: فهم الهجات (span 4) */}
          <Reveal delay={0} style={{ gridColumn: "span 4" }}>
            <div
              style={{
                ...glassCard,
                padding: "var(--s-6)",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                transition: "border-color 300ms",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.borderColor =
                  "rgba(245,245,244,0.15)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.borderColor =
                  "rgba(245,245,244,0.08)")
              }
            >
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--c-primary)",
                  letterSpacing: "0.04em",
                  marginBottom: "var(--s-3)",
                }}
              >
                فهم الهجات
              </span>
              <h3
                style={{
                  fontSize: "1.25rem",
                  fontWeight: 700,
                  margin: 0,
                  marginBottom: "var(--s-2)",
                  color: "var(--c-text)",
                }}
              >
                اللهجة العربية بألوانها
              </h3>
              <p
                style={{
                  fontSize: 14,
                  color: "var(--c-text-3)",
                  lineHeight: 1.8,
                  margin: 0,
                  marginBottom: "var(--s-4)",
                }}
              >
                يفهم الفروق الدقيقة بين اللهجات ويرد بطريقة مناسبة.
              </p>
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--s-3)",
                  flexWrap: "wrap",
                }}
              >
                {["مصري", "سعودي", "شامي", "خليجي", "مغربي"].map(
                  (d) => (
                    <span
                      key={d}
                      className="rq-badge rq-badge-neutral"
                      style={{ fontSize: 12 }}
                    >
                      {d}
                    </span>
                  ),
                )}
              </div>
            </div>
          </Reveal>

          {/* Card 2: الذاكرة (span 4) */}
          <Reveal delay={100} style={{ gridColumn: "span 4" }}>
            <div
              style={{
                ...glassCard,
                padding: "var(--s-6)",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                transition: "border-color 300ms",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.borderColor =
                  "rgba(245,245,244,0.15)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.borderColor =
                  "rgba(245,245,244,0.08)")
              }
            >
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--c-primary)",
                  letterSpacing: "0.04em",
                  marginBottom: "var(--s-3)",
                }}
              >
                الذاكرة
              </span>
              <h3
                style={{
                  fontSize: "1.25rem",
                  fontWeight: 700,
                  margin: 0,
                  marginBottom: "var(--s-2)",
                  color: "var(--c-text)",
                }}
              >
                يتذكر كل حوار
              </h3>
              <p
                style={{
                  fontSize: 14,
                  color: "var(--c-text-3)",
                  lineHeight: 1.8,
                  margin: 0,
                  marginBottom: "var(--s-4)",
                }}
              >
                يحفظ سياق المحادثات السابقة ويربطها بالمحادثة الحالية.
              </p>
              <div
                style={{
                  flex: 1,
                  background: "var(--c-surface-2)",
                  borderRadius: "var(--radius-md)",
                  padding: "var(--s-4)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--s-2)",
                }}
              >
                {[
                  { sim: "92%", text: "سعر الشنطة كام؟" },
                  { sim: "89%", text: "عايزة أعرف لو في خصم" },
                  { sim: "86%", text: "الشنطة مقاسها كام؟" },
                ].map((item) => (
                  <div
                    key={item.sim}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      fontSize: 12,
                    }}
                  >
                    <span style={{ color: "var(--c-text-3)" }}>
                      {item.text}
                    </span>
                    <span className="rq-badge rq-badge-brand">
                      {item.sim}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>

          {/* Card 3: التدريب (span 3) */}
          <Reveal delay={200} style={{ gridColumn: "span 3" }}>
            <div
              style={{
                ...glassCard,
                padding: "var(--s-6)",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                transition: "border-color 300ms",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.borderColor =
                  "rgba(245,245,244,0.15)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.borderColor =
                  "rgba(245,245,244,0.08)")
              }
            >
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--c-primary)",
                  letterSpacing: "0.04em",
                  marginBottom: "var(--s-3)",
                }}
              >
                التدريب
              </span>
              <h3
                style={{
                  fontSize: "1.25rem",
                  fontWeight: 700,
                  margin: 0,
                  marginBottom: "var(--s-2)",
                  color: "var(--c-text)",
                }}
              >
                خط أنابيب التعلّم
              </h3>
              <p
                style={{
                  fontSize: 14,
                  color: "var(--c-text-3)",
                  lineHeight: 1.8,
                  margin: 0,
                  marginBottom: "var(--s-4)",
                }}
              >
                بياناتك تُستخدم لتدريب نموذج خاص بصفحتك فقط.
              </p>
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--s-2)",
                  justifyContent: "center",
                }}
              >
                {["خام", "مُحلَّل", "ذاكرة", "تقييم"].map(
                  (stage, i, arr) => (
                    <div
                      key={stage}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "var(--s-2)",
                      }}
                    >
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 800,
                          color: "var(--c-primary)",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {stage}
                      </span>
                      {i < arr.length - 1 && (
                        <span
                          style={{
                            color: "var(--c-text-3)",
                            fontSize: 10,
                          }}
                        >
                          →
                        </span>
                      )}
                    </div>
                  ),
                )}
              </div>
            </div>
          </Reveal>

          {/* Card 4: الردود الذكية (span 5) */}
          <Reveal delay={300} style={{ gridColumn: "span 5" }}>
            <div
              style={{
                ...glassCard,
                padding: "var(--s-6)",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                transition: "border-color 300ms",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.borderColor =
                  "rgba(245,245,244,0.15)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.borderColor =
                  "rgba(245,245,244,0.08)")
              }
            >
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--c-primary)",
                  letterSpacing: "0.04em",
                  marginBottom: "var(--s-3)",
                }}
              >
                الردود الذكية
              </span>
              <h3
                style={{
                  fontSize: "1.25rem",
                  fontWeight: 700,
                  margin: 0,
                  marginBottom: "var(--s-2)",
                  color: "var(--c-text)",
                }}
              >
                ردود بأسلوب صفحتك
              </h3>
              <p
                style={{
                  fontSize: 14,
                  color: "var(--c-text-3)",
                  lineHeight: 1.8,
                  margin: 0,
                  marginBottom: "var(--s-4)",
                }}
              >
                اقتراحات ذكية جاهزة للمراجعة والإرسال.
              </p>
              <div
                style={{
                  flex: 1,
                  background: "var(--c-surface-2)",
                  borderRadius: "var(--radius-md)",
                  padding: "var(--s-4)",
                }}
              >
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 800,
                    color: "var(--c-text-3)",
                    marginBottom: "var(--s-2)",
                    letterSpacing: "0.04em",
                  }}
                >
                  اقتراح رقيب
                </div>
                <div
                  style={{
                    fontSize: "var(--font-sm)",
                    lineHeight: 1.85,
                    color: "var(--c-text-2)",
                  }}
                >
                  أهلاً بحضرتك 🌟 سعر الشنطة 850 جنيه والشحن مجاني لكل
                  المحافظات. تحب أأكدلك المقاس؟
                </div>
              </div>
            </div>
          </Reveal>

          {/* Card 5: المراجعة البشرية (span 5) */}
          <Reveal delay={400} style={{ gridColumn: "span 5" }}>
            <div
              style={{
                ...glassCard,
                padding: "var(--s-6)",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                transition: "border-color 300ms",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.borderColor =
                  "rgba(245,245,244,0.15)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.borderColor =
                  "rgba(245,245,244,0.08)")
              }
            >
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--c-primary)",
                  letterSpacing: "0.04em",
                  marginBottom: "var(--s-3)",
                }}
              >
                المراجعة البشرية
              </span>
              <h3
                style={{
                  fontSize: "1.25rem",
                  fontWeight: 700,
                  margin: 0,
                  marginBottom: "var(--s-2)",
                  color: "var(--c-text)",
                }}
              >
                أنت تقرّر
              </h3>
              <p
                style={{
                  fontSize: 14,
                  color: "var(--c-text-3)",
                  lineHeight: 1.8,
                  margin: 0,
                  marginBottom: "var(--s-4)",
                }}
              >
                رقيب يقترح، أنت تعتمد أو تعدّل — التعلّم من مراجعتك.
              </p>
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--s-3)",
                  justifyContent: "center",
                }}
              >
                {[
                  { label: "اعتماد", cls: "rq-badge-success" },
                  { label: "تعديل", cls: "rq-badge-warn" },
                  { label: "رفض", cls: "rq-badge-danger" },
                ].map((b) => (
                  <span
                    key={b.label}
                    className={`rq-badge ${b.cls}`}
                    style={{ fontSize: 13, padding: "6px 16px" }}
                  >
                    {b.label}
                  </span>
                ))}
              </div>
            </div>
          </Reveal>

          {/* Card 6: الأمان (span 3) */}
          <Reveal delay={500} style={{ gridColumn: "span 3" }}>
            <div
              style={{
                ...glassCard,
                padding: "var(--s-6)",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                transition: "border-color 300ms",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.borderColor =
                  "rgba(245,245,244,0.15)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.borderColor =
                  "rgba(245,245,244,0.08)")
              }
            >
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--c-primary)",
                  letterSpacing: "0.04em",
                  marginBottom: "var(--s-3)",
                }}
              >
                الأمان
              </span>
              <h3
                style={{
                  fontSize: "1.25rem",
                  fontWeight: 700,
                  margin: 0,
                  marginBottom: "var(--s-2)",
                  color: "var(--c-text)",
                }}
              >
                بياناتك آمنة
              </h3>
              <p
                style={{
                  fontSize: 14,
                  color: "var(--c-text-3)",
                  lineHeight: 1.8,
                  margin: 0,
                  marginBottom: "var(--s-4)",
                }}
              >
                تشفير كامل، بيانات معزولة، لا مشاركة مع أطراف ثالثة.
              </p>
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 48,
                }}
              >
                🛡️
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ═══ 6 · ARABIC INTELLIGENCE ═══ */}
      <section style={sectionPadLarge}>
        <Reveal>
          <div className="rq-container">
            <div style={tintDot()} />
            <h2
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "clamp(2.25rem, 5vw, 3.75rem)",
                fontWeight: 500,
                letterSpacing: "-0.05em",
                lineHeight: 1.2,
                margin: 0,
                marginBottom: "var(--s-16)",
              }}
            >
              لغة حقيقية
            </h2>
          </div>
        </Reveal>

        <div
          className="rq-container"
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "var(--s-10)",
            padding: "var(--s-8) 0",
          }}
        >
          {/* Egyptian */}
          <Reveal delay={0}>
            <div style={{ textAlign: "center" }}>
              <p
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: "clamp(2rem, 4vw, 3.5rem)",
                  fontWeight: 700,
                  lineHeight: 1.3,
                  margin: 0,
                }}
              >
                بكام يا باشا؟
              </p>
              <span
                className="rq-badge rq-badge-brand"
                style={{ marginTop: "var(--s-2)", fontSize: 12 }}
              >
                مصري
              </span>
            </div>
          </Reveal>

          {/* Saudi */}
          <Reveal delay={150}>
            <div style={{ textAlign: "center" }}>
              <p
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: "clamp(1.75rem, 3.5vw, 3rem)",
                  fontWeight: 700,
                  lineHeight: 1.3,
                  margin: 0,
                  color: "var(--c-text-2)",
                }}
              >
                وش سعره؟
              </p>
              <span
                className="rq-badge rq-badge-neutral"
                style={{ marginTop: "var(--s-2)", fontSize: 12 }}
              >
                سعودي
              </span>
            </div>
          </Reveal>

          {/* MSA */}
          <Reveal delay={300}>
            <div style={{ textAlign: "center" }}>
              <p
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: "clamp(1.5rem, 3vw, 2.5rem)",
                  fontWeight: 400,
                  lineHeight: 1.3,
                  margin: 0,
                  color: "var(--c-text-3)",
                }}
              >
                عايز أعرف السعر
              </p>
              <span
                className="rq-badge rq-badge-neutral"
                style={{ marginTop: "var(--s-2)", fontSize: 12 }}
              >
                فصحى
              </span>
            </div>
          </Reveal>

          {/* Arabizi */}
          <Reveal delay={450}>
            <div style={{ textAlign: "center" }}>
              <p
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "clamp(1.25rem, 2.5vw, 2rem)",
                  fontWeight: 700,
                  lineHeight: 1.3,
                  margin: 0,
                  color: "var(--c-text-3)",
                  opacity: 0.6,
                  direction: "ltr",
                }}
              >
                bkam da?
              </p>
              <span
                className="rq-badge rq-badge-neutral"
                style={{ marginTop: "var(--s-2)", fontSize: 12 }}
              >
                عربيزي
              </span>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ═══ 7 · PRODUCT PREVIEW ═══ */}
      <Reveal>
        <section
          style={{
            padding: "var(--s-16) var(--s-6)",
            overflow: "hidden",
          }}
        >
          <div
            className="rq-container"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                background:
                  "linear-gradient(180deg, rgba(255,255,255,0.02), transparent), var(--c-surface-1)",
                border: "1px solid var(--c-border-strong)",
                borderRadius: "var(--radius-xl)",
                overflow: "hidden",
                boxShadow: "0 40px 90px -30px rgba(0,0,0,0.9)",
                transform: "scale(0.95)",
                perspective: 1200,
                width: "100%",
                maxWidth: 1100,
              }}
            >
              {/* Window dots */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--s-2)",
                  padding: "var(--s-4) var(--s-5)",
                  borderBottom: "1px solid var(--c-border)",
                }}
              >
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    background: "var(--c-error)",
                    opacity: 0.8,
                  }}
                />
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    background: "var(--c-warn)",
                    opacity: 0.8,
                  }}
                />
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    background: "var(--c-success)",
                    opacity: 0.8,
                  }}
                />
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "280px 1fr",
                }}
              >
                {/* Conversation list */}
                <div
                  style={{
                    borderInlineEnd: "1px solid var(--c-border)",
                    padding: "var(--s-5)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "var(--s-3)",
                    background: "var(--c-surface-0)",
                  }}
                >
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 800,
                      color: "var(--c-text-3)",
                      letterSpacing: "0.04em",
                      textTransform: "uppercase" as const,
                      marginBottom: "var(--s-2)",
                    }}
                  >
                    المحادثات
                  </div>
                  {[
                    {
                      name: "سارة أحمد",
                      msg: "عايزة أعرف سعر الشنطة",
                      active: true,
                    },
                    {
                      name: "محمد علي",
                      msg: "هل فيه شحن للسعودية؟",
                      active: false,
                    },
                    {
                      name: "نورة حسن",
                      msg: "ممكن أشوف صور المنتج؟",
                      active: false,
                    },
                  ].map((conv) => (
                    <div
                      key={conv.name}
                      style={{
                        padding: "var(--s-3)",
                        borderRadius: "var(--radius-sm)",
                        background: conv.active
                          ? "var(--c-primary-dim)"
                          : "transparent",
                        border: conv.active
                          ? "1px solid rgba(37,99,235,0.3)"
                          : "1px solid transparent",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "var(--font-sm)",
                          fontWeight: 800,
                          marginBottom: 2,
                        }}
                      >
                        {conv.name}
                      </div>
                      <div
                        style={{
                          fontSize: "var(--font-xs)",
                          color: "var(--c-text-3)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {conv.msg}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Conversation detail */}
                <div
                  style={{
                    padding: "var(--s-6)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "var(--s-4)",
                  }}
                >
                  <div
                    style={{
                      borderBottom: "1px solid var(--c-border)",
                      paddingBottom: "var(--s-4)",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "var(--font-base)",
                        fontWeight: 800,
                      }}
                    >
                      سارة أحمد
                    </div>
                    <div
                      style={{
                        fontSize: "var(--font-xs)",
                        color: "var(--c-text-3)",
                      }}
                    >
                      عميلة · القاهرة · اللهجة: مصري
                    </div>
                  </div>

                  <div
                    style={{
                      maxWidth: "75%",
                      alignSelf: "flex-start",
                      background: "var(--c-surface-2)",
                      border: "1px solid var(--c-border)",
                      borderRadius: "var(--radius-lg)",
                      borderRadiusEndEnd: "4px",
                      padding: "var(--s-4)",
                      fontSize: "var(--font-sm)",
                      lineHeight: 1.85,
                    }}
                  >
                    عايزة أعرف سعر الشنطة الجلد دي
                  </div>

                  <div
                    style={{
                      maxWidth: "75%",
                      alignSelf: "flex-end",
                      background:
                        "linear-gradient(135deg, rgba(37,99,235,0.18), rgba(37,99,235,0.06))",
                      border: "1px solid rgba(37,99,235,0.35)",
                      borderRadius: "var(--radius-lg)",
                      borderRadiusStartStart: "4px",
                      padding: "var(--s-4)",
                      fontSize: "var(--font-sm)",
                      lineHeight: 1.85,
                      color: "#cbdbea",
                    }}
                  >
                    أهلاً بحضرتك 🌟 سعر الشنطة 850 جنيه والشحن مجاني.
                  </div>

                  <div
                    style={{
                      ...glassCard,
                      borderRadius: "var(--radius-md)",
                      padding: "var(--s-4)",
                      maxWidth: "70%",
                      alignSelf: "flex-end",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "var(--s-2)",
                        marginBottom: "var(--s-2)",
                      }}
                    >
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 800,
                          color: "var(--c-primary)",
                        }}
                      >
                        ✦ اقتراح رقيب
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: "var(--font-sm)",
                        lineHeight: 1.8,
                        color: "var(--c-text-2)",
                      }}
                    >
                      تحب أأددلك المقاس؟ عندنا S, M, L
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </Reveal>

      {/* ═══ 8 · FINAL CTA ═══ */}
      <Reveal>
        <section
          style={{
            ...sectionPadLarge,
            textAlign: "center",
          }}
        >
          <div
            className="rq-container"
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              maxWidth: "30ch",
              marginInline: "auto",
            }}
          >
            <h2
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "clamp(2.25rem, 5vw, 3.75rem)",
                fontWeight: 500,
                letterSpacing: "-0.05em",
                lineHeight: 1.2,
                margin: 0,
                marginBottom: "var(--s-4)",
              }}
            >
              ابدأ الآن
            </h2>
            <p
              style={{
                fontSize: "clamp(1rem, 2vw, 1.125rem)",
                lineHeight: 1.85,
                color: "var(--c-text-2)",
                margin: 0,
                marginBottom: "var(--s-8)",
              }}
            >
              أنشئ حسابك واربط صفحتك في دقائق.
            </p>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "var(--s-4)",
              }}
            >
              <Link
                to="/auth?mode=register&returnTo=/app"
                style={{
                  background:
                    "linear-gradient(135deg, rgba(37,99,235,0.8), var(--c-primary))",
                  color: "#fff",
                  borderRadius: "var(--radius-full)",
                  padding: "12px 32px",
                  fontWeight: 700,
                  fontSize: "var(--font-sm)",
                  border: "none",
                  cursor: "pointer",
                  boxShadow: "0 10px 26px -10px rgba(37,99,235,0.55)",
                  transition:
                    "transform 200ms var(--ease), box-shadow 200ms",
                  textDecoration: "none",
                  display: "inline-flex",
                  alignItems: "center",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = "scale(1.05)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "scale(1)";
                }}
              >
                ابدأ مجانًا
              </Link>
              <a
                href="#how"
                style={{
                  color: "var(--c-text-3)",
                  fontSize: "var(--font-sm)",
                  fontWeight: 700,
                  transition: "color 200ms",
                  textDecoration: "none",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.color = "var(--c-primary)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.color = "var(--c-text-3)")
                }
              >
                أو تعرّف على المزيد
              </a>
            </div>
          </div>
        </section>
      </Reveal>

      {/* ═══ 9 · FOOTER ═══ */}
      <footer
        style={{
          height: 64,
          display: "flex",
          alignItems: "center",
          borderTop: "1px solid rgba(245,245,244,0.08)",
          padding: "0 var(--s-6)",
        }}
      >
        <div
          className="rq-container"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
            padding: "0 var(--s-6)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--s-2)",
            }}
          >
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: "var(--radius-xs)",
                background:
                  "linear-gradient(140deg, #3b82f6, #1d4ed8)",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: "var(--font-display)",
                fontWeight: 700,
                fontSize: "0.875rem",
                flexShrink: 0,
              }}
            >
              ر
            </div>
            <span
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 700,
                fontSize: "var(--font-sm)",
                color: "var(--c-text)",
              }}
            >
              رقيب
            </span>
          </div>

          <span
            style={{
              fontSize: "var(--font-xs)",
              color: "var(--c-text-3)",
            }}
          >
            © {new Date().getFullYear()} رقيب
          </span>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--s-4)",
              fontSize: "var(--font-xs)",
            }}
          >
            <a
              href="#features"
              style={{
                color: "var(--c-text-3)",
                fontWeight: 700,
                textDecoration: "none",
              }}
            >
              المميزات
            </a>
            <a
              href="#privacy"
              style={{
                color: "var(--c-text-3)",
                fontWeight: 700,
                textDecoration: "none",
              }}
            >
              الخصوصية
            </a>
            <a
              href="#"
              style={{
                color: "var(--c-text-3)",
                fontWeight: 700,
                textDecoration: "none",
              }}
            >
              التوثيق
            </a>
          </div>
        </div>
      </footer>

      {/* ═══ KEYFRAMES ═══ */}
      <style>{`
        @keyframes rq-hero-drift-1 {
          0% { transform: translate(0, 0) scale(1); }
          100% { transform: translate(60px, 40px) scale(1.15); }
        }
        @keyframes rq-hero-drift-2 {
          0% { transform: translate(0, 0) scale(1); }
          100% { transform: translate(-50px, -30px) scale(1.1); }
        }
        @keyframes rq-hero-drift-3 {
          0% { transform: translate(0, 0) scale(1); }
          100% { transform: translate(40px, -50px) scale(1.2); }
        }
        @keyframes rq-particle-float {
          0% { transform: translateY(0); opacity: 0.15; }
          100% { transform: translateY(-20px); opacity: 0.35; }
        }
        @keyframes rq-bounce-arrow {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(8px); }
        }
        @media (max-width: 768px) {
          .rq-landing [style*="grid-template-columns: repeat(8"] {
            grid-template-columns: 1fr !important;
          }
          .rq-landing [style*="grid-template-columns: 1fr 1fr"] {
            grid-template-columns: 1fr !important;
          }
          .rq-landing [style*="grid-template-columns: 280px 1fr"] {
            grid-template-columns: 1fr !important;
          }
          .rq-landing [style*="grid-column: span 4"],
          .rq-landing [style*="grid-column: span 5"],
          .rq-landing [style*="grid-column: span 3"] {
            grid-column: span 1 !important;
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .rq-landing * {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
          }
        }
      `}</style>
    </div>
  );
}
