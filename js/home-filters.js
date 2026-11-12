/* Velmach Aerospace: home page Part Search filters (Aircraft, Brand, Category and Condition under the hero search).
   Options: data/aircraft.js (every model, grouped by maker), data/brands.js (every brand, A-Z) and data/categories.js;
   both lists are managed on admin.html. data/catalog/meta.json gives the product count shown next to an option; an
   aircraft or brand with no products yet is still offered (the search page then offers to source the part).
   Once a filter is picked, the search index (VM_SEARCH.index()) is loaded and the counts follow the choice.
   Aircraft and Brand get a searchable list laid over their <select>; the select keeps the value and is what submits.
   Condition chips (NE NS OH SV RP OR AR) can be combined; they fill the hidden "cond" input.
   The form submits to search.dc.html?q=&ac=<aircraft id>&brand=<brand slug>&sub=<subcategory>&cond=ne,ns, where the
   listing applies the same filters (ProductListing.dc.html) and a quote request carries the conditions. */
(function () {
  var form = document.querySelector('[data-home-filters]');
  if (!form) return;
  var root = form.closest('form');
  var sels = { ac: form.querySelector('[data-hf="ac"]'), brand: form.querySelector('[data-hf="brand"]'), sub: form.querySelector('[data-hf="sub"]') };
  var GET = { ac: function (c) { return c.a || []; }, brand: function (c) { return c.bs ? [c.bs] : []; }, sub: function (c) { return c.c ? [c.c] : []; } };
  var condBox = root.querySelector('[data-home-cond]'), condInput = condBox && condBox.querySelector('input[name="cond"]');
  var chips = condBox ? [].slice.call(condBox.querySelectorAll('[data-cond]')) : [];
  var meta = null, cards = null, loading = false, combos = {};
  // Aircraft and Brand hold hundreds of options: they are built the first time their list opens (page speed)
  var full = { ac: false, brand: false, sub: true };

  function ready() { return window.VM && window.VM_I18N && window.VM_CATS && window.VM_BRANDS && window.VM_AIRCRAFT; }
  function pickedConds() { return chips.filter(function (b) { return b.getAttribute('aria-pressed') === 'true'; }).map(function (b) { return b.dataset.cond; }); }

  // every option with its total from meta.json ({v, l, n, g: group label for aircraft})
  function options(dim) {
    var VM = window.VM, out = [], az = function (a, b) { return a.localeCompare(b, VM.lang, { numeric: true, sensitivity: 'base' }); };
    if (dim === 'ac') {
      window.VM_AIRCRAFT.slice().sort(function (a, b) { return az(a.make, b.make); }).forEach(function (m) {
        m.models.slice().sort(az).forEach(function (model) {
          var id = VM.acId(m.make, model);
          out.push({ v: id, l: model, full: m.make + ' ' + model, g: m.make, n: (meta.aircraft || {})[id] || 0 });
        });
      });
      return out;
    }
    if (dim === 'brand') {
      window.VM_BRANDS.forEach(function (b) { out.push({ v: b.slug, l: b.name, full: b.name, n: (meta.brands || {})[b.slug] || 0 }); });
      return out.sort(function (a, b) { return az(a.l, b.l); });
    }
    window.VM_CATS.forEach(function (p) { p.children.forEach(function (c) { out.push({ v: c.slug, l: VM.label(c), full: VM.label(c), n: ((meta.categories[p.slug] || {}).c || {})[c.slug] || 0 }); }); });
    return out.filter(function (o) { return o.n > 0; }).sort(function (a, b) { return az(a.l, b.l); });
  }

  // counts for one filter given the values picked in the others (needs the search index)
  function liveCounts(dim) {
    var n = {}, conds = pickedConds();
    cards.forEach(function (c) {
      for (var k in sels) if (k !== dim && sels[k].value && GET[k](c).indexOf(sels[k].value) < 0) return;
      if (conds.length && conds.indexOf(c.k) < 0) return;
      GET[dim](c).forEach(function (v) { n[v] = (n[v] || 0) + 1; });
    });
    return n;
  }

  function render() {
    if (!meta) return;
    var t = window.VM.t(), all = { ac: t.hf_all_ac, brand: t.hf_all_brand, sub: t.hf_all_cat };
    var picked = sels.ac.value || sels.brand.value || sels.sub.value || pickedConds().length;
    Object.keys(sels).forEach(function (dim) {
      var el = sels[dim], cur = el.value, live = null, group = null, groupName = null;
      if (!full[dim] && !cur) {
        if (!el.options.length || el.options[0].text !== all[dim]) { el.innerHTML = ''; el.appendChild(new Option(all[dim], '')); }
        if (combos[dim]) combos[dim].sync();
        return;
      }
      live = cards && picked ? liveCounts(dim) : null;
      el.innerHTML = '';
      el.appendChild(new Option(all[dim], ''));
      options(dim).forEach(function (o) {
        var n = live ? live[o.v] || 0 : o.n, opt = new Option(o.l + (n ? ' (' + n + ')' : ''), o.v);
        opt.dataset.full = o.full; opt.dataset.n = n;
        // category keeps its "has products" rule; aircraft and brands are all offered
        if (dim === 'sub') opt.disabled = !n && o.v !== cur;
        if (o.g) {
          if (o.g !== groupName) { groupName = o.g; group = document.createElement('optgroup'); group.label = o.g; el.appendChild(group); }
          group.appendChild(opt);
        } else el.appendChild(opt);
      });
      el.value = cur;
      if (combos[dim]) combos[dim].sync();
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

  /* Searchable list over a <select>: a button shows the choice; opening it shows a search box and the options
     (grouped like the select's optgroups). Keyboard: arrows move, Enter picks, Escape closes. */
  var uid = 0;
  function combo(sel) {
    var id = 'hfc' + (++uid), labelId = sel.getAttribute('aria-labelledby');
    var box = document.createElement('div'); box.className = 'pcb';
    box.innerHTML = '<button type="button" class="pcb-btn" aria-haspopup="listbox" aria-expanded="false"><span class="pcb-val"></span></button>' +
      '<div class="pcb-pop" hidden><input class="pcb-q" type="search" autocomplete="off" spellcheck="false" role="combobox" aria-expanded="true" aria-autocomplete="list" aria-controls="' + id + '">' +
      '<ul class="pcb-list" role="listbox" id="' + id + '"></ul></div>';
    sel.parentNode.insertBefore(box, sel);
    sel.classList.add('pcb-native'); sel.tabIndex = -1; sel.setAttribute('aria-hidden', 'true');
    var btn = box.querySelector('.pcb-btn'), val = box.querySelector('.pcb-val'), pop = box.querySelector('.pcb-pop');
    var q = box.querySelector('.pcb-q'), list = box.querySelector('.pcb-list'), items = [], active = -1;
    if (labelId) { btn.setAttribute('aria-labelledby', labelId + ' ' + id + 'v'); val.id = id + 'v'; q.setAttribute('aria-labelledby', labelId); list.setAttribute('aria-labelledby', labelId); }

    function sync() {
      var o = sel.options[sel.selectedIndex];
      val.textContent = o ? (o.value ? o.dataset.full || o.text : o.text) : '';
      box.classList.toggle('is-set', !!sel.value);
    }
    function build() {
      var term = q.value.trim().toLowerCase(), html = [], n = 0;
      items = [];
      [].forEach.call(sel.children, function (node) {
        var opts = node.tagName === 'OPTGROUP' ? [].slice.call(node.children) : [node];
        var gMatch = node.tagName === 'OPTGROUP' && term && node.label.toLowerCase().indexOf(term) > -1;
        var shown = opts.filter(function (o) {
          if (!term) return true;
          if (!o.value) return false;
          return gMatch || (o.dataset.full || o.text).toLowerCase().indexOf(term) > -1;
        });
        if (!shown.length) return;
        if (node.tagName === 'OPTGROUP') html.push('<li class="pcb-g" role="presentation">' + esc(node.label) + '</li>');
        shown.forEach(function (o) {
          var on = o.value === sel.value, cnt = +o.dataset.n || 0;
          html.push('<li class="pcb-o' + (o.disabled ? ' is-off' : '') + '" role="option" id="' + id + 'o' + n + '" aria-selected="' + on + '"' + (o.disabled ? ' aria-disabled="true"' : '') + ' data-i="' + n + '">' +
            '<span>' + esc(o.value ? o.text.replace(/ \(\d+\)$/, '') : o.text) + '</span>' + (cnt ? '<small>' + cnt + '</small>' : '') + '</li>');
          items.push(o); n++;
        });
      });
      if (!items.length) html.push('<li class="pcb-none" role="presentation">' + esc(window.VM.t().hf_none || 'No match') + '</li>');
      list.innerHTML = html.join('');
      var cur = -1; items.forEach(function (o, i) { if (o.value === sel.value) cur = i; });
      move(term ? 0 : Math.max(cur, 0), true);
    }
    function move(i, keep) {
      var els = list.querySelectorAll('.pcb-o');
      if (!els.length) { active = -1; q.removeAttribute('aria-activedescendant'); return; }
      active = Math.max(0, Math.min(els.length - 1, i));
      [].forEach.call(els, function (e, j) { e.classList.toggle('is-act', j === active); });
      q.setAttribute('aria-activedescendant', els[active].id);
      var e = els[active], top = e.offsetTop, bottom = top + e.offsetHeight;
      if (top < list.scrollTop) list.scrollTop = top - (keep ? 40 : 0);
      else if (bottom > list.scrollTop + list.clientHeight) list.scrollTop = bottom - list.clientHeight + (keep ? 40 : 0);
    }
    function pick(i) {
      var o = items[i]; if (!o || o.disabled) return;
      sel.value = o.value; sel.dispatchEvent(new Event('change', { bubbles: true }));
      close(true);
    }
    function open() {
      if (!pop.hidden) return;
      loadCards();
      var dim = sel.getAttribute('data-hf');
      if (!full[dim]) { full[dim] = true; render(); }
      // the hero clips overflow: open upwards when there is not enough room below
      var hero = box.closest('.hero') || document.body, r = btn.getBoundingClientRect(), h = hero.getBoundingClientRect();
      var below = h.bottom - r.bottom - 12, above = r.top - h.top - 12, up = below < 260 && above > below;
      box.classList.toggle('is-up', up);
      pop.style.setProperty('--pcb-max', Math.max(160, Math.min(340, up ? above : below) - 56) + 'px');
      pop.hidden = false; btn.setAttribute('aria-expanded', 'true'); box.classList.add('is-open');
      q.value = ''; q.placeholder = window.VM.t().hf_search_ph || ''; build(); q.focus();
      document.addEventListener('pointerdown', outside, true);
    }
    function close(focus) {
      if (pop.hidden) return;
      pop.hidden = true; btn.setAttribute('aria-expanded', 'false'); box.classList.remove('is-open');
      document.removeEventListener('pointerdown', outside, true);
      if (focus) btn.focus();
    }
    function outside(e) { if (!box.contains(e.target)) close(false); }
    btn.addEventListener('click', function () { if (pop.hidden) open(); else close(true); });
    btn.addEventListener('keydown', function (e) { if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); open(); } });
    btn.addEventListener('focus', loadCards, { once: true });
    q.addEventListener('input', build);
    q.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); move(active + 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); move(active - 1); }
      else if (e.key === 'Home' && !q.value) { e.preventDefault(); move(0); }
      else if (e.key === 'End' && !q.value) { e.preventDefault(); move(items.length - 1); }
      else if (e.key === 'Enter') { e.preventDefault(); pick(active); }
      else if (e.key === 'Escape') { e.preventDefault(); close(true); }
      else if (e.key === 'Tab') close(false);
    });
    list.addEventListener('mousedown', function (e) { e.preventDefault(); });   // keep focus in the search box
    list.addEventListener('click', function (e) { var li = e.target.closest('.pcb-o'); if (li) pick(+li.dataset.i); });
    list.addEventListener('mousemove', function (e) { var li = e.target.closest('.pcb-o'); if (li && +li.dataset.i !== active) move(+li.dataset.i); });
    sync();
    return { sync: sync };
  }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

  function setChips() {
    var t = window.VM && window.VM_I18N ? window.VM.t() : null;
    chips.forEach(function (b) {
      if (t && t.cond && t.cond[b.dataset.cond]) b.title = b.dataset.cond.toUpperCase() + ' – ' + t.cond[b.dataset.cond];
    });
    if (condInput) condInput.value = pickedConds().join(',');
  }

  function start() {
    if (!ready()) { setTimeout(start, 40); return; }
    combos.ac = combo(sels.ac); combos.brand = combo(sels.brand);
    chips.forEach(function (b) {
      b.addEventListener('click', function () {
        b.setAttribute('aria-pressed', String(b.getAttribute('aria-pressed') !== 'true'));
        setChips(); loadCards(); render();
      });
    });
    setChips();
    window.VM.subscribe(setChips);
    fetch('data/catalog/meta.json').then(function (r) { return r.json(); }).then(function (m) {
      meta = m; render();
      var lang = window.VM.lang;
      window.VM.subscribe(function () { if (window.VM.lang !== lang) { lang = window.VM.lang; render(); } });   // option names follow the language
    }).catch(function () { form.hidden = true; });
    Object.keys(sels).forEach(function (k) {
      sels[k].addEventListener('change', function () { loadCards(); render(); });
      sels[k].addEventListener('focus', loadCards, { once: true });
    });
    // leave unused filters out of the URL
    root.addEventListener('submit', function () {
      var off = Object.keys(sels).map(function (k) { return sels[k]; }).concat(condInput ? [condInput] : []);
      off.forEach(function (el) { el.disabled = !el.value; });
      setTimeout(function () { off.forEach(function (el) { el.disabled = false; }); }, 0);
    });
  }
  start();
})();
