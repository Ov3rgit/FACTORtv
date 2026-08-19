"""Headless engineer test: does Dean say the right thing, and stay quiet otherwise?

The interesting assertions are the SILENCE ones. An engineer who reports a
steady state every lap gets muted, at which point he conveys nothing.
    python tests/radiotest.py
"""
import os, sys, time
import re as _re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import era as era_mod, cast as cast_mod
from overlay_radio import RadioMixin
from overlay_dash import FuelModel

class C:
    def __init__(s, cid=1, place=5, name='Driver'):
        s.id=cid; s.place=place; s.display_name=name; s.name=name
        s.in_pits=False; s.laps=10; s.gap_ahead=2.0; s.gap_behind=2.0
        s.fuel=40.0; s.fuel_cap=100.0; s.last_lap=90.0; s.best_lap=89.5
        s.purple_lap=False; s.penalties=0; s.damage=(0,)*8
        s.tyre_wear=(0.9,0.9,0.85,0.85); s.tyre_temp=(90,92,95,94)
        s.brake_temp=(400,410,380,390); s.places_gained=0; s.is_player=True
        s.cls='F1 Test 2025'; s.vehicle='Max Verstappen'; s.finish_status=0
class S:
    def __init__(s, me, others=None, **kw):
        s.valid=True; s.player=me; s.order=[me]+(others or [])
        for i,c in enumerate(s.order): c.place=i+1
        s.kind='race'; s.green=True; s.finished=False; s.track='Zandvoort'
        s.max_laps=30; s.laps_left=15; s.leader_laps=15; s.num_cars=len(s.order)
        s.session_index=10; s.full_course_yellow=False; s.yellow_sectors=(0,0,0)
        s.era=era_mod.classify('F1 Test 2025','Max'); s.player_era=s.era
        for k,v in kw.items(): setattr(s,k,v)
    def car_ahead(s,c):
        i=c.place-1; return s.order[i-1] if 0<i<len(s.order) else None
    def car_behind(s,c):
        i=c.place-1; return s.order[i+1] if 0<=i<len(s.order)-1 else None
class FakeTts:
    def __init__(s): s.said=[]; s.speaking=False
    def speak(s,text,who,intensity=0,build=False,name=""): s.said.append((who,text))
class R(RadioMixin):
    def __init__(s):
        s.radio_enabled=True; s.tts=FakeTts(); s.fuel_model=FuelModel()
        s.fuel_model.laps=[2.5,2.5,2.5]; s.show_dash=False; s.radio_init()
    def _hide_panel(s,n): pass

fails=[]
def check(c,l,e=""):
    print(("  [ OK ] " if c else "  [FAIL] ")+l+(("  "+e) if e else ""))
    if not c: fails.append(l)
def run(r, s, ticks=1, advance=0.0):
    for _ in range(ticks):
        if advance:
            r._radio_last-=advance
            for k in list(r._topic_last): r._topic_last[k]-=advance
        r.update_radio(s)

print(chr(10) + "1. THE FIRST WORD OF EACH SESSION")
# A RACE gets no greeting: the gap between going on air and lights out is a
# few seconds and the booth owns them. His first word comes AFTER the start,
# when there is something to say about how it actually went.
r=R(); me=C(); run(r,S(me))
first = r.tts.said[:1]
check(bool(first), "he speaks once the race is under way", repr(first))
check(not any(w in first[0][1].lower() for w in ("radio check", "morning"))
      if first else False,
      "and it is not a greeting", repr(first))

# QUALIFYING is where a greeting belongs — there is room for it there.
r2=R(); me2=C(); run(r2,S(me2,kind="quali"))
check(bool(r2.tts.said), "qualifying does get one", repr(r2.tts.said[:1]))
print("\n2. SILENCE ON STEADY STATE")
r=R(); me=C(); run(r,S(me)); run(r,S(me),advance=100)
r.tts.said=[]
run(r,S(me),ticks=300,advance=100)   # nothing changes, 300 ticks
n=len(r.tts.said)
check(n<=6, "300 unchanging ticks stay near-silent", "%d calls" % n)

print("\n3. FUEL — only on state CHANGE")
r=R(); me=C(); run(r,S(me)); run(r,S(me),advance=100); r.tts.said=[]
me.fuel=20.0                      # 15 laps x 2.5 = 37.5 needed -> critical
run(r,S(me),advance=100)
# Prose matching again (LAW 7), and the shuffle bag persists in _bag.json, so
# a narrow keyword list fails only on the runs that happen to draw the wrong
# line. "This is serious on fuel - 7 laps down" is a perfectly good critical
# call containing none of critical/save/short.
crit=[t for _,t in r.tts.said
      if any(w in t.lower() for w in ('critical','save','short','fuel','litres'))]
check(bool(crit), "fuel shortfall is called", repr(r.tts.said[-1:]))
r.tts.said=[]
run(r,S(me),ticks=200,advance=100)  # still critical, unchanged
again=[t for _,t in r.tts.said if 'fuel' in t.lower() or 'save' in t.lower()]
check(len(again)==0, "does not repeat while the state is unchanged", repr(again[:2]))

print("\n4. TYRE HYSTERESIS")
r=R(); me=C(); run(r,S(me)); run(r,S(me),advance=100); r.tts.said=[]
worn=0
for w in (0.50,0.44,0.46,0.44,0.47,0.43,0.46,0.44):   # oscillating on the line
    me.tyre_wear=(w,w,w,w); run(r,S(me),advance=100)
worn=len([t for _,t in r.tts.said if 'tyre' in t.lower() or 'deg' in t.lower() or 'front' in t.lower()])
check(worn<=1, "a tyre hovering on the threshold is reported once", "%d calls" % worn)

print("\n5. DEFEND uses the strike gap")
# Matching on prose is fragile (LAW 7) — every defend line has to contain one
# of these words or the test fails on a perfectly good new line. It is shared
# with section 8 so there is only one list to keep honest.
DEFEND_WORDS = ('behind', 'mirrors', 'defend', 'cover', 'on you',
                'have a look', 'difficult', "he's there")
def _defends(said):
    return [t for _, t in said
            if any(w in t.lower() for w in DEFEND_WORDS)]
r=R(); me=C(); rival=C(2,2,'Rival')
r2=S(me,[rival]); run(r,r2); run(r,r2,advance=100); r.tts.said=[]
rival.gap_ahead=0.4               # right on the player's tail
run(r,S(me,[rival]),advance=100)
check(bool(_defends(r.tts.said)),
      "close car behind triggers a defend call", repr(r.tts.said[-1:]))

print("\n6. ERA GATING (1966 car must never hear DRS/ERS)")
r=R(); me=C(); e66=era_mod.classify('','Brabham_1966')
s=S(me); s.era=s.player_era=e66
run(r,s); run(r,s,advance=100); r.tts.said=[]
for i in range(120):
    me.gap_ahead=0.5; me.tyre_wear=(0.3,)*4; me.fuel=10.0
    s=S(me); s.era=s.player_era=e66; run(r,s,advance=100)
bad=[t for _,t in r.tts.said if any(w in t.lower() for w in ('drs','push-to-pass','deployment','recharge'))]
check(not bad, "no anachronisms in %d radio calls" % len(r.tts.said), repr(bad[:2]))

print("\n8. DEFEND IS ONCE PER THREAT, NOT ONCE PER COOLDOWN")
# A car sitting behind you stays behind you. Before the edge-trigger the topic
# cooldown alone let this air 13 times in one race.
r=R(); me=C(); rival=C(2,2,'Rival')
run(r,S(me,[rival])); run(r,S(me,[rival]),advance=100); r.tts.said=[]
for _ in range(60):                    # ~10 minutes of him sitting on your tail
    rival.gap_ahead=0.4; run(r,S(me,[rival]),advance=100)
n=len(_defends(r.tts.said))
check(n==1, "a persistent car behind is called ONCE", "%d calls" % n)

r.tts.said=[]
for _ in range(10):                    # he drops away...
    rival.gap_ahead=4.0; run(r,S(me,[rival]),advance=100)
for _ in range(10):                    # ...and comes back
    rival.gap_ahead=0.4; run(r,S(me,[rival]),advance=100)
n=len(_defends(r.tts.said))
check(n==1, "a threat that leaves and returns is called again", "%d calls" % n)

r.tts.said=[]
for w in (0.4,0.9,0.5,1.0,0.6,0.85,0.45):   # oscillating across STRIKE_GAP
    rival.gap_ahead=w; run(r,S(me,[rival]),advance=100)
n=len(_defends(r.tts.said))
check(n==0, "a gap chattering around the strike line does not re-arm",
      "%d calls" % n)

print("\n7. ONLY THE ENGINEER SPEAKS")
who=set(w for w,_ in r.tts.said)
check(who=={cast_mod.ENGINEER} or not who, "all radio is from the engineer", str(who))

print("\nHOW HE SOUNDS — the register, not the repetition")
# Half of "monotone and a bit robotic" was repetition and is fixed by the
# hysteresis and the topic budget. The other half was his REGISTER: 381 lines
# averaging eight words, a quarter using the driver's name. That is a
# dashboard being read aloud, and the fix is framing rather than length.
import random as _random
import overlay_radio as _RV
_random.seed(1)
_framed = []
for _ in range(400):
    r._framed_last = False
    out = r._frame("Watch the brakes, they're getting warm.", {"drv": "Lewis"}, 25)
    if out != "Watch the brakes, they're getting warm.":
        _framed.append(out)
check(_framed, "an ordinary call is sometimes framed")
check(len(_framed) < 400, "and sometimes left bare — the variation is the point",
      "%d of 400" % len(_framed))
# GRAMMAR. "Right, That's your quickest" was the bug: `"That's".isalpha()` is
# False because of the apostrophe, so the lowercasing silently skipped.
bad = [t for t in _framed
       if _re.search(r"^[A-Z][a-z]+[ ,]+[A-Z][a-z]", t) and "Lewis" not in t]
check(not bad, "with the original first word correctly lowercased", str(bad[:2]))
# ACRONYMS AND SLOTS MUST SURVIVE.
r._framed_last = False
drs = [r._frame("DRS enabled. Use it on the straight.", {"drv": "Lewis"}, 25)
       for _ in range(60)]
check(not any("drs enabled" in t for t in drs),
      "an acronym is never lowercased into nonsense")
r._framed_last = False
slot = [r._frame("{rival} is right behind you.", {"drv": "Lewis"}, 25)
        for _ in range(60)]
check(all("{rival}" in t for t in slot),
      "and a line opening on a slot is left alone")
# URGENCY. "Okay Lewis, you have just been hit" is a man reading from a card.
r._framed_last = False
urgent = set(r._frame("Fuel critical. We will not make the flag like this.",
                      {"drv": "Lewis"}, 85) for _ in range(50))
check(urgent == {"Fuel critical. We will not make the flag like this."},
      "an urgent call is never framed — he just says the thing")
# NOTHING ACKNOWLEDGES THE DRIVER. Rival and driver radio were removed, so
# the player never transmits and there is nothing for Dean to reply to.
check(not any(o.lower().startswith(("understood", "copy"))
              for o in _RV.ENG_OPENERS),
      "and no opener replies to a driver who never transmits",
      str(_RV.ENG_OPENERS))

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
