"""Point tolls: barriers, bridges and sections priced on their own (not an
entry -> exit ticket). Data comes from the Journal officiel order of
28 January 2026 (see build_tariffs.JO_FILE) and the operators' leaflets.

JSON shape of one point (see TollKit/TollPoint.swift):
    {"id", "name", "kind", "lat", "lon", "booths",
     "tariff": {"heavyScheme": "standard" | "atlandes",
                "holidays": [...], "bands": {...},
                "periods": [{"when": null | {"season": [[from, to]]} | {"band": "A"},
                             "prices": {"1": cents, "3": {"default": cents, "euro0": cents, ...}}}]}}
"""
import re
import sys
from pathlib import Path

import pdfplumber

RAW = Path(__file__).resolve().parent / "raw"
JO = RAW / "jo" / "joe_20260130_0025_0037.pdf"
NUMBER = re.compile(r"^\d+,\d{2}$")


def cents(s):
    euros, dec = s.split(",")
    return int(euros) * 100 + int(dec)


def _jo_tables(page_no):
    with pdfplumber.open(JO) as pdf:
        return pdf.pages[page_no].extract_tables()


def _flat_table(table, expected):
    """[['Classe 1', '4,40'], ...] -> {"1": 440, ...}"""
    out = {}
    for label, value in table[1:]:
        m = re.fullmatch(r"Classe (\d)", label.strip())
        if not m or not NUMBER.match(value.strip()):
            sys.exit(f"JO: unexpected row {label!r} {value!r}")
        out[m.group(1)] = cents(value.strip())
    if sorted(out) != sorted(expected):
        sys.exit(f"JO: expected classes {expected}, got {sorted(out)}")
    return out


def _euro_table(table):
    """Header 'TARIF NON MODULÉ', 'EURO 0'.. 'EURO 7', 'GNV' -> per-row dict."""
    keys = []
    for head in table[0][1:]:
        h = " ".join(head.split()).upper()
        if "NON" in h:
            keys.append("default")
        elif h.startswith("EURO"):
            keys.append("euro" + h.split()[-1])
        elif h == "GNV":
            keys.append("gnv")
        else:
            sys.exit(f"JO: unknown column {head!r}")
    rows = {}
    for row in table[1:]:
        label = " ".join(row[0].split())
        values = [v.strip() for v in row[1:]]
        if not all(NUMBER.match(v) for v in values):
            sys.exit(f"JO: unreadable row {row}")
        rows[label] = {k: cents(v) for k, v in zip(keys, values)}
    return rows


def atlandes():
    """A63 Salles – Saint-Geours-de-Maremne, same price 'à chaque barrière'.
    Heavy vehicles use classes A, B, C (axles and gross weight) instead of 3/4."""
    flat, heavy = _jo_tables(19)
    prices = _flat_table(flat, ["1", "2", "5"])
    euro = _euro_table(heavy)
    for letter in "ABC":
        prices[letter] = euro[f"CLASSE {letter}"]
    tariff = {"heavyScheme": "atlandes", "periods": [{"when": None, "prices": prices}]}
    return [
        {"name": "Barrière de Saugnac-et-Muret", "kind": "barrier", "osm": ["Saugnac et Muret"], "tariff": tariff},
        {"name": "Barrière de Castets", "kind": "barrier", "osm": ["Castets"], "tariff": tariff},
    ]


def albea():
    """A150 Écalles-Alix – Barentin: one barrier."""
    flat, heavy = _jo_tables(20)
    prices = _flat_table(flat, ["1", "2", "5"])
    euro = _euro_table(heavy)
    prices["3"], prices["4"] = euro["CLASSE 3"], euro["CLASSE 4"]
    return [{"name": "Barrière de l'A150 (Écalles-Alix / Barentin)", "kind": "barrier",
             "booths": [[49.548203, 0.921779], [49.548080, 0.921491]],  # OSM ways 835356467/835356468
             "tariff": {"heavyScheme": "standard", "periods": [{"when": None, "prices": prices}]}}]


def millau():
    """Viaduc de Millau: summer 15/06–15/09 (leaflet), prices from JO annex III."""
    with pdfplumber.open(JO) as pdf:
        text = pdf.pages[8].extract_text()
    summer = re.search(r"Tarifs été (\S+) (\S+)\n(\S+) (\S+) (\S+) (\S+)\nTarifs hors été (\S+) (\S+)", text)
    if not summer:
        sys.exit("JO annex III: layout changed")
    s1, s2, c3, c4, c5, _convoy, h1, h2 = (cents(v) for v in summer.groups())
    both = {"3": c3, "4": c4, "5": c5}
    return [{"name": "Viaduc de Millau", "kind": "bridge",
             "booths": [[44.1342973, 3.0257623], [44.1339763, 3.0253575]],  # OSM nodes 2032423306/7
             "tariff": {"heavyScheme": "standard", "periods": [
                 {"when": {"season": [["06-15", "09-15"]]}, "prices": {"1": s1, "2": s2, **both}},
                 {"when": {"season": [["09-16", "06-14"]]}, "prices": {"1": h1, "2": h2, **both}},
             ]}}]


# A355 time bands, transcribed from the "Détail des plages horaires" table of
# JO annex XI. "sun" also covers public holidays (listed below).
MON_THU = ["mon", "tue", "wed", "thu"]
A355_BANDS = {
    "A": [(["mon", "tue", "wed", "thu", "fri", "sat", "sun"], "00:00", "04:59"), (["sun"], "05:00", "05:59"),
          (MON_THU, "19:30", "19:59"), (MON_THU + ["fri"], "20:00", "20:29"),
          (MON_THU + ["fri", "sat"], "20:30", "23:59")],
    "B": [(MON_THU, "05:00", "05:59")],
    "C": [(MON_THU, "06:00", "06:29")],
    "D": [(MON_THU, "06:30", "06:59")],
    "E": [(MON_THU, "07:00", "08:59"), (["fri"], "16:00", "16:29")],
    "F": [(MON_THU, "09:00", "15:29")],
    "G": [(MON_THU, "15:30", "15:59")],
    "H": [(MON_THU, "16:00", "16:29")],
    "I": [(MON_THU, "16:30", "17:29")],
    "J": [(MON_THU, "17:30", "18:29")],
    "K": [(MON_THU, "18:30", "18:59")],
    "L": [(MON_THU, "19:00", "19:29")],
    "M": [(["fri"], "05:00", "05:29"), (["sat"], "05:00", "05:29"), (["sun"], "21:00", "23:59")],
    "N": [(["fri"], "05:30", "06:29"), (["sat"], "05:30", "06:59"), (["sun"], "06:00", "07:29")],
    "O": [(["sat"], "07:00", "08:59")],
    "P": [(["sat"], "09:00", "14:59"), (["sun"], "09:00", "19:29")],
    "Q": [(["sat"], "15:00", "18:59")],
    "R": [(["sat"], "19:00", "20:29")],
    "S": [(["sun"], "07:30", "08:59"), (["sun"], "19:30", "20:59")],
    "T": [(["fri"], "06:30", "07:29")],
    "U": [(["fri"], "07:30", "08:59")],
    "V": [(["fri"], "09:00", "13:59")],
    "W": [(["fri"], "14:00", "15:59")],
    "X": [(["fri"], "16:30", "18:29")],
    "Y": [(["fri"], "18:30", "18:59")],
    "Z": [(["fri"], "19:00", "19:59")],
}
# "1er janvier, Vendredi Saint, Lundi de Pâques, 1er mai, 8 mai, Jeudi de
# l'Ascension, Lundi de Pentecôte, 14 juillet, 15 août, 1er novembre,
# 11 novembre, 25 décembre, 26 décembre" (easter±n = days from Easter Sunday)
A355_HOLIDAYS = ["01-01", "easter-2", "easter+1", "05-01", "05-08", "easter+39", "easter+50",
                 "07-14", "08-15", "11-01", "11-11", "12-25", "12-26"]
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def band_at(day, minute):
    found = [b for b, rules in A355_BANDS.items()
             for days, start, end in rules if day in days and _minutes(start) <= minute <= _minutes(end)]
    return found


def check_bands():
    """Every minute of every day type must fall in exactly one band."""
    for day in DAYS:
        for minute in range(24 * 60):
            found = band_at(day, minute)
            if len(found) != 1:
                sys.exit(f"A355 bands: {day} {minute // 60:02d}:{minute % 60:02d} is in {found or 'no band'}")


def _a355_sections():
    """{section: {band: {class key: cents or {euro key: cents}}}} from JO annex XI tables."""
    sections = {}
    section = bands = None
    klass = None
    with pdfplumber.open(JO) as pdf:
        tables = [t for p in range(21, 26) for t in pdf.pages[p].extract_tables()]
    for table in tables:
        if table[0][0] and table[0][0].startswith(("Intitulé", "Détail")):
            continue  # band definitions (transcribed in A355_BANDS)
        for row in table:
            cells = [(c or "").strip() for c in row]
            joined = " ".join(c for c in cells if c)
            m = re.search(r"Section (\w+) .*plages horaires ([A-Z]) à ([A-Z])", joined)
            if m:
                section = m.group(1).lower()
                continue
            if cells[2:] and all(len(c) == 1 and c.isalpha() for c in cells[2:]):
                bands = cells[2:]
                continue
            if not cells[2:] or not all(NUMBER.match(c) for c in cells[2:]):
                if joined:
                    sys.exit(f"A355: unexpected row {row}")
                continue
            if cells[0]:
                klass = re.fullmatch(r"Classe (\d)", " ".join(cells[0].split())).group(1)
            sub = " ".join(cells[1].split()).upper()
            key = None if not sub else ("default" if sub.startswith("NON") else "euro" + sub[4:])
            for band, value in zip(bands, cells[2:]):
                slot = sections.setdefault(section, {}).setdefault(band, {})
                if key is None:
                    slot[klass] = cents(value)
                else:
                    slot.setdefault(klass, {})[key] = cents(value)
    for name, by_band in sections.items():
        if sorted(by_band) != sorted(A355_BANDS):
            sys.exit(f"A355 section {name}: bands {sorted(by_band)}")
        for band, prices in by_band.items():
            if sorted(prices) != ["1", "2", "3", "4", "5"]:
                sys.exit(f"A355 section {name} band {band}: classes {sorted(prices)}")
    return sections


def _add(a, b):
    if isinstance(a, dict):
        if sorted(a) != sorted(b):
            sys.exit("A355: sections have different Euro columns")
        return {k: a[k] + b[k] for k in a}
    return a + b


def arcos():
    """A355 Strasbourg western bypass. The JO prices three sections; the
    Ittenheim barrier on the main line collects Nord + Centre, the Ittenheim
    side station one section (VINCI's leaflet, checked in verify_tariffs.py)."""
    check_bands()
    sections = _a355_sections()
    nord, centre = sections["nord"], sections["centre"]

    def tariff(by_band):
        return {"heavyScheme": "standard", "bands": {b: [[d, s, e] for d, s, e in r] for b, r in A355_BANDS.items()},
                "holidays": A355_HOLIDAYS, "holidaysAs": "sun",
                "periods": [{"when": {"band": b}, "prices": by_band[b]} for b in sorted(by_band)]}

    barrier = {b: {k: _add(nord[b][k], centre[b][k]) for k in nord[b]} for b in nord}
    if nord != centre:
        sys.exit("A355: Nord and Centre sections differ; the side station needs a direction")
    return [
        {"name": "Barrière d'Ittenheim", "kind": "barrier", "osm": ["Barrière de péage d'Ittenheim"],
         "tariff": tariff(barrier)},
        {"name": "Gare latérale d'Ittenheim", "kind": "barrier", "tariff": tariff(nord)},
    ], sections


OTHER = RAW / "other"


def _html_lines(path):
    import html as htmllib
    t = path.read_text(encoding="utf-8", errors="ignore")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    t = htmllib.unescape(re.sub(r"<[^>]+>", "\n", t))
    return [" ".join(l.split()) for l in t.splitlines() if l.strip()]


def _one_way(lines, start_marker, classes):
    """ATMB page: 'Dans le sens France – Italie :' then 'Classe N' / one-way / return."""
    i = lines.index(start_marker)
    out = {}
    while len(out) < len(classes):
        i += 1
        m = re.fullmatch(r"Classe (\d)", lines[i])
        if m and m.group(1) in classes:
            # the class's description line comes first, then one-way and return prices
            price = next(l for l in lines[i + 1:i + 4] if re.fullmatch(r"\d+,\d{2} €", l))
            out[m.group(1)] = cents(price.replace(" €", ""))
    return out


# Heavy vehicles below Euro 5 may not use the Alpine tunnels; the published
# truck prices are for "Euro 5-6" (other Euro classes are not priced).
def _euro5_plus(price):
    return {"euro5": price, "euro6": price}


def mont_blanc():
    vl = _html_lines(OTHER / "atmb-tunnel-mont-blanc-vl-2026.html")
    pl = _html_lines(OTHER / "atmb-tunnel-mont-blanc-pl-2026.html")
    points = []
    for marker, name, booths in [
        ("Dans le sens France – Italie :", "Tunnel du Mont-Blanc (France → Italie)", [[45.900965, 6.860764]]),
        ("Dans le sens Italie – France :", "Tunnel du Mont-Blanc (Italie → France)", [[45.817119, 6.951815], [45.817585, 6.953042]]),
    ]:
        prices = _one_way(vl, marker, ["1", "2", "5"])
        heavy = _one_way(pl, marker, ["3", "4"])
        prices.update({k: _euro5_plus(v) for k, v in heavy.items()})
        points.append({"name": name, "kind": "tunnel", "booths": booths,
                       "tariff": {"heavyScheme": "standard", "periods": [{"when": None, "prices": prices}]}})
    return points


def frejus():
    """SFTRF leaflet, French platform (France -> Italy), one-way ("Course simple")."""
    with pdfplumber.open(OTHER / "frejus-tunnel-2026.pdf") as pdf:
        text = pdf.pages[0].extract_text()
    prices = {}
    for klass in ["5", "1", "2"]:
        m = re.search(rf"Classe {klass}\n(\d+,\d{{2}}) ", text)
        prices[klass] = cents(m.group(1))
    for klass in ["3", "4"]:
        m = re.search(rf"Classe {klass} (\d[\d ]*,\d{{2}}) \S+ PL Euro 5-6", text)
        prices[klass] = _euro5_plus(cents(m.group(1).replace(" ", "")))
    return [{"name": "Tunnel du Fréjus (France → Italie)", "kind": "tunnel",
             "booths": [[45.194357, 6.674273], [45.194394, 6.674062]],  # OSM, SFTRF, A43
             "tariff": {"heavyScheme": "standard", "periods": [{"when": None, "prices": prices}]}}]


def maurice_lemaire():
    """APRR leaflet: péage de Lusse (tunnel Maurice-Lemaire, N159)."""
    with pdfplumber.open(OTHER / "aprr-tml-2026.pdf") as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    prices = {k: cents(v) for k, v in re.findall(r"^([1-5]) (\d+,\d{2})\s*€\s*$", text, re.M)}
    if sorted(prices) != ["1", "2", "3", "4", "5"]:
        sys.exit(f"TML leaflet: classes {sorted(prices)}")
    return [{"name": "Tunnel Maurice-Lemaire", "kind": "tunnel", "osm": ["Péage du Tunnel Maurice-Lemaire"],
             "tariff": {"heavyScheme": "standard", "periods": [{"when": None, "prices": prices}]}}]


def puymorens():
    """Arrêté du 28 janvier 2026 relatif aux péages applicables sur le réseau
    concédé à ASF et au tunnel du Puymorens (JORFTEXT000053417660). Légifrance
    refuses this build's downloads, so the five values are transcribed; classes
    1-4 were confirmed by a second source."""
    prices = {"1": 780, "2": 1610, "3": 2640, "4": 4350, "5": 460}
    return [{"name": "Tunnel du Puymorens", "kind": "tunnel",
             "booths": [[42.539594, 1.824122], [42.53959, 1.823841]],  # OSM booths at the tunnel toll plaza
             "tariff": {"heavyScheme": "standard", "periods": [{"when": None, "prices": prices}]}}]


def ponts_seine():
    """CCI Seine Estuaire page, prices from 1 May 2026 (classes 1-4 published)."""
    lines = _html_lines(OTHER / "ponts-normandie-tancarville-2026.html")
    out = []
    for bridge, booths in [("Pont de Normandie", [[49.450006, 0.271386], [49.450011, 0.271709]]),
                           ("Pont de Tancarville", [[49.463607, 0.473908], [49.463657, 0.474048]])]:
        i = max(i for i, l in enumerate(lines) if l == bridge and i + 1 < len(lines) and l.startswith("Pont")
                and lines[i + 1].startswith("Classe 1"))
        prices = {k: cents(v) for k, v in re.findall(r"Classe (\d) : (\d+,\d{2}) €", lines[i + 1])}
        if sorted(prices) != ["1", "2", "3", "4"]:
            sys.exit(f"{bridge}: classes {sorted(prices)}")
        out.append({"name": bridge, "kind": "bridge", "booths": booths,
                    "tariff": {"heavyScheme": "standard", "periods": [{"when": None, "prices": prices}]}})
    return out



def a14():
    """SAPN A14: Montesson (base / reduced rate by time) and Chambourcy.
    'Le tarif réduit est applicable du lundi au vendredi hors jours fériés de
    10h à 16h et de 21h à 6h.' Whether the 21h–6h window runs past Friday
    night and starts on Sunday night is not stated, so on Saturday and Monday
    00:00–05:59 both bands match and the quote is the range of the two."""
    with pdfplumber.open(RAW / "sanef" / "2026_02-Grille-SAPN.pdf") as pdf:
        texts = [pdf.pages[k].extract_text() for k in range(1, 6)]
    base, reduced, chambourcy = {}, {}, {}
    for k, text in enumerate(texts, start=1):
        base[str(k)] = cents(re.search(r"PEAGE DE MONTESSON TARIF DE BASE (\d+,\d{2})", text).group(1))
        reduced[str(k)] = cents(re.search(r"TARIF REDUIT (\d+,\d{2})", text).group(1))
        chambourcy[str(k)] = cents(re.search(r"PEAGE DE CHAMBOURCY (\d+,\d{2})", text).group(1))
    weekdays = ["mon", "tue", "wed", "thu", "fri"]
    bands = {
        "reduit": [[weekdays, "10:00", "15:59"], [weekdays, "21:00", "23:59"],
                   [["tue", "wed", "thu", "fri"], "00:00", "05:59"],
                   [["mon", "sat"], "00:00", "05:59"]],  # ambiguous windows
        "base": [[weekdays, "06:00", "09:59"], [weekdays, "16:00", "20:59"],
                 [["sat", "sun"], "00:00", "23:59"],
                 [["mon"], "00:00", "05:59"]],  # ambiguous window (Saturday is covered above)
    }
    national_holidays = ["01-01", "easter+1", "05-01", "05-08", "easter+39", "easter+50",
                         "07-14", "08-15", "11-01", "11-11", "12-25"]
    return [
        {"name": "Péage de Montesson", "kind": "barrier",
         "booths": [[48.9142945, 2.1510977], [48.9142182, 2.1510852]],  # OSM toll gantries, A14
         "tariff": {"heavyScheme": "standard", "bands": bands, "holidays": national_holidays, "holidaysAs": "sun",
                    "periods": [{"when": {"band": "base"}, "prices": base},
                                {"when": {"band": "reduit"}, "prices": reduced}]}},
        {"name": "Péage de Chambourcy", "kind": "barrier",
         "booths": [[48.9102342, 2.048088], [48.9118061, 2.0467239]],  # OSM toll gantries, A14
         "tariff": {"heavyScheme": "standard", "periods": [{"when": None, "prices": chambourcy}]}},
    ]

POINT_NETWORKS = {
    "cevm": ("CEVM (Viaduc de Millau)", millau),
    "atlandes": ("ATLANDES (A63 Salles – Saint-Geours-de-Maremne)", atlandes),
    "albea": ("ALBEA (A150 Écalles-Alix – Barentin)", albea),
    "arcos": ("ARCOS (A355 contournement ouest de Strasbourg)", lambda: arcos()[0]),
    "tmb": ("Tunnel du Mont-Blanc (ATMB / GEIE-TMB)", mont_blanc),
    "frejus": ("Tunnel du Fréjus (SFTRF)", frejus),
    "tml": ("Tunnel Maurice-Lemaire (APRR)", maurice_lemaire),
    "puymorens": ("Tunnel du Puymorens (ASF)", puymorens),
    "ponts-seine": ("Ponts de Normandie et de Tancarville (CCI Seine Estuaire)", ponts_seine),
    "sapn-a14": ("SAPN (A14 Montesson, Chambourcy)", a14),
}

POINT_SOURCES = {
    "cevm": ("2026-02-01", "https://www.a63-atlandes.fr/wp-content/uploads/2026/01/joe_20260130_0025_0037.pdf"),
    "atlandes": ("2026-02-01", "https://www.a63-atlandes.fr/wp-content/uploads/2026/01/joe_20260130_0025_0037.pdf"),
    "albea": ("2026-02-01", "https://www.a63-atlandes.fr/wp-content/uploads/2026/01/joe_20260130_0025_0037.pdf"),
    "arcos": ("2026-02-01", "https://www.a63-atlandes.fr/wp-content/uploads/2026/01/joe_20260130_0025_0037.pdf"),
    "tmb": ("2026-01-01", "https://www.atmb.com/telepeage-tarifs/les-tarifs-au-tunnel-du-mont-blanc-pour-les-vehicules-legers/"),
    "frejus": ("2026-01-01", "https://www.sftrf.fr/wp-content/uploads/2025/12/Tarifs_tunnel_2026_FR.pdf"),
    "tml": ("2026-02-01", "https://voyage.aprr.fr/sites/default/files/2026-02/TARIFS_TML.pdf"),
    "puymorens": ("2026-02-01", "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000053417660"),
    "ponts-seine": ("2026-05-01", "https://www.pontsnormandietancarville.fr/tarifs-de-peage/"),
    "sapn-a14": ("2026-02-01", "https://www.autoroutes.sanef.com/sites/default/files/2026-01/2026_02-Grille-SAPN.pdf"),
}


def verify_a355_against_vinci():
    """VINCI's A355 leaflet prints, per station, class and Euro group, the
    price for each half-hour slot and day type. Every slot must match the JO
    band prices (barrier = Nord + Centre, side station = one section)."""
    points_by_name = {p["name"]: p for p in arcos()[0]}
    groups = {"non modulé": ["default"], "Classe Euro 00, 01, 02, 03, 04": ["euro0", "euro1", "euro2", "euro3", "euro4"],
              "Classe Euro 05, 15, EEV": ["euro5"], "Classe Euro 06 ou plus": ["euro6"]}
    columns = ["sun", "mon", "fri", "sat"]  # "Dimanche et jours fériés", "Du lundi au jeudi", "Vendredi", "Samedi"
    checked = 0
    with pdfplumber.open(RAW / "vinci" / "A355-Guide-tarifaire-2026.pdf") as pdf:
        for page in pdf.pages[7:29]:
            lines = (page.extract_text() or "").splitlines()
            head = next(l for l in lines if l.startswith("VÉHICULES DE CLASSE"))
            m = re.match(r"VÉHICULES DE CLASSE (\d)(?: - (.*))?$", head)
            klass, group = m.group(1), m.group(2)
            station = next(l for l in lines if "Ittenheim" in l).replace("’", "'")
            prices = {p["when"]["band"]: p["prices"] for p in points_by_name[station]["tariff"]["periods"]}
            for line in lines:
                sm = re.match(r"^(\d+)h(\d*)-(\d+)h(\d*) ((?:\d+,\d{2} ?){4})$", line.strip())
                if not sm:
                    continue
                start = int(sm.group(1)) * 60 + int(sm.group(2) or 0)
                end = int(sm.group(3)) * 60 + int(sm.group(4) or 0) or 24 * 60
                values = [cents(v) for v in sm.group(5).split()]
                for day, value in zip(columns, values):
                    for minute in range(start, end):
                        (band,) = band_at(day, minute)
                        cell = prices[band][klass]
                        keys = groups[group] if group else [None]
                        for key in keys:
                            expected = cell if key is None else cell[key]
                            if expected != value:
                                sys.exit(f"A355 {station} classe {klass} {group or ''} {day} "
                                         f"{minute // 60}h{minute % 60:02d}: JO {expected} vs VINCI {value}")
                    checked += 1
    return checked
