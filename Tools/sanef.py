"""Sanef and SAPN tariff grids (tarifs de péage au 1er février 2026).

Each class page holds staircase triangles drawn as ruled tables. Cells are
read with pdfplumber's table finder; station names are the words next to the
cells:
  * each row's station is written right of its last cell;
  * the first station of a section is written above the table;
  * a column belongs to the station written on the diagonal just above the
    column's top cell (checked against the label's position);
  * a few open-system exits sit in a last row with their name written left
    of their only cell ("VALLÉE DE LA HEM N°2 | 1,3").
Empty or grey cells mean the trip does not exist.
"""
import re
import sys
from pathlib import Path

import pdfplumber

RAW = Path(__file__).resolve().parent / "raw" / "sanef"
PRICE = re.compile(r"^\d+,\d{1,2}$")
WHITE = (1.0, 1.0, 1.0)


def cents(text):
    euros, dec = text.split(",")
    return int(euros) * 100 + int(dec.ljust(2, "0"))


def _words(page):
    return [w for w in page.extract_words(extra_attrs=["non_stroking_color"])
            if tuple(w["non_stroking_color"] or ()) != WHITE]  # road badges are white on blue


def _line(words):
    return " ".join(w["text"] for w in sorted(words, key=lambda w: w["x0"]))


def parse_page(page, page_no):
    words = _words(page)
    sections = []
    for table in page.find_tables():
        grid = table.extract()
        rows = table.rows
        x0, top, _, _ = table.bbox
        if len(rows) < 2 or x0 > 50:
            continue  # the A14 boxes (handled separately) and decorations; grids start at the margin
        # column left edges from all cells
        col_x = {}
        for r in rows:
            for c, cell in enumerate(r.cells):
                if cell:
                    col_x.setdefault(c, cell[0])
        # first station: the line right above the table
        header = [w for w in words if top - 12 < w["bottom"] <= top + 1 and w["x0"] < x0 + 150]
        if not header:
            sys.exit(f"page {page_no}: no section header above table at y={top:.0f}")
        stations = [{"name": _line(header), "row": -1, "x": min(w["x0"] for w in header)}]
        row_cells = []
        extra = []
        for r_index, r in enumerate(rows):
            present = [c for c, cell in enumerate(r.cells) if cell]
            cells = {c: (grid[r_index][c] or "").strip() for c in present}
            last = r.cells[present[-1]]
            y0, y1 = min(r.cells[c][1] for c in present), max(r.cells[c][3] for c in present)
            mid = (y0 + y1) / 2
            label = [w for w in words if w["x0"] >= last[2] - 1 and abs((w["top"] + w["bottom"]) / 2 - mid) < (y1 - y0) / 2]
            if label:
                stations.append({"name": _line(label), "row": len(row_cells), "x": min(w["x0"] for w in label)})
                row_cells.append(cells)
            else:
                # last row of open-system exits: names left of their single cell
                previous_right = x0 - 1
                for c in present:
                    cell = r.cells[c]
                    left = [w for w in words if previous_right <= w["x0"] and w["x1"] <= cell[0] + 1
                            and abs((w["top"] + w["bottom"]) / 2 - mid) < (y1 - y0) / 2]
                    previous_right = cell[2]
                    if cells[c].startswith("AUTOROUTE"):
                        continue  # a section banner caught by the table finder
                    if cells[c] and not left:
                        sys.exit(f"page {page_no}: unlabelled cell {cells[c]!r}")
                    if left:
                        extra.append((_line(left), c, cells[c]))
        # column c belongs to the station on the diagonal above its top cell
        top_row = {}
        for i, cells in enumerate(row_cells):
            for c in cells:
                top_row.setdefault(c, i)
        column_station = {}
        for c, first in top_row.items():
            owner = next(s for s in stations if s["row"] == first - 1)
            if abs(owner["x"] - col_x[c]) > 8:
                sys.exit(f"page {page_no}: column {c} (x={col_x[c]:.0f}) vs label {owner['name']!r} "
                         f"at x={owner['x']:.0f}")
            column_station[c] = owner["name"]
        prices = {}
        for s in stations[1:]:
            for c, text in row_cells[s["row"]].items():
                if not text:
                    continue
                if not PRICE.match(text):
                    sys.exit(f"page {page_no}: unreadable cell {text!r}")
                prices[(s["name"], column_station[c])] = cents(text)
        for name, c, text in extra:
            if text:
                prices[(name, column_station[c])] = cents(text)
        # the section's motorways, from its white banner ("AUTOROUTES A13 - A29 SUD")
        banner = [w["text"] for w in page.extract_words(extra_attrs=["non_stroking_color"])
                  if tuple(w["non_stroking_color"] or ()) == WHITE and top - 30 < w["top"] < table.bbox[3]]
        roads = sorted(set(re.findall(r"^A\d+$", " ".join(banner).replace(" ", " "), re.M)
                           + [t for t in banner if re.fullmatch(r"A\d+", t)]))
        sections.append({"stations": [s["name"] for s in stations] + [e[0] for e in extra], "prices": prices,
                         "roads": roads})
    return sections


def parse_grid(file_name):
    """Rows (entry, exit, None, None, -1, [5 prices]) for build_tariffs.build()."""
    with pdfplumber.open(RAW / file_name) as pdf:
        per_class = []
        for k in range(1, 6):
            page = pdf.pages[k]
            if f"CLASSE" not in (page.extract_text() or ""):
                sys.exit(f"{file_name} page {k}: not a class page")
            per_class.append(parse_page(page, k))
    shape = [[s["stations"] for s in sections] for sections in per_class]
    for k, sh in enumerate(shape[1:], start=2):
        if sh != shape[0]:
            sys.exit(f"{file_name}: class {k} sections differ from class 1")
    rows = []
    for i, section in enumerate(per_class[0]):
        keys = set(section["prices"])
        for k, sections in enumerate(per_class[1:], start=2):
            if set(sections[i]["prices"]) != keys:
                sys.exit(f"{file_name}: class {k} prices different trips in section {i}")
        for pair in sorted(keys):
            prices = [sections[i]["prices"][pair] for sections in per_class]
            (a, ca), (b, cb) = split_exit(pair[0]), split_exit(pair[1])
            roads = ",".join(section["roads"])
            ca = f"{roads}|{ca}" if ca and roads else ca
            cb = f"{roads}|{cb}" if cb and roads else cb
            rows.append((a, b, ca, cb, -1, prices))
            rows.append((b, a, cb, ca, -1, prices))
    return rows


def split_exit(label):
    """'BOULOGNE SUD N°28' -> ('BOULOGNE SUD', '28'); labels that name several
    exits ('CHAUFOUR N°15 à GAILLON N°17') are kept whole."""
    m = re.fullmatch(r"(.*?) N°(\S+)", label)
    if m and "N°" not in m.group(1):
        return m.group(1), m.group(2)
    return label, None


# The A1 grid's rows are these Sanef stations (exits 10, 9, 8 and the
# Chamant barrier); its columns are matched to Sanef stations by their prices.
A1_ROWS = {
    "ARSY": "COMPIÈGNE OUEST",
    "CHEVRIERES": "PONT-SAINTE-MAXENCE",
    "SENLIS": "SENLIS",
    "CHAMANT": "PARIS / ROISSY (péage de Chamant)",
}
A1_LEVELS = ["normal", "green", "red"]  # "Normal", "vert", "rouge" blocks, top to bottom


def parse_a1_modulation(grid_rows):
    """Class 1 time modulation on the A1 (grille-modulee-01022026.pdf).
    Returns [(entry, exit, {level: cents})] for trips from the northern
    stations (columns) to the four southern ones (rows). The "normal" level
    must equal the regular Sanef class 1 fare, which also identifies each
    column's station: a column is assigned to the only Sanef station whose
    regular fares to the rows equal the column's normal prices."""
    with pdfplumber.open(RAW / "grille-modulee-01022026.pdf") as pdf:
        tables = pdf.pages[0].extract_tables()
    table = max(tables, key=len)
    blocks, current = [], []
    for row in table:
        values = [v for v in row if v and PRICE.match(v)]
        if not values:
            if current:
                blocks.append(current)
                current = []
            continue
        current.append([cents(v) if v and PRICE.match(v) else None for v in row])
    if current:
        blocks.append(current)
    if len(blocks) != 3 or any(len(b) != 4 for b in blocks):
        sys.exit(f"A1 grid: expected 3 blocks of 4 rows, got {[len(b) for b in blocks]}")
    row_names = list(A1_ROWS.values())
    regular = {(a, b): p[0] for a, b, _, _, _, p in grid_rows}
    width = sum(v is not None for v in blocks[0][0])  # northern columns (row ARSY)
    stations = sorted({a for a, _ in regular})
    columns = []
    for c in range(width):
        normal = [blocks[0][r][c] for r in range(4)]
        matches = [s for s in stations if all(regular.get((s, row_names[r])) == normal[r] for r in range(4))]
        if len(matches) != 1:
            sys.exit(f"A1 grid: column {c} (normal {normal}) matches {matches}")
        columns.append(matches[0])
    # the southern stations are also columns (ARSY, CHEVRIERES, SENLIS)
    columns += row_names[:3]
    out = []
    for r in range(4):
        for c, entry in enumerate(columns):
            if blocks[0][r][c] is None or c >= len(blocks[0][r]):
                continue
            levels = {level: blocks[i][r][c] for i, level in enumerate(A1_LEVELS)}
            if None in levels.values():
                sys.exit(f"A1 grid: {entry} -> {row_names[r]} missing a level")
            if regular.get((entry, row_names[r])) != levels["normal"]:
                sys.exit(f"A1 grid: {entry} -> {row_names[r]} normal {levels['normal']} "
                         f"vs Sanef grid {regular.get((entry, row_names[r]))}")
            out.append((entry, row_names[r], levels))
    return out
