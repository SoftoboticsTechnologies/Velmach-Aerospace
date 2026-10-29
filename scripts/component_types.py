"""Component types for representative product images (scripts/representative-images.py).

Each type: id, English label, a regular expression matched against the product description (first match wins, so the more
specific types come first) and the searches used to find candidate photos on Wikimedia Commons. A description that matches
no type keeps its category placeholder. Edit the table to add types or move descriptions between them.
"""
import re

TYPES = [
    # id, label, description pattern, Commons searches
    ('fan-blade', 'Engine fan blade', r'\bfan blade|\bfan stator|\bstator vane|\bcompressor blade|\bturbine blade', ['turbofan fan blade', 'jet engine fan blade']),
    ('engine', 'Turbofan engine', r'^engine$|^engine assy|\bturbofan|\btfe731|\bcfe738|\bspey\b|\btay\b', ['TFE731 engine', 'business jet turbofan engine']),
    ('pcb', 'Printed circuit card', r'\bpcb\b|circuit (card|board)|\bswitch card|\bcard assy|\bpower supply card|\bboard assy|^card\b|\bcircuit card', ['printed circuit board avionics', 'printed circuit board']),
    ('cdu', 'Control display unit', r'control display unit|\bcdu\b|\bmcdu\b|\bfmc\b|\bfms\b|flight management', ['control display unit FMS cockpit', 'flight management system CDU']),
    ('display', 'Cockpit display', r'\bdisplay unit|flight display|\bmonitor\b|\bdisplay\b(?! control)|\bcrt\b|\bmfd\b|\bpfd\b|\befis\b|\bdu-\d', ['EFIS display cockpit', 'aircraft multi-function display']),
    ('control-panel', 'Cockpit control panel', r'^(?!.*\b(fairing|access|floor|trim|leading edge|pylon|exterior|closeout|lower|tksa?|heating|lens|stall)\b)(?!panel( assembly)?$).*(\bpanel\b|\bpnl\b|display controller|(weather radar|flight guidance|flight deck|\bhf|\badf|ahrs|audio|call|cursor|manual) controller|controller, (audio|rotary)|mode select|\bcursor control|reversion|\bkeyboard\b|\bswitch box|radio tuning|radio management|radio (set )?control|radio control set|radar control|(cvr|elt|fdr|audio) control box)', ['aircraft cockpit control panel', 'avionics control panel cockpit']),
    ('antenna', 'Aircraft antenna', r'\bantenna\b|\bantena\b', ['aircraft antenna', 'VHF aircraft antenna']),
    ('sensor', 'Sensor / probe / transmitter', r'^(?!.*\bindicator\b).*(?:\bsensor|tank unit|fuel quan|angle of attack|\bpick ?off|accelerometer|\bprobe\b|\btransducer|\btransmitter\b|\bthermocouple|\bthermostat|\bswitch\b.*pressure|\bpressure switch|\bpotentiometer|\bdetector)', ['aircraft pitot probe', 'aircraft temperature probe']),
    ('radio', 'Avionics radio unit', r'^(?!.*(\bindicator\b|battery|switch|cd player)).*(\btransceiver|\btranciever|\btransciever|\breceiver\b|\breciever\b|\brcvr\b|\btransponder|\bdme\b|\badf\b|\bvor\b|\bvhf\b|\bhf\b|\bgps\b|\bselcal|\bradio\b|\bradar\b|\bcvr\b|\bfdr\b|\belt\b|locator|recorder|\begpws|duplexer)', ['avionics line replaceable unit', 'aircraft radio transceiver avionics']),
    ('audio', 'Audio control unit', r'\baudio\b|\bspeaker\b|\bheadset|\bintercom|\bamplifier|\bamp\b', ['aircraft audio control panel', 'aircraft cabin speaker']),
    ('avionics-unit', 'Avionics unit', r'\bunit\b|\bcomputer\b|\bmodule\b|\bconcentrator|\bcoupler|\brepeater|\bconverter|\bdecoder|\bacquisition|\bprocessor|\bdmu\b|\bfadec|\bioc-|\biec-|\bpwr-|\binterface\b|symbol generator|(?<!gear )(?<!filler )\bbox\b|\bdvd\b|\bclock\b|\bchronometer', ['avionics line replaceable unit', 'avionics box aircraft electronics']),
    ('tank', 'Tank / reservoir / bottle', r'\btank\b|\breservoir|\bresevoir|\bbottle\b', ['aircraft hydraulic reservoir', 'nitrogen bottle aircraft']),
    ('heat-exchanger', 'Heat exchanger / cooler', r'\bcooler\b|precooler|heat exchanger|water separator|water seperator|\bacm\b|cooling turbine|air cycle', ['aircraft heat exchanger', 'air cycle machine aircraft']),
    ('wheel', 'Aircraft wheel', r'\bwheel\b|\brim\b|\btire\b|\btyre\b', ['aircraft main wheel', 'business jet wheel tire']),
    ('brake', 'Aircraft brake', r'\bbrake\b(?!.*actuator)', ['aircraft wheel brake assembly', 'aircraft carbon brake']),
    ('actuator', 'Aircraft actuator', r'\bactuator|\bactoator|\bscrew jack|\bjack\b|\bservo\b|\bservovalve|\bservo valve', ['aircraft hydraulic actuator', 'aircraft linear actuator']),
    ('landing-gear', 'Landing gear component', r'landing gear|\bl/g\b|\bnlg\b|\bmlg\b|\buplock|\bdownlock|\bgear door|\bstrut\b|\bshock absorber|\btorque link', ['business jet landing gear', 'aircraft landing gear detail']),
    ('hydraulic-pump', 'Hydraulic pump', r'hydraulic pump|\bpump\b', ['aircraft hydraulic pump', 'aircraft fuel pump']),
    ('accumulator', 'Hydraulic accumulator', r'\baccumulator', ['hydraulic accumulator', 'aircraft hydraulic accumulator']),
    ('valve', 'Aircraft valve', r'\bvalve|\brestrictor|\bhydraulic fuse|\bmanifold|\bregulator\b(?!.*(window|temp))', ['aircraft valve', 'aircraft hydraulic valve']),
    ('filter', 'Aircraft filter', r'\bfilter\b(?!.*emi)', ['aircraft hydraulic filter', 'aircraft air filter']),
    ('hose', 'Hose assembly', r'\bhose\b', ['aircraft hydraulic hose', 'braided hose assembly aircraft']),
    ('pipe', 'Pipe / tube / duct', r'\bpipe\b|\btube\b|\bduct\b|\bducting|\boutlet\b|\binlet\b(?!.*(guide|cowl))|\belbow\b', ['aircraft tubing', 'aircraft hydraulic lines tubing']),
    ('instrument', 'Cockpit instrument', r'^(?!.*(power supply|packaging)).*(\bindicator|\bgauge|\bgage\b|\btachometer|\baltimeter|\bairspeed|\bhorizon\b|\bcompass|\bvsi\b|\bhsi\b|\badi\b|\binstrument|\bind\.?$)', ['aircraft cockpit instrument gauge', 'aircraft analog instrument']),
    ('electrical', 'Electrical component', r'\brelay\b|\bcontactor|\bcircuit breaker|\bswitch\b|\bsolenoid|\binverter|\bpower supply|\bpwr sup|\bballast|\bdimmer|\bconnector|\btransformer|\brectifier|\bgenerator|\bstarter|\bexciter|\bresistor|\bshunt', ['aircraft electrical relay contactor', 'aircraft circuit breaker panel']),
    ('cable', 'Cable / wire harness', r'\bcable\b|\bharness\b|\bwire\b|\bwiring', ['aircraft wire harness', 'aircraft control cable']),
    ('battery', 'Aircraft battery', r'^(?!.*\b(blower|charger|door|elt|pack|temp)\b).*(\bbattery|\bbatteries)', ['aircraft battery', 'nickel cadmium aircraft battery']),
    ('light', 'Exterior aircraft light', r'^(?!.*\b(lens|usb|reading|overhead|cargo|bay|ramp|cabin|exit|instrument)\b).*\b(nav(igation(al)?)?\.?|strobe|beacon|landing|taxi|logo|position(ing)?|anti[- ]?coll?ision|wing|fairing)\b.*\blights?\b|^(?!.*(pwr|power)).*\bstrobe\b|\bbeacon\b|^light, navigational$', ['aircraft navigation light', 'aircraft strobe light']),
    ('light-other', 'Aircraft light (interior or unspecified)', r'\blight\b|\blamp\b|\bexit sign|\billuminat', ['aircraft cabin reading light', 'aircraft exit sign']),
    ('oxygen', 'Oxygen equipment', r'\boxygen|\bmask\b|\bo2\b', ['aircraft oxygen mask', 'aircraft oxygen bottle']),
    ('fire-portable', 'Portable halon fire extinguisher', r'\bhalon\b.*\bextingu', ['aviation halon fire extinguisher']),
    ('fire', 'Fire protection', r'\bextinguisher|\bfire\b|\bsmoke\b', ['aircraft fire extinguisher bottle', 'portable fire extinguisher aircraft']),
    ('window', 'Window / windshield', r'^(?!.*\b(wiper|motor|brush(es)?|regulator|heat|temp|controller|switch|shade|blind)\b).*(\bwindow\b|\bwindscreen|\bwindshield|\bwind shield)', ['business jet windshield', 'aircraft cockpit windshield']),
    ('cabin-seat', 'Cabin passenger seat (single)', r'^(?!.*\b(double|pilot|co-?pilot|crew|observer|cockpit|sign)\b).*(passenger seat|\b(lh|rh) \d+ seat\b)', ['business jet cabin seat']),
    ('seat', 'Seat (crew, double or unspecified)', r'\bseat\b', ['business jet cabin seat', 'aircraft passenger seat']),
    ('flight-control-surface', 'Flight control surface', r'^(?!.*\b(support|bracket|fitting|tee|hinge|rib|seal|track|carriage|screw)\b).*(\bflap\b|\baileron|\belevator\b|\brudder|\bslat\b|\bspoiler|\bairbrake|\bleading edge|\btrim tab)', ['business jet wing flap', 'aircraft aileron']),
    ('fairing', 'Fairing / airframe panel', r'\bfairing|\bcowl|\btail cone|\bspinner|\bnacelle|\bradome|\bdoor\b|\bhatch\b', ['aircraft fairing', 'business jet tail cone']),
    ('linkage', 'Control rod / linkage', r'\bcontrol rod|\brod assy|\brod\b|\bbellcrank|\blever\b|\bcrank\b|\blink\b|\bpushrod', ['aircraft control rod bellcrank', 'aircraft flight control linkage']),
    ('fan', 'Fan / blower', r'\bfan\b|\bblower', ['aircraft avionics cooling fan', 'electric blower fan']),
    ('motor', 'Electric motor', r'\bmotor\b|\bwiper', ['aircraft electric motor', 'electric motor aerospace']),
    ('seal', 'Seal / O-ring', r'\bseal\b|\bo-ring|\bgasket|\bpacking\b', ['o-ring seals', 'aircraft seal gasket']),
    ('hardware', 'Fasteners / hardware', r'\bbolt\b|\bnut\b|\bscrew\b|\bwasher|\brivet|\bclamp\b|\bbracket|\bfitting\b|\bmount\b|\bbearing\b|\bspring\b|\bpin\b', ['aircraft fasteners', 'aerospace bolts nuts']),
]
_COMPILED = [(t[0], re.compile(t[2], re.I)) for t in TYPES]
LABELS = {t[0]: t[1] for t in TYPES}
QUERIES = {t[0]: t[3] for t in TYPES}


def component_type(title):
    """The component type id for a product description, or ''."""
    for tid, pat in _COMPILED:
        if pat.search(title or ''):
            return tid
    return ''

# Wikimedia Commons categories searched first (they hold photos of the object itself; plain text searches mostly find
# photos of people at work). A category that does not exist simply finds nothing.
CATEGORIES = {
    'fan-blade': ['Fan blades', 'Turbofan engines', 'Honeywell TFE731'], 'engine': ['Honeywell TFE731', 'Turbofan engines in museums'],
    'pcb': ['Printed circuit boards', 'Avionics'], 'cdu': ['Flight management systems', 'Control display units'],
    'display': ['Multi-function displays', 'Glass cockpits', 'Electronic flight instrument systems'],
    'control-panel': ['Aircraft control panels', 'Cockpit panels', 'Avionics'], 'antenna': ['Aircraft antennas'],
    'sensor': ['Pitot tubes', 'Aircraft sensors', 'Angle of attack sensors'], 'radio': ['Aircraft radios', 'Transponders', 'Avionics'],
    'audio': ['Aircraft audio panels', 'Aviation headsets'], 'avionics-unit': ['Avionics', 'Line-replaceable units'],
    'tank': ['Hydraulic accumulators', 'Gas cylinders'], 'heat-exchanger': ['Heat exchangers', 'Air cycle machines'],
    'wheel': ['Aircraft wheels'], 'brake': ['Aircraft brakes', 'Disc brakes of aircraft'], 'landing-gear': ['Aircraft landing gear', 'Nose landing gear'],
    'actuator': ['Hydraulic cylinders', 'Linear actuators', 'Aircraft actuators'], 'hydraulic-pump': ['Hydraulic pumps', 'Aircraft hydraulic systems'],
    'accumulator': ['Hydraulic accumulators'], 'valve': ['Valves', 'Ball valves', 'Solenoid valves'], 'filter': ['Oil filters', 'Hydraulic filters', 'Air filters'],
    'hose': ['Hoses', 'Hydraulic hoses'], 'pipe': ['Pipes', 'Tubes (pipes)', 'Aircraft ducts'], 'instrument': ['Aircraft instruments', 'Flight instruments', 'Gauges'],
    'electrical': ['Relays', 'Contactors', 'Circuit breakers'], 'cable': ['Wiring harnesses', 'Cables'], 'battery': ['Aircraft batteries', 'Nickel-cadmium batteries'],
    'light': ['Aircraft lights', 'Navigation lights', 'Aircraft landing lights'], 'oxygen': ['Oxygen masks', 'Aircraft oxygen systems'],
    'fire': ['Fire extinguishers', 'Halon fire extinguishers'], 'window': ['Aircraft windows', 'Windshields'], 'seat': ['Aircraft seats', 'Business jet interiors'],
    'flight-control-surface': ['Flaps (aircraft)', 'Ailerons', 'Spoilers (aircraft)'], 'fairing': ['Aircraft fairings', 'Tail cones'],
    'linkage': ['Bellcranks', 'Aircraft flight control systems'], 'fan': ['Electric fans', 'Axial fans'], 'motor': ['Electric motors'],
    'seal': ['O-rings', 'Gaskets'], 'hardware': ['Bolts', 'Fasteners', 'Rivets'],
}


def commons_queries(tid):
    return [f'incategory:"{c}" filetype:bitmap' for c in CATEGORIES.get(tid, [])] + QUERIES.get(tid, [])
