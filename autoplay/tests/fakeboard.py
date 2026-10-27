"""Draws fake Word Hunt screens for the OCR tests (macOS only, uses AppKit)."""

import AppKit
from Foundation import NSMakeRect


def rgb(r, g, b):
    return AppKit.NSColor.colorWithDeviceRed_green_blue_alpha_(r, g, b, 1)


def render(letters, path, width=652, height=1440, font="Helvetica-Bold", board_top=0.45, pitch=0.21, timer="1:18",
           tile=(0.96, 0.89, 0.74), ink=(0.1, 0.1, 0.1), background=(0.36, 0.62, 0.36)):
    """Save a phone-shaped PNG with a 4x4 board of `letters`; returns the true tile centres in pixels (top-left origin)."""
    rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, width, height, 8, 4, True, False, AppKit.NSDeviceRGBColorSpace, 0, 0)
    AppKit.NSGraphicsContext.saveGraphicsState()
    AppKit.NSGraphicsContext.setCurrentContext_(AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))

    def text(s, size, cx, cy, colour):
        attrs = {AppKit.NSFontAttributeName: AppKit.NSFont.fontWithName_size_(font, size),
                 AppKit.NSForegroundColorAttributeName: rgb(*colour)}
        string = AppKit.NSAttributedString.alloc().initWithString_attributes_(s, attrs)
        w, h = string.size()
        string.drawAtPoint_((cx - w / 2, height - cy - h / 2))  # AppKit's origin is bottom-left

    rgb(*background).setFill()
    AppKit.NSRectFill(NSMakeRect(0, 0, width, height))
    text(f"SCORE: 0   WORDS: 0", 0.035 * width, width / 2, 0.12 * height, (1, 1, 1))
    text(timer, 0.06 * width, width / 2, 0.2 * height, (1, 1, 1))

    pitch = pitch * width
    left = (width - 4 * pitch) / 2
    top = board_top * height
    centres = []
    for i, letter in enumerate(letters):
        r, c = divmod(i, 4)
        cx, cy = left + (c + 0.5) * pitch, top + (r + 0.5) * pitch
        centres.append((cx, cy))
        size = 0.86 * pitch
        rgb(*tile).setFill()
        AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(cx - size / 2, height - cy - size / 2, size, size), 0.12 * size, 0.12 * size).fill()
        text(letter.upper(), 0.5 * pitch, cx, cy, ink)

    AppKit.NSGraphicsContext.restoreGraphicsState()
    png = rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {})
    png.writeToFile_atomically_(str(path), True)
    return centres
