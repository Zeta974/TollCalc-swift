# TollCalc

**TollKit** is a Swift package that prices French toll roads exactly. It has no UI and no map provider; apps, servers or other tools are meant to be built on top of it.

It contains:
- **The data:** official 2026 tariffs, converted to JSON and checked against the source documents (`Sources/TollKit/Resources/networks/`).
- **The engine:** prices tickets, barriers, bridges and tunnels, including seasonal, time-of-day and Euro-emission pricing.
- **Route detection:** finds the toll stations and points a route polyline goes through, using OpenStreetMap positions.
- **The pipeline:** turns the operators' PDFs into that JSON and verifies it (`Tools/`).

**Exact means:** every price comes from a published table and is handled in integer euro cents.
- When a price depends on something you did not give (the date, a truck's axle count…), you get the published minimum and maximum plus the list of missing inputs.
- When nothing publishes a price, you get "unavailable", never an estimate.

## Using it

```swift
import TollKit

let db = try TollDatabase.bundled()
let calculator = TollCalculator(database: db)

// One closed-system ticket
let q = try calculator.quote(from: "ALLAINES", to: "AMBERIEU", vehicleClass: .class1)
q.total                       // 58,20 €

// A trip through stations and toll points, at a given time
let stops: [TollStop] = ["Chatillon", "Viaduc de Millau", "Origine"].compactMap(db.stop(named:))
let trip = calculator.quote(stops: stops, vehicle: Vehicle(.class1), date: someDate)
trip.lines                    // each ticket / barrier with its Amount
trip.total                    // exact total, or nil if a line is a range or unavailable
trip.totalRange               // (min, max) when some input is missing
trip.missingInputs            // e.g. [.date]

// Trucks: Euro class, axles and weight matter on some roads
let truck = Vehicle(.class4, euroClass: .euro6, axles: 5)

// A route polyline (from any router)
let (passages, routeQuote) = calculator.quote(route: polyline, vehicle: truck, date: someDate)
```

The main types:

| Type | Role |
|---|---|
| `Vehicle` | Class 1–5, plus optional Euro class, axles, gross weight (PTAC), natural gas |
| `SanefA1Period` | Normal / green / red level on the A1, when you know it |
| `TollStop` | `.station` (a stop of a closed-system grid) or `.point` (barrier, bridge, tunnel) |
| `Amount` | `.exact`, `.range(min, max, needs:)`, `.unavailable(reason)` |
| `TollQuote` | Ordered lines, plus `total`, `totalRange`, `isExact`, `isComplete` and `missingInputs` |
| `RouteTollDetector` | Polyline → ordered passages |

`swift test` runs the suite (31 tests; Linux or macOS).

## Coverage

Coverage below is as of 30 September 2026. `COVERAGE.md` has the per-grid detail and every station that is not on the map yet.

### Closed-system grids (entry → exit tickets, 5 classes)

| Operator | Motorways | Source | Trips priced |
|---|---|---|---:|
| APRR | A5, A6, A19, A26, A31, A36, A39, A40, A42, A71, A77…, including tickets onto neighbouring networks | APRR 2026 grid | 21,505 |
| AREA | A41, A43, A48, A49, A51, A410, A430, A432 | AREA 2026 grid | 815 |
| ALIAE | A79, Deux-Chaises barrier | ALIAE 2026 grid | 324 |
| VINCI – Cofiroute | A10 Paris–Tours, A11, A28, A71, A81, A85… | Cofiroute guide | 11,004 |
| VINCI – ASF | A7, A8, A9, A10, A20, A46, A54, A61–A64, A66, A68, A72, A83, A87, A89… | ASF per-class charts (June 2026) | 18,508 |
| VINCI – Escota | A8 Aix–Menton, A50, A51, A52, A57, A500 | Escota guide | 2,260 |
| ATMB | A40, A41 nord, B41 | Journal officiel* | 262 |
| SFTRF | A43 Maurienne | Journal officiel* | 30 |
| ALIS | A28 Rouen–Alençon | Journal officiel* | 42 |
| ARCOUR | A19 Artenay–Courtenay | Journal officiel* | 56 |
| ADELAC | A41 Saint-Julien–Villy-le-Pelloux | Journal officiel* | 6 |
| A'LIÉNOR | A65 Langon–Pau | Journal officiel* | 82 |
| ALICORNE | A88 Falaise–Sées | Journal officiel* | 26 |
| Sanef | A1, A2, A4, A16, A26, A29 | Sanef 2026 grid | 2,734 |
| SAPN | A13, A29 (incl. A13 free-flow sections) | SAPN 2026 grid | 310 |

\* Arrêté du 28 janvier 2026 (JO du 30 janvier 2026, NOR TRAT2534086A).

### Toll points (paid where they are)

| Point | Pricing | Source |
|---|---|---|
| Viaduc de Millau | Summer (15/06–15/09) vs rest of year | Journal officiel + viaduct leaflet |
| A63 Atlandes: barriers of Saugnac-et-Muret and Castets | Heavy classes A/B/C (axles, PTAC) × Euro class, natural gas | Journal officiel |
| A150 Albea barrier | Classes 3/4 × Euro 0–7 | Journal officiel |
| A355 Ittenheim barrier and side station | 26 time bands (weekday, hour, public holidays) × Euro class | Journal officiel + VINCI leaflet |
| Mont-Blanc tunnel, France→Italy and Italy→France | One-way; trucks Euro 5–6 | ATMB |
| Fréjus tunnel, France→Italy | One-way; trucks Euro 5–6 | SFTRF |
| Maurice-Lemaire tunnel | Flat | APRR |
| Puymorens tunnel | Flat | Légifrance (see below) |
| Normandie and Tancarville bridges (from 1 May 2026) | Classes 1–4 | CCI Seine Estuaire |
| A14 Montesson | Base / reduced rate by weekday and hour, public holidays | SAPN grid |
| A14 Chambourcy | Flat | SAPN grid |

**A1 time modulation (Sanef):** 122 class 1 trips towards Paris (to Compiègne ouest, Pont-Sainte-Maxence, Senlis and the Chamant barrier) have three official levels: normal, green (vert) and red (rouge). Sanef decides when the green and red periods apply, and that calendar is not in the data. So these trips come back as a green-to-red range unless you pass `sanefA1Period:`.

### Not covered yet

| What | Why |
|---|---|
| A79 free-flow gantries | The Journal officiel and ALIAE's leaflet publish different gantries and prices. The Deux-Chaises barrier *is* covered. |
| Duplex A86 (VINCI) | Priced by entry, direction, half-hour, day type (incl. eves of public holidays and August working days) and payment method. Needs its own model; the PDF is in `Tools/raw/other/`. |
| Prado-Carénage / Prado-Sud tunnels (Marseille) | The operator's page loads its prices with JavaScript. |
| Subscriptions, discounts, return tickets | Only the public one-way price is modelled. |

## How exactness is checked

`Tools/verify_tariffs.py` runs these checks; the unit tests cover the rest.

- **APRR, AREA, A79:** every fare is rebuilt as text and must match a line of the PDF, one to one.
- **Cofiroute:** every fare line of the guide is in the data, with nothing extra.
- **ASF:** the charts are printed twice (per-class files and the guide, with different layouts); both parse to identical cells.
- **Journal officiel grids:** parsed from the ruled table cells. The page's plain text must then contain exactly the same prices, for every class.
- **A355:** VINCI's per-station leaflet (half-hour slots × 4 day types × every class and Euro group, 1,760 cells) matches the Journal officiel's time bands minute by minute.
- **Millau:** the Journal officiel matches the viaduct's own leaflet.
- **Mont-Blanc and Fréjus:** the France-side prices, from two different operators' pages, are identical.
- **Sanef / SAPN:** parsed from the table cells; each class page's plain text must contain exactly the same prices. Each column of the A1 time grid is matched to the only Sanef station whose regular fares equal its "normal" prices, and all 122 matched.
- **Across operators:** wherever two grids price the same trip (APRR↔ASF, APRR↔Cofiroute, ASF↔Cofiroute, ALIS↔ASF, ARCOUR↔Cofiroute, A'LIÉNOR↔ASF, A79↔APRR/Cofiroute: about 5,600 trips), they agree to the cent. A unit test checks every shared pair.
- **VINCI's own summary:** VINCI's "principales liaisons" table and the guides' worked examples match on all classes.

### Interpretation choices

- **Charts:** a price applies in both directions (the charts and Journal officiel triangles print one value per pair).
- **Shared rows:** a row carrying two station names prices both. Examples: ATMB "Findrol / Scientrier", Escota "St-Cyr / La Cadière".
- **Blanks:** blank, "-", "x", "." and "---" cells are trips that do not exist.
- **Toulouse ring:** three free (0 €) ASF links are left out. One chart prints them at 0 €, another as impossible.
- **A355 holidays:** public holidays are billed like Sundays ("dimanches et jours fériés"), using the order's list, which includes Good Friday and 26 December.
- **A63 truck classes:** class 3 vehicles are class A up to 12 t PTAC, B above. Class 4 is B with 3 axles, C above.
- **Undeclared Euro class:** a heavy vehicle without one pays the "non modulé" price where one is published. Where none is, the Euro class is required.
- **A14 Montesson:** the reduced rate applies "du lundi au vendredi hors jours fériés de 10h à 16h et de 21h à 6h". It is not stated whether the 21h–6h window runs on after Friday night or starts on Sunday night, so on Saturday and Monday 00:00–05:59 the quote is the range between the two rates.
- **A1 time grid:** its "normal" prices equal the regular grid, so it is read as trips towards Paris (northern entry, southern exit). The reverse direction uses the regular fare.
- **Puymorens:** Légifrance also refuses this environment. The five prices were transcribed from its text; classes 1–4 match a second source, class 5 (4,60 €) has only that one.

## Route detection

- **Positions come from OpenStreetMap:** toll booths (`barrier=toll_booth`) or, for stations with no mapped booth, the exit nodes of their interchange on both carriageways (`highway=motorway_junction`). They are matched by name, by road plus exit number, or by exit number near the rest of the grid, and reviewed pins cover the small networks.
- **Tolerances:** a booth counts when the route passes within 35 m of it, an interchange within 80 m.
- **One place, several names:** the same interchange named differently in two grids ("AMBERIEU" / "Ambérieu-en-Bugey") is treated as one stop.
- **Coverage:** 83% of grid entries and 14 of 15 toll points are located; `COVERAGE.md` lists the rest. The A13/A14 free-flow sections are only partly mapped.
- **Not yet tested on real routes.** Detection has only been checked on synthetic polylines. Use itineraries by station name when the detector misses something.

## Project layout

```
Package.swift                    TollKit (iOS 17+, macOS 14+, Linux)
Sources/TollKit/
  Money.swift                    integer euro cents
  VehicleClass.swift, Vehicle.swift
  TollNetwork.swift              one grid: stations, entry → exit fares, toll points
  TollPoint.swift                barriers/bridges/tunnels: seasons, time bands, Euro classes
  TollDatabase.swift             all grids; stations merged across grids
  TollCalculator.swift           quotes: tickets + points, ranges, missing inputs
  RouteTollDetector.swift        polyline → passages
  Resources/networks/*.json      generated data (one file per operator)
Tools/
  build_tariffs.py               PDFs → JSON, OSM positions
  vinci_charts.py                reader for ASF/Escota chart PDFs
  points.py                      toll points (JO annexes, tunnels, bridges, A14)
  sanef.py                       Sanef / SAPN grids and the A1 time grid
  verify_tariffs.py              the checks above
  coverage.py                    writes COVERAGE.md
  raw/                           official source documents
  data/                          OpenStreetMap snapshots (toll booths, motorway exits)
```

## Updating the data (every February, plus mid-year revisions)

```sh
python3 -m venv .venv && .venv/bin/pip install pdfplumber
# put the new documents in Tools/raw/ and update URLs/dates in build_tariffs.py / points.py
.venv/bin/python Tools/build_tariffs.py          # or only some grids: … build_tariffs.py asf tmb
.venv/bin/python Tools/verify_tariffs.py         # every check must pass
python3 Tools/coverage.py
swift test
```

## Licences

- **Tariffs:** published by the operators (APRR, AREA, ALIAE, VINCI Autoroutes, Sanef, SAPN, ATMB, SFTRF, CEVM, ALIS, ARCOUR, ADELAC, A'LIÉNOR, ALICORNE, ATLANDES, ALBEA, ARCOS, CCI Seine Estuaire) and in the Journal officiel.
- **Positions:** © OpenStreetMap contributors, [ODbL 1.0](https://opendatacommons.org/licenses/odbl/). Any product showing or redistributing them must credit OpenStreetMap, and the ODbL's share-alike terms apply to derived databases.
