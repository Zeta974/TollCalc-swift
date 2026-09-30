import Foundation

/// A toll station the route goes through.
public struct TollPassage: Sendable, Hashable {
    public let station: TollStation
    /// Distance from the start of the route to the station, in metres.
    public let distanceAlongRoute: Double
    /// How far the closest booth is from the route line, in metres.
    public let offset: Double
}

/// Finds the toll stations a route polyline goes through, in driving order.
///
/// Booths sit on the ramps or across the carriageway, so a route that uses a
/// station passes within a few metres of it, while a route that just drives
/// by an exit stays further away. `tolerance` sets that cut-off.
public struct RouteTollDetector: Sendable {
    public let stations: [TollStation]
    public var tolerance: Double

    public init(database: TollDatabase, tolerance: Double = 35) {
        self.stations = database.stations.filter { !$0.booths.isEmpty }
        self.tolerance = tolerance
    }

    public func passages(along route: [GeoPoint]) -> [TollPassage] {
        guard route.count >= 2 else { return [] }

        var cumulative = [0.0]
        cumulative.reserveCapacity(route.count)
        for i in 1..<route.count {
            cumulative.append(cumulative[i - 1] + Geo.distance(route[i - 1], route[i]))
        }

        // ~0.001° is ~110 m in latitude; enough slack for any tolerance used here.
        let margin = max(0.001, tolerance / 50_000)
        let minLat = route.map(\.latitude).min()! - margin, maxLat = route.map(\.latitude).max()! + margin
        let minLon = route.map(\.longitude).min()! - margin * 1.6, maxLon = route.map(\.longitude).max()! + margin * 1.6

        var found: [TollPassage] = []
        for station in stations {
            var bestOffset = Double.infinity
            var bestAlong = 0.0
            for booth in station.booths
            where (minLat...maxLat).contains(booth.latitude) && (minLon...maxLon).contains(booth.longitude) {
                for i in 1..<route.count {
                    let a = route[i - 1], b = route[i]
                    if booth.latitude < min(a.latitude, b.latitude) - margin
                        || booth.latitude > max(a.latitude, b.latitude) + margin
                        || booth.longitude < min(a.longitude, b.longitude) - margin * 1.6
                        || booth.longitude > max(a.longitude, b.longitude) + margin * 1.6 { continue }
                    let (offset, fraction) = Geo.project(booth, onto: a, b)
                    if offset < bestOffset {
                        bestOffset = offset
                        bestAlong = cumulative[i - 1] + fraction * (cumulative[i] - cumulative[i - 1])
                    }
                }
            }
            if bestOffset <= tolerance {
                found.append(TollPassage(station: station, distanceAlongRoute: bestAlong, offset: bestOffset))
            }
        }
        return found.sorted { $0.distanceAlongRoute < $1.distanceAlongRoute }
    }
}
