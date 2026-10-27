"""python -m autoplay: plays GamePigeon Word Hunt through iPhone Mirroring. See README.md."""

import argparse
import json
import re
import sys
import time
import traceback
from pathlib import Path

from . import mac, ocr
from .grid import SIZE, Grid, from_corners
from .play import Speed, Stopped, play
from .solver import Dictionary, InvalidPath, check_path, solve

HERE = Path(__file__).resolve().parent
CALIBRATION = HERE / "calibration.json"
SETTINGS = HERE / "settings.json"
ROUND_SECONDS = 80  # one Word Hunt round
MARGIN = 1.5  # stop swiping this many seconds before the game's clock runs out


def options(argv=None):
    parser = argparse.ArgumentParser(prog="python -m autoplay",
                                     description="Plays GamePigeon Word Hunt through iPhone Mirroring.")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "read", "calibrate"],
                        help="run (default): wait for the hotkey, then read the board and play. "
                             "read: show what the bot sees, without playing. "
                             "calibrate: set the tile positions by hand, for when the board isn't found on its own.")
    parser.add_argument("image", nargs="?", help="read: a screenshot file to read instead of the iPhone Mirroring window")
    parser.add_argument("--hotkey", default="ctrl+alt+p", help="starts a game (default: %(default)s)")
    parser.add_argument("--now", action="store_true", help="play one game straight away instead of waiting for the hotkey")
    parser.add_argument("--dry-run", action="store_true",
                        help="read and solve, then print the swipes and tile coordinates without touching the mouse")
    parser.add_argument("--board", help="use these 16 letters (row by row) instead of reading them off the screen")
    parser.add_argument("--countdown", type=float, default=1,
                        help="seconds between reading the board and the first swipe (default: %(default)s)")
    parser.add_argument("--time-limit", type=float, default=70,
                        help="seconds to play when the game's clock can't be read (default: %(default)s)")
    parser.add_argument("--steps", type=int, default=Speed.steps,
                        help="drag events per tile-to-tile move (default: %(default)s)")
    parser.add_argument("--step-delay", type=float, default=Speed.step_delay,
                        help="seconds between drag events (default: %(default)s)")
    parser.add_argument("--dwell", type=float, default=Speed.dwell,
                        help="seconds to rest on each tile; raise it if letters in the middle of words get skipped "
                             "(default: %(default)s)")
    parser.add_argument("--hold", type=float, default=Speed.hold,
                        help="seconds to hold after pressing on the first tile and before letting go (default: %(default)s)")
    parser.add_argument("--word-delay", type=float, default=Speed.word_delay,
                        help="seconds between words (default: %(default)s)")
    if SETTINGS.exists():
        parser.set_defaults(**json.loads(SETTINGS.read_text()))
    args = parser.parse_args(argv)
    try:
        args.keys = mac.parse_hotkey(args.hotkey)
    except ValueError as error:
        parser.error(str(error))
    if args.board:
        args.board = re.sub(r"[^a-z?]", "", args.board.lower())
        if len(args.board) != SIZE * SIZE:
            parser.error("--board needs exactly 16 letters")
    return args


def need_permissions(post=False, listen=False, capture=False):
    missing = mac.missing_permissions(post, listen, capture)
    if missing:
        sys.exit(f"{mac.terminal_app()} needs these permissions: {', '.join(missing)}.\n"
                 "Turn them on in System Settings → Privacy & Security (macOS may have just opened a prompt),\n"
                 "then quit and reopen the terminal app and run this again.")


def need_window():
    window = mac.find_window()
    if window is None:
        sys.exit("iPhone Mirroring isn't on screen. Open it and connect to your iPhone first.")
    return window


def calibrated(window, sx, sy):
    """The hand-calibrated grid in screenshot pixels, if one was saved for a window this size."""
    if not CALIBRATION.exists():
        return None
    saved = json.loads(CALIBRATION.read_text())
    if saved["window"] != [window.w, window.h]:
        print("(Ignoring calibration.json: the iPhone Mirroring window changed size. Run calibrate again.)")
        return None
    return Grid(*saved["grid"]).scaled(sx, sy)


def look(window):
    """Screenshot `window` and read the board: (reading, tile centres in screen points), or (None, None)."""
    image = mac.capture(window)
    width, height = ocr.size(image)
    sx, sy = width / window.w, height / window.h  # screenshot pixels per screen point
    if abs(sx - sy) > 0.02 * sx:
        raise RuntimeError(f"the screenshot ({width}x{height} px) doesn't match the window ({window.w:g}x{window.h:g} pt)")
    reading = ocr.read(image, calibrated(window, sx, sy))
    if reading is None:
        return None, None
    return reading, reading.grid.scaled(1 / sx, 1 / sy).moved(window.x, window.y).centres()


def clock(seconds):
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def show(letters, words, note):
    lines = [f"{len(words)} words, {sum(w.points for w in words):,} points on the board", note]
    for row in range(SIZE):
        tiles = " ".join(letters[row * SIZE:(row + 1) * SIZE].upper())
        print(f"    {tiles}      {lines[row] if row < len(lines) else ''}".rstrip())
    if "?" in letters:
        print("    (? = a tile it couldn't read; words through it are skipped)")


def show_centres(centres, unit):
    print(f"Tile centres ({unit}):")
    for row in range(SIZE):
        print("    " + "  ".join(f"{row * SIZE + col:2d}:({x:6.1f},{y:6.1f})"
                                  for col, (x, y) in enumerate(centres[row * SIZE:(row + 1) * SIZE])))


def read(args):
    started = time.monotonic()
    if args.image:
        reading = ocr.read(ocr.load(args.image))
        centres = reading.grid.centres() if reading else None
        unit = "pixels in the image"
    else:
        need_permissions(capture=True)
        reading, centres = look(need_window())
        unit = "screen points"
    if reading is None:
        sys.exit("No Word Hunt board found.")
    print(f"Read in {time.monotonic() - started:.2f} s.")
    letters = args.board or reading.letters.lower()
    seconds = reading.seconds_left
    show(letters, solve(letters, Dictionary.load()),
         f"game clock {clock(seconds)}" if seconds is not None else "game clock not found")
    show_centres(centres, unit)


def calibrate(args):
    window = need_window()
    print("This tells the bot where the tiles are, for when it can't find the board by itself.\n"
          "Open a Word Hunt game in iPhone Mirroring. Keep this terminal focused: hover, don't click.")
    input("Hover over the centre of the TOP-LEFT tile and press Enter... ")
    x1, y1 = mac.cursor()
    input("Hover over the centre of the BOTTOM-RIGHT tile and press Enter... ")
    x2, y2 = mac.cursor()
    grid = from_corners((x1 - window.x, y1 - window.y), (x2 - window.x, y2 - window.y))
    if grid.dx < 10 or grid.dy < 10:
        sys.exit("Those two points don't look like the top-left and bottom-right tiles. Try again.")
    CALIBRATION.write_text(json.dumps({"window": [window.w, window.h], "grid": list(grid),
                                       "tiles": [[round(x, 1), round(y, 1)] for x, y in grid.centres()]},
                                      indent=2) + "\n")
    print(f"Saved {CALIBRATION}.")
    show_centres(grid.centres(), "points from the window's top-left corner")
    if input("Hover over each tile in turn to check them (no clicks)? [y/N] ").strip().lower() == "y":
        need_permissions(post=True)
        mouse = mac.Mouse()
        for x, y in grid.moved(window.x, window.y).centres():
            mouse.move(x, y)
            time.sleep(0.3)


def countdown(seconds, listener):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if listener.reason:
            raise Stopped(listener.reason)
        print(f"\r  starting in {end - time.monotonic():.1f} s ", end="", flush=True)
        time.sleep(0.05)
    print("\r" + " " * 30 + "\r", end="")


def game(args, dictionary, listener, mouse, speed):
    started = time.monotonic()
    window = mac.find_window()
    if window is None:
        print("iPhone Mirroring isn't on screen.")
        return
    for _ in range(3):
        reading, centres = look(window)
        if reading:
            break
        time.sleep(0.5)  # the board may still be sliding in
    else:
        print("No Word Hunt board found in the iPhone Mirroring window.")
        return

    letters = args.board or reading.letters.lower()
    words = solve(letters, dictionary)
    try:
        for word in words:
            check_path(letters, word.word, word.path)
    except InvalidPath as error:
        print(f"Not playing, a solved path failed its check: {error}")
        return

    seconds = reading.seconds_left
    if seconds is not None and 0 < seconds <= ROUND_SECONDS:
        deadline, note = started + seconds - MARGIN, f"game clock {clock(seconds)}"
    else:
        deadline, note = started + args.time_limit, f"clock not found, playing {args.time_limit:g} s"
    print(f"\nRead the board in {time.monotonic() - started:.2f} s:")
    show(letters, words, note)

    if args.dry_run:
        show_centres(centres, "screen points")
        print("Swipe order (tile numbers as above):")
        for n, word in enumerate(words, 1):
            tiles = " ".join(str(r * SIZE + c) for r, c in word.path)
            print(f"  {n:3d}. {word.word.upper():<12} {word.points:>5}  {tiles}")
        return

    pitch_x, pitch_y = centres[1][0] - centres[0][0], centres[SIZE][1] - centres[0][1]
    board = (centres[0][0] - pitch_x / 2, centres[0][1] - pitch_y / 2, SIZE * pitch_x, SIZE * pitch_y)

    def progress(word, played):
        score = sum(w.points for w in played)
        print(f"\r  {len(played):3d}/{len(words)}  {word.word.upper():<12} +{word.points:<5} score {score:>7,}"
              f"   {max(0, deadline - time.monotonic()):4.1f} s left ", end="", flush=True)

    listener.arm()
    try:
        mac.activate()
        countdown(args.countdown, listener)
        reason = mac.blocker(window, board)
        if reason:
            raise Stopped(reason)
        # Focus click in the gap between the four middle tiles, away from every letter.
        gap = ((centres[5][0] + centres[10][0]) / 2, (centres[5][1] + centres[10][1]) / 2)
        mouse.move(*gap)
        time.sleep(speed.hold)
        mouse.down(*gap)
        time.sleep(speed.hold)
        mouse.up(*gap)
        time.sleep(0.2)
        played, why = play(words, centres, mouse, speed, deadline,
                           stop=lambda: listener.reason,
                           check=lambda: mac.blocker(window, board),
                           progress=progress)
    except Stopped as stopped:
        played, why = [], str(stopped)
    finally:
        listener.disarm()
    print(f"\n{why[0].upper() + why[1:]}: swiped {len(played)} of {len(words)} words, "
          f"{sum(w.points for w in played):,} points if the game takes them all.")


def run(args):
    speed = Speed(steps=args.steps, step_delay=args.step_delay, dwell=args.dwell, hold=args.hold,
                  word_delay=args.word_delay)
    listen = not (args.now and args.dry_run)
    need_permissions(post=not args.dry_run, listen=listen, capture=True)
    dictionary = Dictionary.load()
    listener = mac.Listener(args.keys) if listen else None
    mouse = None if args.dry_run else mac.Mouse()
    print(f"Word Hunt autoplay: {len(dictionary.words):,} words loaded"
          f"{', DRY RUN (the mouse is never touched)' if args.dry_run else ''}.")
    print("Esc, the hotkey, or touching the mouse stops a game.")
    while True:
        if not args.now:
            missing = "" if mac.find_window() else " (iPhone Mirroring isn't on screen yet)"
            print(f"\nREADY: start a Word Hunt game, then press {args.hotkey}. Ctrl+C quits.{missing}")
            listener.hotkey.clear()
            while not listener.hotkey.wait(0.25):
                pass
        try:
            game(args, dictionary, listener, mouse, speed)
        except Exception:
            traceback.print_exc()
        if args.now:
            return


def main(argv=None):
    args = options(argv)
    try:
        {"run": run, "read": read, "calibrate": calibrate}[args.command](args)
    except KeyboardInterrupt:
        print("\nBye.")


if __name__ == "__main__":
    main()
