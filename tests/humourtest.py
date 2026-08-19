"""Jokes, banter and digs — and, mostly, when the booth must not make one.

Asked for directly: "wheres the jokes and banter and little digs? its nice to
have some comedic moments on track".

The cost of this feature is asymmetric and that is what the suite is shaped
around. A joke that lands adds a little; a joke over a driver sitting in a
wrecked car destroys the illusion in one line and nothing afterwards repairs
it. So most of what follows asserts SILENCE, and the one test that asserts a
joke actually happens is nearly the shortest in the file.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import era as era_mod, cast as cast_mod, lines as lines_mod
from overlay_common import safe_format
from overlay_booth import (BoothMixin, HUMOUR_CATS, HUMOUR_FAMILY_GAP,
                           LEVITY_AFTER_INCIDENT, DIG_WIDE_OFFS, LONG_FIGHT,
                           STRIKE_GAP)

fails=[]
def check(c,l,e=""):
    print(("  [ OK ] " if c else "  [FAIL] ")+l+(("  "+e) if e else ""))
    if not c: fails.append(l)

E = era_mod.classify("F1 Test 2025", "Max Verstappen")

class FakeTts:
    def __init__(s): s.said=[]; s.speaking=False
    def speak(s,t,who,intensity=0,build=False,name=""): s.said.append((who,t))
class Booth(BoothMixin):
    def __init__(s):
        s.booth_enabled=True; s.tts=FakeTts(); s.tracker=None; s.sting_bank=None
        s.booth_init(); s.season=None; s._season_round=None
    def _short_track(s,n): return n
    def _hide_panel(s,n): pass
    def _show_caption(s,t,w,n): pass
class Car:
    def __init__(s,i,n,p):
        s.id=i; s.name=n; s.display_name=n; s.place=p; s.started_place=p
        s.cls="F1"; s.in_pits=False; s.gap_ahead=2.0; s.gap_leader=2.0*(p-1)
        s.is_player=(p==4); s.damage=(0,)*8; s.speed=200.0; s.laps=10
        s.places_gained=0; s.best_lap=90.0; s.last_lap=90.5; s.surface=(0,)*4
        s.wheels_off=0; s.tyre_wear=(1.0,)*4
class S:
    def __init__(s, names, **kw):
        s.order=[Car(i,n,i+1) for i,n in enumerate(names)]
        s.player=next((c for c in s.order if c.is_player), s.order[0])
        s.leader=s.order[0]; s.era=E; s.player_era=E; s.circuit=None
        s.track="Zandvoort"; s.kind="race"; s.green=True; s.max_laps=40
        s.leader_laps=20; s.laps_left=20; s.full_course_yellow=False
        s.valid=True; s.finished=False; s.on_air=True; s.started=True
        s.num_cars=len(s.order); s.time_left=None; s.best_lap_time=90.0
        s.multiclass=False; s.classes=["F1"]; s.yellow_sectors=(0,0,0)
        for k,v in kw.items(): setattr(s,k,v)
    def car_ahead(s,c):
        i=c.place-1
        return s.order[i-1] if 0<i<len(s.order) else None
NAMES=["Verstappen","Norris","Leclerc","Hamilton","Piastri","Russell",
       "Sainz","Albon","Alonso","Gasly"]

def fresh():
    """A booth mid-race with nothing wrong, which is the only state that
    permits a joke at all."""
    b=Booth(); b._phase="mid"
    # Nothing has gone wrong for a long time. `_sting_at` starts at 0.0 and
    # time.time() is enormous, so the incident gate is already open.
    return b

print("\n1. THE POOLS EXIST AND ARE NOT THIN")
sizes={c:len(lines_mod.pool(c)) for c in HUMOUR_CATS}
check(all(v>=6 for v in sizes.values()), "every humour pool has 6+ lines",
      str(sizes))
check(sizes["booth_joke"]>=15,
      "and the general pool is big enough not to repeat inside a season",
      str(sizes["booth_joke"]))
# `booth_joke` existed with five lines and was never offered by any filler —
# dead code that had never aired. It must be reachable now, and it must not
# be defined in two files at once (the loader EXTENDS across files).
import json, glob
dupes=[f for f in glob.glob(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "lines_data", "*.json"))
       if "booth_joke" in json.load(open(f,encoding="utf-8"))]
check(len(dupes)==1, "booth_joke is defined in exactly one file",
      str([os.path.basename(f) for f in dupes]))

print("\n2. THE LEVITY GATE — when a joke is FORBIDDEN")
now=time.time()
b=fresh()
check(b._levity_ok(S(NAMES), now), "a normal mid-race moment permits levity")

b=fresh(); b._sting_at=now-5.0
check(not b._levity_ok(S(NAMES), now),
      "not five seconds after an alert nobody has explained yet")
b=fresh(); b._sting_at=now-(LEVITY_AFTER_INCIDENT-1)
check(not b._levity_ok(S(NAMES), now),
      "and not until the whole quiet period has passed")
b=fresh(); b._sting_at=now-(LEVITY_AFTER_INCIDENT+1)
check(b._levity_ok(S(NAMES), now), "...after which it is allowed again")

b=fresh(); b._incidents=[now-10.0]
check(not b._levity_ok(S(NAMES), now),
      "not just after an incident, whoever it happened to")
b=fresh(); b._yellow_on=True
check(not b._levity_ok(S(NAMES), now), "not under a yellow flag")
b=fresh()
check(not b._levity_ok(S(NAMES, full_course_yellow=True), now),
      "nor a full course yellow")
b=fresh(); b._phase="closing"
check(not b._levity_ok(S(NAMES), now), "not on the last lap of anything")

print("\n3. ...AND NOT WHILE THE PLAYER IS HAVING A BAD TIME")
# He is the one man on the grid who cannot be the joke, because he is the one
# actually living it.
b=fresh(); b.player_off=("spin", now)
check(not b._levity_ok(S(NAMES), now), "not while the player is off")
b=fresh(); s=S(NAMES); s.player.damage=(0,0,3,0,0,0,0,0)
check(not b._levity_ok(s, now), "not while his car is damaged")
b=fresh(); s=S(NAMES); s.player.in_pits=True
check(not b._levity_ok(s, now), "not while he is in the pit lane")
# ...but being SLOW is not a misfortune, it is racing.
b=fresh(); s=S(NAMES); s.player.place=10; s.player.gap_leader=90.0
check(b._levity_ok(s, now),
      "though being nowhere near the front is fair game, as it should be")

print("\n4. A RACE THAT HAS NOT SETTLED IS NOT FUNNY YET")
b=fresh()
check(not b._levity_ok(S(NAMES, leader_laps=0, max_laps=40), now),
      "lap one is busy, not funny")
check(not b._levity_ok(S(NAMES, leader_laps=1, max_laps=40), now),
      "and neither is lap two")
check(b._levity_ok(S(NAMES, leader_laps=6, max_laps=40), now),
      "by a few laps in the race has a shape and a joke has somewhere to sit")

print("\n5. THE TITLE DECIDER")
# The one broadcast where the tension IS the product. Silent for the whole
# late phase, not just the closing lap.
class FakeCareer(object):
    def __init__(s, left): s._left=left
    def title_state(s): return {"rounds_left": s._left, "decided": False}
class OpenCareer(object):
    def title_state(s): return {"rounds_left": None, "decided": False}
b=fresh(); b._phase="late"
check(b._levity_ok(S(NAMES), now),
      "the late phase of an ordinary race still allows a light moment")
b=fresh(); b._phase="late"; b.season=FakeCareer(1); b._season_round={"n":9}
check(not b._levity_ok(S(NAMES), now),
      "but the late phase of a title decider does not")
b=fresh(); b._phase="mid"; b.season=FakeCareer(1); b._season_round={"n":9}
check(b._levity_ok(S(NAMES), now),
      "though the middle of one is still a race like any other")
# LAW 4 survives: an open season with no declared length cannot know whether
# this is a decider, and an unknown is not one.
b=fresh(); b._phase="late"; b.season=OpenCareer(); b._season_round={"n":3}
check(b._levity_ok(S(NAMES), now),
      "and a season that cannot count its rounds never claims to be a decider")

print("\n6. THE FAMILY GATE (LAW 15)")
# Five correct categories that are all "the booth being light". Back to back
# they are a comedy show with a race on in the background.
b=fresh(); s=S(NAMES)
first=b._levity(s, now)
check(first, "levity is offered when everything allows it",
      "%d offered" % len(first))
check(all(c in HUMOUR_CATS for c,_,_ in first), "all of it in the family")
b._cat_last["booth_joke"]=now
check(not b._levity(s, now+5.0),
      "and the whole family goes quiet after any one of them airs")
check(b._levity(s, now+HUMOUR_FAMILY_GAP+1.0),
      "coming back only when the family gap has passed")

print("\n7. A DIG AT A DRIVER MUST BE GROUNDED IN SOMETHING SEEN")
# The difference between a joke and a sneer is whether the viewer watched the
# same thing. Nothing observed, no dig.
b=fresh(); s=S(NAMES)
cats=[c for c,_,_ in b._levity(s, now)]
check("dig_stuck" not in cats and "dig_wide" not in cats,
      "a clean race produces no digs at anybody", str(cats))
# Stuck: twice the threshold that already earns a "sustained battle" call.
b=fresh(); s=S(NAMES)
s.order[1].gap_ahead=0.6
b._battle_since[s.order[1].id]=(now-(LONG_FIGHT*2+5), s.order[0].id)
cats=[c for c,_,_ in b._levity(s, now)]
check("dig_stuck" in cats,
      "a stalemate the viewer is also bored of earns one", str(cats))
kw=next(kw for c,kw,_ in b._levity(s, now) if c=="dig_stuck")
check(kw.get("a") and kw.get("b"),
      "naming both cars in it", "%s / %s" % (kw.get("a"), kw.get("b")))
# Wide: three separate excursions, not two.
b=fresh(); s=S(NAMES); b._off_count={s.order[5].id: DIG_WIDE_OFFS-1}
check("dig_wide" not in [c for c,_,_ in b._levity(s, now)],
      "two offs is unlucky and draws nothing")
b=fresh(); s=S(NAMES); b._off_count={s.order[5].id: DIG_WIDE_OFFS}
ev=[(c,kw) for c,kw,_ in b._levity(s, now) if c=="dig_wide"]
check(ev, "three is a pattern, and the booth may notice it out loud")
if ev:
    check(ev[0][1].get("drv")=="Russell",
          "about the right driver", str(ev[0][1].get("drv")))
# A car in the pits is not on screen to be teased.
b=fresh(); s=S(NAMES); s.order[5].in_pits=True
b._off_count={s.order[5].id: DIG_WIDE_OFFS+2}
check("dig_wide" not in [c for c,_,_ in b._levity(s, now)],
      "and never about a car that is not out there to be seen")

print("\n8. EVERY LINE RENDERS, AND STANDS ALONE")
kw={"a":"Norris","b":"Verstappen","drv":"Russell","trk":"Zandvoort","lap":12}
bad=[]
for cat in HUMOUR_CATS:
    for e in lines_mod.candidates(cat, E):
        t=lines_mod._sentence_case(safe_format(e["t"], kw))
        if "{" in t or "  " in t or " ," in t or t[:1].islower():
            bad.append((cat,t[:60]))
check(not bad, "every humour line renders cleanly", str(bad[:2]))
orphans=[]
for cat in HUMOUR_CATS:
    for e in lines_mod.pool(cat):
        t=(e["t"] if isinstance(e,dict) else e).lstrip().lower()
        if t.startswith(("and ","but ","so ","which ","either ","neither ",
                         "also ","that's why")):
            orphans.append((cat,t[:50]))
check(not orphans, "and every one of them works as the first thing said",
      str(orphans[:2]))

print("\n9. WHO IS ALLOWED TO BE FUNNY, AND ABOUT WHOM")
check(cast_mod.who_says("booth_dig")==cast_mod.PLAY,
      "ribbing the analyst belongs to the play-by-play seat")
check(not cast_mod.can_say(cast_mod.ANALYST,"booth_dig"),
      "and Chuck cannot dig at himself")
check(cast_mod.can_say(cast_mod.HISTORIC_PLAY,"booth_dig"),
      "while Brett inherits it, so a historic race is not humourless")
for c in ("booth_joke","analyst_dig","dig_stuck","dig_wide"):
    check(cast_mod.who_says(c)==cast_mod.ANALYST,
          "%s is the analyst's" % c)
# Chuck has never driven a Formula One car. A joke may not rest on having.
fp=[]
for cat in HUMOUR_CATS:
    for e in lines_mod.pool(cat):
        d=e if isinstance(e,dict) else {"t":e}
        if "stock" in (d.get("disc") or ()):
            continue          # his own discipline, where he may speak from it
        low=d["t"].lower()
        for claim in ("i drove","when i raced","i remember driving","in my day",
                      "we called it","i've driven","back when i","i raced"):
            if claim in low:
                fp.append((cat,d["t"][:55]))
check(not fp, "and no ungated joke has him claiming a career he did not have",
      str(fp[:2]))

print("\n10. NOTHING HERE IS ACTUALLY NASTY")
# Real people, several of them dead, and the booth likes all of them.
CRUEL=("idiot","stupid","fool","clown","useless","pathetic","hopeless",
       "amateur","embarrassing","disgrace","joke of a","can't drive",
       "shouldn't be","doesn't belong","fat","old man","kid should")
mean=[]
for cat in HUMOUR_CATS:
    for e in lines_mod.pool(cat):
        low=(e["t"] if isinstance(e,dict) else e).lower()
        for word in CRUEL:
            if word in low:
                mean.append((cat,low[:55]))
check(not mean, "no line reads as contempt rather than affection",
      str(mean[:2]))

print("\n11. AND THE WHOLE THING, THROUGH THE REAL FILLER PATH")
b=fresh(); s=S(NAMES)
allcats=[c for c,_,_ in b._filler(s, now)]
check(any(c in HUMOUR_CATS for c in allcats),
      "the race filler reaches the humour pools",
      str([c for c in allcats if c in HUMOUR_CATS]))
# ...and stops reaching them the moment something goes wrong.
b=fresh(); b._incidents=[now-2.0]
allcats=[c for c,_,_ in b._filler(s, now)]
check(not any(c in HUMOUR_CATS for c in allcats),
      "and offers not one of them while an incident is fresh", str(allcats[:4]))
# The ranking is NOT what protects this. Prove the gate is upstream of it.
check(b._levity(s, now)==[],
      "the veto is upstream of the ranking, not a matter of losing the tick")

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
