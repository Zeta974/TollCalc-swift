/// Everything about a vehicle that can change its toll price.
///
/// Only `vehicleClass` is required. The other fields matter on a few
/// networks; when one of them is needed and missing, quotes come back as a
/// range listing what is missing instead of a guessed price.
public struct Vehicle: Hashable, Sendable, Codable {
    public var vehicleClass: VehicleClass
    /// Euro emission class of a heavy vehicle (classes 3 and 4). Several
    /// operators modulate truck prices by it (A63, A150, A355). `nil` means the
    /// class is not declared, which is billed at the "non modulé" price.
    public var euroClass: EuroClass?
    /// Number of axles, including any trailer. Needed on the A63 (Atlandes)
    /// for class 4 vehicles.
    public var axles: Int?
    /// Gross vehicle weight rating (PTAC) in tonnes. Needed on the A63
    /// (Atlandes) for class 3 vehicles.
    public var grossWeightTonnes: Double?
    /// Natural gas (GNV) trucks have their own price on the A63.
    public var usesNaturalGas: Bool

    public init(_ vehicleClass: VehicleClass, euroClass: EuroClass? = nil, axles: Int? = nil,
                grossWeightTonnes: Double? = nil, usesNaturalGas: Bool = false) {
        self.vehicleClass = vehicleClass
        self.euroClass = euroClass
        self.axles = axles
        self.grossWeightTonnes = grossWeightTonnes
        self.usesNaturalGas = usesNaturalGas
    }
}

public enum EuroClass: Int, CaseIterable, Codable, Sendable {
    case euro0, euro1, euro2, euro3, euro4, euro5, euro6, euro7

    var key: String { "euro\(rawValue)" }
}

/// Inputs a quote may need beyond the vehicle class.
public enum TripInput: String, Hashable, Sendable, Codable, CaseIterable {
    /// Date and time of the passage (seasonal or time-of-day prices).
    case date
    /// `Vehicle.axles`
    case axles
    /// `Vehicle.grossWeightTonnes`
    case grossWeight
}
