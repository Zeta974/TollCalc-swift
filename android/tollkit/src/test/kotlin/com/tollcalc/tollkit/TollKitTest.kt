package com.tollcalc.tollkit

import java.math.BigDecimal
import kotlin.math.cos
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Kotlin port of Tests/TollKitTests/TollKitTests.swift: same data, same expectations. */
class TollKitTest {
    companion object {
        val database: TollDatabase by lazy { TollDatabase.bundled() }
    }

    private val calculator get() = TollCalculator(database)

    // MARK: - Data loading

    @Test
    fun bundledNetworksLoad() {
        val byID = database.networks.associateBy { it.id }
        assertEquals(21_505, byID["aprr"]?.fareCount)
        assertEquals(815, byID["area"]?.fareCount)
        assertEquals(324, byID["aliae"]?.fareCount)
        assertEquals(11_004, byID["cofiroute"]?.fareCount)
        assertEquals(18_508, byID["asf"]?.fareCount)
        assertEquals(2_260, byID["escota"]?.fareCount)
        assertEquals("2026-06-01", byID["asf"]?.validFrom) // ASF revised its grid on 1 June 2026
        assertTrue(database.networks.filter { it.id != "asf" }.all { it.validFrom == "2026-02-01" })
    }

    // MARK: - Prices copied from the official PDFs (1 February 2026)

    @Test
    fun aprrFareAllClasses() {
        // "ALLAINES AMBERIEU 462,61 58,20 € 89,10 € 143,00 € 190,70 € 32,80 €"
        val expected = mapOf(
            VehicleClass.CLASS1 to 5820, VehicleClass.CLASS2 to 8910, VehicleClass.CLASS3 to 14300,
            VehicleClass.CLASS4 to 19070, VehicleClass.CLASS5 to 3280,
        )
        for ((vehicleClass, cents) in expected) {
            val quote = calculator.quote("ALLAINES", "AMBERIEU", vehicleClass)
            assertEquals(Money(cents), quote.total, "$vehicleClass")
            assertEquals(462_610, quote.lines.first().distanceMeters)
            assertTrue(quote.isComplete)
        }
    }

    @Test
    fun areaFareUsesCodedGrid() {
        // "3007 AIGUEBELETTE 3010 AIX NORD 24,00 3,50 € 5,50 € 7,60 €"
        val quote = calculator.quote("AIGUEBELETTE", "AIX NORD", VehicleClass.CLASS1)
        assertEquals(Money(350), quote.total)
        assertEquals("area", quote.lines.first().networkID)
        assertEquals(Money(760), calculator.quote("AIGUEBELETTE", "AIX NORD", VehicleClass.CLASS3).total)
    }

    @Test
    fun stationNamesContainingRoadNumbersParse() {
        // "3016 CRUSEILLES A 410 3400 Système Ouvert 25,00 3,20 € 4,90 € 7,40 €"
        val quote = calculator.quote("CRUSEILLES A 410", "Système Ouvert", VehicleClass.CLASS2)
        assertEquals(Money(490), quote.total)
    }

    @Test
    fun a79DeuxChaisesBarrier() {
        // "ALLAINES DEUX CHAISES 261,00 28,90 € 46,00 € 71,70 € 96,20 € 17,60 €"
        val quote = calculator.quote("ALLAINES", "DEUX CHAISES", VehicleClass.CLASS5)
        assertEquals(Money(1760), quote.total)
    }

    // MARK: - VINCI Autoroutes
    //
    // Expected values come from VINCI's own "Tarifs des principales liaisons
    // 2026" table and the guides' worked examples, which are printed
    // separately from the charts the grids are parsed from.

    private fun assertAllClasses(entry: String, exit: String, euros: List<String>, network: String) {
        for ((vehicleClass, expected) in VehicleClass.entries.zip(euros)) {
            val quote = calculator.quote(entry, exit, vehicleClass)
            assertEquals(expected, quote.total.formatted, "$entry → $exit $vehicleClass")
            assertEquals(network, quote.lines.first().networkID)
        }
    }

    @Test
    fun asfMatchesPublishedLiaisons() {
        // "A9 Montpellier / Espagne (Perthus) 23,10 € 35,30 € 50,90 € 62,50 € 13,00 €"
        assertAllClasses("Montpellier est", "Péage du Perthus",
            listOf("23,10 €", "35,30 €", "50,90 €", "62,50 €", "13,00 €"), network = "asf")
        // "A9 Montpellier / Narbonne-est 9,70 € 14,70 € 21,50 € 27,50 € 5,60 €"
        assertAllClasses("Montpellier est", "Narbonne est",
            listOf("9,70 €", "14,70 €", "21,50 €", "27,50 €", "5,60 €"), network = "asf")
        // "A10 Tours Centre (Sorigny) / Bordeaux (Virsac) 34,90 € 53,50 € 79,30 € 105,00 € 21,50 €"
        assertAllClasses("Péage de Tours centre", "Péage de Virsac",
            listOf("34,90 €", "53,50 €", "79,30 €", "105,00 €", "21,50 €"), network = "asf")
    }

    @Test
    fun escotaMatchesPublishedLiaisons() {
        // "A8 Aix / Nice 21,20 € 31,50 € 45,00 € 62,60 € 13,00 €"
        assertAllClasses("Aix (A57, A50, A52, A8)", "Nice-ouest",
            listOf("21,20 €", "31,50 €", "45,00 €", "62,60 €", "13,00 €"), network = "escota")
        // "A51 Aix / Gap (La Saulce) 14,90 € 20,60 € 28,90 € 42,00 € 8,70 €"
        assertAllClasses("Aix (A51)", "La Saulce",
            listOf("14,90 €", "20,60 €", "28,90 €", "42,00 €", "8,70 €"), network = "escota")
        // Guide example: "La Saulce > Peyruis = 5,70 €"
        assertEquals("5,70 €", calculator.quote("La Saulce", "Peyruis", VehicleClass.CLASS1).total.formatted)
    }

    @Test
    fun cofirouteRowVerbatim() {
        // "A11 1 ABLIS A28 18 ALENCON NORD 21,80 € 33,70 € 52,30 € 72,90 € 12,90 €"
        val cofiroute = assertNotNull(database.networks.firstOrNull { it.id == "cofiroute" })
        val fare = assertNotNull(cofiroute.fare(station("ABLIS"), station("ALENCON NORD")))
        assertEquals(listOf("21,80 €", "33,70 €", "52,30 €", "72,90 €", "12,90 €"),
            VehicleClass.entries.map { fare.price(it).formatted })
        assertEquals("1", fare.entry.code)
        assertNull(fare.distanceMeters)
        // ASF prints the same trip in its A11/A28 chart; both grids agree.
        assertEquals(Money(7290), calculator.quote("ABLIS", "ALENCON NORD", VehicleClass.CLASS4).total)
    }

    @Test
    fun chartsAreSymmetric() {
        for (network in database.networks.filter { it.id in setOf("asf", "escota") }) {
            for (fare in network.allFares) {
                assertEquals(fare.price(VehicleClass.CLASS1), network.fare(fare.exit, fare.entry)?.price(VehicleClass.CLASS1),
                    "${fare.entry.name} ↔ ${fare.exit.name}")
            }
        }
    }

    @Test
    fun sameNamedStationsAreKeptApart() {
        // A837 has two exits called Tonnay-Charente; a barrier is not the exit it is named after.
        assertNotNull(database.station("Tonnay-Charente (sortie 33)"))
        assertNotNull(database.station("Tonnay-Charente (sortie 34)"))
        assertNotEquals(database.station("Péage de Biriatou")?.key, database.station("Biriatou")?.key)
    }

    @Test
    fun nameLookupIgnoresAccentsCaseAndAbbreviations() {
        assertEquals("BELLEVILLE S/SAONE", database.station("Belleville-sur-Saône")?.name)
        assertEquals("BEAUNE SUD", database.station("beaune sud")?.name)
        assertEquals(listOf("BESANCON EST", "BESANCON NORD", "BESANCON OUEST"),
            database.search("besancon").map { it.name }.sorted())
    }

    // MARK: - Exactness guarantees

    @Test
    fun gridsNeverDisagreeOnSharedPairs() {
        var checked = 0
        for (network in database.networks) {
            for (fare in network.allFares) {
                for ((other, otherFare) in database.fares(fare.entry, fare.exit)) {
                    if (other.id == network.id) continue
                    checked++
                    for (vehicleClass in VehicleClass.entries) {
                        assertEquals(fare.price(vehicleClass), otherFare.price(vehicleClass),
                            "${network.id} vs ${other.id}: ${fare.entry.name} → ${fare.exit.name}")
                    }
                }
            }
        }
        assertTrue(checked > 0, "expected the APRR and ALIAE grids to overlap")
    }

    @Test
    fun unknownPairIsReportedNotEstimated() {
        // AREA-internal stations and APRR-only stations share no published ticket.
        val error = assertFailsWith<TollException.NoPublishedFare> {
            calculator.quote("AIGUEBELETTE", "ALLAINES", VehicleClass.CLASS1)
        }
        assertEquals(TollException.NoPublishedFare("AIGUEBELETTE", "ALLAINES"), error)
    }

    @Test
    fun moneyFormattingAndSums() {
        assertEquals("58,20 €", Money(5820).formatted)
        assertEquals("0,05 €", Money(5).formatted)
        assertEquals("-1,05 €", Money(-105).formatted)
        assertEquals(30, (Money(10) + Money(20)).cents)
        assertEquals(BigDecimal("58.20"), Money(5820).euros)
    }

    // MARK: - Itineraries

    @Test
    fun itineraryPrefersSinglePublishedTicket() {
        val stops = listOf("ALLAINES", "AUXERRE NORD", "AMBERIEU").map(::station)
        val quote = calculator.quote(TollItinerary(stops, VehicleClass.CLASS1))
        // ALLAINES → AMBERIEU is published as one ticket, so AUXERRE NORD is a drive-by.
        assertEquals(1, quote.lines.size)
        assertEquals(Money(5820), quote.total)
    }

    @Test
    fun itinerarySplitsWhenNoSingleTicketExists() {
        // Leave APRR at AMBERIEU, then later use the AREA network on its own.
        val stops = listOf("ALLAINES", "AMBERIEU", "AIGUEBELETTE", "AIX NORD").map(::station)
        val quote = calculator.quote(TollItinerary(stops, VehicleClass.CLASS1))
        assertEquals(listOf("AMBERIEU", "AIGUEBELETTE", "AIX NORD"), quote.lines.map { it.exit.name })
        assertFalse(quote.isComplete, "AMBERIEU → AIGUEBELETTE is not a published ticket")
        assertEquals(1, quote.unpricedLines.size)
        assertEquals(Money(5820 + 350), quote.total)
    }

    // MARK: - Route detection

    @Test
    fun detectorFindsStationsOnRouteInOrder() {
        val entry = station("ALLAINES").booths.first()
        val exit = station("AMBERIEU").booths.first()
        // A synthetic polyline that passes exactly through both stations' booths.
        val route = listOf(
            GeoPoint(entry.latitude - 0.01, entry.longitude),
            entry,
            GeoPoint((entry.latitude + exit.latitude) / 2 + 1, (entry.longitude + exit.longitude) / 2),
            exit,
            GeoPoint(exit.latitude + 0.01, exit.longitude),
        )
        val passages = RouteTollDetector(database).passages(route)
        assertEquals("ALLAINES", passages.first().station.key)
        assertEquals("AMBERIEU", passages.last().station.key)
        val quote = calculator.quote(passages.map { it.station }, VehicleClass.CLASS1)
        assertEquals(Money(5820), quote.total)
    }

    @Test
    fun detectorIgnoresStationsAwayFromRoute() {
        val booth = station("ALLAINES").booths.first()
        // Parallel line ~200 m east of the booth.
        val offset = 200 / (111_320 * cos(booth.latitude * Math.PI / 180))
        val route = listOf(
            GeoPoint(booth.latitude - 0.01, booth.longitude + offset),
            GeoPoint(booth.latitude + 0.01, booth.longitude + offset),
        )
        assertFalse(RouteTollDetector(database).passages(route).any { it.station.key == "ALLAINES" })
    }

    @Test
    fun geoDistance() {
        val paris = GeoPoint(48.8566, 2.3522)
        val lyon = GeoPoint(45.7640, 4.8357)
        assertEquals(391_500.0, Geo.distance(paris, lyon), 1_500.0)
    }

    private fun station(name: String): TollStation = assertNotNull(database.station(name), name)
}
