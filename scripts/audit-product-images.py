"""Product image audit: python scripts/audit-product-images.py

Writes reports/product_image_audit.csv with one line per product in data/catalog/products.jsonl (every inventory row),
built from what is recorded, never guessed:
  - the product itself (part number, alternate part number, brand, category, the image it has now)
  - the image search of its part number: data/catalog/.image-state.json and data/catalog/product-images.json, written by
    scripts/find-product-images.py, plus any manual searches listed in reports/image-search-log.csv
    (columns: Part Number, Query, Engine, Date, Result, Source URL, Note)
Products that share a part number share one search and one photo, so they carry the same search columns.

Statuses: Placeholder (no suitable image: not searched by part number, and no representative photo for its component
type), Representative image (a labelled photo of its component type, scripts/representative-images.py), Verified (photo passed every check and is on the product: Integration Status
Integrated), Needs Manual Review (a candidate photo waits in reports/image-review.csv, the search failed, or the record is
too thin to search reliably), Unresolved (searched, nothing shows the exact part number with a real product photo).
Also writes reports/product-image-audit-summary.md: totals, duplicate part numbers, photos shared by different part numbers,
missing image files and incomplete records. Safe to run any time; it changes nothing but the two reports.
"""
import collections, csv, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_lib as L
from component_types import LABELS, component_type

STATE = os.path.join(L.CATALOG, '.image-state.json')
IMAGES = os.path.join(L.CATALOG, 'product-images.json')
LOG = os.path.join(L.ROOT, 'reports', 'image-search-log.csv')
OUT = os.path.join(L.ROOT, 'reports', 'product_image_audit.csv')
SUMMARY = os.path.join(L.ROOT, 'reports', 'product-image-audit-summary.md')
COLUMNS = ['Processing ID', 'Product ID', 'Product Name', 'SKU', 'Model Number', 'Brand', 'Category', 'Existing Image',
           'Search Queries Used', 'Image Source', 'Source URL', 'Downloaded Image Path', 'Match Confidence',
           'Verification Status', 'Integration Status', 'Failure Reason']


def load(path, default):
    try:
        return json.load(open(path, encoding='utf-8'))
    except (OSError, ValueError):
        return default


def load_log():
    """Manual searches by part number key: [{Query, Engine, Date, Result, Source URL, Note}]."""
    out = collections.defaultdict(list)
    if os.path.exists(LOG):
        for r in csv.DictReader(open(LOG, encoding='utf-8-sig')):
            out[L.norm_key(r['Part Number'])].append(r)
    return out


def thin(r):
    """Why a record is too thin to search reliably, or ''."""
    pn = L.norm_key(r['partNumber'])
    if len(pn) < 4:
        return f'part number "{r["partNumber"]}" is too short to identify one product'
    if not r.get('title') or r['title'].lower() in ('part', 'assy', 'assembly', 'unit', 'misc'):
        return 'no usable description'
    return ''


def main():
    store = L.load_store()
    state, found, log = load(STATE, {}), load(IMAGES, {}), load_log()
    reps = L.load_representative()
    rows = sorted(store.values(), key=lambda r: r.get('serialNo') or 0)
    counts = collections.Counter()
    for r in rows:
        counts[L.norm_key(r['partNumber'])] += 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tally, missing_files, out = collections.Counter(), [], []
    for r in rows:
        k = L.norm_key(r['partNumber'])
        st, img, manual = state.get(k, {}), found.get(k), log.get(k, [])
        queries = [f'{q["q"]} [search API {st.get("tried", "")}]' for q in st.get('queries', [])] + \
                  [f'{m["Query"]} [{m["Engine"]} {m["Date"]}]' for m in manual]
        best = st.get('best') or {}
        existing = r['images'][0]['large'] if r.get('images') else (r.get('placeholder') or '') + ' (placeholder)'
        line = {c: '' for c in COLUMNS}
        line.update({'Processing ID': f'VMA-{r.get("serialNo") or 0:05d}', 'Product ID': r['id'], 'Product Name': r['title'],
                     'SKU': r['partNumber'], 'Model Number': r.get('altPartNumber', ''), 'Brand': r.get('brand', ''),
                     'Category': f'{r["categoryParent"]}/{r.get("categoryChild", "")}', 'Existing Image': existing,
                     'Search Queries Used': ' | '.join(queries)})
        if img:
            path = img.get('large', '')
            if path and not os.path.exists(os.path.join(L.ROOT, path)):
                missing_files.append(path)
            on_product = bool(r.get('images')) and r['images'][0].get('large') == path
            line.update({'Image Source': f'{img.get("site", "")} ({img.get("attribution", "")}; licence: {img.get("license", "")})',
                         'Source URL': img.get('page', ''), 'Downloaded Image Path': path,
                         'Match Confidence': 'High: ' + ', '.join(best.get('checks', [])) + f' ({img.get("verified", "")})',
                         'Verification Status': 'Verified', 'Integration Status': 'Integrated' if on_product else 'Downloaded'})
        elif r.get('images') and r['images'][0].get('kind') == 'representative':
            line.update({'Image Source': r['images'][0].get('credit', ''), 'Source URL': r['images'][0].get('src', ''),
                         'Downloaded Image Path': r['images'][0]['large'], 'Match Confidence': 'Component type only (labelled on the page)',
                         'Verification Status': 'Representative image', 'Integration Status': 'Integrated',
                         'Failure Reason': 'no photo of this exact part found' if st or manual else ''})
        elif st.get('status') == 'error' and not manual:
            line.update({'Verification Status': 'Needs Manual Review', 'Integration Status': 'Placeholder kept',
                         'Failure Reason': f'search error (retried on the next run): {st.get("error", "")}'})
        elif best:
            line.update({'Image Source': best.get('site', ''), 'Source URL': best.get('page', ''), 'Downloaded Image Path': best.get('large', ''),
                         'Match Confidence': 'Medium: ' + ', '.join(best.get('checks', [])), 'Verification Status': 'Needs Manual Review',
                         'Integration Status': 'Staged, not published (reports/image-review.csv)',
                         'Failure Reason': '; '.join(x for x in [best.get('reason', ''), 'same picture as ' + ', '.join(st['shared'])
                                                                  if st.get('shared') else ''] if x)})
        elif st or manual:
            notes = [m['Note'] for m in manual if m.get('Note')] + ([st['reason']] if st.get('reason') else [])
            line.update({'Verification Status': 'Unresolved', 'Integration Status': 'Placeholder kept',
                         'Failure Reason': '; '.join(notes) or 'no result shows the exact part number with a product photo'})
        elif thin(r):
            line.update({'Verification Status': 'Needs Manual Review', 'Integration Status': 'Placeholder kept', 'Failure Reason': thin(r)})
        else:
            # not searched by part number (that search was stopped); its component type was reviewed for a representative photo
            t = component_type(r['title'])
            why = (f'component type "{LABELS[t]}": no suitable free photo found (reviewed on Wikimedia Commons)' if t
                   else 'description matches no component type')
            if t and t in reps and reps[t].get('aircraft'):
                why = f'representative photo of {LABELS[t].lower()} is for {reps[t]["aircraft"].lstrip("^")} only'
            line.update({'Verification Status': 'Placeholder (no suitable image)', 'Integration Status': 'Placeholder kept',
                         'Failure Reason': why})
        tally[line['Verification Status']] += 1
        out.append(line)

    with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, COLUMNS)
        w.writeheader()
        w.writerows(out)

    # photos used for more than one part number: suspicious, the finder should never do this
    by_image = collections.defaultdict(set)
    for k, img in found.items():
        by_image[img.get('source', '')].add(k)
    shared = {s: ks for s, ks in by_image.items() if s and len(ks) > 1}
    dup_pn = sorted(((n, k) for k, n in counts.items() if n > 1), reverse=True)
    no_brand = sum(1 for r in rows if not r.get('brand'))
    thin_n = sum(1 for r in rows if thin(r))
    searched = {k for k in counts if state.get(k, {}).get('status') not in (None, 'error')} | (set(log) & set(counts))
    calls = sum(e.get('calls', 0) for e in state.values())
    lines = ['# Product image audit', '', f'Products: {len(rows)} (inventory rows). Distinct part numbers: {len(counts)}.',
             f'Part numbers searched: {len(searched)} of {len(counts)}; not searched yet: {len(counts) - len(searched)}. '
             f'Search API requests: {calls}.',
             f'With a published photo: {len(found)} part numbers ({sum(counts[k] for k in found)} products).',
             f'Products accounted for: {sum(tally.values())} of {len(rows)}.', '', '| Status | Products |', '|---|---|']
    lines += [f'| {s} | {n} |' for s, n in tally.most_common()]
    lines += ['', f'Products without a brand (no aircraft type in the inventory): {no_brand}.',
              f'Products too thin to search reliably: {thin_n}.',
              f'Image files missing on disk: {len(missing_files)}' + (': ' + ', '.join(missing_files[:20]) if missing_files else '.'),
              f'Photos shared by different part numbers: {len(shared)}' + ''.join(f'\n- {s}: {", ".join(sorted(ks))}' for s, ks in shared.items()),
              '', f'Part numbers listed on more than one product (one per physical unit, they share one photo): {len(dup_pn)}. Most units:']
    lines += [f'- {k}: {n}' for n, k in dup_pn[:15]]
    L.write_if_changed(SUMMARY, '\n'.join(lines) + '\n')
    print(f'{len(rows)} products: ' + ', '.join(f'{s} {n}' for s, n in tally.most_common()) + f'.\n{L.rel(OUT)}\n{L.rel(SUMMARY)}')


if __name__ == '__main__':
    main()
