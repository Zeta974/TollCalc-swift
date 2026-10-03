import XCTest
@testable import TollKit

/// Duplex A86 (VINCI leaflet, prices from 1 January 2026). Expected values
/// are read from the leaflet's tables.
final class DuplexTests: XCTestCase {
    var database: TollDatabase { TollKitTests.database }
    var calculator: TollCalculator { TollCalculator(database: database) }

    func station(_ name: String) throws -> TollStop {
        .point(try XCTUnwrap(database.point(named: "Duplex A86 \(name)"), name))
    }

    func paris(_ month: Int, _ day: Int, _ hour: Int, _ minute: Int = 0) -> Date {
        PointTariff.paris.date(from: DateComponents(year: 2026, month: month, day: day, hour: hour, minute: minute))!
    }

    func price(_ entry: String, _ exit: String, at date: Date?, vehicle: Vehicle = Vehicle(.class1)) throws -> TollQuote {
        calculator.quote(stops: [try station(entry), try station(exit)], vehicle: vehicle, date: date)
    }

    func testDayTypes() throws {
        // Rueil -> Vélizy
        XCTAssertEqual(try price("Rueil", "Vélizy", at: paris(10, 1, 8, 15)).total, Money(cents: 1170))   // Thursday
        XCTAssertEqual(try price("Rueil", "Vélizy", at: paris(10, 1, 16, 30)).total, Money(cents: 1290))
        XCTAssertEqual(try price("Rueil", "Vélizy", at: paris(10, 2, 17, 15)).total, Money(cents: 1490))  // Friday
        XCTAssertEqual(try price("Rueil", "Vélizy", at: paris(11, 10, 16, 30)).total, Money(cents: 1470)) // eve of 11 Nov
        XCTAssertEqual(try price("Rueil", "Vélizy", at: paris(11, 11, 12)).total, Money(cents: 1210))     // 11 Nov
        XCTAssertEqual(try price("Rueil", "Vélizy", at: paris(10, 3, 9, 30)).total, Money(cents: 1040))   // Saturday
        XCTAssertEqual(try price("Rueil", "Vélizy", at: paris(8, 10, 9, 30)).total, Money(cents: 1110))   // August, Monday
        XCTAssertEqual(try price("Rueil", "Vélizy", at: paris(8, 15, 12)).total, Money(cents: 1210))      // 15 Aug, a Saturday
        XCTAssertEqual(try price("Rueil", "Vélizy", at: paris(8, 16, 12)).total, Money(cents: 1210))      // Sunday in August
        XCTAssertEqual(try price("Rueil", "Vélizy", at: paris(10, 1, 1)).total, Money(cents: 200))        // 00h-4h30
        XCTAssertEqual(try price("Rueil", "Vélizy", at: paris(10, 1, 23, 59)).total, Money(cents: 310))   // 22h-00h
    }

    func testDirectionsAndStations() throws {
        // Same time, other direction: Vélizy -> Rueil 14,9
        XCTAssertEqual(try price("Vélizy", "Rueil", at: paris(10, 1, 8, 15)).total, Money(cents: 1490))
        // From Vaucresson, one table for both exits: Saturday 12h, 6,6
        XCTAssertEqual(try price("Vaucresson", "Rueil", at: paris(10, 3, 12)).total, Money(cents: 660))
        XCTAssertEqual(try price("Vaucresson", "Vélizy", at: paris(10, 3, 12)).total, Money(cents: 660))
        // Without a time: a range, asking for it
        let undated = try price("Rueil", "Vélizy", at: nil)
        XCTAssertEqual(undated.missingInputs, [.date])
        XCTAssertEqual(undated.totalRange.min, Money(cents: 200))
        // A station alone is not a trip
        XCTAssertNil(calculator.quote(stops: [try station("Rueil")], vehicle: Vehicle(.class1)).total)
        // Passing near Vaucresson on the way from Rueil to Vélizy does not split the trip
        let through = calculator.quote(stops: [try station("Rueil"), try station("Vaucresson"), try station("Vélizy")],
                                       vehicle: Vehicle(.class1), date: paris(10, 1, 8, 15))
        XCTAssertEqual(through.lines.count, 1)
        XCTAssertEqual(through.total, Money(cents: 1170))
    }

    func testTollBadge() throws {
        // Rueil -> Vaucresson, Thursday 18h: cash 13,7, badge 11,5
        XCTAssertEqual(try price("Rueil", "Vaucresson", at: paris(10, 1, 18)).total, Money(cents: 1370))
        let badge = Vehicle(.class1, subscriptions: [.tollBadge])
        XCTAssertEqual(try price("Rueil", "Vaucresson", at: paris(10, 1, 18), vehicle: badge).total, Money(cents: 1150))
        // An Ulys Tunnel Pass+ is a toll badge too
        let pradoPlus = Vehicle(.class1, subscriptions: [.pradoTunnelPassPlus])
        XCTAssertEqual(try price("Rueil", "Vaucresson", at: paris(10, 1, 18), vehicle: pradoPlus).total, Money(cents: 1150))
        // Rueil -> Vélizy has one price for every payment method
        XCTAssertEqual(try price("Rueil", "Vélizy", at: paris(10, 1, 8, 15), vehicle: badge).total, Money(cents: 1170))
    }
}
