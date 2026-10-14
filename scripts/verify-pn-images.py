"""Check product pages found by part-number search and take their product photo: python scripts/verify-pn-images.py <results-dir>

<results-dir> holds result*.json files, each a list of {"id", "pn", "urls": [page URLs found by searching the exact part
number]} (ids as in data/velmach-import.json). Sources allowed (decision 2026-10-13): the manufacturer's own site or a
distributor's store; marketplaces and brokers are refused.

For every page, in the order given:
  - robots.txt is respected and at most one request per second is made; a site that refuses or times out is skipped
  - the page must show the exact part number (as a whole code: "36853" does not match "368531")
  - the image is the page's product image (og:image, else an <img> whose address or alt text holds the part number);
    logos, placeholders, banners and icons are refused, and the downloaded picture must be a real image of 200 px or more
  - a picture found for two different products is not used for either (pack-size variants of one product may share it)
Every decision is written to reports/web-images-pn.csv; accepted images are added to data/velmach-web-images.json
({id: {image, page, site}}), which scripts/extract-documents.py and the importer use.
"""
import collections, csv, glob, hashlib, html, importlib.util, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = 'VelmachCatalogImporter/1.0 (+https://www.velmachaerospace.com)'
LOG = os.path.join(ROOT, 'reports', 'web-images-pn.csv')
OUT = os.path.join(ROOT, 'data', 'velmach-web-images.json')
BLOCK = re.compile(r'amazon\.|ebay\.|alibaba\.|aliexpress\.|walmart\.|etsy\.|temu\.|dhgate\.|indiamart\.|made-in-china\.|partsbase\.|ilsmart\.'
                   r'|nsn|pilotjohn\.com|wikipedia\.|patents\.|\.pdf($|\?)', re.I)
BAD_IMG = re.compile(r'logo|placeholder|no[-_ ]?image|noimage|default|banner|icon|sprite|blank|spacer|coming[-_]soon|og[-_]?default', re.I)
spec = importlib.util.spec_from_file_location('fw', os.path.join(ROOT, 'scripts', 'find-web-images.py'))
FW = importlib.util.module_from_spec(spec); spec.loader.exec_module(FW)


class NetworkDown(Exception):
    pass


class Fetcher:
    # robots.txt is read for this script's name and for ClaudeBot (the AI agent running it); the stricter rule wins:
    # a page either one may not fetch is not fetched, and the longer Crawl-delay is kept (at least 1 second)
    def __init__(self):
        self.last, self.robots, self.blocked, self.delay = {}, {}, {}, {}

    def wait(self, host=''):
        gap = self.delay.get(host, 1.0)
        d = time.time() - self.last.get(host, 0.0)
        if d < gap:
            time.sleep(gap - d)
        self.last[host] = time.time()

    def allowed(self, url):
        u = urllib.parse.urlparse(url)
        host = f'{u.scheme}://{u.hostname}'
        if host not in self.robots:
            rp = urllib.robotparser.RobotFileParser(host + '/robots.txt')
            try:
                self.wait(u.hostname)
                with urllib.request.urlopen(urllib.request.Request(host + '/robots.txt', headers={'User-Agent': UA}), timeout=25) as r:
                    rp.parse(r.read().decode('utf-8', 'replace').splitlines())
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    rp.disallow_all = True
                else:
                    rp.allow_all = True
            except Exception:
                rp.disallow_all = True               # robots.txt unreachable: the site is not used
            self.robots[host] = rp
            delays = [rp.crawl_delay(a) for a in (UA, 'ClaudeBot')] if rp.default_entry or rp.entries else []
            self.delay[u.hostname] = max([1.0] + [float(x) for x in delays if x])
        rp = self.robots[host]
        return rp.can_fetch(UA, url) and rp.can_fetch('ClaudeBot', url)

    def get(self, url, binary=False):
        host = urllib.parse.urlparse(url).hostname or ''
        if host in self.blocked:
            raise PermissionError(self.blocked[host])
        if not self.allowed(url):
            raise PermissionError('robots.txt does not allow this page')
        for attempt in range(6):
            self.wait(host)
            try:
                req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*' if binary else 'text/html'})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read(15 * 1024 * 1024)
                    self.net_fail = 0
                    return data if binary else data.decode(r.headers.get_content_charset() or 'utf-8', 'replace')
            except urllib.error.HTTPError as e:
                if e.code in (401, 403, 429):
                    self.blocked[host] = f'site refused automated access (HTTP {e.code}); skipped'
                    raise PermissionError(self.blocked[host])
                raise ValueError(f'HTTP {e.code}')
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                # a network problem on this side (e.g. WinError 10013) is not the site saying no: wait and try again
                if attempt < 5:
                    time.sleep(30 * (attempt + 1)); continue
                self.net_fail = getattr(self, 'net_fail', 0) + 1
                if self.net_fail >= 3:
                    raise NetworkDown(f'no network for {host} after several retries ({getattr(e, "reason", e)})')
                raise ValueError(f'did not answer ({getattr(e, "reason", e)})')


def pn_pattern(pn):
    # the exact code, as a whole: separators between its parts may be "-", " " or nothing
    parts = [re.escape(x) for x in re.split(r'[\s\-]+', pn.strip()) if x]
    return re.compile(r'(?<![A-Za-z0-9])' + r'[\s\-]?'.join(parts) + r'(?![A-Za-z0-9])', re.I)


COLOURS = {'white', 'black', 'red', 'blue', 'green', 'yellow', 'gray', 'grey', 'orange', 'brown', 'tan', 'amber', 'clear', 'silver',
           'maroon', 'purple', 'pink', 'beige', 'ivory', 'indigo', 'natural', 'neutral', 'cream', 'gold', 'violet'}


def related_product(ours, theirs):
    # for a product known only by its name: every model number of the name is on the page (the page may add codes such as
    # a catalyst "PC-216" or a stock number), one distinctive word matches, and the colours do not contradict
    a, b = FW.model_keys(ours), FW.model_keys(theirs)
    if not a or not a <= b:
        return False
    mine, page = FW.tokens(ours), set(FW.tokens(theirs))
    words = [w for w in mine if not re.search(r'\d', w) and w not in FW.COMMON and len(w) > 2 and w not in COLOURS]
    if words and not any(w in page or w in ''.join(FW.tokens(theirs)) for w in words):
        return False
    c1, c2 = COLOURS & set(mine), COLOURS & page
    return not (c1 and c2 and not (c1 & c2))


def text_of(page):
    page = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', page, flags=re.S | re.I)
    return html.unescape(re.sub(r'<[^>]+>', ' ', page))


def product_image(page, url, pat):
    og = FW.meta(page, 'og:image')
    if og and not BAD_IMG.search(og):
        return urllib.parse.urljoin(url, og)
    for tag in re.findall(r'<img[^>]+>', page, re.I):
        src = re.search(r'(?:data-src|src)=["\']([^"\']+)', tag)
        alt = re.search(r'alt=["\']([^"\']*)', tag)
        if src and not BAD_IMG.search(src.group(1)) and (pat.search(src.group(1)) or (alt and pat.search(alt.group(1)))):
            return urllib.parse.urljoin(url, html.unescape(src.group(1)))
    return ''


def family_ids():
    # products whose only photo is a catalog family photo: an exact photo may replace it
    path = os.path.join(ROOT, 'data', 'velmach-products.json')
    if not os.path.exists(path):
        return set()
    return {p['key'] for p in json.load(open(path, encoding='utf-8'))['products']
            if p['images'] and all(i.get('note') == 'family photo' for i in p['images'])}


def main():
    rdir = sys.argv[1]
    store = {}
    for line in open(os.path.join(ROOT, 'data', 'catalog', 'products.jsonl'), encoding='utf-8'):
        if line.strip():
            r = json.loads(line)
            store[r['key'][4:] if r['key'].startswith('doc:') else r['key']] = r
    items = [x for f in sorted(glob.glob(os.path.join(rdir, 'result*.json'))) for x in json.load(open(f, encoding='utf-8'))]
    fam = family_ids()
    f = Fetcher()
    from PIL import Image
    found, log, stats = {}, [], collections.Counter()
    # progress is saved as it goes; running the same command again carries on where it stopped
    partial = os.path.join(rdir, '.progress.json')
    # one run per folder: a second copy would double the requests to the site and mix up the progress file
    lock = os.path.join(rdir, '.lock')
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 300:
        sys.exit(f'another run is working on {rdir} (lock updated less than 5 minutes ago); not starting')
    open(lock, 'w').write(str(os.getpid()))
    done_ids = set()
    if os.path.exists(partial):
        pr = json.load(open(partial, encoding='utf-8'))
        found, log, done_ids = pr['found'], pr['log'], set(pr['done'])
        stats.update(pr.get('stats', {}))
        print(f'resuming: {len(done_ids)} products already checked', flush=True)
    for n_it, it in enumerate(items):
        if n_it:
            # saved after every product, so a verified photo can be put on the site straight away
            tmp = partial + '.tmp'
            json.dump({'found': found, 'log': log, 'done': sorted(done_ids), 'stats': stats}, open(tmp, 'w', encoding='utf-8'))
            for _ in range(20):
                try:
                    os.replace(tmp, partial); break
                except PermissionError:
                    time.sleep(0.5)
            open(lock, 'w').write(str(os.getpid()))
            if n_it % 20 == 0:
                print(f'  {len(done_ids)}/{len(items)} checked, {stats["verified"]} photos so far', flush=True)
        if it['id'] in done_ids:
            continue
        done_ids.add(it['id'])
        rec = store.get(it['id'])
        if not rec or (rec.get('images') and it['id'] not in fam):
            continue
        by_name = it.get('match') == 'name' or not it['pn'].strip()
        pat = pn_pattern(it['pn']) if it['pn'].strip() else re.compile(r'(?!x)x')
        done = False
        for url in it.get('urls', [])[:3]:
            host = urllib.parse.urlparse(url).hostname or ''
            row = [it['id'], it['pn'], rec['title'], url, host, '', '', '']
            if BLOCK.search(url):
                row[7] = 'refused: marketplace / broker / not a product page'; log.append(row); continue
            try:
                page = f.get(url)
            except NetworkDown as e:
                done_ids.discard(it['id'])
                json.dump({'found': found, 'log': log, 'done': sorted(done_ids), 'stats': stats}, open(partial, 'w', encoding='utf-8'))
                os.remove(lock)
                sys.exit(f'stopped: {e}; run the same command again to carry on')
            except Exception as e:
                row[7] = 'skipped: ' + str(e); log.append(row); stats['site blocked'] += 1; continue
            if by_name:
                # no part number in the documents: the page's own product name must be the same product
                # (same model numbers and name words; another pack size of it is fine)
                names = FW.page_names(page)
                if not any(related_product(rec['title'], n) for n in names[:3]):
                    row[5], row[7] = 'no (page names: ' + '; '.join(names[:2])[:80] + ')', 'not used: page is not the same product'
                    log.append(row); stats['not same product'] += 1; continue
                row[5] = 'same product by name (page: ' + names[0][:60] + ')'
                img = FW.meta(page, 'og:image')
                img = urllib.parse.urljoin(url, img) if img and not BAD_IMG.search(img) else ''
            else:
                if not pat.search(text_of(page)):
                    row[5], row[7] = 'no', 'not used: exact part number not on the page'; log.append(row); stats['no exact pn'] += 1; continue
                row[5] = 'yes'
                img = product_image(page, url, pat)
            if not img:
                row[7] = 'not used: no product image on the page'; log.append(row); stats['no image'] += 1; continue
            try:
                data = f.get(img, binary=True)
                im = Image.open(io.BytesIO(data)); im.load()
                if min(im.size) < 200:
                    raise ValueError(f'image too small ({im.size[0]}x{im.size[1]})')
                if im.convert('L').getextrema()[0] == im.convert('L').getextrema()[1]:
                    raise ValueError('blank image')
            except Exception as e:
                row[6], row[7] = img, 'not used: ' + str(e)[:80]; log.append(row); stats['bad image'] += 1; continue
            row[6], row[7] = img, 'verified: web-sourced'
            stats['verified'] += 1
            ident = FW.designation(rec['title'])      # product name without pack size: pack variants may share a photo
            found[it['id']] = {'image': img, 'page': url, 'site': host, 'pn': ident, 'hash': hashlib.sha1(data).hexdigest(), 'row': row}
            log.append(row); done = True
            break
        if not done and not it.get('urls'):
            log.append([it['id'], it['pn'], rec['title'], '', '', '', '', 'no page found by part-number search (' + (it.get('note') or '')[:60] + ')'])
    # one picture, one part number: a picture found for different part numbers is dropped everywhere
    by_hash = collections.defaultdict(set)
    for k, v in found.items():
        by_hash[v['hash']].add(re.sub(r'[^a-z0-9]', '', v['pn'].lower()))
    out = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
    for k, v in found.items():
        if len(by_hash[v['hash']]) > 1:
            v['row'][7] = 'not used: same picture found for different products'; stats['shared picture'] += 1; continue
        out[k] = {'image': v['image'], 'page': v['page'], 'site': v['site']}
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    new = not os.path.exists(LOG)
    with open(LOG, 'a', encoding='utf-8-sig' if new else 'utf-8', newline='') as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(['id', 'part number', 'title', 'page URL', 'site', 'exact part number on page', 'image URL', 'status'])
        w.writerows(log)
    for x in (partial, lock):
        if os.path.exists(x):
            os.remove(x)
    print(dict(stats), '| added:', sum(1 for k, v in found.items() if k in out), '| blocked sites:', len(f.blocked))


if __name__ == '__main__':
    main()
