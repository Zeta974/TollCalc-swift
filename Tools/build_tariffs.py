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
                rows.append((en, xn, None if ex == "-" else ex, None if xx == "-" else xx, -1, prices))
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
    stations = [{"id": f"{net_id}:{n}", "name": n, **({"code": c} if c else {})} for n, c in sorted(names.items())]
    index = {s["name"]: i for i, s in enumerate(stations)}
    locate(stations, osm, set(meta["osmOperators"]), meta.get("matchCodes", False))
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
    }
    for net_id in sys.argv[1:] or parsers:
        build(net_id, SOURCES[net_id], parsers[net_id](), osm)


if __name__ == "__main__":
    main()
