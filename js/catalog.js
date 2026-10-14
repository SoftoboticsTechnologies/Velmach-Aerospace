/* Velmach Aerospace: loads the catalogue files written by scripts/build-catalog.py (data/catalog/).
   Every call returns a Promise and each file is fetched once per page.
     VM_CATALOG.meta()                  counts per category, subcategory, brand, condition and aircraft
     VM_CATALOG.list(parent, child)     compact cards for a category or subcategory, newest first
     VM_CATALOG.brand(slug)             compact cards for a brand
     VM_CATALOG.product(slug)           one product with every field (null when it does not exist)
   Card fields: s slug, t title, pn part number, b brand, bs brand slug, p category, c subcategory, k "new"/"used",
   i thumbnail, d date added, a compatible aircraft ids (absent = fits all), x 1 for sample products. */
(function () {
  if (window.VM_CATALOG) return;
  var BASE = 'data/catalog/', cache = {};
  function get(path, fallback) {
    if (!cache[path]) cache[path] = fetch(BASE + path).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .catch(function () { delete cache[path]; return fallback; });
    return cache[path];
  }
  var enc = encodeURIComponent;
  window.VM_CATALOG = {
    meta: function () { return get('meta.json', { total: 0, categories: {}, brands: {}, conditions: {}, aircraft: {} }); },
    list: function (parent, child) { return get('c/' + enc(parent) + (child ? '/' + enc(child) : '') + '.json', []); },
    brand: function (slug) { return get('b/' + enc(slug) + '.json', []); },
    product: function (slug) { return get('p/' + enc(slug) + '.json', null); },
    /* products a category page shows when an aircraft is selected (VM.fitsAircraft reads card field a) */
    fits: function (cards) { var VM = window.VM; return VM ? cards.filter(function (c) { return VM.fitsAircraft({ compatibleAircraft: c.a }); }) : cards; }
  };
})();
