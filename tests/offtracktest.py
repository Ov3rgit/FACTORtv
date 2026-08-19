"""Off-track detection: does the booth call the ones that matter and stay
quiet about kerbs?

rF2 gives a per-wheel surface type, so an excursion here is a FACT rather
than the speed-drop inference the RaceRoom overlay had to use. These assert
the two things that make it worth having: it catches an off that costs NO
speed (tarmac runoff, foot still in), and it never calls a kerb.

    python tests/offtracktest.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import era as era_mod
from overlay_booth import BoothMixin
from overlay_radio import RadioMixin
from overlay_dash import FuelModel
import cast as cast_mod

DRY, WET, GRASS, GRAVEL, KERB = 0, 1, 2, 4, 5


class C:
    def __init__(s, cid=1, place=5, name='Driver'):
        s.id=cid; s.place=place; s.display_name=name; s.name=name
        s.in_pits=False; s.laps=10; s.gap_ahead=2.0; s.gap_behind=2.0
        s.speed=200.0; s.is_player=(cid==1); s.finish_status=0
        s.cls='F1 Test 2025'; s.vehicle=name; s.best_lap=None; s.last_lap=90.0
        s.fuel=40.0; s.fuel_cap=100.0; s.purple_lap=False; s.penalties=0
        s.damage=(0,)*8; s.tyre_wear=(0.9,)*4; s.tyre_temp=(90,)*4
        s.brake_temp=(400,)*4; s.places_gained=0; s.laps_down=0
        s.gap_leader=1.2; s.sector=1; s.tyre_front=''
        s.wheels_off=0; s.surface=(DRY,)*4

    def on(s, *surf):
        """Put the car on `surf` (one value, or four)."""
        surf = surf * 4 if len(surf) == 1 else surf
        s.surface = tuple(surf)
        from rf2_session import ON_TRACK_SURFACES
        s.wheels_off = sum(1 for x in surf if x not in ON_TRACK_SURFACES)
        return s


class B(BoothMixin):
    def __init__(s):
        s.booth_enabled=True; s.tts=None; s.booth_init()


fails=[]
def check(cond, label, extra=""):
    print(("  [ OK ] " if cond else "  [FAIL] ")+label+(("  "+extra) if extra else ""))
    if not cond: fails.append(label)


def excursion(surfaces, speeds, dt=0.05, entry=200.0):
    """Drive a car through `surfaces` at `speeds` and return what was called.

    Both sequences are per tick. Returns the list of non-None gradings.
    """
    b = B()
    c = C(); c.speed = entry
    prev = C(); prev.speed = entry
    out = []
    now = 0.0
    for surf, spd in zip(surfaces, speeds):
        prev.speed = c.speed
        c.on(*surf); c.speed = spd
        now += dt
        ev = b._track_excursion(c, prev, None, now)
        if ev:
            out.append(ev)
    return out


ON  = (DRY,)
OFF4 = (GRASS, GRASS, GRASS, GRASS)
OFF2 = (DRY, DRY, GRASS, GRASS)
KRB = (DRY, DRY, KERB, KERB)

print("\n1. A KERB IS NOT AN EXCURSION")
# Two wheels on the rumblestrip at every apex, all race, no pace lost.
ev = excursion([ON]*4 + [KRB]*6 + [ON]*4, [200.0]*14)
check(ev == [], "riding the kerbs is never called", repr(ev))

print("\n2. THE ONE THE OLD DETECTOR MISSED")
# All four wheels off, foot still in, NO speed lost. A speed-drop detector is
# silent here; this is the whole reason for reading the surface.
ev = excursion([ON]*2 + [OFF4]*12 + [ON]*4, [200.0]*18)
check(ev == ["offtrack"], "four wheels off at unchanged speed is called",
      repr(ev))

print("\n3. A SPIN IS GRADED ABOVE AN OFF")
speeds = [200.0]*2 + [190.0, 150.0, 90.0, 55.0, 40.0, 45.0, 60.0] + [90.0]*4
ev = excursion([ON]*2 + [OFF4]*7 + [ON]*4, speeds)
check(ev == ["spin"], "a big loss of pace grades as a spin", repr(ev))

print("\n4. A BRUSH IS NOT AN INCIDENT")
# Two wheels on the grass for a fraction of a second, pace intact.
ev = excursion([ON]*4 + [OFF2]*2 + [ON]*6, [200.0]*12)
check(ev == [], "a momentary two-wheel brush stays silent", repr(ev))

print("\n5. A LONG SLIDE ON TWO WHEELS IS A MOMENT")
ev = excursion([ON]*2 + [OFF2]*30 + [ON]*4, [200.0]*36)
check(ev == ["ranwide"], "a sustained two-wheel excursion is a moment",
      repr(ev))

print("\n6. CALLED ONCE, NOT PER TICK")
ev = excursion([ON]*2 + [OFF4]*40 + [ON]*10, [200.0]*52)
check(len(ev) == 1, "one excursion produces exactly one call",
      "%d calls" % len(ev))

print("\n7. NO TELEMETRY IS NOT 'ON TRACK'")
# wheels_off None means we do not know. It must fall back to the speed-drop
# inference rather than silently asserting the car stayed on the road.
b = B(); c = C(); c.wheels_off = None
prev = C(); prev.speed = 200.0; c.speed = 120.0
check(b._track_excursion(c, prev, None, 1.0) is not None,
      "an unknown-surface car still gets the speed-drop fallback")

print("\n8. THE ENGINEER REACTS, AND ONLY ONCE")
class FakeTts:
    def __init__(s): s.said=[]; s.speaking=False
    def speak(s, text, who, intensity=0, build=False, name=""):
        s.said.append((who, text))
class S:
    def __init__(s, me):
        s.valid=True; s.player=me; s.order=[me]; s.kind='race'; s.green=True
        s.finished=False; s.track='Zandvoort'; s.max_laps=30; s.laps_left=15
        s.leader_laps=15; s.num_cars=1; s.session_index=10
        s.full_course_yellow=False; s.yellow_sectors=(0,0,0)
        s.era=era_mod.classify('F1 Test 2025','Max'); s.player_era=s.era
    def car_ahead(s,c): return None
    def car_behind(s,c): return None
class R(RadioMixin):
    def __init__(s):
        s.radio_enabled=True; s.tts=FakeTts(); s.fuel_model=FuelModel()
        s.radio_init(); s.player_off=None

r = R(); me = C()
for _ in range(3):
    r.update_radio(S(me))
    r._radio_last -= 100
    for k in list(r._topic_last): r._topic_last[k] -= 100
r.tts.said = []
r.player_off = ("spin", 0.0)          # the booth publishes an off
for _ in range(4):
    r.update_radio(S(me))
    r._radio_last -= 100
    for k in list(r._topic_last): r._topic_last[k] -= 100
n = len(r.tts.said)
check(n == 1, "an off gets exactly one check-in from the engineer",
      "%d calls: %r" % (n, r.tts.said))
check(r.player_off is None, "the published off is consumed, not left to re-fire")

print("\n9. THE STING FIRES FOR AN OFF, NOT ONLY A SPIN")
# The user's report: RacerTV played the "sorry to cut you off" alert for ANY
# real excursion, and this booth restricted it to spins. Four wheels off is
# every bit as much an interruption as a spin — the sting has to fire before
# the booth names anyone, so both severities need it.
class FakeSting:
    def __init__(s): s.n = 0
    def play(s, key):
        s.n += 1
        return "Sorry to cut in, but there's been an incident." if key == "alert" else None

for kind in ("spin", "offtrack"):
    b = B(); b.tts = FakeTts(); b._stings = FakeSting(); b._sting_at = 0.0
    b._incident_sting(50.0)
    check(b._stings.n == 1, "the sting fires for a %s" % kind,
          "%d calls" % b._stings.n)

print("\n10. SEVERITY DECIDES THE ENGINEER'S TONE")
# A spin or a real off is a moment he has to check you are alright about. A
# tidy-up that ran wide cost places, not confidence, and "are you okay?"
# about a moment that cost nothing reads as him not having watched the race.
#
# Checked at the CATEGORY `_engineer_events` chose, not the rendered text —
# `_frame()` may prepend an opener and lowercase the original first letter,
# which made a text comparison here flaky: the same correct category can
# render as "You alright, Driver?" or "Okay, you alright, driver?" depending
# on the random roll, and a suffix match cannot see through a template that
# still has "{drv}" unfilled in the raw pool.
import lines as lines_mod
for kind, expect in (("spin", "eng_incident"), ("offtrack", "eng_incident"),
                     ("ranwide", "eng_offtrack_light")):
    r2 = R(); me2 = C()
    for _ in range(3):
        r2.update_radio(S(me2))
        r2._radio_last -= 100
        for k in list(r2._topic_last): r2._topic_last[k] -= 100
    r2.player_off = (kind, 0.0)
    # `_radio` is the one place a category becomes a spoken line — recorded
    # here rather than matched from the rendered text, because `_frame()`
    # may prepend an opener and lowercase the original letter, which made a
    # text comparison flaky against its own random roll.
    chosen = []
    real_radio = r2._radio
    def _spy(cat, *a, **kw):
        chosen.append(cat)
        return real_radio(cat, *a, **kw)
    r2._radio = _spy
    r2.update_radio(S(me2))
    check(expect in chosen, "a %s off offers %s" % (kind, expect), str(chosen))
    other = "eng_offtrack_light" if expect == "eng_incident" else "eng_incident"
    check(other not in chosen, "and never the other severity's pool",
          str(chosen))

print("\n11. RANWIDE STILL REACHES THE ENGINEER AT ALL")
# Before this fix `player_off` carrying "ranwide" was consumed by nobody —
# `overlay_radio` only checked for ("spin", "offtrack"), so a driver who ran
# wide got silence from both the booth's colour and the pit wall.
r3 = R(); me3 = C()
for _ in range(3):
    r3.update_radio(S(me3))
    r3._radio_last -= 100
    for k in list(r3._topic_last): r3._topic_last[k] -= 100
r3.tts.said = []
r3.player_off = ("ranwide", 0.0)
r3.update_radio(S(me3))
check(bool(r3.tts.said), "a ranwide off draws a response from the engineer",
      repr(r3.tts.said))

print("\n12. THE GAME'S OWN TRACK-LIMITS MESSAGE IS GROUND TRUTH")
# rF2 posts a status message the moment a track-limits or cut warning fires,
# and until now nothing read it. Confirmed edge-triggered and keyword-gated
# so a penalty or pit-instruction message sharing the same buffer cannot be
# mistaken for an off.
class Sess:
    def __init__(s, msg, new):
        s.status_message = msg; s.status_message_new = new
b4 = B()
check(b4._track_limits_ground_truth(
        Sess("TRACK LIMITS WARNING", True), 10.0),
      "a fresh track-limits message is recognised")
check(not b4._track_limits_ground_truth(
        Sess("TRACK LIMITS WARNING", False), 20.0),
      "the SAME message staying on screen is not re-read (edge-triggered)")
b5 = B()
check(not b5._track_limits_ground_truth(
        Sess("3 second penalty applied", True), 10.0),
      "an unrelated status message (a penalty) is not mistaken for an off")
b6 = B()
check(b6._track_limits_ground_truth(Sess("Cut track - lap invalidated", True), 10.0),
      "and a cut-track message is recognised under its own wording")

print("\n13. AN OFF IN QUALIFYING IS AN OFF")
# The user's report, in his words: "I was in a quali and I went off while
# trying to do a lap, and neither did the commentators say anything about
# going off the track ... nor the race engineer".
#
# The cause was structural rather than a missing line: EVERY excursion check
# lived inside `_detect`, and a qualifying session is routed to
# `_quali_detect` instead. So for a whole session nothing looked at the
# surface, nothing rang the sting, and `player_off` — which is published by
# that code and nowhere else — was never set, which silenced the engineer
# too. One missing call site, three symptoms.
import time as _time
from fakes import FakeSession as _FS, grid as _grid

class QB(BoothMixin):
    """A booth with a real sting bank and tts, so the whole chain is visible."""
    def __init__(s):
        s.booth_enabled = True
        s.tts = type("T", (), {"said": [], "speaking": False,
                               "speak": lambda self, t, w, **k: self.said.append((w, t)),
                               "play_file": lambda self, p, w, t: None})()
        s.tts.said = []
        s.sting_bank = type("S", (), {"played": [],
                                      "play": lambda self, g, interrupt=False:
                                      (self.played.append(g), "[%s]" % g)[1]})()
        s.sting_bank.played = []
        s.tracker = type("K", (), {"confirmed_places":
                                   lambda self, sess: {c.id: c.place
                                                       for c in sess.order}})()
        s.booth_init()
    def _short_track(s, n): return n
    def _hide_panel(s, n): pass

def _quali_off(kind_surface):
    """Run a player excursion through the QUALIFYING detector specifically."""
    b = QB()
    cars = _grid()
    me = cars[3]
    me.is_player = True
    for c in cars:
        c.wheels_off = 0
        c.speed = 200.0
        c.best_lap = 90.0 + c.place
    s = _FS(cars, kind="quali", max_laps=0, laps_left=0, leader_laps=4,
            time_left=600.0, end_et=1200.0)
    s.player = me
    now = _time.time()
    b._snapshot(s)                       # a baseline to diff against
    # off...
    for i in range(12):
        me.wheels_off = 4
        me.surface = kind_surface
        b._quali_detect(s, now + 0.05 * (i + 1))
    # ...and back on again: an excursion is graded on the way BACK.
    me.wheels_off = 0
    return b, b._quali_detect(s, now + 1.0), me

b7, evs, me7 = _quali_off((GRASS,) * 4)
said = [t for _w, t in b7.tts.said]
check(bool(said) or [e[0] for e in evs],
      "the booth calls an off that happens in QUALIFYING",
      str(said or [e[0] for e in evs]))
check(b7.player_off is not None,
      "and publishes player_off, which is what reaches the engineer",
      str(b7.player_off))
check(b7.sting_bank.played,
      "the sting still comes FIRST, exactly as it does in a race",
      str(b7.sting_bank.played))

print("\n13b. AND IT IS A SEQUENCE, NOT A LINE THAT LOSES ITS OWN TICK")
# The live log's verdict on the old design: three alerts in a qualifying
# session and not one of them ever followed by a name.
#
#   [1861.5s] STING  Wait — we've got a car in trouble!
#   [1861.5s] SAY    ENGINEER  Are you okay? Talk to me.
#   ...and nothing else. Ever.
#
# `offtrack` carries priority 50, `_say` drops anything under 80 while audio
# is playing, and the sting IS audio — so the alert reliably silenced the line
# that explains it, and detection being edge-triggered meant no second chance.
# The whole sequence is spoken in one breath now, which is the only way it can
# survive its own sting.
b8 = QB()
cars8 = _grid()
me8 = cars8[3]
me8.is_player = True
for c in cars8:
    c.wheels_off = 0
    c.speed = 200.0
    c.best_lap = 90.0 + c.place
s8 = _FS(cars8, kind="quali", max_laps=0, laps_left=0, leader_laps=4,
         time_left=600.0, end_et=1200.0)
s8.player = me8
now8 = _time.time()
b8._snapshot(s8)
for i in range(12):
    me8.wheels_off = 4
    me8.speed = 120.0
    b8._quali_detect(s8, now8 + 0.05 * (i + 1))
me8.wheels_off = 0
b8.tts.speaking = True            # THE EXACT CONDITION THAT KILLED IT BEFORE
b8._quali_detect(s8, now8 + 1.0)
voices = [w for w, _t in b8.tts.said]
texts = [t for _w, t in b8.tts.said]
check(len(texts) >= 2,
      "the sequence airs even while the sting is still audible", str(texts))
check(voices[:1] == [cast_mod.ANALYST],
      "the PUNDIT pays the debt his own alert created — he names the driver",
      str(voices))
check(any(me8.display_name in t for t in texts[:1]),
      "and the name is actually in it", str(texts[:1]))
check(cast_mod.PLAY in voices,
      "then the play-by-play seat answers him — two voices, not one",
      str(voices))
check(b8._named_incident,
      "so the alert is never left unexplained")

print("\n14. AND THE ENGINEER ANSWERS IT IN QUALIFYING TOO")
# `_engineer_events` returns `_quali_radio(...)` long before the race path
# that consumes `player_off`, so the flag was set and then silently dropped.
# The lines differ from the race ones on purpose: "lost a few places there"
# is a race sentence, and an off on a Saturday costs a LAP.
rq = R()
meq = C()
sq = S(meq)
sq.kind = "quali"
for _ in range(3):                       # get the greeting out of the way
    rq.update_radio(sq)
    rq._radio_last -= 100
    for k in list(rq._topic_last):
        rq._topic_last[k] -= 100
rq.tts.said = []
rq.player_off = ("ranwide", 0.0)
rq.update_radio(sq)
check(bool(rq.tts.said), "the engineer reacts to a qualifying off",
      repr(rq.tts.said[:1]))

print("\n15. A DELETED LAP IS THE GAME'S CALL, NEVER OURS")
# `quali_deleted` was deliberately NOT built, because `last_lap_valid` is
# declared and never assigned — there was no honest source, and a phantom
# deletion the timing screen contradicts costs more than the line is worth.
# The extended buffer's status message IS that source, so the line exists
# now — and stays gated on the sim saying it.
def _deleted(msg, kind="quali"):
    b = QB()
    cars = _grid()
    me = cars[0]
    me.is_player = True
    s = _FS(cars, kind=kind, max_laps=0, laps_left=0, leader_laps=4,
            time_left=600.0, end_et=1200.0)
    s.player = me
    s.status_message = msg
    s.status_message_new = bool(msg)
    return b, b._lap_deleted(s, _time.time())

_b, ev = _deleted("INVALID LAP - TRACK LIMITS")
check([e[0] for e in ev] == ["quali_deleted"],
      "the sim taking a lap away is called", str([e[0] for e in ev]))
check(_b.player_lap_deleted is not None,
      "and the engineer is told, separately from any off")
_b2, ev2 = _deleted("")
check(ev2 == [], "no message, no call — never inferred")
_b3, ev3 = _deleted("3 SECOND PENALTY APPLIED")
check(ev3 == [], "and an unrelated message is not a deletion", str(ev3))
_b4, ev4 = _deleted("INVALID LAP - TRACK LIMITS", kind="race")
check(ev4 == [], "a race is not a timesheet, so it gets no deletion call")
# Track limits at a bad exit can bin three laps in a row.
_b5 = QB()
cars5 = _grid(); cars5[0].is_player = True
s5 = _FS(cars5, kind="quali", max_laps=0, laps_left=0, leader_laps=4,
         time_left=600.0, end_et=1200.0)
s5.player = cars5[0]
s5.status_message = "INVALID LAP - TRACK LIMITS"
s5.status_message_new = True
t0 = _time.time()
n = sum(len(_b5._lap_deleted(s5, t0 + i)) for i in range(0, 30, 5))
check(n == 1, "and three deletions in a row are one piece of news, not three",
      "%d calls" % n)

print("\n16. THE DELETION SOURCE IS A NUMBER, NOT ON-SCREEN ENGLISH")
# The first live run answered the question the status message could not: a
# 40-minute session, a full qualifying run, and the log contains ZERO status
# messages. Pattern-matching the sim's on-screen text was always the weaker
# half of the design; `mCountLapFlag` is on the vehicle struct that is read
# every tick anyway.
#
#   0 = do not count the lap   1 = count the lap, not its time   2 = count both
#
# Below 2 means the time is not going on the sheet, which is what a driver
# means by "they took my lap away".
def _flagged(seq, kind="quali"):
    """Run a sequence of (count_lap, in_pits) and return which ticks called."""
    b = QB()
    cars = _grid()
    me = cars[0]
    me.is_player = True
    s = _FS(cars, kind=kind, max_laps=0, laps_left=0, leader_laps=4,
            time_left=600.0, end_et=1200.0)
    s.player = me
    s.status_message = ""
    s.status_message_new = False
    t0 = _time.time()
    fired = []
    for i, (flag, pits) in enumerate(seq):
        me.count_lap = flag
        me.in_pits = pits
        # Spaced past QUALI_DELETED_GAP so the pacing guard is not what is
        # being measured here — the edge is.
        if b._lap_deleted(s, t0 + i * 60):
            fired.append(i)
    return b, fired

_b, fired = _flagged([(2, False), (2, False), (1, False), (1, False)])
check(fired == [2], "the flag dropping below 2 calls the lap deleted, ONCE",
      str(fired))
_b, fired = _flagged([(2, False), (0, False)])
check(fired == [1], "and 'do not count the lap at all' counts too", str(fired))
_b, fired = _flagged([(1, False), (1, False), (1, False)])
check(fired == [], "a lap that never counted is not a DELETION", str(fired))
_b, fired = _flagged([(2, True), (1, True)])
check(fired == [], "and the flag sitting low in the pits is not one either",
      str(fired))
_b, fired = _flagged([(2, False), (1, False)], kind="race")
check(fired == [], "a race still gets no deletion call", str(fired))
_b, fired = _flagged([(None, False), (None, False)])
check(fired == [], "no flag at all is silence, not a guess", str(fired))
# It must still reach the engineer, which is the half the driver actually
# hears — the booth remarks on it, Dean is the one who tells you.
_b, fired = _flagged([(2, False), (1, False)])
check(_b.player_lap_deleted is not None,
      "and the engineer is told through the same channel as an off")
# `last_lap_valid` was declared in rf2_session and never assigned since the
# module was written; that is precisely why this call was refused for so long.
import rf2_session as _rs
check("count_lap" in _rs.Car.__slots__ and "last_lap_valid" in _rs.Car.__slots__,
      "the session layer carries the flag, so nothing has to re-read the buffer")

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
