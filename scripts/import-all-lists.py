"""Add the products of every list in "assets/velmach product/list sheet": python scripts/import-all-lists.py [--no-build]

Existing products are kept as they are; only new products (and new brands) are added. Re-running replaces the products
an earlier run added (keys "sheet:", keeping their slugs and dates) and never touches the others.

Files (the folder is scanned recursively; every file is listed in reports/list-import-files.csv):
  oil and lubricants.xlsx, PRODUCT LIST.xlsx 2.xlsx       consumables (scripts/list_sheet_parsers.py)
  VELMACH AEROSPACE Master Parts Inventory *.xlsx          Part #, Description, Alt P/N, S/N, Condition, 8130, Aircraft Type
  2026-10-lead-time-updates.xlsx                           Part Number, Description, current / new lead time, % change
  AeroDirect_Rotable_Parts.xlsx                            Part Number, Description, Serial Number, Certified by, Cert Date,
                                                           Condition, Qty, Source
  REGIONAL AVIONICS STOCK INVENTORY.xlsx                   Item, Description, Condition, Quantity On Hand
  2026-10-seasonal-parts.xlsx                              A/C Model, Part Number, Description, Category, Bin Qty
  PICIMAGE.xlsx, product images.docx, embedded pictures    logos (brand and customer logos), not product photos
  products-export.csv                                      an export written by an earlier import: its rows are checked
                                                           against the lists above and not imported a second time
Values are kept as written; nothing is invented and an unknown field stays empty. The parts lists have no brand or
category: they go to Aircraft Parts without a subcategory and without a brand.

Duplicates (reports/list-import-duplicates.csv):
  - rows of the lists with the same part number are one product (the details of every row are kept: serial numbers,
    conditions, lead times ...); consumables without a part number merge by name (list_sheet_parsers)
  - a new product that is already on the website (same part number; or same name with the same or an unstated brand,
    and no different part number) is skipped, and the existing product is left unchanged
  - existing products that are the same product twice (same specific name containing a model number, same or unstated
    brand, no conflicting part number) keep the most complete entry; the others are removed
Images: no list has a product photo, so a new product shows its brand's logo (public/brands/<slug>.svg|png|webp; logos
cut from the sheet for brands without one: list_sheet_parsers.SHEET_LOGOS) or else the Velmach logo. It is shown as a
logo, never as a photo of the part.
Writes the store (data/catalog/store/), public/brands/<slug>.png (sheet logos), images/placeholders/velmach-logo.png,
reports/list-import-<date>.md and the CSV reports, then runs scripts/build-catalog.py.
"""
import argparse, collections, csv, datetime, html, importlib.util, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_lib as L
import list_sheet_parsers as P

SRC = P.SRC
REPORTS = os.path.join(L.ROOT, 'reports')
PREFIX = 'sheet:'
VELMACH_LOGO = P.VELMACH_LOGO
PARTS_PARENT = 'aircraft-parts'
NO_SERIAL = {'nsn', 'na', 'n/a', 'none', '-', 'no s/n'}

# parts lists: file pattern -> (header row, {column index: field}, file label). Fields with a "spec:" name become
# specifications; pn and desc are the part number and description.
PARTS = [
    (r'^VELMACH AEROSPACE Master Parts Inventory.*\.xlsx$', 2, {0: 'pn', 1: 'desc', 2: 'spec:Alternate part number', 3: 'spec:Serial number (S/N)',
                                                              4: 'cond', 5: 'spec:Certification (8130)', 6: 'spec:Aircraft'}, 'Master Parts Inventory'),
    (r'^2026-10-lead-time-updates\.xlsx$', 1, {0: 'pn', 1: 'desc', 2: 'spec:Current lead time (days)', 3: 'spec:New lead time (days)',
                                             4: 'spec:Lead time change (%)'}, 'Lead-time updates (Oct 2026)'),
    (r'^AeroDirect_Rotable_Parts\.xlsx$', 3, {0: 'pn', 1: 'desc', 2: 'spec:Serial number (S/N)', 3: 'spec:Certified by', 4: 'spec:Certification date',
                                            5: 'cond', 6: 'spec:Quantity', 7: 'spec:Source'}, 'AeroDirect rotable parts'),
    (r'^REGIONAL AVIONICS STOCK INVENTORY\.xlsx$', 3, {1: 'pn', 2: 'desc', 3: 'cond', 4: 'spec:Quantity on hand'}, 'Regional Avionics stock'),
    (r'^2026-10-seasonal-parts\.xlsx$', 1, {0: 'spec:A/C model', 1: 'pn', 2: 'desc', 3: 'spec:Category (as listed)', 4: 'spec:Bin quantity'},
     'Seasonal parts (Oct 2026)'),
]
CONSUMABLES = {P.OIL, P.PL2}
LOGO_FILES = {'PICIMAGE.xlsx': 'pictures only: customer, airline and aircraft-maker logo collages and a supplier link (no products)',
              'product images.docx': 'one picture: a collage of brand logos (no products)'}
EXPORT_FILE = 'products-export.csv'


def clean(v):
    """Cell value as written: trimmed text, Excel whole numbers without ".0", dates as YYYY-MM-DD."""
    if v is None:
        return ''
    if isinstance(v, (datetime.datetime, datetime.date)):
        return f'{v:%Y-%m-%d}'
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r'\s+', ' ', str(v).replace('\xa0', ' ')).strip()


def has_model(title):
    return bool(re.search(r'\d', title))


# ---------- reading ----------

def scan(src):
    files = []
    for root, _, names in os.walk(src):
        for n in sorted(names):
            files.append(os.path.relpath(os.path.join(root, n), src).replace(os.sep, '/'))
    return sorted(files)


def read_parts(src, files, log):
    """Parts lists -> {part-number key: record}; rows with the same part number merge, keeping every row's details."""
    import openpyxl
    parts = collections.OrderedDict()
    merged_rows = collections.Counter()
    for pattern, head, cols, label in PARTS:
        for f in [x for x in files if re.match(pattern, os.path.basename(x))]:
            ws = openpyxl.load_workbook(os.path.join(src, f), read_only=True, data_only=True).worksheets[0]
            n_rows = n_used = 0
            for excel_row, row in enumerate(ws.iter_rows(min_row=head + 1, values_only=True), head + 1):
                vals = {fld: clean(row[i]) if i < len(row) else '' for i, fld in cols.items()}
                if not any(vals.values()):
                    continue
                n_rows += 1
                pn = vals.pop('pn')
                if not pn:
                    log['no part number'].append((f, excel_row, vals.get('desc', '')))
                    continue
                n_used += 1
                k = L.norm_key(pn)
                r = parts.get(k)
                if r is None:
                    r = parts[k] = {'pn': pn, 'title': '', 'conds': [], 'specs': collections.OrderedDict(), 'units': 0,
                                    'sources': collections.OrderedDict(), 'first': f'{f} row {excel_row}'}
                else:
                    merged_rows[k] += 1
                r['units'] += 1
                r['sources'][label] = r['sources'].get(label, 0) + 1
                if vals.get('desc') and not r['title']:
                    r['title'] = vals['desc']
                elif vals.get('desc') and L.norm_key(vals['desc']) != L.norm_key(r['title']):
                    r['specs'].setdefault('Other description', []).append(vals['desc'])
                c = vals.get('cond', '')
                if c and c not in r['conds']:
                    r['conds'].append(c)
                for fld, v in vals.items():
                    if not fld.startswith('spec:') or not v:
                        continue
                    name = fld[5:]
                    if name == 'Serial number (S/N)' and v.lower() in NO_SERIAL:
                        v = v.upper()                     # "NSN": no serial number, kept as written
                    lst = r['specs'].setdefault(name, [])
                    if v not in lst:
                        lst.append(v)
            log['files'].append((f, 'parts list', f'{n_rows} rows, {n_used} with a part number'))
    return parts, merged_rows


def read_export(src, files):
    out = []
    for f in [x for x in files if os.path.basename(x) == EXPORT_FILE]:
        with open(os.path.join(src, f), encoding='utf-8-sig', newline='') as fh:
            for i, row in enumerate(csv.DictReader(fh), 2):
                out.append((f, i, row.get('Part number', ''), row.get('Title', ''), row.get('Brand', '')))
    return out


# ---------- existing catalogue ----------

class Existing:
    """Lookup of the products already on the website: by part number, and by name (+ brand)."""

    def __init__(self, store):
        self.by_pn, self.by_name = {}, collections.defaultdict(list)
        for r in store.values():
            if L.norm_key(r['partNumber']):
                self.by_pn.setdefault(L.norm_key(r['partNumber']), r)
            self.by_name[L.norm_key(r['title'])].append(r)

    def match(self, pn, title, brand):
        """(existing product, reason) or (None, '')."""
        kp, kb = L.norm_key(pn), L.norm_key(brand)
        if kp and kp in self.by_pn:
            return self.by_pn[kp], 'same part number'
        for r in self.by_name.get(L.norm_key(title), []):
            rp, rb = L.norm_key(r['partNumber']), L.norm_key(r['brand'])
            # a generic name ("ELT", "Valve") does not identify a product that has its own part number
            if kp and not rp and not has_model(title):
                continue
            if (not kp or not rp or kp == rp) and (not kb or not rb or kb == rb):
                return r, 'same name' + (' and brand' if kb and rb else '')
        return None, ''


def completeness(r):
    return (sum(1 for f in ('partNumber', 'brand', 'categoryChild', 'shortDescription', 'description') if r.get(f))
            + 5 * len(r.get('images') or []) + len(r.get('specifications') or []) + 2 * len(r.get('documents') or []))


def existing_duplicates(store):
    """Groups of existing products that are one product twice: the same specific name (with a model number), the same or
    an unstated brand and no conflicting part number. Returns [(kept, [removed])]."""
    groups = collections.defaultdict(list)
    for r in store.values():
        if not r['key'].startswith(PREFIX) and has_model(r['title']):
            groups[L.norm_key(r['title'])].append(r)
    out = []
    for g in groups.values():
        if len(g) < 2:
            continue
        pns = {L.norm_key(x['partNumber']) for x in g if L.norm_key(x['partNumber'])}
        brands = {L.norm_key(x['brand']) for x in g if L.norm_key(x['brand'])}
        if len(pns) > 1 or len(brands) > 1:
            continue
        g = sorted(g, key=lambda x: (-completeness(x), x.get('createdAt') or '', x['slug']))
        out.append((g[0], g[1:]))
    return out


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', default=SRC)
    ap.add_argument('--no-build', action='store_true', help='do not run build-catalog.py afterwards')
    a = ap.parse_args()
    files = scan(a.src)
    log = collections.defaultdict(list)

    # consumables
    col, cons, conflicts, sheet1 = P.extract(a.src)
    for f in sorted(CONSUMABLES):
        n = sum(1 for r in col.rows if r['file'] == f)
        log['files'].append((f, 'consumables list', f'{n} product rows; ' + '; '.join(col.notes.get(f, []))))
    # parts lists
    parts, merged_rows = read_parts(a.src, files, log)
    export_rows = read_export(a.src, files)
    for f in files:
        b = os.path.basename(f)
        if b in LOGO_FILES:
            log['files'].append((f, 'pictures', LOGO_FILES[b]))
        elif b == EXPORT_FILE:
            log['files'].append((f, 'export of an earlier import', f'{len(export_rows)} rows, checked for duplicates'))
    handled = {x[0] for x in log['files']}
    for f in files:
        if f not in handled:
            log['files'].append((f, 'not read', 'not a product list this import knows'))

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
    existing_before = len(store)

    # existing duplicates
    removed_existing = []
    for kept, extra in existing_duplicates(store):
        for r in extra:
            removed_existing.append((r, kept))
            del store[r['key']]
    existing = Existing(store)

    # candidates: consumables first, then parts lists (a part number in both is one product: the consumable's entry)
    dup_log, candidates, seen_pn = [], [], {}
    for p in cons:
        candidates.append(('cons', p))
        if L.norm_key(p['partNumber']):
            seen_pn[L.norm_key(p['partNumber'])] = p['title']
    for k, r in parts.items():
        if k in seen_pn:
            dup_log.append(('merged in the new data', r['pn'], r['title'], f'also in the consumables lists as "{seen_pn[k]}"', ''))
            continue
        candidates.append(('part', r))
    for k, n in merged_rows.items():
        r = parts[k]
        dup_log.append(('merged in the new data', r['pn'], r['title'], f'{n + 1} rows with this part number in the lists ('
                        + ', '.join(f'{s}: {c}' for s, c in r['sources'].items()) + ')', ''))

    # brands and logos
    # brands the website had before: those of its existing products (data/brands.js is rewritten by every build)
    known_brands = {L.norm_key(r['brand']): r['brand'] for r in store.values() if r['brand']}
    brands_used = {L.slugify(p['brand']) for kind, p in candidates if kind == 'cons' and p['brand']}
    logos_saved = P.save_sheet_logos(sheet1, brands_used)
    os.makedirs(os.path.join(L.ROOT, 'images', 'placeholders'), exist_ok=True)
    shutil.copyfile(P.VELMACH_LOGO_SRC, os.path.join(L.ROOT, VELMACH_LOGO))

    taken = {r['slug'] for r in store.values()}
    old_slug = {k: r['slug'] for k, r in old_added.items()}
    old_created = {k: r.get('createdAt') for k, r in old_added.items()}
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    added, skipped_existing, how_cat = [], [], collections.Counter()
    for kind, p in candidates:
        if kind == 'cons':
            key = PREFIX + p['key']
            pn, title, brand = p['partNumber'], p['title'] or p['partNumber'], p['brand']
        else:
            key = PREFIX + 'pn:' + L.norm_key(p['pn'])
            pn, title, brand = p['pn'], p['title'] or p['pn'], ''
        hit, why = existing.match(pn, title, brand)
        if hit:
            skipped_existing.append((pn, title, brand, hit, why))
            continue
        if kind == 'cons':
            parent, child, how = P.categorize(p, cname)
            specs = [{'name': k, 'value': v} for k, v in p['specifications'].items() if v]
            if p['cat_doc']:
                specs.append({'name': 'Listed under', 'value': ' / '.join(p['cat_doc'])})
            desc_extra = p['description']
            cond_code, cond, cert, aircraft_ids, aircraft_listed = '', 'Not stated', '', [], ''
            sources = '; '.join(p['sources'])
        else:
            parent, child, how = PARTS_PARENT, '', 'parts list (no category in the list)'
            specs = [{'name': k, 'value': ', '.join(v)} for k, v in p['specs'].items()]
            if p['units'] > 1:
                specs.append({'name': 'Rows in the lists', 'value': str(p['units'])})
            specs.append({'name': 'Listed in', 'value': ', '.join(p['sources'])})
            desc_extra = ''
            # the filter uses the first condition that is a code ("IN", "SV"); "-" or "." state nothing
            cond_code = next((c for c in p['conds'] if re.search(r'[A-Za-z]', c)), '')
            cond = ', '.join(p['conds']) or 'Not stated'
            cert = ', '.join(p['specs'].get('Certification (8130)', []))
            aircraft_listed = ', '.join(p['specs'].get('Aircraft', []))
            # the seasonal list names Boeing models by number ("747", "787")
            aircraft_ids = sorted({f'boeing/{m}' for m in p['specs'].get('A/C model', []) if re.fullmatch(r'7[0-9]7', m)})
            sources = p['first'] + (f' (+{p["units"] - 1} more rows)' if p['units'] > 1 else '')
        how_cat[how] += 1
        bslug = L.slugify(brand) if brand else ''
        logo, dark = P.find_logo(bslug) if bslug else ('', False)
        slug = old_slug.get(key)
        if not slug or slug in taken:
            base = L.slugify(title if not pn or L.norm_key(pn) in L.norm_key(title) else f'{pn} {title}', 70) or L.slugify(pn) or 'product'
            slug, n = base, 2
            while slug in taken:
                slug = f'{base}-{n}'; n += 1
        taken.add(slug)
        sentence = html.escape(title) + (f', part number {html.escape(pn)}' if pn and L.norm_key(pn) not in L.norm_key(title) else '') \
            + (f', by {html.escape(brand)}' if brand else '') + '.'
        extra = html.escape(desc_extra) if desc_extra else ''
        rec = {
            'key': key, 'id': L.product_id(key), 'slug': slug, 'pnDir': L.safe_part_number(pn or slug),
            'title': title, 'partNumber': pn, 'altPartNumber': ', '.join(p['specs'].get('Alternate part number', [])) if kind == 'part' else '',
            'serialNumber': '', 'brand': brand, 'brandSlug': bslug, 'brandBasis': 'brand' if brand else '',
            'categoryParent': parent, 'categoryChild': child,
            'shortDescription': (sentence + (' ' + extra if extra else '')).replace('&amp;', '&'),
            'description': '<p>' + sentence + '</p>' + (f'<p>{extra}</p>' if extra else ''),
            'specifications': specs, 'images': [],
            'placeholder': logo if logo and not dark else VELMACH_LOGO,
            'placeholderKind': 'brand logo' if logo and not dark else 'company logo',
            'documents': [], 'compatibleAircraft': aircraft_ids, 'aircraftListed': aircraft_listed,
            'condition': cond, 'conditionCode': cond_code if len(cond_code) <= 4 else '', 'certification': cert, 'sample': False,
            'source': sources, 'createdAt': old_created.get(key) or now, 'updatedAt': now,
        }
        prev = old_added.get(key)
        if prev and {k: v for k, v in prev.items() if k != 'updatedAt'} == {k: v for k, v in rec.items() if k != 'updatedAt'}:
            rec['updatedAt'] = prev.get('updatedAt', now)
        store[key] = rec
        added.append(rec)
        if L.norm_key(pn):
            existing.by_pn.setdefault(L.norm_key(pn), rec)    # later rows naming this part number are the same product
        if kind == 'cons':
            existing.by_name[L.norm_key(title)].append(rec)

    # export rows: every row should be a product of the lists above or of the website
    export_status = collections.Counter()
    for f, i, pn, title, brand in export_rows:
        hit, _ = existing.match(pn, title, brand)
        if hit:
            export_status['duplicate'] += 1
        else:
            export_status['not found'] += 1
            log['export not matched'].append((f, i, pn, title))

    L.save_store(store)
    new_brands = sorted({r['brand'] for r in added if r['brand'] and L.norm_key(r['brand']) not in known_brands}, key=str.lower)
    write_reports(files, log, cons, parts, col, added, skipped_existing, dup_log, removed_existing, new_brands, logos_saved,
                  how_cat, existing_before, export_status, conflicts)
    print(f'Files scanned: {len(files)}. New products added: {len(added)}; already on the website (skipped): {len(skipped_existing)}; '
          f'existing duplicates removed: {len(removed_existing)}; new brands: {len(new_brands)}.')
    if not a.no_build:
        spec = importlib.util.spec_from_file_location('build_catalog', os.path.join(L.ROOT, 'scripts', 'build-catalog.py'))
        B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
        B.build()


def write_reports(files, log, cons, parts, col, added, skipped_existing, dup_log, removed_existing, new_brands, logos_saved,
                  how_cat, existing_before, export_status, conflicts):
    os.makedirs(REPORTS, exist_ok=True)
    today = datetime.date.today().isoformat()

    def write_csv(name, header, rows):
        with open(os.path.join(REPORTS, name), 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f); w.writerow(header); w.writerows(rows)

    write_csv('list-import-files.csv', ['File', 'Read as', 'Result'], log['files'])
    write_csv('list-import-duplicates.csv', ['Action', 'Part number', 'Name', 'Reason', 'Existing product (kept)'],
              [('skipped: already on the website', pn, t, why + (f' (brand {b})' if b else ''), f'{h["title"]} | {h["partNumber"]} | product.dc.html?p={h["slug"]}')
               for pn, t, b, h, why in skipped_existing]
              + [('removed: existing duplicate', r['partNumber'], r['title'], 'same product as the kept entry, which is more complete',
                  f'{k["title"]} | {k["partNumber"]} | product.dc.html?p={k["slug"]}') for r, k in removed_existing]
              + dup_log)
    write_csv('list-import-new-brands.csv', ['Brand', 'Products added', 'Logo'],
              [(b, sum(1 for r in added if r['brand'] == b), next((r['placeholder'] for r in added if r['brand'] == b and r['placeholderKind'] == 'brand logo'), 'none: Velmach logo'))
               for b in new_brands])
    write_csv('list-import-no-part-number.csv', ['File', 'Excel row', 'Description'], log['no part number'])
    write_csv('list-import-conflicts.csv', ['Product', 'Field', 'Value used', 'Other values (source)'],
              [(who, field, chosen[0], ' || '.join(f'{v} ({s})' for v, s, _ in vals if v != chosen[0])) for who, field, vals, chosen in conflicts])
    C = collections.Counter
    img = C(r['placeholderKind'] for r in added)
    by_source = C('Consumables lists' if r['source'].startswith((P.OIL, P.PL2)) else 'Parts lists' for r in added)
    rows_parts = sum(r['units'] for r in parts.values())
    missing = C()
    for r in added:
        for name, v in (('part number', r['partNumber']), ('brand', r['brand']), ('subcategory', r['categoryChild']),
                        ('description beyond the name', '</p><p>' in r['description'] or r['specifications'])):
            if not v:
                missing[name] += 1
    lines = [
        f'# List-sheet import {today}', '', 'Source: `assets/velmach product/list sheet` (scripts/import-all-lists.py)', '',
        '| | |', '|---|---|',
        f'| Files scanned | {len(files)} (reports/list-import-files.csv) |',
        f'| Product rows in the consumables lists | {len(col.rows)} (→ {len(cons)} products after merging the same part number / name) |',
        f'| Rows in the parts lists | {rows_parts} (→ {len(parts)} distinct part numbers) |',
        f'| Rows without a part number (not imported) | {len(log["no part number"])} (reports/list-import-no-part-number.csv) |',
        f'| Existing products before the import | {existing_before} |',
        f'| Existing duplicates removed | {len(removed_existing)} |',
        f'| Existing products kept unchanged | {existing_before - len(removed_existing)} |',
        f'| New products already on the website (skipped) | {len(skipped_existing)} |',
        f'| New products added | {len(added)} |',
        f'| New brands added | {len(new_brands)} (reports/list-import-new-brands.csv) |',
        f'| Brand logos cut from the sheet | {", ".join(logos_saved) or "none"} |',
        f'| products-export.csv rows | {sum(export_status.values())}: {export_status["duplicate"]} duplicates of products on the site, {export_status["not found"]} not found |',
        '', '## Added products by source', '| Source | Products |', '|---|---|'] + [f'| {k} | {v} |' for k, v in by_source.most_common()] + [
        '', '## Image of the added products', '| Image | Products |', '|---|---|'] + [f'| {k} | {v} |' for k, v in img.most_common()] + [
        '| Real product photo | 0 (no list contains a product photo) |',
        '', '## Category basis', '| Basis | Products |', '|---|---|'] + [f'| {k} | {v} |' for k, v in how_cat.most_common()] + [
        '', '## Missing data in the added products', '| Missing | Products |', '|---|---|'] + [f'| {k} | {v} |' for k, v in missing.most_common()] + [
        f'| price | {len(added)} (no list has a price) |',
        '', '## New brands'] + [f'- {b}' for b in new_brands] + ['', '## Files'] + [f'- {f}: {kind}; {res}' for f, kind, res in log['files']]
    if log['export not matched']:
        lines += ['', '## products-export.csv rows not matched'] + [f'- {f} row {i}: {pn} {t}' for f, i, pn, t in log['export not matched'][:200]]
    with open(os.path.join(REPORTS, f'list-import-{today}.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
