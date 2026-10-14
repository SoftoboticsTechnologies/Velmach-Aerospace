/* Velmach Aerospace: shared state for every page (language, RFQ list, breakpoints, reveal-on-scroll). */
(function () {
  if (window.VM) return;
  var LK = 'vm_lang', RK = 'vm_rfq', AK = 'vm_aircraft';
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
  window.addEventListener('storage', function (e) { if (e.key === RK || e.key === AK) emit(); if (e.key === LK && (e.newValue === 'en' || e.newValue === 'ar')) { lang = e.newValue; apply(); emit(); } });
  function apply() { var d = document.documentElement; d.lang = lang; d.dir = lang === 'ar' ? 'rtl' : 'ltr'; }
  apply();

  var logoFail = {};
  try { logoFail = JSON.parse(sessionStorage.getItem('vm_logo_fail2') || '{}') || {}; } catch (e) {}

  var FAR = "'IBM Plex Sans Arabic', 'Segoe UI', Tahoma, sans-serif";
  var io = null;
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var VM = window.VM = {
    PAGES: ['home', 'about', 'products', 'industries', 'services', 'quality', 'blog', 'contact'],
    HREF: { home: 'index.html', about: 'about.dc.html', products: 'categories.dc.html', industries: 'industries.dc.html', services: 'services.dc.html', quality: 'quality.dc.html', blog: 'blogs.dc.html', contact: 'contact.dc.html', rfq: 'rfq.dc.html',
      categories: 'categories.dc.html', brands: 'brands.dc.html', search: 'search.dc.html' },
    /* Catalogue links. Query URLs work on any static host; js/routes.js documents the clean /c/, /brand/ forms. */
    /* With cleanUrls: true in js/site-config.js (only once the host has the rewrite rules from _redirects, vercel.json
       or .htaccess) these return /c/<parent>/<child>, /p/<slug>, /brand/<slug>, /search?q=, /<service> instead. */
    clean: function () { return !!(window.VM_CONFIG && window.VM_CONFIG.cleanUrls); },
    catHref: function (parent, child) { var p = encodeURIComponent(parent) + (child ? '/' + encodeURIComponent(child) : ''); return VM.clean() ? '/c/' + p : 'category.dc.html?c=' + p; },
    productHref: function (slug) { return VM.clean() ? '/p/' + encodeURIComponent(slug) : 'product.dc.html?p=' + encodeURIComponent(slug); },
    brandHref: function (slug) { return VM.clean() ? '/brand/' + encodeURIComponent(slug) : 'brand.dc.html?b=' + encodeURIComponent(slug); },
    searchHref: function (q) { return (VM.clean() ? '/search?q=' : 'search.dc.html?q=') + encodeURIComponent(q); },
    pageHref: function (slug) { return VM.clean() ? '/' + encodeURIComponent(slug) : 'page.dc.html?p=' + encodeURIComponent(slug); },
    /* The previous catalogue's category ids (products.dc.html?cat=...), pointed at the closest new category. */
    legacyCatHref: function (cat) {
      var m = { parts: 'aircraft-parts', used: 'aircraft-parts', lubricants: 'consumables', chemicals: 'consumables', cleaners: 'consumables',
        paints: 'consumables', adhesives: 'consumables', sealants: 'consumables', petrochem: 'consumables', tapes: 'consumables/tape' };
      if (cat === 'consultancy') return 'services.dc.html';
      return m[cat] ? 'category.dc.html?c=' + m[cat] : 'categories.dc.html';
    },
    /* Category tree lookups (data/categories.js). path is "parent" or "parent/child". */
    findCat: function (path) {
      var bits = String(path || '').split('/'), cats = window.VM_CATS || [], p = null, c = null;
      for (var i = 0; i < cats.length; i++) if (cats[i].slug === bits[0]) p = cats[i];
      if (p && bits[1]) for (var j = 0; j < p.children.length; j++) if (p.children[j].slug === bits[1]) c = p.children[j];
      return p ? { parent: p, child: c } : null;
    },
    label: function (node) { return node ? (lang === 'ar' && node.ar ? node.ar : node.en) : ''; },
    /* Brand logo path from data/brands.js ("logo", filled in by scripts/build-catalog.py from public/brands/), otherwise ''
       and the brand name shows. A logo that fails to load is remembered for the session (VM.logoFailed). */
    brandLogo: function (slug) {
      if (logoFail[slug]) return '';
      var bs = window.VM_BRANDS || [];
      for (var i = 0; i < bs.length; i++) if (bs[i].slug === slug) return bs[i].logo || '';
      return '';
    },
    /* true when the brand's only logo is white (public/brands/<slug>-white.*): pages show it on a dark backing */
    brandLogoDark: function (slug) {
      var bs = window.VM_BRANDS || [];
      for (var i = 0; i < bs.length; i++) if (bs[i].slug === slug) return !!bs[i].logoDark;
      return false;
    },
    logoFailed: function (slug) { if (logoFail[slug]) return; logoFail[slug] = 1; try { sessionStorage.setItem('vm_logo_fail2', JSON.stringify(logoFail)); } catch (e) {} emit(); },

    /* Shop by Aircraft: saved aircraft and the one currently shopped for (localStorage vm_aircraft).
       Aircraft ids are "<make-slug>/<model-slug>", the same ids products list in compatibleAircraft. */
    acId: function (make, model) { var s = function (x) { return String(x).toLowerCase().replace(/&/g, ' ').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, ''); }; return s(make) + '/' + s(model); },
    hangar: function () {
      try { var h = JSON.parse(get(AK) || 'null'); if (h && Array.isArray(h.saved)) return { saved: h.saved, current: h.current || null }; } catch (e) {}
      return { saved: [], current: null };
    },
    setHangar: function (h) { set(AK, JSON.stringify(h)); emit(); },
    currentAircraft: function () { var h = VM.hangar(); for (var i = 0; i < h.saved.length; i++) if (h.saved[i].id === h.current) return h.saved[i]; return null; },
    addAircraft: function (make, model) {
      var h = VM.hangar(), id = VM.acId(make, model), has = false;
      for (var i = 0; i < h.saved.length; i++) if (h.saved[i].id === id) has = true;
      if (!has) h.saved.push({ id: id, make: make, model: model });
      h.current = id; VM.setHangar(h);
    },
    selectAircraft: function (id) { var h = VM.hangar(); h.current = id || null; VM.setHangar(h); },
    removeAircraft: function (id) { var h = VM.hangar(); h.saved = h.saved.filter(function (a) { return a.id !== id; }); if (h.current === id) h.current = null; VM.setHangar(h); },
    clearAircraft: function () { VM.setHangar({ saved: [], current: null }); },
    /* true when a product suits the selected aircraft (no aircraft selected, or the product lists none, means it fits) */
    fitsAircraft: function (product) {
      var a = VM.currentAircraft(), list = product && product.compatibleAircraft;
      if (!a || !list || !list.length) return true;
      for (var i = 0; i < list.length; i++) { var x = String(list[i]); if (x === a.id || x.toLowerCase() === (a.make + ' ' + a.model).toLowerCase()) return true; }
      return false;
    },
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
      // one line per product: by part number, or by product page when the source gives no part number
      for (var j = 0; j < r.length; j++) if (item.pn ? r[j].pn === item.pn : (!r[j].pn && r[j].slug && r[j].slug === item.slug)) i = j;
      if (i >= 0) r[i].qty += qty; else r.push(Object.assign({}, item, { qty: qty }));
      VM.setRfq(r);
      window.dispatchEvent(new CustomEvent('vm:toast', { detail: VM.t().p_added }));
    },
    openRfq: function () { window.dispatchEvent(new Event('vm:open-rfq')); },
    /* Request for Quote form for one product ({ title, pn, brand, slug }); RfqModal.dc.html listens for it. */
    requestQuote: function (product) { window.dispatchEvent(new CustomEvent('vm:rfq-product', { detail: product })); },
    /* Quote list entry for a catalogue product (same list the header badge and rfq.dc.html use). */
    addToQuote: function (product, qty) {
      VM.addRfq({ pn: product.pn, name_en: product.title, name_ar: product.title, brand: product.brand || '', slug: product.slug || '',
        image: product.image || '', cond: 'any' }, qty || 1);
    },
    /* "Boeing 737 NG" for an aircraft id ("boeing/737-ng"), from data/aircraft.js */
    acLabel: function (id) {
      var list = window.VM_AIRCRAFT || [];
      for (var i = 0; i < list.length; i++) for (var j = 0; j < list[i].models.length; j++)
        if (VM.acId(list[i].make, list[i].models[j]) === id) return list[i].make + ' ' + list[i].models[j];
      return id;
    },
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
        fBody: ar ? FAR : "'VMAmp', 'Archivo', system-ui, -apple-system, 'Segoe UI', sans-serif",
        fHead: ar ? FAR : "'VMAmp', 'Archivo', system-ui, -apple-system, 'Segoe UI', sans-serif",
        fMono: ar ? FAR : "'Archivo', system-ui, sans-serif",
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
