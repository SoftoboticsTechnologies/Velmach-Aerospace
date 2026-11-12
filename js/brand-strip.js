/* Velmach Aerospace: home page brand strips.
   [data-brand-strip]: every product brand (data/brands.js, A to Z, aircraft makers left out) dealt across three rows.
   [data-maker-strip]: aircraft and helicopter manufacturers (data/makers.js), one labelled row per type.
   Rows scroll in alternating directions without a seam and keep moving on hover (pause only for keyboard focus); each tile shows the logo (when
   there is one) above the name. With reduced motion the rows stay still and scroll by hand. */
(function () {
  var builtW = 0, resizeT, MAX_BRANDS = 60;
  function brandTile(b) { return { name: b.name, href: window.VM.brandHref(b.slug), slug: b.slug }; }
  // a maker that is a catalog brand links to its brand page; any other maker to the quote request page
  function isBrand(slug) { return !!slug && (window.VM_BRANDS || []).some(function (b) { return b.slug === slug; }); }
  function makerTile(m) { return { name: m.name, href: isBrand(m.slug) ? window.VM.brandHref(m.slug) : 'rfq.dc.html', logo: m.logo }; }
  function brandRows() {
    var mk = window.VM_MAKERS || {}, skip = {};
    (mk.aircraft || []).concat(mk.helicopters || []).forEach(function (m) { if (m.slug) skip[m.slug] = 1; });
    // at most MAX_BRANDS tiles (featured first, then brands with a logo): the page stays light and "View all brands"
    // lists the rest
    var all = (window.VM_BRANDS || []).filter(function (b) { return !skip[b.slug]; });
    var rank = function (b) { return (b.featured ? 0 : 2) + (window.VM.brandLogo(b.slug) ? 0 : 1); };
    all = all.map(function (b, i) { return [rank(b), i, b]; }).sort(function (x, y) { return x[0] - y[0] || x[1] - y[1]; })
      .slice(0, MAX_BRANDS).map(function (x) { return x[2]; })
      .sort(function (a, b) { return a.name.localeCompare(b.name); });
    // dealt in turn, so each row runs A to Z on its own
    var rows = [[], [], []];
    all.forEach(function (b, i) { rows[i % 3].push(brandTile(b)); });
    return rows.map(function (list) { return { list: list }; });
  }
  function makerRows() {
    var mk = window.VM_MAKERS || {};
    return [{ label: 'hm_air', list: (mk.aircraft || []).map(makerTile) }, { label: 'hm_heli', list: (mk.helicopters || []).map(makerTile) }];
  }
  function fill(host, rows) {
    host.innerHTML = '';
    var t = window.VM.t() || {};
    rows.forEach(function (r, ri) {
      var list = r.list;
      if (!list.length) return;
      if (r.label) {
        var h = document.createElement('p');
        h.className = 'bstrip-lbl wrap';
        h.setAttribute('data-t', r.label);
        h.textContent = t[r.label] || '';
        host.appendChild(h);
      }
      var row = document.createElement('div');
      row.className = 'bstrip-row' + (ri % 2 ? ' bstrip-row--rev' : '');
      var track = document.createElement('ul');
      track.className = 'bstrip-track';
      function add(copy) {
        list.forEach(function (b) {
          var li = document.createElement('li'), a = document.createElement('a');
          a.className = 'bstrip-tile';
          a.href = b.href;
          if (b.slug) a.setAttribute('data-brand', b.slug);
          if (b.logo) a.setAttribute('data-logo', b.logo);
          if (copy) { li.setAttribute('aria-hidden', 'true'); a.tabIndex = -1; }
          var n = document.createElement('span'); n.className = 'bstrip-n'; n.textContent = b.name; a.appendChild(n);
          li.appendChild(a); track.appendChild(li);
        });
      }
      add(0);
      row.appendChild(track); host.appendChild(row);
      // half the track must be at least as wide as the strip, or the row runs out and leaves a gap; so the list is
      // repeated `reps` times per half, then the half twice, and moving by half the width loops seamlessly
      var gap = parseFloat(getComputedStyle(track).columnGap) || 0;
      var reps = Math.max(1, Math.ceil(builtW / (track.scrollWidth + gap)));
      for (var copy = 1; copy < reps * 2; copy++) add(copy);
      track.style.animationDuration = Math.max(28, list.length * reps * 5) + 's';
    });
  }
  function build() {
    if (!window.VM) return;
    var b = document.querySelector('[data-brand-strip]'), m = document.querySelector('[data-maker-strip]');
    builtW = (b || m || document.body).clientWidth;
    if (b && (window.VM_BRANDS || []).length) fill(b, brandRows());
    if (m && window.VM_MAKERS) fill(m, makerRows());
    paintLogos();
  }
  // a wider strip may need more repeats; rebuild once resizing settles
  function onResize() {
    clearTimeout(resizeT);
    resizeT = setTimeout(function () {
      var host = document.querySelector('[data-brand-strip]') || document.querySelector('[data-maker-strip]');
      if (host && host.clientWidth > builtW) build();
    }, 200);
  }
  // logo above the name; a logo that fails to load is dropped and the name stays. Row labels follow the language.
  function paintLogos() {
    var t = window.VM.t() || {};
    document.querySelectorAll('.bstrip-lbl[data-t]').forEach(function (p) { var v = t[p.getAttribute('data-t')]; if (v) p.textContent = v; });
    document.querySelectorAll('.bstrip-tile[data-brand], .bstrip-tile[data-logo]').forEach(function (a) {
      var slug = a.getAttribute('data-brand'), src = a.getAttribute('data-logo') || (slug ? window.VM.brandLogo(slug) : '');
      if (src && !a.querySelector('img')) {
        var img = new Image();
        img.src = src; img.alt = a.textContent + ' logo'; img.loading = 'lazy';
        if (slug && window.VM.brandLogoDark(slug)) img.className = 'is-dark';
        img.onerror = function () { img.remove(); if (slug) window.VM.logoFailed(slug); };
        a.insertBefore(img, a.firstChild);
      }
    });
  }
  function start() {
    // the strips sit below the first screen: build them when they come near, so they cost nothing at page load
    var host = document.querySelector('[data-maker-strip]') || document.querySelector('[data-brand-strip]');
    if (host && 'IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (es) { if (es.some(function (e) { return e.isIntersecting; })) { io.disconnect(); build(); } }, { rootMargin: '600px 0px' });
      io.observe(host);
    } else build();
    if (window.VM) window.VM.subscribe(paintLogos);
    window.addEventListener('resize', onResize);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
