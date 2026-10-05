/* Velmach Aerospace: shared state for every page (language, RFQ list, breakpoints, reveal-on-scroll). */
(function () {
  if (window.VM) return;
  var LK = 'vm_lang', RK = 'vm_rfq';
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function initLang() {
    var u = new URLSearchParams(location.search).get('lang');
    if (u === 'en' || u === 'ar') { set(LK, u); return u; }          // URL wins
    var s = get(LK); if (s === 'en' || s === 'ar') return s;
    return (navigator.language || '').toLowerCase().indexOf('ar') === 0 ? 'ar' : 'en';
  }
  var lang = initLang();
  var subs = [];
  function emit() { subs.slice().forEach(function (f) { try { f(); } catch (e) {} }); }
  function bpOf(w) { return w < 760 ? 'sm' : w < 1100 ? 'md' : 'lg'; }
  var lastBp = bpOf(window.innerWidth);
  function checkBp() { var b = bpOf(window.innerWidth); if (b !== lastBp) { lastBp = b; emit(); } }
  window.addEventListener('resize', checkBp);
  window.addEventListener('load', function () { lastBp = bpOf(window.innerWidth); emit(); });
  document.addEventListener('DOMContentLoaded', checkBp);
  setTimeout(checkBp, 300); setTimeout(checkBp, 1200);
  window.addEventListener('storage', function (e) { if (e.key === RK) emit(); if (e.key === LK && (e.newValue === 'en' || e.newValue === 'ar')) { lang = e.newValue; apply(); emit(); } });
  function apply() { var d = document.documentElement; d.lang = lang; d.dir = lang === 'ar' ? 'rtl' : 'ltr'; }
  apply();

  var FAR = "'IBM Plex Sans Arabic', 'Segoe UI', Tahoma, sans-serif";
  var io = null;
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var VM = window.VM = {
    PAGES: ['home', 'about', 'products', 'industries', 'services', 'quality', 'blog', 'contact'],
    HREF: { home: 'index.html', about: 'about.dc.html', products: 'products.dc.html', industries: 'industries.dc.html', services: 'services.dc.html', quality: 'quality.dc.html', blog: 'blogs.dc.html', contact: 'contact.dc.html', rfq: 'rfq.dc.html' },
    reduced: reduced,
    get lang() { return lang; },
    get bp() { return bpOf(window.innerWidth); },
    t: function () { return window.VM_I18N[lang]; },
    setLang: function (l) { lang = l; set(LK, l); if (location.search.indexOf('lang=') > -1) history.replaceState(null, '', location.pathname + location.hash); apply(); emit(); },
    toggleLang: function () { VM.setLang(lang === 'ar' ? 'en' : 'ar'); },
    subscribe: function (f) { subs.push(f); return function () { subs = subs.filter(function (x) { return x !== f; }); }; },
    rfq: function () { try { return JSON.parse(get(RK) || '[]') || []; } catch (e) { return []; } },
    setRfq: function (r) { set(RK, JSON.stringify(r)); emit(); },
    addRfq: function (item, qty) {
      var r = VM.rfq(), i = -1;
      for (var j = 0; j < r.length; j++) if (r[j].pn === item.pn) i = j;
      if (i >= 0) r[i].qty += qty; else r.push(Object.assign({}, item, { qty: qty }));
      VM.setRfq(r);
      window.dispatchEvent(new CustomEvent('vm:toast', { detail: VM.t().p_added }));
    },
    openRfq: function () { window.dispatchEvent(new Event('vm:open-rfq')); },
    meta: function (page) {
      var m = VM.t().meta[page] || VM.t().meta.home;
      document.title = m[0];
      var md = document.querySelector('meta[name="description"]');
      if (!md) { md = document.createElement('meta'); md.name = 'description'; document.head.appendChild(md); }
      md.content = m[1];
    },
    /* Style values that change with language (fonts, rhythm, direction). */
    sv: function () {
      var ar = lang === 'ar', bp = bpOf(window.innerWidth);
      return {
        lang: lang, dir: ar ? 'rtl' : 'ltr', ar: ar,
        fBody: ar ? FAR : "'Manrope', system-ui, -apple-system, 'Segoe UI', sans-serif",
        fHead: ar ? FAR : "'Space Grotesk', system-ui, -apple-system, 'Segoe UI', sans-serif",
        fMono: ar ? FAR : "'IBM Plex Mono', ui-monospace, Menlo, monospace",
        lh: ar ? 1.85 : 1.6, lhHead: ar ? 1.35 : 1.06, ls: ar ? '0' : '.16em', lsHead: ar ? '0' : '-0.02em',
        arrow: ar ? '←' : '→', flip: ar ? 'scaleX(-1)' : 'none', start: ar ? 'right' : 'left', end: ar ? 'left' : 'right',
        sm: bp === 'sm', md: bp === 'md', lg: bp === 'lg', notLg: bp !== 'lg', notSm: bp !== 'sm'
      };
    },
    /* Reveal-on-scroll for elements marked data-reveal (optional data-reveal-delay in ms). */
    reveal: function () {
      if (reduced || !('IntersectionObserver' in window)) return;
      if (!io) io = new IntersectionObserver(function (es) {
        es.forEach(function (e) { if (e.isIntersecting) { e.target.style.opacity = '1'; e.target.style.transform = 'none'; io.unobserve(e.target); } });
      }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
      document.querySelectorAll('[data-reveal]:not([data-rv])').forEach(function (el) {
        el.setAttribute('data-rv', '1');
        var d = el.getAttribute('data-reveal-delay') || 0, line = el.getAttribute('data-reveal') === 'line';
        el.style.opacity = line ? '1' : '0'; el.style.transform = line ? 'scaleX(0)' : 'translateY(22px)';
        el.style.transition = 'opacity .8s cubic-bezier(.2,.7,.2,1) ' + d + 'ms, transform ' + (line ? '1.4s' : '.8s') + ' cubic-bezier(.2,.7,.2,1) ' + d + 'ms';
        io.observe(el);
      });
    }
  };
})();
