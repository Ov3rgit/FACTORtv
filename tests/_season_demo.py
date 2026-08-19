"""Print a whole CAREER, several rounds of it, without driving anything.

The single question this answers: does the context stay cohesive across
rounds? A race reads fine on its own and still be nonsense as round four of a
season — the standings drift, the booth forgets it has been to a circuit
before, the championship talk contradicts the table. The only way to see that
is to read several rounds in order.

    python tests/_season_demo.py [rounds] [preset]
    python tests/_season_demo.py 3
    python tests/_season_demo.py 5 f1_2021

Runs entirely on temp files: your real careers/ folder is never touched.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import season as season_mod                                   # noqa: E402

_TMP = tempfile.mkdtemp(prefix="factortv_seasondemo_")
season_mod.CAREER_DIR = _TMP

import cast as cast_mod                                       # noqa: E402
import career as career_mod                                   # noqa: E402
import track as track_mod                                     # noqa: E402
from fakes import Booth, FakeSession, grid, run                # noqa: E402

ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
PRESET = sys.argv[2] if len(sys.argv) > 2 else "f1_2025"
ME = "Kandasamy"
CLS = "F1 Test 2025"

# Where the player finishes each round. Deliberately a shape rather than a
# list of good results: a career that only ever goes well never exercises the
# lines about slipping backwards or losing a championship lead.
FINISHES = [3, 1, 5, 2, 8, 1, 4, 2]


def line(ch="-", n=74):
    print(ch * n)


def say(booth, limit=None):
    for who, text in (booth.tts.said[:limit] if limit else booth.tts.said):
        print("   %-16s %s" % (cast_mod.name_of(who), text))


def race_round(car, rnd, finish):
    """One round: the build-up, a slice of the race, and the wrap."""
    slug = rnd["slug"]
    circuit = track_mod.Track(slug)
    cars = grid()
    for i, c in enumerate(cars):
        c.cls = CLS
        c.is_player = False
        c.started_place = c.place
        c.gap_ahead = 2.5
        c.laps = 20
    me = cars[finish - 1]
    me.is_player = True
    me.display_name = ME
    me.started_place = min(len(cars), finish + 2)

    b = Booth()
    b.season = car
    b.season_record = True
    b.career = HISTORY

    print()
    line("=")
    print("ROUND %d  —  %s  (%s)   player finishes P%d"
          % (rnd["n"], rnd.get("event") or slug, circuit.name, finish))
    line("=")

    # BUILD-UP: the pre-race running order, which is where season and career
    # context actually lands.
    pre = FakeSession(cars, circuit=circuit, green=False, started=False,
                      leader_laps=0, laps_left=20, max_laps=20)
    pre.player = me
    print(" BEFORE THE RACE")
    run(b, pre, ticks=18, step=2.2)
    say(b)
    if b.sting_bank.played:
        print("   %-16s [%s]" % ("(sting)", ", ".join(b.sting_bank.played)))

    # A slice of the middle, so the demo shows the race is being watched and
    # not just book-ended.
    b.tts.said = []
    print(" DURING")
    for lap in range(2, 18):
        s = FakeSession(cars, circuit=circuit, leader_laps=lap,
                        laps_left=20 - lap, max_laps=20)
        s.player = me
        for _ in range(6):
            run(b, s, ticks=1, step=5.0)
    say(b, limit=6)

    # THE WRAP, including the championship.
    b.tts.said = []
    fin = FakeSession(cars, circuit=circuit, finished=True, green=False,
                      leader_laps=20, laps_left=0, max_laps=20)
    fin.player = me
    print(" AFTER THE FLAG")
    for _ in range(10):
        b.update_booth(fin)
        b._last_spoke -= 8.0
    say(b)


HISTORY = career_mod.History(os.path.join(_TMP, "_career.json"))

try:
    car = season_mod.create(PRESET, me=ME)
    if car is None:
        print("no such preset: %s" % PRESET)
        sys.exit(1)
    print("CAREER: %s   %s rounds" % (car.name, car.total_rounds or "open"))

    for i in range(ROUNDS):
        rnd = car.next_round()
        if rnd is None:
            print("\nthe season is complete.")
            break
        race_round(car, rnd, FINISHES[i % len(FINISHES)])
        st = car.title_state()
        print()
        print(" CHAMPIONSHIP after %d round(s):" % st["rounds_done"])
        for n, (name, pts) in enumerate(st["table"][:5], 1):
            mark = "  <-- you" if name == ME else ""
            print("   %d. %-16s %3d%s" % (n, name, pts, mark))
        print("   %s leads. %s rounds left, %s points still available."
              % (st["leader"], st["rounds_left"], st["points_available"]))
finally:
    shutil.rmtree(_TMP, ignore_errors=True)
