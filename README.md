# Velmach Aerospace website (v2)

Bilingual (EN / AR) site for VELMACH AEROSPACE F.Z.C. Pages in this project are Design Components (`*.dc.html`), each opening directly in a browser.

## Pages
- index.html (Home), about.dc.html, products.dc.html, industries.dc.html, services.dc.html, quality.dc.html, rfq.dc.html, contact.dc.html, 404.dc.html
- Shared parts: SiteHeader.dc.html (utility bar, nav, drawer, RFQ panel, AOG + WhatsApp buttons), SiteFooter.dc.html, RfqPanel.dc.html (RFQ list + form, used in the header panel and on rfq.dc.html)
- Previous version kept as `Velmach Website.dc.html`

## Run locally
Serve the folder with any static server (for example `npx serve .` or `python -m http.server`) and open index.html.

## Shared state
`js/vm-core.js` holds language (localStorage `vm_lang`, URL `?lang=ar|en` wins), the RFQ list (localStorage `vm_rfq`), breakpoints and reveal-on-scroll. All pages update live when the language or RFQ list changes.

## Products
Edit `data/products.js` (used by the site, works from file://). `data/products.json` mirrors it for a future backend. Fields: partNumber, category (parts, lubricants, chemicals, paints, adhesives, tapes, petrochem, oilgas, used, consultancy), condition (new, used, surplus), name_en, name_ar, desc_en, desc_ar.

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
