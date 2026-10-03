"""Parser for the VINCI Autoroutes (ASF, Escota) triangular tariff charts.

Those PDFs print tariffs as charts, not tables:

* triangle blocks: the stations of one motorway section are written at 45°
  along a staircase; the cell at (row r, column c) is the price between
  station r+1 and station c;
* rectangle blocks: prices between two sections; row stations are written
  horizontally on the left, column stations at 45° above the columns.

Everything is recovered from glyph positions. Cells use the "UniversLTStd-Cn"
font; labels use Futura. White text (road badges, direction flags) is
ignored. A cell holding "." means the trip is not possible.
"""
import re
from dataclasses import dataclass, field

import pdfplumber

CELL_TOKEN = re.compile(r"^(\d+(,\d)?|\.|-+)$")  # "." or "---": trip not possible
EXIT_TEXT = re.compile(r"^\d+(\.\d+)?[a-z]?$")  # "12", "11.1", "40a"
WHITES = {(1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 0.0), (1.0,)}


@dataclass(frozen=True)
class Style:
    """Fonts of one chart family (font names without the subset prefix)."""
    cell_font: str
    label_font: str  # prefix, e.g. "Futura" matches FuturaStd-Medium
    exit_font: str | None = None  # font used only for circled exit numbers


ASF = Style(cell_font="UniversLTStd-Cn", label_font="Futura", exit_font="FuturaStd-CondensedExtraBd")
ESCOTA = Style(cell_font="VinciSans", label_font="VinciSans-")


def _font(c):
    return c["fontname"].split("+")[-1]


class ChartError(Exception):
    pass


@dataclass
class Token:
    text: str
    x: float  # centre, PDF points, y axis pointing up
    y: float


@dataclass
class Line45:
    """A line of rotated label text. `dx, dy` is the unit reading direction
    (about 45°, but some charts are slightly squashed)."""
    text: str
    x: float  # origin of the first glyph
    y: float
    dx: float
    dy: float
    is_exit: bool = False  # circled exit number printed before the name

    def q(self, x, y):
        """Offset of point (x, y) across the reading direction."""
        return x * self.dy - y * self.dx

    def s(self, x, y):
        """Position of point (x, y) along the reading direction."""
        return x * self.dx + y * self.dy


@dataclass
class Block:
    kind: str  # "triangle" | "rectangle"
    page: int
    # each row/column is a list of stations (name, exit number or None); a
    # row can stand for several stations that share the same prices
    rows: list = field(default_factory=list)
    cols: list = field(default_factory=list)
    cells: dict = field(default_factory=dict)  # (row station, col station) -> cents or None

    def fill(self, grid):
        for (r, c), text in grid.items():
            for a in self.rows[r]:
                for b in self.cols[c]:
                    self.cells[(a, b)] = cents(text)

    @property
    def stations(self):
        return list(dict.fromkeys(st for group in self.cols + self.rows for st in group))


def _is_upright(c):
    return abs(c["matrix"][1]) < 0.01 and abs(c["matrix"][2]) < 0.01


def _color(c):
    col = c.get("non_stroking_color")
    return tuple(col) if isinstance(col, (list, tuple)) else col


def _chars(page):
    """Page glyphs with overprinted duplicates (same glyph within 0.3 pt) removed."""
    seen, out = set(), []
    for c in page.chars:
        x, y = c["matrix"][4], c["matrix"][5]
        cell = (round(x / 0.3), round(y / 0.3))
        if any((c["text"], cell[0] + i, cell[1] + j) in seen for i in (-1, 0, 1) for j in (-1, 0, 1)):
            continue
        seen.add((c["text"], *cell))
        out.append(c)
    return out


def _is_white(c):
    return _color(c) in WHITES


def cell_tokens(page, style):
    chars = [c for c in _chars(page) if _is_upright(c) and _font(c) == style.cell_font and c["size"] < 7.5]
    chars.sort(key=lambda c: (-round(c["matrix"][5], 1), c["matrix"][4]))
    tokens, cur = [], None
    for c in chars:
        x, y, w = c["matrix"][4], c["matrix"][5], c["width"]
        if c["text"].strip() == "":
            cur = None
            continue
        # glyphs of one number touch or overlap (gap <= 0); neighbouring
        # cells are at least ~0.5 pt apart even for 3-digit prices
        if cur and abs(cur["y"] - y) < 0.5 and -1.0 <= x - cur["x1"] < 0.3:
            cur["text"] += c["text"]
            cur["x1"] = x + w
        else:
            cur = {"text": c["text"], "x0": x, "x1": x + w, "y": y, "size": c["size"]}
            tokens.append(cur)
    out = []
    for t in tokens:
        if not CELL_TOKEN.match(t["text"]):
            if re.fullmatch(r"[\d,.\-]+", t["text"]):
                raise ChartError(f"unreadable cell {t['text']!r} at ({t['x0']:.0f},{t['y']:.0f})")
            continue  # e.g. the "Liaison / prix" side box
        out.append(Token(t["text"], (t["x0"] + t["x1"]) / 2, t["y"] + t["size"] * 0.35))
    return out


def label_lines(page, style):
    rot = [c for c in _chars(page)
           if c["matrix"][0] > 0.01 and c["matrix"][1] > 0.01
           and not _is_white(c) and _font(c).startswith(style.label_font)]
    lines = []
    for c in rot:  # glyphs are stored in reading order
        is_exit = _font(c) == style.exit_font
        a, b = c["matrix"][0], c["matrix"][1]
        norm = (a * a + b * b) ** 0.5
        dx, dy = a / norm, b / norm
        x, y = c["matrix"][4], c["matrix"][5]
        if lines:
            ln = lines[-1]
            across = (x - ln["x"]) * ln["dy"] - (y - ln["y"]) * ln["dx"]
            along = (x - ln["ex"]) * ln["dx"] + (y - ln["ey"]) * ln["dy"]
            if abs(across) < 0.9 and -1 < along < 10 and abs(dx - ln["dx"]) < 0.02 and ln["exit"] == is_exit:
                ln["text"] += c["text"]
                ln["ex"], ln["ey"] = x, y
                continue
        lines.append({"text": c["text"], "x": x, "y": y, "ex": x, "ey": y, "dx": dx, "dy": dy, "exit": is_exit})
    return [Line45(" ".join(l["text"].split()), l["x"], l["y"], l["dx"], l["dy"],
                   l["exit"] or bool(EXIT_TEXT.match(l["text"].strip())))
            for l in lines if l["text"].strip()]


def horizontal_lines(page, style):
    """Upright label text grouped into lines (for rectangle row labels)."""
    chars = [c for c in _chars(page) if _is_upright(c) and _font(c).startswith(style.label_font) and not _is_white(c)]
    # band glyphs by baseline first, then split each band on horizontal gaps
    chars.sort(key=lambda c: -c["matrix"][5])
    bands = []
    for c in chars:
        if bands and abs(bands[-1][0]["matrix"][5] - c["matrix"][5]) < 1.0:
            bands[-1].append(c)
        else:
            bands.append([c])
    lines = []
    for band in bands:
        cur = None
        for c in sorted(band, key=lambda c: c["matrix"][4]):
            x, y = c["matrix"][4], c["matrix"][5]
            if cur and x - cur["x1"] < 6:
                cur["chars"].append(c)
                cur["x1"] = x + c["width"]
            else:
                cur = {"chars": [c], "x0": x, "x1": x + c["width"], "y": y}
                lines.append(cur)
    out = []
    for l in lines:
        text = "".join(c["text"] for c in l["chars"] if _font(c) != style.exit_font)
        exit_ = "".join(c["text"] for c in l["chars"] if _font(c) == style.exit_font).strip()
        m = re.match(r"^(\d+(?:\.\d+)?[a-z]?) ?([A-ZÀ-Ý].*)$", " ".join(text.split()))
        if m and not exit_:  # exit number in the label font, e.g. "56 Monaco" or "56Monaco"
            exit_, text = m.group(1), m.group(2)
        text = " ".join(text.split())
        if text:
            out.append({"text": text, "exit": exit_ or None, "x0": l["x0"], "x1": l["x1"], "y": l["y"] + 2})
    return out


def _cluster(values, tol):
    values = sorted(values)
    groups = [[values[0]]]
    for v in values[1:]:
        if v - groups[-1][-1] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [sum(g) / len(g) for g in groups]


def _pitch(tokens):
    by_row = {}
    for t in tokens:
        by_row.setdefault(round(t.y), []).append(t.x)
    gaps = []
    for xs in by_row.values():
        xs.sort()
        gaps += [b - a for a, b in zip(xs, xs[1:]) if b - a > 2]
    gaps.sort()
    return gaps[len(gaps) // 4]  # lower quartile: adjacent cells


def blocks_of(tokens, pitch):
    """Connected components of neighbouring cells."""
    parent = list(range(len(tokens)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    idx = sorted(range(len(tokens)), key=lambda i: tokens[i].x)
    for a_pos, a in enumerate(idx):
        for b in idx[a_pos + 1:]:
            if tokens[b].x - tokens[a].x > 1.5 * pitch:
                break
            dx, dy = abs(tokens[b].x - tokens[a].x), abs(tokens[b].y - tokens[a].y)
            if (dy < 0.35 * pitch and dx < 1.5 * pitch) or (dx < 0.45 * pitch and dy < 1.5 * pitch):
                parent[find(a)] = find(b)
    groups = {}
    for i in range(len(tokens)):
        groups.setdefault(find(i), []).append(tokens[i])
    return [g for g in groups.values() if len(g) >= 1]


def cents(text):
    if text == "." or text.startswith("-"):
        return None
    euros, _, dec = text.partition(",")
    return int(euros) * 100 + int(dec or 0) * 10


def parse_page(page, page_no, style):
    tokens = cell_tokens(page, style)
    if not tokens:
        return []
    pitch = _pitch(tokens)
    labels45 = label_lines(page, style)
    hlines = horizontal_lines(page, style)
    used = set()
    result = []
    for group in blocks_of(tokens, pitch):
        ys = sorted(_cluster([t.y for t in group], 0.3 * pitch), reverse=True)  # top row first
        xs = _cluster([t.x for t in group], 0.4 * pitch)
        grid = {}
        for t in group:
            r = min(range(len(ys)), key=lambda i: abs(ys[i] - t.y))
            c = min(range(len(xs)), key=lambda i: abs(xs[i] - t.x))
            if (r, c) in grid:
                raise ChartError(f"page {page_no}: two tokens in one cell near ({t.x:.0f},{t.y:.0f})")
            grid[(r, c)] = t.text
        n_rows, n_cols = len(ys), len(xs)
        # small inset charts can use a different cell size than the page's main chart
        diffs = sorted(b - a for a, b in zip(xs, xs[1:]))
        block_pitch = diffs[len(diffs) // 2] if diffs else pitch
        # staircase: every row holds columns 0..last, and each row is as long as
        # the previous one or one cell longer
        lasts = []
        for row in range(n_rows):
            cols_in_row = sorted(c for (r, c) in grid if r == row)
            lasts.append(cols_in_row[-1] if cols_in_row == list(range(len(cols_in_row))) else None)
        triangle = (None not in lasts and lasts[0] == 0 and lasts[-1] == n_cols - 1
                    and all(b - a in (0, 1) for a, b in zip(lasts, lasts[1:])))
        rectangle = len(grid) == n_rows * n_cols
        if len(group) == 1:
            # a lone cell with horizontal labels: column station above it, row station beside it
            t = group[0]
            beside = [h for h in hlines if abs(h["y"] - t.y) < 0.4 * pitch and 0 < h["x0"] - t.x < 3 * pitch]
            above = [h for h in hlines if 0.5 * pitch < h["y"] - t.y < 2 * pitch and abs(h["x0"] - t.x) < 3 * pitch]
            if len(beside) != 1 or len(above) != 1:
                raise ChartError(f"page {page_no}: lone cell {t.text} at ({t.x:.0f},{t.y:.0f}) has unclear labels")
            row, col = (beside[0]["text"], beside[0]["exit"]), (above[0]["text"], above[0]["exit"])
            block = Block("rectangle", page_no, rows=[[row]], cols=[[col]])
            block.fill({(0, 0): t.text})
            result.append(block)
            continue
        if triangle:
            # Labels sit on the diagonal: a row's station is labelled just right
            # of its last cell, a column's station just above its top cell.
            # In a regular triangle both coincide; a junction may own a row but
            # no column ("flat step").
            def xpos(c):
                return xs[c] if c < n_cols else xs[-1] + (c - n_cols + 1) * block_pitch

            def ypos(r):
                return ys[r] if r >= 0 else ys[0] + block_pitch

            row_slot = [(lasts[r] + 1, r) for r in range(n_rows)]
            top = [min(r for (r, c) in grid if c == col) for col in range(n_cols)]
            col_slot = [(col, top[col] - 1) for col in range(n_cols)]
            slots = sorted(set(row_slot) | set(col_slot), key=lambda cr: (cr[1], cr[0]))
            anchors = [(xpos(c), ypos(r)) for c, r in slots]
            names = dict(zip(slots, _assign45(labels45, anchors, block_pitch, used, page_no)))
            rows = [names[sl] for sl in row_slot]
            cols = [names[sl] for sl in col_slot]
            block = Block("triangle", page_no, rows=rows, cols=cols)
            block.fill(grid)
        elif rectangle:
            anchors = [(x, ys[0] + block_pitch) for x in xs]
            cols = _assign45(labels45, anchors, block_pitch, used, page_no)
            rows = []
            left, right = min(xs) - block_pitch / 2, max(xs) + block_pitch / 2
            for y in ys:
                # row labels sit either left or right of the block
                cands = [h for h in hlines if abs(h["y"] - y) < 0.4 * block_pitch and (
                    (h["x1"] < left + 1 and left - h["x1"] < 3 * block_pitch)
                    or (h["x0"] > right - 1 and h["x0"] - right < 3 * block_pitch))]
                if len(cands) != 1:
                    raise ChartError(f"page {page_no}: row label at y={y:.1f}: {[c['text'] for c in cands]}")
                rows.append([(cands[0]["text"], cands[0]["exit"])])
            block = Block("rectangle", page_no, rows=rows, cols=cols)
            block.fill(grid)
        else:
            raise ChartError(f"page {page_no}: block of {len(group)} cells is neither triangle nor rectangle "
                             f"({n_rows} rows x {n_cols} cols)")
        result.append(block)
    unused = [l.text for i, l in enumerate(labels45) if i not in used]
    return result, unused


def _assign45(lines, anchors, pitch, used, page_no):
    """Map rotated label lines to slots (one per station) and return
    [(name, exit number or None)]. A slot's label starts next to its anchor
    cell; a long label may wrap onto a second line, drawn just across the
    reading direction from the first one."""
    near = {False: [], True: []}
    for i, ln in enumerate(lines):
        if i in used:
            continue
        qs = [ln.q(x, y) for x, y in anchors]
        q = ln.q(ln.x, ln.y)
        k = min(range(len(qs)), key=lambda j: abs(q - qs[j]))
        gaps = [abs(b - a) for a, b in zip(qs, qs[1:])]
        step = min(gaps) if gaps else 2 * pitch
        start = ln.s(ln.x, ln.y) - ln.s(*anchors[k])
        if abs(q - qs[k]) < step and -2 * pitch < start < 4 * pitch:
            near[ln.is_exit].append((i, ln, q, qs, step))
    if not near[False]:
        raise ChartError(f"page {page_no}: no labels found for block")

    def place(items, bias):
        residuals = sorted(q - min(qs, key=lambda a: abs(q - a)) for _, _, q, qs, _ in items)
        offset = residuals[len(residuals) // 2]
        slots = [[] for _ in anchors]
        pending = []
        for i, ln, q, qs, step in items:
            r = [q - offset - a - bias * step for a in qs]
            k = min(range(len(qs)), key=lambda j: abs(r[j]))
            if abs(r[k]) < 0.5 * step:
                slots[k].append((q, ln.text))
                used.add(i)
            else:
                pending.append((i, ln, q, qs))
        # wrapped first lines that fell between slots: attach to the slot whose
        # label they precede
        for i, ln, q, qs in pending:
            k = min(range(len(qs)), key=lambda j: abs(q - offset - qs[j]))
            if slots[k]:
                slots[k].append((q, ln.text))
                used.add(i)
        return slots

    text_slots = place(near[False], 0.2)
    exit_slots = place(near[True], 0.0) if near[True] else [[] for _ in anchors]
    stations = []
    for k, slot in enumerate(text_slots):
        if not slot:
            raise ChartError(f"page {page_no}: no label for slot {k} of {len(text_slots)}")
        texts = [t for _, t in sorted(slot)]
        exits = [t for _, t in sorted(exit_slots[k])]
        if len(exits) <= 1:
            # one station, possibly wrapped over several lines
            stations.append([(" ".join(texts), exits[0] if exits else None)])
        elif len(exits) == len(texts):
            # several stations sharing one row, each with its own exit number
            stations.append(list(zip(texts, exits)))
        else:
            raise ChartError(f"page {page_no}: slot {k} has labels {texts} and exits {exits}")
    return stations


def parse_chart_pdf(path, style, pages=None):
    blocks, leftovers = [], []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            if pages is not None and i not in pages:
                continue
            parsed = parse_page(page, i, style)
            if not parsed:
                continue
            b, unused = parsed
            blocks += b
            leftovers += [(i, u) for u in unused]
    return blocks, leftovers
