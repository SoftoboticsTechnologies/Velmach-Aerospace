/* Velmach Aerospace: site-wide settings for the header (contact details, service links).
   Edit the values here; every page picks them up. Text has an English (en) and Arabic (ar) version. */
window.VM_CONFIG = {
  phone: { display: "+971 50 925 9286", tel: "+971509259286" },
  email: { sales: "sales@velmachaerospace.com", aog: "AOG@velmachaerospace.com", info: "info@velmachaerospace.com" },

  // Request for Quote sending. With endpoint empty, the visitor's email app opens with the request filled in.
  // To send from the page instead (with file attachments and an automatic reply to the customer), create a form at a
  // form service such as Formspree (formspree.io) that delivers to the address below, and paste its URL as endpoint,
  // e.g. "https://formspree.io/f/abcdwxyz". Auto-reply is switched on in that service's settings.
  rfq: { endpoint: "", to: "sales@velmachaerospace.com" },

  // Clean URLs (/c/<category>, /p/<product>, /brand/<brand>, /quote ...). Turn on only after the host has the rewrite
  // rules in _redirects (Netlify), vercel.json (Vercel) or .htaccess (Apache); with false the site links to the
  // .dc.html pages, which work on any host. Incoming clean URLs work either way once the rules are installed.
  cleanUrls: false,

  // Product index for the search suggestions and search page, written by scripts/build-catalog.py.
  searchIndex: "data/catalog/search.json",

  // Services mega menu cards (image paths are relative to the site root).
  services: [
    { id: "gse-service-repair", href: "page.dc.html?p=gse-service-repair", img: "assets/header/svc-gse-repair.webp" },
    { id: "mobile-service-team", href: "page.dc.html?p=mobile-service-team", img: "assets/header/svc-mobile-team.webp" },
    { id: "calibration", href: "page.dc.html?p=calibration", img: "assets/header/svc-calibration.webp" },
    { id: "rentals", href: "page.dc.html?p=rentals", img: "assets/header/svc-rentals.webp" },
    { id: "sell-trade", href: "page.dc.html?p=sell-trade", img: "assets/header/svc-sell-trade.webp" },
    { id: "financing", href: "page.dc.html?p=financing", img: "assets/header/svc-financing.webp" },
    { id: "about", href: "about.dc.html", img: "assets/header/svc-about.webp" }
  ]
};
