package com.tollcalc.tollkit

import java.text.Normalizer

/** A toll station ("gare de péage") as named in an operator's tariff grid. */
data class TollStation(
    /** Network-scoped identifier, e.g. `aprr:ALLAINES`. */
    val id: String,
    /** Name exactly as printed in the official grid. */
    val name: String,
    /** Station code (AREA) or exit number (VINCI grids) when the grid publishes one. */
    val code: String?,
    val networkID: String,
    /** Mean position of the station's booths (from OpenStreetMap), if known. */
    val location: GeoPoint?,
    /** Every known booth of the station; used to detect passages along a route. */
    val booths: List<GeoPoint>,
) {
    /** Normalised name shared by the same physical station across grids. */
    val key: String by lazy(LazyThreadSafetyMode.PUBLICATION) { StationName.key(name) }

    /** "Système Ouvert" rows price the transition into an open-system section. */
    val isOpenSystemMarker: Boolean get() = key == "SYSTEME OUVERT"
}

/** One entry → exit line of an official grid. */
data class Fare(
    val entry: TollStation,
    val exit: TollStation,
    /** Tariff distance ("distance tarifaire") in metres, when the grid publishes it. */
    val distanceMeters: Int?,
    internal val prices: List<Money>,
) {
    fun price(vehicleClass: VehicleClass): Money = prices[vehicleClass.rawValue - 1]
}

/** A closed-system tariff grid published by one operator. */
class TollNetwork private constructor(
    val id: String,
    val name: String,
    /** Date the tariffs came into force (usually 1 February; ASF also revised on 1 June 2026). */
    val validFrom: String,
    val source: String,
    val stations: List<TollStation>,
    private val fareTable: Map<Long, Row>,
    private val stationsByKey: Map<String, Int>,
) {
    private class Row(val distanceMeters: Int?, val prices: List<Money>)

    val fareCount: Int get() = fareTable.size

    /** Station of this grid matching a name, using the normalised key. */
    fun station(named: String): TollStation? = stationsByKey[StationName.key(named)]?.let { stations[it] }

    fun fare(from: TollStation, to: TollStation): Fare? {
        val e = stationsByKey[from.key] ?: return null
        val x = stationsByKey[to.key] ?: return null
        val row = fareTable[pair(e, x)] ?: return null
        return Fare(stations[e], stations[x], row.distanceMeters, row.prices)
    }

    /** All fares, in grid order. Mostly useful for validation. */
    val allFares: List<Fare>
        get() = fareTable.map { (pair, row) ->
            Fare(stations[(pair ushr 32).toInt()], stations[pair.toInt()], row.distanceMeters, row.prices)
        }

    companion object {
        private fun pair(entry: Int, exit: Int): Long = (entry.toLong() shl 32) or (exit.toLong() and 0xFFFF_FFFFL)

        /** Decodes the JSON produced by `Tools/build_tariffs.py`. */
        fun fromJson(json: String): TollNetwork {
            val root = JsonReader(json).parse() as? Map<*, *> ?: corrupt("root is not an object")
            val id = root.string("id")
            val stations = root.list("stations").map { raw ->
                raw as? Map<*, *> ?: corrupt("station is not an object in $id")
                val lat = (raw["lat"] as? Number)?.toDouble()
                val lon = (raw["lon"] as? Number)?.toDouble()
                TollStation(
                    id = raw.string("id"),
                    name = raw.string("name"),
                    code = raw["code"] as? String,
                    networkID = id,
                    location = if (lat != null && lon != null) GeoPoint(lat, lon) else null,
                    booths = (raw["booths"] as? List<*>).orEmpty().mapNotNull { booth ->
                        val pt = (booth as? List<*>)?.map { (it as Number).toDouble() }
                        if (pt?.size == 2) GeoPoint(pt[0], pt[1]) else null
                    },
                )
            }

            val keys = HashMap<String, Int>()
            stations.forEachIndexed { index, station ->
                if (keys.put(station.key, index) != null) corrupt("Two stations normalise to ${station.key} in $id")
            }

            // [entry, exit, distanceMeters (-1 if unpublished), class1 … class5] — prices in cents.
            val rows = root.list("fares")
            val table = LinkedHashMap<Long, Row>(rows.size * 2)
            for (raw in rows) {
                val row = (raw as? List<*>)?.map { (it as? Long)?.toInt() }
                if (row == null || row.size != 8 || row.any { it == null } ||
                    row[0]!! !in stations.indices || row[1]!! !in stations.indices
                ) corrupt("Malformed fare row $raw in $id")
                val distance = row[2]!!
                table[pair(row[0]!!, row[1]!!)] =
                    Row(if (distance >= 0) distance else null, row.subList(3, 8).map { Money(it!!) })
            }

            return TollNetwork(
                id = id,
                name = root.string("name"),
                validFrom = root.string("validFrom"),
                source = root.string("source"),
                stations = stations,
                fareTable = table,
                stationsByKey = keys,
            )
        }

        private fun Map<*, *>.string(key: String): String = this[key] as? String ?: corrupt("missing \"$key\"")
        private fun Map<*, *>.list(key: String): List<*> = this[key] as? List<*> ?: corrupt("missing \"$key\"")
        private fun corrupt(message: String): Nothing = throw TollException.CorruptData(message)
    }
}

/**
 * Station-name normalisation shared by every grid, so "BELLEVILLE S/SAONE"
 * and "Belleville-sur-Saône" resolve to the same key. "Péage de" is kept:
 * "Péage de Biriatou" (the barrier) and "Biriatou" (the exit) are different
 * stations. Must match `StationName.key` in TollKit (Swift) and `app_key` in
 * Tools/build_tariffs.py.
 */
object StationName {
    private val diacritics = Regex("\\p{Mn}+")
    private val sur = Regex("(\\bS)?/\\s*")
    private val chateau = Regex("\\bCH\\.")
    private val separators = Regex("[^A-Z0-9]+")

    fun key(name: String): String {
        var s = Normalizer.normalize(name, Normalizer.Form.NFD).replace(diacritics, "").uppercase()
        s = s.replace(sur, " SUR ")
        s = s.replace(chateau, "CHATEAU ")
        s = s.replace("SAINTE", "STE").replace("SAINT", "ST")
        s = s.replace(separators, " ")
        return s.split(' ').filter { it.isNotEmpty() }.joinToString(" ")
    }
}
