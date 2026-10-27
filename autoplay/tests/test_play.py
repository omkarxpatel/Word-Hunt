import time

import pytest

from autoplay.grid import Grid
from autoplay.play import Speed, Stopped, drag_points, play, swipe
from autoplay.solver import Word, points

CENTRES = Grid(100, 500, 60, 60).centres()
FAST = Speed(steps=4, step_delay=0, dwell=0, hold=0, word_delay=0)


class FakeMouse:
    def __init__(self):
        self.events = []

    def move(self, x, y):
        self.events.append(("move", x, y))

    def down(self, x, y):
        self.events.append(("down", x, y))

    def drag(self, x, y):
        self.events.append(("drag", x, y))

    def up(self, x, y):
        self.events.append(("up", x, y))


def never():
    return None


def test_straight_moves_end_on_each_tile_centre():
    moves = drag_points(CENTRES, ((0, 0), (0, 1), (1, 1)), steps=4)
    assert moves == [[(115, 500), (130, 500), (145, 500), (160, 500)],
                     [(160, 515), (160, 530), (160, 545), (160, 560)]]


def test_moves_land_exactly_on_centres_that_are_not_round_numbers():
    centres = Grid(100.3, 500.7, 59.9, 60.1).centres()
    moves = drag_points(centres, ((0, 0), (1, 1), (2, 1)), steps=3)
    assert [move[-1] for move in moves] == [centres[5], centres[9]]


def test_diagonal_moves_skip_the_shared_corner():
    [move] = drag_points(CENTRES, ((0, 0), (1, 1)), steps=4)
    assert len(move) == 5  # bumped to an odd count
    assert (130, 530) not in move  # the corner where four tiles meet
    assert move[-1] == (160, 560)


def test_swipe_rests_on_every_tile_centre(monkeypatch):
    mouse, log = FakeMouse(), []
    monkeypatch.setattr("autoplay.play.time.sleep", lambda seconds: log.append((seconds, mouse.events[-1])))
    speed = Speed(steps=2, step_delay=0.001, dwell=0.5, hold=0.01, word_delay=0)
    swipe(mouse, CENTRES, ((0, 0), (0, 1), (1, 2)), speed, never)
    rests = [event for seconds, event in log if seconds == 0.5]
    assert rests == [("drag", 160, 500), ("drag", 220, 560)]  # the centres of tiles 1 and 6


def test_swipe_presses_drags_and_releases():
    mouse = FakeMouse()
    swipe(mouse, CENTRES, ((0, 0), (0, 1), (0, 2)), FAST, never)
    kinds = [e[0] for e in mouse.events]
    assert kinds == ["move", "down"] + ["drag"] * 8 + ["up"]
    assert mouse.events[1] == ("down", 100, 500)
    assert mouse.events[-1] == ("up", 220, 500)


def test_swipe_releases_the_button_when_stopped():
    mouse = FakeMouse()
    calls = iter([None, None, "Esc pressed"])
    with pytest.raises(Stopped, match="Esc"):
        swipe(mouse, CENTRES, ((0, 0), (0, 1), (0, 2)), FAST, lambda: next(calls))
    assert mouse.events[-1] == ("up", 130, 500)  # let go where the drag stopped
    assert [e[0] for e in mouse.events].count("drag") == 2


def word(text, *tiles):
    return Word(text, points(len(text)), tiles)


LONG = word("abcde", (0, 0), (0, 1), (0, 2), (0, 3), (1, 3))
SHORT = word("abc", (0, 0), (0, 1), (0, 2))


def test_play_swipes_every_word_in_order():
    mouse, seen = FakeMouse(), []
    played, why = play([LONG, SHORT], CENTRES, mouse, FAST, time.monotonic() + 60, never, never,
                       lambda w, done: seen.append(w.word))
    assert played == [LONG, SHORT] and seen == ["abcde", "abc"]
    assert why == "every word swiped"


def test_play_skips_words_that_no_longer_fit_in_the_time_left():
    slow = Speed(steps=4, step_delay=0.01, dwell=0, hold=0, word_delay=0)  # ~0.2 s for 5 letters, ~0.1 s for 3
    played, why = play([LONG, SHORT], CENTRES, FakeMouse(), slow, time.monotonic() + 0.15, never, never,
                       lambda w, done: None)
    assert played == [SHORT]
    assert why == "time's up"


def test_play_stops_on_abort_and_reports_why():
    reasons = iter([None, "you moved the mouse"])
    played, why = play([SHORT, SHORT, SHORT], CENTRES, FakeMouse(), FAST, time.monotonic() + 60,
                       never, lambda: next(reasons), lambda w, done: None)
    assert played == [SHORT]
    assert why == "you moved the mouse"


def test_estimated_time_grows_with_word_length():
    speed = Speed()
    assert speed.seconds(3) < speed.seconds(8)
    assert 0.3 < speed.seconds(5) < 1.5
