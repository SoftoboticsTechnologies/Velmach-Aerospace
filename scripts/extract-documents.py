"""Dry run: read every document in "assets/velmach product", extract products, merge them and write reports.

python scripts/extract-documents.py [--src "assets/velmach product"]

Writes (nothing on the site changes):
  data/velmach-products.json        merged products, each with its sources (file + sheet/row, page)
  data/velmach-staging/images/      images taken out of the documents, named by product key
  reports/extraction-summary.md     totals per category and per source file, 10 random products
  reports/conflicts.md              fields where two documents disagree (both values kept)
  reports/new-categories.md         document categories that do not fit the existing tree
  reports/missing-images.csv        products with no image from the documents, and why
  reports/web-images.csv            images found on the web (header only until a web lookup is approved)

Rules: values come only from the documents. Brand is set only when a document states it (a brand column, a brand
heading, or a trademark mark such as "3M(TM)" in a product heading). Prices, quantities, lead times, serial numbers
and certifier names are not extracted. An image is attached only when exactly one product sits next to it.
"""
import argparse, collections, csv, hashlib, io, json, os, pickle, random, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import catalog_lib as L
import importlib.util
_spec = importlib.util.spec_from_file_location('mapper', os.path.join(ROOT, 'scripts', 'map-old-categories.py'))
MAP = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(MAP)

for extra in sys.argv:          # optional library folders (openpyxl, python-docx, rapidocr) given with --lib
    pass

STAGE = os.path.join(ROOT, 'data', 'velmach-staging', 'images')
REPORTS = os.path.join(ROOT, 'reports')
CTRL = re.compile(r'[\x00-\x08\x0b-\x1f\x7f]')
PRICE = re.compile(r'price|cost|amount|currency|usd|aed|\$', re.I)
SKIP_COLS = re.compile(r'qty|quantity|quanity|serial|s/n|lead time|% change|bin qty|cert date|certified by|source', re.I)

# file -> how it is read. Kinds: velmach (Velmach's own lists), stock (other companies' stock / planning lists),
# catalog (distributor / manufacturer catalogs), suppliers (approved-supplier lists: no products), profile, links,
# duplicate (an identical or image-only copy of another file).
FILES = {
    'VELMACH AEROSPACE Master Parts Inventory 06-05-2026.xlsx': 'velmach',
    'PRODUCT LIST.xlsx': 'velmach',
    'PRODUCT LIST WITH FULL DETAILS.pdf': 'velmach',
    'PRODUCT LIST.xlsx 2.xlsx': 'velmach',
    'PRODUCT LIST.xlsx 2 (1).xlsx': 'duplicate:PRODUCT LIST.xlsx 2.xlsx',
    'PRODUCTLIST.pdf': 'duplicate:Consumables Catalog.pdf (image-only copy)',
    'PRODUCTLIST (1).pdf': 'duplicate:Consumables Catalog.pdf (image-only copy)',
    'BATTERIES.pdf': 'duplicate:Battery Catalog.pdf (image-only copy)',
    'REGIONAL AVIONICS STOCK INVENTORY.xlsx': 'stock',
    'AeroDirect_Rotable_Parts.xlsx': 'stock',
    '2026-10-lead-time-updates.xlsx': 'stock',
    '2026-10-seasonal-parts.xlsx': 'stock',
    'Aviall Product Catalog & Source Book.pdf': 'apart',          # old location; the book now sits in its own folder
    'Aviall Product Catalog & Source Book/Aviall Product Catalog & Source Book.pdf': 'aviall-ocr',
    'Aviall-Industry-Maint-Catalog-2019.pdf': 'apart',
    'aviall-helicopter-product-catalog.pdf': 'apart',
    'Celeste-All-Products-Booklet--Rev-16--Aviall-NORTH-AMERICA.pdf': 'apart',
    'All-Products-Booklet-Rev-17-Aviall-NORTH-AMERICA.pdf': 'apart',
    'A220-Program-Approved-Supplier-List.pdf': 'suppliers',
    'AW Approved Supplier List_raw_06_02_26.pdf': 'suppliers',
    'mastlist.pdf': 'suppliers',
    'Profile-Aero Enterprises.pdf': 'profile',
    'Aeroservices - Core Capability.pdf': 'profile',
    'https.docx': 'links',
}
PRIORITY = {'velmach': 0, 'catalog': 1, 'aviall-ocr': 2}
# page pictures of the Aviall Source Book: its part-number column uses a font without text, so those cells are read from
# the picture of the page (OCR). Other folders of page pictures are copies of PDFs that are read from their text.
OCR_PAGES = {'Aviall Product Catalog & Source Book/Aviall Product Catalog & Source Book.pdf': 'Aviall IMG Product Catalog & Source Book_'}
PAGE_PICTURE_DIRS = ('Aviall IMG Product Catalog & Source Book_/', 'avaiation documents IMAGES/')
# family photos (approved 2026-10-14): a catalog photo beside a table of related products is used for each of them and
# marked "family photo"; an exact photo found later (scripts/verify-pn-images.py) replaces it. VELMACH_FAMILY_PHOTOS=0 turns it off.
FAMILY_PHOTOS = os.environ.get('VELMACH_FAMILY_PHOTOS', '1') == '1'
# a variant description that is only a size or pack ("400 ML", "1 gal can", "Case: 12 bottles", "1 in x 36 yd")
PACK = re.compile(r'^(?:[\d.,/\s\-x×]*(?:fl\.?\s?oz|oz|ml|cc|l|lt|ltr|lit(?:er|re)s?|gal(?:lon)?s?|qt|quarts?|pt|pints?|lbs?|kg|g|gm|grams?'
                  r'|in(?:ch(?:es)?)?|"|mm|cm|m|yds?|ft)\b\.?|[\s,;:()\-x×/]+|\d+(?:\.\d+)?|cartridges?|tubes?|cans?|aerosols?|kits?|drums?|pails?'
                  r'|bottles?|jars?|syringes?|sachets?|totes?|case|each|ea|packs?|bags?|box(?:es)?|rolls?|spray|sprays|squeeze|caps?|pouch(?:es)?'
                  r'|aerosol\s+can|wide|long|width|length|size|pump|trigger|semkit|pk|pkg|unit|units|bulk|gun|spool)+$', re.I)
CACHE = os.path.join(ROOT, 'data', 'velmach-staging', 'cache')

HEADER_SYNONYMS = {
    'pn': ['part #', 'part#', 'part number', 'part no', 'part no.', 'p/n', 'item', 'part', 'pn'],
    'alt': ['alt p/n', 'alternate part #', 'alternate part', 'alt pn', 'alternate p/n'],
    'title': ['product name', 'name'],
    'desc': ['description'],
    'cond': ['condition'],
    'aircraft': ['aircraft type', 'aircrafttype', 'a/c model', 'aircraft'],
    'cat': ['category'],
    'trace8130': ['8130', 'traceability'],
    'brand': ['brand', 'manufacturer', 'mfr'],
}
COND = {'NE': 'New', 'NS': 'New', 'FN': 'New', 'NEW': 'New', 'IN': 'Used', 'SV': 'Used', 'OH': 'Used', 'RP': 'Used', 'AR': 'Used',
        'USED': 'Used', 'SERVICEABLE': 'Used', 'OVERHAULED': 'Used', 'REPAIRED': 'Used', 'INSPECTED': 'Used', 'TESTED': 'Used'}
COND_NAME = {'NE': 'New', 'NS': 'New surplus', 'FN': 'Factory new', 'IN': 'Inspected', 'SV': 'Serviceable', 'OH': 'Overhauled',
             'RP': 'Repaired', 'AR': 'As removed'}


def clean(v):
    if v is None:
        return ''
    s = re.sub(r'[\x80-\x9f]', '', CTRL.sub('', str(v))).replace('\u019f', 'ti').replace('\xa0', ' ').replace('‐', '-').replace('‑', '-').replace('�', '')
    s = re.sub(r'\s+', ' ', s).strip()
    return '' if s.lower() in ('none', 'n/a', 'na', '-', '--') else s


class Collector:
    def __init__(self):
        self.rows, self.files, self.notes = [], collections.OrderedDict(), collections.defaultdict(list)

    def add(self, file, loc, kind, **f):
        f = {k: v for k, v in f.items() if v not in (None, '', [], {})}
        if not (f.get('pn') or f.get('title')):
            return
        f.update(file=file, loc=loc, kind=kind)
        self.rows.append(f)
        self.files.setdefault(file, collections.Counter())['rows'] += 1

    def note(self, file, msg):
        self.notes[file].append(msg)


# ---------------- spreadsheets ----------------

def header_map(cells):
    m = {}
    for i, c in enumerate(cells):
        t = clean(c).lower().rstrip(':').strip()
        if not t:
            continue
        if PRICE.search(t):
            m.setdefault('_price', []).append(clean(c)); continue
        if SKIP_COLS.search(t) and t not in ('item',):
            m.setdefault('_skip', []).append(clean(c)); continue
        for key, names in HEADER_SYNONYMS.items():
            if t in names and key not in m:
                m[key] = i; break
    return m


def split_name_pn(name, pn):
    # returns (part number, title, description, how, value as written) for lists whose "part no." column is often not a part number
    def code(v):
        v = (v or '').strip()
        return (' ' not in v and 3 <= len(v) <= 30 and bool(re.search(r'\d', v))
                and not re.match(r'(MIL|AMS|SAE|NLGI|ISO|ASTM|BMS|DOD|FED)', v, re.I) and not re.search(r'OZ|GAL|QT|LB|TUBE|KG|LTR', v, re.I))
    name, pn = (name or '').strip(), (pn or '').strip()
    if not pn:
        return '', name, '', '', ''
    if code(pn):
        return pn, name, '', '', ''
    if code(name):
        title = f'{name} {pn}' if len(pn.split()) <= 2 else pn
        return name, title, '', 'part number was in the name column', ''
    return '', name, '', 'part-number column is not a part number (kept as written)', pn


def read_table_sheet(col, file, ws, kind):
    rows = list(ws.iter_rows(values_only=True))
    hdr, hm = None, {}
    for i, r in enumerate(rows[:40]):
        m = header_map(r)
        if ('pn' in m or 'title' in m) and ('desc' in m or 'title' in m or 'pn' in m) and len([k for k in m if not k.startswith('_')]) >= 2:
            hdr, hm = i, m; break
    if hdr is None:
        return False
    if hm.get('_price'):
        col.note(file, f'sheet "{ws.title}": price columns ignored: {", ".join(hm["_price"])}')
    if hm.get('_skip'):
        col.note(file, f'sheet "{ws.title}": not published: {", ".join(hm["_skip"])}')
    for n, r in enumerate(rows[hdr + 1:], start=hdr + 2):
        g = lambda k: clean(r[hm[k]]) if k in hm and hm[k] < len(r) else ''
        pn, desc = g('pn'), g('desc')
        title = g('title') or desc
        if 'title' in hm and 'desc' not in hm:
            pn, title, desc2, how, raw = split_name_pn(g('title'), pn)
            if how:
                col.files[file]['how: ' + how] += 1
            if desc2:
                desc = desc2
        if not pn and not title:
            continue
        if pn and not title:
            col.note(file, f'row {n}: part number {pn} has no description'); title = ''
        specs = {}
        if g('alt'):
            specs['Alternate part number'] = g('alt')
        code = g('cond').upper()
        if code:
            specs['Condition'] = COND_NAME.get(code, g('cond'))
        if g('trace8130'):
            t = g('trace8130')
            specs['FAA 8130-3'] = 'Yes' if t.lower() in ('yes', 'y') else t
        if 'title' in hm and 'desc' not in hm and raw:
            specs['Part no. (as written)'] = raw
        col.add(file, f'sheet "{ws.title}" row {n}', kind, pn=pn, title=title, desc=desc if g('title') else '', brand=g('brand'),
                cat_doc=g('cat'), cond=COND.get(code, ''), aircraft=[g('aircraft')] if g('aircraft') else [], specs=specs)
    return True


def is_brand_line(t, group_heading='', following=()):
    # brand lines in your lists are short names without a pack size ("Sikkens", "Dow Corning", "TURCO Italiana") directly
    # above a group heading. Above a "<x> products" heading that is enough; above any other heading ("Sealants & Paint")
    # one of the next product lines must start with the same name ("SIKKENS AUTOCRYL ..."), so a product without a pack
    # size ("SUPER XL BRIGHTENER") is not taken for a brand.
    if not (len(t) < 30 and len(t.split()) <= 3 and not re.search(r'[\d()]', t)):
        return False
    if group_heading.lower().endswith('products'):
        return True
    first = re.sub(r'[^a-z]', '', t.split()[0].lower())
    return bool(first) and any(re.sub(r'[^a-z ]', '', x.lower()).startswith(first) for x in following[:4])


def read_numbered_list(col, file, ws, kind, images):
    """PRODUCT LIST Sheet1: 20pt bold category, 13.5pt bold group ("<x> products", "Raw Materials"), a plain brand line just
    above a "... products" group, then product lines (numbered or not; later ones as "Name - description - Specification: X")."""
    lines = []          # (row, text, level) level: cat / group / text
    for n, r in enumerate(ws.iter_rows(), start=1):
        a = clean(r[0].value) if len(r) > 0 else ''
        c = r[1] if len(r) > 1 else None
        b = clean(c.value) if c is not None else ''
        if not b:
            continue
        f = c.font
        level = 'cat' if f.b and (f.sz or 0) >= 18 else 'group' if f.b and (f.sz or 0) >= 13 else 'text'
        lines.append((n, b, level, a, [clean(x.value) for x in r[2:5]]))
    cat = group = brand = ''
    just_brand = False
    item_rows, heading_rows = {}, set()
    for i, (n, b, level, a, rest) in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if level == 'cat':
            cat, group, brand = b, '', ''; heading_rows.add(n); continue
        if level == 'group':
            if not b.lower().endswith('products'):
                group = b
                if not just_brand:
                    brand = ''
            just_brand = False
            heading_rows.add(n); continue
        just_brand = False
        # a brand: a short line (no pack size) directly above a group heading ("Sikkens" above "Sealants & Paint")
        after = [x[1] for x in lines[i + 2:i + 8] if x[2] == 'text']
        if nxt and nxt[2] == 'group' and not re.fullmatch(r'\d+', a) and is_brand_line(b, nxt[1], after):
            brand, just_brand = b, True; heading_rows.add(n); continue
        txt, spec = b, ''
        m = re.search(r'spec(?:ification)?\s*:\s*(.+)$', txt, re.I)
        if m:
            spec = m.group(1).strip(' -–'); txt = txt[:m.start()].strip(' -–')
        parts = re.split(r'\s+[-–]\s+|\s*–\s*', txt, maxsplit=1)
        title = parts[0].strip(' -–')
        desc = ' '.join(([parts[1].strip()] if len(parts) > 1 else []) + [x for x in rest if x])
        item_rows[n] = len(col.rows)
        col.add(file, f'sheet "{ws.title}" row {n}', kind, title=title, desc=desc, brand=brand,
                cat_doc=cat, sub_doc=group, specs={'Specification': spec} if spec else {})
    attach_row_images(col, file, ws, images, item_rows, heading_rows)


def read_line_list(col, file, ws, kind, images):
    """PRODUCT LIST 2: one product per row, "Name - description - Specification : X"."""
    item_rows = {}
    for n, r in enumerate(ws.iter_rows(values_only=True), start=1):
        txt = clean(' '.join(str(x) for x in r if x not in (None, '')))
        if not txt or len(txt) < 3:
            continue
        spec = ''
        m = re.search(r'specification\s*:?\s*(.+)$', txt, re.I)
        if m:
            spec = m.group(1).strip(' -–'); txt = txt[:m.start()].strip(' -–')
        parts = re.split(r'\s+[-–]\s+', txt, maxsplit=1)
        title = parts[0].strip(' -–')
        desc = parts[1].strip() if len(parts) > 1 else ''
        item_rows[n] = len(col.rows)
        col.add(file, f'sheet "{ws.title}" row {n}', kind, title=title, desc=desc, specs={'Specification': spec} if spec else {})
    attach_row_images(col, file, ws, images, item_rows)


def attach_row_images(col, file, ws, images, item_rows, heading_rows=()):
    """An image anchored on a product's row, or in the empty rows just below it (up to 3) before the next line.
    Images on heading or brand rows are logos and are not used as product photos."""
    filled = sorted(set(item_rows) | set(heading_rows))
    logos = unplaced = 0
    for im in getattr(ws, '_images', []):
        row = im.anchor._from.row + 1
        above = [r for r in filled if r <= row]
        owner = above[-1] if above else None
        if owner in heading_rows:
            logos += 1; continue
        if owner is None or owner not in item_rows or row - owner > 3:
            unplaced += 1; continue
        idx = item_rows[owner]
        data = im._data()
        images.append((idx, data, f'{file}, sheet "{ws.title}" row {row}', None))
    n = len(getattr(ws, '_images', []))
    if n:
        col.note(file, f'sheet "{ws.title}": {n} embedded images: {n - logos - unplaced} beside a product, {logos} on brand/heading rows (logos, not used), {unplaced} with no product next to them (not used)')


def read_xlsx(col, path, file, kind, images):
    import openpyxl
    big = os.path.getsize(path) > 3_000_000
    wb = openpyxl.load_workbook(path, read_only=big, data_only=True)
    for ws in wb.worksheets:
        if read_table_sheet(col, file, ws, kind):
            continue
        first = [clean(c) for r in ws.iter_rows(values_only=True, max_row=8) for c in r if clean(c)]
        if first and first[0].lower().startswith('source'):
            col.note(file, f'sheet "{ws.title}": list of supplier websites and e-mails, not products'); continue
        if file.startswith('PRODUCT LIST.xlsx 2'):
            read_line_list(col, file, ws, kind, images)
        elif file == 'PRODUCT LIST.xlsx':
            read_numbered_list(col, file, ws, kind, images)
        else:
            col.note(file, f'sheet "{ws.title}": no product table found')


# ---------------- PDFs ----------------

def page_blocks(pg):
    out = []
    for b in pg.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        spans = [s for l in b['lines'] for s in l['spans'] if s['text'].strip()]
        if not spans:
            continue
        text = clean(' '.join(''.join(s['text'] for s in l['spans']) for l in b['lines']))
        out.append({'bbox': b['bbox'], 'text': text, 'size': max(s['size'] for s in spans),
                    'bold': any('Bold' in s['font'] or 'Black' in s['font'] or (s['flags'] & 16) for s in spans)})
    return out


def pdf_image(doc, xref):
    """A PDF image as file bytes. When the PDF keeps its transparency in a separate mask (SMask), the mask is applied and a
    PNG is returned; taking the image without its mask would turn the transparent background black."""
    import fitz
    info = doc.extract_image(xref)
    if doc.xref_get_key(xref, 'ImageMask')[1] == 'true':
        # a stencil (line drawing): the PDF paints its marks in the current colour; drawn here as black ink on white
        try:
            from PIL import Image
            pm = fitz.Pixmap(doc, xref)
            ink = Image.frombytes('L', (pm.width, pm.height), pm.samples)
            out = Image.new('L', ink.size, 255)
            out.paste(0, mask=ink)
            buf = io.BytesIO(); out.save(buf, 'PNG')
            return buf.getvalue()
        except Exception:
            return info['image']
    if not info.get('smask'):
        return info['image']
    try:
        base, mask = fitz.Pixmap(doc, xref), fitz.Pixmap(doc, info['smask'])
        if base.alpha:
            base = fitz.Pixmap(base, 0)
        if base.n > 3:                                   # CMYK -> RGB before adding the mask
            base = fitz.Pixmap(fitz.csRGB, base)
        return fitz.Pixmap(base, mask).tobytes('png')
    except Exception:
        return info['image']


def big_images(doc, pg, min_area=3500):
    out = []
    for info in pg.get_image_info(xrefs=True):
        x0, y0, x1, y1 = info['bbox']
        if (x1 - x0) * (y1 - y0) >= min_area and info.get('xref'):
            out.append((info['bbox'], info['xref']))
    return out


def brand_from_heading(h):
    m = re.match(r'^([A-Z0-9][\w&.\- ]{0,24}?)\s?(?:™|®|\(TM\)|\(R\))', h)
    return m.group(1).strip() if m else ''


class PageOCR:
    """Reads text from the picture of a PDF page (one JPG per page, 0001.jpg = page 1). Results are cached."""
    def __init__(self, img_dir, cache_dir):
        self.img_dir, self.cache_dir, self.engine, self.pages = img_dir, cache_dir, None, {}
        os.makedirs(cache_dir, exist_ok=True)

    def words(self, pno, page_rect):
        if pno in self.pages:
            return self.pages[pno]
        cp = os.path.join(self.cache_dir, f'{pno:04d}.json')
        if os.path.exists(cp):
            res = json.load(open(cp, encoding='utf-8'))
        else:
            img = os.path.join(self.img_dir, f'{pno:04d}.jpg')
            if not os.path.exists(img):
                self.pages[pno] = []; return []
            if self.engine is None:
                from rapidocr_onnxruntime import RapidOCR
                self.engine = RapidOCR()
            from PIL import Image
            w = Image.open(img).size[0]
            out, _ = self.engine(img)
            scale = page_rect.width / w
            res = [[[min(x for x, _ in b) * scale, min(y for _, y in b) * scale, max(x for x, _ in b) * scale, max(y for _, y in b) * scale], t, c]
                   for b, t, c in (out or [])]
            json.dump(res, open(cp, 'w', encoding='utf-8'))
            if pno % 25 == 0:
                print(f'  OCR page {pno}', flush=True)
        self.pages[pno] = res
        return res

    def text_in(self, pno, page_rect, bbox):
        x0, y0, x1, y1 = bbox
        hits = [(b[1], b[0], t) for b, t, c in self.words(pno, page_rect)
                if c >= 0.8 and x0 - 2 <= (b[0] + b[2]) / 2 <= x1 + 2 and y0 - 2 <= (b[1] + b[3]) / 2 <= y1 + 2]
        return ' '.join(t for _, _, t in sorted(hits)).strip()


def read_catalog_pdf(col, path, file, kind, images, page_cats=True, ocr=None):
    import fitz
    doc = fitz.open(path)
    ocr_used = 0
    tables_seen = rows_kept = garbled = 0
    family_imgs = single_imgs = variant_imgs = not_pn = family_used = 0
    for pno, pg in enumerate(doc, start=1):
        if pno % 200 == 0:
            print(f'  {file}: page {pno}/{doc.page_count}', flush=True)
        try:
            tabs = pg.find_tables().tables
        except Exception:
            tabs = []
        blocks = page_blocks(pg)
        if not blocks:
            continue
        # page category: the largest text near the top; subcategory: the next size down
        top = sorted([b for b in blocks if b['bbox'][1] < pg.rect.height * 0.2 and len(b['text']) < 60], key=lambda b: -b['size'])
        cat = top[0]['text'] if top else ''
        sub = next((b['text'] for b in top[1:] if b['size'] < top[0]['size'] - 1), '') if top else ''
        imgs = big_images(doc, pg)
        page_pn = 0
        for t in tabs:
            data = t.extract()
            if not data:
                continue
            head = [clean(c).lower() for c in data[0]]
            pcol = next((i for i, h in enumerate(head) if h.startswith('part n') or h in ('part', 'part #', 'p/n', 'pn')), None)
            if pcol is None:
                # product table without part numbers: PRODUCT | PURPOSE | FEATURES | APPLICATION | SPECIFICATIONS
                if head and head[0] == 'product' and len(data) == 1:
                    rows_kept += column_products(col, pg, pno, file, kind, t, data[0], cat, doc, images)
                    continue
                if head and head[0] == 'product':
                    pi = next((i for i, h in enumerate(head) if h == 'purpose'), None)
                    for rno, r in enumerate(data[1:], start=2):
                        cell = str(r[0] or '').strip()
                        title = clean(cell.split('\n')[0]) if cell else ''
                        if not title or title.lower() == 'product':
                            continue
                        specs = {clean(data[0][i]).title(): clean(str(r[i] or '').replace('•', ' / ')).strip(' /')
                                 for i in range(1, min(len(r), len(head))) if head[i] and i != pi and clean(r[i]) and not PRICE.search(head[i])}
                        col.add(file, f'page {pno} table row {rno}', kind, title=title,
                                desc=clean(r[pi]) if pi is not None and pi < len(r) else '', cat_doc=cat, specs=specs)
                        rows_kept += 1
                continue
            tables_seen += 1; page_pn += 1
            # a row may hold several products side by side: "Part Number | Grade | Part Number | Grade"
            pcols = [i for i, h in enumerate(head) if h.startswith('part n') or h in ('part', 'part #', 'p/n', 'pn')]
            groups = []
            for gi, pc in enumerate(pcols):
                end = pcols[gi + 1] if gi + 1 < len(pcols) else len(head)
                dc = next((i for i in range(pc + 1, end) if 'descr' in head[i]), None)
                nc = next((i for i in range(len(head)) if head[i] in ('product name', 'product', 'name') and i != pc), None)
                ex = [(i, clean(data[0][i])) for i in range(pc + 1, end) if i not in (dc, nc) and head[i] and not PRICE.search(head[i]) and not SKIP_COLS.search(head[i])]
                groups.append((pc, dc, ex, nc))
            tx0, ty0, tx1, ty1 = t.bbox
            # product heading: the nearest bold or large (11 pt+) line above the table in the same column, not the page header
            above = [b for b in blocks if b['bbox'][3] <= ty0 + 2 and b['bbox'][0] < tx1 and b['bbox'][2] > tx0 and ty0 - b['bbox'][3] < 220]
            above.sort(key=lambda b: -b['bbox'][3])
            heading_b = next((b for b in above if (b['bold'] or b['size'] >= 11) and len(b['text']) < 90 and b['text'] != cat
                              and not re.search(r'[.:;]\s|\b(is|are|by|with|for use)\b', b['text']) and not NOT_HEADING.search(b['text'])
                              and b['text'].lower() not in ('part number', 'description') and not b['text'].upper().endswith('(CONT.)')), None)
            if heading_b is None:
                # heading in another column beside the table (Battery Catalog): the nearest bold / large line starting above the table's end
                side = [b for b in blocks if b['bbox'][1] < ty1 and (b['bold'] or b['size'] >= 11) and len(b['text']) < 90 and b['text'] != cat
                        and not (tx0 - 2 <= b['bbox'][0] <= tx1) and not re.search(r'[.:;]\s|\b(is|are|by|with|for use|call)\b', b['text'], re.I)
                        and not NOT_HEADING.search(b['text'])]
                side.sort(key=lambda b: abs(b['bbox'][1] - ty0))
                heading_b = side[0] if side else None
            heading = heading_b['text'] if heading_b else (sub if sub and sub != cat and not NOT_HEADING.search(sub) else '')
            desc_lines = [b['text'] for b in above if heading_b and b['bbox'][1] > heading_b['bbox'][1] and not b['bold'] and b['size'] < 11]
            family_desc = ' '.join(reversed(desc_lines))
            kept, vdescs, subhead = [], [], ''
            for rno, r in enumerate(data[1:], start=1):
                cells = [clean(c) for c in r]
                filled = [c for c in cells if c]
                # a row with a single text cell inside the table is a sub-heading ("STIKIT(TM) DISC - 5 INCH")
                unreadable = any(CTRL.search(str(r[pc] or '')) for pc, *_ in groups if pc < len(r))
                if len(filled) == 1 and not unreadable and not is_pn(filled[0].upper()) and not re.search(r'\d{3,}', filled[0]):
                    subhead = filled[0]; continue
                for pc, dc, ex, nc in groups:
                    pn = cells[pc] if pc < len(cells) else ''
                    raw_unreadable = pc < len(r) and bool(CTRL.search(str(r[pc] or '')))
                    if (not pn and not raw_unreadable) or pn.lower().startswith('part n'):
                        continue
                    if raw_unreadable and ocr is not None:
                        # the PDF has no text for this cell: read it from the picture of the page
                        try:
                            cell = t.rows[rno].cells[pc]
                        except Exception:
                            cell = None
                        pn = clean(ocr.text_in(pno, pg.rect, cell)) if cell else ''
                        if pn and re.fullmatch(r'[A-Z0-9][A-Z0-9\-./]{2,30}', pn.upper().replace(' ', '')):
                            pn = pn.replace(' ', ''); ocr_used += 1
                        else:
                            garbled += 1; continue
                    elif raw_unreadable or not pn or len(pn) > 40 or ' ' in pn.strip() and len(pn.split()) > 3:
                        garbled += 1; continue
                    if re.search(r'[”"’]|\b[a-z]{3,}\b|XXX', pn) or not (re.search(r'\d', pn) or re.fullmatch(r'[A-Z][A-Z0-9\-*]{1,24}', pn)):
                        not_pn += 1; continue           # pack text that landed in the part-number column ("1” Discs 50/Box")
                    vdesc = cells[dc] if dc is not None and dc < len(cells) else ''
                    pname = cells[nc] if nc is not None and nc < len(cells) else ''
                    if pname:
                        vdesc = ' – '.join(x for x in (pname, vdesc) if x)
                    specs = {name: cells[i] for i, name in ex if i < len(cells) and cells[i]}
                    if not vdesc and ex:
                        # no description column: the first detail column tells the rows apart in the title
                        # ("RESPIRATOR MASK ACCESSORIES – 6001 / Organic Vapor / 2PK")
                        vdesc = next((cells[i] for i, _ in ex if i < len(cells) and cells[i]), '')
                    name = ' – '.join(x for x in (heading, subhead, vdesc) if x)
                    title = name or pn
                    aircraft = []
                    if {'manufacturer', 'model', 'battery type'} <= set(head):
                        # battery application table: the battery type is the name; aircraft maker + model go to the aircraft list
                        hi = {h: i for i, h in enumerate(head)}
                        title = cells[hi['battery type']] or pn
                        mk, md = cells[hi['manufacturer']], cells[hi['model']]
                        aircraft = [' '.join(x for x in (mk, md) if x)] if (mk or md) else []
                        specs = {k: v for k, v in specs.items() if k.lower() not in ('manufacturer', 'model', 'battery type')}
                        specs['Battery type'] = cells[hi['battery type']]
                    vdescs.append(' '.join(x for x in (subhead, vdesc) if x))
                    kept.append(len(col.rows))
                    col.add(file, f'page {pno}', kind, pn=pn, title=title, desc=family_desc, brand=brand_from_heading(heading),
                            cat_doc=cat, sub_doc=sub, specs=specs, aircraft=aircraft, brand_from='heading' if brand_from_heading(heading) else '')
            rows_kept += len(kept)
            # image of this product block: overlapping the block vertically, beside or above the table
            region = (min([heading_b['bbox'][1]] if heading_b else [ty0]) - 10, ty1 + 10)
            near = [(bb, x) for bb, x in imgs if bb[1] < region[1] and bb[3] > region[0]]
            if near and images is not None and kept:
                variants = len(kept) > 1 and heading and all(v and PACK.match(v) for v in vdescs)
                if len(kept) == 1 or variants:
                    bb, xref = near[0]
                    try:
                        data_ = pdf_image(doc, xref)
                        gid = ('variants|' if variants else 'single|') + f'{file}|{pno}|{round(ty0)}'
                        for idx in kept:
                            images.append((idx, data_, f'{file}, page {pno}', gid))
                        single_imgs += 1
                        variant_imgs += len(kept) if variants else 0
                    except Exception:
                        pass
                else:
                    family_imgs += 1
                    if FAMILY_PHOTOS:
                        # one catalog photo beside a table of related products: used for each of them, marked "family photo"
                        try:
                            data_ = pdf_image(doc, near[0][1])
                            for idx in kept:
                                images.append((idx, data_, f'{file}, page {pno}', f'family|{file}|{pno}|{round(ty0)}'))
                            family_used += len(kept)
                        except Exception:
                            pass
    col.note(file, f'{doc.page_count} pages, {tables_seen} part-number tables, {rows_kept} product rows'
                   + (f', {ocr_used} part numbers read from the page pictures (OCR)' if ocr_used else '')
                   + (f', {garbled} rows skipped (unreadable characters)' if garbled else '')
                   + (f', {not_pn} rows skipped (part-number cell holds pack text, not a part number)' if not_pn else '')
                   + f'; photos attached: {single_imgs} ({variant_imgs} products share a photo with their other size/pack variants)'
                   + f'; photos not used because they show several different products: {family_imgs}')
    return rows_kept


# never a product heading: link notes, column headers, a table row of the next table ("051125-85357 1/2” / 72/CS")
# and running page headers ("AEROSPACE SEALANTS AND ACCESSORIES (CONT.)")
NOT_HEADING = re.compile(r'^click\b|shop\.boeing\.com|\bpart no\b|\bpart number\b|^\s*\d{5,}(?:-\d+)?\s|\(cont\.?\)', re.I)
PN_TOKEN = re.compile(r'^[A-Z0-9][A-Z0-9\-./]{2,24}$')
NAV = {'INTERIOR SURFACES', 'EXTERIOR SURFACES', 'TOILETS & DRAINS', 'ODOR CONTROL', 'HAND CARE', 'MRO MAINTENANCE'}


def is_pn(t):
    return bool(PN_TOKEN.match(t) and re.search(r'\d', t) and re.search(r'[A-Z]', t))


def text_part_lists(col, pg, pno, file, kind):
    # "Part Number" lists drawn as plain text: product title above the bullet points, then part-number / packaging lines
    lines = [clean(x) for x in pg.get_text().split('\n')]
    kept = 0
    for i, ln in enumerate(lines):
        if not ln.lower().startswith('part number'):
            continue
        bullets = [k for k in range(max(0, i - 60), i) if lines[k].startswith('•')]
        if not bullets:
            continue
        start = bullets[-1]
        for k in reversed(bullets[:-1]):          # contiguous bullet group: gaps of at most 4 lines
            if start - k <= 4:
                start = k
            else:
                break
        t, m = [], start - 1
        while m >= 0 and lines[m] and lines[m] not in NAV and len(t) < 8:
            t.insert(0, lines[m]); m -= 1
        if len(t) > 1 and not re.search(r'[®™]', t[0]) and re.search(r'[®™]', ' '.join(t[1:3])):
            t = t[1:]                              # a section name on its own line before the brand
        title = re.sub(r'\s+([®™])', r'\1', re.sub(r'\s+-\s*', '-', ' '.join(t))).strip()
        if not title or len(title) > 160:
            continue
        n = i + 1
        while n < len(lines) and (not lines[n] or lines[n].lower() in ('packaging', 'uom', 'description', 'size')):
            n += 1
        while n < len(lines):
            tok = lines[n]
            if not tok:
                n += 1; continue
            if not is_pn(tok):
                break
            v, n = [], n + 1
            while n < len(lines) and lines[n] and not is_pn(lines[n]) and not lines[n].lower().startswith('test ref'):
                v.append(lines[n]); n += 1
            vdesc = clean(' '.join(v))
            col.add(file, f'page {pno}', kind, pn=tok, title=title + (' – ' + vdesc.split('Case:')[0].strip() if vdesc else ''),
                    brand=brand_from_heading(title), specs={'Packaging': vdesc} if vdesc else {}, brand_from='heading')
            kept += 1
    return kept


def column_products(col, pg, pno, file, kind, t, header, cat, doc=None, images=None):
    # Zip-Chem layout: only the header row is a drawn table. Each product row starts at its name (large bold text);
    # text in the row goes to a column by the header's column edges; the photo in the PRODUCT column belongs to that row.
    cells = sorted([c for c in t.cells if c and abs(c[1] - t.bbox[1]) < 2], key=lambda c: c[0])
    if len(cells) != len(header):
        return 0
    edges = [c[0] for c in cells] + [pg.rect.width]
    names = [clean(h).title() for h in header]
    lines = []
    for b in pg.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            sp = [x for x in l['spans'] if x['text'].strip()]
            if not sp or l['bbox'][1] < t.bbox[3] - 1:
                continue
            lines.append((l['bbox'][1], l['bbox'][0], clean(''.join(x['text'] for x in sp)), max(x['size'] for x in sp),
                          any('Bo' in x['font'] for x in sp)))
    lines.sort()
    starts = [(y, txt) for y, x, txt, size, bold in lines if bold and size >= 11 and len(txt) < 40
              and '@' not in txt and not txt.lower().startswith('for more information')]
    kept = 0
    for k, (y0, title) in enumerate(starts):
        y1 = starts[k + 1][0] - 4 if k + 1 < len(starts) else pg.rect.height - 90
        cols = {}
        for y, x, txt, size, bold in lines:
            if not (y0 - 4 <= y < y1) or size < 5 or (y == y0 and txt == title):
                continue
            c = next((n for n in range(len(cells)) if edges[n] - 2 <= x < edges[n + 1] - 2), None)
            if c:
                cols.setdefault(names[c], []).append(txt)
        cols = {a: clean(' '.join(v)).replace('• ', '').strip() for a, v in cols.items()}
        desc = cols.pop('Purpose', '')
        specs = {a: v for a, v in cols.items() if v and not PRICE.search(a)}
        idx = len(col.rows)
        col.add(file, f'page {pno}', kind, title=title, desc=desc, cat_doc=cat, specs=specs)
        kept += 1
        if doc is not None and images is not None:
            photos = [(bb, xr) for bb, xr in big_images(doc, pg, 2500) if bb[0] < edges[1] and y0 - 40 <= (bb[1] + bb[3]) / 2 < y1]
            if len(photos) == 1:
                try:
                    images.append((idx, pdf_image(doc, photos[0][1]), f'{file}, page {pno}', None))
                except Exception:
                    pass
    return kept


def read_name_list_pdf(col, path, file, kind):
    # Boeing Chemicals line card: section (14pt bold), group (8pt bold), product names (light condensed); spec numbers skipped
    import fitz
    doc = fitz.open(path)
    section = group = ''
    kept = specs_skipped = 0
    for pno, pg in enumerate(doc, start=1):
        if pno < 4 or pno == doc.page_count:
            continue
        for b in pg.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                for sp in l['spans']:
                    t = clean(sp['text'])
                    if not t or t.isdigit() or t.upper() == 'BOEING DISTRIBUTION SERVICES':
                        continue
                    f = sp['font']
                    if f.endswith('-Bd') and sp['size'] >= 12:
                        section, group = t.title(), ''; continue
                    if f.endswith('-Bd'):
                        group = (group + ' / ' + t.strip(' /').title()) if t.startswith('/') else t.strip(' /').title(); continue
                    if not f.endswith('LtCn'):
                        continue
                    if re.match(r'^(A-A-|TT-|MIL-|AMS|BMS|DOD-|SAE)', t):
                        specs_skipped += 1; continue
                    col.add(file, f'page {pno}', kind, title=t, cat_doc=section, sub_doc=group); kept += 1
    col.note(file, f'{doc.page_count} pages, {kept} product names (no part numbers in this file); {specs_skipped} specification-number lines skipped')


def read_full_details_pdf(col, path, file, kind, images):
    """PRODUCT LIST WITH FULL DETAILS: a numbered name / part-number table, then brand and category sections."""
    import fitz
    doc = fitz.open(path)
    brand, cat, kept, lines = '', '', 0, []
    for pno, pg in enumerate(doc, start=1):
        tabs = pg.find_tables().tables
        if tabs:
            for t in tabs:
                for rno, r in enumerate(t.extract(), start=1):
                    cells = [clean(c) for c in r]
                    vals = [c for c in cells if c]
                    if len(vals) >= 2 and not vals[0].lower().startswith('product'):
                        name, pn = (vals[-2], vals[-1]) if not re.fullmatch(r'\d+', vals[-1]) else (vals[0], '')
                        if re.fullmatch(r'\d+', name):
                            continue
                        pn, name, desc, how, raw = split_name_pn(name, pn)
                        if how:
                            col.files[file]['how: ' + how] += 1
                        col.add(file, f'page {pno} table row {rno}', kind, title=name, pn=pn, desc=desc,
                                specs={'Part no. (as written)': raw} if raw else {}); kept += 1
            continue
        for l in pg.get_text('dict')['blocks']:
            for ln in l.get('lines', []):
                sp = [x for x in ln['spans'] if x['text'].strip()]
                if sp:
                    lines.append((pno, clean(''.join(x['text'] for x in sp)), max(x['size'] for x in sp),
                                  any('Bold' in x['font'] or x['flags'] & 16 for x in sp)))
    # same layout as the Excel list: 20 pt+ bold category, 13 pt+ bold group ("<x> products"), a brand line directly above
    # a "... products" group, product lines; the later description pages (9 pt) have no brands at all
    group, just_brand = '', False
    for i, (pno, t, size, bold) in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if not t or t.isdigit():
            continue
        if bold and size >= 18:
            cat, group, brand = t, '', ''; continue
        if bold and size >= 13:
            if not t.lower().endswith('products'):
                group = t
                if not just_brand:
                    brand = ''
            just_brand = False
            continue
        just_brand = False
        after = [x[1] for x in lines[i + 2:i + 8] if not x[3]]
        if nxt and nxt[3] and nxt[2] >= 13 and size >= 10.5 and is_brand_line(t, nxt[1], after):
            brand, just_brand = t, True; continue
        if re.match(r'spec(ification)?\s*:', t, re.I) and col.rows and col.rows[-1]['file'] == file:
            sp_ = col.rows[-1].setdefault('specs', {})        # a specification on its own line belongs to the line above
            sp_['Specification'] = (sp_.get('Specification', '') + ' / ' if sp_.get('Specification') else '') + re.sub(r'^spec(ification)?\s*:\s*', '', t, flags=re.I)
            continue
        for item in [x.strip() for x in re.split(r'\s/\s', t) if x.strip()] if size >= 10.5 else [t]:
            m = re.match(r'^(\d+)\s+(\S.*)$', item)
            if m and len(m.group(2)) < 80:
                item = m.group(2)
            spec = ''
            sm = re.search(r'spec(?:ifi?cation)?\s*:?\s*(.+)$', item, re.I)
            if sm and re.search(r'[A-Z]{2,}', sm.group(1)):
                spec = sm.group(1).strip(' -–'); item = item[:sm.start()].strip(' -–')
            parts = re.split(r'\s*[–]\s*|\s+-\s+', item, maxsplit=1)
            title = parts[0].strip(' -–')
            if len(title) < 3:
                continue
            col.add(file, f'page {pno}', kind, title=title, desc=parts[1].strip(' -–') if len(parts) > 1 else '', brand=brand,
                    cat_doc=cat, sub_doc=group, specs={'Specification': spec} if spec else {}); kept += 1
    col.note(file, f'{doc.page_count} pages, {kept} product rows; its images are page decorations (no product photos beside rows)')


def ocr_pages(path, pages, ocr):
    import fitz
    doc = fitz.open(path)
    out = []
    for p in pages:
        pix = doc[p - 1].get_pixmap(dpi=200)
        res, _ = ocr(pix.tobytes('png'))
        out.append((p, ' '.join(r[1] for r in (res or []))))
    return out


# ---------------- merge, categories, images ----------------

def key_of(r):
    pn = L.norm_key(r.get('pn', ''))
    if pn and len(pn) <= 4:
        # very short part numbers ("74") are not unique across makers: they merge within your own lists, not across catalogs
        return 'pn:' + pn + '|' + ('velmach' if r['kind'] == 'velmach' else L.norm_key(r['file']))
    return ('pn:' + pn) if pn else ('name:' + L.norm_key(r.get('title', '')))


def pick(vals):
    """vals: [(value, source, file)]. Returns (chosen, resolved?) using the document dates: the newest document wins;
    when the newest date is shared by different values, or a date is unknown, nothing is decided (first value kept)."""
    if len(vals) < 2:
        return vals[0], True
    dated = [(DOC_DATES.get(f, ('', ''))[0], v, s_, f) for v, s_, f in vals]
    if any(not d for d, *_ in dated):
        return vals[0], False
    top = max(d for d, *_ in dated)
    best = [x for x in dated if x[0] == top]
    if len({L.norm_key(x[1]) for x in best}) > 1:
        return vals[0], False
    return (best[0][1], best[0][2], best[0][3]), True


def merge(rows):
    groups = collections.OrderedDict()
    for i, r in enumerate(rows):
        groups.setdefault(key_of(r), []).append(i)
    products, conflicts, resolved = [], [], []
    for key, idxs in groups.items():
        rs = sorted((rows[i] for i in idxs), key=lambda r: PRIORITY.get(r['kind'], 9))
        p = {'key': key, 'partNumber': next((r['pn'] for r in rs if r.get('pn')), ''), 'title': '', 'brand': '', 'description': '',
             'cat_doc': [], 'condition': '', 'aircraft': [], 'specifications': {}, 'sources': [], 'kinds': sorted({r['kind'] for r in rs}), 'rows': idxs}
        who = lambda: p['partNumber'] or p['title']
        for field, out in (('title', 'title'), ('brand', 'brand'), ('desc', 'description'), ('cond', 'condition')):
            vals = []
            for r in rs:
                v = r.get(field, '')
                if field == 'brand' and r.get('brand_from') == 'heading' and L.norm_key(v) not in EXPLICIT_BRANDS:
                    p.setdefault('brandSuggestion', v)      # a name marked TM / (R) in the heading: suggested, not used
                    continue
                if v and L.norm_key(v) not in [L.norm_key(x[0]) for x in vals]:
                    vals.append((v, f"{r['file']}, {r['loc']}", r['file']))
            if not vals:
                continue
            similar = field == 'title' and all(L.norm_key(vals[0][0]) in L.norm_key(v) or L.norm_key(v) in L.norm_key(vals[0][0]) for v, _, _ in vals[1:])
            chosen, ok = pick(vals)
            p[out] = chosen[0]
            if len(vals) > 1 and not similar:
                (resolved if ok else conflicts).append((p['partNumber'] or chosen[0], out, vals, chosen))
        spec_vals = collections.OrderedDict()
        for r in rs:
            for c in (r.get('cat_doc'), r.get('sub_doc')):
                if c and c not in p['cat_doc']:
                    p['cat_doc'].append(c)
            for a in r.get('aircraft', []):
                if a not in p['aircraft']:
                    p['aircraft'].append(a)
            for k, v in r.get('specs', {}).items():
                spec_vals.setdefault(k, collections.OrderedDict()).setdefault(r['file'], [])
                if v not in spec_vals[k][r['file']]:
                    spec_vals[k][r['file']].append(v)
            src = f"{r['file']}, {r['loc']}"
            if src not in p['sources']:
                p['sources'].append(src)
        for k, per_file in spec_vals.items():
            # one file listing several values (one part number on several serial rows): all kept, joined
            vals = [(' / '.join(v), f, f) for f, v in per_file.items()]
            if len({L.norm_key(v) for v, _, _ in vals}) > 1:
                chosen, ok = pick(vals)
                (resolved if ok else conflicts).append((p['partNumber'] or p['title'], 'specification: ' + k, vals, chosen))
                p['specifications'][k] = chosen[0]
            else:
                p['specifications'][k] = vals[0][0]
        products.append(p)
    return products, conflicts, resolved


# suggestions from scripts/map-old-categories.py that you approved, and where they now live in the tree
SUGGEST = {
    'Consumables > Adhesives & Compounds (new subcategory)': ('consumables', 'adhesives-compounds'),
    'Consumables > Sealants (new subcategory)': ('consumables', 'sealants'),
    'Consumables > Paints & Coatings (new subcategory)': ('consumables', 'paints-coatings'),
    'Consumables > Chemicals (new subcategory)': ('consumables', 'chemicals'),
    'Consumables > NDT Chemicals (new subcategory)': ('consumables', 'ndt-chemicals'),
    'Consumables > Composite Materials (new subcategory)': ('consumables', 'composite-materials'),
    'Raw Materials (new category)': ('consumables', 'raw-materials'),
    'Aircraft Parts > Electrical Hardware (new subcategory)': ('aircraft-parts', 'electrical-hardware'),
    'Aircraft Parts > Hardware & Fasteners (new subcategory)': ('aircraft-parts', 'hardware-fasteners'),
    'Aircraft Parts > Seals & O-Rings (new subcategory)': ('aircraft-parts', 'seals-o-rings'),
}


TYPE_WORDS = [r'SEAL', r'PAINT|COAT|PRIMER', r'ADHESIV|EPOXY|BOND', r'OIL|GREASE|LUBRIC', r'CLEAN|SOLVENT|DEGREAS', r'TAPE|WIPE']


def classify_text(text, pn, names):
    parent, child, conf, reason = MAP.classify({'desc_en': text, 'name_en': pn, 'category': ''}, names)
    t = text.upper()
    # a marking tool only when it is a pen / paint / ink marker; seat-row and placard markers are cabin parts
    if child == 'marking-tools' and re.search(r'\bMARKER', t) and not re.search(r'PEN|INK|PAINT|PERMANENT|SHARPIE|MARKING|CRAYON|LAYOUT', t):
        if re.search(r'SEAT|ROW|PLACARD|LATCH|LOAD LIMIT|EXIT|DECAL|LAV', t):
            return MAP.PRT, 'cockpit-cabin-parts', 'medium', '"Marker" with seat / placard words: a cabin marker, not a marking tool'
        return None, None, 'low', '"Marker" without pen / paint words: not clear which kind; needs a person'
    reason = reason.replace('; old category ""', '').replace(' differs', '')
    if not parent:
        for sug, (par, slug) in SUGGEST.items():
            if f'would fit: {sug}' in reason:
                word = re.match(r'"([^"]+)"', reason)
                return par, slug, 'medium', (f'"{word.group(1)}" in the description' if word else reason.split(';')[0])
    return parent, child, conf, reason


def family_only(p):
    # the product's only document photo is a family photo (one photo for a table of related products)
    return bool(p['images']) and all(i.get('note') == 'family photo' for i in p['images'])


def categorize(p, names):
    own = classify_text(' '.join([p['title'], p['description']]), p['partNumber'], names)
    if own[0]:
        return own
    # only the most specific heading that names a product type; a heading naming two types ("Sealants & Paint") stops the search
    for heading in reversed(p['cat_doc']):
        kinds = [w for w in TYPE_WORDS if re.search(w, heading.upper())]
        if not kinds:
            continue
        if len(kinds) > 1:
            break
        h = classify_text(heading, '', names)
        if h[0]:
            return h[0], h[1], 'low', f'from the section heading "{heading}" in your list (the product name alone does not say)'
        break
    return own


def best_guess(p, names):
    # for the review file only: a guess for a product that is not published yet
    own = classify_text(' '.join([p['title'], p['description']]), p['partNumber'], names)
    m = re.search(r'would fit: ([^;]+)', own[3])
    if m:
        g = m.group(1)
        return (g.split(':')[0].strip() if ':' in g else g), 'low', own[3]
    for heading in reversed(p['cat_doc']):
        h = classify_text(heading, '', names)
        if h[0]:
            return names(h[0], h[1]), 'low', f'section heading "{heading}" (names more than one type, or not the product itself)'
    return '', 'none', own[3]


DOC_DATES = {}
EXPLICIT_BRANDS = set()      # brands a document names outright (a brand heading or a brand column)


def doc_date(path, rel):
    # the date the document carries: last-saved date in the file's properties (xlsx) or the PDF's modified / created date
    try:
        if rel.lower().endswith('.xlsx'):
            import openpyxl
            pr = openpyxl.load_workbook(path, read_only=True).properties
            d = pr.modified or pr.created
            return (d.date().isoformat(), 'last saved (file properties)') if d else ('', 'unknown')
        if rel.lower().endswith('.pdf'):
            import fitz
            m = fitz.open(path).metadata
            raw = m.get('modDate') or m.get('creationDate') or ''
            mm = re.match(r'D:(\d{4})(\d{2})(\d{2})', raw)
            return (f'{mm.group(1)}-{mm.group(2)}-{mm.group(3)}', 'PDF ' + ('modified' if m.get('modDate') else 'created') + ' date') if mm else ('', 'unknown')
    except Exception:
        pass
    return '', 'unknown'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.path.join(ROOT, 'assets', 'velmach product'))
    ap.add_argument('--lib', action='append', default=[], help='extra library folder (openpyxl, python-docx, rapidocr)')
    args = ap.parse_args()
    for p in args.lib:
        sys.path.insert(0, p)
    col, images = Collector(), []
    ocr = None
    for dp, _, fs in os.walk(args.src):
        for fn in sorted(fs):
            path = os.path.join(dp, fn); rel = os.path.relpath(path, args.src).replace(os.sep, '/')
            if rel.startswith(PAGE_PICTURE_DIRS):
                continue                     # page pictures: used through OCR_PAGES, not documents themselves
            kind = FILES.get(rel, 'catalog')
            col.files.setdefault(rel, collections.Counter())
            if kind == 'apart':
                col.note(rel, 'kept apart (your decision): not read, no products and no images taken')
                print('apart  ', rel, flush=True)
                continue
            st = os.stat(path)
            cpath = os.path.join(CACHE, hashlib.sha1(f'{rel}|{st.st_size}|{int(st.st_mtime)}'.encode()).hexdigest() + '.pkl')
            if os.path.exists(cpath):
                c = pickle.load(open(cpath, 'rb'))
                base = len(col.rows)
                col.rows += c['rows']; col.files[rel] = c['count']; col.notes[rel] = c['notes']
                images += [(base + x[0], x[1], x[2], x[3] if len(x) > 3 else None) for x in c['images']]
                print('cached ', rel, flush=True)
                continue
            r0, i0 = len(col.rows), len(images)
            print('reading', rel, flush=True)
            try:
                if kind.startswith('duplicate'):
                    col.note(rel, 'not read separately: ' + kind.split(':', 1)[1]); continue
                if kind == 'links':
                    import docx
                    urls = [x.text.strip() for x in docx.Document(path).paragraphs if x.text.strip()]
                    col.note(rel, 'links only, not fetched: ' + ', '.join(urls)); continue
                if kind == 'suppliers':
                    col.note(rel, 'approved-supplier list (supplier names, codes and specifications): no products'); continue
                if fn.lower().endswith('.xlsx'):
                    read_xlsx(col, path, rel, kind, images)
                elif rel == 'Boeing_Distribution_Chemicals_May20_digital.pdf':
                    read_name_list_pdf(col, path, rel, kind)
                elif rel == 'PRODUCT LIST WITH FULL DETAILS.pdf':
                    read_full_details_pdf(col, path, rel, kind, images)
                elif fn.lower().endswith('.pdf'):
                    import fitz
                    d = fitz.open(path)
                    scanned = [i + 1 for i, pg in enumerate(d) if len(pg.get_text().strip()) <= 40]
                    if kind == 'profile':
                        txt = ' '.join(pg.get_text() for pg in d)
                        if scanned:
                            if ocr is None:
                                from rapidocr_onnxruntime import RapidOCR
                                ocr = RapidOCR()
                            txt += ' '.join(t for _, t in ocr_pages(path, scanned, ocr))
                        col.note(rel, 'company profile (read' + (' with OCR' if scanned else '') + '): no part-number list. Text: ' + clean(txt)[:300])
                        continue
                    ocr = None
                    if rel in OCR_PAGES:
                        ocr = PageOCR(os.path.join(args.src, OCR_PAGES[rel]), os.path.join(CACHE, 'ocr', re.sub(r'\W+', '-', rel)[:60]))
                    n = read_catalog_pdf(col, path, rel, 'catalog' if kind == 'aviall-ocr' else kind, images, ocr=ocr)
                    if scanned:
                        col.note(rel, f'pages without text (covers / photos): {", ".join(map(str, scanned[:12]))}{" ..." if len(scanned) > 12 else ""}')
                else:
                    col.note(rel, 'file type not read')
            except Exception as e:
                col.note(rel, f'could not read: {type(e).__name__}: {e}')
            os.makedirs(CACHE, exist_ok=True)
            pickle.dump({'rows': col.rows[r0:], 'count': col.files[rel], 'notes': col.notes.get(rel, []),
                         'images': [(x[0] - r0,) + tuple(x[1:]) for x in images[i0:]]}, open(cpath, 'wb'))
    # main list: your Velmach lists and the kept catalogs. Other companies' stock lists only add to products already in it.
    stock_rows = [r for r in col.rows if r['kind'] == 'stock']
    keep_idx = [i for i, r in enumerate(col.rows) if r['kind'] in PRIORITY]
    remap = {old: new for new, old in enumerate(keep_idx)}
    images = [(remap[x[0]],) + tuple(x[1:]) for x in images if x[0] in remap]
    all_rows, col.rows = col.rows, [col.rows[i] for i in keep_idx]
    print('merging', len(col.rows), 'rows', flush=True)
    for f in {r['file'] for r in col.rows}:
        DOC_DATES[f] = doc_date(os.path.join(args.src, f), f)
    EXPLICIT_BRANDS.update(L.norm_key(r['brand']) for r in col.rows if r.get('brand') and not r.get('brand_from'))
    products, conflicts, resolved = merge(col.rows)
    col.resolved = resolved
    by_pn = {p['key']: p for p in products if p['key'].startswith('pn:')}
    enriched = collections.Counter()
    for r in stock_rows:
        p = by_pn.get(key_of(r))
        if not p:
            continue
        what = []
        if r.get('desc') and not p['description'] and L.norm_key(r['desc']) != L.norm_key(p['title']):
            p['description'] = r['desc']; what.append('description')
        if not p['description'] and r.get('title') and L.norm_key(r['title']) != L.norm_key(p['title']) and not r.get('desc'):
            p['description'] = r['title']; what.append('description')
        if r.get('cond') and not p['condition']:
            p['condition'] = r['cond']; what.append('condition')
        for a in r.get('aircraft', []):
            if a not in p['aircraft']:
                p['aircraft'].append(a); what.append('aircraft type')
        for k, v in r.get('specs', {}).items():
            if k not in p['specifications']:
                p['specifications'][k] = v; what.append(k.lower())
        if what:
            src = f"{r['file']}, {r['loc']} (added: {', '.join(sorted(set(what)))})"
            if src not in p['sources']:
                p['sources'].append(src)
            enriched[r['file']] += 1
            p.setdefault('enriched', set()).update(what)
    col.enriched = enriched
    col.stock_matched = sum(1 for p in products if p.get('enriched'))
    row_owner = {}
    for pi, p in enumerate(products):
        for i in p['rows']:
            row_owner[i] = pi
    # images: a photo beside one product, or beside size / pack variants of the same product; never one shown with different products
    import shutil
    shutil.rmtree(STAGE, ignore_errors=True)
    os.makedirs(STAGE, exist_ok=True)
    groups_of = collections.defaultdict(set)
    for idx, data, src, gid in images:
        pi = row_owner.get(idx)
        if pi is not None:
            groups_of[hashlib.sha1(data).hexdigest()].add(gid or f'p{pi}')
    img_of, shared_logo = collections.defaultdict(list), collections.defaultdict(bool)
    for idx, data, src, gid in images:
        pi = row_owner.get(idx)
        if pi is None:
            continue
        h = hashlib.sha1(data).hexdigest()
        if len(groups_of[h]) > 1:
            shared_logo[pi] = True; continue
        if any(x[1] == src for x in img_of[pi]):
            continue
        try:
            from PIL import Image
            Image.open(io.BytesIO(data)).verify()
        except Exception:
            continue
        name = f"{h[:16]}.img"
        path = os.path.join(STAGE, name)
        if not os.path.exists(path):
            open(path, 'wb').write(data)
        note = 'variant photo' if gid and gid.startswith('variants|') else 'family photo' if gid and gid.startswith('family|') else 'product photo'
        img_of[pi].append((os.path.relpath(path, ROOT).replace(os.sep, '/'), src, note))
    cats = L.load_categories()
    by = {p['slug']: p for p in cats}
    def names(parent, child=''):
        c = next((x for x in by[parent]['children'] if x['slug'] == child), None)
        return by[parent]['en'] + (' > ' + c['en'] if c else '')
    out, missing = [], []
    for pi, p in enumerate(products):
        parent, child, conf, reason = categorize(p, names)
        imgs = img_of.get(pi, [])
        rec = {'key': p['key'], 'partNumber': p['partNumber'], 'title': p['title'], 'title_ar': '', 'brand': p['brand'],
               'description': p['description'], 'description_ar': '', 'specifications': [{'name': k, 'value': v} for k, v in p['specifications'].items()],
               'condition': p['condition'], 'documentCategories': p['cat_doc'], 'aircraftTypes': p['aircraft'],
               'categoryParent': parent or '', 'categoryChild': child or '', 'categoryConfidence': conf, 'categoryReason': reason,
               'images': [{'path': a, 'source': s_, 'origin': 'document', 'note': n_} for a, s_, n_ in imgs],
               'sources': p['sources'], 'sourceKinds': p['kinds'], 'enrichedFromStockLists': sorted(p.get('enriched', [])),
               'brandSuggestion': '' if p['brand'] else p.get('brandSuggestion', '')}
        if not parent:
            rec['bestGuess'], rec['bestGuessConfidence'], rec['bestGuessWhy'] = best_guess(p, names)
        out.append(rec)
        if not imgs:
            why = 'photo shown with different products (not used)' if shared_logo[pi] else 'no image next to this product in the documents'
            missing.append(rec | {'why': why})
    json.dump({'source': os.path.relpath(args.src, ROOT), 'products': out}, open(os.path.join(ROOT, 'data', 'velmach-products.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    old = os.path.join(ROOT, 'data', 'velmach-aviall-only.json')
    if os.path.exists(old):
        os.remove(old)                 # written by an earlier dry run of this script; Aviall products are not used
    imp = []
    wpath = os.path.join(ROOT, 'data', 'velmach-web-images.json')     # verified manufacturer images (scripts/find-web-images.py)
    web = json.load(open(wpath, encoding='utf-8')) if os.path.exists(wpath) else {}
    hpath = os.path.join(ROOT, 'data', 'velmach-hidden.json')        # duplicates hidden by scripts/remove-duplicates.py
    hidden = json.load(open(hpath, encoding='utf-8')) if os.path.exists(hpath) else {}
    for p in out:
        if not p['categoryParent'] or p['key'] in hidden:
            continue
        specs = [s_ for s_ in p['specifications'] if s_['value']]
        if p['aircraftTypes']:
            specs.append({'name': 'Aircraft', 'value': ', '.join(p['aircraftTypes'])})
        imp.append({'importKey': p['key'], 'title': p['title'], 'partNumber': p['partNumber'], 'brand': p['brand'], 'categoryParent': p['categoryParent'],
                    'categoryChild': p['categoryChild'], 'description': p['description'], 'specifications': specs,
                    'images': ([web[p['key']]['image']] if p['key'] in web and family_only(p) else [i['path'] for i in p['images']]
                               or ([web[p['key']]['image']] if p['key'] in web else [])),
                    'sourceUrl': web[p['key']]['page'] if p['key'] in web and (not p['images'] or family_only(p)) else '',
                    'condition': p['condition'], 'documentSource': p['sources'][0]})
    json.dump(imp, open(os.path.join(ROOT, 'data', 'velmach-import.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    col.import_count = len(imp)
    write_reports(col, out, conflicts, missing, names, stock_rows)


ACRONYMS = {'MIL', 'AMS', 'SAE', 'NLGI', 'PTFE', 'RTV', 'PPG', 'UV', 'LED', 'ISO', 'BMS', 'DOD', 'USA', 'UK', 'II', 'III', 'IV', 'VI', 'CIC',
            'IPA', 'MEK', 'NAS', 'BAC', 'AN', 'MS', 'PR', 'PS', 'EA', 'HS', 'HT', 'LT', 'ML', 'KG', 'GR', 'GM', 'QT', 'OZ', 'GAL', 'GLN', 'LB',
            'LBS', 'MM', 'CM', 'PCS', 'PC', 'RTU', 'MC', 'AC', 'DC', 'VOC', 'NDT', 'ESD', 'PVC', 'PVF', 'PE', 'TDS', 'SDS', 'ATR', 'ATA', 'FAA',
            'EASA', 'OEM', 'ID', 'OD', 'CCM', 'CC', 'LTR', 'TCA', 'TSP', 'SP', 'NA', 'AERO', 'MRO', 'GSE', 'ELT', 'PBE', 'HVLP', 'ASTM', 'DIN', 'EN'}
SMALL = {'and', 'or', 'for', 'with', 'of', 'the', 'to', 'in', 'on', 'a', 'an', 'by', 'per'}


COMMON = {'oil', 'kit', 'box', 'cap', 'gun', 'cup', 'pad', 'bag', 'can', 'dry', 'wet', 'hot', 'air', 'red', 'top', 'low', 'new', 'mix',
          'jet', 'gel', 'wax', 'ink', 'tip', 'set', 'tub', 'jar', 'rod', 'bar', 'pin', 'nut', 'one', 'two', 'big', 'pro', 'max', 'all', 'use'}


def smart_case(t):
    parts = re.split(r'(\s+|[/(),–])', t)
    out = []
    for n, tok in enumerate(parts):
        if not tok or not re.search(r'[A-Za-z]', tok):
            out.append(tok); continue
        segs = tok.split('-')
        coded = len(segs) > 1 and any(re.search(r'\d', x) for x in segs)     # "C-AK", "EPC-1", "BAC-5010": a code, left as it is
        if re.search(r'\d', tok) or coded:
            out.append(tok); continue
        cased = []
        for x in segs:
            core = re.sub(r'[^A-Za-z]', '', x)
            if not core:
                cased.append(x)
            elif core.isupper() and (core in ACRONYMS or (len(core) <= 3 and core.lower() not in COMMON and core.lower() not in SMALL)):
                cased.append(x)                                              # short capitals are usually codes: LH, AK, SO, EPC
            elif core.lower() in SMALL and n > 0:
                cased.append(x.lower())
            else:
                cased.append(x[:1].upper() + x[1:].lower())
        out.append('-'.join(cased))
    return ''.join(out)


def write_title_changes(out):
    # proposals only (nothing is changed): spacing, glued words, and casing of all-capitals or all-lowercase titles
    vocab = collections.Counter(w for p in out for w in re.findall(r'[a-z]{4,}', (p['title'] + ' ' + p['description']).lower()))
    def unglue(tok):
        low = tok.lower()
        if len(low) < 9 or not low.isalpha() or vocab[low] >= 5 or not (tok.islower() or tok.isupper()):
            return tok                       # mixed case ("SuperMasterCharger") is how the maker writes it
        best = None
        for i in range(4, len(low) - 3):
            a, b = low[:i], low[i:]
            fa, fb = vocab[a] + vocab[a + 's'], vocab[b] + vocab[b + 's']      # "sanitizer" also counts "sanitizers"
            # both halves are known long words, or one is a common word (6+ letters) and the other a long word (8+)
            both = fa >= 1 and fb >= 1 and len(a) >= 6 and len(b) >= 6
            one = (fb >= 3 and len(b) >= 6 and len(a) >= 8) or (fa >= 3 and len(a) >= 6 and len(b) >= 8)
            if (both or one) and a != low and b != low:
                score = fa + fb
                if not best or score > best[0]:
                    best = (score, tok[:i], tok[i:])
        return f'{best[1]} {best[2]}' if best else tok
    rows = []
    for p in out:
        t0 = p['title']
        t = re.sub(r'\s+', ' ', t0).strip(' ,;-–')
        t = re.sub(r'\s+([,)])', r'\1', t)
        t = re.sub(r'\(\s+', '(', t)
        t = re.sub(r'\s*–\s*', ' – ', t)
        t = re.sub(r'\b[A-Za-z]{9,}\b', lambda m: unglue(m.group(0)), t)
        letters = re.sub(r'[^A-Za-z]', '', t)
        why = []
        if letters and (letters.isupper() or letters.islower()) and len(letters) >= 4:
            t2 = smart_case(t)
            if t2 != t:
                why.append('casing')
            t = t2
        if t != t0 and not why:
            why.append('spacing')
        elif t != t0 and re.sub(r'\s', '', t.lower()) != re.sub(r'\s', '', t0.lower()):
            why.append('spacing')
        if t != t0:
            rows.append([p['partNumber'], t0, t, ', '.join(why), p['sources'][0], p['key']])
        elif p['partNumber'] and t0 == p['partNumber']:
            rows.append([p['partNumber'], t0, '', 'title is only the part number: needs a name from you', p['sources'][0], p['key']])
    with open(os.path.join(REPORTS, 'title-changes.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['part number', 'current title', 'proposed title', 'what changed', 'source', 'id (do not edit)'])
        w.writerows(rows)
    return len(rows)


def web_priority(p):
    # 1: brand and part number; 2: a clear product name (a model designation with digits, e.g. "PR 1776 S"); 0: not searched
    if p['brand'] and p['partNumber']:
        return 1
    t = p['title']
    if len(t) <= 70 and len(t.split()) >= 2 and re.search(r'\b[A-Z]{0,6}[- ]?\d{2,}', t, re.I):
        return 2
    return 0


def write_reports(col, out, conflicts, missing, names, stock_rows):
    os.makedirs(REPORTS, exist_ok=True)
    total = len(out)
    mapped = [p for p in out if p['categoryParent']]
    # extraction summary
    per_file = collections.Counter(); per_file_kind = {}
    for p in out:
        for s in p['sources']:
            per_file[s.split(',')[0]] += 1
    lines = ['# Document extraction: dry run', '', 'Nothing has been imported and nothing on the site has changed.', '',
             f'- Rows read: {len(col.rows)}; products after merging by part number (or exact name when there is none): **{total}**',
             f'- With a part number: {sum(1 for p in out if p["partNumber"])}; without: {sum(1 for p in out if not p["partNumber"])}',
             f'- With a brand stated in the documents: {sum(1 for p in out if p["brand"])}; without: {sum(1 for p in out if not p["brand"])}',
             f'- With an image from the documents: {total - len(missing)}; without: {len(missing)} (reports/missing-images.csv)',
             f'- Category mapped onto the existing tree: {len(mapped)} (high {sum(p["categoryConfidence"] == "high" for p in mapped)}, medium {sum(p["categoryConfidence"] == "medium" for p in mapped)}, low {sum(p["categoryConfidence"] == "low" for p in mapped)}); not mapped: {total - len(mapped)} (reports/new-categories.md)',
             f'- Conflicts between documents: {len(conflicts)} (reports/conflicts.md)', '',
             '## Per source file', '', '| File | Rows read | Products it contributes | Notes |', '|---|---:|---:|---|']
    stock_files = {r['file'] for r in stock_rows}
    for f, c in col.files.items():
        hows = [f'{k[5:]}: {v} rows' for k, v in c.items() if k.startswith('how: ')]
        if f in stock_files:
            hows.append(f'stock list: not products; {col.enriched.get(f, 0)} rows added details to products in the main list')
        lines.append(f"| {f} | {c['rows']} | {per_file.get(f, 0)} | {'; '.join(col.notes.get(f, []) + hows)[:900].replace('|', '/')} |")
    lines += ['', '## Per category (existing tree), main list', '', '| Category | Subcategory | Products |', '|---|---|---:|']
    pc = collections.Counter((p['categoryParent'], p['categoryChild']) for p in mapped)
    for (a, b), n in sorted(pc.items()):
        lines.append(f'| {names(a)} | {names(a, b).split(" > ")[-1]} | {n} |')
    lines.append(f'| Not mapped (needs a category) | | {total - len(mapped)} |')
    own = [p for p in out if 'velmach' in p['sourceKinds']]
    cat_only = [p for p in out if 'velmach' not in p['sourceKinds']]
    lines += ['', '## By source group', '', '| Group | Products | With part # | With brand | With document image | Category mapped |', '|---|---:|---:|---:|---:|---:|']
    for label, ps in (('Your Velmach lists', own), ('Kept catalogs only (Boeing, Battery, Zip-Chem, Celeste cabin)', cat_only)):
        lines.append(f"| {label} | {len(ps)} | {sum(1 for p in ps if p['partNumber'])} | {sum(1 for p in ps if p['brand'])} | "
                     f"{sum(1 for p in ps if p['images'])} | {sum(1 for p in ps if p['categoryParent'])} |")
    lines += ['', f'Stock lists (lead-time, AeroDirect, seasonal, Regional Avionics): {len(stock_rows)} rows read, not used as products; '
              f'{col.stock_matched} main-list products got extra details from them (condition, aircraft type, alternate part number, description when empty).']
    random.seed(11)
    sample = random.sample(own, min(6, len(own))) + random.sample(cat_only, min(4, len(cat_only)))
    lines += ['', '## 10 random products (6 from your Velmach lists, 4 from the kept catalogs)', '', '| Title | Part number | Brand | Category | Image | Source |', '|---|---|---|---|---|---|']
    for p in sample:
        cat = names(p['categoryParent'], p['categoryChild']) if p['categoryParent'] else 'Not mapped'
        lines.append(f"| {p['title'][:60]} | `{p['partNumber']}` | {p['brand']} | {cat} | {p['images'][0]['path'] if p['images'] else '(none)'} | {p['sources'][0]} |")
    open(os.path.join(REPORTS, 'extraction-summary.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    # conflicts: only those the document dates cannot settle; settled ones go to conflicts-resolved.csv
    dl = ['| Document | Date used | Basis |', '|---|---|---|'] + [f'| {f} | {d or "unknown"} | {b} |' for f, (d, b) in sorted(DOC_DATES.items())]
    cl = ['# Conflicts to review', '', 'Rule: the most recent document is taken as correct. Listed here are only the cases where the documents have the',
          'same date (usually two rows of the same file) or a date is unknown. The site uses the first value until you decide.',
          f'{len(col.resolved)} other conflicts were settled by date: reports/conflicts-resolved.csv.', '', '## Document dates', ''] + dl + \
         ['', f'## {len(conflicts)} conflicts', '', '| Product | Field | Values (source) |', '|---|---|---|']
    for who, field, vals, chosen in conflicts:
        cl.append(f"| `{who}` | {field} | {' <br> '.join(f'{v[:80]} ({s_})' for v, s_, _ in vals).replace('|', '/')} |")
    with open(os.path.join(REPORTS, 'conflicts-resolved.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh); w.writerow(['product', 'field', 'value used', 'from (newest document)', 'date', 'other values (source)'])
        for who, field, vals, chosen in col.resolved:
            w.writerow([who, field, chosen[0], chosen[1], DOC_DATES.get(chosen[2], ('', ''))[0],
                        ' | '.join(f'{v} ({s_}, {DOC_DATES.get(f, ("", ""))[0]})' for v, s_, f in vals if v != chosen[0])])
    open(os.path.join(REPORTS, 'conflicts.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(cl) + '\n')
    # new categories
    import re as _re
    um = [p for p in out if not p['categoryParent']]
    by_doc = collections.Counter()
    for p in um:
        by_doc[p['documentCategories'][0] if p['documentCategories'] else '(no category in the documents)'] += 1
    by_sug = collections.Counter()
    for p in um:
        m = _re.search(r'would fit: (.*?)(;|$)', p['categoryReason'])
        by_sug[m.group(1) if m else 'no rule matched (needs a person)'] += 1
    nl = ['# Categories that need your decision', '', f'{len(um)} products did not clearly fit the existing tree. They are not imported until you decide.', '',
          '## Suggested new subcategories (from the product descriptions)', '', '| Suggestion | Products |', '|---|---:|']
    nl += [f'| {k} | {n} |' for k, n in by_sug.most_common()]
    nl += ['', '## Category names used in the documents (unmapped products)', '', '| Document category | Products |', '|---|---:|']
    nl += [f'| {k} | {n} |' for k, n in by_doc.most_common(150)]
    open(os.path.join(REPORTS, 'new-categories.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(nl) + '\n')
    # review files
    with open(os.path.join(REPORTS, 'category-review.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['title', 'part number', 'source', 'best-guess category', 'confidence', 'why', 'id (do not edit)'])
        for p in out:
            if not p['categoryParent']:
                w.writerow([p['title'], p['partNumber'], p['sources'][0], p['bestGuess'], p['bestGuessConfidence'], p['bestGuessWhy'], p['key']])
    with open(os.path.join(REPORTS, 'low-confidence-review.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['title', 'part number', 'source', 'category (published)', 'why', 'id (do not edit)'])
        for p in out:
            if p['categoryParent'] and p['categoryConfidence'] == 'low':
                w.writerow([p['title'], p['partNumber'], p['sources'][0], names(p['categoryParent'], p['categoryChild']), p['categoryReason'], p['key']])
    write_title_changes(out)
    bs = collections.defaultdict(list)
    for p in out:
        if p.get('brandSuggestion'):
            bs[p['brandSuggestion']].append(p)
    with open(os.path.join(REPORTS, 'brand-suggestions.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['suggested brand (from a TM / (R) heading)', 'products', 'example title', 'example source', 'approve? (yes / no / correct name)'])
        for name_, ps in sorted(bs.items(), key=lambda kv: -len(kv[1])):
            w.writerow([name_, len(ps), ps[0]['title'], ps[0]['sources'][0], ''])
    with open(os.path.join(REPORTS, 'missing-images.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh); w.writerow(['partNumber', 'title', 'brand', 'category', 'reason', 'source'])
        for p in missing:
            w.writerow([p['partNumber'], p['title'], p['brand'], names(p['categoryParent'], p['categoryChild']) if p['categoryParent'] else 'Not mapped', p['why'], p['sources'][0]])
    # web image queue: your own Velmach products without a document image, brand + part number first, then clear names
    queue = sorted(((web_priority(p), p) for p in out if 'velmach' in p['sourceKinds'] and not p['images']), key=lambda x: x[0] or 9)
    done = {}                                  # rows already searched are kept on re-runs
    wpath = os.path.join(REPORTS, 'web-images.csv')
    if os.path.exists(wpath):
        for r in csv.reader(open(wpath, encoding='utf-8-sig')):
            if len(r) >= 10 and r[0] != 'priority' and r[9] != 'pending':
                done[(r[1], r[2])] = r[:10]
    with open(wpath, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['priority', 'partNumber', 'title', 'brand', 'search', 'image URL', 'page URL', 'site (manufacturer / authorized distributor)', 'exact match shown on page', 'status', 'id'])
        for pr, p in queue:
            if pr:
                q = ' '.join(x for x in (p['brand'], p['partNumber'] or p['title']) if x)
                w.writerow((done.get((p['partNumber'], p['title'])) or [pr, p['partNumber'], p['title'], p['brand'], q, '', '', '', '', 'pending']) + [p['key']])
    col.web_queue = collections.Counter(pr for pr, _ in queue)
    print('\n'.join(lines[:12]))
    print('web queue', dict(col.web_queue))


if __name__ == '__main__':
    main()
