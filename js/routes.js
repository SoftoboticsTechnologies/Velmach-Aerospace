/* Velmach Aerospace: URLs and page metadata for the catalogue and the blog.
   Today pages use query URLs (product.dc.html?p=<slug>, blog.dc.html?a=<slug>), which work on any static host and from file://.
   To switch to clean URLs (/products/<slug>, /blogs/<slug>): configure the host to serve product.dc.html for /products/*
   and blog.dc.html for /blogs/*, serve the site from the domain root (asset paths become root-relative), then set CLEAN = true.
   Both URL styles keep resolving because slugFrom() reads either form. */
(function () {
  if (window.VM_ROUTES) return;
  var CLEAN = false;
  // TODO: replace canonical domain (same placeholder as the page heads and sitemaps)
  var SITE = 'https://www.velmachaerospace.com/';
  var enc = encodeURIComponent;
  function withLang(url, ar) { return ar ? url + (url.indexOf('?') > -1 ? '&' : '?') + 'lang=ar' : url; }
  function root(path) { return CLEAN ? '/' + path : path; }

  var R = window.VM_ROUTES = {
    clean: CLEAN, site: SITE,
    asset: function (path) { return path ? root(path) : ''; },
    // the catalogue now starts at the category pages; an old category id maps to the closest new category
    products: function (ar, cat) { return withLang(root(cat && window.VM ? window.VM.legacyCatHref(cat) : 'categories.dc.html'), ar); },
    product: function (id, ar) { return withLang(CLEAN ? '/products/' + enc(id) : 'product.dc.html?p=' + enc(id), ar); },
    blogs: function (ar, cat) { return withLang(CLEAN ? '/blogs' + (cat ? '?cat=' + enc(cat) : '') : 'blogs.dc.html' + (cat ? '?cat=' + enc(cat) : ''), ar); },
    blog: function (slug, ar) { return withLang(CLEAN ? '/blogs/' + enc(slug) : 'blog.dc.html?a=' + enc(slug), ar); },
    home: function (ar) { return withLang(root('index.html'), ar); },
    // canonical URLs use the deployed names (.html), as in the other pages and the sitemaps
    canonical: {
      product: function (id) { return SITE + (CLEAN ? 'products/' + enc(id) : 'product.html?p=' + enc(id)); },
      blogs: function () { return SITE + (CLEAN ? 'blogs' : 'blogs.html'); },
      blog: function (slug) { return SITE + (CLEAN ? 'blogs/' + enc(slug) : 'blog.html?a=' + enc(slug)); },
      // catalogue navigation; path is "parent" or "parent/child"
      categories: function () { return SITE + (CLEAN ? 'categories' : 'categories.html'); },
      category: function (path) { return SITE + (CLEAN ? 'c/' + path : 'category.html?c=' + path); },
      brands: function () { return SITE + (CLEAN ? 'brands' : 'brands.html'); },
      brand: function (slug) { return SITE + (CLEAN ? 'brand/' + enc(slug) : 'brand.html?b=' + enc(slug)); },
      page: function (slug) { return SITE + (CLEAN ? enc(slug) : 'page.html?p=' + enc(slug)); }
    },
    abs: function (path) { return /^https?:/.test(path) ? path : SITE + String(path).replace(/^\//, ''); },
    // slug of the current page from ?p= / ?a= or from a clean /products/<slug> / /blogs/<slug> path
    slugFrom: function (kind) {
      var q = new URLSearchParams(location.search).get(kind === 'product' ? 'p' : 'a');
      if (q) return q;
      var m = location.pathname.match(kind === 'product' ? /\/products\/([^\/?#]+)\/?$/ : /\/blogs\/([^\/?#]+)\/?$/);
      return m ? decodeURIComponent(m[1]) : '';
    },
    // per-page head: title, description, canonical, Open Graph, robots and one JSON-LD block
    head: function (o) {
      function el(sel, make) { var e = document.head.querySelector(sel); if (!e) { e = make(); document.head.appendChild(e); } return e; }
      function meta(key, attr, val) {
        var e = el('meta[' + attr + '="' + key + '"]', function () { var m = document.createElement('meta'); m.setAttribute(attr, key); return m; });
        if (val == null) e.remove(); else e.setAttribute('content', val);
      }
      document.title = o.title;
      meta('description', 'name', o.description);
      meta('robots', 'name', o.noindex ? 'noindex' : null);
      meta('og:title', 'property', o.title); meta('og:description', 'property', o.description);
      meta('og:type', 'property', o.type || 'website'); meta('og:url', 'property', o.url || null);
      meta('og:image', 'property', o.image || null);
      meta('article:published_time', 'property', o.published || null);
      var c = document.head.querySelector('link[rel="canonical"]');
      if (o.url) { if (!c) { c = document.createElement('link'); c.rel = 'canonical'; document.head.appendChild(c); } c.href = o.url; } else if (c) c.remove();
      var ld = document.getElementById('vm-ld');
      if (o.ld) { if (!ld) { ld = document.createElement('script'); ld.id = 'vm-ld'; ld.type = 'application/ld+json'; document.head.appendChild(ld); } ld.textContent = JSON.stringify(o.ld); }
      else if (ld) ld.remove();
    }
  };
})();
