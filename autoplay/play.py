"""Turning solved words into swipes: the drag path, its timing, and the game loop."""

import time
from dataclasses import dataclass

from .solver import SIZE


@dataclass
class Speed:
    steps: int = 4  # drag events per tile-to-tile move
    step_delay: float = 0.01  # seconds between drag events
    # Rest on each tile centre. iPhone Mirroring doesn't hand every mouse position to the phone, so
    # without a rest the touch can jump straight past a tile and the game never sees it.
    dwell: float = 0.06
    hold: float = 0.05  # pause after pressing on the first tile, and before letting go on the last
    word_delay: float = 0.15  # pause between words

    def seconds(self, letters):
        """Roughly how long one word takes, including the pause after it."""
        move = (self.steps + 1) * self.step_delay + self.dwell
        return 3 * self.hold + (letters - 1) * move + self.word_delay


class Stopped(Exception):
    pass


def drag_points(centres, path, steps):
    """Where the drag events go for one word: for each move to the next tile, `steps` points ending
    exactly on its centre."""
    moves = []
    for (r1, c1), (r2, c2) in zip(path, path[1:]):
        (x1, y1), (x2, y2) = centres[r1 * SIZE + c1], centres[r2 * SIZE + c2]
        n = steps
        if r1 != r2 and c1 != c2 and n % 2 == 0:
            n += 1  # keeps diagonal moves off the corner point shared with the two tiles beside them
        moves.append([(x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n) for k in range(1, n)] + [(x2, y2)])
    return moves


def swipe(mouse, centres, path, speed, stop):
    """Swipe one word. `stop()` returns a reason to abort, or None; it is checked before every drag event."""
    row, col = path[0]
    last = centres[row * SIZE + col]
    mouse.move(*last)
    time.sleep(speed.hold)
    mouse.down(*last)
    try:
        time.sleep(speed.hold)
        for move in drag_points(centres, path, speed.steps):
            for point in move:
                reason = stop()
                if reason:
                    raise Stopped(reason)
                mouse.drag(*point)
                last = point
                time.sleep(speed.step_delay)
            time.sleep(speed.dwell)
        time.sleep(speed.hold)
    finally:
        mouse.up(*last)  # never leave the button held down, even when aborting mid-word


def play(words, centres, mouse, speed, deadline, stop, check, progress):
    """Swipe `words` in order until they run out or the clock (time.monotonic) reaches `deadline`.

    `stop()` is checked between drag events and `check()` before each word; either returning a reason
    ends the game. Returns (words swiped, why it ended).
    """
    played = []
    try:
        for word in words:
            if time.monotonic() + speed.seconds(len(word.word)) > deadline:
                continue  # no time for this one; a shorter word further down may still fit
            reason = stop() or check()
            if reason:
                raise Stopped(reason)
            swipe(mouse, centres, word.path, speed, stop)
            played.append(word)
            progress(word, played)
            time.sleep(speed.word_delay)
    except Stopped as stopped:
        return played, str(stopped)
    return played, "every word swiped" if len(played) == len(words) else "time's up"
