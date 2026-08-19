# -*- coding: utf-8 -*-
"""
FACTORtv — the engine.

Owns the tk root, the panel windows, the tick loop and the settings. Composes
the drawing mixins into one `Overlay` object so they can all share `self`
without any of them importing each other.

    python factor_tv.py

Design notes
------------
Panels are created LAZILY and cached by name. Creating ~10 always-on-top
windows up front costs a visible stall on launch and leaves empty windows
flickering in the corner before the first session loads; creating each the
first time something wants to draw it means an overlay with no relative panel
simply never makes that window.

The tick is a tk `after` callback rather than a thread. Every draw call has to
happen on the tk thread anyway, and a worker thread posting draw commands adds
a queue and a class of races for no gain — the shared-memory read is a memcpy,
not IO.

The overlay never takes focus and never eats a click: every panel is created
click-through (WS_EX_TRANSPARENT), so the mouse belongs to the game at all
times. Hotkeys are polled with GetAsyncKeyState instead of being bound to a
tk window, for the same reason.
"""
import json
import os
import sys
import time
import tkinter as tk
import tkinter.font as tkfont

import era as era_mod
import rf2_session as RS
from overlay_common import (TH, UI, UPDATE_MS, VK_C, VK_CONTROL, VK_D, VK_E,
                            VK_LBUTTON, VK_M, VK_N, VK_O, VK_Q, VK_R, VK_S,
                            VK_SHIFT, VK_T, VK_V, VK_Y)
import career as career_mod
import season as season_mod
from overlay_booth import BoothMixin
from overlay_dash import DashMixin, FuelModel
from overlay_draw import DrawMixin
from overlay_radio import RadioMixin
from overlay_rival import RivalMixin
from stings import Stings
from tts import Tts
from overlay_panels import PanelsMixin
from overlay_panel import (Panel, find_game_window, key_down, screen_size,
                           virtual_screen)

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(_DIR, "_settings.json")

DEFAULTS = {
    "display_name": "",       # what the booth calls you (rF2 says "Your Name")
    "results_dir": "",        # rF2 result XMLs; found automatically if blank
    "career": "",             # active career slug (see season.py); "" = none
    "career_record": True,    # count completed races towards the championship
    "show_dash": True,
    "show_tower": True,
    "show_relative": True,
    "tower_rows": 16,
    "relative_rows": 3,
    "tower_interval": True,   # interval to car ahead vs gap to leader
    "scale": 1.25,          # global UI scale — everything reads small at 1.0
    "booth": True,            # commentary on/off
    "radio": True,            # team radio on/off
    "rivals": True,           # rival driver radio on/off
    "show_sectors": True,
    "show_map": True,
    # 0.65 RATHER THAN 0.9, on his own listening: "the intro race engineer
    # is very soft, can we have the base volume at 65". A default nobody
    # has to go and find is worth more than a default that is technically
    # louder, and a first-run introduction is the first thing anybody
    # hears — if that is quiet, the product is quiet.
    "volume": 0.65,
}


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    return s


def save_settings(s):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass


class Overlay(DrawMixin, PanelsMixin, DashMixin, BoothMixin, RadioMixin,
              RivalMixin):

    def __init__(self):
        self.cfg = load_settings()
        self.root = tk.Tk()
        self.root.withdraw()          # the root is never shown; panels are

        self._fonts()
        self.logo_img = self._load_logo()
        self.panels = {}
        self._used_this_frame = set()

        self.tracker = RS.SessionTracker(
            display_name=self.cfg.get("display_name") or None)
        self.fuel_model = FuelModel()
        self.booth_enabled = self.cfg.get("booth", True)
        self.tts = Tts(volume=self.cfg.get("volume", 0.9))
        self.radio_enabled = self.cfg.get("radio", True)
        # Pre-render the stings on a background thread so lights-out and
        # incident reactions can fire with no render latency.
        self.sting_bank = Stings(self.tts)
        # Career history, folded from rF2's own result XMLs. Scanned on a
        # background thread for the same reason the stings are: a cold cache
        # is a second or two of parsing and the overlay must be up before
        # then. Anything that reads it copes with it not being ready.
        self.career = career_mod.History()
        self.career.scan_async(career_mod.find_results_dir(self.cfg))
        # The active season, if one is loaded. A career that has been deleted
        # or renamed out from under the settings file simply resolves to
        # None, and everything downstream treats that as "no career".
        self.season = season_mod.load(self.cfg.get("career") or "")
        self.season_record = self.cfg.get("career_record", True)
        self._menu_offset = 0
        # A career can be raced under a driver's own name. Applied to the
        # tracker, which is what substitutes rF2's "Your Name" everywhere —
        # booth, engineer and timing tower all follow from that one field.
        if self.season is not None and self.season.data.get("driver"):
            self.tracker.display_name = self.season.data["driver"]
        self.rival_enabled = self.cfg.get("rivals", True)
        self.booth_init()
        self.radio_init()
        self.rival_init()
        self._last_era_obj = None

        self.show_dash = self.cfg["show_dash"]
        self.show_tower = self.cfg["show_tower"]
        self.show_relative = self.cfg["show_relative"]
        self.tower_rows = self.cfg["tower_rows"]
        self.relative_rows = self.cfg["relative_rows"]
        self.tower_interval = self.cfg["tower_interval"]
        self.show_sectors = self.cfg.get("show_sectors", True)
        self.show_map = self.cfg.get("show_map", True)
        self.menu_open = False
        self.menu_page = "main"       # the settings menu has pages now
        self._menu_confirm = None     # pending destructive action, if any

        self.visible = True
        self.debug = False
        self.game_rect = self._default_rect()
        self._keys_down = set()
        self._last_era_key = None
        self._last_session_sig = None
        self._alive = True
        self._frames = 0
        self._t0 = time.time()

    # -- fonts ---------------------------------------------------------------
    def _fonts(self):
        """Load the bundled faces if present, else fall back.

        The fonts are loaded by FAMILY NAME after AddFontResourceEx so nothing
        is installed on the user's system. If they are missing entirely the
        overlay still runs — a missing typeface must never be fatal.
        """
        fam = self._load_fonts()
        cond = fam.get("cond", "Arial Narrow")
        disp = fam.get("disp", "Arial")
        # One global scale so the whole UI grows together. At 1.0 everything
        # reads small on a 1080p screen from a normal seating distance, which
        # is the distance that actually matters for a driving overlay.
        k = float(self.cfg.get("scale", 1.0) or 1.0)
        self.scale = k
        UI.k = k          # published so panels scale with the fonts

        def sz(n):
            return max(6, int(round(n * k)))
        self.f_logo = tkfont.Font(family=disp, size=sz(17), weight="bold")
        self.f_logo_sm = tkfont.Font(family=disp, size=sz(12), weight="bold")
        self.f_logo_w = self.f_logo.measure("FACTOR")
        self.f_speed = tkfont.Font(family=cond, size=sz(26), weight="bold")
        self.f_speed_sm = tkfont.Font(family=cond, size=sz(14), weight="bold")
        self.f_gear = tkfont.Font(family=cond, size=sz(22), weight="bold")
        self.f_gear_sm = tkfont.Font(family=cond, size=sz(14), weight="bold")
        # The F1 strip display makes the GEAR the dominant number, the way a
        # real steering-wheel screen does, so it needs its own larger size.
        self.f_gear_big = tkfont.Font(family=cond, size=sz(38), weight="bold")
        self.f_row = tkfont.Font(family=cond, size=sz(10))
        self.f_small = tkfont.Font(family=cond, size=sz(10), weight="bold")
        self.f_tiny = tkfont.Font(family=cond, size=sz(8))
        # DashMixin indexes f_speed_sm[0] for the family when it scales the
        # dial readout, so expose a plain tuple form too.
        self.f_speed_sm = (cond, sz(14), "bold")
        self.f_tiny = (cond, sz(8))
        self.f_small = (cond, sz(10), "bold")
        self.f_row = (cond, sz(10))
        self.f_speed = (cond, sz(26), "bold")
        self.f_gear = (cond, sz(22), "bold")
        self.f_gear_sm = (cond, sz(14), "bold")
        self.f_gear_big = (cond, sz(38), "bold")

    def _load_logo(self):
        """The supplied Factor.png, scaled to the header.

        Drawn as the real artwork rather than reconstructed from type. The
        earlier version rebuilt the mark from a bold word plus a cyan box,
        which was close but not the same logo — and a channel bug that is
        nearly right looks like a mistake rather than a placeholder.
        """
        self.logo_w = 0
        try:
            from PIL import Image, ImageTk
        except Exception:
            return None
        path = os.path.join(_DIR, "Factor.png")
        if not os.path.exists(path):
            return None
        try:
            im = Image.open(path).convert("RGBA")
            # The source has a large transparent margin; crop to the ink so
            # the bug can be sized by its actual height rather than by canvas.
            bb = im.getbbox()
            if bb:
                im = im.crop(bb)
            h = max(12, int(round(26 * self.scale)))
            w = max(12, int(round(im.width * h / float(im.height))))
            im = im.resize((w, h), Image.LANCZOS)

            # The supplied artwork is DARK NAVY type on transparent, designed
            # for a light background. On the overlay's dark panel it was
            # almost invisible. Lift only the dark pixels to near-white and
            # leave the cyan "TV" block alone, so the mark keeps its shape and
            # its accent colour but reads against the panel.
            px = im.load()
            for iy in range(im.height):
                for ix in range(im.width):
                    r, g, b, a = px[ix, iy]
                    # Anything that is not the cyan block gets lifted to
                    # white. The first attempt only caught pixels below
                    # (120,120,160), which missed the anti-aliased edges and
                    # left the wordmark looking grey and muddy on the panel.
                    # Cyan is identified by blue clearly leading red.
                    if a > 12 and not (b > r + 40 and b > 110):
                        px[ix, iy] = (255, 255, 255, a)
            self.logo_w = w
            return ImageTk.PhotoImage(im)
        except Exception:
            return None

    def _load_fonts(self):
        fam = {}
        try:
            import ctypes
            gdi = ctypes.windll.gdi32
            for fn, key, name in (("ChakraPetch-SemiBold.ttf", "cond",
                                   "Chakra Petch SemiBold"),
                                  ("Michroma-Regular.ttf", "disp", "Michroma")):
                p = os.path.join(_DIR, fn)
                if os.path.exists(p):
                    gdi.AddFontResourceExW(ctypes.c_wchar_p(p), 0x10, 0)
                    fam[key] = name
        except Exception:
            pass
        avail = set(tkfont.families(self.root))
        for k, default in (("cond", "Arial"), ("disp", "Arial")):
            if fam.get(k) not in avail:
                for cand in ("Chakra Petch", "Bahnschrift Condensed",
                             "Segoe UI Semibold", "Arial"):
                    if cand in avail:
                        fam[k] = cand
                        break
                else:
                    fam[k] = default
        return fam

    # -- panels ---------------------------------------------------------------
    def _begin_panel(self, name, x, y, w, h, clickable=False):
        p = self.panels.get(name)
        if p is None:
            # `clickable` is decided at CREATION because it sets a window
            # style; the settings menu is the only panel that takes the mouse.
            p = self.panels[name] = Panel(self.root, clickable=clickable)
        p.place(x, y, w, h)
        self._used_this_frame.add(name)
        return p

    def _hide_panel(self, name):
        p = self.panels.get(name)
        if p is not None:
            p.hide()

    def _sweep_panels(self):
        """Hide any panel nothing drew into this frame.

        Without this a panel that stops being relevant (the flag strip after
        a yellow clears) keeps its last frame on screen forever, because
        nothing ever tells its window to go away.
        """
        for name, p in self.panels.items():
            if name not in self._used_this_frame:
                p.hide()
        self._used_this_frame.clear()

    def _hide_all(self):
        for p in self.panels.values():
            p.hide()
        self._used_this_frame.clear()

    # -- geometry --------------------------------------------------------------
    def _default_rect(self):
        w, h = screen_size()
        return (0, 0, w, h)

    def _lock_to_game(self):
        """Follow the game window if we can find it, else use the screen.

        Anchoring to the window rather than the screen keeps the layout
        correct in borderless-windowed at a non-native resolution, which is
        the mode rF2 users run for overlays in the first place.
        """
        r = find_game_window(("rFactor2", "rFactor 2"))
        # AND IT CANNOT BE BIGGER THAN THE SCREEN. `find_game_window` now
        # reports the client area, which fixes the ordinary windowed case, but
        # a window dragged half off the display or sized past it would still
        # put an edge-hugging panel where nothing can be seen. Panels are
        # placed FROM this rect, so intersecting it with the screen once here
        # is the one place that guard belongs.
        was = self.game_rect
        self.game_rect = self._on_screen(r) if r else self._default_rect()
        # SAY WHERE THE OVERLAY THINKS THE PICTURE IS, WHENEVER THAT CHANGES.
        # The division's mark was reported cut off by the right-hand edge and
        # could not be reproduced from the numbers this machine reports — which
        # means the rect in a live run is not the rect a test computes, and
        # nothing in the log said so. Every panel is positioned from this, so it
        # is the first thing to read when something is in the wrong place.
        if was != self.game_rect:
            try:
                self._log("RECT", "game=%s window=%s screen=%s virtual=%s "
                                  "scale=%.2f" % (self.game_rect, r,
                                                  screen_size(),
                                                  virtual_screen(),
                                                  float(getattr(self, "scale",
                                                                1.0))))
            except Exception:
                pass
        return r is not None

    def _on_screen(self, rect):
        sw, sh = screen_size()
        x, y, w, h = rect
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(sw, x + w), min(sh, y + h)
        if x1 - x0 < 640 or y1 - y0 < 400:
            return self._default_rect()
        return (x0, y0, x1 - x0, y1 - y0)

    # -- hotkeys ---------------------------------------------------------------
    def _hotkeys(self):
        if not (key_down(VK_CONTROL) and key_down(VK_SHIFT)):
            self._keys_down.clear()
            return
        for vk, fn in ((VK_O, self._toggle_ui), (VK_D, self._toggle_debug),
                       (VK_E, self._toggle_tower), (VK_V, self._toggle_rel), (VK_R, self._toggle_radio),
                       (VK_T, self._toggle_dash), (VK_M, self._cycle_gap),
                       (VK_C, self._toggle_booth), (VK_S, self._toggle_menu),
                       (VK_Q, self.quit)):
            if key_down(vk):
                if vk not in self._keys_down:
                    self._keys_down.add(vk)
                    fn()
            else:
                self._keys_down.discard(vk)

    def _toggle_ui(self):
        self.visible = not self.visible
        if not self.visible:
            self._hide_all()

    def _toggle_debug(self):
        self.debug = not self.debug

    def _toggle_tower(self):
        self.show_tower = not self.show_tower
        self.cfg["show_tower"] = self.show_tower
        save_settings(self.cfg)

    def _toggle_rel(self):
        self.show_relative = not self.show_relative
        self.cfg["show_relative"] = self.show_relative
        save_settings(self.cfg)

    def _toggle_dash(self):
        self.show_dash = not self.show_dash
        self.cfg["show_dash"] = self.show_dash
        save_settings(self.cfg)

    def _toggle_booth(self):
        self.booth_enabled = not self.booth_enabled
        self.cfg["booth"] = self.booth_enabled
        if not self.booth_enabled:
            self.tts.interrupt()
        save_settings(self.cfg)

    def _toggle_menu(self):
        self.menu_open = not self.menu_open
        # Reopen on the main page, never on a half-finished confirmation.
        self.menu_page = "main"
        self._menu_confirm = None

    def _menu_mouse(self):
        """Poll for a click on the menu button, or inside the open menu.

        Polled rather than bound: the overlay never takes focus, so there is
        no tk event to bind to.

        This used to return immediately unless the menu was already open, as
        a cost saving — which meant the hamburger could only ever CLOSE the
        menu. Opening it by mouse was impossible, and the button sat there
        looking clickable while only Ctrl+Shift+S actually worked. The saving
        was imaginary anyway: this is one GetAsyncKeyState per frame, next to
        the eight the hotkeys already do, and the cursor position is only
        read on the frame a click actually begins.
        """
        down = key_down(VK_LBUTTON)
        if down and not getattr(self, "_mouse_down", False):
            import ctypes
            from ctypes import wintypes
            pt = wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            self.menu_click(pt.x, pt.y)
        self._mouse_down = down

    def _toggle_radio(self):
        # One key covers both radio channels: they are the same feature to a
        # user ("voices that aren't the booth"), and two keys for it would be
        # two keys to remember for no benefit.
        self.radio_enabled = not self.radio_enabled
        self.rival_enabled = self.radio_enabled
        self.cfg["radio"] = self.radio_enabled
        self.cfg["rivals"] = self.rival_enabled
        save_settings(self.cfg)

    def _cycle_gap(self):
        self.tower_interval = not self.tower_interval
        self.cfg["tower_interval"] = self.tower_interval
        save_settings(self.cfg)

    def quit(self):
        self._alive = False
        try:
            self.tts.close()
        except Exception:
            pass
        try:
            self.tracker.close()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    # -- tick -------------------------------------------------------------------
    def tick(self):
        if not self._alive:
            return
        t0 = time.perf_counter()
        try:
            self._tick_body()
        except Exception:
            # A drawing bug must never take the overlay down mid-race. Report
            # once to the console and keep ticking; the alternative is the
            # user losing every panel because one gap was None.
            if self.debug:
                import traceback
                traceback.print_exc()
        finally:
            if self._alive:
                # UPDATE_MS IS A PERIOD, NOT A GAP AFTER THE WORK.
                #
                # This was `after(UPDATE_MS, ...)` unconditionally, which put
                # a full 50ms between the END of one frame and the start of
                # the next — so the real cadence was work + 50ms. At a
                # measured 32ms frame that is 82ms, or 12Hz, for a panel set
                # nominally running at 20. The speedo was not lagging because
                # a value arrived late; it was lagging because it was only
                # being redrawn twelve times a second.
                #
                # Scheduling from the frame START restores the actual 20Hz.
                # The floor of 1ms matters: a frame that overruns its budget
                # must still yield to Tk, or a slow frame on a loaded machine
                # turns into a busy loop that never lets the UI breathe.
                spent = (time.perf_counter() - t0) * 1000.0
                self._frame_ms = spent
                self.root.after(max(1, int(UPDATE_MS - spent)), self.tick)

    def _tick_body(self):
        # When this frame started. Read by anything that wants to know how
        # much of the tick is left before it takes on optional work — the
        # gauge's cache prewarm is the one that matters. Set here rather than
        # in `tick` so the profiler and the preview, which call `_tick_body`
        # directly, get the same behaviour as a real run.
        self._frame_t0 = time.perf_counter()
        self._hotkeys()
        self._menu_mouse()
        self._frames += 1
        if not self.visible:
            return

        if self._frames % 20 == 1:      # re-locate the game ~1/s, not per frame
            self._lock_to_game()

        # WHICH VOICES DID HE ACTUALLY GET? Printed ONCE, the first time the
        # answer is known — a tester should not have to wonder whether the
        # robotic voice he can hear is the product or his connection.
        if not getattr(self, "_said_voices", False):
            try:
                line = self.tts.voice_report()
            except Exception:
                line = ""
            if line:
                self._said_voices = True
                print(line)
                try:
                    self._log("VOICES", line.split(None, 1)[1])
                except Exception:
                    pass

        plugin = self.tracker.plugin_present
        s = self.tracker.update() if plugin else None

        # Re-skin when the era changes. Doing this only on change avoids
        # rebuilding the palette 20 times a second for no reason.
        if s is not None and s.valid and s.era is not None:
            self._last_era_obj = s.player_era or s.era
            if s.era.key != self._last_era_key:
                self._last_era_key = s.era.key
                TH.follow(s.era)
                self.fuel_model.reset()

        if self.draw_status(s, plugin):
            # The MENU is not part of the broadcast and must not wait for one.
            # Everything else here needs a live session to draw, so the early
            # return was reasonable — except that it also took the hamburger
            # with it, which meant a career could only be configured while
            # already sitting in a race. That is precisely the wrong moment:
            # setting one up before going on track is the whole point.
            # THE INTRODUCTION, before anything else on the tick. It only ever
            # speaks when there is no session or the car is not out, which is
            # exactly the state this branch is for.
            self.update_tutorial(s)
            self.draw_menu_button()
            self.draw_inbox_button()
            self.draw_mode_badge()
            self.draw_division_logo()
            self.draw_settings()
            # THE GARAGE IS PART OF THE WEEKEND. `draw_status` claims the whole
            # tick whenever the session is not live, which includes the pit
            # screen — so the booth was not even RUNNING there.
            #
            # `draw_status` claims the frame whenever the session is not live —
            # which includes the pit screen, where a driver sits deciding what to
            # do. So `update_booth` was never CALLED in the garage, and moving the
            # arming inside it earlier did nothing: the whole tick was skipped.
            # The user, twice: *"the prompt only comes up after I press drive ...
            # which tells me the overlay doesn't pick it up until you're out on
            # track"*. He was right both times.
            #
            # `update_booth` returns at its own on-air gate before anything can be
            # SPOKEN, so calling it here costs one arming decision and cannot
            # produce a word of commentary over a loading screen — which is what
            # that gate has always been for.
            self.update_booth(s)
            self._test_watch(s)
            self._sweep_panels()
            return

        self.draw_header(s)
        self.draw_flags(s)
        if self.show_tower:
            self.draw_tower(s)
        if self.show_relative:
            self.draw_relative(s)
        if self.show_dash:
            self.draw_dash(s)
        self.draw_sectors(s)
        self.draw_map(s)
        self.draw_podium(s)
        # THE TEST PROGRAMME WATCHES EVERY SESSION, INCLUDING THE ONES THE BOOTH
        # DOES NOT COVER. A test outing IS a practice session, and `update_booth`
        # returns immediately for those — so hanging this off the booth would put
        # the tick behind the one gate guaranteed to be shut. It also must not
        # depend on the commentary being switched on: this is career bookkeeping,
        # like the badge beside it.
        self._test_watch(s)
        self.update_tutorial(s)
        self.draw_menu_button()
        self.draw_inbox_button()
        self.draw_mode_badge()
        self.draw_division_logo()
        self.draw_settings()
        self.update_booth(s)
        self.update_radio(s)
        self.update_rivals(s)
        _now = time.time()
        # Cards wait for their line to actually be AUDIBLE before appearing.
        # `tts.speak()` only enqueues and a render takes 2-6s, so a card
        # pushed at speak time is on screen several seconds before the voice.
        # Released here, every frame, right before the panel is drawn.
        self.release_cards(_now)
        self.draw_caption(_now)
        self.draw_radio(_now)
        if self.debug:
            self.draw_debug(s)
        self._sweep_panels()

    def draw_debug(self, s):
        w, h = 250, 96
        gx, gy, gw, gh = self.game_rect
        x, y = gx + 16, gy + gh - h - 16
        p = self._begin_panel("debug", x, y, w, h)
        c = p.canvas_at(x, y)
        self._body(c, x, y, w, h)
        fps = self._frames / max(0.001, time.time() - self._t0)
        e = s.era if s else None
        lines = [
            "fps %.1f   panels %d" % (fps, len(self.panels)),
            "game %dx%d @%d,%d" % (gw, gh, gx, gy),
            "era  %s / %s" % (e.key if e else "-", e.discipline if e else "-"),
            "skin %s   cars %d" % (TH.name, s.num_cars if s else 0),
            "phase %s  et %.0f" % (s.phase_name if s else "-", s.et if s else 0),
        ]
        for i, ln in enumerate(lines):
            c.create_text(x + 10, y + 10 + i * 16, text=ln, anchor="nw",
                          fill=TH.dim, font=self.f_tiny)

    def run(self):
        print("FACTORtv running.  Ctrl+Shift+O hide/show, +D debug, +Q quit.")
        if not self.tracker.plugin_present:
            print("Waiting for rFactor 2 (shared memory not found).")
        self.root.after(200, self.tick)
        self.root.mainloop()


def main():
    ov = Overlay()
    try:
        ov.run()
    except KeyboardInterrupt:
        ov.quit()


if __name__ == "__main__":
    main()
