"""Shared fakes for the headless booth tests.

A booth test needs a session, a car, a TTS and a sting bank, none of which
exist without the game. They live here rather than being copied into each
test, so a change to the Session shape is a one-file change and each test
file can be read for what it actually asserts.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import era as era_mod                                    # noqa: E402
from overlay_booth import BoothMixin                     # noqa: E402


class FakeCar:
    def __init__(s, cid, place, name, laps=5):
        s.id = cid; s.place = place; s.display_name = name; s.name = name
        s.laps = laps; s.in_pits = False; s.best_lap = 92.0; s.speed = 200.0
        s.finish_status = 0; s.sector = 1; s.is_player = (cid == 1)
        s.cls = 'F1 Test 2025'; s.vehicle = name
        s.gap_ahead = 1.2; s.gap_leader = 1.2 * place; s.laps_down = 0
        s.places_gained = 0; s.started_place = place
        s.purple_lap = False; s.tyre_front = ''
        # Sector splits of the best lap. rF2 gives these per car, and they
        # add up to best_lap, so the booth can say where a lap was won.
        s.fuel = 40.0; s.fuel_cap = 100.0; s.last_lap = 92.0
        s.best_s1 = 30.0; s.best_s2 = 31.0; s.best_s3 = 31.0
        s.last_s1 = 30.0; s.last_s2 = 31.0; s.last_s3 = 31.0

class FakeSession:
    def __init__(s, cars, **kw):
        s.valid = True; s.order = cars; s.cars = {c.id: c for c in cars}
        s.leader = cars[0]
        s.player = next((c for c in cars if c.is_player), cars[0])
        s.track = 'Zandvoort'; s.kind = 'race'; s.green = True
        s.finished = False; s.on_air = True
        s.max_laps = 17; s.laps_left = 12; s.leader_laps = 5
        s.num_cars = len(cars); s.session_index = 10; s.multiclass = False
        s.full_course_yellow = False; s.started = True
        s.yellow_sectors = (0, 0, 0); s.classes = ['F1 Test 2025']
        s.time_left = None; s.end_et = 0.0; s.best_lap_time = 92.0
        s.circuit = None
        s.era = era_mod.classify('F1 Test 2025', 'Max Verstappen')
        s.player_era = s.era
        for k, v in kw.items():
            setattr(s, k, v)
    def car_ahead(s, c):
        i = c.place - 1
        return s.order[i - 1] if 0 < i < len(s.order) else None

class FakeTts:
    def __init__(s): s.said = []; s.speaking = False
    def speak(s, text, who, intensity=0, build=False, name=""):
        s.said.append((who, text))
    def interrupt(s): pass
    def play_file(s, path, who, text): s.said.append((who, text))

class FakeStings:
    """Every sting is available, so the pre-race order is exercised on the
    path a warmed-up install actually takes."""
    def __init__(s): s.played = []
    def play(s, group, interrupt=False):
        s.played.append(group)
        return "[%s]" % group

class FakeTracker:
    def confirmed_places(s, sess): return {c.id: c.place for c in sess.order}

class Booth(BoothMixin):
    def __init__(s, stings=True):
        s.booth_enabled = True; s.tts = FakeTts(); s.tracker = FakeTracker()
        s.sting_bank = FakeStings() if stings else None
        s.booth_init()
    def _short_track(s, n): return n
    def _hide_panel(s, n): pass

NAMES = ['Verstappen', 'Russell', 'Leclerc', 'Hamilton', 'Piastri', 'Alonso',
         'Ocon', 'Gasly', 'Sainz', 'Norris', 'Albon', 'Stroll']

def grid(order=None):
    order = order or list(range(len(NAMES)))
    return [FakeCar(i + 1, p + 1, NAMES[i]) for p, i in enumerate(order)]

def run(b, s, ticks=1, step=1.0):
    """Tick the booth with time genuinely advancing, since almost everything
    here is a cooldown and a zero-length race is not a test."""
    for _ in range(ticks):
        b.update_booth(s)
        b._last_spoke -= step
        for k in list(b._cat_last):
            b._cat_last[k] -= step
        if b._convo:
            b._convo["at"] -= step

def texts(b):
    return [t for _, t in b.tts.said]


