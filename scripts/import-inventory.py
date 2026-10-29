"""Import the master parts inventory spreadsheet: python scripts/import-inventory.py [file.xlsx] [--max-serial 5560]

Replaces the whole catalogue with the rows of the inventory (the spreadsheet is the source of truth): every product in
data/catalog/products.jsonl that is not in the sheet is removed. Re-run it whenever the inventory is updated.

Columns are found by their header (the first row in the top 10 that names a part number and a description):
  Part # / Part Number / P/N            -> partNumber (required)
  Description                           -> title
  Alt P/N                               -> alternate part number (searchable)
  S/N / Serial Number                   -> the unit's serial number (keeps rows of the same part apart)
  Condition                             -> condition code (NE, OH, SV, AR, RP, IN ...; names in scripts/inventory_rules.py)
  8130                                  -> certification (FAA Form 8130-3, C of C ...)
  Aircraft Type                         -> aircraft model (Shop by Aircraft, aircraft filter) and the brand (aircraft OEM)
  Brand / Manufacturer / OEM (optional) -> brand; when the sheet has no such column the aircraft OEM is used
  Serial No. / Sr No (optional)         -> inventory serial number; without it, data row 1 is serial 1, and so on
Price, cost and quantity columns are not published (the site quotes on request).

Each data row becomes one product: one row is one physical unit, so a part number listed with three serial numbers gives
three products. Rows past --max-serial are ignored. Empty rows are skipped and listed in reports/inventory-skipped.csv.
The category is chosen from keywords in the description (scripts/inventory_rules.py) because the sheet has none.

Writes: data/catalog/products.jsonl, data/aircraft.js (every aircraft model in the sheet), reports/inventory-skipped.csv,
reports/inventory-import-<date>.md; then runs scripts/build-catalog.py (product, listing, brand and search files, sitemaps).
Product images come from data/catalog/product-images.json (scripts/find-product-images.py); a product without one shows
the placeholder picture of its category (images/placeholders/).
URL slugs are part number + short description; a product keeps its slug on later imports (matched by part number,
serial number and position among identical rows).
"""
import argparse, collections, csv, datetime, html, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_lib as L
import inventory_rules as R

DEFAULT_FILE = os.path.join(L.ROOT, 'assets', 'VELMACH AEROSPACE Master Parts Inventory 06-05-2026.xlsx')
IMAGES = os.path.join(L.CATALOG, 'product-images.json')
REPORTS = os.path.join(L.ROOT, 'reports')
PARENT = 'aircraft-parts'

# header text -> field. Matched on the header lowered with spaces collapsed; first matching pattern wins.
COLUMNS = [
    ('serial', r'^(s\.?\s*no\.?|sr\.?\s*no\.?|sl\.?\s*no\.?|serial\s*no\.?|#|no\.?)$'),
    ('altPn', r'^alt(ernate|\.)?\s*(p/?n|part)'),
    ('pn', r'^(part\s*(#|no\.?|number|num)?|p/?n|pn)$'),
    ('desc', r'^(description|desc\.?|part\s*name|nomenclature)$'),
    ('sn', r'^(s/n|serial\s*(number|#)|sn)$'),
    ('cond', r'^(cond\.?|condition(\s*code)?)$'),
    ('cert', r'8130|^cert|^trace'),
    ('aircraft', r'aircraft|a/c|plane|^model$|^application$'),
    ('brand', r'^(brand|manufacturer|mfr|mfg|oem|make)$'),
    ('category', r'^(category|type)$'),
]
R_PN = r'^(part\s*(#|no\.?|number|num)?|p/?n|pn)$'
NO_SERIAL = {'nsn', 'na', 'n/a', 'none', '-', 'tbd', 'unknown', 'no s/n'}


def clean(v, warn=None):
    """Cell value as trimmed text with single spaces; Excel numbers keep their digits (270, not 270.0)."""
    if v is None:
        return ''
    if isinstance(v, (datetime.datetime, datetime.date)):    # a serial number Excel turned into a date
        if warn:
            warn(f'date value {v:%Y-%m-%d} read as "{v:%b-%Y}"')
        return f'{v:%b-%Y}'
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r'\s+', ' ', str(v)).strip()


def find_header(ws):
    for n, row in enumerate(ws.iter_rows(min_row=1, max_row=10, values_only=True), 1):
        heads = [re.sub(r'\s+', ' ', str(c or '')).strip().lower() for c in row]
        if any(re.match(R_PN, h) for h in heads) and any(re.match(r'^desc', h) for h in heads):
            cols = {}
            for i, h in enumerate(heads):
                if not h:
                    continue
                for field, rx in COLUMNS:
                    if field not in cols and re.search(rx, h):
                        cols[field] = i
                        break
            return n, cols, heads
    raise SystemExit('No header row with a part number and a description column in the first 10 rows.')


def norm_brand(name):
    name = clean(name)
    if not name:
        return ''
    return R.BRAND_ALIASES.get(L.norm_key(name)) or ' '.join(w if w.isupper() and len(w) <= 4 else w.capitalize() for w in name.split())


def parse_aircraft(raw):
    """'Falcon 2000 SN 138' -> {'make': 'Dassault', 'model': 'Falcon 2000', 'oem': 'Dassault Aviation', 'airframe': '138', 'engine': ''}"""
    text = clean(raw)
    if text.lower() in R.NO_AIRCRAFT:
        return None
    info = {'raw': text, 'airframe': '', 'engine': ''}
    m = R.AIRFRAME_SN.search(text)
    if m:
        info['airframe'] = m.group(1)
        text = text[:m.start()].strip()
    m = R.ENGINE_NOTE.search(text)
    if m:
        info['engine'] = R.ENGINES.get(m.group(1), m.group(1)) + ' engine'
        text = text[:m.start()].strip()
    for pattern, make, model, oem in R.AIRCRAFT:
        m = re.search(pattern, text, re.I)
        if m:
            if model is None:   # take the model from the text: the last group ("800A", "45", "328")
                model = re.sub(r'\s+', '', m.group(m.lastindex)).upper()
            return {**info, 'make': make, 'model': model, 'oem': oem}
    # an aircraft the rules do not know yet: first word is the make, the rest the model; reported for review
    words = text.split()
    make = words[0].title()
    return {**info, 'make': make, 'model': ' '.join(words[1:]) or text, 'oem': norm_brand(make), 'unknown': True}


def short_desc(desc, words=5):
    return ' '.join(re.sub(r'[^\w\s/-]+', ' ', desc).split()[:words])


def load_images():
    try:
        return json.load(open(IMAGES, encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file', nargs='?', default=DEFAULT_FILE, help='inventory .xlsx (default: %(default)s)')
    ap.add_argument('--sheet', help='sheet name (default: the first sheet)')
    ap.add_argument('--max-serial', type=int, default=5560, help='import serial numbers 1..N only (default: %(default)s); 0 = every row')
    ap.add_argument('--no-build', action='store_true', help='do not run build-catalog.py afterwards')
    a = ap.parse_args()

    import openpyxl
    wb = openpyxl.load_workbook(a.file, read_only=True, data_only=True)
    ws = wb[a.sheet] if a.sheet else wb.worksheets[0]
    head_row, cols, heads = find_header(ws)
    if 'pn' not in cols:
        raise SystemExit('No part number column found.')
    print(f'{os.path.basename(a.file)} / sheet "{ws.title}": header on row {head_row}; columns: '
          + ', '.join(f'{f}="{heads[i]}"' for f, i in sorted(cols.items(), key=lambda x: x[1])))
    ignored = [h for i, h in enumerate(heads) if h and i not in cols.values()]
    if ignored:
        print('  columns not imported: ' + ', '.join(ignored))

    old = L.load_store()
    old_slug = {k: r['slug'] for k, r in old.items() if k.startswith('inv:')}
    old_created = {k: r.get('createdAt') for k, r in old.items() if k.startswith('inv:')}
    images, reps = load_images(), L.load_representative()
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()

    store, skipped, warnings = {}, [], []
    seen_unit = collections.Counter()
    taken = set()
    pos = 0
    for excel_row, row in enumerate(ws.iter_rows(min_row=head_row + 1, values_only=True), head_row + 1):
        cell = lambda f: row[cols[f]] if f in cols and cols[f] < len(row) else None
        pos += 1
        serial = pos
        if 'serial' in cols:
            s = clean(cell('serial'))
            serial = int(float(s)) if re.fullmatch(r'\d+(\.0+)?', s) else pos
        if a.max_serial and serial > a.max_serial:
            if 'serial' not in cols:
                break
            continue
        warn = lambda msg: warnings.append((serial, excel_row, msg))
        pn, desc = clean(cell('pn')), clean(cell('desc'))
        if not pn and not desc:
            skipped.append((serial, excel_row, '', 'empty row'))
            continue
        if not pn:
            skipped.append((serial, excel_row, desc, 'no part number'))
            continue
        alt = clean(cell('altPn'))
        sn = clean(cell('sn'), warn)
        if sn.lower() in NO_SERIAL:
            sn = ''
        code = clean(cell('cond')).upper()
        cond = R.CONDITIONS.get(code, code)
        if code and code not in R.CONDITIONS:
            warn(f'condition code "{code}" has no name in inventory_rules.CONDITIONS; shown as "{code}"')
        cert_raw = clean(cell('cert'))
        cert = R.CERT_ALIASES.get(L.norm_key(cert_raw), cert_raw)
        ac = parse_aircraft(cell('aircraft'))
        if ac and ac.get('unknown'):
            warn(f'aircraft "{ac["raw"]}" is not in inventory_rules.AIRCRAFT; read as make "{ac["make"]}", model "{ac["model"]}"')
        brand = norm_brand(cell('brand')) if 'brand' in cols else ''
        brand_basis = 'brand'
        if not brand and ac:
            brand, brand_basis = ac['oem'], 'aircraft OEM'
        cat = R.category_for(' '.join([desc, clean(cell('category'))]))

        unit = L.norm_key(pn) + '|' + (L.norm_key(sn) or '-')
        seen_unit[unit] += 1
        key = f'inv:{unit}|{seen_unit[unit]}'
        slug = old_slug.get(key)
        if not slug or slug in taken:
            base = L.slugify(f'{pn} {short_desc(desc)}', 70) or L.slugify(pn) or 'part'
            slug = base
            if slug in taken and sn:
                slug = L.slugify(f'{base} sn {sn}', 90)
            n = 2
            while slug in taken:
                slug = f'{base}-{n}'; n += 1
        taken.add(slug)

        specs = []                                   # part number and brand have their own rows on the product page
        if alt:
            specs.append({'name': 'Alternate part number', 'value': alt})
        if sn:
            specs.append({'name': 'Serial number (S/N)', 'value': sn})
        if code:
            specs.append({'name': 'Condition', 'value': f'{cond} ({code})' if cond != code else code})
        if cert:
            specs.append({'name': 'Certification (8130)', 'value': cert})
        if ac:
            specs.append({'name': 'Aircraft', 'value': f"{ac['make']} {ac['model']}"})
            if ac['airframe']:
                specs.append({'name': 'Aircraft serial number', 'value': ac['airframe']})
            if ac['engine']:
                specs.append({'name': 'Application', 'value': ac['engine']})
        specs.append({'name': 'Inventory serial no.', 'value': str(serial)})

        title = desc or pn
        sentence = f'{html.escape(title)}, part number {html.escape(pn)}'
        if ac:
            sentence += f", for the {html.escape(ac['make'] + ' ' + ac['model'])}"
        sentence += '.'
        extra = []
        if code:
            extra.append(f'Condition: {html.escape(cond)}.')
        if cert and cert not in ('N/A', 'No'):
            extra.append(f'Certification: {html.escape(cert if cert != "Yes" else "8130-3 available")}.')
        rec = {
            'key': key, 'id': L.product_id(key), 'slug': slug, 'pnDir': L.safe_part_number(pn),
            'title': title, 'partNumber': pn, 'altPartNumber': alt, 'serialNumber': sn, 'serialNo': serial,
            'brand': brand, 'brandSlug': L.slugify(brand) if brand else '', 'brandBasis': brand_basis if brand else '',
            'categoryParent': PARENT, 'categoryChild': cat,
            'shortDescription': ' '.join([sentence] + extra).replace('&amp;', '&'),
            'description': '<p>' + sentence + '</p>' + ('<p>' + ' '.join(extra) + '</p>' if extra else ''),
            'specifications': specs,
            'images': L.images_for({'partNumber': pn, 'title': title, 'id': L.product_id(key)}, images, reps),
            'placeholder': f"images/placeholders/{R.PLACEHOLDER.get(cat, 'generic')}.svg",
            'documents': [], 'compatibleAircraft': [L.aircraft_id(ac['make'], ac['model'])] if ac else [],
            'aircraftListed': ac['raw'] if ac else '', 'aircraftMake': ac['make'] if ac else '', 'aircraftModel': ac['model'] if ac else '',
            'condition': cond or 'Not stated', 'conditionCode': code, 'certification': cert, 'sample': False,
            'source': f'{os.path.basename(a.file)} row {excel_row}',
            'createdAt': old_created.get(key) or now, 'updatedAt': now,
        }
        store[key] = rec

    # ---- write ----
    removed = len([k for k in old if k not in store])
    L.save_store(store)
    write_aircraft(store.values())
    products = list(store.values())
    expected = (max((r['serialNo'] for r in products), default=0) if not a.max_serial else a.max_serial)
    write_reports(a, products, skipped, warnings, removed, expected)
    print(f'Imported {len(products)} products ({len(skipped)} rows skipped, {len(warnings)} warnings); '
          f'{removed} products not in the sheet removed from the catalogue.')
    if len(products) + len(skipped) != expected:
        print(f'  ! {len(products)} imported + {len(skipped)} skipped is not the expected {expected} rows: the sheet ends early or has gaps in its serial numbers')
    if not a.no_build:
        import importlib.util
        spec = importlib.util.spec_from_file_location('build_catalog', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build-catalog.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.build()


def write_aircraft(products):
    """data/aircraft.js: every aircraft make and model that has parts, so Shop by Aircraft and the filters list exactly these."""
    makes = {}
    for r in products:
        if r['aircraftMake']:
            makes.setdefault(r['aircraftMake'], set()).add(r['aircraftModel'])

    def model_key(m):
        return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', m)]
    rows = ',\n'.join('  { make: ' + json.dumps(mk) + ', models: [' + ', '.join(json.dumps(x) for x in sorted(ms, key=model_key)) + '] }'
                      for mk, ms in sorted(makes.items()))
    text = ('/* Velmach Aerospace: aircraft makes and models for "Shop by Aircraft" and the aircraft filter.\n'
            '   Written by scripts/import-inventory.py from the Aircraft Type column of the inventory: every model that has parts.\n'
            '   A product\'s compatibleAircraft list uses the same ids ("<make-slug>/<model-slug>", e.g. "dassault/falcon-2000").\n'
            '   To add or rename a model, edit AIRCRAFT in scripts/inventory_rules.py and re-run the import. */\n'
            'window.VM_AIRCRAFT = [\n' + rows + '\n];\n')
    L.write_if_changed(os.path.join(L.ROOT, 'data', 'aircraft.js'), text)


def grouped(warnings):
    """One line per kind of warning, with the serial numbers it applies to."""
    by = collections.OrderedDict()
    for serial, _, msg in warnings:
        by.setdefault(msg, []).append(str(serial))
    lines = []
    for m, v in by.items():
        more = f' and {len(v) - 30} more' if len(v) > 30 else ''
        lines.append(f"- {m}: serial {', '.join(v[:30])}{more} ({len(v)} rows)")
    return '\n'.join(lines)


def write_reports(a, products, skipped, warnings, removed, expected):
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(REPORTS, 'inventory-skipped.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['Serial No', 'Excel row', 'Description', 'Reason'])
        w.writerows(skipped)
    today = datetime.date.today().isoformat()
    count = lambda f: collections.Counter(f(r) for r in products)
    ac = count(lambda r: next((s['value'] for s in r['specifications'] if s['name'] == 'Aircraft'), '(no aircraft)'))
    listed = count(lambda r: r['aircraftListed'] or '(empty)')
    brands = count(lambda r: r['brand'] or '(no brand)')
    cats = count(lambda r: r['categoryChild'])
    conds = count(lambda r: f"{r['condition']} ({r['conditionCode']})" if r['conditionCode'] else '(not stated)')
    certs = count(lambda r: r['certification'] or '(empty)')
    with_img = sum(1 for r in products if r['images'] and r['images'][0].get('kind') != 'representative')
    with_rep = sum(1 for r in products if r['images'] and r['images'][0].get('kind') == 'representative')
    table = lambda c: '\n'.join(f'| {k} | {v} |' for k, v in sorted(c.items(), key=lambda x: (-x[1], x[0])))
    md = f"""# Inventory import {today}

Source: `{os.path.relpath(a.file, L.ROOT)}`, serial numbers 1 to {expected}.

| | |
|---|---|
| Rows read | {len(products) + len(skipped)} |
| Products imported | {len(products)} |
| Rows skipped | {len(skipped)} (reports/inventory-skipped.csv) |
| Distinct part numbers | {len({L.norm_key(r['partNumber']) for r in products})} |
| Products with a photo of the part | {with_img} |
| Products with a representative photo of their component type | {with_rep} |
| Products removed (not in the sheet) | {removed} |

## Aircraft (filter values)
| Aircraft | Products |
|---|---|
{table(ac)}

## Aircraft Type as written in the sheet
| Sheet value | Products |
|---|---|
{table(listed)}

## Brand (aircraft OEM)
| Brand | Products |
|---|---|
{table(brands)}

## Category (from the description)
| Subcategory | Products |
|---|---|
{table(cats)}

## Condition
| Condition | Products |
|---|---|
{table(conds)}

## Certification (8130 column)
| Value | Products |
|---|---|
{table(certs)}

## Warnings
{grouped(warnings) or 'None.'}
"""
    L.write_if_changed(os.path.join(REPORTS, f'inventory-import-{today}.md'), md)


if __name__ == '__main__':
    main()
