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


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"\bPEAGE (DE |D')?", "", s)
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


def load_osm():
    return json.loads(OSM.read_text())["elements"]


def locate(stations, osm, operators):
    """Attach coordinates from OSM: by operator code first, then normalized name."""
    by_ref, by_name = {}, {}
    for e in osm:
        op = (e.get("operator") or "").upper()
        if e.get("ref") and op in operators:
            by_ref.setdefault((op, e["ref"].lstrip("0")), []).append(e)
        if e.get("name"):
            by_name.setdefault(norm(e["name"]), []).append(e)
    for s in stations:
        cands = []
        if s.get("code"):
            for op in operators:
                cands = by_ref.get((op, s["code"].lstrip("0")), [])
                if cands:
                    break
        if not cands:
            cands = by_name.get(norm(ALIASES.get(s["name"], s["name"])), [])
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


def build(net_id, meta, rows, osm):
    names = {}
    codes = {}
    for en, xn, ec, xc, *_ in rows:
        names.setdefault(en, ec)
        names.setdefault(xn, xc)
    stations = [{"id": f"{net_id}:{n}", "name": n, **({"code": c} if c else {})} for n, c in sorted(names.items())]
    index = {s["name"]: i for i, s in enumerate(stations)}
    locate(stations, osm, set(meta["osmOperators"]))
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
    osm = load_osm()
    build("aprr", SOURCES["aprr"], parse_named_grid(RAW / SOURCES["aprr"]["file"], 150), osm)
    build("area", SOURCES["area"], parse_area(RAW / SOURCES["area"]["file"]), osm)
    build("aliae", SOURCES["aliae"], parse_named_grid(RAW / SOURCES["aliae"]["file"], 150), osm)


if __name__ == "__main__":
    main()
