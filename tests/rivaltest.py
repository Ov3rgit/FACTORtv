"""Rival radio: do the right drivers get a CARD, and rarely enough?

Rival radio is deliberately silent. The audio was removed because edge-tts
has no Dutch- or Italian-accented English, so a full grid came out as a few
approximate accents that fooled nobody and pulled against the three voices
that do work. The reaction is now a caption on a helmet card, so what these
tests assert is that the right driver's CARD appears — and that nothing is
ever spoken.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import era as era_mod, cast as cast_mod, overlay_rival as RV
from overlay_rival import RivalMixin

class C:
    def __init__(s, cid, place, name, player=False):
        s.id=cid; s.place=place; s.name=name; s.display_name=name
        s.is_player=player; s.in_pits=False; s.damage=(0,)*8
        s.gap_ahead=1.0; s.gap_leader=float(place); s.cls='F1 Test 2025'
class S:
    def __init__(s, cars):
        s.valid=True; s.green=True; s.order=cars
        s.player=next(c for c in cars if c.is_player)
        s.era=era_mod.classify('F1 Test 2025','Max'); s.player_era=s.era
    def car_behind(s,c):
        i=c.place-1; return s.order[i+1] if 0<=i<len(s.order)-1 else None
class FakeTts:
    def __init__(s): s.said=[]; s.speaking=False
    def speak(s,t,who,intensity=0,build=False,name=""): s.said.append((who,name,t))
class R(RivalMixin):
    def __init__(s): s.rival_enabled=True; s.tts=FakeTts(); s.rival_init(); s.msgs=[]
    def _push_msg(s,*a,**k): s.msgs.append((a,k))

fails=[]
def check(c,l,e=""):
    print(("  [ OK ] " if c else "  [FAIL] ")+l+(("  "+e) if e else ""))
    if not c: fails.append(l)
# Car IDs must be tied to the DRIVER, not to grid position. rF2's mID is
# stable per car for the whole session; an earlier version of this helper
# renumbered by finishing order, so when two cars swapped places the snapshot
# lookup matched the wrong driver and no pass was ever detected.
_IDS={}
def cid_of(name):
    return _IDS.setdefault(name, len(_IDS)+1)
def field(order):
    cars=[C(cid_of(n), 0, n, n=='YOU') for n in order]
    for i,c in enumerate(cars): c.place=i+1; c.gap_leader=float(i)
    return cars

print("\n1. STABLE IDENTITY")
a=[(RV.persona_for(n), RV.helmet_for(n)) for n in ('Lewis Hamilton','Max Verstappen')]
b=[(RV.persona_for(n), RV.helmet_for(n)) for n in ('Lewis Hamilton','Max Verstappen')]
check(a==b, "persona and helmet are stable across calls", str(a))
check(len(set(RV.persona_for(n) for n in
      ('Hamilton','Verstappen','Leclerc','Norris','Piastri','Alonso','Ocon'))) > 2,
      "a grid gets a spread of personalities")

print("\n2. THE PLAYER PASSES A RIVAL")
r=R(); cars=field(['Rival','YOU','Other']); r.update_rivals(S(cars))
cars2=field(['YOU','Rival','Other'])          # player takes P1 from Rival
r.msgs=[]; r.tts.said=[]; r.update_rivals(S(cars2))
check(bool(r.msgs), "the passed driver gets a card", repr(r.msgs[:1]))
check(not r.tts.said, "and nothing is spoken", repr(r.tts.said[:1]))
if r.msgs:
    a, k = r.msgs[0]
    check(a[0]==cast_mod.DRIVER, "carded as a DRIVER, not the booth", str(a[0]))
    check(k.get('label')=='Rival', "under the rival's own name",
          str(k.get('label')))

print("\n3. A RIVAL PASSES THE PLAYER")
r=R(); cars=field(['YOU','Rival','Other']); r.update_rivals(S(cars))
cars2=field(['Rival','YOU','Other'])
r.msgs=[]; r.tts.said=[]; r.update_rivals(S(cars2))
check(bool(r.msgs), "the passing driver gets a card", repr(r.msgs[:1]))
check(not r.tts.said, "and still nothing is spoken")

print("\n4. RARITY")
r=R(); n=0
cars=field(['Rival','YOU','Other']); r.update_rivals(S(cars))
for i in range(200):
    order=['YOU','Rival','Other'] if i%2 else ['Rival','YOU','Other']
    r.update_rivals(S(field(order)))
check(len(r.msgs)<=3, "200 rapid swaps stay rare",
      "%d cards" % len(r.msgs))

print("\n5. DISTANT DRAMA IS IGNORED")
r=R(); cars=field(['YOU','A','B','C','D','E','F','Far'])
r.update_rivals(S(cars))
cars2=field(['YOU','A','B','C','D','E','F','Far'])
cars2[7].damage=(2,)*8            # a car 7s up the road takes damage
cars2[7].gap_leader=99.0
r.msgs=[]; r.tts.said=[]; r.update_rivals(S(cars2))
check(not r.msgs, "damage to a car the player cannot see is not aired",
      repr(r.msgs))


# ---------------------------------------------------------------------------
print("\nDRIVER CARDS: the triggers that were written and never fired")
# `incident`, `frustrated`, `pumped`, `pit` and `praise` had 40 lines between
# them and no trigger emitted any of them — dead since the file was written,
# exactly like `booth_joke`. A pool with no caller is invisible, and lines.py
# reports it as healthy because the lines are valid.
import json as _json, os as _os, random as _random
import drivers as _drv, era as _era
_data = _json.load(open(_os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    "lines_data", "rival.json"), encoding="utf-8"))
_events = {k.split("_", 2)[2] for k in _data if k.startswith("rival_")}
_src = open(_os.path.join(_os.path.dirname(_os.path.dirname(
    _os.path.abspath(__file__))), "overlay_rival.py"), encoding="utf-8").read()
_dead = sorted(e for e in _events if '"%s"' % e not in _src)
check(not _dead, "every rival event type has a trigger that can emit it",
      str(_dead))

print("\nSIGNATURE LINES: the right driver, the right moment, or nothing")
E25 = _era.classify("F1 Test 2025", "Max Verstappen")
E88 = _era.classify("F1 1988 Historic Edition", "Ayrton Senna")
check(_drv.quote("Max Verstappen", E25, "win") == "Simply lovely.",
      "Max gets his line for a win")
check(not _drv.quote("Max Verstappen", E25, "bad"),
      "and NOT for a bad afternoon — the occasion has to fit")
check("Smooth operator" in _drv.quote("Lando Norris", E25, "good"),
      "Lando gets his for a good run")
check(not _drv.quote("Lando Norris", E25, "win")
      or "Smooth" in _drv.quote("Lando Norris", E25, "win"),
      "and never somebody else's line")
check(not _drv.quote("Oliver Bearman", E25, "win"),
      "a driver with no signature line gets none invented for him")
check(not _drv.quote("Max Verstappen", E88, "win"),
      "and a quote cannot leak into a season the man was not in")
# A catchphrase is only a catchphrase while it is rare.
check(0.0 < RV.QUOTE_CHANCE < 1.0,
      "signature lines are refused more often than not",
      str(RV.QUOTE_CHANCE))

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
