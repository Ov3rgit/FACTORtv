"""The race story: how a driver's afternoon has gone, and the wrap.

The complaint this answers: the booth held eight conversations in a
fifty-two minute race and not one of them was about a driver, and the wrap
was four lines that said nothing about how anybody had actually driven.

The rule underneath all of it: an Arc states only what was MEASURED, and
`headline()` returns None when a driver's race has no shape. A generic "he
has had a solid afternoon" about a man who finished where he started is the
padding this system exists to avoid.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import story as story_mod, lines as lines_mod, cast as cast_mod
import era as era_mod, season as season_mod
from overlay_common import safe_format
from overlay_booth import POST_RACE, STORY_FOCUS
from fakes import Booth, FakeSession, grid

fails=[]
def check(c,l,e=""):
    print(("  [ OK ] " if c else "  [FAIL] ")+l+(("  "+e) if e else ""))
    if not c: fails.append(l)

E = era_mod.classify("F1 Test 2025", "Max Verstappen")
E88 = era_mod.classify("F1 1988 Historic Edition", "Ayrton Senna")

def arc(**kw):
    class C:
        id=1; display_name=kw.pop("name","Driver"); name=display_name
        in_pits=False; retired=kw.pop("retired",False)
    return story_mod.Arc(C(), **kw)

print("\n1. AN ARC IS MEASURED, NOT INFERRED")
a = arc(name="Hamilton", grid=12, place=4, best=4, worst=14)
check(a.gained==8 and a.recovered==10 and a.slid==0,
      "gained, recovered and slid are all read off real positions",
      "+%d gained, %d recovered" % (a.gained, a.recovered))
check(arc(grid=0, place=4).gained==0,
      "no grid slot means no claim about places gained")
check(arc(grid=3, place=3).headline()=="story_holding",
      "a driver who started and finished third has held, not charged")
check(arc(grid=7, place=7, offs=1).headline() is None,
      "and one with a single off and no movement has NO story at all")

print("\n2. THE HEADLINE PICKS THE TRUEST THING")
CASES = [
    ("a recovery drive",      dict(grid=12, place=4, best=4, worst=14), "story_recovery"),
    ("a charge from the back",dict(grid=14, place=6, best=6, worst=14), "story_recovery"),
    ("a steady climb",        dict(grid=9,  place=3, best=3, worst=9),  "story_recovery"),
    ("a slide, no mistakes",  dict(grid=2,  place=8, best=2, worst=8),  "story_slide"),
    ("a slide he caused",     dict(grid=2,  place=8, best=2, worst=8, offs=3), "story_undone"),
    ("scruffy but even",      dict(grid=6,  place=6, best=5, worst=7, offs=3), "story_scrappy"),
    ("led the whole way",     dict(grid=1,  place=1, best=1, worst=1, led=30), "story_led"),
    ("out of the race",       dict(grid=4,  place=18, retired=True),    "story_out"),
    ("small progress",        dict(grid=8,  place=6, best=6, worst=8),  "story_progress"),
    ("small loss",            dict(grid=6,  place=8, best=6, worst=8),  "story_losing"),
]
bad=[(l,e,arc(**k).headline()) for l,k,e in CASES if arc(**k).headline()!=e]
check(not bad, "%d race shapes all resolve correctly" % len(CASES), str(bad[:2]))

print("\n3. A DRIVER WITH NOTHING TO SAY GETS NOTHING SAID")
# The most important negative in the file. A booth that always has an answer
# is a booth reading a script.
quiet = [arc(grid=g, place=g, best=g, worst=g) for g in range(4, 12)]
check(all(a.headline()=="story_holding" for a in quiet),
      "holding position is the ONLY thing said about an uneventful race")
check(arc(grid=0, place=0).headline() is None,
      "and a driver we know nothing about produces no line at all")

print("\n4. INTEREST IS NOT POSITION")
# A man in fourteenth who has climbed nine places is a better story than the
# man who has been third all afternoon — and the second is already covered by
# every other category the booth has.
b = Booth(); cars = grid()
for c in cars: c.gap_ahead=3.0; c.gap_leader=3.0*(c.place-1)
cars[9].started_place = 18
b._story = {cars[9].id: {"best":10,"worst":18,"now":10},
            cars[2].id: {"best":3,"worst":3,"now":3}}
s = FakeSession(cars, max_laps=40, leader_laps=20, laps_left=20)
order = [a.name for a in story_mod.field(b, s, top=STORY_FOCUS)]
check(order and order[0]=="Norris",
      "the recovery drive in tenth outranks the man who has held third",
      str(order[:3]))

print("\n5. EVERY ANSWER RENDERS, AND IS THE ANALYST'S")
POOLS = [c for c in
         ("story_recovery","story_charge","story_slide","story_undone",
          "story_scrappy","story_led","story_dropping","story_progress",
          "story_losing","story_holding","story_out","story_from_quali")]
sizes = {c: len(lines_mod.pool(c)) for c in POOLS}
check(all(v>=3 for v in sizes.values()), "every story pool has lines", str(sizes))
kw = {"drv":"Hamilton","pos":"fourth","grid":"twelfth","best":"second",
      "worst":"fourteenth","n":"eight places","offs":"three times"}
bad=[]
for c in POOLS + ["story_ask","wrap_ask_impressed","wrap_impressed"]:
    for e in lines_mod.candidates(c, E):
        t = lines_mod._sentence_case(safe_format(e["t"], kw))
        if "{" in t or "  " in t or " ," in t or t[:1].islower():
            bad.append((c, t[:60]))
check(not bad, "every story line renders cleanly", str(bad[:2]))
check(all(cast_mod.who_says(c)==cast_mod.ANALYST for c in POOLS),
      "every answer is Chuck's — they are judgements about driving")
check(cast_mod.who_says("story_ask")==cast_mod.PLAY
      and not cast_mod.can_say(cast_mod.ANALYST,"story_ask"),
      "and the question is Miles's — a man does not ask himself")

print("\n6. IT WORKS IN EVERY ERA, INCLUDING THE HISTORIC SEAT")
# A race story is the one thing about this sport that has never changed, so
# nothing here may name a piece of equipment, a regulation or a decade.
thin = [c for c in POOLS if len(lines_mod.candidates(c, E88)) <
        len(lines_mod.candidates(c, E))]
check(not thin, "no story line is gated away from a 1988 field", str(thin))
check(all(cast_mod.can_say(cast_mod.HISTORIC_PLAY, c)
          for c in ("story_ask","wrap_ask_impressed")),
      "and Brett can ask the question, so a classic race gets the same system")

print("\n7. THE BOOTH ASKS, AND CHUCK ANSWERS, IN ONE BREATH")
b = Booth(); cars = grid()
for c in cars: c.gap_ahead=3.0; c.gap_leader=3.0*(c.place-1)
cars[3].started_place = 12
b._story = {cars[3].id: {"best":4,"worst":14,"now":4}}
s = FakeSession(cars, max_laps=40, leader_laps=20, laps_left=20)
now = time.time()
b._last_spoke = 0
check(b._story_report(s, now), "a driver with a story gets reported on")
said = b.tts.said
check(len(said)==2, "as an exchange, not a statement", str(len(said)))
if len(said)==2:
    check(said[0][0]==cast_mod.PLAY and said[1][0]==cast_mod.ANALYST,
          "question from the booth, answer from the analyst")
    check("Hamilton" in said[0][1],
          "the question names the driver", said[0][1])
    check(len(said[1][1].split())>=12,
          "and the answer is a real answer, not one statement and a full stop",
          "%d words" % len(said[1][1].split()))

print("\n8. ONE REPORT PER DRIVER PER RACE")
b._last_spoke = 0
b._cat_last["story_ask"] = 0
b.tts.said = []
b._story_report(s, now + 400)
again = [t for _w, t in b.tts.said if "Hamilton" in t]
check(not again, "the same driver is not reported on twice", str(again[:1]))

print("\n9. A RACE THAT HAS NOT HAPPENED YET GETS NO REPORT")
b2 = Booth(); b2._last_spoke = 0
early = FakeSession(cars, max_laps=40, leader_laps=1, laps_left=39)
check(not b2._story_report(early, time.time()),
      "nothing to report on lap two, because nothing has happened")

print("\n10. THE WRAP HAS THE BEATS IT WAS MISSING")
check("topraces" in POST_RACE and "impressed" in POST_RACE,
      "the wrap covers how the podium drove and who else impressed",
      str(POST_RACE))
check(POST_RACE.index("topraces") < POST_RACE.index("championship"),
      "the racing is described before the scoreboard is read")

class Career(object):
    def __init__(s, rounds, length=10):
        s.rounds=rounds; s.data={"length":length}; s.me="Verstappen"
        s.total_rounds=length
    def points_for(s,p):
        t=[25,18,15,12,10,8,6,4,2,1]
        return t[p-1] if 0<p<=len(t) else 0
    def next_round(s): return {"n":len(s.rounds)+1}
    uses_quali=True
    standings=season_mod.Career.standings
    title_state=season_mod.Career.title_state

b3 = Booth(); cars = grid()
for c in cars: c.gap_ahead=1.5; c.gap_leader=1.5*(c.place-1)
cars[1].started_place=9; cars[6].started_place=16
b3._story={cars[1].id:{"best":2,"worst":11,"now":2},
           cars[6].id:{"best":7,"worst":16,"now":7}}
G=["Verstappen","Russell","Leclerc","Hamilton"]
b3.season = Career([{"n":n,"classified":[[x,i+1] for i,x in enumerate(G)]}
                    for n in (1,2,3)])
b3._season_round={"n":3}
fin = FakeSession(cars, max_laps=40, leader_laps=40, laps_left=0, finished=True)
b3._post = list(POST_RACE); t = time.time()
while b3._post:
    b3._post_stage(fin, t); t += 6.0
txt = [x for _w, x in b3.tts.said]
check(len(txt) >= 6, "the wrap is more than four lines now",
      "%d lines" % len(txt))
check(any("Ocon" in x for x in txt),
      "somebody outside the podium is named as the drive of the day",
      str([x for x in txt if "Ocon" in x][:1]))
check(not any("Ocon" in x and "Verstappen" in x for x in txt),
      "and the winner is not offered as the drive of the day")
# STRUCTURAL, NOT KEYWORD-MATCHED — and this is the SECOND time in one
# session that grepping the rendered prose produced a flaky test. The bag
# persists across runs, so a different line is drawn each time, and one of
# the four `champ_closes` lines ("The gap comes down to...") is perfectly
# correct while containing neither word. Ask which CATEGORY was chosen.
cat_c, kw_c = b3._championship_call(fin)
check(cat_c in ("champ_extends", "champ_closes"),
      "the wrap draws a real championship implication", str(cat_c))
check(kw_c.get("pts") and kw_c.get("left"),
      "carrying the exact gap and the rounds remaining",
      "%s points, %s" % (kw_c.get("pts"), kw_c.get("left")))

print("\n11. THE CHAMPIONSHIP IMPLICATION OBEYS LAW 4")
# An open season with no declared length cannot count its rounds, so it must
# not claim anything about what the result means.
b4 = Booth()
b4.season = Career([{"n":n,"classified":[[x,i+1] for i,x in enumerate(G)]}
                    for n in (1,2,3)], length=0)
b4._season_round={"n":3}
cat, kw2 = b4._championship_call(fin)
check(cat not in ("champ_extends","champ_closes"),
      "a season that cannot count its rounds makes no claim about them", str(cat))

print("\n12. QUALIFYING IS REMEMBERED INTO THE RACE")
note = story_mod.quali_note(1, 20, late=True, improved=0)
check(note and note["notable"], "pole taken late is worth remembering")
check(not story_mod.quali_note(11, 20, late=False, improved=0)["notable"],
      "an ordinary session is not brought up on lap forty")
check(story_mod.quali_note(4, 20, late=False, improved=5)["notable"],
      "but a big climb late in the session is")
b5 = Booth()
b5._quali_story = {story_mod._key("Norris"): note}
a5 = story_mod.of(b5, s, cars[9])
check(a5.quali is not None and a5.quali["notable"],
      "and the arc carries it into the race by NAME, which survives the "
      "session change")

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
