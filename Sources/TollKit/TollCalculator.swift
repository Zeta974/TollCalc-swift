import Foundation

/// Something a trip goes through: a station of a closed-system grid (you
/// take a ticket there or pay a ticket there) or a toll point (you pay there).
public enum TollStop: Hashable, Sendable {
    case station(TollStation)
    case point(TollPoint)

    public var name: String {
        switch self {
        case .station(let s): return s.name
        case .point(let p): return p.name
        }
    }

    public var key: String {
        switch self {
        case .station(let s): return s.key
        case .point(let p): return p.key
        }
    }

    public var networkID: String {
        switch self {
        case .station(let s): return s.networkID
        case .point(let p): return p.networkID
        }
    }

    public var location: GeoPoint? {
        switch self {
        case .station(let s): return s.location
        case .point(let p): return p.location
        }
    }

    public var booths: [GeoPoint] {
        switch self {
        case .station(let s): return s.booths
        case .point(let p): return p.booths
        }
    }

    /// Where the route detector looks for this stop: its booths, or failing
    /// that the exit nodes of its interchange.
    public var anchors: [GeoPoint] {
        switch self {
        case .station(let s): return s.booths.isEmpty ? s.junctions : s.booths
        case .point(let p): return p.booths
        }
    }

    public var station: TollStation? {
        if case .station(let s) = self { return s }
        return nil
    }

    public var point: TollPoint? {
        if case .point(let p) = self { return p }
        return nil
    }
}

/// The price of a trip, built only from published prices.
public struct TollQuote: Sendable {
    public struct Line: Sendable, Hashable {
        public enum Kind: Sendable, Hashable {
            /// A closed-system ticket: enter at `entry`, pay at `exit`.
            case ticket(entry: TollStation, exit: TollStation)
            /// A barrier, bridge or section paid on its own.
            case point(TollPoint)
        }

        public let kind: Kind
        /// Grid the price comes from; `nil` when no grid publishes it.
        public let networkID: String?
        public let distanceMeters: Int?
        public let amount: Amount

        /// The exact price, when there is one.
        public var price: Money? { amount.exactValue }

        public var title: String {
            switch kind {
            case .ticket(let entry, let exit): return "\(entry.name) → \(exit.name)"
            case .point(let point): return point.name
            }
        }

        public var entry: TollStation? {
            if case .ticket(let entry, _) = kind { return entry }
            return nil
        }

        public var exit: TollStation? {
            if case .ticket(_, let exit) = kind { return exit }
            return nil
        }
    }

    public let vehicle: Vehicle
    public let lines: [Line]

    public var vehicleClass: VehicleClass { vehicle.vehicleClass }

    /// Every line has an official price (possibly a range).
    public var isComplete: Bool {
        lines.allSatisfy { if case .unavailable = $0.amount { return false } else { return true } }
    }

    /// Every line has one exact official price.
    public var isExact: Bool { lines.allSatisfy { $0.price != nil } }

    /// Exact total, exact to the cent; `nil` unless `isExact`.
    public var total: Money? {
        isExact ? lines.compactMap(\.price).reduce(.zero, +) : nil
    }

    /// Lowest and highest possible totals of the priced lines. Unpriced lines
    /// are not included, so when `isComplete` is false this is a lower bound.
    public var totalRange: (min: Money, max: Money) {
        lines.compactMap(\.amount.bounds).reduce((Money.zero, Money.zero)) { ($0.0 + $1.0, $0.1 + $1.1) }
    }

    /// Inputs that would turn the ranges into exact prices.
    public var missingInputs: Set<TripInput> {
        lines.reduce(into: []) { result, line in
            if case .range(_, _, let needs) = line.amount { result.formUnion(needs) }
        }
    }

    public var unpricedLines: [Line] {
        lines.filter { if case .unavailable = $0.amount { return true } else { return false } }
    }
}

public struct TollCalculator: Sendable {
    public let database: TollDatabase

    public init(database: TollDatabase) {
        self.database = database
    }

    /// Price of a single ticket: enter at `entry`, leave at `exit`.
    ///
    /// On the A1, Sanef varies some class 1 fares by period (normal, green,
    /// red); pass `sanefA1Period` to get the exact price, otherwise those
    /// trips come back as the green-to-red range.
    public func fare(from entry: TollStation, to exit: TollStation, vehicleClass: VehicleClass,
                     sanefA1Period: SanefA1Period? = nil) throws -> TollQuote.Line {
        let found = database.fares(from: entry, to: exit)
        guard let first = found.first else {
            throw TollError.noPublishedFare(entry: entry.name, exit: exit.name)
        }
        // Grids overlap on shared stations; they must agree to the cent.
        let price = first.fare.price(for: vehicleClass)
        guard found.allSatisfy({ $0.fare.price(for: vehicleClass) == price }) else {
            throw TollError.conflictingFares(entry: entry.name, exit: exit.name)
        }
        var amount = Amount.exact(price)
        if vehicleClass == .class1,
           let levels = found.lazy.compactMap({ $0.network.class1Modulation(from: entry, to: exit) }).first {
            if let period = sanefA1Period, let exact = levels[period] {
                amount = .exact(exact)
            } else {
                amount = .range(min: levels.values.min()!, max: levels.values.max()!, needs: [.sanefA1Period])
            }
        }
        return TollQuote.Line(kind: .ticket(entry: first.fare.entry, exit: first.fare.exit),
                              networkID: first.network.id, distanceMeters: first.fare.distanceMeters,
                              amount: amount)
    }

    /// One ticket between two named stations.
    public func quote(from entry: String, to exit: String, vehicle: Vehicle,
                      sanefA1Period: SanefA1Period? = nil) throws -> TollQuote {
        guard let e = database.station(named: entry) else { throw TollError.unknownStation(entry) }
        guard let x = database.station(named: exit) else { throw TollError.unknownStation(exit) }
        return TollQuote(vehicle: vehicle, lines: [try fare(from: e, to: x, vehicleClass: vehicle.vehicleClass,
                                                            sanefA1Period: sanefA1Period)])
    }

    public func quote(from entry: String, to exit: String, vehicleClass: VehicleClass) throws -> TollQuote {
        try quote(from: entry, to: exit, vehicle: Vehicle(vehicleClass))
    }

    /// Price of passing one toll point.
    public func quote(point: TollPoint, vehicle: Vehicle, date: Date? = nil) -> TollQuote {
        TollQuote(vehicle: vehicle, lines: [pointLine(point, vehicle: vehicle, date: date)])
    }

    /// Price a trip from the ordered stations and toll points it goes through.
    ///
    /// Toll points are paid where they are. Closed-system stations are
    /// grouped into tickets: a published entry → exit fare is what the driver
    /// pays between those two stations, including any barrier in between, so
    /// the stations are split into the fewest consecutive tickets that each
    /// have a published fare (a station passed "on the way" is absorbed by the
    /// longer ticket). Stretches no grid prices are reported as unavailable,
    /// never estimated. `date` is the time of the trip, used by seasonal and
    /// time-of-day prices; without it those come back as ranges.
    public func quote(stops: [TollStop], vehicle: Vehicle, date: Date? = nil,
                      sanefA1Period: SanefA1Period? = nil) -> TollQuote {
        let stops = mergingCombinedPoints(stops)
        var lines: [TollQuote.Line] = []
        var run: [TollStation] = []
        func flush() {
            lines += tickets(for: run, vehicleClass: vehicle.vehicleClass, sanefA1Period: sanefA1Period)
            run = []
        }
        for stop in stops {
            switch stop {
            case .station(let station):
                if run.last?.key != station.key { run.append(station) }
            case .point(let point):
                // A point between two stations of the same ticket does not
                // split it: the barrier is paid separately.
                lines.append(pointLine(point, vehicle: vehicle, date: date))
            }
        }
        flush()
        return TollQuote(vehicle: vehicle, lines: ordered(lines, by: stops))
    }

    public func quote(passages stations: [TollStation], vehicleClass: VehicleClass) -> TollQuote {
        quote(stops: stations.map(TollStop.station), vehicle: Vehicle(vehicleClass))
    }

    // MARK: - Internals

    /// Replaces two points with the point that bills them together. Points
    /// of the same network passed in between are absorbed (a route through the
    /// Duplex A86 from Rueil to Vélizy may come close to the Vaucresson booths);
    /// the furthest match wins.
    private func mergingCombinedPoints(_ stops: [TollStop]) -> [TollStop] {
        var out: [TollStop] = []
        var i = 0
        next: while i < stops.count {
            if let a = stops[i].point {
                var j = i + 1
                while j < stops.count, j <= i + 2, stops[j].point?.networkID == a.networkID { j += 1 }
                for k in stride(from: j - 1, to: i, by: -1) {
                    if let b = stops[k].point, let both = database.combined(a, b) {
                        out.append(.point(both))
                        i = k + 1
                        continue next
                    }
                }
            }
            out.append(stops[i])
            i += 1
        }
        return out
    }

    private func pointLine(_ point: TollPoint, vehicle: Vehicle, date: Date?) -> TollQuote.Line {
        TollQuote.Line(kind: .point(point), networkID: point.networkID, distanceMeters: nil,
                       amount: point.amount(for: vehicle, at: date))
    }

    /// The same physical station can be named differently in two grids
    /// ("AMBERIEU" for APRR, "Ambérieu-en-Bugey" elsewhere). Consecutive
    /// stations less than `sameStationRadius` apart are one stop; a ticket may
    /// start or end at any of its names.
    static let sameStationRadius = 1_000.0

    /// When names at the same place price the trip differently (one plaza
    /// that is two grid entries, e.g. ASF "Péage de Toulouse nord/est" and
    /// "nord/ouest"), the route alone cannot tell which applies: the line is
    /// the range of those fares and asks for `.station`.
    private func fare(from entries: [TollStation], to exits: [TollStation], vehicleClass: VehicleClass,
                      sanefA1Period: SanefA1Period?) -> TollQuote.Line? {
        var lines: [TollQuote.Line] = []
        for entry in entries {
            for exit in exits {
                if let line = try? fare(from: entry, to: exit, vehicleClass: vehicleClass, sanefA1Period: sanefA1Period) {
                    lines.append(line)
                }
            }
        }
        guard let first = lines.first else { return nil }
        let bounds = lines.compactMap(\.amount.bounds)
        guard Set(lines.map(\.amount)).count > 1, bounds.count == lines.count,
              let low = bounds.map(\.0).min(), let high = bounds.map(\.1).max() else { return first }
        var needs: Set<TripInput> = [.station]
        for line in lines {
            if case .range(_, _, let more) = line.amount { needs.formUnion(more) }
        }
        return TollQuote.Line(kind: first.kind, networkID: first.networkID, distanceMeters: nil,
                              amount: .range(min: low, max: high, needs: needs))
    }

    private func group(_ path: [TollStation]) -> [[TollStation]] {
        var groups: [[TollStation]] = []
        for station in path {
            if let last = groups.last?.last, let a = last.location, let b = station.location,
               Geo.distance(a, b) < Self.sameStationRadius {
                groups[groups.count - 1].append(station)
            } else {
                groups.append([station])
            }
        }
        return groups
    }

    /// Fewest consecutive published tickets covering `stations`.
    private func tickets(for stations: [TollStation], vehicleClass: VehicleClass,
                         sanefA1Period: SanefA1Period?) -> [TollQuote.Line] {
        let path = group(stations)
        guard path.count >= 2 else { return [] }
        // Shortest path over a DAG: node i = "a ticket ends at path[i]". A
        // priced ticket costs 1; an unpriced hop between neighbours costs a
        // lot, so it is only used when nothing published covers that stretch.
        let unpricedCost = 1_000
        let n = path.count
        var best = [Int](repeating: .max, count: n)
        var previous = [(index: Int, line: TollQuote.Line)?](repeating: nil, count: n)
        best[0] = 0
        for i in 0..<n where best[i] != .max {
            for j in (i + 1)..<n {
                let line: TollQuote.Line
                let cost: Int
                if let priced = fare(from: path[i], to: path[j], vehicleClass: vehicleClass, sanefA1Period: sanefA1Period) {
                    line = priced
                    cost = 1
                } else if j == i + 1 {
                    let entry = path[i][0], exit = path[j][0]
                    line = TollQuote.Line(kind: .ticket(entry: entry, exit: exit), networkID: nil,
                                          distanceMeters: nil,
                                          amount: .unavailable("No official fare is published for \(entry.name) → \(exit.name)"))
                    cost = unpricedCost
                } else {
                    continue
                }
                if best[i] + cost < best[j] {
                    best[j] = best[i] + cost
                    previous[j] = (i, line)
                }
            }
        }
        var lines: [TollQuote.Line] = []
        var cursor = n - 1
        while let step = previous[cursor] {
            lines.append(step.line)
            cursor = step.index
        }
        return lines.reversed()
    }

    /// Order lines as the trip meets them: a ticket where its exit is, a point where it is.
    private func ordered(_ lines: [TollQuote.Line], by stops: [TollStop]) -> [TollQuote.Line] {
        var position: [String: Int] = [:]
        for (i, stop) in stops.enumerated() where position[stop.key] == nil {
            position[stop.key] = i
        }
        func rank(_ line: TollQuote.Line) -> Int {
            switch line.kind {
            case .ticket(_, let exit): return position[exit.key] ?? .max
            case .point(let point): return position[point.key] ?? .max
            }
        }
        return lines.enumerated().sorted { (rank($0.element), $0.offset) < (rank($1.element), $1.offset) }.map(\.element)
    }
}

/// A simple itinerary: the stations and toll points to go through, in order,
/// e.g. `[ALLAINES, AMBERIEU]` for a single ticket.
public struct TollItinerary: Sendable, Hashable {
    public var stops: [TollStop]
    public var vehicle: Vehicle
    /// Time of the trip (local French time is derived from it).
    public var date: Date?
    /// Sanef A1 tariff level, when known (see `SanefA1Period`).
    public var sanefA1Period: SanefA1Period?

    public init(stops: [TollStop] = [], vehicle: Vehicle = Vehicle(.class1), date: Date? = nil,
                sanefA1Period: SanefA1Period? = nil) {
        self.stops = stops
        self.vehicle = vehicle
        self.date = date
        self.sanefA1Period = sanefA1Period
    }
}

extension TollCalculator {
    public func quote(_ itinerary: TollItinerary) -> TollQuote {
        quote(stops: itinerary.stops, vehicle: itinerary.vehicle, date: itinerary.date,
              sanefA1Period: itinerary.sanefA1Period)
    }
}
