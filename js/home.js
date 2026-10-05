/* Velmach Aerospace: home page behaviour.
   The page ships as complete English HTML (see tools/prerender-home.mjs). This script applies the visitor's
   language from js/i18n.js (data-t / data-t-attr keys), mounts the shared footer component, and runs the
   page's motion and interactions. Business logic (RFQ list, language state) stays in js/vm-core.js. */
(function () {
  var VM = window.VM, doc = document, root = doc.documentElement;
  if (!VM || !window.VM_I18N) return;
  var reduced = VM.reduced;
  var $ = function (s, el) { return (el || doc).querySelector(s); };
  var $$ = function (s, el) { return Array.prototype.slice.call((el || doc).querySelectorAll(s)); };
  var get = function (o, k) { return k.split('.').reduce(function (v, p) { return v == null ? v : v[p]; }, o); };

  /* ---------- language ---------- */
  var CO = { en: ['Velmach Aerospace F.Z.C', 'Velmach Aerospace F.Z.C logo'], ar: ['فيلماك إيروسبايس ش.م.ح', 'شعار فيلماك إيروسبايس'] };
  var lastLang = null;
  function applyLang() {
    if (VM.lang === lastLang) return;
    lastLang = VM.lang;
    var t = VM.t();
    $$('[data-t]').forEach(function (el) {
      var v = get(t, el.getAttribute('data-t')), sep = el.getAttribute('data-split');
      if (typeof v !== 'string') return;
      if (!sep) { el.textContent = v; return; }
      // one cell per term, e.g. "Aerospace parts • Materials • Sourcing"
      el.textContent = '';
      v.split(sep).map(function (x) { return x.trim(); }).filter(Boolean).forEach(function (x) {
        var c = doc.createElement('span'); c.className = 'tagbar-item'; c.textContent = x; el.appendChild(c);
      });
      el.classList.add('is-split');
    });
    $$('[data-t-attr]').forEach(function (el) {
      el.getAttribute('data-t-attr').split(';').forEach(function (p) { var kv = p.split(':'), v = get(t, kv[1]); if (typeof v === 'string') el.setAttribute(kv[0], v); });
    });
    var co = CO[VM.lang] || CO.en;
    $$('[data-co-name]').forEach(function (el) { el.textContent = co[0]; });
    $$('.rfq-logo img').forEach(function (el) { el.alt = co[1]; });
    VM.meta('home');
    placeIndBar();
  }

  /* ---------- shared footer (DC component, rendered by the same runtime as the header) ---------- */
  function mountFooter(tries) {
    var host = $('#site-footer');
    if (!host || host.firstChild) return;
    if (window.React && window.ReactDOM && window.getDC && window.ReactDOM.createRoot) {
      window.ReactDOM.createRoot(host).render(window.React.createElement(window.getDC('SiteFooter')));
    } else if ((tries || 0) < 200) setTimeout(function () { mountFooter((tries || 0) + 1); }, 50);
  }

  /* ---------- reveal on scroll ---------- */
  function reveals() {
    var els = $$('[data-rv]');
    els.forEach(function (el) {   // stagger siblings that reveal together
      var sib = el.parentElement ? $$(':scope > [data-rv]', el.parentElement) : [];
      var i = sib.indexOf(el);
      if (i > 0) el.style.setProperty('--d', Math.min(i, 6) * 0.07 + 's');
    });
    if (reduced || !('IntersectionObserver' in window)) { els.forEach(function (el) { el.classList.add('is-in'); }); return; }
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); } });
    }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
    els.forEach(function (el) { io.observe(el); });
    var once = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('is-in'); once.unobserve(e.target); } });
    }, { threshold: 0.3 });
    [$('.map'), $('.aog')].forEach(function (el) { el && once.observe(el); });
  }

  /* ---------- hero: open-rotor engine (js/hero-engine.js) + layered pointer parallax ---------- */
  var engine = null;
  function mountEngine() {
    var c = $('[data-engine]');
    if (!c || !window.VMHeroEngine) return;
    var lite = VM.bp === 'sm';                       // phones: lighter mesh, capped pixel ratio, ~30 fps
    if (engine && engine.lite === lite) return;
    engine && engine.destroy();
    engine = window.VMHeroEngine.mount(c, { reduced: reduced, lite: lite });
  }
  function hero() {
    var h = $('.hero');
    if (!h) return;
    mountEngine();
    VM.subscribe(mountEngine);
    if (reduced || !window.matchMedia('(pointer:fine)').matches) return;
    var raf = 0;
    h.addEventListener('pointermove', function (e) {
      var r = h.getBoundingClientRect(), x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(function () {
        h.style.setProperty('--mx', x.toFixed(3)); h.style.setProperty('--my', y.toFixed(3));
        engine && engine.setPointer(x, y);
      });
    });
    h.addEventListener('pointerleave', function () { h.style.setProperty('--mx', 0); h.style.setProperty('--my', 0); engine && engine.setPointer(0, 0); });
  }

  /* ---------- background navigation drawing (from <template id="nd-src">), animated only while visible ---------- */
  function sectionDrawings() {
    var tpl = doc.getElementById('nd-src'), slots = $$('[data-nd]');
    if (!tpl || !slots.length) return;
    slots.forEach(function (slot, i) {
      var nd = tpl.content.firstElementChild.cloneNode(true);
      // the first copy keeps the shared <defs> and ids; the others reference them
      if (i > 0) {
        $$('defs', nd).forEach(function (d) { d.remove(); });
        $$('[id]', nd).forEach(function (el) { el.removeAttribute('id'); });
      }
      slot.appendChild(nd);
    });
    if (!('IntersectionObserver' in window)) return;
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { e.target.classList.toggle('is-paused', !e.isIntersecting); });
    });
    slots.forEach(function (slot) { slot.classList.add('is-paused'); io.observe(slot); });
  }

  /* ---------- poster carousel: 2 s per slide, driven by the progress bar's CSS animation ---------- */
  function posterCarousel() {
    var root = $('[data-pcar]');
    if (!root) return;
    var slides = $$('.pcar-slide', root), dots = $$('.pcar-dot', root), pauseBtn = $('.pcar-pause', root);
    var at = 0, hover = false, focus = false, offscreen = false, stopped = false;
    function sync() {
      root.classList.toggle('is-paused', hover || focus || offscreen || stopped);
      root.classList.toggle('is-stopped', stopped);
      var t = VM.t();
      pauseBtn.setAttribute('aria-label', stopped ? t.car_play : t.car_pause);
      dots.forEach(function (d, i) { d.setAttribute('aria-label', t.car_goto + ' ' + (i + 1) + ' / ' + dots.length); });
    }
    function show(i) {
      at = (i + slides.length) % slides.length;
      slides.forEach(function (s, k) {
        var on = k === at;
        s.classList.toggle('is-active', on);
        if (on) { s.removeAttribute('aria-hidden'); s.removeAttribute('tabindex'); }
        else { s.setAttribute('aria-hidden', 'true'); s.setAttribute('tabindex', '-1'); }
      });
      dots.forEach(function (d, k) {
        d.classList.remove('is-active');
        d.classList.toggle('is-done', k < at);
        if (k === at) d.setAttribute('aria-current', 'true'); else d.removeAttribute('aria-current');
      });
      void dots[at].offsetWidth;                       // restart the fill animation
      dots[at].classList.add('is-active');
    }
    // the active bar finishing its 2 s fill advances the slide; pausing the animation pauses the carousel
    dots.forEach(function (d) { d.querySelector('i').addEventListener('animationend', function () { if (d.classList.contains('is-active')) show(at + 1); }); });
    if (reduced) root.classList.add('is-static');      // no automatic rotation when reduced motion is requested
    $$('[data-step]', root).forEach(function (b) { b.addEventListener('click', function () { show(at + Number(b.getAttribute('data-step'))); }); });
    dots.forEach(function (d) { d.addEventListener('click', function () { show(Number(d.getAttribute('data-go'))); }); });
    pauseBtn.addEventListener('click', function () { stopped = !stopped; sync(); });
    var frame = $('.pcar-frame', root);
    frame.addEventListener('mouseenter', function () { hover = true; sync(); });
    frame.addEventListener('mouseleave', function () { hover = false; sync(); });
    root.addEventListener('focusin', function () { focus = true; sync(); });
    root.addEventListener('focusout', function (e) { if (!root.contains(e.relatedTarget)) { focus = false; sync(); } });
    root.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      var fwd = (e.key === 'ArrowRight') !== (VM.lang === 'ar');
      e.preventDefault(); show(at + (fwd ? 1 : -1));
    });
    // swipe on touch screens; a swipe must not also follow the slide's link
    var x0 = null, swiped = false, track = $('.pcar-track', root);
    track.addEventListener('pointerdown', function (e) { x0 = e.clientX; swiped = false; });
    track.addEventListener('pointerup', function (e) {
      if (x0 === null) return;
      var dx = e.clientX - x0; x0 = null;
      if (Math.abs(dx) > 40) { swiped = true; var fwd = (dx < 0) !== (VM.lang === 'ar'); show(at + (fwd ? 1 : -1)); }
    });
    track.addEventListener('click', function (e) { if (swiped) { e.preventDefault(); swiped = false; } }, true);
    track.addEventListener('dragstart', function (e) { e.preventDefault(); });
    if ('IntersectionObserver' in window) new IntersectionObserver(function (es) { offscreen = !es[0].isIntersecting; sync(); }).observe(root);
    VM.subscribe(sync);
    sync(); show(0);
  }

  /* ---------- location: hover a region to trace its route ---------- */
  function regionMap() {
    var map = $('.map');
    $$('.loc-regions li').forEach(function (li) {
      var on = function () { map.setAttribute('data-hl', li.getAttribute('data-region')); };
      var off = function () { map.removeAttribute('data-hl'); };
      li.addEventListener('mouseenter', on); li.addEventListener('mouseleave', off);
      li.addEventListener('focus', on); li.addEventListener('blur', off);
    });
  }

  /* ---------- why: active item follows the reading position ---------- */
  function why() {
    var items = $$('.why-item'), n = $('[data-why-n]');
    if (!items.length) return;
    var set = function (i) {
      items.forEach(function (el, j) { el.classList.toggle('is-active', j === i); });
      var v = ('0' + (i + 1)).slice(-2);
      if (n && n.textContent !== v) {
        if (reduced) { n.textContent = v; return; }
        n.classList.add('is-swap');
        requestAnimationFrame(function () { n.textContent = v; requestAnimationFrame(function () { n.classList.remove('is-swap'); }); });
      }
    };
    if (!('IntersectionObserver' in window)) return;
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) set(items.indexOf(e.target)); });
    }, { rootMargin: '-42% 0px -42% 0px' });
    items.forEach(function (el) { io.observe(el); });
  }

  /* ---------- how it works: scroll-linked progress line ---------- */
  function timeline() {
    var tl = $('[data-tl]');
    if (!tl) return;
    var fill = $('.tl-track', tl), steps = $$('.tl-step', tl), nodes = $$('.tl-node', tl), ticking = false;
    function update() {
      ticking = false;
      var vh = window.innerHeight, r = tl.getBoundingClientRect(), vertical = VM.bp !== 'lg';
      var p = reduced ? 1 : Math.max(0, Math.min(1, (vh * 0.78 - r.top) / (vertical ? r.height : vh * 0.42)));
      tl.style.setProperty('--p', p.toFixed(4));
      var tr = fill.getBoundingClientRect();
      nodes.forEach(function (nd, i) {
        var b = nd.getBoundingClientRect(), at;
        if (vertical) at = (b.top + b.height / 2 - tr.top) / (tr.height || 1);
        else at = VM.lang === 'ar' ? (tr.right - (b.left + b.width / 2)) / (tr.width || 1) : (b.left + b.width / 2 - tr.left) / (tr.width || 1);
        steps[i].classList.toggle('is-on', p >= at - 0.002);
      });
    }
    var req = function () { if (!ticking) { ticking = true; requestAnimationFrame(update); } };
    window.addEventListener('scroll', req, { passive: true });
    window.addEventListener('resize', req);
    VM.subscribe(req);
    update();
  }

  /* ---------- industries: one open at a time; panel sits beside the list on lg, inline below ---------- */
  var indSel = null;
  function placeIndBar() {
    if (!indSel) return;
    var bar = $('.ind-bar', indSel), btn = $('.ind-btn[aria-expanded="true"]', indSel);
    if (!bar || !btn || VM.bp !== 'lg') return;
    var a = indSel.getBoundingClientRect(), b = btn.getBoundingClientRect();
    bar.style.height = b.height + 'px';
    bar.style.transform = 'translateY(' + (b.top - a.top) + 'px)';
  }
  function industries() {
    indSel = $('[data-ind]');
    if (!indSel) return;
    var btns = $$('.ind-btn', indSel), timer = 0;
    function open(btn, toggle) {
      var wasOpen = btn.getAttribute('aria-expanded') === 'true';
      var collapse = toggle && wasOpen && VM.bp !== 'lg';   // accordion can close; the side-by-side view always shows one
      btns.forEach(function (b) {
        var on = b === btn && !collapse;
        if ((b.getAttribute('aria-expanded') === 'true') === on) return;
        b.setAttribute('aria-expanded', on ? 'true' : 'false');
        b.closest('.ind-item').classList.toggle('is-open', on);
        doc.getElementById(b.getAttribute('aria-controls')).hidden = !on;
      });
      placeIndBar();
    }
    btns.forEach(function (b) {
      b.addEventListener('click', function () { open(b, true); });
      b.addEventListener('mouseenter', function () {
        if (VM.bp !== 'lg' || !window.matchMedia('(pointer:fine)').matches) return;
        clearTimeout(timer); timer = setTimeout(function () { open(b, false); }, 140);
      });
      b.addEventListener('mouseleave', function () { clearTimeout(timer); });
    });
    // arrow keys move between industries
    indSel.addEventListener('keydown', function (e) {
      var i = btns.indexOf(doc.activeElement);
      if (i < 0 || (e.key !== 'ArrowDown' && e.key !== 'ArrowUp')) return;
      e.preventDefault();
      var nx = btns[(i + (e.key === 'ArrowDown' ? 1 : btns.length - 1)) % btns.length];
      nx.focus(); if (VM.bp === 'lg') open(nx, false);
    });
    window.addEventListener('resize', placeIndBar);
    VM.subscribe(placeIndBar);
    if (doc.fonts && doc.fonts.ready) doc.fonts.ready.then(placeIndBar);
    placeIndBar();
  }

  /* ---------- final RFQ: same behaviour as before (add the part number, open the RFQ panel) ---------- */
  function rfqForm() {
    var f = $('[data-rfq-form]');
    if (!f) return;
    f.addEventListener('submit', function (e) {
      e.preventDefault();
      var input = f.querySelector('input'), pn = input.value.trim();
      if (pn) { VM.addRfq({ pn: pn, name_en: '__manual', name_ar: '__manual', cond: 'any' }, 1); input.value = ''; }
      VM.openRfq();
    });
  }

  function init() {
    applyLang();
    VM.subscribe(applyLang);
    mountFooter(0);
    sectionDrawings(); reveals(); hero(); posterCarousel(); regionMap(); why(); timeline(); industries(); rfqForm();
  }
  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', init); else init();
})();
