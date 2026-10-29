"""Find a photo for each inventory part on the web: python scripts/find-product-images.py [--test 40] [--limit N] [--reverify]

Products that share a part number (ignoring dashes, spaces and case) are one group: one search, one photo. For each group:
  1. Image search through a search API, at most 3 queries, stopping once a photo is verified:
       "<part number>" <description>          (the part number as the inventory writes it)
       "<part number>" <aircraft>             (e.g. Falcon 2000, Gulfstream GIV)
       "<alternate part number>" <description>, or the part number without separators
     Only results that name the part number (page title, page or image address) are kept, never results from stock-photo,
     marketplace or social sites, never pictures named like logos, placeholders or "no image".
  2. Each kept result is checked on its own page (robots.txt respected, at most one request a second per site):
       a. the exact part number, as a whole code, is in the page text   b. and in the page title or main heading
       c. the page names the same kind of part (a word of our description: valve, wheel, actuator ...)
       d. the picture is the page's product picture and tied to the part number (in its address or alt text, or the page's
          og:image on a page titled with the part number)
       e. the picture is a real photo: at least 250 px, not blank, not a banner
  3. Verified (published automatically): a-e pass AND the site is the manufacturer's or an authorized distributor's (OEM,
     DISTRIBUTORS below). Needs Manual Review: the part number is on the page and d-e pass, but the site is a broker or other
     seller, or b/c fail; the photo is kept aside in data/catalog/.image-review/ (not on the site) and listed in
     reports/image-review.csv. Write approve or reject in its Decision column and run with --apply: approved photos are
     published. Unresolved: nothing passed. A picture found for two different part numbers is never published.
     No match means no photo: the products keep their category placeholder.
Photos are saved as WebP in images/products/<PN>/ (<PN>-1.webp at most 1200 px, thumbs/<PN>-1.webp 400 px). Published
photos are in data/catalog/product-images.json (with source page, site and the page's copyright line; also read by
import-inventory.py), the products get them and the catalogue is rebuilt. Only the images field of a product changes.

Keys (environment variables, or a .env file in the project root, which git ignores; keys are never printed):
  brave    BRAVE_API_KEY                         https://api-dashboard.search.brave.com  (Search plan, $5 per 1,000 requests)
  google   GOOGLE_CSE_KEY and GOOGLE_CSE_CX      https://programmablesearchengine.google.com (image search on)
  serpapi  SERPAPI_KEY                           https://serpapi.com (Google Images)
Brave is used when its key is set, unless --provider says otherwise.

Progress is saved after every part number in data/catalog/.image-state.json (with the search results, so --reverify can
check them again under new rules without new searches): stop at any time (Ctrl+C) and run again to continue. Searches that
failed (network, rate limit) are retried on the next run; --retry-unresolved searches again those that found nothing.
--test N searches N representative part numbers, publishes nothing and writes reports/image-search-test.csv with the
API calls, cost and outcome of each. Afterwards run scripts/audit-product-images.py for the full audit.
"""
import argparse, collections, csv, hashlib, html, importlib.util, io, json, os, random, re, sys, time, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_lib as L

_spec = importlib.util.spec_from_file_location('verify_pn', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify-pn-images.py'))
V = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(V)

STATE = os.path.join(L.CATALOG, '.image-state.json')
IMAGES = os.path.join(L.CATALOG, 'product-images.json')
STAGING = os.path.join(L.CATALOG, '.image-review')
REPORT = os.path.join(L.ROOT, 'reports', 'image-report.csv')
REVIEW = os.path.join(L.ROOT, 'reports', 'image-review.csv')
TEST = os.path.join(L.ROOT, 'reports', 'image-search-test.csv')
UA = 'VelmachCatalogImages/1.0 (+https://www.velmachaerospace.com)'
COST = {'brave': 0.005, 'google': 0.005, 'serpapi': 0.015}     # USD per request (serpapi depends on the plan)

# never used: stock libraries (watermarks), marketplaces and social sites (images not theirs to license)
BLOCKED = ['shutterstock.', 'alamy.', 'dreamstime.', 'istockphoto.', 'gettyimages.', '123rf.', 'depositphotos.', 'adobe.com',
           'pinterest.', 'facebook.', 'instagram.', 'twitter.', 'x.com', 'tiktok.', 'youtube.', 'reddit.', 'aliexpress.',
           'alibaba.', 'etsy.', 'walmart.', 'wish.com', 'temu.', 'craigslist.', 'lookaside.', 'fbsbx.', 'dhgate.',
           'indiamart.', 'made-in-china.', 'patents.google', 'wikipedia.', 'scribd.', 'manualslib.']
# manufacturers (aircraft and component OEMs) and their authorized distributors: the only sites published automatically
OEM = ['honeywell.', 'collinsaerospace.', 'rockwellcollins.', 'dassault-aviation.', 'dassaultfalcon.', 'gulfstream.', 'txtav.',
       'textron', 'bombardier.', 'safran-group.', 'safran', 'parker.', 'eaton.', 'woodward.', 'moog.', 'meggitt.', 'thalesgroup.',
       'l3harris.', 'garmin.', 'universalavionics.', 'astronics.', 'ametek', 'curtisswright.', 'crane-aerospace.', 'craneae.',
       'goodrich.', 'kidde-aerospace.', 'esterline.', 'liebherr.', 'triumphgroup.', 'transdigm.', 'boeing.com']
DISTRIBUTORS = ['shop.boeing.', 'aviall.', 'wencor.', 'satair.', 'aarcorp.', 'kellstrom.', 'heico.', 'skygeek.',
                'aircraftspruce.', 'proponent.', 'avfuelparts.']
# reasons that keep a photo off the site until someone approves it in reports/image-review.csv
HOLD = ('page does not name the part', 'too short')
BAD_IMG = re.compile(r'logo|placeholder|no[-_ ]?image|noimage|image[-_ ]?not|not[-_ ]?available|default|banner|icon|sprite|blank'
                     r'|spacer|coming[-_]soon|og[-_]?default|favicon|avatar', re.I)
# description words that say nothing about what the part is
GENERIC = {'assy', 'assembly', 'unit', 'part', 'parts', 'with', 'left', 'right', 'main', 'aircraft', 'kit', 'new', 'used', 'misc',
           'type', 'model', 'serial', 'complete', 'and', 'for', 'the', 'lower', 'upper', 'inboard', 'outboard', 'forward', 'rear'}


def compact(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def host(url):
    return (urllib.parse.urlparse(url).hostname or '').lower()


def site_rank(h):
    """0 manufacturer, 1 authorized distributor, 2 anything else."""
    return 0 if any(o in h for o in OEM) else 1 if any(d in h for d in DISTRIBUTORS) else 2


def load_env():
    """KEY=value lines from .env in the project root (not committed); variables already set win."""
    path = os.path.join(L.ROOT, '.env')
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            m = re.match(r'\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$', line)
            if m and not line.lstrip().startswith('#'):
                os.environ.setdefault(m.group(1), m.group(2).strip('"\''))


def get_json(url, headers=None, timeout=25):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json', **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


# ---------- search providers: each returns [{image, page, title}] ----------

def brave(q):
    d = get_json('https://api.search.brave.com/res/v1/images/search?' + urllib.parse.urlencode({'q': q, 'count': 50, 'safesearch': 'strict'}),
                 {'X-Subscription-Token': os.environ['BRAVE_API_KEY']})
    return [{'image': (r.get('properties') or {}).get('url', ''), 'page': r.get('url', ''), 'title': r.get('title', '')} for r in d.get('results', [])]


def google(q):
    d = get_json('https://www.googleapis.com/customsearch/v1?' + urllib.parse.urlencode(
        {'key': os.environ['GOOGLE_CSE_KEY'], 'cx': os.environ['GOOGLE_CSE_CX'], 'q': q, 'searchType': 'image', 'num': 10, 'safe': 'active'}))
    return [{'image': r.get('link', ''), 'page': (r.get('image') or {}).get('contextLink', ''), 'title': r.get('title', '')} for r in d.get('items', [])]


def serpapi(q):
    d = get_json('https://serpapi.com/search.json?' + urllib.parse.urlencode({'engine': 'google_images', 'q': q, 'api_key': os.environ['SERPAPI_KEY']}))
    return [{'image': r.get('original', ''), 'page': r.get('link', ''), 'title': r.get('title', '')} for r in d.get('images_results', [])[:30]]


PROVIDERS = {'brave': (brave, ['BRAVE_API_KEY']), 'google': (google, ['GOOGLE_CSE_KEY', 'GOOGLE_CSE_CX']), 'serpapi': (serpapi, ['SERPAPI_KEY'])}


def pick_provider(name):
    if name:
        fn, keys = PROVIDERS[name]
        missing = [k for k in keys if not os.environ.get(k)]
        if missing:
            raise SystemExit(f'--provider {name} needs the environment variable(s) {", ".join(missing)}.')
        return name, fn
    for n, (fn, keys) in PROVIDERS.items():
        if all(os.environ.get(k) for k in keys):
            return n, fn
    return None, None


def search(fn, q, calls):
    """One API request with retries on rate limits and server errors. Raises SystemExit when the key is refused."""
    for attempt in range(4):
        calls[0] += 1
        try:
            return fn(q)
        except urllib.error.HTTPError as e:
            if e.code in (401, 402, 403):
                raise SystemExit(f'The search API refused the request (HTTP {e.code}: key wrong, or credits used up). '
                                 'Progress is saved; fix it and run again.')
            if e.code == 429 or e.code >= 500:
                time.sleep(min(120, 10 * 2 ** attempt)); continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < 3:
                time.sleep(10 * (attempt + 1)); continue
            raise
    raise OSError('search API still rate limited after 4 tries')


# ---------- one part-number group ----------

class Group:
    def __init__(self, key, rows):
        self.key, self.rows = key, rows
        self.pns = sorted({r['partNumber'] for r in rows}, key=lambda p: (-len(p), p))     # with separators first
        self.alts = sorted({a.strip() for r in rows for a in re.split(r'[,;/]\s*', r.get('altPartNumber') or '') if len(compact(a)) >= 4})
        self.titles = sorted({r['title'] for r in rows if r.get('title')})
        self.aircraft = next((r['aircraftListed'].split(' SN ')[0] for r in rows if r.get('aircraftListed')), '')
        self.brand = next((r['brand'] for r in rows if r.get('brand')), '')
        self.words = {w.rstrip('s') for t in self.titles for w in re.findall(r'[a-z]{4,}', t.lower()) if w not in GENERIC}
        self.short = len(key) < 4             # "270": too short to identify a product on its own; never published automatically

    def queries(self):
        pn, t = self.pns[0], (self.titles[0] if self.titles else '')
        q = [f'"{pn}" {t}'.strip(), f'"{pn}" {self.aircraft or self.brand}'.strip()]
        if self.alts:
            q.append(f'"{self.alts[0]}" {t}'.strip())
        elif compact(pn) != pn.lower():
            q.append(f'"{compact(pn).upper()}" {t}'.strip())
        return list(dict.fromkeys(q))

    def pattern(self):
        return re.compile('|'.join(V.pn_pattern(p).pattern for p in self.pns), re.I)

    def names_pn(self, r):
        """A search result that names one of our part numbers (short ones only as a separate token)."""
        hay = ' '.join((r['title'], r['page'], r['image']))
        if self.short:
            return bool(self.pattern().search(hay))
        return self.key in compact(hay) or bool(self.pattern().search(hay))


def hits(group, results):
    """Results worth checking: name the part number, not blocked, not a stand-in picture; manufacturers first."""
    out, seen = [], set()
    for r in results:
        if not r['image'].startswith('http') or not r['page'].startswith('http') or r['image'] in seen:
            continue
        hs = host(r['image']) + ' ' + host(r['page'])
        if any(b in hs for b in BLOCKED) or BAD_IMG.search(urllib.parse.urlparse(r['image']).path) or not group.names_pn(r):
            continue
        seen.add(r['image'])
        out.append(r)
    out.sort(key=lambda r: site_rank(host(r['page'])))
    return out[:6]


def page_parts(page):
    title = ' '.join(re.findall(r'<title[^>]*>(.*?)</title>', page, re.S | re.I))
    h1 = ' '.join(re.findall(r'<h1[^>]*>(.*?)</h1>', page, re.S | re.I))
    return html.unescape(re.sub(r'<[^>]+>', ' ', title + ' ' + h1))


def copyright_line(page):
    m = re.search(r'<meta[^>]+name=["\']copyright["\'][^>]+content=["\']([^"\']+)', page, re.I)
    if m:
        return html.unescape(m.group(1))[:120]
    m = re.search(r'(?:&copy;|©|Copyright)\s*(?:&copy;|©)?\s*\d{4}[^<\n]{0,80}', page, re.I)
    return re.sub(r'\s+', ' ', html.unescape(m.group(0))).strip()[:120] if m else ''


def license_of(page):
    m = re.search(r'<a[^>]+rel=["\']license["\'][^>]+href=["\']([^"\']+)', page, re.I)
    return m.group(1) if m else ''


def tied_image(group, page, url, cand, pat):
    """The page's product picture tied to the part number, or ''. Prefers the picture the search found."""
    in_heading = bool(pat.search(page_parts(page)))
    og = V.FW.meta(page, 'og:image')
    og = urllib.parse.urljoin(url, html.unescape(og)) if og and not BAD_IMG.search(og) else ''
    path = urllib.parse.urlparse(cand).path
    if path and path in page:
        for tag in re.findall(r'<img[^>]+>', page, re.I):
            if path in html.unescape(tag):
                alt = re.search(r'alt=["\']([^"\']*)', tag)
                if pat.search(path) or (alt and pat.search(html.unescape(alt.group(1)))) or (cand == og and in_heading):
                    return cand
        if cand == og and in_heading:
            return cand
    img = V.product_image(page, url, pat)          # og:image, else an <img> whose address or alt holds the part number
    if img and not BAD_IMG.search(img) and (img != og or in_heading or pat.search(img)):
        return img
    return ''


def photo(fetcher, url):
    """Download and check the picture. Returns (PIL image, sha1) or raises ValueError with the reason."""
    from PIL import Image, ImageStat
    data = fetcher.get(url, binary=True)
    try:
        im = Image.open(io.BytesIO(data)); im.load()
    except Exception:
        raise ValueError('not a readable image')
    w, h = im.size
    if min(w, h) < 250:
        raise ValueError(f'too small ({w}x{h})')
    if max(w, h) > 3 * min(w, h):
        raise ValueError(f'banner shape ({w}x{h})')
    if ImageStat.Stat(im.convert('L')).stddev[0] < 8:
        raise ValueError('blank or almost uniform image')
    return im, hashlib.sha1(data).hexdigest()


def save_webp(im, folder, name):
    from PIL import Image
    if im.mode not in ('RGB', 'RGBA'):
        im = im.convert('RGBA' if 'transparency' in im.info or im.mode in ('LA', 'P') else 'RGB')
    os.makedirs(os.path.join(folder, 'thumbs'), exist_ok=True)
    out = {}
    for kind, width, path in (('large', 1200, os.path.join(folder, f'{name}-1.webp')), ('thumb', 400, os.path.join(folder, 'thumbs', f'{name}-1.webp'))):
        copy = im.copy()
        if copy.width > width:
            copy = copy.resize((width, round(copy.height * width / copy.width)), Image.LANCZOS)
        buf = io.BytesIO()
        copy.save(buf, 'WEBP', quality=85, method=6)
        L.write_file(path, buf.getvalue())
        out[kind] = L.rel(path)
    return out


def check(group, fetcher, cand):
    """Check one search result on its page. Returns a record with 'tier' verified / review / rejected and the reasons."""
    url, pat, h = cand['page'], group.pattern(), host(cand['page'])
    rec = {'page': url, 'site': h, 'image': cand['image'], 'checks': [], 'tier': 'rejected'}
    try:
        page = fetcher.get(url)
    except V.NetworkDown:
        raise
    except Exception as e:
        rec['reason'] = f'page not read: {e}'; return rec
    text = V.text_of(page)
    if not pat.search(text):
        rec['reason'] = 'exact part number not on the page'; return rec
    rec['checks'].append('part number on page')
    weak = []
    if pat.search(page_parts(page)):
        rec['checks'].append('part number in page title/heading')
    else:
        weak.append('part number not in the page title or heading (may be a list of parts)')
    low = text.lower()
    if group.words and any(w in low for w in group.words):
        rec['checks'].append('same kind of part')
    else:
        weak.append('page does not name the part (' + ', '.join(sorted(group.words)[:4]) + ')')
    img = tied_image(group, page, url, cand['image'], pat)
    if not img:
        rec['reason'] = 'no product picture tied to the part number'; return rec
    rec['image'] = img
    try:
        im, sha = photo(fetcher, img)
    except V.NetworkDown:
        raise
    except Exception as e:
        rec['reason'] = f'picture refused: {e}'; return rec
    rec['checks'].append(f'real photo {im.size[0]}x{im.size[1]}')
    rec.update(sha1=sha, copyright=copyright_line(page), license=license_of(page), pageTitle=page_parts(page).strip()[:160])
    rank = site_rank(h)
    if rank == 2:
        weak.append('site is not a manufacturer or authorized distributor')
    if group.short:
        weak.append('part number too short to identify one product')
    rec['tier'] = 'review' if weak else 'verified'
    rec['reason'] = '; '.join(weak)
    rec.update(save_webp(im, os.path.join(STAGING, L.safe_part_number(group.pns[0])), L.safe_part_number(group.pns[0])))
    return rec


def process(group, fetcher, fn, entry, reverify=False):
    """Search (or re-check stored results) for one group; fills entry and returns it."""
    calls = [0]
    best = None
    if reverify:
        plan = [(q['q'], q.get('hits', [])) for q in entry.get('queries', [])]
    else:
        plan = [(q, None) for q in group.queries()]
        entry['queries'] = []
    entry['checked'] = []
    for i, (q, stored) in enumerate(plan):
        if stored is None:
            found = hits(group, search(fn, q, calls))
            entry['queries'].append({'q': q, 'hits': found})
            if i + 1 < len(plan):
                time.sleep(1.1)
        else:
            found = stored
        for cand in found:
            if any((cand['image'] and c['image'] == cand['image']) or c['page'] == cand['page'] for c in entry['checked']):
                continue
            rec = check(group, fetcher, cand)
            entry['checked'].append({k: v for k, v in rec.items() if k not in ('thumb', 'large')} | ({'staged': rec['large']} if 'large' in rec else {}))
            if rec['tier'] == 'verified':
                best = rec; break
            if rec['tier'] == 'review' and (not best or site_rank(rec['site']) < site_rank(best['site'])):
                best = rec
        if best and best['tier'] == 'verified':
            break
    entry.update(calls=entry.get('calls', 0) + calls[0], tried=time.strftime('%Y-%m-%d %H:%M'))
    if best:
        entry['status'] = best['tier']
        entry['best'] = {k: best.get(k, '') for k in ('page', 'site', 'image', 'sha1', 'copyright', 'license', 'pageTitle', 'reason', 'thumb', 'large', 'checks')}
    else:
        entry['status'] = 'unresolved'
        entry.pop('best', None)
        reasons = collections.Counter(c.get('reason', '') for c in entry['checked'])
        entry['reason'] = ('; '.join(f'{r} ({n})' for r, n in reasons.most_common(3)) if reasons
                           else 'no search result names the part number')
    return entry


# ---------- publishing ----------

def load(path, default):
    try:
        return json.load(open(path, encoding='utf-8'))
    except (OSError, ValueError):
        return default


def read_decisions():
    out = {}
    if os.path.exists(REVIEW):
        for r in csv.DictReader(open(REVIEW, encoding='utf-8-sig')):
            d = (r.get('Decision') or '').strip().lower()
            if d in ('approve', 'approved', 'yes', 'reject', 'rejected', 'no'):
                out[r['Key']] = 'approve' if d in ('approve', 'approved', 'yes') else 'reject'
    return out


def publish(state, groups, decisions):
    """Decide which photos go on the site; copy them from staging into images/products. Returns the published map."""
    # one picture, one part number: a picture found for different part numbers is never published
    by_pic = collections.defaultdict(set)
    for k, e in state.items():
        b = e.get('best')
        if b and e['status'] in ('verified', 'review'):
            by_pic[b.get('sha1') or b['image']].add(k)
            by_pic[b['image']].add(k)
    published = {}
    for k, e in state.items():
        b = e.get('best')
        if not b or k not in groups:
            continue
        shared = sorted((by_pic[b.get('sha1') or b['image']] | by_pic[b['image']]) - {k})
        e['shared'] = shared
        # published: every check passed, or the page shows the part number with its photo and names the same kind of part
        # (any site); held back: a page about another kind of part, a too-short part number, or a picture shared by two
        held = any(x in b.get('reason', '') for x in HOLD)
        ok = not shared and decisions.get(k) != 'reject' and (e['status'] == 'verified' or not held or decisions.get(k) == 'approve')
        if not ok:
            continue
        name = L.safe_part_number(groups[k].pns[0])
        folder = os.path.join(L.PRODUCT_DIR, name)
        out = {}
        for kind in ('large', 'thumb'):
            src = os.path.join(L.ROOT, b[kind])
            dst = os.path.join(folder, *(['thumbs'] if kind == 'thumb' else []), os.path.basename(src))
            if os.path.exists(src) and (not os.path.exists(dst) or open(src, 'rb').read() != open(dst, 'rb').read()):
                L.write_file(dst, open(src, 'rb').read())
            out[kind] = L.rel(dst)
        if not all(os.path.exists(os.path.join(L.ROOT, p)) for p in out.values()):
            continue
        published[k] = {'thumb': out['thumb'], 'large': out['large'], 'original': out['large'], 'source': b['image'],
                        'page': b['page'], 'site': b['site'], 'attribution': b.get('copyright') or b['site'],
                        'license': b.get('license') or 'not stated on the source page',
                        'verified': 'automatic' if e['status'] == 'verified' else 'manual review', 'checked': e.get('tried', '')}
    return published


def apply_images(store, found):
    """Put published photos on the products (only their images field) and rebuild the catalogue."""
    changed, reps = 0, L.load_representative()
    for r in store.values():
        want = L.images_for(r, found, reps)
        if r.get('images') != want:
            r['images'] = want; changed += 1
    if changed:
        L.save_store(store)
        spec = importlib.util.spec_from_file_location('build_catalog', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build-catalog.py'))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); mod.build()
    return changed


def write_reports(store, state, groups, found, decisions):
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    rows = sorted(store.values(), key=lambda r: r.get('serialNo') or 0)
    with open(REPORT, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['Serial No', 'Part Number', 'Image found', 'Image source URL', 'Source page', 'Placeholder used'])
        for r in rows:
            img = found.get(L.norm_key(r['partNumber']))
            w.writerow([r.get('serialNo', ''), r['partNumber'], 'yes' if img else 'no', img.get('source', '') if img else '',
                        img.get('page', '') if img else '', '' if img else r.get('placeholder', '')])
    with open(REVIEW, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['Key', 'Part Number', 'Products', 'Description', 'Aircraft', 'Staged image', 'Source page', 'Image URL', 'Site',
                    'Why review', 'Decision'])
        for k, e in sorted(state.items()):
            b = e.get('best')
            if not b or k not in groups or k in found:
                continue
            g = groups[k]
            why = b.get('reason', '') + ('; same picture as part number(s) ' + ', '.join(e['shared']) if e.get('shared') else '')
            w.writerow([k, g.pns[0], len(g.rows), ' / '.join(g.titles), g.aircraft, b.get('large', ''), b['page'], b['image'], b['site'],
                        why.strip('; '), decisions.get(k, '')])


def representative(groups, n, seed=29):
    """n part numbers spread over brands and categories (proportionally), plus awkward cases: alternate numbers, short ones."""
    rnd = random.Random(seed)
    strata = collections.defaultdict(list)
    for k, g in sorted(groups.items()):
        strata[(g.brand, g.rows[0].get('categoryChild', ''))].append(k)
    picked = []
    for s in sorted(strata, key=lambda s: -len(strata[s])):
        take = max(1, round(n * len(strata[s]) / len(groups)))
        picked += rnd.sample(strata[s], min(take, len(strata[s])))
    extra = [k for k in sorted(groups) if (groups[k].alts or groups[k].short) and k not in picked]
    picked += rnd.sample(extra, min(4, len(extra)))
    rnd.shuffle(picked)
    return picked[:n]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--provider', choices=sorted(PROVIDERS), help='search API to use (default: the first with a key set, brave first)')
    ap.add_argument('--test', type=int, default=0, metavar='N', help='search N representative part numbers, publish nothing')
    ap.add_argument('--limit', type=int, default=0, help='search at most N part numbers in this run (0 = all remaining)')
    ap.add_argument('--retry-unresolved', action='store_true', help='search again part numbers that found nothing before')
    ap.add_argument('--reverify', action='store_true', help='check the stored search results again (no new searches)')
    ap.add_argument('--apply', action='store_true', help='only publish: verified photos and those approved in reports/image-review.csv')
    ap.add_argument('--from-results', metavar='DIR', help='no search API: check the pages listed in DIR/*.json '
                    '([{"pn", "queries", "urls"}], from searching each part number by hand or with an assistant)')
    a = ap.parse_args()

    load_env()
    store = L.load_store()
    state = load(STATE, {})
    by_key = collections.defaultdict(list)
    for r in sorted(store.values(), key=lambda r: r.get('serialNo') or 0):
        by_key[L.norm_key(r['partNumber'])].append(r)
    groups = {k: Group(k, rows) for k, rows in by_key.items()}
    decisions = read_decisions()

    def finish(publish_now=True):
        found = publish(state, groups, decisions) if publish_now else load(IMAGES, {})
        if publish_now:
            L.write_file(IMAGES, json.dumps(found, ensure_ascii=False, indent=0).encode('utf-8'))
        L.write_file(STATE, json.dumps(state, ensure_ascii=False, indent=0).encode('utf-8'))
        changed = apply_images(store, found) if publish_now else 0
        write_reports(store, state, groups, found, decisions)
        n = sum(len(groups[k].rows) for k in found if k in groups)
        st = collections.Counter(state[k]['status'] for k in groups if k in state)
        print(f'Part numbers: {len(groups)}; searched {sum(st.values())} ({", ".join(f"{s} {c}" for s, c in st.most_common())}). '
              f'Published photos: {len(found)} part numbers, {n} of {len(store)} products; {changed} products updated.\n'
              f'Reports: {L.rel(REPORT)}, {L.rel(REVIEW)}')

    if a.apply:
        finish(); return
    if a.from_results:
        # each part number's search results become stored queries, then are checked like --reverify (no API requests)
        import glob
        for path in sorted(glob.glob(os.path.join(a.from_results, '*.json'))):
            for it in load(path, []):
                k = L.norm_key(it.get('pn', ''))
                if k not in groups or state.get(k, {}).get('status') not in (None, 'error'):
                    continue
                urls = [u for u in it.get('urls', []) if u.startswith('http') and not re.search(r'\.pdf($|\?)', u, re.I)]
                state[k] = {'queries': [{'q': q, 'hits': []} for q in it.get('queries', [])] or [{'q': it['pn'], 'hits': []}], 'source': 'web search'}
                state[k]['queries'][0]['hits'] = [{'page': u, 'image': '', 'title': ''} for u in urls]
                state[k]['status'] = 'pending-check'
        a.reverify = True
    name, fn = (None, None) if a.reverify else pick_provider(a.provider)
    if not fn and not a.reverify:
        print('No search API key found (BRAVE_API_KEY, GOOGLE_CSE_KEY + GOOGLE_CSE_CX or SERPAPI_KEY, in the environment or .env), '
              'so nothing was searched.')
        finish(); return

    if a.from_results:
        todo = [k for k in groups if state.get(k, {}).get('status') == 'pending-check']
    elif a.reverify:
        todo = [k for k in groups if state.get(k, {}).get('queries')]
    elif a.test:
        todo = [k for k in representative(groups, a.test) if state.get(k, {}).get('status') in (None, 'error')]
    else:
        todo = [k for k in groups if state.get(k, {}).get('status') in (None, 'error')
                or (a.retry_unresolved and state[k]['status'] == 'unresolved')]
    if a.limit:
        todo = todo[:a.limit]
    print(f'{name or "stored results"}: {len(todo)} part numbers to {"check" if a.reverify else "search"} '
          f'({len(groups)} in the catalogue, {len(store)} products).', flush=True)
    fetcher = V.Fetcher()
    fetcher_ua = V.UA
    V.UA = UA
    calls0 = sum(state.get(k, {}).get('calls', 0) for k in groups)
    test_rows = []
    try:
        for i, k in enumerate(todo, 1):
            g = groups[k]
            entry = dict(state.get(k, {})) if a.reverify else {}
            try:
                process(g, fetcher, fn, entry, reverify=a.reverify)
            except V.NetworkDown as e:
                print(f'Stopped: {e}. Run again to continue.'); break
            except (OSError, ValueError) as e:
                entry.update(status='error', error=str(e)[:200], tried=time.strftime('%Y-%m-%d %H:%M'))
            state[k] = entry
            L.write_file(STATE, json.dumps(state, ensure_ascii=False, indent=0).encode('utf-8'))
            b = entry.get('best') or {}
            print(f'  [{i}/{len(todo)}] {g.pns[0]}: {entry["status"]}' + (f' ({b.get("site")})' if b else ''), flush=True)
            if a.test:
                test_rows.append([k, g.pns[0], ' / '.join(g.titles), g.brand, g.aircraft, len(g.rows), entry.get('calls', 0),
                                  entry['status'], b.get('site', ''), b.get('page', ''), b.get('image', ''), b.get('large', ''),
                                  b.get('reason', '') or entry.get('reason', '') or entry.get('error', ''), ''])
            if not a.reverify:
                time.sleep(1.1)
    except KeyboardInterrupt:
        print('Stopped. Run again to continue.')
    finally:
        V.UA = fetcher_ua
    calls = sum(state.get(k, {}).get('calls', 0) for k in groups) - calls0
    if calls:
        print(f'API requests this run: {calls} (about ${calls * COST.get(name, 0):.2f} at ${COST.get(name, 0)} per request).')
    if a.test:
        with open(TEST, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['Key', 'Part Number', 'Description', 'Brand', 'Aircraft', 'Products', 'API requests', 'Status', 'Site',
                        'Source page', 'Image URL', 'Staged image', 'Reason', 'Picture shows the part (checked by eye)'])
            w.writerows(test_rows)
        print(f'Test: nothing published. Results: {L.rel(TEST)}')
        finish(publish_now=False)
        return
    finish()


if __name__ == '__main__':
    main()
