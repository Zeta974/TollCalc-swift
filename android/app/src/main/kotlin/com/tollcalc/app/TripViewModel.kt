package com.tollcalc.app

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.tollcalc.tollkit.TollCalculator
import com.tollcalc.tollkit.TollDatabase
import com.tollcalc.tollkit.TollItinerary
import com.tollcalc.tollkit.TollQuote
import com.tollcalc.tollkit.TollStation
import com.tollcalc.tollkit.VehicleClass
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Android counterpart of the iOS `TripModel`, stations mode. */
class TripViewModel : ViewModel() {
    var database by mutableStateOf<TollDatabase?>(null)
        private set
    var loadError by mutableStateOf<String?>(null)
        private set

    var vehicleClass by mutableStateOf(VehicleClass.CLASS1)
        private set
    var stops by mutableStateOf<List<TollStation>>(emptyList())
        private set
    var quote by mutableStateOf<TollQuote?>(null)
        private set

    init {
        viewModelScope.launch {
            try {
                database = withContext(Dispatchers.Default) { TollDatabase.bundled() }
            } catch (e: Exception) {
                loadError = e.message ?: e.toString()
            }
        }
    }

    val networksSummary: String
        get() {
            val db = database ?: return ""
            val names = db.networks.joinToString(", ") { it.name }
            val validFrom = db.networks.minOfOrNull { it.validFrom } ?: ""
            return "Tarifs officiels en vigueur au $validFrom : $names."
        }

    fun selectVehicleClass(value: VehicleClass) {
        vehicleClass = value
        requote()
    }

    fun addStop(station: TollStation) {
        stops = stops + station
        requote()
    }

    fun removeStop(index: Int) {
        stops = stops.filterIndexed { i, _ -> i != index }
        requote()
    }

    private fun requote() {
        val db = database ?: return
        quote = if (stops.size >= 2) TollCalculator(db).quote(TollItinerary(stops, vehicleClass)) else null
    }
}
