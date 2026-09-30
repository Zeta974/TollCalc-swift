import MapKit
import SwiftUI
import TollKit

struct ContentView: View {
    @Environment(TripModel.self) private var model
    @State private var camera: MapCameraPosition = .region(MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 46.6, longitude: 2.4),
        span: MKCoordinateSpan(latitudeDelta: 10, longitudeDelta: 10)))

    var body: some View {
        @Bindable var model = model
        VStack(spacing: 0) {
            Map(position: $camera) {
                if model.mode == .route {
                    if let route = model.route {
                        MapPolyline(route.polyline)
                            .stroke(.blue, lineWidth: 5)
                    }
                    ForEach(model.passages, id: \.station.id) { passage in
                        if let location = passage.station.location {
                            Marker(passage.station.name, systemImage: "eurosign", coordinate: location.coordinate)
                                .tint(.orange)
                        }
                    }
                } else {
                    ForEach(Array(model.itinerary.stops.enumerated()), id: \.offset) { _, station in
                        if let location = station.location {
                            Marker(station.name, systemImage: "eurosign", coordinate: location.coordinate)
                                .tint(.orange)
                        }
                    }
                }
            }
            .frame(minHeight: 260)

            Form {
                if let loadError = model.loadError {
                    Section { Text(loadError).foregroundStyle(.red) }
                }

                Section {
                    Picker("Mode", selection: $model.mode) {
                        ForEach(TripModel.Mode.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .onChange(of: model.mode) { model.modeChanged() }

                    Picker("Véhicule", selection: $model.vehicleClass) {
                        ForEach(VehicleClass.allCases) { vehicleClass in
                            Text("\(vehicleClass.title) – \(vehicleClass.summary)").tag(vehicleClass)
                        }
                    }
                }

                switch model.mode {
                case .route: routeSection
                case .stations: StationsItineraryView()
                }

                if let error = model.errorMessage {
                    Section { Text(error).foregroundStyle(.red) }
                }

                if let quote = model.quote {
                    QuoteSection(quote: quote)
                }

                Section {
                    Text(model.networksSummary)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .onChange(of: model.route) {
            if let rect = model.route?.polyline.boundingMapRect {
                camera = .rect(rect.insetBy(dx: -rect.width * 0.1, dy: -rect.height * 0.1))
            }
        }
    }

    @ViewBuilder private var routeSection: some View {
        @Bindable var model = model
        Section("Itinéraire") {
            TextField("Départ (ex. Paris)", text: $model.originQuery)
                .textContentType(.addressCity)
            TextField("Arrivée (ex. Lyon)", text: $model.destinationQuery)
                .textContentType(.addressCity)
            Button {
                Task { await model.computeRoute() }
            } label: {
                HStack {
                    Text("Calculer le péage")
                    if model.isWorking { Spacer(); ProgressView() }
                }
            }
            .disabled(model.isWorking || model.originQuery.isEmpty || model.destinationQuery.isEmpty)

            if let route = model.route {
                LabeledContent("Distance", value: Measurement(value: route.distance / 1000, unit: UnitLength.kilometers)
                    .formatted(.measurement(width: .abbreviated, numberFormatStyle: .number.precision(.fractionLength(0)))))
                LabeledContent("Gares traversées", value: "\(model.passages.count)")
            }
        }
    }
}

struct QuoteSection: View {
    let quote: TollQuote

    var body: some View {
        Section {
            ForEach(Array(quote.lines.enumerated()), id: \.offset) { _, line in
                VStack(alignment: .leading, spacing: 2) {
                    HStack {
                        Text("\(line.entry.name) → \(line.exit.name)")
                        Spacer()
                        if let price = line.price {
                            Text(price.formatted).monospacedDigit()
                        } else {
                            Text("non publié").foregroundStyle(.orange)
                        }
                    }
                    if let network = line.networkID, let meters = line.distanceMeters {
                        Text("\(network.uppercased()) · \(meters / 1000) km tarifaires")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            HStack {
                Text(quote.isComplete ? "Total" : "Total (incomplet)").bold()
                Spacer()
                Text(quote.total.formatted).bold().monospacedDigit()
            }
        } header: {
            Text("Péage – \(quote.vehicleClass.title)")
        } footer: {
            if quote.lines.isEmpty {
                Text("Aucune gare de péage connue sur ce trajet.")
            } else if !quote.isComplete {
                Text("Certains tronçons ne figurent dans aucune grille officielle chargée (réseau non couvert ou gare sans coordonnées). Le total affiché ne les inclut pas.")
            }
        }
    }
}
