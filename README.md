# Velmach Aerospace website (v2)

Bilingual (EN / AR) site for VELMACH AEROSPACE F.Z.C. Pages in this project are Design Components (`*.dc.html`), each opening directly in a browser.

## Pages
- index.html (Home), about.dc.html, industries.dc.html, services.dc.html, quality.dc.html, rfq.dc.html (quote list), contact.dc.html, 404.dc.html
- Catalogue: categories.dc.html (all categories), `category.dc.html?c=<parent>` and `?c=<parent>/<child>` (listing), `product.dc.html?p=<slug>` (product), brands.dc.html (A–Z, `?l=<letter>`), `brand.dc.html?b=<slug>`, `search.dc.html?q=<text>`, aircraft.dc.html (Shop by Aircraft), rfq.dc.html (quote list, /quote)
- cart.html and checkout.html only forward to the quote list: there is no cart, checkout or price anywhere on the site
- Service placeholder pages: `page.dc.html?p=<slug>` for calibration, gse-service-repair, mobile-service-team, rentals, sell-trade, financing and account (text in js/i18n.js under `pg`; review it before launch)
- products.dc.html is now a redirect: `?q=`/`?pn=`/`?kw=` open the search, `?cat=` opens the closest new category, anything else opens categories.dc.html
- Shared parts: SiteHeader.dc.html (see Header below), SiteFooter.dc.html, RfqPanel.dc.html (quote list + form, used in the header panel and on rfq.dc.html), ProductListing.dc.html (product listing with filters, used by the category, brand and search pages), RfqModal.dc.html (Request for Quote form for one product)
- Other pages are still client-rendered Design Components. Without JavaScript they show nothing useful, and the browser briefly parses their raw template (console 404s for `{{ img }}` URLs on product/blog pages). Converting them like index.html removes this.

## Home page (index.html)
- index.html is plain, complete HTML (English), so it reads correctly before or without JavaScript, in link previews and for crawlers. Only the shared header (with the RFQ panel) and footer are rendered by the DC runtime.
- Text comes from js/i18n.js: elements carry `data-t="key.path"` (text) or `data-t-attr="attr:key"` (attributes). js/home.js applies the visitor's language at runtime; `node tools/prerender-home.mjs` writes the English strings into index.html. Run it after changing home strings (`--check` reports missing keys, out-of-date text, or list items in i18n.js that the page does not show yet).
- Styles: css/home.css (design tokens at the top). Images: assets/home/ (catalogue product photos and the region map). `python tools/build-home-map.py` regenerates assets/home/region-map.svg from Natural Earth land data.

## Header (SiteHeader.dc.html)
Every page imports it. From top to bottom:
- Utility bar (1200px and wider): AOG desk, then Calibration, GSE Service & Repair, Rent, Sell / Trade, Contact Us and the phone number (`phone` in js/site-config.js).
- Main row: logo (the square mark below 760px), search with live suggestions, Shop by Aircraft, the quote list button (cart icon) with its item count and the Request Quote button ("RFQ" below 760px). Both open the RFQ panel.
- Navigation (1200px and wider): one mega menu per category in data/categories.js (`nav: true`), then Shop by Brand, Services (cards from `services` in js/site-config.js), Blog and Shop All. Menus open on hover after 150 ms and close on mouse leave or Esc. Keyboard: Tab between items, Enter follows the link, ArrowDown or Space opens the menu and moves into it, ArrowUp/ArrowDown move inside it, ArrowLeft/ArrowRight/Home/End move between items, Esc closes and returns focus.
- Below 1200px: a hamburger opens a side drawer (Shop by Category accordion, Shop by Brand, Shop by Aircraft, Services, Calibration, Rentals, Contact Us, phone, Sign In), and the search sits on its own row under the header.
- Search suggestions (js/search.js) wait 300 ms after typing and show matching products, categories and brands; Enter opens search.dc.html. Products come from `searchIndex` in js/site-config.js (data/catalog/search.json).
- Shop by Aircraft: makes and models come from data/aircraft.js. Saved aircraft and the current one are kept in localStorage `vm_aircraft`; `VM.fitsAircraft(product)` in js/vm-core.js tells listings whether a product fits (a product with an empty compatibleAircraft list always fits). Dropdown on desktop, full screen below 1200px.
- The header measures its own height: it sets the page spacer and the `--hdr` CSS variable (used by the home hero).

## Categories and brands
- data/categories.js holds the category tree: EN + AR names, a short EN + AR description (`desc_en`, `desc_ar`, shown on category pages and in the menus) and URL slugs. Keep a slug once it is published; `nav: false` keeps a category off the header. The tree holds only categories and subcategories that have products: when one is emptied, delete it here (old full tree: backup/categories-before-prune-2026-10-13.js), otherwise build-catalog.py publishes an empty listing for it.
- data/brands.js is rewritten by the catalogue build: every brand that has products, nothing else. `featured: true` (set by hand) puts a brand first in the header menu and the home brand strip. Put each logo in public/brands/ as `<slug>.svg` (or `.png` / `.webp`) and rebuild: the build writes its path into `logo`. Brand tiles show the logo above the name; a brand without a logo file shows its name only.

## Product catalogue
The catalogue is static: no server or database. Products are imported from a spreadsheet into a store file, and a build step writes the small JSON files the pages load.

**Product fields** (one line per product in data/catalog/products.jsonl, keyed by part number + brand): id, slug, title, partNumber, brand, categoryParent, categoryChild, shortDescription, description (HTML, cleaned on import), specifications (name/value list), images (400 px thumbnail + 1200 px large WebP), documents (label + PDF), compatibleAircraft (ids from data/aircraft.js; empty = fits every aircraft), condition (New / Used), sample. There is no price field.

**Import:** `python scripts/import-products.py data/products.csv --category pilot-supplies` (CSV or JSON; `--category` imports one top-level category per batch; run with `--help` for every option).
- Columns: title*, partNumber*, brand*, categoryParent*, categoryChild, shortDescription, description, specifications, images, documents, compatibleAircraft, condition, sourceUrl, slug, sample (* required). Common header variants work (part_number, manufacturer, category, subcategory...). Price, cost or currency columns are never imported; the report lists them as ignored. samples/products.sample.csv is a complete example.
- Lists in a CSV cell use `|`: specifications `Capacity: 12 t | Weight: 85 kg`, images `https://.../a.jpg | samples/images/b.png`, documents `Datasheet::https://.../ds.pdf`, compatibleAircraft `boeing/737-ng | Airbus A320`.
- Categories match by slug or English name. A brand that is not in data/brands.js yet is added.
- Images are downloaded (or copied from a local path) in the order the row lists them, at most one download per second (`--rate`), into `images/products/<part-number>/<part-number>-1.jpg`, `-2.jpg` ... at the original resolution (a JPEG is kept as is; other formats are saved as JPEG). Each also gets a 1200 px display copy (`display/`) and a 400 px thumbnail (`thumbs/`) in WebP for fast pages. Nothing is hotlinked, and a product without images keeps the site's "no image" state: nothing is substituted. Characters a file name cannot hold (/, :, spaces...) become `-`; when two brands share a part number the second folder gets `-<brand>`. PDFs go to `images/products/<part-number>/docs/` (`--link-documents` keeps the links instead).
- After each run: `reports/missing-images.csv` (products of that run with no image, and why) and `reports/import-report-<category>-<date>.md` (rows in the file vs products imported per category and subcategory, products without images, failed and skipped rows with the reason, and 10 random products with their product page, first image and sourceUrl for checking).
- Re-running the same file changes nothing: rows are upserted by part number + brand, an empty cell keeps the stored value, and images already converted are not downloaded again. A product's URL slug never changes once assigned.
- Problems (unknown category, missing brand, failed download, unknown aircraft) go to reports/import-errors.log with the row number; the import carries on.
- Progress is saved every 20 seconds. If an import stops, run the same command again and it resumes; `--restart` starts from the first row.
- Measured on this machine: 10,000 rows without images import and build in about 10 seconds. Image downloads depend on the source servers (`--workers` sets how many run at once, default 6).

**Build:** the importer runs `python scripts/build-catalog.py` at the end; run it alone after editing data/categories.js or data/brands.js. It writes:
- data/catalog/p/<slug>.json: one product (product page)
- data/catalog/c/<parent>.json and c/<parent>/<child>.json: compact cards for every product in a category, newest first (listing pages fetch one file and show 24/48/96 at a time)
- data/catalog/b/<brand>.json: cards for a brand
- data/catalog/search.json: the card of every product (search suggestions and the search page, which filters it like a category; about 1 MB gzipped at 30,000 products)
- data/catalog/meta.json: product counts per category, subcategory, brand and condition
- data/brands.js, sitemap-products.xml (real products only) and sitemap-categories.xml
Unchanged files are skipped using data/catalog/.build-manifest.json (`--force` rewrites everything). A 30,000-product build takes about a minute the first time and a few seconds when little has changed.

**Sample products:** the 80 `VA-SAMPLE-...` test products were removed on 2026-10-13 (`--remove-samples`). Products without a photo show their name in the image area; there is no placeholder picture.

**Pages:** js/catalog.js loads these files (`VM_CATALOG.meta()`, `.list(parent, child)`, `.brand(slug)`, `.product(slug)`).

## Listing, product page and quotes
- **Listing** (ProductListing.dc.html, on category, brand and search pages): filters for subcategory or category, brand (with a search box when there are many), condition and compatible aircraft, each with live counts; active filter chips and Clear all; sort (Relevance, Name A–Z, Name Z–A, Newest); 24/48/96 per page; grid or list view; pagination. The view is kept in the URL (`?sub= &cat= &brand= &cond= &ac= &sort= &per= &view= &page=`, lists comma-separated), so a filtered page can be shared. Below 1100px the filters open in a drawer. 4 columns on desktop, 3 on tablet, 2 on mobile.
- **Aircraft:** when a visitor picks an aircraft (header panel or aircraft.dc.html), every listing shows only products that fit it plus universal ones, with a "Show all parts" link.
- **Product card:** square image → brand → two-line title → part number → "Enquire Now" (opens the Request for Quote form for that product); the whole card opens the product. Add to Quote List is on the product page. Category pages show subcategory tiles above the listing, with the newest product photo of each subcategory.
- **Product page** (product.dc.html): gallery with thumbnails, a full-screen viewer with zoom (click the image), arrow keys and swipe; brand link, part number, short description, a "Fits your <aircraft>" badge, "Price available on request", quantity, Request for Quote, Add to Quote List and a call link; tabs for Description, Specifications, Documents and Compatible Aircraft (arrow keys move between tabs); related products from the same subcategory and more from the same brand. The page title, description, canonical URL and Product schema (name, image, brand, sku, description; no offers or price) are set per product; sample products are marked noindex.
- **Request for Quote form** (RfqModal.dc.html, from cards and the product page): product, part number and brand filled in; full name, company, email, phone with country code, country, quantity, required-by date, message and an optional attachment; validation, a hidden spam-trap field and a sending state. Name, company, email and phone are remembered for the next request on that browser.
- **Quote list** (rfq.dc.html, /quote): products added from cards or product pages, with images, links, quantities, remove and manual part numbers; one request for everything. The header badge shows the count (localStorage `vm_rfq`).
- **Brands:** brands.dc.html shows every brand A–Z with product counts and a letter filter; brand.dc.html shows the logo, a description (`desc_en` / `desc_ar` in data/brands.js, otherwise built from the brand's categories) and the listing. The home page has two rows of featured brands scrolling in opposite directions (js/brand-strip.js), paused on hover.

## Run locally
Serve the folder with any static server (for example `npx serve .` or `python -m http.server`) and open index.html.

## Shared state
`js/vm-core.js` holds language (localStorage `vm_lang`, URL `?lang=ar|en` wins), the RFQ list (localStorage `vm_rfq`), saved aircraft (localStorage `vm_aircraft`), catalogue link helpers (`VM.catHref`, `VM.productHref`, `VM.brandHref`, `VM.searchHref`, `VM.pageHref`), `VM.requestQuote(product)` (opens the Request for Quote form) and `VM.addToQuote(product, qty)`, breakpoints and reveal-on-scroll. All pages update live when the language or RFQ list changes.

## Previous catalogue (removed)
The previous 2,190-product catalogue is no longer on the site. Its data, images (assets/products/), the old full-site page (Velmach Website.dc.html) and its tools were moved to backup/old-catalogue/; backup/old-products.json is the full export. products.dc.html stays as a redirect so old links still land on the new catalogue.

## Blog
- Articles live in `data/blogs.js` (slug, title, seoTitle, description, date, category, tags, image, excerpt, body blocks: h2 / h3 / p / ul). Adding an entry adds it to the listing, related articles and previous/next links; also add its URL to sitemap.xml.
- Pages: blogs.dc.html (listing: featured article, topic filter, search) and `blog.dc.html?a=<slug>` (article, contents, share links, related articles, BlogPosting schema, Open Graph).
- Featured images are 1200x630 PNGs in `assets/blog/`.

## URLs
The site links to the `.dc.html` pages with query strings (category.dc.html?c=, product.dc.html?p=, brand.dc.html?b=), which work on any static host. Clean URLs are ready:
- Rewrite rules for /categories, /c/<parent>, /c/<parent>/<child>, /p/<slug>, /brands, /brand/<slug>, /aircraft, /search, /quote, /contact and the service pages (/calibration, /gse-service-repair, /mobile-service-team, /rentals, /rent, /sell-trade, /financing, /account) are in `_redirects` (Netlify), `vercel.json` (Vercel) and `.htaccess` (Apache). They also send /cart and /checkout to /quote (301).
- With the rules installed, clean URLs work when typed or shared. Set `cleanUrls: true` in js/site-config.js to make the site link to them too. The site must be served from the domain root.
- Category, product and brand pages start with a one-line script that sets `<base href="/">` on nested clean URLs, so their files load from the root. The browser's preloader may still request a few files at the nested path first (harmless 404s in the network log).
- `js/routes.js` builds canonical URLs and blog links; its `CLEAN` flag covers the blog.

## Translations
All strings live in `js/i18n.js` under `en` and `ar`. The v2 block at the end of the file adds redesign strings.

## RFQ / contact submission
By default both quote forms open the visitor's email app (mailto) with the request filled in, including product links; AOG priority goes to AOG@ with sales@ in CC. To send from the page instead, create a form at a form service such as Formspree that delivers to sales@velmachaerospace.com and paste its URL as `rfq.endpoint` in js/site-config.js. Then requests are posted directly, the Request for Quote form accepts an attachment (up to 10 MB), and the service can send the customer an automatic reply (set up in the service). There is no server, so requests are not stored in a database; the form service keeps a copy of each submission.

## TODO checklist (search the code for "TODO: replace")
- Official white / reversed logo for the footer
- Office, team, manager, industry and product photographs
- PDFs in /docs: certificate-of-incorporation.pdf, commercial-registry-certificate.pdf, corporate-tax-certificate.pdf, iso-9001-certificate.pdf, and document thumbnails
- Google Maps embed (contact page)
- Business hours
- Social links (LinkedIn, X, Instagram)
- Canonical domain in page heads, sitemap.xml and robots.txt
- Real catalogue data replacing VA-SAMPLE entries
- Brand logo SVGs in public/brands/
- Review the service placeholder page text (js/i18n.js, `pg`)
- Remove the sample products before launch (`python scripts/import-products.py --remove-samples`)
