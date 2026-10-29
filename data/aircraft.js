/* Velmach Aerospace: aircraft makes and models for "Shop by Aircraft" and the aircraft filter.
   Written by scripts/import-inventory.py from the Aircraft Type column of the inventory: every model that has parts.
   A product's compatibleAircraft list uses the same ids ("<make-slug>/<model-slug>", e.g. "dassault/falcon-2000").
   To add or rename a model, edit AIRCRAFT in scripts/inventory_rules.py and re-run the import. */
window.VM_AIRCRAFT = [
  { make: "Dassault", models: ["Falcon 20", "Falcon 900EX", "Falcon 2000"] },
  { make: "Dornier", models: ["328"] },
  { make: "Gulfstream", models: ["G300", "GIV"] },
  { make: "Hawker", models: ["800", "800A", "800XP"] },
  { make: "Learjet", models: ["45", "60"] },
  { make: "Lockheed", models: ["JetStar"] }
];
