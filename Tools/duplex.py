"""Duplex A86 (VINCI Autoroutes): Rueil - Vaucresson - Vélizy, 2026 leaflet.

Prices depend on the entry station, the direction, the half-hour of entry, the
type of day and, for trips ending at Vaucresson, on paying with a toll badge.
The leaflet draws one ruled table per trip. A price spanning several time
slots is one merged cell, so each cell's span is read from the table geometry
(pdfplumber's find_tables), and its value from the words whose centre lies in
it: clipping characters to the cell borders cuts some numbers in two.

The leaflet prints one price per slot with no vehicle class; the tunnel is
limited to light vehicles under 2 m, so the price is class 1.
"""
import re
from pathlib import Path

import pdfplumber

PDF = Path(__file__).resolve().parent / "raw" / "other" / "Tarifs-Duplex-2026.pdf"

# Day types, as the leaflet's footnotes define them:
#   *   "Tarifs applicables les veilles de jours fériés, hors mois d'août, hors
#       samedi, dimanche et jours fériés."
#   **  "Tarifs applicables le samedi (veille de jours fériés compris) sauf en
#       août, jours fériés."
#   *** "Du lundi au samedi inclus sauf jour férié." (August)
# Each is a list of band rules [days, filter]; together they cover every date once.
WEEK = ["mon", "tue", "wed", "thu"]
DAY_TYPES = {
    "monThu": [[WEEK, {"exceptMonths": [8], "holiday": False, "eveOfHoliday": False}]],
    "friOrEve": [[["fri"], {"exceptMonths": [8], "holiday": False}],
                 [WEEK, {"exceptMonths": [8], "holiday": False, "eveOfHoliday": True}]],
    "sat": [[["sat"], {"exceptMonths": [8], "holiday": False}]],
    "sunOrHoliday": [[["sun"], {}],
                     [WEEK + ["fri", "sat"], {"holiday": True}]],
    "august": [[WEEK + ["fri", "sat"], {"months": [8], "holiday": False}]],
}
ROW_DAY_TYPES = ["monThu", "friOrEve", "sat", "sunOrHoliday", "august"]  # leaflet row order

# Public holidays: the leaflet lists 2026's (1 Jan, 6 Apr, 1 May, 8 May,
# 14 May, 25 May, 14 Jul, 15 Aug, 1 Nov, 11 Nov, 25 Dec), i.e. the usual
# French list: Easter Monday, Ascension (+39) and Whit Monday (+50).
HOLIDAYS = ["01-01", "easter+1", "05-01", "05-08", "easter+39", "easter+50",
            "07-14", "08-15", "11-01", "11-11", "12-25"]
HOLIDAYS_2026 = "1er janvier, 6 avril, 1er mai, 8 mai, 14 mai, 25 mai, 14 juillet, 15 août, 1er novembre, 11 novembre, 25 décembre"

# Tables of page 2, in order: (entry, exits, has a toll badge row)
TABLES = [
    ("Rueil", ["Vélizy"], False),
    ("Rueil", ["Vaucresson"], True),
    ("Vélizy", ["Rueil"], False),
    ("Vélizy", ["Vaucresson"], True),
    ("Vaucresson", ["Rueil", "Vélizy"], False),
]

SLOT = re.compile(r"(\d+)h(\d*)")


def cents(s):
    euros, _, dec = s.partition(",")
    return int(euros) * 100 + int((dec + "0")[:2] or 0)


def _minutes(text):
    h, m = SLOT.fullmatch(text).groups()
    return int(h) * 60 + int(m or 0)


def _slots(header_cells, words):
    """[(from, to)] in minutes, to exclusive, from the header row's cells."""
    slots = []
    for bbox in header_cells:
        tokens = [w["text"] for w in _inside(words, bbox) if SLOT.fullmatch(w["text"])]
        if len(tokens) != 2:
            raise SystemExit(f"duplex: header cell {bbox} reads {tokens}")
        a, b = (_minutes(t) for t in tokens)
        slots.append((a, b if b > a else b + 24 * 60 if b else 24 * 60))
    for (_, end), (start, _) in zip(slots, slots[1:]):
        if end % (24 * 60) != start:
            raise SystemExit(f"duplex: slots do not follow each other: {slots}")
    return slots


def _inside(words, bbox):
    x0, top, x1, bottom = bbox
    return [w for w in words if x0 <= (w["x0"] + w["x1"]) / 2 <= x1 and top <= (w["top"] + w["bottom"]) / 2 <= bottom]


def parse():
    """{(entry, exit): {"cash": {dayType: [(from, to, cents)]}, "badge": {...}}}"""
    with pdfplumber.open(PDF) as pdf:
        page = pdf.pages[1]
        words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
        tables = [t for t in page.find_tables() if len(t.rows) > 2]
        text = page.extract_text()
    if len(tables) != len(TABLES):
        raise SystemExit(f"duplex: {len(tables)} price tables, expected {len(TABLES)}")
    if HOLIDAYS_2026 not in text:
        raise SystemExit("duplex: the leaflet's public holidays changed")

    trips = {}
    for table, (entry, exits, has_badge) in zip(tables, TABLES):
        header, *rows = table.rows
        first = 2 if has_badge else 1  # label column(s) before the time slots
        slot_cells = header.cells[first:]
        slots = _slots(slot_cells, words)
        centres = [((c[0] + c[2]) / 2) for c in slot_cells]
        prices = {"cash": {}, "badge": {}}
        for r, row in enumerate(rows):
            day_type = ROW_DAY_TYPES[r // 2 if has_badge else r]
            payment = "badge" if has_badge and r % 2 else "cash"
            runs = []
            for bbox in row.cells[first:]:
                if bbox is None:
                    continue
                texts = [w["text"] for w in _inside(words, bbox)]
                if len(texts) != 1 or not re.fullmatch(r"\d+(,\d)?", texts[0]):
                    raise SystemExit(f"duplex: {entry}->{exits} cell {bbox} reads {texts}")
                covered = [k for k, c in enumerate(centres) if bbox[0] <= c <= bbox[2]]
                if not covered:
                    raise SystemExit(f"duplex: cell {bbox} covers no slot")
                runs.append((slots[covered[0]][0], slots[covered[-1]][1], cents(texts[0]), covered))
            seen = [k for *_, covered in runs for k in covered]
            if seen != list(range(len(slots))):
                raise SystemExit(f"duplex: {entry}->{exits} {day_type} {payment}: slots {seen}")
            prices[payment][day_type] = [(a, b, c) for a, b, c, _ in runs]
        if not has_badge:
            del prices["badge"]
        for exit_ in exits:
            trips[(entry, exit_)] = prices
    return trips


def _band_rules(day_type, start, end):
    """Band rules for [start, end) minutes on one day type. Slots after
    midnight (22h-00h, 00h-4h30, 4h30-6h) are times of that calendar day."""
    pieces = [(start, end)] if end <= 1440 or start >= 1440 else [(start, 1440), (1440, end)]
    rules = []
    for a, b in pieces:
        a, b = a % 1440, (b - 1) % 1440 + 1
        for days, flt in DAY_TYPES[day_type]:
            rules.append([days, f"{a // 60:02d}:{a % 60:02d}", f"{(b - 1) // 60:02d}:{(b - 1) % 60:02d}", flt])
    return rules


def tariff(prices):
    """PointTariff JSON: class 1 only; badge prices for toll badge holders."""
    bands, periods = {}, []
    for payment, by_day in prices.items():
        for day_type, runs in by_day.items():
            for a, b, price in runs:
                name = f"{payment}-{day_type}-{a}"
                bands[name] = _band_rules(day_type, a, b)
                period = {"when": {"band": name}, "prices": {"1": price}}
                if payment == "badge":
                    period["subscriptions"] = ["toll-badge", "prado-tunnel-pass-plus"]
                periods.append(period)
    return {"heavyScheme": "standard", "holidays": HOLIDAYS, "bands": bands, "periods": periods}


def check_text():
    """The prices read from the cells, table by table and row by row, must be
    exactly the numbers of the page's plain text, in the same order."""
    with pdfplumber.open(PDF) as pdf:
        text = pdf.pages[1].extract_text().split("Tarifs TTC")[0].split("Tarifs 2026", 1)[1]
    printed = [cents(v) for v in re.findall(r"(?<![\d(,h])\d+(?:,\d)?(?![\d,)h])", text)]
    parsed, seen = [], []
    for prices in parse().values():
        if any(prices is p for p in seen):
            continue  # Vaucresson -> Rueil and -> Vélizy share one table
        seen.append(prices)
        for day_type in ROW_DAY_TYPES:
            for payment in prices:
                parsed += [c for _, _, c in prices[payment][day_type]]
    return printed == parsed, len(parsed)
