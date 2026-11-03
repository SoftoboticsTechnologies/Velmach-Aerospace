"""Add products from manufacturers' own product lists: python scripts/import-manufacturer-catalogs.py [--no-build]

Reads data/velmach-staging/manufacturers/<site>.json (written by scripts/fetch-manufacturer-catalogs.py) and adds the
products of brands Velmach supplies. Like scripts/import-all-lists.py it never changes an existing product: a product
already on the site (same part number; or the same name with the same or an unstated brand) is skipped and logged.
Re-running replaces only the products this script added (keys "mfr:").

Taken from the manufacturer's list: product name, part number (SKU / model), brand (the list's vendor, spelled as in
data/supplier-brands.json when it is one of those brands), the manufacturer's own category names ("Listed under") and
the product page (kept as the source, not shown). Not taken: descriptions, prices and photos. A product shows its brand's
logo (public/brands/<slug>.*) or else the Velmach logo, as a logo, not as a photo of the part.
Category: the keyword rules of scripts/extract-documents.py when the name names a product type, else the brand's main
category (DEFAULT_PARENT).
Writes the store, reports/manufacturer-import-<date>.md and reports/manufacturer-import-duplicates.csv, then builds.
"""
import argparse, collections, csv, datetime, html, importlib.util, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_lib as L
import list_sheet_parsers as P

_s = importlib.util.spec_from_file_location('import_all_lists', os.path.join(L.ROOT, 'scripts', 'import-all-lists.py'))
A = importlib.util.module_from_spec(_s); _s.loader.exec_module(A)

SRC = os.path.join(L.ROOT, 'data', 'velmach-staging', 'manufacturers')
REPORTS = os.path.join(L.ROOT, 'reports')
PREFIX = 'mfr:'
SITE_NAMES = {'tronair': 'Tronair', 'startpac': 'Start Pac', 'laversab': 'Laversab', 'itwgse': 'ITW GSE', 'unitron': 'Unitron'}
# main category of a brand's products when the name does not name a product type the keyword rules know
DEFAULT_PARENT = {'laversab': 'aircraft-tooling'}
GSE = 'ground-support-equipment'
SKIP_CATEGORIES = {'oilfield'}          # Laversab's oil-field products are not aviation products
OILFIELD = re.compile(r'\b(rig\W+floor|driller|drilling|witsml|hazloc|hazardous\W+location|zone\W?[12])\b', re.I)   # ... nor uncategorised ones like these


def site_items(name, d):
    """(name, part number, vendor, manufacturer categories, page url) for each product of one site's file."""
    site_brand = SITE_NAMES[name]
    for it in d['items']:
        if name == 'tronair':
            skus = [s for s in it['skus'] if s] or ['']
            for sku, var in zip(skus, it['variants'] + [''] * len(skus)):
                title = it['title']
                if L.norm_key(title) == L.norm_key(sku) or not re.search(r'[A-Za-z]{3}', title):
                    title = it.get('heading') or it.get('type') or title          # the list names some products by number only
                if var and var.lower() not in ('default title', '') and L.norm_key(var) not in L.norm_key(title):
                    title = f'{title} ({var})'
                cats = [c for c in [it.get('type')] if c]
                yield title, sku, it['vendor'] or site_brand, cats, it['url']
        elif name in ('startpac', 'laversab'):
            cats = [c for c in it['categories'] if c and c.lower() not in ('shop now', 'explore laversab products', 'uncategorized', 'compare')]
            aviation = any(c.lower() == 'aviation' for c in it['categories'])
            if not aviation and ({c.lower() for c in it['categories']} & SKIP_CATEGORIES or OILFIELD.search(it['title'])):
                continue
            model = re.search(r'\bmodel\s+([A-Z0-9][\w.-]*\d[\w.-]*)', it['title'], re.I)
            yield it['title'], it.get('sku') or (model.group(1) if model else ''), site_brand, cats, it['url']
        else:
            t = it['title'] or re.split(r'\s+[|–-]\s+', it.get('pageTitle', ''))[0]
            if t:
                yield t, '', site_brand, [], it['url']


WORD = re.compile(r'[a-z]{3,}')


class Existing(A.Existing):
    """Stricter than the list import: a manufacturer's model number ("53200", "3328") can be another maker's part number,
    so a part-number match needs brands that agree or names that share a word, and a match by name needs a specific
    name (one with a model number in it)."""

    def match(self, pn, title, brand):
        kp, kb, words = L.norm_key(pn), L.norm_key(brand), set(WORD.findall(title.lower()))
        r = self.by_pn.get(kp) if kp else None
        if r:
            rb = L.norm_key(r['brand'])
            if rb == kb or words & set(WORD.findall(r['title'].lower())):
                return r, 'same part number'
        if not A.has_model(title):
            return None, ''
        for r in self.by_name.get(L.norm_key(title), []):
            rp, rb = L.norm_key(r['partNumber']), L.norm_key(r['brand'])
            if (not kp or not rp or kp == rp) and (not kb or not rb or kb == rb):
                return r, 'same name' + (' and brand' if kb and rb else '')
        return None, ''


def brand_name(vendor, supplier, from_feed=True):
    k = L.norm_key(vendor)
    if k in supplier:
        return supplier[k]
    for sk, nm in sorted(supplier.items(), key=lambda x: -len(x[0])):
        if len(sk) >= 4 and k.startswith(sk):          # "EAGLE TUGS" -> Eagle, "TRONAIR INC" -> Tronair
            return nm
    return vendor.strip().title() if from_feed and vendor.isupper() else vendor.strip()   # "EAGLE TUGS" -> "Eagle Tugs"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--no-build', action='store_true')
    a = ap.parse_args()
    X = P.X
    supplier = {L.norm_key(b): b for b in L.load_supplier_brands()}
    cats = L.load_categories()
    by_cat = {c['slug']: c for c in cats}

    def cname(parent, child=''):
        if parent not in by_cat:
            return parent + (' > ' + child if child else '')
        c = next((x for x in by_cat[parent]['children'] if x['slug'] == child), None)
        return by_cat[parent]['en'] + (' > ' + c['en'] if c else '')

    old = L.load_store()
    old_added = {k: r for k, r in old.items() if k.startswith(PREFIX)}
    store = {k: r for k, r in old.items() if not k.startswith(PREFIX)}
    existing = Existing(store)
    taken = {r['slug'] for r in store.values()}
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    added, dups, per_site, files = [], [], collections.Counter(), []
    seen = set()
    for f in sorted(os.listdir(SRC)) if os.path.isdir(SRC) else []:
        name = f[:-5]
        if name not in SITE_NAMES:
            continue
        d = json.load(open(os.path.join(SRC, f), encoding='utf-8'))
        n_items = 0
        for title, pn, vendor, mcats, url in site_items(name, d):
            n_items += 1
            title = re.sub(r'\s+', ' ', title).strip()
            if not title:
                continue
            brand = brand_name(vendor, supplier, from_feed=(name == 'tronair'))
            ident = L.norm_key(pn) or (L.norm_key(title) + '|' + L.norm_key(brand))
            if ident in seen:
                dups.append(('merged in the new data', pn, title, f'listed more than once ({SITE_NAMES[name]})', '')); continue
            seen.add(ident)
            hit, why = existing.match(pn, title, brand)
            if hit:
                dups.append(('skipped: already on the website', pn, title, why + f' (brand {brand})',
                             f'{hit["title"]} | {hit["partNumber"]} | product.dc.html?p={hit["slug"]}')); continue
            p = {'title': title, 'description': '', 'partNumber': pn, 'cat_doc': mcats}
            parent, child, _conf, _why = X.categorize(p, cname)
            if not parent or parent not in by_cat:
                parent, child = DEFAULT_PARENT.get(name, GSE), ''
            key = PREFIX + (('pn:' + L.norm_key(pn)) if L.norm_key(pn) else ('name:' + L.norm_key(title) + '|' + L.norm_key(brand)))
            slug = old_added[key]['slug'] if key in old_added and old_added[key]['slug'] not in taken else None
            if not slug:
                base = L.slugify(title if not pn or L.norm_key(pn) in L.norm_key(title) else f'{pn} {title}', 70) or L.slugify(pn) or 'product'
                slug, n = base, 2
                while slug in taken:
                    slug = f'{base}-{n}'; n += 1
            taken.add(slug)
            bslug = L.slugify(brand)
            logo, dark = P.find_logo(bslug)
            specs = [{'name': 'Listed under', 'value': ' / '.join(mcats)}] if mcats else []
            sentence = html.escape(title) + (f', part number {html.escape(pn)}' if pn and L.norm_key(pn) not in L.norm_key(title) else '') + f', by {html.escape(brand)}.'
            rec = {
                'key': key, 'id': L.product_id(key), 'slug': slug, 'pnDir': L.safe_part_number(pn or slug),
                'title': title, 'partNumber': pn, 'altPartNumber': '', 'serialNumber': '',
                'brand': brand, 'brandSlug': bslug, 'brandBasis': 'brand', 'categoryParent': parent, 'categoryChild': child,
                'shortDescription': sentence.replace('&amp;', '&'), 'description': '<p>' + sentence + '</p>',
                'specifications': specs, 'images': [],
                'placeholder': logo if logo and not dark else A.VELMACH_LOGO, 'placeholderKind': 'brand logo' if logo and not dark else 'company logo',
                'documents': [], 'compatibleAircraft': [], 'aircraftListed': '', 'condition': 'New', 'conditionCode': '', 'certification': '',
                'sample': False, 'source': f'{SITE_NAMES[name]} product list ({d.get("fetched", "")})', 'sourceUrl': url,
                'createdAt': (old_added.get(key) or {}).get('createdAt') or now, 'updatedAt': now,
            }
            store[key] = rec
            added.append(rec)
            per_site[SITE_NAMES[name]] += 1
            if L.norm_key(pn):
                existing.by_pn.setdefault(L.norm_key(pn), rec)
            else:
                existing.by_name[L.norm_key(title)].append(rec)
        files.append((f, n_items))
    L.save_store(store)
    write_reports(files, added, dups, per_site)
    print(f'Added {len(added)} products from manufacturers\' lists; {sum(1 for d in dups if d[0].startswith("skipped"))} already on the site; '
          f'{len(old_added) - len([k for k in old_added if k in store])} earlier ones no longer listed were removed.')
    if not a.no_build:
        spec = importlib.util.spec_from_file_location('build_catalog', os.path.join(L.ROOT, 'scripts', 'build-catalog.py'))
        B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B); B.build()


def write_reports(files, added, dups, per_site):
    os.makedirs(REPORTS, exist_ok=True)
    today = datetime.date.today().isoformat()
    with open(os.path.join(REPORTS, 'manufacturer-import-duplicates.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(['Action', 'Part number', 'Name', 'Reason', 'Existing product (kept)']); w.writerows(dups)
    C = collections.Counter
    brands = C(r['brand'] for r in added); img = C(r['placeholderKind'] for r in added)
    cats = C(r['categoryParent'] + (' / ' + r['categoryChild'] if r['categoryChild'] else '') for r in added)
    lines = [f'# Manufacturer product lists {today}', '', 'Source: data/velmach-staging/manufacturers (scripts/fetch-manufacturer-catalogs.py)', '',
             '| | |', '|---|---|', f'| Products added | {len(added)} |',
             f'| Already on the website (skipped) | {sum(1 for d in dups if d[0].startswith("skipped"))} |',
             f'| Listed twice in the lists (merged) | {sum(1 for d in dups if d[0].startswith("merged"))} |',
             f'| Without a part number | {sum(1 for r in added if not r["partNumber"])} |', '',
             '## Files', '| File | Products in it |', '|---|---|'] + [f'| {f} | {n} |' for f, n in files] + [
             '', '## Added per manufacturer site', '| Site | Products |', '|---|---|'] + [f'| {k} | {v} |' for k, v in per_site.most_common()] + [
             '', '## Brands', '| Brand | Products |', '|---|---|'] + [f'| {k} | {v} |' for k, v in brands.most_common()] + [
             '', '## Image', '| Image | Products |', '|---|---|'] + [f'| {k} | {v} |' for k, v in img.most_common()] + [
             '', '## Categories', '| Category | Products |', '|---|---|'] + [f'| {k} | {v} |' for k, v in cats.most_common()]
    with open(os.path.join(REPORTS, f'manufacturer-import-{today}.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
