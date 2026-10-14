/* Velmach Aerospace: home page brand strip. Two rows of brands (data/brands.js, featured first) scroll in opposite
   directions without a seam and pause on hover or keyboard focus; each tile links to its brand page and shows the
   brand's logo (when public/brands/ has one) above its name. With reduced motion the rows stay still and scroll by hand. */
(function () {
  function build() {
    var host = document.querySelector('[data-brand-strip]');
    var VM = window.VM, all = (window.VM_BRANDS || []).slice().sort(function (a, b) { return (b.featured ? 1 : 0) - (a.featured ? 1 : 0); });
    if (!host || !VM || !all.length) return;
    var half = Math.ceil(all.length / 2), rows = [all.slice(0, half), all.slice(half)];
    host.innerHTML = '';
    rows.forEach(function (list, r) {
      if (!list.length) return;
      var row = document.createElement('div');
      row.className = 'bstrip-row' + (r ? ' bstrip-row--rev' : '');
      var track = document.createElement('ul');
      track.className = 'bstrip-track';
      // the list twice: the second copy follows the first, so moving by half the width loops seamlessly
      for (var copy = 0; copy < 2; copy++) list.forEach(function (b) {
        var li = document.createElement('li'), a = document.createElement('a');
        a.className = 'bstrip-tile';
        a.href = VM.brandHref(b.slug);
        a.setAttribute('data-brand', b.slug);
        if (copy) { li.setAttribute('aria-hidden', 'true'); a.tabIndex = -1; }
        var n = document.createElement('span'); n.className = 'bstrip-n'; n.textContent = b.name; a.appendChild(n);
        li.appendChild(a); track.appendChild(li);
      });
      track.style.animationDuration = Math.max(28, list.length * 5) + 's';
      row.appendChild(track); host.appendChild(row);
    });
    paintLogos();
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
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
