"""Race FLOW test: the shape of a broadcast over different race lengths.

`boothtest.py` checks that the right event produces the right call. This
checks the things that only go wrong over TIME:

  * the pre-race running order (welcome, circuit, grid, format) survives
    being entered late and being cut off by the green flag
  * phases scale — a 5-lap dash, a 17-lap sprint, a 60-lap race and a timed
    race must all get an opening, a middle and a run-in in proportion
  * the booth actually talks to itself during dead air, and finishes what it
    started

    python tests/flowtest.py
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lines as lines_mod, cast as cast_mod
from fakes import FakeSession, Booth, grid, run, texts

fails = []
def check(cond, label, extra=""):
    print(("  [ OK ] " if cond else "  [FAIL] ") + label + (("  " + extra) if extra else ""))
    if not cond:
        fails.append(label)

print("\n1. THE PRE-RACE RUNNING ORDER")
b = Booth()
s = FakeSession(grid(), green=False, started=False, leader_laps=0,
                phase_name="gridwalk")
run(b, s, ticks=12)
said = texts(b)
check(b.sting_bank.played[:1] == ["intro"], "the show opens with the intro",
      str(b.sting_bank.played))
# The intro is a pre-rendered sting rather than a spoken line, so the count
# has to include both halves of what the booth actually put to air.
aired = len(said) + len(b.sting_bank.played)
check(aired >= 3, "the running order gets through several stages",
      "%d aired: %r" % (aired, said[:2]))
check("lightsout" not in b.sting_bank.played,
      "and none of it is the start call")

print("\n2. DROPPING IN AT THE GREEN (the reported bug)")
# Entering a session already at COUNTDOWN leaves no room for a running order.
# The welcome must still happen — it becomes the same beat as the start.
b = Booth()
s = FakeSession(grid(), leader_laps=0)
run(b, s, ticks=6)
check("intro" in b.sting_bank.played,
      "the show still opens even though green came immediately",
      str(b.sting_bank.played))
check("lightsout" in b.sting_bank.played, "and the start is still called")
check(b.sting_bank.played.index("intro")
      < b.sting_bank.played.index("lightsout"),
      "welcome first, lights out second")

print("\n3. PHASES SCALE WITH RACE LENGTH")
def phases(max_laps, pace=92.0):
    b = Booth()
    out = []
    for done in range(0, max_laps + 1):
        s = FakeSession(grid(), max_laps=max_laps, leader_laps=done,
                        laps_left=max_laps - done, best_lap_time=pace)
        b._length = b._length_class(s)
        b._phase = b._race_phase(s)
        out.append(b._phase)
    return out

for laps in (5, 17, 40, 60):
    p = phases(laps)
    shape = [p.count(x) for x in ("opening", "mid", "late", "closing")]
    check(all(n > 0 for n in shape[:3]),
          "a %d-lap race has an opening, a middle and a run-in" % laps,
          "open=%d mid=%d late=%d close=%d" % tuple(shape))
    check(shape[1] >= shape[2],
          "and the middle is the biggest part of it" % (),
          "mid=%d late=%d" % (shape[1], shape[2]))

p5, p60 = phases(5), phases(60)
check(p5.count("opening") == 1,
      "a five-lap dash gets one opening lap, not two")
check(phases(60).count("opening") == 2,
      "an hour-long race gets a settling lap as well")
check(p60.count("late") <= 8,
      "and it does not spend its last quarter in run-in mode",
      "late=%d" % p60.count("late"))

print("\n4. A TIMED RACE PHASES ON THE CLOCK")
b = Booth()
def timed_phase(rem, dur=1800.0):
    s = FakeSession(grid(), max_laps=0, laps_left=0, leader_laps=6,
                    time_left=rem, end_et=dur)
    return b._race_phase(s)
check(timed_phase(1500) == "mid", "half an hour in, we're mid-race")
check(timed_phase(200) == "late", "the final fifth is the run-in")
check(timed_phase(30) == "closing", "the last minute is the finish")
check(timed_phase(0) == "closing", "and time expired is the finish")

print("\n5. RACE LENGTH IS RECOGNISED")
b = Booth()
check(b._length_class(FakeSession(grid(), max_laps=5)) == "sprint",
      "5 laps is a sprint")
check(b._length_class(FakeSession(grid(), max_laps=17)) == "normal",
      "17 laps is a normal race")
check(b._length_class(FakeSession(grid(), max_laps=40)) == "long",
      "40 laps is a long race")
check(b._length_class(FakeSession(grid(), max_laps=0, end_et=7200.0))
      == "endurance", "two hours is an endurance run")

print("\n6. THE MIDDLE OF A LONG RACE IS NOT SIX SENTENCES")
b = Booth()
cars = grid()
for c in cars:
    c.gap_ahead = 4.0
    c.gap_leader = 4.0 * (c.place - 1)
s = FakeSession(cars, max_laps=60, leader_laps=20, laps_left=40)
b.update_booth(s)
b.tts.said = []
cats = set()
for lap in range(20, 45):
    s = FakeSession(cars, max_laps=60, leader_laps=lap, laps_left=60 - lap)
    for _ in range(12):
        run(b, s, ticks=1, step=4.0)
    cats |= set(b._cat_last)
uniq = len(set(texts(b)))
check(len(cats) >= 6, "the booth reaches for several kinds of filler",
      "%d categories: %s" % (len(cats), ", ".join(sorted(cats))[:110]))
check(uniq >= 12, "and does not repeat itself across 25 laps",
      "%d unique lines" % uniq)

print("\n7. THE BOOTH TALKS TO ITSELF")
b = Booth()
s = FakeSession(grid(), max_laps=60, leader_laps=20, laps_left=40)
b._phase = "mid"
ok = b._start_convo(s, time.time())
check(ok, "Miles asks Chuck a question", repr(texts(b)[:1]))
if ok:
    check(b.tts.said[0][0] == cast_mod.PLAY, "the question is play-by-play")
    asked, kw = b._convo["topic"], b._convo["kw"]
    # The answer is queued in the SAME breath as the question. `speak()` only
    # enqueues, and a live render takes seconds — queueing the answer only
    # after the question finished playing is what made the two of them sound
    # like they were in different rooms.
    check(len(b.tts.said) == 2,
          "and the answer is queued with it, not after it",
          "%d queued" % len(b.tts.said))
    check(b.tts.said[-1][0] == cast_mod.ANALYST, "the answer is his",
          repr(texts(b)[-1:]))
    # The answer must belong to THIS question. That binding is the entire
    # point of the topic model — a pool of shared answers is what the booth
    # already had, and it is why Chuck used to reply to a question about
    # tyres with an observation about the weather.
    #
    # Answers carry slots, so the comparison is against the FORMATTED
    # candidates for the topic that was actually asked.
    from overlay_common import safe_format
    topic = lines_mod.topics()["topics"][asked]
    # A topic either shares one answer pool or binds answers to each
    # question. Both are legal; the answer must come from whichever this
    # topic uses.
    if topic.get("qa"):
        src = [a for pair in topic["qa"] for a in pair.get("a", [])]
    else:
        src = topic.get("a", [])
    own = [safe_format(x if isinstance(x, str) else x.get("t", ""), kw)
           for x in src]
    check(texts(b)[-1] in own,
          "the answer comes from the topic's own answers", asked)

print("\n8. NEWS INTERRUPTS THE CONVERSATION")
b = Booth()
# Get the show open first: the pre-race running order legitimately owns the
# early ticks, and it would consume the one this test cares about.
run(b, FakeSession(grid()), ticks=8, step=3.0)
b.update_booth(FakeSession(grid()))          # baseline for the delta
b._convo = {"topic": "tyres", "stage": "a", "kw": {}, "at": time.time()}
b._last_spoke = 0.0
b.update_booth(FakeSession(grid([1, 0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])))
check(b._convo is None, "a lead change abandons the exchange mid-topic")

print("\n9. THE WRAP IS A SEQUENCE TOO")
b = Booth()
run(b, FakeSession(grid()), ticks=8, step=3.0)
fin = FakeSession(grid(), finished=True, green=False, leader_laps=17,
                  laps_left=0)
for _ in range(10):
    b.update_booth(fin)
    b._last_spoke -= 6.0
cats = [c for c in ("podium_final", "race_verdict", "signoff")
        if c in b._cat_last]
check(any(c == "win" or c.startswith("win_") for c in b._cat_last),
      "the winner is called")
check(len(cats) >= 2, "the podium and a verdict follow the flag",
      ", ".join(cats))
check(b._signed_off and "outro" in b.sting_bank.played,
      "and the programme signs off at the end of it",
      str(b.sting_bank.played))
check(b.sting_bank.played.index("victory")
      < b.sting_bank.played.index("outro"),
      "in that order — win first, goodbye last")

print("\n10. INCIDENTS ESCALATE INSTEAD OF REPEATING")

def spun(b, which, base=None, speed=20.0):
    """Drop one car's speed hard enough to read as an incident."""
    cars = base or grid()
    for c in cars:
        c.speed = 200.0
    cars[which].speed = speed
    s = FakeSession(cars)
    b.update_booth(s)
    return cars

b = Booth()
run(b, FakeSession(grid()), ticks=8, step=3.0)     # get the show open
b.update_booth(FakeSession(grid()))                # baseline
b._last_spoke = 0.0
b._cat_last.clear()
spun(b, 3)
# The FIRST incident is now a three-beat sequence — sting, the pundit naming
# the driver, the play-by-play seat answering — because the old single line
# was reliably silenced by its own sting (see offtracktest §13b). What the
# escalation below cares about is unchanged: a second and third incident
# inside the window must not be told in the same words as the first.
first = [c for c in b._cat_last
         if c in ("spin", "offtrack", "incident_id_off", "incident_id_spin")]
check(bool(first), "the first incident is called plainly", str(first))

b._last_spoke = 0.0
b.update_booth(FakeSession(grid()))
b._last_spoke = 0.0
spun(b, 4)
check("offtrack_more" in b._cat_last,
      "the second inside the window is 'and another'")

b._last_spoke = 0.0
b.update_booth(FakeSession(grid()))
b._last_spoke = 0.0
spun(b, 5)
check("offtrack_chaos" in b._cat_last, "the third is chaos")

print("\n11. AN INCIDENT CUTS THE BOOTH OFF MID-SENTENCE")
b = Booth()
run(b, FakeSession(grid()), ticks=8, step=3.0)
b.update_booth(FakeSession(grid()))
b._convo = {"topic": "tyres", "stage": "a", "kw": {}, "at": time.time()}
b._last_spoke = 0.0
b._cat_last.clear()
spun(b, 3)
# The apology survived the redesign, in the other direction: the PUNDIT is
# the one cutting in now, so he is the one who says sorry — and he names the
# driver in the same breath, which is what the sting owes the viewer.
check("incident_cut_id" in b._cat_last or "offtrack_cut" in b._cat_last,
      "the booth apologises for interrupting itself",
      repr(texts(b)[-2:]))
check(b._convo is None, "and the exchange is abandoned")

print("\n12. A NAMELESS ALERT GETS ITS NAME EVENTUALLY")
b = Booth()
run(b, FakeSession(grid()), ticks=8, step=3.0)
b.update_booth(FakeSession(grid()))
now = time.time()
b._sting_at = now - 10.0        # the alert fired, nothing named the driver
b._named_incident = False
b._last_spoke = 0.0
b._cat_last.clear()
cars = grid()
cars[6].speed = 40.0
late = [e for e in b._filler(FakeSession(cars), now) if e[0] == "offtrack_late"]
check(bool(late), "the booth comes back and identifies the driver",
      str(late[0][1].get("drv") if late else None))
check(b._named_incident, "and considers the debt paid")

print("\n13. A LONG FIGHT IS ITS OWN STORY")
b = Booth()
run(b, FakeSession(grid()), ticks=8, step=3.0)
now = time.time()
cars = grid()
cars[1].gap_ahead = 0.4
s = FakeSession(cars)
# A fight is (since, opponent-id): the opponent is part of the record, so a
# duration can never be carried over onto a different pair of cars.
b._battle_since[cars[1].id] = (now - 90.0, cars[0].id)
b._last_spoke = 0.0
b._cat_last.clear()
cands = [e for e in b._filler(s, now)]
check(any(c[0] == "battle_sustained" for c in cands),
      "a fight that has lasted gets its own call",
      ", ".join(c[0] for c in cands[:4]))
check(not any(c[0] == "battle" for c in cands),
      "and is not also reported as a fresh battle")

# ...and the pass that ends it is a breakthrough, not a routine move.
b = Booth()
run(b, FakeSession(grid()), ticks=8, step=3.0)
b.update_booth(FakeSession(grid()))
# Leclerc is car 3, and he is the one about to come through into second.
b._battle_since[3] = (time.time() - 90.0, 2)   # he has been trying for ages
b._last_spoke = 0.0
b._cat_last.clear()
b.update_booth(FakeSession(grid([0, 2, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11])))
check("overtake_long" in b._cat_last,
      "the move that ends it is called as a breakthrough",
      repr(texts(b)[-1:]))

print("\n14. QUALIFYING IS A DIFFERENT PROGRAMME")

def qsess(cars, **kw):
    kw.setdefault("kind", "quali")
    kw.setdefault("max_laps", 0)
    kw.setdefault("time_left", 900.0)
    kw.setdefault("end_et", 900.0)
    return FakeSession(cars, **kw)

# The bug: in a timed session, "position" IS timesheet order, so an improved
# lap re-orders the field. Race detection read that as overtaking.
b = Booth()
cars = grid()
for c in cars:
    c.best_lap = 92.0 + c.place
b.update_booth(qsess(cars))
b._last_spoke = 0.0
b._cat_last.clear()
b.tts.said = []
# Leclerc finds two seconds and jumps two places on the sheet.
moved = grid([0, 2, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11])
for c in moved:
    c.best_lap = 92.0 + c.place
b.update_booth(qsess(moved))
check(not any(c in b._cat_last for c in ("overtake", "leadchange", "retake",
                                         "overtake_long")),
      "a timesheet move is NOT called as an overtake",
      ", ".join(sorted(b._cat_last)))

# Provisional pole, and then the same man improving his own time. The
# session starts with an empty timesheet, which is the state that makes the
# first flying lap pole in the first place.
b = Booth()
cars = grid()
for c in cars:
    c.best_lap = None
b.update_booth(qsess(cars))
b._last_spoke = 0.0
cars[0].best_lap = 91.0
b.update_booth(qsess(cars))
check("quali_pole" in b._cat_last, "the first time set is provisional pole",
      ", ".join(sorted(b._cat_last)))
b._last_spoke = 0.0
b._cat_last.pop("quali_fastlap", None)
cars[0].best_lap = 90.5
b.update_booth(qsess(cars))
check("quali_fastlap" in b._cat_last,
      "the same man going quicker is not a change at the top")
b._last_spoke = 0.0
cars[1].best_lap = 90.0
b.update_booth(qsess(cars))
check(b._q_pole == cars[1].id, "and a new man on top takes the pole call")

# An empty session has something honest to say about being empty.
b = Booth()
empty = grid()
for c in empty:
    c.best_lap = None
    c.in_pits = True
cands = [e[0] for e in b._quali_filler(qsess(empty), time.time())]
check("quali_nobody" in cands, "no times on the board is itself the story",
      ", ".join(cands[:5]))
one = grid()
for c in one:
    c.best_lap = None
one[0].best_lap = 93.0
cands = [e[0] for e in b._quali_filler(qsess(one), time.time())]
check("quali_onlyone" in cands, "one time on the board is a different line")
solo = [grid()[0]]
cands = [e[0] for e in b._quali_filler(qsess(solo), time.time())]
check("quali_solo" in cands, "and a one-car session is not a field at all")

# Race questions must not be asked when there is no race on.
b = Booth()
b._phase = "session"
import lines as _lm
name, topic = _lm.topic_for(qsess(grid()).era, "session")
check(topic is not None, "the booth still has something to talk about", str(name))
check(name not in ("prediction", "hold_on", "nerves", "standout"),
      "but not 'who wins this?' in free practice", str(name))

print("\n14b. A FIGHT TIMER NEVER OUTLIVES THE FIGHT")
# From the 2026-08-16 live run: "Nose to tail for 8 laps, these two" about a
# pair eight seconds apart. The reporting loop breaks at the first fight
# worth calling, and the clearing branch lived inside that loop — so every
# car behind it kept a timer nothing ever reset.
b = Booth()
now = time.time()
cars = grid()
for c in cars:
    c.gap_ahead = 4.0
cars[1].gap_ahead = 0.3        # a fight at the front, reported every tick
cars[6].gap_ahead = 0.3        # ...and one further back, never reached
s = FakeSession(cars)
b.update_booth(s)
for i in range(30):
    b._update_battles(s, now + i * 3.0)
check(len(b._battle_since) >= 2, "both fights are timed, not just the reported one",
      str(sorted(b._battle_since)))
cars[6].gap_ahead = 9.0        # the second pair separate
b._update_battles(s, now + 95.0)
check(cars[6].id not in b._battle_since,
      "a fight that ended leaves no timer behind")
cars[6].gap_ahead = 0.3        # and a fresh scrap starts from zero
b._update_battles(s, now + 98.0)
held = b._battle_held(cars[6], s.car_ahead(cars[6]), now + 99.0)
check(held < 5.0, "a new fight does not inherit the old one's duration",
      "%.0fs" % held)

# The opponent is part of the record: same car, different man in front.
b._battle_since[cars[3].id] = (now - 90.0, 999)
held = b._battle_held(cars[3], s.car_ahead(cars[3]), now)
check(held == 0.0, "and a duration never transfers to a different opponent",
      "%.0fs" % held)

print("\n14bb. A SCRAMBLED TICK TEACHES THE ARC NOTHING")
# From the 16:07 live run: "that's 30 places clawed back by Alain Prost" in a
# 31-car race, about a man who led from the front. For a tick or two around a
# standing start rF2 reports an order that never actually existed, and since
# `worst` only ever grows, one such tick is permanent.
b = Booth()
cars = grid()
s = FakeSession(cars)
b.update_booth(s)
before = dict(b._story.get(cars[0].id) or {})
cars[0].place = len(cars)          # the leader, briefly scored last
check(not b._places_sane(s), "a scrambled classification is recognised")
b._track_story(s)
after = b._story.get(cars[0].id) or {}
check(after.get("worst") == before.get("worst"),
      "and the arc does not learn from it",
      "worst %s -> %s" % (before.get("worst"), after.get("worst")))
cars[0].place = 1
b._track_story(s)
check((b._story.get(cars[0].id) or {}).get("worst") == before.get("worst"),
      "a sane tick still updates it normally")

print("\n14c. THE LEADER IS NOT AN UNNOTICED MIDFIELD RECOVERY")
# Also from the live run: "Nobody's mentioned Ayrton Senna, and he's climbed
# to the lead" — about the one driver the booth had discussed all afternoon.
b = Booth()
cars = grid()
s = FakeSession(cars)
b.update_booth(s)
b._story[cars[0].id] = {"best": 1, "worst": 31, "now": 1}
check(b._best_mover(s) is not cars[0],
      "a charge to the lead is not filed as a midfield story")
b._story[cars[9].id] = {"best": 10, "worst": 26, "now": 10}
check(b._best_mover(s) is cars[9],
      "but a genuine midfield recovery still is",
      getattr(b._best_mover(s), "display_name", None))

print("\n15. NO LINE AIRS WITH AN EMPTY SLOT")
# From the 2026-08-16 test run: "Top of the sheets, and it's Derek Warwick
# by !" — the first driver to set a time takes provisional pole with no
# margin over anybody, so {gap} was empty. A slot that CAN be empty must not
# appear in a template.
pool = _lm.pool("quali_pole")
bad = [e["t"] for e in pool if "{gap}" in e.get("t", "")]
check(not bad, "quali_pole never quotes a margin it may not have", str(bad))

# And the real path: first time of the session, no previous benchmark.
b = Booth()
cars = grid()
for c in cars:
    c.best_lap = None
qs = qsess(cars)
b.update_booth(qs)
cars[0].best_lap = 91.0
ev = b._quali_detect(qsess(cars), time.time())
for cat, kw, _ in ev:
    text, _, _ = _lm.pick(cat, qs.era, kw)
    if text:
        check(" !" not in text and "  " not in text and " ." not in text,
              "the first pole of a session reads cleanly", repr(text))

print("\n16. THE PLAY-BY-PLAY SEAT IS CAST BY ERA")
import era as era_mod
import cast as _cast

def seat(cls):
    e = era_mod.classify(cls, "Ayrton Senna")
    _cast.set_era(e)
    return e, _cast.name_of(_cast.PLAY), _cast.voice_for(_cast.PLAY)["voice"]

e, name, voice = seat("F1 1988 Historic Edition")
check(name == "Brett Calloway", "a 1988 field is called by Brett", name)
check(voice == "en-AU-WilliamNeural", "in his own voice", voice)
check(_cast.is_historic(), "and the session is flagged historic")

e, name, voice = seat("F1 Test 2025")
check(name == "Miles Crawford", "a modern field is called by Miles", name)
check(voice == "en-GB-RyanNeural", "in his", voice)
check(not _cast.is_historic(), "and is not flagged historic")

# The seat must not change what either man is ALLOWED to say, or every
# persona rule in the product would need a second copy.
_cast.set_era(era_mod.classify("F1 1988 Historic Edition", "x"))
check(_cast.can_say(_cast.PLAY, "overtake")
      and not _cast.can_say(_cast.PLAY, "analysis"),
      "the seat's rules are the same whoever is in it")
check(_cast.who_says("overtake") == _cast.PLAY,
      "and the director still just asks for PLAY")

print("\n17. THE ARCHIVE IS NEVER CLAIMED AS LIVE, OR AS MEMORY")
hist = era_mod.classify("F1 1988 Historic Edition", "x")
modern = era_mod.classify("F1 Test 2025", "x")
for cat in ("archive_open", "archive_era", "archive_watch",
            "broadcast_archive"):
    check(bool(_lm.pick(cat, hist, {"trk": "Silverstone"})[0]),
          "%s has lines for a historic field" % cat)
    check(_lm.pick(cat, modern, {"trk": "Monza"})[0] is None,
          "...and none for a modern one", cat)

# Neither commentator was there, and neither knows the result. These are the
# two claims that would wreck the framing, so they are asserted against the
# prose directly — the one place where checking words is the right test.
banned = ("i remember", "i was there", "we all know", "as we know",
          "went on to win", "back in 19", "that season", "famously")
bad = []
for cat in ("archive_open", "archive_era", "archive_watch",
            "broadcast_archive"):
    for e in _lm.pool(cat):
        low = e.get("t", "").lower()
        for phrase in banned:
            if phrase in low:
                bad.append((cat, phrase))
check(not bad, "no line claims to have been there or to know the ending",
      str(bad[:3]))

print(chr(10) + "18. THE BOOTH ONLY DISCUSSES WHAT THE RACE SUPPORTS")
# "Who's impressed you so far?" three laps in is a question about nothing.
# Topics that ASSESS the race wait for one; topics about the circuit, the
# cars or the weather are true from lap one.
topics = _lm.topics()["topics"]
gated = {k for k, v in topics.items() if v.get("needs_race")}
check(bool(gated), "some topics are gated behind a race happening",
      ", ".join(sorted(gated)))
leaked = set()
for ph in ("opening", "mid", "late", "closing", "session"):
    for _ in range(60):
        n, _t = _lm.topic_for(hist, ph, race_ready=False)
        if n in gated:
            leaked.add(n)
check(not leaked, "and none of them is offered before then", str(leaked))
check(_lm.topic_for(hist, "mid", race_ready=False)[0] is not None,
      "but the booth still has something to talk about early")

# The booth applies that gate for races and ignores it elsewhere: a practice
# session has no arc to be too early in.
b = Booth()
b._phase = "mid"
early = FakeSession(grid(), leader_laps=1, laps_left=16)
check(not b._enough_race(early), "lap one is not enough race")
late = FakeSession(grid(), leader_laps=9, laps_left=8)
check(b._enough_race(late), "half distance is")

print(chr(10) + "19. A POLE LAP IS ONLY PRAISED WHEN IT MEANS SOMETHING")
b = Booth()
# First time of the session: he has beaten nobody, and somebody will beat him
# in ten minutes. Nothing to say about it.
s_early = qsess(grid(), time_left=900.0, end_et=900.0)
check(not b._quali_lap_notable(s_early, 1, None),
      "the first time on the board is not a great lap")
check(not b._quali_lap_notable(s_early, 2, 0.05),
      "nor is a small improvement early on")
# Late in the session, the benchmark is likely to be the one that stands.
s_late = qsess(grid(), time_left=100.0, end_et=900.0)
check(b._quali_lap_notable(s_late, 4, 0.1),
      "a lap in the closing stages is worth discussing")
# Or when most of the field has run and there is a real order to head.
check(b._quali_lap_notable(s_early, len(grid()), 0.1),
      "so is one that heads a field which has all run")
# Or when it is simply an enormous lap.
check(b._quali_lap_notable(s_early, 3, 0.9),
      "and so is taking most of a second out of the benchmark")

# The reaction is ARMED during detection and fired after the call has been
# spoken. Reacting from inside detection queued Chuck's verdict before Miles
# had made the call he was verdicting.
def quali_run(cars, tl):
    b = Booth()
    for _ in range(6):
        b.update_booth(qsess(cars, time_left=800.0, end_et=900.0))
        b._last_spoke -= 9.0
    b.tts.said = []
    b._last_spoke = 0.0
    b._cat_last.clear()
    return b

# The reaction is probabilistic, so this runs the case repeatedly: EVERY
# time a verdict is given it must come second, and across enough attempts at
# least one must be given at all.
orders, verdicts = [], 0
for _ in range(12):
    cars = grid()
    for i, c in enumerate(cars):
        c.best_lap = 92.0 + i * 0.2
    b = quali_run(cars, 800.0)
    cars[5].best_lap = 90.4                   # a big lap, late, field all out
    b.update_booth(qsess(cars, time_left=90.0, end_et=900.0))
    who = [w for w, _ in b.tts.said]
    if cast_mod.ANALYST in who:
        verdicts += 1
        orders.append(who.index(cast_mod.PLAY) < who.index(cast_mod.ANALYST))
check(verdicts > 0, "a notable lap does draw a verdict",
      "%d of 12 attempts" % verdicts)
check(all(orders), "and the call always comes before it", str(orders[:4]))

# And the early case says nothing at all.
cars2 = grid()
for c in cars2:
    c.best_lap = None
b2 = Booth()
for _ in range(6):
    b2.update_booth(qsess(cars2, time_left=900.0, end_et=900.0))
    b2._last_spoke -= 9.0
b2.tts.said = []
b2._last_spoke = 0.0
cars2[0].best_lap = 91.0
b2.update_booth(qsess(cars2, time_left=880.0, end_et=900.0))
check(all(w != cast_mod.ANALYST for w, _ in b2.tts.said),
      "and the first lap of a session draws no verdict at all",
      repr([t for _, t in b2.tts.said]))

print("\nMULTICLASS — the race the mixed grid is actually in")
# `Car.place_class` was computed on every tick since the session module was
# written and read by NOTHING. A GT3 car leading its class while running
# ninth overall was called "ninth", which is not his race.
_F1_TEAMS = ["McLaren", "Ferrari", "Mercedes", "Red Bull", "Alpine",
             "Aston Martin", "Haas", "Williams", "Alfa Romeo", "Alpha Tauri"]
check(era_mod.team_field(_F1_TEAMS) is not None,
      "a team-named F1 grid is recognised as constructors, not classes")
check(era_mod.team_field(["GT3", "GTE", "LMP2"]) is None,
      "while a genuinely mixed grid is not")

_b = Booth(); _cars = grid()
_CLS = ["LMP2"] * 4 + ["GT3"] * 8
for _i, (_c, _k) in enumerate(zip(_cars, _CLS)):
    _c.cls = _k; _c.gap_ahead = 2.0; _c.gap_leader = 2.0 * _i
    _c.place_class = (_i + 1) if _i < 4 else (_i - 3)
_me = _cars[4]; _me.is_player = True; _me.place_class = 1
_s = FakeSession(_cars, max_laps=40, leader_laps=20, laps_left=20,
                 multiclass=True, classes=["LMP2", "GT3"])
_s.player = _me
_ev = [c for c, _kw, _x in _b._class_filler(_s, time.time())]
check("class_pos" in _ev,
      "the player leading GT3 in fifth is told he leads GT3", str(_ev))
_kwp = next(k for c, k, _x in _b._class_filler(_s, time.time())
            if c == "class_pos")
check(_kwp.get("cpos") == "first" and _kwp.get("pos") == "fifth",
      "with the class position as a RANK and the road place as a place",
      "%s in class, %s on the road" % (_kwp.get("cpos"), _kwp.get("pos")))
check(_kwp.get("cpos") != "the lead",
      "never 'the lead in the GT3 class' — spoken_place is for the road")

_b2 = Booth(); _c2 = grid()
for _c in _c2:
    _c.cls = "F1"; _c.gap_ahead = 2.0
_s2 = FakeSession(_c2, max_laps=40, leader_laps=20, laps_left=20,
                  multiclass=False)
check(_b2._class_filler(_s2, time.time()) == [],
      "and a single-class race is never told about classes")

print("\n20. THE SETTLING WINDOW — broadening after the opening laps")
# The user's ask, in his words: lap 1 is the fight for the lead, "around lap 3
# start broadening to other battles around the field, but overtakes stay top
# priority", then normal mid-race. `settling` is that third state, and it is a
# DEPTH change — what the booth LOOKS at — not a licence for colour.
import overlay_booth as _ob

_p40 = phases(40)
check("settling" in _p40,
      "a 40-lap race has a settling window between the opening and the middle",
      " ".join("%d:%s" % (i, p) for i, p in enumerate(_p40[:8])))
check(_p40.index("settling") == _p40.count("opening"),
      "and it starts the lap the opening ends",
      "opening=%d, settling starts at %d" % (_p40.count("opening"),
                                             _p40.index("settling")))
check(_p40.index("mid") > _p40.index("settling"),
      "with the wide-open middle after it, never before")
check("settling" not in phases(5),
      "a five-lap dash gets NO settling window — it has no middle to protect",
      str(phases(5)))
check(_ob.FOCUS_LIMIT["opening"] < _ob.FOCUS_LIMIT["settling"]
      < _ob.FOCUS_LIMIT["mid"],
      "the booth looks deeper than in the opening, not as deep as mid-race",
      "%d < %d < %d" % (_ob.FOCUS_LIMIT["opening"], _ob.FOCUS_LIMIT["settling"],
                        _ob.FOCUS_LIMIT["mid"]))

# WHICH CATEGORIES, never which words (LAW 20). `_bag` persistence makes any
# prose match flaky, and a category list does not drift as lines are edited.
def _filler_cats(phase, length="normal"):
    bb = Booth()
    bb._phase = phase
    bb._length = length
    bb._field_size = 12
    ss = FakeSession(grid(), max_laps=40, leader_laps=6, laps_left=34)
    return {c for c, _kw, _x in bb._filler(ss, time.time())}

_open, _settle, _mid, _close = (_filler_cats(p) for p in
                                ("opening", "settling", "mid", "closing"))
COLOUR = {"track_fact", "track_character", "analysis", "analysis_era",
          "booth_joke", "booth_dig", "analyst_dig", "dig_stuck", "dig_wide",
          "story_ask", "driver_ask", "interview"}
check(not (_settle & COLOUR),
      "settling offers no colour — no trivia, no jokes, no retrospectives",
      str(sorted(_settle & COLOUR)))
check(_mid & COLOUR,
      "while the middle of the race does", str(sorted(_mid & COLOUR)[:3]))
check(len(_settle) >= len(_open),
      "settling is not NARROWER than the opening",
      "opening=%d settling=%d" % (len(_open), len(_settle)))
check(not (_close & COLOUR),
      "and the closing laps stay clear of it too",
      str(sorted(_close & COLOUR)))

print("\n21. A FIGHT FOR THE LEAD IN THE RUN-IN OUTRANKS EVERYTHING")
# The failure this exists to stop: a P4 overtake (60 + 16) out-scoring a
# battle for the lead (40 + 30) while the race is being decided.
def _front_booth(gap2, phase="late"):
    bb = Booth()
    cars = grid()
    for c in cars:
        c.gap_ahead = 4.0
    cars[1].gap_ahead = gap2
    ss = FakeSession(cars, max_laps=40, leader_laps=36, laps_left=4)
    bb._phase = phase
    bb._front_fight = bb._front_fight_live(ss)
    return bb, cars

_b21, _cars21 = _front_booth(0.4)
check(_b21._front_fight, "the leader being hunted is a fight for the lead")
_lead_ev = ("battle", {}, _cars21[0])
_mid_ev = ("overtake", {}, _cars21[3])
def _score(bb, e):
    return (_ob.PRIORITY.get(e[0], 0) + bb._place_bonus(e) + bb._front_bonus(e))
check(_score(_b21, _lead_ev) > _score(_b21, _mid_ev),
      "so it beats a P4 overtake in the closing stages",
      "lead=%d p4=%d" % (_score(_b21, _lead_ev), _score(_b21, _mid_ev)))

# MID-RACE THE SAME FIGHT STILL COUNTS — reported live: "I pulled up behind
# P1 to battle him for the lead and the commentators said nothing". The bonus
# is reduced rather than removed, so the wide view survives everywhere except
# the one place a race is actually being decided.
_b21b, _c21b = _front_booth(0.4, phase="mid")
_mb = _b21b._front_bonus(("battle", {}, _c21b[0]))
check(0 < _mb < _ob.LATE_FRONT_BONUS,
      "mid-race the override is reduced, not removed", "bonus=%d" % _mb)
check(_score(_b21b, ("battle", {}, _c21b[0]))
      > _score(_b21b, ("overtake", {}, _c21b[3])),
      "and a fight for the lead still beats a midfield pass")
check(_b21b._front_bonus(("overtake", {}, _c21b[3])) == 0,
      "but nothing outside the top two is boosted, ever")
_b21c, _c21c = _front_booth(9.0, phase="mid")
check(_b21c._front_bonus(("battle", {}, _c21c[0])) == 0,
      "and a leader nine seconds clear is a procession, not a fight")

_b21c, _c21c = _front_booth(18.0)
check(not _b21c._front_fight,
      "a leader eighteen seconds clear is a procession, not a fight")
check(_b21c._front_bonus(("battle", {}, _c21c[0])) == 0,
      "and nothing about him is boosted")

print(chr(10) + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
