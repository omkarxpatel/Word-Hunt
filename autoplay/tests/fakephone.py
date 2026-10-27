"""Test helper for test_gui.py: a borderless phone-shaped window that shows an image and logs its mouse events.

Usage: python fakephone.py IMAGE LOG
Writes LOG.ready ({"pid", "frame"}) once the window is up, rewrites LOG ([[kind, x, y], ...] in screen
points) after every mouse-up, and quits after a minute.
"""

import json
import os
import sys

import AppKit
import objc
from Foundation import NSTimer

X, Y = 200, 100  # where the window goes, in screen points from the top-left of the main display
image_path, log_path = sys.argv[1], sys.argv[2]
image = AppKit.NSImage.alloc().initWithContentsOfFile_(image_path)
rep = image.representations()[0]
W, H = rep.pixelsWide() / 2, rep.pixelsHigh() / 2  # drawn at 2x, like a Retina screenshot
events = []


class Recorder(AppKit.NSImageView):
    def acceptsFirstMouse_(self, event):
        return True

    @objc.python_method
    def record(self, kind, event):
        point = event.locationInWindow()  # origin bottom-left of the window
        events.append([kind, X + point.x, Y + H - point.y])

    def mouseDown_(self, event):
        self.record("down", event)

    def mouseDragged_(self, event):
        self.record("drag", event)

    def mouseUp_(self, event):
        self.record("up", event)
        with open(log_path, "w") as f:
            json.dump(events, f)


app = AppKit.NSApplication.sharedApplication()
app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
screen_height = AppKit.NSScreen.screens()[0].frame().size.height
window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
    AppKit.NSMakeRect(X, screen_height - Y - H, W, H), AppKit.NSWindowStyleMaskBorderless,
    AppKit.NSBackingStoreBuffered, False)
view = Recorder.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, W, H))
view.setImage_(image)
view.setImageScaling_(AppKit.NSImageScaleAxesIndependently)
window.setContentView_(view)
window.orderFrontRegardless()
app.activateIgnoringOtherApps_(True)
with open(log_path + ".ready", "w") as f:
    json.dump({"pid": os.getpid(), "frame": [X, Y, W, H]}, f)
NSTimer.scheduledTimerWithTimeInterval_repeats_block_(60, False, lambda timer: app.terminate_(None))
app.run()
