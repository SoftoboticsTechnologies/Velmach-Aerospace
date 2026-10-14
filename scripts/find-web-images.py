"""Find official product images for your own Velmach products: python scripts/find-web-images.py [--site shell.com]

Only these manufacturer sites are used (no resellers, no marketplaces):
  shop.boeing.com, 3m.com, henkel-adhesives.com, loctite.com, eastman.com, hexcel.com, ppgaerospace.com (now ppg.com/aerospace),
  shell.com, zipchem.com

How a product gets an image:
  1. A product page on one of those sites is found: Shell from its own AeroShell index pages; Henkel (henkel-adhesives.com,
     where loctite.com now leads), Eastman, Hexcel, Zip-Chem and shop.boeing.com from the product sitemaps the sites
     publish for search engines; anything else from data/velmach-staging/web-candidates.json ({"<name>": "<page URL>"}).
  2. The page is fetched (robots.txt respected, at most one request per second). If the site refuses or times out, the
     site is skipped and logged; nothing tries to get around a block.
  3. The page's own title must name the exact product: the same model numbers ("EA 9394" is not "EA 9394S") and the same
     brand word, ignoring case, spaces, hyphens and the pack size. A product sold today under another name (Hysol EA 9394
     is now LOCTITE EA 9394 AERO) is logged for you, not matched.
  4. The page's product image (og:image) is taken. Products that are only size / pack variants of that product share it.
Every lookup is written to reports/web-images.csv (image URL, page URL, site, exact match, status). Verified images are
written to data/velmach-web-images.json for scripts/import-products.py (with sourceUrl = the product page).
"""
import argparse, collections, csv, html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import catalog_lib as L

# ppg.com: ppgaerospace.com now redirects to PPG's aerospace pages on ppg.com (approved 2026-10-13)
SITES = ['shop.boeing.com', '3m.com', 'henkel-adhesives.com', 'loctite.com', 'eastman.com', 'hexcel.com', 'ppgaerospace.com', 'ppg.com', 'shell.com', 'zipchem.com']
UA = 'VelmachCatalogImporter/1.0 (+https://www.velmachaerospace.com)'
QUEUE = os.path.join(ROOT, 'reports', 'web-images.csv')
CANDIDATES = os.path.join(ROOT, 'data', 'velmach-staging', 'web-candidates.json')
OUT = os.path.join(ROOT, 'data', 'velmach-web-images.json')
SHELL_INDEX = ['https://www.shell.com/business-customers/aviation/aeroshell.html']
# pack sizes: "(1 QT)", "420 ML", "5 GLN", "3 KG"; a bare "27L" is a model name ("Cor-Ban 27L"), not 27 litres
PACK = re.compile(r'\([^)]*\d[^)]*\)|\b\d+(?:[.,]\d+)?\s*(?:ml|lt|ltr|kg|gr|qt|gln|gal|oz|lb|lbs|pt)\b\.?|\b\d+(?:[.,]\d+)?\s+(?:l|g)\b|\baerosol\b|\bcartridge\b|\bcan\b|\bdrum\b|\bpail\b', re.I)


def site_of(url):
    host = urllib.parse.urlparse(url).hostname or ''
    return next((s for s in SITES if host == s or host.endswith('.' + s)), '')


SITEMAPS = {
    'henkel-adhesives.com': ['https://next.henkel-adhesives.com/us/en.sitemap.products-sitemap.xml'],
    'eastman.com': ['https://www.eastman.com/en/products-new/sitemap.xml'],
    'hexcel.com': ['https://www.hexcel.com/page-sitemap.xml'],
    'zipchem.com': ['https://zipchem.com/product-sitemap.xml'],
    'shop.boeing.com': ['https://shop.boeing.com/sitemap.xml'],
    'ppg.com': ['https://www.ppg.com/ppg-aerospace-sitemap.xml'],
}
COMMON = {'aero', 'adhesive', 'sealant', 'oil', 'grease', 'fluid', 'kit', 'paste', 'epoxy', 'the', 'and', 'for', 'with', 'class', 'type',
          'grade', 'spray', 'film', 'primer', 'part', 'compound', 'cleaner', 'mil', 'prf', 'spec', 'new', 'offer'}


def tokens(title):
    t = PACK.sub(' ', title.lower())
    t = re.sub(r'\b(mil|spec|specification)\b.*$', ' ', t)
    t = re.sub(r'(?<=[a-z])-(?=[a-z])', '', t)              # "cor-ban" -> "corban", "sur-prep" -> "surprep"
    t = re.sub(r'(?<=[a-z])-(?=\d)|(?<=\d)-(?=[a-z])', '', t)  # "ea-9394" -> "ea9394"
    return re.findall(r'[a-z0-9.]+', t)


def model_keys(title):
    # numbers with their short letter prefix: "LOCTITE EA 9394 AERO" -> {"ea9394"}, "COR-BAN 27L" -> {"27l"}
    tk, keys = tokens(title), set()
    for i, x in enumerate(tk):
        if re.search(r'\d', x):
            prev = tk[i - 1] if i and re.fullmatch(r'[a-z]{1,4}', tk[i - 1]) and tk[i - 1] not in COMMON else ''
            keys.add((prev + x).strip('.'))
    return keys


def brand_word(title):
    tk = [x for x in tokens(title) if not re.search(r'\d', x) and x not in COMMON and len(x) > 2]
    return tk[0] if tk else ''


def same_product(ours, theirs):
    # same model numbers, and at least one distinctive word of your name on the page ("ZIP-CHEM CALLA 855" = "Calla 855")
    # and no extra distinctive word on the page ("Cor-Ban 35 Undyed", "Cor-Ban 27L Applications and Training" are not
    # simply "CORBAN 35" / "CORBAN 27L")
    a, b = model_keys(ours), model_keys(theirs)
    words = [x for x in tokens(ours) if not re.search(r'\d', x) and x not in COMMON and len(x) > 2]
    page = set(tokens(theirs)) | {''.join(tokens(theirs))}
    mine = ''.join(tokens(ours))
    extra = [x for x in tokens(theirs) if not re.search(r'\d', x) and x not in COMMON and len(x) > 2 and x not in mine]
    return bool(a) and a == b and any(w in page or w in ''.join(tokens(theirs)) for w in words) and not extra


def designation(title):
    """'AEROSHELL FLUID 41 (1 QT)' -> 'aeroshell fluid 41': name and number without pack size, case or punctuation."""
    t = PACK.sub(' ', title)
    t = re.sub(r'\b(mil|spec|specification)\b.*$', ' ', t, flags=re.I)
    return re.sub(r'[^a-z0-9]+', ' ', t.lower()).strip()


class Fetcher:
    def __init__(self, log):
        self.last, self.robots, self.blocked, self.log = 0.0, {}, {}, log

    def allowed(self, url):
        host = urllib.parse.urlparse(url).scheme + '://' + urllib.parse.urlparse(url).hostname
        if host not in self.robots:
            # read robots.txt with this script's own User-Agent (the standard reader sends Python's default name, which
            # some sites refuse, and would then treat the whole site as disallowed)
            rp = urllib.robotparser.RobotFileParser(host + '/robots.txt')
            try:
                self.wait()
                with urllib.request.urlopen(urllib.request.Request(host + '/robots.txt', headers={'User-Agent': UA}), timeout=30) as r:
                    rp.parse(r.read().decode('utf-8', 'replace').splitlines())
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    rp.disallow_all = True
                else:
                    rp.allow_all = True              # no robots.txt: everything allowed
            except Exception:
                rp = None
            self.robots[host] = rp
        rp = self.robots[host]
        # the stricter of this script's rules and ClaudeBot's (the AI agent running it)
        return rp is None or (rp.can_fetch(UA, url) and rp.can_fetch('ClaudeBot', url))

    def wait(self):
        d = time.time() - self.last
        if d < 1.0:
            time.sleep(1.0 - d)
        self.last = time.time()

    def get(self, url, binary=False):
        site = site_of(url)
        if not site:
            raise ValueError('not an approved manufacturer site')
        if site in self.blocked:
            raise PermissionError(self.blocked[site])
        if not self.allowed(url):
            raise PermissionError('robots.txt does not allow this page')
        self.wait()
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*' if binary else 'text/html'})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read(20 * 1024 * 1024)
                return data if binary else data.decode(r.headers.get_content_charset() or 'utf-8', 'replace')
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 429):
                self.blocked[site] = f'site refused automated access (HTTP {e.code}); skipped'
                self.log(f'{site}: {self.blocked[site]}')
                raise PermissionError(self.blocked[site])
            raise ValueError(f'HTTP {e.code}')
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            self.blocked[site] = f'site did not answer ({getattr(e, "reason", e)}); skipped'
            self.log(f'{site}: {self.blocked[site]}')
            raise PermissionError(self.blocked[site])


def meta(page, prop):
    m = re.search(r'<meta[^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\'][^>]*content=["\']([^"\']+)', page, re.I) or \
        re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']' + re.escape(prop) + r'["\']', page, re.I)
    return html.unescape(m.group(1)).strip() if m else ''


# image servers a manufacturer runs for its own site (its own domain, a different host name)
IMAGE_HOSTS = {'henkel-adhesives.com': ['dm.henkel-dam.com'], 'eastman.com': ['media.eastman.com']}


def official_image(img, site):
    host = urllib.parse.urlparse(img).hostname or ''
    return site_of(img) == site or host in IMAGE_HOSTS.get(site, [])


def product_image(page):
    """The product photo: Henkel's "packshot" from its image server (its og:image is the brand logo), otherwise og:image.
    An image whose address names a logo is never a product photo."""
    m = re.search(r'https://dm\.henkel-dam\.com/is/image/henkel/packshot-[A-Za-z0-9_.-]+', page)
    img = m.group(0) if m else meta(page, 'og:image')
    return '' if re.search(r'logo', img, re.I) else img


def page_names(page):
    """Names the page gives its product: <title> (before the first separator), og:title, <h1>."""
    names = []
    t = re.search(r'<title[^>]*>([^<]+)', page, re.I)
    if t:
        names.append(re.split(r'\s[|–-]\s', html.unescape(t.group(1)))[0])
    for x in (meta(page, 'og:title'), *(re.sub(r'<[^>]+>', ' ', h) for h in re.findall(r'<h1[^>]*>(.*?)</h1>', page, re.I | re.S))):
        if x.strip():
            names.append(html.unescape(re.split(r'\s[|–]\s', x)[0]))
    return [n.strip() for n in names if n.strip()]


def shell_pages(f, log):
    """AeroShell product pages. Shell's pages are built from a public <page>.model.json next to each page; the AeroShell
    page lists the product categories, each category lists its product pages."""
    base = 'https://www.shell.com/business-customers/aviation/aeroshell'
    def links(url):
        try:
            data = f.get(url[:-5] + '.model.json' if url.endswith('.html') else url + '.model.json')
        except Exception as e:
            log(f'shell.com {url}: {e}'); return set()
        return set(re.findall(r'/business-customers/aviation/aeroshell/[a-z0-9\-]+(?:/[a-z0-9\-]+)?', data))
    cats = {u for u in links(base) if u.count('/') == 4 and not re.search(r'knowledge|contact|where-to-buy', u)}
    products = set()
    for c in sorted(cats):
        products |= {u for u in links('https://www.shell.com' + c) if u.count('/') == 5 and not u.endswith('/jcr')}
    pages = {}
    for u in sorted(products):
        url = 'https://www.shell.com' + u + '.html'
        try:
            page = f.get(url)
        except Exception as e:
            log(f'shell.com {url}: {e}'); continue
        names, img = page_names(page), meta(page, 'og:image')
        if names and img:
            pages[url] = (names, img)
    log(f'shell.com: {len(cats)} categories, {len(products)} product pages')
    return pages


def sitemap_pages(f, site, wanted, log):
    # product URLs from the site's sitemap whose address contains every model number of one of your products
    urls = []
    for sm in SITEMAPS.get(site, []):
        try:
            data = f.get(sm)
        except Exception as e:
            log(f'{site} sitemap: {e}'); return {}
        urls += re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', data)
    log(f'{site}: {len(urls)} pages in the sitemap')
    hits = collections.defaultdict(list)
    for u in urls:
        if re.search(r'/(zh|fr|de|es|it|ja|ko|pt|ru)/', u) or '/variation/' in u:
            continue                                       # one language and one address per product is enough
        m = re.search(r'central-pdp\.html/([^/]+)/', u)    # Henkel: .../central-pdp.html/<product-name>/<id>.html
        name = m.group(1) if m else u.rstrip('/').rsplit('/', 1)[-1].replace('.html', '')
        slug = ''.join(tokens(urllib.parse.unquote(name)))
        for title, keys in wanted.items():
            words = [x for x in tokens(title) if not re.search(r'\d', x) and x not in COMMON and len(x) > 2]
            if keys and all(k.replace('.', '') in slug.replace('.', '') for k in keys) and any(w in slug for w in words):
                hits[title].append(u)
    pages = {}
    for title, us in hits.items():
        for u in us[:3]:
            if u in pages:
                continue
            try:
                page = f.get(u)
            except Exception as e:
                log(f'{site} {u}: {e}'); break
            pages[u] = (page_names(page), product_image(page))
    return pages


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--site', default='', help='only this site (e.g. shell.com)')
    args = ap.parse_args()
    logs = []
    log = lambda m: (logs.append(m), print(m, flush=True))
    rows = list(csv.reader(open(QUEUE, encoding='utf-8-sig')))
    head, body = rows[0], rows[1:]
    H = {h: i for i, h in enumerate(head)}
    f = Fetcher(log)
    # candidate pages: designation -> (page url, names on page, image url)
    found = {}
    if args.site in ('', 'shell.com'):
        for url, (names, img) in shell_pages(f, log).items():
            for n in names:
                found.setdefault(designation(n), (url, names, img))
        log(f'shell.com: {len(found)} AeroShell product pages read')
    pending = [r for r in body if r[H['status']] == 'pending']
    wanted = {r[H['title']]: model_keys(r[H['title']]) for r in pending}
    page_list = []
    for site in SITEMAPS:
        if args.site and args.site != site:
            continue
        for url, (names, img) in sitemap_pages(f, site, wanted, log).items():
            page_list.append((url, names, img))
    cands = json.load(open(CANDIDATES, encoding='utf-8')) if os.path.exists(CANDIDATES) else {}
    for name, url in cands.items():
        if args.site and site_of(url) != args.site:
            continue
        d = designation(name)
        if d in found:
            continue
        try:
            page = f.get(url)
        except Exception as e:
            found[d] = (url, [], '', str(e)); continue
        found[d] = (url, page_names(page), product_image(page))
    # match every queued product by designation; the page's own name must give the same designation
    out, stats = {}, collections.Counter()
    for r in body:
        if r[H['status']] not in ('pending', 'not found on approved sites') and not r[H['status']].startswith('pilot'):
            continue
        d = designation(r[H['title']])
        hit = found.get(d)
        if not hit:
            # sitemap pages: the page's own name must be the same product
            close = [(u, n, i) for u, n, i in page_list if any(same_product(r[H['title']], x) for x in n)]
            near = [(u, n, i) for u, n, i in page_list if not close and n and model_keys(r[H['title']]) & model_keys(n[0])
                    and brand_word(r[H['title']]) and brand_word(r[H['title']]) in ''.join(tokens(n[0]))]
            if close:
                hit = close[0]
            elif near:
                u, n, i = near[0]
                r[H['page URL']], r[H['site (manufacturer / authorized distributor)']] = u, site_of(u)
                r[H['exact match shown on page']], r[H['status']] = 'no (page names: ' + n[0] + ')', 'not used: page is not the exact product (check)'
                stats['not exact'] += 1; continue
            else:
                continue
        url, names, img = hit[:3]
        err = hit[3] if len(hit) > 3 else ''
        site = site_of(url)
        exact = any(designation(n) == d or same_product(r[H['title']], n) for n in names[:2])
        r[H['page URL']], r[H['site (manufacturer / authorized distributor)']] = url, site
        if err:
            r[H['status']] = 'skipped: ' + err; stats['blocked'] += 1; continue
        if not exact:
            r[H['exact match shown on page']], r[H['status']] = 'no (page names: ' + '; '.join(names[:2]) + ')', 'not used: page is not the exact product'
            stats['not exact'] += 1; continue
        if not img or not official_image(img, site):              # the image must come from the manufacturer's own site or image server
            r[H['exact match shown on page']], r[H['status']] = 'yes', 'not used: no product image on the page'
            stats['no image'] += 1; continue
        r[H['image URL']], r[H['exact match shown on page']], r[H['status']] = img, 'yes (' + names[0] + ')', 'verified: web-sourced'
        out[r[H['id']]] = {'image': img, 'page': url, 'site': site}
        stats['verified'] += 1
    with open(QUEUE, 'w', encoding='utf-8-sig', newline='') as fh:
        csv.writer(fh).writerows([head] + body)
    # the image list is rebuilt from every verified row, so a match that is no longer accepted drops out
    allv = {r[H['id']]: {'image': r[H['image URL']], 'page': r[H['page URL']], 'site': r[H['site (manufacturer / authorized distributor)']]}
            for r in body if r[H['status']].startswith('verified')}
    json.dump(allv, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(dict(stats), '| blocked sites:', f.blocked or 'none')


if __name__ == '__main__':
    main()
