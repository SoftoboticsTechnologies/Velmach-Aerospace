/* Velmach Aerospace: home page catalogue filters (Aircraft, Brand, Category under the hero search).
   Options come from the catalogue itself: data/aircraft.js, data/brands.js and data/categories.js list what has parts,
   and data/catalog/meta.json gives the product count shown next to each option. Once a filter is picked, the search
   index (VM_CONFIG.searchIndex) is loaded and the counts of the other filters follow the choice (Falcon 2000 + Honeywell).
   The form submits to search.dc.html?q=&ac=<aircraft id>&brand=<brand slug>&sub=<subcategory>, where the listing
   applies the same filters (ProductListing.dc.html). */
(function () {
  var form = document.querySelector('[data-home-filters]');
  if (!form) return;
  var sels = { ac: form.querySelector('[data-hf="ac"]'), brand: form.querySelector('[data-hf="brand"]'), sub: form.querySelector('[data-hf="sub"]') };
  var GET = { ac: function (c) { return c.a || []; }, brand: function (c) { return c.bs ? [c.bs] : []; }, sub: function (c) { return c.c ? [c.c] : []; } };
  var meta = null, cards = null, loading = false;

  function ready() { return window.VM && window.VM_I18N && window.VM_CATS && window.VM_BRANDS && window.VM_AIRCRAFT; }

  // every option with its total from meta.json
  function options(dim) {
    var VM = window.VM, out = [];
    if (dim === 'ac') window.VM_AIRCRAFT.forEach(function (m) { m.models.forEach(function (model) { var id = VM.acId(m.make, model); out.push({ v: id, l: m.make + ' ' + model, n: (meta.aircraft || {})[id] || 0 }); }); });
    if (dim === 'brand') window.VM_BRANDS.forEach(function (b) { out.push({ v: b.slug, l: b.name, n: (meta.brands || {})[b.slug] || 0 }); });
    if (dim === 'sub') window.VM_CATS.forEach(function (p) { p.children.forEach(function (c) { out.push({ v: c.slug, l: VM.label(c), n: ((meta.categories[p.slug] || {}).c || {})[c.slug] || 0 }); }); });
    return out.filter(function (o) { return o.n > 0; }).sort(function (a, b) { return a.l.localeCompare(b.l); });
  }

  // counts for one filter given the values picked in the others (needs the search index)
  function liveCounts(dim) {
    var n = {};
    cards.forEach(function (c) {
      for (var k in sels) if (k !== dim && sels[k].value && GET[k](c).indexOf(sels[k].value) < 0) return;
      GET[dim](c).forEach(function (v) { n[v] = (n[v] || 0) + 1; });
    });
    return n;
  }

  function render() {
    if (!meta) return;
    var t = window.VM.t(), all = { ac: t.hf_all_ac, brand: t.hf_all_brand, sub: t.hf_all_cat };
    var picked = sels.ac.value || sels.brand.value || sels.sub.value;
    Object.keys(sels).forEach(function (dim) {
      var el = sels[dim], cur = el.value, live = cards && picked ? liveCounts(dim) : null;
      el.innerHTML = '';
      el.appendChild(new Option(all[dim], ''));
      options(dim).forEach(function (o) {
        var n = live ? live[o.v] || 0 : o.n, opt = new Option(o.l + ' (' + n + ')', o.v);
        opt.disabled = !n && o.v !== cur;
        el.appendChild(opt);
      });
      el.value = cur;
    });
  }

  function loadCards() {
    if (cards || loading) return;
    // the header's search index (js/search.js reads and decodes data/catalog/search.json once for the whole page)
    if (!window.VM_SEARCH) { setTimeout(loadCards, 60); return; }
    loading = true;
    window.VM_SEARCH.index().then(function (d) { cards = d; render(); })
      .catch(function () { loading = false; });
  }

  function start() {
    if (!ready()) { setTimeout(start, 40); return; }
    fetch('data/catalog/meta.json').then(function (r) { return r.json(); }).then(function (m) {
      meta = m; render();
      window.VM.subscribe(render);   // option names follow the language
    }).catch(function () { form.hidden = true; });
    Object.keys(sels).forEach(function (k) {
      sels[k].addEventListener('change', function () { loadCards(); render(); });
      sels[k].addEventListener('focus', loadCards, { once: true });
    });
    // leave unused filters out of the URL
    form.closest('form').addEventListener('submit', function () {
      Object.keys(sels).forEach(function (k) { sels[k].disabled = !sels[k].value; });
      setTimeout(function () { Object.keys(sels).forEach(function (k) { sels[k].disabled = false; }); }, 0);
    });
  }
  start();
})();
