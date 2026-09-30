import Foundation

/// A toll station ("gare de péage") as named in an operator's tariff grid.
public struct TollStation: Identifiable, Hashable, Sendable {
    /// Network-scoped identifier, e.g. `aprr:ALLAINES`.
    public let id: String
    /// Name exactly as printed in the official grid.
    public let name: String
    /// Operator station code when the grid publishes one (AREA does).
    public let code: String?
    public let networkID: String
    /// Mean position of the station's booths (from OpenStreetMap), if known.
    public let location: GeoPoint?
    /// Every known booth of the station; used to detect passages along a route.
    public let booths: [GeoPoint]

    /// Normalised name shared by the same physical station across grids.
    public var key: String { StationName.key(name) }

    /// "Système Ouvert" rows price the transition into an open-system section.
    public var isOpenSystemMarker: Bool { key == "SYSTEME OUVERT" }
}

/// One entry → exit line of an official grid.
public struct Fare: Hashable, Sendable {
    public let entry: TollStation
    public let exit: TollStation
    /// Tariff distance ("distance tarifaire") in metres, as published.
    public let distanceMeters: Int
    let prices: [Money]

    public func price(for vehicleClass: VehicleClass) -> Money {
        prices[vehicleClass.rawValue - 1]
    }
}

/// A closed-system tariff grid published by one operator.
public struct TollNetwork: Identifiable, Sendable {
    public let id: String
    public let name: String
    /// Date the tariffs came into force (tariffs change every 1 February).
    public let validFrom: String
    public let source: URL
    public let stations: [TollStation]

    private let fareTable: [Pair: Row]
    private let stationsByKey: [String: Int]

    struct Pair: Hashable {
        let entry: Int32
        let exit: Int32
    }

    struct Row {
        let distanceMeters: Int
        let prices: [Money]
    }

    public var fareCount: Int { fareTable.count }

    /// Station of this grid matching a name, using the normalised key.
    public func station(named name: String) -> TollStation? {
        stationsByKey[StationName.key(name)].map { stations[$0] }
    }

    public func fare(from entry: TollStation, to exit: TollStation) -> Fare? {
        guard let e = stationsByKey[entry.key], let x = stationsByKey[exit.key],
              let row = fareTable[Pair(entry: Int32(e), exit: Int32(x))] else { return nil }
        return Fare(entry: stations[e], exit: stations[x], distanceMeters: row.distanceMeters, prices: row.prices)
    }

    /// All fares, in grid order. Mostly useful for validation.
    public var allFares: [Fare] {
        fareTable.map { pair, row in
            Fare(entry: stations[Int(pair.entry)], exit: stations[Int(pair.exit)],
                 distanceMeters: row.distanceMeters, prices: row.prices)
        }
    }
}

// MARK: - Decoding the JSON produced by Tools/build_tariffs.py

extension TollNetwork: Decodable {
    private enum CodingKeys: String, CodingKey {
        case id, name, validFrom, source, stations, fares
    }

    private struct RawStation: Decodable {
        let id: String
        let name: String
        let code: String?
        let lat: Double?
        let lon: Double?
        let booths: [[Double]]?
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        name = try c.decode(String.self, forKey: .name)
        validFrom = try c.decode(String.self, forKey: .validFrom)
        source = try c.decode(URL.self, forKey: .source)
        let networkID = id
        stations = try c.decode([RawStation].self, forKey: .stations).map { raw in
            TollStation(
                id: raw.id,
                name: raw.name,
                code: raw.code,
                networkID: networkID,
                location: raw.lat.flatMap { lat in raw.lon.map { GeoPoint(latitude: lat, longitude: $0) } },
                booths: (raw.booths ?? []).compactMap { $0.count == 2 ? GeoPoint(latitude: $0[0], longitude: $0[1]) : nil }
            )
        }

        var keys: [String: Int] = [:]
        for (index, station) in stations.enumerated() {
            if keys.updateValue(index, forKey: station.key) != nil {
                throw DecodingError.dataCorruptedError(forKey: .stations, in: c,
                    debugDescription: "Two stations normalise to \(station.key) in \(networkID)")
            }
        }
        stationsByKey = keys

        // [entry, exit, distanceMeters, class1 … class5] — prices in cents.
        let rows = try c.decode([[Int]].self, forKey: .fares)
        var table: [Pair: Row] = [:]
        table.reserveCapacity(rows.count)
        for row in rows {
            guard row.count == 8, stations.indices.contains(row[0]), stations.indices.contains(row[1]) else {
                throw DecodingError.dataCorruptedError(forKey: .fares, in: c,
                    debugDescription: "Malformed fare row \(row) in \(networkID)")
            }
            table[Pair(entry: Int32(row[0]), exit: Int32(row[1]))] =
                Row(distanceMeters: row[2], prices: row[3...7].map { Money(cents: $0) })
        }
        fareTable = table
    }
}

/// Station-name normalisation shared by every grid, so "BELLEVILLE S/SAONE"
/// and "Belleville-sur-Saône" resolve to the same key.
public enum StationName {
    public static func key(_ name: String) -> String {
        var s = name.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: Locale(identifier: "fr_FR"))
            .uppercased()
        s = s.replacingOccurrences(of: #"\bPEAGE (DE |D')?"#, with: "", options: .regularExpression)
        s = s.replacingOccurrences(of: #"(\bS)?/\s*"#, with: " SUR ", options: .regularExpression)
        s = s.replacingOccurrences(of: #"\bCH\."#, with: "CHATEAU ", options: .regularExpression)
        s = s.replacingOccurrences(of: "SAINTE", with: "STE").replacingOccurrences(of: "SAINT", with: "ST")
        s = s.replacingOccurrences(of: "[^A-Z0-9]+", with: " ", options: .regularExpression)
        return s.split(separator: " ").joined(separator: " ")
    }
}
