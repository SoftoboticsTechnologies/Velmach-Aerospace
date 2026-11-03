# List-sheet import 2026-11-03

Source: `assets/velmach product/list sheet` (scripts/import-all-lists.py)

| | |
|---|---|
| Files scanned | 10 (reports/list-import-files.csv) |
| Product rows in the consumables lists | 5387 (→ 4195 products after merging the same part number / name) |
| Rows in the parts lists | 403210 (→ 211485 distinct part numbers) |
| Rows without a part number (not imported) | 0 (reports/list-import-no-part-number.csv) |
| Existing products before the import | 5845 |
| Existing duplicates removed | 16 |
| Existing products kept unchanged | 5829 |
| New products already on the website (skipped) | 3344 |
| New products added | 212311 |
| New brands added | 16 (reports/list-import-new-brands.csv) |
| Brand logos cut from the sheet | henkel, chemetall, dow-corning, 3m, ceebee, akzonobel, mobil, loctite, zodiac, anderol |
| products-export.csv rows | 9755: 9754 duplicates of products on the site, 1 not found |

## Added products by source
| Source | Products |
|---|---|
| Parts lists | 210871 |
| Consumables lists | 1440 |

## Image of the added products
| Image | Products |
|---|---|
| company logo | 211813 |
| brand logo | 498 |
| Real product photo | 0 (no list contains a product photo) |

## Category basis
| Basis | Products |
|---|---|
| parts list (no category in the list) | 210871 |
| keyword rules | 694 |
| section heading | 579 |
| Consumables (no rule or heading names the type) | 167 |

## Missing data in the added products
| Missing | Products |
|---|---|
| brand | 211615 |
| subcategory | 211038 |
| part number | 716 |
| description beyond the name | 19 |
| price | 212311 (no list has a price) |

## New brands
- 3M
- AC-Tech
- AeroShell
- AXON
- CeeBee
- Chemetall
- Cytec
- Durferrit GmbH
- Henkel
- Hysol
- LOCTITE
- Mobil
- Preval
- TURCO Spain
- Zerust
- Zettex

## Files
- PRODUCT LIST.xlsx 2.xlsx: consumables list; 506 product rows; sheet "Sheet1": 12 embedded pictures, all brand logos or groups of logos (not product photos)
- oil and lubricants.xlsx: consumables list; 4881 product rows; sheet "Sheet2": list of supplier websites and e-mails, not products; sheet "Sheet1": 57 embedded pictures, all brand logos or groups of logos (not product photos)
- VELMACH AEROSPACE Master Parts Inventory 06-05-2026.xlsx: parts list; 241762 rows, 241762 with a part number
- 2026-10-lead-time-updates.xlsx: parts list; 152614 rows, 152614 with a part number
- AeroDirect_Rotable_Parts.xlsx: parts list; 7685 rows, 7685 with a part number
- REGIONAL AVIONICS STOCK INVENTORY.xlsx: parts list; 459 rows, 459 with a part number
- 2026-10-seasonal-parts.xlsx: parts list; 690 rows, 690 with a part number
- PICIMAGE.xlsx: pictures; pictures only: customer, airline and aircraft-maker logo collages and a supplier link (no products)
- product images.docx: pictures; one picture: a collage of brand logos (no products)
- products-export.csv: export of an earlier import; 9755 rows, checked for duplicates

## products-export.csv rows not matched
- products-export.csv row 9270: 345-6196-04 Elt Switch
