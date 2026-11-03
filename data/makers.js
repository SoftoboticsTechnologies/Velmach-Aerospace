/* Velmach Aerospace: aircraft and helicopter manufacturers for the home page "Aircraft & helicopter brands" strip
   (js/brand-strip.js). Edit by hand. A maker with "slug" is a catalog brand (data/brands.js): its tile links to that
   brand page, uses that brand's logo and is left out of the "Brands we supply" strip. A maker without a slug links to
   the request-a-quote page. "logo" is a file in public/brands/; a maker with no logo shows its name as text. */
window.VM_MAKERS = {
  aircraft: [
    { name: "Airbus", logo: "public/brands/airbus.svg" },
    { name: "Boeing", slug: "boeing" },
    { name: "Dassault Aviation", slug: "dassault-aviation" },
    { name: "Gulfstream Aerospace", slug: "gulfstream-aerospace" },
    { name: "Embraer", logo: "public/brands/embraer.svg" },
    { name: "Hawker Beechcraft", slug: "hawker-beechcraft" },
    { name: "ATR", logo: "public/brands/atr.svg" },
    { name: "Learjet", slug: "learjet" },
    { name: "Cessna", logo: "public/brands/cessna.svg" },
    { name: "Dornier", slug: "dornier" },
    { name: "Pilatus", logo: "public/brands/pilatus.svg" },
    { name: "Lockheed", slug: "lockheed" }
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
