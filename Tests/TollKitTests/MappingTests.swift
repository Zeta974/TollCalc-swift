import XCTest
@testable import TollKit

/// Station positions: what the route detector relies on.
final class MappingTests: XCTestCase {
    var database: TollDatabase { TollKitTests.database }
    var calculator: TollCalculator { TollCalculator(database: database) }

    func testEverythingOnARouteHasAPosition() {
        let stations = database.stations.filter { !$0.isVirtual && $0.location == nil }
        XCTAssertEqual(stations.map(\.id), [])
        // Combined points (A79 transits, Duplex A86 trips, both Prado tunnels) are
        // found through the points they combine.
        let points = database.points.filter { $0.combines.isEmpty && $0.booths.isEmpty }
        XCTAssertEqual(points.map(\.id), [])
    }

    func testHomonymsStayApart() throws {
        // ATMB "Saint-Julien" (en-Genevois) and SFTRF "St Julien" (Mont-Denis)
        let julien = database.stations.filter { $0.key == "ST JULIEN" }
        XCTAssertEqual(Set(julien.map(\.networkID)), ["atmb", "sftrf"])
        let a = try XCTUnwrap(julien.first?.location), b = try XCTUnwrap(julien.last?.location)
        XCTAssertGreaterThan(Geo.distance(a, b), 90_000)
    }

    func testOnePlazaTwoStations() throws {
        // The A62 plaza north of Toulouse is two ASF entries priced differently
        // (Saint-Jory: 1,10 from nord/est, 0,80 from nord/ouest). A route cannot
        // tell them apart: the quote is the range and asks which.
        let est = try XCTUnwrap(database.station(named: "Péage de Toulouse nord/est"))
        let ouest = try XCTUnwrap(database.station(named: "Péage de Toulouse nord/ouest"))
        let jory = try XCTUnwrap(database.station(named: "Saint-Jory"))
        XCTAssertEqual(est.location, ouest.location)
        let quote = calculator.quote(stops: [.station(est), .station(ouest), .station(jory)], vehicle: Vehicle(.class1))
        XCTAssertNil(quote.total)
        XCTAssertEqual(quote.missingInputs, [.station])
        XCTAssertEqual(quote.totalRange.min, Money(cents: 80))
        XCTAssertEqual(quote.totalRange.max, Money(cents: 110))
        // Named, the price is exact
        XCTAssertEqual(try calculator.quote(from: est.name, to: jory.name, vehicleClass: .class1).total, Money(cents: 110))
    }

    func testIttenheimSideStationIsOnTheRamps() throws {
        // OSM names all four booths "Barrière de péage d'Ittenheim"; two are on the
        // A355 (the barrier), two on the ramps (the side station).
        let barrier = try XCTUnwrap(database.point(named: "Barrière d'Ittenheim"))
        let side = try XCTUnwrap(database.point(named: "Gare latérale d'Ittenheim"))
        XCTAssertEqual(barrier.booths.count, 2)
        XCTAssertEqual(side.booths.count, 2)
        XCTAssertTrue(Set(barrier.booths).isDisjoint(with: side.booths))
    }

    func station(_ network: String, _ name: String) throws -> GeoPoint {
        try XCTUnwrap(database.networks.first { $0.id == network }?.station(named: name)?.location, "\(network):\(name)")
    }

    func testCorrectedPositions() throws {
        // Cofiroute "ANGERS" was placed at Ancenis (the guide prints it with the
        // other station's exit number); it is west of Angers, before Saint-Jean-de-Linières.
        let angers = try station("cofiroute", "ANGERS")
        let linieres = try station("cofiroute", "SAINT JEAN DE LINIERES")
        XCTAssertLessThan(Geo.distance(angers, linieres), 10_000)
        // Cofiroute "CHALONS - LA VEUVE" was placed 55 km away, near Sainte-Menehould.
        let veuve = try station("cofiroute", "CHALONS - LA VEUVE")
        let sanef = try station("sanef", "CHÂLONS-EN-CHAMPAGNE / LA VEUVE")
        XCTAssertLessThan(Geo.distance(veuve, sanef), 3_000)
    }
}
