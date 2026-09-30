import MapKit
import Observation
import TollKit

@Observable
@MainActor
final class TripModel {
    enum Mode: String, CaseIterable, Identifiable {
        case route = "Trajet"
        case stations = "Gares"
        var id: String { rawValue }
    }

    let database: TollDatabase?
    let loadError: String?

    var mode: Mode = .route
    var vehicleClass: VehicleClass = .class1 { didSet { requote() } }

    // Route mode: free-text origin/destination routed with MapKit.
    var originQuery = ""
    var destinationQuery = ""
    private(set) var route: MKRoute?
    private(set) var passages: [TollPassage] = []

    // Stations mode: an itinerary picked from the official station lists.
    var itinerary = TollItinerary() { didSet { requote() } }

    private(set) var quote: TollQuote?
    private(set) var errorMessage: String?
    private(set) var isWorking = false

    init() {
        do {
            database = try TollDatabase.bundled()
            loadError = nil
        } catch {
            database = nil
            loadError = "\(error)"
        }
    }

    var networksSummary: String {
        guard let database else { return "" }
        let names = database.networks.map(\.name).joined(separator: ", ")
        let validFrom = database.networks.map(\.validFrom).min() ?? ""
        return "Tarifs officiels en vigueur au \(validFrom) : \(names)."
    }

    func computeRoute() async {
        guard let database else { return }
        let origin = originQuery.trimmingCharacters(in: .whitespaces)
        let destination = destinationQuery.trimmingCharacters(in: .whitespaces)
        guard !origin.isEmpty, !destination.isEmpty else { return }

        isWorking = true
        errorMessage = nil
        defer { isWorking = false }
        do {
            let from = try await RouteService.place(for: origin)
            let to = try await RouteService.place(for: destination)
            let route = try await RouteService.route(from: from, to: to)
            let polyline = route.polyline.geoPoints
            let passages = await Task.detached {
                RouteTollDetector(database: database).passages(along: polyline)
            }.value
            self.route = route
            self.passages = passages
            requote()
        } catch {
            self.route = nil
            self.passages = []
            self.quote = nil
            errorMessage = error.localizedDescription
        }
    }

    private func requote() {
        guard let database else { return }
        let calculator = TollCalculator(database: database)
        switch mode {
        case .route:
            quote = route == nil ? nil : calculator.quote(passages: passages.map(\.station), vehicleClass: vehicleClass)
        case .stations:
            var itinerary = itinerary
            itinerary.vehicleClass = vehicleClass
            quote = itinerary.stops.count >= 2 ? calculator.quote(itinerary) : nil
        }
    }

    func modeChanged() {
        errorMessage = nil
        requote()
    }
}
