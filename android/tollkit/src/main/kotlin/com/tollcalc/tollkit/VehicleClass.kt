package com.tollcalc.tollkit

/** The five toll classes used on every French motorway concession. */
enum class VehicleClass(val rawValue: Int, val summary: String) {
    /** Light vehicles: height ≤ 2 m and PTAC ≤ 3.5 t (cars, small vans). */
    CLASS1(1, "Véhicules légers (≤ 2 m, ≤ 3,5 t)"),
    /** Intermediate vehicles: height 2–3 m and PTAC ≤ 3.5 t (motorhomes, large vans). */
    CLASS2(2, "Véhicules intermédiaires (2 à 3 m, ≤ 3,5 t)"),
    /** Two-axle heavy vehicles: height ≥ 3 m or PTAC > 3.5 t. */
    CLASS3(3, "Poids lourds et autocars à 2 essieux"),
    /** Heavy vehicles and buses with three axles or more. */
    CLASS4(4, "Poids lourds et autocars à 3 essieux et plus"),
    /** Motorcycles and trikes. */
    CLASS5(5, "Motos, side-cars et trikes");

    val title: String get() = "Classe $rawValue"

    companion object {
        fun of(rawValue: Int): VehicleClass? = entries.firstOrNull { it.rawValue == rawValue }
    }
}
