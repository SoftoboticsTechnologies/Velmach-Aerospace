/* Velmach Aerospace: aircraft makes and models for "Shop by Aircraft".
   A product's compatibleAircraft list uses the same ids ("<make-slug>/<model-slug>", e.g. "boeing/737"); an empty list
   means the product fits any aircraft. Add makes or models here; keep existing ids once products use them. */
window.VM_AIRCRAFT = [
  { make: "Airbus", models: ["A220", "A300", "A310", "A318", "A319", "A320", "A321", "A330", "A340", "A350", "A380"] },
  { make: "Airbus Helicopters", models: ["H125", "H130", "H135", "H145", "H155", "H160", "H175", "H225"] },
  { make: "ATR", models: ["ATR 42", "ATR 72"] },
  { make: "Beechcraft", models: ["Baron G58", "Bonanza G36", "King Air 250", "King Air 260", "King Air 350", "King Air 360", "1900D"] },
  { make: "Bell", models: ["206", "407", "412", "429", "505", "525"] },
  { make: "Boeing", models: ["717", "727", "737 Classic", "737 NG", "737 MAX", "747", "757", "767", "777", "787"] },
  { make: "Bombardier", models: ["Challenger 300/350", "Challenger 604/605/650", "CRJ200", "CRJ700", "CRJ900", "Global 5000/6000", "Global 7500", "Learjet 45/75", "Dash 8 Q400"] },
  { make: "Cessna", models: ["152", "172 Skyhawk", "182 Skylane", "206 Stationair", "208 Caravan", "Citation CJ3/CJ4", "Citation Latitude", "Citation Longitude", "Citation Sovereign", "Citation XLS"] },
  { make: "Cirrus", models: ["SR20", "SR22", "Vision Jet SF50"] },
  { make: "Dassault", models: ["Falcon 2000", "Falcon 50", "Falcon 7X", "Falcon 8X", "Falcon 900", "Falcon 6X"] },
  { make: "De Havilland Canada", models: ["DHC-6 Twin Otter", "Dash 8-100/200/300", "DHC-8-400"] },
  { make: "Diamond", models: ["DA40", "DA42", "DA62"] },
  { make: "Embraer", models: ["E170", "E175", "E190", "E195", "E190-E2", "E195-E2", "ERJ 135/145", "Legacy 450/500", "Phenom 100", "Phenom 300", "Praetor 500/600"] },
  { make: "Gulfstream", models: ["G280", "G450", "G500", "G550", "G600", "G650", "G700", "GIV", "GV"] },
  { make: "Leonardo", models: ["AW109", "AW119", "AW139", "AW169", "AW189"] },
  { make: "Lockheed Martin", models: ["C-130 Hercules", "L-100"] },
  { make: "Pilatus", models: ["PC-6", "PC-12", "PC-24"] },
  { make: "Piper", models: ["PA-28 Cherokee/Archer", "PA-31 Navajo", "PA-34 Seneca", "PA-44 Seminole", "PA-46 M350/M500/M600"] },
  { make: "Robinson", models: ["R22", "R44", "R66"] },
  { make: "Sikorsky", models: ["S-76", "S-92", "UH-60 Black Hawk"] },
  { make: "Textron Aviation", models: ["Beechjet 400", "Hawker 800/900", "Hawker 4000"] }
];
