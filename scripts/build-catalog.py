"""Publish the catalogue: python scripts/build-catalog.py

Reads the store (data/catalog/store/*.jsonl, written by the importers) and writes the static files the site loads.
Each file plays the part a database index would on a server:
  data/catalog/p/<bucket>.json           the products whose slug hashes to that bucket (product page): {slug: product}.
                                         bucket = FNV-1a 32-bit hash of the slug, modulo BUCKETS, as 3 hex digits
                                         (js/catalog.js computes the same); ~60 products per file instead of one file each
  data/catalog/c/<parent>.json           every product in a category, as compact cards     - lookup by category
  data/catalog/c/<parent>/<child>.json   every product in a subcategory
  data/catalog/b/<brand>.json            every product of a brand                           - lookup by brand
  data/catalog/search.json               cards of every product (search suggestions, search page, and every list
                                         longer than BIG_LIST: its own file is then {"src": "all", "p", "c" | "bs"}, and
                                         the page filters the cards of this file instead of loading a second copy)
  data/catalog/r/<n>/<id>.json           24-card slices of each subcategory and brand list, newest first: the related
                                         rails of a product page (the product names its slices in "rails")
  data/catalog/meta.json                 product counts per category, subcategory, brand, condition and aircraft
  data/brands.js                         every brand that has products, with its logo file when public/brands/ has one
  sitemap-products.xml (a sitemap index of sitemap-products-<n>.xml, SITEMAP_URLS each), sitemap-categories.xml
Card files are compact (see encode_cards): {"f": fields, "d": {field: values}, "r": rows}; js/search.js turns them
back into card objects. Listing pages page through them 24/48/96 at a time; images load lazily.
Cards are sorted newest first. Files whose content has not changed are left untouched.
"""
import argparse, collections, os, re, sys
from urllib.parse import quote
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_lib as L

SITE = 'https://www.velmachaerospace.com/'   # TODO: replace domain (same placeholder as sitemap.xml)
BUCKETS = 4096          # product files
BIG_LIST = 20000        # a list longer than this is read from search.json instead of its own file
RAIL = 24               # cards per related-rail slice
SITEMAP_URLS = 40000    # URLs per product sitemap file (the protocol allows 50,000)
# card fields in the order rows store them (fields usually empty go last, so rows end early); fields in DICT are
# stored as an index into a list of their distinct values (index 0 = empty)
CARD_FIELDS = ['s', 'pn', 't', 'pc', 'k', 'i', 'd', 'ph', 'b', 'rep', 'a', 'm', 'ap', 'sn', 'x']
DICT = ['t', 'pc', 'k', 'i', 'd', 'b', 'a', 'm']   # a list: file content must not depend on set order


def bucket(slug):
    """FNV-1a 32-bit of the slug's characters (slugs are ASCII), modulo BUCKETS, as 3 hex digits. js/catalog.js matches it."""
    h = 0x811c9dc5
    for ch in slug:
        h = ((h ^ ord(ch)) * 0x01000193) & 0xffffffff
    return f'{h % BUCKETS:03x}'


def encode_cards(cards):
    """Compact card file: {"f": CARD_FIELDS, "d": {field: [distinct values]}, "r": [[value or index, ...], ...]}.
    pc holds [category, subcategory], b holds [brand, brand slug], a the aircraft ids joined by spaces."""
    dicts = {f: ([['', '']] if f in ('pc', 'b') else ['']) for f in DICT}
    index = {f: {} for f in DICT}
    rows = []
    for c in cards:
        vals = dict(c, pc=[c['p'], c['c']], b=[c['b'], c['bs']], a=' '.join(c.get('a', [])))
        row = []
        for f in CARD_FIELDS:
            v = vals.get(f, '')
            if f in DICT:
                if not v or v == ['', '']:
                    v = 0
                else:
                    key = tuple(v) if isinstance(v, list) else v
                    if key not in index[f]:
                        index[f][key] = len(dicts[f]); dicts[f].append(v)
                    v = index[f][key]
            elif f in ('ph', 'rep', 'x'):
                v = 1 if v else 0
            row.append(v)
        while row and row[-1] in (0, ''):
            row.pop()
        rows.append(row)
    return {'f': CARD_FIELDS, 'd': dicts, 'r': rows}


def cond_key(r):
    """Condition filter value: the inventory's condition code (in, ar, rp ...), or new / used for older imports."""
    if r.get('conditionCode'):
        return r['conditionCode'].lower()
    return 'used' if r.get('condition') == 'Used' else ('none' if r.get('condition') == 'Not stated' else 'new')


def card(r):
    """Compact listing record: short keys keep category files small at tens of thousands of products."""
    c = {'s': r['slug'], 't': r['title'], 'pn': r['partNumber'], 'b': r['brand'], 'bs': r['brandSlug'],
         'p': r['categoryParent'], 'c': r['categoryChild'], 'k': cond_key(r),
         'i': r['images'][0]['thumb'] if r.get('images') else r.get('placeholder', ''), 'd': (r.get('createdAt') or '')[:10]}
    if not r.get('images') and r.get('placeholder'):
        c['ph'] = 1                                  # category placeholder, not a photo of the part
    elif r.get('images') and r['images'][0].get('kind') == 'representative':
        c['rep'] = 1                                 # photo of the component type, not of this exact part
    if r.get('altPartNumber'):
        c['ap'] = r['altPartNumber']
    if r.get('serialNumber'):
        c['sn'] = r['serialNumber']
    if r.get('compatibleAircraft'):
        c['a'] = r['compatibleAircraft']
        # aircraft names for the text search ("falcon 2000", "gulfstream giv sn 1352")
        c['m'] = ' '.join(dict.fromkeys(filter(None, [(r.get('aircraftMake', '') + ' ' + r.get('aircraftModel', '')).strip(), r.get('aircraftListed', '')])))
    if r.get('sample'):
        c['x'] = 1
    return c


def public(r):
    """What the product page loads; source URLs and internal keys stay in the store."""
    return {'id': r['id'], 'slug': r['slug'], 'title': r['title'], 'partNumber': r['partNumber'], 'brand': r['brand'], 'brandSlug': r['brandSlug'],
            'categoryParent': r['categoryParent'], 'categoryChild': r['categoryChild'], 'shortDescription': r.get('shortDescription', ''),
            'description': r.get('description', ''), 'specifications': r.get('specifications', []),
            'images': [{'thumb': i['thumb'], 'large': i['large'], 'original': i.get('original', i['large'])}
                       | ({'kind': i['kind'], 'credit': i.get('credit', '')} if i.get('kind') else {}) for i in r.get('images', [])],
            'documents': [{'label': d['label'], 'url': d['url']} for d in r.get('documents', [])],
            'compatibleAircraft': r.get('compatibleAircraft', []), 'condition': r.get('condition', 'New'),
            'conditionCode': r.get('conditionCode', ''), 'altPartNumber': r.get('altPartNumber', ''), 'serialNumber': r.get('serialNumber', ''),
            'certification': r.get('certification', ''), 'aircraftListed': r.get('aircraftListed', ''), 'placeholder': r.get('placeholder', ''),
            'sample': bool(r.get('sample')), 'updatedAt': r.get('updatedAt', '')}


def sync_dir(folder, wanted):
    """Remove .json files in folder (recursively) that are not in `wanted` (absolute paths)."""
    removed = 0
    if not os.path.isdir(folder):
        return 0
    for dirpath, _, files in os.walk(folder, topdown=False):
        for f in files:
            p = os.path.join(dirpath, f)
            if f.endswith('.json') and p not in wanted:
                os.remove(p); removed += 1
        if dirpath != folder and not os.listdir(dirpath):
            os.rmdir(dirpath)
    return removed


def urlset(urls):
    rows = []
    for u in urls:
        rows.append(f'  <url><loc>{escape(u)}</loc><xhtml:link rel="alternate" hreflang="en" href="{escape(u + ("&" if "?" in u else "?") + "lang=en")}"/>'
                    f'<xhtml:link rel="alternate" hreflang="ar" href="{escape(u + ("&" if "?" in u else "?") + "lang=ar")}"/></url>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<!-- Generated by scripts/build-catalog.py. TODO: replace domain -->\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + '\n'.join(rows) + ('\n' if rows else '') + '</urlset>\n')


LOGO_DIR = os.path.join(L.ROOT, 'public', 'brands')


def brand_logo(slug):
    """(path, on_dark): public/brands/<slug>.svg, .png or .webp (SVG preferred); a brand whose only logo is white is
    saved as <slug>-white.<ext> and shown on a dark backing."""
    for suffix, dark in (('', False), ('-white', True)):
        for ext in ('svg', 'png', 'webp'):
            if os.path.isfile(os.path.join(LOGO_DIR, f'{slug}{suffix}.{ext}')):
                return f'public/brands/{slug}{suffix}.{ext}', dark
    return '', False


def write_brands_js(brands):
    def row(b):
        o = {'slug': b['slug'], 'name': b['name'], 'featured': bool(b.get('featured'))}
        logo, dark = brand_logo(b['slug'])
        if logo:
            o['logo'] = logo
            if dark:
                o['logoDark'] = True
        return o
    lines = ',\n'.join('  ' + L.dumps(row(b)).replace('","', '", "').replace('":', '": ') for b in brands)
    text = ('/* Velmach Aerospace: brands. Updated by scripts/build-catalog.py: every brand that appears on products is listed;\n'
            '   a brand with no products is dropped. featured: true puts the brand first in the header menu; set it by hand.\n'
            '   Logos: put <slug>.svg (or .png / .webp) in public/brands/ and rebuild; the build fills in "logo" (a white-only logo:\n'
            '   <slug>-white.<ext>, shown on a dark backing: "logoDark"). A brand without a\n'
            '   logo file shows its name as text instead. URLs: brand.dc.html?b=<slug> (clean form: /brand/<slug>). Keep a slug once published. */\n'
            'window.VM_BRANDS = [\n' + lines + '\n];\n')
    return L.write_if_changed(os.path.join(L.ROOT, 'data', 'brands.js'), text)


def build(force=False):
    cats = L.load_categories()
    tree = {p['slug']: {c['slug'] for c in p['children']} for p in cats}
    store = L.load_store()
    products, dropped = [], []
    for r in store.values():
        if r['categoryParent'] in tree and (not r['categoryChild'] or r['categoryChild'] in tree[r['categoryParent']]):
            products.append(r)
        else:
            dropped.append(r)
    for r in dropped:
        print(f"  ! {r['partNumber']} ({r['brand']}): category {r['categoryParent']}/{r['categoryChild']} no longer exists in data/categories.js; not published")
    # newest first; products imported together keep the inventory's order (serial number 1, 2, 3 ...)
    products.sort(key=lambda r: (r.get('createdAt') or '', -(r.get('serialNo') or 0), r['slug']), reverse=True)

    # Shop by Aircraft: a product without compatibleAircraft takes its aircraft from an "Aircraft" specification
    amap, unknown_ac = L.AircraftMap(L.load_aircraft()), {}
    for r in products:
        if r.get('compatibleAircraft'):
            continue
        ids = []
        for s in r.get('specifications') or []:
            if str(s.get('name', '')).strip().lower() == 'aircraft':
                found, unknown = amap.from_spec(s.get('value', ''))
                ids += found
                for u in unknown:
                    unknown_ac[u] = unknown_ac.get(u, 0) + 1
        if ids:
            r['compatibleAircraft'] = sorted(set(ids))
    for u, n in sorted(unknown_ac.items(), key=lambda x: -x[1]):
        print(f'  ! aircraft "{u}" in {n} product specification(s) is not in data/aircraft.js; those products show for every aircraft')

    written = 0
    base = L.CATALOG
    wanted = set()
    manifest = L.Manifest(os.path.join(base, '.build-manifest.json'), force)

    def put(rel_path, obj):
        nonlocal written
        path = os.path.join(base, *rel_path.split('/'))
        wanted.add(path)
        written += manifest.put(path, L.dumps(obj))

    cards = [card(r) for r in products]
    by_parent, by_child, by_brand = {}, {}, {}
    for c in cards:
        by_parent.setdefault(c['p'], []).append(c)
        if c['c']:
            by_child.setdefault((c['p'], c['c']), []).append(c)
        if c['bs']:                                  # products without a stated brand have no brand page
            by_brand.setdefault(c['bs'], []).append(c)

    def put_list(rel_path, lst, ref):
        put(rel_path, dict(ref, src='all') if len(lst) > BIG_LIST else encode_cards(lst))

    # related rails: each subcategory and brand list cut in slices of RAIL cards; a product names the slice it is in
    rails, rail_of = 0, {}
    for kind, groups in (('rel', by_child), ('brand', by_brand)):
        for lst in groups.values():
            for i in range(0, len(lst), RAIL):
                part = lst[i:i + RAIL]
                put(f'r/{rails // 1000}/{rails}.json', encode_cards(part))
                for c in part:
                    rail_of.setdefault(c['s'], {})[kind] = rails
                rails += 1
    buckets = {}
    for r in products:
        rec = public(r)
        if r['slug'] in rail_of:
            rec['rails'] = rail_of[r['slug']]
        buckets.setdefault(bucket(r['slug']), {})[r['slug']] = rec
    for bk, recs in buckets.items():
        put(f'p/{bk}.json', recs)
    # every category gets a file (an empty list when it has no products yet), so pages never request a missing file
    for p in cats:
        put_list(f"c/{p['slug']}.json", by_parent.get(p['slug'], []), {'p': p['slug']})
        for ch in p['children']:
            put_list(f"c/{p['slug']}/{ch['slug']}.json", by_child.get((p['slug'], ch['slug']), []), {'p': p['slug'], 'c': ch['slug']})

    # brands: every brand that has products, plus the brands of data/supplier-brands.json (published before they have
    # products; their page shows the empty listing). Any other brand without products is dropped, featured or not.
    known = {b['slug']: dict(b) for b in L.load_brands()}
    for r in products:
        if r['brandSlug'] and r['brandSlug'] not in known:
            known[r['brandSlug']] = {'slug': r['brandSlug'], 'name': r['brand'], 'featured': False}
    by_name = {L.norm_key(b['name']): b['slug'] for b in known.values()}
    listed = set()
    for name in L.load_supplier_brands():
        slug = by_name.get(L.norm_key(name)) or L.slugify(name)
        known.setdefault(slug, {'slug': slug, 'name': name, 'featured': False})
        listed.add(slug)
    brands = sorted((b for b in known.values() if b['slug'] in by_brand or b['slug'] in listed), key=lambda b: b['name'].lower())
    for b in brands:
        b['featured'] = bool(b.get('featured', False))
        put_list(f"b/{b['slug']}.json", by_brand.get(b['slug'], []), {'bs': b['slug']})
    brands_changed = write_brands_js(brands)

    # the search index holds full cards, so the search page can filter by category, brand, condition and aircraft
    put('search.json', encode_cards(cards))
    meta = {'total': len(products), 'samples': sum(1 for r in products if r.get('sample')),
            'categories': {p['slug']: {'n': len(by_parent.get(p['slug'], [])), 'c': {ch['slug']: len(by_child.get((p['slug'], ch['slug']), [])) for ch in p['children']},
                                       # tile images: the newest product photo in each subcategory, else its placeholder
                                       'i': {ch['slug']: next((c['i'] for c in by_child.get((p['slug'], ch['slug']), []) if c['i'] and not c.get('ph')),
                                                              next((c['i'] for c in by_child.get((p['slug'], ch['slug']), []) if c['i']), '')) for ch in p['children']}} for p in cats},
            'brands': {b['slug']: len(by_brand.get(b['slug'], [])) for b in brands},
            'conditions': dict(sorted(collections.Counter(c['k'] for c in cards).items()))}
    # Shop by Aircraft page: how many products list each aircraft
    by_ac = {}
    for c in cards:
        for a in c.get('a', []):
            by_ac[a] = by_ac.get(a, 0) + 1
    meta['aircraft'] = dict(sorted(by_ac.items()))
    put('meta.json', meta)
    removed = sum(sync_dir(os.path.join(base, d), wanted) for d in ('p', 'c', 'b', 'r'))
    manifest.save()

    # sitemaps: real products only (sample products are for testing and stay out of search engines)
    live = [r for r in products if not r.get('sample')]
    urls = [SITE + 'product.html?p=' + quote(r['slug']) for r in live]
    parts = [urls[i:i + SITEMAP_URLS] for i in range(0, len(urls), SITEMAP_URLS)] or [[]]
    for n, part in enumerate(parts, 1):
        L.write_if_changed(os.path.join(L.ROOT, f'sitemap-products-{n}.xml'), urlset(part))
    for f in os.listdir(L.ROOT):                     # files of an earlier, longer catalogue
        m = re.fullmatch(r'sitemap-products-(\d+)\.xml', f)
        if m and int(m.group(1)) > len(parts):
            os.remove(os.path.join(L.ROOT, f))
    L.write_if_changed(os.path.join(L.ROOT, 'sitemap-products.xml'),
                       '<?xml version="1.0" encoding="UTF-8"?>\n<!-- Generated by scripts/build-catalog.py. TODO: replace domain -->\n'
                       '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                       + ''.join(f'  <sitemap><loc>{SITE}sitemap-products-{n}.xml</loc></sitemap>\n' for n in range(1, len(parts) + 1))
                       + '</sitemapindex>\n')
    cat_urls = [SITE + 'categories.html'] + [SITE + 'category.html?c=' + p['slug'] for p in cats] + \
               [SITE + 'category.html?c=' + p['slug'] + '/' + ch['slug'] for p in cats for ch in p['children']] + \
               [SITE + 'brands.html'] + [SITE + 'brand.html?b=' + quote(b['slug']) for b in brands] + \
               ([SITE + 'aircraft.html'] if any(r.get('compatibleAircraft') for r in live) else [])
    L.write_if_changed(os.path.join(L.ROOT, 'sitemap-categories.xml'), urlset(cat_urls))

    print(f"Catalogue built: {len(products)} products ({meta['samples']} samples), {len(brands)} brands, "
          f"{written} file(s) written, {removed} removed{', data/brands.js updated' if brands_changed else ''}.")
    return meta


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--force', action='store_true', help='rewrite every file, even when the manifest says it is unchanged')
    build(ap.parse_args().force)
