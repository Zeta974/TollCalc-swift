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


results = [
    check("aprr", "TARIFS_APRR.pdf", named),
    check("area", "TARIFS_INTERNES_AREA.pdf", area),
    check("aliae", "TARIFS_ALIAE-2026.pdf", named),
    check_cofiroute(),
    check_asf_guide(),
]
sys.exit(0 if all(results) else 1)
