import random

from autoplay.grid import Box, Grid, fit, from_corners, snap, vote

TRUE = Grid(120, 600, 118, 118)  # roughly a 652 px wide iPhone Mirroring screenshot


def tiles(grid=TRUE, skip=(), jitter=0.0, seed=0):
    rng = random.Random(seed)
    return [Box("", x + rng.uniform(-jitter, jitter), y + rng.uniform(-jitter, jitter), 0.85 * grid.dx)
            for i, (x, y) in enumerate(grid.centres()) if i not in skip]


def close(a, b, tolerance=1.0):
    return all(abs(p - q) < tolerance for (x1, y1), (x2, y2) in zip(a.centres(), b.centres()) for p, q in ((x1, x2), (y1, y2)))


def test_centres_run_row_by_row():
    assert TRUE.centre(0) == (120, 600)
    assert TRUE.centre(3) == (120 + 3 * 118, 600)
    assert TRUE.centre(4) == (120, 600 + 118)
    assert TRUE.centre(15) == (120 + 3 * 118, 600 + 3 * 118)


def test_from_corners_spreads_16_tiles_between_the_corner_centres():
    grid = from_corners((10, 20), (310, 320))
    assert grid.centres()[0] == (10, 20)
    assert grid.centres()[15] == (310, 320)
    assert grid.centre(5) == (110, 120)


def test_screenshot_pixels_to_screen_points():
    # A 326x720 pt window at (589, 142) captured at 2x: pixel centres → screen points.
    pixels = Grid(120, 600, 118, 118)
    screen = pixels.scaled(1 / 2, 1 / 2).moved(589, 142)
    assert screen.centre(0) == (589 + 60, 142 + 300)
    assert screen.centre(15) == (589 + 60 + 3 * 59, 142 + 300 + 3 * 59)


def test_fit_finds_a_full_board():
    assert close(fit(tiles()), TRUE)


def test_fit_fills_in_missing_tiles():
    assert close(fit(tiles(skip={1, 2, 6, 9, 11, 14})), TRUE)


def test_fit_ignores_other_things_on_screen():
    clutter = [Box("", 326, 160, 40), Box("", 326, 780, 4.2 * 118),  # score banner, the board's own outline
               Box("S", 200, 100, 30), Box("C", 230, 100, 30), Box("O", 260, 100, 30)]
    assert close(fit(tiles() + clutter), TRUE)


def test_fit_tolerates_jitter():
    assert close(fit(tiles(jitter=6, seed=4)), TRUE, tolerance=6)


def test_fit_accepts_letter_boxes():
    letters = [Box("A", x, y, 0.45 * 118 * (0.8 if i % 3 else 1.2)) for i, (x, y) in enumerate(TRUE.centres())]
    assert close(fit(letters), TRUE)


def test_fit_rejects_too_little_evidence():
    assert fit(tiles(skip=set(range(11)))) is None


def test_fit_rejects_a_board_missing_a_whole_row():
    # Rows 0-2 only: the board could just as well extend up or down.
    assert fit(tiles(skip={12, 13, 14, 15})) is None


def test_fit_rejects_bigger_maps():
    five_by_five = [Box("", 100 + c * 100, 500 + r * 100, 85) for r in range(5) for c in range(5)]
    assert fit(five_by_five) is None


def test_fit_rejects_scattered_boxes():
    rng = random.Random(1)
    assert fit([Box("", rng.uniform(0, 650), rng.uniform(0, 1400), 80) for _ in range(16)]) is None


def test_snap_assigns_letters_to_the_nearest_tile():
    letters = [Box("A", 120 + 5, 600 - 4, 50), Box("B", 120 + 118 * 3, 600 + 118 * 3, 50),
               Box("Z", 120 + 59, 600, 50),  # halfway between two tiles: ignored
               Box("Y", 0, 0, 50)]  # off the board
    assert snap(letters, TRUE) == {0: "A", 15: "B"}


def test_vote_takes_the_majority_and_marks_gaps():
    readings = [{0: "A", 1: "B"}, {0: "A", 1: "B"}, {0: "R"}]
    assert vote(readings) == "AB" + "?" * 14


def test_vote_prefers_q_over_o_and_letters_over_bare_shapes():
    readings = [{0: "O", 1: "I", 2: "O"}, {0: "O", 1: "L", 2: "C"}, {0: "Q"}]
    assert vote(readings)[:3] == "QLC"


def test_vote_with_no_readings():
    assert vote([]) == "?" * 16
