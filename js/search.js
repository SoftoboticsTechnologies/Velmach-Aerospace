/* Velmach Aerospace: catalogue search used by the header suggestions and search.dc.html.
   Categories (data/categories.js) and brands (data/brands.js) are matched in memory. Products come from the index
   named in VM_CONFIG.searchIndex (a JSON array of { s: slug, t: title, pn: part number, b: brand, i: thumbnail }),
   fetched once on first use; with no index configured, product results are simply empty. */
(function () {
  if (window.VM_SEARCH) return;
  var index = null, loading = null;

  // lower case, accents stripped, punctuation folded to spaces
  function norm(s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9؀-ۿ]+/g, ' ').trim(); }
  // part numbers compare without spaces, dashes or slashes
  function compact(s) { return String(s || '').toLowerCase().replace(/[^a-z0-9]/g, ''); }

  // 3 = starts with the query, 2 = a word starts with it, 1 = contains it, 0 = no match
  function score(text, q) {
    var t = norm(text);
    if (!t || !q) return 0;
    if (t.indexOf(q) === 0) return 3;
    if ((' ' + t).indexOf(' ' + q) > -1) return 2;
    return t.indexOf(q) > -1 ? 1 : 0;
  }

  function loadIndex() {
    var url = window.VM_CONFIG && window.VM_CONFIG.searchIndex;
    if (!url) return Promise.resolve([]);
    if (index) return Promise.resolve(index);
    if (!loading) loading = fetch(url).then(function (r) { return r.ok ? r.json() : []; })
      .then(function (d) { index = Array.isArray(d) ? d : []; return index; })
      .catch(function () { loading = null; return []; });
    return loading;
  }

  function matchCats(q, ar, limit) {
    var out = [];
    (window.VM_CATS || []).forEach(function (p) {
      var sp = Math.max(score(p.en, q), score(p.ar, q));
      if (sp) out.push({ rank: sp + 0.5, parent: p, child: null });
      p.children.forEach(function (c) {
        var sc = Math.max(score(c.en, q), score(c.ar, q));
        if (sc) out.push({ rank: sc, parent: p, child: c });
      });
    });
    out.sort(function (a, b) { return b.rank - a.rank; });
    return out.slice(0, limit).map(function (m) {
      var node = m.child || m.parent;
      return { label: ar && node.ar ? node.ar : node.en, parentLabel: m.child ? (ar && m.parent.ar ? m.parent.ar : m.parent.en) : '',
        href: window.VM.catHref(m.parent.slug, m.child && m.child.slug) };
    });
  }

  function matchBrands(q, limit) {
    return (window.VM_BRANDS || []).map(function (b) { return { b: b, rank: score(b.name, q) }; })
      .filter(function (m) { return m.rank; })
      .sort(function (a, b) { return b.rank - a.rank || a.b.name.localeCompare(b.b.name); })
      .slice(0, limit).map(function (m) { return { label: m.b.name, slug: m.b.slug, href: window.VM.brandHref(m.b.slug) }; });
  }

  // products matching q (already normalised), best first: part number, then title, then brand
  function rank(list, q) {
    var cq = compact(q), out = [];
    for (var i = 0; i < list.length; i++) {
      var p = list[i], r = 0, pn = compact(p.pn);
      if (cq && pn) r = pn === cq ? 10 : pn.indexOf(cq) === 0 ? 8 : pn.indexOf(cq) > -1 ? 5 : 0;
      r = Math.max(r, score(p.t, q) * 2, score(p.b, q) * 1.5);
      if (r) out.push({ p: p, r: r, i: i });
    }
    out.sort(function (a, b) { return b.r - a.r || a.i - b.i; });
    return out;
  }

  function matchProducts(list, q, limit) {
    return rank(list, q).slice(0, limit).map(function (m) {
      return { title: m.p.t, pn: m.p.pn || '', brand: m.p.b || '', img: m.p.i || '', href: window.VM.productHref(m.p.s) };
    });
  }

  window.VM_SEARCH = {
    norm: norm,
    /* every product card (data/catalog/search.json) */
    index: loadIndex,
    /* product cards matching the text, best first */
    rank: function (list, raw) { var q = norm(raw); return q ? rank(list, q).map(function (m) { return m.p; }) : list.slice(); },
    matchCats: function (raw, ar, limit) { var q = norm(raw); return q ? matchCats(q, ar, limit || 24) : []; },
    matchBrands: function (raw, limit) { var q = norm(raw); return q ? matchBrands(q, limit || 12) : []; },
    /* Header suggestions: up to 5 products, 4 categories and 4 brands. */
    suggest: function (raw, ar) {
      var q = norm(raw);
      if (q.length < 2) return Promise.resolve({ q: raw, products: [], cats: [], brands: [] });
      return loadIndex().then(function (list) {
        return { q: raw, products: matchProducts(list, q, 5), cats: matchCats(q, ar, 4), brands: matchBrands(q, 4) };
      });
    },
    /* Search page: wider limits. */
    search: function (raw, ar) {
      var q = norm(raw);
      if (!q) return Promise.resolve({ q: raw, products: [], cats: [], brands: [] });
      return loadIndex().then(function (list) {
        return { q: raw, products: matchProducts(list, q, 200), cats: matchCats(q, ar, 24), brands: matchBrands(q, 12) };
      });
    }
  };
})();
