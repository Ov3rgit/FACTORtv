# -*- coding: utf-8 -*-
"""
FACTORtv — on-screen preview.

Runs the REAL overlay against a synthetic race so every panel can be seen and
screenshotted without rFactor 2 running. Not a mock-up: it is the actual
Overlay object with the actual draw code, so what you see is what you get.

    python preview.py                  look at it, silent
    python preview.py --live           ...and HEAR the booth, radio and stings
    python preview.py --live --historic    a pre-2000 field: Brett in the chair
    python preview.py --class="GT3 2020"   any class era.py can classify

Ctrl+Shift+Q to quit, Ctrl+Shift+S for the settings menu, and every other
hotkey works exactly as it does in a race.

`--live` exists because a transcript cannot answer the question that actually
matters — whether it FEELS like a broadcast. Delivery, pacing, whether two
voices sound like a conversation, whether a sting lands on the moment: none
of that is visible in text. With `--live` the whole audio chain runs against
the synthetic race, so the booth can be judged without driving anything.

The fake session advances — cars swap places, lap times fall, tyres wear,
fuel drains — so the tower, dash and sector strip all show live-looking data
rather than a frozen frame.
"""
import math
import sys
import time

import era as era_mod
import factor_tv
import track as track_mod

# The car class the synthetic field is running. Set from the command line so
# the preview can be pointed at any era — which is the only way to see and
# HEAR the historic booth without owning a race in that era.
CAR_CLASS = "F1 Test 2025"

NAMES = ["Verstappen", "Norris", "Leclerc", "Kandasamy", "Hamilton",
         "Piastri", "Russell", "Sainz", "Alonso", "Gasly", "Ocon", "Albon",
         "Tsunoda", "Hulkenberg", "Stroll", "Bearman"]


class Car(object):
    def __init__(self, cid, place, name):
        self.id = cid
        self.place = place
        self.place_class = place
        self.name = name
        self.display_name = name
        self.is_player = (name == "Kandasamy")
        self.is_ai = not self.is_player
        self.in_pits = False
        self.in_garage = False
        self.laps = 8
        self.laps_down = 0
        self.gap_ahead = 0.4 + place * 0.35
        self.gap_leader = place * 1.6
        self.gap_behind = 0.9
        self.best_lap = 71.234 + place * 0.18
        self.last_lap = self.best_lap + 0.4
        self.cur_s1 = self.cur_s2 = None
        self.last_s1, self.last_s2, self.last_s3 = 21.1, 24.3, 25.9
        self.best_s1, self.best_s2, self.best_s3 = 21.0, 24.2, 25.8
        self.sector = 2
        self.purple_lap = (place == 1)
        self.purple_s1 = self.purple_s2 = self.purple_s3 = False
        self.places_gained = (1 if place % 3 == 0 else
                              (-1 if place % 4 == 0 else 0))
        self.started_place = place
        self.penalties = 0
        self.pit_stops = 1
        self.pit_state = 0
        self.finish_status = 0
        self.control = 0 if self.is_player else 1
        self.blue_flag = False
        self.under_yellow = False
        self.cls = CAR_CLASS
        self.vehicle = name
        self.tyre_front = "Soft"
        self.tyre_rear = "Soft"
        self.car_number = place
        self.speed = 250.0
        self.rpm = 10800.0
        self.max_rpm = 13000.0
        self.gear = 6
        self.fuel = 42.0
        self.fuel_cap = 110.0
        self.battery = 0.64
        self.flap = 1
        self.headlights = False
        self.surface = (0, 0, 0, 0)
        self.wheels_off = 0
        self.lap_start_et = 0.0
        self.time_into_lap = 30.0
        self.est_lap = 72.0
        self.lap_dist = 0.0
        self.race_dist = 0.0
        self.damage = (0, 1, 0, 0, 0, 0, 2, 0) if self.is_player else (0,) * 8
        self.tyre_wear = (0.88, 0.85, 0.66, 0.63)
        self.tyre_temp = (94.0, 98.0, 104.0, 108.0)
        self.brake_temp = (430.0, 455.0, 385.0, 400.0)
        self.pos = (0.0, 0.0)


class Session(object):
    """A synthetic race that actually moves."""

    def __init__(self):
        self.t0 = time.time()
        self.cars_l = [Car(i + 1, i + 1, n) for i, n in enumerate(NAMES)]
        self.valid = True
        self.track = "Zandvoort 2021"
        self.circuit = track_mod.Track(self.track)
        self.track_len = 4245.6
        self.kind = "race"
        self.session_index = 10
        self.phase = 5
        self.phase_name = "green"
        self.green = True
        self.started = True
        self.countdown = False
        self.finished = False
        self.in_realtime = True
        self.max_laps = 17
        self.timed = False
        self.time_left = None
        self.end_et = 0.0
        self.multiclass = False
        self.classes = ["F1 Test 2025"]
        self.era = era_mod.classify(CAR_CLASS, "Max Verstappen")
        self.player_era = self.era
        self.yellow = 0
        self.yellow_sectors = (0, 0, 0)
        self.full_course_yellow = False
        self.air_temp = 24.0
        self.track_temp = 38.0
        self.raining = 0.0
        self.wetness = 0.0
        self.best_s1, self.best_s2, self.best_s3 = 20.9, 24.1, 25.7
        self.best_lap_time = 70.9
        self.best_lap_driver = "Verstappen"
        self.pit_speed_limit = 80.0
        self.replay = False
        self.update()

    def update(self):
        """Advance the fake race so the panels show live-looking data."""
        el = time.time() - self.t0
        self.et = el
        self.leader_laps = 8 + int(el // 40)
        self.laps_left = max(0, self.max_laps - self.leader_laps)
        self.num_cars = len(self.cars_l)

        for i, c in enumerate(self.cars_l):
            # Positions drift so the tower's gain/loss arrows animate.
            c.laps = self.leader_laps if i == 0 else self.leader_laps - (i > 9)
            ang = el * 0.35 + i * (2 * math.pi / len(self.cars_l))
            # A rough oval, so the learned track map has something to draw.
            c.pos = (900.0 * math.cos(ang), 520.0 * math.sin(ang * 1.9))
            c.lap_dist = (ang % (2 * math.pi)) / (2 * math.pi) * self.track_len
            c.race_dist = c.laps * self.track_len + c.lap_dist
            c.gap_ahead = 0.3 + (i * 0.31) % 2.4
            c.gap_leader = i * 1.55
            c.in_pits = (i == 11 and 18 < (el % 60) < 30)

        me = self.player
        me.speed = 180 + 90 * abs(math.sin(el * 0.5))
        me.rpm = 8000 + 4500 * abs(math.sin(el * 0.5))
        me.gear = 3 + int(4 * abs(math.sin(el * 0.5)))
        me.fuel = max(3.0, 42.0 - el * 0.05)
        me.battery = 0.35 + 0.45 * abs(math.sin(el * 0.2))
        me.flap = 1 if (el % 8) > 5 else 0
        w = max(0.15, 0.88 - el * 0.004)
        me.tyre_wear = (w, w - 0.03, w - 0.20, w - 0.23)
        me.tyre_temp = (92 + 8 * math.sin(el * 0.3), 96 + 8 * math.sin(el * 0.3),
                        103 + 9 * math.sin(el * 0.3), 107 + 9 * math.sin(el * 0.3))
        me.sector = 1 + int((el % 9) // 3)

        # A scripted excursion, so the off-track detector and the engineer's
        # reaction can actually be SEEN and HEARD from the preview. Without
        # this nothing in a synthetic race ever leaves the road, and the one
        # part of the booth that most needs judging by ear never fires.
        # Two cars, staggered, and one of them is you.
        for c, at, dur, grass in ((self.player, 50.0, 2.5, 4),
                                  (self.cars_l[3], 95.0, 1.2, 2)):
            if at < el < at + dur:
                # GRASS on `grass` wheels; speed collapses so it grades as a
                # spin rather than a tidy run-off.
                c.surface = tuple([2] * grass + [0] * (4 - grass))
                c.wheels_off = grass
                c.speed = 55.0
            else:
                c.surface = (0, 0, 0, 0)
                c.wheels_off = 0
        return self

    # -- the interface the overlay expects ---------------------------------
    @property
    def order(self):
        return self.cars_l

    @property
    def cars(self):
        return {c.id: c for c in self.cars_l}

    @property
    def leader(self):
        return self.cars_l[0]

    @property
    def player(self):
        return next(c for c in self.cars_l if c.is_player)

    def car_ahead(self, c):
        i = c.place - 1
        return self.cars_l[i - 1] if 0 < i < len(self.cars_l) else None

    def car_behind(self, c):
        i = c.place - 1
        return self.cars_l[i + 1] if 0 <= i < len(self.cars_l) - 1 else None

    def in_class(self, cls):
        return [c for c in self.cars_l if c.cls == cls]


def main():
    global CAR_CLASS
    args = [a for a in sys.argv[1:]]
    live = ("--live" in args or "--audio" in args)
    if "--historic" in args:
        CAR_CLASS = "F1 1988 Historic Edition"
    for a in args:
        if a.startswith("--class="):
            CAR_CLASS = a.split("=", 1)[1]

    print("FACTORtv preview — the real overlay, synthetic race data.")
    print("  class: %s" % CAR_CLASS)
    print("  Ctrl+Shift+S  settings menu")
    print("  Ctrl+Shift+Q  quit")
    if live:
        print("  LIVE: commentary, radio and stings are ON — this is what a")
        print("        race sounds like, without driving one.")
    else:
        print("  (audio is OFF — pass --live to hear the booth)")

    ov = factor_tv.Overlay()
    sess = Session()

    # Silence the booth by default: a preview is for LOOKING at, and a
    # commentary track running over a screenshot session is just noise.
    # `--live` is the opposite job — judging whether the broadcast FEELS
    # right, which cannot be done by reading a transcript.
    if not live:
        ov.booth_enabled = False
        ov.radio_enabled = False
        ov.rival_enabled = False

    # The overlay normally reads shared memory; feed it the fake race instead.
    # `plugin_present` is a read-only property on the real tracker, so the
    # whole tracker is swapped rather than patched piecemeal.
    class _FakeTracker(object):
        plugin_present = True
        def update(self):
            return sess.update()
        def confirmed_places(self, s):
            return {c.id: c.place for c in s.order}
        def close(self):
            pass
    ov.tracker = _FakeTracker()

    # Preview covers the whole screen, since there is no game window to
    # anchor to.
    ov._lock_to_game = lambda: False
    ov.menu_open = False         # start clean; Ctrl+Shift+S opens it
    ov.run()


if __name__ == "__main__":
    sys.exit(main() or 0)
