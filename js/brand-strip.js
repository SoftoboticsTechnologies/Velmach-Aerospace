/* Velmach Aerospace: home page brand strip. Two rows of every brand (data/brands.js, A to Z and Z to A) scroll in opposite
   directions without a seam and pause on keyboard focus; each tile links to its brand page and shows the
   brand's logo (when public/brands/ has one) above its name. With reduced motion the rows stay still and scroll by hand. */
(function () {
  function build() {
    var host = document.querySelector('[data-brand-strip]');
    var VM = window.VM, all = (window.VM_BRANDS || []).slice().sort(function (a, b) { return a.name.localeCompare(b.name); });
    if (!host || !VM || !all.length) return;
    // every brand in both rows: A to Z on the first, Z to A on the second
    var rows = [all, all.slice().reverse()];
    host.innerHTML = '';
    builtW = host.clientWidth;
    rows.forEach(function (list, r) {
      if (!list.length) return;
      var row = document.createElement('div');
      row.className = 'bstrip-row' + (r ? ' bstrip-row--rev' : '');
      var track = document.createElement('ul');
      track.className = 'bstrip-track';
      function add(copy) {
        list.forEach(function (b) {
          var li = document.createElement('li'), a = document.createElement('a');
          a.className = 'bstrip-tile';
          a.href = VM.brandHref(b.slug);
          a.setAttribute('data-brand', b.slug);
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
    paintLogos();
  }
  var builtW = 0, resizeT;
  // a wider strip may need more repeats; rebuild once resizing settles
  function onResize() {
    clearTimeout(resizeT);
    resizeT = setTimeout(function () {
      var host = document.querySelector('[data-brand-strip]');
      if (host && host.clientWidth > builtW) build();
    }, 200);
  }
  // logo above the name; a logo that fails to load is dropped and the name stays
  function paintLogos() {
    document.querySelectorAll('.bstrip-tile[data-brand]').forEach(function (a) {
      var slug = a.getAttribute('data-brand'), src = window.VM.brandLogo(slug);
      if (src && !a.querySelector('img')) {
        var img = new Image();
        img.src = src; img.alt = a.textContent + ' logo'; img.loading = 'lazy';
        if (window.VM.brandLogoDark(slug)) img.className = 'is-dark';
        img.onerror = function () { img.remove(); window.VM.logoFailed(slug); };
        a.insertBefore(img, a.firstChild);
      }
    });
  }
  function start() {
    build();
    if (window.VM) window.VM.subscribe(paintLogos);
    window.addEventListener('resize', onResize);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
