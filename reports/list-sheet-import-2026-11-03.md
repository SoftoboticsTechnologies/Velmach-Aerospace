# List-sheet import 2026-11-03

Source: `assets/velmach product/list sheet` (scripts/import-list-sheet.py)

| | |
|---|---|
| Rows read | 5387 |
| Products (after merging rows with the same part number / name) | 4195 |
| Earlier list-sheet products removed | 0 |
| Field conflicts (reports/list-sheet-conflicts.csv) | 157 |
| Brand logos taken from the sheet (public/brands/<slug>.png) | henkel, chemetall, dow-corning, 3m, ceebee, akzonobel, mobil, loctite, zodiac, anderol |

## Rows per sheet
| Sheet | Rows |
|---|---|
| oil and lubricants.xlsx, sheet "Sheet1" | 2778 |
| oil and lubricants.xlsx, sheet "Sheet3" | 2103 |
| PRODUCT LIST.xlsx 2.xlsx, sheet "Sheet1" | 506 |

## Image (placeholder) per product
| Kind | Products |
|---|---|
| company logo | 2175 |
| brand logo | 2020 |

## Category basis
| Basis | Products |
|---|---|
| keyword rules | 3207 |
| section heading | 792 |
| Consumables (no rule or heading names the type) | 196 |

## Categories
| Category | Products |
|---|---|
| consumables / adhesives-compounds | 792 |
| consumables / sealants | 603 |
| consumables / paints-coatings | 594 |
| consumables / chemicals | 457 |
| consumables / lubricating-oils | 432 |
| consumables / aircraft-grease | 295 |
| consumables / aircraft-hangar-cleaning-supplies | 291 |
| consumables / (parent only) | 196 |
| consumables / composite-materials | 134 |
| consumables / anti-corrosion-lubricants | 93 |
| consumables / engine-oil | 88 |
| consumables / tape | 80 |
| consumables / hydraulic-fluid | 46 |
| consumables / raw-materials | 23 |
| consumables / ndt-chemicals | 11 |
| consumables / landing-gear-fluid | 10 |
| aircraft-parts / seals-o-rings | 9 |
| aircraft-parts / hardware-fasteners | 8 |
| aircraft-tooling / sealant-adhesive-application-tools | 5 |
| consumables / fuel-additives | 5 |
| aircraft-parts / engine-parts | 4 |
| consumables / calibration-fluids | 4 |
| aircraft-tooling / marking-tools | 4 |
| aircraft-tooling / abrasives | 3 |
| consumables / leak-detector-fluid | 3 |
| aircraft-parts / lighting | 1 |
| aircraft-parts / hydraulic-parts | 1 |
| aircraft-tooling / other-aircraft-tools | 1 |
| aircraft-parts / electrical-hardware | 1 |
| consumables / safety-wire-lockwire | 1 |

## Brands
| Brand | Products | Placeholder |
|---|---|---|
| (no brand stated) | 1805 | company logo |
| AkzoNobel | 366 | brand logo |
| LOCTITE | 292 | brand logo |
| Henkel | 249 | brand logo |
| Chemetall | 191 | brand logo |
| 3M | 185 | brand logo |
| CeeBee | 137 | brand logo |
| AeroShell | 101 | company logo |
| PPG | 98 | brand logo |
| Dow Corning | 83 | brand logo |
| Anderol | 71 | brand logo |
| AC-Tech | 60 | company logo |
| Mobil | 57 | brand logo |
| Cytec | 54 | company logo |
| Huntsman | 41 | brand logo |
| NYCO | 40 | brand logo |
| Solvay | 34 | company logo |
| Bostik | 26 | brand logo |
| Momentive | 21 | brand logo |
| Nitto Denko | 20 | company logo |
| Zip Chem | 19 | brand logo |
| Lubriplate | 17 | brand logo |
| Castrol | 15 | brand logo |
| SOCOMORE | 14 | company logo |
| Hysol | 14 | company logo |
| DuPont | 12 | brand logo |
| Kimberly Clark | 12 | brand logo |
| BP | 12 | brand logo |
| ECOLAB | 11 | brand logo |
| PRC-Desoto | 10 | company logo |
| EOX INTERNATIONAL | 9 | company logo |
| MAGNAFLUX | 8 | brand logo |
| CAAP CO | 7 | company logo |
| KRYTOX | 7 | brand logo |
| LUBRIBOND | 6 | company logo |
| DYKEM | 6 | brand logo |
| AV-DEC | 5 | brand logo |
| KEMET | 5 | company logo |
| MAGNOLIA | 5 | brand logo |
| KINGSTON | 4 | company logo |
| Parker | 4 | company logo |
| Carberto | 4 | company logo |
| STABOND CORPORATION | 4 | brand logo |
| GORE | 3 | brand logo |
| TURCO Italiana | 3 | brand logo |
| TURCO Spain | 3 | company logo |
| Armite | 3 | brand logo |
| Mouse Milk | 3 | brand logo |
| Nycote Laboratories | 3 | company logo |
| Nye | 3 | brand logo |
| SENTINEL | 3 | brand logo |
| Houghton | 2 | brand logo |
| ZYVAX | 2 | company logo |
| Zodiac | 2 | brand logo |
| AXON | 2 | company logo |
| DOW | 2 | company logo |
| Preval | 2 | company logo |
| Prist | 2 | brand logo |
| Zerust | 2 | company logo |
| Permabond | 2 | brand logo |
| Alglas | 1 | company logo |
| Arlon LLC | 1 | company logo |
| Chicopee | 1 | brand logo |
| Mouser | 1 | company logo |
| Shurtape | 1 | company logo |
| TEFLEASE | 1 | company logo |
| Jet Lube | 1 | brand logo |
| RUST-OLEUM | 1 | brand logo |
| Durferrit GmbH | 1 | company logo |
| DYSOL | 1 | company logo |
| Zettex | 1 | company logo |
| Click Bond | 1 | brand logo |

## Incomplete data
| Missing | Products |
|---|---|
| Part number | 2812 |
| Brand | 1805 |
| Subcategory (Consumables parent only) | 196 |
| Description beyond the name | 3881 |
| Price | 4195 (no list has a price) |
| Condition | 4195 (no list states one) |

## Notes
- oil and lubricants.xlsx: sheet "Sheet2": list of supplier websites and e-mails, not products
- oil and lubricants.xlsx: sheet "Sheet1": 57 embedded pictures, all brand logos or groups of logos (not product photos)
- PRODUCT LIST.xlsx 2.xlsx: sheet "Sheet1": 12 embedded pictures, all brand logos or groups of logos (not product photos)
