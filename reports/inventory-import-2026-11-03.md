# Inventory import 2026-11-03

Source: `assets\VELMACH AEROSPACE Master Parts Inventory 06-05-2026.xlsx`, serial numbers 1 to 241762.

| | |
|---|---|
| Rows read | 241762 |
| Products imported | 222109 |
| Repeated rows merged (no S/N, every column the same) | 19653 |
| Rows skipped | 0 (reports/inventory-skipped.csv) |
| Distinct part numbers | 211147 |
| Products with a photo of the part | 0 |
| Products with a representative photo of their component type | 812 |
| Products removed (not in the sheet) | 1 |

## Aircraft (filter values)
| Aircraft | Products |
|---|---|
| (no aircraft) | 216236 |
| Dassault Falcon 2000 | 3249 |
| Gulfstream GIV | 851 |
| Hawker 800A | 641 |
| Boeing 777 | 254 |
| Dornier 328 | 203 |
| Boeing 767 | 134 |
| Boeing 787 | 127 |
| Dassault Falcon 900EX | 121 |
| Boeing 757 | 96 |
| Boeing 747 | 79 |
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
| (empty) | 216236 |
| Falcon 2000 | 2653 |
| Hawker 800A | 641 |
| Falcon 2000 SN 138 | 466 |
| Gulfstream GIV | 439 |
| Gulfstream GIV SN 1352 | 412 |
| 777 | 254 |
| Dornier 328 | 203 |
| 767 | 134 |
| 787 | 127 |
| Falcon 900EX SN 52 | 112 |
| 757 | 96 |
| Falcon 2000 SN 43 | 92 |
| 747 | 79 |
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
| (no brand) | 216236 |
| Dassault Aviation | 3378 |
| Gulfstream Aerospace | 898 |
| Boeing | 690 |
| Hawker Beechcraft | 663 |
| Dornier | 203 |
| Lockheed | 23 |
| Learjet | 18 |

## Category (from the description)
| Subcategory | Products |
|---|---|
| other-aircraft-parts | 216733 |
| avionics | 1277 |
| electrical-hardware | 451 |
| valves-regulators | 407 |
| flight-controls | 396 |
| instruments-indicators | 393 |
| cockpit-cabin-parts | 336 |
| engine-parts | 222 |
| lighting | 214 |
| fuel-system-parts | 185 |
| hardware-fasteners | 179 |
| air-conditioning-pneumatics | 176 |
| airframe-structures | 159 |
| hydraulic-parts | 155 |
| ducting-hoses | 145 |
| seals-o-rings | 133 |
| landing-gear-parts | 121 |
| oxygen-fire-protection | 119 |
| wheels-brakes | 105 |
| windows-windshields | 105 |
| filters | 46 |
| aircraft-batteries | 34 |
| emergency-locator-transmitters-elts | 18 |

## Condition
| Condition | Products |
|---|---|
| (not stated) | 153134 |
| New Surplus (NS) | 28792 |
| As Removed (AR) | 27339 |
| Inspected (IN) | 4560 |
| Serviceable (SV) | 4427 |
| New (NE) | 2733 |
| Repaired (RP) | 661 |
| Overhauled (OH) | 396 |
| RD (RD) | 35 |
| - (-) | 6 |
| AI (AI) | 5 |
| Factory New (FN) | 5 |
| CR (CR) | 4 |
| . (.) | 3 |
| _ (_) | 3 |
| RE (RE) | 2 |
| SR (SR) | 2 |
| NQ (NQ) | 1 |
| Tested (TST) | 1 |

## Certification (8130 column)
| Value | Products |
|---|---|
| (empty) | 216556 |
| Yes | 3639 |
| FAA Form 8130-3 | 1056 |
| N/A | 792 |
| Aircraft | 40 |
| C of C | 19 |
| Engine | 5 |
| No | 2 |

## Warnings
- date value 3380-06-01 read as "Jun-3380": serial 157 (1 rows)
- condition code "RD" has no name in inventory_rules.CONDITIONS; shown as "RD": serial 618, 619, 1199, 1200, 1201, 1202, 1203, 1204, 1205, 1206, 1207, 1208, 1209, 1210, 1211, 1212, 1213, 1214, 1215, 1216, 1217, 1218, 1219, 1220, 1221, 1222, 1223, 1224, 1225, 1226 and 5 more (35 rows)
- condition code "CR" has no name in inventory_rules.CONDITIONS; shown as "CR": serial 623, 2248, 2249, 3281 (4 rows)
- condition code "AI" has no name in inventory_rules.CONDITIONS; shown as "AI": serial 159712, 159713, 159714, 159715, 159716 (5 rows)
- condition code "_" has no name in inventory_rules.CONDITIONS; shown as "_": serial 159717, 165971, 165972 (3 rows)
- condition code "NQ" has no name in inventory_rules.CONDITIONS; shown as "NQ": serial 166515 (1 rows)
- condition code "RE" has no name in inventory_rules.CONDITIONS; shown as "RE": serial 170385, 205166 (2 rows)
- condition code "SR" has no name in inventory_rules.CONDITIONS; shown as "SR": serial 171116, 220434 (2 rows)
- condition code "." has no name in inventory_rules.CONDITIONS; shown as ".": serial 217809, 220813, 225780, 234416, 240995 (5 rows)
- condition code "-" has no name in inventory_rules.CONDITIONS; shown as "-": serial 241696, 241756, 241757, 241758, 241759, 241760 (6 rows)
