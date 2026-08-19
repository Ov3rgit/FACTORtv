"""Headless director test: build fake sessions, assert the booth reacts.

Runs with no game and no audio — the TTS is stubbed, so this checks the
DIRECTION (what fires, when, and who says it) rather than the voices.
    python tests/boothtest.py
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import era as era_mod, lines as lines_mod, cast as cast_mod
from overlay_booth import BoothMixin

class FakeCar:
    def __init__(s, cid, place, name, laps=5):
        s.id=cid; s.place=place; s.display_name=name; s.name=name; s.laps=laps
        s.in_pits=False; s.best_lap=None; s.speed=200.0; s.finish_status=0
        s.sector=1; s.is_player=(cid==1); s.cls='F1 Test 2025'; s.vehicle=name
        s.gap_ahead=1.2; s.gap_leader=1.2; s.laps_down=0; s.places_gained=0
        s.purple_lap=False; s.tyre_front=''
class FakeSession:
    def __init__(s, cars, **kw):
        s.valid=True; s.order=cars; s.cars={c.id:c for c in cars}
        s.leader=cars[0]; s.player=next((c for c in cars if c.is_player), cars[0])
        s.track='Zandvoort'; s.kind='race'; s.green=True; s.finished=False
        s.max_laps=17; s.laps_left=12; s.leader_laps=5; s.num_cars=len(cars)
        s.session_index=10; s.multiclass=False; s.full_course_yellow=False; s.started=True
        s.yellow_sectors=(0,0,0); s.classes=['F1 Test 2025']
        s.era=era_mod.classify('F1 Test 2025','Max Verstappen'); s.player_era=s.era
        for k,v in kw.items(): setattr(s,k,v)
    def car_ahead(s,c):
        i=c.place-1; return s.order[i-1] if 0<i<len(s.order) else None
class FakeTts:
    def __init__(s): s.said=[]; s.speaking=False
    def speak(s,text,who,intensity=0,build=False,name=""): s.said.append((who,text,intensity,build))
    def interrupt(s): pass
class FakeTracker:
    def confirmed_places(s,sess): return {c.id:c.place for c in sess.order}
class Booth(BoothMixin):
    def __init__(s):
        s.booth_enabled=True; s.tts=FakeTts(); s.tracker=FakeTracker(); s.booth_init()
    def _short_track(s,n): return n
    def _hide_panel(s,n): pass

def opened(b, sess):
    """Drain the broadcast bookends.

    A real race opens with the intro sting and then lights-out, which
    legitimately consume the first ticks. Tests of in-race behaviour start
    after the show is actually running.
    """
    for _ in range(4):
        b.update_booth(sess)
    b._last_spoke = 0; b._cat_last.clear(); b.tts.said = []

fails=[]
def check(cond,label,extra=""):
    print(("  [ OK ] " if cond else "  [FAIL] ")+label+(("  "+extra) if extra else ""))
    if not cond: fails.append(label)

names=['Verstappen','Russell','Leclerc','Hamilton','Piastri','Alonso','Ocon','Gasly']
def grid(order=None):
    order = order or list(range(len(names)))
    return [FakeCar(i+1, p+1, names[i]) for p,i in enumerate(order)]

print("\n1. START")
b=Booth(); s=FakeSession(grid())
b.update_booth(s); b.update_booth(s)
# Assert on the CATEGORY that fired, not on words in the prose. Keyword
# matching made this test flaky at ~17%: "Twenty-odd cars funnelling into that
# first corner!" is a perfectly good start call that happens to contain none
# of the expected words. The booth is allowed to write freely; the test's job
# is to check that the right EVENT was recognised.
check('start' in b._cat_last, "green flag produces a start call",
      repr(b.tts.said[:1]))

print("\n2. OVERTAKE (P2 passes P1 -> lead change)")
b=Booth(); s1=FakeSession(grid([0,1,2,3,4,5,6,7])); opened(b, s1)
s2=FakeSession(grid([1,0,2,3,4,5,6,7]))
b.update_booth(s2)
said=b.tts.said
check('leadchange' in b._cat_last or 'overtake' in b._cat_last,
      "a pass for the lead is called", repr(said[:1]))
if said:
    who,txt,inten,build = said[0]
    check(who==cast_mod.PLAY, "called by play-by-play, not the analyst", who)
# Not every line names the drivers on purpose ("That is the move for the lead
# of the Grand Prix!" is about the moment). Check the SLOTS fill correctly
# across a run instead of asserting on one draw.
named=0
for i in range(30):
    b2=Booth(); opened(b2, FakeSession(grid([0,1,2,3,4,5,6,7])))
    b2.update_booth(FakeSession(grid([1,0,2,3,4,5,6,7])))
    if any(('Russell' in t or 'Verstappen' in t) for _,t,_,_ in b2.tts.said): named+=1
check(named>0, "driver-name slots fill correctly", "%d/30 draws named a driver" % named)

print("\n3. SUPPRESSION")
b=Booth(); s1=FakeSession(grid()); b.update_booth(s1); b._last_spoke=0; b.tts.said=[]
n=0
for i in range(40):
    order=[1,0,2,3,4,5,6,7] if i%2 else [0,1,2,3,4,5,6,7]
    b.update_booth(FakeSession(grid(order)))
    n=len(b.tts.said)
check(n<=6, "40 rapid swaps do not produce 40 calls", "%d lines" % n)

print("\n4. PHASE FOCUS")
# Focus is PHASE-dependent now, which is the whole point of the flow model:
# a P7/P8 swap is legitimate mid-race and is noise on the final lap.
#
# Asserts on the CATEGORY that fired, not on words in the prose. Keyword
# matching made this flaky at ~50%, because plenty of legitimate overtake
# lines ("Wheel to wheel, and it's X who comes out in front!") contain none
# of the obvious verbs. The booth writes freely; the test checks the event.


def deep_swap(b, laps_left, leader_laps):
    back = grid(); back[6], back[7] = back[7], back[6]
    for i, c in enumerate(back):
        c.place = i + 1
    sess = FakeSession(back)
    sess.laps_left = laps_left
    sess.leader_laps = leader_laps
    b._cat_last.pop('overtake', None)
    b._cat_last.pop('overtake_multi', None)
    b.update_booth(sess)
    return ('overtake' in b._cat_last) or ('overtake_multi' in b._cat_last)


b = Booth(); base = FakeSession(grid()); opened(b, base)
check(deep_swap(b, 12, 5), "mid-race: a P7/P8 swap IS called (field is open)")

b = Booth(); base = FakeSession(grid()); base.laps_left = 1; base.leader_laps = 16
opened(b, base)
check(not deep_swap(b, 1, 16),
      "final lap: the same swap is IGNORED (only the win matters)")

probe = Booth()
phases = []
for ll, done in ((17, 0), (12, 5), (3, 14), (1, 16)):
    sess = FakeSession(grid()); sess.laps_left = ll; sess.leader_laps = done
    phases.append("%dtogo->%s" % (ll, probe._race_phase(sess)))
print("       " + "  ".join(phases))

print("\n5. ERA GATING (1966 field must never hear DRS)")
b=Booth()
e66=era_mod.classify('','Brabham_1966')
s1=FakeSession(grid()); s1.era=s1.player_era=e66; b.update_booth(s1)
b._last_spoke=0; b._cat_last.clear(); b.tts.said=[]
bad=0
for i in range(60):
    s=FakeSession(grid([1,0,2,3,4,5,6,7] if i%2 else [0,1,2,3,4,5,6,7]))
    s.era=s.player_era=e66; b._last_spoke=0; b._cat_last.clear()
    b.update_booth(s)
for who,txt,_,_ in b.tts.said:
    if any(w in txt.lower() for w in ('drs','rear wing','push-to-pass','hybrid','battery')): bad+=1
check(bad==0, "no anachronisms in %d generated lines" % len(b.tts.said))

print("\n6. PERSONA CONSTRAINTS")
b=Booth(); s1=FakeSession(grid()); opened(b, s1)
for i in range(200):
    b._last_spoke=0; b._cat_last.clear()
    b.update_booth(FakeSession(grid([1,0,2,3,4,5,6,7] if i%2 else [0,1,2,3,4,5,6,7])))
seen=set(w for w,_,_,_ in b.tts.said)
check(cast_mod.PLAY in seen, "play-by-play speaks")
check(cast_mod.ANALYST in seen, "analyst speaks too", str(sorted(seen)))
uniq=len(set(t for _,t,_,_ in b.tts.said)); tot=len(b.tts.said)
check(uniq >= min(12, tot), "lines are varied", "%d unique / %d spoken" % (uniq, tot))

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
