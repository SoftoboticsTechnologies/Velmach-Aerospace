"""Proposes a new category and subcategory for every product of the previous (hidden) catalogue.

python scripts/map-old-categories.py   ->  reports/category-mapping.csv  (nothing on the site changes)

Reads backup/old-products.json only. Each product is matched on its own description, name and old category with the
keyword rules below; nothing is fetched, invented or rewritten. The first matching rule wins; a second rule pointing
somewhere else is noted as the alternative. Confidence:
  high    a specific keyword that agrees with the product's old category
  medium  a specific keyword, but the old category differs, or the alternative is in another top-level category
  low     a weak keyword (still assigned, worth a look)
Products no rule places with confidence go to "Needs Review" (kept hidden). Where the tree has no fitting subcategory
(sealants, paints, adhesives, general hardware ...), the reason names the subcategory that would fit; none is created.
"""
import csv, json, os, re, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import catalog_lib as L

GSE, AVN, TLS, PRT, CON, PLT, SAF = ('ground-support-equipment', 'avionics', 'aircraft-tooling', 'aircraft-parts',
                                     'consumables', 'pilot-supplies', 'safety-equipment')
ANY = None   # rule is high confidence whatever the old category

# (regex on the upper-cased description + name, parent, child, old categories that make it "high", cap)
# cap: 'high' (default), 'medium' or 'low' limits the confidence of a rule that is less specific.
RULES = [
    # ---- test sets and lifting gear before the systems they test or lift ----
    (r'TEST SET|RAMP TEST', AVN, 'test-equipment', ANY, 'medium'),
    (r'FUEL TEST KIT|MICROB ?MONITOR|WATER DETECT|AQUADIS', GSE, 'fueling-gse', ANY, 'medium'),
    (r'\bHOIST', GSE, 'lifting-equipment', ANY, 'medium'),
    (r'O2 CYLINDER|OXYGEN (CYLINDER|BOTTLE)', PRT, 'cockpit-cabin-parts', ANY, 'medium'),
    # ---- tooling first: tool words would otherwise match the materials they apply ----
    (r'SEALANT GUN|CARTRIDGE GUN|SEMCO|DISPENSING GUN|APPLICATION GUN|MIXING NOZZLE|DISPENSER', TLS, 'sealant-adhesive-application-tools', ANY, 'medium'),
    (r'TAPE MEASURE|MEASURING TAPE', TLS, 'tape-measures', ANY, 'high'),
    (r'CRIMP', TLS, 'crimping-tools', ANY, 'high'),
    (r'WIRE STRIP', TLS, 'wire-strippers', ANY, 'high'),
    (r'COUNTERSINK', TLS, 'countersink-drill-bits', ANY, 'medium'),
    (r'DRILL BIT|\bDRILL\b', TLS, 'drill-bits', ANY, 'medium'),
    (r'SAW BLADE|HACKSAW', TLS, 'saw-blades', ANY, 'high'),
    (r'TORQUE WRENCH|^(?!.*GAUGE).*\bWRENCH|SPANNER', TLS, 'wrenches', ANY, 'high'),
    (r'PLIER', TLS, 'pliers', ANY, 'high'),
    (r'SCREWDRIVER', TLS, 'screwdrivers', ANY, 'high'),
    (r'HAMMER|MALLET', TLS, 'hammers', ANY, 'high'),
    (r'KNIFE|SCALPEL', TLS, 'knives', ANY, 'high'),
    (r'ABRASIVE|SANDPAPER|SAND PAPER|EMERY|SCOTCH-?BRITE|SANDING|GRINDING DISC|FLAP DISC|POLISHING DISC|CUT-?OFF WHEEL|GRINDING WHEEL', TLS, 'abrasives', ANY, 'high'),
    (r'MULTIMETER|INSULATION TESTER|MEGGER|BONDING METER|MILLIOHM', TLS, 'specialty-testers', ANY, 'high'),
    (r'LOAD CELL|FORCE GAUGE', TLS, 'force-gauges', ANY, 'medium'),
    (r'THERMOMETER|THERMOCOUPLE|INFRARED THERM', TLS, 'temperature-measurement', ANY, 'high'),
    (r'MANOMETER', TLS, 'manometers', ANY, 'high'),
    (r'BORESCOPE|BORE ?SCOPE', TLS, 'borescopes', ANY, 'high'),
    (r'CALIPER|MICROMETER|FEELER GAUGE', TLS, 'measurement-tools', ANY, 'high'),
    (r'MARKER|MARKING PEN|SCRIBE', TLS, 'marking-tools', ANY, 'medium'),
    (r'FLASHLIGHT|TORCH LIGHT|INSPECTION (LIGHT|LAMP|MIRROR)', TLS, 'inspection-lights', ANY, 'high'),
    (r'TOOL ?BOX|TOOL CHEST|TOOL KIT|TOOLKIT', TLS, 'general-tool-kits', ANY, 'medium'),
    (r'TAP AND DIE|THREAD REPAIR KIT|\bTAP SET\b|DIE SET', TLS, 'threading-tools', ANY, 'medium'),
    (r'INSPECTION GAUGE|GAP GAUGE|GO ?/ ?NO-?GO|\bGAGE\b', TLS, 'measurement-tools', ANY, 'medium'),
    (r'REAMER', TLS, 'cutting-tools', ANY, 'medium'),
    (r'LAYOUT FLUID', TLS, 'marking-tools', ANY, 'medium'),
    (r'EXTRACTION TOOL|EXTRACTOR|INSERTION TOOL|REMOVAL TOOL|INSTALLATION TOOL|\bTOOL\b', TLS, 'other-aircraft-tools', ANY, 'low'),
    # ---- safety ----
    (r'FIRST AID', SAF, 'first-aid-kits', ANY, 'high'),
    (r'FIRE EXTINGUISH', SAF, 'fire-extinguishers', ANY, 'high'),
    (r'GOGGLE|SAFETY GLASSES|SAFETY SPECTACLE', SAF, 'goggles', ANY, 'high'),
    (r'EAR ?PLUG|EAR ?MUFF|EAR DEFENDER|HEARING PROTECT', SAF, 'hearing-protection', ANY, 'high'),
    (r'\bGLOVES?\b|COVERALL|SAFETY SHOE|SAFETY BOOT|APRON', SAF, 'safety-apparel', ANY, 'high'),
    (r'HI-?VIS|SAFETY VEST|REFLECTIVE VEST', SAF, 'safety-vests', ANY, 'high'),
    (r'LIFE ?VEST|LIFE ?JACKET', SAF, 'life-vests', ANY, 'high'),
    (r'SMOKE HOOD|PROTECTIVE BREATHING', SAF, 'protective-breathing-equipment-pbe', ANY, 'high'),
    (r'SAFETY CONE|TRAFFIC CONE|MARSHAL', SAF, 'marshaling-wands-safety-cones', ANY, 'high'),
    (r'DOWN ?LOCK PIN|GEAR PIN|REMOVE BEFORE FLIGHT', SAF, 'downlock-pins', ANY, 'high'),
    # ---- consumables with a clear home ----
    (r'SAFETY WIRE|LOCK ?WIRE|SHEAR WIRE', CON, 'safety-wire-lockwire', ('parts', 'other', 'tapes'), 'high'),
    (r'\bTAPES?\b|TAPE-|\bTAPE\d', CON, 'tape', ('tapes', 'other', 'adhesives'), 'high'),
    (r'SHOCK STRUT|LANDING GEAR FLUID', CON, 'landing-gear-fluid', ('lubricants', 'chemicals', 'other'), 'high'),
    (r'SKYDROL|HYJET|HYDRAULIC (OIL|FLUID)|5606|83282|87257|AEROSHELL FLUID 4\b|NYCO.?FH', CON, 'hydraulic-fluid', ('lubricants', 'chemicals', 'other'), 'high'),
    (r'TURBINE OIL|ENGINE OIL|JET OIL|TURBO OIL|PISTON ENGINE OIL|MOBIL ?JET|AEROSHELL (OIL|TURBINE|W ?\d)|\bW ?(80|100|120)\b|23699|7808|\bASTO\b|ETO ?2380|BP ?TURBO|TURBONYCOIL|NYCOIL', CON, 'engine-oil', ('lubricants', 'other'), 'high'),
    (r'GREASE', CON, 'aircraft-grease', ('lubricants', 'chemicals', 'other'), 'high'),
    (r'CORROSION (INHIBIT|PREVENT)|ANTI-?CORROSION|CORROSION PREVENTIVE|RUST (PREVENT|INHIBIT)|ACF-?50|CORBAN|\bLPS\b|DINITROL|RUST ?LICK|WATER DISPLAC|WD-?40|RUST REMOVER', CON, 'anti-corrosion-lubricants', ('chemicals', 'lubricants', 'other'), 'high'),
    (r'ANTI-?SEIZE', CON, 'anti-corrosion-lubricants', ('chemicals', 'lubricants', 'other'), 'medium'),
    (r'FUEL ADDITIVE|BIOBOR|PRIST|ANTI-?ICING ADDITIVE|FSII|MICROBIOCIDE|BIOCIDE', CON, 'fuel-additives', ('chemicals', 'other'), 'high'),
    (r'CALIBRATION FLUID|CALIBRATING FLUID', CON, 'calibration-fluids', ANY, 'high'),
    (r'COOLANOL|DIELECTRIC (COOLANT|FLUID)', CON, 'dielectric-coolants', ANY, 'high'),
    (r'DE-?ICING|ANTI-?ICING FLUID|KILFROST|SAFEWING', CON, 'deicing-anti-icing-fluids', ANY, 'high'),
    (r'COMPRESSOR WASH|ENGINE WASH|TURBINE (ENGINE )?CLEAN|GAS PATH CLEAN', CON, 'engine-compressor-washer-fluid', ('cleaners', 'chemicals'), 'high'),
    (r'LEAK DETECT|SNOOP|LEAK ?TEC', CON, 'leak-detector-fluid', ('chemicals', 'other'), 'high'),
    (r'CAN OPENER|POUR SPOUT', CON, 'can-openers-caps', ANY, 'high'),
    (r'LUBRICATING OIL|GEAR OIL|INSTRUMENT OIL|SILICONE OIL|\bOIL\b(?! (FILTER|SEAL|COOLER|PUMP))', CON, 'lubricating-oils', ('lubricants',), 'medium'),
    (r'LUBRICANT|DRY FILM|MOLYBDENUM|MOLY\b', CON, 'lubricating-oils', ('lubricants',), 'medium'),
    (r'CLEANER|CLEANING|DEGREAS|DETERGENT|\bSOAP\b|POLISH|\bWIPES?\b|DESCALER|SCALER|DISHWASH', CON, 'aircraft-hangar-cleaning-supplies', ('cleaners', 'chemicals'), 'high'),
    (r'SOLVENT(?![ -]?(FREE|RESISTANT|BASED))', CON, 'aircraft-hangar-cleaning-supplies', ('cleaners',), 'low'),
    (r'ACRYLIC SHEET|POLYCARBONATE|PERSPEX|PLEXIGLAS|NYLON (ROD|SHEET)|PTFE (ROD|SHEET)|PLASTIC SHEET', CON, 'plastics', ANY, 'medium'),
    # ---- aircraft parts with a clear system ----
    (r'AIR FILTER|INDUCTION FILTER|FILTER.{0,12}\bAIR\b', PRT, 'air-filters', ('parts',), 'high'),
    (r'FUEL.{0,25}(FILTER|PUMP|VALVE|CAP|DRAIN|SENSOR|NOZZLE|TANK|PROBE|QUANTITY|LINE|STRAINER)|(FILTER|PUMP|VALVE|CAP|DRAIN|SENSOR|NOZZLE|TANK|PROBE|STRAINER).{0,15}FUEL', PRT, 'fuel-system-parts', ('parts',), 'high'),
    (r'HYDRAULIC', PRT, 'hydraulic-parts', ('parts',), 'medium'),
    (r'\bLAMPS?\b|\bBULBS?\b|INCANDESCENT|HALOGEN|\bLED\b|\bLIGHT\b', PRT, 'lighting', ('parts',), 'high'),
    (r'\bTIRES?\b|\bTYRES?\b|INNER TUBE', PRT, 'aircraft-tires', ('parts',), 'high'),
    (r'BATTERY|BATTERIES', PRT, 'aircraft-batteries', ('parts',), 'high'),
    (r'\bELT\b|EMERGENCY LOCATOR|LOCATOR BEACON', PRT, 'emergency-locator-transmitters-elts', ('parts',), 'high'),
    (r'\bBRAKES?\b|\bWHEEL\b(?! CHOCK)', PRT, 'wheels-brakes', ('parts',), 'high'),
    (r'WINDSHIELD|WINDSCREEN|\bWINDOW', PRT, 'windows-windshields', ('parts',), 'high'),
    (r'HOSE ASS(Y|EMBLY)', PRT, 'hose-assemblies', ('parts',), 'high'),
    (r'\bHOSE\b|\bDUCT', PRT, 'ducting-hoses', ('parts',), 'medium'),
    (r'LANDING GEAR|\bSTRUT\b|\bAXLE', PRT, 'landing-gear-parts', ('parts',), 'high'),
    (r'ALTERNATOR|GENERATOR BRUSH', PRT, 'alternator-parts', ('parts',), 'high'),
    (r'GOVERNOR', PRT, 'prop-governor-parts', ('parts',), 'high'),
    (r'SPARK PLUG|IGNITER|IGNITION|CYLINDER|PISTON\b|CRANKSHAFT|CAMSHAFT|TURBOCHARGER|MAGNETO|STARTER|\bENGINE\b|OIL FILTER|EXHAUST', PRT, 'engine-parts', ('parts',), 'medium'),
    (r'OXYGEN MASK|\bSEAT\b|ARMREST|CARPET|CURTAIN|PLACARD|\bCABIN\b|COCKPIT|INSTRUMENT PANEL|\bKNOB\b|LAVATORY|GALLEY', PRT, 'cockpit-cabin-parts', ('parts',), 'medium'),
]
RULES = [(re.compile(rx), p, c, olds, cap) for rx, p, c, olds, cap in RULES]

# no subcategory in the tree fits these: they stay in Needs Review with a suggestion (in this order)
REVIEW = [
    (r'SEALANT|SEALENT|SEAL COATING|NAFTOSEAL|\bPR-?\d{3,4}|\bPS ?8\d\d|\bRTV\b|FIREWALL SEAL|AEROSPACE SEAL', 'Consumables > Sealants (new subcategory)'),
    (r'PRIMER|\bPAINT|TOPCOAT|COATING|THINNER|HARDENER|HARDNER|ACTIVATOR|ENAMEL|LACQUER|VARNISH|DESOTHANE|ALODINE|CHROMATE|ALEXIT|AEROWAVE|POLYURETHANE|\bBASE\b', 'Consumables > Paints & Coatings (new subcategory)'),
    (r'ADHESIVE|EPOXY|THREADLOCK|LOCTITE|ARALDITE|\bGLUE|BONDING|CYANOACRYLATE|STRUCTURAL|POTTING|PUTTY|FILLER|COMPOUND|RETAINING', 'Consumables > Adhesives & Compounds (new subcategory)'),
    (r'PENETRANT|DEVELOPER|MAGNETIC PARTICLE|\bNDT\b|DYE CHECK|MET-L-CHEK', 'Consumables > NDT Chemicals (new subcategory)'),
    (r'CARBON FIB|FIBERGLASS|FIBREGLASS|PRE-?PREG|\bCLOTH\b|FABRIC|BREATHER|BAGGING|PEEL PLY|RELEASE FILM|GLASS BUBBLE|MYLAR', 'Consumables > Composite Materials (new subcategory)'),
    (r'CLAD SHEET|ALUMINIUM SHEET|ALUMINUM SHEET|\bSHEET\b|STAINLESS STEEL|\bROD\b|\bBAR\b', 'Raw Materials (new category)'),
    (r'SAP LICENSE', 'not a physical product (software licence): consider leaving it hidden'),
    (r'RELEASE AGENT|MOLD RELEASE|MOULD RELEASE|ADHESION PROMOTER|REAGENT|\bACID\b|HYDROXIDE|ACETONE|KETONE|ALCOHOL|ISOPROPYL|\bMEK\b|DESICCANT|DESICANT|ELECTROLYTE|POWDER|COOLANT|REPELL?ANT|REPELLENT|REMOVER|ACCELERATOR|PASTE', 'Consumables > Chemicals (new subcategory)'),
    (r'O-?RING|\bORING|PACKING|\bSEAL\b|\bSEALS\b|GASKET', 'Aircraft Parts > Seals & O-Rings (new subcategory)'),
    (r'SCREW|BOLT|\bNUTS?\b|WASHER|RIVET|COTTER|\bPINS?\b|INSERT|HELI-?COIL|HELICA|SPACER|BUSHING|BEARING|\bSHIMS?\b|SPRING|CLAMP|\bCLIPS?\b|FITTING|UNION|ELBOW|GROMMET|\bSTUD|RETAINER|COLLAR|LOCK ?RING|SNAP RING|\bCAPS?\b|\bPLUG\b|\bPLATE\b|\bRING\b', 'Aircraft Parts > Hardware & Fasteners (new subcategory)'),
    (r'CABLE TIE|TIE ?WRAP|LACING|SHRINK|SLEEV|TERMINAL|CONTACT|CONNECTOR|SPLICE|\bWIRE\b|\bCABLE\b', 'Aircraft Parts > Electrical Hardware (new subcategory)'),
    (r'\bFILTER|\bELEMENT\b|FILTRANT', 'Aircraft Parts: filter for an unnamed system'),
    (r'SWITCH|RELAY|SENSOR|HINGE|\bPANEL\b|FAIRING|CONTROLS|INSULATOR|WEIGHT|BOBBIN|HI-?LOK|HI-?LITE|TERMINAL BLOCK', 'Aircraft Parts: no matching subcategory'),
]
REVIEW = [(re.compile(rx), s) for rx, s in REVIEW]
RANK = {'low': 0, 'medium': 1, 'high': 2}
MATERIAL = re.compile(r'SEALANT|SEALENT|PRIMER|\bPAINT|COATING|ADHESIVE|EPOXY|COOLANT|LACQUER|THINNER|HARDENER')
TOOLS_FOR_MATERIALS = {'sealant-adhesive-application-tools', 'marking-tools', 'tape'}
MATERIAL_STRONG = re.compile(r'SEALANT|SEALENT|PRIMER|\bPAINT|ADHESIVE|EPOXY')


def text_of(p):
    return ' '.join(str(p.get(k) or '') for k in ('desc_en', 'name_en')).upper().replace('&NBSP;', ' ')


def classify(p, names):
    t, old = text_of(p), p.get('category')
    hits = []
    for rx, parent, child, olds, cap in RULES:
        m = rx.search(t)
        if m and (parent, child) not in [(h[0], h[1]) for h in hits]:
            hits.append((parent, child, olds, cap, m.group(0).strip()))
    # a material named in the description keeps a product out of parts, safety, tool and GSE subcategories
    if hits and hits[0][1] not in TOOLS_FOR_MATERIALS:
        # parts, tools, safety, GSE: any material word; other consumables (oils, greases, cleaners): only the strong ones
        m = MATERIAL.search(t) if hits[0][0] != CON else MATERIAL_STRONG.search(t)
        if m:
            sug = next((s for rx, s in REVIEW if rx.search(t)), 'Consumables (no matching subcategory)')
            return None, None, 'low', (f'"{m.group(0).strip().title()}" in the description: a material, not a {hits[0][1].replace("-", " ")} item; '
                                       f'no subcategory in the tree fits; would fit: {sug}')
    if hits:
        parent, child, olds, cap, word = hits[0]
        conf = 'high' if olds is ANY or old in olds else 'medium'
        if RANK[cap] < RANK[conf]:
            conf = cap
        reason = f'"{word.title()}" in the description'
        reason += f'; old category "{old}"' + ('' if olds is ANY or old in olds else ' differs')
        alt = next((h for h in hits[1:]), None)
        if alt:
            reason += f'; alternative: {names(alt[0], alt[1])}'
            if alt[0] != parent and conf == 'high':
                conf = 'medium'
        return parent, child, conf, reason
    for rx, suggestion in REVIEW:
        m = rx.search(t)
        if m:
            return None, None, 'low', f'"{m.group(0).strip().title()}" in the description; no subcategory in the tree fits; would fit: {suggestion}'
    return None, None, 'low', f'no rule matched the description; old category "{old}"'


def main():
    cats = L.load_categories()
    by = {p['slug']: p for p in cats}
    def names(parent, child=''):
        p = by[parent]
        c = next((x for x in p['children'] if x['slug'] == child), None)
        return p['en'] + (' > ' + c['en'] if c else '')
    products = json.load(open(os.path.join(ROOT, 'backup', 'old-products.json'), encoding='utf-8'))['products']
    pn_count = collections.Counter((p.get('partNumber') or '').strip().upper() for p in products)
    out = os.path.join(ROOT, 'reports', 'category-mapping.csv')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rows = []
    for p in products:
        parent, child, conf, reason = classify(p, names)
        pn = (p.get('partNumber') or '').strip()
        if pn_count[pn.upper()] > 1:
            reason += f'; part number appears {pn_count[pn.upper()]} times in the old catalogue'
        rows.append({'product_id': p['id'], 'product_name': p.get('name_en') or '', 'part_number': pn, 'brand': p.get('brand') or '',
                     'old_category': p.get('category') or '',
                     'new_category': by[parent]['en'] if parent else 'Needs Review',
                     'new_subcategory': next(x['en'] for x in by[parent]['children'] if x['slug'] == child) if parent else '',
                     'confidence': conf, 'reason': reason,
                     # not part of the requested columns, kept so the descriptions can be read while reviewing
                     'description': (p.get('desc_en') or '').replace('&nbsp;', ' ').strip()})
    with open(out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f'{len(rows)} products -> {L.rel(out)}')
    return rows


if __name__ == '__main__':
    main()
