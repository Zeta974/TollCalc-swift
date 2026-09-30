import Foundation

/// An amount in euro cents. Toll prices are always handled as integers so that
/// sums are exact to the cent — no floating point is ever involved.
public struct Money: Hashable, Comparable, Sendable, Codable {
    public let cents: Int

    public init(cents: Int) {
        self.cents = cents
    }

    public static let zero = Money(cents: 0)

    public static func + (lhs: Money, rhs: Money) -> Money {
        Money(cents: lhs.cents + rhs.cents)
    }

    public static func += (lhs: inout Money, rhs: Money) {
        lhs = lhs + rhs
    }

    public static func < (lhs: Money, rhs: Money) -> Bool {
        lhs.cents < rhs.cents
    }

    /// Exact decimal value in euros, for use with `Decimal`-based formatters.
    public var euros: Decimal {
        Decimal(cents) / 100
    }

    /// French formatting as printed on the operators' grids, e.g. "58,20 €".
    public var formatted: String {
        let sign = cents < 0 ? "-" : ""
        let absolute = abs(cents)
        let remainder = absolute % 100
        return "\(sign)\(absolute / 100),\(remainder < 10 ? "0" : "")\(remainder) €"
    }
}

extension Money: CustomStringConvertible {
    public var description: String { formatted }
}
