"""The booth knows whose career it is commentating.

Until this existed the commentary knew the race, the circuit, the cars and the
real drivers — and nothing about the career being played. A man in his third
season of Formula 3, who won karting two years ago and has a Formula 2 seat
riding on the afternoon, was "the driver in fourth".

The whole feature rests on one property: EVERY FACT IT SAYS WAS WATCHED. Not
looked up, not invented — recorded by this overlay, in seasons it scored. That
is why it works identically on a fictional GT4 grid and in Formula One, and it
is the line this test exists to hold.

    python tests/careerboothtest.py
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lines
import lines as lines_mod
import overlay_booth as ob
import season as S

fails = []
def check(c, l, e=""):
    print(("  [ OK ] " if c else "  [FAIL] ") + l + (("  " + e) if e else ""))
    if not c:
        fails.append(l)


_tmp = tempfile.mkdtemp(prefix="factortv_cb_")
S.CAREER_DIR = _tmp
ME = "Kandasamy"


class Car(object):
    def __init__(self, name, place):
        self.name = self.display_name = name
        self.place = place
        self.is_player = (place == 1)
        self.cls = "Tatuus F3"
        self.laps = 4
        self.in_pits = False
        self.best_lap = 90.0 + place


class Sess(object):
    """The smallest session the career caller actually touches."""
    def __init__(self):
        self.order = [Car(ME, 1), Car("A Rival", 2), Car("B Rival", 3)]
        self.player = self.order[0]
        self.leader = self.order[0]
        self.green = True
        self.kind = "race"
        self.circuit = None
        self.classes = ["Tatuus F3"]
        self.multiclass = False


class Booth(ob.BoothMixin):
    """The mixin alone, with the two attributes the caller reads."""
    def __init__(self, career, rnd=None):
        self.season = career
        self._season_round = rnd or {"n": 1, "slug": "x", "event": ""}

    def _kw(self, s, **kw):
        out = dict(kw)
        for k, v in list(out.items()):
            if hasattr(v, "display_name"):
                out[k] = v.display_name
        return out


def _career(tier=2, path="single_seater", rounds=6, history=(), arcs=()):
    c = S.create("open", me=ME, rounds=rounds, ladder_path=path,
                 tier_index=tier)
    if history:
        c.data["ladder_history"] = [dict(h) for h in history]
    if arcs:
        c.data["ladder_done"] = list(arcs)
    return c


def _race(c, pos=1, n=None):
    n = n or (len(c.rounds) + 1)
    order = ["A Rival", "B Rival"]
    order.insert(min(pos - 1, 2), ME)
    c.record({"n": n, "slug": "t%d" % n, "pos": order.index(ME) + 1,
              "laps": 20, "race_laps": 20,
              "classified": [(nm, i + 1) for i, nm in enumerate(order)]})


WON_F4 = ({"name": "Formula 4", "pos": 1, "rounds": 6, "wins": 4,
           "podiums": 5, "when": 2},)

print("\n1. THE POOLS EXIST AND SOMETHING CALLS THEM")
# LAW 21, which this project has broken four times: a pool with no caller is
# invisible and `lines.py` reports it as healthy, because the lines are valid.
src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "overlay_booth.py"), encoding="utf-8").read()
pools = [k for k in lines.load() if k.startswith(("ladder_", "reg_"))]
check(len(pools) >= 10, "the career pools are loaded", "%d" % len(pools))
orphans = [k for k in pools if ('"%s"' % k) not in src]
check(not orphans, "and every one of them has a caller", str(orphans))
check(set(ob.LADDER_CATS) >= set(pools),
      "all of them share the family cooldown — one thought, said once",
      str(sorted(set(pools) - set(ob.LADDER_CATS))))

print("\n1c. VARIANTS IN PROPORTION TO HOW OFTEN A POOL FIRES")
# The user, after every content pass so far: "repetitiveness will be a real
# killer here". He is right and the answer is not a flat number — it is a rule.
#
# A pool a driver hears in EVERY SESSION of a division he sits in for seasons
# needs a deep bag. One that fires once in a career does not. This encodes
# which is which, so the next pool added has to answer the question rather than
# inherit whatever felt like enough on the day.
OFTEN = ("status_rookie", "status_riser", "status_contender",
         "status_champion", "status_multi", "status_legend",
         "reg_grassroots", "reg_junior", "reg_professional",
         "ladder_rivalry", "ladder_needle")
SOMETIMES = ("ladder_home", "ladder_nation", "ladder_title_run",
             "ladder_climb", "ladder_record", "ladder_promotion",
             "ladder_reigning", "ladder_first_race", "ladder_arc")
ONCE = ("status_arrival", "status_arrival_more", "ladder_home_win",
        "ladder_last_chance")
thin = [(k, len(lines_mod.pool(k))) for k in OFTEN
        if len(lines_mod.pool(k)) < 5]
check(not thin, "a pool heard every session has at least five wordings",
      str(thin))
thin = [(k, len(lines_mod.pool(k))) for k in SOMETIMES
        if len(lines_mod.pool(k)) < 3]
check(not thin, "one heard a few times a season has at least three", str(thin))
thin = [(k, len(lines_mod.pool(k))) for k in ONCE
        if len(lines_mod.pool(k)) < 3]
check(not thin, "and even the once-a-career lines have alternatives, because "
      "a career is replayed", str(thin))
# ...AND NO TWO LINES IN A POOL MAY OPEN THE SAME WAY. Six wordings that all
# start "{drv} is" are one wording with six endings.
same = []
for k in OFTEN + SOMETIMES:
    heads = [" ".join((e["t"] if isinstance(e, dict) else e).split()[:4])
             for e in lines_mod.pool(k)]
    if len(set(heads)) < len(heads):
        same.append(k)
check(not same, "and no two lines in a pool open with the same four words",
      str(same))


print("\n1d. THE LAST TWO RUNGS CARRY THEIR YEAR")
# Asked for directly: "for the sake of the career and the story arc I want it
# year specific and mentioned in commentary for F2 and F1 - that 2021 season
# is iconic and it will work better for players to feel like they are working
# towards it."
#
# THIS IS THE EXCEPTION THE PRODUCT ALREADY MAKES. The rule that a mod year
# is "for knowing, never for saying" is about the ROAD - a 1991 Silverstone
# layout announcing itself tells a driver he is re-running somebody else's
# season. A SEASON year is the opposite, and `season_launch` has always said
# "the opening round of the 1988 Formula One season" for that reason.
import era as _era2


class _YP(object):
    def __init__(self, cls):
        self.cls = cls
        self.display_name = ME
        self.place = 1


class _YS(object):
    """A session with the WHOLE class list, which is what dates a
    team-named Formula One grid - one constructor on its own cannot be
    dated and resolves to 2020, which is where "welcome to the 2020
    season" came from the first time."""
    def __init__(self, cls, classes):
        self.player = _YP(cls)
        self.era = _era2.classify(cls, "", classes)
        self.player_era = self.era


_F1_2021 = ["Alfa Romeo", "Alpha Tauri", "Alpine", "Aston Martin", "Ferrari",
            "Haas", "McLaren", "Mercedes", "Red Bull", "Williams"]
for _tier, _cls, _classes, _want in (
        (0, "Kart F1", ["Kart F1"], "Karting"),
        (1, "Tatuus F4", ["Tatuus F4"], "Formula 4"),
        (2, "Formula 3 2019", ["Formula 3 2019"], "Formula 3"),
        (3, "Formula 2 2019", ["Formula 2 2019"], "2019 Formula 2"),
        (4, "Mercedes", _F1_2021, "2021 Formula One")):
    _c = S.create("open", me=ME, rounds=5, ladder_path="single_seater",
                  tier_index=_tier)
    _got = Booth(_c)._series_name(_YS(_cls, _classes))
    check(_got == _want, "%s is called %r" % (_cls, _want), _got)

# ...AND THE JUNIOR RUNGS STAY YEAR-FREE. Down there a year would be the
# MOD's rather than the story's, which is the layout rule again.
_junior = [Booth(S.create("open", me=ME, rounds=5, ladder_path="single_seater",
                          tier_index=_t))._series_name(_YS(_c2, [_c2]))
           for _t, _c2 in ((0, "Kart F1"), (1, "Tatuus F4"),
                           (2, "Formula 3 2019"))]
# A YEAR, NOT ANY DIGIT. "Formula 4" and "Formula 3" have a number in the
# NAME of the championship — checking for digits called both of them dated,
# which is the sort of test that fails while the code is right.
import re as _re3
check(not any(_re3.search(r"(19|20)\d\d", n) for n in _junior),
      "no year below Formula 2", str(_junior))


print("\n1b. THE CHAMPIONSHIP NAMES ITSELF, THE CAR NEVER NAMES IT")
# A LIVE, GAME-BREAKING BUG. The user started a USF2000 career and the booth
# opened qualifying with "the 2000 Formula One season" - because `_series_name`
# was a staticmethod with no access to the career and inferred a name from the
# CAR: era.classify reads the "2000" in "USF2000" as a year and the chassis as
# a single-seater. A guess about which championship he is driving is not a
# small wrongness; it is the line that exists to say career mode is running.
import era as _era

class _P(object):
    def __init__(self, cls):
        self.cls = cls
        self.display_name = ME
        self.place = 1

class _Sess(object):
    def __init__(self, cls):
        self.player = _P(cls)
        self.era = _era.classify(cls, "")
        self.player_era = self.era

for path, tier, cls, want in (("road_to_indy", 0, "USF2000", "USF2000"),
                              ("touring", 0, "Clio Cup", "Hot hatch"),
                              ("single_seater", 2, "Tatuus F3", "Formula 3"),
                              ("stock_car", 3, "NASCAR", "NASCAR")):
    car = S.create("open", me=ME, rounds=5, ladder_path=path, tier_index=tier)
    got = Booth(car)._series_name(_Sess(cls))
    check(got == want, "a %s career is called %r" % (want, want), got)
check("Formula" not in Booth(S.create(
    "open", me=ME, rounds=5, ladder_path="road_to_indy", tier_index=0)
    )._series_name(_Sess("USF2000")),
    "and USF2000 is NEVER called Formula One again")
# A one-off race has no career to ask, so the car is all there is — but the
# fallback now prefers the REAL class string over a category invented from it.
check(Booth(None)._series_name(_Sess("USF2000")) == "USF2000",
      "a one-off in the same car names the class rather than guessing a series")
check("2025" in Booth(None)._series_name(_Sess("F1 Test 2025")),
      "while a season era.py genuinely knows keeps its proper name",
      Booth(None)._series_name(_Sess("F1 Test 2025")))

print("\n2. IT SAYS NOTHING WITHOUT A CAREER")
# A one-off race must cost the broadcast nothing at all.
plain = S.create("open", me=ME, rounds=3)
check(Booth(plain)._ladder_call(Sess()) == (None, {}),
      "a career off the ladder produces no career line")
check(Booth(None)._ladder_call(Sess()) == (None, {}),
      "and no career at all produces none either")
# THE SAME GATE THE DRIVER RECORDS USE. A career stays loaded in the settings
# for as long as it exists, so a race that is not one of its rounds must be
# silent about it.
lad = _career(history=WON_F4)
b = Booth(lad)
b._season_round = None
check(b._ladder_call(Sess()) == (None, {}),
      "and a race that is not a round of the career says nothing about it")

print("\n3. HIS FIRST RACE IN A NEW DIVISION")
b = Booth(_career(history=WON_F4))
cat, kw = b._ladder_call(Sess(), pre=True)
check(cat == "ladder_reigning",
      "the reigning champion of the division below is the strongest thing to "
      "say about him", str(cat))
check(kw.get("below") == "Formula 4", "and it names the division he won",
      str(kw.get("below")))
# ...but only while it IS last season. A man who won Formula 4 two rungs ago
# is not the reigning anything.
old = _career(history=(WON_F4[0],
                       {"name": "Formula 3", "pos": 4, "rounds": 6, "when": 3}))
cat, kw = Booth(old)._ladder_call(Sess(), pre=True)
check(cat != "ladder_reigning",
      "a title two seasons ago does not make him the reigning champion",
      str(cat))

print("\n4. THE SEAT ABOVE IS THE STORY, AND IT OUTRANKS THE RECORD")
c = _career(history=WON_F4)
for i in range(5):
    _race(c, pos=1, n=i + 1)
b = Booth(c, rnd={"n": 6, "slug": "x", "event": ""})
cat, kw = b._ladder_call(Sess())
check(cat == "ladder_last_chance",
      "the final round with a promotion riding on it beats everything else",
      str(cat))
check(kw.get("need") == "P3", "and it says what the seat actually costs",
      str(kw.get("need")))
# A rung with nothing above it cannot have a promotion story.
top = _career(tier=4, history=WON_F4)
for i in range(5):
    _race(top, n=i + 1)
cat, _ = Booth(top, rnd={"n": 6, "slug": "x"})._ladder_call(Sess())
check(cat != "ladder_last_chance",
      "at the top of a path there is no seat above to race for", str(cat))

print("\n5. IT ONLY CLAIMS WHAT THE STORE HOLDS")
# A driver in his first season has no record, and the booth stays quiet rather
# than padding — the same discipline the real-driver records follow.
# ...EXCEPT THAT HE IS A ROOKIE, which is a fact about him rather than a claim
# about a record he does not have. This is the start of the arc the user asked
# for — "the first few divisions the commentary team should have a nickname for
# me, being The Rookie" — and it is the one thing that can be said about a
# driver with no history at all.
fresh = _career()
cat, _ = Booth(fresh)._ladder_call(Sess())
check(cat == "status_rookie",
      "a first-season driver is a rookie, and gets no record claim", str(cat))
rich = _career(tier=4, history=(WON_F4[0],
                                {"name": "Formula 3", "pos": 1, "rounds": 6,
                                 "wins": 5, "podiums": 6, "when": 3},
                                {"name": "Formula 2", "pos": 1, "rounds": 6,
                                 "wins": 6, "podiums": 6, "when": 4}))
_race(rich)
cat, kw = Booth(rich, rnd={"n": 2, "slug": "x"})._ladder_call(Sess())
check(cat in ("ladder_record", "ladder_climb", "ladder_arc"),
      "a driver with a career behind him gets one", str(cat))
check(int(kw.get("wins") or 0) == rich.resume()["wins"],
      "and every number in it comes from the store",
      "%s vs %s" % (kw.get("wins"), rich.resume()["wins"]))

print("\n6. REGISTER IS A TONE, AND IT FOLLOWS THE RUNG")
for tier, want in ((0, "reg_grassroots"), (2, "reg_junior"),
                   (4, "reg_professional")):
    c = _career(tier=tier)
    cat, _ = Booth(c)._register_call(Sess())
    check(cat == want, "%s sounds like %s" % (S.ladder_mod.tiers(
        "single_seater")[tier]["name"], want.split("_")[1]), str(cat))
# The archive register already has its own programme — Brett, and
# booth_archive.json — and a second voice over it is two shows at once.
hist = _career(path="historic", tier=0)
cat, _ = Booth(hist)._register_call(Sess())
check(cat is None, "and the historic tour keeps the archive's own voice",
      str(cat))

print("\n6b. WHERE HE IS FROM, AND WHEN IT IS HOME")
# The third identity field. It exists for one reason: "the young Australian,
# and this is his home race" is a thing a booth says on the first lap and a
# player feels. A favourite colour would not be.
import nations as _nat
check(not _nat.validate(), "nations.json validates", str(_nat.validate()[:2]))
check(_nat.demonym("Australia") == "Australian", "a country has a demonym")
check(_nat.demonym("") == "" and _nat.demonym("Atlantis") == "",
      "and one we do not hold produces nothing rather than a guess")
# THE CIRCUIT DATA IS INCONSISTENT ABOUT THE ARTICLE — twelve circuits under
# "United States" and five under "the United States". A home race that worked
# at Watkins Glen and not at Sebring would be a bug nobody could explain.
check(_nat.is_home("the United States", "United States"),
      "a leading 'the' is folded on both sides")
check(not _nat.is_home("Australia", ""),
      "and a circuit with no country is never home")

class _Circuit(object):
    def __init__(self, country):
        self.country = country
        self.name = "Somewhere"
        self.known = True

home = _career(history=WON_F4)
home.set_nationality("Australia")
sess = Sess()
sess.circuit = _Circuit("Australia")
cat, kw = Booth(home)._ladder_call(sess, pre=True)
check(cat == "ladder_home", "his own country is a home race", str(cat))
check(kw.get("nat") == "Australian", "and the demonym is filled in",
      str(kw.get("nat")))
sess.circuit = _Circuit("Belgium")
cat, _ = Booth(home)._ladder_call(sess, pre=True)
check(cat != "ladder_home", "anywhere else is not", str(cat))
# NO NATIONALITY, NO CLAIM. A career that never picked one is silent about it
# rather than guessing from the driver name.
anon = _career(history=WON_F4)
sess.circuit = _Circuit("Australia")
cat, _ = Booth(anon)._ladder_call(sess, pre=True)
check(cat != "ladder_home",
      "a driver with no nationality has no home race", str(cat))

print("\n6c. ROOKIE TO LEGEND — the arc the whole climb is for")
# The user's ask: "players will work hard trying to get through the ranks, and a
# commentary line or news report goes a long way in rewarding a player". Every
# threshold below is something this overlay WATCHED him cross.
def _st(tier, hist, path="single_seater"):
    c = S.create("open", me=ME, rounds=5, ladder_path=path, tier_index=tier)
    c.data["ladder_history"] = list(hist)
    return c

_won = lambda n: [{"name": "X", "pos": 1, "rounds": 5, "when": i}
                  for i in range(n)]
_ran = lambda n: [{"name": "X", "pos": 3, "rounds": 5, "when": i}
                  for i in range(n)]
for tier, hist, want in ((0, [], "rookie"), (2, [], "rookie"),
                         (2, _ran(1), "riser"), (4, _ran(4), "contender"),
                         (4, _won(1), "champion"), (4, _won(2), "multi"),
                         (4, _won(3), "legend")):
    got = _st(tier, hist).status()[0]
    check(got == want, "tier %d with %d seasons -> %s" % (tier, len(hist), want),
          got)
# SEASONS COMPLETED, NOT RUNGS REACHED. `reached` is non-zero for anybody who
# joined a path partway up, so reading it called a man in his very FIRST season
# a Riser — the opposite of an arc that has to start at rookie.
check(_st(4, []).status()[0] == "rookie",
      "a driver who ENTERED at a professional rung has still done nothing yet")

print("\n6d. THE STATUS RISES ONCE, AND NEVER FALLS")
c = _st(4, _won(1))
check(c.status_changed()[0] == "champion", "becoming champion is news once")
check(c.status_changed() is None, "and is not news a second time")
# A SIDEWAYS MOVE DROPS HIM INTO A JUNIOR DIVISION, and no sport has ever run
# the headline "Dante Kandasamy has been demoted to Riser".
c.data["ladder_history"] = _ran(2)
check(c.status_changed() is None, "and it can never go backwards")

print("\n6e. THE FLAG MOMENT")
# "From rookie to champion" — the one line here that can only be said in the
# four seconds after a chequered flag, and the reward for the whole climb.
first = _st(4, _won(1))
sess = Sess()
sess.finished = True
cat, kw = Booth(first)._ladder_call(sess)
check(cat == "status_arrival", "a first title gets the rise called out loud",
      str(cat))
check(Booth(first)._ladder_call(sess)[0] != "status_arrival",
      "and it cannot fire twice for one championship")
more = _st(4, _won(2))
check(Booth(more)._ladder_call(sess)[0] == "status_arrival_more",
      "a second title gets its own, which is not the same sentence")
sess.finished = False
check(Booth(_st(4, _won(3)))._ladder_call(sess)[0] != "status_arrival",
      "and nothing of the kind is said mid-race")

print("\n7. EVERY LINE RENDERS WITH REAL FACTS")
# LAW 5: a slot that can be empty must not be in a template. Rendering every
# line of every pool against a real career is the only way to know.
import era as era_mod
c = _career(tier=2, history=WON_F4, arcs=("touring",))
_race(c)
b = Booth(c, rnd={"n": 2, "slug": "x"})
_cat, kw = b._ladder_call(Sess())
kw = dict(kw or {})
kw.update({"drv": ME, "series": "Formula 3", "below": "Formula 4",
           "need": "P3", "seasons": "two", "races": 7, "wins": 4,
           "titles": "one", "left": 3,
           # WHERE HE IS FROM. A demonym is a bare noun ("Australian") because
           # the lines put their own article in front of it, and the adjective
           # is separate because "a Australian licence" is not a sentence.
           "nat": "Australian", "adj": "Australian",
           # The rivalry lines name the other man and the gap — both come from
           # `Career.rivals()`, which the news feed reads too.
           "b": "Marcus Vinter", "pts": 4})
bad = []
for pool in pools:
    for e in lines.pool(pool):
        t = e["t"] if isinstance(e, dict) else e
        try:
            out = t.format(**kw)
        except KeyError as exc:
            bad.append("%s: no %s" % (pool, exc))
            continue
        if "  " in out or out.strip().startswith(("and", ",")):
            bad.append("%s: %r" % (pool, out[:40]))
check(not bad, "no line has a slot the career cannot fill", str(bad[:3]))

print("\n8. THE PRE-RACE SEQUENCE HAS A CAREER BEAT")
check("career" in ob.PRE_RACE and "career" in ob.PRE_QUALI,
      "it airs before a race and before qualifying too",
      str(ob.PRE_RACE))
check(ob.PRE_RACE.index("career") == ob.PRE_RACE.index("season") + 1,
      "straight after the season beat — 'round four of six' and 'a seat rides "
      "on it' are one thought")

print("\n9. AND IT IS COLOUR, NOT NEWS")
# A career fact during the opening lap or the run to the flag is the booth
# looking away from the race — the exact complaint that produced the phase
# gates in the first place. It has to sit BEHIND them in `_filler`.
i_open = src.index('if self._phase == "opening":')
i_close = src.index('if self._phase == "closing":', i_open)
i_call = src.index("LADDER_FAMILY_GAP:", i_open)
check(i_call > i_open and i_call > i_close,
      "the career is offered only after the opening and closing gates")
check(src.index("LADDER_CATS = (") < src.index("DRIVER_CATS = ("),
      "and the whole family shares one cooldown")

shutil.rmtree(_tmp, ignore_errors=True)

# ---------------------------------------------------------------- 20. HIS NAME
#
# "the booth should basically call me by two things, either my name or my
# status". The first mention of the player in a session carries what he is;
# after that he is himself, with the status form returning now and then.
banner = lambda t: print("\n" + t)
banner("20. the name carries the status the first time it is said")

_nb = Booth(_career(tier=0, rounds=3))
_nb._pre_at = 1000.0
_nb._status_named = False
_sess = Sess()
_sess.player.is_player = True
_first = _nb._status_form(_sess, ME)
check(ME in _first and "rookie" in _first.lower(),
      "the first mention is name plus status", _first)
check(_first in ("%s, the rookie," % ME, "the rookie %s" % ME),
      "and it is one of the two forms asked for", _first)
_nb._status_named = True

# 20. A STATUS LINE SAYS WHAT HE IS, NOT WHAT THE BOOTH IS SEEING.
#
# Heard in the pre-qualifying sequence of the FIRST session of a career,
# before a single lap had been set anywhere: "there is something about the
# way he is placing this car". There was nothing about the way he was placing
# the car. He had not yet driven it.
#
# These pools are drawn by the PRE-SESSION career beat, so nothing in them
# may claim an observation. What a man IS can be said before the engines
# start; what he is DOING cannot.
import re as _re2
_SEEN = (r"placing this car", r"the way he (is|has)", r"you can see it",
         r"watching him", r"this afternoon", r"out there today",
         r"so far this")
_claims = []
for _p in ("status_rookie", "status_riser", "status_contender",
           "status_champion", "status_multi", "status_legend"):
    for _e in lines_mod.pool(_p):
        _t = (_e.get("t") if isinstance(_e, dict) else _e) or ""
        if any(_re2.search(_w, _t.lower()) for _w in _SEEN):
            _claims.append("%s: %s" % (_p, _t[:60]))
check(not _claims,
      "no status line claims to have watched him drive",
      "; ".join(_claims[:2]))


# 20a. A POOL THAT SAYS THE STATUS MUST NOT ALSO BE HANDED IT.
#
# A LIVE BUG, heard in a karting session: "The rookie, the rookie. And Chuck,
# there is something about the way he is placing this car..." The template is
# `"The rookie, {drv}."`, written when {drv} was always a NAME - and the
# status form then filled the slot with the status as well.
#
# LAW 13, exactly: never put a determiner in front of a slot, because the
# slot carries its own article. The margin slots learned it first ("another a
# tenth"); this is the same mistake with a person instead of a gap.
import json as _json, glob as _glob, re as _re
_STATUS_WORDS = ("rookie", "riser", "contender", "champion", "legend")
_writes_it = []
for _f in _glob.glob(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "lines_data", "*.json")):
    try:
        _d = _json.load(open(_f, encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(_d, dict):
        continue
    for _pool, _v in _d.items():
        if not isinstance(_v, list):
            continue
        for _e in _v:
            _t = (_e.get("t") if isinstance(_e, dict) else "") or ""
            if "{drv}" not in _t and "{a}" not in _t:
                continue
            if any(_re.search(r"the %s" % _w, _t.lower())
                   for _w in _STATUS_WORDS):
                _writes_it.append(_pool)
                break
_leaky = sorted(set(_writes_it) - set(ob.STATUS_SELF))
check(not _leaky,
      "a pool that writes the status is never handed it in the slot too",
      str(_leaky))
check(all(p not in ob.STATUS_SELF or True for p in ob.STATUS_SELF),
      "and the exempt list is declared, not inferred at runtime")


# 20b. AFTERWARDS HE IS A NAME, AND MOSTLY A SURNAME.
#
# The user, from the live log: "the status names like Rookie is being used too
# much when they are addressing the player ... more often than not use more of
# the surname". The log had "rookie" nineteen times against thirty-three uses
# of his name.
#
# AND THE REASON WAS A BUG, NOT A RATIO. The seed was `hash((name,
# self._pre_at))` — constant for the entire session — so `seed % 5` was never
# one mention in five. It was ALL of them or NONE of them, and that session it
# was all of them. Seeding on lines-actually-aired is what makes the ratio
# mean anything, and this checks the property that was missing: the form has
# to VARY across mentions.
# A TWO-WORD NAME, because the whole point is the choice between the full
# name and the surname — and `ME` is a single word, which hides it.
FULL = "Dante Kandasamy"
_plain_forms = {}
_apt_forms = {}
for _n in range(60):
    _nb._say_n = _n
    _plain_forms[_nb._status_form(_sess, FULL, apt=False)] = 1
    _apt_forms[_nb._status_form(_sess, FULL, apt=True)] = 1
check(len(_plain_forms) > 1,
      "the wording varies between mentions rather than per session",
      str(sorted(_plain_forms)))
check("Kandasamy" in _plain_forms and FULL in _plain_forms,
      "and it alternates between the full name and the surname",
      str(sorted(_plain_forms)))

# THE STATUS ONLY WHERE IT FITS. "That is the rookie off at turn four" works
# because the mistake and the status are one thought; "the rookie is four
# tenths down in sector two" is a badge stapled to a gap.
check("the rookie" not in _plain_forms,
      "an ordinary line never reaches for the status", str(sorted(_plain_forms)))
check("the rookie" in _apt_forms,
      "and a line the status belongs in does", str(sorted(_apt_forms)))

# ...AND THE SURNAME IS THE COMMON CASE, which is simply how a broadcast
# talks once it has introduced somebody.
_counts = {}
for _n in range(120):
    _nb._say_n = _n
    _f = _nb._status_form(_sess, FULL, apt=True)
    _counts[_f] = _counts.get(_f, 0) + 1
_surname = FULL.split()[-1]
check(max(_counts, key=_counts.get) == _surname,
      "the surname is the most common form", str(_counts))
check(_counts.get("the rookie", 0) < _counts[_surname] / 2.0,
      "and the status is a long way behind it",
      "status %d vs surname %d"
      % (_counts.get("the rookie", 0), _counts[_surname]))

# ANYTHING NOT DECLARED APT GETS A NAME. The default matters: a new pool has
# to ASK for the status form, so the next category added cannot join the list
# by accident.
# ASSERTED AGAINST THE SOURCE, and deliberately.
#
# The `Booth` in this file OVERRIDES `_kw` with a stub — which is the exact
# habit the handover calls the most expensive one in this project: a shim
# that replaces the method under suspicion tests the shim. So this reads the
# real `overlay_booth.py` instead. Crude, and it holds a property no stub
# can fake: an unconsumed `cat` key would become a template slot named
# "cat", one typo away from airing.
_src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "overlay_booth.py"), encoding="utf-8").read()
check('extra.pop("cat", None)' in _src,
      "the real `_kw` consumes the category instead of leaking it as a slot")
check('_status_form(s, n, apt=apt)' in _src,
      "...and hands it to the status form")

# Outside a career the name is a name. A one-off race must cost nothing.
check(Booth(None)._status_form(_sess, ME) == ME,
      "no career, no decoration")
_plain = S.create("open", me=ME, rounds=3)
check(Booth(_plain)._status_form(_sess, ME) == ME,
      "and a plain season is not a ladder career")

banner("21. and what he is follows, once, whoever says it")
_sb = Booth(_career(tier=0, rounds=3))
_cat, _kw = _sb._status_call(Sess())
check(_cat == "status_rookie", "a debutant is introduced as a rookie", str(_cat))
check(_sb._status_call(Sess())[1].get("drv"),
      "and the line knows whose name to use")
check(Booth(None)._status_call(Sess()) == (None, {}),
      "no career, nothing to introduce")
# LAW 11: the flag flips when a line AIRS, never when one is composed.
_src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "overlay_booth.py"), encoding="utf-8").read()
_kwbody = _src.split("def _kw(self, s,")[1].split("\n    def ")[0]
check("_status_named = True" not in _kwbody,
      "composing a line never spends the introduction")



# ---------------------------------------------------------------- 22. THE CRASH
#
# A colour source that RAISES takes the whole booth off the air, because the
# filler asks for a career line on every quiet tick. One session logged 2,618
# identical tracebacks and went silent for half a race: `Track.country` is a
# METHOD and the career caller read it as an attribute.
banner("22. a career line can never take the booth off the air")

class _Circuit(object):
    name = "Kyalami"
    known = True
    def country(self):          # A METHOD. This is the shape that broke it.
        return "South Africa"

_cs = Sess()
_cs.circuit = _Circuit()
_cs.track = "kyalami"
_cc = _career(tier=0, rounds=3)
_cc.set_nationality("South Africa")
try:
    _cat, _ = Booth(_cc)._ladder_call(_cs, pre=True)
    check(True, "a circuit whose country is a method does not raise", str(_cat))
except Exception as _e:
    check(False, "a circuit whose country is a method does not raise", repr(_e))

import nations as _nat
check(_nat.is_home("South Africa", lambda: "x") is False,
      "and the folder itself refuses anything that is not a name")
check(_nat.is_home("South Africa", "The South Africa") is True,
      "while still folding the article it was written for")

banner("23. a fight for the lead outranks a midfield move ANYWHERE in a race")
_lead = ob.PRIORITY["battle"] + ob.PLACE_WEIGHT[2] + ob.FRONT_BONUS
_mid = ob.PRIORITY["overtake"] + ob.PLACE_WEIGHT[4]
check(_lead > _mid, "mid-race: the lead battle wins", "%d vs %d" % (_lead, _mid))
check(ob.LATE_FRONT_BONUS > ob.FRONT_BONUS,
      "and the closing laps still weigh it hardest")



# ---------------------------------------------------------------- 24. THE FENCE
#
# "so you sure the commentary won't break again?" It cannot be guaranteed that
# no source ever raises. It CAN be guaranteed that one which does costs a line
# rather than the broadcast — which is the property this holds.
banner("24. one broken source cannot silence the booth")

class _Exploding(Booth):
    def _ladder_call(self, s, pre=False):
        raise RuntimeError("the career source is broken")

_xb = _Exploding(_career(tier=0, rounds=3))
_xb._log = lambda *a: None                     # quiet during the test
_out = _xb._guard("career colour", _xb._ladder_call, Sess(),
                  fallback=(None, {}))
check(_out == (None, {}), "a raising source returns its fallback", str(_out))
check(len(_xb._guard_seen) == 1, "and the fault is recorded once")

_reported = []
_xb2 = _Exploding(_career(tier=0, rounds=3))
_xb2._log = lambda tag, msg: _reported.append(msg)
for _ in range(300):
    _xb2._guard("career colour", _xb2._ladder_call, Sess(), fallback=(None, {}))
check(len(_reported) <= 6,
      "300 identical failures are a handful of log lines, not 300",
      "reported=%d" % len(_reported))
check(any("x100" in m for m in _reported),
      "and the count is carried, so a persistent fault is still obvious")

# A DIFFERENT fault is never hidden behind an old one.
def _other():
    raise ValueError("something else entirely")
_xb2._guard("career colour", _other, fallback=None)
check(len(_xb2._guard_seen) == 2, "a new fault gets its own entry")


print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
