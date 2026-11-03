"""Import Velmach's consumables lists: python scripts/import-list-sheet.py [--src "assets/velmach product/list sheet"]

Reads the product lists in the "list sheet" folder and adds them to the store (data/catalog/store/) next to the master
inventory (scripts/import-inventory.py). Products of this import have keys starting "list:"; a re-run replaces them all
(keeping each product's slug and createdAt) and leaves every other product alone.

  oil and lubricants.xlsx   Sheet1: 20pt bold category, 13.5pt bold group ("3M products", "Henkel Loctite"), a brand line
                            above a group, then product lines (the "All material" block: "Name - description Specification: X").
                            Sheet2: supplier websites and e-mails (not products).
                            Sheet3: sections ("ADHESIVE", "GREASE" ...); the first lists PRODUCT NAME | PART NO., the others
                            PART NO. | DESCRIPTION, and "Pest Control Agents And Disinfectants" adds the manufacturer.
  PRODUCT LIST.xlsx 2.xlsx  one product per line, the same list as the "All material" block (merged with it).
Other files in the folder are not product lists of Velmach's own: the master inventory (scripts/import-inventory.py),
other companies' stock / planning lists, and logo pictures (PICIMAGE.xlsx, product images.docx).

Rules: values come only from the lists. Rows with the same part number (or, without one, the same name) are one product.
The brand is the brand line or group heading above the product, the manufacturer column, "Brand, part no., ..." in a
description, or a brand name the lists use at the start of the product name. The category comes from the keyword rules
of scripts/extract-documents.py, else from the section heading (HEADING_CAT below), else the Consumables parent only.
No list has prices, conditions or photos: condition is "Not stated", and the pictures in the sheets are brand logos.
Images: no product photo exists, so the placeholder is the brand's logo (public/brands/<slug>.svg|png|webp; logos cut
from the sheet are saved there for brands that have none: SHEET_LOGOS) or, without one, the Velmach logo. A white-only
logo is not used (the placeholder sits on a light background). The placeholder is never presented as a photo of the part.

Writes: the store, public/brands/<slug>.png (SHEET_LOGOS), images/placeholders/velmach-logo.png,
reports/list-sheet-import-<date>.md, reports/list-sheet-conflicts.csv, "assets/velmach product/products-export.csv"
(every product on the site, with its image status); then runs scripts/build-catalog.py.
"""
import argparse, collections, csv, datetime, html, importlib.util, io, json, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_lib as L

_spec = importlib.util.spec_from_file_location('extract_documents', os.path.join(L.ROOT, 'scripts', 'extract-documents.py'))
X = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(X)
clean = X.clean

SRC = os.path.join(L.ROOT, 'assets', 'velmach product', 'list sheet')
EXPORT = os.path.join(L.ROOT, 'assets', 'velmach product', 'products-export.csv')
REPORTS = os.path.join(L.ROOT, 'reports')
OIL, PL2 = 'oil and lubricants.xlsx', 'PRODUCT LIST.xlsx 2.xlsx'
OLD_BRANDS = os.path.join(L.ROOT, 'backup', 'catalogue-before-master-inventory-2026-10-29', 'brands.js')   # brand spellings used before
VELMACH_LOGO_SRC = os.path.join(L.ROOT, 'assets', 'img', 'logo-480.png')
VELMACH_LOGO = 'images/placeholders/velmach-logo.png'

# brand named by a Sheet1 group heading (used when no brand line stands above the group)
HEADING_BRAND = [(r'^3M products$', '3M'), (r'^AV-Dec products$', 'AV-DEC'), (r'^Anderol products$', 'Anderol'),
                 (r'^Aviocom products$', 'Aviocom'), (r'^Cytec products$', 'Cytec'), (r'^Dow Corning products$', 'Dow Corning'),
                 (r'^Ecopoint products$', 'Ecopoint'), (r'^Huntsman products$', 'Huntsman'), (r'^Kimberly Clark products$', 'Kimberly Clark'),
                 (r'^Nye products$', 'Nye'), (r'^PPG products$', 'PPG'), (r'^Socomor products$', 'SOCOMORE'), (r'^Zerust products$', 'Zerust'),
                 (r'^Zipchem products$', 'Zip Chem'), (r'^Henkel ', 'Henkel'), (r'^AeroShell ', 'AeroShell'), (r'^Chemetall ', 'Chemetall'),
                 (r'^Mobil Fluids$', 'Mobil'), (r'^CeeBee Cabin$', 'CeeBee'), (r'^AkzoNobel ', 'AkzoNobel')]
# consumables subcategory for a section heading, when the keyword rules do not place the product (most specific first)
HEADING_CAT = {
    # Sheet3 sections
    'PPG SEALANT': 'sealants', 'ADHESIVE': 'adhesives-compounds', 'GREASE': 'aircraft-grease',
    'Aircraft Corrosion Inhibitors': 'anti-corrosion-lubricants', 'Aircraft Lubricants': 'lubricating-oils',
    'Aircraft Paints and Primer List': 'paints-coatings', 'Aircraft Resins': 'composite-materials', 'Aircraft Sealant': 'sealants',
    'Pest Control Agents And Disinfectants': 'aircraft-hangar-cleaning-supplies', 'Miscellaneous Chemical Specialties': 'chemicals',
    # Sheet1 groups
    'NDT Chemicals': 'ndt-chemicals', 'Raw Materials': 'raw-materials', 'CeeBee Cabin': 'aircraft-hangar-cleaning-supplies',
    'Toilet Deodorant': 'aircraft-hangar-cleaning-supplies', 'Prepreg': 'composite-materials', 'AeroShell Greases': 'aircraft-grease',
    'Aeroshell Piston Engine Oils': 'engine-oil', 'Oil & Greases': 'lubricating-oils', 'Henkel Loctite': 'adhesives-compounds',
    'Henkel Hysol': 'adhesives-compounds', 'Henkel Chemical Milling': 'chemicals', 'Chemetall CIC': 'chemicals',
    'Chemetall Naftoseal': 'sealants', 'Sealants Europe': 'sealants', 'AkzoNobel Hardeners': 'paints-coatings',
}
SHEET3_SECTIONS = list(HEADING_CAT)[:10]
SECTION_KEEPS = {'Aircraft Lubricants': {'engine-oil', 'anti-corrosion-lubricants', 'aircraft-grease', 'hydraulic-fluid', 'landing-gear-fluid',
                                         'calibration-fluids', 'fuel-additives'},
                 'GREASE': {'anti-corrosion-lubricants'}}
CAT_HEADING_CAT = {'Wipes and Tapes': 'tape', 'Surface Treatment': 'chemicals', 'Sealants and Silicones': 'sealants',
                   'Paint Systems and Coatings': 'paints-coatings', 'Composite Technologies': 'composite-materials', 'Adhesives': 'adhesives-compounds'}
# single-brand logos embedded in oil and lubricants.xlsx Sheet1 (anchor row), checked by eye; saved for brands without a logo file
SHEET_LOGOS = {'henkel': 2691, 'chemetall': 1059, 'dow-corning': 1134, '3m': 987, 'ceebee': 696, 'akzonobel': 1442,
               'mobil': 2026, 'loctite': 2796, 'zodiac': 1435, 'anderol': 1856}
PACK_RX = re.compile(r'\(([^()]*\d[^()]*(?:ML|LT|LTR|L|GLN|GAL|QT|PINT|OZ|LB|KG|GR|G|MTR|M|MM|CM|YD|IN|EA|PCS|SHEETS|KIT)\.?\s*)\)\s*$', re.I)
CORP = re.compile(r'(inc|corp|corporation|co|ltd|llc|gmbh|company)$')


def read_sheet1(col, ws):
    lines = []
    for n, r in enumerate(ws.iter_rows(), start=1):
        c = r[1] if len(r) > 1 else None
        b = clean(c.value) if c is not None else ''
        if not b:
            continue
        f = c.font
        level = 'cat' if f.b and (f.sz or 0) >= 18 else 'group' if f.b and (f.sz or 0) >= 13 else 'text'
        lines.append((n, b, level, clean(r[0].value)))
    cat = group = brand = hbrand = ''
    for i, (n, b, level, a) in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if level == 'cat':
            cat, group, brand, hbrand = b, '', '', ''; continue
        if level == 'group':
            group = b
            hbrand = next((v for rx, v in HEADING_BRAND if re.search(rx, b, re.I)), '')
            if not (lines[i - 1][2] == 'text' and lines[i - 1][1] == brand):
                brand = ''                                # a group not directly under a brand line
            continue
        after = [x[1] for x in lines[i + 2:i + 8] if x[2] == 'text']
        if nxt and nxt[2] == 'group' and not re.fullmatch(r'\d+', a) and X.is_brand_line(b, nxt[1], after):
            brand = b; continue
        txt, spec = b, ''
        m = re.search(r'spec(?:ification)?\s*:\s*(.+)$', txt, re.I)
        if m:
            spec = m.group(1).strip(' -–'); txt = txt[:m.start()].strip(' -–')
        parts = re.split(r'\s+[-–]\s+|\s*–\s*', txt, maxsplit=1)
        title = parts[0].strip(' -–')
        specs = {'Specification': spec} if spec else {}
        pm = PACK_RX.search(title)
        if pm:
            specs['Pack size'] = pm.group(1).strip()
        col.add(OIL, f'sheet "Sheet1" row {n}', 'velmach', title=title, desc=parts[1].strip() if len(parts) > 1 else '',
                brand=brand or hbrand, cat_doc=cat, sub_doc=group, specs=specs)


def read_sheet3(col, ws, known):
    section = ''
    for n, r in enumerate(ws.iter_rows(values_only=True), start=1):
        a, b, c, d = (clean(r[i]) if len(r) > i else '' for i in range(4))
        if not (b or c):
            continue
        if not a and not c:
            section = b; continue
        if b.upper() in ('PRODUCT NAME', 'PART NO.') or c.upper() in ('PART NO.', 'DESCRIPTION'):
            continue                                      # column headings
        specs, brand, desc = {}, '', ''
        if not section:                                   # first block: PRODUCT NAME | PART NO.
            pn, title, _, _, raw = X.split_name_pn(b, c)
            if raw:
                specs['Part no. (as written)'] = raw
        else:                                             # PART NO. | DESCRIPTION (| manufacturer)
            pn, desc = b, c
            if not pn:
                col.note(OIL, f'sheet "Sheet3" row {n}: no part number ({desc or "empty row"}), not imported'); continue
            if not desc:
                title = pn
            elif (re.fullmatch(r'[\d\s.,/-]*(?:lb|gal|oz|qt|pint|ml|l|kg|g)s?\.?\s.*', desc, re.I)
                  or re.search(r'\b(drum|pail|bucket|can|cartridge|tube|kit|aerosol)\b', desc, re.I) and len(desc.split()) <= 5
                  and not re.search(r'[a-z]{4,}\s+(?:adhesive|sealant|grease|primer)', desc, re.I)):
                title = f'{pn} ({desc})'; specs['Pack size'] = desc          # "Tribolube-15" | "240-Lb Drum-16 Ga"
            elif len(desc.split()) <= 2 and L.norm_key(pn) not in L.norm_key(desc):
                title = f'{pn} {desc}'                    # a bare type word ("Lubricant", "Resin")
            else:
                title = desc
            parts = [x.strip() for x in desc.split(',')]
            if len(parts) >= 3 and L.norm_key(parts[1]) == L.norm_key(pn):
                brand = parts[0]                          # "AC-Tech, AC-350 Class B-2, Gallon Sealant"
            if section == 'PPG SEALANT':
                brand = 'PPG'
            if d:
                mk = known.get(CORP.sub('', L.norm_key(d)))
                if mk:
                    brand = mk
                else:
                    specs['Manufacturer (as listed)'] = d
        col.add(OIL, f'sheet "Sheet3" row {n}', 'velmach', pn=pn, title=title, desc='' if L.norm_key(desc) in L.norm_key(title) else desc, brand=brand,
                cat_doc=section, specs=specs)


def save_sheet_logos(ws, brands_used):
    """Cut the SHEET_LOGOS pictures to public/brands/<slug>.png for brands with products and no non-white logo file.
    Returns the SHEET_LOGOS brands whose logo file is the one cut from the sheet (saved now or by an earlier run)."""
    saved = [s for s in SHEET_LOGOS if s in brands_used and os.path.isfile(os.path.join(L.ROOT, 'public', 'brands', f'{s}.png'))]
    by_row = {im.anchor._from.row + 1: im for im in ws._images}
    for slug, row in SHEET_LOGOS.items():
        if slug not in brands_used or not by_row.get(row):
            continue
        logo, dark = find_logo(slug)
        if (logo and not dark) or slug in saved:
            continue
        from PIL import Image
        im = Image.open(io.BytesIO(by_row[row]._data()))
        path = os.path.join(L.ROOT, 'public', 'brands', f'{slug}.png')
        im.save(path, 'PNG')
        saved.append(slug)
    return saved


def find_logo(slug):
    for suffix, dark in (('', False), ('-white', True)):
        for ext in ('svg', 'png', 'webp'):
            if os.path.isfile(os.path.join(L.ROOT, 'public', 'brands', f'{slug}{suffix}.{ext}')):
                return f'public/brands/{slug}{suffix}.{ext}', dark
    return '', False


def extract(src):
    import openpyxl
    old_brands = json.loads(re.search(r'\[.*\]', open(OLD_BRANDS, encoding='utf-8').read(), re.S).group(0))
    col = X.Collector()
    wb = openpyxl.load_workbook(os.path.join(src, OIL), data_only=True)
    read_sheet1(col, wb['Sheet1'])
    known = {}
    for nm in [b['name'] for b in old_brands] + [v for _, v in HEADING_BRAND] + [r['brand'] for r in col.rows if r.get('brand')]:
        known.setdefault(L.norm_key(nm), nm)
    col.note(OIL, 'sheet "Sheet2": list of supplier websites and e-mails, not products')
    read_sheet3(col, wb['Sheet3'], known)
    X.read_line_list(col, PL2, openpyxl.load_workbook(os.path.join(src, PL2), data_only=True).active, 'velmach', [])
    col.notes[PL2] = [n for n in col.notes[PL2] if 'embedded images' not in n]
    col.note(PL2, 'sheet "Sheet1": 12 embedded pictures, all brand logos or groups of logos (not product photos)')
    col.note(OIL, 'sheet "Sheet1": 57 embedded pictures, all brand logos or groups of logos (not product photos)')
    for r in col.rows:                                    # brands Sheet3 names ("LOCTITE, EA 9364FR, AERO", manufacturer column)
        if r.get('brand'):
            known.setdefault(L.norm_key(r['brand']), r['brand'])
    # a product name that starts with a brand name the lists use ("3M 2090 MASKPAINT", "Castrol Aero 40") names its brand
    names = sorted({nm for nm in known.values() if len(L.norm_key(nm)) >= 2}, key=len, reverse=True)
    prefix = [(re.compile(r'^' + re.escape(nm).replace(r'\ ', r'[\s-]*') + r'(?![a-z0-9])', re.I), nm) for nm in names]
    for r in col.rows:
        hit = next((nm for rx, nm in prefix if rx.search(r.get('title', ''))), '')
        if hit:
            r['brand'] = hit
    spelling = {}
    for r in col.rows:                                    # one spelling per brand: the earlier catalogue's, else the first seen
        if r.get('brand'):
            spelling.setdefault(L.norm_key(r['brand']), known.get(L.norm_key(r['brand']), r['brand']))
    for r in col.rows:
        if r.get('brand'):
            r['brand'] = spelling[L.norm_key(r['brand'])]
    X.EXPLICIT_BRANDS.update(L.norm_key(r['brand']) for r in col.rows if r.get('brand'))
    for f in (OIL, PL2):
        X.DOC_DATES[f] = X.doc_date(os.path.join(src, f), f)
    products, conflicts, _ = X.merge(col.rows)
    return col, products, conflicts, wb['Sheet1']


def categorize(p, cname):
    parent, child, conf, reason = X.categorize(p, cname)
    text = ' '.join([p['title'], p['description']]).upper()
    if child == 'aircraft-grease' and 'DEGREAS' in text and not re.search(r'(?<!DE)GREASE', text):
        child = 'aircraft-hangar-cleaning-supplies'      # "Orange Degreaser" matched the grease rule
    # a Sheet3 section names the product type outright: it wins over the keyword rules, except a more specific type of
    # the same family ("Aircraft Lubricants" -> engine oil); the broad "Miscellaneous Chemical Specialties" does not
    section = next((d for d in reversed(p['cat_doc']) if d in SHEET3_SECTIONS), '')
    if section and section != 'Miscellaneous Chemical Specialties' and child not in SECTION_KEEPS.get(section, set()) | {HEADING_CAT[section]}:
        return 'consumables', HEADING_CAT[section], 'section heading'
    if parent:
        return parent, child, 'keyword rules'
    child = next((HEADING_CAT[d] for d in reversed(p['cat_doc']) if d in HEADING_CAT), '') \
        or next((CAT_HEADING_CAT[d] for d in p['cat_doc'] if d in CAT_HEADING_CAT), '')
    return 'consumables', child, ('section heading' if child else 'Consumables (no rule or heading names the type)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', default=SRC)
    ap.add_argument('--no-build', action='store_true', help='do not run build-catalog.py afterwards')
    a = ap.parse_args()

    col, products, conflicts, sheet1 = extract(a.src)
    cats = L.load_categories()
    by = {c['slug']: c for c in cats}
    def cname(parent, child=''):
        if parent not in by:
            return parent + (' > ' + child if child else '')
        c = next((x for x in by[parent]['children'] if x['slug'] == child), None)
        return by[parent]['en'] + (' > ' + c['en'] if c else '')

    brands_used = {L.slugify(p['brand']) for p in products if p['brand']}
    logos_saved = save_sheet_logos(sheet1, brands_used)
    os.makedirs(os.path.dirname(os.path.join(L.ROOT, VELMACH_LOGO)), exist_ok=True)
    shutil.copyfile(VELMACH_LOGO_SRC, os.path.join(L.ROOT, VELMACH_LOGO))

    old = L.load_store()
    old_slug = {k: r['slug'] for k, r in old.items() if k.startswith('list:')}
    old_created = {k: r.get('createdAt') for k, r in old.items() if k.startswith('list:')}
    store = {k: r for k, r in old.items() if not k.startswith('list:')}
    taken = {r['slug'] for r in store.values()}
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    how_cat = collections.Counter()
    for p in products:
        key = 'list:' + p['key']
        pn, title, brand = p['partNumber'], p['title'] or p['partNumber'], p['brand']
        parent, child, how = categorize(p, cname)
        how_cat[how] += 1
        slug = old_slug.get(key)
        if not slug or slug in taken:
            base = L.slugify(title if not pn or L.norm_key(pn) in L.norm_key(title) else f'{pn} {title}', 70) or 'product'
            slug, n = base, 2
            while slug in taken:
                slug = f'{base}-{n}'; n += 1
        taken.add(slug)
        specs = [{'name': k, 'value': v} for k, v in p['specifications'].items() if v]
        if p['cat_doc']:
            specs.append({'name': 'Listed under', 'value': ' / '.join(p['cat_doc'])})
        bslug = L.slugify(brand) if brand else ''
        logo, dark = find_logo(bslug) if bslug else ('', False)
        sentence = html.escape(title) + (f', part number {html.escape(pn)}' if pn and L.norm_key(pn) not in L.norm_key(title) else '') \
            + (f', by {html.escape(brand)}' if brand else '') + '.'
        desc = html.escape(p['description']) if p['description'] else ''
        store[key] = {
            'key': key, 'id': L.product_id(key), 'slug': slug, 'pnDir': L.safe_part_number(pn or slug),
            'title': title, 'partNumber': pn, 'altPartNumber': '', 'serialNumber': '',
            'brand': brand, 'brandSlug': bslug, 'brandBasis': 'brand' if brand else '',
            'categoryParent': parent, 'categoryChild': child,
            'shortDescription': (sentence + (' ' + desc if desc else '')).replace('&amp;', '&'),
            'description': '<p>' + sentence + '</p>' + (f'<p>{desc}</p>' if desc else ''),
            'specifications': specs, 'images': [],
            'placeholder': logo if logo and not dark else VELMACH_LOGO,
            'placeholderKind': 'brand logo' if logo and not dark else 'company logo',
            'documents': [], 'compatibleAircraft': [], 'aircraftListed': '', 'aircraftMake': '', 'aircraftModel': '',
            'condition': 'Not stated', 'conditionCode': '', 'certification': '', 'sample': False,
            'source': '; '.join(p['sources']),
            'createdAt': old_created.get(key) or now, 'updatedAt': now,
        }
        prev = old.get(key)
        if prev and {k: v for k, v in prev.items() if k != 'updatedAt'} == {k: v for k, v in store[key].items() if k != 'updatedAt'}:
            store[key]['updatedAt'] = prev.get('updatedAt', now)     # unchanged: keeps its date
    removed = len([k for k in old if k.startswith('list:') and k not in store])
    L.save_store(store)
    new = [r for r in store.values() if r['key'].startswith('list:')]
    missing_cat = sorted({(r['categoryParent'], r['categoryChild']) for r in new
                          if r['categoryParent'] not in by or (r['categoryChild'] and r['categoryChild'] not in {c['slug'] for c in by[r['categoryParent']]['children']})})
    write_reports(col, new, conflicts, how_cat, logos_saved, removed, missing_cat)
    write_export(store)
    print(f'Imported {len(new)} products from the list sheets ({removed} earlier list-sheet products no longer in the lists removed); '
          f'brand logos from the sheet: {", ".join(logos_saved) or "none"}.')
    if missing_cat:
        print('  ! categories not in data/categories.js (those products are not published): ' + ', '.join('/'.join(c) for c in missing_cat))
    if not a.no_build:
        spec = importlib.util.spec_from_file_location('build_catalog', os.path.join(L.ROOT, 'scripts', 'build-catalog.py'))
        B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
        B.build()


def image_status(r):
    if r.get('images'):
        return ('representative photo' if r['images'][0].get('kind') == 'representative' else 'real image'), r['images'][0].get('large', '')
    if r.get('placeholderKind'):
        return r['placeholderKind'], r.get('placeholder', '')
    return 'category placeholder', r.get('placeholder', '')


def write_export(store):
    cats = {c['slug']: c for c in L.load_categories()}
    def label(parent, child):
        p = cats.get(parent)
        if not p:
            return parent, child
        c = next((x for x in p['children'] if x['slug'] == child), None)
        return p['en'], (c['en'] if c else child)
    with open(EXPORT, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Source list', 'Title', 'Part number', 'Alternate part number', 'Serial number', 'Brand', 'Category', 'Subcategory',
                    'Description', 'Condition', 'Certification', 'Aircraft', 'Specifications', 'Image status', 'Image file', 'Product URL',
                    'Source (file, sheet, row)', 'Missing'])
        for r in sorted(store.values(), key=lambda r: (not r['key'].startswith('list:'), r['brand'].lower(), r['title'].lower())):
            cat, sub = label(r['categoryParent'], r['categoryChild'])
            status, img = image_status(r)
            missing = [n for n, v in (('part number', r['partNumber']), ('brand', r['brand']), ('subcategory', r['categoryChild']),
                                      ('description', r['key'].startswith('inv:') or '</p><p>' in r['description'])) if not v]
            missing.append('price (no list has one)')
            w.writerow(['Consumables lists' if r['key'].startswith('list:') else 'Master Parts Inventory', r['title'], r['partNumber'],
                        r.get('altPartNumber', ''), r.get('serialNumber', ''), r['brand'], cat, sub, L.strip_html(r['description']),
                        r.get('condition', ''), r.get('certification', ''), r.get('aircraftListed', ''),
                        ' | '.join(f"{s['name']}: {s['value']}" for s in r['specifications']), status, img,
                        f"product.dc.html?p={r['slug']}", r.get('source', ''), ', '.join(missing)])


def write_reports(col, new, conflicts, how_cat, logos_saved, removed, missing_cat):
    os.makedirs(REPORTS, exist_ok=True)
    today = datetime.date.today().isoformat()
    C = collections.Counter
    with open(os.path.join(REPORTS, 'list-sheet-conflicts.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Product', 'Field', 'Value used', 'Other values (source)'])
        for who, field, vals, chosen in conflicts:
            w.writerow([who, field, chosen[0], ' || '.join(f'{v} ({s})' for v, s, _ in vals if v != chosen[0])])
    brands = C(r['brand'] or '(no brand stated)' for r in new)
    img = C(r['placeholderKind'] for r in new)
    cats = C((r['categoryParent'], r['categoryChild'] or '(parent only)') for r in new)
    rows = C(r['file'] + ', ' + r['loc'].split(' row')[0] for r in col.rows)
    lines = [f'# List-sheet import {today}', '', 'Source: `assets/velmach product/list sheet` (scripts/import-list-sheet.py)', '',
             '| | |', '|---|---|', f'| Rows read | {len(col.rows)} |', f'| Products (after merging rows with the same part number / name) | {len(new)} |',
             f'| Earlier list-sheet products removed | {removed} |', f'| Field conflicts (reports/list-sheet-conflicts.csv) | {len(conflicts)} |',
             f'| Brand logos taken from the sheet (public/brands/<slug>.png) | {", ".join(logos_saved) or "none"} |', '',
             '## Rows per sheet', '| Sheet | Rows |', '|---|---|'] + [f'| {k} | {v} |' for k, v in rows.most_common()] + [
             '', '## Image (placeholder) per product', '| Kind | Products |', '|---|---|'] + [f'| {k} | {v} |' for k, v in img.most_common()] + [
             '', '## Category basis', '| Basis | Products |', '|---|---|'] + [f'| {k} | {v} |' for k, v in how_cat.most_common()] + [
             '', '## Categories', '| Category | Products |', '|---|---|'] + [f'| {p} / {c} | {n} |' for (p, c), n in cats.most_common()] + [
             '', '## Brands', '| Brand | Products | Placeholder |', '|---|---|---|'] + [
             f'| {b} | {n} | {next((r["placeholderKind"] for r in new if (r["brand"] or "(no brand stated)") == b), "")} |' for b, n in brands.most_common()] + [
             '', '## Incomplete data', '| Missing | Products |', '|---|---|',
             f'| Part number | {sum(1 for r in new if not r["partNumber"])} |', f'| Brand | {sum(1 for r in new if not r["brand"])} |',
             f'| Subcategory (Consumables parent only) | {sum(1 for r in new if not r["categoryChild"])} |',
             f'| Description beyond the name | {sum(1 for r in new if "</p><p>" not in r["description"])} |',
             f'| Price | {len(new)} (no list has a price) |', f'| Condition | {len(new)} (no list states one) |', '', '## Notes']
    lines += [f'- {f}: {n}' for f, ns in col.notes.items() for n in ns]
    if missing_cat:
        lines.append('- categories not in data/categories.js (not published): ' + ', '.join('/'.join(c) for c in missing_cat))
    with open(os.path.join(REPORTS, f'list-sheet-import-{today}.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
