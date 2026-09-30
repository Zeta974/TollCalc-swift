import MapKit
import TollKit

/// Geocoding and routing with Apple MapKit (free, no API key required).
enum RouteService {
    enum Failure: LocalizedError {
        case placeNotFound(String)
        case noRoute

        var errorDescription: String? {
            switch self {
            case .placeNotFound(let query): return "Lieu introuvable : « \(query) »."
            case .noRoute: return "Aucun itinéraire routier trouvé."
            }
        }
    }

    static func place(for query: String) async throws -> MKMapItem {
        let request = MKLocalSearch.Request()
        request.naturalLanguageQuery = query
        // Bias results towards metropolitan France.
        request.region = MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: 46.6, longitude: 2.4),
            span: MKCoordinateSpan(latitudeDelta: 11, longitudeDelta: 13))
        let response = try await MKLocalSearch(request: request).start()
        guard let item = response.mapItems.first else { throw Failure.placeNotFound(query) }
        return item
    }

    static func route(from origin: MKMapItem, to destination: MKMapItem) async throws -> MKRoute {
        let request = MKDirections.Request()
        request.source = origin
        request.destination = destination
        request.transportType = .automobile
        request.tollPreference = .any
        let response = try await MKDirections(request: request).calculate()
        guard let route = response.routes.first else { throw Failure.noRoute }
        return route
    }
}

extension MKPolyline {
    var geoPoints: [GeoPoint] {
        let points = self.points()
        return (0..<pointCount).map { index in
            let coordinate = points[index].coordinate
            return GeoPoint(latitude: coordinate.latitude, longitude: coordinate.longitude)
        }
    }
}

extension GeoPoint {
    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }
}
