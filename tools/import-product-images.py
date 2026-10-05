"""Import product images that are still pending into assets/products/.

Products whose image could not be imported during the migration keep the original URL in "sourceImage"
(data/products.json). This script downloads those files (original bytes, no recompression), sets "image",
clears "sourceImage" and rebuilds data/products.js.

Every download is validated before it is saved: the response must be an image (Content-Type and file signature),
of a reasonable size, and it is saved with the extension of its real format. A verification/HTML page is never
saved. Files are requested one at a time with a pause, and the run stops as soon as the source answers with a
non-image response, so it never works around the source's protection.

Run:  python tools/import-product-images.py [--sap FG02240,FG02210 | --id-file verified-ids.txt] [--limit N]
"""
import json, os, subprocess, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC, DEST = os.path.join(ROOT, 'data', 'products.json'), os.path.join(ROOT, 'assets', 'products')
SIGNATURES = [(b'\x89PNG\r\n\x1a\n', 'png'), (b'\xff\xd8\xff', 'jpg'), (b'GIF87a', 'gif'), (b'GIF89a', 'gif')]
MIN_BYTES = 1024

def arg(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None

def image_kind(body):
    for sig, ext in SIGNATURES:
        if body.startswith(sig): return ext
    if body[:4] == b'RIFF' and body[8:12] == b'WEBP': return 'webp'
    return None

def complete(body, kind):
    # a cut-off upload still has a valid signature but renders blank: require the format's end marker
    if kind == 'jpg': return b'\xff\xd9' in body[-64:]
    if kind == 'png': return b'IEND' in body[-32:]
    return True

def local_name(url, kind):
    base = urllib.parse.unquote(url.rsplit('/', 1)[-1])
    stem, ext = os.path.splitext(base)
    ext = ext.lower().lstrip('.')
    # keep the source file name; correct the extension when it does not match the real format
    return base if (ext == kind or (kind == 'jpg' and ext == 'jpeg')) else f'{stem}.{kind}'

only = set(arg('--sap').split(',')) if arg('--sap') else set(open(arg('--id-file')).read().split()) if arg('--id-file') else None
limit = int(arg('--limit')) if arg('--limit') else None
products = json.load(open(SRC, encoding='utf-8'))
pending = [p for p in products if p.get('sourceImage') and not p.get('image') and not {'source-image-not-an-image', 'source-image-damaged'} & set(p.get('review') or []) and (not only or p.get('sap') in only or p['id'] in only)]
print(f'{len(pending)} products waiting for an image')
os.makedirs(DEST, exist_ok=True)
done, invalid, stopped = 0, [], None
try:
    for p in pending[:limit]:
        url = p['sourceImage']
        req = urllib.request.Request(urllib.parse.quote(url, safe=':/'), headers={'User-Agent': 'Mozilla/5.0 (Velmach catalogue import)'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r: ctype, body = r.headers.get('Content-Type', ''), r.read()
        except Exception as e:
            stopped = f'{p["id"]}: {e}'; break
        kind = image_kind(body)
        if not kind and ('html' in ctype or body.lstrip()[:15].lower().startswith((b'<!doctype', b'<html'))):
            stopped = f'{p["id"]}: HTML response instead of an image ({len(body)} bytes), likely a verification page'; break
        if not kind:   # the source links a non-image file (e.g. a .zip) as this product's image: skip it, never save it
            invalid.append(f'{p["id"]}: not an image ({ctype or "unknown type"}, {len(body)} bytes)')
            p['review'] = [f for f in (p.get('review') or []) if f != 'image-pending'] + ['source-image-not-an-image']
            time.sleep(1.2); continue
        if not complete(body, kind):
            invalid.append(f'{p["id"]}: truncated {kind} file at the source ({len(body)} bytes)')
            p['review'] = [f for f in (p.get('review') or []) if f != 'image-pending'] + ['source-image-damaged']
            time.sleep(1.2); continue
        if not ctype.startswith('image/') or len(body) < MIN_BYTES:
            invalid.append(f'{p["id"]}: {ctype}, {len(body)} bytes'); continue
        name = local_name(url, kind)
        open(os.path.join(DEST, name), 'wb').write(body)
        p['image'] = 'assets/products/' + name; p['sourceImage'] = None
        p['review'] = [f for f in (p.get('review') or []) if f not in ('image-pending', 'no-image-at-source')] or None
        done += 1
        if done % 100 == 0:
            json.dump(products, open(SRC, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); print(f'imported {done}', flush=True)
        time.sleep(1.2)
finally:
    json.dump(products, open(SRC, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'build-products-js.py')], check=True)
    print(f'imported {done}; invalid {len(invalid)}; {len(pending) - done - len(invalid)} still pending')
    for x in invalid: print('  invalid:', x)
    if stopped: print('stopped:', stopped)
