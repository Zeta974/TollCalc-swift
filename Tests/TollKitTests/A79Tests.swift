import XCTest
@testable import TollKit

/// A79 free-flow gantries (ALIAE leaflet, 1 February 2026).
final class A79Tests: XCTestCase {
    var database: TollDatabase { TollKitTests.database }
    var calculator: TollCalculator { TollCalculator(database: database) }

    func gantry(_ name: String) throws -> TollStop {
        .point(try XCTUnwrap(database.point(named: "A79 \(name)"), name))
    }

    var eastbound: [TollStop] {
        get throws {
            try ["Le Montet Ouest", "Le Montet Est", "Montbeugny Ouest", "Montbeugny Est",
                 "Molinet Ouest", "Molinet Est"].map(gantry)
        }
    }

    func testUlysMontluconToMacon() throws {
        // Ulys estimate, class 1: Montluçon -> Deux Chaises 3,30; Le Montet,
        // Montbeugny and Molinet in transit 1,00 + 1,90 + 1,30; total 7,50.
        let stops = [TollStop.station(try XCTUnwrap(database.station(named: "MONTLUCON"))),
                     .station(try XCTUnwrap(database.station(named: "DEUX CHAISES")))] + (try eastbound)
        let quote = calculator.quote(stops: stops, vehicle: Vehicle(.class1))
        XCTAssertEqual(quote.lines.map(\.amount.exactValue), [330, 100, 190, 130].map { Money(cents: $0) as Money? })
        XCTAssertEqual(quote.total, Money(cents: 750))
    }

    func testLeafletTrips() throws {
        // Leaflet page 3, class 1 base / VTFE, from Le Montet Ouest
        let all = try eastbound
        let car = Vehicle(.class1), electric = Vehicle(.class1, isVeryLowEmission: true)
        XCTAssertEqual(calculator.quote(stops: Array(all[0..<1]), vehicle: car).total, Money(cents: 20))   // -> Le Montet
        XCTAssertEqual(calculator.quote(stops: Array(all[0..<3]), vehicle: car).total, Money(cents: 210))  // -> Montbeugny
        XCTAssertEqual(calculator.quote(stops: Array(all[0..<5]), vehicle: car).total, Money(cents: 410))  // -> Molinet
        XCTAssertEqual(calculator.quote(stops: all, vehicle: car).total, Money(cents: 420))
        XCTAssertEqual(calculator.quote(stops: all, vehicle: electric).total, Money(cents: 320))
        // Westbound too: Molinet Est -> Le Montet Ouest 4,20
        XCTAssertEqual(calculator.quote(stops: all.reversed(), vehicle: car).total, Money(cents: 420))
        // Le Montet -> Montbeugny (Le Montet Est, Montbeugny Ouest): 2,20
        XCTAssertEqual(calculator.quote(stops: Array(all[1..<3]), vehicle: car).total, Money(cents: 220))
    }

    func testHeavyVehiclesByEuroClass() throws {
        let all = try eastbound
        // Class 3 from Le Montet Ouest to Molinet Est: noir 13,50, vert 11,70
        XCTAssertEqual(calculator.quote(stops: all, vehicle: Vehicle(.class3, euroClass: .euro3)).total, Money(cents: 1350))
        XCTAssertEqual(calculator.quote(stops: all, vehicle: Vehicle(.class3, euroClass: .euro6)).total, Money(cents: 1170))
        // No price for an undeclared Euro class: a range, asking for it
        let unknown = calculator.quote(stops: all, vehicle: Vehicle(.class3))
        XCTAssertNil(unknown.total)
        XCTAssertEqual(unknown.missingInputs, [.euroClass])
        XCTAssertEqual(unknown.totalRange.min, Money(cents: 1170))
        XCTAssertEqual(unknown.totalRange.max, Money(cents: 1350))
    }

    func testRouteDetection() throws {
        // A polyline through the six gantries, eastbound
        let route = try eastbound.map { try XCTUnwrap($0.location) }
        let (passages, quote) = calculator.quote(route: route, vehicle: Vehicle(.class1))
        XCTAssertEqual(passages.count, 6)
        XCTAssertEqual(quote.total, Money(cents: 420))
    }
}
