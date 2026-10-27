"""End-to-end check on your Mac, without the phone: a fake phone window (fakephone.py) shows a generated
board, the bot reads and plays it with real mouse events, and the window logs where every swipe went.

It takes over the mouse for about ten seconds, so it only runs when asked:
    AUTOPLAY_GUI_TEST=1 .venv/bin/python -m pytest autoplay/tests/test_gui.py
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

if os.environ.get("AUTOPLAY_GUI_TEST") != "1":
    pytest.skip("takes over the mouse; run with AUTOPLAY_GUI_TEST=1", allow_module_level=True)

from autoplay import __main__ as cli  # noqa: E402
from autoplay import mac  # noqa: E402
from autoplay.solver import Dictionary, solve  # noqa: E402
from fakeboard import render  # noqa: E402

LETTERS = "GSYNROASRKNAEEVG"


def strokes(events, tiles, half_tile):
    """Split logged [kind, x, y] events into strokes (down..up), each a list of tile indices (None between tiles)."""
    def tile_at(x, y):
        for i, (tx, ty) in enumerate(tiles):
            if abs(x - tx) <= half_tile and abs(y - ty) <= half_tile:
                return i
        return None

    done, current = [], []
    for kind, x, y in events:
        current.append(tile_at(x, y))
        if kind == "up":
            done.append(current)
            current = []
    return done


def test_bot_plays_a_fake_phone(tmp_path, monkeypatch, capsys):
    assert mac.find_window() is None, "close iPhone Mirroring first, so no swipe can reach the phone"
    # No clock on this board, so the bot plays for --time-limit seconds.
    centres = render(LETTERS, tmp_path / "board.png", timer="")
    log = tmp_path / "events.json"
    app = subprocess.Popen([sys.executable, Path(__file__).with_name("fakephone.py"), tmp_path / "board.png", log])
    cursor = mac.cursor()
    try:
        ready = Path(f"{log}.ready")
        for _ in range(100):
            if ready.exists():
                break
            time.sleep(0.1)
        info = json.loads(ready.read_text())
        x0, y0, _, _ = info["frame"]
        monkeypatch.setattr(mac, "_pids", lambda: {info["pid"]})
        monkeypatch.setattr(mac, "activate", lambda: None)  # the fake phone brought itself to the front
        time.sleep(0.5)
        cli.main(["--now", "--countdown", "0.5", "--time-limit", "6"])
        time.sleep(0.3)
    finally:
        mac.Mouse().move(*cursor)
        app.terminate()

    output = capsys.readouterr().out
    assert "Time's up" in output, output  # not stopped by its own events or a covered board

    # Screen position of each tile centre: the window shows the 2x image at half size.
    tiles = [(x0 + x / 2, y0 + y / 2) for x, y in centres]
    half_tile = 0.43 * (tiles[1][0] - tiles[0][0])  # fakeboard tiles are 86% of the pitch
    focus, *swipes = strokes(json.loads(log.read_text()), tiles, half_tile)
    assert focus == [None, None]  # the focus click lands between tiles
    words = solve(LETTERS.lower(), Dictionary.load())
    assert len(swipes) >= 5
    for stroke, word in zip(swipes, words):
        visited = [t for i, t in enumerate(stroke) if t is not None and (i == 0 or t != stroke[i - 1])]
        assert None not in stroke[:1] + stroke[-1:], word  # pressed and released on tiles
        assert visited == [r * 4 + c for r, c in word.path], word  # no grazed neighbours
