"""Find product pages for products without a photo in a distributor's or maker's sitemap:
python scripts/match-sitemaps.py <out-dir> <sitemap-url> [<sitemap-url> ...]

Sources allowed (decision 2026-10-13): manufacturers' own sites and distributors' stores, no marketplaces. The sitemap
is what the site publishes for search engines; it is read with robots.txt and the site's Crawl-delay respected (the
stricter of this script's rules and ClaudeBot's). A sitemap index is followed one level down.

A page is a candidate for a product when its address holds
  - the product's exact part number as whole parts ("3m-021200-21181-..." for 021200-21181; "021200-2118" is no match), or
  - for a product without a part number, every model number of its name and one of its distinctive words
    ("castrol-brayco-460-..." for "BRAYCO 460 (5 GLN)"); the page title is checked later by verify-pn-images.py.
Writes <out-dir>/result-<site>.json for scripts/verify-pn-images.py (which opens the pages and checks them).
"""
import collections, gzip, importlib.util, json, os, re, sys, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, 'scripts', file))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
VP = _load('vp', 'verify-pn-images.py')
FW = VP.FW


def toks(s):
    return re.findall(r'[a-z0-9]+', urllib.parse.unquote(s).lower())


def sitemap_urls(f, url, depth=0):
    data = f.get(url, binary=True)
    if data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)
    text = data.decode('utf-8', 'replace')
    locs = [l.replace('&amp;', '&') for l in re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', text)]
    if '<sitemapindex' in text and depth < 1:
        out = []
        for l in locs:
            try:
                out += sitemap_urls(f, l, depth + 1)
            except Exception as e:
                print('  sitemap', l, e)
        return out
    return locs


def family_ids():
    # products whose only photo is a catalog family photo: an exact photo may replace it
    path = os.path.join(ROOT, 'data', 'velmach-products.json')
    if not os.path.exists(path):
        return set()
    return {p['key'] for p in json.load(open(path, encoding='utf-8'))['products']
            if p['images'] and all(i.get('note') == 'family photo' for i in p['images'])}


def main():
    out_dir, maps = sys.argv[1], sys.argv[2:]
    os.makedirs(out_dir, exist_ok=True)
    f = VP.Fetcher()
    urls = []
    for m in maps:
        urls += sitemap_urls(f, m)
    urls = [u for u in dict.fromkeys(urls) if not VP.BLOCK.search(u)]
    site = urllib.parse.urlparse(maps[0]).hostname
    print(f'{site}: {len(urls)} pages in the sitemap', flush=True)
    # index: first token of the address part -> [(tokens, url)]
    index = collections.defaultdict(list)
    for u in urls:
        t = toks(u.rstrip('/').rsplit('/', 1)[-1].rsplit('.', 1)[0])
        for i, x in enumerate(t):
            index[x].append((t, i, u))
    # products on the site without a photo
    items, fam = [], family_ids()
    for line in open(os.path.join(ROOT, 'data', 'catalog', 'products.jsonl'), encoding='utf-8'):
        if not line.strip():
            continue
        r = json.loads(line)
        pid = r['key'][4:] if r['key'].startswith('doc:') else r['key']
        if (r.get('images') and pid not in fam) or r.get('sample'):
            continue
        items.append(r)
    res, stats = [], collections.Counter()
    for r in items:
        pid = r['key'][4:] if r['key'].startswith('doc:') else r['key']
        pn = r['partNumber'].strip()
        found = []
        parts = toks(pn)
        if pn and len(''.join(parts)) >= 5:
            for t, i, u in index.get(parts[0], []):
                if t[i:i + len(parts)] == parts:
                    found.append(u)
            if found:
                res.append({'id': pid, 'pn': pn, 'urls': found[:3], 'match': 'pn'}); stats['by part number'] += 1
                continue
        keys = FW.model_keys(r['title'])
        words = [w for w in FW.tokens(r['title']) if not re.search(r'\d', w) and w not in FW.COMMON and len(w) > 2]
        if keys and words:
            first = words[0]
            cands = set()
            for t, i, u in index.get(first, []):
                slug = ''.join(t)
                if all(k.replace('.', '') in slug for k in keys):
                    cands.add(u)
            if cands:
                res.append({'id': pid, 'pn': pn, 'title': r['title'], 'urls': sorted(cands, key=len)[:3], 'match': 'name'}); stats['by name'] += 1
    path = os.path.join(out_dir, f'result-{site}.json')
    json.dump(res, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f'{len(items)} products without a photo; candidates: {dict(stats)} -> {path}')


if __name__ == '__main__':
    main()
