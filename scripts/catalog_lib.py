"""Shared helpers for the catalogue scripts (import-products.py, build-catalog.py).

The catalogue "database" is data/catalog/products.jsonl: one product per line, keyed by part number + brand.
The site never reads it directly; build-catalog.py turns it into the small JSON files the pages load.
"""
import hashlib, html, json, os, re, tempfile, unicodedata, time
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, 'data', 'catalog')
STORE = os.path.join(CATALOG, 'products.jsonl')
ASSETS = os.path.join(ROOT, 'assets', 'catalog')          # earlier layout (one folder per URL slug); removed with --remove-samples
PRODUCT_DIR = os.path.join(ROOT, 'images', 'products')    # images/products/<part-number>/<part-number>-1.jpg ...


def rel(path):
    """Site-relative path with forward slashes (what the pages use in src/href)."""
    return os.path.relpath(path, ROOT).replace(os.sep, '/')


def slugify(text, max_len=80):
    s = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('ascii').lower().replace('&', ' ')
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    if len(s) > max_len:
        s = s[:max_len].rsplit('-', 1)[0] or s[:max_len]
    return s


def norm_key(text):
    """Part numbers and brands compare without case, spaces or punctuation."""
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(text)).lower())


def product_key(part_number, brand):
    return norm_key(part_number) + '|' + norm_key(brand)


def safe_part_number(pn):
    """Part number as a folder and file name: characters Windows and URLs cannot hold become '-', case is kept."""
    s = re.sub(r'[\\/:*?"<>|#%&{}$!\'@+`=\s]+', '-', str(pn).strip()).strip('-.')
    return s[:80] or 'part'


def product_id(key):
    return 'vm' + hashlib.sha1(key.encode('utf-8')).hexdigest()[:12]


def short_hash(text, n=10):
    return hashlib.sha1(str(text).encode('utf-8')).hexdigest()[:n]


# ---------- reading the site's JS data files ----------

def _js_value(path, var):
    """Parse `window.<var> = <literal>;` from a site data file. Bare object keys are quoted so json can read it."""
    src = open(path, encoding='utf-8').read()
    m = re.search(r'window\.' + re.escape(var) + r'\s*=\s*', src)
    if not m:
        raise SystemExit(f'{rel(path)}: window.{var} not found')
    body = src[m.end():].strip()
    body = body[:body.rindex(';')] if body.rstrip().endswith(';') else body
    out, i, in_str = [], 0, None
    while i < len(body):                       # quote bare keys outside strings, drop // comments
        ch = body[i]
        if in_str:
            out.append(ch)
            if ch == '\\':
                out.append(body[i + 1]); i += 1
            elif ch == in_str:
                in_str = None
        elif ch in '"\'':
            in_str = ch; out.append('"' if ch == "'" else ch)
        elif body.startswith('//', i):
            while i < len(body) and body[i] != '\n':
                i += 1
            continue
        else:
            km = re.match(r'([{,]\s*)([A-Za-z_]\w*)(\s*:)', body[i:])
            if km and ch in '{,':
                out.append(km.group(1) + '"' + km.group(2) + '"' + km.group(3)); i += km.end(); continue
            out.append(ch)
        i += 1
    text = re.sub(r',(\s*[\]}])', r'\1', ''.join(out))   # trailing commas
    return json.loads(text)


def load_categories():
    return _js_value(os.path.join(ROOT, 'data', 'categories.js'), 'VM_CATS')


def load_aircraft():
    return _js_value(os.path.join(ROOT, 'data', 'aircraft.js'), 'VM_AIRCRAFT')


def load_brands():
    path = os.path.join(ROOT, 'data', 'brands.js')
    return _js_value(path, 'VM_BRANDS') if os.path.exists(path) else []


def aircraft_id(make, model):
    """Same id as VM.acId() in js/vm-core.js: '<make-slug>/<model-slug>'."""
    s = lambda x: re.sub(r'[^a-z0-9]+', '-', str(x).lower().replace('&', ' ')).strip('-')
    return s(make) + '/' + s(model)


class CategoryMap:
    """Resolves categoryParent / categoryChild given as slug or English name."""

    def __init__(self, cats):
        self.cats = cats
        self.parent = {}
        self.child = {}
        for p in cats:
            for k in (p['slug'], norm_key(p['en'])):
                self.parent[k] = p
            for c in p['children']:
                for k in (c['slug'], norm_key(c['en'])):
                    self.child[(p['slug'], k)] = c

    def resolve(self, parent, child):
        p = self.parent.get(str(parent).strip()) or self.parent.get(norm_key(parent))
        if not p:
            return None, None, f'unknown categoryParent "{parent}"'
        if not str(child or '').strip():
            return p['slug'], '', None
        c = self.child.get((p['slug'], str(child).strip())) or self.child.get((p['slug'], norm_key(child)))
        if not c:
            return None, None, f'unknown categoryChild "{child}" in {p["slug"]}'
        return p['slug'], c['slug'], None


class AircraftMap:
    """Resolves compatibleAircraft entries given as ids ("boeing/737-ng") or names ("Boeing 737 NG")."""

    def __init__(self, makes):
        self.ids = {}
        for m in makes:
            for model in m['models']:
                aid = aircraft_id(m['make'], model)
                self.ids[aid] = aid
                self.ids[norm_key(m['make'] + ' ' + model)] = aid

    def resolve(self, value):
        v = str(value).strip()
        return self.ids.get(v.lower()) or self.ids.get(norm_key(v))


# ---------- product description HTML ----------

ALLOWED = {'p', 'br', 'ul', 'ol', 'li', 'strong', 'b', 'em', 'i', 'u', 'h3', 'h4', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'a', 'span', 'sup', 'sub', 'blockquote'}
VOID = {'br'}
BLOCK = {'p', 'ul', 'ol', 'table', 'h3', 'h4', 'blockquote'}
DROP_CONTENT = {'script', 'style', 'iframe', 'object', 'embed', 'noscript', 'template', 'svg', 'math', 'form'}


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.stack, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT:
            self.skip += 1; return
        if self.skip or tag not in ALLOWED:
            return
        extra = ''
        if tag == 'a':
            href = dict(attrs).get('href') or ''
            if not re.match(r'^(https?:|mailto:)', href.strip(), re.I):
                return
            extra = f' href="{html.escape(href.strip(), quote=True)}" target="_blank" rel="noopener nofollow"'
        if tag in ('td', 'th'):
            span = dict(attrs).get('colspan')
            if span and span.isdigit():
                extra = f' colspan="{span}"'
        # close implicitly ended elements the way browsers do (<li>a<li>b, <p>text<ul>...)
        if tag in BLOCK:
            self._close_open('p', ())
        if tag == 'li':
            self._close_open('li', ('ul', 'ol'))
        elif tag == 'tr':
            self._close_open('tr', ('table', 'thead', 'tbody'))
        elif tag in ('td', 'th'):
            self._close_open('td', ('tr',)); self._close_open('th', ('tr',))
        self.out.append(f'<{tag}{extra}>')
        if tag not in VOID:
            self.stack.append(tag)

    def _close_open(self, tag, scope):
        """Close `tag` if it is open inside the innermost `scope` element (or anywhere when scope is empty)."""
        for j in range(len(self.stack) - 1, -1, -1):
            if self.stack[j] in scope:
                return
            if self.stack[j] == tag:
                while len(self.stack) > j:
                    self.out.append(f'</{self.stack.pop()}>')
                return

    def handle_endtag(self, tag):
        if tag in DROP_CONTENT:
            self.skip = max(0, self.skip - 1); return
        if self.skip or tag not in self.stack:
            return
        while self.stack:                       # close anything left open inside it
            t = self.stack.pop()
            self.out.append(f'</{t}>')
            if t == tag:
                break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(html.escape(data, quote=False))


def sanitize_html(text):
    """Keeps a small set of formatting tags; scripts, styles, event handlers and other attributes are removed.
    Plain text (no tags) is wrapped in paragraphs, one per blank-line-separated block."""
    text = str(text or '').strip()
    if not text:
        return ''
    if not re.search(r'<[a-zA-Z/]', text):
        blocks = [b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]
        return ''.join('<p>' + html.escape(b).replace('\n', '<br>') + '</p>' for b in blocks)
    s = _Sanitizer()
    s.feed(text); s.close()
    s.out.extend(f'</{t}>' for t in reversed(s.stack))
    return ''.join(s.out).strip()


def strip_html(text):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', str(text or '')))).strip()


# ---------- files ----------

def write_file(path, data):
    """Atomic write of bytes."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix='.tmp-')
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
    # Windows: antivirus or an editor's file watcher can hold a file for a moment; retry before giving up
    for attempt in range(8):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 7:
                os.remove(tmp)
                raise
            time.sleep(0.25 * (attempt + 1))


class Manifest:
    """Content hashes of the files a build wrote, so the next build can skip unchanged files without opening them
    (opening tens of thousands of files is slow on Windows with antivirus scanning)."""

    def __init__(self, path, force=False):
        self.path = path
        try:
            self.old = {} if force else json.load(open(path, encoding='utf-8'))
        except (OSError, ValueError):
            self.old = {}
        self.new = {}

    def put(self, path, text):
        """Write path unless the manifest says it already holds this content. Returns True when written."""
        data = text.encode('utf-8')
        key = os.path.relpath(path, ROOT).replace(os.sep, '/')
        h = hashlib.sha1(data).hexdigest()
        self.new[key] = h
        if self.old.get(key) == h and os.path.exists(path):
            return False
        write_file(path, data)
        return True

    def save(self):
        write_if_changed(self.path, json.dumps(self.new, separators=(',', ':'), sort_keys=True))


def write_if_changed(path, text):
    """Atomic write; leaves the file (and its timestamp) alone when the content is the same. Returns True if written."""
    data = text.encode('utf-8')
    if os.path.exists(path):
        with open(path, 'rb') as f:
            if f.read() == data:
                return False
    write_file(path, data)
    return True


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def load_store():
    """key -> product record."""
    store = {}
    if os.path.exists(STORE):
        with open(STORE, encoding='utf-8') as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        rec = json.loads(line)
                    except ValueError as e:
                        raise SystemExit(f'{rel(STORE)} line {n}: {e}')
                    store[rec['key']] = rec
    return store


def save_store(store):
    lines = [dumps(store[k]) for k in sorted(store)]
    write_file(STORE, ('\n'.join(lines) + ('\n' if lines else '')).encode('utf-8'))
