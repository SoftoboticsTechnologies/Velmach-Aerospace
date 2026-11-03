/* Velmach Aerospace: brands. Updated by scripts/build-catalog.py: every brand that appears on products is listed;
   a brand with no products is dropped. featured: true puts the brand first in the header menu; set it by hand.
   Logos: put <slug>.svg (or .png / .webp) in public/brands/ and rebuild; the build fills in "logo" (a white-only logo:
   <slug>-white.<ext>, shown on a dark backing: "logoDark"). A brand without a
   logo file shows its name as text instead. URLs: brand.dc.html?b=<slug> (clean form: /brand/<slug>). Keep a slug once published. */
window.VM_BRANDS = [
  {"slug": "dassault-aviation", "name": "Dassault Aviation", "featured": false,"logo": "public/brands/dassault-aviation.svg"},
  {"slug": "dornier", "name": "Dornier", "featured": false,"logo": "public/brands/dornier.svg"},
  {"slug": "gulfstream-aerospace", "name": "Gulfstream Aerospace", "featured": false,"logo": "public/brands/gulfstream-aerospace.svg"},
  {"slug": "hawker-beechcraft", "name": "Hawker Beechcraft", "featured": false,"logo": "public/brands/hawker-beechcraft.svg"},
  {"slug": "learjet", "name": "Learjet", "featured": false,"logo": "public/brands/learjet.svg"},
  {"slug": "lockheed", "name": "Lockheed", "featured": false,"logo": "public/brands/lockheed.png"}
];
