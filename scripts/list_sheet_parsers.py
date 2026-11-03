"""Parsers for Velmach's consumables lists in "assets/velmach product/list sheet" (used by scripts/import-all-lists.py).

  oil and lubricants.xlsx   Sheet1: 20pt bold category, 13.5pt bold group ("3M products", "Henkel Loctite"), a brand line
                            above a group, then product lines (the "All material" block: "Name - description Specification: X").
                            Sheet2: supplier websites and e-mails (not products).
                            Sheet3: sections ("ADHESIVE", "GREASE" ...); the first lists PRODUCT NAME | PART NO., the others
                            PART NO. | DESCRIPTION, and "Pest Control Agents And Disinfectants" adds the manufacturer.
  PRODUCT LIST.xlsx 2.xlsx  one product per line, the same list as the "All material" block (merged with it).

Values come only from the lists. Rows with the same part number (or, without one, the same name) are one product.
The brand is the brand line or group heading above the product, the manufacturer column, "Brand, part no., ..." in a
description, or a brand name the lists use at the start of the product name. The category comes from the keyword rules
of scripts/extract-documents.py, else from the section heading (HEADING_CAT), else the Consumables parent only.
The pictures in the sheets are brand logos, not product photos: SHEET_LOGOS (checked by eye) are cut to
public/brands/<slug>.png for brands that have no logo file yet.
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
