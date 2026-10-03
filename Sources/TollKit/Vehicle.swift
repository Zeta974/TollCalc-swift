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
    /// Crit'Air 0 or fully electric. The A79 free-flow section has a lower
    /// price for these in classes 1, 2 and 5.
    public var isVeryLowEmission: Bool
    /// Subscriptions held for this vehicle. Where one has its own price, the
    /// quote uses it instead of the public price.
    public var subscriptions: Set<TollSubscription>

    public init(_ vehicleClass: VehicleClass, euroClass: EuroClass? = nil, axles: Int? = nil,
                grossWeightTonnes: Double? = nil, usesNaturalGas: Bool = false, isVeryLowEmission: Bool = false,
                subscriptions: Set<TollSubscription> = []) {
        self.vehicleClass = vehicleClass
        self.euroClass = euroClass
        self.axles = axles
        self.grossWeightTonnes = grossWeightTonnes
        self.usesNaturalGas = usesNaturalGas
        self.isVeryLowEmission = isVeryLowEmission
        self.subscriptions = subscriptions
    }

    private enum CodingKeys: String, CodingKey {
        case vehicleClass, euroClass, axles, grossWeightTonnes, usesNaturalGas, isVeryLowEmission, subscriptions
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.init(try c.decode(VehicleClass.self, forKey: .vehicleClass),
                  euroClass: try c.decodeIfPresent(EuroClass.self, forKey: .euroClass),
                  axles: try c.decodeIfPresent(Int.self, forKey: .axles),
                  grossWeightTonnes: try c.decodeIfPresent(Double.self, forKey: .grossWeightTonnes),
                  usesNaturalGas: try c.decodeIfPresent(Bool.self, forKey: .usesNaturalGas) ?? false,
                  isVeryLowEmission: try c.decodeIfPresent(Bool.self, forKey: .isVeryLowEmission) ?? false,
                  subscriptions: try c.decodeIfPresent(Set<TollSubscription>.self, forKey: .subscriptions) ?? [])
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
    /// `Vehicle.euroClass`, where no price is published for an undeclared
    /// class (A79 heavy vehicles).
    case euroClass
    /// Which Sanef A1 tariff level applies (normal, green or red). Sanef sets
    /// the green and red periods; the calendar is not part of the bundled data.
    case sanefA1Period
    /// Which of several grid entries sharing one place the trip uses (one
    /// plaza priced as two stations, e.g. the Toulouse nord/est and nord/ouest
    /// barriers). Name the stations in the itinerary to get one price.
    case station
}

/// A subscription with its own per-passage price. Only per-passage prices are
/// modelled; deposits and monthly fees are not part of a quote.
public enum TollSubscription: String, CaseIterable, Codable, Sendable {
    /// Any electronic toll badge (télépéage), whatever its issuer. The Duplex
    /// A86 has a lower price for trips ending at Vaucresson with one.
    case tollBadge = "toll-badge"
    /// Tunnels Prado (Marseille) "Tunnel Pass" badge.
    case pradoTunnelPass = "prado-tunnel-pass"
    /// Tunnels Prado "Tunnel Pass+" badge: an Ulys toll badge, so it also
    /// gets the Duplex A86 badge price.
    case pradoTunnelPassPlus = "prado-tunnel-pass-plus"
}

/// Class 1 tariff levels Sanef applies on the A1 towards Paris
/// (grille "Modulation horaire des tarifs sur A1").
public enum SanefA1Period: String, CaseIterable, Codable, Sendable {
    case normal, green, red
}
