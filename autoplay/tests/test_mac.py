import pytest

pytest.importorskip("Quartz")

from autoplay import mac  # noqa: E402

PHONE = mac.Window(7, 589, 142, 326, 720)
BOARD = (620, 440, 260, 260)  # x, y, w, h in screen points


def window(number, owner, x, y, w, h, layer=0, alpha=1.0, pid=1):
    return {"kCGWindowNumber": number, "kCGWindowOwnerName": owner, "kCGWindowOwnerPID": pid,
            "kCGWindowLayer": layer, "kCGWindowAlpha": alpha, "kCGWindowBounds": {"X": x, "Y": y, "Width": w, "Height": h}}


MIRRORING = window(7, "iPhone Mirroring", 589, 142, 326, 720, pid=42)


@pytest.fixture
def screen(monkeypatch):
    """The on-screen window list (frontmost first) that mac sees, and an unlocked session."""
    windows = []
    monkeypatch.setattr(mac, "_on_screen", lambda: windows)
    monkeypatch.setattr(mac, "_pids", lambda: {42})
    monkeypatch.setattr(mac.Quartz, "CGSessionCopyCurrentDictionary", lambda: {})
    return windows


def test_finds_the_phone_window_among_the_apps_other_windows(screen):
    screen += [window(1, "iPhone Mirroring", 0, 0, 1512, 33, pid=42),  # strip along the menu bar
               window(2, "iPhone Mirroring", 436, 176, 640, 662, pid=42),  # welcome window
               window(3, "Safari", 589, 142, 326, 720, pid=9),  # same shape, other app
               MIRRORING]
    assert mac.find_window() == PHONE


def test_no_window_when_iphone_mirroring_is_closed(screen):
    screen += [window(3, "Safari", 589, 142, 326, 720, pid=9)]
    assert mac.find_window() is None


def test_board_is_clear(screen):
    screen += [window(9, "Terminal", 0, 0, 500, 300),  # in front, but not over the board
               MIRRORING,
               window(10, "Code", 0, 0, 1512, 982)]  # behind
    assert mac.blocker(PHONE, BOARD) is None


@pytest.mark.parametrize("cover", [
    window(9, "Terminal", 600, 400, 500, 300),
    window(9, "Notch", 600, 400, 100, 100, layer=1000),  # a floating window
    window(9, "loginwindow", 0, 0, 1512, 982, layer=2004),
])
def test_board_is_covered(screen, cover):
    screen += [cover, MIRRORING]
    assert mac.blocker(PHONE, BOARD) == f"{cover['kCGWindowOwnerName']} is covering the board"


def test_ignores_invisible_windows_and_system_indicators(screen):
    screen += [window(8, "Window Server", 600, 400, 28, 28, layer=2147483630),
               window(9, "Code", 0, 0, 1512, 982, layer=26, alpha=0.0),
               MIRRORING]
    assert mac.blocker(PHONE, BOARD) is None


def test_window_moved_or_gone(screen):
    screen += [window(7, "iPhone Mirroring", 600, 142, 326, 720, pid=42)]
    assert mac.blocker(PHONE, BOARD) == "the iPhone Mirroring window moved"
    screen.clear()
    assert mac.blocker(PHONE, BOARD) == "the iPhone Mirroring window is gone"


def test_locked_screen(screen, monkeypatch):
    monkeypatch.setattr(mac.Quartz, "CGSessionCopyCurrentDictionary", lambda: {"CGSSessionScreenIsLocked": 1})
    screen += [MIRRORING]
    assert mac.blocker(PHONE, BOARD) == "the screen is locked"


def test_hotkeys():
    ctrl, alt, cmd, shift = (mac.MODIFIERS[m] for m in ("ctrl", "alt", "cmd", "shift"))
    assert mac.parse_hotkey("ctrl+alt+p") == (35, ctrl | alt)
    assert mac.parse_hotkey("Cmd + Shift + F5") == (96, cmd | shift)
    for bad in ("p", "ctrl+", "hyper+p", "ctrl+enter"):
        with pytest.raises(ValueError):
            mac.parse_hotkey(bad)
