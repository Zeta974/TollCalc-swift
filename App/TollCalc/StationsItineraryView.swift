import SwiftUI
import TollKit

/// Build an itinerary by picking toll stations from the official grids.
struct StationsItineraryView: View {
    @Environment(TripModel.self) private var model
    @State private var isPicking = false

    var body: some View {
        @Bindable var model = model
        Section {
            ForEach(Array(model.itinerary.stops.enumerated()), id: \.offset) { index, station in
                LabeledContent(label(for: index), value: station.name)
            }
            .onDelete { model.itinerary.stops.remove(atOffsets: $0) }

            Button(model.itinerary.stops.isEmpty ? "Choisir la gare d'entrée" : "Ajouter une gare") {
                isPicking = true
            }
        } header: {
            Text("Gares")
        } footer: {
            Text("Entrée, puis sortie. Ajoutez des gares intermédiaires si vous sortez puis reprenez l'autoroute.")
        }
        .sheet(isPresented: $isPicking) {
            if let database = model.database {
                StationPicker(database: database) { station in
                    model.itinerary.stops.append(station)
                    isPicking = false
                }
            }
        }
    }

    private func label(for index: Int) -> String {
        switch index {
        case 0: return "Entrée"
        case model.itinerary.stops.count - 1: return "Sortie"
        default: return "Gare \(index + 1)"
        }
    }
}

struct StationPicker: View {
    let database: TollDatabase
    let onPick: (TollStation) -> Void
    @State private var query = ""

    var body: some View {
        NavigationStack {
            List(database.search(query)) { station in
                Button(station.name) { onPick(station) }
            }
            .searchable(text: $query, prompt: "Nom de la gare")
            .navigationTitle("Gare de péage")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}
