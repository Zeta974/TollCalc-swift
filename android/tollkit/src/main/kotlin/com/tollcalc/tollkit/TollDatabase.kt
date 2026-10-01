package com.tollcalc.tollkit

/**
 * Every tariff grid known to the app.
 *
 * The same physical station appears in several grids (the APRR grid also
 * prices tickets that end on neighbouring networks), so stations are merged
 * across grids by their normalised name ([TollStation.key]).
 */
class TollDatabase(val networks: List<TollNetwork>) {
    private val stationsByKey: Map<String, TollStation>

    /** One entry per physical station, sorted by name, booths merged across grids. */
    val stations: List<TollStation>

    init {
        val merged = HashMap<String, TollStation>()
        for (network in networks) {
            for (station in network.stations) {
                val existing = merged[station.key]
                merged[station.key] = if (existing == null) station else existing.copy(
                    code = existing.code ?: station.code,
                    location = existing.location ?: station.location,
                    booths = existing.booths + station.booths.filter { it !in existing.booths },
                )
            }
        }
        stationsByKey = merged
        stations = merged.values.sortedBy { it.name }
    }

    fun station(named: String): TollStation? = stationsByKey[StationName.key(named)]

    /** Stations whose name contains every word of [query] (accent/case insensitive). */
    fun search(query: String): List<TollStation> {
        val words = StationName.key(query).split(' ').filter { it.isNotEmpty() }
        if (words.isEmpty()) return stations
        return stations.filter { station -> words.all { station.key.contains(it) } }
    }

    /** Every published fare for this entry → exit pair, one per grid that lists it. */
    fun fares(from: TollStation, to: TollStation): List<Pair<TollNetwork, Fare>> =
        networks.mapNotNull { network -> network.fare(from, to)?.let { network to it } }

    companion object {
        private const val RESOURCE_DIR = "networks"

        /**
         * Loads the grids bundled with TollKit (the `networks/<id>.json` files on the
         * classpath, listed in `networks/index.txt`). Works the same on the JVM
         * and on Android, where library Java resources are packaged in the APK.
         *
         * Parsing ~2 MB of JSON takes a moment: call it off the main thread.
         */
        @JvmStatic
        fun bundled(): TollDatabase {
            val loader = TollDatabase::class.java.classLoader ?: throw TollException.MissingResources()
            fun read(path: String): String =
                loader.getResourceAsStream(path)?.use { it.readBytes().toString(Charsets.UTF_8) }
                    ?: throw TollException.MissingResources()
            val files = read("$RESOURCE_DIR/index.txt").lines().map { it.trim() }.filter { it.endsWith(".json") }.sorted()
            if (files.isEmpty()) throw TollException.MissingResources()
            return fromJson(files.map { read("$RESOURCE_DIR/$it") })
        }

        /** Builds a database from the JSON text of each grid (e.g. read from Android assets). */
        @JvmStatic
        fun fromJson(grids: List<String>): TollDatabase = TollDatabase(grids.map(TollNetwork::fromJson))
    }
}

sealed class TollException(message: String) : Exception(message) {
    class MissingResources : TollException("Tariff resources are missing from the TollKit bundle.")

    class CorruptData(detail: String) : TollException("Malformed tariff data: $detail")

    data class UnknownStation(val name: String) : TollException("Unknown toll station “$name”.")

    /** No official grid lists this entry → exit pair. The app never estimates. */
    data class NoPublishedFare(val entry: String, val exit: String) :
        TollException("No official fare is published for $entry → $exit.")

    /** Two grids publish different prices for the same pair. */
    data class ConflictingFares(val entry: String, val exit: String) :
        TollException("Official grids disagree on $entry → $exit.")
}
