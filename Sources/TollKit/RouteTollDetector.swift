import Foundation

/// A station or toll point the route goes through.
public struct TollPassage: Sendable, Hashable {
    public let stop: TollStop
    /// Distance from the start of the route to the stop, in metres.
    public let distanceAlongRoute: Double
    /// How far the closest booth is from the route line, in metres.
    public let offset: Double

    public var station: TollStation? { stop.station }

    /// The route goes through the station's toll plaza (it passes over a
    /// booth), so the driver stops there. A plaza beside the road (an exit's
    /// ramp booths a few tens of metres from the main line) is only driven past.
    public var isThroughPlaza: Bool { !stop.booths.isEmpty && offset <= Self.plazaOffset }

    /// Booths are mapped on the lane the route follows: real stops measure 0–2 m.
    public static let plazaOffset = 10.0
}

/// Finds the stations and toll points a route polyline goes through, in
/// driving order.
///
/// Booths sit on the ramps or across the carriageway, so a route that uses a
/// station passes within a few metres of it, while a route that just drives
/// by an exit stays further away. `tolerance` sets that cut-off.
///
/// Stations with no mapped booth are matched on their interchange instead:
/// the exit nodes of both carriageways. A route leaving there runs over the
/// exit node; a route joining there passes next to the opposite
/// carriageway's exit node, hence the wider `junctionTolerance`. A route that
/// only drives past an interchange is detected too, which is harmless: the
/// calculator absorbs stations passed on the way into the longer ticket.
public struct RouteTollDetector: Sendable {
    public let stops: [TollStop]
    public var tolerance: Double
    public var junctionTolerance: Double

    public init(database: TollDatabase, tolerance: Double = 35, junctionTolerance: Double = 80) {
        self.stops = (database.stations.map(TollStop.station) + database.points.map(TollStop.point))
            .filter { !$0.anchors.isEmpty }
        self.tolerance = tolerance
        self.junctionTolerance = junctionTolerance
    }

    public func passages(along route: [GeoPoint]) -> [TollPassage] {
        guard route.count >= 2 else { return [] }

        var cumulative = [0.0]
        cumulative.reserveCapacity(route.count)
        for i in 1..<route.count {
            cumulative.append(cumulative[i - 1] + Geo.distance(route[i - 1], route[i]))
        }

        // ~0.001° is ~110 m in latitude; enough slack for any tolerance used here.
        let margin = max(0.001, max(tolerance, junctionTolerance) / 50_000)
        let minLat = route.map(\.latitude).min()! - margin, maxLat = route.map(\.latitude).max()! + margin
        let minLon = route.map(\.longitude).min()! - margin * 1.6, maxLon = route.map(\.longitude).max()! + margin * 1.6

        var found: [TollPassage] = []
        for stop in stops {
            var bestOffset = Double.infinity
            var bestAlong = 0.0
            let (anchors, limit) = stop.booths.isEmpty ? (stop.anchors, junctionTolerance) : (stop.booths, tolerance)
            for booth in anchors
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
            if bestOffset <= limit {
                found.append(TollPassage(stop: stop, distanceAlongRoute: bestAlong, offset: bestOffset))
            }
        }
        return found.sorted { $0.distanceAlongRoute < $1.distanceAlongRoute }
    }
}

extension TollCalculator {
    /// Price a route: detect what it goes through, then quote it.
    public func quote(route: [GeoPoint], vehicle: Vehicle, date: Date? = nil, sanefA1Period: SanefA1Period? = nil,
                      detector: RouteTollDetector? = nil) -> (passages: [TollPassage], quote: TollQuote) {
        let passages = (detector ?? RouteTollDetector(database: database)).passages(along: route)
        return (passages, quote(passages: passages, vehicle: vehicle, date: date, sanefA1Period: sanefA1Period))
    }

    /// Price the passages of a route: tickets change at every plaza the
    /// route goes through (`TollPassage.isThroughPlaza`).
    public func quote(passages: [TollPassage], vehicle: Vehicle, date: Date? = nil,
                      sanefA1Period: SanefA1Period? = nil) -> TollQuote {
        let plazas = Set(passages.filter(\.isThroughPlaza).compactMap { $0.station?.id })
        return quote(stops: passages.map(\.stop), vehicle: vehicle, date: date, sanefA1Period: sanefA1Period,
                     plazaStops: plazas)
    }
}
