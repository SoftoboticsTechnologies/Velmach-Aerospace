"""Hide duplicate products: python scripts/remove-duplicates.py [--dry-run]

A duplicate is the same product listed twice: the same name (ignoring case, spaces, punctuation and TM/(R) marks) where
one entry has a part number and the other has none (it came from a list that gives no part number). The entry with the
part number stays; if only the hidden one has a photo, the photo moves to the one that stays. Products with the same name
but different part numbers are NOT duplicates (they can be different variants) and are left alone.

Nothing is deleted: hidden products are saved to backup/duplicates-removed-<date>.jsonl, listed in
reports/duplicates-removed.csv, and added to data/velmach-hidden.json so a later import does not bring them back.
"""
import collections, csv, datetime, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, 'data', 'catalog', 'products.jsonl')
HIDDEN = os.path.join(ROOT, 'data', 'velmach-hidden.json')


def norm(t):
    return re.sub(r'[^a-z0-9]', '', (t or '').lower())


def main():
    dry = '--dry-run' in sys.argv
    lines = [l for l in open(STORE, encoding='utf-8').read().splitlines() if l.strip()]
    recs = [json.loads(l) for l in lines]
    groups = collections.defaultdict(list)
    for r in recs:
        if not r.get('sample'):
            groups[norm(r['title'])].append(r)
    hide, moves = {}, []
    for name, rs in groups.items():
        if len(rs) < 2:
            continue
        with_pn = [r for r in rs if norm(r['partNumber'])]
        without = [r for r in rs if not norm(r['partNumber'])]
        if not without:
            continue                                   # all have part numbers: variants, not duplicates
        if len({norm(r['partNumber']) for r in with_pn}) > 1:
            continue                                   # several part numbers: cannot tell which one is the same product
        keep = with_pn[0] if with_pn else max(without, key=lambda r: (bool(r.get('images')), len(r.get('description') or ''), len(r.get('specifications') or [])))
        for r in rs:
            if r is keep or (with_pn and r in with_pn):
                continue
            hide[r['key']] = (r, keep)
            if r.get('images') and not keep.get('images'):
                moves.append((keep, r))
    print(f'duplicates to hide: {len(hide)}; photos moved to the product that stays: {len(moves)}')
    with open(os.path.join(ROOT, 'reports', 'duplicates-removed.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['hidden title', 'hidden part number', 'hidden source', 'kept title', 'kept part number', 'kept source', 'photo moved'])
        moved = {k['key'] for k, _ in moves}
        for k, (r, keep) in hide.items():
            w.writerow([r['title'], r['partNumber'], r.get('documentSource', ''), keep['title'], keep['partNumber'], keep.get('documentSource', ''),
                        'yes' if keep['key'] in moved and r.get('images') else ''])
    if dry or not hide:
        return
    stamp = datetime.date.today().isoformat()
    with open(os.path.join(ROOT, 'backup', f'duplicates-removed-{stamp}.jsonl'), 'a', encoding='utf-8', newline='\n') as fh:
        for k, (r, _) in hide.items():
            fh.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
    # photos of hidden duplicates go to the product that stays (the image files are reused, nothing is downloaded)
    by_key = {r['key']: r for r in recs}
    for keep, r in moves:
        by_key[keep['key']]['images'] = r['images']
        if r.get('sourceUrl') and not keep.get('sourceUrl'):
            by_key[keep['key']]['sourceUrl'] = r['sourceUrl']
        by_key[keep['key']]['pnDir'] = by_key[keep['key']].get('pnDir') or r.get('pnDir')
    out = [json.dumps(by_key[r['key']], ensure_ascii=False, separators=(',', ':')) for r in recs if r['key'] not in hide]
    open(STORE, 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
    hidden = json.load(open(HIDDEN, encoding='utf-8')) if os.path.exists(HIDDEN) else {}
    for k, (r, keep) in hide.items():
        hidden[k[4:] if k.startswith('doc:') else k] = {'reason': 'duplicate', 'kept': keep['key'], 'date': stamp}
    json.dump(hidden, open(HIDDEN, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'build-catalog.py')], cwd=ROOT)


if __name__ == '__main__':
    main()
