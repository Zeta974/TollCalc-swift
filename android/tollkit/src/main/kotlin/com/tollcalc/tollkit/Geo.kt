package com.tollcalc.tollkit

import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * A WGS84 coordinate. Kept independent from `android.location` so TollKit builds
 * and tests on the plain JVM; the app converts from its map/routing types.
 */
data class GeoPoint(val latitude: Double, val longitude: Double)

internal object Geo {
    const val EARTH_RADIUS = 6_371_008.8
    private const val DEG = Math.PI / 180

    /** Great-circle distance in metres. */
    fun distance(a: GeoPoint, b: GeoPoint): Double {
        val lat1 = a.latitude * DEG
        val lat2 = b.latitude * DEG
        val dLat = lat2 - lat1
        val dLon = (b.longitude - a.longitude) * DEG
        val h = sin(dLat / 2) * sin(dLat / 2) + cos(lat1) * cos(lat2) * sin(dLon / 2) * sin(dLon / 2)
        return 2 * EARTH_RADIUS * asin(min(1.0, sqrt(h)))
    }

    /**
     * Distance in metres from [p] to segment [a]–[b], and the fraction (0…1)
     * along the segment of the closest point. Uses a local equirectangular
     * projection, which is accurate to well under a metre at segment scale.
     */
    fun project(p: GeoPoint, a: GeoPoint, b: GeoPoint): Projection {
        val cosLat = cos(a.latitude * DEG)
        val bx = (b.longitude - a.longitude) * cosLat * DEG * EARTH_RADIUS
        val by = (b.latitude - a.latitude) * DEG * EARTH_RADIUS
        val px = (p.longitude - a.longitude) * cosLat * DEG * EARTH_RADIUS
        val py = (p.latitude - a.latitude) * DEG * EARTH_RADIUS
        val lengthSquared = bx * bx + by * by
        val t = if (lengthSquared == 0.0) 0.0 else max(0.0, min(1.0, (px * bx + py * by) / lengthSquared))
        val dx = px - t * bx
        val dy = py - t * by
        return Projection(sqrt(dx * dx + dy * dy), t)
    }

    data class Projection(val distance: Double, val fraction: Double)
}
