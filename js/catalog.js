/* Velmach Aerospace: loads the catalogue files written by scripts/build-catalog.py (data/catalog/).
   Every call returns a Promise and each file is fetched once per page.
     VM_CATALOG.meta()                  counts per category, subcategory, brand, condition and aircraft
     VM_CATALOG.all()                   compact cards of every product (search.json)
     VM_CATALOG.list(parent, child)     compact cards for a category or subcategory, newest first
     VM_CATALOG.brand(slug)             compact cards for a brand
     VM_CATALOG.product(slug)           one product with every field (null when it does not exist)
     VM_CATALOG.rail(id)               the 24-card slice of a list named in a product's "rails" (related products)
   Card fields: s slug, t title, pn part number, b brand, bs brand slug, p category, c subcategory, k "new"/"used",
   i thumbnail, d date added, a compatible aircraft ids (absent = fits all), x 1 for sample products.
   Card files are compact ({f, d, r}, see encode_cards in scripts/build-catalog.py); decode() turns them into card
   objects. A list longer than the build's BIG_LIST is a stub ({src: "all", p, c | bs}) read from search.json. */
(function () {
  if (window.VM_CATALOG) return;
  var BASE = 'data/catalog/', BUCKETS = 4096, cache = {};
  function get(path, fallback, then) {
    if (!cache[path]) cache[path] = fetch(BASE + path).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(then || function (d) { return d; })
      .catch(function () { delete cache[path]; return fallback; });
    return cache[path];
  }
  // compact card file -> card objects (an array of card objects, from an older build, is returned as it is)
  function decode(d) {
    if (Array.isArray(d)) return d;
    if (!d || !d.r) return [];
    var f = d.f, D = d.d, rows = d.r, out = new Array(rows.length);
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i], c = { s: '', t: '', pn: '', b: '', bs: '', p: '', c: '', k: '', i: '', d: '' };
      for (var j = 0; j < row.length; j++) {
        var v = row[j], k = f[j];
        if (!v) continue;
        if (k === 'pc') { c.p = D.pc[v][0]; c.c = D.pc[v][1]; }
        else if (k === 'b') { c.b = D.b[v][0]; c.bs = D.b[v][1]; }
        else if (k === 'a') c.a = D.a[v].split(' ');
        else c[k] = D[k] ? D[k][v] : v;
      }
      out[i] = c;
    }
    return out;
  }
  // FNV-1a 32-bit of the slug, modulo BUCKETS, as 3 hex digits (bucket() in scripts/build-catalog.py)
  function bucket(slug) {
    var h = 0x811c9dc5;
    for (var i = 0; i < slug.length; i++) { h ^= slug.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
    return ('00' + (h % BUCKETS).toString(16)).slice(-3);
  }
  function all() { return get('search.json', [], decode); }
  // a list file, or the cards of search.json it points to
  function cards(path, keep) {
    var key = '=' + path;
    if (!cache[key]) cache[key] = get(path, [], function (d) {
      if (!d || d.src !== 'all') return decode(d);
      return all().then(function (list) { return list.filter(function (c) { return keep(c, d); }); });
    });
    return cache[key];
  }
  var enc = encodeURIComponent;
  window.VM_CATALOG = {
    decode: decode,
    meta: function () { return get('meta.json', { total: 0, categories: {}, brands: {}, conditions: {}, aircraft: {} }); },
    all: all,
    list: function (parent, child) {
      return cards('c/' + enc(parent) + (child ? '/' + enc(child) : '') + '.json', function (c, d) { return c.p === d.p && (!d.c || c.c === d.c); });
    },
    brand: function (slug) { return cards('b/' + enc(slug) + '.json', function (c, d) { return c.bs === d.bs; }); },
    product: function (slug) {
      var one = function (s) { return get('p/' + bucket(String(s || '')) + '.json', null).then(function (m) { return (m && m[s]) || null; }); };
      // a product merged into another (scripts/merge-duplicate-pns.py) is found under the slug it was merged into
      return one(slug).then(function (p) {
        return p || get('moved.json', {}).then(function (mv) { return mv && mv[slug] ? one(mv[slug]) : null; });
      });
    },
    rail: function (id) { return get('r/' + Math.floor(id / 1000) + '/' + id + '.json', [], decode); },
    /* products a category page shows when an aircraft is selected (VM.fitsAircraft reads card field a) */
    fits: function (cards) { var VM = window.VM; return VM ? cards.filter(function (c) { return VM.fitsAircraft({ compatibleAircraft: c.a }); }) : cards; }
  };
})();
