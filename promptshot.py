# -*- coding: utf-8 -*-
"""
FACTORtv — does the "count this race?" prompt actually appear in the garage?

    python promptshot.py            -> _prompt_preview.png

ASKED FOR AFTER IT SHIPPED BROKEN: *"you should do a test, like a fake preview
test if someone loads into a garage does the prompt even show to begin with."*

He is right, and the reason he is right is the whole method of this project. The
assertion version of this test passed while the feature was broken in the game —
because the assertion called `season_prompt()` directly, and the bug was that the
ROUND was never decided, three layers upstairs, on a tick that only exists when a
real session is loading. A picture cannot be fooled that way: either the card is
in the frame or it is not.

WHAT IT DRIVES
--------------
The REAL `update_booth` over a garage session, tick by tick, exactly as
`factor_tv` does — including the part that broke:

  tick 1   the session appears with NOTHING resolved. No circuit, no car class.
  tick 2   rF2 publishes the circuit and the class, a beat later.
  tick 3+  the round is matched, and the card should be on screen.

Then it draws with the real `draw_career_prompt` on a real canvas and grabs the
pixels — the same method `mailshot.py`, `menushot.py` and `dashshot.py` use, for
the same reason: re-drawing the card in PIL would let the preview agree with me
rather than with the overlay.
"""
import io
import os
import sys
import tempfile
import tkinter as tk

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

CW, CH = 1000, 260


class _Circuit:
    """What `track.resolve` hands back once rF2 has published a track."""
    slug = "interlagos"
    name = "Interlagos"
    known = True
    year = None

    @staticmethod
    def country():
        return "Brazil"

    @staticmethod
    def facts(*a, **k):
        return []

    @staticmethod
    def character(*a, **k):
        return ""

    @staticmethod
    def corner(*a, **k):
        return ""

    @staticmethod
    def corners(*a, **k):
        return []

    @staticmethod
    def sector(*a, **k):
        return ""

    @staticmethod
    def overtaking(*a, **k):
        return ""


class Car:
    def __init__(s, cid, place, name, cls):
        s.id = cid; s.place = place; s.name = name; s.display_name = name
        s.is_player = (place == 4); s.in_pits = True; s.laps = 0
        s.gap_ahead = None; s.gap_leader = None; s.gap_behind = None
        s.best_lap = None; s.last_lap = None; s.speed = 0.0
        s.places_gained = 0; s.finish_status = 0; s.sector = 1
        s.cls = cls; s.vehicle = name; s.laps_down = 0
        s.purple_lap = False; s.started_place = place
        s.damage = (0,) * 8; s.tyre_wear = (1.0,) * 4; s.tyre_temp = (60,) * 4
        s.brake_temp = (200,) * 4; s.fuel = 20.0; s.fuel_cap = 40.0
        s.rpm = 0; s.max_rpm = 12000; s.gear = 0; s.pos = (0.0, 0.0)
        s.battery = 0.0; s.flap = 0; s.penalties = 0; s.pit_stops = 0
        s.control = 0; s.blue_flag = False; s.under_yellow = False
        s.last_s1 = s.last_s2 = s.last_s3 = None
        s.best_s1 = s.best_s2 = s.best_s3 = None
        s.tyre_front = s.tyre_rear = ""
        s.in_garage = True


class Garage:
    """A race session sitting in the garage, before anybody has gone out.

    `on_air` is False, which is the whole point: it is what stopped the round
    being decided until the car was already on track.
    """
    def __init__(s, cls="Tatuus_F4-T014", resolved=False):
        names = ["Marco Bellini", "Theo Vasseur", "Sam Okonkwo",
                 "Dante Kandasamy", "Ahti Jyrki", "Norbert Truls"]
        s.order = [Car(i + 1, i + 1, n, cls if resolved else "")
                   for i, n in enumerate(names)]
        s.cars = {c.id: c for c in s.order}
        s.player = next(c for c in s.order if c.is_player)
        s.leader = s.order[0]
        s.valid = True
        s.track = "SaoPaulo GP" if resolved else ""
        s.circuit = _Circuit() if resolved else None
        s.kind = "race"
        s.phase_name = "garage"
        s.green = False
        s.started = False
        s.finished = False
        s.on_air = False              # in the garage, not in realtime
        s.in_realtime = False
        s.max_laps = 10
        s.laps_left = 10
        s.leader_laps = 0
        s.num_cars = len(s.order)
        s.session_index = 3
        s.multiclass = False
        s.classes = [cls] if resolved else []
        s.full_course_yellow = False
        s.yellow = 0
        s.yellow_sectors = (0, 0, 0)
        s.time_left = None
        s.et = 12.0
        s.best_lap_time = None
        s.best_lap_driver = ""
        s.best_s1 = s.best_s2 = s.best_s3 = None
        s.status_message = ""
        s.status_message_new = False
        import era as era_mod
        s.era = era_mod.classify(cls if resolved else "", "")
        s.player_era = s.era

    def car_ahead(s, c):
        i = c.place - 1
        return s.order[i - 1] if 0 < i < len(s.order) else None

    def car_behind(s, c):
        i = c.place - 1
        return s.order[i + 1] if 0 <= i < len(s.order) - 1 else None


def _career():
    """A Formula 4 career with round one unraced — his own situation."""
    import season as S
    S.CAREER_DIR = tempfile.mkdtemp(prefix="factortv_prompt_")
    c = S.create("open", me="Dante Kandasamy", rounds=10,
                 ladder_path="single_seater", tier_index=1)
    c.data["nationality"] = "South Africa"
    c.data["driver"] = "Dante Kandasamy"
    c.save()
    return c


def main():
    from PIL import ImageGrab
    import era as era_mod
    from overlay_common import TH, CHROMA, UI
    from overlay_draw import DrawMixin
    from overlay_panels import PanelsMixin
    from overlay_booth import BoothMixin
    from overlay_panel import TCanvas
    import career as career_mod
    import cast as cast_mod

    career = _career()
    UI.k = 1.25
    TH.apply(era_mod.skin_for(era_mod.classify("Tatuus_F4-T014", "")))

    root = tk.Tk()
    root.configure(bg=CHROMA)
    cv = tk.Canvas(root, width=CW, height=CH, bg=CHROMA, highlightthickness=0)
    cv.pack()

    class FakeTts:
        speaking = False
        now_playing = None

        def speak(self, *a, **k):
            pass

        def interrupt(self):
            pass

    class FakeTracker:
        def __init__(self):
            self._place_pending = {}
            self._place_confirmed = {}

        def confirmed_places(self, s):
            return {c.id: c.place for c in s.order}

    class Host(DrawMixin, PanelsMixin, BoothMixin):
        def __init__(self):
            self.root = root
            # The card sits above the caption box on the bottom edge, so the
            # canvas pretends to be the bottom strip of a 1920x1080 screen.
            self.game_rect = (0, 1080 - CH, CW, CH)
            for n, sz in (("f_small", 10), ("f_row", 10), ("f_tiny", 8),
                          ("f_logo", 17), ("f_logo_sm", 12)):
                setattr(self, n, ("Arial", int(sz * 1.25)))
            self.season = career
            self.career = career_mod.History()
            self.season_record = True
            self.menu_open = False
            self.menu_page = "main"
            self._menu_confirm = None
            self._menu_offset = 0
            self.booth_enabled = True
            self.tts = FakeTts()
            self.tracker = FakeTracker()
            self.sting_bank = None
            self.cfg = {}
            self.booth_init()

        def _begin_panel(self, name, x, y, w, h, clickable=False):
            # THE PANEL'S OWN ORIGIN IS THE CANVAS ORIGIN. `TCanvas` subtracts
            # the offset it is given from absolute screen coordinates, so
            # handing it the panel's own (x, y) puts the card's top-left corner
            # at the top-left of this canvas. Shifting it a second time — which
            # the first version of this file did — drew it above the canvas,
            # off the picture, and reported an empty frame as a product bug.
            self._shot = (int(x), int(y), int(w), int(h))

            class P(object):
                def canvas_at(self_inner, ox, oy):
                    return TCanvas(cv, ox - 12, oy - 12)
            return P()

        def _hide_panel(self, n):
            pass

        def _short_track(self, n):
            return n

        def _sweep_panels(self):
            pass

        def _test_watch(self, s):
            pass

        def _garage_frame(self, s):
            """The frame's not-live branch, in the order `factor_tv` runs it.

            READ OUT OF THE REAL SOURCE, not copied by hand: a preview that
            hard-codes the order is a preview that keeps passing after the frame
            changes. If `factor_tv` stops calling the prompt here, this fails.
            """
            import re
            src = io.open(os.path.join(_DIR, "factor_tv.py"),
                          encoding="utf-8").read()
            branch = src.split("if self.draw_status(s, plugin):")[1]
            # THE STATEMENT, NOT THE WORD. Splitting on "return" cut the
            # branch off inside a COMMENT containing "returns", which found no
            # calls at all and reported the frame as broken when it was not.
            branch = branch.split(chr(10) + " " * 12 + "return")[0]
            calls = re.findall(r"self\.(draw_\w+|update_booth|_test_watch)\(",
                               branch)
            for name in calls:
                fn = getattr(self, name, None)
                if fn is None:
                    continue
                try:
                    fn(s) if name != "draw_settings" else fn()
                except TypeError:
                    fn()
            return calls

    host = Host()
    cast_mod.set_era(era_mod.classify("Tatuus_F4-T014", ""))

    # TICK 1: the session exists and rF2 has published nothing useful yet.
    cold = Garage(resolved=False)
    host.update_booth(cold)
    armed_cold = host._season_armed
    round_cold = host._season_round

    # TICK 2 ONWARD: the circuit and the car class arrive.
    warm = Garage(resolved=True)
    warm.session_index = cold.session_index
    for _ in range(3):
        warm.et += 0.05
        host.update_booth(warm)

    print("tick 1 (nothing published): armed=%s round=%s"
          % (armed_cold, round_cold))
    print("tick 2+ (circuit + class):  armed=%s round=%s"
          % (host._season_armed, host._season_round))
    info = host.season_prompt(warm)
    print("prompt:", info)

    # THE FRAME MUST DRAW IT, NOT JUST THE PANEL METHOD.
    #
    # Calling `draw_career_prompt` directly is what this file did first, and it
    # PASSED while the feature was still broken in the game — because the real
    # frame short-circuits in the garage (`draw_status` claims the tick when the
    # session is not live) and never reached the card at all. So the check is now
    # made through the same gate the game goes through.
    drew = []
    _real_begin = host._begin_panel

    def _spy(name, x, y, w, h, clickable=False):
        drew.append(name)
        return _real_begin(name, x, y, w, h, clickable)
    host._begin_panel = _spy
    host._garage_frame(warm)
    host._begin_panel = _real_begin
    print("panels the frame drew in the garage:", sorted(set(drew)))
    if "career" not in drew:
        print("FAILED: the frame never reached the prompt in the garage")
        return 1
    root.attributes("-topmost", True)
    root.lift()
    root.update_idletasks()
    root.update()
    root.after(350, root.quit)
    root.mainloop()
    root.update()
    x0, y0 = root.winfo_rootx(), root.winfo_rooty()
    img = ImageGrab.grab((x0, y0, x0 + CW, y0 + CH)).convert("RGB")
    root.destroy()
    path = os.path.join(_DIR, "_prompt_preview.png")
    img.save(path)

    # THE PICTURE IS THE TEST. An empty frame means the card was not drawn, and
    # counting non-background pixels is the only way to say so without a person
    # looking at it.
    from PIL import ImageStat
    ink = sum(ImageStat.Stat(img).stddev)
    print("wrote %s  (ink spread %.1f — near zero means an EMPTY frame)"
          % (path, ink))
    if not info or ink < 5:
        print("FAILED: the prompt did not draw")
        return 1
    print("OK: the card is on screen in the garage, before the green flag")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
