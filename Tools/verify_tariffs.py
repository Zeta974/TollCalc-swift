#!/usr/bin/env python3
"""Independent check that the generated JSON matches the official PDFs exactly.

build_tariffs.py parses words by position; this script instead uses the PDF's
plain-text lines, rebuilds every expected line from the JSON and requires a
one-to-one match (same number of rows, every row found verbatim).
"""
import json
import sys
from collections import Counter
from pathlib import Path

import pdfplumber

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


results = [
    check("aprr", "TARIFS_APRR.pdf", named),
    check("area", "TARIFS_INTERNES_AREA.pdf", area),
    check("aliae", "TARIFS_ALIAE-2026.pdf", named),
]
sys.exit(0 if all(results) else 1)
