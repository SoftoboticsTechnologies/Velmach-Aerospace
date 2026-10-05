"""Builds the vector maps used on the site from Natural Earth 1:50m admin-0 countries (public domain):
  assets/home/region-map.svg  home page Strategic Location (Europe, Africa, Middle East, South Asia)
  assets/home/uae-map.svg     contact page close-up of the UAE around Ajman
Land, country borders and the UAE highlighted. Each projection and extent must match the overlay
coordinates in the page that uses it (index.html routes and labels, contact.dc.html marker).

usage: python tools/build-home-map.py [path/to/ne_50m_admin_0_countries.geojson]
Without an argument the GeoJSON is downloaded from the Natural Earth repository.
"""
import json, math, os, sys, urllib.request

LON0, LON1, LAT0, LAT1 = -20.0, 100.0, -5.0, 62.0    # extent (deg); LAT0 trims the frame to a wider aspect
KX = 9.06                                             # px per deg lon (10 * cos 25deg)
KY = 10.0                                             # px per deg lat
EPS = 0.55                                            # outline simplification tolerance (px)
HIGHLIGHT = {'ARE'}                                   # United Arab Emirates
SRC = 'https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@master/geojson/ne_50m_admin_0_countries.geojson'
HOME = os.path.join(os.path.dirname(__file__), '..', 'assets', 'home')
LAND, BORDER, UAE = '#FBFBF9', '#C9D0D6', '#0759A5'


def load(path):
    if path:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    with urllib.request.urlopen(SRC) as r:
        return json.loads(r.read().decode('utf-8'))


V = {}   # active view: extent and scale


def proj(lon, lat):
    return ((lon - V['lon0']) * V['kx'], (V['lat1'] - lat) * V['ky'])


def rdp(pts, eps):
    """Ramer-Douglas-Peucker on a closed ring (iterative)."""
    if len(pts) < 4:
        return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1; L = math.hypot(dx, dy) or 1e-9
        best, idx = 0.0, -1
        for i in range(a + 1, b):
            d = abs(dy * pts[i][0] - dx * pts[i][1] + x2 * y1 - y2 * x1) / L
            if d > best:
                best, idx = d, i
        if best > eps and idx > 0:
            keep[idx] = True; stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def simplify_ring(pts):
    # a closed ring starts and ends on the same point, so split it at the point farthest from the start
    x0, y0 = pts[0]
    far = max(range(len(pts)), key=lambda i: (pts[i][0] - x0) ** 2 + (pts[i][1] - y0) ** 2)
    if far == 0:
        return pts
    return rdp(pts[:far + 1], V['eps'])[:-1] + rdp(pts[far:], V['eps'])


def ring_path(ring):
    pts = simplify_ring([proj(c[0], c[1]) for c in ring])
    if len(pts) < 3:
        return ''
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    if max(xs) - min(xs) < 1.2 and max(ys) - min(ys) < 1.2:
        return ''                                     # sub-pixel islands
    out, px, py = [], None, None
    for i, (x, y) in enumerate(pts):
        x, y = round(x, 1), round(y, 1)
        if (x, y) == (px, py):
            continue
        out.append(('M' if i == 0 else 'L') + ('%g %g' % (x, y)))
        px, py = x, y
    return ''.join(out) + 'Z'


def in_extent(ring):
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
    return not (max(xs) < V['lon0'] - 2 or min(xs) > V['lon1'] + 2 or max(ys) < V['lat0'] - 2 or min(ys) > V['lat1'] + 2)


def render(gj, out, lon0, lon1, lat0, lat1, kx, ky, eps, stroke, uae_fill=UAE):
    V.update(lon0=lon0, lon1=lon1, lat0=lat0, lat1=lat1, kx=kx, ky=ky, eps=eps)
    land, hi = [], []
    for ft in gj['features']:
        g = ft['geometry']
        if not g:
            continue
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        d = ''.join(ring_path(r) for poly in polys for r in poly if in_extent(r))
        if not d:
            continue
        (hi if ft['properties'].get('ADM0_A3') in HIGHLIGHT else land).append(d)
    W = round((lon1 - lon0) * kx); H = round((lat1 - lat0) * ky)
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">'
           '<path d="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="round"/>'
           '<path d="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="round"/></svg>\n') % (
        W, H, W, H, ''.join(land), LAND, BORDER, stroke, ''.join(hi), uae_fill, UAE, stroke)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(svg)
    print('wrote', out, len(land) + len(hi), 'countries', W, 'x', H, len(svg) // 1024, 'KB')


def main():
    gj = load(sys.argv[1] if len(sys.argv) > 1 else None)
    render(gj, os.path.join(HOME, 'region-map.svg'), LON0, LON1, LAT0, LAT1, KX, KY, EPS, '.8')
    # UAE close-up: 52-58.6 E, 22.4-27.4 N at 120 px/deg (lon scaled by cos 25deg); Ajman 55.44 E 25.41 N
    render(gj, os.path.join(HOME, 'uae-map.svg'), 52.0, 58.6, 22.4, 27.4, 108.8, 120.0, .35, '1.2', uae_fill='#DCE7F3')


if __name__ == '__main__':
    main()
