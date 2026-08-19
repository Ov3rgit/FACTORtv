# -*- coding: utf-8 -*-
"""
FACTORtv — overlay window plumbing.

Click-through, always-on-top panel windows plus the canvas wrapper that lets
panel-local draw code keep using screen coordinates.

Separate from overlay_common because this needs tk and the win32 API, and
overlay_common must stay importable by everything.

Why many small windows instead of one big one
---------------------------------------------
A single full-screen transparent window does not composite reliably over a
borderless DirectX game — it flickers, and on some driver versions it simply
does not appear. A cluster of small tool windows, each only as large as the
panel it draws, composites correctly and costs less to repaint. The price is
this bookkeeping.

The predecessor also carried a two-window "glass" mode for translucent panel
bodies. It is deliberately gone: it produced a one-frame mismatch on any
panel that resizes (radio cards appearing, a caption growing with its text)
because the content window repainted immediately while its backing layer only
repainted on flush. Single-window rendering is the known-good path.
"""
import ctypes
import time
from ctypes import wintypes

import tkinter as tk

from overlay_common import CHROMA, WIN_ALPHA

user32 = ctypes.windll.user32
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOMOVE_NOSIZE_NOACT = 0x1 | 0x2 | 0x10

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x80         # keep it out of the alt-tab list
WS_EX_NOACTIVATE = 0x8000000    # never steal focus from the game
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20        # clicks pass straight through


class TCanvas(object):
    """Canvas wrapper that subtracts a panel's origin.

    Draw code is written in whole-screen coordinates because that is how the
    layout is reasoned about; each panel window then only owns a small rect of
    that space. This shim does the translation so no draw call has to know
    which window it landed in.
    """

    __slots__ = ("cv", "ox", "oy")

    def __init__(self, cv, ox, oy):
        self.cv, self.ox, self.oy = cv, ox, oy

    def create_rectangle(self, x1, y1, x2, y2, **kw):
        return self.cv.create_rectangle(x1 - self.ox, y1 - self.oy,
                                        x2 - self.ox, y2 - self.oy, **kw)

    def create_oval(self, x1, y1, x2, y2, **kw):
        return self.cv.create_oval(x1 - self.ox, y1 - self.oy,
                                   x2 - self.ox, y2 - self.oy, **kw)

    def create_arc(self, x1, y1, x2, y2, **kw):
        return self.cv.create_arc(x1 - self.ox, y1 - self.oy,
                                  x2 - self.ox, y2 - self.oy, **kw)

    def create_text(self, x, y, **kw):
        return self.cv.create_text(x - self.ox, y - self.oy, **kw)

    def create_image(self, x, y, **kw):
        return self.cv.create_image(x - self.ox, y - self.oy, **kw)

    def create_line(self, *a, **kw):
        pts = [a[i] - (self.ox if i % 2 == 0 else self.oy) for i in range(len(a))]
        return self.cv.create_line(*pts, **kw)

    def create_polygon(self, *a, **kw):
        pts = [a[i] - (self.ox if i % 2 == 0 else self.oy) for i in range(len(a))]
        return self.cv.create_polygon(*pts, **kw)


class Panel(object):
    """One always-on-top, click-through window sized to a single UI panel."""

    def __init__(self, root, clickable=False):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", WIN_ALPHA)
            self.win.attributes("-transparentcolor", CHROMA)
        except Exception:
            pass
        self.win.configure(bg=CHROMA)
        self.cv = tk.Canvas(self.win, highlightthickness=0, bd=0, bg=CHROMA)
        self.cv.pack(fill="both", expand=True)
        self.win.withdraw()

        self.shown = False
        self.clickable = clickable
        self._geo = None
        self._raise_t = 0.0
        self.hwnd = None
        try:
            self.win.update_idletasks()
            h = user32.GetAncestor(self.win.winfo_id(), 2)
            ex = user32.GetWindowLongW(h, GWL_EXSTYLE)
            ex |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            # Everything except the settings/toggle furniture is transparent
            # to the mouse, so the overlay never eats a click meant for the
            # game — the single most important property of a racing overlay.
            if not clickable:
                ex |= WS_EX_TRANSPARENT | WS_EX_LAYERED
            user32.SetWindowLongW(h, GWL_EXSTYLE, ex)
            self.hwnd = h
        except Exception:
            pass

    def place(self, x, y, w, h):
        """Move/resize, show if hidden, clear the canvas, return it to draw on."""
        w, h = max(1, int(w)), max(1, int(h))
        x, y = int(x), int(y)
        # A PANEL PLACED OFF THE SCREEN IS A PANEL NOBODY CAN SEE, and the
        # division's mark was reported cut off by the right-hand edge twice.
        # Every panel derives its position from `game_rect`, so each of them is
        # one bad rect away from the same fault — and there are twenty of them.
        # Clamping HERE fixes the class of bug rather than the instance: this is
        # the only place in the product that actually puts a window somewhere.
        #
        # THE VIRTUAL DESKTOP, NOT THE PRIMARY MONITOR. `GetSystemMetrics(0)` is
        # the primary display, and a game on a second monitor legitimately draws
        # outside it — clamping to the primary would drag every panel off the
        # game and onto the wrong screen, which is a worse bug than the one being
        # fixed.
        x, y = clamp_to_screen(x, y, w, h)
        geo = (x, y, w, h)
        moved = geo != self._geo
        if moved:
            self.win.geometry("%dx%d+%d+%d" % (w, h, x, y))
            self.cv.config(width=w, height=h)
            self._geo = geo
        self.cv.delete("all")
        if not self.shown:
            self.win.deiconify()
            self.shown = True
            moved = True
        # Assert z-order on a slow cadence, not every frame. Re-raising ~30
        # windows at 20 Hz is ~600 z-order changes a second, each forcing a
        # repaint — that alone was a visible source of flicker. The game only
        # steals topmost occasionally, so twice a second is ample.
        now = time.time()
        if moved or now - self._raise_t > 0.5:
            self._raise_t = now
            if self.hwnd:
                user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                    SWP_NOMOVE_NOSIZE_NOACT)
        return self.cv

    def canvas_at(self, x, y):
        """A TCanvas translated to this panel's origin."""
        return TCanvas(self.cv, x, y)

    def hide(self):
        if self.shown:
            self.win.withdraw()
            self.shown = False

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass


def client_rect(hwnd):
    """The game's DRAWING area in screen coordinates, or None.

    THE WINDOW RECT IS NOT THE PICTURE, and the difference is what put the
    division's mark half off the screen. A windowed rF2 carries a title bar
    and, on Windows 10/11, invisible resize borders that sit OUTSIDE the
    visible frame — so a 1920-wide window on a 1920-wide screen reports a
    rect several pixels wider than the display and starting at a negative x.
    Every panel that hugs the right-hand edge is then placed past the edge of
    the screen and clipped by it, which is exactly what the user photographed.

    In borderless and fullscreen the client rect IS the window rect, so this
    changes nothing in the mode most of this was built against — which is
    also why the bug survived so long.
    """
    try:
        r = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(r)):
            return None
        w, h = r.right - r.left, r.bottom - r.top
        if w < 640 or h < 400:
            return None
        pt = wintypes.POINT(r.left, r.top)
        if not user32.ClientToScreen(hwnd, ctypes.byref(pt)):
            return None
        return (pt.x, pt.y, w, h)
    except Exception:
        return None


def find_game_window(titles=("rFactor2",), class_hint=None):
    """Locate the rFactor 2 window so the overlay can lock to it.

    Matches on the window TITLE and requires a sensible size, because rF2
    puts up a small launcher/loading window first and anchoring to that puts
    every panel in the wrong place for the first few seconds of a session.
    """
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value or ""
        low = title.lower()
        if not any(t.lower() in low for t in titles):
            return True
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        if w < 640 or h < 400:
            return True          # the launcher, not the game
        found.append(client_rect(hwnd) or (r.left, r.top, w, h))
        return False

    try:
        user32.EnumWindows(cb, 0)
    except Exception:
        pass
    return found[0] if found else None


def screen_size():
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


# The whole desktop across every monitor: SM_XVIRTUALSCREEN and friends. Cached
# because `Panel.place` asks on every geometry change and the answer only moves
# when a display is plugged in.
_SM_VIRTUAL = (76, 77, 78, 79)
_virtual = None


def virtual_screen():
    """(x, y, w, h) of the whole desktop, or (0, 0, 0, 0) if it cannot be read.

    ZERO MEANS "DO NOT CLAMP", which is the honest failure here: a bad reading
    would move every panel, and a panel in the wrong place is worse than a panel
    that hangs off an edge.
    """
    global _virtual
    if _virtual is None:
        try:
            _virtual = tuple(user32.GetSystemMetrics(m) for m in _SM_VIRTUAL)
            if _virtual[2] < 640 or _virtual[3] < 400:
                _virtual = (0, 0, 0, 0)
        except Exception:
            _virtual = (0, 0, 0, 0)
    return _virtual


def clamp_to_screen(x, y, w, h, bounds=None):
    """Pull a panel back onto the desktop. Returns (x, y).

    A panel wider or taller than the desktop keeps its ORIGIN rather than being
    centred: the layout law is that everything hugs an edge, and the top-left of
    an oversized panel is the part with the labels on it.
    """
    vx, vy, vw, vh = bounds if bounds is not None else virtual_screen()
    if not vw or not vh:
        return x, y                 # unknown bounds: do not move anything
    if w < vw:
        x = max(vx, min(x, vx + vw - w))
    if h < vh:
        y = max(vy, min(y, vy + vh - h))
    return x, y


def key_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)
