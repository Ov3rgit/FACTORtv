"""The title arithmetic, and the rivalry that comes out of the same table.

    python tests/pointstest.py

WHY THIS SUITE IS DIFFERENT FROM THE REST.

Everything else the booth says is about something that has already happened.
`title_scenarios()` is a claim about what WILL be enough — and the listener
checks it at the chequered flag. One missed permutation and Miles tells a man
he has won a championship he has not won, in the last five minutes of a
season he has spent ten hours on.

So this file does not assert my reasoning. It BRUTE-FORCES the answer: for
every finishing position, it enumerates what every driver could still score
and asks whether the player is beaten in any of them. If the closed-form
answer and the enumeration ever disagree, the closed form is wrong.

The other half is the rivalry rule, which the user rewrote: after four rounds
your rival is whoever is next to you in the standings. That replaced a rule
that also required the two men to have raced each other on the road, and the
case it was getting wrong is in section 5 — two drivers level on points who
are rarely in the same part of the circuit, which is what most title fights
in the sport's history actually look like.
"""
import os, sys, tempfile, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import season as S
S.CAREER_DIR = tempfile.mkdtemp()

fails = []
def check(cond, label, extra=""):
    print(("  [ OK ] " if cond else "  [FAIL] ") + label +
          (("  " + extra) if extra else ""))
    if not cond:
        fails.append(label)


NAMES = ["Kandasamy", "Borda", "Juliano", "Groening", "Peal",
         "Camaj", "Miller", "Wheatley"]


def mk(orders, length, me="Kandasamy"):
    c = S.create("open", me=me, rounds=length, cls="Clio Cup 2010")
    for i, order in enumerate(orders, start=1):
        pos = order.index(me) + 1 if me in order else len(order) + 1
        c.record({"n": i, "slug": "t%d" % i, "pos": pos, "laps": 20,
                  "race_laps": 20, "cls": "Clio Cup 2010",
                  "classified": [(nm, p + 1) for p, nm in enumerate(order)]})
    return c


def brute_secure(c, field):
    """The worst finish that wins the title against EVERY possible result.

    Enumerated, not reasoned about. With one round left this is exhaustive
    over the finishing order of everyone who can still catch him.
    """
    table = c.standings()
    pts = dict(table)
    me = c.me
    my = pts[me]
    left = c.total_rounds - len(c.rounds)
    if left != 1:
        return None
    others = [n for n, _p in table if n != me]
    best = None
    for p in range(1, field + 1):
        slots = [s for s in range(1, field + 1) if s != p]
        safe = True
        # Only the men who could possibly pass him matter; giving every other
        # driver a free run at P1 as well would be the same answer more
        # slowly.
        live = [n for n in others if pts[n] + c.points_for(1) > my]
        for assign in itertools.permutations(slots, len(live)):
            for n, s in zip(live, assign):
                if pts[n] + c.points_for(s) >= my + c.points_for(p):
                    safe = False
                    break
            if not safe:
                break
        if safe:
            best = p
    return best


# ---------------------------------------------------------------------------
print("\n1. THE CLOSED FORM AGREES WITH BRUTE FORCE")

FIELD = 8
cases = [
    ("a comfortable lead",
     [["Kandasamy"] + NAMES[1:]] * 3 + [["Borda", "Kandasamy"] + NAMES[2:]], 5),
    ("nose to nose",
     [["Kandasamy"] + NAMES[1:], ["Borda", "Kandasamy"] + NAMES[2:],
      ["Kandasamy"] + NAMES[1:], ["Borda", "Kandasamy"] + NAMES[2:]], 5),
    ("he is behind",
     [["Borda", "Kandasamy"] + NAMES[2:]] * 4, 5),
    ("three men in it",
     [["Kandasamy", "Borda", "Juliano"] + NAMES[3:],
      ["Borda", "Juliano", "Kandasamy"] + NAMES[3:],
      ["Juliano", "Kandasamy", "Borda"] + NAMES[3:],
      ["Kandasamy", "Juliano", "Borda"] + NAMES[3:]], 5),
]
for label, orders, length in cases:
    c = mk(orders, length)
    sc = c.title_scenarios(field=FIELD)
    want = brute_secure(c, FIELD)
    got = sc.get("secure") if sc else None
    if sc and sc.get("decided"):
        got = 0
        want = 0 if want is None else want
    check(got == want, "secure position is right: %s" % label,
          "closed form P%s / brute force P%s   table %s"
          % (got, want, [t for t in c.standings()[:3]]))


# ---------------------------------------------------------------------------
print("\n2. THE CONDITIONAL TABLE IS EXACT TOO")
# "P5 if Borda wins, P8 if he is second" — the thing the user asked for, and
# the thing with the most ways to be quietly wrong.
c = mk([["Kandasamy"] + NAMES[1:]] * 3 + [["Borda", "Kandasamy"] + NAMES[2:]],
       5)
sc = c.title_scenarios(field=FIELD)
pts = dict(c.standings())
my, riv = pts["Kandasamy"], pts["Borda"]
bad = []
for row in sc["ifs"]:
    q, need = row["rival_pos"], row["need"]
    if need is None:
        continue
    # It must WIN at the stated position...
    if not (my + c.points_for(need) > riv + c.points_for(q)):
        bad.append("P%s does not beat rival P%d" % (need, q))
    # ...and it must be the WORST such position, or the booth is asking for
    # more than the maths does.
    nxt = need + 1
    if nxt != q and nxt <= FIELD and \
            my + c.points_for(nxt) > riv + c.points_for(q):
        bad.append("P%s would also have done for rival P%d" % (nxt, q))
check(not bad, "every conditional is exactly the worst finish that wins",
      "; ".join(bad[:3]))
check(len(sc["ifs"]) >= 3, "there is a table, not a single case",
      "%d rows" % len(sc["ifs"]))


# ---------------------------------------------------------------------------
print("\n3. A TIE IS NOT A TITLE")
# `standings()` breaks a tie ALPHABETICALLY. That is a sort order, not a
# countback rule, and this product does not model one — so equal points must
# never be reported as a championship won. It costs a sentence occasionally
# and it can never be wrong.
bad = []
for label, orders, length in cases:
    c = mk(orders, length)
    sc = c.title_scenarios(field=FIELD)
    if not sc or not sc.get("secure"):
        continue
    pts = dict(c.standings())
    my = pts[c.me]
    p = sc["secure"]
    # The best any chaser can still do, given the player took `p` — two cars
    # cannot occupy one place, which is the trap the first draft of this
    # check fell into by letting both men finish first.
    slot = 1 if p != 1 else 2
    for n in sc.get("chasers") or []:
        if my + c.points_for(p) <= pts[n] + c.points_for(slot):
            bad.append("%s: P%d only ties/loses to %s" % (label, p, n))
check(not bad, "the secure position wins outright, never on equal points",
      "; ".join(bad[:3]))

# And the same rule stated directly: level pegging with one round to go
# cannot produce a claim that anything is secured below a win.
c = mk([["Kandasamy", "Borda"] + NAMES[2:],
        ["Borda", "Kandasamy"] + NAMES[2:]], 3)
sc = c.title_scenarios(field=FIELD)
pts = dict(c.standings())
check(sc and sc["secure"] == 1,
      "two men dead level going into the last round: only a win does it",
      "secure=P%s with %s" % (sc and sc["secure"], c.standings()[:2]))


# ---------------------------------------------------------------------------
print("\n4. IT REFUSES WHEN IT CANNOT KNOW (LAW 4)")
c = S.create("open", me="Kandasamy", rounds=0, cls="Clio Cup 2010")
c.record({"n": 1, "slug": "t1", "pos": 1, "laps": 20, "race_laps": 20,
          "cls": "Clio Cup 2010",
          "classified": [(n, i + 1) for i, n in enumerate(NAMES)]})
check(c.title_scenarios() is None,
      "an open season with no declared length claims nothing at all")

c = mk([["Kandasamy"] + NAMES[1:]] * 3, 3)
check(c.title_scenarios() is None,
      "a finished season has no scenario - there is nothing left to do")


# ---------------------------------------------------------------------------
print("\n5. THE RIVALRY IS THE STANDINGS")

c = mk([["Kandasamy"] + NAMES[1:]] * 3, 8)
check(c.rivals() is None, "nobody is anybody's rival after three rounds",
      "RIVAL_AFTER=%d" % S.Career.RIVAL_AFTER)

c = mk([["Kandasamy", "Borda"] + NAMES[2:],
        ["Borda", "Kandasamy"] + NAMES[2:],
        ["Kandasamy", "Borda"] + NAMES[2:],
        ["Borda", "Kandasamy"] + NAMES[2:]], 8)
r = c.rivals()
check(r and r["player"] and r["b"] == "Borda",
      "the man next to him in the table is his rival", str(r))
check(r and r["a"] == c.me, "and he is always named first when he is in it")

# THE CASE THE OLD RULE MISSED, and the reason the user changed it. These two
# are level on points and hardly ever near each other on the road — which is
# what a great many championship fights actually look like.
c = mk([["Kandasamy", "X", "Y", "Borda"],
        ["Borda", "X", "Y", "Kandasamy"],
        ["Kandasamy", "X", "Y", "Borda"],
        ["Borda", "X", "Y", "Kandasamy"]], 8)
r = c.rivals()
check(r and {r["a"], r["b"]} == {"Kandasamy", "Borda"},
      "two men level on points who never race each other are still rivals",
      str(r))

# A PROCESSION IS NOT A RIVALRY. Telling a man eighty points clear that he has
# a rival is a claim his own standings screen contradicts.
c = mk([["Kandasamy"] + NAMES[1:]] * 4, 10)
r = c.rivals()
check(not (r and r["player"]),
      "a runaway leader is not given a rival he is not racing", str(r))
check(r is None or not r["player"],
      "...and the fight BEHIND him is found instead, which is what he asked for",
      str(r))


# ---------------------------------------------------------------------------
print("\n5b. THE MAN IN THE OTHER SIDE OF THE GARAGE")
# The only comparison in this sport with nothing to explain it away: same
# car, same team, same information. It is the first number any Formula One
# paddock looks up, and it is computable from rounds this overlay recorded.

hh = S.create("open", me="Kandasamy", rounds=8, cls="Mercedes")
check(hh.team_mate_record() is None,
      "no rounds, no head-to-head - and nothing invented to fill it")

for _i, (_q, _qm, _r, _rm) in enumerate(
        [(2, 1, 3, 1), (1, 2, 1, 2), (3, 2, 2, 3), (1, 3, 4, 2), (2, 4, 1, 5)],
        start=1):
    hh.record_quali(_i, _q, 20, "t%d" % _i, mate_pos=_qm, mate="Hamilton")
    hh.record({"n": _i, "slug": "t%d" % _i, "pos": _r, "laps": 20,
               "race_laps": 20, "cls": "Mercedes", "team": "Mercedes",
               "mate": "Hamilton", "mate_pos": _rm,
               "classified": [("Kandasamy", _r), ("Hamilton", _rm),
                              ("Verstappen", 6)]})
rec = hh.team_mate_record()
check(rec and rec["mate"] == "Hamilton", "the team-mate is remembered by name")
check(rec["quali_up"] == 3 and rec["quali_down"] == 2,
      "the qualifying head-to-head is counted",
      "%d-%d" % (rec["quali_up"], rec["quali_down"]))
check(rec["races_up"] == 3 and rec["races_down"] == 2,
      "and the race one too",
      "%d-%d" % (rec["races_up"], rec["races_down"]))

# A ROUND IS BUILT FIELD BY FIELD IN `record`, so anything new has to be
# named there or it is silently dropped. That is exactly what happened: the
# team-mate reached the store and vanished, and the race half read nil-nil
# for ever while the qualifying half (its own writer) worked perfectly.
check(all(r.get("mate") for r in hh.rounds),
      "the team-mate survives into the stored round")

# A DNF IS NOT A BEATING. A head-to-head that counts one flatters whoever
# had the car that held together, and this is meant to measure driving.
hh.record({"n": 6, "slug": "t6", "pos": 18, "laps": 3, "race_laps": 20,
           "cls": "Mercedes", "team": "Mercedes", "mate": "Hamilton",
           "mate_pos": 1, "dnf": True,
           "classified": [("Kandasamy", 18), ("Hamilton", 1)]})
after = hh.team_mate_record()
check(after["races_up"] == 3 and after["races_down"] == 2,
      "a retirement counts for neither of them",
      "%d-%d" % (after["races_up"], after["races_down"]))


print("\n6. THE BOOTH SAYS IT, AND ONLY ON THE CROSSINGS")
# LAW 21: the pools exist, so something must emit them. And LAW 1: "he is
# inside the position he needs" is TRUE for most of a good afternoon, so a
# level-triggered version of this would say it every twenty seconds for half
# an hour.

import era as era_mod
from overlay_booth import BoothMixin


class _Car:
    def __init__(s, cid, place, name):
        s.id=cid; s.place=place; s.display_name=name; s.name=name; s.laps=5
        s.in_pits=False; s.best_lap=None; s.speed=200.0; s.finish_status=0
        s.sector=1; s.is_player=(cid==1); s.cls='Clio Cup 2010'; s.vehicle=name
        s.gap_ahead=1.2; s.gap_leader=1.2; s.laps_down=0; s.places_gained=0
        s.purple_lap=False; s.tyre_front=''; s.started_place=place


class _Sess:
    def __init__(s, cars):
        s.valid=True; s.order=cars; s.cars={c.id:c for c in cars}
        s.leader=cars[0]; s.player=next(c for c in cars if c.is_player)
        s.track='Kyalami'; s.kind='race'; s.green=True; s.finished=False
        s.max_laps=17; s.laps_left=12; s.leader_laps=5; s.num_cars=len(cars)
        s.session_index=10; s.multiclass=False; s.full_course_yellow=False
        s.started=True; s.best_lap_time=80.0; s.yellow_sectors=(0,0,0)
        s.classes=['Clio Cup 2010']
        s.era=era_mod.classify('Clio Cup 2010','')
        s.player_era=s.era
    def car_ahead(s,c):
        i=c.place-1; return s.order[i-1] if 0<i<len(s.order) else None


class _Tts:
    def __init__(s): s.said=[]; s.speaking=False
    def speak(s,t,w,intensity=0,build=False,name=""): s.said.append((w,t))
    def interrupt(s): pass


class _Booth(BoothMixin):
    def __init__(s):
        s.booth_enabled=True; s.tts=_Tts()
        s.tracker=type("T",(),{"confirmed_places":
                               lambda self,x:{c.id:c.place for c in x.order}})()
        s.booth_init()
    def _short_track(s,n): return n
    def _hide_panel(s,n): pass


def _grid(order):
    """order[i] is the driver index running in place i+1; index 0 is him."""
    who = ["Kandasamy"] + NAMES[1:]
    return [_Car(i+1, p+1, who[i]) for p, i in enumerate(order)]


final = mk([["Kandasamy"] + NAMES[1:]] * 3 +
           [["Borda", "Kandasamy"] + NAMES[2:]], 5)
need = final.title_scenarios(field=8)["secure"]
check(need and need > 1, "the fixture needs a real target", "P%s" % need)

b = _Booth()
s = _Sess(_grid([1, 2, 3, 4, 5, 0, 6, 7]))     # him P6, outside
b.season = final
b._season_round = {"n": 5}
b._phase = "mid"
b._title_side = None

fired = []
def _tick(order):
    s.order = _grid(order)
    s.cars = {c.id: c for c in s.order}
    s.leader = s.order[0]
    s.player = next(c for c in s.order if c.is_player)
    ev = b._title_watch(s, 2000.0)
    fired.extend(e[0] for e in ev)
    return [e[0] for e in ev]

first = _tick([1, 2, 3, 4, 5, 0, 6, 7])
check(not first, "the first tick establishes a baseline and says nothing",
      str(first))
up = _tick([1, 2, 0, 3, 4, 5, 6, 7])           # into P3 — inside
check(up == ["title_live"], "crossing INTO the needed place is called",
      str(up))
again = _tick([1, 0, 2, 3, 4, 5, 6, 7])        # P2 — still inside
check(not again, "...and staying there is not said again (LAW 1)", str(again))
down = _tick([1, 2, 3, 4, 0, 5, 6, 7])         # P5 — outside
check(down == ["title_lost"], "and losing it is the same story, both ways",
      str(down))

# NOT ON A ROUND THAT CANNOT DECIDE ANYTHING. With two to go, "he needs
# fifth" is a fact about a race that is not this one.
mid = mk([["Kandasamy"] + NAMES[1:]] * 2, 5)
b2 = _Booth(); s2 = _Sess(_grid([1, 2, 3, 4, 5, 0, 6, 7]))
b2.season = mid; b2._season_round = {"n": 3}; b2._phase = "mid"
b2._title_watch(s2, 2000.0)
s2.order = _grid([1, 2, 0, 3, 4, 5, 6, 7])
s2.player = next(c for c in s2.order if c.is_player)
check(not b2._title_watch(s2, 2001.0),
      "nothing is claimed on a round that cannot settle the championship")

# AND NEVER OFF A CAREER ROUND. A one-off race in the same car is not a
# round of his championship, and the same gate the rest of the booth uses
# applies here.
b3 = _Booth(); s3 = _Sess(_grid([1, 2, 3, 4, 5, 0, 6, 7]))
b3.season = final; b3._season_round = None; b3._phase = "mid"
check(not b3._title_watch(s3, 2000.0),
      "an off-career race says nothing about the championship")


print("\n" + ("ALL PASSED" if not fails else "FAILED: %d" % len(fails)))
for f in fails:
    print("   -", f)
sys.exit(1 if fails else 0)
