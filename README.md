# Velmach Aerospace website (v2)

Bilingual (EN / AR) site for VELMACH AEROSPACE F.Z.C. Pages in this project are Design Components (`*.dc.html`), each opening directly in a browser.

## Pages
- index.html (Home), about.dc.html, products.dc.html, industries.dc.html, services.dc.html, quality.dc.html, rfq.dc.html, contact.dc.html, 404.dc.html
- Shared parts: SiteHeader.dc.html (utility bar, nav, drawer, RFQ panel, AOG + WhatsApp buttons), SiteFooter.dc.html, RfqPanel.dc.html (RFQ list + form, used in the header panel and on rfq.dc.html)
- Previous version kept as `Velmach Website.dc.html`
- Other pages are still client-rendered Design Components. Without JavaScript they show nothing useful, and the browser briefly parses their raw template (console 404s for `{{ img }}` URLs on product/blog pages). Converting them like index.html removes this.

## Home page (index.html)
- index.html is plain, complete HTML (English), so it reads correctly before or without JavaScript, in link previews and for crawlers. Only the shared header (with the RFQ panel) and footer are rendered by the DC runtime.
- Text comes from js/i18n.js: elements carry `data-t="key.path"` (text) or `data-t-attr="attr:key"` (attributes). js/home.js applies the visitor's language at runtime; `node tools/prerender-home.mjs` writes the English strings into index.html. Run it after changing home strings (`--check` reports missing keys, out-of-date text, or list items in i18n.js that the page does not show yet).
- Styles: css/home.css (design tokens at the top). Images: assets/home/ (catalogue product photos and the region map). `python tools/build-home-map.py` regenerates assets/home/region-map.svg from Natural Earth land data.

## Run locally
Serve the folder with any static server (for example `npx serve .` or `python -m http.server`) and open index.html.

## Shared state
`js/vm-core.js` holds language (localStorage `vm_lang`, URL `?lang=ar|en` wins), the RFQ list (localStorage `vm_rfq`), breakpoints and reveal-on-scroll. All pages update live when the language or RFQ list changes.

## Products
`data/products.json` is the editable catalogue (2,190 products migrated from the supplier catalogue). After editing it, run `python tools/build-products-js.py`: it regenerates `data/products.js` (the compact copy the pages load, works from file://) and `sitemap-products.xml`. Do not edit `data/products.js` by hand.
- Fields: id (URL slug), sourceId, partNumber, sap, category (parts, lubricants, chemicals, cleaners, paints, adhesives, sealants, tapes, other, petrochem, oilgas, used, consultancy), name_en, name_ar, desc_en, desc_ar, stock, image (assets/products/...), sourceImage, condition (new, used, surplus), sourceUrl. Fields the source did not publish are null; empty ones are hidden on the site.
- Listing: products.dc.html (search by part number/SAP code/keyword, category filter, sort, pagination; the view is kept in the URL: `?cat=`, `?pn=`, `?kw=`, `?sort=`, `?page=`).
- Product page: `product.dc.html?p=<id>` (image, specs, RFQ, related products, per-product title/description/canonical/Product schema).
- Images: product images live in `assets/products/`. Products whose image is still pending keep the original URL in `sourceImage`; `python tools/import-product-images.py` imports them politely and stops if the source blocks automated requests.
- Only products.dc.html and product.dc.html load the catalogue; other pages do not.
- Availability: no live inventory data exists, so every product shows "Availability on request". The source's "In Stock" value is kept only as `sourceStock` in products.json.
- Missing images show `assets/img/product-placeholder.svg` with a translated caption; an image that fails to load falls back to it too.
- Internal review flags live in products.json `review` (duplicate-sap, duplicate-part-number, description-truncated-at-source, image-pending, no-image-at-source). Duplicates are kept for manual review. `descSource` keeps the original truncated source text.

## Blog
- Articles live in `data/blogs.js` (slug, title, seoTitle, description, date, category, tags, image, excerpt, body blocks: h2 / h3 / p / ul). Adding an entry adds it to the listing, related articles and previous/next links; also add its URL to sitemap.xml.
- Pages: blogs.dc.html (listing: featured article, topic filter, search) and `blog.dc.html?a=<slug>` (article, contents, share links, related articles, BlogPosting schema, Open Graph).
- Featured images are 1200x630 PNGs in `assets/blog/`.

## URLs
`js/routes.js` builds every product and blog link and canonical URL. Pages use query URLs today (product.dc.html?p=, blog.dc.html?a=). To move to /products/<slug> and /blogs/<slug>, add host rewrites to product.dc.html and blog.dc.html and set `CLEAN = true` in js/routes.js; both URL styles keep working.

## Translations
All strings live in `js/i18n.js` under `en` and `ar`. The v2 block at the end of the file adds redesign strings.

## RFQ / contact submission
Forms open the visitor's email app (mailto). AOG priority goes to AOG@ with sales@ in CC. Commented Formspree and EmailJS code is in RfqPanel.dc.html (submit method).

## TODO checklist (search the code for "TODO: replace")
- Official white / reversed logo for the footer
- Office, team, manager, industry and product photographs
- PDFs in /docs: trade-license.pdf, certificate-of-incorporation.pdf, corporate-tax-certificate.pdf, and document thumbnails
- Google Maps embed (contact page)
- Business hours
- Social links (LinkedIn, X, Instagram)
- Canonical domain in page heads, sitemap.xml and robots.txt
- Real catalogue data replacing VA-SAMPLE entries
