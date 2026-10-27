"""Draws docs/demo.svg: the bot reading one board and swiping its first ten words, on a loop.

The words, tile paths and swipe timing come from the bot's own code (solver.py, and play.py at the
default speed) and the terminal shows the CLI's own wording. It is drawn rather than screen-recorded
because a recording needs a live game on a phone.

Run from the repo root: .venv/bin/python docs/make_demo.py
"""

import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from autoplay.grid import SIZE, Grid  # noqa: E402
from autoplay.play import Speed, drag_points  # noqa: E402
from autoplay.solver import Dictionary, points, solve  # noqa: E402

BOARD = "resocaerehtfdsat"  # chosen so the first ten words are everyday English
SHOWN = 10  # words swiped before the animation starts over
CLOCK = 79  # seconds on the game's clock when the animation starts
STEP = 0.001  # two keyframes this close together make an instant change
COLOURS = {"none": "#ffffff", "new": "#86fe8c", "found": "#ffe95e"}  # the game's colours for a selection
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"

W, H = 980, 600
TX, TY, TW, TH = 20, 20, 620, 330  # terminal
NX, NY, NW, NH = 20, 370, 620, 210  # the three steps
PX, PY, PW, PH = 670, 20, 290, 560  # phone
SX, SY, SW, SH = PX + 8, PY + 8, PW - 16, PH - 16  # its screen
BOARD_SIZE = 0.8 * SW
BX, BY = SX + (SW - BOARD_SIZE) / 2, SY + 0.4 * SH
PAD = 0.045 * BOARD_SIZE
PITCH = (BOARD_SIZE - 2 * PAD) / SIZE
TILE = 0.86 * PITCH
CENTRES = Grid(BX + PAD + PITCH / 2, BY + PAD + PITCH / 2, PITCH, PITCH).centres()


class Animation:
    """SVG elements animated by CSS keyframes that all run on one looping clock."""

    def __init__(self):
        self.parts, self.rules = [], []

    def add(self, markup, frames=None):
        """Add `markup`; with `frames` ([(seconds, {css property: value})]) its {id} gets animated."""
        if frames:
            name = f"a{len(self.rules)}"
            markup = markup.replace("{id}", name)
            self.rules.append((name, sorted(frames, key=lambda frame: frame[0])))
        self.parts.append(markup)

    def svg(self, duration):
        css = []
        for name, frames in self.rules:
            start = {k: v for t, props in frames if t == 0 for k, v in props.items()}
            last = {k: v for t, props in frames for k, v in props.items()}
            # Hold the last values to the end of the loop, then snap back to where it started.
            if frames[-1][0] < duration - STEP:
                frames = frames + [(duration - STEP, last)]
            frames = frames + [(duration, start)]
            stops = " ".join(f"{100 * min(t, duration) / duration:.3f}%{{"
                             + ";".join(f"{k}:{v}" for k, v in props.items()) + "}" for t, props in frames)
            css.append(f"@keyframes {name}{{{stops}}}#{name}{{animation:{name} {duration:.2f}s linear infinite}}")
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">\n'
                f'<title>Word Hunt autoplay demo</title>\n'
                f"<style><![CDATA[\n{chr(10).join(css)}\n]]></style>\n" + "\n".join(self.parts) + "\n</svg>\n")


def shown(*intervals):
    """Frames that show an element from each start up to each end (in seconds) and hide it otherwise."""
    frames = [(0, {"opacity": 0})]
    for start, end in intervals:
        frames += [(max(0, start - STEP), {"opacity": 0}), (start, {"opacity": 1}),
                   (end - STEP, {"opacity": 1}), (end, {"opacity": 0})]
    return frames


def text(x, y, content, size, fill, family=MONO, weight="normal", anchor="start", extra=""):
    return (f'<text {extra} x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" xml:space="preserve" '
            f'style="white-space:pre">{escape(content)}</text>')


speed = Speed()
dictionary = Dictionary.load()
words = solve(BOARD, dictionary)

# The timeline, following game() and swipe() at the default speed.
HOTKEY = 1.4
READ = HOTKEY + 0.35  # board read and solved
FOCUS = READ + 1.0  # after the 1 s countdown, the focus click between the middle tiles
t = FOCUS + 2 * speed.hold + 0.2
swipes = []
for word in words[:SHOWN]:
    t += speed.hold  # the cursor jumps to the first tile and settles
    down = t
    t += speed.hold
    arrivals = [down]
    for move in drag_points(CENTRES, word.path, speed.steps):
        t += len(move) * speed.step_delay
        arrivals.append(t)
        t += speed.dwell
    t += speed.hold
    swipes.append((word, arrivals, t))  # t is when the button comes up
    t += speed.word_delay
END = swipes[-1][2] + 1.8
DEADLINE = READ + (CLOCK - 1) - 1.5  # the clock reads 01:18 at READ; the bot stops 1.5 s early

found = set()


def status(prefix):
    if len(prefix) >= 3 and prefix in dictionary.words:
        return "found" if prefix in found else "new"
    return "none"


def stroke(state):
    return "#ff4d4d" if state == "none" else "#ffffff"  # the game draws a non-word's path in red


a = Animation()
a.add(f'<rect width="{W}" height="{H}" rx="16" fill="#0d1117"/>')

# Terminal.
a.add(f'<rect x="{TX}" y="{TY}" width="{TW}" height="{TH}" rx="10" fill="#1e1e1e" stroke="#30363d"/>'
      f'<path d="M{TX} {TY + 10}a10 10 0 0 1 10 -10h{TW - 20}a10 10 0 0 1 10 10v18h-{TW}z" fill="#2d2d2d"/>'
      + "".join(f'<circle cx="{TX + 18 + 18 * i}" cy="{TY + 14}" r="6" fill="{c}"/>'
                for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")))
      + text(TX + TW / 2, TY + 19, "zsh — Word-Hunt", 12, "#9a9a9a", SANS, anchor="middle"))
line_y = [TY + 52 + 19 * i for i in range(15)]
a.add(text(TX + 16, line_y[0], "$ ", 13, "#6a9955") + text(TX + 32, line_y[0], ".venv/bin/python -m autoplay", 13, "#d4d4d4"))
a.add(text(TX + 16, line_y[1], f"Word Hunt autoplay: {len(dictionary.words):,} words loaded.", 13, "#d4d4d4"))
a.add(text(TX + 16, line_y[2], "Esc, the hotkey, or touching the mouse stops a game.", 13, "#d4d4d4"))
a.add(text(TX + 16, line_y[4], "READY: start a Word Hunt game, then press ctrl+alt+p. Ctrl+C quits.", 13, "#d4d4d4"))
a.add(text(TX + 16, line_y[6], "Read the board in 0.35 s:", 13, "#d4d4d4", extra='id="{id}"'), shown((READ, END)))
notes = [f"{len(words)} words, {sum(w.points for w in words):,} points on the board", "game clock 01:18", "", ""]
for row in range(SIZE):
    letters = " ".join(BOARD[row * SIZE:(row + 1) * SIZE].upper())
    a.add(text(TX + 16, line_y[7 + row], f"    {letters}      {notes[row]}", 13, "#d4d4d4", extra='id="{id}"'),
          shown((READ, END)))
a.add(text(TX + 16, line_y[11], "  starting in 1.0 s", 13, "#d4d4d4", extra='id="{id}"'), shown((READ, READ + 0.5)))
a.add(text(TX + 16, line_y[11], "  starting in 0.5 s", 13, "#d4d4d4", extra='id="{id}"'), shown((READ + 0.5, FOCUS)))
score = 0
for n, (word, arrivals, up) in enumerate(swipes, 1):
    score += word.points
    until = swipes[n][2] if n < len(swipes) else END
    line = (f"  {n:3d}/{len(words)}  {word.word.upper():<12} +{word.points:<5} score {score:>7,}"
            f"   {DEADLINE - up:4.1f} s left")
    a.add(text(TX + 16, line_y[11], line, 13, "#d4d4d4", extra='id="{id}"'), shown((up, until)))

# The three steps, lit up in turn.
a.add(f'<rect x="{NX}" y="{NY}" width="{NW}" height="{NH}" rx="10" fill="#161b22" stroke="#30363d"/>'
      + text(NX + 20, NY + 30, "What happens when you press the hotkey", 13, "#8b949e", SANS))
steps = [("Press ctrl+alt+p once the game has started", (HOTKEY - 0.3, READ)),
         ("It screenshots the board, reads it with Apple Vision and solves it", (READ, FOCUS)),
         ("It swipes the best words first, until the clock is about to run out", (FOCUS, END - 0.6))]
for i, (label, active) in enumerate(steps):
    y = NY + 66 + 46 * i
    a.add(f'<rect id="{{id}}" x="{NX + 10}" y="{y - 20}" width="{NW - 20}" height="38" rx="8" fill="#1f6feb" fill-opacity="0.18"/>',
          shown(active))
    a.add(f'<circle cx="{NX + 34}" cy="{y - 1}" r="12" fill="#30363d"/>')
    a.add(f'<circle id="{{id}}" cx="{NX + 34}" cy="{y - 1}" r="12" fill="#2ea043"/>', shown(active))
    a.add(text(NX + 34, y + 4, str(i + 1), 13, "#ffffff", SANS, "bold", "middle"))
    a.add(text(NX + 58, y + 4, label, 14, "#e6edf3", SANS))

# Phone, styled after the game.
a.add(f'<defs><pattern id="maze" width="22" height="22" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
      f'<rect width="22" height="22" fill="#5d9a59"/><path d="M0 6h22M0 17h22M6 0v6M17 6v11" stroke="#68a764" stroke-width="5"/>'
      f'</pattern><linearGradient id="wood" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fbe2b4"/>'
      f'<stop offset="1" stop-color="#efc27c"/></linearGradient>'
      f'<clipPath id="screen"><rect x="{SX}" y="{SY}" width="{SW}" height="{SH}" rx="34"/></clipPath></defs>')
a.add(f'<rect x="{PX}" y="{PY}" width="{PW}" height="{PH}" rx="42" fill="#111" stroke="#3a3a3a" stroke-width="2"/>'
      f'<rect x="{SX}" y="{SY}" width="{SW}" height="{SH}" rx="34" fill="url(#maze)"/>'
      f'<rect x="{SX + SW / 2 - 40}" y="{SY + 10}" width="80" height="22" rx="11" fill="#000"/>')
banner_x, banner_y = SX + 16, SY + 48
a.add(f'<rect x="{banner_x}" y="{banner_y}" width="{SW - 32}" height="64" rx="3" fill="#fff"/>'
      f'<circle cx="{banner_x + 32}" cy="{banner_y + 32}" r="21" fill="#3d6fb4"/>'
      f'<circle cx="{banner_x + 32}" cy="{banner_y + 26}" r="8" fill="#f2c9a0"/>'
      f'<path d="M{banner_x + 18} {banner_y + 46}a14 12 0 0 1 28 0z" fill="#f2c9a0"/>')
score, starts = 0, [0] + [up for _, _, up in swipes]
for n, start in enumerate(starts):
    if n:
        score += swipes[n - 1][0].points
    until = starts[n + 1] if n + 1 < len(starts) else END
    a.add(f'<g id="{{id}}">' + text(banner_x + 62, banner_y + 25, f"WORDS: {n}", 11, "#111", SANS, "800")
          + text(banner_x + 62, banner_y + 50, f"SCORE: {score:04d}", 21, "#111", SANS, "800") + "</g>",
          shown((start, until)))
a.add(f'<rect x="{SX + SW - 74}" y="{banner_y + 70}" width="58" height="22" rx="6" fill="#3b6a36"/>')
for s in range(math.ceil(END)):
    a.add(text(SX + SW - 45, banner_y + 85, f"{(CLOCK - s) // 60:02d}:{(CLOCK - s) % 60:02d}", 12, "#fff", SANS,
               "bold", "middle", 'id="{id}"'), shown((s, min(s + 1, END))))
a.add(f'<rect x="{BX}" y="{BY}" width="{BOARD_SIZE}" height="{BOARD_SIZE}" rx="12" fill="#415a40" '
      f'stroke="#8ee588" stroke-width="4"/>')
for x, y in CENTRES:
    a.add(f'<rect x="{x - TILE / 2:.1f}" y="{y - TILE / 2 + 3:.1f}" width="{TILE:.1f}" height="{TILE:.1f}" rx="6" fill="#b8894a"/>'
          f'<rect x="{x - TILE / 2:.1f}" y="{y - TILE / 2:.1f}" width="{TILE:.1f}" height="{TILE:.1f}" rx="6" fill="url(#wood)"/>')

# Each swipe: tiles light up as they're reached, the word pill above the board, and the path.
overlays, pills, paths = [], [], []
for word, arrivals, up in swipes:
    prefixes = [word.word[:k + 1] for k in range(len(word.word))]
    states = [status(p) for p in prefixes]
    for k, (r, c) in enumerate(word.path):
        x, y = CENTRES[r * SIZE + c]
        frames = [(0, {"opacity": 0, "fill": COLOURS[states[k]]}), (arrivals[k] - STEP, {"opacity": 0}),
                  (arrivals[k], {"opacity": 1})]
        for j in range(k + 1, len(arrivals)):
            frames += [(arrivals[j] - STEP, {"fill": COLOURS[states[j - 1]]}), (arrivals[j], {"fill": COLOURS[states[j]]})]
        frames += [(up, {"opacity": 1}), (up + 0.12, {"opacity": 0})]
        overlays.append((f'<rect id="{{id}}" x="{x - TILE / 2:.1f}" y="{y - TILE / 2:.1f}" width="{TILE:.1f}" '
                         f'height="{TILE:.1f}" rx="6" fill="#fff"/>', frames))
    for k, (prefix, state) in enumerate(zip(prefixes, states)):
        label = prefix.upper() + (f" (+{points(len(prefix))})" if state == "new" else "")
        width = 9.5 * len(label) + 26
        until = arrivals[k + 1] if k + 1 < len(arrivals) else up + 0.25
        pills.append((f'<g id="{{id}}"><rect x="{SX + SW / 2 - width / 2:.1f}" y="{BY - 46}" width="{width:.1f}" '
                      f'height="28" rx="14" fill="{COLOURS[state]}"/>'
                      + text(SX + SW / 2, BY - 26, label, 15, "#1a1a1a", SANS, "800", "middle") + "</g>",
                      shown((arrivals[k], until))))
    corners = [CENTRES[r * SIZE + c] for r, c in word.path]
    lengths = [0.0]
    for (x1, y1), (x2, y2) in zip(corners, corners[1:]):
        lengths.append(lengths[-1] + math.hypot(x2 - x1, y2 - y1))
    total = lengths[-1]
    frames = [(0, {"opacity": 0, "stroke-dashoffset": f"{total:.1f}", "stroke": stroke(states[0])}),
              (arrivals[0] - STEP, {"opacity": 0}), (arrivals[0], {"opacity": 0.75})]
    for k in range(1, len(arrivals)):
        frames += [(arrivals[k - 1] + (speed.dwell if k > 1 else speed.hold), {"stroke-dashoffset": f"{total - lengths[k - 1]:.1f}"}),
                   (arrivals[k] - STEP, {"stroke": stroke(states[k - 1])}),
                   (arrivals[k], {"stroke-dashoffset": f"{total - lengths[k]:.1f}", "stroke": stroke(states[k])})]
    frames += [(up, {"opacity": 0.75}), (up + 0.12, {"opacity": 0})]
    paths.append((f'<polyline id="{{id}}" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in corners)}" fill="none" '
                  f'stroke-width="12" stroke-linecap="round" stroke-linejoin="round" '
                  f'stroke-dasharray="{total:.1f} {total + 1:.1f}"/>', frames))
    found.add(word.word)
for markup, frames in overlays:
    a.add(markup, frames)
for i, (x, y) in enumerate(CENTRES):
    a.add(text(x, y + 9, BOARD[i].upper(), 27, "#1b1b1b", SANS, "800", "middle"))
for markup, frames in pills + paths:
    a.add(markup, frames)

# The cursor: it jumps to the first tile of each word, then drags through the tile centres.
rest = (SX + 0.82 * SW, SY + 0.93 * SH)
gap = ((CENTRES[5][0] + CENTRES[10][0]) / 2, (CENTRES[5][1] + CENTRES[10][1]) / 2)
moves = [(0, rest), (FOCUS - STEP, rest), (FOCUS, gap)]
pressed = [(FOCUS + speed.hold, FOCUS + 2 * speed.hold)]
here = gap
for word, arrivals, up in swipes:
    first = CENTRES[word.path[0][0] * SIZE + word.path[0][1]]
    moves += [(arrivals[0] - speed.hold - STEP, here), (arrivals[0] - speed.hold, first), (arrivals[0] + speed.hold, first)]
    for (r, c), at in list(zip(word.path, arrivals))[1:]:
        here = CENTRES[r * SIZE + c]
        moves += [(at, here), (at + speed.dwell, here)]
    pressed.append((arrivals[0], up))
moves += [(swipes[-1][2] + 0.4, here), (END - 0.3, rest)]
moves = [(t, {"transform": f"translate({x:.1f}px,{y:.1f}px)"}) for t, (x, y) in moves]
# A soft circle under the cursor while the button is down; CSS animates each property on its own frames.
a.add('<circle id="{id}" r="13" fill="#ffffff" fill-opacity="0.35"/>', moves + shown(*pressed))
a.add('<path id="{id}" d="M0 0v17l4-4 3 7 3-1-3-7h5z" fill="#fff" stroke="#000" stroke-width="1.2" '
      'stroke-linejoin="round"/>', moves)

Path(__file__).with_name("demo.svg").write_text(a.svg(END))
print(f"wrote docs/demo.svg: {END:.1f} s loop, {len(swipes)} words")
