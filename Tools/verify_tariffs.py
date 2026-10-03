#!/usr/bin/env python3
"""Independent checks that the generated JSON matches the official PDFs exactly.

* APRR / AREA / ALIAE: build_tariffs.py parses words by position; this script
  uses the PDF's plain-text lines, rebuilds every expected line from the JSON
  and requires a one-to-one match (same number of rows, every row verbatim).
* Cofiroute: every fare line of the guide must be in the JSON and vice versa.
* ASF: the charts are printed twice (per-class files and the tariff guide,
  with different layouts); both must parse to identical cells.

Cross-operator agreement (the same trip priced by two grids) is checked by
the Swift test suite.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "Tools" / "raw"
NETWORKS = ROOT / "Sources" / "TollKit" / "Resources" / "networks"


def eur(cents):
    return f"{cents // 100},{cents % 100:02d} €"


def km(meters):
    return f"{meters // 1000},{(meters % 1000) // 10:02d}"


def pdf_lines(path):
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                if "€" in line:
                    yield line.strip()


def check(net_id, pdf_name, render):
    doc = json.loads((NETWORKS / f"{net_id}.json").read_text())
    st = doc["stations"]
    expected = Counter()
    for f in doc["fares"]:
        for line in render(st[f[0]], st[f[1]], f):
            expected[line] += 1
    actual = Counter(pdf_lines(RAW / pdf_name))
    missing = expected - actual
    extra = actual - expected
    ok = not missing and not extra
    print(f"{net_id}: {len(doc['fares'])} fares, {sum(actual.values())} PDF price lines -> {'OK' if ok else 'MISMATCH'}")
    for line in list(missing)[:10]:
        print("  in JSON, not in PDF:", line)
    for line in list(extra)[:10]:
        print("  in PDF, not in JSON:", line)
    return ok


def named(e, x, f):
    return [f"{e['name']} {x['name']} {km(f[2])} " + " ".join(eur(c) for c in f[3:8])]


def area(e, x, f):
    # classes 1-3 and classes 4-5 are printed on separate pages
    return [
        f"{e['code']} {e['name']} {x['code']} {x['name']} {km(f[2])} " + " ".join(eur(c) for c in f[3:6]),
        " ".join(eur(c) for c in f[6:8]),
    ]


def check_cofiroute():
    """Every fare line of the Cofiroute guide must be in the JSON, and nothing else."""
    import re
    from build_tariffs import COFIROUTE_ROW, app_key
    doc = json.loads((NETWORKS / "cofiroute.json").read_text())
    st = doc["stations"]
    expected = Counter((app_key(st[f[0]]["name"]), app_key(st[f[1]]["name"]), tuple(f[3:8])) for f in doc["fares"])
    actual = Counter()
    for line in pdf_lines(RAW / "vinci" / "Cofiroute-Guide-tarifaire-2026.pdf"):
        m = COFIROUTE_ROW.match(line)
        if not m:
            if line.count("€") >= 5 and not re.match(r"^A\d+(/A\d+)* ", line):
                print("  unparsed Cofiroute line:", line)
                return False
            continue
        prices = tuple(int(p.replace(",", "")) for p in m.groups()[6:])
        actual[(app_key(m.group(3)), app_key(m.group(6)), prices)] += 1
    ok = expected == actual
    print(f"cofiroute: {len(doc['fares'])} fares, {sum(actual.values())} PDF fare lines -> {'OK' if ok else 'MISMATCH'}")
    for item in list((expected - actual) + (actual - expected))[:10]:
        print("  differs:", item)
    return ok


def check_asf_guide():
    """ASF publishes its charts twice (per-class files and the tariff guide);
    both renderings must give identical cells."""
    import vinci_charts
    from build_tariffs import app_key

    def cells(blocks):
        return {(app_key(a[0]), app_key(b[0])): v for blk in blocks for (a, b), v in blk.cells.items()}

    guide, _ = vinci_charts.parse_chart_pdf(RAW / "vinci" / "ASF-Guide-tarifaire-2026-maj062026.pdf",
                                            vinci_charts.ASF, set(range(6, 51)))
    per_class = len(guide) // 5
    ok = True
    for k in range(1, 6):
        maille, _ = vinci_charts.parse_chart_pdf(RAW / "vinci" / f"C{k}-TARIFS-WEB-2026-maille_maj062026.pdf",
                                                 vinci_charts.ASF)
        a, b = cells(maille), cells(guide[(k - 1) * per_class:k * per_class])
        same = a == b
        ok &= same
        print(f"asf class {k}: {len(a)} chart cells, guide rendering {'identical' if same else 'DIFFERENT'}")
        if not same:
            diff = [(key, a.get(key), b.get(key)) for key in a.keys() | b.keys() if a.get(key) != b.get(key)]
            print("  ", diff[:10])
    return ok


def check_journal_officiel():
    """The JO tables are parsed from the ruled table cells; here the page's
    plain text is used instead. Per network and class, the prices printed in
    the text must be exactly the prices in the JSON (as a multiset)."""
    import re
    from build_tariffs import JO_FILE, JO_TRIANGLES
    ok = True
    with pdfplumber.open(RAW / JO_FILE) as pdf:
        for annex, (net_id, _, pages) in JO_TRIANGLES.items():
            text = "\n".join(pdf.pages[p].extract_text() or "" for p in pages)
            # split by class heading ("Véhicules de classe k", or SFTRF's "Classe k Aiton …")
            parts = re.split(r"Véhicules de classe (\d)", text)
            printed = {int(parts[i]): Counter(re.findall(r"\b\d+,\d{2}\b", parts[i + 1]))
                       for i in range(1, len(parts), 2)}
            doc = json.loads((NETWORKS / f"{net_id}.json").read_text())
            names = [s["name"] for s in doc["stations"]]
            pairs = {}
            for f in doc["fares"]:
                pairs[frozenset((f[0], f[1]))] = f[3:8]
            # ATMB prints one row for both Findrol and Scientrier: their prices to
            # the eight stations before them are printed once for the two.
            shared = set()
            if net_id == "atmb":
                before = ["Chatillon", "Bellegarde", "Eloise", "Saint-Julien", "Genève", "Archamps", "Gaillard",
                          "Etrembières - Annemasse"]
                shared = {frozenset((names.index("Scientrier"), names.index(b))) for b in before}
            network_ok = True
            for k in range(1, 6):
                expected = Counter(eur(v[k - 1]).replace(" €", "") for pair, v in pairs.items() if pair not in shared)
                if expected != printed.get(k):
                    network_ok = False
                    print(f"  {net_id} class {k}: JSON {sum(expected.values())} prices, "
                          f"text {sum(printed.get(k, Counter()).values())}; differs: "
                          f"{list(((expected - printed.get(k, Counter())) + (printed.get(k, Counter()) - expected)).items())[:6]}")
            ok &= network_ok
            print(f"{net_id}: {len(pairs)} trips x 5 classes vs JO text -> {'OK' if network_ok else 'MISMATCH'}")
    return ok


def check_points():
    """Point tolls with two independent sources."""
    import re
    import points
    ok = True
    # Millau: JO annex III vs the viaduct's own 2026 leaflet
    jo = {p["when"]["season"][0][0]: p["prices"] for p in points.millau()[0]["tariff"]["periods"]}
    with pdfplumber.open(RAW / "other" / "millau-2026.pdf") as pdf:
        text = pdf.pages[-1].extract_text()
    rows = re.findall(r"^(\d+,\d{2}) € (\d+,\d{2}) €$", text, re.M)[-5:]
    leaflet_off = [points.cents(a) for a, _ in rows]
    leaflet_summer = [points.cents(b) for _, b in rows]
    same = ([jo["09-16"][k] for k in "12345"] == leaflet_off and [jo["06-15"][k] for k in "12345"] == leaflet_summer)
    ok &= same
    print(f"cevm (Millau): JO annex III vs viaduct leaflet -> {'OK' if same else 'MISMATCH'}")
    # Mont-Blanc and Fréjus: identical tariffs on the French side (bilateral agreement)
    mb = points.mont_blanc()[0]["tariff"]["periods"][0]["prices"]
    fr = points.frejus()[0]["tariff"]["periods"][0]["prices"]
    same = mb == fr
    ok &= same
    print(f"tunnels: Mont-Blanc (ATMB page) vs Fréjus (SFTRF leaflet), France side -> {'OK' if same else 'MISMATCH'}")
    ok &= check_a79()
    import duplex
    same, count = duplex.check_text()
    ok &= same
    print(f"duplex-a86: {count} prices read from the table cells vs page text, in order -> {'OK' if same else 'MISMATCH'}")
    return ok


def check_a79():
    """A79 gantries are transcribed from the ALIAE leaflet (an image). JO annex
    XII prints them as text in the same column order; from "Le Montet Est" on,
    every row must match. Its first rows (a "Deux-Chaises / Ouest" gantry, a
    different Le Montet transit) disagree with the leaflet, which Ulys confirms."""
    import re
    import points
    with pdfplumber.open(points.JO) as pdf:
        text = next(p.extract_text() for p in pdf.pages if "ANNEXE XII" in (p.extract_text() or ""))
    jo = {}
    for name, side, values in re.findall(r"^([A-Z][\w-]+(?: [A-Z][\w-]+)?) / (Ouest|Transit|Est) ((?:\d+,\d{2} € ?)+)$", text, re.M):
        jo.setdefault(f"{name} {side}", []).extend(points.cents(v) for v in re.findall(r"\d+,\d{2}", values))
    leaflet = points.a79_rows()
    agreeing = list(leaflet)[2:]
    same = all(jo.get(k) == leaflet[k] for k in agreeing)
    print(f"aliae-a79: leaflet transcription vs JO annex XII, {len(agreeing)} gantries x 14 prices -> {'OK' if same else 'MISMATCH'}")
    return same


def check_sanef():
    """Sanef/SAPN grids are read from table cells; here each class page's plain
    text must contain exactly the parsed prices (the A14 box values aside)."""
    import re
    import sanef
    ok = True
    for net_id, file_name in [("sanef", "2026_02-Grille-Sanef.pdf"), ("sapn", "2026_02-Grille-SAPN.pdf")]:
        doc = json.loads((NETWORKS / f"{net_id}.json").read_text())
        pairs = {frozenset((f[0], f[1])): f[3:8] for f in doc["fares"]}
        network_ok = True
        with pdfplumber.open(RAW / "sanef" / file_name) as pdf:
            for k in range(1, 6):
                text = pdf.pages[k].extract_text()
                text = re.sub(r"PEAGE DE MONTESSON TARIF DE BASE \S+|TARIF REDUIT \S+|PEAGE DE CHAMBOURCY \S+", "", text)
                printed = Counter(sanef.cents(v) for v in re.findall(r"(?<![\d,.])\d+,\d{1,2}(?![\d,])", text))
                expected = Counter(v[k - 1] for v in pairs.values())
                if printed != expected:
                    network_ok = False
                    print(f"  {net_id} class {k}: differs {list(((printed - expected) + (expected - printed)).items())[:8]}")
        ok &= network_ok
        print(f"{net_id}: {len(pairs)} trips x 5 classes vs page text -> {'OK' if network_ok else 'MISMATCH'}")
    # A1 modulation: every "normal" level equals the grid (checked at build time); count them here
    doc = json.loads((NETWORKS / "sanef.json").read_text())
    print(f"sanef A1 modulation: {len(doc['class1Modulations'])} trips, normal level = regular fare (checked at build)")
    return ok


def check_a355():
    import points
    slots = points.verify_a355_against_vinci()
    print(f"arcos (A355): {slots} half-hour slots of VINCI's leaflet match the JO time bands -> OK")
    return True


# Same normalised name, different places: kept apart by TollDatabase.
HOMONYMS = {"ST JULIEN"}  # ATMB Saint-Julien(-en-Genevois), SFTRF St Julien(-Mont-Denis)


def check_positions():
    """Station positions against the grids: the same name in two grids must be
    one place, and no fare may join stations further apart (straight line)
    than its tariff distance, or, without one, be under 2 cents a kilometre
    over more than 15 km. Catches a station placed at the wrong exit."""
    import math
    from build_tariffs import app_key

    def km(a, b):
        return 6371 * math.hypot(math.radians(a[0] - b[0]), math.radians(a[1] - b[1]) * math.cos(math.radians(a[0])))

    docs = {p.stem: json.loads(p.read_text()) for p in sorted(NETWORKS.glob("*.json"))}
    problems, places = [], {}
    for net, d in docs.items():
        for s in d["stations"]:
            if "lat" in s:
                places.setdefault(app_key(s["name"]), []).append((net, s["name"], (s["lat"], s["lon"])))
    for key, entries in places.items():
        far = [(a, b) for i, a in enumerate(entries) for b in entries[i + 1:] if km(a[2], b[2]) > 3]
        if far and key not in HOMONYMS:
            problems += [f"{a[0]}:{a[1]} and {b[0]}:{b[1]} are {km(a[2], b[2]):.0f} km apart" for a, b in far]
    checked = 0
    for net, d in docs.items():
        st = d["stations"]
        for e, x, dist, c1, *_ in d["fares"]:
            a, b = st[e], st[x]
            if "lat" not in a or "lat" not in b:
                continue
            checked += 1
            line = km((a["lat"], a["lon"]), (b["lat"], b["lon"]))
            if dist > 0 and line > dist / 1000 * 1.1 + 3:
                problems.append(f"{net}: {a['name']} -> {b['name']}: {line:.0f} km apart, tariff distance {dist / 1000:.0f} km")
            elif dist < 0 and c1 > 0 and line > 15 and c1 / line < 2:
                problems.append(f"{net}: {a['name']} -> {b['name']}: {c1 / 100:.2f} € for {line:.0f} km")
    for p in problems[:20]:
        print("   ", p)
    print(f"positions: {checked} located fares and every shared name vs the grids -> {'OK' if not problems else 'MISMATCH'}")
    return not problems


results = [
    check("aprr", "TARIFS_APRR.pdf", named),
    check("area", "TARIFS_INTERNES_AREA.pdf", area),
    check("aliae", "TARIFS_ALIAE-2026.pdf", named),
    check_cofiroute(),
    check_asf_guide(),
    check_journal_officiel(),
    check_a355(),
    check_points(),
    check_sanef(),
    check_positions(),
]
sys.exit(0 if all(results) else 1)
