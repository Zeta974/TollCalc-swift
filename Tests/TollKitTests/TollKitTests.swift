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
        XCTAssertTrue(database.networks.allSatisfy { $0.validFrom == "2026-02-01" })
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
        let quote = calculator.quote(TollItinerary(stops: stops, vehicleClass: .class1))
        // ALLAINES → AMBERIEU is published as one ticket, so AUXERRE NORD is a drive-by.
        XCTAssertEqual(quote.lines.count, 1)
        XCTAssertEqual(quote.total, Money(cents: 5820))
    }

    func testItinerarySplitsWhenNoSingleTicketExists() throws {
        // Leave APRR at AMBERIEU, then later use the AREA network on its own.
        let stops = try ["ALLAINES", "AMBERIEU", "AIGUEBELETTE", "AIX NORD"].map(station)
        let quote = calculator.quote(TollItinerary(stops: stops, vehicleClass: .class1))
        XCTAssertEqual(quote.lines.map(\.exit.name), ["AMBERIEU", "AIGUEBELETTE", "AIX NORD"])
        XCTAssertFalse(quote.isComplete, "AMBERIEU → AIGUEBELETTE is not a published ticket")
        XCTAssertEqual(quote.unpricedLines.count, 1)
        XCTAssertEqual(quote.total, Money(cents: 5820 + 350))
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
        XCTAssertEqual(passages.first?.station.key, "ALLAINES")
        XCTAssertEqual(passages.last?.station.key, "AMBERIEU")
        let quote = calculator.quote(passages: passages.map(\.station), vehicleClass: .class1)
        XCTAssertEqual(quote.total, Money(cents: 5820))
    }

    func testDetectorIgnoresStationsAwayFromRoute() throws {
        let booth = try XCTUnwrap(station("ALLAINES").booths.first)
        // Parallel line ~200 m east of the booth.
        let offset = 200 / (111_320 * cos(booth.latitude * .pi / 180))
        let route = [GeoPoint(latitude: booth.latitude - 0.01, longitude: booth.longitude + offset),
                     GeoPoint(latitude: booth.latitude + 0.01, longitude: booth.longitude + offset)]
        XCTAssertFalse(RouteTollDetector(database: database).passages(along: route).contains { $0.station.key == "ALLAINES" })
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
