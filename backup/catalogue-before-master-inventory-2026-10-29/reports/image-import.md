# Product image import report (2026-10-05)

Source: live category listings of the supplier site (all 9 categories, 186 pages, 0 failed). A product received an image only when its live card had the same source product id, SAP code and product name. Only image fields changed; names, SAP codes, part numbers, descriptions, categories and slugs are unchanged.

| | |
|---|---|
| Total products | 2190 |
| Images already present before this task | 185 |
| New images successfully imported | 1785 (5 test products + 1,780 in the full run) |
| Products with images now | 1970 |
| Products still without images | 220 |
| ... source shows only a "coming soon" placeholder (incl. the 4 below) | 217 |
| ... source image file is damaged (truncated upload) | 2 |
| ... source "image" is not an image (.zip) | 1 |
| Products not on the live source any more | 4 (dell-pro-14-essential-pv14250-fg02153, microtek-ups-legend-1000-fg02149, brother-drum-unit-dr-b021-fg02148, br-toner-tn-b021-fg02147) |
| Identity mismatches (not imported) | 0 |
| Failed / blocked downloads | 0 |
| Invalid image files rejected | 3 (1 zip, 2 truncated) |
| Image-path errors fixed | 0 (none found) |
| Frontend rendering errors fixed | 0 (none found) |

Root cause of "Product image unavailable": the images had never been downloaded (the source blocked automated downloads during the original migration), so those products had `image: null` and the page correctly showed the placeholder. The data → build → page → browser path was verified working.

Every newly imported image is listed in `image-import.csv`.
