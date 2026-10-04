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

Coverage below is as of 1 October 2026. Every station and toll point a route can go through has a position; `COVERAGE.md` has the per-grid detail.

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
| Duplex A86 (Rueil, Vaucresson, Vélizy), the 6 directional trips | Half-hour of entry × 5 day types (Mon–Thu, Friday or eve of a public holiday, Saturday, Sunday or public holiday, August working days); toll badge price on trips to Vaucresson | VINCI leaflet |
| Prado-Carénage and Prado-Sud tunnels (Marseille), each or both in a row | Class 1; Tunnel Pass / Tunnel Pass+ prices by day (7h–20h) and night | Operator's price page (screenshot in `Tools/raw/other/`) |
| A79 free-flow gantries (Le Montet, Montbeugny, Molinet) | Per gantry or "transit" through both gantries of an interchange; very low emission cars (Crit'Air 0 / electric); trucks by Euro class | ALIAE leaflet |

**A1 time modulation (Sanef):** 122 class 1 trips towards Paris (to Compiègne ouest, Pont-Sainte-Maxence, Senlis and the Chamant barrier) have three official levels: normal, green (vert) and red (rouge). Sanef decides when the green and red periods apply, and that calendar is not in the data. So these trips come back as a green-to-red range unless you pass `sanefA1Period:`.

### Not covered yet

| What | Why |
|---|---|
| Motorway subscriptions, discounts, return tickets | Only the public one-way price is modelled. Commuter offers are tied to a registered trip and monthly use, and need each operator's terms. |

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
- **A79 gantries:** the leaflet's table is an image, so it is transcribed. The Journal officiel prints the same table as text: 7 of its 9 gantries match on all 14 prices. The first two differ (the JO lists an extra "Deux-Chaises / Ouest" gantry and a 1,20 € Le Montet transit). Ulys bills the leaflet's figures (Montluçon → Mâcon, class 1: 3,30 + 1,00 + 1,90 + 1,30 = 7,50 €), so the leaflet is used. Unit tests also check trips of the leaflet's trip table.
- **Duplex A86:** each price is read from its table cell, merged cells spanning several half-hours. All 398 values, table by table and row by row, equal the numbers of the page's plain text in the same order.
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
- **A79 transit:** passing both gantries of an interchange (Ouest then Est, or the reverse) is billed once at the "transit" price, as the leaflet's trip table and Ulys do. Trucks have no price for an undeclared Euro class there, so the quote asks for it.
- **Duplex A86 day types:** taken from the leaflet's footnotes. "Friday or eve" covers Fridays and Monday–Thursday eves of public holidays, outside August. In August, Monday to Saturday use the August row; Sundays and public holidays use their own row all year. Times after midnight belong to that calendar day. The price is the one at the time given for the trip (the entry time). Holidays follow the usual French list, which matches the leaflet's 2026 dates.
- **Duplex A86 detection:** each station is a point placed on its OSM toll booth, with no price of its own. Entering at one and leaving at another is replaced by that trip's price. A third station passed in between (a route from Rueil to Vélizy may run close to Vaucresson) is absorbed. The leaflet prints no vehicle class; the tunnel only takes light vehicles under 2 m, so the price is class 1.
- **Subscriptions:** `Vehicle.subscriptions` lists badges held. Where a toll has a subscriber price for one of them, the quote uses it, otherwise the public price. Deposits and monthly fees are not part of a trip's price. Modelled: any toll badge (Duplex A86), and the Prado Tunnel Pass and Tunnel Pass+.
- **Prado tunnels:** the page prints one price per tunnel without a vehicle class, so only class 1 is priced. "De 7h à 20h" is read as 07:00–19:59. Taking both tunnels in a row has its own price: 6,20 € (the sum), but 5,80 / 5,40 € for subscribers, 10 or 20 cents more than the sum. The booths of the two tunnels are about 100 m apart at Rabatau, so detecting them from a route still needs a test on a real route.
- **A1 time grid:** its "normal" prices equal the regular grid, so it is read as trips towards Paris (northern entry, southern exit). The reverse direction uses the regular fare.
- **Puymorens:** Légifrance also refuses this environment. The five prices were transcribed from its text; classes 1–4 match a second source, class 5 (4,60 €) has only that one.

## Route detection

- **Positions come from OpenStreetMap:** toll booths (`barrier=toll_booth`) or, for stations with no mapped booth, the exit nodes of their interchange on both carriageways (`highway=motorway_junction`). They are matched by name, by road plus exit number, or by exit number near the rest of the grid.
- **Hand-checked positions (`Tools/pins.py`):** 247 grid entries the matching cannot place: names printed differently from OSM, ASF exits listed without their motorway, barriers named after a place, and stations another grid already places under another name ("same:"). Each was checked against the grid itself: the order of stations in the ASF charts, the cheapest neighbouring trips, and whether a booth is on the main line or on a ramp. Pins also fixed three wrong automatic positions: Cofiroute "ANGERS" (the guide prints it with the other station's exit number, so it had been placed at Ancenis), Cofiroute "CHALONS - LA VEUVE" (55 km off), and the A355 Ittenheim side station (OSM gives the barrier's name to its ramp booths).
- **Checked against the grids:** `verify_tariffs.py` fails if a fare joins two stations further apart in a straight line than its tariff distance, or costs under 2 cents a kilometre over more than 15 km, or if one name sits in two places.
- **Tolerances:** a booth counts when the route passes within 35 m of it, an interchange within 80 m.
- **Tickets change at every plaza on the route:** when the route goes through a station's plaza (it passes over a booth, within 10 m: `TollPassage.isThroughPlaza`), the driver paid or took a ticket there. Grids also publish fares for other paths between two stations (ASF prices Toulouse → Peyrehorade by the A62 and A65, 54,90 €), so a ticket may not run through such a plaza unless it costs the same as one side of it (Mirambeau → Carbon-Blanc = Mirambeau → Virsac barrier). Exit plazas a few tens of metres beside the road (Salon sud, St-Jean-de-Védas) are driven past, not stops. Use `quote(route:)` or `quote(passages:)`; in an itinerary named by hand, a station in the middle stays a waypoint.
- **Checked on a real route:** Trets → Capbreton (OSRM over OpenStreetMap, 719 km, kept in `Tests/TollKitTests/Resources`) gives the six amounts Ulys bills, 67,20 €: La Barque 1,00, Lançon → St-Martin-de-Crau 5,20, Arles → Toulouse sud-ouest 34,80, Muret 1,80, Lestelle → Sames 22,40, Capbreton 2,00.
- **Free stretches:** between two plazas with no published fare (the Aix and Arles bypasses, the Toulouse ring), the quote keeps an explicit line without a price rather than assuming 0 €.
- **One place, several names:** the same station named differently in two grids ("AMBERIEU" / "Ambérieu-en-Bugey") is one stop. When names at one place price a trip differently (the A62 plaza north of Toulouse is both "Péage de Toulouse nord/est" and "nord/ouest" in the ASF grid), the route cannot tell which applies: the quote is the range and asks for `.station`; naming the station gives the exact price.
- **Same name, different places:** ATMB "Saint-Julien" (en-Genevois) and SFTRF "St Julien" (Mont-Denis) normalise to the same key; entries more than 5 km apart are kept as separate stations.
- **Not on a route:** the open-system marker, concession limits (e.g. ATMB "Chatillon", between Sylans and Bellegarde), borders (ATMB "Genève") and APRR "LUSSE" (the Maurice-Lemaire tunnel, priced by its own toll point) are priced when named but never detected.
- **One real route tested so far** (above). Use itineraries by station name when the detector misses something.

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
  pins.py                        hand-checked station positions
  coverage.py                    writes COVERAGE.md
  raw/                           official source documents
  data/                          OpenStreetMap snapshots (toll booths, motorway exits)
android/                         Android port (Gradle): tollkit/ engine in Kotlin, app/ Compose demo
```

## Android

`android/tollkit` is a line-by-line Kotlin port of TollKit. It depends only on the Kotlin standard library and reads the **same** `Sources/TollKit/Resources/networks/*.json` files: nothing is copied, so `Tools/build_tariffs.py` stays the single source of tariffs for both platforms. Its tests are in `TollKitTest.kt`.

```sh
cd android
./gradlew :tollkit:test          # engine + tests on any JVM (no Android SDK needed)
./gradlew :app:assembleDebug     # demo APK (needs the Android SDK, API 35; minSdk 26)
```

```kotlin
import com.tollcalc.tollkit.*

val db = TollDatabase.bundled()              // ~2 MB of JSON: call off the main thread
val calculator = TollCalculator(db)

calculator.quote("ALLAINES", "AMBERIEU", VehicleClass.CLASS1).total   // 58,20 €

val stops = listOf("ALLAINES", "AMBERIEU").mapNotNull(db::station)
calculator.quote(TollItinerary(stops, VehicleClass.CLASS5))

// A route polyline from any routing service, as GeoPoint(lat, lon)
val passages = RouteTollDetector(db).passages(polyline)
calculator.quote(passages.map { it.station }, VehicleClass.CLASS1)
```

The demo app covers the "Gares" mode only (pick stations → price). Route mode needs a routing provider on Android (Google Maps, OSRM…); the engine side (`RouteTollDetector`) is ready for it.

**The Kotlin port is behind the Swift engine.** It loads every grid, so closed-system tickets (Sanef and SAPN included) are priced, but it ignores toll points (barriers, bridges, tunnels, Duplex A86, A79 and A14 free-flow), the A1 time modulation (it returns the "normal" price) and the `Vehicle` details. Porting `TollPoint.swift` is the next step for Android.

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
