# TollCalc

iOS app to calculate French motorway tolls. v1 covers the basics:

- **Map & routing:** Apple MapKit. It's free, needs no API key, and includes geocoding and driving directions.
- **Toll data:** the operators' official 2026 tariff grids, converted to JSON and bundled in the app.
- **Itinerary:** type a start and an end point (MapKit route → toll stations crossed → price), or pick the toll stations yourself.
- **Exact pricing:** every price comes straight from a published entry → exit fare and is stored in euro cents. The app never interpolates or estimates. If a stretch of the trip is in no loaded grid, it is shown as *non publié* and the total is marked incomplete.

The UI is deliberately minimal and will be redesigned later.

## Coverage

| Grid | Source | In force since | Fares | Stations with GPS position |
|---|---|---|---|---|
| APRR (A5, A6, A19, A26, A31, A36, A39, A40, A42, A71, A77…, including tickets that end on neighbouring networks) | [TARIFS_APRR.pdf](https://voyage.aprr.fr/sites/default/files/2026-02/TARIFS_APRR.pdf) | 1 Feb 2026 | 21,505 | 155 / 177 |
| AREA (A41, A43, A48, A49, A51, A410, A430, A432 internal) | [TARIFS_INTERNES_AREA.pdf](https://voyage.aprr.fr/sites/default/files/2026-01/TARIFS_INTERNES_AREA.pdf) | 1 Feb 2026 | 815 | 44 / 45 |
| ALIAE A79, Deux-Chaises barrier | [TARIFS_ALIAE-2026.pdf](https://www.aliae.com/files/live/sites/aliae/files/Documents/TARIFS_ALIAE-2026.pdf) | 1 Feb 2026 | 324 | 143 / 163 |
| **VINCI – Cofiroute** (A10 Paris–Tours, A11, A28, A71, A81, A85, A19, plus tickets onto APRR/Sanef) | [Cofiroute guide](https://public-content.vinci-autoroutes.com/PDF/Tarifs-peage-Cofiroute/Cofiroute-Guide-tarifaire-2026.pdf) | 1 Feb 2026 | 11,004 | 200 / 251 |
| **VINCI – ASF** (A7, A8, A9, A10 Tours–Bordeaux, A20, A46, A54, A61, A62, A63, A64, A66, A68, A72, A83, A87, A89, A709, A837…) | [per-class grids C1–C5](https://public-content.vinci-autoroutes.com/PDF/Tarifs-peage-asf/C1-TARIFS-WEB-2026-maille_maj062026.pdf) | 1 Jun 2026 | 18,508 | 321 / 499 |
| **VINCI – Escota** (A8 Aix–Menton, A50, A51, A52, A57, A500) | [Escota guide](https://public-content.vinci-autoroutes.com/PDF/Tarifs-peage-Escota/Escota-Guide-tarifaire-2026.pdf) | 1 Feb 2026 | 2,260 | 31 / 55 |

All five vehicle classes are included. The ASF station count includes the APRR, Cofiroute and Sanef stations that ASF prints tickets to.

**Not covered yet:**
- **Sanef/SAPN:** their site refused this build's downloads.
- **ATMB, SFTRF and the tunnels.**
- **Time-of-day pricing:** VINCI's A355 (Strasbourg bypass), the Duplex A86 and the A1.
- **Free-flow sections:** the A79 gantries and A13/A14.

A trip that uses any of these gets an incomplete quote, never a guessed one. To add a network, add a parser to `Tools/build_tariffs.py` that writes the same JSON format. No Swift changes are needed.

### How the VINCI grids are read

- **Cofiroute** publishes a normal table.
- **ASF and Escota** only publish *charts*:
  - Stations are written at 45° along a staircase, and each cell is the price between a row station and a column station.
  - Rectangular blocks price trips between two motorway sections.

`Tools/vinci_charts.py` rebuilds these charts from glyph positions: cells, rotated labels, exit numbers, labels that wrap onto two lines, and two stations sharing one row. It refuses any cell or label it cannot place. The charts are symmetric, so each price applies in both directions. Stations that share a name get their exit number appended, e.g. `Tonnay-Charente (sortie 33)` and `(sortie 34)`.

Three free (0 €) links on the Toulouse ring are left out: one ASF chart shows them as 0 € and another as "not possible".

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
Tools/vinci_charts.py         reader for the ASF / Escota chart PDFs
Tools/verify_tariffs.py       PDF ↔ JSON checks
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

## How exactness is checked

- **APRR, AREA, A79:** every JSON fare is rebuilt as text and must match a line of the PDF exactly, one to one (`Tools/verify_tariffs.py`).
- **Cofiroute:** every fare line of the guide must be in the JSON, and the JSON must have nothing extra.
- **ASF:** ASF publishes its charts twice, as per-class files and in the tariff guide, with different layouts. Both parse to identical cells for all 5 classes. The same reader handles both, so this catches layout mistakes but not a reader bug that affects both.
- **Across operators:** 5,552 trips are priced by two different operators' documents (APRR↔ASF 1,104, APRR↔Cofiroute 3,382, ASF↔Cofiroute 838, A79↔APRR/Cofiroute 228). They all agree to the cent, and a unit test checks every shared pair.
- **VINCI's own summary:** the unit tests compare against VINCI's "Tarifs des principales liaisons 2026" table and the guides' worked examples, which are printed separately from the charts. All match for every class.
- **Escota:** there is only one source, so it is checked only against those summary figures.

## Updating the tariffs (every 1 February, sometimes mid-year: ASF revised its grid on 1 June 2026)

```sh
python3 -m venv .venv && .venv/bin/pip install pdfplumber
# drop the new PDFs into Tools/raw/ and update URLs/dates in SOURCES
# (VINCI's download links are in the page data of
#  https://www.vinci-autoroutes.com/fr/conseils/autoroute-mode-demploi/tarifs-peage-vinci-autoroutes/)
.venv/bin/python Tools/build_tariffs.py            # or only some grids: … build_tariffs.py asf escota
.venv/bin/python Tools/verify_tariffs.py   # must print OK for every grid
swift test
```

## Data licences

- Tariffs: published by APRR, AREA, ALIAE and VINCI Autoroutes (ASF, Cofiroute, Escota) (links above).
- Toll booth positions: © OpenStreetMap contributors, [ODbL 1.0](https://opendatacommons.org/licenses/odbl/). The app must show this attribution before it ships.
