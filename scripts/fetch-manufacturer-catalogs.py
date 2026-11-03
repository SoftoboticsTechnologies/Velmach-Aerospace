"""Download manufacturers' public product lists: python scripts/fetch-manufacturer-catalogs.py [--only tronair]

For brands Velmach supplies (data/supplier-brands.json), the product names and part numbers come from the manufacturers'
own websites, through the product feeds and sitemaps those sites publish:
  tronair    www.tronair.com/products.json (Shopify; also lists the brands Tronair sells: Eagle, Malabar, Columbus Jack ...)
  startpac   startpac.com/wp-json/wc/store/v1/products (WooCommerce Store API)
  laversab   laversab.com/wp-json/wc/store/v1/products (WooCommerce Store API)
  itwgse     itwgse.com/product-sitemap.xml, then each product page's title (ITW GSE, which includes Hobart)
  unitron    unitronlp.com/sitemap.xml (/product/ pages), then each page's title
Every URL is checked against the site's robots.txt first, requests are spaced by --delay seconds, and a site that
refuses (401/403/429) is skipped, not retried. Raw results are saved to data/velmach-staging/manufacturers/<site>.json
for scripts/import-manufacturer-catalogs.py. Descriptions and photos are not taken (they belong to the manufacturer).
"""
import argparse, html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_lib as L

OUT = os.path.join(L.ROOT, 'data', 'velmach-staging', 'manufacturers')
UA = 'VelmachCatalogImporter/1.0 (+https://www.velmachaerospace.com)'


class Polite:
    def __init__(self, delay):
        self.delay, self.last, self.robots = delay, 0.0, {}

    def allowed(self, url):
        base = '{0.scheme}://{0.netloc}'.format(urllib.parse.urlparse(url))
        if base not in self.robots:
            # read robots.txt with our own User-Agent: some sites refuse Python's default one, which RobotFileParser.read()
            # would take as "everything disallowed"
            rp = urllib.robotparser.RobotFileParser(base + '/robots.txt')
            try:
                req = urllib.request.Request(base + '/robots.txt', headers={'User-Agent': UA})
                with urllib.request.urlopen(req, timeout=30) as r:
                    rp.parse(r.read().decode('utf-8', 'replace').splitlines())
            except urllib.error.HTTPError as e:
                rp = 'deny' if e.code in (401, 403) else None    # no robots.txt (404): everything allowed
            except (urllib.error.URLError, OSError):
                rp = None
            self.robots[base] = rp
        rp = self.robots[base]
        if rp == 'deny':
            return False
        if rp is not None:
            self.delay = max(self.delay, float(rp.crawl_delay(UA) or 0))     # the site's Crawl-delay
        return rp is None or rp.can_fetch(UA, url)

    def get(self, url):
        if not self.allowed(url):
            raise PermissionError(f'robots.txt disallows {url}')
        wait = self.delay - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json, text/html, application/xml'})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    return r.read().decode('utf-8', 'replace')
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == 3:
                    raise
                # "too many requests": wait as long as the site asks (Retry-After) and go slower from now on
                wait = int(e.headers.get('Retry-After') or 0) or 60 * (attempt + 1)
                self.delay = max(self.delay * 2, 3)
                print(f'  site asked to slow down (429): waiting {wait}s, then {self.delay}s between requests', flush=True)
                time.sleep(wait)
                self.last = time.time()


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', str(s or '')))).strip()


def shopify(w, base):
    out, page = [], 1
    while True:
        try:
            d = json.loads(w.get(f'{base}/products.json?limit=250&page={page}'))
        except urllib.error.HTTPError as e:
            print(f'  stopped at page {page} (HTTP {e.code}); keeping {len(out)} products read so far')
            break
        items = d.get('products', [])
        if not items:
            break
        for p in items:
            out.append({'title': p.get('title', ''), 'vendor': p.get('vendor', ''), 'type': p.get('product_type', ''), 'tags': p.get('tags', []),
                        'skus': [v.get('sku') or '' for v in p.get('variants', [])], 'variants': [v.get('title', '') for v in p.get('variants', [])],
                        'heading': text(re.search(r'<h\d[^>]*>(.*?)</h\d>', p.get('body_html') or '', re.S).group(1)) if re.search(r'<h\d[^>]*>(.*?)</h\d>', p.get('body_html') or '', re.S) else '',
                        'url': f"{base}/products/{p.get('handle', '')}"})
        print(f'  page {page}: {len(out)} products', flush=True)
        page += 1
    return out


def woo(w, base):
    out, page = [], 1
    while True:
        d = json.loads(w.get(f'{base}/wp-json/wc/store/v1/products?per_page=100&page={page}'))
        if not d:
            break
        for p in d:
            out.append({'title': text(p.get('name')), 'sku': p.get('sku', ''), 'categories': [text(c.get('name')) for c in p.get('categories', [])],
                        'url': p.get('permalink', '')})
        print(f'  page {page}: {len(out)} products', flush=True)
        page += 1
    return out


def sitemap_pages(w, sitemap, keep):
    urls = sorted(set(u for u in re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', w.get(sitemap)) if keep(u)))
    out = []
    for i, u in enumerate(urls, 1):
        try:
            page = w.get(u)
        except (urllib.error.URLError, PermissionError, OSError) as e:
            print(f'  skip {u}: {e}'); continue
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', page, re.S)
        title = re.search(r'<title[^>]*>(.*?)</title>', page, re.S)
        out.append({'title': text(h1.group(1)) if h1 else '', 'pageTitle': text(title.group(1)) if title else '', 'url': u})
        if i % 10 == 0:
            print(f'  {i}/{len(urls)} pages', flush=True)
    return out


SITES = {
    'tronair': lambda w: shopify(w, 'https://www.tronair.com'),
    'startpac': lambda w: woo(w, 'https://startpac.com'),
    'laversab': lambda w: woo(w, 'https://laversab.com'),
    'itwgse': lambda w: sitemap_pages(w, 'https://itwgse.com/product-sitemap.xml', lambda u: '/products/' in u and u.rstrip('/').count('/') >= 5),
    'unitron': lambda w: sitemap_pages(w, 'https://unitronlp.com/sitemap.xml', lambda u: '/product/' in u),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', choices=sorted(SITES), action='append')
    ap.add_argument('--delay', type=float, default=1.5)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    w = Polite(a.delay)
    for name in a.only or SITES:
        print(f'{name}:', flush=True)
        try:
            items = SITES[name](w)
        except urllib.error.HTTPError as e:
            print(f'  refused (HTTP {e.code}); skipped'); continue
        except (urllib.error.URLError, PermissionError, OSError, ValueError) as e:
            print(f'  failed ({e}); skipped'); continue
        L.write_file(os.path.join(OUT, f'{name}.json'), json.dumps({'fetched': time.strftime('%Y-%m-%d'), 'items': items}, ensure_ascii=False, indent=0).encode('utf-8'))
        print(f'  saved {len(items)} items')


if __name__ == '__main__':
    main()
