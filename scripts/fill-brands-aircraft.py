"""Fill in brands and compatible aircraft that the lists state but the import left empty: python scripts/fill-brands-aircraft.py

Brands: a product with no brand whose name starts with a brand name gets that brand (e.g. "MOLYKOTE 111 ..." -> Molykote).
Only the start of the name is used, only names in BRANDS below or already on the site, and a product that already has
a brand is never changed. Parts from the parts lists (aircraft-parts from the sheets) are left alone: their names are
part descriptions. 3M product lines (Scotch, Stikit, Roloc, Hookit) go to 3M.
Aircraft: a parts-list product whose "Aircraft" (Master Parts Inventory, "Aircraft Type") names a model in
data/aircraft.js gets that model in compatibleAircraft, so it shows under Shop by Aircraft.
Writes data/catalog/store/*.jsonl and reports/fill-brands-aircraft.csv; then run scripts/build-catalog.py.
"""
import csv, glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_lib as L

# leading words (upper case) -> brand name as the site shows it
BRANDS = {
    'HENKEL': 'Henkel', 'BONDERITE': 'Bonderite', 'ALODINE': 'Alodine', 'TRIBOLUBE': 'Tribolube', 'NAFTOSEAL': 'Naftoseal',
    'AERODUR': 'Aerodur', 'CEE BEE': 'CeeBee', 'CEE-BEE': 'CeeBee', 'MOLYKOTE': 'Molykote', 'ROCOL': 'Rocol', 'BOELUBE': 'Boelube',
    'ARDROX': 'Ardrox', 'LPS': 'LPS', 'SIKA': 'Sika', 'BRAYCOTE': 'Braycote', 'BRAYCO': 'Brayco', 'ALUMIGRIP': 'Alumigrip',
    'ARALDITE': 'Araldite', 'CYCOM': 'Cycom', 'HUMISEAL': 'HumiSeal', 'AVIOX': 'Aviox', 'ORAPI': 'Orapi', 'TURCO': 'Turco',
    'EPIBOND': 'Epibond', 'PRAXAIR': 'Praxair', 'SOFICOR': 'Soficor', 'PERMATEX': 'Permatex', 'AKZO': 'AkzoNobel',
    'AKZONOBEL': 'AkzoNobel', 'EVERLUBE': 'Everlube', 'DOWSIL': 'Dowsil', 'SONTARA': 'Sontara', 'DAUBERT': 'Daubert',
    'HYDRAUNICOIL': 'Hydraunicoil', 'TURBONYCOIL': 'Turbonycoil', 'NYCOLUBE': 'Nycolube', 'BLUESTAR': 'Bluestar Silicones',
    'MCGEAN': 'McGean', 'EXXON': 'Exxon', 'TESA': 'tesa', 'PRC-DESOTO': 'PRC-DeSoto', 'PRC DESOTO': 'PRC-DeSoto',
    'SHERWIN-WILLIAMS': 'Sherwin-Williams', 'INSTABOND': 'Instabond', 'STYCAST': 'Stycast', 'FLAMEMASTER': 'Flamemaster',
    'NUSIL': 'NuSil', 'FUCHS': 'Fuchs', 'METAFLEX': 'Metaflex', 'LORD': 'LORD', 'MAPAERO': 'Mapaero', 'URALANE': 'Uralane',
    'ACCUSPRAY': 'Accuspray', 'JEHIER': 'Jehier', 'PLIOBOND': 'Pliobond', 'INTERGARD': 'Intergard', 'MONOPOL': 'Monopol',
    'HYJET': 'HyJet', 'EASTMAN': 'Eastman', 'ACHESON': 'Acheson', 'EPON': 'EPON', 'TECTYL': 'Tectyl', 'ACF-50': 'ACF-50',
    'CHEMI-PRO': 'Chemi-Pro', 'WD-40': 'WD-40', 'SCAPA': 'Scapa', 'SAFT': 'Saft', 'MANKIEWICZ': 'Mankiewicz',
    'TEROSON': 'Teroson', 'HEXPLY': 'HexPly', 'ACCU-LUBE': 'Accu-Lube', 'PHILIPS': 'Philips', 'ARLON': 'Arlon LLC',
    'SCOTCH': '3M', 'SCOTCH-WELD': '3M', 'SCOTCH-BRITE': '3M', 'SCOTCH-GRIP': '3M', 'SCOTCHBLOCK': '3M', 'SCOTCHKOTE': '3M',
    'STIKIT': '3M', 'ROLOC': '3M', 'HOOKIT': '3M',
}
# site brands too generic to read from the start of a name
SKIP_SITE = {'eagle', 'champion', 'sentinel', 'axon', 'kingston', 'tpi', 'nav aids', 'carberto', 'kunz'}

# "Aircraft Type" as written in the Master Parts Inventory -> (make, model) in data/aircraft.js
AIRCRAFT = [
    (r'^(falcon 2000|f2000)\b', ('Dassault', 'Falcon 2000')), (r'^falcon 900ex\b', ('Dassault', 'Falcon 900EX')),
    (r'^falcon 20\b', ('Dassault', 'Falcon 20/200')), (r'^hawker 800', ('Textron Aviation', 'Hawker 800/900')),
    (r'^gulfstream giv\b', ('Gulfstream', 'GIV')), (r'^gulfstream 300\b', ('Gulfstream', 'G300')),
    (r'^(747|757|767|777|787)$', None), (r'^dornier 328$', ('Dornier', '328')), (r'^jetstar$', ('Lockheed Martin', 'JetStar')),
    (r'^lear 45$', ('Bombardier', 'Learjet 45/75')), (r'^lear 60$', ('Bombardier', 'Learjet 60')),
]


def ac_id(make, model):
    s = lambda x: re.sub(r'^-+|-+$', '', re.sub(r'[^a-z0-9]+', '-', str(x).lower().replace('&', ' ')))
    return s(make) + '/' + s(model)


def load_aircraft_ids():
    src = open('data/aircraft.js', encoding='utf-8').read()
    ids = set()
    for make, models in re.findall(r'make: "([^"]+)", models: \[([^\]]*)\]', src):
        for m in re.findall(r'"([^"]+)"', models):
            ids.add(ac_id(make, m))
    return ids


def site_brands():
    src = open('data/brands.js', encoding='utf-8').read()
    return [n for n in re.findall(r'"name": "([^"]+)"', src) if n.lower() not in SKIP_SITE]


def main():
    lead = {k.upper(): v for k, v in BRANDS.items()}
    for n in site_brands():
        lead.setdefault(n.upper(), n)
    keys = sorted(lead, key=len, reverse=True)
    ac_ids = load_aircraft_ids()
    log, nb, na = [], 0, 0
    for f in sorted(glob.glob('data/catalog/store/*.jsonl')):
        rows = [json.loads(l) for l in open(f, encoding='utf-8') if l.strip()]
        changed = False
        for r in rows:
            sheet_part = r['key'].startswith('sheet:') and r.get('categoryParent') == 'aircraft-parts'
            if not r.get('brand') and not sheet_part:
                name = re.sub(r'[^A-Z0-9\- ]', ' ', (r.get('title') or '').upper())
                name = re.sub(r'\s+', ' ', name).strip()
                hit = next((k for k in keys if name == k or name.startswith(k + ' ')), None)
                if hit:
                    b = lead[hit]
                    r['brand'], r['brandSlug'], r['brandBasis'] = b, L.slugify(b), 'name'
                    for ext in ('svg', 'png', 'webp'):
                        logo = f'public/brands/{r["brandSlug"]}.{ext}'
                        if r.get('placeholderKind') == 'company logo' and os.path.exists(logo):
                            r['placeholder'], r['placeholderKind'] = logo, 'brand logo'
                            break
                    log.append(('brand', r['slug'], r['title'], b)); nb += 1; changed = True
            listed = (r.get('aircraftListed') or '').strip()
            if listed and not r.get('compatibleAircraft'):
                low = listed.lower()
                for pat, mm in AIRCRAFT:
                    if re.search(pat, low):
                        i = ac_id('Boeing', low) if mm is None else ac_id(*mm)
                        if i in ac_ids:
                            r['compatibleAircraft'] = [i]
                            log.append(('aircraft', r['slug'], r['title'], i)); na += 1; changed = True
                        break
        if changed:
            with open(f, 'w', encoding='utf-8', newline='\n') as w:
                for r in rows:
                    w.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
    os.makedirs('reports', exist_ok=True)
    with open('reports/fill-brands-aircraft.csv', 'w', encoding='utf-8-sig', newline='') as w:
        c = csv.writer(w); c.writerow(['what', 'slug', 'title', 'value']); c.writerows(log)
    print(f'brands filled: {nb}; aircraft linked: {na}')


if __name__ == '__main__':
    main()
