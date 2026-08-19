"""Session lifecycle: does the broadcast open, run and close correctly?

Walks a real race through the rF2 phase sequence and asserts the booth does
the right thing at each transition, including the awkward ones:

  * a FORMATION lap, and the same race with it SKIPPED (spacebar) — rF2 jumps
    straight from countdown to green, so nothing may depend on having seen a
    formation phase
  * a MID-RACE RESTART, which keeps the same track and session index and so
    cannot be detected by session identity alone
  * a restart AFTER the flag, which must revive a booth that has signed off

    python tests/lifecycletest.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cast as cast_mod
import era as era_mod
from overlay_booth import BoothMixin

# rF2 game phases, by the names the session layer produces.
GARAGE, GRIDWALK, FORMATION, COUNTDOWN, GREEN, OVER = 0, 2, 3, 4, 5, 8


class Car:
    def __init__(s, cid, place, name):
        s.id = cid; s.place = place; s.name = name; s.display_name = name
        s.is_player = (name == "YOU"); s.in_pits = False; s.laps = 0
        s.gap_ahead = 1.0; s.gap_leader = float(place); s.best_lap = None
        s.last_lap = None; s.speed = 200.0; s.finish_status = 0; s.sector = 1
        s.places_gained = 0; s.purple_lap = False; s.damage = (0,) * 8
        s.cls = "F1 Test 2025"; s.vehicle = name; s.laps_down = 0
        s.last_s1 = s.last_s2 = s.last_s3 = None


class Sess:
    def __init__(s, phase, laps=0, order=None, track="Kyalami"):
        names = order or ["Verstappen", "YOU", "Leclerc", "Hamilton"]
        s.order = [Car(i + 1, i + 1, n) for i, n in enumerate(names)]
        s.cars = {c.id: c for c in s.order}
        s.player = next(c for c in s.order if c.is_player)
        s.leader = s.order[0]
        s.valid = True; s.track = track; s.kind = "race"
        s.phase = phase
        s.green = (phase == GREEN)
        s.started = phase >= GREEN
        s.finished = (phase == OVER)
        s.num_cars = len(s.order)
        s.max_laps = 10; s.leader_laps = laps
        s.laps_left = max(0, 10 - laps)
        s.session_index = 10; s.multiclass = False
        s.full_course_yellow = False; s.yellow_sectors = (0, 0, 0)
        s.era = era_mod.classify("F1 Test 2025", "Max")
        s.player_era = s.era
        for c in s.order:
            c.laps = laps

    def car_ahead(s, c):
        i = c.place - 1
        return s.order[i - 1] if 0 < i < len(s.order) else None

    def car_behind(s, c):
        i = c.place - 1
        return s.order[i + 1] if 0 <= i < len(s.order) - 1 else None


class FakeTts:
    def __init__(s): s.said = []; s.speaking = False
    def speak(s, t, who, intensity=0, build=False, name=""):
        s.said.append((who, t))
    def interrupt(s): pass


class FakeStings:
    """Stand-in for the pre-rendered sting bank. Records what fired."""
    def __init__(s): s.played = []
    def play(s, group, interrupt=False):
        s.played.append(group)
        return "<%s sting>" % group


class FakeTracker:
    def confirmed_places(s, sess):
        return {c.id: c.place for c in sess.order}


class Booth(BoothMixin):
    def __init__(s, stings=True):
        s.booth_enabled = True; s.tts = FakeTts(); s.tracker = FakeTracker()
        s.sting_bank = FakeStings() if stings else None
        s.booth_init()
    def _short_track(s, n): return n
    def _hide_panel(s, n): pass


fails = []


def check(cond, label, extra=""):
    print(("  [ OK ] " if cond else "  [FAIL] ") + label +
          (("  " + extra) if extra else ""))
    if not cond:
        fails.append(label)


def run(b, sess, ticks=2):
    for _ in range(ticks):
        b.update_booth(sess)


def lines(b):
    return [t for _, t in b.tts.said]


# --------------------------------------------------------------------------
print("\n1. NORMAL RACE — garage -> formation -> green -> flag")
b = Booth()
run(b, Sess(GARAGE))
check("intro" in b.sting_bank.played, "intro sting fires once cars appear",
      str(b.sting_bank.played))
run(b, Sess(GRIDWALK))
run(b, Sess(FORMATION))
check("lightsout" not in b.sting_bank.played,
      "lights-out does NOT fire during the formation lap")
run(b, Sess(COUNTDOWN))
check("lightsout" not in b.sting_bank.played,
      "lights-out does NOT fire during the countdown")
run(b, Sess(GREEN))
check("lightsout" in b.sting_bank.played, "lights-out fires on green",
      str(b.sting_bank.played))
run(b, Sess(GREEN, laps=5))
b.tts.said = []
run(b, Sess(OVER, laps=10))
check("victory" in b.sting_bank.played, "victory sting fires at the flag")
# The victory call is story-shaped: a last-corner win, a comeback and a
# cruise are different categories of the same moment. Any of them satisfies
# "the race got a winner"; asserting on the plain `win` pool alone made the
# test fail the moment the booth had something more specific to say.
check(any(c == "win" or c.startswith("win_") for c in b._cat_last),
      "the winner is called by name",
      repr(lines(b)[:1]))

print("\n2. FORMATION SKIPPED (spacebar) — countdown straight to green")
b = Booth()
run(b, Sess(GARAGE))
run(b, Sess(COUNTDOWN))          # no formation phase at all
run(b, Sess(GREEN))
check("lightsout" in b.sting_bank.played,
      "lights-out still fires with no formation lap",
      str(b.sting_bank.played))

print("\n3. MID-RACE RESTART — same track, same session index")
b = Booth()
run(b, Sess(GARAGE)); run(b, Sess(GREEN))
check(b.sting_bank.played.count("lightsout") == 1, "first start called")
run(b, Sess(GREEN, laps=3))
run(b, Sess(GRIDWALK))           # player restarts
run(b, Sess(COUNTDOWN))
run(b, Sess(GREEN))
check(b.sting_bank.played.count("lightsout") == 2,
      "the RESTART gets its own start call",
      "lightsout fired %d time(s)" % b.sting_bank.played.count("lightsout"))
check(not b._said_win and not b._signed_off,
      "restart clears the finished/signed-off state")

print("\n4. RESTART AFTER THE FLAG — booth must come back on air")
b = Booth()
run(b, Sess(GARAGE)); run(b, Sess(GREEN))
run(b, Sess(OVER, laps=10))
# The wrap is a SEQUENCE — podium, verdict, sign-off, then the outro sting —
# and each beat waits on wall time so they do not run together. A tight loop
# never reaches that, so age the clock deliberately between beats rather than
# spinning 400 times and concluding it is broken.
for _ in range(6):
    b._last_spoke -= 12.0
    run(b, Sess(OVER, laps=10))
check(b._signed_off, "booth signs off after the wrap")
check("outro" in b.sting_bank.played, "outro sting fires",
      str(b.sting_bank.played))

# ONE GOODBYE PER SESSION, AND IT IS THE LAST THING SAID.
#
# The user: 'once Miles says "and that's it from FACTORtv" then boom, that's
# it, end of commentary for that session'. He also reported the ending
# repeating — and the live log shows exactly why, four seconds apart:
#
#   SAY   Michael Borda wins at Kyalami, and that's our race.   <- signoff
#   STING That's it from FACTORtv. See you next time.           <- outro
#
# Every line in `signoff` was a farewell as well as the outro, so the show
# said goodbye twice, every session, in the race AND in qualifying. Those
# pools now state the RESULT and the outro states the end.
#
# THIS IS ONE OF THE FEW PLACES THE PROSE **IS** THE RULE, so grepping it is
# correct here where LAW 20 would normally forbid it — the same exemption
# `eratest.py` uses for Chuck's biography and the archive rules. What is
# being tested is that no OTHER pool says goodbye.
import lines as _lines
FAREWELLS = ("goodbye", "thanks for watching", "see you next time",
             "see you at the next", "that's our race", "thats our race",
             "we'll see you", "join us when", "see you for the race")
guilty = []
for _pool in ("signoff", "quali_over_signoff", "podium_final", "race_verdict",
              "quali_over_verdict", "quali_over_player"):
    for _e in (_lines.pool(_pool) if hasattr(_lines, "pool") else []):
        _t = (_e.get("t") or "").lower()
        if any(w in _t for w in FAREWELLS):
            guilty.append("%s: %s" % (_pool, _e.get("t")))
check(not guilty, "only the ending phrase says goodbye",
      "; ".join(guilty[:3]))

# ...and every wording of the ending phrase actually IS one, in both chairs.
import stings as _st
for _key, _bank in (("modern", _st.STING_LINES["outro"]),
                    ("historic", _st.STING_LINES_HISTORIC["outro"])):
    bad = [t for t in _bank if "factortv" not in t.lower().replace(" ", "")]
    check(not bad, "every %s ending phrase names the channel" % _key, str(bad))

# NOTHING AIRS AFTER IT. The latch exists (`update_booth` returns immediately
# when `_signed_off`), and this is the check that it holds — because the
# user's report was that the ending repeated, and a latch nobody tests is a
# latch that will be refactored away.
said_before = len(b.tts.said)
for _ in range(40):
    b._last_spoke -= 12.0
    run(b, Sess(OVER, laps=10))
check(len(b.tts.said) == said_before,
      "and the booth is silent for the rest of the session",
      "%d lines after the ending phrase" % (len(b.tts.said) - said_before))
before = b.sting_bank.played.count("lightsout")
run(b, Sess(GRIDWALK)); run(b, Sess(COUNTDOWN)); run(b, Sess(GREEN))
check(not b._signed_off, "a restart revives the signed-off booth")
check(b.sting_bank.played.count("lightsout") == before + 1,
      "and the new race gets a start call")

print("\n5. RESTART MID-RACE REPEATEDLY (crash, restart, crash, restart)")
# A restart returns you to the GRID, so the lap count goes back to zero and
# the call is a standing start. The separate "restart" sting is for a race
# RESUMING under green after a caution, where laps are already on the board —
# an earlier version of this test drove the lap count up across restarts and
# then failed because it got the (correct) resume sting instead.
b = Booth()
run(b, Sess(GARAGE))
for _ in range(4):
    run(b, Sess(GREEN, laps=0))
    run(b, Sess(GRIDWALK))
    run(b, Sess(COUNTDOWN))
n = b.sting_bank.played.count("lightsout")
check(n == 4, "four restarts produce four start calls",
      "%d call(s)" % n)

print("\n5b. RESUMING AFTER A CAUTION uses the restart sting")
b = Booth()
run(b, Sess(GARAGE)); run(b, Sess(GREEN))
run(b, Sess(GREEN, laps=4))
b._said_start = False              # caution over, racing resumes on lap 4
run(b, Sess(GREEN, laps=4))
check("restart" in b.sting_bank.played,
      "mid-race resumption is a restart, not a standing start",
      str(b.sting_bank.played))

print("\n6. NO STING BANK (first run, cache still building)")
b = Booth(stings=False)
run(b, Sess(GARAGE))
run(b, Sess(GREEN))
check("start" in b._cat_last,
      "falls back to a LIVE start line when no sting is cached",
      repr(lines(b)[-1:]))


print("\n13. THE FLAG IS THE WINNER'S, NOT HIS")
# Reported after driving it: "on that last lap I managed to take the lead but
# then I also ran out of fuel before the flag and then the wrong race result was
# recorded as I only finished 10th."
#
# His log, twelve seconds apart:
#
#   [2097.6s] PLAYER  Dante Kandasamy  P4        <- banked into the championship
#   [2109.4s] STATE   lap 7/7  P10  fuel=0.0     <- where he actually finished
#
# `_season_record` fired on `s.finished` and read `me.place`. But the flag falls
# for the WINNER: a car coasting on an empty tank has not finished anything, and
# its position on the road at that instant is not a result. This is LAW 2's
# other half — that law asks whether the RACE was completed, this asks whether
# HE completed it.
import shutil as _sh, tempfile as _tf
import season as _S

_dir = _tf.mkdtemp(prefix="factortv_result_")
_old_career_dir = _S.CAREER_DIR
_S.CAREER_DIR = _dir
try:
    # A LADDER CAREER, because that is where the result sheet comes from — and
    # the letter is half of what this section is about.
    car = _S.create("open", me="Kandasamy", rounds=3,
                    ladder_path="single_seater", tier_index=0)
    car.data["cls"] = "F1 Test 2025"

    b = Booth()
    b.season = car
    b._season_round = {"n": 1, "slug": "interlagos", "event": "Interlagos"}
    b._season_count = True
    b._season_done = False
    b._season_settle = None

    s = Sess(GREEN, laps=6)
    s.max_laps = 7
    s.laps_left = 1
    for i, c in enumerate(s.order):
        c.laps = 6
        c.place = i + 1
    me = s.player
    # THE NAME HAS TO MATCH THE CAREER'S. A result sheet is dropped when a fact
    # is missing (the inbox's second rule), and the player's own line in the
    # classification is looked up by name — so a fixture whose driver is called
    # "YOU" produces no letter at all, for a good reason.
    me.display_name = "Kandasamy"
    me.place = 4                      # where he was when the winner crossed
    me.finish_status = 0              # ...and his race is NOT over

    # THE RACE HAS TO HAVE BEEN RUNNING, or the bookends are still on the grid:
    # the win branch is the END of a sequence, not a state.
    b._bookends(s, 90.0)

    # THE FLAG.
    s.finished = True
    s.green = False
    b._bookends(s, 100.0)
    rnd = [r for r in car.rounds if r.get("n") == 1]
    check(bool(rnd), "the result is banked at the flag, as it always was")
    check(rnd and rnd[0]["pos"] == 4,
          "with what was true at that moment", str(rnd and rnd[0]["pos"]))
    check(b._season_settle is not None,
          "but it is PROVISIONAL while his own race is still going")
    # NO POST YET. A result sheet quotes his finishing position and is frozen
    # when sent, so a letter written off a provisional place would sit in the
    # archive congratulating him on a fourth place he did not get.
    import inbox as _inbox
    _sheets = [m for m in _inbox.messages(car)
               if m["kind"].startswith("result_")]
    check(not _sheets,
          "and no result sheet is written from a provisional place",
          str([m["kind"] for m in _sheets]))

    # ...AND THEN HE COASTS. Six cars go by while he is out of fuel.
    me.place = 10
    b._season_resettle(s, 104.0)
    rnd = [r for r in car.rounds if r.get("n") == 1]
    check(rnd and rnd[0]["pos"] == 10,
          "the result follows him down the order", str(rnd and rnd[0]["pos"]))
    check(len(car.rounds) == 1,
          "and it CORRECTS the round rather than adding a second result",
          str(len(car.rounds)))

    # THE GAME SAYS HIS RACE IS OVER, and that is the end of it.
    me.finish_status = 1
    b._season_resettle(s, 112.0)
    check(b._season_settle is None,
          "once the game classifies him, nothing more is written")
    _sheets = [m for m in _inbox.messages(car)
               if m["kind"].startswith("result_")]
    check(bool(_sheets), "and the post goes out on the FINAL result",
          str([m["kind"] for m in _sheets]))
    _body = " ".join(_sheets[0]["body"]) if _sheets else ""
    check("tenth" in _body.lower(),
          "written about the race he actually had, not the one at the flag",
          _body[:70])

    # A LATER MOVE CHANGES NOTHING. The result is his result now.
    me.place = 2
    b._season_resettle(s, 130.0)
    rnd = [r for r in car.rounds if r.get("n") == 1]
    check(rnd and rnd[0]["pos"] == 10,
          "a place change after he is classified is ignored",
          str(rnd and rnd[0]["pos"]))

    # AND THE ORDINARY CASE IS UNTOUCHED: a driver who takes the flag has his
    # result banked once, immediately, with the post — which is what happens in
    # every race that does not end like his did.
    car2 = _S.create("open", me="Kandasamy", rounds=3,
                     ladder_path="single_seater", tier_index=0)
    b2 = Booth()
    b2.season = car2
    b2._season_round = {"n": 1, "slug": "kyalami", "event": "Kyalami"}
    b2._season_count = True
    s2 = Sess(GREEN, laps=6)
    s2.max_laps = 7
    s2.laps_left = 1
    for i, c in enumerate(s2.order):
        c.laps = 7
        c.place = i + 1
    s2.player.display_name = "Kandasamy"
    s2.player.place = 2
    s2.player.finish_status = 1        # he took the flag
    b2._bookends(s2, 90.0)
    s2.finished = True
    s2.green = False
    b2._bookends(s2, 100.0)
    check(b2._season_settle is None,
          "a driver who has finished needs no settling period")
    _r2 = [r for r in car2.rounds if r.get("n") == 1]
    check(_r2 and _r2[0]["pos"] == 2, "and his result is banked at once",
          str(_r2 and _r2[0]["pos"]))
finally:
    _S.CAREER_DIR = _old_career_dir
    _sh.rmtree(_dir, ignore_errors=True)


print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
