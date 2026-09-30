import Foundation

/// A WGS84 coordinate. Kept independent from CoreLocation so TollKit builds
/// and tests on any platform; the app converts to `CLLocationCoordinate2D`.
public struct GeoPoint: Hashable, Sendable, Codable {
    public var latitude: Double
    public var longitude: Double

    public init(latitude: Double, longitude: Double) {
        self.latitude = latitude
        self.longitude = longitude
    }
}

enum Geo {
    static let earthRadius = 6_371_008.8

    /// Great-circle distance in metres.
    static func distance(_ a: GeoPoint, _ b: GeoPoint) -> Double {
        let lat1 = a.latitude * .pi / 180, lat2 = b.latitude * .pi / 180
        let dLat = lat2 - lat1
        let dLon = (b.longitude - a.longitude) * .pi / 180
        let h = sin(dLat / 2) * sin(dLat / 2) + cos(lat1) * cos(lat2) * sin(dLon / 2) * sin(dLon / 2)
        return 2 * earthRadius * asin(min(1, sqrt(h)))
    }

    /// Distance in metres from `p` to segment `a`–`b`, and the fraction (0…1)
    /// along the segment of the closest point. Uses a local equirectangular
    /// projection, which is accurate to well under a metre at segment scale.
    static func project(_ p: GeoPoint, onto a: GeoPoint, _ b: GeoPoint) -> (distance: Double, fraction: Double) {
        let cosLat = cos(a.latitude * .pi / 180)
        func xy(_ q: GeoPoint) -> (Double, Double) {
            ((q.longitude - a.longitude) * cosLat * .pi / 180 * earthRadius,
             (q.latitude - a.latitude) * .pi / 180 * earthRadius)
        }
        let (bx, by) = xy(b)
        let (px, py) = xy(p)
        let lengthSquared = bx * bx + by * by
        let t = lengthSquared == 0 ? 0 : max(0, min(1, (px * bx + py * by) / lengthSquared))
        let dx = px - t * bx, dy = py - t * by
        return (sqrt(dx * dx + dy * dy), t)
    }
}
