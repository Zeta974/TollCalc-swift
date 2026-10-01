package com.tollcalc.tollkit

import kotlin.math.max
import kotlin.math.min

/** A toll station the route goes through. */
data class TollPassage(
    val station: TollStation,
    /** Distance from the start of the route to the station, in metres. */
    val distanceAlongRoute: Double,
    /** How far the closest booth is from the route line, in metres. */
    val offset: Double,
)

/**
 * Finds the toll stations a route polyline goes through, in driving order.
 *
 * Booths sit on the ramps or across the carriageway, so a route that uses a
 * station passes within a few metres of it, while a route that just drives
 * by an exit stays further away. [tolerance] sets that cut-off.
 */
class RouteTollDetector(database: TollDatabase, val tolerance: Double = 35.0) {
    val stations: List<TollStation> = database.stations.filter { it.booths.isNotEmpty() }

    fun passages(route: List<GeoPoint>): List<TollPassage> {
        if (route.size < 2) return emptyList()

        val cumulative = DoubleArray(route.size)
        for (i in 1 until route.size) {
            cumulative[i] = cumulative[i - 1] + Geo.distance(route[i - 1], route[i])
        }

        // ~0.001° is ~110 m in latitude; enough slack for any tolerance used here.
        val margin = max(0.001, tolerance / 50_000)
        val minLat = route.minOf { it.latitude } - margin
        val maxLat = route.maxOf { it.latitude } + margin
        val minLon = route.minOf { it.longitude } - margin * 1.6
        val maxLon = route.maxOf { it.longitude } + margin * 1.6

        val found = ArrayList<TollPassage>()
        for (station in stations) {
            var bestOffset = Double.POSITIVE_INFINITY
            var bestAlong = 0.0
            for (booth in station.booths) {
                if (booth.latitude !in minLat..maxLat || booth.longitude !in minLon..maxLon) continue
                for (i in 1 until route.size) {
                    val a = route[i - 1]
                    val b = route[i]
                    if (booth.latitude < min(a.latitude, b.latitude) - margin ||
                        booth.latitude > max(a.latitude, b.latitude) + margin ||
                        booth.longitude < min(a.longitude, b.longitude) - margin * 1.6 ||
                        booth.longitude > max(a.longitude, b.longitude) + margin * 1.6
                    ) continue
                    val (offset, fraction) = Geo.project(booth, a, b)
                    if (offset < bestOffset) {
                        bestOffset = offset
                        bestAlong = cumulative[i - 1] + fraction * (cumulative[i] - cumulative[i - 1])
                    }
                }
            }
            if (bestOffset <= tolerance) found.add(TollPassage(station, bestAlong, bestOffset))
        }
        return found.sortedBy { it.distanceAlongRoute }
    }
}
