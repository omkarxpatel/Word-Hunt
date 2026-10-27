"""Everything that talks to macOS: the iPhone Mirroring window, screenshots, synthetic mouse events,
and the system-wide listener for the hotkey and the abort triggers."""

import os
import subprocess
import tempfile
import threading
from typing import NamedTuple

import AppKit
import Quartz
# Used on the listener thread, so resolved here at import: pyobjc's lazy name lookup isn't thread-safe,
# and a lookup racing the main thread can raise inside the callback.
from Quartz import (
    CFRunLoopRun, CGEventGetFlags, CGEventGetIntegerValueField, CGEventTapEnable, kCGEventKeyDown,
    kCGEventLeftMouseDragged, kCGEventMouseMoved, kCGEventSourceUserData, kCGEventTapDisabledByTimeout,
    kCGEventTapDisabledByUserInput, kCGKeyboardEventAutorepeat, kCGKeyboardEventKeycode, kCGMouseEventDeltaX,
    kCGMouseEventDeltaY,
)

from . import ocr

BUNDLE_ID = "com.apple.ScreenContinuity"  # iPhone Mirroring
EVENT_TAG = 0x5748  # stamped on our own mouse events so the listener can tell them apart from yours
ESCAPE = 53
# Key codes are physical key positions (US layout names).
KEYCODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11, "q": 12,
    "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23,
    "9": 25, "7": 26, "8": 28, "0": 29, "o": 31, "u": 32, "i": 34, "p": 35, "l": 37, "j": 38, "k": 40,
    "n": 45, "m": 46, "space": 49, "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
}
MODIFIERS = {
    "ctrl": Quartz.kCGEventFlagMaskControl, "control": Quartz.kCGEventFlagMaskControl,
    "alt": Quartz.kCGEventFlagMaskAlternate, "opt": Quartz.kCGEventFlagMaskAlternate,
    "option": Quartz.kCGEventFlagMaskAlternate, "cmd": Quartz.kCGEventFlagMaskCommand,
    "command": Quartz.kCGEventFlagMaskCommand, "shift": Quartz.kCGEventFlagMaskShift,
}
ALL_MODIFIERS = (Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskAlternate
                 | Quartz.kCGEventFlagMaskCommand | Quartz.kCGEventFlagMaskShift)


class Window(NamedTuple):
    id: int
    x: float  # screen points, origin at the top-left of the main display
    y: float
    w: float
    h: float


def parse_hotkey(text):
    """'ctrl+alt+p' → (key code, modifier flags)."""
    *mods, key = text.lower().replace(" ", "").split("+")
    if key not in KEYCODES or not mods or any(m not in MODIFIERS for m in mods):
        raise ValueError(f"can't use {text!r} as a hotkey; use modifiers plus a key, like ctrl+alt+p")
    flags = 0
    for m in mods:
        flags |= MODIFIERS[m]
    return KEYCODES[key], flags


def _on_screen():
    """On-screen windows, frontmost first."""
    return Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID) or []


def _pids():
    return {app.processIdentifier()
            for app in AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_(BUNDLE_ID)}


def find_window():
    """The iPhone Mirroring phone window, or None if it isn't on screen."""
    pids = _pids()
    best = None
    for info in _on_screen():
        b = info["kCGWindowBounds"]
        # The phone window is tall; this skips the app's welcome window and the strips along the menu bar.
        if (info["kCGWindowOwnerPID"] in pids and info["kCGWindowLayer"] == 0
                and b["Width"] and 1.6 < b["Height"] / b["Width"] < 2.6):
            window = Window(info["kCGWindowNumber"], b["X"], b["Y"], b["Width"], b["Height"])
            if best is None or window.w * window.h > best.w * best.h:
                best = window
    return best


def blocker(window, rect):
    """Why a swipe inside `rect` (x, y, w, h in screen points) wouldn't reach `window`, or None if it would."""
    if (Quartz.CGSessionCopyCurrentDictionary() or {}).get("CGSSessionScreenIsLocked"):
        return "the screen is locked"
    x, y, w, h = rect
    for info in _on_screen():  # frontmost first, so everything before our window is in front of it
        b = info["kCGWindowBounds"]
        if info["kCGWindowNumber"] == window.id:
            if (b["X"], b["Y"], b["Width"], b["Height"]) != (window.x, window.y, window.w, window.h):
                return "the iPhone Mirroring window moved"
            return None
        # Any visible window over the board would catch the swipes: another app, a floating panel,
        # a notification. macOS's own status indicators (owned by the Window Server) don't take clicks.
        if (info.get("kCGWindowAlpha", 1) > 0 and info.get("kCGWindowOwnerName") != "Window Server"
                and b["X"] < x + w and x < b["X"] + b["Width"] and b["Y"] < y + h and y < b["Y"] + b["Height"]):
            return f"{info.get('kCGWindowOwnerName') or 'another window'} is covering the board"
    return "the iPhone Mirroring window is gone"


def activate():
    """Bring iPhone Mirroring to the front."""
    subprocess.run(["open", "-b", BUNDLE_ID], capture_output=True)


def capture(window):
    """Screenshot of `window` as a CGImage. Needs Screen Recording permission."""
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "window.png")
        # -o: no shadow, -a: not the windows attached to it, so the image covers exactly the window.
        subprocess.run(["screencapture", "-x", "-o", "-a", "-l", str(window.id), path],
                       check=True, capture_output=True, timeout=10)
        return ocr.load(path)


def cursor():
    point = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
    return point.x, point.y


class Mouse:
    """Posts left-button mouse events. Needs Accessibility permission."""

    def __init__(self):
        self.source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
        Quartz.CGEventSourceSetUserData(self.source, EVENT_TAG)

    def _post(self, kind, x, y):
        event = Quartz.CGEventCreateMouseEvent(self.source, kind, (x, y), Quartz.kCGMouseButtonLeft)
        if kind in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
            Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventClickState, 1)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def move(self, x, y):
        self._post(Quartz.kCGEventMouseMoved, x, y)

    def down(self, x, y):
        self._post(Quartz.kCGEventLeftMouseDown, x, y)

    def drag(self, x, y):
        self._post(Quartz.kCGEventLeftMouseDragged, x, y)

    def up(self, x, y):
        self._post(Quartz.kCGEventLeftMouseUp, x, y)


class Listener:
    """Watches the keyboard and mouse system-wide. Needs Input Monitoring permission.

    The hotkey sets `hotkey`. While armed, Esc, the hotkey, or any mouse or trackpad input of yours
    sets `abort` and `reason`; the bot's own tagged events are ignored.
    """

    MOVE_LIMIT = 50  # points of your own mouse travel that count as grabbing it; a resting hand drifts less

    def __init__(self, hotkey):
        self.keycode, self.flags = hotkey
        self.hotkey = threading.Event()
        self.abort = threading.Event()
        self.reason = None
        self.armed = False
        self._travel = 0
        self._tap = None
        started = threading.Event()
        threading.Thread(target=self._run, args=(started,), daemon=True).start()
        started.wait(5)
        if self._tap is None:
            raise PermissionError("couldn't start listening to the keyboard and mouse (Input Monitoring)")

    def arm(self):
        self.abort.clear()
        self.reason = None
        self._travel = 0
        self.armed = True

    def disarm(self):
        self.armed = False

    def _run(self, started):
        mask = 0
        for kind in (Quartz.kCGEventKeyDown, Quartz.kCGEventMouseMoved, Quartz.kCGEventLeftMouseDown,
                     Quartz.kCGEventLeftMouseDragged, Quartz.kCGEventRightMouseDown, Quartz.kCGEventScrollWheel):
            mask |= Quartz.CGEventMaskBit(kind)
        # Listen-only, so a busy Python thread can never hold up your typing.
        self._tap = Quartz.CGEventTapCreate(Quartz.kCGSessionEventTap, Quartz.kCGHeadInsertEventTap,
                                            Quartz.kCGEventTapOptionListenOnly, mask, self._event, None)
        if self._tap is not None:
            source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
            Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(self._tap, True)
        started.set()
        if self._tap is not None:
            CFRunLoopRun()

    def _event(self, proxy, kind, event, refcon):
        try:
            self._handle(kind, event)
        except Exception as error:  # an exception here would end the listener thread and lose the abort
            self._stop(f"listener error: {error}")
        return event

    def _handle(self, kind, event):
        if kind in (kCGEventTapDisabledByTimeout, kCGEventTapDisabledByUserInput):
            CGEventTapEnable(self._tap, True)
        elif CGEventGetIntegerValueField(event, kCGEventSourceUserData) == EVENT_TAG:
            pass  # one of our own swipes
        elif kind == kCGEventKeyDown:
            code = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            is_hotkey = (code == self.keycode
                         and CGEventGetFlags(event) & ALL_MODIFIERS == self.flags
                         and not CGEventGetIntegerValueField(event, kCGKeyboardEventAutorepeat))
            if self.armed and code == ESCAPE:
                self._stop("Esc pressed")
            elif self.armed and is_hotkey:
                self._stop("hotkey pressed")
            elif is_hotkey:
                self.hotkey.set()
        elif self.armed:
            if kind in (kCGEventMouseMoved, kCGEventLeftMouseDragged):
                self._travel += (abs(CGEventGetIntegerValueField(event, kCGMouseEventDeltaX))
                                 + abs(CGEventGetIntegerValueField(event, kCGMouseEventDeltaY)))
                if self._travel > self.MOVE_LIMIT:
                    self._stop("you moved the mouse")
            else:
                self._stop("you clicked or scrolled")

    def _stop(self, reason):
        if not self.abort.is_set():
            self.reason = reason
            self.abort.set()


def missing_permissions(post, listen, capture):
    """Names of the needed privacy permissions this process lacks. Asks macOS to prompt for each one."""
    checks = [
        ("Accessibility", post, Quartz.CGPreflightPostEventAccess, Quartz.CGRequestPostEventAccess),
        ("Input Monitoring", listen, Quartz.CGPreflightListenEventAccess, Quartz.CGRequestListenEventAccess),
        ("Screen Recording", capture, Quartz.CGPreflightScreenCaptureAccess, Quartz.CGRequestScreenCaptureAccess),
    ]
    missing = []
    for name, needed, have, request in checks:
        if needed and not have():
            request()
            missing.append(name)
    return missing


def terminal_app():
    names = {"Apple_Terminal": "Terminal", "iTerm.app": "iTerm", "vscode": "Visual Studio Code"}
    return names.get(os.environ.get("TERM_PROGRAM"), "the app you run this from")
