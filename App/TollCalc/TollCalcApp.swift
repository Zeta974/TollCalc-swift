import SwiftUI

@main
struct TollCalcApp: App {
    @State private var model = TripModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(model)
        }
    }
}
