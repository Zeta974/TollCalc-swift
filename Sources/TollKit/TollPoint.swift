import Foundation

/// A toll paid at one place regardless of where the trip started: an
/// open-system barrier, a bridge, or a priced section.
public struct TollPoint: Identifiable, Hashable, Sendable {
    public enum Kind: String, Hashable, Sendable, Codable {
        case barrier, bridge, tunnel, gantry
    }

    public let id: String
    public let name: String
    public let kind: Kind
    public let networkID: String
    public let location: GeoPoint?
    public let booths: [GeoPoint]
    public let tariff: PointTariff
    /// Ids of two points this one replaces when a trip passes them one after
    /// the other, in either order: on the A79 free-flow section, driving
    /// through both gantries of an interchange is billed once, at the
    /// "transit" price, not as the sum of the two gantries.
    public let combines: Set<String>

    public init(id: String, name: String, kind: Kind, networkID: String, location: GeoPoint?,
                booths: [GeoPoint], tariff: PointTariff, combines: Set<String> = []) {
        self.id = id
        self.name = name
        self.kind = kind
        self.networkID = networkID
        self.location = location
        self.booths = booths
        self.tariff = tariff
        self.combines = combines
    }

    public var key: String { StationName.key(name) }

    /// Price for one passage. `date` is the local time of the passage; when a
    /// price depends on it and it is `nil`, the result is a range.
    public func amount(for vehicle: Vehicle, at date: Date?) -> Amount {
        tariff.amount(for: vehicle, at: date)
    }
}

/// The amount of one toll line.
public enum Amount: Hashable, Sendable {
    /// The exact price.
    case exact(Money)
    /// The price depends on inputs that were not given; it is one of the
    /// published prices between `min` and `max`.
    case range(min: Money, max: Money, needs: Set<TripInput>)
    /// No official price exists for this line (reason given).
    case unavailable(String)

    public var exactValue: Money? {
        if case .exact(let money) = self { return money }
        return nil
    }

    var bounds: (Money, Money)? {
        switch self {
        case .exact(let m): return (m, m)
        case .range(let lo, let hi, _): return (lo, hi)
        case .unavailable: return nil
        }
    }
}

/// Published prices of a toll point, possibly varying with the season, the
/// time of day and the vehicle's emission class.
public struct PointTariff: Hashable, Sendable {
    /// How classes 3 and 4 map to the keys of `prices`.
    public enum HeavyScheme: String, Hashable, Sendable {
        /// Keys "3" and "4".
        case standard
        /// A63 (Atlandes): heavy vehicles use classes A, B and C.
        /// A: 2 axles, PTAC ≤ 12 t; B: 2 axles over 12 t, or 3 axles; C: more than 3 axles.
        case atlandes
    }

    /// A price table and the condition under which it applies.
    struct Period: Hashable, Sendable {
        enum Condition: Hashable, Sendable {
            /// Month-day ranges, inclusive, e.g. [(6, 15), (9, 15)]; may wrap over new year.
            case season([ClosedMonthDayRange])
            /// A named time band from `bands`.
            case band(String)
        }

        let condition: Condition?
        /// Subscriptions this price is reserved to; `nil` for the public price.
        let subscriptions: Set<TollSubscription>?
        /// Class key ("1"…"5", or "A"/"B"/"C") -> price cell.
        let prices: [String: PriceCell]
    }

    enum PriceCell: Hashable, Sendable {
        case flat(Money)
        /// Keys "default" (non modulé), "euro0"…"euro7", "gnv", and "vtfe"
        /// (very low emission: Crit'Air 0 / fully electric).
        case modulated([String: Money])

        enum Missing: Error {
            /// The cell has no "default" price and the Euro class is not
            /// given: the price is one of these.
            case euroClass([Money])
            case price(String)

            var key: String {
                switch self {
                case .euroClass: return "undeclared Euro class"
                case .price(let key): return key
                }
            }
        }

        var allPrices: [Money] {
            switch self {
            case .flat(let m): return [m]
            case .modulated(let d): return Array(Set(d.values))
            }
        }

        /// The price this vehicle pays.
        func prices(for vehicle: Vehicle) -> Result<[Money], Missing> {
            guard case .modulated(let byKey) = self else { return .success(allPrices) }
            if vehicle.usesNaturalGas, let m = byKey["gnv"] { return .success([m]) }
            if vehicle.isVeryLowEmission, let m = byKey["vtfe"] { return .success([m]) }
            let hasEuroKeys = byKey.keys.contains { $0.hasPrefix("euro") }
            if let euro = vehicle.euroClass, hasEuroKeys {
                return byKey[euro.key].map { .success([$0]) } ?? .failure(.price(euro.key))
            }
            if let m = byKey["default"] { return .success([m]) }
            if hasEuroKeys {
                // Every Euro class priced, none for an undeclared one.
                let euros = Set(byKey.filter { $0.key.hasPrefix("euro") }.values)
                return .failure(euros.count > 1 ? .euroClass(Array(euros)) : .price("default"))
            }
            return .failure(.price("default"))
        }
    }

    struct ClosedMonthDayRange: Hashable, Sendable {
        let from: (month: Int, day: Int)
        let to: (month: Int, day: Int)

        static func == (a: Self, b: Self) -> Bool {
            a.from == b.from && a.to == b.to
        }

        func hash(into hasher: inout Hasher) {
            hasher.combine(from.month); hasher.combine(from.day); hasher.combine(to.month); hasher.combine(to.day)
        }

        func contains(month: Int, day: Int) -> Bool {
            let x = month * 100 + day, a = from.month * 100 + from.day, b = to.month * 100 + to.day
            return a <= b ? (a...b).contains(x) : (x >= a || x <= b)
        }
    }

    struct BandRule: Hashable, Sendable {
        let days: Set<Int>  // 1 = Monday … 7 = Sunday
        let from: Int  // minutes after midnight, inclusive
        let to: Int  // inclusive
    }

    let heavyScheme: HeavyScheme
    let periods: [Period]
    let bands: [String: [BandRule]]
    /// Holidays ("MM-DD" or "easter±N"), billed like `holidaysAs`.
    let holidays: [String]
    let holidaysAs: Int?

    /// Every published price of this tariff, for listing and validation.
    public var allPrices: [Money] {
        periods.flatMap { $0.prices.values.flatMap(\.allPrices) }
    }

    public var dependsOnDate: Bool { periods.contains { $0.condition != nil } }

    func amount(for vehicle: Vehicle, at date: Date?) -> Amount {
        var needs = Set<TripInput>()

        // A subscriber pays the subscription price where one exists, else the public one.
        let subscribed = self.periods.filter { !($0.subscriptions ?? []).isDisjoint(with: vehicle.subscriptions) }
        let offered = subscribed.isEmpty ? self.periods.filter { $0.subscriptions == nil } : subscribed

        let periods: [Period]
        if let date {
            periods = offered.filter { $0.condition.map { matches($0, date) } ?? true }
            if periods.isEmpty { return .unavailable("No published price at this date") }
        } else {
            periods = offered
        }

        let classKeys: [String]
        switch (heavyScheme, vehicle.vehicleClass) {
        case (.atlandes, .class3):
            // Class 3 vehicles have two axles; the gross weight decides between A and B.
            if let weight = vehicle.grossWeightTonnes {
                classKeys = [weight <= 12 ? "A" : "B"]
            } else {
                classKeys = ["A", "B"]
                needs.insert(.grossWeight)
            }
        case (.atlandes, .class4):
            if let axles = vehicle.axles {
                classKeys = [axles <= 3 ? "B" : "C"]
            } else {
                classKeys = ["B", "C"]
                needs.insert(.axles)
            }
        default:
            classKeys = [String(vehicle.vehicleClass.rawValue)]
        }

        var candidates: [Money] = []
        var byKeyAcrossPeriods: [String: Set<[Money]>] = [:]
        for period in periods {
            for key in classKeys {
                guard let cell = period.prices[key] else {
                    return .unavailable("No published price for \(vehicle.vehicleClass.title)")
                }
                let prices: [Money]
                switch cell.prices(for: vehicle) {
                case .success(let found):
                    prices = found
                case .failure(let missing):
                    if case .euroClass(let possible) = missing { needs.insert(.euroClass); prices = possible }
                    else { return .unavailable("No published price for \(missing.key)") }
                }
                candidates += prices
                byKeyAcrossPeriods[key, default: []].insert(prices.sorted())
            }
        }
        if date == nil, byKeyAcrossPeriods.values.contains(where: { $0.count > 1 }) {
            needs.insert(.date)
        }
        guard let lo = candidates.min(), let hi = candidates.max() else {
            return .unavailable("No published price")
        }
        if lo == hi { return .exact(lo) }
        return .range(min: lo, max: hi, needs: needs)
    }

    // MARK: Dates (French local time)

    static let paris: Calendar = {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Europe/Paris")!
        return calendar
    }()

    private func matches(_ condition: Period.Condition, _ date: Date) -> Bool {
        let c = Self.paris.dateComponents([.year, .month, .day, .weekday, .hour, .minute], from: date)
        switch condition {
        case .season(let ranges):
            return ranges.contains { $0.contains(month: c.month!, day: c.day!) }
        case .band(let name):
            // Calendar weekday: 1 = Sunday … 7 = Saturday -> ISO 1 = Monday … 7 = Sunday
            var day = (c.weekday! + 5) % 7 + 1
            if let holidayDay = holidaysAs, isHoliday(year: c.year!, month: c.month!, day: c.day!) {
                day = holidayDay
            }
            let minute = c.hour! * 60 + c.minute!
            return (bands[name] ?? []).contains { $0.days.contains(day) && (($0.from)...($0.to)).contains(minute) }
        }
    }

    private func isHoliday(year: Int, month: Int, day: Int) -> Bool {
        holidays.contains { spec in
            if spec.hasPrefix("easter") {
                let offset = Int(spec.dropFirst("easter".count)) ?? 0
                let easter = Self.easterSunday(year: year)
                guard let date = Self.paris.date(from: DateComponents(year: year, month: easter.month, day: easter.day)),
                      let holiday = Self.paris.date(byAdding: .day, value: offset, to: date) else { return false }
                let h = Self.paris.dateComponents([.month, .day], from: holiday)
                return h.month == month && h.day == day
            }
            let parts = spec.split(separator: "-").compactMap { Int($0) }
            return parts.count == 2 && parts[0] == month && parts[1] == day
        }
    }

    /// Gregorian Easter Sunday (anonymous Gregorian algorithm).
    static func easterSunday(year: Int) -> (month: Int, day: Int) {
        let a = year % 19, b = year / 100, c = year % 100
        let d = b / 4, e = b % 4, f = (b + 8) / 25, g = (b - f + 1) / 3
        let h = (19 * a + b - d - g + 15) % 30
        let i = c / 4, k = c % 4
        let l = (32 + 2 * e + 2 * i - h - k) % 7
        let m = (a + 11 * h + 22 * l) / 451
        let month = (h + l - 7 * m + 114) / 31
        let day = (h + l - 7 * m + 114) % 31 + 1
        return (month, day)
    }
}

// MARK: - Decoding (see Tools/points.py)

extension PointTariff: Decodable {
    private enum CodingKeys: String, CodingKey {
        case heavyScheme, periods, bands, holidays, holidaysAs
    }

    private struct RawPeriod: Decodable {
        struct When: Decodable {
            let season: [[String]]?
            let band: String?
        }
        let when: When?
        let subscriptions: [String]?
        let prices: [String: RawCell]
    }

    private enum RawCell: Decodable {
        case flat(Int)
        case modulated([String: Int])

        init(from decoder: Decoder) throws {
            let c = try decoder.singleValueContainer()
            if let value = try? c.decode(Int.self) {
                self = .flat(value)
            } else {
                self = .modulated(try c.decode([String: Int].self))
            }
        }
    }

    private static let dayNames = ["mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 7]

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        heavyScheme = HeavyScheme(rawValue: try c.decodeIfPresent(String.self, forKey: .heavyScheme) ?? "standard") ?? .standard
        holidays = try c.decodeIfPresent([String].self, forKey: .holidays) ?? []
        holidaysAs = try c.decodeIfPresent(String.self, forKey: .holidaysAs).flatMap { Self.dayNames[$0] }

        func minutes(_ s: String) throws -> Int {
            let parts = s.split(separator: ":").compactMap { Int($0) }
            guard parts.count == 2 else {
                throw DecodingError.dataCorruptedError(forKey: .bands, in: c, debugDescription: "Bad time \(s)")
            }
            return parts[0] * 60 + parts[1]
        }
        // "A": [[["mon", "tue"], "00:00", "04:59"], …]
        let rawBands = try c.decodeIfPresent([String: [[BandField]]].self, forKey: .bands) ?? [:]
        var bands: [String: [BandRule]] = [:]
        for (name, rules) in rawBands {
            bands[name] = try rules.map { rule in
                guard rule.count == 3, case .days(let days) = rule[0], case .time(let from) = rule[1],
                      case .time(let to) = rule[2] else {
                    throw DecodingError.dataCorruptedError(forKey: .bands, in: c, debugDescription: "Bad band \(name)")
                }
                return BandRule(days: Set(days.compactMap { Self.dayNames[$0] }), from: try minutes(from), to: try minutes(to))
            }
        }
        self.bands = bands

        func monthDay(_ s: String) throws -> (month: Int, day: Int) {
            let parts = s.split(separator: "-").compactMap { Int($0) }
            guard parts.count == 2 else {
                throw DecodingError.dataCorruptedError(forKey: .periods, in: c, debugDescription: "Bad date \(s)")
            }
            return (parts[0], parts[1])
        }
        periods = try c.decode([RawPeriod].self, forKey: .periods).map { raw in
            var condition: Period.Condition?
            if let season = raw.when?.season {
                condition = .season(try season.map { pair in
                    ClosedMonthDayRange(from: try monthDay(pair[0]), to: try monthDay(pair[1]))
                })
            } else if let band = raw.when?.band {
                guard bands[band] != nil else {
                    throw DecodingError.dataCorruptedError(forKey: .periods, in: c, debugDescription: "Unknown band \(band)")
                }
                condition = .band(band)
            }
            let prices = raw.prices.mapValues { cell -> PriceCell in
                switch cell {
                case .flat(let cents): return .flat(Money(cents: cents))
                case .modulated(let d): return .modulated(d.mapValues { Money(cents: $0) })
                }
            }
            let subscriptions = try raw.subscriptions.map { names in
                Set(try names.map { name in
                    guard let subscription = TollSubscription(rawValue: name) else {
                        throw DecodingError.dataCorruptedError(forKey: .periods, in: c,
                                                               debugDescription: "Unknown subscription \(name)")
                    }
                    return subscription
                })
            }
            return Period(condition: condition, subscriptions: subscriptions, prices: prices)
        }
    }

    /// One field of a band rule: the list of days, or a "HH:MM" time.
    private enum BandField: Decodable {
        case days([String])
        case time(String)

        init(from decoder: Decoder) throws {
            let c = try decoder.singleValueContainer()
            if let days = try? c.decode([String].self) {
                self = .days(days)
            } else {
                self = .time(try c.decode(String.self))
            }
        }
    }
}
