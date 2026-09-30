import Foundation

/// The price of a trip, built only from published entry → exit fares.
public struct TollQuote: Sendable {
    public struct Line: Sendable, Hashable {
        public let entry: TollStation
        public let exit: TollStation
        /// Grid the fare comes from; `nil` when no grid publishes this pair.
        public let networkID: String?
        public let distanceMeters: Int?
        /// `nil` when the segment could not be priced from official data.
        public let price: Money?
    }

    public let vehicleClass: VehicleClass
    public let lines: [Line]

    /// Sum of the priced lines, exact to the cent.
    public var total: Money { lines.compactMap(\.price).reduce(.zero, +) }

    /// `true` when every segment was priced from an official grid. When it is
    /// `false`, `total` is only a lower bound and must be shown as such.
    public var isComplete: Bool { lines.allSatisfy { $0.price != nil } }

    public var unpricedLines: [Line] { lines.filter { $0.price == nil } }
}

public struct TollCalculator: Sendable {
    public let database: TollDatabase

    public init(database: TollDatabase) {
        self.database = database
    }

    /// Price of a single ticket: enter at `entry`, leave at `exit`.
    public func fare(from entry: TollStation, to exit: TollStation, vehicleClass: VehicleClass) throws -> TollQuote.Line {
        let found = database.fares(from: entry, to: exit)
        guard let first = found.first else {
            throw TollError.noPublishedFare(entry: entry.name, exit: exit.name)
        }
        // Grids overlap on shared stations; they must agree to the cent.
        let price = first.fare.price(for: vehicleClass)
        guard found.allSatisfy({ $0.fare.price(for: vehicleClass) == price }) else {
            throw TollError.conflictingFares(entry: entry.name, exit: exit.name)
        }
        return TollQuote.Line(entry: first.fare.entry, exit: first.fare.exit, networkID: first.network.id,
                              distanceMeters: first.fare.distanceMeters, price: price)
    }

    public func quote(from entry: String, to exit: String, vehicleClass: VehicleClass) throws -> TollQuote {
        guard let e = database.station(named: entry) else { throw TollError.unknownStation(entry) }
        guard let x = database.station(named: exit) else { throw TollError.unknownStation(exit) }
        return TollQuote(vehicleClass: vehicleClass, lines: [try fare(from: e, to: x, vehicleClass: vehicleClass)])
    }

    /// Price a trip from the ordered toll stations it passes through.
    ///
    /// A published entry → exit fare is what the driver pays between those two
    /// stations, including any toll barrier in between. So the trip is split
    /// into the fewest consecutive tickets that each have a published fare
    /// (a station passed "on the way" that is really a drive-by is absorbed by
    /// the longer ticket). Segments that no grid prices are reported as
    /// unpriced rather than estimated.
    public func quote(passages stations: [TollStation], vehicleClass: VehicleClass) -> TollQuote {
        var path: [TollStation] = []
        for station in stations where path.last?.key != station.key {
            path.append(station)
        }
        guard path.count >= 2 else { return TollQuote(vehicleClass: vehicleClass, lines: []) }

        // Shortest path over a DAG: node i = "a ticket ends at path[i]".
        // A priced ticket costs 1; an unpriced hop between neighbours costs a
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
                if let priced = try? fare(from: path[i], to: path[j], vehicleClass: vehicleClass) {
                    line = priced
                    cost = 1
                } else if j == i + 1 {
                    line = TollQuote.Line(entry: path[i], exit: path[j], networkID: nil, distanceMeters: nil, price: nil)
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
        return TollQuote(vehicleClass: vehicleClass, lines: lines.reversed())
    }
}

/// A simple itinerary: the toll stations to go through, in order, e.g.
/// `[ALLAINES, AMBERIEU]` for a single ticket, or more stops for a trip that
/// leaves and re-enters the motorway.
public struct TollItinerary: Sendable, Hashable {
    public var stops: [TollStation]
    public var vehicleClass: VehicleClass

    public init(stops: [TollStation] = [], vehicleClass: VehicleClass = .class1) {
        self.stops = stops
        self.vehicleClass = vehicleClass
    }
}

extension TollCalculator {
    public func quote(_ itinerary: TollItinerary) -> TollQuote {
        quote(passages: itinerary.stops, vehicleClass: itinerary.vehicleClass)
    }
}
