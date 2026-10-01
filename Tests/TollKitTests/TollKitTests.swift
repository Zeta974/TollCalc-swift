import XCTest
@testable import TollKit

final class TollKitTests: XCTestCase {
    static let database = try! TollDatabase.bundled()
    var database: TollDatabase { Self.database }
    var calculator: TollCalculator { TollCalculator(database: database) }

    // MARK: - Data loading

    func testBundledNetworksLoad() {
        let byID = Dictionary(uniqueKeysWithValues: database.networks.map { ($0.id, $0) })
        XCTAssertEqual(byID["aprr"]?.fareCount, 21_505)
        XCTAssertEqual(byID["area"]?.fareCount, 815)
        XCTAssertEqual(byID["aliae"]?.fareCount, 324)
        XCTAssertEqual(byID["cofiroute"]?.fareCount, 11_004)
        XCTAssertEqual(byID["asf"]?.fareCount, 18_508)
        XCTAssertEqual(byID["escota"]?.fareCount, 2_260)
        XCTAssertEqual(byID["asf"]?.validFrom, "2026-06-01")  // ASF revised its grid on 1 June 2026
        // Alpine tunnels change on 1 January, the Seine bridges changed on 1 May 2026.
        // The Prado tunnels' page gives no start date: it is the day it was read.
        let exceptions = ["asf": "2026-06-01", "tmb": "2026-01-01", "frejus": "2026-01-01", "ponts-seine": "2026-05-01",
                          "prado": "2026-10-01"]
        for network in database.networks {
            XCTAssertEqual(network.validFrom, exceptions[network.id] ?? "2026-02-01", network.id)
        }
    }

    // MARK: - Prices copied from the official PDFs (1 February 2026)

    func testAPRRFareAllClasses() throws {
        // "ALLAINES AMBERIEU 462,61 58,20 € 89,10 € 143,00 € 190,70 € 32,80 €"
        let expected: [VehicleClass: Int] = [.class1: 5820, .class2: 8910, .class3: 14300, .class4: 19070, .class5: 3280]
        for (vehicleClass, cents) in expected {
            let quote = try calculator.quote(from: "ALLAINES", to: "AMBERIEU", vehicleClass: vehicleClass)
            XCTAssertEqual(quote.total, Money(cents: cents), "\(vehicleClass)")
            XCTAssertEqual(quote.lines.first?.distanceMeters, 462_610)
            XCTAssertTrue(quote.isComplete)
        }
    }

    func testAREAFareUsesCodedGrid() throws {
        // "3007 AIGUEBELETTE 3010 AIX NORD 24,00 3,50 € 5,50 € 7,60 €"
        let quote = try calculator.quote(from: "AIGUEBELETTE", to: "AIX NORD", vehicleClass: .class1)
        XCTAssertEqual(quote.total, Money(cents: 350))
        XCTAssertEqual(quote.lines.first?.networkID, "area")
        XCTAssertEqual(try calculator.quote(from: "AIGUEBELETTE", to: "AIX NORD", vehicleClass: .class3).total,
                       Money(cents: 760))
    }

    func testStationNamesContainingRoadNumbersParse() throws {
        // "3016 CRUSEILLES A 410 3400 Système Ouvert 25,00 3,20 € 4,90 € 7,40 €"
        let quote = try calculator.quote(from: "CRUSEILLES A 410", to: "Système Ouvert", vehicleClass: .class2)
        XCTAssertEqual(quote.total, Money(cents: 490))
    }

    func testA79DeuxChaisesBarrier() throws {
        // "ALLAINES DEUX CHAISES 261,00 28,90 € 46,00 € 71,70 € 96,20 € 17,60 €"
        let quote = try calculator.quote(from: "ALLAINES", to: "DEUX CHAISES", vehicleClass: .class5)
        XCTAssertEqual(quote.total, Money(cents: 1760))
    }

    // MARK: - VINCI Autoroutes
    //
    // Expected values come from VINCI's own "Tarifs des principales liaisons
    // 2026" table and the guides' worked examples, which are printed
    // separately from the charts the grids are parsed from.

    private func assertAllClasses(_ entry: String, _ exit: String, _ euros: [String],
                                  network: String, file: StaticString = #filePath, line: UInt = #line) throws {
        for (vehicleClass, expected) in zip(VehicleClass.allCases, euros) {
            let quote = try calculator.quote(from: entry, to: exit, vehicleClass: vehicleClass)
            XCTAssertEqual(quote.total?.formatted, expected, "\(entry) → \(exit) \(vehicleClass)", file: file, line: line)
            XCTAssertEqual(quote.lines.first?.networkID, network, file: file, line: line)
        }
    }

    func testASFMatchesPublishedLiaisons() throws {
        // "A9 Montpellier / Espagne (Perthus) 23,10 € 35,30 € 50,90 € 62,50 € 13,00 €"
        try assertAllClasses("Montpellier est", "Péage du Perthus",
                             ["23,10 €", "35,30 €", "50,90 €", "62,50 €", "13,00 €"], network: "asf")
        // "A9 Montpellier / Narbonne-est 9,70 € 14,70 € 21,50 € 27,50 € 5,60 €"
        try assertAllClasses("Montpellier est", "Narbonne est",
                             ["9,70 €", "14,70 €", "21,50 €", "27,50 €", "5,60 €"], network: "asf")
        // "A10 Tours Centre (Sorigny) / Bordeaux (Virsac) 34,90 € 53,50 € 79,30 € 105,00 € 21,50 €"
        try assertAllClasses("Péage de Tours centre", "Péage de Virsac",
                             ["34,90 €", "53,50 €", "79,30 €", "105,00 €", "21,50 €"], network: "asf")
    }

    func testEscotaMatchesPublishedLiaisons() throws {
        // "A8 Aix / Nice 21,20 € 31,50 € 45,00 € 62,60 € 13,00 €"
        try assertAllClasses("Aix (A57, A50, A52, A8)", "Nice-ouest",
                             ["21,20 €", "31,50 €", "45,00 €", "62,60 €", "13,00 €"], network: "escota")
        // "A51 Aix / Gap (La Saulce) 14,90 € 20,60 € 28,90 € 42,00 € 8,70 €"
        try assertAllClasses("Aix (A51)", "La Saulce",
                             ["14,90 €", "20,60 €", "28,90 €", "42,00 €", "8,70 €"], network: "escota")
        // Guide example: "La Saulce > Peyruis = 5,70 €"
        XCTAssertEqual(try calculator.quote(from: "La Saulce", to: "Peyruis", vehicleClass: .class1).total?.formatted,
                       "5,70 €")
    }

    func testCofirouteRowVerbatim() throws {
        // "A11 1 ABLIS A28 18 ALENCON NORD 21,80 € 33,70 € 52,30 € 72,90 € 12,90 €"
        let cofiroute = try XCTUnwrap(database.networks.first { $0.id == "cofiroute" })
        let fare = try XCTUnwrap(cofiroute.fare(from: try station("ABLIS"), to: try station("ALENCON NORD")))
        XCTAssertEqual(VehicleClass.allCases.map { fare.price(for: $0).formatted },
                       ["21,80 €", "33,70 €", "52,30 €", "72,90 €", "12,90 €"])
        XCTAssertEqual(fare.entry.code, "1")
        XCTAssertNil(fare.distanceMeters)
        // ASF prints the same trip in its A11/A28 chart; both grids agree.
        XCTAssertEqual(try calculator.quote(from: "ABLIS", to: "ALENCON NORD", vehicleClass: .class4).total,
                       Money(cents: 7290))
    }

    func testChartsAreSymmetric() throws {
        for network in database.networks where ["asf", "escota"].contains(network.id) {
            for fare in network.allFares {
                XCTAssertEqual(network.fare(from: fare.exit, to: fare.entry)?.price(for: .class1),
                               fare.price(for: .class1), "\(fare.entry.name) ↔ \(fare.exit.name)")
            }
        }
    }

    func testSameNamedStationsAreKeptApart() {
        // A837 has two exits called Tonnay-Charente; a barrier is not the exit it is named after.
        XCTAssertNotNil(database.station(named: "Tonnay-Charente (sortie 33)"))
        XCTAssertNotNil(database.station(named: "Tonnay-Charente (sortie 34)"))
        XCTAssertNotEqual(database.station(named: "Péage de Biriatou")?.key, database.station(named: "Biriatou")?.key)
    }

    func testNameLookupIgnoresAccentsCaseAndAbbreviations() {
        XCTAssertEqual(database.station(named: "Belleville-sur-Saône")?.name, "BELLEVILLE S/SAONE")
        XCTAssertEqual(database.station(named: "beaune sud")?.name, "BEAUNE SUD")
        XCTAssertEqual(database.search("besancon").map(\.name).sorted(),
                       ["BESANCON EST", "BESANCON NORD", "BESANCON OUEST"])
    }

    // MARK: - Exactness guarantees

    func testGridsNeverDisagreeOnSharedPairs() {
        var checked = 0
        for network in database.networks {
            for fare in network.allFares {
                for (other, otherFare) in database.fares(from: fare.entry, to: fare.exit) where other.id != network.id {
                    checked += 1
                    for vehicleClass in VehicleClass.allCases {
                        XCTAssertEqual(fare.price(for: vehicleClass), otherFare.price(for: vehicleClass),
                                       "\(network.id) vs \(other.id): \(fare.entry.name) → \(fare.exit.name)")
                    }
                }
            }
        }
        XCTAssertGreaterThan(checked, 0, "expected the APRR and ALIAE grids to overlap")
    }

    func testUnknownPairIsReportedNotEstimated() throws {
        // AREA-internal stations and APRR-only stations share no published ticket.
        XCTAssertThrowsError(try calculator.quote(from: "AIGUEBELETTE", to: "ALLAINES", vehicleClass: .class1)) { error in
            XCTAssertEqual(error as? TollError, .noPublishedFare(entry: "AIGUEBELETTE", exit: "ALLAINES"))
        }
    }

    func testMoneyFormattingAndSums() {
        XCTAssertEqual(Money(cents: 5820).formatted, "58,20 €")
        XCTAssertEqual(Money(cents: 5).formatted, "0,05 €")
        XCTAssertEqual((Money(cents: 10) + Money(cents: 20)).cents, 30)
        XCTAssertEqual(Money(cents: 5820).euros, Decimal(string: "58.2"))
    }

    // MARK: - Itineraries

    func testItineraryPrefersSinglePublishedTicket() throws {
        let stops = try ["ALLAINES", "AUXERRE NORD", "AMBERIEU"].map(station)
        let quote = calculator.quote(TollItinerary(stops: stops.map(TollStop.station)))
        // ALLAINES → AMBERIEU is published as one ticket, so AUXERRE NORD is a drive-by.
        XCTAssertEqual(quote.lines.count, 1)
        XCTAssertEqual(quote.total, Money(cents: 5820))
    }

    func testItinerarySplitsWhenNoSingleTicketExists() throws {
        // Leave APRR at AMBERIEU, then later use the AREA network on its own.
        let stops = try ["ALLAINES", "AMBERIEU", "AIGUEBELETTE", "AIX NORD"].map(station)
        let quote = calculator.quote(TollItinerary(stops: stops.map(TollStop.station)))
        XCTAssertEqual(quote.lines.map(\.exit?.name), ["AMBERIEU", "AIGUEBELETTE", "AIX NORD"])
        XCTAssertFalse(quote.isComplete, "AMBERIEU → AIGUEBELETTE is not a published ticket")
        XCTAssertEqual(quote.unpricedLines.count, 1)
        XCTAssertNil(quote.total, "an incomplete quote has no exact total")
        XCTAssertEqual(quote.totalRange.min, Money(cents: 5820 + 350))
    }

    // MARK: - Route detection

    func testDetectorFindsStationsOnRouteInOrder() throws {
        let entry = try XCTUnwrap(station("ALLAINES").booths.first)
        let exit = try XCTUnwrap(station("AMBERIEU").booths.first)
        // A synthetic polyline that passes exactly through both stations' booths.
        let route = [
            GeoPoint(latitude: entry.latitude - 0.01, longitude: entry.longitude),
            entry,
            GeoPoint(latitude: (entry.latitude + exit.latitude) / 2 + 1, longitude: (entry.longitude + exit.longitude) / 2),
            exit,
            GeoPoint(latitude: exit.latitude + 0.01, longitude: exit.longitude),
        ]
        let detector = RouteTollDetector(database: database)
        let passages = detector.passages(along: route)
        XCTAssertEqual(passages.first?.stop.key, "ALLAINES")
        // Other grids call the same interchange "Ambérieu-en-Bugey"; both are detected.
        XCTAssertTrue(["AMBERIEU", "AMBERIEU EN BUGEY"].contains(passages.last?.stop.key ?? ""))
        let quote = calculator.quote(stops: passages.map(\.stop), vehicle: Vehicle(.class1))
        XCTAssertEqual(quote.total, Money(cents: 5820))
    }

    func testDetectorIgnoresStationsAwayFromRoute() throws {
        let booth = try XCTUnwrap(station("ALLAINES").booths.first)
        // Parallel line ~200 m east of the booth.
        let offset = 200 / (111_320 * cos(booth.latitude * .pi / 180))
        let route = [GeoPoint(latitude: booth.latitude - 0.01, longitude: booth.longitude + offset),
                     GeoPoint(latitude: booth.latitude + 0.01, longitude: booth.longitude + offset)]
        XCTAssertFalse(RouteTollDetector(database: database).passages(along: route).contains { $0.stop.key == "ALLAINES" })
    }

    func testGeoDistance() {
        let paris = GeoPoint(latitude: 48.8566, longitude: 2.3522)
        let lyon = GeoPoint(latitude: 45.7640, longitude: 4.8357)
        XCTAssertEqual(Geo.distance(paris, lyon), 391_500, accuracy: 1_500)
    }

    private func station(_ name: String) throws -> TollStation {
        try XCTUnwrap(database.station(named: name), name)
    }
}
