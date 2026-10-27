"""Python port of the solver in wordhunt.js, plus the path checks the bot runs before swiping."""

from pathlib import Path
from typing import NamedTuple

WORDS_FILE = Path(__file__).resolve().parent.parent / "utils" / "words.txt"
SIZE = 4

Tile = tuple[int, int]  # (row, col), 0-indexed: the same format as the paths on the website


class Word(NamedTuple):
    word: str
    points: int
    path: tuple[Tile, ...]


class InvalidPath(ValueError):
    pass


def points(length):
    """Same table as wordhunt.js: 3 → 100, 4 → 400, 5 → 800, 6 → 1400, then +400 per letter."""
    if length < 3:
        return 0
    return {3: 100, 4: 400, 5: 800}.get(length, 1400 + 400 * (length - 6))


class Dictionary:
    def __init__(self, words):
        self.words = set(words)
        # Every prefix of every word (words included), so the search can stop on dead ends.
        self.prefixes = {word[:i] for word in self.words for i in range(1, len(word) + 1)}

    @classmethod
    def load(cls, path=WORDS_FILE):
        return cls(path.read_text().split())


def neighbours(row, col):
    # Same order as getAdjacentNodes in wordhunt.js, so both solvers pick the same path for a word.
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            r, c = row + dr, col + dc
            if (dr or dc) and 0 <= r < SIZE and 0 <= c < SIZE:
                yield r, c


def solve(board, dictionary):
    """Every word on `board` (16 letters, row by row) with one path each, highest points first.

    Tiles that aren't a-z, like the '?' used for a letter OCR couldn't read, are skipped.
    """
    board = board.lower()
    found = {}

    def search(path, word):
        if word in dictionary.words and word not in found:
            found[word] = tuple(path)
        for r, c in neighbours(*path[-1]):
            longer = word + board[r * SIZE + c]
            if (r, c) not in path and longer in dictionary.prefixes:
                path.append((r, c))
                search(path, longer)
                path.pop()

    for i, letter in enumerate(board):
        if letter in dictionary.prefixes:
            search([divmod(i, SIZE)], letter)

    words = [Word(word, points(len(word)), path) for word, path in found.items()]
    return sorted(words, key=lambda w: (-w.points, w.word))


def check_path(board, word, path):
    """Raise InvalidPath unless `path` spells `word` on `board` through distinct, 8-way adjacent tiles."""
    if len(word) < 3 or len(path) != len(word):
        raise InvalidPath(f"{word}: {len(path)} tiles for {len(word)} letters")
    if len(set(path)) != len(path):
        raise InvalidPath(f"{word}: reuses a tile")
    for r, c in path:
        if not (0 <= r < SIZE and 0 <= c < SIZE):
            raise InvalidPath(f"{word}: tile {(r, c)} is off the board")
    for (r1, c1), (r2, c2) in zip(path, path[1:]):
        if max(abs(r1 - r2), abs(c1 - c2)) != 1:
            raise InvalidPath(f"{word}: {(r1, c1)} and {(r2, c2)} aren't neighbours")
    spelled = "".join(board[r * SIZE + c] for r, c in path).lower()
    if spelled != word.lower():
        raise InvalidPath(f"{word}: path spells {spelled!r}")
