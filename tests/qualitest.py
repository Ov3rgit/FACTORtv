# -*- coding: utf-8 -*-
"""Qualifying: the timesheet as a story.

A quali session has no overtakes and no meaningful gaps. What it has is a
sheet, and the things worth saying about one are who is on top, by how much,
whether anybody is trading it with him, and who is nowhere.

Every assertion here is really the same assertion: DO NOT SAY SOMETHING THE
TIMING SCREEN CONTRADICTS. A margin over a runner-up who does not exist, a
"duel" between three different drivers, a man called slow when he simply has
not been out yet — each of those is visible to the viewer as a lie.

    python tests/qualitest.py
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lines as lines_mod
from fakes import FakeSession, Booth, grid

fails = []


def check(cond, label, extra=""):
    print(("  [ OK ] " if cond else "  [FAIL] ") + label
          + (("  " + extra) if extra else ""))
    if not cond:
        fails.append(label)


def qsess(cars, **kw):
    kw.setdefault("kind", "quali")
    kw.setdefault("max_laps", 0)
    kw.setdefault("time_left", 900.0)
    kw.setdefault("end_et", 900.0)
    return FakeSession(cars, **kw)


def times(cars, secs):
    """Set best laps; None means this driver has NOT run."""
    for c, t in zip(cars, secs):
        c.best_lap = t
    return cars


def cats(events):
    return [e[0] for e in events]


print("\n1. A MARGIN NEEDS SOMEBODY TO BE AHEAD OF")
# The first driver to set a time leads by nothing. This is the same trap
# `quali_pole` already carries a warning about, and it airs as "by !".
b = Booth()
cars = grid()
times(cars, [92.0] + [None] * (len(cars) - 1))
ev = cats(b._quali_detect(qsess(cars), time.time()))
check("quali_pole" in ev, "the first time set is still provisional pole", str(ev))
check("quali_margin_big" not in ev and "quali_margin_slim" not in ev,
      "but no margin is claimed over an empty sheet", str(ev))

print("\n2. HOW BIG THE MARGIN IS")
b = Booth()
cars = grid()
times(cars, [92.0, 92.05] + [93.0] * (len(cars) - 2))
b._quali_detect(qsess(cars), time.time())
cars[5].best_lap = 91.0                      # a dominant lap by a new man
ev = cats(b._quali_detect(qsess(cars), time.time()))
check("quali_margin_big" in ev, "a second clear is a big margin", str(ev))

b = Booth()
cars = grid()
times(cars, [92.0] + [93.0] * (len(cars) - 1))
b._quali_detect(qsess(cars), time.time())
cars[5].best_lap = 91.97                     # 0.03 up on the old benchmark
ev = cats(b._quali_detect(qsess(cars), time.time()))
check("quali_margin_slim" in ev, "three hundredths is a slim one", str(ev))
check("quali_margin_big" not in ev, "and not a big one at the same time")

print("\n3. THE MARGIN IS AGAINST THE RUNNER-UP, NOT THE OLD BENCHMARK")
# A driver can take half a second off HIS OWN time and still lead by a
# hundredth. Grading on the improvement would call that dominant.
b = Booth()
cars = grid()
# cars[1] holds pole on 91.49; cars[0] is half a second adrift on 92.00.
times(cars, [92.00, 91.49] + [93.0] * (len(cars) - 2))
b._quali_detect(qsess(cars), time.time())
# He takes 0.52 out of HIMSELF and ends up a hundredth clear. Grading on the
# improvement would call that dominant; it is nothing of the kind.
cars[0].best_lap = 91.48
ev = cats(b._quali_detect(qsess(cars), time.time()))
check("quali_margin_big" not in ev,
      "a big self-improvement with a small edge is not a big margin", str(ev))
check("quali_margin_slim" in ev, "it is a slim one", str(ev))

print("\n4. A DUEL IS TWO DRIVERS, NOT THREE")
b = Booth()
cars = grid()
times(cars, [92.0] + [93.0] * (len(cars) - 1))
now = time.time()
b._quali_detect(qsess(cars), now)
ev = []
for i, t in enumerate((91.8, 91.6, 91.4, 91.2)):
    cars[1 if i % 2 else 0].best_lap = t     # the same two men trading it
    ev += cats(b._quali_detect(qsess(cars), now + i * 10))
check("quali_duel" in ev, "two drivers trading pole is a duel", str(ev))

b = Booth()
cars = grid()
times(cars, [92.0] + [93.0] * (len(cars) - 1))
ev = []
for i, t in enumerate((91.8, 91.6, 91.4)):
    cars[i + 1].best_lap = t                 # three DIFFERENT drivers
    ev += cats(b._quali_detect(qsess(cars), now + i * 10))
check("quali_duel" not in ev,
      "three different men going fastest is not a duel", str(ev))

print("\n5. THE BOTTOM OF THE SHEET")
b = Booth()
cars = grid()
# Everyone has run, and the last man is a long way off.
times(cars, [92.0 + i * 0.25 for i in range(len(cars))])
ev = cats(b._quali_filler(qsess(cars), time.time()))
check("quali_tail" in ev, "a spread-out field gets its tail called", str(ev))

print("\n6. A MAN WHO HAS NOT RUN IS NOT SLOW")
b = Booth()
cars = grid()
# Only three have set a time. The rest are absent, not off the pace.
times(cars, [92.0, 92.4, 92.9] + [None] * (len(cars) - 3))
ev = cats(b._quali_filler(qsess(cars), time.time()))
check("quali_tail" not in ev and "quali_offpace" not in ev,
      "no tail call while most of the field is yet to run", str(ev))

print("\n7. A TEST SESSION HAS NO TAIL")
b = Booth()
cars = grid()[:4]
times(cars, [92.0, 93.5, 95.0, 96.5])
ev = cats(b._quali_filler(qsess(cars), time.time()))
check("quali_tail" not in ev, "four cars is not a field", str(ev))

print("\n8. NO SLOT EVER AIRS EMPTY")
# LAW 5, applied to every new category by rendering each one with the slots
# its caller actually supplies.
b = Booth()
cars = grid()
times(cars, [92.0 + i * 0.25 for i in range(len(cars))])
s = qsess(cars)
now = time.time()
events = b._quali_filler(s, now)
cars[5].best_lap = 91.0
events += b._quali_detect(s, now)
bad = []
for cat, kw, _c in events:
    if not cat.startswith("quali_"):
        continue
    for _ in range(12):
        txt, _i, _who = lines_mod.pick(cat, s.era, kw)
        if not txt:
            continue
        # The failure mode is a template slot that resolved to nothing:
        # "by !", "and  is", a trailing "of".
        for probe in (" !", " .", " ,", "by  ", "of  ", "  "):
            if probe in txt:
                bad.append((cat, txt))
                break
check(not bad, "every new quali line renders complete", repr(bad[:3]))

print("\n9. MARGINS ARE SPOKEN, NOT DUMPED")
m = Booth()._margin
check(m(0.01) == "a hundredth", "0.01 -> a hundredth", m(0.01))
check(m(0.03) == "3 hundredths", "0.03 -> 3 hundredths", m(0.03))
check(m(0.1) == "a tenth", "0.10 -> a tenth", m(0.1))
check(m(0.25) == "3 tenths", "0.25 -> 3 tenths (half UP, not bankers)", m(0.25))
check(m(0.35) == "4 tenths", "0.35 -> 4 tenths, consistently", m(0.35))
check(m(1.4) == "1.4 seconds", "1.40 -> 1.4 seconds", m(1.4))
# 0.96 rounds to ten tenths, and nobody says "10 tenths off".
check(m(0.96) == "a second", "0.96 -> a second, not 10 tenths", m(0.96))
check(m(0.94) == "9 tenths", "0.94 stays in tenths", m(0.94))
# "1.0 seconds behind him" is not English either.
check(m(1.0) == "a second", "1.00 -> a second", m(1.0))
# The short forms carry an ARTICLE, so no template may put a determiner in
# front of the slot: "Leclerc another a tenth" went to air.
import glob as _glob, json as _json, re as _re, io as _io
det = []
for _f in _glob.glob("lines_data/*.json"):
    _d = _json.load(_io.open(_f, encoding="utf-8"))
    if not isinstance(_d, dict):
        continue
    for _k, _v in _d.items():
        if _k == "_comment" or not isinstance(_v, list):
            continue
        for _e in _v:
            if isinstance(_e, dict) and _re.search(
                    r"(another|a further)\s+\{(gap|g2|g3)\}",
                    _e.get("t", "")):
                det.append((_k, _e["t"]))
check(not det, "no template puts a determiner before a margin slot",
      repr(det[:3]))
# "2.1 seconds" ends in "1 seconds"; the plural fixer used to rewrite that to
# "2.1 second", which went to air.
from overlay_common import _fix_plural
check(_fix_plural("2.1 seconds off the pace") == "2.1 seconds off the pace",
      "a decimal is not mistaken for a singular")
check(_fix_plural("1 seconds left") == "1 second left",
      "but a real '1 seconds' is still fixed")
check(m(None) == "", "no margin -> empty, and the line is gated instead")

print("\n10. THE SHEET IS SORTED ON THE LAP, NOT ON PLACE")
# mPlace goes to 255 in the garage and scrambles around session changes; a
# top-three built from it is a lie the viewer can see on their own screen.
b = Booth()
cars = grid()
times(cars, [93.0, 92.0, 94.0] + [95.0] * (len(cars) - 3))
for c in cars:
    c.place = 255
sheet = b._sheet(qsess(cars))
check([c.best_lap for c in sheet] == sorted(c.best_lap for c in cars),
      "scrambled places still produce a correct timesheet")

print("\n11. WHERE THE LAP WAS WON")


def with_sectors(c, s1, s2, s3):
    c.best_s1, c.best_s2, c.best_s3 = s1, s2, s3
    c.best_lap = s1 + s2 + s3
    return c


b = Booth()
cars = grid()
for c in cars:
    with_sectors(c, 31.0, 31.0, 31.0)
with_sectors(cars[0], 30.5, 31.0, 31.0)          # the standing benchmark
b._quali_detect(qsess(cars), time.time())
# A new benchmark won almost entirely in the middle sector.
with_sectors(cars[3], 30.48, 30.20, 30.98)
ev = cats(b._quali_detect(qsess(cars), time.time()))
check("quali_lap_sector" in ev, "one dominant sector is named", str(ev))

b = Booth()
cars = grid()
for c in cars:
    with_sectors(c, 31.0, 31.0, 31.0)
with_sectors(cars[0], 31.0, 31.0, 31.0)
b._quali_detect(qsess(cars), time.time())
# Time found evenly across all three: a different, better story.
with_sectors(cars[3], 30.8, 30.8, 30.8)
ev = cats(b._quali_detect(qsess(cars), time.time()))
check("quali_lap_allround" in ev, "time found everywhere is not one sector",
      str(ev))

# THE HONESTY GATE. Two splits out of three is the shape of an answer that
# sounds authoritative and is wrong, so it must produce silence.
b = Booth()
cars = grid()
for c in cars:
    with_sectors(c, 31.0, 31.0, 31.0)
b._quali_detect(qsess(cars), time.time())
cars[3].best_s3 = None
cars[3].best_lap = 90.0
ev = cats(b._quali_detect(qsess(cars), time.time()))
check("quali_lap_sector" not in ev and "quali_lap_allround" not in ev,
      "a missing third split means no sector claim at all", str(ev))

# And the very first benchmark has nothing to be compared against.
b = Booth()
cars = grid()
for c in cars:
    c.best_lap = None
with_sectors(cars[2], 30.0, 31.0, 31.0)
ev = cats(b._quali_detect(qsess(cars), time.time()))
check("quali_lap_sector" not in ev,
      "the first benchmark of the session beats no sectors", str(ev))

print("\n11b. THE ENGINEER IN QUALIFYING")
from overlay_radio import RadioMixin
from overlay_dash import FuelModel
import cast as cast_mod


class QTts(object):
    def __init__(self):
        self.said = []
        self.speaking = False

    def speak(self, text, who, intensity=0, build=False, name=""):
        self.said.append((who, text))


class QRadio(RadioMixin):
    def __init__(self):
        self.radio_enabled = True
        self.tts = QTts()
        self.fuel_model = FuelModel()
        self.radio_init()
        self.player_off = None
        self._greeted = True         # skip the hello


def qrun(r, cars, ticks=1, advance=0.0):
    for _ in range(ticks):
        if advance:
            r._radio_last -= advance
            for k in list(r._topic_last):
                r._topic_last[k] -= advance
        r.update_radio(qsess(cars))


r = QRadio()
cars = grid()
for c in cars:
    with_sectors(c, 31.0, 31.0, 31.0)
me = cars[0]
me.is_player = True
qrun(r, cars, advance=100)
r.tts.said = []
# The player completes a lap and improves.
me.laps += 1
with_sectors(me, 30.4, 30.4, 30.4)
qrun(r, cars, advance=100)
check(bool(r.tts.said), "he says something when you set a time",
      repr(r.tts.said[-1:]))
check(all(w == cast_mod.ENGINEER for w, _t in r.tts.said),
      "and it is the engineer, not the booth")

# Losing a chunk in ONE sector gets named; losing a little everywhere does not.
r = QRadio()
cars = grid()
for c in cars:
    with_sectors(c, 30.0, 30.0, 30.0)
me = cars[1]
me.is_player = True
cars[0].is_player = False
with_sectors(me, 30.02, 30.60, 30.02)        # all of it in sector two
qrun(r, cars, advance=100)
r.tts.said = []
me.laps += 1
qrun(r, cars, ticks=4, advance=100)
sec = [t for _w, t in r.tts.said if "sector two" in t.lower()]
check(bool(sec), "one bad sector is named", repr(r.tts.said))

r = QRadio()
cars = grid()
for c in cars:
    with_sectors(c, 30.0, 30.0, 30.0)
me = cars[1]
me.is_player = True
cars[0].is_player = False
with_sectors(me, 30.2, 30.2, 30.2)           # slower everywhere, evenly
qrun(r, cars, advance=100)
r.tts.said = []
me.laps += 1
qrun(r, cars, ticks=4, advance=100)
# BEING SLOWER EVERYWHERE IS STILL WORTH SAYING — but not as though one
# sector were the problem.
#
# This used to assert total silence, and total silence is what the live
# qualifying session actually got: the call required one sector to carry 55%
# of the deficit, which is rare, so it never fired once in a whole session.
# Being evenly down is the NORMAL case and the driver still wants to know
# where the most of it is going.
#
# The rule the old test was protecting survives intact: he must not claim the
# lap is lost in one place when it is not. So the spread line is required to
# say so.
named = [t for _w, t in r.tts.said
         if "sector one" in t.lower() or "sector two" in t.lower()
         or "sector three" in t.lower()]
check(bool(named), "being slower everywhere still gets a diagnosis", repr(named))
# STRUCTURAL, NOT KEYWORD-MATCHED. The first version of this check grepped
# the prose for words like "everywhere" and "spread", and it was FLAKY: the
# shuffle bag persists across runs, so a different line is drawn each time
# and one of them ("no single problem out there...") used none of those
# words while being perfectly correct. Testing which POOL the line came from
# is the thing that actually matters and cannot drift as prose is edited.
import lines as _lines
SPREAD_POOLS = ("eng_quali_sector_spread", "eng_quali_sector_spread_coach")
DOMINANT = ("eng_quali_sector", "eng_quali_sector_coach")
def _from(pools, text):
    for pool in pools:
        for e in _lines.pool(pool):
            tmpl = e["t"] if isinstance(e, dict) else e
            head = tmpl.split("{")[0].strip()
            if head and head.lower() in text.lower():
                return True
    return False
check(all(_from(SPREAD_POOLS, t) for t in named),
      "...drawn from the SPREAD pools, which say the deficit is spread",
      repr(named))
check(not any("all of it" in t.lower() or "whole deficit" in t.lower()
              or "nowhere else" in t.lower() for t in named),
      "and never claiming one sector carries a deficit that is spread",
      repr(named))

print("\n11b. A FULL PIT LANE IS ONLY A STORY WHILE RUNNING REMAINS")
# The lines say "nobody wants to go early" and "the circuit is empty" — true
# of a session holding fire, nonsense at the end of one, when everybody is in
# the pits because they have finished. It went out in the live log directly
# after "all 20 have set a time now".
b = Booth()
cars = grid()
for c in cars:
    c.best_lap = None
    c.in_pits = True
ev = cats(b._quali_filler(qsess(cars), time.time()))
check("quali_pits" in ev, "a full lane with nobody out yet IS a story", str(ev))

b = Booth()
cars = grid()
for c in cars:
    c.best_lap = 92.0
    c.in_pits = True
ev = cats(b._quali_filler(qsess(cars), time.time()))
check("quali_pits" not in ev,
      "a full lane once everyone has run is just the session ending", str(ev))

print("\n11c. A CIRCUIT FACT IS NOT REPEATED IN ONE SESSION")
# Montreal has four facts, and its island-in-the-Saint-Lawrence line went out
# three times in one qualifying session: the shared bag's recency block lifts
# after a few minutes and the pool is tiny.
import track as _track
b = Booth()
s_ = qsess(grid())
s_.circuit = _track.Track("Montreal")
seen = []
for _ in range(4):
    b._cat_last.clear()
    b._last_spoke = 0
    b.tts.said = []
    if b._track_line(s_, time.time(), "fact", force=True) and b.tts.said:
        seen.append(b.tts.said[-1][1])
check(len(seen) >= 2 and len(seen) == len(set(seen)),
      "consecutive draws give different facts",
      "%d draws, %d distinct" % (len(seen), len(set(seen))))

print("\n12. 'EVERYONE HAS RUN' IS SAID ONCE")
# It is a STATE, not an event (LAW 1). Offered every pass it cycled its four
# lines for the rest of the session: four different ways of saying the same
# unchanging thing, over and over.
b = Booth()
cars = grid()
times(cars, [92.0 + i * 0.1 for i in range(len(cars))])
sx = qsess(cars)
n = 0
for _ in range(12):
    n += cats(b._quali_filler(sx, time.time())).count("quali_all_run")
check(n == 1, "the full field is remarked on exactly once", "%d times" % n)

print("\n12. A LINE NEVER OPENS IN LOWERCASE")
# Several slots are lowercase prose ({gap} "3 tenths", {pos} "twelfth"), so a
# template opening on one inherited its case: "a tenth covering the front
# row" went to air, and to the caption with it. Fixed in
# `lines._sentence_case` rather than by editing the 31 templates that
# currently open on a slot, because the next line anybody writes would
# reintroduce it.
from lines import _sentence_case as _sc
check(_sc("a tenth covering the front row.")
      == "A tenth covering the front row.",
      "a lowercase slot value is capitalised")
check(_sc("3 tenths and shrinking.") == "3 tenths and shrinking.",
      "a line opening on a number is left alone")
check(_sc('"a tenth" he said.') == '"A tenth" he said.',
      "an opening quote is skipped, not capitalised")
# Slots land MID-LINE too: "Improvement. {pos} on the sheet" rendered as
# "Improvement. fourth on the sheet".
check(_sc("Improvement. fourth on the sheet.")
      == "Improvement. Fourth on the sheet.",
      "a slot opening a later sentence is capitalised too")
# ...but a lap time's decimal point must not arm it.
check(_sc("A 1:31.4 is the benchmark. 2 tenths away.")
      == "A 1:31.4 is the benchmark. 2 tenths away.",
      "a decimal point is not a sentence end")

b = Booth()
cars = grid()
times(cars, [92.0 + i * 0.25 for i in range(len(cars))])
s = qsess(cars)
opens = []
for cat, kw, _c in b._quali_filler(s, time.time()):
    for _ in range(20):
        txt, _i, _w = lines_mod.pick(cat, s.era, kw)
        if txt and txt[0].isalpha() and not txt[0].isupper():
            opens.append((cat, txt))
check(not opens, "nothing the booth actually renders starts lowercase",
      repr(opens[:3]))

print("\n13. THE FLAG IN QUALIFYING IS AN EVENT")
# Asked for directly: "there is a chequered flag when the session is over, and
# the commentators and race engineer never get triggered their outro lines".
# The session simply stopped — the last thing aired was whatever colour was in
# the queue, then silence through the flag and the final order.
import cast as cast_mod
from fakes import run as _run

_cars = grid()
_me = _cars[7]
_me.is_player = True
_me.display_name = "Lando Norris"
for _i, _c in enumerate(_cars):
    _c.best_lap = 90.0 + _i * 0.35
_b = Booth()
_s = FakeSession(_cars, kind="quali", max_laps=0, laps_left=0, leader_laps=6,
                 time_left=0.0, end_et=1200.0)
_s.player = _me
_run(_b, _s, ticks=4, step=3.0)
_b.tts.said = []
_b.sting_bank.played = []
_s.finished = True
for _ in range(14):
    _b.update_booth(_s)
    _b._last_spoke -= 5
    for _k in list(_b._cat_last):
        _b._cat_last[_k] -= 5
_said = [t for _w, t in _b.tts.said]
_who = [w for w, _t2 in _b.tts.said]
check("chequered" in _b.sting_bank.played,
      "the flag itself is called", str(_b.sting_bank.played))
check(len(_said) >= 4, "and a wrap follows it, not silence",
      "%d lines" % len(_said))
check(any("pole" in t.lower() or "heads the" in t.lower() for t in _said),
      "pole position is announced", str(_said[:1]))
check(cast_mod.ANALYST in _who,
      "the analyst gets his verdict in — two voices, not a monologue",
      str(_who))
check(any(_me.display_name in t for t in _said),
      "and the PLAYER is told where he ended up", str(_said))
check("outro" in _b.sting_bank.played, "then the programme signs off")

# THE ORDER COMES FROM THE TIMESHEET, NOT THE ROAD. In a timed session rF2's
# position field is as often the running order as the classification, so
# reading `s.order[0]` as the pole man announces pole for whoever happened to
# be in front when the flag fell.
_cars2 = grid()
for _i, _c in enumerate(_cars2):
    _c.best_lap = 95.0 - _i * 0.4      # LAST on the road is the quickest
_b2 = Booth()
_s2 = FakeSession(_cars2, kind="quali", max_laps=0, laps_left=0, leader_laps=6,
                  time_left=0.0, end_et=1200.0)
_s2.player = _cars2[0]
_run(_b2, _s2, ticks=4, step=3.0)
_b2.tts.said = []
_s2.finished = True
for _ in range(6):
    _b2.update_booth(_s2)
    _b2._last_spoke -= 5
_quickest = min(_cars2, key=lambda c: c.best_lap).display_name
_first = [t for _w, t in _b2.tts.said][:1]
check(bool(_first) and _quickest in _first[0],
      "pole goes to the QUICKEST man, not the one leading on the road",
      "%s / %r" % (_quickest, _first))

print("\n14. AND THE SESSION IS REMEMBERED ONCE IT ENDS")
# "Quali results must be remembered when a session finishes" — the engineer
# reads it back a session later ("last time out you put it fourth"), by which
# point there is nothing in shared memory to recover it from. Banking happens
# at the flag, in the same beat that calls it.
check(bool(_b._quali_story),
      "the session's story is kept for the race to look back on",
      "%d driver(s)" % len(_b._quali_story))
# Keyed by `story._key`, not by the display name — the same folded form the
# race uses to look a driver back up, because car ids do not survive a session
# change and the mod's spelling is not stable either.
import story as _story_mod
check(_story_mod._key(_me.display_name) in _b._quali_story,
      "including the player's own session", str(list(_b._quali_story)[:3]))

print("\n15. A QUALIFYING SESSION IS NOT A RACE")
# The user, driving it: the booth asked "That's proper racecraft, isn't it
# Chuck?" in a QUALIFYING session. ONE WORD in one `when` list let a topic about
# making a pass stick into a session where a driver is alone on the circuit
# looking for two tenths. Every suite was green at the time, because the leak is
# in the DATA — so only a sweep of the data finds it.
import json as _json
_ct = _json.load(open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lines_data", "crosstalk.json"),
    encoding="utf-8"))
RACE_WORDS = ("racecraft", "overtak", "make a pass", "pass stick", "this race",
              "two-stop", "pit stop", "hold on", "defend")
_bad = []
for _name, _t in _ct.items():
    if _name.startswith("_") or not isinstance(_t, dict):
        continue
    if "session" not in (_t.get("when") or []):
        continue
    _text = " ".join(list(_t.get("q") or []) + list(_t.get("a") or [])
                     + [str(x) for x in (_t.get("qa") or [])]).lower()
    _hit = [w for w in RACE_WORDS if w in _text]
    if _hit:
        _bad.append("%s: %s" % (_name, _hit))
check(not _bad, "no topic offered in qualifying talks about racing somebody",
      str(_bad))

print("\n16. THE PRE-SESSION SEQUENCE SURVIVES A BUSY TIMESHEET")
# THE BUG THE USER HAD TO REPORT TWICE. He started a new career and no rookie
# line ever aired in his first qualifying session — not because the line was
# refused, but because the WHOLE pre-session sequence was thrown away on the
# first tick. A quali session has a full timesheet immediately, those events
# outrank PRE_YIELD, and the code EMPTIED the queue rather than pausing it.
#
# Every suite was green. The pre-RACE path was tested; the pre-QUALI path in a
# session with live events was not, and that is the only place it happens.
import tempfile as _tf
import season as _S
from fakes import Booth as _Booth, run as _run
_S.CAREER_DIR = _tf.mkdtemp(prefix="factortv_prequali_")
_car = _S.create("open", me="Kandasamy", rounds=5,
                 ladder_path="road_to_indy", tier_index=0)
_pb = _Booth()
_pb.season = _car
_psess = FakeSession(grid(), kind="quali", green=False)
_psess.player.display_name = "Kandasamy"
_said = []
_orig_say = _pb._say


def _spy_say(cat, kw, sess, now, **k):
    ok = _orig_say(cat, kw, sess, now, **k)
    if ok:
        _said.append(cat)
    return ok


_pb._say = _spy_say
for _ in range(30):
    _pb._season_round = {"n": 1, "slug": "z", "event": ""}   # the game re-arms
    _run(_pb, _psess, ticks=1, step=4.0)
check("status_rookie" in _said,
      "a brand new career is introduced as a rookie in its first session",
      str(_said))
check("season_launch" in _said,
      "and the season still opens, with a busy sheet from the first tick")
check(not _pb._pre, "the sequence drains rather than dribbling out for ever")


print("\n17. PRACTICE IS THE ENGINEER'S SESSION")
# Asked for directly: "if it is a practice session then disable all commentary,
# lets just have the race engineer and driver, but for quali and race sessions
# then we must have commentary."
#
# NOBODY BROADCASTS A PRACTICE SESSION. No crowd, no result, no timing screen
# worth showing — a booth narrating one is the first thing in this product that
# does not happen in real life. What a driver has in a practice session is his
# engineer, and Dean already covers timed sessions, so the whole session becomes
# the pit wall by deleting a caller rather than by writing anything.
b = Booth()
sp = FakeSession(grid(), kind="practice", green=False,
                 started=False)
for _i in range(40):
    b.update_booth(sp)
check(not b.tts.said, "the booth says nothing at all in a practice session",
      str([t[1][:40] for t in b.tts.said][:3]))
check(not b.sting_bank.played,
      "and no sting plays either — not even the intro",
      str(b.sting_bank.played))

# ...AND THE TWO SESSIONS THAT ARE BROADCAST ARE UNTOUCHED.
b2 = Booth()
sq = FakeSession(grid(), kind="quali")
for _i in range(40):
    b2.update_booth(sq)
check(bool(b2.tts.said),
      "qualifying still has a booth", str(len(b2.tts.said)))

# THE GATE IS ON THE SESSION KIND, checked before anything can speak — asserted
# against the SOURCE, because a shim that reaches the speaking path has already
# passed the thing under test (LAW 0).
import inspect as _inspect
import overlay_booth as _ob
_src = _inspect.getsource(_ob.BoothMixin.update_booth)
check("BOOTH_SILENT" in _src.split("on_air")[0],
      "and it is checked above the on-air gate, not somewhere downstream")
check("practice" in _ob.BOOTH_SILENT and "test" in _ob.BOOTH_SILENT,
      "practice and the no-session state are what it covers",
      str(_ob.BOOTH_SILENT))
check("quali" not in _ob.BOOTH_SILENT and "race" not in _ob.BOOTH_SILENT,
      "and the broadcast sessions are not")


print("\n18. DOES THIS ROUND COUNT — DECIDED IN THE MENU, NOT IN A WINDOW")
# The in-session card is GONE. It failed four times in four different ways —
# matched under the on-air gate, armed before the data arrived, never reached by
# the frame, and finally refused because rF2 publishes a game phase outside 0..8
# in the pit screen, which `started` read as "the race has begun". Every one was a
# symptom of the same fault: THE DECISION WAS BEING ASKED FOR IN A WINDOW THE GAME
# CONTROLS, out of data the game publishes when it feels like it.
#
# The user's call: *"let the player have control and make it a choice that needs
# clicking before a round ... to switch it off it must be done by either turning
# that off or closing the career."*
import shutil as _sh3, tempfile as _tf3
import season as _S3

_d3 = _tf3.mkdtemp(prefix="factortv_count_")
_old3 = _S3.CAREER_DIR
_S3.CAREER_DIR = _d3


class _C3:
    slug = "zandvoort"
    key = "zandvoort"
    name = "Zandvoort"
    known = True


try:
    car = _S3.create("open", me="Kandasamy", rounds=5)
    check(car.round_counts(1),
          "a round counts by default — a race that quietly failed to count "
          "cannot be recovered")
    check(car.set_round_counts(1, False) is False and not car.round_counts(1),
          "switching it off is one call")
    check(car.round_counts(2),
          "and it is PER ROUND, so the next one is unaffected")
    check(car.data.get("rounds_off") == [1],
          "only the exceptions are stored, so an old career file needs no "
          "migration", str(car.data.get("rounds_off")))
    _re = _S3.load(car.slug)
    check(_re is not None and not _re.round_counts(1),
          "and it SURVIVES a reload — the whole reason it is not session state")

    # A SWITCHED-OFF ROUND IS OFF-CAREER, not merely unrecorded. His own framing:
    # "if I want to do a random race I just switch it off and the commentary
    # system and race engineer will know". A booth calling it "round two of the
    # Formula 4 season" while nothing records contradicts the standings screen.
    b = Booth()
    b.season = car
    b.career = None
    sess = FakeSession(grid(), kind="race")
    sess.circuit = _C3()
    sess.on_air = False
    sess.started = False
    sess.green = False
    b.update_booth(sess)
    check(b._season_armed and b._season_round is None,
          "with the round switched off, the session is not a round at all",
          str(b._season_round))
    check(not b._season_count, "so nothing will be recorded")

    car.set_round_counts(1, True)
    b2 = Booth()
    b2.season = car
    b2.career = None
    s2 = FakeSession(grid(), kind="race")
    s2.circuit = _C3()
    s2.on_air = False
    s2.started = False
    s2.green = False
    b2.update_booth(s2)
    check(b2._season_round is not None and b2._season_count,
          "switched back on, it is round one again and it will be recorded",
          str(b2._season_round))

    # AN UNRECOGNISED GAME PHASE CANNOT BREAK IT ANY MORE, which is the point of
    # moving the decision out of the session: rF2 may publish what it likes.
    b3 = Booth()
    b3.season = car
    b3.career = None
    s3 = FakeSession(grid(), kind="race")
    s3.circuit = _C3()
    s3.on_air = False
    s3.started = True
    s3.green = False
    s3.phase_name = "?9"
    b3.update_booth(s3)
    check(b3._season_round is not None,
          "a phase nobody recognises no longer decides anything")
finally:
    _S3.CAREER_DIR = _old3
    _sh3.rmtree(_d3, ignore_errors=True)


print("\n19. SATURDAY IS BANKED EVEN THOUGH THE BOOTH HAS GONE OFF AIR")
# From the 18:26 log: he qualified P13 at Montreal and `quali_results` in the
# save was EMPTY. `_quali_bank` refuses to act until `s.finished`, which is only
# true at game phase OVER — the same moment rF2 drops `mInRealtime` and `on_air`
# goes false, so `update_booth` returned above the call every time. The third
# time something needed at the END of a session was found under a gate that
# closes at the end of the session.
_qc = _S3.create("open", me="Kandasamy", rounds=4)
_qc.data["quali"] = True
_qc.save()
qb = Booth()
qb.season = _qc
qb.career = None
qs = FakeSession(grid(), kind="quali")
qs.circuit = _C3()
qs.on_air = False            # the booth is off air, as it is at phase OVER
qs.finished = True           # ...which is exactly when the session is over
qs.started = True
qs.green = False
me = qs.player
for j, c in enumerate(qs.order):
    c.best_lap = 90.0 + j     # a real sheet, with him last of those who ran
qb.update_booth(qs)
banked = _qc.data.get("quali_results") or []
check(banked, "the qualifying position is stored with the booth off air",
      str(banked))
if banked:
    check(banked[0].get("pos") == 1 + [c.id for c in sorted(
        qs.order, key=lambda c: c.best_lap)].index(me.id),
        "and it is where he actually finished on the sheet", str(banked[0]))
    check(banked[0].get("n") == 1, "against the round the career is on",
          str(banked[0].get("n")))
# ...AND ONCE ONLY, however many ticks arrive after the flag.
qb.update_booth(qs)
qb.update_booth(qs)
check(len(_qc.data.get("quali_results") or []) == 1,
      "once, not once per tick",
      str(len(_qc.data.get("quali_results") or [])))

print("\n20. ONE RACE IS ONE ROUND, WHATEVER HAPPENS AFTER THE FLAG")
# He drove ONE Formula 3 race and his career recorded TWO rounds and twelve
# points. His words: "I never raced 2 F3 rounds? I only did round 1 then was
# promoted on the second round so i never got to even race a second f3 race" —
# and the phantom round is what promoted him, because `callup_due` counted it.
#
#   [2100.9s] RESULT  settled P6  status=1 laps=7   <- the race he drove
#   [2342.1s] SESSION  | test | phase=garage | 0 cars
#             RESULT  settled P10 status=1 laps=6   <- nobody's race
#
# The pending settle exists to correct a result while his own race finishes. It
# was not bound to the round it was created for, so once round one was banked and
# re-arming matched the next UNRACED round, the leftover write landed on round
# two.
_1c = _S3.create("open", me="Kandasamy", rounds=5)
_1b = Booth()
_1b.season = _1c
_1b.career = None
_1s = FakeSession(grid(), kind="race")
_1s.circuit = _C3()
_1s.on_air = True
_1s.started = True
_1s.green = True
_1b.update_booth(_1s)
check(_1b._season_round is not None and _1b._season_count,
      "the session arms as round one", str(_1b._season_round))
# He crosses the line with his own race unfinished, so a settle is pending.
_me = _1s.player
_me.place = 6
_me.finish_status = 0
_1s.finished = True
_1s.green = False
_1b.update_booth(_1s)
check(len(_1c.rounds) == 1, "one race banks one round", str(len(_1c.rounds)))
check(getattr(_1b, "_season_settle", None),
      "with a correction still pending, because his race is not over")
# NOW THE SESSION GOES AWAY — he leaves the race. Re-arming would match round
# TWO, since round one is taken, and the pending write must not follow it there.
_1b._season_round = {"n": 2, "slug": "montreal"}
_1s2 = FakeSession(grid(), kind="race")
_1s2.circuit = _C3()
_1s2.order = []
_1s2.player = None
_1s2.on_air = False
_1s2.started = False
_1s2.finished = False
_1b.update_booth(_1s2)
check(len(_1c.rounds) == 1,
      "and an empty session banks nothing at all", str(len(_1c.rounds)))
check(not getattr(_1b, "_season_settle", None),
      "the pending write is dropped rather than redirected")
check([r.get("n") for r in _1c.rounds] == [1],
      "so the career holds round one and nothing else",
      str([r.get("n") for r in _1c.rounds]))

print("\n21. A RETIREMENT IS A RESULT, AND IT IS BANKED WHEN HIS RACE ENDS")
# A play tester "ran out of feul at the redbull ring kart race doing round 2 but
# the the race result never recorded or anyhting". The only place a race result
# was ever written is the WINNER'S flag — `s.finished`, game phase OVER — and a
# driver stopped on track who then leaves the session, which is the only thing
# there is to do when the car will not move, never reaches it. The championship
# simply had no round two.
_rc = _S3.create("open", me="Kandasamy", rounds=5)
_rb = Booth()
_rb.season = _rc
_rb.career = None
_rs = FakeSession(grid(), kind="race")
_rs.circuit = _C3()
_rs.on_air = True
_rs.started = True
_rs.green = True
_rb.update_booth(_rs)
check(_rb._season_count and _rb._season_round,
      "the round arms", str(_rb._season_round))
# HE RUNS OUT OF FUEL. The race is still running — the leader has not finished,
# so `s.finished` is false and always will be as far as he is concerned.
# HIS PLACE IS WHATEVER THE FIELD ALREADY GIVES HIM. Setting it by hand made two
# cars ninth and nobody first, and the code correctly refuses to renumber a field
# whose places are not a clean 1..N — so the fixture, not the product, was what
# broke the first version of this check.
_me = _rs.player
_road = _me.place
_me.laps = 4
_me.finish_status = 2            # rF2: 2 and 3 are the retirements
_rb.update_booth(_rs)
check(len(_rc.rounds) == 1,
      "his retirement is banked while the race is still going",
      str(len(_rc.rounds)))
if _rc.rounds:
    _r = _rc.rounds[0]
    check(_r.get("dnf"), "recorded as a retirement", str(_r.get("dnf")))
    # BEHIND EVERY CAR STILL RUNNING, not where he was on the road. He stopped
    # ninth of twelve; the eleven cars still circulating are all going to finish
    # ahead of him, so banking ninth would hand him a flattering result AND the
    # points for it if he then leaves. This is the P4-for-a-tenth-place error in
    # a new place, and the first version of this fix reintroduced it.
    check(_r.get("pos") == _r.get("field"),
          "classified behind everyone still running",
          "P%s banked, P%s on the road, %s in the field"
          % (_r.get("pos"), _road, _r.get("field")))
    # THE CLASSIFICATION AGREES WITH THE POSITION. The fake field names the
    # player's car whatever the harness names it, so look him up by the position
    # rather than by a name this test does not own.
    _cl = dict(_r.get("classified") or ())
    check(sorted(_cl.values()) == list(range(1, len(_cl) + 1)),
          "and the classification is a clean 1..N with no repeats",
          str(sorted(_cl.values())))
    check(len([p for p in _cl.values() if p == len(_cl)]) == 1,
          "with last place given out exactly once",
          str([n for n, p in _cl.items() if p == len(_cl)]))
    check(_r.get("laps") == 4, "on the lap he actually reached",
          str(_r.get("laps")))
# NO RESULT SHEET YET, because the figure may still be corrected by the flag and
# a letter is frozen when it is sent.
import inbox as _ibx2
check(not [m for m in _ibx2.messages(_rc) if m["kind"].startswith("result")],
      "with no result letter sent on a provisional figure")
# AND ONCE, however long he sits there.
_rb.update_booth(_rs)
_rb.update_booth(_rs)
check(len(_rc.rounds) == 1, "banked once, not once per tick",
      str(len(_rc.rounds)))
# HE LEAVES. The round survives, which is the whole point.
_rs2 = FakeSession(grid(), kind="race")
_rs2.circuit = _C3()
_rs2.order = []
_rs2.player = None
_rs2.on_air = False
_rs2.started = False
_rb.update_booth(_rs2)
check([r.get("n") for r in _rc.rounds] == [1],
      "and leaving the session cannot lose it",
      str([r.get("n") for r in _rc.rounds]))
# A DRIVER WHOSE RACE IS STILL RUNNING BANKS NOTHING, which is the other half:
# this must not turn every green-flag lap into a result.
_gc = _S3.create("open", me="Kandasamy", rounds=5)
_gb = Booth()
_gb.season = _gc
_gb.career = None
_gs = FakeSession(grid(), kind="race")
_gs.circuit = _C3()
_gs.on_air = True
_gs.started = True
_gs.green = True
_gs.player.finish_status = 0
_gb.update_booth(_gs)
_gb.update_booth(_gs)
check(not _gc.rounds, "a race in progress records nothing at all",
      str(len(_gc.rounds)))

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
