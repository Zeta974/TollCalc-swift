# TollCalc

iOS app to calculate French motorway tolls. v1 covers the basics:

- **Map & routing:** Apple MapKit. It's free, needs no API key, and includes geocoding and driving directions.
- **Toll data:** the operators' official 2026 tariff grids, converted to JSON and bundled in the app.
- **Itinerary:** type a start and an end point (MapKit route → toll stations crossed → price), or pick the toll stations yourself.
- **Exact pricing:** every price comes straight from a published entry → exit fare and is stored in euro cents. The app never interpolates or estimates. If a stretch of the trip is in no loaded grid, it is shown as *non publié* and the total is marked incomplete.

The UI is deliberately minimal and will be redesigned later.

## Coverage (tariffs in force since 1 February 2026)

| Grid | Source | Fares | Stations with GPS position |
|---|---|---|---|
| APRR (A5, A6, A19, A26, A31, A36, A39, A40, A42, A71, A77…, including tickets that end on neighbouring networks) | [TARIFS_APRR.pdf](https://voyage.aprr.fr/sites/default/files/2026-02/TARIFS_APRR.pdf) | 21,505 | 155 / 177 |
| AREA (A41, A43, A48, A49, A51, A410, A430, A432 internal) | [TARIFS_INTERNES_AREA.pdf](https://voyage.aprr.fr/sites/default/files/2026-01/TARIFS_INTERNES_AREA.pdf) | 815 | 44 / 45 |
| ALIAE A79, Deux-Chaises barrier | [TARIFS_ALIAE-2026.pdf](https://www.aliae.com/files/live/sites/aliae/files/Documents/TARIFS_ALIAE-2026.pdf) | 324 | 143 / 163 |

All five vehicle classes are included.

**Not covered yet:** the Vinci networks (ASF, Cofiroute, Escota, Arcour), Sanef/SAPN, ATMB, SFTRF, the tunnels, the A79 free-flow gantries, the A13/A14 free-flow sections, and time-of-day pricing on the A1. A trip that uses these networks gets an incomplete quote, never a guessed one. To add a network, add a parser to `Tools/build_tariffs.py` that writes the same JSON format. No Swift changes are needed.

## Project layout

```
Package.swift                 TollKit: pure-Swift pricing engine (iOS, macOS, Linux)
Sources/TollKit/
  Money.swift                 integer euro cents
  VehicleClass.swift          classes 1–5
  TollNetwork.swift           one official grid (entry → exit fares)
  TollDatabase.swift          all grids, stations merged across grids
  TollCalculator.swift        quotes, itineraries
  RouteTollDetector.swift     route polyline → toll stations crossed, in order
  Resources/networks/*.json   generated tariff data
App/TollCalc/                 SwiftUI + MapKit app
project.yml                   XcodeGen spec for the iOS app
Tools/build_tariffs.py        PDF grids → JSON (+ OSM coordinates)
Tools/verify_tariffs.py       independent PDF ↔ JSON check
Tools/raw/                    the official PDFs
Tools/data/osm_toll_booths.json  OpenStreetMap toll booth snapshot
```

## Running

```sh
# Pricing engine and tests (macOS or Linux)
swift test

# iOS app (macOS with Xcode 15+)
brew install xcodegen
xcodegen            # creates TollCalc.xcodeproj from project.yml
open TollCalc.xcodeproj
```

Using the engine directly:

```swift
import TollKit

let db = try TollDatabase.bundled()
let calculator = TollCalculator(database: db)

// A single ticket
let quote = try calculator.quote(from: "ALLAINES", to: "AMBERIEU", vehicleClass: .class1)
print(quote.total)   // 58,20 €

// An itinerary (stations in driving order)
let stops = ["ALLAINES", "AMBERIEU"].compactMap(db.station(named:))
let q = calculator.quote(TollItinerary(stops: stops, vehicleClass: .class5))

// A route polyline, e.g. from MKRoute
let passages = RouteTollDetector(database: db).passages(along: polylinePoints)
let routeQuote = calculator.quote(passages: passages.map(\.station), vehicleClass: .class1)
```

## How the price is computed

1. On a route, a toll station counts as crossed when the route passes within 35 m of one of its booths (OpenStreetMap positions). Booths sit on the exit ramps, so a route that only drives past an exit doesn't count it.
2. The crossed stations are split into the **fewest consecutive tickets that each have a published fare**. A published entry → exit fare is what you pay between those two stations, including any barriers in between.
3. Each ticket's price is read from the grid for the chosen vehicle class, and the tickets are added up in cents. When two grids list the same pair, their prices must agree exactly (a unit test checks every shared pair).

## Updating the tariffs (every 1 February)

```sh
python3 -m venv .venv && .venv/bin/pip install pdfplumber
# drop the new PDFs into Tools/raw/ and update URLs/dates in SOURCES
.venv/bin/python Tools/build_tariffs.py
.venv/bin/python Tools/verify_tariffs.py   # must print OK for every grid
swift test
```

## Data licences

- Tariffs: published by APRR, AREA and ALIAE (links above).
- Toll booth positions: © OpenStreetMap contributors, [ODbL 1.0](https://opendatacommons.org/licenses/odbl/). The app must show this attribution before it ships.
