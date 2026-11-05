/* Velmach Aerospace: aircraft and helicopter manufacturers for the home page "Aircraft & helicopter brands" strip
   (js/brand-strip.js). Edit by hand. A maker with "slug" that is a catalog brand (data/brands.js) links to that brand
   page and is left out of the "Brands we have" strip; any other maker links to the request-a-quote page. "logo" is a file in public/brands/; a maker with no logo shows its name as text. */
window.VM_MAKERS = {
  aircraft: [
    { name: "Airbus", slug: "airbus", logo: "public/brands/airbus.svg" },
    { name: "Boeing", slug: "boeing", logo: "public/brands/boeing.svg" },
    { name: "Dassault Aviation", slug: "dassault-aviation", logo: "public/brands/dassault-aviation.svg" },
    { name: "Gulfstream Aerospace", slug: "gulfstream-aerospace", logo: "public/brands/gulfstream-aerospace.svg" },
    { name: "Embraer", logo: "public/brands/embraer.svg" },
    { name: "Hawker Beechcraft", slug: "hawker-beechcraft", logo: "public/brands/hawker-beechcraft.svg" },
    { name: "ATR", logo: "public/brands/atr.svg" },
    { name: "Learjet", slug: "learjet", logo: "public/brands/learjet.svg" },
    { name: "Cessna", logo: "public/brands/cessna.svg" },
    { name: "Dornier", slug: "dornier", logo: "public/brands/dornier.svg" },
    { name: "Pilatus", logo: "public/brands/pilatus.svg" },
    { name: "Lockheed", slug: "lockheed", logo: "public/brands/lockheed.png" }
  ],
  helicopters: [
    { name: "Airbus Helicopters", logo: "public/brands/airbus-helicopters.svg" },
    { name: "Bell", logo: "public/brands/bell.svg" },
    { name: "Sikorsky", logo: "public/brands/sikorsky.svg" },
    { name: "Leonardo Helicopters" },
    { name: "Robinson Helicopter" },
    { name: "MD Helicopters" }
  ]
};
