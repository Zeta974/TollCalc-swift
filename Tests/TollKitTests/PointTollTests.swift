import XCTest
@testable import TollKit

/// Networks from the Journal officiel order of 28 January 2026 and the toll
/// points (barriers, bridge, priced sections). Expected values are read from
/// the order's tables.
final class PointTollTests: XCTestCase {
    var database: TollDatabase { TollKitTests.database }
    var calculator: TollCalculator { TollCalculator(database: database) }

    /// Local French time.
    private func paris(_ y: Int, _ m: Int, _ d: Int, _ h: Int, _ min: Int) -> Date {
        PointTariff.paris.date(from: DateComponents(year: y, month: m, day: d, hour: h, minute: min))!
    }

    private func point(_ name: String) throws -> TollPoint {
        try XCTUnwrap(database.point(named: name), name)
    }

    // MARK: Closed grids from the JO order

    func testJournalOfficielGrids() throws {
        // ATMB annex I: Chatillon -> Origine (Mont-Blanc tunnel platform), classes 1 and 5
        XCTAssertEqual(try calculator.quote(from: "Chatillon", to: "Origine", vehicleClass: .class1).total, Money(cents: 1410))
        XCTAssertEqual(try calculator.quote(from: "Origine", to: "Chatillon", vehicleClass: .class5).total, Money(cents: 880))
        // Findrol and Scientrier share one row of the ATMB table.
        XCTAssertEqual(try calculator.quote(from: "Scientrier", to: "Chatillon", vehicleClass: .class1).total, Money(cents: 930))
        XCTAssertEqual(try calculator.quote(from: "Bonneville-Ouest", to: "Scientrier", vehicleClass: .class4).total, Money(cents: 480))
        // SFTRF annex II: Aiton -> Modane
        XCTAssertEqual(try calculator.quote(from: "Aiton", to: "Modane", vehicleClass: .class3).total, Money(cents: 3180))
        // ALIS annex IV: Alençon -> A13
        XCTAssertEqual(try calculator.quote(from: "Alençon", to: "A13", vehicleClass: .class4).total, Money(cents: 10760))
        // ARCOUR annex V: Piffonds -> Chevilly (first station printed above the table)
        XCTAssertEqual(try calculator.quote(from: "Piffonds", to: "Chevilly", vehicleClass: .class1).total, Money(cents: 2390))
        // ADELAC annex VI
        XCTAssertEqual(try calculator.quote(from: "Saint-Julien-en-Genevois", to: "BPV Villy-le-Pelloux",
                                            vehicleClass: .class2).total, Money(cents: 1560))
        // A'LIÉNOR annex VII: wrapped names ("Mont-\\nde-Marsan", "Pau\\n(A64)")
        XCTAssertEqual(try calculator.quote(from: "Langon (A62)", to: "Pau (A64)", vehicleClass: .class5).total, Money(cents: 1730))
        XCTAssertEqual(try calculator.quote(from: "Mont-de-Marsan", to: "Roquefort", vehicleClass: .class1).total, Money(cents: 180))
        // ALICORNE annex VIII
        XCTAssertEqual(try calculator.quote(from: "Falaise Ouest", to: "Sées", vehicleClass: .class1).total, Money(cents: 870))
    }

    func testBlankCellsAreNotTrips() {
        // A'LIÉNOR: nothing is printed between the two Aire-sur-l'Adour exits, nor Aire Sud -> Garlin.
        XCTAssertThrowsError(try calculator.quote(from: "Aire-sur-l'Adour Sud", to: "Garlin", vehicleClass: .class1))
        // ALICORNE: the Argentan sud row is empty.
        XCTAssertThrowsError(try calculator.quote(from: "Argentan sud", to: "Falaise Ouest", vehicleClass: .class1))
    }

    // MARK: Viaduc de Millau (season)

    func testMillauSeasons() throws {
        let millau = try point("Viaduc de Millau")
        XCTAssertEqual(millau.amount(for: Vehicle(.class1), at: paris(2026, 7, 14, 12, 0)), .exact(Money(cents: 1380)))
        XCTAssertEqual(millau.amount(for: Vehicle(.class1), at: paris(2026, 6, 15, 0, 5)), .exact(Money(cents: 1380)))
        XCTAssertEqual(millau.amount(for: Vehicle(.class1), at: paris(2026, 9, 16, 12, 0)), .exact(Money(cents: 1130)))
        XCTAssertEqual(millau.amount(for: Vehicle(.class2), at: paris(2026, 12, 24, 12, 0)), .exact(Money(cents: 1700)))
        // Heavy vehicles and motorbikes pay the same all year: no date needed.
        XCTAssertEqual(millau.amount(for: Vehicle(.class4), at: nil), .exact(Money(cents: 4770)))
        XCTAssertEqual(millau.amount(for: Vehicle(.class1), at: nil),
                       .range(min: Money(cents: 1130), max: Money(cents: 1380), needs: [.date]))
    }

    // MARK: A63 Atlandes (classes A/B/C, Euro, GNV)

    func testAtlandesHeavyClasses() throws {
        let castets = try point("Barrière de Castets")
        XCTAssertEqual(castets.amount(for: Vehicle(.class1), at: nil), .exact(Money(cents: 440)))
        // Class 3 with PTAC <= 12 t is class A; Euro 4 -> 17,80
        XCTAssertEqual(castets.amount(for: Vehicle(.class3, euroClass: .euro4, grossWeightTonnes: 7.5), at: nil),
                       .exact(Money(cents: 1780)))
        // Class 4 with 5 axles is class C; undeclared Euro class -> "non modulé" 21,64
        XCTAssertEqual(castets.amount(for: Vehicle(.class4, axles: 5), at: nil), .exact(Money(cents: 2164)))
        // Natural gas, class C
        XCTAssertEqual(castets.amount(for: Vehicle(.class4, euroClass: .euro6, axles: 5, usesNaturalGas: true), at: nil),
                       .exact(Money(cents: 1950)))
        // Axles unknown: B or C
        XCTAssertEqual(castets.amount(for: Vehicle(.class4, euroClass: .euro6), at: nil),
                       .range(min: Money(cents: 1670), max: Money(cents: 2150), needs: [.axles]))
    }

    // MARK: A150 Albea (Euro 0–7)

    func testAlbeaEuroClasses() throws {
        let barrier = try point("Barrière de l'A150 (Écalles-Alix / Barentin)")
        XCTAssertEqual(barrier.amount(for: Vehicle(.class2), at: nil), .exact(Money(cents: 670)))
        XCTAssertEqual(barrier.amount(for: Vehicle(.class3), at: nil), .exact(Money(cents: 850)))
        XCTAssertEqual(barrier.amount(for: Vehicle(.class4, euroClass: .euro7), at: nil), .exact(Money(cents: 1150)))
    }

    // MARK: A355 (time bands, holidays)

    func testA355TimeBands() throws {
        let barrier = try point("Barrière d'Ittenheim")
        let side = try point("Gare latérale d'Ittenheim")
        // Monday 5 Oct 2026 08:00 -> band E: 2,60 per section, the barrier collects two sections.
        XCTAssertEqual(side.amount(for: Vehicle(.class1), at: paris(2026, 10, 5, 8, 0)), .exact(Money(cents: 260)))
        XCTAssertEqual(barrier.amount(for: Vehicle(.class1), at: paris(2026, 10, 5, 8, 0)), .exact(Money(cents: 520)))
        // Friday 16:15 is band E too; Friday 16:45 is band X (2,60 as well for class 1, 3,80 for class 2).
        XCTAssertEqual(side.amount(for: Vehicle(.class2), at: paris(2026, 10, 9, 16, 15)), .exact(Money(cents: 380)))
        XCTAssertEqual(side.amount(for: Vehicle(.class2), at: paris(2026, 10, 9, 16, 45)), .exact(Money(cents: 380)))
        // Sunday 10:00 -> band P: 2,70
        XCTAssertEqual(side.amount(for: Vehicle(.class1), at: paris(2026, 10, 4, 10, 0)), .exact(Money(cents: 270)))
        // Easter Monday 2026 (6 April) is billed like a Sunday; an ordinary Monday 10:00 is band F (2,20).
        XCTAssertEqual(side.amount(for: Vehicle(.class1), at: paris(2026, 4, 6, 10, 0)), .exact(Money(cents: 270)))
        XCTAssertEqual(side.amount(for: Vehicle(.class1), at: paris(2026, 4, 13, 10, 0)), .exact(Money(cents: 220)))
        // Night: band A, 1,20
        XCTAssertEqual(side.amount(for: Vehicle(.class1), at: paris(2026, 10, 7, 2, 30)), .exact(Money(cents: 120)))
        // Heavy vehicle, Euro 6, Tuesday 06:45 (band D): 5,60
        XCTAssertEqual(side.amount(for: Vehicle(.class3, euroClass: .euro6), at: paris(2026, 10, 6, 6, 45)),
                       .exact(Money(cents: 560)))
        // Without a date: the lowest and highest bands.
        guard case .range(let lo, let hi, let needs) = side.amount(for: Vehicle(.class1), at: nil) else {
            return XCTFail("expected a range")
        }
        XCTAssertEqual([lo, hi], [Money(cents: 120), Money(cents: 270)])
        XCTAssertEqual(needs, [.date])
    }

    func testEaster() {
        XCTAssertTrue(PointTariff.easterSunday(year: 2026) == (4, 5))
        XCTAssertTrue(PointTariff.easterSunday(year: 2027) == (3, 28))
        XCTAssertTrue(PointTariff.easterSunday(year: 2030) == (4, 21))
    }

    // MARK: Trips mixing tickets and points

    func testTripWithTicketAndBridge() throws {
        let stops: [TollStop] = [
            .station(try XCTUnwrap(database.station(named: "Chatillon"))),
            .point(try point("Viaduc de Millau")),
            .station(try XCTUnwrap(database.station(named: "Origine"))),
        ]
        let summer = calculator.quote(stops: stops, vehicle: Vehicle(.class1), date: paris(2026, 8, 1, 10, 0))
        XCTAssertEqual(summer.lines.map(\.title), ["Viaduc de Millau", "Chatillon → Origine"])
        XCTAssertEqual(summer.total, Money(cents: 1380 + 1410))
        let undated = calculator.quote(stops: stops, vehicle: Vehicle(.class1))
        XCTAssertNil(undated.total)
        XCTAssertTrue(undated.isComplete)
        XCTAssertEqual(undated.missingInputs, [.date])
        XCTAssertEqual(undated.totalRange.min, Money(cents: 1130 + 1410))
        XCTAssertEqual(undated.totalRange.max, Money(cents: 1380 + 1410))
    }
}
