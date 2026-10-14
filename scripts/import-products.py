"""Import products into the catalogue: python scripts/import-products.py [data/products.csv]

Reads a CSV (UTF-8, header row) or a JSON array with these columns (names are case-insensitive):
  title*, partNumber, brand, categoryParent*, categoryChild, shortDescription, description (HTML or plain text),
  specifications, images, documents, compatibleAircraft, condition (New / Used), sourceUrl, documentSource, slug, sample
  * required. Price columns are never imported (they are listed as ignored in the report).
  importKey (optional): a stable id for the product from scripts/extract-documents.py; when given, it is used to match
  rows to stored products instead of part number + brand.
  partNumber and brand are left empty when the source does not state them (nothing is made up); such a product is
  matched by its title (and brand) instead of its part number, and its image folder is named after the title.
List columns in a CSV use "|" between items:
  specifications      Capacity: 12 t | Weight: 85 kg        (or a JSON object / array)
  images              https://example.com/a.jpg | samples/images/b.png   (URLs or local files)
  documents           Datasheet::https://example.com/ds.pdf | https://example.com/manual.pdf
  compatibleAircraft  boeing/737-ng | Airbus A320            (ids or names from data/aircraft.js; empty = fits all)
Categories are matched by slug or English name (data/categories.js). New brands are added to data/brands.js.

What it does, per product:
  - upserts by part number + brand (re-running the same file changes nothing; a blank cell keeps the stored value)
  - downloads every image in the order given (or copies a local file), at most one download per second (--rate),
    into images/products/<part-number>/<part-number>-1.jpg, -2.jpg ... at the original resolution, plus a 1200 px
    display copy (display/) and a 400 px thumbnail (thumbs/) as WebP; PDFs go to images/products/<part-number>/docs/
    (--link-documents keeps links). A product without images keeps the site's "no image" state; nothing is substituted.
  - logs problems to reports/import-errors.log and carries on
  - saves progress regularly: if it stops, run the same command again to resume (--restart starts over)
  - writes reports/missing-images.csv and reports/import-report-<batch>-<date>.md (per-category counts, failed and
    skipped rows, 10 random products to check against their source)
Then it runs scripts/build-catalog.py to publish the JSON files the site reads.

Batches: --category pilot-supplies imports only the rows of that top-level category (slug or English name).
Other commands:
  --remove-samples   delete every product marked sample=true (and its images), then rebuild
"""
import argparse, concurrent.futures as cf, csv, datetime, hashlib, io, json, os, random, re, shutil, sys, threading, time, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_lib as L

try:
    from PIL import Image, ImageOps
except ImportError:
    raise SystemExit('Pillow is required: pip install Pillow')

STATE = os.path.join(L.CATALOG, '.import-state.json')
ERRLOG = os.path.join(L.ROOT, 'reports', 'import-errors.log')
DISPLAY, THUMB = 1200, 400
REPORTS = os.path.join(L.ROOT, 'reports')
BATCH = 25
SAVE_EVERY = 20          # seconds between progress saves (the store is rewritten in full, so not after every batch)
UA = 'VelmachCatalogImporter/1.0 (+https://www.velmachaerospace.com)'
MAX_BYTES = 30 * 1024 * 1024

ALIASES = {
    'documentSource': ['documentsource', 'sourcedocument'],
    'importKey': ['importkey'],
    'title': ['title', 'name', 'productname', 'product'],
    'partNumber': ['partnumber', 'pn', 'part', 'partno', 'sku', 'mpn'],
    'brand': ['brand', 'manufacturer', 'mfr', 'make'],
    'categoryParent': ['categoryparent', 'category', 'parentcategory', 'maincategory'],
    'categoryChild': ['categorychild', 'subcategory', 'childcategory'],
    'shortDescription': ['shortdescription', 'summary', 'short'],
    'description': ['description', 'longdescription', 'descriptionhtml', 'details'],
    'specifications': ['specifications', 'specs', 'specification'],
    'images': ['images', 'image', 'imageurls', 'imageurl', 'photos'],
    'documents': ['documents', 'docs', 'pdfs', 'datasheets'],
    'compatibleAircraft': ['compatibleaircraft', 'aircraft', 'fits', 'compatibility'],
    'condition': ['condition'],
    'slug': ['slug'],
    'sample': ['sample'],
    'sourceUrl': ['sourceurl', 'source', 'url', 'producturl', 'originalurl'],
}
PRICE_RE = re.compile(r'price|cost|msrp|rrp|amount|currency', re.I)
FIELD_OF = {a: f for f, names in ALIASES.items() for a in names}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


class Log:
    def __init__(self, source):
        os.makedirs(os.path.dirname(ERRLOG), exist_ok=True)
        self.f = open(ERRLOG, 'a', encoding='utf-8')
        self.count = 0
        self.f.write(f'\n=== {now_iso()} import {source} ===\n')

    def error(self, row, pn, msg):
        self.count += 1
        self.last = msg
        line = f'row {row}' + (f' ({pn})' if pn else '') + f': {msg}'
        self.f.write(line + '\n'); self.f.flush()
        print('  ! ' + line)

    def close(self):
        self.f.write(f'=== {self.count} problem(s) ===\n'); self.f.close()


# ---------- reading the input ----------

def read_rows(path):
    if path.lower().endswith('.json'):
        data = json.load(open(path, encoding='utf-8-sig'))
        if not isinstance(data, list):
            raise SystemExit(f'{path}: expected a JSON array of products')
        rows = data
    else:
        with open(path, encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
    out, ignored = [], set()
    for r in rows:
        row = {}
        for k, v in (r or {}).items():
            f = FIELD_OF.get(re.sub(r'[^a-z]', '', str(k or '').lower()))
            if f:
                row[f] = v
            elif k and PRICE_RE.search(str(k)):
                ignored.add(str(k))              # prices are never imported or shown
        out.append(row)
    return out, sorted(ignored)


def split_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [x for x in value if x not in (None, '')]
    return [x.strip() for x in re.split(r'\s*[|\n]\s*', str(value)) if x.strip()]


def parse_specs(value):
    if value in (None, ''):
        return None
    if isinstance(value, dict):
        return [{'name': str(k).strip(), 'value': str(v).strip()} for k, v in value.items() if str(k).strip()]
    if isinstance(value, list):
        items = value
    else:
        text = str(value).strip()
        if text[:1] in '{[':
            try:
                return parse_specs(json.loads(text))
            except ValueError:
                pass
        items = split_list(text)
    out = []
    for it in items:
        if isinstance(it, dict):
            name, val = it.get('name') or it.get('key') or it.get('k'), it.get('value') or it.get('v')
        else:
            name, _, val = str(it).partition(':')
        if str(name or '').strip() and str(val or '').strip():
            out.append({'name': str(name).strip(), 'value': str(val).strip()})
    return out


def parse_docs(value):
    out = []
    for it in (value if isinstance(value, list) else split_list(value)):
        if isinstance(it, dict):
            label, src = it.get('label') or it.get('name') or '', it.get('url') or it.get('src') or ''
        else:
            label, sep, src = str(it).partition('::')
            if not sep:
                label, src = '', label
        src = src.strip()
        if src:
            out.append({'label': label.strip() or os.path.splitext(os.path.basename(src.split('?')[0]))[0].replace('-', ' ').replace('_', ' ').strip() or 'Document', 'src': src})
    return out


def parse_condition(value):
    v = str(value or '').strip().lower()
    if not v:
        return None
    if v in ('new', 'ne', 'fn', 'factory new', 'brand new'):
        return 'New'
    if v in ('used', 'serviceable', 'sv', 'oh', 'overhauled', 'ar', 'as removed', 'repaired', 'rp', 'refurbished'):
        return 'Used'
    return 'invalid'


def truthy(v):
    return str(v or '').strip().lower() in ('1', 'true', 'yes', 'y', 'x')


# ---------- fetching and converting files ----------

class RateLimit:
    """At most one request every `interval` seconds across all download threads."""
    def __init__(self, per_second):
        self.interval = 1.0 / per_second if per_second > 0 else 0
        self.lock, self.next = threading.Lock(), 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            if self.next > now:
                time.sleep(self.next - now)
            self.next = max(now, self.next) + self.interval


LIMIT = RateLimit(1.0)


def fetch(src, base_dir):
    """Bytes of a URL (rate limited, with retries) or a local file (relative to the input file, then the site root)."""
    if re.match(r'^https?://', src, re.I):
        delay = 2
        for attempt in range(4):
            LIMIT.wait()
            try:
                req = urllib.request.Request(src, headers={'User-Agent': UA, 'Accept': '*/*'})
                with urllib.request.urlopen(req, timeout=40) as r:
                    data = r.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError('file larger than 30 MB')
                return data
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                    wait = int(e.headers.get('Retry-After') or delay) if str(e.headers.get('Retry-After') or '').isdigit() else delay
                    time.sleep(min(wait, 60)); delay *= 2; continue
                raise ValueError(f'HTTP {e.code}')
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if attempt < 3:
                    time.sleep(delay); delay *= 2; continue
                raise ValueError(f'download failed ({getattr(e, "reason", e)})')
    for base in (base_dir, L.ROOT):
        p = os.path.normpath(os.path.join(base, src))
        if os.path.isfile(p):
            return open(p, 'rb').read()
    raise ValueError('file not found')


def make_images(data, folder, name):
    """<folder>/<name>.jpg at the original resolution (a JPEG source is kept byte for byte), plus
    <folder>/display/<name>.webp (1200 px) and <folder>/thumbs/<name>.webp (400 px). Returns their site paths."""
    try:
        im = Image.open(io.BytesIO(data))
        fmt = im.format
        im.seek(0)
        im = ImageOps.exif_transpose(im)
    except Exception:
        raise ValueError('not a readable image (JPEG, PNG, WebP, GIF or TIFF expected)')
    os.makedirs(os.path.join(folder, 'display'), exist_ok=True)
    os.makedirs(os.path.join(folder, 'thumbs'), exist_ok=True)
    original = os.path.join(folder, name + '.jpg')
    if fmt == 'JPEG':
        open(original, 'wb').write(data)
    else:                                         # PNG, WebP, GIF, TIFF: saved as JPEG on white
        flat = im.convert('RGBA')
        bg = Image.new('RGB', flat.size, (255, 255, 255)); bg.paste(flat, mask=flat.split()[3])
        bg.save(original, 'JPEG', quality=95, subsampling=0)
    has_alpha = im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info)
    work = im.convert('RGBA' if has_alpha else 'RGB')
    out = {'original': L.rel(original)}
    for key, size, sub in (('large', DISPLAY, 'display'), ('thumb', THUMB, 'thumbs')):
        copy = work.copy()
        copy.thumbnail((size, size), Image.LANCZOS)
        path = os.path.join(folder, sub, name + '.webp')
        copy.save(path, 'WEBP', quality=82, method=4)
        out[key] = L.rel(path)
    return out


def store_doc(data, folder, label, src):
    if not data.startswith(b'%PDF'):
        raise ValueError('not a PDF file')
    base = L.slugify(os.path.splitext(os.path.basename(src.split('?')[0]))[0] or label, 60) or 'document'
    path = os.path.join(folder, 'docs', f'{base}-{L.short_hash(src, 6)}.pdf')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        open(path, 'wb').write(data)
    return L.rel(path)


# ---------- the import ----------

class Importer:
    def __init__(self, args):
        self.args = args
        self.cats = L.CategoryMap(L.load_categories())
        self.aircraft = L.AircraftMap(L.load_aircraft())
        self.brands = {L.norm_key(b['name']): b for b in L.load_brands()}
        self.store = L.load_store()
        self.slugs = {r['slug']: k for k, r in self.store.items()}
        self.reserved, self.only = {}, ''
        self.dirs = {r.get('pnDir'): k for k, r in self.store.items() if r.get('pnDir')}
        self.stats = {'added': 0, 'updated': 0, 'unchanged': 0, 'skipped': 0, 'images': 0}
        self.touched, self.img_errors, self.problems, self.other_category = {}, {}, [], 0
        global LIMIT
        LIMIT = RateLimit(args.rate)

    def folder_for(self, key, f):
        """images/products/<part-number>/ (with -<brand> added when another brand already uses that part number)."""
        rec = self.store.get(key)
        if rec and rec.get('pnDir'):
            return rec['pnDir']
        base = L.safe_part_number(f['partNumber']) if f['partNumber'] else L.slugify(f['title'], 70) or 'product'
        for cand in [base] + ([f"{base}-{f['brandSlug']}"] if f['brandSlug'] else []) + [f'{base}-{n}' for n in range(2, 100)]:
            if self.dirs.get(cand) in (None, key):
                self.dirs[cand] = key
                return cand
        raise ValueError('could not find a free image folder')

    def brand(self, name):
        if not str(name or '').strip():
            return {'slug': '', 'name': ''}           # no brand stated in the source
        k = L.norm_key(name)
        b = self.brands.get(k)
        if not b:
            for r in self.store.values():            # same brand already imported under another spelling
                if L.norm_key(r['brand']) == k:
                    b = {'slug': r['brandSlug'], 'name': r['brand']}; break
        if not b:
            b = {'slug': L.slugify(name, 60), 'name': ' '.join(str(name).split())}
            self.brands[k] = b
        return b

    def slug_for(self, key, f):
        """The product's URL slug: kept once assigned; a new product reserves one as soon as its row is read."""
        if key in self.store:
            return self.store[key]['slug']
        if key not in self.reserved:
            slug = self.unique_slug(f.get('slugWanted') or f"{f['title']} {f['partNumber']}", key, f['brandSlug'])
            self.reserved[key] = slug
            self.slugs[slug] = key
        return self.reserved[key]

    def unique_slug(self, want, key, brand_slug):
        base = L.slugify(want) or 'product'
        for cand in [base, f'{base}-{brand_slug}'] + [f'{base}-{n}' for n in range(2, 500)]:
            if self.slugs.get(cand) in (None, key):
                return cand
        raise ValueError('could not find a free URL slug')

    def parse(self, row, n, log):
        """Row -> (key, fields) with only the columns that were filled in, or None when the row is skipped."""
        title, pn, brand = (str(row.get(f) or '').strip() for f in ('title', 'partNumber', 'brand'))
        if not title:
            log.error(n, pn, 'missing title'); return None
        key = L.product_key(pn, brand) if pn else 'name:' + L.norm_key(title) + '|' + L.norm_key(brand)
        if str(row.get('importKey') or '').strip():
            key = 'doc:' + str(row['importKey']).strip()     # the id the extraction gave this product (scripts/extract-documents.py)
        existing = self.store.get(key)
        parent, child = row.get('categoryParent'), row.get('categoryChild')
        if not existing and not str(parent or '').strip():
            log.error(n, pn, 'missing categoryParent'); return None
        if str(parent or '').strip():
            p, c, err = self.cats.resolve(parent or '', child)
            if err:
                log.error(n, pn, err); return None
        else:
            p, c = existing['categoryParent'], existing['categoryChild']
            if str(child or '').strip():
                p, c, err = self.cats.resolve(p, child)
                if err:
                    log.error(n, pn, err); return None
        if self.only and p != self.only:
            self.other_category += 1
            return 'other'
        b = self.brand(brand)
        f = {'title': ' '.join(title.split()), 'partNumber': pn, 'brand': b['name'], 'brandSlug': b['slug'], 'categoryParent': p, 'categoryChild': c}
        if str(row.get('shortDescription') or '').strip():
            f['shortDescription'] = ' '.join(L.strip_html(row['shortDescription']).split())
        if str(row.get('description') or '').strip():
            f['description'] = L.sanitize_html(row['description'])
        specs = parse_specs(row.get('specifications'))
        if specs is not None:
            f['specifications'] = specs
        if split_list(row.get('images')):
            f['imageSrc'] = split_list(row.get('images'))
        docs = parse_docs(row.get('documents'))
        if docs:
            f['documentSrc'] = docs
        ac = split_list(row.get('compatibleAircraft'))
        if ac:
            ids = []
            for a in ac:
                aid = self.aircraft.resolve(a)
                if aid:
                    ids.append(aid)
                else:
                    log.error(n, pn, f'unknown aircraft "{a}" (add it to data/aircraft.js); ignored')
            f['compatibleAircraft'] = sorted(set(ids))
        cond = parse_condition(row.get('condition'))
        if cond == 'invalid':
            log.error(n, pn, f'condition "{row.get("condition")}" is not New or Used; stored as New'); cond = 'New'
        if cond:
            f['condition'] = cond
        if 'sample' in row and str(row.get('sample') or '').strip():
            f['sample'] = truthy(row.get('sample'))
        if str(row.get('slug') or '').strip():
            f['slugWanted'] = row['slug']
        if str(row.get('sourceUrl') or '').strip():
            f['sourceUrl'] = str(row['sourceUrl']).strip()
        if str(row.get('documentSource') or '').strip():
            f['documentSource'] = str(row['documentSource']).strip()
        return key, f

    def run_files(self, jobs, log):
        """jobs: list of (row, pn, kind, src, folder, extra). Downloads/converts in parallel. Returns {(folder, src, kind): result}."""
        results = {}
        if not jobs:
            return results

        def work(job):
            n, pn, kind, src, folder, extra = job
            try:
                data = fetch(src, self.base_dir)
                return job, (make_images(data, folder, extra) if kind == 'img' else store_doc(data, folder, extra, src)), None
            except Exception as e:
                return job, None, str(e)

        with cf.ThreadPoolExecutor(max_workers=self.args.workers) as ex:
            for job, res, err in ex.map(work, jobs):
                n, pn, kind, src, folder, extra = job
                if err:
                    log.error(n, pn, f'{"image" if kind == "img" else "document"} {src}: {err}')
                    self.problems.append((n, pn, f'{"image" if kind == "img" else "document"} {src}: {err}'))
                    if kind == 'img':
                        self.img_errors.setdefault(pn, []).append(err)
                else:
                    results[(folder, src, kind)] = res
                    if kind == 'img':
                        self.stats['images'] += 1
        return results

    def commit(self, key, f, files, n, log):
        old = self.store.get(key)
        rec = dict(old) if old else {'key': key, 'id': L.product_id(key), 'shortDescription': '', 'description': '', 'specifications': [],
                                     'images': [], 'documents': [], 'compatibleAircraft': [], 'condition': 'New', 'sample': False}
        if not old:
            rec['slug'] = self.slug_for(key, f)
        rec['pnDir'] = self.folder_for(key, f)
        folder = os.path.join(L.PRODUCT_DIR, rec['pnDir'])
        for k in ('title', 'partNumber', 'brand', 'brandSlug', 'categoryParent', 'categoryChild', 'shortDescription', 'description',
                  'specifications', 'compatibleAircraft', 'condition', 'sample', 'sourceUrl', 'documentSource'):
            if k in f:
                rec[k] = f[k]
        if 'imageSrc' in f:
            prev = {i['src']: i for i in rec.get('images', [])}
            imgs = []
            for src in f['imageSrc']:
                got = files.get((folder, src, 'img')) or (prev.get(src) if self.args.skip_images else None)
                if got:
                    imgs.append({'src': src, 'original': got.get('original', got['large']), 'thumb': got['thumb'], 'large': got['large']})
            if imgs or not f['imageSrc'] or self.args.skip_images:
                rec['images'] = imgs
            # remove image files that no product image points to any more
            keep = {os.path.normpath(os.path.join(L.ROOT, p)) for i in rec['images'] for p in (i['original'], i['thumb'], i['large'])}
            for sub in ('', 'display', 'thumbs'):
                d = os.path.join(folder, sub)
                if os.path.isdir(d):
                    for name in os.listdir(d):
                        p = os.path.normpath(os.path.join(d, name))
                        if os.path.isfile(p) and name.endswith(('.jpg', '.webp')) and p not in keep:
                            os.remove(p)
        if 'documentSrc' in f:
            docs = []
            for d in f['documentSrc']:
                if self.args.link_documents and re.match(r'^https?://', d['src'], re.I):
                    docs.append({'label': d['label'], 'src': d['src'], 'url': d['src']})
                else:
                    got = files.get((folder, d['src'], 'doc'))
                    if got:
                        docs.append({'label': d['label'], 'src': d['src'], 'url': got})
            rec['documents'] = docs
        self.touched[key] = n
        same = old is not None and {k: v for k, v in rec.items() if k not in ('updatedAt',)} == {k: v for k, v in old.items() if k not in ('updatedAt',)}
        if same:
            self.stats['unchanged'] += 1; return
        stamp = now_iso()
        rec.setdefault('createdAt', stamp)
        rec['updatedAt'] = stamp
        self.store[key] = rec
        self.slugs[rec['slug']] = key
        self.stats['updated' if old else 'added'] += 1

    def needs_file(self, key, slug, src, kind):
        """False when this exact document is already stored on disk (so a re-run or resume does not download it again)."""
        old = self.store.get(key)
        if not old:
            return True
        for it in old.get('documents', []):
            if it.get('src') == src:
                return not (re.match(r'^https?://', it['url']) or os.path.exists(os.path.join(L.ROOT, it['url'])))
        return True

    def images_current(self, key, srcs, folder):
        """True when the product already has exactly these image sources, in this order, stored in this folder."""
        old = self.store.get(key)
        if not old or [i['src'] for i in old.get('images', [])] != srcs:
            return False
        return all(i.get('original', '').startswith(L.rel(folder) + '/') and all(os.path.exists(os.path.join(L.ROOT, i[k])) for k in ('original', 'thumb', 'large'))
                   for i in old['images'])

    def run(self, path):
        self.base_dir = os.path.dirname(os.path.abspath(path))
        rows, self.ignored_cols = read_rows(path)
        self.only = ''
        if self.args.category:
            p, _, err = self.cats.resolve(self.args.category, '')
            if err:
                raise SystemExit(f'--category: {err}')
            self.only = p
        digest = hashlib.sha256(open(path, 'rb').read()).hexdigest() + ('|' + self.only if self.only else '')
        start = 0
        if os.path.exists(STATE) and not self.args.restart:
            st = json.load(open(STATE, encoding='utf-8'))
            if st.get('sha256') == digest and st.get('input') == L.rel(os.path.abspath(path)):
                start = st.get('done', 0)
                print(f'Resuming {L.rel(os.path.abspath(path))} at row {start + 2} ({start} of {len(rows)} rows already done). Use --restart to start over.')
        log = Log(L.rel(os.path.abspath(path)))
        last_save = time.time()
        print(f'Importing {len(rows) - start} of {len(rows)} rows from {L.rel(os.path.abspath(path))}')
        try:
            for b0 in range(start, len(rows), BATCH):
                batch = rows[b0:b0 + BATCH]
                parsed, jobs = [], []
                for i, row in enumerate(batch):
                    n = b0 + i + 2                      # spreadsheet row number (row 1 is the header)
                    try:
                        got = self.parse(row, n, log)
                    except Exception as e:
                        log.error(n, row.get('partNumber'), f'could not read row: {e}'); got = None
                    if got == 'other':
                        continue                         # another top-level category: not in this batch
                    if not got:
                        self.stats['skipped'] += 1
                        self.problems.append((n, row.get('partNumber'), 'skipped: ' + getattr(log, 'last', 'see reports/import-errors.log')))
                        continue
                    key, f = got
                    slug = self.slug_for(key, f)
                    pn_dir = self.folder_for(key, f)
                    folder = os.path.join(L.PRODUCT_DIR, pn_dir)
                    if not self.args.skip_images and f.get('imageSrc'):
                        if self.images_current(key, f['imageSrc'], folder):
                            for prev in self.store[key]['images']:
                                parsed.append(('cached', (folder, prev['src'], 'img'), prev))
                        else:
                            for i, src in enumerate(f['imageSrc'], 1):   # numbered in the order the source lists them
                                jobs.append((n, f['partNumber'], 'img', src, folder, f'{pn_dir}-{i}'))
                    for d in f.get('documentSrc', []):
                        if self.args.link_documents and re.match(r'^https?://', d['src'], re.I):
                            continue
                        if self.needs_file(key, slug, d['src'], 'doc'):
                            jobs.append((n, f['partNumber'], 'doc', d['src'], folder, d['label']))
                        else:
                            prev = next(x for x in self.store[key]['documents'] if x['src'] == d['src'])
                            parsed.append(('cached', (folder, d['src'], 'doc'), prev['url']))
                    parsed.append(('row', n, key, f))
                files = self.run_files(jobs, log)
                for item in parsed:
                    if item[0] == 'cached':
                        files[item[1]] = item[2]
                for item in parsed:
                    if item[0] == 'row':
                        _, n, key, f = item
                        try:
                            self.commit(key, f, files, n, log)
                        except Exception as e:
                            log.error(n, f.get('partNumber'), f'could not save: {e}'); self.stats['skipped'] += 1
                done = b0 + len(batch)
                if time.time() - last_save >= SAVE_EVERY or done >= len(rows):
                    # progress is saved together with the store, so a resume never skips rows that were not stored
                    L.save_store(self.store)
                    L.write_if_changed(STATE, json.dumps({'input': L.rel(os.path.abspath(path)), 'sha256': digest, 'done': done}))
                    last_save = time.time()
                    print(f'  {done}/{len(rows)} rows')
        finally:
            log.close()
        if os.path.exists(STATE):
            os.remove(STATE)
        self.reports(path, len(rows))
        s = self.stats
        print(f"Done: {s['added']} added, {s['updated']} updated, {s['unchanged']} unchanged, {s['skipped']} skipped, "
              f"{s['images']} images converted, {log.count} problem(s) logged to {L.rel(ERRLOG)}")

    def reports(self, path, n_rows):
        """reports/missing-images.csv and reports/import-report-<batch>-<date>.md for the rows of this run."""
        os.makedirs(REPORTS, exist_ok=True)
        cats = {p['slug']: p for p in L.load_categories()}
        name = lambda p, c='': (cats[p]['en'] + (' > ' + next((x['en'] for x in cats[p]['children'] if x['slug'] == c), c) if c else '')) if p in cats else p
        recs = [self.store[k] for k in self.touched if k in self.store]
        missing = [r for r in recs if not r.get('images')]
        with open(os.path.join(REPORTS, 'missing-images.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['partNumber', 'brand', 'title', 'category', 'row', 'reason', 'sourceUrl'])
            for r in missing:
                errs = self.img_errors.get(r['partNumber'])
                w.writerow([r['partNumber'], r['brand'], r['title'], name(r['categoryParent'], r['categoryChild']), self.touched[r['key']],
                            'image download failed: ' + '; '.join(errs) if errs else 'no image in the source data', r.get('sourceUrl', '')])
        # per category: rows in this file vs products imported, with and without images
        table = {}
        for r in recs:
            for k in ((r['categoryParent'], ''), (r['categoryParent'], r['categoryChild'])):
                if k[1] == '' or r['categoryChild']:
                    t = table.setdefault(k, [0, 0])
                    t[0] += 1; t[1] += 0 if r.get('images') else 1
        site = {}
        for r in self.store.values():
            site[r['categoryParent']] = site.get(r['categoryParent'], 0) + 1
        batch = self.only or 'all'
        stamp = datetime.date.today().isoformat()
        out = os.path.join(REPORTS, f'import-report-{batch}-{stamp}.md')
        s = self.stats
        lines = [f'# Import report: {name(self.only) if self.only else "all categories"} ({stamp})', '',
                 f'- Input: `{L.rel(os.path.abspath(path))}`, {n_rows} rows' + (f', of which {n_rows - self.other_category} in this category' if self.only else ''),
                 f"- Imported: {s['added']} added, {s['updated']} updated, {s['unchanged']} unchanged; {s['skipped']} rows skipped",
                 f"- Images converted this run: {s['images']}; products without any image: {len(missing)} (reports/missing-images.csv)",
                 f"- Price columns ignored: {', '.join(self.ignored_cols) if self.ignored_cols else 'none in the file'}", '',
                 '## Per category', '', '| Category | Products in this import | Without image | Products on site (top level) |', '|---|---:|---:|---:|']
        for (p, c), (n_ok, n_missing) in sorted(table.items(), key=lambda kv: (name(kv[0][0]), kv[0][1] != '', name(*kv[0]))):
            lines.append(f"| {'&nbsp;&nbsp;' if c else '**'}{name(p, c) if c else name(p)}{'' if c else '**'} | {n_ok} | {n_missing} | {'' if c else site.get(p, 0)} |")
        lines += ['', '## Failed or skipped rows', '']
        lines += [f'- row {n}' + (f' ({pn})' if pn else '') + f': {msg}' for n, pn, msg in sorted(self.problems, key=lambda x: x[0])] or ['None.']
        lines += ['', '## 10 random products to check against their source', '',
                  '| Part number | Brand | Product | Product page | First image | Source |', '|---|---|---|---|---|---|']
        for r in random.sample(recs, min(10, len(recs))):
            img = r['images'][0]['original'] if r.get('images') else '(no image)'
            lines.append(f"| `{r['partNumber']}` | {r['brand']} | {r['title']} | product.dc.html?p={r['slug']} | {img} | {r.get('sourceUrl', '') or r.get('documentSource', '')} |")
        open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
        print(f'Reports: {L.rel(out)}, reports/missing-images.csv')

    def remove_samples(self):
        gone = [k for k, r in self.store.items() if r.get('sample')]
        for k in gone:
            shutil.rmtree(os.path.join(L.ASSETS, self.store[k]['slug']), ignore_errors=True)
            if self.store[k].get('pnDir'):
                shutil.rmtree(os.path.join(L.PRODUCT_DIR, self.store[k]['pnDir']), ignore_errors=True)
            del self.store[k]
        L.save_store(self.store)
        print(f'Removed {len(gone)} sample product(s).')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input', nargs='?', default=os.path.join(L.ROOT, 'data', 'products.csv'), help='CSV or JSON file (default data/products.csv)')
    ap.add_argument('--restart', action='store_true', help='ignore saved progress and start from the first row')
    ap.add_argument('--category', default='', help='import only this top-level category (slug or English name), e.g. pilot-supplies')
    ap.add_argument('--rate', type=float, default=1.0, help='maximum downloads per second (default 1)')
    ap.add_argument('--workers', type=int, default=4, help='images converted at the same time (default 4)')
    ap.add_argument('--skip-images', action='store_true', help='do not download images (keeps images already stored)')
    ap.add_argument('--link-documents', action='store_true', help='keep PDF links instead of storing the files')
    ap.add_argument('--no-build', action='store_true', help='do not run build-catalog.py afterwards')
    ap.add_argument('--remove-samples', action='store_true', help='delete all sample products, then rebuild')
    args = ap.parse_args()
    imp = Importer(args)
    if args.remove_samples:
        imp.remove_samples()
    else:
        if not os.path.exists(args.input):
            raise SystemExit(f'{args.input} not found. Put your products in data/products.csv (see samples/products.sample.csv for the columns).')
        imp.run(args.input)
    if not args.no_build:
        import importlib.util
        spec = importlib.util.spec_from_file_location('build_catalog', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build-catalog.py'))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        mod.build()


if __name__ == '__main__':
    main()
