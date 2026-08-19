"""Season / championship test.

Runs entirely on temp files: careers are created, raced, recorded, undone and
deleted without touching the real `careers/` folder or the settings.

The two things worth protecting here are the rules the whole feature rests
on, both stated in season.py:

  * only a completed race counts
  * never state title maths that is not exactly true

    python tests/seasontest.py
"""
import os, shutil, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import season as season_mod
import track as track_mod
from fakes import Booth, FakeSession, grid, run

fails = []
def check(cond, label, extra=""):
    print(("  [ OK ] " if cond else "  [FAIL] ") + label + (("  " + extra) if extra else ""))
    if not cond:
        fails.append(label)

tmp = tempfile.mkdtemp(prefix="factortv_season_")
season_mod.CAREER_DIR = tmp
F1 = "F1 Test 2025"


def finished_race(cars, laps=20):
    """A session as it looks at the chequered flag."""
    s = FakeSession(cars, finished=True, green=False, leader_laps=laps,
                    laps_left=0, circuit=track_mod.Track("Montreal"))
    for c in cars:
        c.laps = laps
        c.cls = F1
    s.player = next(c for c in cars if c.is_player)
    return s


try:
    print("\n1. PRESETS AND CREATION")
    pres = season_mod.presets()
    # THE OPEN SEASON IS THE ONLY FORMAT NOW. The fixed F1 calendars were
    # removed: they matched only at their own circuits, so a career raced
    # anywhere else silently did nothing — no round, no prompt, no context.
    # The live 2021 run raced at Montreal, which the filtered 2021 calendar
    # did not contain, and the whole career was invisible for the session.
    # The season's identity lives in the CAR CLASS instead.
    check("open" in pres, "presets load", ", ".join(sorted(pres)))
    check(not any(p.get("calendar") for p in pres.values()),
          "and none of them is a fixed calendar")
    car = season_mod.create("open", me="Kandasamy", rounds=24,
                            only_installed=False)
    check(car is not None and car.total_rounds == 24,
          "a 24-round open season can be created")
    check(len(season_mod.list_careers()) == 1, "and is listed")

    print("\n2. MATCHING A SESSION TO A ROUND")
    m = car.match("montreal", F1)
    check(m and m["n"] == 1, "any circuit is the next round", str(m and m["n"]))
    check(car.match("daytona", F1) is not None,
          "including one no calendar would ever have listed")

    print("\n3. THE LAW — only a completed race counts")
    base = {"n": 1, "slug": "montreal", "event": "Canadian Grand Prix",
            "cls": F1, "me": "Kandasamy", "grid": 5, "field": 20,
            "classified": [("Kandasamy", 3), ("Norris", 1), ("Piastri", 2)],
            "race_laps": 20}
    quit_early = dict(base, pos=18, laps=2)
    check(car.record(quit_early) is None,
          "a race abandoned on lap two is refused")
    check(len(car.rounds) == 0, "and nothing is written to the championship")
    real = dict(base, pos=3, laps=20)
    check(car.record(real) is not None, "the race he finished is recorded")
    check(len(car.rounds) == 1, "and the round is banked")

    print("\n4. POINTS ARE COMPUTED, NOT INHERITED")
    table = dict(car.standings())
    check(table.get("Norris") == 25 and table.get("Piastri") == 18
          and table.get("Kandasamy") == 15,
          "F1 points by finishing position", str(sorted(table.items())))

    print("\n5. RE-RUNNING A ROUND REPLACES IT")
    car.record(dict(base, pos=1, laps=20,
                    classified=[("Kandasamy", 1), ("Norris", 2)]))
    check(len(car.rounds) == 1, "a repeat of the round just raced replaces it",
          str(len(car.rounds)))
    check(dict(car.standings()).get("Kandasamy") == 25,
          "and the standings reflect the new result only")

    print("\n6. THE CLASS LOCK")
    check(car.data["cls"] == F1, "the first result locks the class")
    check(car.match("silverstone", "Some GT3 Field") is None,
          "a GT3 race cannot become a round of an F1 championship")
    check(car.match("silverstone", F1) is not None, "the right class still can")

    print("\n7. TITLE MATHS IS EXACT OR ABSENT")
    st = car.title_state()
    check(st["leader"] == "Kandasamy" and st["my_place"] == 1,
          "the leader is whoever actually has the points")
    check(st["rounds_left"] == 23, "rounds remaining is real", str(st["rounds_left"]))
    check(st["points_available"] == 23 * 25, "so points available is exact",
          str(st["points_available"]))
    check(st["decided"] is False, "one round in, nothing is decided")
    check(st["can_catch"] is True, "and everyone can still catch up")

    # An open season has no end, so it must refuse to do title maths at all.
    op = season_mod.create("open", me="Kandasamy", only_installed=False)
    op.record(dict(base, n=1, pos=1, laps=20,
                   classified=[("Kandasamy", 1), ("Norris", 2)]))
    ost = op.title_state()
    check(ost["rounds_left"] is None and ost["points_available"] is None,
          "an open season knows it cannot count what is left")
    check(ost["decided"] is False and ost["can_catch"] is None,
          "so it never claims a title is settled", str(ost["can_catch"]))
    check(op.total_rounds == 0, "and never claims a round total")

    print("\n8. A DECIDED CHAMPIONSHIP")
    solo = season_mod.create("open", me="Kandasamy", rounds=24,
                             only_installed=False)
    for i in range(1, 24):
        solo.record({"n": i, "slug": "x", "pos": 1, "laps": 20,
                     "race_laps": 20, "cls": F1, "me": "Kandasamy",
                     "classified": [("Kandasamy", 1), ("Norris", 2)]})
    st = solo.title_state()
    check(st["rounds_left"] == 1, "one round to go", str(st["rounds_left"]))
    check(st["decided"] is True,
          "a lead bigger than the points left IS decided",
          "lead=%d avail=%d" % (st["leader_points"] - st["second_points"],
                                st["points_available"]))

    print("\n9. UNDO")
    n_before = len(solo.rounds)
    solo.drop_last()
    check(len(solo.rounds) == n_before - 1, "the last result can be undone")
    check(season_mod.load(solo.slug) is not None
          and len(season_mod.load(solo.slug).rounds) == n_before - 1,
          "and the undo is persisted")

    print("\n10. THE BOOTH SPEAKS THE SEASON")
    b = Booth()
    b.season = car
    b.season_record = True
    cars = grid()
    me = cars[2]
    for c in cars:
        c.is_player = False
        c.cls = F1
    me.is_player = True
    me.display_name = "Kandasamy"
    s = FakeSession(cars, circuit=track_mod.Track("Silverstone"))
    s.player = me
    b._season_arm(s)
    check(b._season_round and b._season_round["n"] == 2,
          "the booth knows which round it is",
          str(b._season_round and b._season_round["n"]))
    cat, kw = b._season_call(s)
    check(cat in ("season_round", "season_round_anytrack", "title_lead",
                  "title_chase", "season_midway", "season_late"),
          "and has something to say about it", str(cat))
    import lines as lines_mod
    text, _, _ = lines_mod.pick(cat, s.era, kw)
    check("{" not in (text or "x"), "with every slot filled", repr(text))
    # "N to run after this one" comes from the DECLARED LENGTH. Round 2 of a
    # 24-race season has 22 to come — which is exactly why a declared length
    # matters: without one there is no honest number here at all.
    check(kw["left"] == 22, "'rounds to go' counts from the declared length",
          "left=%s" % kw["left"])

    # No career, no season talk. This is the normal case for a one-off race.
    b.season = None
    b._season_arm(s)
    check(b._season_call(s)[0] is None, "no career means silence, not a guess")

    print("\n11. RECORDING HAPPENS AT THE FLAG, ONCE")
    b = Booth()
    b.season = season_mod.create("open", me="Kandasamy", rounds=24,
                                   only_installed=False)
    b.season_record = True
    cars = grid()
    for c in cars:
        c.is_player = False
    me = cars[1]
    me.is_player = True
    me.display_name = "Kandasamy"
    fin = finished_race(cars)
    b._season_arm(fin)
    b._season_record(fin)
    check(len(b.season.rounds) == 1, "the flag banks the round",
          str(len(b.season.rounds)))
    # Half distance: the player pulled off. Nothing may be written.
    b2 = Booth()
    b2.season = season_mod.create("open", me="Kandasamy", rounds=24,
                                   only_installed=False)
    b2.season_record = True
    cars2 = grid()
    for c in cars2:
        c.is_player = False
    cars2[1].is_player = True
    fin2 = finished_race(cars2)
    cars2[1].laps = 3
    b2._season_arm(fin2)
    b2._season_record(fin2)
    check(len(b2.season.rounds) == 0,
          "a player who covered three laps of twenty is not a result")

    print("\n12. A SEASON HAS A SHAPE")
    five = season_mod.create("open", me="Kandasamy", rounds=5)
    shape = [five.phase(n) for n in range(1, 6)]
    check(shape == ["opener", "early", "midway", "late", "finale"],
          "a five-race season runs opener/early/midway/late/finale",
          ", ".join(shape))
    check(five.total_rounds == 5,
          "an open season of declared length knows its total")
    endless = season_mod.create("open", me="Kandasamy", rounds=0)
    check(endless.total_rounds == 0 and endless.phase(4) is None,
          "a season with no declared length has no shape to speak of")

    print("\n13. RACE ANYWHERE, ONE CLASS")
    # The format that actually fits how the game gets played: N races, any
    # circuit, locked to the car class of the first result.
    anyw = season_mod.create("open", me="Kandasamy", rounds=3)
    for i, slug in enumerate(("hockenheim", "daytona", "spa"), 1):
        m = anyw.match(slug, F1)
        check(m is not None and m["n"] == i,
              "race %d can be anywhere — %s is round %s"
              % (i, slug, m and m["n"]))
        anyw.record({"n": m["n"], "slug": slug, "pos": 2, "laps": 20,
                     "race_laps": 20, "cls": F1, "me": "Kandasamy",
                     "classified": [("Senna", 1), ("Kandasamy", 2)]})
    check(anyw.match("monza", F1) is None,
          "and once the season is complete it takes no more rounds")

    # A repeat circuit is a NEW round, unless it is the one just raced.
    rerun = season_mod.create("open", me="Kandasamy", rounds=5)
    for slug in ("hockenheim", "spa", "monza"):
        m = rerun.match(slug, F1)
        rerun.record({"n": m["n"], "slug": slug, "pos": 1, "laps": 20,
                      "race_laps": 20, "cls": F1, "me": "Kandasamy",
                      "classified": [("Kandasamy", 1)]})
    again = rerun.match("spa", F1)
    check(again and again["n"] == 4 and not again["done"],
          "racing a circuit again later is a NEW round", str(again))
    redo = rerun.match("monza", F1)
    check(redo and redo["n"] == 3 and redo["done"],
          "but re-running the round just raced replaces it", str(redo))
    check([r["n"] for r in anyw.visits("spa")] == [3],
          "the season remembers which round happened where",
          str(anyw.visits("spa")))

    print("\n14. AN OPEN SEASON NEEDS NO CIRCUITS TO BE INSTALLED")
    # The whole "do you own this track" problem disappears with the fixed
    # calendars. An open season has no calendar to filter, so no round can
    # ever be unreachable — which is exactly the failure the 2021 career hit:
    # its calendar was five circuits and the user raced at Montreal.
    real_installed = track_mod.installed
    track_mod.installed = lambda force=False: {"monza"}
    try:
        anyt = season_mod.create("open", me="Kandasamy", rounds=8)
        check(anyt.calendar == [], "an open season carries no calendar",
              str(anyt.calendar))
        check(anyt.match("suzuka", F1) is not None,
              "and a circuit you do not even own is still a round")
        check(anyt.total_rounds == 8,
              "while the declared length still gives exact title maths")
    finally:
        track_mod.installed = real_installed

    print("\n15. THE CLASS CAN BE CHOSEN UP FRONT")
    picked = season_mod.create("open", me="Kandasamy", rounds=3,
                               cls="StockCar 2018 X Series")
    check(picked.data["cls"] == "StockCar 2018 X Series",
          "a career can be locked to a class before racing")
    check(picked.match("spa", "StockCar 2018 X Series") is not None,
          "the chosen class matches")
    check(picked.match("spa", F1) is None, "and anything else does not")
    loose = season_mod.create("open", me="Kandasamy", rounds=3)
    check(loose.data["cls"] == "",
          "leaving it unset still means 'decide on the first race'")
    check(loose.match("spa", F1) is not None,
          "so any class matches until one is recorded")

    print("\n16. RACING UNDER ANOTHER NAME")
    named = season_mod.create("open", me="Kandasamy", rounds=3)
    check(named.me == "Kandasamy", "a career defaults to the settings name")
    named.set_driver("Nigel Mansell")
    check(named.me == "Nigel Mansell",
          "and can be raced under a driver's own name")
    check(season_mod.load(named.slug).me == "Nigel Mansell", "which persists")
    named.set_driver("")
    check(named.me == "Kandasamy", "clearing it restores the settings name")

    print("\n17. QUALIFYING IS REMEMBERED")
    q = season_mod.create("open", me="Kandasamy", rounds=3)
    check(q.uses_quali, "careers expect qualifying by default")
    check(q.quali_result() is None, "with nothing on record to begin with")
    q.record_quali(1, 4, 26, "silverstone")
    last = q.quali_result()
    check(last and last["pos"] == 4 and last["slug"] == "silverstone",
          "a qualifying position is banked against its round", str(last))
    q.record_quali(1, 2, 26, "silverstone")
    check(q.quali_result()["pos"] == 2,
          "and re-qualifying replaces it rather than adding a second")
    check(len(q.data["quali_results"]) == 1, "one result per round")
    q.set_quali(False)
    check(not q.uses_quali, "qualifying can be turned off for a career")

    print("\n18. DELETION")
    slug = solo.slug
    check(season_mod.delete(slug), "a career can be deleted")
    check(season_mod.load(slug) is None, "and is gone")
    check(all(c["slug"] != slug for c in season_mod.list_careers()),
          "and no longer listed")

finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
