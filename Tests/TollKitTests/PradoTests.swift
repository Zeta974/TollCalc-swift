import XCTest
@testable import TollKit

/// Tunnels Prado (Marseille): public price and Tunnel Pass subscription
/// prices by time of day. Values from the operator's price page.
final class PradoTests: XCTestCase {
    var database: TollDatabase { TollKitTests.database }
    var calculator: TollCalculator { TollCalculator(database: database) }

    func tunnel(_ name: String) throws -> TollStop {
        .point(try XCTUnwrap(database.point(named: name), name))
    }

    func paris(_ day: Int, _ hour: Int, _ minute: Int = 0) -> Date {
        PointTariff.paris.date(from: DateComponents(year: 2026, month: 10, day: day, hour: hour, minute: minute))!
    }

    func testPublicPrice() throws {
        let car = Vehicle(.class1)
        XCTAssertEqual(calculator.quote(stops: [try tunnel("Tunnel Prado Carénage")], vehicle: car).total, Money(cents: 330))
        XCTAssertEqual(calculator.quote(stops: [try tunnel("Tunnel Prado Sud")], vehicle: car).total, Money(cents: 290))
        // Both tunnels in a row: 6,20
        let both = calculator.quote(stops: [try tunnel("Tunnel Prado Sud"), try tunnel("Tunnel Prado Carénage")], vehicle: car)
        XCTAssertEqual(both.lines.count, 1)
        XCTAssertEqual(both.total, Money(cents: 620))
        // The page prices no other class
        XCTAssertNil(calculator.quote(stops: [try tunnel("Tunnel Prado Sud")], vehicle: Vehicle(.class2)).total)
    }

    func testTunnelPass() throws {
        let subscriber = Vehicle(.class1, subscriptions: [.pradoTunnelPass])
        let carenage = [try tunnel("Tunnel Prado Carénage")]
        // 7h–20h: 3,00; 20h–7h: 2,70 (Thursday 1 and Saturday 3 October 2026)
        XCTAssertEqual(calculator.quote(stops: carenage, vehicle: subscriber, date: paris(1, 7)).total, Money(cents: 300))
        XCTAssertEqual(calculator.quote(stops: carenage, vehicle: subscriber, date: paris(1, 19, 59)).total, Money(cents: 300))
        XCTAssertEqual(calculator.quote(stops: carenage, vehicle: subscriber, date: paris(3, 20)).total, Money(cents: 270))
        XCTAssertEqual(calculator.quote(stops: carenage, vehicle: subscriber, date: paris(3, 6, 59)).total, Money(cents: 270))
        // Without a time: the range, asking for it
        let undated = calculator.quote(stops: carenage, vehicle: subscriber)
        XCTAssertEqual(undated.missingInputs, [.date])
        XCTAssertEqual(undated.totalRange.min, Money(cents: 270))
        XCTAssertEqual(undated.totalRange.max, Money(cents: 300))
        // Tunnel Pass+: same prices; both tunnels 5,80 by day, 5,40 by night
        let plus = Vehicle(.class1, subscriptions: [.pradoTunnelPassPlus])
        let both = [try tunnel("Tunnel Prado Carénage"), try tunnel("Tunnel Prado Sud")]
        XCTAssertEqual(calculator.quote(stops: both, vehicle: plus, date: paris(1, 12)).total, Money(cents: 580))
        XCTAssertEqual(calculator.quote(stops: both, vehicle: plus, date: paris(1, 23)).total, Money(cents: 540))
        // A subscription does not change motorway prices
        XCTAssertEqual(try calculator.quote(from: "MONTLUCON", to: "DEUX CHAISES", vehicleClass: .class1).total,
                       Money(cents: 330))
    }
}
