package com.tollcalc.tollkit

/** The price of a trip, built only from published entry → exit fares. */
data class TollQuote(val vehicleClass: VehicleClass, val lines: List<Line>) {
    data class Line(
        val entry: TollStation,
        val exit: TollStation,
        /** Grid the fare comes from; `null` when no grid publishes this pair. */
        val networkID: String?,
        val distanceMeters: Int?,
        /** `null` when the segment could not be priced from official data. */
        val price: Money?,
    )

    /** Sum of the priced lines, exact to the cent. */
    val total: Money get() = lines.mapNotNull { it.price }.sum()

    /**
     * `true` when every segment was priced from an official grid. When it is
     * `false`, [total] is only a lower bound and must be shown as such.
     */
    val isComplete: Boolean get() = lines.all { it.price != null }

    val unpricedLines: List<Line> get() = lines.filter { it.price == null }
}

/**
 * A simple itinerary: the toll stations to go through, in order, e.g.
 * `[ALLAINES, AMBERIEU]` for a single ticket, or more stops for a trip that
 * leaves and re-enters the motorway.
 */
data class TollItinerary(
    val stops: List<TollStation> = emptyList(),
    val vehicleClass: VehicleClass = VehicleClass.CLASS1,
)

class TollCalculator(val database: TollDatabase) {

    /** Price of a single ticket: enter at [entry], leave at [exit]. */
    @Throws(TollException::class)
    fun fare(entry: TollStation, exit: TollStation, vehicleClass: VehicleClass): TollQuote.Line {
        val found = database.fares(entry, exit)
        val first = found.firstOrNull()?.second ?: throw TollException.NoPublishedFare(entry.name, exit.name)
        // Grids overlap on shared stations; they must agree to the cent.
        val price = first.price(vehicleClass)
        if (!found.all { it.second.price(vehicleClass) == price }) {
            throw TollException.ConflictingFares(entry.name, exit.name)
        }
        return TollQuote.Line(first.entry, first.exit, found.first().first.id, first.distanceMeters, price)
    }

    @Throws(TollException::class)
    fun quote(from: String, to: String, vehicleClass: VehicleClass): TollQuote {
        val e = database.station(from) ?: throw TollException.UnknownStation(from)
        val x = database.station(to) ?: throw TollException.UnknownStation(to)
        return TollQuote(vehicleClass, listOf(fare(e, x, vehicleClass)))
    }

    /**
     * Price a trip from the ordered toll stations it passes through.
     *
     * A published entry → exit fare is what the driver pays between those two
     * stations, including any toll barrier in between. So the trip is split
     * into the fewest consecutive tickets that each have a published fare
     * (a station passed "on the way" that is really a drive-by is absorbed by
     * the longer ticket). Segments that no grid prices are reported as
     * unpriced rather than estimated.
     */
    fun quote(passages: List<TollStation>, vehicleClass: VehicleClass): TollQuote {
        val path = ArrayList<TollStation>()
        for (station in passages) {
            if (path.lastOrNull()?.key != station.key) path.add(station)
        }
        if (path.size < 2) return TollQuote(vehicleClass, emptyList())

        // Shortest path over a DAG: node i = "a ticket ends at path[i]".
        // A priced ticket costs 1; an unpriced hop between neighbours costs a
        // lot, so it is only used when nothing published covers that stretch.
        val unpricedCost = 1_000
        val n = path.size
        val best = IntArray(n) { Int.MAX_VALUE }
        val previous = arrayOfNulls<Pair<Int, TollQuote.Line>>(n)
        best[0] = 0
        for (i in 0 until n) {
            if (best[i] == Int.MAX_VALUE) continue
            for (j in i + 1 until n) {
                val priced = try {
                    fare(path[i], path[j], vehicleClass)
                } catch (_: TollException) {
                    null
                }
                val (line, cost) = when {
                    priced != null -> priced to 1
                    j == i + 1 -> TollQuote.Line(path[i], path[j], null, null, null) to unpricedCost
                    else -> continue
                }
                if (best[i] + cost < best[j]) {
                    best[j] = best[i] + cost
                    previous[j] = i to line
                }
            }
        }

        val lines = ArrayList<TollQuote.Line>()
        var cursor = n - 1
        while (true) {
            val (index, line) = previous[cursor] ?: break
            lines.add(line)
            cursor = index
        }
        return TollQuote(vehicleClass, lines.reversed())
    }

    fun quote(itinerary: TollItinerary): TollQuote = quote(itinerary.stops, itinerary.vehicleClass)
}
