/// The five toll classes used on every French motorway concession.
public enum VehicleClass: Int, CaseIterable, Codable, Sendable, Identifiable {
    /// Light vehicles: height ≤ 2 m and PTAC ≤ 3.5 t (cars, small vans).
    case class1 = 1
    /// Intermediate vehicles: height 2–3 m and PTAC ≤ 3.5 t (motorhomes, large vans).
    case class2 = 2
    /// Two-axle heavy vehicles: height ≥ 3 m or PTAC > 3.5 t.
    case class3 = 3
    /// Heavy vehicles and buses with three axles or more.
    case class4 = 4
    /// Motorcycles and trikes.
    case class5 = 5

    public var id: Int { rawValue }

    public var title: String { "Classe \(rawValue)" }

    public var summary: String {
        switch self {
        case .class1: return "Véhicules légers (≤ 2 m, ≤ 3,5 t)"
        case .class2: return "Véhicules intermédiaires (2 à 3 m, ≤ 3,5 t)"
        case .class3: return "Poids lourds et autocars à 2 essieux"
        case .class4: return "Poids lourds et autocars à 3 essieux et plus"
        case .class5: return "Motos, side-cars et trikes"
        }
    }
}
