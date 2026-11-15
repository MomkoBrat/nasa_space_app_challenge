/* =========================================================================
   New Horizon — mission briefing deck
   Click / → / Space / PageDown : next      ← / PageUp / Backspace : back
   F : fullscreen      H : hide HUD (for clean recordings)      Home / End
   Every click reveals the next group of elements marked data-step="n",
   each with its own entrance (data-anim). Slides enter with their own
   transition (data-transition) while the starfield jumps to warp speed.
   ========================================================================= */

// ---- Edit these two lines if needed ---------------------------------------
const CONFIG = {
  TEAM_NAME: 'New Neighbours',
  // The exact Space Apps challenge title can be put here; it replaces the text on slide 3.
  CHALLENGE: '',
};
// ---------------------------------------------------------------------------

(() => {
  // ------------------------------------------------------------- config text
  document.querySelectorAll('[data-config]').forEach((el) => {
    const v = CONFIG[el.dataset.config];
    if (v) el.textContent = v;
  });

  // ------------------------------------------------------------- stage scale
  const stage = document.getElementById('stage');
  function fit() {
    const s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    stage.style.transform = `scale(${s})`;
  }
  window.addEventListener('resize', fit);
  fit();

  // --------------------------------------------------------------- starfield
  const canvas = document.getElementById('stars');
  const ctx = canvas.getContext('2d');
  let W = 0, H = 0, stars = [], speed = 0.6, targetSpeed = 0.6, shooting = [];
  function resize() {
    W = canvas.width = window.innerWidth * devicePixelRatio;
    H = canvas.height = window.innerHeight * devicePixelRatio;
  }
  window.addEventListener('resize', resize);
  resize();
  for (let i = 0; i < 900; i++) stars.push(newStar(true));
  function newStar(any) {
    return { x: (Math.random() - .5) * 2, y: (Math.random() - .5) * 2, z: any ? Math.random() : 1, hue: Math.random() < .12 ? 20 : (Math.random() < .1 ? 200 : 0) };
  }
  let warp = function (power = 38) { targetSpeed = power; setTimeout(() => (targetSpeed = 0.6), 420); };
  function frame() {
    speed += (targetSpeed - speed) * 0.08;
    ctx.fillStyle = speed > 3 ? 'rgba(4,3,10,0.35)' : 'rgba(4,3,10,0.9)';
    ctx.fillRect(0, 0, W, H);
    const cx = W / 2, cy = H / 2, f = Math.min(W, H) * .9;
    for (const s of stars) {
      const pz = s.z;
      s.z -= 0.0009 * speed;
      if (s.z <= 0.02) Object.assign(s, newStar(false));
      const sx = cx + (s.x / s.z) * f * .5, sy = cy + (s.y / s.z) * f * .5;
      const px = cx + (s.x / pz) * f * .5, py = cy + (s.y / pz) * f * .5;
      if (sx < 0 || sx > W || sy < 0 || sy > H) { Object.assign(s, newStar(false)); continue; }
      const a = Math.min(1, (1 - s.z) * 1.4);
      const r = Math.max(.4, (1 - s.z) * 2.2) * devicePixelRatio;
      const col = s.hue === 20 ? `rgba(255,176,138,${a})` : s.hue === 200 ? `rgba(150,220,255,${a})` : `rgba(255,255,255,${a})`;
      if (speed > 2) {
        ctx.strokeStyle = col; ctx.lineWidth = r; ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(sx, sy); ctx.stroke();
      } else {
        ctx.fillStyle = col; ctx.beginPath(); ctx.arc(sx, sy, r, 0, Math.PI * 2); ctx.fill();
      }
    }
    // occasional shooting star
    if (Math.random() < 0.004) shooting.push({ x: Math.random() * W, y: Math.random() * H * .5, vx: -(6 + Math.random() * 6) * devicePixelRatio, vy: (3 + Math.random() * 3) * devicePixelRatio, life: 1 });
    shooting = shooting.filter((m) => m.life > 0);
    for (const m of shooting) {
      const g = ctx.createLinearGradient(m.x, m.y, m.x - m.vx * 14, m.y - m.vy * 14);
      g.addColorStop(0, `rgba(255,255,255,${m.life})`); g.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.strokeStyle = g; ctx.lineWidth = 2 * devicePixelRatio;
      ctx.beginPath(); ctx.moveTo(m.x, m.y); ctx.lineTo(m.x - m.vx * 14, m.y - m.vy * 14); ctx.stroke();
      m.x += m.vx; m.y += m.vy; m.life -= 0.015;
    }
    requestAnimationFrame(frame);
  }
  frame();

  // ---------------------------------------------------------- text effects
  const timers = new WeakMap();
  function stopFx(el) { (timers.get(el) || []).forEach(clearInterval); timers.set(el, []); el.classList.remove('typing'); }
  function keepTimer(el, t) { timers.set(el, [...(timers.get(el) || []), t]); }

  function original(el) {
    if (!el.dataset.text) el.dataset.text = el.innerHTML;
    return el.dataset.text;
  }
  // Typewriter (plain text only; markup is restored at the end).
  function typewriter(el) {
    const html = original(el);
    const tmp = document.createElement('div'); tmp.innerHTML = html;
    const text = tmp.textContent;
    let i = 0; el.textContent = ''; el.classList.add('typing');
    const t = setInterval(() => {
      i += 1; el.textContent = text.slice(0, i);
      if (i >= text.length) { clearInterval(t); el.innerHTML = html; setTimeout(() => el.classList.remove('typing'), 900); }
    }, Math.max(12, 900 / text.length));
    keepTimer(el, t);
  }
  // Scramble / decode: random glyphs settle into the final text.
  const GLYPHS = '01<>/\\|=+*#%ΔΣΩ◆◇◉⌖▲▼';
  function scramble(el, duration = 1300) {
    const html = original(el);
    const tmp = document.createElement('div'); tmp.innerHTML = html;
    const text = tmp.textContent;
    const start = performance.now();
    const t = setInterval(() => {
      const p = Math.min(1, (performance.now() - start) / duration);
      const fixed = Math.floor(text.length * p);
      let out = '';
      for (let i = 0; i < text.length; i++) out += i < fixed || text[i] === ' ' ? text[i] : GLYPHS[(Math.random() * GLYPHS.length) | 0];
      el.textContent = out;
      if (p >= 1) { clearInterval(t); el.innerHTML = html; }
    }, 40);
    keepTimer(el, t);
  }
  // Number counters inside an element: <b data-count="17735" data-dec="1">
  function countUp(root, instant) {
    const nodes = root.matches('[data-count]') ? [root] : [...root.querySelectorAll('[data-count]')];
    nodes.forEach((n) => {
      const target = parseFloat(n.dataset.count), dec = parseInt(n.dataset.dec || '0', 10);
      const fmt = (v) => v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
      if (instant) { n.textContent = fmt(target); return; }
      const start = performance.now(), dur = 1100;
      const tick = (now) => {
        const p = Math.min(1, (now - start) / dur), e = 1 - Math.pow(1 - p, 4);
        n.textContent = fmt(target * e);
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  }

  // ------------------------------------------------------------- the deck
  const slides = [...document.querySelectorAll('.slide')];
  const decks = slides.map((s) => {
    const steps = [...s.querySelectorAll('[data-step]')];
    const max = steps.reduce((m, el) => Math.max(m, +el.dataset.step), 0);
    const groups = Array.from({ length: max }, (_, i) => steps.filter((el) => +el.dataset.step === i + 1));
    return { el: s, groups };
  });
  let cur = 0, step = 0, busy = false;

  function reveal(el, instant) {
    stopFx(el);
    const anim = el.dataset.anim || 'rise';
    el.classList.remove('in', 'shown');
    void el.getBoundingClientRect(); // restart CSS animation
    if (instant) {
      el.classList.add('shown');
      if (el.dataset.text) el.innerHTML = el.dataset.text;
    } else {
      el.classList.add('in', `a-${anim}`);
      if (anim === 'typewriter') typewriter(el);
      if (anim === 'scramble' || anim === 'decode') scramble(el, anim === 'decode' ? 1100 : 800);
    }
    countUp(el, instant);
  }
  function hide(el) {
    stopFx(el);
    el.classList.remove('in', 'shown');
    [...el.classList].filter((c) => c.startsWith('a-')).forEach((c) => el.classList.remove(c));
    if (el.dataset.text) el.innerHTML = el.dataset.text;
    el.querySelectorAll('[data-count]').forEach((n) => (n.textContent = '0'));
    if (el.matches('[data-count]')) el.textContent = '0';
  }

  function onStepChange() {
    // Roadmap rocket follows the path to the latest milestone.
    const d = decks[cur];
    const rocket = d.el.querySelector('.rocket');
    const path = d.el.querySelector('#rmPath');
    if (rocket && path) {
      const len = path.getTotalLength(), total = d.groups.length;
      const t = step === 0 ? 0 : step / total;
      const p = path.getPointAtLength(len * t), q = path.getPointAtLength(Math.min(len, len * t + 4));
      const svg = path.ownerSVGElement, box = svg.viewBox.baseVal;
      const sx = svg.clientWidth / box.width, sy = svg.clientHeight / box.height;
      rocket.style.left = `${p.x * sx}px`;
      rocket.style.top = `${70 + p.y * sy}px`;
      const ang = Math.atan2(q.y - p.y, q.x - p.x) * 180 / Math.PI + 45;
      rocket.style.setProperty('--rot', `${ang}deg`);
    }
    updateHud();
  }

  function show(index, atStep = 0, direction = 1) {
    const prev = slides[cur];
    if (index !== cur) {
      prev.classList.remove('active', ...[...prev.classList].filter((c) => c.startsWith('t-')));
      prev.classList.add('leaving');
      setTimeout(() => prev.classList.remove('leaving'), 420);
      warp(direction > 0 ? 40 : 18);
    }
    cur = index;
    const d = decks[cur];
    d.groups.flat().forEach(hide);
    const s = d.el;
    s.classList.remove('active');
    void s.getBoundingClientRect();
    s.classList.add('active', `t-${s.dataset.transition || 'warp'}`);
    s.querySelectorAll('.intro [data-count], .intro[data-count]').forEach((n) => countUp(n.closest('.intro'), false));
    step = 0;
    for (let i = 0; i < atStep; i++) d.groups[i].forEach((el) => reveal(el, true));
    step = atStep;
    onStepChange();
    history.replaceState(null, '', `#${cur + 1}`);
  }

  function next() {
    if (busy) return;
    const d = decks[cur];
    if (step < d.groups.length) {
      d.groups[step].forEach((el) => reveal(el, false));
      step += 1;
      onStepChange();
    } else if (cur < slides.length - 1) {
      busy = true; setTimeout(() => (busy = false), 350);
      show(cur + 1, 0, 1);
    }
  }
  function prev() {
    if (busy) return;
    const d = decks[cur];
    if (step > 0) {
      step -= 1;
      d.groups[step].forEach(hide);
      onStepChange();
    } else if (cur > 0) {
      busy = true; setTimeout(() => (busy = false), 450);
      show(cur - 1, decks[cur - 1].groups.length, -1);
    }
  }

  // ------------------------------------------------------------------ HUD
  const hud = document.getElementById('hud');
  const hudLabel = document.getElementById('hud-label');
  const hudCount = document.getElementById('hud-count');
  const hudSteps = document.getElementById('hud-steps');
  const bar = document.querySelector('#progress i');
  const pad = (n) => String(n).padStart(2, '0');
  function updateHud() {
    const d = decks[cur];
    hudLabel.textContent = (d.el.dataset.label || '').toUpperCase();
    hudCount.textContent = `${pad(cur + 1)} / ${pad(slides.length)}`;
    hudSteps.innerHTML = d.groups.map((_, i) => `<i class="${i < step ? 'on' : ''}"></i>`).join('');
    const totalSteps = decks.reduce((s, x) => s + x.groups.length + 1, 0);
    const done = decks.slice(0, cur).reduce((s, x) => s + x.groups.length + 1, 0) + step + 1;
    bar.style.width = `${(done / totalSteps) * 100}%`;
  }

  // --------------------------------------------------------------- input
  const ripples = document.getElementById('ripples');
  function ripple(x, y) {
    ['', 'b'].forEach((c) => {
      const r = document.createElement('span');
      r.className = `ripple ${c}`; r.style.left = `${x}px`; r.style.top = `${y}px`;
      ripples.appendChild(r); setTimeout(() => r.remove(), 1000);
    });
  }
  document.addEventListener('click', (e) => { ripple(e.clientX, e.clientY); next(); });
  document.addEventListener('contextmenu', (e) => { e.preventDefault(); prev(); });
  document.addEventListener('keydown', (e) => {
    if (['ArrowRight', 'ArrowDown', ' ', 'PageDown', 'Enter'].includes(e.key)) { e.preventDefault(); next(); }
    else if (['ArrowLeft', 'ArrowUp', 'PageUp', 'Backspace'].includes(e.key)) { e.preventDefault(); prev(); }
    else if (e.key === 'Home') show(0, 0, -1);
    else if (e.key === 'End') show(slides.length - 1, 0, 1);
    else if (e.key.toLowerCase() === 'f') { if (!document.fullscreenElement) document.documentElement.requestFullscreen?.(); else document.exitFullscreen?.(); }
    else if (e.key.toLowerCase() === 'h') hud.classList.toggle('hidden');
  });
  let touchX = null;
  document.addEventListener('touchstart', (e) => (touchX = e.touches[0].clientX), { passive: true });
  document.addEventListener('touchend', (e) => {
    if (touchX === null) return;
    const dx = e.changedTouches[0].clientX - touchX;
    if (Math.abs(dx) > 50) { dx < 0 ? next() : prev(); }
    touchX = null;
  });

  // --------------------------------------------------------------- start
  // #N opens slide N; ?all shows every step of it at once (handy for checking layouts).
  const fromHash = parseInt(location.hash.slice(1), 10);
  const startAt = Number.isFinite(fromHash) && fromHash >= 1 && fromHash <= slides.length ? fromHash - 1 : 0;
  const params = new URLSearchParams(location.search);
  const revealAll = params.has('all');
  if (params.has('static')) { document.documentElement.classList.add('static'); warp = () => {}; }
  show(startAt, revealAll ? decks[startAt].groups.length : 0, 1);
})();
