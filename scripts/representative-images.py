"""Representative photos per component type: python scripts/representative-images.py --candidates fan-blade valve ...

Most inventory parts have no photo of their own anywhere on the open web. This gives a product a photo of its component
type instead (a valve, an aircraft wheel, a cockpit display ...), clearly labelled on the product page as a representative
image with its credit. A product with a photo of its own part number (scripts/find-product-images.py) always keeps that.

  --types                     products per component type (scripts/component_types.py), and the types without a photo yet
  --candidates TYPE ...       search Wikimedia Commons (api.wikimedia.org, free, no key) with the type's searches, keep
                              freely licensed photos (CC0, public domain, CC BY, CC BY-SA) and write a numbered contact
                              sheet per type to data/velmach-staging/representative/<type>.jpg for a person to look at
  --choose TYPE=N ...         use candidate N of TYPE (chosen by looking at the contact sheet); nothing is published yet
  --aircraft TYPE=REGEX ...   the photo shows the part of some aircraft only (e.g. engine='Hawker 800'): other aircraft keep
                              the placeholder (matched against the inventory's aircraft, e.g. "Falcon 2000")
  --apply [--only ID ...]     download the chosen photos (1200 px and 400 px WebP in images/representative/), put them on
                              the products of their type that have no photo of their own, rebuild the catalogue.
                              --only limits it to those product ids (a test); without it every product of the type.
  --remove TYPE ...           take a type's photo off the products again
Choices and credits are kept in data/catalog/representative-images.json. Wikimedia's robots.txt is respected: its own
search page is not used, only its public REST API, file pages and image server, at most one request a second.
"""
import argparse, collections, html, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_lib as L
from component_types import LABELS, commons_queries, component_type

UA = 'VelmachCatalogImages/1.0 (+https://www.velmachaerospace.com)'
STAGING = os.path.join(L.ROOT, 'data', 'velmach-staging', 'representative')
OUT_DIR = os.path.join(L.ROOT, 'images', 'representative')
FREE = re.compile(r'^(cc0|cc[- ]zero|public domain|pd\b|pd-|no restrictions|cc[- ]by(-sa)?[- ]\d)', re.I)
_last = [0.0]


def get(url, binary=False):
    gap = time.time() - _last[0]
    if gap < 1.0:
        time.sleep(1.0 - gap)
    _last[0] = time.time()
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*' if binary else 'application/json, text/html'})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read(25 * 1024 * 1024)
            return data if binary else data.decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            if attempt == 3 or not (e.code == 429 or e.code >= 500):
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 3:
                raise
        time.sleep(5 * 2 ** attempt)          # rate limited or a server hiccup: wait, then try again


def search(q, limit=12):
    d = json.loads(get('https://api.wikimedia.org/core/v1/commons/search/page?' + urllib.parse.urlencode({'q': q, 'limit': limit})))
    return [p['key'] for p in d.get('pages', []) if p['key'].startswith('File:') and re.search(r'\.(jpe?g|png|webp|tiff?)$', p['key'], re.I)]


def file_info(title):
    """Image URLs, licence and author of a Commons file, or None when the licence is not a free one we can name."""
    d = json.loads(get('https://api.wikimedia.org/core/v1/commons/file/' + urllib.parse.quote(title)))
    pref = d.get('preferred') or {}
    if pref.get('mediatype') != 'BITMAP' or min(pref.get('width') or 0, pref.get('height') or 0) < 300:
        return None
    page_url = 'https://commons.wikimedia.org/wiki/' + urllib.parse.quote(title.replace(' ', '_'))
    page = get(page_url).replace('&#95;', '_')      # Commons escapes the underscores in its licence and author class names
    lic = re.search(r'class="licensetpl_short"[^>]*>([^<]+)<', page)
    lic = html.unescape(lic.group(1)).strip() if lic else ''
    if not lic or not FREE.search(lic):
        return None
    aut = re.search(r'id="fileinfotpl_aut"[^>]*>.*?</td>\s*<td[^>]*>(.*?)</td>', page, re.S)
    aut = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', aut.group(1)))).strip() if aut else ''
    aut = re.sub(r'\s*\(talk\)|\s*\bUnknown author\b', '', aut)[:80]
    return {'file': title, 'image': pref['url'], 'width': pref.get('width'), 'height': pref.get('height'),
            'page': page_url, 'license': lic, 'author': aut}


def contact_sheet(cands, path):
    from PIL import Image, ImageDraw
    cell, cols = 300, 4
    rows = (len(cands) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cell, rows * (cell + 24)), 'white')
    dr = ImageDraw.Draw(sheet)
    for i, c in enumerate(cands):
        try:
            im = Image.open(io.BytesIO(get(c['image'], binary=True))).convert('RGB')
            im.thumbnail((cell - 8, cell - 8))
            x, y = (i % cols) * cell, (i // cols) * (cell + 24)
            sheet.paste(im, (x + 4, y + 4))
            dr.text((x + 6, y + cell + 4), f'{i + 1}: {c["license"][:18]} {c["file"][5:30]}', fill='black')
        except Exception as e:
            print(f'    could not load candidate {i + 1}: {e}')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.save(path, quality=85)


def load_reps():
    try:
        return json.load(open(L.REPRESENTATIVE, encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_reps(reps):
    L.write_if_changed(L.REPRESENTATIVE, json.dumps(reps, ensure_ascii=False, indent=1) + '\n')


def save_webp(data, tid):
    from PIL import Image
    im = Image.open(io.BytesIO(data)); im.load()
    if im.mode not in ('RGB', 'RGBA'):
        im = im.convert('RGB')
    out = {}
    for kind, width, path in (('large', 1200, os.path.join(OUT_DIR, f'{tid}.webp')), ('thumb', 400, os.path.join(OUT_DIR, 'thumbs', f'{tid}.webp'))):
        copy = im.copy()
        if copy.width > width:
            copy = copy.resize((width, round(copy.height * width / copy.width)), Image.LANCZOS)
        buf = io.BytesIO()
        copy.save(buf, 'WEBP', quality=85, method=6)
        L.write_file(path, buf.getvalue())
        out[kind] = L.rel(path)
    return out


def apply_to_store(store):
    found = json.load(open(os.path.join(L.CATALOG, 'product-images.json'), encoding='utf-8')) if os.path.exists(os.path.join(L.CATALOG, 'product-images.json')) else {}
    reps, changed = L.load_representative(), 0
    for r in store.values():
        want = L.images_for(r, found, reps)
        if r.get('images') != want:
            r['images'] = want; changed += 1
    if changed:
        L.save_store(store)
        import importlib.util
        spec = importlib.util.spec_from_file_location('build_catalog', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build-catalog.py'))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); mod.build()
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--types', action='store_true')
    ap.add_argument('--candidates', nargs='*', metavar='TYPE')
    ap.add_argument('--choose', nargs='+', metavar='TYPE=N')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--only', nargs='+', metavar='ID', help='with --apply: only these product ids (a test)')
    ap.add_argument('--remove', nargs='+', metavar='TYPE')
    ap.add_argument('--aircraft', nargs='+', metavar='TYPE=REGEX')
    a = ap.parse_args()
    store, reps = L.load_store(), load_reps()
    per_type = collections.Counter(component_type(r['title']) for r in store.values())

    if a.types:
        for tid, n in per_type.most_common():
            print(f'{tid or "(no type: placeholder)":28} {n:5}  {"photo chosen" if reps.get(tid, {}).get("file") else ""}')
        return

    if a.candidates is not None:
        for tid in a.candidates or [t for t in LABELS if not reps.get(t, {}).get('file')]:
            if tid not in LABELS:
                print(f'unknown type {tid}'); continue
            seen, cands = set(), []
            if os.path.exists(os.path.join(STAGING, f'{tid}.json')) and not a.candidates:
                continue                      # done in an earlier run (name the type to search it again)
            for q in commons_queries(tid):
                try:
                    titles = search(q)
                except Exception as e:
                    print(f'    search "{q}" failed: {e}'); continue
                for title in titles:
                    if title in seen or len(cands) >= 16:
                        continue
                    seen.add(title)
                    try:
                        info = file_info(title)
                    except Exception as e:
                        print(f'    {title}: {e}'); continue
                    if info:
                        cands.append(info)
            os.makedirs(STAGING, exist_ok=True)
            json.dump(cands, open(os.path.join(STAGING, f'{tid}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            if cands:
                contact_sheet(cands, os.path.join(STAGING, f'{tid}.jpg'))
            print(f'{tid}: {len(cands)} freely licensed candidates -> {L.rel(os.path.join(STAGING, tid + ".jpg"))}')
        return

    if a.choose:
        for item in a.choose:
            tid, n = item.split('=')
            cands = json.load(open(os.path.join(STAGING, f'{tid}.json'), encoding='utf-8'))
            c = cands[int(n) - 1]
            reps[tid] = {'label': LABELS[tid], 'file': c['file'], 'page': c['page'], 'source': c['image'], 'license': c['license'],
                         'author': c['author']}
            print(f'{tid}: {c["file"]} ({c["license"]})')
        save_reps(reps)
        return

    if a.aircraft:
        for item in a.aircraft:
            tid, rx = item.split('=', 1)
            re.compile(rx)
            reps[tid]['aircraft'] = rx
            print(f'{tid}: only aircraft matching {rx!r}')
        save_reps(reps)
        return

    if a.remove:
        for tid in a.remove:
            reps.pop(tid, None)
        save_reps(reps)
        print(f'{apply_to_store(store)} products updated')
        return

    if a.apply:
        for tid, rep in reps.items():
            if not rep.get('file'):
                continue
            if not rep.get('large') or not os.path.exists(os.path.join(L.ROOT, rep['large'])) or rep.get('saved') != rep['file']:
                rep.update(save_webp(get(rep['source'], binary=True), tid), saved=rep['file'])
            rep['credit'] = 'Photo: ' + ', '.join(x for x in (rep.get('author'), rep.get('license')) if x) + ', via Wikimedia Commons'
            if a.only:
                rep['only'] = sorted(set(a.only))
            else:
                rep.pop('only', None)
        save_reps(reps)
        changed = apply_to_store(store)
        n = sum(1 for r in store.values() if r.get('images') and r['images'][0].get('kind') == 'representative')
        print(f'{changed} products updated; {n} of {len(store)} products show a representative photo.')
        return
    ap.print_help()


if __name__ == '__main__':
    main()
