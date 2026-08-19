"""The career ladders: which rung a car is on, and what the next seat costs.

The whole feature rests on two questions being answered correctly, and both
have a way of being subtly wrong:

  * WHICH RUNG IS THIS CAR ON? Matched from the CarClass a live session
    reports, or the installed folder name before one exists. Get it wrong and
    a season is credited to a championship the driver never entered.
  * HAS HE EARNED THE NEXT SEAT? The bar rises as he climbs — fifth gets you
    out of karting, second gets you into Formula One — so the comparison is
    against the tier being ENTERED, not the one being left.

    python tests/laddertest.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ladder as L

fails = []
def check(c, l, e=""):
    print(("  [ OK ] " if c else "  [FAIL] ") + l + (("  " + e) if e else ""))
    if not c:
        fails.append(l)


print("\n1. THE DATA OBEYS ITS OWN RULES")
errs = L.validate()
check(not errs, "ladders.json validates", "; ".join(errs[:3]))
check(len(L.paths()) >= 6, "every path is present", "%d" % len(L.paths()))
check(sum(len(L.tiers(k)) for k in L.paths()) >= 25, "and every rung",
      "%d tiers" % sum(len(L.tiers(k)) for k in L.paths()))

print("\n2. THE BAR RISES AS YOU CLIMB")
# The user's own design: "if I want a seat in F2 and F1 I need at least P3 and
# P2". A rung easier to reach than the one below it would let a driver skip
# the hardest part of his own career by accident, so `validate` rejects it.
ss = L.tiers("single_seater")
needs = [t.get("needs") for t in ss]
check(needs == [None, 5, 4, 3, 2],
      "single-seater escalates entry, 5, 4, 3, 2", str(needs))
check(all(a is None or b is None or b <= a
          for a, b in zip(needs, needs[1:])),
      "and never gets easier further up")

print("\n3. WHICH RUNG IS THIS CAR ON")
# The CLASS is what a live session gives us; the FOLDER is what the menu has
# before a car has ever been loaded. Both must resolve.
for cls, want in (("Formula One 2021", ("single_seater", 4)),
                  ("F1 1988 Historic Edition", None),
                  ("Tatuus F4", ("single_seater", 1)),
                  ("GT3 World Series", ("endurance", 2)),
                  ("StockCar 2018 X Series", ("stock_car", 1)),
                  ("GT-R GT500 2013", ("touring", 2)),
                  ("IndyCar", ("road_to_indy", 3))):
    got = L.tier_of(car_class=cls)
    ok = (got == want) if want else True
    name = L.tiers(got[0])[got[1]]["name"] if got else "-"
    check(ok, "class %r -> %s" % (cls, name), "" if ok else "got %r" % (got,))

for veh, want in (("Kart_cup_2014", ("single_seater", 0)),
                  ("Tatuus_PM-18_2018", ("road_to_indy", 2)),
                  ("SC2018_2018", ("stock_car", 2)),
                  ("McLaren_MP4_13_1998", ("historic", 3))):
    got = L.tier_of(vehicle=veh)
    check(got == want, "mod %r -> %s" % (
        veh, L.tiers(got[0])[got[1]]["name"] if got else "-"),
        "" if got == want else "got %r" % (got,))

print("\n4. THE TRAP: A LONGER NAME IS A DIFFERENT RUNG")
# `SC2018X` and `SC2018` are two rungs of the same path. A substring match
# that takes the first hit promotes a driver out of a series he is still in —
# and it is invisible, because both answers look reasonable.
check(L.tier_of(vehicle="SC2018X_2018") == ("stock_car", 1),
      "SC2018X is Stock Car X, not Stock Car Pro",
      str(L.tier_of(vehicle="SC2018X_2018")))
check(L.tier_of(vehicle="SC2018_2018") == ("stock_car", 2),
      "and SC2018 is still Stock Car Pro")
# A car we know nothing about is silence, not a guess at rung one.
check(L.tier_of(car_class="Some Mod Nobody Has") is None,
      "an unknown car belongs to no rung")
check(L.tier_of() is None, "and no car at all is not rung one either")

print("\n5. EARNING THE NEXT SEAT")
p = L.Progress("single_seater")          # karting
check(p.tier()["key"] == "kart", "a new career starts at the bottom")
check(p.needs() == 5, "and needs fifth to get out of karting", str(p.needs()))
check(not p.earned(6), "sixth is not enough")
check(p.earned(5), "fifth is")
check(p.earned(1), "and so is winning it")
p.promote(5)
check(p.tier()["key"] == "f4", "promotion moves him up one rung")
check(p.results["kart"] == 5, "and remembers what the season below finished at")
check(p.needs() == 4, "F3 asks for more than F4 did", str(p.needs()))

# Straight to the top, checking the bar at each step.
seq = []
q = L.Progress("single_seater")
for pos in (5, 4, 3, 2):
    seq.append((q.tier()["name"], q.needs()))
    q.promote(pos)
check(q.tier()["key"] == "f1", "four promotions reach Formula One",
      q.tier()["name"])
check(q.needs() is None, "and there is nothing above it")
check(not q.earned(1), "so winning it promotes you nowhere")

print("\n6. A TOUR IS NOT A LADDER")
# Nobody is promoted from 1966 to 1975. Every era is open from the start, and
# asking what the next one "needs" is a category error.
h = L.Progress("historic")
check(h.needs() is None, "the historic path asks for nothing")
check(not h.earned(1), "winning a season promotes you nowhere")
check(all(t["open"] for t in h.unlocked()),
      "and every era is open from the first day",
      str([t["key"] for t in h.unlocked() if not t["open"]]))

print("\n7. WHAT THE INBOX DRAWS ITS DIVISIONS VIEW FROM")
u = L.Progress("single_seater", reached=2, results={"kart": 3, "f4": 2})
rows = u.unlocked()
check([r["open"] for r in rows] == [True, True, True, False, False],
      "everything up to his current rung is open", str([r["open"] for r in rows]))
check(sum(1 for r in rows if r["current"]) == 1, "exactly one rung is current")
check(next(r for r in rows if r["current"])["key"] == "f3",
      "and it is the one he is racing")
check(next(r for r in rows if r["key"] == "f2")["needs"] == 3,
      "a locked rung says what it would take")
check(next(r for r in rows if r["key"] == "kart")["result"] == 3,
      "and a finished one says how it went")

print("\n8. MISSING THE CUT OFFERS A DIFFERENT PATH")
# The user's own call: stay and go again, or try something else. The sideways
# offer is matched on REGISTER — a professional seat for a professional seat —
# because tier NUMBER means nothing across paths of different lengths.
opts = L.sideways("single_seater", 3)     # in F2, missed the F1 seat
check(opts, "a missed promotion has somewhere else to go", str(opts[:3]))
check(all(k != "single_seater" for k, _i, _n in opts),
      "never back onto the path he is already on")
check(all(not (L.path(k) or {}).get("tour") for k, _i, _n in opts),
      "and never into the historic tour, which is not a career")
# THE OFFER MATCHES THE SEAT HE MISSED, NOT THE ONE HE IS IN. A driver who
# just failed to make Formula One should be hearing from GT3 and IndyCar, not
# from Formula 4 — matching his current register offers a "sideways" move that
# is really a demotion.
regs = {L.tiers(k)[i]["register"] for k, i, _n in opts}
check(regs == {"professional"},
      "and every offer is a professional seat, because F1 was", str(regs))
names = sorted(n for _k, _i, n in opts)
check("GT3" in names, "GT3 is one of them", str(names))
# From the bottom of a path the offer is a bottom-of-path seat.
low = L.sideways("single_seater", 0)      # in karting, missed the F4 seat
check({L.tiers(k)[i]["register"] for k, i, _n in low} == {"grassroots"},
      "while missing the F4 seat offers grassroots seats, not GT3",
      str(sorted(n for _k, _i, n in low)))

print("\n9. PERSISTENCE SURVIVES A ROUND TRIP")
a = L.Progress("endurance", reached=2, results={"club": 4, "gt4": 1})
b = L.Progress.from_json(a.to_json())
check((b.path, b.reached, b.results) == (a.path, a.reached, a.results),
      "a career's ladder state saves and loads unchanged")
check(L.Progress.from_json({}).reached == 0,
      "and an empty record is a fresh start, not a crash")

print("\n10. IT NEVER CLAIMS A CAR IS RACEABLE")
# Installed does not mean licensed — the paid GT3 cars are fully downloaded
# and indistinguishable on disk. So the rung's cars are curated in the data,
# and this module only ever answers "is the folder there".
import json as _json
raw = _json.load(open(L.DATA, encoding="utf-8"))
gt3 = next(t for t in raw["paths"]["endurance"]["tiers"] if t["key"] == "gt3")
paid = ("mclaren_720s", "mercedes_amg", "porsche_911_gt3", "bentley",
        "audi_r8lms", "bmw_m6_gt3", "bmw_m4_gt3")
listed = " ".join(gt3.get("mods", []) + gt3.get("classes", [])).lower()
check(not any(x in listed for x in paid),
      "no paid GT3 car is listed on the GT3 rung", listed)
check(L.tier_installed({"mods": ["definitely not installed xyz"]}, mods=[]) is False,
      "an empty install claims nothing")
# ...AND THE SCAN HAS TO ACTUALLY RUN. The first version required the caller to
# supply a game directory and nothing ever did, so every rung answered "no car"
# and the divisions view told a man with eighty mods that he owned nothing.
# On a machine without rF2 this is empty, which is a different answer from
# wrong — `known_mods()` reports None and callers do not filter.
_m = L.installed_mods(force=True)
check(isinstance(_m, list), "the vehicle scan finds the game by itself",
      "%d folders" % len(_m))
check((L.known_mods() is None) == (not _m),
      "and unknown stays distinguishable from none")

print("\n10b. WHICH CAR DO I ACTUALLY LOAD?")
# The user, trying to start a Hot hatch season: "what car does the hot hatch
# season fall under?" He should never have had to ask — the answer is on his
# disk and the FIA entry pack is the honest place to put it.
check(L.pretty_mod("ClioCup_2010") == "Clio Cup",
      "a folder becomes something a person would say",
      L.pretty_mod("ClioCup_2010"))
check(L.pretty_mod("Renault_MeganeTrophyII_2013") == "Renault Megane Trophy II",
      "including the awkward ones",
      L.pretty_mod("Renault_MeganeTrophyII_2013"))
# UNDERSCORE IS A WORD CHARACTER, so a \b before the year matches nothing in
# "ClioCup_2010". The first version stripped no years at all.
check(not any(ch.isdigit() for ch in L.pretty_mod("Kart_cup_2014")),
      "and the year goes, which a word boundary alone would not do",
      L.pretty_mod("Kart_cup_2014"))
hatch = next(t for t in L.tiers("touring") if t["key"] == "hatch")
cars = L.tier_cars(hatch, mods=["ClioCup_2010", "Renault_MeganeTrophyII_2013",
                                "Tatuus_F4_2018"])
check([c[1] for c in cars] == ["ClioCup_2010", "Renault_MeganeTrophyII_2013"],
      "and only the cars that belong to the division are listed", str(cars))
check(L.tier_cars(hatch, mods=[]) == [],
      "an empty install lists nothing rather than guessing")

print("\n11. A SEASON IS A RUNG — season.py wiring")
# The ladder only means anything once a real championship is being raced at
# one of its tiers. Everything below runs the REAL create/record/advance path,
# against a throwaway careers directory: a test that writes into the user's
# own careers folder is a test that can lose him a season.
import shutil
import tempfile

import season as S

_tmp = tempfile.mkdtemp(prefix="factortv_ladder_")
S.CAREER_DIR = _tmp


def _season(pos_each, length=3, path="single_seater", tier=0, name="Tester"):
    """A finished (or part-finished) ladder season where the player took
    `pos_each` in every round. Two cars, so a championship exists at all."""
    car = S.create("open", me=name, rounds=length,
                   ladder_path=path, tier_index=tier)
    for i, pos in enumerate(pos_each, start=1):
        other = 1 if pos != 1 else 2
        car.record({"n": i, "slug": "trk%d" % i, "pos": pos,
                    "laps": 20, "race_laps": 20,
                    "classified": [(name, pos), ("A Rival", other)]})
    return car


c = _season([], length=3)
check(c is not None and c.on_ladder, "a career can be started on a ladder")
check(c.name == "Karting", "and is named for the rung, not its length", c.name)
check((c.tier() or {}).get("key") == "kart", "the season knows which rung it is")
check(c.register == "grassroots", "and how the booth should sound there",
      c.register)
ev = c.evaluate()
check(ev["needs"] == 5 and not ev["complete"],
      "before a race it knows what the next seat costs and that nothing is decided",
      str((ev["needs"], ev["complete"])))
check(ev["pos"] is None and not ev["earned"],
      "and claims no championship position from an empty season")
check(S.create("open", rounds=3, ladder_path="single_seater",
               tier_index=99) is None,
      "a rung off the end of a path creates nothing at all")

print("\n12. PROMOTION IS EVALUATED AT SEASON END, NEVER BEFORE")
part = _season([1, 1], length=3)
check(not part.season_done(), "two rounds of three is not a finished season")
check(part.evaluate()["earned"] and not part.evaluate()["promoted"],
      "as it stands he is clearing the bar — but he has not been promoted")
check(part.advance("promote") is None,
      "and half a championship advances nowhere")
check(len(part.rounds) == 2, "the season it refused to end is untouched")

won = _season([1, 1, 1], length=3)
check(won.season_done() and won.my_position() == 1,
      "three of three, won", str(won.my_position()))
ev = won.evaluate()
check(ev["promoted"] and ev["next"] == "f4",
      "the karting title earns the Formula 4 seat", str((ev["promoted"], ev["next"])))
t = won.advance("promote")
check(t and t["key"] == "f4", "and advancing takes it", str(t))
check(won.name == "Formula 4" and not won.rounds,
      "the new season is empty and named for the new rung",
      "%s / %d rounds" % (won.name, len(won.rounds)))
check(won.data.get("cls") == "" and not won.data.get("cls_any"),
      "THE CLASS LOCK IS CLEARED — carrying karting's class into F4 would "
      "match nothing for the rest of the career")
hist = won.data.get("ladder_history") or []
check(len(hist) == 1 and hist[0]["tier"] == "kart" and hist[0]["pos"] == 1,
      "and the season below is remembered as a summary", str(hist))
check((won.ladder.results or {}).get("kart") == 1,
      "including on the ladder itself, which the divisions view reads")

print("\n13. MISSING THE CUT IS NOT A DEAD END")
# THE BAR IS THE ONE ON THE SEAT HE IS REACHING FOR, so the refusal is tested
# where the bar is high: third in Formula 2 is a fine season and it is not a
# Formula One seat.
low = _season([3, 3, 3], length=3, path="single_seater", tier=3)   # F2 -> F1
check(low.evaluate()["needs"] == 2, "Formula One asks for second",
      str(low.evaluate()["needs"]))
low.data["rounds"][0]["classified"] = [("Tester", 3), ("A", 1), ("B", 2)]
low.data["rounds"][1]["classified"] = [("Tester", 3), ("A", 1), ("B", 2)]
low.data["rounds"][2]["classified"] = [("Tester", 3), ("A", 1), ("B", 2)]
check(low.my_position() == 3, "third in the championship", str(low.my_position()))
ev = low.evaluate()
check(not ev["promoted"], "third does not earn a Formula One seat")
check(low.advance("promote") is None, "and it cannot be taken by clicking")
check(ev["sideways"], "but somewhere else is offering a seat", str(ev["sideways"][:3]))
again = low.advance("retry")
check(again and again["key"] == "f2", "staying to go again keeps the rung",
      str(again))
check(not low.rounds and (low.data["ladder_history"] or [])[-1]["pos"] == 3,
      "with a clean season and the failed one on the record")

print("\n14. A SIDEWAYS MOVE IS A REAL MOVE")
sw = _season([3, 3, 3], length=3, path="single_seater", tier=3)
opts = sw.evaluate()["sideways"]
pk, ti, nm = opts[0]
t = sw.advance("switch", path_key=pk, tier_index=ti)
check(t and t["name"] == nm, "he lands on the seat he was offered", str(t))
check(sw.ladder.path == pk and sw.ladder.reached == ti,
      "the career is on the new path now", "%s/%s" % (sw.ladder.path, sw.ladder.reached))
check(sw.advance("switch", path_key="no_such_path") is None,
      "a path that does not exist moves nobody")

print("\n14b. AN ARC IS FINISHED BY WINNING ITS LAST CHAMPIONSHIP")
# The user's own definition, and 100% is every path's final championship won:
# he does not have to drive every division, he has to FINISH every arc.
top = _season([2, 2, 2], length=3, path="touring", tier=2)      # Super GT500
ev = top.evaluate()
check(ev["top"] and ev["complete"], "he is in the final championship, and it is over")
check(not ev["arc_done"],
      "SECOND IN THE LAST DIVISION DOES NOT FINISH THE ARC — reaching the top "
      "rung is not the same as winning it")
check(not ev["next_paths"], "so the FIA grants him nothing")
check(top.advance("newpath", path_key="stock_car") is None,
      "and a new path cannot be taken anyway")

champ = _season([1, 1, 1], length=3, path="touring", tier=2)
ev = champ.evaluate()
check(ev["arc_done"], "winning it finishes the arc")
check(ev["career_pct"] == 0.0,
      "which is still not counted until he actually banks it", str(ev["career_pct"]))
nxt = {p["key"] for p in ev["next_paths"]}
check(nxt and "touring" not in nxt,
      "the paths on offer never include the one he has just finished", str(nxt))
check("historic" not in nxt,
      "NOR THE HISTORIC TOUR — it is bonus content with no championship to win")
entries = dict((p["key"], p["entries"]) for p in ev["next_paths"])
regs = [r for _i, _n, r in entries.get("single_seater", ())]
check(regs == ["grassroots", "professional"],
      "and each offers two seats: the bottom, or the professional rung",
      str(regs))

print("\n14c. THE FIA GRANTS PERMISSION TO COMPETE ELSEWHERE")
i_pro = next(i for i, _n, r in entries["single_seater"] if r == "professional")
t = champ.advance("newpath", path_key="single_seater", tier_index=i_pro)
check(t and t["key"] == "f1", "a champion may join a new path at the top of it",
      str(t))
check(champ.paths_won == ["touring"], "the finished arc is banked",
      str(champ.paths_won))
# TWO FIGURES, BOTH TRUE. A career ENDS at three arcs — one championship is a
# season or two, and the story is about a man who gave the sport years — while
# a 100% RECORD is all five. Printing one number for both makes one of them a
# lie the other screen contradicts.
check(champ.career_pct() == 1 / 3.0,
      "one arc is a third of a career, which ends at three",
      str(champ.career_pct()))
check(champ.completion_pct() == 1 / 5.0,
      "and a fifth of a 100% record, which is all five",
      str(champ.completion_pct()))
check(not champ.career_over, "one arc does not finish a career")
champ.data["ladder_done"] = ["touring", "stock_car", "endurance"]
check(champ.career_over and champ.career_pct() == 1.0,
      "three of them do")
check(champ.completion_pct() < 1.0,
      "with two divisions still unwon — finished is not the same as complete",
      str(champ.completion_pct()))
champ.data["ladder_done"] = ["touring"]
check(champ.ladder.results == {},
      "RESULTS DO NOT TRAVEL between paths — a GT500 result against an F1 rung "
      "would be a season he never raced", str(champ.ladder.results))
check(champ.evaluate()["rungs_left"] == 0,
      "and joining at the top leaves nothing above him")

print("\n14d. WHAT THE BOOTH IS ALLOWED TO KNOW ABOUT HIM")
# Most of the gameplay is the commentary, so where a driver came from is worth
# more than another panel. Every figure was WATCHED — no claim about the real
# world, which is why it is safe on a fictional grid.
r = champ.resume()
check(r["title_count"] == 1 and r["reigning"] == "Super GT500",
      "the reigning champion of the division he just left", str(r["reigning"]))
check(r["arc_names"] == ["Touring"], "and the arc he finished", str(r["arc_names"]))
check(r["seasons"] == 1 and r["races"] == 3,
      "with a career length measured in seasons and races",
      "%s seasons / %s races" % (r["seasons"], r["races"]))
check(r["tier_name"] == "Formula One", "and where he is now", r["tier_name"])
check(_season([], length=3).resume()["title_count"] == 0,
      "a driver with no history claims none")
check(S.create("open", me="T", rounds=3).resume() is None,
      "and a career off the ladder has no arc to have a résumé about")

print("\n15. THE RUNG IS A LOCK ON WHAT COUNTS")
lk = _season([], length=5)                       # karting
check(lk.match("spa", cls="GT3 World Series") is None,
      "a GT3 race is not a round of a karting championship")
check(lk.match("spa", cls="Kart") is not None,
      "a kart is", str(lk.match("spa", cls="Kart")))
# A CURATED LIST WILL ALWAYS TRAIL THE INSTALLED MODS. An unrecognised class
# is unknown, not wrong — refusing it would make a career silently stop
# counting the first time he races something ladders.json has not been told
# about.
check(lk.match("spa", cls="Some Mod Nobody Has") is not None,
      "and a class the ladder has never heard of is not refused")

print("\n16. A CAREER OFF THE LADDER IS UNCHANGED")
plain = S.create("open", me="Tester", rounds=3)
check(plain.ladder is None and not plain.on_ladder,
      "an ordinary career is on no path")
check(plain.evaluate() is None, "there is nothing to evaluate")
check(plain.advance() is None, "and nothing to advance")
check(plain.tier() is None and plain.register == "",
      "no rung, and no register for the booth to take a tone from")
check(plain.match("spa", cls="Anything At All") is not None,
      "and the ladder lock does not touch it")
check("ladder" not in plain.data,
      "the saved file gains no ladder block it does not need")

print("\n17. THE CAR HE CHOSE FOR THIS SEASON")
# Asked for as an RPG beat: "instead of it telling me which car is eligible,
# give the player a select option ... let the player pick which between these
# 2 they will race in."

c = _season([], length=3, path="touring", tier=0)
check(c.car_pick() is None, "a new season has no car chosen yet")
c.pick_car("ClioCup_2010")
check(c.car_pick() == ("Clio Cup", "ClioCup_2010"),
      "picking stores the tidy name and the FOLDER", str(c.car_pick()))
check(S.load(c.slug).car_pick() == ("Clio Cup", "ClioCup_2010"),
      "and it survives a save and a reload")

# THE PICK IS A QUESTION PER DIVISION. The Clio he chose for Hot hatch means
# nothing in Touring cars, and leaving it set would have the FIA telling him
# to load a car that is not eligible for the championship he was promoted
# into. Same reason `_start_rung` clears the class lock.
c = _season([1, 1, 1], length=3, path="touring", tier=0)
c.pick_car("ClioCup_2010")
c.advance("promote")
check(c.car_pick() is None,
      "a promotion asks the question again", str(c.car_pick()))

# ...AND THE BINDING IS THE CLASS LOCK THAT ALREADY EXISTS, not a second one.
# A pick is a FOLDER name and a live session reports a CarClass; the two are
# different names for a car and `ladders.json` only maps them one-to-one on
# some rungs (Hot hatch does, Touring cars does not — `volvo s40` has no class
# alias). Refusing a session on a mapping that is guesswork for half the
# ladder would risk a career that silently stops counting, which is the worst
# failure this module has.
_src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "season.py"), encoding="utf-8").read()
check("def pick_car" in _src and "car_pick" in _src,
      "the pick is recorded")
check("_start_rung" in _src and 'self.data.pop("car_pick", None)' in _src,
      "and cleared with the rung, beside the class lock")


print("\n17b. THE NAME IN THE GAME IS NOT THE NAME OF THE FOLDER")
# The user opened his first FIA letter, was told the eligible car was "Kart
# Cup 2014", went to look for it in the game and found "Kart F1" and "Kart
# Junior". One folder, two selectable cars, and the folder cannot name
# either of them - vehicle definitions live in compressed (here encrypted)
# .mas archives, which is the same reason class names have never been
# readable off the disk.
#
# So the real names are CURATED in ladders.json, exactly as the car lists
# themselves are, and only from what the user has confirmed seeing.
_kart = L.tiers("single_seater")[0]
_names = [n for n, _f in L.tier_cars(_kart, mods=["Kart_cup_2014"])]
check(_names == ["Kart Junior", "Kart F1"],
      "the karting rung offers the cars the GAME shows", str(_names))
check("Kart Cup 2014" not in _names,
      "and never the tidied folder name, which he cannot select")
# ...and a session in either of them still resolves to karting, or the season
# would silently stop counting the moment he picked one.
for _cls in ("Kart Junior", "Kart F1", "Kart"):
    check(L.tier_of(car_class=_cls) == ("single_seater", 0),
          "a live session in %r is a karting round" % _cls,
          str(L.tier_of(car_class=_cls)))
# A rung with no curated names falls back to the folder, tidied. That is a
# guess, which is why the letter quotes the folder beside it.
_hatch = L.tiers("touring")[0]
check(all(n for n, _f in L.tier_cars(_hatch, mods=["ClioCup_2010"])),
      "a rung with no `ui` map still names something")


print("\n17c. THE F2 RUNG TAKES THE 2019 MOD AND NOT THE 2017 ONE")
# The user subscribed to both by accident and was explicit: use Formula 2
# 2019, never the 2017 championship. It matters beyond preference - the
# junior-programme arc is written round the real 2019 teams.
#
# AND IT IS THE `cup` TRAP AGAIN. `_norm` splits camelCase, so "F2_2019"
# folds to " f 2 2019 " and "ASR_2017_F2_Champioship" to
# " asr 2017 f 2 champioship " - BOTH contain " f 2 ", so a bare `f2` alias
# would put the unwanted mod on the rung. The year is what separates them,
# so the year is in the alias.
_f2 = L.tiers("single_seater")[3]
check([f for _n, f in L.tier_cars(_f2, mods=["F2_2019"])] == ["F2_2019"],
      "the 2019 mod is eligible for Formula 2")
check(not L.tier_cars(_f2, mods=["ASR_2017_F2_Champioship"]),
      "and the 2017 one is not, however similar the folder looks")
check(L.tier_of(vehicle="ASR_2017_F2_Champioship") != ("single_seater", 3),
      "...by any route")


print("\n17d. SIMULATING A ROUND")
# Asked for as a testing convenience and kept as a real feature. The user:
# "the game physics is tricky to master in every division and for purposes
# of testing I don't have time to be getting good."
#
# So the FIRST TWO RUNGS of a path are generous - a simulated season earns
# the promotion - and above that the sim reports his own form, because by
# then the career is a record of what he can actually do and flattering it
# would make the climb meaningless.
GRID = ["A Rival", "B Rival", "C Rival", "D Rival", "E Rival",
        "F Rival", "G Rival", "H Rival", "I Rival"]

kart = _season([], length=5, path="single_seater", tier=0)
for _n in range(1, 6):
    _r = kart.simulate_round(n=_n, slug="t%d" % _n, names=GRID)
    check(_r is not None and _r["pos"] <= S.Career.SIM_LEARN_WORST,
          "karting round %d is a learning result" % _n,
          "P%s" % (_r or {}).get("pos"))
check((kart.evaluate() or {}).get("promoted"),
      "a simulated season in a learning division earns the seat above")

# ABOVE THE LEARNING RUNGS IT IS HONEST. A man who has been finishing
# seventh does not simulate a win.
# A REAL FIELD, because the sim clamps to the grid it can see: `_season`
# builds a two-car championship, in which seventh place cannot exist and a
# correct clamp to P2 looks like a broken simulation.
f3 = S.create("open", me="Tester", rounds=6, ladder_path="single_seater",
              tier_index=2)
for _n in (1, 2, 3):
    _order = list(GRID)
    _order.insert(6, "Tester")
    f3.record({"n": _n, "slug": "t%d" % _n, "pos": 7, "laps": 20,
               "race_laps": 20,
               "classified": [(nm, i + 1) for i, nm in enumerate(_order)]})
_r = f3.simulate_round(n=4, names=GRID)
check(_r and abs(_r["pos"] - 7) <= S.Career.SIM_WOBBLE,
      "an honest division simulates his own form",
      "P%s against an average of 7" % (_r or {}).get("pos"))

# A SIMULATED ROUND PRODUCES POSITIONS AND POINTS, NEVER EVENTS.
check(_r.get("simulated") is True, "and it is marked as simulated")
check(not _r.get("fastest"), "with no fastest lap - that is an event")
check(not _r.get("dnf"), "and no retirement")

# ...AND IT IS NOT A QUALIFYING RESULT, which is what keeps the engineer
# honest for free: "last time out you put it fourth" reads `quali_result()`,
# and a simulated round never writes one.
check(not f3.quali_result(),
      "no qualifying result, so nobody can say he put it anywhere")

# DETERMINISTIC. A random result would mean reloading the save produced a
# different season, which is the rule `record_absence` already documents.
a = _season([7, 7, 7], length=6, path="single_seater", tier=2)
b = _season([7, 7, 7], length=6, path="single_seater", tier=2)
check(a.simulate_round(n=4, names=GRID)["pos"]
      == b.simulate_round(n=4, names=GRID)["pos"],
      "two identical careers simulate the same round the same way")

# NO FIELD, NO RACE. Inventing opponents would be inventing a championship.
empty = _season([], length=5, path="single_seater", tier=0)
check(empty.simulate_round(n=1) is None,
      "with no form and no roster it refuses rather than inventing a grid")


print("\n17e. THE SIM REFUSES BEFORE THE CAREER IS SET UP")
# Two bugs the user found together, and the first explains the second: he
# pressed Simulate, confirmed, and NOTHING HAPPENED - and he could reach the
# button before choosing a car or a nationality at all.
#
# The cause was one line. `cls` is filled in by the first race a season
# RECORDS, so a career that has not raced has none - which is exactly the
# career somebody wants to simulate from. The roster lookup was keyed on it,
# found nothing, and `simulate_round` refused silently.
#
# So the grid is found by RUNG now, and the button SAYS WHY when it cannot
# run. A disabled control that gives no reason is the thing he actually
# complained about.
import career as _C
import overlay_panels as _op3


class _SimHost(_op3.PanelsMixin):
    def __init__(self, hist):
        self.career = hist


_hist = _C.History(path=os.path.join(_tmp, "_hist.json"))
_hist.data.setdefault("classes", {})["Clio Cup 2010"] = {
    "races": 0, "share": 1.0, "last": 0,
    "drivers": ["Michael Borda", "Scott Juliano", "Dan Peal"]}
_h = _SimHost(_hist)

_sc = S.create("open", me="Tester", rounds=5, ladder_path="touring",
               tier_index=0)
check(_h._sim_blocked(_sc) == "pick a nationality",
      "a career with no nationality cannot be simulated",
      str(_h._sim_blocked(_sc)))
_sc.data["nationality"] = "South Africa"; _sc.save()
check(_h._sim_blocked(_sc) == "pick a car first",
      "...nor one that has not chosen between its eligible cars",
      str(_h._sim_blocked(_sc)))
_sc.pick_car("ClioCup_2010", "Clio Cup")
check(_h._sim_blocked(_sc) is None, "once it is set up, it may run",
      str(_h._sim_blocked(_sc)))

# THE GRID COMES FROM THE RUNG, not from a class lock that does not exist
# yet. This is the bug itself.
check(_h._sim_grid(_sc), "and it finds a grid before any class is locked",
      str(_h._sim_grid(_sc)))
check(_sc.simulate_round(n=1, slug="t1", names=_h._sim_grid(_sc)),
      "so the round actually banks instead of failing silently")

# NOBODY TO RACE IS A REASON, NOT A SILENCE. A career whose cars have never
# been loaded has no roster, and banking a round he was alone in would be
# worse than refusing.
_bare = S.create("open", me="Tester", rounds=5, ladder_path="stock_car",
                 tier_index=0)
_bare.data["nationality"] = "South Africa"; _bare.save()
check(_h._sim_blocked(_bare), "a division he has never loaded says so",
      str(_h._sim_blocked(_bare)))


print("\n18. HOW HE ARRIVED IS REMEMBERED")
# The paper needs a different sentence for each way of arriving, and only
# `advance()` knows which it was — so it records a FACT rather than leaving
# the feed to infer one from the shape of the results. Two detectors would
# eventually disagree about whether a man was promoted.
c = _season([1, 1, 1], length=3)
check(not c.data.get("arrived_by"),
      "a career that began here has no arrival to explain")
c.advance("promote")
check(c.data.get("arrived_by") == "promote", "a promotion is recorded")
for _n in range(1, 4):
    c.record({"n": _n, "slug": "t%d" % _n, "pos": 4, "laps": 20,
              "race_laps": 20,
              "classified": [("Tester", 4), ("A Rival", 1)]})
c.advance("switch", path_key="endurance", tier_index=1)
check(c.data.get("arrived_by") == "switch",
      "and a sideways move is NOT recorded as one", c.data.get("arrived_by"))


print("\n17. WHAT THE GAME CALLS IT — read from the game")
# The FIA letter has now named a car that is not on the menu three times:
# "Kart Cup 2014" for a folder that offers "Kart Junior" and "Kart F1", "Tatuus
# F4 2018" for a car the game lists as "Tatuus_F4-T014", and a pack the user
# spelled from memory. Every one is the same fault — a FOLDER NAME IS NOT A MENU
# NAME — and the module's own comment said the real names could only come from
# him, because the `.mas` archives are compressed and, for the Tatuus mod,
# encrypted outright.
#
# The rF2 UI is an Electron app and caches its content list as plain JSON, with
# `vehFile` pointing at the folder and `fullPathTree` holding the menu path. So
# the game can be asked after all.
#
# SYNTHETIC CACHE, because the suites run on machines with no rFactor 2 — and
# because the fixture is the only way to test the shapes that are NOT on this
# disk: a truncated record, a comma with no space, a pack of sixty liveries.
import modnames as _mn

_cache_dir = os.path.join(_tmp, "UserData", "player", "LocalStorage", "Cache")
os.makedirs(_cache_dir, exist_ok=True)


def _rec(tree, folder, veh="01_X.VEH"):
    p = ("D:" + chr(92) + "rF2" + chr(92) + "Installed" + chr(92) + "Vehicles"
         + chr(92) + folder + chr(92) + "1.0" + chr(92) + veh)
    p = p.replace(chr(92), chr(92) + chr(92))
    return ('{"name":"x","fullPathTree":"%s","vehFile":"%s","engine":"E",'
            '"manufacturer":"M"}' % (tree, p))


_body = "[" + ",".join([
    _rec("Karts, Kart Junior", "Kart_cup_2014", "01K.VEH"),
    _rec("Karts,Kart F1", "Kart_cup_2014", "02K.VEH"),          # no space
    _rec("Tatuus, Tatuus_F4-T014", "Tatuus_F4_2018"),
    _rec("GT3 World Series, Bmw M6 GT3, Blancpain 2016", "STK BMW M6 GT3"),
    _rec("GT3 World Series, Bmw M6 GT3, British GT 2016", "STK BMW M6 GT3"),
    _rec("GT3 World Series, Bmw M6 GT3, Super GT300 2016", "STK BMW M6 GT3"),
    _rec("GT3 World Series, Bmw M6 GT3, VLN 2016", "STK BMW M6 GT3"),
    _rec("Nowhere, Ghost Car", "NotInstalled_2020"),
]) + "]"
with open(os.path.join(_cache_dir, "f_00abcd"), "w", encoding="utf-8") as _f:
    _f.write("HTTP/1.1 200 OK\r\n\r\n" + _body)
# A file that is not a content list at all, and a truncated one. Neither may
# raise and neither may contribute a name.
with open(os.path.join(_cache_dir, "f_00dead"), "wb") as _f:
    _f.write(b"\x00\x01\x02 not json at all \xff")
with open(os.path.join(_cache_dir, "f_00trun"), "w", encoding="utf-8") as _f:
    _f.write('[{"fullPathTree":"Half, A Car","vehFile":"D:')

_mods = ["Kart_cup_2014", "Tatuus_F4_2018", "STK BMW M6 GT3"]
_got = _mn.scan(game_dir=_tmp, mods=_mods)
check(set(_got) == set(_mods),
      "every installed folder in the cache is read, and nothing else is",
      str(sorted(_got)))
check("NotInstalled_2020" not in _got,
      "a name for a folder that is not installed is discarded")

_mn._cache = dict(_got)          # skip the store; this is the parse under test
check(_mn.pick_names("Tatuus_F4_2018") == ["Tatuus > Tatuus_F4-T014"],
      "the F4 car is named the way the GAME names it",
      str(_mn.pick_names("Tatuus_F4_2018")))
_karts = _mn.pick_names("Kart_cup_2014")
check(sorted(_karts) == ["Karts > Kart F1", "Karts > Kart Junior"],
      "ONE FOLDER, TWO SELECTABLE CARS — and it names both", str(_karts))
# THE USEFUL LEVEL IS NOT ALWAYS THE LEAF. For the GT3 pack the leaf is a
# SERIES, so taking it would tell him to look for "Blancpain 2016" — which is
# not a car. The answer is the deepest level every path agrees on.
check(_mn.pick_names("STK BMW M6 GT3") == ["GT3 World Series > Bmw M6 GT3"],
      "a folder of many liveries names what they are all inside",
      str(_mn.pick_names("STK BMW M6 GT3")))

# A CURATED NAME STILL WINS. `ui` is a word the user has read on his own screen;
# a learned name is the game's string; the tidied folder is a guess. That order
# is the whole design, and the karting rung is where it matters — the curated
# entry is what he confirmed after the letter got it wrong.
_kt = {"name": "Karting", "mods": ["kart cup"], "classes": ["kart"],
       "ui": {"kart cup": ["Kart Junior", "Kart F1"]}}
_cars = L.tier_cars(_kt, ["Kart_cup_2014"])
check([n for n, _ in _cars] == ["Kart Junior", "Kart F1"],
      "a curated name beats a learned one", str(_cars))
_kt2 = {"name": "Karting", "mods": ["kart cup"], "classes": ["kart"]}
_cars2 = L.tier_cars(_kt2, ["Kart_cup_2014"])
check(all(">" in n for n, _ in _cars2) and len(_cars2) == 2,
      "and with nothing curated, the game's own names are used", str(_cars2))

# NO GAME, NO CLAIM. Every failure path here returns nothing rather than
# raising: this runs inside a letter that must still be sent.
check(_mn.scan(game_dir=os.path.join(_tmp, "nope")) == {},
      "an unreadable game directory yields no names and no exception")
_mn._cache = {}
check(_mn.pick_names("Tatuus_F4_2018") == [],
      "and an empty map is 'we do not know', not a guess")
_mn._cache = None


print("\n18. THE HISTORIC TOUR IS EARNED, ONE ERA AT A TIME")
# The user's idea: "can those races be unlocked through an invite the player
# receives after completing their championship, so if I beat 2021 then I get
# invited to compete in the 1988 F1 season as a reward as well."
#
# It fits because the tour was already the odd one out: `career_paths()` excludes
# it from the 100% (nobody is promoted from 1966 to 1975, so there is no final
# championship to win), which is exactly what makes it the right thing to give
# away — the one path with nothing to lose by being optional.
#
# His three decisions: Formula One only, one era per championship, and it counts
# for nothing.
import inbox as _inbox

_top = len(L.tiers("single_seater")) - 1
tour = S.create("open", me="Tester", rounds=3,
                ladder_path="single_seater", tier_index=_top)
check((tour.ladder.tier() or {}).get("key") == "f1",
      "a career at the top of the single-seater path")
check(tour.f1_titles() == 0 and not tour.tour_state()["owed"],
      "before he wins anything, no era is owed")
_inbox.refresh(tour)
check(not [m for m in _inbox.messages(tour) if m["kind"] == "tour_invite"],
      "and no invitation is written")
check(not tour.tour_open("eighties"),
      "the eras are shut until one is earned")

for _n in (1, 2, 3):
    tour.record({"n": _n, "slug": "t%d" % _n, "pos": 1, "laps": 20,
                 "race_laps": 20,
                 "classified": [("Tester", 1), ("A Rival", 2)]})
check(tour.f1_titles() == 1,
      "winning the top championship counts, on the afternoon it happens",
      str(tour.f1_titles()))
st = tour.tour_state()
check(st["owed"] == 1 and st["next"] and st["next"][1]["key"] == "eighties",
      "and the era owed is the EIGHTIES first — the best one, not the oldest",
      str(st["next"][1]["name"] if st["next"] else None))

got = [m for m in (_inbox.refresh(tour) or []) if m
       and m["kind"] == "tour_invite"]
check(len(got) == 1, "the invitation arrives as a letter", str(len(got)))
check(got and "eighties" in (got[0]["subject"] + got[0]["body"][0]).lower(),
      "naming the era it opens", got[0]["subject"] if got else "")
check(tour.tour_open("eighties"),
      "and the era he has been INVITED to is the era he may race")
check(not tour.tour_open("nineties"),
      "one championship, one era — the rest stay shut")
check(not [m for m in (_inbox.refresh(tour) or []) if m
           and m["kind"] == "tour_invite"],
      "and the invitation is not sent twice")

# A SECOND TITLE OPENS THE NEXT ONE, not the same one again.
tour.advance("retry")
for _n in (1, 2, 3):
    tour.record({"n": _n, "slug": "s%d" % _n, "pos": 1, "laps": 20,
                 "race_laps": 20,
                 "classified": [("Tester", 1), ("A Rival", 2)]})
_inbox.refresh(tour)
check(tour.tour_state()["unlocked"] == ["eighties", "nineties"],
      "a second championship opens the next era in turn",
      str(tour.tour_state()["unlocked"]))

# FORMULA ONE ONLY. A champion of another path is not invited to a Grand Prix
# season — the user was explicit, and it is the stranger sentence.
other = S.create("open", me="Tester", rounds=3, ladder_path="stock_car",
                 tier_index=len(L.tiers("stock_car")) - 1)
for _n in (1, 2, 3):
    other.record({"n": _n, "slug": "n%d" % _n, "pos": 1, "laps": 20,
                  "race_laps": 20,
                  "classified": [("Tester", 1), ("A Rival", 2)]})
check(other.title_count() >= 1, "he has won a championship elsewhere",
      str(other.title_count()))
check(other.f1_titles() == 0 and not other.tour_state()["owed"],
      "but a NASCAR title does not invite him to 1988", str(other.f1_titles()))

# AND IT COUNTS FOR NOTHING, which is decision three and the reason this was
# safe to add late: the 100% arithmetic is untouched.
check(L.tour_key() not in L.career_paths(),
      "the tour is still outside the paths a 100% career is counted over")
check(len(L.career_paths()) == 5, "which is still five", str(len(L.career_paths())))

shutil.rmtree(_tmp, ignore_errors=True)

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
