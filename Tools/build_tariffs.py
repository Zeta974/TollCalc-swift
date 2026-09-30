#!/usr/bin/env python3
"""Build TollKit tariff resources from the operators' official PDF grids.

Usage:
    python3 -m venv .venv && .venv/bin/pip install pdfplumber
    .venv/bin/python Tools/build_tariffs.py

Inputs  : Tools/raw/*.pdf            (official grids, see SOURCES below)
          Tools/data/osm_toll_booths.json (OSM snapshot for coordinates)
Outputs : Sources/TollKit/Resources/networks/<id>.json

Every price is copied verbatim from the PDF and stored as integer euro cents,
so the app never does floating point arithmetic on money. The script aborts
if a row cannot be parsed instead of silently skipping it.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import pdfplumber

import points as point_tolls
import vinci_charts

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "Tools" / "raw"
OUT = ROOT / "Sources" / "TollKit" / "Resources" / "networks"
OSM = ROOT / "Tools" / "data" / "osm_toll_booths.json"

# Grid name -> OSM name, checked by hand (road + operator) where normalisation is not enough.
ALIASES = {
    "AMBERIEU": "Ambérieu-en-Buguey",  # sic, as tagged in OSM
    "CHALONS LA VEUVE": "Châlons-en-Champagne La Veuve",
    "CHATILLON-LABORDE": "Châtillon-la-Borde",
    "GIDY": "Saran-Gidy",
}
CROSS_NETWORK_OPERATORS = ["APRR", "AREA", "COFIROUTE", "SANEF", "ALIAE", "ALICORNE", "ASF", "ARCOUR", "ATMB"]

SOURCES = {
    **{net_id: {
        "name": name,
        "file": "jo/joe_20260130_0025_0037.pdf",
        "url": "https://www.a63-atlandes.fr/wp-content/uploads/2026/01/joe_20260130_0025_0037.pdf",
        "validFrom": "2026-02-01",
        "osmOperators": CROSS_NETWORK_OPERATORS + ["SFTRF", "ALIS", "ADELAC", "A'LIENOR", "ALICORNE", "ARCOUR"],
    } for net_id, name, _ in [
        ("atmb", "ATMB (A40, A41 nord, B41)", None), ("sftrf", "SFTRF (A43 Maurienne)", None),
        ("alis", "ALIS (A28 Rouen–Alençon)", None), ("arcour", "ARCOUR (A19 Artenay–Courtenay)", None),
        ("adelac", "ADELAC (A41 Saint-Julien–Villy-le-Pelloux)", None),
        ("alienor", "A'LIÉNOR (A65 Langon–Pau)", None), ("alicorne", "ALICORNE (A88 Falaise–Sées)", None)]},
    "aprr": {
        "name": "APRR",
        "file": "TARIFS_APRR.pdf",
        "url": "https://voyage.aprr.fr/sites/default/files/2026-02/TARIFS_APRR.pdf",
        "validFrom": "2026-02-01",
        "osmOperators": CROSS_NETWORK_OPERATORS,
    },
    "area": {
        "name": "AREA",
        "file": "TARIFS_INTERNES_AREA.pdf",
        "url": "https://voyage.aprr.fr/sites/default/files/2026-01/TARIFS_INTERNES_AREA.pdf",
        "validFrom": "2026-02-01",
        "osmOperators": ["AREA"],
        "matchCodes": True,  # AREA station codes are OSM operator:ref
    },
    "asf": {
        "name": "ASF (VINCI Autoroutes)",
        "files": {k: f"vinci/C{k}-TARIFS-WEB-2026-maille_maj062026.pdf" for k in range(1, 6)},
        "url": "https://public-content.vinci-autoroutes.com/PDF/Tarifs-peage-asf/C1-TARIFS-WEB-2026-maille_maj062026.pdf",
        "validFrom": "2026-06-01",
        "osmOperators": CROSS_NETWORK_OPERATORS + ["ESCOTA", "ATLANDES", "A'LIENOR"],
        "style": vinci_charts.ASF,
        # rectangle/row spellings -> the spelling used in the section's own triangle
        "aliases": {
            ("Orange", "21"): "Orange centre",
            ("Le Boulou (système fermé)", "43"): "Le Boulou (péage en système fermé)",
            ("La Tour de Salvagny limite de concession", None): "Tour de Salvagny limite de concession",
        },
    },
    "escota": {
        "name": "Escota (VINCI Autoroutes)",
        "files": {k: ("vinci/Escota-Guide-tarifaire-2026.pdf", 5 + k) for k in range(1, 6)},
        "url": "https://public-content.vinci-autoroutes.com/PDF/Tarifs-peage-Escota/Escota-Guide-tarifaire-2026.pdf",
        "validFrom": "2026-02-01",
        "osmOperators": ["ESCOTA", "ASF"],
        "style": vinci_charts.ESCOTA,
        "aliases": {},
    },
    "cofiroute": {
        "name": "Cofiroute (VINCI Autoroutes)",
        "file": "vinci/Cofiroute-Guide-tarifaire-2026.pdf",
        "url": "https://public-content.vinci-autoroutes.com/PDF/Tarifs-peage-Cofiroute/Cofiroute-Guide-tarifaire-2026.pdf",
        "validFrom": "2026-02-01",
        "osmOperators": CROSS_NETWORK_OPERATORS,
    },
    "aliae": {
        "name": "ALIAE (A79) - barrière de Deux-Chaises",
        "file": "TARIFS_ALIAE-2026.pdf",
        "url": "https://www.aliae.com/files/live/sites/aliae/files/Documents/TARIFS_ALIAE-2026.pdf",
        "validFrom": "2026-02-01",
        "osmOperators": CROSS_NETWORK_OPERATORS,
    },
}

PRICE = r"(\d+,\d{2}) €"
MONEY_RE = re.compile(PRICE)
NAMED_ROW = re.compile(r"^(\d+,\d{2}) " + " ".join([PRICE] * 5) + r"$")
AREA_ROW = re.compile(r"^(\d{4}) (.+?) (\d{4}) (.+) (\d+,\d{2}) " + " ".join([PRICE] * 3) + r"$")
AREA_45_ROW = re.compile(r"^" + PRICE + " " + PRICE + r"$")


def cents(s: str) -> int:
    euros, dec = s.split(",")
    return int(euros) * 100 + int(dec)


def dist_m(s: str) -> int:
    km, dec = s.split(",")
    return int(km) * 1000 + int(dec) * 10


def norm(name: str, strip_peage: bool = True) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().upper()
    if strip_peage:
        s = re.sub(r"\bPEAGE (DE |DU |DES |D'|D’)?", "", s)
    s = re.sub(r"(\bS)?/\s*", " SUR ", s)  # 'BELLEVILLE S/SAONE', 'FONTENAY /LOING'
    s = re.sub(r"\bCH\.", "CHATEAU ", s)
    s = re.sub(r"\bBARRIERE\b", "", s)
    s = s.replace("SAINTE", "STE").replace("SAINT", "ST")
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return " ".join(s.split())


def parse_named_grid(path: Path, entry_col_max_x: float):
    """APRR-style grid: 'ENTRY EXIT dist c1 c2 c3 c4 c5' with no station codes.

    Station names contain spaces, so the entry/exit split uses the x position
    of each word (entry column starts at the left margin)."""
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            # group words into lines; the '€' glyphs sit a fraction of a point higher
            lines = []
            for w in sorted(page.extract_words(), key=lambda w: w["top"]):
                if lines and abs(lines[-1][0] - w["top"]) < 2.5:
                    lines[-1][1].append(w)
                else:
                    lines.append((w["top"], [w]))
            for _, line_words in lines:
                words = sorted(line_words, key=lambda w: w["x0"])
                text = " ".join(w["text"] for w in words)
                if text.count("€") != 5:
                    continue
                entry = " ".join(w["text"] for w in words if w["x0"] < entry_col_max_x)
                rest = [w for w in words if w["x0"] >= entry_col_max_x]
                # first numeric token is the distance; everything before it is the exit name
                idx = next(i for i, w in enumerate(rest) if re.fullmatch(r"\d+,\d{2}", w["text"]))
                exit_ = " ".join(w["text"] for w in rest[:idx])
                tail = " ".join(w["text"] for w in rest[idx:])
                m = NAMED_ROW.match(tail)
                if not entry or not exit_ or not m:
                    sys.exit(f"{path.name}: unparseable row: {text!r}")
                rows.append((entry, exit_, None, None, dist_m(m.group(1)), [cents(g) for g in m.groups()[1:]]))
    return rows


def parse_area(path: Path):
    """AREA grid: classes 1-3 on the first half of the pages, classes 4-5 on
    the second half, in the same row order."""
    main, extra = [], []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                line = line.strip()
                if m := AREA_ROW.match(line):
                    main.append(m.groups())
                elif m := AREA_45_ROW.match(line):
                    extra.append(m.groups())
                elif "€" in line:
                    sys.exit(f"{path.name}: unparseable row: {line!r}")
    if len(main) != len(extra):
        sys.exit(f"{path.name}: {len(main)} class 1-3 rows vs {len(extra)} class 4-5 rows")
    rows = []
    for (ec, en, xc, xn, d, c1, c2, c3), (c4, c5) in zip(main, extra):
        rows.append((en, xn, ec, xc, dist_m(d), [cents(c) for c in (c1, c2, c3, c4, c5)]))
    return rows


COFIROUTE_ROW = re.compile(
    r"^(A\d+) (\S+) (.+?) (A\d+) (\S+) (.+) " + " ".join([PRICE] * 5) + r"$")


def parse_cofiroute(path: Path):
    """'A11 1 ABLIS A28 18 ALENCON NORD 21,80 € …' (road, exit number, name)."""
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                line = line.strip()
                if line.count("€") < 5:
                    continue
                m = COFIROUTE_ROW.match(line)
                if not m:
                    if "TARIFS DE PEAGE" in line or "/" in line and "Liaison" in line:
                        continue
                    if re.match(r"^A\d+(/A\d+)* ", line):  # "principales liaisons" summary table
                        continue
                    sys.exit(f"{path.name}: unparseable row: {line!r}")
                er, ex, en, xr, xx, xn = m.groups()[:6]
                prices = [cents(g) for g in m.groups()[6:]]
                rows.append((en, xn, None if ex == "-" else f"{er}|{ex}", None if xx == "-" else f"{xr}|{xx}",
                             -1, prices))
    return rows


def _chart_key(name):
    return re.sub(r"[^A-Z0-9]+", " ", unicodedata.normalize("NFKD", name).encode("ascii", "ignore")
                  .decode().upper()).strip()


def parse_charts(net_id, meta):
    """ASF / Escota charts: one PDF (or page) per vehicle class."""
    per_class = []
    for k in range(1, 6):
        spec = meta["files"][k]
        path, pages = (spec, None) if isinstance(spec, str) else (spec[0], {spec[1]})
        blocks, unused = vinci_charts.parse_chart_pdf(RAW / path, meta["style"], pages)
        if unused:
            sys.exit(f"{net_id} class {k}: labels not attached to any chart: {unused}")
        per_class.append(blocks)

    aliases = meta["aliases"]

    def canonical(station):
        name, exit_ = station
        return aliases.get((name, exit_), name), exit_

    # every class must print the same charts with the same stations
    def shape(blocks):
        # exit numbers are occasionally missing from one class's labels, so compare names only
        return [(b.kind, [[_chart_key(canonical(st)[0]) for st in group] for group in b.rows + b.cols])
                for b in blocks]
    for k, blocks in enumerate(per_class[1:], start=2):
        if shape(blocks) != shape(per_class[0]):
            sys.exit(f"{net_id}: class {k} charts differ from class 1")

    # names printed with different exit numbers are different stations
    # (e.g. Tonnay-Charente, exits 33 and 34): suffix them with the exit
    exits_by_key = {}
    for blocks in per_class:
        for b in blocks:
            for st in b.stations:
                name, exit_ = canonical(st)
                exits_by_key.setdefault(_chart_key(name), set()).add(exit_)
    ambiguous = {key for key, exits in exits_by_key.items() if len(exits - {None}) > 1}
    for key in ambiguous:
        if None in exits_by_key[key]:
            sys.exit(f"{net_id}: '{key}' is printed without exit number but has several")
    only_exit = {key: next(iter(exits - {None})) for key, exits in exits_by_key.items() if len(exits - {None}) == 1}

    spelling = {}

    def display(station):
        name, exit_ = canonical(station)
        key = _chart_key(name)
        exit_ = exit_ or only_exit.get(key)
        if key in ambiguous:
            key = f"{key} {exit_}"
            name = f"{name} (sortie {exit_})"
        # keep one spelling per station, preferring accented forms
        best = spelling.setdefault(key, name)
        if sum(ord(ch) > 127 for ch in name) > sum(ord(ch) > 127 for ch in best):
            spelling[key] = name
        return key, exit_

    cells = {}
    for k, blocks in enumerate(per_class):
        for b in blocks:
            for (a, c), price in b.cells.items():
                pair = (display(a), display(c))
                if pair[0][0] == pair[1][0]:
                    continue  # same station
                seen = cells.setdefault(pair, [[] for _ in range(5)])
                seen[k].append((price, b.page))
    rows, conflicts = [], []
    for ((ka, ea), (kc, ec)), seen in cells.items():
        # a pair printed in several charts must read the same everywhere
        bad = [k for k, values in enumerate(seen) if len({v for v, _ in values}) > 1]
        if bad and all({v for v, _ in seen[k]} <= {0, None} for k in bad):
            # free ring-road links shown as 0 € in one chart and "." in another:
            # leave them out rather than pick one reading
            print(f"  {net_id}: skipping {ka} - {kc} (0 € in one chart, not possible in another)")
            continue
        if bad:
            conflicts.append(f"{ka} - {kc}: " + "; ".join(
                f"class {k + 1} {sorted(set(seen[k]), key=str)}" for k in bad))
            continue
        prices = [values[0][0] if values else None for values in seen]
        if all(p is None for p in prices):
            continue  # "." / "---": trip not possible
        if any(p is None for p in prices):
            sys.exit(f"{net_id}: {ka} - {kc} priced for some classes only: {prices}")
        a, c = spelling[ka], spelling[kc]
        # charts are symmetric: the same price applies in both directions
        rows.append((a, c, ea, ec, -1, prices))
        rows.append((c, a, ec, ea, -1, prices))
    if conflicts:
        sys.exit(f"{net_id}: {len(conflicts)} pairs printed differently in two charts:\n  " + "\n  ".join(conflicts))
    return rows


JO_FILE = "jo/joe_20260130_0025_0037.pdf"
JO_URL = "https://www.a63-atlandes.fr/wp-content/uploads/2026/01/joe_20260130_0025_0037.pdf"
# Journal officiel du 30 janvier 2026, arrêté du 28 janvier 2026 (NOR TRAT2534086A):
# annex -> (network id, display name, pages holding its five class tables)
JO_TRIANGLES = {
    "I": ("atmb", "ATMB (A40, A41 nord, B41)", [3, 4, 5]),
    "II": ("sftrf", "SFTRF (A43 Maurienne)", [6, 7]),
    "IV": ("alis", "ALIS (A28 Rouen–Alençon)", [9, 10]),
    "V": ("arcour", "ARCOUR (A19 Artenay–Courtenay)", [11, 12]),
    "VI": ("adelac", "ADELAC (A41 Saint-Julien–Villy-le-Pelloux)", [13]),
    "VII": ("alienor", "A'LIÉNOR (A65 Langon–Pau)", [14, 15, 16]),
    "VIII": ("alicorne", "ALICORNE (A88 Falaise–Sées)", [17, 18]),
}
NUMBER = re.compile(r"^\d+,\d{2}$")
NO_TRIP = {"", "-", "x", "X"}


def _jo_label(cell):
    """'Mont-\nde-Marsan' -> 'Mont-de-Marsan', 'Savigny\nsur Claris' -> 'Savigny sur Claris'."""
    out = ""
    for part in cell.split("\n"):
        part = part.strip()
        out += part if out.endswith("-") or not out else " " + part
    return out


def parse_jo_triangle(pages):
    """Lower-triangle tables: row k holds the prices from station k to the
    stations of columns 0..k-1, then the station's own name on the diagonal.
    A row may hold two names (two stations sharing that row's prices, e.g.
    ATMB 'Findrol' / 'Scientrier'); blank, '-' and 'x' cells mean no trip."""
    tables, first_names = [], []
    with pdfplumber.open(RAW / JO_FILE) as pdf:
        for page_no in pages:
            page = pdf.pages[page_no]
            lines = (page.extract_text() or "").splitlines()
            heads = [i for i, l in enumerate(lines) if l.startswith("Véhicules de classe")]
            page_tables = page.extract_tables()
            if len(page_tables) != len(heads):
                sys.exit(f"JO page {page_no}: {len(page_tables)} tables for {len(heads)} class headings")
            tables += page_tables
            first_names += [lines[i + 1].strip() for i in heads]
    if len(tables) != 5:
        sys.exit(f"JO pages {pages}: expected 5 class tables, found {len(tables)}")

    per_class = []
    for table, first in zip(tables, first_names):
        stations, cells = [], {}
        for row in table:
            row = [(c or "").strip() for c in row]
            labels = [(i, _jo_label(c)) for i, c in enumerate(row) if c and not NUMBER.match(c) and c not in NO_TRIP]
            if not labels:
                if not stations and not any(row):
                    stations.append(first)  # header row whose name sits outside the ruled cell
                continue
            if row[0] == "" and not stations and labels[0][0] > 0:
                stations.append(first)
            first_label = labels[0][0]
            if first_label != len(stations):
                # the first station's name can be printed above the table
                if not stations and first_label == 1:
                    stations.append(first)
                else:
                    sys.exit(f"JO pages {pages}: label {labels[0][1]!r} in column {first_label}, "
                             f"expected column {len(stations)}")
            for offset, (col, name) in enumerate(labels):
                if col != first_label + offset:
                    sys.exit(f"JO pages {pages}: labels of one row are not adjacent: {labels}")
            for _, name in labels:
                for col in range(first_label):
                    value = row[col]
                    if NUMBER.match(value):
                        cells[(name, stations[col])] = cents(value)
                    elif value not in NO_TRIP:
                        sys.exit(f"JO pages {pages}: unreadable cell {value!r}")
            stations += [name for _, name in labels]
        per_class.append((stations, cells))

    names = per_class[0][0]
    for k, (stations, _) in enumerate(per_class[1:], start=2):
        if stations != names:
            sys.exit(f"JO pages {pages}: class {k} stations differ: {stations} vs {names}")
    rows = []
    for pair in per_class[0][1]:
        prices = [cells.get(pair) for _, cells in per_class]
        if None in prices:
            sys.exit(f"JO pages {pages}: {pair} missing for some classes: {prices}")
        a, b = pair
        rows.append((a, b, None, None, -1, prices))
        rows.append((b, a, None, None, -1, prices))
    for _, cells in per_class[1:]:
        if set(cells) != set(per_class[0][1]):
            sys.exit(f"JO pages {pages}: classes do not price the same trips")
    return rows


def parse_jo_matrix(pages):
    """SFTRF: upper triangle with a header row of station names."""
    per_class = []
    with pdfplumber.open(RAW / JO_FILE) as pdf:
        for page_no in pages:
            per_class += pdf.pages[page_no].extract_tables()
    if len(per_class) != 5:
        sys.exit(f"JO pages {pages}: expected 5 class tables, found {len(per_class)}")
    results = []
    for k, table in enumerate(per_class, start=1):
        header = [(c or "").strip() for c in table[0]]
        if header[0] != f"Classe {k}":
            sys.exit(f"JO pages {pages}: table {k} starts with {header[0]!r}")
        cols = header[1:]
        cells = {}
        for row in table[1:]:
            row = [(c or "").strip() for c in row]
            entry = row[0]
            for j, value in enumerate(row[1:]):
                if NUMBER.match(value):
                    cells[(entry, cols[j])] = cents(value)
                elif value not in NO_TRIP:
                    sys.exit(f"JO pages {pages}: unreadable cell {value!r}")
        results.append(cells)
    rows = []
    for pair in results[0]:
        prices = [cells.get(pair) for cells in results]
        if None in prices or any(set(c) != set(results[0]) for c in results):
            sys.exit(f"JO pages {pages}: classes do not price the same trips")
        a, b = pair
        rows.append((a, b, None, None, -1, prices))
        rows.append((b, a, None, None, -1, prices))
    return rows


def load_osm():
    return json.loads(OSM.read_text())["elements"]


def locate(stations, osm, operators, match_codes=False):
    """Attach coordinates from OSM: by operator code (AREA only), then by name.

    Names are compared with "Péage de" kept first, so a barrier and the exit
    it is named after ("Péage de Biriatou" / "Biriatou") are not merged; the
    loose comparison is only used when it is unambiguous within the grid."""
    by_ref, by_exact, by_loose = {}, {}, {}
    for e in osm:
        op = (e.get("operator") or "").upper()
        if e.get("ref") and op in operators:
            by_ref.setdefault((op, e["ref"].lstrip("0")), []).append(e)
        if e.get("name"):
            by_exact.setdefault(norm(e["name"], strip_peage=False), []).append(e)
            by_loose.setdefault(norm(e["name"]), []).append(e)
    loose_count = {}
    for s in stations:
        loose_count[norm(s["name"])] = loose_count.get(norm(s["name"]), 0) + 1
    for s in stations:
        cands = []
        if match_codes and s.get("code"):
            for op in operators:
                cands = by_ref.get((op, s["code"].lstrip("0")), [])
                if cands:
                    break
        name = ALIASES.get(s["name"], s["name"])
        if not cands:
            cands = by_exact.get(norm(name, strip_peage=False), [])
        if not cands and loose_count[norm(s["name"])] == 1:
            cands = by_loose.get(norm(name), [])
        # only trust booths from the expected operators (or untagged ones)
        cands = [c for c in cands if (c.get("operator") or "").upper() in operators | {""}]
        if not cands:
            continue
        # booths of one station are within a few hundred metres; reject ambiguous matches
        lats = [c["lat"] for c in cands]
        lons = [c["lon"] for c in cands]
        if max(lats) - min(lats) > 0.02 or max(lons) - min(lons) > 0.03:
            continue
        s["lat"] = round(sum(lats) / len(lats), 6)
        s["lon"] = round(sum(lons) / len(lons), 6)
        s["booths"] = [[c["lat"], c["lon"]] for c in cands]


def app_key(name: str) -> str:
    """Same normalisation as StationName.key in TollKit."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"(\bS)?/\s*", " SUR ", s)
    s = re.sub(r"\bCH\.", "CHATEAU ", s)
    s = s.replace("SAINTE", "STE").replace("SAINT", "ST")
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", s).split())


JUNCTIONS = ROOT / "Tools" / "data" / "osm_motorway_junctions.json"
# Grid entries that are not a place you can enter or leave the motorway:
# concession limits, motorway forks, the open-system marker, the border.
VIRTUAL = re.compile(r"limite de concession|LIM\.? ?CONC|bifurcation|syst[eè]me ouvert|fronti[eè]re", re.I)
_junctions = None


def _km(a, b):
    import math
    dlat = math.radians(b[0] - a[0])
    dlon = math.radians(b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2))
    return 6371 * math.hypot(dlat, dlon)


def _clusters(nodes, radius_km=3):
    """Group junction nodes of one interchange (both carriageways, all ramps)."""
    groups = []
    for n in nodes:
        for g in groups:
            if any(_km((n["lat"], n["lon"]), (m["lat"], m["lon"])) < radius_km for m in g):
                g.append(n)
                break
        else:
            groups.append([n])
    return groups


def _ref_key(ref):
    return re.sub(r"[\s.\-]+", ".", ref.strip().lower())


# Stations placed by hand, checked against exit numbers, positions and the
# order of stations along the road. Values are OSM junction node ids ("n…")
# from Tools/data/osm_motorway_junctions.json, or booth names from
# Tools/data/osm_toll_booths.json ("booth:…"), or an explicit [lat, lon].
MANUAL_PINS = {
    "atmb": {
        "Saint-Julien": ["n11264369966"],  # A40 exit 13 Saint-Julien-en-Genevois
        "Etrembières - Annemasse": ["n1110757713", "n7043179811"],  # A40 exit 14 Annemasse
        "Origine": [[45.900965, 6.860764]],  # Mont-Blanc tunnel toll plaza (French side)
    },
    "sftrf": {  # A43 exits in Maurienne
        "St Pierre": ["n2188188165", "n612573928"],  # exit 25 Saint-Pierre-de-Belleville
        "Ste Marie": ["n21032841", "n60294409"],  # exit 26 Sainte-Marie-de-Cuines
        "St Jean": ["n2185654628"],  # exit 27 Saint-Jean-de-Maurienne
        "St Julien": ["n267165935"],  # exit 28 Saint-Julien-Mont-Denis
        "Modane": ["n1139898026", "n279888636"],  # exit 30 Modane
    },
    "alis": {
        "Alençon": ["booth:Alençon Nord"],
        "Broglie": ["booth:Broglie-Orbec"],
        "A13": ["n248867577"],  # A28/A13 junction
    },
    "arcour": {
        "Savigny sur Claris": ["booth:Savigny-sur-Clairis"],
        "Gondreville la Franche": ["n1808309613", "n457361469"],  # A19/A77 junction
        "Piffonds": ["n456719874", "n97733462"],  # A19/A6 junction near Courtenay
        "Chevilly": ["n456737416"],  # A19/A10 junction near Artenay
    },
    "alienor": {
        "Aire-sur-l'Adour centre": ["booth:Aire-sur-l'Adour Nord"],
        "Langon (A62)": ["n648626013", "n648626111"],  # A62/A65 junction
        "Pau (A64)": ["n1921056977"],  # A65/A64 junction
    },
    "alicorne": {  # A88 exits 11 to 15
        "Falaise Ouest": ["n712698030", "n27784198"],
        "Falaise sud": ["n987821573"],
        "Argentan sud": ["n270426632"],
        "Mortrée": ["n1014077869", "n229546977"],
    },
}


def apply_pins(net_id, stations, osm):
    pins = MANUAL_PINS.get(net_id, {})
    if not pins:
        return
    junctions = {j["osm"]: j for j in json.loads(JUNCTIONS.read_text())["elements"]}
    booths = {}
    for e in osm:
        if e.get("name"):
            booths.setdefault(e["name"], []).append(e)
    by_name = {s["name"]: s for s in stations}
    for name, refs in pins.items():
        s = by_name.get(name)
        if s is None:
            sys.exit(f"{net_id}: pinned station {name!r} is not in the grid")
        points, kind = [], "junctions"
        for ref in refs:
            if isinstance(ref, list):
                points.append(ref)
            elif ref.startswith("booth:"):
                found = booths.get(ref[6:], [])
                if not found:
                    sys.exit(f"{net_id}: no OSM booth named {ref[6:]!r}")
                points += [[e["lat"], e["lon"]] for e in found]
                kind = "booths"
            else:
                points.append([junctions[ref]["lat"], junctions[ref]["lon"]])
        s[kind] = points
        s["lat"] = round(sum(p[0] for p in points) / len(points), 6)
        s["lon"] = round(sum(p[1] for p in points) / len(points), 6)


def locate_junctions(net_id, stations):
    """Place stations that have no toll booth in OSM at their interchange
    (highway=motorway_junction nodes of both carriageways):
      1. road + exit number (grids that print the road, e.g. Cofiroute),
      2. exact name, if it resolves to a single interchange near the network,
      3. exit number alone, if a single interchange with that number lies
         within 20 km of an already located station of the same grid
         (repeated until nothing changes).
    Anything ambiguous stays unlocated."""
    global _junctions
    if _junctions is None:
        _junctions = json.loads(JUNCTIONS.read_text())["elements"]
    by_name, by_road_ref, by_ref = {}, {}, {}
    for j in _junctions:
        if j.get("name"):
            by_name.setdefault(norm(j["name"]), []).append(j)
        if j.get("ref"):
            by_ref.setdefault(_ref_key(j["ref"]), []).append(j)
            for road in j.get("roads", []):
                by_road_ref.setdefault((road, _ref_key(j["ref"])), []).append(j)

    def located():
        return [(s["lat"], s["lon"]) for s in stations if "lat" in s]

    def near_network(cluster, radius):
        anchors = located()
        c = cluster[0]
        return not anchors or min(_km((c["lat"], c["lon"]), a) for a in anchors) < radius

    used = set()

    def place(s, cluster, how):
        used.update(j["osm"] for j in cluster)
        s["junctions"] = [[j["lat"], j["lon"]] for j in cluster]
        s["lat"] = round(sum(j["lat"] for j in cluster) / len(cluster), 6)
        s["lon"] = round(sum(j["lon"] for j in cluster) / len(cluster), 6)
        counts[how] += 1

    counts = {"road+exit": 0, "name": 0, "exit near grid": 0}
    todo = []
    for s in stations:
        if VIRTUAL.search(s["name"]):
            s["virtual"] = True
        elif "lat" not in s:
            todo.append(s)
    for s in list(todo):
        if s.get("road") and s.get("code"):
            groups = _clusters(by_road_ref.get((s["road"].replace(" ", ""), _ref_key(s["code"])), []))
            if len(groups) == 1:
                place(s, groups[0], "road+exit")
                todo.remove(s)
    def bare(name):
        return norm(re.sub(r"\s*\(sortie [^)]*\)", "", name), strip_peage=False)

    repeated = {n for n in (bare(s["name"]) for s in stations) if sum(bare(t["name"]) == n for t in stations) > 1}
    for s in list(todo):
        # A barrier ("Péage de X") is on the main road, not at exit X; and
        # names shared by several stations can only be told apart by exit number.
        if re.match(r"p[ée]age\b", s["name"], re.I) or bare(s["name"]) in repeated:
            continue
        groups = [g for g in _clusters(by_name.get(bare(s["name"]), []))
                  if near_network(g, 150) and not used & {j["osm"] for j in g}]
        if len(groups) == 1:
            place(s, groups[0], "name")
            todo.remove(s)
    changed = True
    while changed:
        changed = False
        for s in list(todo):
            if not s.get("code"):
                continue
            groups = [g for g in _clusters(by_ref.get(_ref_key(s["code"]), []))
                      if located() and near_network(g, 20) and not used & {j["osm"] for j in g}]
            if len(groups) == 1:
                place(s, groups[0], "exit near grid")
                todo.remove(s)
                changed = True
    if any(counts.values()):
        print(f"  {net_id}: placed at interchanges by " + ", ".join(f"{k} {v}" for k, v in counts.items() if v))


def build(net_id, meta, rows, osm):
    # one spelling per station ("VILLEFRANCHE NORD" / "VILLEFRANCHE-NORD")
    spelling = {}
    for en, xn, *_ in rows:
        spelling.setdefault(app_key(en), en)
        spelling.setdefault(app_key(xn), xn)
    rows = [(spelling[app_key(en)], spelling[app_key(xn)], *rest) for en, xn, *rest in rows]
    names = {}
    codes = {}
    for en, xn, ec, xc, *_ in rows:
        names.setdefault(en, ec)
        names.setdefault(xn, xc)
    stations = []
    for n, c in sorted(names.items()):
        station = {"id": f"{net_id}:{n}", "name": n}
        if c:
            road, _, code = c.rpartition("|")
            station["code"] = code
            if road:
                station["road"] = road
        stations.append(station)
    index = {s["name"]: i for i, s in enumerate(stations)}
    locate(stations, osm, set(meta["osmOperators"]), meta.get("matchCodes", False))
    apply_pins(net_id, stations, osm)
    locate_junctions(net_id, stations)
    fares, seen = [], {}
    for en, xn, _, _, d, prices in rows:
        key = (index[en], index[xn])
        if key in seen:
            if seen[key] != (d, prices):
                sys.exit(f"{net_id}: conflicting duplicate fare {en} -> {xn}")
            continue
        seen[key] = (d, prices)
        fares.append([key[0], key[1], d, *prices])
    located = sum(1 for s in stations if "lat" in s)
    for s in stations:
        s.pop("road", None)
    doc = {
        "id": net_id,
        "name": meta["name"],
        "validFrom": meta["validFrom"],
        "source": meta["url"],
        "currency": "EUR",
        "fareColumns": ["entry", "exit", "distanceMeters", "class1", "class2", "class3", "class4", "class5"],
        "stations": stations,
        "fares": fares,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{net_id}.json", "w") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{net_id}: {len(stations)} stations ({located} located), {len(fares)} fares")



def build_points(net_id, osm):
    """Networks made of point tolls only (barriers, bridges)."""
    name, make = point_tolls.POINT_NETWORKS[net_id]
    by_name = {}
    for e in osm:
        if e.get("name"):
            by_name.setdefault(e["name"], []).append(e)
    out = []
    for p in make():
        booths = p.get("booths") or [[e["lat"], e["lon"]] for n in p.get("osm", []) for e in by_name.get(n, [])]
        point = {"id": f"{net_id}:{p['name']}", "name": p["name"], "kind": p["kind"], "tariff": p["tariff"]}
        if booths:
            point["lat"] = round(sum(b[0] for b in booths) / len(booths), 6)
            point["lon"] = round(sum(b[1] for b in booths) / len(booths), 6)
            point["booths"] = booths
        out.append(point)
    valid_from, source = point_tolls.POINT_SOURCES[net_id]
    doc = {"id": net_id, "name": name, "validFrom": valid_from, "source": source, "currency": "EUR",
           "fareColumns": ["entry", "exit", "distanceMeters", "class1", "class2", "class3", "class4", "class5"],
           "stations": [], "fares": [], "points": out}
    with open(OUT / f"{net_id}.json", "w") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{net_id}: {len(out)} toll points ({sum('booths' in p for p in out)} located)")

def main():
    """Build every grid, or only the ids given on the command line."""
    osm = load_osm()
    parsers = {
        "aprr": lambda: parse_named_grid(RAW / SOURCES["aprr"]["file"], 150),
        "area": lambda: parse_area(RAW / SOURCES["area"]["file"]),
        "aliae": lambda: parse_named_grid(RAW / SOURCES["aliae"]["file"], 150),
        "cofiroute": lambda: parse_cofiroute(RAW / SOURCES["cofiroute"]["file"]),
        "asf": lambda: parse_charts("asf", SOURCES["asf"]),
        "escota": lambda: parse_charts("escota", SOURCES["escota"]),
        "sftrf": lambda: parse_jo_matrix([6, 7]),
        **{net_id: (lambda pages=pages: parse_jo_triangle(pages))
           for annex, (net_id, _, pages) in JO_TRIANGLES.items() if net_id != "sftrf"},
    }
    for net_id in sys.argv[1:] or [*parsers, *point_tolls.POINT_NETWORKS]:
        if net_id in point_tolls.POINT_NETWORKS:
            build_points(net_id, osm)
        else:
            build(net_id, SOURCES[net_id], parsers[net_id](), osm)


if __name__ == "__main__":
    main()
