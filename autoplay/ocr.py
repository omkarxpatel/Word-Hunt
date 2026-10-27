"""Reading the board from a screenshot with Apple's Vision text recognition."""

import re
from typing import NamedTuple

import Quartz
import Vision
from Foundation import NSData

from .grid import SIZE, Box, Grid, fit, snap, vote

# Revision 2 of Vision's recognizer finds lone round letters (O, C, U...) that revision 3 skips.
REVISION = 2
# Shapes OCR reads as digits or symbols, but which can only be letters on a tile.
FIXES = {"0": "O", "1": "I", "l": "I", "i": "I", "|": "I", "!": "I"}
# Lowercase letters shaped like their capitals. Any other lowercase answer on an all-caps board is a misread.
SAME_SHAPE = set("cosuvwxz")
# Extra readings: tiles pasted side by side so Vision reads them like one word, which catches the
# letters it skips when they stand alone. (tile order, crop size as a fraction of the tile pitch),
# picked by benchmarking on generated boards in several fonts.
STRIPS = [
    ([r * SIZE + c for c in range(SIZE) for r in range(SIZE)], 0.7),  # column by column
    (list(range(SIZE * SIZE)), 0.7),  # row by row
    (list(range(SIZE * SIZE)), 0.85),
]
TIMER = re.compile(r"(0[01]):([0-5]\d)")  # the game shows "01:18"; the iPhone's clock never starts with 0
# The live board's tile pitch is about 18% of the screen width; the sample board on the
# "How to play" card and the boards drawn in chat bubbles are much smaller.
PITCH_RANGE = (0.12, 0.26)
MAX_UNREAD = 4  # more unreadable tiles than this means it isn't a live board (e.g. a bubble of '?' tiles)


class Reading(NamedTuple):
    letters: str  # 16 letters row by row, '?' for tiles nothing could read
    grid: Grid  # tile centres in image pixels
    seconds_left: int | None  # the game's countdown, if it was on screen


def load(path):
    data = NSData.dataWithContentsOfFile_(str(path))
    if data is None:
        raise FileNotFoundError(path)
    return Quartz.CGImageSourceCreateImageAtIndex(Quartz.CGImageSourceCreateWithData(data, None), 0, None)


def size(image):
    return Quartz.CGImageGetWidth(image), Quartz.CGImageGetHeight(image)


def recognize(image):
    """Text lines Vision finds in `image`: [(text, (x, y, w, h))] in pixels, origin top-left."""
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(False)
    request.setMinimumTextHeight_(0.005)  # the game clock's digits are under 1% of the screen height
    if REVISION in Vision.VNRecognizeTextRequest.supportedRevisions():
        request.setRevision_(REVISION)
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, {})
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"Vision text recognition failed: {error}")
    width, height = size(image)
    lines = []
    for observation in request.results():
        box = observation.boundingBox()  # normalised, origin bottom-left
        lines.append((observation.topCandidates_(1)[0].string(),
                      (box.origin.x * width, (1 - box.origin.y - box.size.height) * height,
                       box.size.width * width, box.size.height * height)))
    return lines


def letter(char):
    char = FIXES.get(char, char)
    if char.islower() and char not in SAME_SHAPE:
        return None
    char = char.upper()
    return char if "A" <= char <= "Z" else None


def letters(lines):
    """Letters with their positions. Vision boxes whole lines, so a line of several letters is split evenly."""
    found = []
    for text, (x, y, w, h) in lines:
        chars = [letter(c) for c in text if not c.isspace()]
        if not chars or None in chars:
            continue
        step = w / len(chars)
        found += [Box(c, x + (k + 0.5) * step, y + h / 2, h) for k, c in enumerate(chars)]
    return found


def tiles(image):
    """Square-ish rectangles Vision finds in `image`, as Boxes without a letter."""
    request = Vision.VNDetectRectanglesRequest.alloc().init()
    request.setMaximumObservations_(0)  # no limit
    request.setMinimumAspectRatio_(0.8)
    request.setMinimumSize_(0.08)
    request.setMinimumConfidence_(0.3)
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, {})
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"Vision rectangle detection failed: {error}")
    width, height = size(image)
    boxes = []
    for observation in request.results():
        box = observation.boundingBox()
        boxes.append(Box("", (box.origin.x + box.size.width / 2) * width,
                         (1 - box.origin.y - box.size.height / 2) * height, box.size.height * height))
    return boxes


def seconds_left(lines):
    for text, _ in lines:
        match = TIMER.fullmatch(text.strip())
        if match:
            return int(match[1]) * 60 + int(match[2])
    return None


def read_strip(image, grid, order, crop):
    """Letters for the tiles in `order`, read as one word. Only trusted when the letter count matches."""
    side = round(crop * (grid.dx + grid.dy) / 2)
    context = Quartz.CGBitmapContextCreate(None, side * len(order), side, 8, 0,
                                           Quartz.CGColorSpaceCreateDeviceRGB(),
                                           Quartz.kCGImageAlphaPremultipliedLast)
    for k, i in enumerate(order):
        x, y = grid.centre(i)
        tile = Quartz.CGImageCreateWithImageInRect(image, Quartz.CGRectMake(x - side / 2, y - side / 2, side, side))
        Quartz.CGContextDrawImage(context, Quartz.CGRectMake(k * side, 0, side, side), tile)
    strip = Quartz.CGBitmapContextCreateImage(context)
    chars = [letter(c) for text, _ in recognize(strip) for c in text if not c.isspace()]
    if len(chars) != len(order) or None in chars:
        return {}
    return dict(zip(order, chars))


def read(image, calibrated=None):
    """Find and read the board in `image`, or return None if there isn't one.

    `calibrated` is a Grid in image pixels, used when the board can't be found automatically.
    """
    lines = recognize(image)
    if any("how to play" in text.lower() for text, _ in lines):
        return None  # the start card, whose sample board isn't the game
    found = letters(lines)
    grid = fit(tiles(image)) or fit(found) or calibrated
    if grid is None or not PITCH_RANGE[0] < grid.dx / size(image)[0] < PITCH_RANGE[1]:
        return None
    readings = [snap(found, grid)] + [read_strip(image, grid, order, crop) for order, crop in STRIPS]
    board = vote(readings)
    if board.count("?") > MAX_UNREAD:
        return None
    return Reading(board, grid, seconds_left(lines))
