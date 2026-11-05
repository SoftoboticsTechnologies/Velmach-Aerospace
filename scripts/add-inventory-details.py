"""Add the Master Parts Inventory details to products that were on the site before the list import:
python scripts/add-inventory-details.py

scripts/import-all-lists.py skipped inventory rows whose part number was already on the website and left those
products unchanged, so their inventory details (alternate P/N, serial numbers, condition, 8130, aircraft) never
reached the site. This adds them as specifications, the way the import writes them for its own products: values as
written, rows with the same part number joined with ", ". Nothing on the product is replaced: a specification is
only added when the product has none of that name, and aircraftListed / compatibleAircraft only when empty.
Writes data/catalog/store/*.jsonl and reports/inventory-details-added.csv; then run
scripts/fill-brands-aircraft.py (links the aircraft) and scripts/build-catalog.py.
"""
import collections, csv, datetime, glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_lib as L
import openpyxl

SRC = os.path.join('assets', 'velmach product', 'list sheet')
NO_SERIAL = {'nsn', 'na', 'n/a', 'none', '-', 'no s/n'}
COLS = {2: 'Alternate part number', 3: 'Serial number (S/N)', 4: 'Condition (inventory)', 5: 'Certification (8130)', 6: 'Aircraft'}


def clean(v):
    """Cell value as written (same as import-all-lists.py)."""
    if v is None:
        return ''
    if isinstance(v, (datetime.datetime, datetime.date)):
        return f'{v:%Y-%m-%d}'
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r'\s+', ' ', str(v).replace('\xa0', ' ')).strip()


def read_inventory():
    f = next(x for x in glob.glob(os.path.join(SRC, 'VELMACH AEROSPACE Master Parts Inventory*.xlsx')))
    ws = openpyxl.load_workbook(f, read_only=True, data_only=True).worksheets[0]
    parts = {}
    for n, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        pn = clean(row[0]) if row else ''
        if not pn:
            continue
        r = parts.setdefault(L.norm_key(pn), {'rows': [], 'specs': collections.OrderedDict()})
        r['rows'].append(n)
        for i, name in COLS.items():
            v = clean(row[i]) if i < len(row) else ''
            if not v:
                continue
            if name == 'Serial number (S/N)' and v.lower() in NO_SERIAL:
                v = v.upper()
            lst = r['specs'].setdefault(name, [])
            if v not in lst:
                lst.append(v)
    return os.path.basename(f), parts


def main():
    fname, inv = read_inventory()
    # part numbers the list import already published as its own products
    imported = set()
    for g in glob.glob('data/catalog/store/*.jsonl'):
        for l in open(g, encoding='utf-8'):
            p = json.loads(l)
            if p['key'].startswith('sheet:') and p.get('partNumber'):
                imported.add(L.norm_key(p['partNumber']))
    log = []
    for g in sorted(glob.glob('data/catalog/store/*.jsonl')):
        rows = [json.loads(l) for l in open(g, encoding='utf-8') if l.strip()]
        changed = False
        for p in rows:
            if p['key'].startswith('sheet:'):
                continue
            keys = {L.norm_key(x) for x in (p.get('partNumber'), p.get('altPartNumber')) if x}
            m = re.match(r'^\w+:pn:(.+)$', p['key'])
            if m:
                keys.add(m.group(1))
            hit = next((k for k in keys if k in inv and k not in imported), None)
            if not hit:
                continue
            r, have = inv[hit], {s['name'] for s in p.get('specifications') or []}
            added = []
            specs = p.setdefault('specifications', [])
            for name, vals in r['specs'].items():
                if name not in have:
                    specs.append({'name': name, 'value': ', '.join(vals)})
                    added.append(name)
            if 'Listed in' not in have:
                specs.append({'name': 'Listed in', 'value': 'Master Parts Inventory'
                              + (f' ({len(r["rows"])} rows)' if len(r['rows']) > 1 else '')})
                added.append('Listed in')
            if r['specs'].get('Aircraft') and not p.get('aircraftListed'):
                p['aircraftListed'] = ', '.join(r['specs']['Aircraft'])
            if added:
                changed = True
                log.append((p['slug'], p['title'], hit, '; '.join(added), f'{fname} rows ' + ', '.join(map(str, r['rows'][:10]))
                            + (' ...' if len(r['rows']) > 10 else '')))
        if changed:
            with open(g, 'w', encoding='utf-8', newline='\n') as w:
                for p in rows:
                    w.write(json.dumps(p, ensure_ascii=False, separators=(',', ':')) + '\n')
    with open('reports/inventory-details-added.csv', 'w', encoding='utf-8-sig', newline='') as w:
        c = csv.writer(w)
        c.writerow(['slug', 'title', 'part number (normalised)', 'specifications added', 'inventory rows'])
        c.writerows(log)
    print(f'products given inventory details: {len(log)}')


if __name__ == '__main__':
    main()
