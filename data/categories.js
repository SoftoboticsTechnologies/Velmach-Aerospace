/* Velmach Aerospace: product category tree (EN / AR).
   URLs: category.dc.html?c=<parent> and ?c=<parent>/<child> (clean form: /c/<parent>/<child>, see js/routes.js).
   desc_en / desc_ar: the short introduction shown on the category page and in the menus.
   Slugs are part of every product and category URL: rename a label freely, but keep its slug.
   nav: false keeps a category off the header menus (it is still listed on categories.dc.html).
   The master inventory has no category column: scripts/import-inventory.py picks the subcategory from the description
   (CATEGORY_RULES in scripts/inventory_rules.py). A new subcategory there needs an entry here.
   The tree before the master inventory import: backup/catalogue-before-master-inventory-2026-10-29/categories.js */
window.VM_CATS = [
  {"slug": "aircraft-parts", "en": "Aircraft Parts", "ar": "قطع غيار الطائرات", "nav": true, "desc_en": "Rotables and components for business and regional aircraft, each with its part number, serial number, condition and certification.", "desc_ar": "قطع دوّارة ومكونات لطائرات الأعمال والطائرات الإقليمية، لكل منها رقم القطعة والرقم التسلسلي والحالة والشهادة.", "children": [
    {"slug": "avionics", "en": "Avionics", "ar": "إلكترونيات الطيران", "desc_en": "Radios, navigation, displays, flight computers, audio and cabin electronics.", "desc_ar": "أجهزة الراديو والملاحة والشاشات وحواسيب الطيران وأنظمة الصوت وإلكترونيات المقصورة."},
    {"slug": "instruments-indicators", "en": "Instruments & Indicators", "ar": "العدادات والمؤشرات", "desc_en": "Indicators, gauges, probes, sensors and transmitters.", "desc_ar": "مؤشرات وعدادات ومجسات وحساسات وأجهزة إرسال القياسات."},
    {"slug": "electrical-hardware", "en": "Electrical Components", "ar": "المكونات الكهربائية", "desc_en": "Switches, relays, contactors, generators, inverters, power supplies and wiring.", "desc_ar": "مفاتيح ومرحلات وموصلات قدرة ومولدات وعواكس ومزودات طاقة وأسلاك."},
    {"slug": "engine-parts", "en": "Engine & APU Parts", "ar": "قطع المحرك ووحدة الطاقة المساعدة", "desc_en": "Engine and APU components, ignition, starters, cowls and thrust reversers.", "desc_ar": "مكونات المحرك ووحدة الطاقة المساعدة والإشعال والمشغلات والأغطية وعاكسات الدفع."},
    {"slug": "flight-controls", "en": "Flight Controls", "ar": "أنظمة التحكم في الطيران", "desc_en": "Flaps, slats, spoilers, trim, actuators, servos and control linkages.", "desc_ar": "القلابات والشرائح والمفسدات والتقليم والمشغلات والمؤازرات ووصلات التحكم."},
    {"slug": "valves-regulators", "en": "Valves & Regulators", "ar": "الصمامات والمنظمات", "desc_en": "Shut-off, check, relief and control valves, pressure regulators and restrictors.", "desc_ar": "صمامات الإغلاق وعدم الرجوع والتنفيس والتحكم ومنظمات الضغط والمقيّدات."},
    {"slug": "cockpit-cabin-parts", "en": "Cockpit & Cabin Parts", "ar": "قطع قمرة القيادة والمقصورة", "desc_en": "Panels, seats, galley equipment, doors and cabin furnishings.", "desc_ar": "ألواح ومقاعد ومعدات المطبخ وأبواب وتجهيزات المقصورة."},
    {"slug": "lighting", "en": "Lighting", "ar": "الإنارة", "desc_en": "Exterior, interior and cockpit lights, strobes, ballasts and light controls.", "desc_ar": "إنارة خارجية وداخلية وإنارة قمرة القيادة ومصابيح وامضة وموازنات ووحدات تحكم بالإنارة."},
    {"slug": "fuel-system-parts", "en": "Fuel System Parts", "ar": "قطع نظام الوقود", "desc_en": "Fuel pumps, valves, controls, tubes and quantity components.", "desc_ar": "مضخات الوقود وصماماته ووحدات التحكم والأنابيب ومكونات قياس الكمية."},
    {"slug": "air-conditioning-pneumatics", "en": "Air Conditioning & Pneumatics", "ar": "التكييف والأنظمة الهوائية", "desc_en": "Bleed air, pressurisation, ducts, fans, heat exchangers and ice protection.", "desc_ar": "هواء التنفيس والضغط ومجاري الهواء والمراوح والمبادلات الحرارية والحماية من الجليد."},
    {"slug": "hydraulic-parts", "en": "Hydraulic Parts", "ar": "القطع الهيدروليكية", "desc_en": "Pumps, accumulators, servo valves, motors and hydraulic actuators.", "desc_ar": "مضخات ومراكم وصمامات مؤازرة ومحركات ومشغلات هيدروليكية."},
    {"slug": "ducting-hoses", "en": "Hoses, Tubes & Manifolds", "ar": "الخراطيم والأنابيب والمشعبات", "desc_en": "Hose assemblies, tubes, pipes and manifolds.", "desc_ar": "مجموعات الخراطيم والأنابيب والمواسير والمشعبات."},
    {"slug": "landing-gear-parts", "en": "Landing Gear Parts", "ar": "قطع عجلات الهبوط", "desc_en": "Gear actuators, uplocks, struts, steering and landing gear components.", "desc_ar": "مشغلات العجلات وأقفالها والمساعدات والتوجيه ومكونات عجلات الهبوط."},
    {"slug": "oxygen-fire-protection", "en": "Oxygen & Fire Protection", "ar": "الأكسجين والحماية من الحريق", "desc_en": "Oxygen bottles, masks, regulators, fire detection and extinguishing.", "desc_ar": "أسطوانات الأكسجين والأقنعة والمنظمات وكشف الحريق وإطفاؤه."},
    {"slug": "airframe-structures", "en": "Airframe & Structures", "ar": "هيكل الطائرة والأجزاء الإنشائية", "desc_en": "Fairings, leading edges, skins, ribs, extrusions and structural parts.", "desc_ar": "الأغطية الانسيابية والحواف الأمامية والجلد والأضلاع والمقاطع المبثوقة والأجزاء الإنشائية."},
    {"slug": "wheels-brakes", "en": "Wheels & Brakes", "ar": "العجلات والفرامل", "desc_en": "Wheels, rims, brakes, brake accumulators and brake controls.", "desc_ar": "العجلات والجنوط والفرامل ومراكم الفرامل ووحدات التحكم بها."},
    {"slug": "windows-windshields", "en": "Windows & Windshields", "ar": "النوافذ والزجاج الأمامي", "desc_en": "Windshields, cabin windows and wiper assemblies.", "desc_ar": "الزجاج الأمامي ونوافذ المقصورة ومجموعات المساحات."},
    {"slug": "hardware-fasteners", "en": "Hardware & Fasteners", "ar": "المثبتات والقطع المعدنية", "desc_en": "Brackets, rods, mounts, bearings and other hardware.", "desc_ar": "حوامل وقضبان وقواعد تثبيت ومحامل وقطع معدنية أخرى."},
    {"slug": "seals-o-rings", "en": "Seals & O-Rings", "ar": "موانع التسرب والحلقات الدائرية", "desc_en": "Seals, O-rings, gaskets and packings.", "desc_ar": "موانع التسرب والحلقات الدائرية والحشوات."},
    {"slug": "filters", "en": "Filters", "ar": "الفلاتر", "desc_en": "Air, hydraulic, fuel and electronic filters and filter assemblies.", "desc_ar": "فلاتر الهواء والهيدروليك والوقود والفلاتر الإلكترونية ومجموعاتها."},
    {"slug": "aircraft-batteries", "en": "Batteries & Chargers", "ar": "البطاريات والشواحن", "desc_en": "Aircraft batteries, chargers and battery monitoring parts.", "desc_ar": "بطاريات الطائرات وشواحنها وقطع مراقبة البطاريات."},
    {"slug": "emergency-locator-transmitters-elts", "en": "Emergency Locator Transmitters (ELTs)", "ar": "أجهزة إرسال تحديد موقع الطوارئ (ELT)", "desc_en": "ELTs, ELT control panels and antennas.", "desc_ar": "أجهزة تحديد موقع الطوارئ ولوحات التحكم بها وهوائياتها."},
    {"slug": "other-aircraft-parts", "en": "Other Aircraft Parts", "ar": "قطع طائرات أخرى", "desc_en": "Components that do not fall under a single system.", "desc_ar": "مكونات لا تندرج ضمن نظام واحد."}
  ]}
];
