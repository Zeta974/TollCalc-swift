import XCTest
@testable import TollKit

/// Sanef and SAPN grids (1 February 2026). Expected values are read from the
/// PDFs' tables.
final class SanefTests: XCTestCase {
    var database: TollDatabase { TollKitTests.database }
    var calculator: TollCalculator { TollCalculator(database: database) }

    func testSanefGrid() throws {
        // A16: "1,1 BOULOGNE SUD N°28" (class 1) and "1,6" (class 2) from Boulogne Est
        XCTAssertEqual(try calculator.quote(from: "BOULOGNE EST (péage d'Herquelingue)", to: "BOULOGNE SUD",
                                            vehicleClass: .class1).total, Money(cents: 110))
        XCTAssertEqual(try calculator.quote(from: "BOULOGNE SUD", to: "BOULOGNE EST (péage d'Herquelingue)",
                                            vehicleClass: .class2).total, Money(cents: 160))
        // Open-system exit printed left of its cell: "VALLÉE DE LA HEM N°2 | 1,3"
        let hem = try XCTUnwrap(database.station(named: "VALLÉE DE LA HEM"))
        XCTAssertEqual(hem.code, "2")
    }

    func testSAPNGrid() throws {
        // A13: Caen -> Poissy / Orgeval … Mantes-Sud, classes 1 and 2
        XCTAssertEqual(try calculator.quote(from: "CAEN", to: "POISSY / ORGEVAL N°7 à MANTES-SUD N°12",
                                            vehicleClass: .class1).total, Money(cents: 1800))
        XCTAssertEqual(try calculator.quote(from: "CAEN", to: "POISSY / ORGEVAL N°7 à MANTES-SUD N°12",
                                            vehicleClass: .class2).total, Money(cents: 2740))
        // A29 nord: Le Havre -> St-Saëns
        XCTAssertEqual(try calculator.quote(from: "LE HAVRE N°5 / A131", to: "ST-SAËNS N°10 / A28",
                                            vehicleClass: .class1).total, Money(cents: 950))
        // Grey cell: La Haie-Tondue has no priced trips
        XCTAssertThrowsError(try calculator.quote(from: "CAEN", to: "LA HAIE-TONDUE", vehicleClass: .class1))
    }

    func testA1Modulation() throws {
        // Calais (Setques) -> Compiègne ouest, class 1: normal 18,5, green 16,2, red 20,8
        let trip = try calculator.quote(from: "CALAIS (péage de Setques)", to: "COMPIÈGNE OUEST", vehicleClass: .class1)
        XCTAssertNil(trip.total)
        XCTAssertEqual(trip.missingInputs, [.sanefA1Period])
        XCTAssertEqual(trip.totalRange.min, Money(cents: 1620))
        XCTAssertEqual(trip.totalRange.max, Money(cents: 2080))
        for (period, cents) in [(SanefA1Period.normal, 1850), (.green, 1620), (.red, 2080)] {
            XCTAssertEqual(try calculator.quote(from: "CALAIS (péage de Setques)", to: "COMPIÈGNE OUEST",
                                                vehicle: Vehicle(.class1), sanefA1Period: period).total,
                           Money(cents: cents))
        }
        // Other classes are not modulated.
        XCTAssertNotNil(try calculator.quote(from: "CALAIS (péage de Setques)", to: "COMPIÈGNE OUEST",
                                             vehicleClass: .class2).total)
    }

    func testA14Montesson() throws {
        let montesson = try XCTUnwrap(database.point(named: "Péage de Montesson"))
        let paris = PointTariff.paris
        func at(_ y: Int, _ m: Int, _ d: Int, _ h: Int) -> Date {
            paris.date(from: DateComponents(year: y, month: m, day: d, hour: h))!
        }
        // Wednesday 11:00 reduced, Wednesday 08:00 base, Saturday 11:00 base
        XCTAssertEqual(montesson.amount(for: Vehicle(.class1), at: at(2026, 10, 7, 11)), .exact(Money(cents: 660)))
        XCTAssertEqual(montesson.amount(for: Vehicle(.class1), at: at(2026, 10, 7, 8)), .exact(Money(cents: 1080)))
        XCTAssertEqual(montesson.amount(for: Vehicle(.class1), at: at(2026, 10, 10, 11)), .exact(Money(cents: 1080)))
        // Public holiday (Ascension, Thursday 14 May 2026) 11:00: base
        XCTAssertEqual(montesson.amount(for: Vehicle(.class1), at: at(2026, 5, 14, 11)), .exact(Money(cents: 1080)))
        // Saturday 03:00: the order does not say whether Friday night's reduced rate runs on
        XCTAssertEqual(montesson.amount(for: Vehicle(.class1), at: at(2026, 10, 10, 3)),
                       .range(min: Money(cents: 660), max: Money(cents: 1080), needs: []))
        let chambourcy = try XCTUnwrap(database.point(named: "Péage de Chambourcy"))
        XCTAssertEqual(chambourcy.amount(for: Vehicle(.class4), at: nil), .exact(Money(cents: 1240)))
    }
}
