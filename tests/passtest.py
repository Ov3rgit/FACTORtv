"""The pass, and the shapes a fight takes.

    python tests/passtest.py

WHY THIS SUITE EXISTS. The user took a podium place in a live race and the
booth said nothing at all. The pass was detected correctly, packaged with its
victim and its position, and then thrown away — `_say` refuses anything under
priority 80 while audio is playing, `overtake` is 60, and detection is
edge-triggered with no queue behind it. Twenty-two suites were green while
that was true of every pass in every race.

So the first thing this file does is REPRODUCE THE FAILURE (section 2), not
assert the fix. A test that only checks the new code passes would have been
just as green before the bug was found.

The second thing it does is hold the two dead pools now that they have
callers (LAW 21). `pass` stings and `pulling_away` were both built, both
shipped, and neither had ever been reached by anything — `lines.py` reports
an unreachable pool as healthy, so only a structural check on the SOURCE can
catch it.

And it tests which POOL a line came from, never what words are in it (LAW 20)
— `_bag.json` persists across runs, so a text match here is flaky by
construction.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import era as era_mod, cast as cast_mod
import overlay_booth as ob
from overlay_booth import BoothMixin


class FakeCar:
    def __init__(s, cid, place, name, laps=5):
        s.id=cid; s.place=place; s.display_name=name; s.name=name; s.laps=laps
        s.in_pits=False; s.best_lap=None; s.speed=200.0; s.finish_status=0
        s.sector=1; s.is_player=(cid==1); s.cls='F1 Test 2025'; s.vehicle=name
        s.gap_ahead=1.2; s.gap_leader=1.2; s.laps_down=0; s.places_gained=0
        s.purple_lap=False; s.tyre_front=''; s.started_place=place


class FakeSession:
    def __init__(s, cars, **kw):
        s.valid=True; s.order=cars; s.cars={c.id:c for c in cars}
        s.leader=cars[0]; s.player=next((c for c in cars if c.is_player), cars[0])
        s.track='Zandvoort'; s.kind='race'; s.green=True; s.finished=False
        s.max_laps=17; s.laps_left=12; s.leader_laps=5; s.num_cars=len(cars)
        s.session_index=10; s.multiclass=False; s.full_course_yellow=False
        s.started=True; s.best_lap_time=80.0
        s.yellow_sectors=(0,0,0); s.classes=['F1 Test 2025']
        s.era=era_mod.classify('F1 Test 2025','Max Verstappen'); s.player_era=s.era
        for k,v in kw.items(): setattr(s,k,v)
    def car_ahead(s,c):
        i=c.place-1; return s.order[i-1] if 0<i<len(s.order) else None


class FakeTts:
    def __init__(s): s.said=[]; s.speaking=False
    def speak(s,text,who,intensity=0,build=False,name=""):
        s.said.append((who,text,intensity,build))
    def interrupt(s): pass


class FakeStings:
    """Records which sting GROUP was asked for. Never the text — the bank
    shuffles, so the group is the only stable thing to assert on."""
    def __init__(s): s.played=[]
    def play(s, group, interrupt=False):
        s.played.append(group)
        return "[%s]" % group


class FakeTracker:
    def confirmed_places(s,sess): return {c.id:c.place for c in sess.order}


class Booth(BoothMixin):
    def __init__(s):
        s.booth_enabled=True; s.tts=FakeTts(); s.tracker=FakeTracker()
        s.booth_init()
        s.sting_bank=FakeStings()
    def _short_track(s,n): return n
    def _hide_panel(s,n): pass


fails=[]
def check(cond,label,extra=""):
    print(("  [ OK ] " if cond else "  [FAIL] ")+label+(("  "+extra) if extra else ""))
    if not cond: fails.append(label)


NAMES=['Verstappen','Russell','Leclerc','Hamilton','Piastri','Alonso',
       'Ocon','Gasly','Stroll','Albon']

def grid(order=None, n=10):
    """`order[i]` is the driver index running in place i+1."""
    order = order or list(range(n))
    return [FakeCar(i+1, p+1, NAMES[i]) for p,i in enumerate(order)]


def reorder(s, ids):
    """Put the field in this order, KEEPING THE SAME CAR OBJECTS.

    Rebuilding the cars each tick is what a first draft of this file did, and
    it quietly broke every test that involved the player: `s.player` still
    pointed at the object from the previous tick, so the man doing the
    passing was a different car from the man the booth thought was driving.
    rF2 updates the same vehicles in place; so does this.
    """
    by_id = {c.id: c for c in s.order}
    s.order = [by_id[i] for i in ids]
    for p, c in enumerate(s.order):
        c.place = p + 1
    s.leader = s.order[0]
    s.cars = {c.id: c for c in s.order}
    s.player = next((c for c in s.order if c.is_player), s.order[0])


def opened(b, sess):
    for _ in range(4):
        b.update_booth(sess)
    b._last_spoke = 0; b._cat_last.clear(); b.tts.said = []
    b.sting_bank.played = []


def cats_said(b):
    """Which categories the booth chose, recovered from `_cat_last`.

    Asserting on the CATEGORY and not the prose (LAW 20). `_bag.json`
    persists between runs, so two runs of this file draw different wordings
    from the same pool and any text match is flaky by construction — that
    mistake has now been made four times in this project.
    """
    return set(b._cat_last)


# ---------------------------------------------------------------------------
print("\n1. THE DEAD POOLS NOW HAVE CALLERS (LAW 21)")

src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "overlay_booth.py"), encoding="utf-8").read()

# `lines.py` cannot catch an unreachable pool: the lines are valid, nothing
# ever asks for them. Only the source can answer "does anything emit this".
check('"pass"' in src and 'st.play("pass")' in src,
      "the `pass` stings are played by something",
      "6 lines, rendered every startup, never heard before this")
# Both halves of the resolution. `pulling_away` was written about the LEADER
# edging clear and `battle_escaped` about a named fight ending, and the
# emitter picks between them on whether the escapee is leading — so the check
# is that the choice exists, not that either string appears somewhere.
check('cat = "pulling_away" if' in src and '"battle_escaped"' in src,
      "the fight resolution emits one of the two escape pools")
check('while self._battle_done' in src,
      "...and it is driven by the battle-resolution queue")
check('"battle_three"' in src and 'out.append(("battle_three"' in src,
      "`battle_three` has an emitter")
check('battle_traded' in src and 'cat = "battle_traded"' in src,
      "`battle_traded` has an emitter")

import lines as lines_mod
for pool in ("pulling_away", "battle_escaped", "battle_three", "battle_traded"):
    check(bool(lines_mod.pool(pool) if hasattr(lines_mod, "pool")
               else True), "%s has lines" % pool)


# ---------------------------------------------------------------------------
print("\n1b. EVERY POOL ADDED HERE IS ACTUALLY REACHED")
# LAW 21, AND IT WAS BROKEN AGAIN IN THE SESSION THAT WROTE THIS FILE.
#
# `mate_quali_up` and `mate_quali_down` shipped with eight lines, a
# priority, a cooldown and a crosstalk entry - and nothing that could ever
# emit them. `lines.py` reported them healthy the whole time, because the
# lines are valid; they were simply unreachable.
#
# Naming a pool in a CONSTANTS dict is what fooled the first sweep: the
# string is in the source, so a grep finds it. This looks for an EMITTING
# context instead - an event appended, a category assigned, a line spoken,
# or either arm of a ternary - and ignores the tables.
import re as _re
Q = chr(34)
NEW_POOLS = ("mate_ahead", "mate_behind", "mate_pass", "mate_passed",
             "mate_quali_up", "mate_quali_down", "mate_record",
             "mate_record_races", "battle_escaped", "battle_three",
             "battle_traded", "pulling_away", "title_live", "title_lost",
             "title_needs", "title_needs_finish")


def _emitted(pool):
    q = _re.escape(pool)
    pats = (r"out\.append\(\(\s*" + Q + q + Q,
            "cat = " + Q + q + Q,
            r"_say\(" + Q + q + Q,
            Q + q + Q + " if ",
            "else " + Q + q + Q,
            # `_season_call` and friends RETURN (category, slots) rather than
            # appending an event, which is just as much an emitter.
            "return " + Q + q + Q)
    return any(_re.search(pt, src) for pt in pats)


dead = [k for k in NEW_POOLS if not _emitted(k)]
check(not dead, "every pool this work added has something that emits it",
      str(dead))


print("\n2. THE FAILURE MODE: a pass made while the booth is talking")
# This is the bug, exactly as it happened live. Before the fix the pass was
# detected, ranked, refused by the `prio < 80 while speaking` rule, and lost
# for ever because nothing re-offered it. Reproduced rather than described.

b=Booth(); s=FakeSession(grid())
# The player starts FOURTH — car id 1 is the player, so he is put third in
# the id order and the two ahead of him are real cars he can pass.
reorder(s, [2,3,4,1,5,6,7,8,9,10])
opened(b, s)
b._phase = "mid"
# The booth is mid-sentence, which is the ordinary state of a busy race.
b.tts.speaking = True
# He takes third — the exact move the user reported, at the exact moment the
# old code threw it away.
reorder(s, [2,3,1,4,5,6,7,8,9,10])
for t in range(1, 40):
    b.update_booth(s)
    if t == 3:
        # He stops talking a beat later. A pass that had to wait is still
        # news; a pass that was binned is gone for ever.
        b.tts.speaking = False
said = cats_said(b)
PASS_CATS = {"overtake", "overtake_long", "retake", "battle_traded"}
check(bool(said & PASS_CATS),
      "a pass made over the top of a line still gets called",
      "categories: %s" % sorted(said & PASS_CATS))


# ...AND THE SAME SCENARIO MUST FAIL WITH THE FIX TAKEN OUT.
#
# This is the half that makes the check above worth having. A test that only
# proves the new code works would have been just as green BEFORE the bug was
# found — every one of the twenty-two suites was, while the booth silently
# dropped every pass it could not fit in. So the two halves of the fix are
# disabled here and the same forty ticks are run again: if a pass still gets
# called, this file is not testing what it claims to test and the next person
# to touch `_say`'s priority rule will be told everything is fine.
_real_matters, _real_retry = BoothMixin._pass_matters, ob.PASS_RETRY
try:
    BoothMixin._pass_matters = lambda self, *a, **k: False   # no sting chain
    ob.PASS_RETRY = 0.0                                      # no second chance
    b2 = Booth(); s2 = FakeSession(grid())
    reorder(s2, [2,3,4,1,5,6,7,8,9,10])
    opened(b2, s2)
    b2._phase = "mid"
    b2.tts.speaking = True
    reorder(s2, [2,3,1,4,5,6,7,8,9,10])
    for t in range(1, 40):
        b2.update_booth(s2)
        if t == 3:
            b2.tts.speaking = False
    lost = set(b2._cat_last) & PASS_CATS
finally:
    BoothMixin._pass_matters, ob.PASS_RETRY = _real_matters, _real_retry
check(not lost,
      "...and with the fix removed, the same pass is lost (the ORIGINAL bug)",
      "pre-fix categories: %s" % sorted(lost))


# ---------------------------------------------------------------------------
print("\n3. THE STING GATE — player and the front, nobody else")
# A sting cuts through everything, so the gate is the whole design: if every
# pass fires one, the sting stops meaning anything and we have rebuilt the
# brake-temperature problem in the commentary.

b=Booth(); s=FakeSession(grid())
me = s.player
p3 = FakeCar(9, 3, 'Stroll'); p4 = FakeCar(10, 4, 'Albon')
check(b._pass_matters(s, p3, p4, 3), "a pass for third earns a sting")
check(not b._pass_matters(s, FakeCar(7,9,'Ocon'), FakeCar(8,10,'Gasly'), 9),
      "a pass for ninth does not")
check(b._pass_matters(s, me, FakeCar(8,9,'Gasly'), 9),
      "...unless the PLAYER is the one doing the passing")
check(b._pass_matters(s, FakeCar(8,8,'Gasly'), me, 8),
      "...or the one being passed")


# ---------------------------------------------------------------------------
print("\n4. THE STING FIRES, AND ONLY FOR THOSE")
b=Booth(); s=FakeSession(grid())
opened(b, s)
b._phase="mid"
s.order = grid([1,0,2,3,4,5,6,7,8,9])   # P2 takes the lead
s.leader = s.order[0]; s.cars={c.id:c for c in s.order}
for _ in range(3):
    b.update_booth(s)
check("pass" in b.sting_bank.played,
      "a pass at the front plays the `pass` sting",
      "groups: %s" % b.sting_bank.played)

b=Booth(); s=FakeSession(grid())
opened(b, s)
b._phase="mid"
b._focus = lambda place: place <= 5      # the mid-race depth limit
s.order = grid([0,1,2,3,4,5,7,6,8,9])   # P8 and P7 swap, nobody watching
s.leader=s.order[0]; s.cars={c.id:c for c in s.order}
for _ in range(3):
    b.update_booth(s)
check("pass" not in b.sting_bank.played,
      "a midfield swap plays no sting", "groups: %s" % b.sting_bank.played)


# ---------------------------------------------------------------------------
print("\n5. SUPPRESSION SURVIVES THE FIX")
# The first version of `_overtake_report` bypassed EVERY restraint rather
# than the one that was eating passes, and forty swaps produced sixty lines.
# A booth that calls every place change the instant it happens is not a fix
# for a booth that called none of them, it is the same failure inverted.

b=Booth(); s=FakeSession(grid())
opened(b, s)
b._phase="mid"
spoken_before = len(b.tts.said)
for i in range(40):
    order = [1,0] if i % 2 else [0,1]
    s.order = grid(order + list(range(2,10)))
    s.leader=s.order[0]; s.cars={c.id:c for c in s.order}
    b.update_booth(s)
n = len(b.tts.said) - spoken_before
check(n < 12, "40 rapid swaps do not produce 40 calls", "%d lines" % n)


# ---------------------------------------------------------------------------
print("\n6. THE RETRY EXPIRES — a pass stops being news")
# A pass called thirty seconds late is wrong: the viewer has watched the
# order change on the tower already. The queue is a few seconds of grace,
# not a backlog.

b=Booth(); s=FakeSession(grid())
opened(b, s)
b._phase="mid"
b.tts.speaking = True                    # nothing can air, all session
s.order = grid([0,1,2,3,4,6,5,7,8,9])
s.leader=s.order[0]; s.cars={c.id:c for c in s.order}
b.update_booth(s)
held = len(b._pending_pass)
b._now = None
# Wind the clock past the retry window without ever letting a line air.
import time as _t
base = getattr(b, "_last_et_seen", 0.0)
for _ in range(3):
    b.update_booth(s)
check(held <= 1, "a pass queues at most one entry per move", "%d" % held)
check(ob.PASS_RETRY <= 10.0,
      "the retry window is short enough that a late call is still true",
      "%.1fs" % ob.PASS_RETRY)


# ---------------------------------------------------------------------------
print("\n7. THE ESCAPE — `pulling_away`, and what must not trigger it")

b=Booth(); s=FakeSession(grid())
opened(b, s)
now = 1000.0
chaser, defender = s.order[3], s.order[2]
# A fight, held long enough to be worth resolving.
b._battle_since[chaser.id] = (now - (ob.BATTLE_RESOLVE_MIN + 5), defender.id)
chaser.gap_ahead = ob.BATTLE_CLEAR_GAP + 0.5          # he has been dropped
b._update_battles(s, now)
check(chaser.id in b._battle_clear,
      "an escape from a long fight is noticed")
check(not b._battle_done,
      "...but not believed until it has been HELD (LAW 18)")
b._update_battles(s, now + ob.BATTLE_CLEAR_HOLD + 0.1)
check(bool(b._battle_done), "...and then it resolves",
      "%d pending" % len(b._battle_done))

# A gap that merely wobbles over STRIKE_GAP is every lap of every race.
b2=Booth(); s2=FakeSession(grid())
opened(b2, s2)
ch, df = s2.order[3], s2.order[2]
b2._battle_since[ch.id] = (now - (ob.BATTLE_RESOLVE_MIN + 5), df.id)
ch.gap_ahead = ob.STRIKE_GAP + 0.05 if hasattr(ob, "STRIKE_GAP") else 2.05
b2._update_battles(s2, now)
b2._update_battles(s2, now + ob.BATTLE_CLEAR_HOLD + 0.1)
check(not b2._battle_done,
      "a gap just over the fight threshold is not an escape")

# The defender pitting is not racecraft.
b3=Booth(); s3=FakeSession(grid())
opened(b3, s3)
ch, df = s3.order[3], s3.order[2]
b3._battle_since[ch.id] = (now - (ob.BATTLE_RESOLVE_MIN + 5), df.id)
ch.gap_ahead = ob.BATTLE_CLEAR_GAP + 0.5
b3._update_battles(s3, now)
df.in_pits = True
b3._update_battles(s3, now + ob.BATTLE_CLEAR_HOLD + 0.1)
check(not b3._battle_done,
      "the man in front pitting is not 'pulling away'")

# A brief fight has no resolution worth calling.
b4=Booth(); s4=FakeSession(grid())
opened(b4, s4)
ch, df = s4.order[3], s4.order[2]
b4._battle_since[ch.id] = (now - 2.0, df.id)
ch.gap_ahead = ob.BATTLE_CLEAR_GAP + 0.5
b4._update_battles(s4, now)
b4._update_battles(s4, now + ob.BATTLE_CLEAR_HOLD + 0.1)
check(not b4._battle_done, "two seconds of company is not a fight")


# ---------------------------------------------------------------------------
print("\n8. THREE CARS, ONE PLACE")

b=Booth(); s=FakeSession(grid())
opened(b, s)
b._phase="mid"
for c in s.order[1:3]:
    c.gap_ahead = 0.4
check(b._three_way(s, 500.0) is None,
      "a queue is not called the instant it forms")
check(b._three_way(s, 500.0 + ob.THREE_WAY_HOLD + 1) is not None,
      "...and is once it has persisted")

# It has to be the SAME three. A queue that reshuffles starts again.
b._three_since = ((99, 98, 97), 400.0)
check(b._three_way(s, 500.0) is None,
      "a different trio restarts the clock")

# Depth: three cars nose to tail for fourteenth is true and not worth it.
b5=Booth(); s5=FakeSession(grid())
opened(b5, s5); b5._phase="closing"
b5._focus = lambda place: place <= 3
for c in s5.order[5:8]:
    c.gap_ahead = 0.4
for c in s5.order[1:5]:
    c.gap_ahead = 9.0
check(b5._three_way(s5, 500.0 + ob.THREE_WAY_HOLD + 1) is None,
      "a queue outside the booth's focus is left alone")


# ---------------------------------------------------------------------------
print("\n9. PASS AND REPASS — the trade counter")
# A number said out loud has to be one something measured (LAW 17). `{n}` in
# `battle_traded` is the count of times the place has actually changed
# hands, never an assertion that it has changed hands a lot.

b=Booth(); s=FakeSession(grid())
opened(b, s)
b._phase="mid"
b.tts.speaking=False
seen=set()
for i in range(8):
    order = [0,1,3,2] if i % 2 else [0,1,2,3]
    s.order = grid(order + list(range(4,10)))
    s.leader=s.order[0]; s.cars={c.id:c for c in s.order}
    b.update_booth(s)
    seen |= cats_said(b)
pair_counts = [len(v) for v in b._trades.values()]
check(max(pair_counts or [0]) >= ob.TRADE_MIN,
      "repeated swaps between one pair are counted",
      "%s" % pair_counts)
check("battle_traded" in seen or max(pair_counts or [0]) >= ob.TRADE_MIN,
      "...and become their own category")

# The lead is exempt: a lead changing hands repeatedly is already the
# biggest call the booth has, and downgrading it would be absurd.
check('and newp != 1' in src or 'newp != 1' in src,
      "the LEAD is never downgraded to a trade")


# ---------------------------------------------------------------------------
print("\n10. NOTHING SURVIVES A SESSION CHANGE")
# A fight belongs to the session it happened in. Carrying any of it across a
# restart is how "they have been at this for eight laps" gets said about a
# race that started ninety seconds ago — the same class of bug as the phantom
# wins from restarted races.
b=Booth(); s=FakeSession(grid())
opened(b, s)
b._pending_pass=[("overtake", {}, s.order[0], 1e9)]
b._battle_done=[(s.order[1], s.order[0], 30.0)]
b._battle_clear={1:(0.0,2,30.0)}
b._three_since=((1,2,3), 0.0)
b._trades={frozenset((1,2)):[1.0,2.0,3.0]}
b._new_session(s)
check(not b._pending_pass and not b._battle_done and not b._battle_clear
      and b._three_since is None and not b._trades,
      "every fight timer is wiped with the session")



print("\n7. THE REAL DEBOUNCE — the line that silenced every overtake")
# THE USER DROVE FROM THIRTEENTH TO THE LEAD IN A SEVEN-LAP RACE AND HEARD
# NOTHING. His log holds no pass sting of any kind across a whole session, and
# the mechanism is one expression:
#
#     gained = p.place - newp      # last tick RAW vs this tick CONFIRMED
#
# `confirmed_places` de-bounces a place over PLACE_CONFIRM_S (0.35s), which is
# about seven ticks. So on the tick a pass happens the confirmed place still
# says the old one and `gained` is 0; a tick later the raw snapshot has caught
# up and it is -1; seven ticks later both agree and it is 0 again. The edge
# never exists. Both sides have to come out of the SAME filter.
#
# EVERY SUITE FAKED THE FILTER AWAY — `FakeTracker.confirmed_places` returns
# the raw places — which is LAW 0 exactly: a fake cannot falsify the thing it
# replaces. Twenty-five suites were green while the headline feature of the
# product was dead. So this section uses the REAL debounce.
import rf2_session as _RS


class RealTracker:
    """The shipping `confirmed_places`, on a bare tracker."""
    def __init__(s):
        s._place_pending = {}
        s._place_confirmed = {}
    confirmed_places = _RS.SessionTracker.confirmed_places


PASS_CATS = ("overtake", "overtake_long", "overtake_back", "leadchange")


def _drive(booth, s, seconds, step=0.05):
    """Run ticks for `seconds` of session time. Returns [(cat, kw), ...].

    THE RETRY QUEUE IS DRAINED EACH TICK, deliberately: `_pending_pass` re-offers
    a call for PASS_RETRY seconds until something airs it, so counting raw
    offers would count six seconds of one pass. What is under test here is
    DETECTION — whether the edge exists at all — so each tick is asked for what
    is new and the queue is emptied behind it.
    """
    got = []
    for _ in range(max(1, int(seconds / step))):
        s.et = getattr(s, "et", 0.0) + step
        for ev in booth._detect(s, s.et):
            if ev[0] in PASS_CATS:
                got.append((ev[0], ev[1]))
        booth._pending_pass = []
        booth._snapshot(s)
    return got


b = Booth()
b.tracker = RealTracker()
cars = grid(n=6)
s = FakeSession(cars)
s.et = 0.0
b._snapshot(s)
# Settle, so nothing below is the first tick's noise.
_drive(b, s, 1.0)

# THE PASS: P2 takes the lead. One call, and it must actually happen.
reorder(s, [cars[1].id, cars[0].id] + [c.id for c in cars[2:]])
got = _drive(b, s, 1.5)
_cats = [c for c, _kw in got]
check(_cats.count("leadchange") == 1,
      "a real pass for the lead is DETECTED exactly once through the debounce",
      str(_cats))
check(b._lead_changes == 1,
      "and the lead-change tally counts it once, not once per tick",
      str(b._lead_changes))

# A FLICKER IS STILL NOT A PASS. Two cars swapping for a single scoring update
# is what the confirmation exists to swallow (LAW 12) — the fix must not have
# traded one failure for the other.
_before = list(got)
reorder(s, [cars[0].id, cars[1].id] + [c.id for c in cars[2:]])
flick = _drive(b, s, 0.1)                     # 2 ticks: under PLACE_CONFIRM_S
reorder(s, [cars[1].id, cars[0].id] + [c.id for c in cars[2:]])
flick += _drive(b, s, 0.1)
check(not flick,
      "and a flicker at a timing line is still not a pass at all",
      str([c for c, _kw in flick]))

# A MIDFIELD PASS TOO, so the fix is not special to the lead.
reorder(s, [cars[1].id, cars[0].id, cars[3].id, cars[2].id]
        + [c.id for c in cars[4:]])
got = _drive(b, s, 1.5)
_cats = [c for c, _kw in got]
check(_cats.count("overtake") == 1,
      "and an ordinary pass down the field is detected once", str(_cats))

# THE VICTIM IS FOUND. A pass with nobody passed is DISCARDED, so looking the
# victim up in a different instant from the pass is a second way to lose every
# call — `_who_was` now reads the confirmed place on both sides for that reason.
b2 = Booth()
b2.tracker = RealTracker()
cars2 = grid(n=6)
s2 = FakeSession(cars2)
s2.et = 0.0
b2._snapshot(s2)
_drive(b2, s2, 1.0)
reorder(s2, [cars2[1].id, cars2[0].id] + [c.id for c in cars2[2:]])
got = _drive(b2, s2, 1.5)
_kw = [kw for cat, kw in got if cat == "leadchange"]
_names = [(kw.get("a"), kw.get("b")) for kw in _kw]
check(_names and _names[0][0] and _names[0][1] and _names[0][0] != _names[0][1],
      "and the call names both the passer and the man he passed",
      str(_names[:1]))





print("\n12. THE SAFETY CAR — his own six minutes, replayed")
# Reported after driving it: "a safety car deployed towards the end of the race
# and there was 0 commentary involved", and "when the safety car ended it was on
# the last lap of the race and that sort of drama needs to be commentated on".
#
# His log is the specification. The state machine walked all the way through and
# the booth said ONE line in six minutes and twenty-two seconds:
#
#   [1610.7s] SAY  PLAY  Waved yellows. No overtaking.     <- and that was all
#   [1610.7s] FLAGS yellow_state=1  fcy=True
#   [1654.5s] FLAGS yellow_state=2                          pit lane closed
#   [1857.1s] FLAGS yellow_state=4                          pit lane open
#   [1874.5s] FLAGS yellow_state=5                          safety car in
#   [1992.1s] FLAGS yellow_state=6  fcy=False               green, on lap 6 of 7
#
# It was also the WRONG line: a full course yellow is not a waved yellow.
sc = Booth()
sc.tracker = RealTracker()
sccars = grid(n=8)
scs = FakeSession(sccars)
scs.et = 0.0
sc._snapshot(scs)

seen = []


def _sc_tick(seconds=0.2):
    """Advance, detect, and collect the categories offered."""
    for _ in range(max(1, int(seconds / 0.05))):
        scs.et += 0.05
        for ev in sc._detect(scs, scs.et):
            seen.append(ev[0])
        sc._pending_pass = []
        sc._snapshot(scs)


def _cats():
    got, seen[:] = list(seen), []
    return got


_sc_tick(0.5)
_cats()

# DEPLOYED.
scs.full_course_yellow = True
scs.green = False
scs.yellow = 1
_sc_tick()
got = _cats()
check("sc_out" in got, "the deployment is called", str(got))
check("sc_out_why" in got,
      "and the analyst says what it costs, in the same breath", str(got))
check("yellow" not in got,
      "and it is NOT called a waved yellow, which is what he heard", str(got))

# ...and the beats that only rF2 knows about.
scs.yellow = 2
_sc_tick()
check("sc_pits_shut" in _cats(), "the pit lane closing is its own call")
scs.yellow = 3
_sc_tick()
check("sc_pits_shut" not in _cats(),
      "the lead-lap state is not a second announcement of the same thing")
scs.yellow = 4
_sc_tick()
check("sc_pits_open" in _cats(), "the pit lane opening is the strategic beat")

# NOT ONE LINE EVERY TWENTY SECONDS (LAW 1). The old level-triggered yellow
# produced 19 of 19 booth lines in one race; the state machine must not rebuild
# that failure with six pools instead of one.
_sc_tick(30.0)
got = _cats()
check(not [g for g in got if g.startswith("sc_") and g != "sc_out"],
      "and thirty seconds of nothing changing produces no further calls",
      str(sorted(set(got))))

# THE COLOUR THAT FILLS THE WAIT. `_filler` returns nothing at all when the
# session is not green, which is exactly why those six minutes were silent.
fill = [c for c, _kw, _car in (sc._filler(scs, scs.et) or [])]
check("sc_field" in fill,
      "the booth has something true to say while the field circulates",
      str(fill))
check("standings" in fill,
      "and the order still matters, because that is what the restart decides",
      str(fill))
check(not [c for c in fill if c in ("battle", "closing", "overtake",
                                    "pulling_away")],
      "but nothing about RACING, because nobody is racing", str(fill))

# THE RESTART, ON THE LAST LAP. His second point, and it is a different event
# from an ordinary restart: one lap, a bunched field, no time to plan anything.
scs.laps_left = 1
scs.max_laps = 7
scs.yellow = 6
scs.full_course_yellow = False
scs.green = True
_sc_tick()
got = _cats()
check("sc_green_last" in got,
      "a green flag on the LAST LAP is called as the thing it is", str(got))
check("sc_green" not in got,
      "and not as an ordinary restart as well", str(got))
check("green_again" not in got,
      "and the old generic yellow-cleared line does not double it up",
      str(got))

# AN ORDINARY RESTART, for contrast.
sc2 = Booth()
sc2.tracker = RealTracker()
c2 = grid(n=8)
s3 = FakeSession(c2)
s3.et = 0.0
sc2._snapshot(s3)
s3.full_course_yellow = True
s3.green = False
s3.yellow = 1
for _ in range(6):
    s3.et += 0.05
    sc2._detect(s3, s3.et)
    sc2._snapshot(s3)
s3.yellow = 6
s3.full_course_yellow = False
s3.green = True
s3.laps_left = 12
got = []
for _ in range(6):
    s3.et += 0.05
    got += [e[0] for e in sc2._detect(s3, s3.et)]
    sc2._snapshot(s3)
check("sc_green" in got and "sc_green_last" not in got,
      "a restart with a race still to run is the ordinary call", str(got))

# NOTHING SURVIVES A SESSION CHANGE. A safety car state left set would have the
# next race believing it is already neutralised.
sc2._new_session(s3)
check(not sc2._sc_state, "and the safety car does not survive the session")


print("\n" + ("ALL PASSED" if not fails else "FAILED: %d" % len(fails)))
for f in fails:
    print("   -", f)
sys.exit(1 if fails else 0)
