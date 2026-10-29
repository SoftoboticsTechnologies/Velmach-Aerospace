# Inventory import 2026-10-29

Source: `assets\VELMACH AEROSPACE Master Parts Inventory 06-05-2026.xlsx`, serial numbers 1 to 5560.

| | |
|---|---|
| Rows read | 5560 |
| Products imported | 5560 |
| Rows skipped | 0 (reports/inventory-skipped.csv) |
| Distinct part numbers | 2315 |
| Products with a photo | 0 (the rest show their category placeholder) |
| Products removed (not in the sheet) | 0 |

## Aircraft (filter values)
| Aircraft | Products |
|---|---|
| Dassault Falcon 2000 | 3249 |
| Gulfstream GIV | 852 |
| Hawker 800A | 641 |
| (no aircraft) | 376 |
| Dornier 328 | 203 |
| Dassault Falcon 900EX | 121 |
| Gulfstream G300 | 47 |
| Lockheed JetStar | 23 |
| Hawker 800XP | 21 |
| Learjet 45 | 13 |
| Dassault Falcon 20 | 8 |
| Learjet 60 | 5 |
| Hawker 800 | 1 |

## Aircraft Type as written in the sheet
| Sheet value | Products |
|---|---|
| Falcon 2000 | 2653 |
| Hawker 800A | 641 |
| Falcon 2000 SN 138 | 466 |
| Gulfstream GIV | 440 |
| Gulfstream GIV SN 1352 | 412 |
| (empty) | 376 |
| Dornier 328 | 203 |
| Falcon 900EX SN 52 | 112 |
| Falcon 2000 SN 43 | 92 |
| Gulfstream 300 | 47 |
| F2000 738 Engine | 38 |
| JetStar | 23 |
| Hawker 800XP | 21 |
| Lear 45 | 13 |
| Falcon 900EX | 9 |
| Falcon 20 | 8 |
| Lear 60 | 5 |
| Hawker 800 | 1 |

## Brand (aircraft OEM)
| Brand | Products |
|---|---|
| Dassault Aviation | 3378 |
| Gulfstream Aerospace | 899 |
| Hawker Beechcraft | 663 |
| (no brand) | 376 |
| Dornier | 203 |
| Lockheed | 23 |
| Learjet | 18 |

## Category (from the description)
| Subcategory | Products |
|---|---|
| avionics | 1272 |
| engine-parts | 436 |
| electrical-hardware | 434 |
| valves-regulators | 416 |
| instruments-indicators | 402 |
| flight-controls | 389 |
| other-aircraft-parts | 339 |
| cockpit-cabin-parts | 285 |
| lighting | 212 |
| fuel-system-parts | 197 |
| air-conditioning-pneumatics | 167 |
| hydraulic-parts | 152 |
| ducting-hoses | 148 |
| landing-gear-parts | 119 |
| oxygen-fire-protection | 114 |
| airframe-structures | 110 |
| wheels-brakes | 105 |
| windows-windshields | 99 |
| hardware-fasteners | 66 |
| filters | 46 |
| aircraft-batteries | 33 |
| emergency-locator-transmitters-elts | 18 |
| seals-o-rings | 1 |

## Condition
| Condition | Products |
|---|---|
| Inspected (IN) | 4561 |
| As Removed (AR) | 581 |
| Repaired (RP) | 280 |
| New (NE) | 44 |
| Serviceable (SV) | 43 |
| RD (RD) | 35 |
| (not stated) | 8 |
| CR (CR) | 4 |
| Overhauled (OH) | 3 |
| Tested (TST) | 1 |

## Certification (8130 column)
| Value | Products |
|---|---|
| Yes | 3640 |
| FAA Form 8130-3 | 1056 |
| N/A | 792 |
| Aircraft | 40 |
| C of C | 19 |
| (empty) | 6 |
| Engine | 5 |
| No | 2 |

## Warnings
- date value 3380-06-01 read as "Jun-3380": serial 157 (1 rows)
- condition code "RD" has no name in inventory_rules.CONDITIONS; shown as "RD": serial 618, 619, 1199, 1200, 1201, 1202, 1203, 1204, 1205, 1206, 1207, 1208, 1209, 1210, 1211, 1212, 1213, 1214, 1215, 1216, 1217, 1218, 1219, 1220, 1221, 1222, 1223, 1224, 1225, 1226 and 5 more (35 rows)
- condition code "CR" has no name in inventory_rules.CONDITIONS; shown as "CR": serial 623, 2248, 2249, 3281 (4 rows)
