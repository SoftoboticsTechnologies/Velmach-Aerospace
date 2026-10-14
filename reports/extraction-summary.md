# Document extraction: dry run

Nothing has been imported and nothing on the site has changed.

- Rows read: 18691; products after merging by part number (or exact name when there is none): **9354**
- With a part number: 4628; without: 4726
- With a brand stated in the documents: 615; without: 8739
- With an image from the documents: 513; without: 8841 (reports/missing-images.csv)
- Category mapped onto the existing tree: 5845 (high 106, medium 3832, low 1907); not mapped: 3509 (reports/new-categories.md)
- Conflicts between documents: 460 (reports/conflicts.md)

## Per source file

| File | Rows read | Products it contributes | Notes |
|---|---:|---:|---|
| 2026-10-lead-time-updates.xlsx | 152614 | 24 | sheet "2026-10-lead-time-updates": not published: Current Lead Time (Days), New Lead Time (Days), % Change; stock list: not products; 24 rows added details to products in the main list |
| 2026-10-seasonal-parts.xlsx | 690 | 0 | sheet "Seasonality_10126": not published: Bin Qty; stock list: not products; 0 rows added details to products in the main list |
| A220-Program-Approved-Supplier-List.pdf | 0 | 0 | approved-supplier list (supplier names, codes and specifications): no products |
| AW Approved Supplier List_raw_06_02_26.pdf | 0 | 0 | approved-supplier list (supplier names, codes and specifications): no products |
| AeroDirect_Rotable_Parts.xlsx | 7684 | 1 | sheet "Sheet1": not published: Serial Number, Certified by, Cert Date, Qty, Source; stock list: not products; 1 rows added details to products in the main list |
| Aeroservices - Core Capability.pdf | 0 | 0 | company profile (read with OCR): no part-number list. Text: CORECAPABILITIES AEROSERVICES (Lubricants&Consumables) KeepingGlobalAviationWellOiled Onestopshopsolutionsfromover5oOEMs ExonMobil 3M EASTMAN Aviation Lubricants AeroShell AkzoNobel ALGLAS ARROW Castrol Chemetall CYTEC DASIC CLARIANT INTERNATIONAL DOWCORNING FUCHS Henkel HUNTSMAN Indestructible JET- |
| Airline-Product-Line-Card-2018.pdf | 0 | 0 | 12 pages, 0 part-number tables, 0 product rows; photos attached: 0 (0 products share a photo with their other size/pack variants); photos not used because they show several different products: 0 |
| All-Products-Booklet-Rev-17-Aviall-NORTH-AMERICA.pdf | 0 | 0 | kept apart (your decision): not read, no products and no images taken |
| Aviall Product Catalog & Source Book.pdf | 0 | 0 | kept apart (your decision): not read, no products and no images taken |
| Aviall-Industry-Maint-Catalog-2019.pdf | 0 | 0 | kept apart (your decision): not read, no products and no images taken |
| BATTERIES.pdf | 0 | 0 | not read separately: Battery Catalog.pdf (image-only copy) |
| Battery Catalog.pdf | 361 | 319 | 86 pages, 90 part-number tables, 361 product rows; photos attached: 59 (2 products share a photo with their other size/pack variants); photos not used because they show several different products: 13 |
| Boeing-Distribution-Services-Line-Card-09-23.pdf | 0 | 0 | 2 pages, 0 part-number tables, 0 product rows; photos attached: 0 (0 products share a photo with their other size/pack variants); photos not used because they show several different products: 0 |
| Boeing-Paint-Catalog-2022.pdf | 649 | 641 | 42 pages, 172 part-number tables, 649 product rows, 17 rows skipped (unreadable characters), 35 rows skipped (part-number cell holds pack text, not a part number); photos attached: 38 (29 products share a photo with their other size/pack variants); photos not used because they show several different products: 79; pages without text (covers / photos): 1, 2, 40 |
| Boeing_Distribution_Chemicals_May20_digital.pdf | 1411 | 1410 | 16 pages, 1411 product names (no part numbers in this file); 217 specification-number lines skipped |
| Celeste-All-Products-Booklet--Rev-16--Aviall-NORTH-AMERICA.pdf | 0 | 0 | kept apart (your decision): not read, no products and no images taken |
| Consumables Catalog.pdf | 490 | 490 | 36 pages, 189 part-number tables, 490 product rows, 15 rows skipped (unreadable characters); photos attached: 105 (104 products share a photo with their other size/pack variants); photos not used because they show several different products: 71; pages without text (covers / photos): 1, 34, 35 |
| PRODUCT LIST WITH FULL DETAILS.pdf | 4790 | 4764 | 138 pages, 4790 product rows; its images are page decorations (no product photos beside rows); part-number column is not a part number (kept as written): 808 rows; part number was in the name column: 1187 rows |
| PRODUCT LIST.xlsx | 4892 | 4892 | sheet "Sheet1": 57 embedded images: 22 beside a product, 31 on brand/heading rows (logos, not used), 4 with no product next to them (not used); sheet "Sheet2": list of supplier websites and e-mails, not products; part-number column is not a part number (kept as written): 776 rows; part number was in the name column: 1308 rows |
| PRODUCT LIST.xlsx 2 (1).xlsx | 0 | 0 | not read separately: PRODUCT LIST.xlsx 2.xlsx |
| PRODUCT LIST.xlsx 2.xlsx | 506 | 506 | sheet "Sheet1": 12 embedded images: 12 beside a product, 0 on brand/heading rows (logos, not used), 0 with no product next to them (not used) |
| PRODUCTLIST (1).pdf | 0 | 0 | not read separately: Consumables Catalog.pdf (image-only copy) |
| PRODUCTLIST.pdf | 0 | 0 | not read separately: Consumables Catalog.pdf (image-only copy) |
| PROPONENT Main_Product_Guide_2026_Digital.pdf | 0 | 0 | 32 pages, 0 part-number tables, 0 product rows; photos attached: 0 (0 products share a photo with their other size/pack variants); photos not used because they show several different products: 0; pages without text (covers / photos): 1, 4, 30, 31 |
| Profile-Aero Enterprises.pdf | 0 | 0 | company profile (read): no part-number list. Text: 2027/7, 3rd Mob.: +91-98 We Aero Enterprises are pleased Industry providing Aircraft / Helicop OEM C of C / Release note. Consumables We offer wide range of consumab Sealant, Solvent, Paint, Primer, Varn We have established our warehou condition. This helps us to deliver th We supply all the items w |
| REGIONAL AVIONICS STOCK INVENTORY.xlsx | 459 | 9 | sheet "Sheet1": not published: Quantity On Hand; stock list: not products; 9 rows added details to products in the main list |
| Tramec Aero Presentation.pdf | 0 | 0 | 3 pages, 0 part-number tables, 0 product rows; photos attached: 0 (0 products share a photo with their other size/pack variants); photos not used because they show several different products: 0 |
| VELMACH AEROSPACE Master Parts Inventory 06-05-2026.xlsx | 5554 | 5554 | sheet "Master Inventory": not published: S/N; sheet "Coming Soon": not published: Quanity, Serial Number |
| aviall-helicopter-product-catalog.pdf | 0 | 0 | kept apart (your decision): not read, no products and no images taken |
| aviation-tech-review.pdf | 0 | 0 | 94 pages, 0 part-number tables, 0 product rows; photos attached: 0 (0 products share a photo with their other size/pack variants); photos not used because they show several different products: 0; pages without text (covers / photos): 4 |
| brochure-zip-chem-general-aviation-and-business-jet-products.pdf | 16 | 16 | 4 pages, 0 part-number tables, 16 product rows; photos attached: 0 (0 products share a photo with their other size/pack variants); photos not used because they show several different products: 0 |
| celeste-cabin-cleaning-solutions-business-general-aviation-fnl-digital.pdf | 22 | 19 | 12 pages, 6 part-number tables, 22 product rows; photos attached: 0 (0 products share a photo with their other size/pack variants); photos not used because they show several different products: 2; pages without text (covers / photos): 9, 10, 11 |
| https.docx | 0 | 0 | links only, not fetched: https://shop.boeing.com/all-products/engines, https://santiemidwest.com/anderol/, https://pilotjohn.com/manufacturer |
| mastlist.pdf | 0 | 0 | approved-supplier list (supplier names, codes and specifications): no products |

## Per category (existing tree), main list

| Category | Subcategory | Products |
|---|---|---:|
| Aircraft Parts | Air Filters | 4 |
| Aircraft Parts | Aircraft Batteries | 75 |
| Aircraft Parts | Aircraft Tires | 9 |
| Aircraft Parts | Cockpit & Cabin Parts | 71 |
| Aircraft Parts | Ducting & Hoses | 42 |
| Aircraft Parts | Electrical Hardware | 68 |
| Aircraft Parts | Emergency Locator Transmitters (ELTs) | 9 |
| Aircraft Parts | Engine Parts | 44 |
| Aircraft Parts | Fuel System Parts | 39 |
| Aircraft Parts | Hardware & Fasteners | 56 |
| Aircraft Parts | Hose Assemblies | 15 |
| Aircraft Parts | Hydraulic Parts | 41 |
| Aircraft Parts | Landing Gear Parts | 22 |
| Aircraft Parts | Lighting | 80 |
| Aircraft Parts | Seals & O-Rings | 20 |
| Aircraft Parts | Wheels & Brakes | 52 |
| Aircraft Parts | Windows & Windshields | 36 |
| Aircraft Tooling | Abrasives | 75 |
| Aircraft Tooling | Crimping Tools | 4 |
| Aircraft Tooling | Drill Bits | 1 |
| Aircraft Tooling | Inspection Lights | 4 |
| Aircraft Tooling | Knives | 1 |
| Aircraft Tooling | Marking Tools | 4 |
| Aircraft Tooling | Measurement Tools | 3 |
| Aircraft Tooling | Other Aircraft Tools | 21 |
| Aircraft Tooling | Screwdrivers | 1 |
| Aircraft Tooling | Sealant & Adhesive Application Tools | 16 |
| Aircraft Tooling | Temperature Measurement | 1 |
| Aircraft Tooling | Wrenches | 5 |
| Consumables | Adhesives & Compounds | 1383 |
| Consumables | Aircraft Grease | 282 |
| Consumables | Aircraft & Hangar Cleaning Supplies | 433 |
| Consumables | Anti-Corrosion Lubricants | 122 |
| Consumables | Calibration Fluids | 4 |
| Consumables | Chemicals | 117 |
| Consumables | Composite Materials | 20 |
| Consumables | Dielectric Coolants | 2 |
| Consumables | Engine Oil | 150 |
| Consumables | Fuel Additives | 5 |
| Consumables | Hydraulic Fluid | 60 |
| Consumables | Landing Gear Fluid | 15 |
| Consumables | Leak Detector Fluid | 3 |
| Consumables | Lubricating Oils | 446 |
| Consumables | NDT Chemicals | 9 |
| Consumables | Paints & Coatings | 998 |
| Consumables | Raw Materials | 43 |
| Consumables | Safety Wire & Lockwire | 1 |
| Consumables | Sealants | 583 |
| Consumables | Tape | 295 |
| Ground Support Equipment | Fueling GSE | 2 |
| Safety Equipment | Fire Extinguishers | 6 |
| Safety Equipment | Goggles | 3 |
| Safety Equipment | Protective Breathing Equipment (PBE) | 1 |
| Safety Equipment | Safety Apparel | 43 |
| Not mapped (needs a category) | | 3509 |

## By source group

| Group | Products | With part # | With brand | With document image | Category mapped |
|---|---:|---:|---:|---:|---:|
| Your Velmach lists | 6629 | 3222 | 615 | 29 | 3512 |
| Kept catalogs only (Boeing, Battery, Zip-Chem, Celeste cabin) | 2725 | 1406 | 0 | 484 | 2333 |

Stock lists (lead-time, AeroDirect, seasonal, Regional Avionics): 161447 rows read, not used as products; 34 main-list products got extra details from them (condition, aircraft type, alternate part number, description when empty).

## 10 random products (6 from your Velmach lists, 4 from the kept catalogs)

| Title | Part number | Brand | Category | Image | Source |
|---|---|---|---|---|---|
| MCS-352B | `` |  | Aircraft Parts > Hydraulic Parts | (none) | PRODUCT LIST WITH FULL DETAILS.pdf, page 128 |
| Selcal Decoder | `1200008-003` |  | Not mapped | (none) | VELMACH AEROSPACE Master Parts Inventory 06-05-2026.xlsx, sheet "Master Inventory" row 438 |
| Switch Card | `FRTEEE97-05` |  | Not mapped | (none) | VELMACH AEROSPACE Master Parts Inventory 06-05-2026.xlsx, sheet "Coming Soon" row 517 |
| Everlube 620 | `` |  | Not mapped | (none) | PRODUCT LIST WITH FULL DETAILS.pdf, page 132 |
| Exxon Instrument Oil | `` |  | Consumables > Lubricating Oils | (none) | PRODUCT LIST WITH FULL DETAILS.pdf, page 128 |
| 70206 ThermaPlex® Hi-Temp | `70206` |  | Not mapped | (none) | PRODUCT LIST.xlsx, sheet "Sheet3" row 833 |
| Silver Grade – 8 oz. Brush Can | `76732` |  | Not mapped | (none) | Consumables Catalog.pdf, page 12 |
| HARD CUP COMPONENTS MIXING CUP AND COLLAR | `051131-16023` |  | Aircraft Parts > Hardware & Fasteners | (none) | Boeing-Paint-Catalog-2022.pdf, page 27 |
| LIDS ONLY (WITH QUARTER-TURN LID LOCKING SYSTEM) – Large / S | `051131-26200` |  | Consumables > Paints & Coatings | (none) | Boeing-Paint-Catalog-2022.pdf, page 26 |
| TPD-1000A | `` |  | Consumables > Paints & Coatings | (none) | Boeing_Distribution_Chemicals_May20_digital.pdf, page 14 |
