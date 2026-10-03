import Foundation

/// Every tariff grid known to the app.
///
/// The same physical station appears in several grids (the APRR grid also
/// prices tickets that end on neighbouring networks), so stations are merged
/// across grids by their normalised name (`TollStation.key`).
public struct TollDatabase: Sendable {
    public let networks: [TollNetwork]
    /// One entry per physical station, sorted by name, booths merged across grids.
    public let stations: [TollStation]
    /// Every barrier, bridge or section priced on its own.
    public let points: [TollPoint]
    private let stationsByKey: [String: TollStation]
    private let pointsByKey: [String: TollPoint]
    /// Points that replace two consecutive points (`TollPoint.combines`).
    private let combinedPoints: [[String]: TollPoint]

    public init(networks: [TollNetwork]) {
        self.networks = networks
        var merged: [String: TollStation] = [:]
        // Same name, different places (ATMB "Saint-Julien" en-Genevois and SFTRF
        // "St Julien" Mont-Denis): kept apart.
        var homonyms: [TollStation] = []
        for network in networks {
            for station in network.stations {
                if let existing = merged[station.key], let a = existing.location, let b = station.location,
                   Geo.distance(a, b) > Self.homonymDistance {
                    homonyms.append(station)
                } else if let existing = merged[station.key] {
                    let booths = existing.booths + station.booths.filter { !existing.booths.contains($0) }
                    let junctions = existing.junctions + station.junctions.filter { !existing.junctions.contains($0) }
                    // Prefer a booth position over an interchange position.
                    let location = existing.booths.isEmpty && !station.booths.isEmpty
                        ? station.location : (existing.location ?? station.location)
                    merged[station.key] = TollStation(
                        id: existing.id, name: existing.name, code: existing.code ?? station.code,
                        networkID: existing.networkID, location: location,
                        booths: booths, junctions: junctions, isVirtual: existing.isVirtual && station.isVirtual)
                } else {
                    merged[station.key] = station
                }
            }
        }
        stationsByKey = merged
        stations = (Array(merged.values) + homonyms).sorted { $0.name < $1.name }
        points = networks.flatMap(\.points).sorted { $0.name < $1.name }
        pointsByKey = Dictionary(points.map { ($0.key, $0) }, uniquingKeysWith: { first, _ in first })
        var combined: [[String]: TollPoint] = [:]
        for point in points where point.combines.count == 2 {
            combined[point.combines] = combined[point.combines] ?? point
            if !point.combinesInOrder {
                combined[point.combines.reversed()] = combined[point.combines.reversed()] ?? point
            }
        }
        combinedPoints = combined
    }

    /// The point billed instead of passing `a` then `b`, if any.
    public func combined(_ a: TollPoint, _ b: TollPoint) -> TollPoint? {
        combinedPoints[[a.id, b.id]]
    }

    /// Entries of different grids with the same name are one station unless
    /// they are further apart than this.
    static let homonymDistance = 5_000.0

    /// Loads the grids bundled with TollKit (`Resources/networks/*.json`).
    public static func bundled() throws -> TollDatabase {
        guard let directory = Bundle.module.url(forResource: "networks", withExtension: nil) else {
            throw TollError.missingResources
        }
        let files = try FileManager.default
            .contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
            .filter { $0.pathExtension == "json" }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
        let decoder = JSONDecoder()
        return TollDatabase(networks: try files.map { try decoder.decode(TollNetwork.self, from: Data(contentsOf: $0)) })
    }

    public func station(named name: String) -> TollStation? {
        stationsByKey[StationName.key(name)]
    }

    public func point(named name: String) -> TollPoint? {
        pointsByKey[StationName.key(name)]
    }

    /// A station or a toll point with this name.
    public func stop(named name: String) -> TollStop? {
        station(named: name).map(TollStop.station) ?? point(named: name).map(TollStop.point)
    }

    /// Stations and toll points whose name contains every word of `query`.
    public func searchStops(_ query: String) -> [TollStop] {
        let words = StationName.key(query).split(separator: " ")
        let stops = stations.map(TollStop.station) + points.map(TollStop.point)
        return stops.filter { stop in words.allSatisfy { stop.key.contains($0) } }
    }

    /// Stations whose name contains every word of `query` (accent/case insensitive).
    public func search(_ query: String) -> [TollStation] {
        let words = StationName.key(query).split(separator: " ")
        guard !words.isEmpty else { return stations }
        return stations.filter { station in
            let key = station.key
            return words.allSatisfy { key.contains($0) }
        }
    }

    /// Every published fare for this entry → exit pair, one per grid that lists it.
    public func fares(from entry: TollStation, to exit: TollStation) -> [(network: TollNetwork, fare: Fare)] {
        networks.compactMap { network in
            network.fare(from: entry, to: exit).map { (network, $0) }
        }
    }
}

public enum TollError: Error, Equatable, CustomStringConvertible {
    case missingResources
    case unknownStation(String)
    /// No official grid lists this entry → exit pair. The app never estimates.
    case noPublishedFare(entry: String, exit: String)
    /// Two grids publish different prices for the same pair.
    case conflictingFares(entry: String, exit: String)

    public var description: String {
        switch self {
        case .missingResources: return "Tariff resources are missing from the TollKit bundle."
        case .unknownStation(let name): return "Unknown toll station “\(name)”."
        case .noPublishedFare(let entry, let exit): return "No official fare is published for \(entry) → \(exit)."
        case .conflictingFares(let entry, let exit): return "Official grids disagree on \(entry) → \(exit)."
        }
    }
}
