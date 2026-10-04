import XCTest
@testable import TollKit

/// A trip must change ticket at every toll plaza it goes through, even when a
/// grid publishes one fare for the whole trip by another path.
final class RouteSplitTests: XCTestCase {
    var database: TollDatabase { TollKitTests.database }
    var calculator: TollCalculator { TollCalculator(database: database) }

    func stops(_ names: [String]) throws -> [TollStop] {
        try names.map { .station(try XCTUnwrap(database.station(named: $0), $0)) }
    }

    func testAixToPeyrehorade() throws {
        // Stations in the order a route meets them: the plazas it goes through
        // (main-line barriers, and the first and last plaza) and the exits it
        // drives past that are placed at their interchange. Exits placed at
        // their ramp booths are not met unless used.
        let trip = try stops([
            "Cannet-de-Meyreuil", "Aix (A57, A50, A52, A8)", "Aix ouest", "Péage de Lançon (Aix/Berre)",
            "St-Martin-de-Crau est", "Péage de St-Martin-de-Crau", "Péage d’Arles", "Péage de Toulouse sud/ouest", "Péage de Toulouse sud/est",
            "Le Palays", "Francazal", "Roques", "Péage de Muret", "Muret nord", "Martres-Tolosane",
            "Péage de Lestelle", "Péage de Sames", "Peyrehorade",
        ])
        let quote = calculator.quote(stops: trip, vehicle: Vehicle(.class1), plazasAreStops: true)
        let priced = quote.lines.compactMap { line in line.price.map { (line.title, $0.cents) } }
        // Ulys bills the same: Canet 1,00 (La Barque), Lançon → St-Martin-de-Crau
        // 5,20, Arles → Toulouse sud-ouest 34,80, Muret 1,80, Lestelle → Sames 22,40.
        XCTAssertEqual(priced.map(\.1), [100, 520, 3480, 180, 2240, 260])
        XCTAssertEqual(priced.map(\.0), [
            "Cannet-de-Meyreuil → Aix (A57, A50, A52, A8)", "Aix ouest → Péage de St-Martin-de-Crau",
            "Péage d’Arles → Le Palays", "Francazal → Muret nord", "Martres-Tolosane → Péage de Sames",
            "Péage de Sames → Peyrehorade",
        ])
        // Before, one ASF fare covered Toulouse → Peyrehorade by the A62 and A65
        // (Le Palays → Peyrehorade, 54,90 €) and ran through Muret, Lestelle and Sames.
        XCTAssertFalse(quote.lines.contains { $0.title == "Le Palays → Peyrehorade" })
        // The stretches between plazas with no published fare are free roads
        // (Aix, Arles, the Toulouse ring, the A64 before Lestelle); they stay
        // explicit lines without a price.
        XCTAssertEqual(quote.unpricedLines.count, 4)
    }

    func testFareEqualToOneSideRunsThroughThePlaza() throws {
        // Mirambeau → Carbon-Blanc (6,10) = Mirambeau → Virsac barrier: the A10
        // is free after Virsac, so the published fare is kept as one ticket.
        let quote = calculator.quote(stops: try stops(["Mirambeau", "Péage de Virsac", "Carbon-Blanc"]),
                                     vehicle: Vehicle(.class1), plazasAreStops: true)
        XCTAssertEqual(quote.lines.count, 1)
        XCTAssertEqual(quote.total, Money(cents: 610))
    }

    func testNamedItineraryKeepsWaypoints() throws {
        // Named by hand, a station in the middle is a waypoint: the same trip
        // keeps the single ASF fare (that path is the user's choice).
        let quote = calculator.quote(stops: try stops(["Le Palays", "Péage de Muret", "Peyrehorade"]),
                                     vehicle: Vehicle(.class1))
        XCTAssertEqual(quote.total, Money(cents: 5490))
        let route = calculator.quote(stops: try stops(["Le Palays", "Péage de Muret", "Peyrehorade"]),
                                     vehicle: Vehicle(.class1), plazasAreStops: true)
        XCTAssertNil(route.total)
    }
}
