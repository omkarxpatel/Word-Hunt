"""Board geometry: finding the 4x4 grid among OCR'd letters, or building it from a two-corner calibration.

Pure math with no macOS calls, so it is unit-tested without the phone.
"""

from collections import Counter
from itertools import combinations
from statistics import median
from typing import NamedTuple

SIZE = 4


class Box(NamedTuple):
    """Something Vision found on screen: a letter (char set) or a tile-shaped rectangle (char empty)."""
    char: str
    x: float  # centre
    y: float
    h: float  # height


class Grid(NamedTuple):
    x0: float  # centre of the top-left tile
    y0: float
    dx: float  # distance between neighbouring tile centres
    dy: float

    def centre(self, index):
        row, col = divmod(index, SIZE)
        return self.x0 + col * self.dx, self.y0 + row * self.dy

    def centres(self):
        return [self.centre(i) for i in range(SIZE * SIZE)]

    def scaled(self, sx, sy):
        return Grid(self.x0 * sx, self.y0 * sy, self.dx * sx, self.dy * sy)

    def moved(self, ox, oy):
        return Grid(self.x0 + ox, self.y0 + oy, self.dx, self.dy)


def from_corners(top_left, bottom_right):
    """The grid through the centres of the top-left and bottom-right tiles."""
    (x1, y1), (x2, y2) = top_left, bottom_right
    return Grid(x1, y1, (x2 - x1) / (SIZE - 1), (y2 - y1) / (SIZE - 1))


def fit(boxes, min_hits=6):
    """Find the board: the 4x4 lattice that lines up the most same-sized boxes (tiles or letters).

    Returns a Grid, or None when nothing on screen looks like a board.
    """
    if len(boxes) < min_hits:
        return None

    # Tiles (or board letters) share one size; the score, timer and names don't. OCR boxes vary a
    # lot from letter to letter, hence the loose bounds.
    def similar(a, b):
        return 0.55 < a.h / b.h < 1.8

    ref = max(boxes, key=lambda b: (sum(similar(b, o) for o in boxes), b.h))
    boxes = [b for b in boxes if similar(b, ref)]
    if len(boxes) < min_hits:
        return None

    # Tile pitch: the distance that best explains the gaps along rows and columns as 1, 2 or 3 tiles.
    h = median(b.h for b in boxes)
    gaps = []
    for a, b in combinations(boxes, 2):
        if abs(a.y - b.y) < h / 2:
            gaps.append(abs(a.x - b.x))
        elif abs(a.x - b.x) < h / 2:
            gaps.append(abs(a.y - b.y))
    gaps = [d for d in gaps if d > h / 2]
    if not gaps:
        return None

    def explained(p):
        return sum(any(abs(d - k * p) < 0.1 * p for k in (1, 2, 3)) for d in gaps)

    pitch = max(gaps, key=lambda p: (explained(p), -p))

    # Snap boxes onto a lattice anchored at each box in turn and keep the 4x4 window with the most hits.
    best, outside = {}, 0
    for anchor in boxes:
        snapped = {}
        for b in boxes:
            u, v = (b.x - anchor.x) / pitch, (b.y - anchor.y) / pitch
            if abs(u - round(u)) < 0.25 and abs(v - round(v)) < 0.25:
                snapped.setdefault((round(v), round(u)), b)
        for r0 in range(-SIZE + 1, 1):
            for c0 in range(-SIZE + 1, 1):
                cells = {(r - r0) * SIZE + (c - c0): b for (r, c), b in snapped.items()
                         if r0 <= r < r0 + SIZE and c0 <= c < c0 + SIZE}
                if len(cells) > len(best):
                    best, outside = cells, len(snapped) - len(cells)

    # Tiles lined up beyond the 4x4 mean one of the bigger maps (donut, cross, 5x5), which isn't supported.
    if outside >= SIZE:
        return None
    # Every row and column needs a hit, otherwise the board could sit one tile further over.
    if (len(best) < min_hits
            or len({i // SIZE for i in best}) < SIZE
            or len({i % SIZE for i in best}) < SIZE):
        return None

    x0, dx = _line([(i % SIZE, b.x) for i, b in best.items()])
    y0, dy = _line([(i // SIZE, b.y) for i, b in best.items()])
    if not 0.8 < dx / dy < 1.25:
        return None
    return Grid(x0, y0, dx, dy)


def snap(letters, grid):
    """Tile index → letter for the letter boxes that sit on a tile of `grid`."""
    cells = {}
    for b in letters:
        u, v = (b.x - grid.x0) / grid.dx, (b.y - grid.y0) / grid.dy
        col, row = round(u), round(v)
        if 0 <= col < SIZE and 0 <= row < SIZE and abs(u - col) < 0.35 and abs(v - row) < 0.35:
            cells.setdefault(row * SIZE + col, b.char)
    return cells


def _line(points):
    """Least-squares fit of value = start + index * step."""
    n = len(points)
    mean_i = sum(i for i, _ in points) / n
    mean_v = sum(v for _, v in points) / n
    step = (sum((i - mean_i) * (v - mean_v) for i, v in points)
            / sum((i - mean_i) ** 2 for i, _ in points))
    return mean_v - step * mean_i, step


def vote(readings):
    """Combine several readings of the board (dicts of tile index → letter) into 16 letters, '?' where none."""
    letters = []
    for i in range(SIZE * SIZE):
        votes = Counter(r[i] for r in readings if i in r)
        if "Q" in votes:
            votes["Q"] += votes.pop("O", 0)  # OCR drops the tail off a Q far more often than it invents one
        # On a tie, prefer a letter with more strokes over the bare shapes misreads collapse to.
        letters.append(max(votes, key=lambda c: (votes[c], c not in "IO")) if votes else "?")
    return "".join(letters)
