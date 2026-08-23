/* Raqib landing — original interactions */
(function () {
  'use strict';

  /* ── Navbar shadow on scroll ── */
  const nav = document.getElementById('navbar');
  addEventListener('scroll', () => nav.classList.toggle('scrolled', scrollY > 10), { passive: true });

  /* ── Mobile burger ── */
  const burger = document.getElementById('burger');
  if (burger) {
    burger.addEventListener('click', () => {
      const links = document.querySelector('.nav-links');
      const open = links.style.display === 'flex';
      links.style.display = open ? '' : 'flex';
      if (!open) {
        Object.assign(links.style, { position: 'fixed', inset: '68px 0 auto 0', background: '#FFFBF5', flexDirection: 'column', padding: '24px', borderBottom: '2px solid #151515' });
      }
    });
  }

  /* ── Scroll reveal ── */
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
  }, { threshold: 0.12 });
  document.querySelectorAll('.reveal').forEach((el) => io.observe(el));

  /* ── Animated counters ── */
  const cio = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      const b = e.target;
      const target = parseInt(b.dataset.count || '0', 10);
      const prefix = b.dataset.prefix || '';
      const suffix = b.dataset.suffix || '';
      const dur = 1200; const t0 = performance.now();
      (function tick(t) {
        const p = Math.min((t - t0) / dur, 1);
        b.textContent = prefix + Math.round(target * (1 - Math.pow(1 - p, 3))) + (p === 1 && target !== 24 ? '' : '');
        if (p < 1) requestAnimationFrame(tick);
        else b.textContent = target === 0 ? '$0' : (suffix === '<3s' ? '<3s' : target + (target === 24 ? '/7' : ''));
      })(t0);
      cio.unobserve(b);
    });
  }, { threshold: 0.6 });
  document.querySelectorAll('[data-count]').forEach((el) => cio.observe(el));

  /* ── Live chat demo loop ── */
  const body = document.getElementById('chatBody');
  if (!body) return;

  const script = [
    { type: 'cust', text: 'عندك مقاس 42 كوتشي أبيض؟ 👟' },
    { type: 'typing', who: 'ai', delay: 1100 },
    { type: 'ai', text: 'أهلاً بيكي 🙌 أيوه متوفر مقاس 42 أبيض بـ <b>850 ج.م</b>، وفيه كمان أسود لو حابة ✨' },
    { type: 'voice', delay: 900 },                       // customer sends voice note
    { type: 'note', text: '🎤 جاري التفريغ محليًا… faster-whisper' },
    { type: 'typing', who: 'ai', delay: 1300 },
    { type: 'ai', text: 'سمعتك واضحة يا فندم 👌 عنوانك فين عشان أحسبلك الشحن؟' },
    { type: 'cust', text: 'المعادي' },
    { type: 'typing', who: 'ai', delay: 1000 },
    { type: 'ai', text: 'تمام! الشحن للقاهرة <b>35 ج.م</b> — يبقى الإجمالي <b>885 ج.م</b> كاش عند الاستلام 💚 ابعتيلي اسمك ورقم تليفونك وأأكد الطلب فورًا.' },
    { type: 'note', text: '✅ تم إنشاء الطلب ORD-260823-114 · إيميل لصاحب الصفحة' },
  ];

  function el(html) { const d = document.createElement('div'); d.innerHTML = html.trim(); return d.firstChild; }
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  async function play() {
    body.innerHTML = '';
    for (const step of script) {
      if (step.type === 'typing') {
        await sleep(500);
        const t = el('<div class="msg ai typing"><i></i><i></i><i></i></div>');
        body.appendChild(t); body.scrollTop = body.scrollHeight;
        await sleep(step.delay || 1000);
        t.remove();
      } else if (step.type === 'voice') {
        await sleep(step.delay || 700);
        body.appendChild(el(
          '<div class="voice-chip"><span style="font-size:18px">🎤</span>' +
          '<span class="bars">' + Array.from({ length: 9 }, (_, i) =>
            `<i style="animation-delay:${i * 90}ms"></i>`).join('') +
          '</span><span>0:04</span></div>'
        ));
        body.scrollTop = body.scrollHeight;
      } else if (step.type === 'note') {
        await sleep(step.delay || 600);
        body.appendChild(el(`<div class="msg note">${step.text}</div>`));
        body.scrollTop = body.scrollHeight;
      } else {
        await sleep(step.delay || 850);
        body.appendChild(el(`<div class="msg ${step.type}">${step.text}</div>`));
        body.scrollTop = body.scrollHeight;
      }
    }
    await sleep(5200);   // hold finished conversation
    play();              // loop forever
  }
  play();

  /* ── FAQ: close others when one opens ── */
  document.querySelectorAll('details.faq').forEach((d) => {
    d.addEventListener('toggle', () => {
      if (d.open) document.querySelectorAll('details.faq[open]').forEach((o) => { if (o !== d) o.open = false; });
    });
  });
})();
