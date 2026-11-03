"""Normalisation rules for scripts/import-inventory.py (the master parts inventory spreadsheet).

Edit these tables when a new inventory brings a new aircraft, condition code or kind of part; everything else in the
import adapts. The sheet has no brand or category column, so:
  - brand  = the aircraft OEM, taken from the Aircraft Type column (AIRCRAFT below)
  - category = a subcategory of Aircraft Parts, chosen from keywords in the description (CATEGORY_RULES below)
"""
import re

# ---------- aircraft ----------
# (pattern on the cleaned Aircraft Type cell, make, model, OEM brand). First match wins. The make + model become the
# "Shop by Aircraft" entry (data/aircraft.js) and the brand is the aircraft OEM shown on the product.
AIRCRAFT = [
    (r'^(dassault\s+)?(falcon|f)\s*2000', 'Dassault', 'Falcon 2000', 'Dassault Aviation'),
    (r'^(dassault\s+)?(falcon|f)\s*900\s*ex', 'Dassault', 'Falcon 900EX', 'Dassault Aviation'),
    (r'^(dassault\s+)?(falcon|f)\s*900', 'Dassault', 'Falcon 900', 'Dassault Aviation'),
    (r'^(dassault\s+)?(falcon|f)\s*50', 'Dassault', 'Falcon 50', 'Dassault Aviation'),
    (r'^(dassault\s+)?(falcon|f)\s*20', 'Dassault', 'Falcon 20', 'Dassault Aviation'),
    (r'^(dassault\s+)?(falcon|f)\s*7x', 'Dassault', 'Falcon 7X', 'Dassault Aviation'),
    (r'^gulfstream\s*(g\s*)?(iv|4)\b', 'Gulfstream', 'GIV', 'Gulfstream Aerospace'),
    (r'^gulfstream\s*(g\s*)?(v|5)\b', 'Gulfstream', 'GV', 'Gulfstream Aerospace'),
    (r'^gulfstream\s*(g\s*)?300\b', 'Gulfstream', 'G300', 'Gulfstream Aerospace'),
    (r'^gulfstream\s*(g\s*)?450\b', 'Gulfstream', 'G450', 'Gulfstream Aerospace'),
    (r'^gulfstream\s*(g\s*)?550\b', 'Gulfstream', 'G550', 'Gulfstream Aerospace'),
    (r'^(raytheon\s+|bae\s+)?hawker\s*(\d{3,4}\s*[a-z]*)', 'Hawker', None, 'Hawker Beechcraft'),   # model = "800A", "800XP" ...
    (r'^dornier\s*328\s*jet', 'Dornier', '328JET', 'Dornier'),
    (r'^dornier\s*(\d{3})', 'Dornier', None, 'Dornier'),
    (r'^(lockheed\s+)?jet\s*star', 'Lockheed', 'JetStar', 'Lockheed'),
    (r'^(bombardier\s+)?lear(jet)?\s*(\d{2})', 'Learjet', None, 'Learjet'),
    (r'^(bombardier\s+)?challenger\s*(\d{3})', 'Bombardier', None, 'Bombardier'),
    (r'^(boeing\s+)?(7[0-9]7)\b', 'Boeing', None, 'Boeing'),                # the Boeing lists give the model alone: "777"
]
# makes whose parts the representative photos were reviewed for (scripts/representative-images.py); other aircraft keep
# the placeholder until their photos are reviewed
REVIEWED_PHOTO_MAKES = {'Dassault', 'Gulfstream', 'Hawker', 'Dornier', 'Lockheed', 'Learjet'}
# values that mean "no aircraft"
NO_AIRCRAFT = {'', 'na', 'n/a', 'none', '-', 'tbd', 'unknown'}
# airframe / engine details after the model: "Falcon 2000 SN 138", "F2000 738 Engine"
AIRFRAME_SN = re.compile(r'\b(?:sn|s/n|msn)\s*[:#]?\s*(\S+)\s*$', re.I)
ENGINE_NOTE = re.compile(r'\b(\d{3})\s+engine\b', re.I)
ENGINES = {'738': 'CFE738'}   # "F2000 738 Engine": the Falcon 2000's CFE738 engine

# unify brand spellings: key = brand lowered without spaces/punctuation
BRAND_ALIASES = {
    'dassault': 'Dassault Aviation', 'dassaultaviation': 'Dassault Aviation',
    'gulfstream': 'Gulfstream Aerospace', 'gulfstreamaerospace': 'Gulfstream Aerospace',
    'hawker': 'Hawker Beechcraft', 'hawkerbeechcraft': 'Hawker Beechcraft', 'raytheon': 'Hawker Beechcraft',
    'lockheed': 'Lockheed', 'lockheedmartin': 'Lockheed', 'learjet': 'Learjet', 'lear': 'Learjet',
    'boeing': 'Boeing', 'airbus': 'Airbus', 'honeywell': 'Honeywell', 'collins': 'Collins Aerospace',
    'rockwellcollins': 'Collins Aerospace', 'dornier': 'Dornier', 'bombardier': 'Bombardier',
}

# ---------- condition (ATA Spec 2000 codes and the ones this inventory uses) ----------
CONDITIONS = {
    'NE': 'New', 'NS': 'New Surplus', 'FN': 'Factory New', 'OH': 'Overhauled', 'SV': 'Serviceable', 'RP': 'Repaired',
    'IN': 'Inspected', 'TST': 'Tested', 'AR': 'As Removed', 'BER': 'Beyond Economic Repair', 'MD': 'Modified',
}

# ---------- 8130 column ----------
CERT_ALIASES = {'yes': 'Yes', 'faaform81303': 'FAA Form 8130-3', '81303': 'FAA Form 8130-3', 'na': 'N/A', 'no': 'No',
                'cofc': 'C of C', 'certificateofconformity': 'C of C', 'aircraft': 'Aircraft', 'engine': 'Engine'}

# ---------- category (Aircraft Parts subcategories) ----------
# First matching rule wins, so specific systems come before generic words ("fuel pump" is fuel, a bare "pump" hydraulic).
# Patterns run on the lower-case description with punctuation turned into spaces.
CATEGORY_RULES = [
    ('aircraft-batteries', r'\bbatt(ery|eries)?\b'),
    ('emergency-locator-transmitters-elts', r'\belt\b|emergency locator'),
    ('seals-o-rings', r'\bseals?\b|o ring|\boring\b|gasket|\bpacking\b'),
    ('oxygen-fire-protection', r'\boxygen\b|\bo2\b|\bmask\b|\bfire\b|extinguish|\bsmoke\b|\bsquib\b|\bovht\b|overheat det'),
    ('fuel-system-parts', r'\bfuel\b|crossfeed|\bjet pump\b|\bfcu\b'),
    ('windows-windshields', r'windshield|windscreen|\bwindow\b|\bwiper\b'),
    ('lighting', r'\blights?\b|\blamp\b|\bstrobe\b|\bbeacon\b|\bballast\b|flashlight|\bled\b|\bdimm(er|ing)\b|\bnav pos\b'),
    ('wheels-brakes', r'\bwheel\b|(?<!air)brake|\brim\b|\btire\b|\btyre\b|anti skid|antiskid'),
    ('landing-gear-parts', r'landing gear|\bmlg\b|\bnlg\b|\buplock\b|\bdownlock\b|\bgear\b(?! ?box)|\bstrut\b|\bsteering\b|\bshimmy\b|\btorque link\b'),
    ('engine-parts', r'\bengine\b|\bfadec\b|\bignit|\bexciter\b|\bigniter\b|\bstarter\b|\bturbine\b|compressor|reverser|\bcowl|\bapu\b|\bstator\b|'
                     r'\bnacelle\b|\bgear ?box\b|\boil\b|\bitt\b|\begt\b|\bn1\b|\bn2\b|\bpylon\b|\bexhaust\b|\bfan blade\b|\bthrust\b|'
                     r'\bchip detector\b|\bspinner\b|\b(eng|engine) inlet\b|\bair intake\b|\bhmu\b|\bthrottle\b|\bairturbine\b'),
    ('hydraulic-parts', r'hydraul|\bhyd\b|accumulator|servo ?valve|\breservoir\b|\bpump\b|\bnitrogen\b'),
    ('flight-controls', r'\bflaps?\b|\bslats?\b|spoiler|airbrake|aileron|\brudder\b|elevator|\btrim\b|\byoke\b|\bpedal|bellcrank|stick shaker|'
                        r'control column|contorl column|bell ?crank|gust lock|\bservo\b|\bpitch\b|\broll\b|\byaw\b|\bafu\b|\bjack\b|\bactuator\b'),
    ('air-conditioning-pneumatics', r'\bbleed\b|pneumatic|air cond|\bpack\b|pressuri|outflow|cabin press|\bheat exch|\bducts?\b|\bblower\b|'
                                    r'\bfan\b|\bvent(ilation)?\b|precooler|water separ|\bozone\b|anti ice|de ice|\bice\b|\bheater\b|\bmixing\b|\bair cycle\b|\bacm\b|\bventuri\b|\bcondens|\bcold air\b|air temp|\bairflow\b|\bair inlet\b|\bair outlet\b|alternate air|\bdiffuser\b|refrigerat'),
    ('instruments-indicators', r'(pressure|temp|temperature|quantity|quanity|flow|oil) (transmitter|transducer|sensor|switch)|\bindicator\b|\bgauge\b|'
                               r'altimeter|airspeed|\bclock\b|tachometer|\bind\b|\bcompass\b|\bflux\b|attitude|\bpitot\b|\bstatic\b|\bprobe\b|'
                               r'angle of attack|\baoa\b|\bsensor\b|transducer|\bthermocouple\b|\bvsi\b|\bhsi\b|\badi\b|\binstrument\b|\bstandby\b|\bmach\b|chronometer|accelerometer|\bg meter\b|\bgyro\b|horizon|\bcounter pointer\b'),
    ('avionics', r'\bradio\b|\bvhf\b|\bhf\b|\bvor\b|\bdme\b|\badf\b|\bgps\b|transponder|\batc\b|\btcas\b|\begpws\b|\bradar\b|antenna|receiver|reciever|'
                 r'\brcvr\b|transmitter|transceiver|\baudio\b|\bdisplay\b|computer|\bfms\b|\bfdr\b|\bcvr\b|\bselcal\b|satcom|\bafis\b|\biec\b|\bdmu\b|'
                 r'\bnav\b|\bcomm?\b|\bvideo\b|\bcards?\b|\bpcb\b|circuit card|printed|\bmodule\b|\binterface\b|\bdata\b|processor|autopilot|'
                 r'\bahrs\b|\birs\b|\badc\b|\bmfd\b|\bpfd\b|\bcrt\b|\bmonitor\b|speaker|amplifier|\bamp\b|headset|\bioc\b|\bloc\b|glide ?slope|'
                 r'\bils\b|\bmarker\b|\bflight director\b|\bfgc\b|\btuning\b|\bacars\b|\bcmu\b|\bsdu\b|\bhpa\b|\bdigital\b|\bcamera\b|\bmodem\b|'
                 r'\bphone\b|\baircell\b|\bdau\b|\bacquisition\b|\bconcentrator\b|\bswitching\b|\bwarning\b|\bannunciator\b|\bcontroller\b|\bfmc\b|\bfcc\b|\biru\b|\bfdau\b|\bfdep\b|\bgpws\b|\befis\b|\beadi\b|\bgarmin\b|\badsb\b|'
                 r'duplexer|airshow|briefing|headphones?|\bmic\b|microphone|positioning|navigation|file server|firewire|wireless|airphone|'
                 r'\bfqmc\b|\bbscu\b|\bcsu\b|\bdu \d|\bcd \d|\bhd \d|\bfailure advisory\b|\bflight profile\b|\bequalizer\b|\bair ?cell\b'),
    ('electrical-hardware', r'\bswitch|\brelay\b|contactor|generator|inverter|converter|transformer|power supply|\bpsu\b|breaker|\bfuse\b|harness|'
                            r'\bwire\b|\bcable\b|connector|\bbus\b|solenoid|\bmotor\b|potentiometer|rectifier|\btru\b|\bvolt|current limit|\bgcu\b|'
                            r'\bresistor\b|\bdiode\b|\bshunt\b|\bpwr\b|\bpower\b|\belectric|\bplug\b|\bsocket\b|\bjunction\b|alternator|\b(ac|dc) (control|variable|vari|current)|\btime delay\b|\blimiter\b|\bvac outlet\b|\bcharging port\b|\btimer\b|\bbuzzer\b|\balarm\b|\bdisconnect\b'),
    ('cockpit-cabin-parts', r'\bseats?\b|\bcabin\b|\bgalley\b|\boven\b|coffee|\blav(atory)?\b|toilet|\bdoor\b|\bsign\b|passenger|\bdivan\b|\btable\b|'
                            r'curtain|carpet|cockpit|overhead|\bmirror\b|armrest|entertainment|\bdvd\b|\bplayer\b|\bchiller\b|\bsink\b|\bwater\b|'
                            r'\bpanel\b|\bpnl\b|\bcabinet\b|\bdrawer\b|\bglareshield\b|\bstep\b|\bstairs?\b'),
    ('ducting-hoses', r'\bhose\b|\btube\b|\bpipe\b|\bmanifold\b|\bline\b|\bfitting\b'),
    ('valves-regulators', r'valve|regulator|restrictor|\bcheck\b|shut ?off|\brelief\b|\bbutterfly\b|\bflow control\b'),
    ('airframe-structures', r'\bskin\b|\bweb\b|extrusion|\brib\b|\bspar\b|stringer|\bframe\b|fairing|leading edge|trailing edge|\bcone\b|radome|'
                            r'\bbeam\b|longeron|doubler|splice|\bangle\b|\bintercostal\b|\bclip\b|\bchord\b|\bcover\b|\bfillet\b|\bsupport\b|\bfloor\b|'
                            r'\bwing\b|\bfuselage\b|\bstabilizer\b|\bfin\b|\btail\b|\bnose\b|\binsulation\b|\bliner\b|\bshroud\b|\bpanel assy\b'),
    ('hardware-fasteners', r'\bscrew\b|\bbolt\b|\bnut\b|\brivet\b|\bwasher\b|bracket|\bclamp\b|\bpin\b|bushing|bearing|\bspacer\b|\bstud\b|\bolive\b|'
                           r'\bmount(ing)?\b|\blink\b|\brod\b|\bspring\b|\bshaft\b|\bhinge\b|\blatch\b|\bplate\b|\bcollar\b|\bretainer\b'),
    ('filters', r'\bfilters?\b|\belement\b|\bstrainer\b'),
]
FALLBACK_CATEGORY = 'other-aircraft-parts'
NO_AIRCRAFT_CATEGORY = 'other-aircraft-parts'   # Other / Miscellaneous: every row with no Aircraft Type (your rule, 2026-11-03)

# placeholder picture for each subcategory (images/placeholders/<name>.svg) when a product has no photo
PLACEHOLDER = {
    'aircraft-batteries': 'electrical', 'emergency-locator-transmitters-elts': 'avionics', 'oxygen-fire-protection': 'safety',
    'fuel-system-parts': 'fuel', 'windows-windshields': 'window', 'lighting': 'lighting', 'wheels-brakes': 'landing-gear',
    'landing-gear-parts': 'landing-gear', 'engine-parts': 'engine', 'hydraulic-parts': 'hydraulic', 'flight-controls': 'flight-controls',
    'air-conditioning-pneumatics': 'pneumatic', 'instruments-indicators': 'instrument', 'avionics': 'avionics',
    'electrical-hardware': 'electrical', 'cockpit-cabin-parts': 'cabin', 'seals-o-rings': 'hardware', 'ducting-hoses': 'pneumatic',
    'valves-regulators': 'hydraulic', 'airframe-structures': 'structure', 'hardware-fasteners': 'hardware', 'filters': 'hydraulic',
    'other-aircraft-parts': 'generic',
}

_COMPILED = [(slug, re.compile(p)) for slug, p in CATEGORY_RULES]


def category_for(description):
    text = ' ' + re.sub(r'[^a-z0-9]+', ' ', str(description or '').lower()) + ' '
    for slug, rx in _COMPILED:
        if rx.search(text):
            return slug
    return FALLBACK_CATEGORY
