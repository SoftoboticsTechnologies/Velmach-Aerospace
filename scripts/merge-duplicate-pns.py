"""Merge products that are the same part number twice: python scripts/merge-duplicate-pns.py

The list import compared part numbers with each product's "partNumber" field, but some older products keep their part
number only in their key ("doc:pn:<part number>"), so the same part was added a second time. For every part number on
more than one product, the most complete product is kept (a product with photos first, then the one with the most
filled-in fields) and the others are removed; what only a removed product had is copied into the kept one:
specifications it does not have, the part number, brand, aircraft and condition when empty. Nothing the kept product
already has is replaced. Log: reports/duplicates-merged-<date>.csv. Then run scripts/build-catalog.py.
"""
import collections, csv, datetime, glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_lib as L

# part numbers shared by different products (checked by hand on 2026-11-05): never merged
SEPARATE = {'3328', '53200', '74', '38004', '51007', '7020013'}


def pn_of(p):
    if p.get('partNumber'):
        return p['partNumber']
    m = re.match(r'^\w+:pn:(.+)$', p['key'])
    return m.group(1) if m else ''


def score(p):
    filled = sum(1 for f in ('partNumber', 'brand', 'categoryChild', 'shortDescription', 'description', 'aircraftListed') if p.get(f))
    return (bool(p.get('images')), len(p.get('documents') or []), filled, len(p.get('specifications') or []), not p['key'].startswith('sheet:'))


def merge(keep, other):
    added = []
    have = {s['name'] for s in keep.get('specifications') or []}
    for s in other.get('specifications') or []:
        if s['name'] not in have:
            keep.setdefault('specifications', []).append(s)
            have.add(s['name'])
            added.append(s['name'])
    if not keep.get('partNumber') and other.get('partNumber'):
        keep['partNumber'] = other['partNumber']; added.append('partNumber')
    if not keep.get('brand') and other.get('brand'):
        keep['brand'], keep['brandSlug'] = other['brand'], other.get('brandSlug') or L.slugify(other['brand'])
        keep['brandBasis'] = other.get('brandBasis', ''); added.append('brand')
    for f in ('aircraftListed', 'compatibleAircraft', 'certification', 'altPartNumber', 'categoryChild'):
        if not keep.get(f) and other.get(f) and (f != 'categoryChild' or other.get('categoryParent') == keep.get('categoryParent')):
            keep[f] = other[f]; added.append(f)
    if (keep.get('condition') in (None, '', 'Not stated')) and other.get('condition') not in (None, '', 'Not stated'):
        keep['condition'] = other['condition']; added.append('condition')
        if other.get('conditionCode') and not keep.get('conditionCode'):
            keep['conditionCode'] = other['conditionCode']
    return added


def main():
    files = {g: [json.loads(l) for l in open(g, encoding='utf-8') if l.strip()] for g in sorted(glob.glob('data/catalog/store/*.jsonl'))}
    groups = collections.defaultdict(list)
    for g, rows in files.items():
        for p in rows:
            pn = pn_of(p)
            if pn:
                groups[L.norm_key(pn)].append(p)
    remove, log = set(), []
    for k, ps in groups.items():
        if len(ps) < 2 or k in SEPARATE:
            continue
        ps.sort(key=score, reverse=True)
        keep = ps[0]
        for o in ps[1:]:
            added = merge(keep, o)
            remove.add(o['key'])
            log.append((pn_of(keep), keep['title'], keep['slug'], o['title'], o['slug'], '; '.join(added)))
    for g, rows in files.items():
        out = [p for p in rows if p['key'] not in remove]
        with open(g, 'w', encoding='utf-8', newline='\n') as w:
            for p in out:
                w.write(json.dumps(p, ensure_ascii=False, separators=(',', ':')) + '\n')
    # old links keep working: the product page looks a missing slug up here (js/catalog.js)
    mpath = 'data/catalog/moved.json'
    moved = json.load(open(mpath, encoding='utf-8')) if os.path.exists(mpath) else {}
    moved.update({x[4]: x[2] for x in log})
    with open(mpath, 'w', encoding='utf-8') as w:
        json.dump(dict(sorted(moved.items())), w, ensure_ascii=False, separators=(',', ':'))
    rep = f'reports/duplicates-merged-{datetime.date.today().isoformat()}.csv'
    with open(rep, 'w', encoding='utf-8-sig', newline='') as w:
        c = csv.writer(w)
        c.writerow(['part number', 'kept product', 'kept slug', 'removed product', 'removed slug (URL no longer works)', 'copied into the kept product'])
        c.writerows(log)
    print(f'duplicates removed: {len(remove)}; log: {rep}')


if __name__ == '__main__':
    main()
