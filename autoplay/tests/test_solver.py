import pytest

from autoplay.solver import Dictionary, InvalidPath, check_path, points, solve

BOARD = "tcneobruresdwtds"  # T C N E / O B R U / R E S D / W T D S
ALPHABET = "abcdefghijklmnop"  # a b c d / e f g h / i j k l / m n o p


@pytest.fixture(scope="module")
def dictionary():
    return Dictionary.load()


def test_points_match_the_website():
    assert [points(n) for n in range(3, 11)] == [100, 400, 800, 1400, 1800, 2200, 2600, 3000]
    assert points(2) == 0


def test_solve_matches_the_website(dictionary):
    # The website finds the same 230 words, 145,600 points, and path for BEST on this board.
    words = solve(BOARD, dictionary)
    assert len(words) == 230
    assert sum(w.points for w in words) == 145600
    assert next(w for w in words if w.word == "best").path == ((1, 1), (2, 1), (2, 2), (3, 1))


def test_best_words_come_first(dictionary):
    words = solve(BOARD, dictionary)
    assert words[0].word == "encrusted"
    assert [w.points for w in words] == sorted((w.points for w in words), reverse=True)


def test_every_solved_path_passes_the_checks(dictionary):
    for w in solve(BOARD, dictionary):
        check_path(BOARD, w.word, w.path)


def test_follows_neighbours_and_does_not_wrap_rows():
    words = Dictionary(["abf", "afk", "ponm", "dea", "aba"])
    # dea would need d (tile 3) next to e (tile 4), which are on different rows; aba reuses the a.
    assert {w.word for w in solve(ALPHABET, words)} == {"abf", "afk", "ponm"}


def test_unreadable_tiles_are_skipped():
    words = Dictionary(["abf", "afk", "ponm"])
    assert {w.word for w in solve("abcde?ghijklmnop", words)} == {"ponm"}


def test_check_path_accepts_a_valid_path():
    check_path(ALPHABET, "afkp", ((0, 0), (1, 1), (2, 2), (3, 3)))


@pytest.mark.parametrize("word, path, problem", [
    ("ab", ((0, 0), (0, 1)), "tiles for"),  # too short to score
    ("abc", ((0, 0), (0, 1)), "tiles for"),  # path shorter than the word
    ("aba", ((0, 0), (0, 1), (0, 0)), "reuses"),
    ("abd", ((0, 0), (0, 1), (0, 3)), "neighbours"),  # skips a tile
    ("cde", ((0, 2), (0, 3), (1, 0)), "neighbours"),  # tiles 3 → 4 wrap across rows
    ("abx", ((0, 0), (0, 1), (-1, 1)), "off the board"),
    ("abe", ((0, 0), (0, 1), (1, 1)), "spells"),
])
def test_check_path_rejects(word, path, problem):
    with pytest.raises(InvalidPath, match=problem):
        check_path(ALPHABET, word, path)
