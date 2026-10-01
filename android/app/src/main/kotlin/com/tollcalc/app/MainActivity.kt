package com.tollcalc.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.tollcalc.tollkit.TollDatabase
import com.tollcalc.tollkit.TollQuote
import com.tollcalc.tollkit.TollStation
import com.tollcalc.tollkit.VehicleClass

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MaterialTheme {
                TollCalcScreen()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TollCalcScreen(model: TripViewModel = viewModel()) {
    var isPicking by remember { mutableStateOf(false) }

    Scaffold(topBar = { TopAppBar(title = { Text("Péage") }) }) { padding ->
        val database = model.database
        when {
            model.loadError != null -> Text(
                "Impossible de charger les tarifs : ${model.loadError}",
                Modifier.padding(padding).padding(16.dp),
            )
            database == null -> Column(
                Modifier.padding(padding).fillMaxSize(),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) { CircularProgressIndicator() }
            else -> LazyColumn(
                Modifier.padding(padding).fillMaxSize(),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                item { SectionTitle("Véhicule") }
                item { VehicleClassPicker(model.vehicleClass, model::selectVehicleClass) }

                item { SectionTitle("Gares") }
                itemsIndexed(model.stops) { index, station ->
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(stopLabel(index, model.stops.size), Modifier.weight(0.3f), fontWeight = FontWeight.Medium)
                        Text(station.name, Modifier.weight(0.6f))
                        TextButton(onClick = { model.removeStop(index) }) { Text("✕") }
                    }
                }
                item {
                    Button(onClick = { isPicking = true }) {
                        Text(if (model.stops.isEmpty()) "Choisir la gare d'entrée" else "Ajouter une gare")
                    }
                    Text(
                        "Entrée, puis sortie. Ajoutez des gares intermédiaires si vous sortez puis reprenez l'autoroute.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }

                model.quote?.let { quote -> item { QuoteSection(quote) } }

                item {
                    HorizontalDivider()
                    Text(model.networksSummary, style = MaterialTheme.typography.bodySmall)
                    Text("Positions des gares © les contributeurs d'OpenStreetMap (ODbL).",
                        style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        if (isPicking && database != null) {
            StationPicker(database, onDismiss = { isPicking = false }) {
                model.addStop(it)
                isPicking = false
            }
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(text, style = MaterialTheme.typography.titleMedium)
}

private fun stopLabel(index: Int, count: Int): String = when (index) {
    0 -> "Entrée"
    count - 1 -> "Sortie"
    else -> "Gare ${index + 1}"
}

@Composable
private fun VehicleClassPicker(selected: VehicleClass, onSelect: (VehicleClass) -> Unit) {
    Column {
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            VehicleClass.entries.forEach { vehicleClass ->
                FilterChip(
                    selected = vehicleClass == selected,
                    onClick = { onSelect(vehicleClass) },
                    label = { Text("${vehicleClass.rawValue}") },
                )
            }
        }
        Text("${selected.title} : ${selected.summary}", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun QuoteSection(quote: TollQuote) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        SectionTitle("Prix")
        quote.lines.forEach { line ->
            Row(Modifier.fillMaxWidth()) {
                Text("${line.entry.name} → ${line.exit.name}", Modifier.weight(1f))
                Text(line.price?.formatted ?: "non publié")
            }
        }
        Row(Modifier.fillMaxWidth()) {
            Text("Total", Modifier.weight(1f), fontWeight = FontWeight.Bold)
            Text(
                if (quote.isComplete) quote.total.formatted else "≥ ${quote.total.formatted}",
                fontWeight = FontWeight.Bold,
            )
        }
        if (!quote.isComplete) {
            Text(
                "Incomplet : aucun tarif officiel n'est publié pour au moins un tronçon.",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun StationPicker(database: TollDatabase, onDismiss: () -> Unit, onPick: (TollStation) -> Unit) {
    var query by remember { mutableStateOf("") }
    val results = remember(query) { database.search(query) }
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = {},
        dismissButton = { TextButton(onClick = onDismiss) { Text("Annuler") } },
        title = { Text("Gare de péage") },
        text = {
            Column {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    placeholder = { Text("Nom de la gare") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                LazyColumn {
                    items(results, key = { it.key }) { station ->
                        Text(
                            station.name,
                            Modifier.fillMaxWidth().clickable { onPick(station) }.padding(vertical = 12.dp),
                        )
                    }
                }
            }
        },
    )
}
