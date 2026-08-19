"""Real-world driver knowledge: is it TRUE, is it gated, and does it air?

The premise of this whole feature is that a false claim about Senna costs
more than silence about Senna, so most of what follows tests the refusal
paths rather than the happy one. A booth that says nothing passes half of
these tests by default, and that is deliberate — the failure this suite
exists to catch is a confident wrong sentence, not a missing one.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import drivers as drv_mod, era as era_mod, cast as cast_mod, lines as lines_mod
from overlay_booth import BoothMixin, DRIVER_CATS, DRIVER_FAMILY_GAP

fails=[]
def check(c,l,e=""):
    print(("  [ OK ] " if c else "  [FAIL] ")+l+(("  "+e) if e else ""))
    if not c: fails.append(l)

drv_mod.load()

# The eras the user actually tests on, built the way the game builds them —
# 2021 through the constructor list, because that mod names a class per team
# and dating it from the team names is the only thing that works.
E88   = era_mod.classify("F1 1988 Historic Edition", "Ayrton Senna")
E21   = era_mod.classify("McLaren", "Lando Norris", field_classes=[
    "McLaren","Ferrari","Mercedes","Red Bull","Alpine","Aston Martin","Haas",
    "Williams","Alfa Romeo","Alpha Tauri"])
E25   = era_mod.classify("F1 Test 2025", "Max Verstappen")
E92   = era_mod.classify("Formula 1 1992 Season by ASRC", "Nigel Mansell")
EGT3  = era_mod.classify("BMW M4 GT3 2021", "Some Driver")

print("\n1. THE DATA IS INTERNALLY CONSISTENT")
probs = drv_mod.validate()
check(not probs, "%d drivers across %s seasons, no contradictions"
      % (sum(drv_mod.stats().values()), len(drv_mod.stats())),
      str(probs[:3]))
check(drv_mod.seasons()==[1988,2021,2025],
      "and the scope is the three seasons it is meant to be",
      str(drv_mod.seasons()))

print("\n2. THE NUMBERS ARE THE ONES THAT WERE TRUE AT THE TIME")
# Spot checks, hand-verified. These are the whole product: if any of them is
# wrong the feature is worse than not existing. Career totals are the trap —
# Prost finished with 51 wins and Hamilton with more than 105, and neither of
# those numbers is true on the grid in the season being raced.
FACTS = [
    (E88, "Ayrton Senna",    0, 6),
    (E88, "Alain Prost",     2, 28),
    (E88, "Nelson Piquet",   3, 20),
    (E88, "Nigel Mansell",   0, 13),
    (E88, "Gerhard Berger",  0, 3),
    (E21, "Lewis Hamilton",  7, 95),
    (E21, "Max Verstappen",  0, 10),
    (E21, "Sebastian Vettel",4, 53),
    (E21, "Fernando Alonso", 2, 32),
    (E21, "Kimi Raikkonen",  1, 21),
    (E25, "Max Verstappen",  4, 63),
    (E25, "Lewis Hamilton",  7, 105),
    (E25, "Lando Norris",    0, 4),
    (E25, "Charles Leclerc", 0, 8),
    (E25, "Oscar Piastri",   0, 2),
]
bad=[]
for era,name,titles,wins in FACTS:
    d = drv_mod.lookup(name, era)
    if d is None or d.titles!=titles or d.wins!=wins:
        bad.append((name, era.year, titles, wins,
                    (d.titles,d.wins) if d else None))
check(not bad, "%d hand-verified records are exactly right" % len(FACTS),
      str(bad[:3]))
# The same man, two seasons, two different records. This is the property that
# makes the file worth having rather than a static career database.
h21 = drv_mod.lookup("Lewis Hamilton", E21)
h25 = drv_mod.lookup("Lewis Hamilton", E25)
check(h21.wins < h25.wins and h21.team != h25.team,
      "and a driver's record differs BETWEEN seasons, as it must",
      "%d wins at %s -> %d at %s" % (h21.wins,h21.team,h25.wins,h25.team))

print("\n3. THE ERA GATE — no facts outside the seasons we have")
check(drv_mod.season_of(E92) is None,
      "1992 is not one of our seasons, so it resolves to nothing")
check(drv_mod.lookup("Nigel Mansell", E92) is None,
      "and Mansell in 1992 returns NO record, though we hold one for 1988")
check(drv_mod.lookup("Fernando Alonso", EGT3) is None,
      "a GT3 car in 2021 is not the 2021 Formula One season")
check(drv_mod.lookup("Ayrton Senna", None) is None,
      "and no era at all is silence, not a default season")
check(drv_mod.roster(E92)==[] and drv_mod.label(E92)=="",
      "an era we do not have offers no roster and no label")

print("\n4. NAME MATCHING AGAINST THE SPELLINGS THE MODS ACTUALLY SHIP")
# Every one of these strings came out of the user's own rF2 result files or
# _career.json. A name the mod spells its own way must still resolve, and the
# only alternative to matching it is silence about that driver all season.
SPELLINGS = [
    (E88, "Andrea DeCesaris",     "Andrea de Cesaris"),
    (E88, "Rene Arnoux",          "René Arnoux"),
    (E88, "Luis Perez-Sala",      "Luis Pérez-Sala"),
    (E25, "Nico Hulkenberg",      "Nico Hülkenberg"),
    (E25, "Gabriel Bortoletto",   "Gabriel Bortoleto"),
    (E25, "Carlos Sainz Jr.",     "Carlos Sainz"),
    (E25, "Alex Albon",           "Alexander Albon"),
    (E21, "Kimi Raikkonen",       "Kimi Räikkönen"),
    (E21, "Sergio Perez",         "Sergio Pérez"),
    # A surname on its own, where it is unambiguous in that season.
    (E21, "Verstappen",           "Max Verstappen"),
    (E88, "Senna",                "Ayrton Senna"),
]
miss=[(raw,exp,(drv_mod.lookup(raw,e).name if drv_mod.lookup(raw,e) else None))
      for e,raw,exp in SPELLINGS
      if not (drv_mod.lookup(raw,e) and drv_mod.lookup(raw,e).name==exp)]
check(not miss, "%d mod spellings all resolve to the right man" % len(SPELLINGS),
      str(miss[:3]))
check(drv_mod.lookup("Fred Quirk", E25) is None
      and drv_mod.lookup("Lukas Scraples", E25) is None,
      "and the mod's invented AI names resolve to nobody")
check(drv_mod.lookup("Max Verstappen", E88) is None,
      "a driver who was not in that season is not in that season")

print("\n5. A CATEGORY IS NEVER OFFERED FOR A DRIVER IT IS FALSE OF")
# This is LAW 5 at the source. `slots_for` is the only way the booth gets
# slots, and it refuses rather than handing back a dict with a blank in it —
# because safe_format would happily air "chasing , and he".
norris21 = drv_mod.lookup("Lando Norris", E21)
check(drv_mod.slots_for(norris21, "driver_chasing") is None,
      "Norris in 2021 cannot be chasing an eighth title")
check(drv_mod.slots_for(norris21, "driver_champion") is None,
      "...nor be described as a champion")
check(drv_mod.slots_for(norris21, "driver_winless") is not None,
      "but he IS still looking for a first win, and that is offered")
ham21 = drv_mod.lookup("Lewis Hamilton", E21)
check(drv_mod.slots_for(ham21, "driver_winless") is None,
      "and a 95-time winner is never called winless")
check(drv_mod.slots_for(ham21, "driver_rookie") is None,
      "nor a seven-time champion a rookie")
# The contender gate. Both men have two titles; only one of them is in a car
# that could win this year's championship, and the booth should only ask the
# question of that one.
al25 = drv_mod.lookup("Fernando Alonso", E25)
ver25 = drv_mod.lookup("Max Verstappen", E25)
check(drv_mod.slots_for(al25, "driver_chasing") is None,
      "Alonso is not asked about a third title from a 2025 Aston Martin")
check(drv_mod.slots_for(ver25, "driver_chasing") is not None,
      "but Verstappen is asked about a fifth")

print("\n6. THE PHRASING — articles, plurals and ordinals")
check(ham21.next_title()=="an eighth",
      "seven titles makes 'an eighth', with its own article", ham21.next_title())
check(ver25.next_title()=="a fifth", "four makes 'a fifth'", ver25.next_title())
check(ham21.titles_phrase()=="a seven-time world champion",
      "and the title count reads as English", ham21.titles_phrase())
one = drv_mod.lookup("Kimi Raikkonen", E21)
check(one.titles_phrase()=="a world champion",
      "a single title is not 'a one-time world champion'", one.titles_phrase())
gasly = drv_mod.lookup("Pierre Gasly", E21)
check(gasly.wins_phrase()=="one win", "one win is singular", gasly.wins_phrase())
check(drv_mod.lookup("Alain Prost",E88).wins_phrase()=="twenty-eight wins",
      "and counts are spoken as words, not digits")
check(drv_mod.lookup("Nelson Piquet",E88).reigning
      and not drv_mod.lookup("Alain Prost",E88).reigning,
      "the reigning champion in 1988 is Piquet and nobody else")

print("\n7. THE POOLS — LAW 13 and LAW 14")
POOLS = list(DRIVER_CATS)
sizes = {c: len(lines_mod.pool(c)) for c in POOLS}
check(all(v>=6 for v in sizes.values()),
      "every driver pool has 6+ lines", str(sizes))
# LAW 13: the slots carry their own determiner, so a determiner in the
# template doubles it — "a a seven-time world champion".
CARRY = ("titles","next_title","wins")
dets=[]
for c in POOLS:
    for e in lines_mod.pool(c):
        t = e["t"] if isinstance(e,dict) else e
        for slot in CARRY:
            for det in ("a ","an ","the ","another "):
                if (det+"{"+slot+"}") in t.lower():
                    dets.append((c,t[:50]))
check(not dets, "no template puts a determiner in front of a slot that has one",
      str(dets[:2]))
# LAW 14: the bag can draw any line first, so nothing may read as a reply.
orphans=[]
for c in POOLS:
    for e in lines_mod.pool(c):
        t = (e["t"] if isinstance(e,dict) else e).lstrip()
        low = t.lower()
        if low.startswith(("and ","but ","so ","which ","he ","him ","that's why",
                           "neither ","either ","also ")):
            orphans.append((c,t[:50]))
check(not orphans, "and every line stands alone as an opener", str(orphans[:2]))
# The tense rule. These facts are what a driver BROUGHT to the season; the
# booth does not know how the user's championship is going and must never
# sound like it does.
tense=[]
for c in POOLS:
    for e in lines_mod.pool(c):
        low = (e["t"] if isinstance(e,dict) else e).lower()
        for phrase in ("so far this season","leads the championship",
                       "points this season","has won this year",
                       "this season he has"):
            if phrase in low:
                tense.append((c,low[:50]))
check(not tense, "and none of them claims to know how THIS season is going",
      str(tense[:2]))

print("\n8. EVERY LINE RENDERS FOR EVERY DRIVER THAT CAN DRAW IT")
# The real LAW 5 sweep: fill each category with every driver eligible for it,
# in every season, and demand there is no empty slot in the result. This is
# the test that would have caught "by !".
from overlay_common import safe_format
blanks=[]; rendered=0
for era in (E88,E21,E25):
    for d in drv_mod.roster(era):
        for c in drv_mod.eligible(d):
            slots = drv_mod.slots_for(d, c)
            for e in lines_mod.candidates(c, era):
                txt = safe_format(e["t"], slots)
                rendered += 1
                if "  " in txt or " ," in txt or " ." in txt or "{" in txt:
                    blanks.append((d.name,c,txt[:60]))
check(not blanks, "%d rendered lines, not one empty slot" % rendered,
      str(blanks[:3]))
caps = [t for t in
        (lines_mod._sentence_case(safe_format(
            (e["t"] if isinstance(e,dict) else e), drv_mod.slots_for(
                drv_mod.lookup("Lewis Hamilton",E21), "driver_champion")))
         for e in lines_mod.pool("driver_champion"))
        if t[:1].islower()]
check(not caps, "and nothing the booth renders starts lowercase", str(caps[:2]))

print("\n9. THE CAST — who is allowed to say this")
notallowed=[c for c in POOLS if not cast_mod.can_say(cast_mod.PLAY,c)]
check(not notallowed, "Miles may introduce a driver in every category",
      str(notallowed))
check(all(cast_mod.can_say(cast_mod.ANALYST,c) for c in POOLS),
      "and Chuck may deliver the ones marked as his")
# Brett sits in the same SEAT, so a historic grid must not go silent — this
# is the 1988 case, which is the one the user tests most.
check(all(cast_mod.can_say(cast_mod.HISTORIC_PLAY,c) for c in POOLS),
      "and Brett inherits all of it, so 1988 is not mute")
# Chuck has never driven a Formula One car. Nothing here may have him
# claiming otherwise — the same rule eratest.py enforces on the rest.
firstperson=[]
for c in POOLS:
    for e in lines_mod.pool(c):
        if not isinstance(e,dict) or e.get("who")!="ANALYST":
            continue
        low = e["t"].lower()
        for claim in ("i remember driving","i drove","when i raced","i raced",
                      "i've driven","i have driven","back when i"):
            if claim in low:
                firstperson.append((c,e["t"][:50]))
check(not firstperson, "and no analyst line claims first-hand Formula One time",
      str(firstperson[:2]))

print("\n10. THE BOOTH AIRS IT — and then stops")
class FakeTts:
    def __init__(s): s.said=[]; s.speaking=False
    def speak(s,t,who,intensity=0,build=False,name=""): s.said.append((who,t))
class Booth(BoothMixin):
    def __init__(s):
        s.booth_enabled=True; s.tts=FakeTts(); s.tracker=None; s.sting_bank=None
        s.booth_init()
    def _short_track(s,n): return n
    def _hide_panel(s,n): pass
    def _show_caption(s,t,w,n): pass
class Car:
    def __init__(s,i,name,place):
        s.id=i; s.name=name; s.display_name=name; s.place=place
        s.started_place=place; s.cls="McLaren"; s.in_pits=False
        s.gap_ahead=1.0; s.gap_leader=0.0; s.is_player=(place==5)
class S:
    def __init__(s,era,names):
        s.order=[Car(i,n,i+1) for i,n in enumerate(names)]
        s.player=s.order[4] if len(s.order)>4 else None
        s.leader=s.order[0]; s.era=era; s.player_era=era
        s.circuit=None; s.track="Montreal GP"; s.kind="race"
        s.leader_laps=3; s.laps_left=10; s.max_laps=13; s.green=True
NAMES21=["Lewis Hamilton","Max Verstappen","Valtteri Bottas","Sergio Perez",
         "Lando Norris","Charles Leclerc","Daniel Ricciardo","Carlos Sainz",
         "Pierre Gasly","Fernando Alonso"]
b=Booth(); s=S(E21,NAMES21); now=time.time()
ev = b._driver_facts(s, now)
check(ev, "the booth finds something true to say about this grid",
      "%d offered" % len(ev))
check(all(c in DRIVER_CATS for c,_,_ in ev),
      "all of it in the driver family")
aired=[]
for cat,kw,subj in ev:
    if b._driver_line(cat,kw,s,now):
        aired.append((cat,b.tts.said[-1][1])); break
check(aired, "and one of them airs", repr(aired[:1]))
if aired:
    txt = aired[0][1]
    check("{" not in txt and "  " not in txt and " ," not in txt,
          "with every slot filled", txt)

# THE FAMILY GATE (LAW 15). `driver_reigning` and `driver_chasing` are both
# correct and both about the champion; back to back they are a man reading a
# record book. Nothing more from the family until the gate expires.
again = b._driver_facts(s, now+5.0)
check(not again, "and the family goes quiet immediately afterwards")
later = b._driver_facts(s, now+DRIVER_FAMILY_GAP+1.0)
check(later, "coming back only once the family gate has expired",
      "%d offered" % len(later))

# ONCE PER DRIVER PER CATEGORY. The same fact about the same man twice in one
# session is worse than never saying it.
said_cat, said_kw, _ = ev[0]
subject = said_kw.get("drv")
repeats=[c for c,kw,_ in b._driver_facts(s, now+DRIVER_FAMILY_GAP+1.0)
         if kw.get("drv")==subject and c==said_cat]
check(not repeats, "and never repeats the same fact about the same driver",
      "%s / %s" % (subject, said_cat))

print("\n11. AN ERA WE HAVE NO DATA FOR IS COMPLETELY SILENT")
b2=Booth()
check(b2._driver_facts(S(E92,["Nigel Mansell","Ayrton Senna","Michael Schumacher"]),
                       time.time())==[],
      "1992 offers no driver facts at all")
b3=Booth()
check(b3._driver_facts(S(EGT3,["Lewis Hamilton","Max Verstappen","Lando Norris"]),
                       time.time())==[],
      "and neither does a GT3 field, whatever the names on it")

print("\n12. ONLY DRIVERS THE VIEWER CAN SEE")
b4=Booth()
deep = S(E21, ["Nobody One","Nobody Two","Nobody Three","Nobody Four",
               "Nobody Five","Nobody Six","Nobody Seven","Nobody Eight",
               "Nobody Nine","Nobody Ten","Nobody Eleven","Lewis Hamilton"])
deep.player = deep.order[4]
check(b4._driver_facts(deep, time.time())==[],
      "a champion running twelfth is out of focus and stays unmentioned")
# ...unless he is the player, who is the one man the viewer is definitely
# watching wherever he happens to be running.
b5=Booth()
deep.player = deep.order[11]
check(b5._driver_facts(deep, time.time()),
      "but the PLAYER is always in scope, wherever he is")

print("\n13. THE PRE-RACE BEAT — who is that on pole?")
# The grid beat names the man on pole; the "who" beat says who he IS. It is
# the most natural place in a whole broadcast for a driver's record, and it
# is scripted rather than filler, so it bypasses the family gate on purpose.
b6=Booth(); pole=S(E21,NAMES21)
b6._pre=["who"]
ok = b6._pre_stage(pole, time.time(), None)
check(ok and b6.tts.said, "the opening sequence introduces the man on pole",
      repr(b6.tts.said[-1:]))
if b6.tts.said:
    check("Hamilton" in b6.tts.said[-1][1],
          "and it is about the driver on pole, not somebody down the order",
          b6.tts.said[-1][1])
# A grid we know nothing about must cost the opening sequence a beat and
# nothing more — the same contract as the season and history stages.
b7=Booth(); b7._pre=["who"]
check(not b7._pre_stage(S(E92,["Nigel Mansell","Ayrton Senna"]),
                        time.time(), None),
      "and an unknown grid drops the beat silently rather than inventing one")
check(not b7.tts.said, "with nothing said at all", repr(b7.tts.said))

print("\n14. THE RECORD IS LIVE — history PLUS what you did in this career")
# The point the whole feature turns on. Race as Hamilton, win three, and the
# third is his ninety-eighth, not his third. Take the championship and it is
# his eighth, not his first. And the same maths applies to the AI: win it as
# an AI Senna in 1988 and that is a FIRST world championship.
import season as season_mod
class FakeCareer(object):
    """A declared-length open season. Only the parts drivers.py reads."""
    def __init__(s, length, rounds, me="Lewis Hamilton"):
        s.rounds=rounds; s.data={"length":length}; s.me=me
        s.total_rounds=length
    def points_for(s,pos):
        tbl=[25,18,15,12,10,8,6,4,2,1]
        return tbl[pos-1] if 0<pos<=len(tbl) else 0
    standings = season_mod.Career.standings
    title_state = season_mod.Career.title_state
def rnd(n, order):
    return {"n":n, "classified":[[nm,i+1] for i,nm in enumerate(order)]}

GRID21=["Lewis Hamilton","Max Verstappen","Valtteri Bottas","Lando Norris"]
c1=FakeCareer(3,[rnd(1,GRID21)])
st=drv_mod.standing("Lewis Hamilton", E21, c1, upto=1)
check(st.wins==96 and st.season_wins==1,
      "one win as Hamilton makes it ninety-six, not one",
      "%d (+%d)" % (st.wins, st.season_wins))
check(st.slots()["nth_win"]=="ninety-sixth",
      "and the win is his ninety-sixth", st.slots()["nth_win"])
check(not st.first_win and not st.won_title,
      "with no title claimed on the strength of one race")

c3=FakeCareer(3,[rnd(i+1,GRID21) for i in range(3)])
st3=drv_mod.standing("Lewis Hamilton", E21, c3, upto=3)
check(st3.wins==98 and st3.titles==8,
      "three wins from three makes ninety-eight and an eighth title",
      "%d wins / %d titles" % (st3.wins, st3.titles))
check(st3.slots()["this_title"]=="an eighth",
      "phrased as 'an eighth'", st3.slots()["this_title"])
check(st3.slots()["titles"]=="an eight-time world champion",
      "and eight takes 'an', not 'a'", st3.slots()["titles"])
check(not st3.new_champion, "he was already a champion, so this is not a first")

# A FIRST title, for a man who has never had one. Norris wins all three.
GRIDN=["Lando Norris","Lewis Hamilton","Max Verstappen","Valtteri Bottas"]
cn=FakeCareer(3,[rnd(i+1,GRIDN) for i in range(3)], me="Lando Norris")
stn=drv_mod.standing("Lando Norris", E21, cn, upto=3)
check(stn.new_champion and stn.titles==1,
      "Norris taking the championship is a FIRST world title")
check(stn.first_win and stn.wins==3,
      "and his first ever Grand Prix win is in there too",
      "%d wins, first=%s" % (stn.wins, stn.first_win))
# The AI. Senna wins the 1988 season while the user drives somebody else.
GRID88=["Ayrton Senna","Alain Prost","Nigel Mansell","Nelson Piquet"]
cs=FakeCareer(3,[rnd(i+1,GRID88) for i in range(3)], me="Nigel Mansell")
sts=drv_mod.standing("Ayrton Senna", E88, cs, upto=3)
check(sts.new_champion and sts.wins==9,
      "an AI Senna winning the 1988 title is a first championship, on 9 wins",
      "%d wins / %d titles" % (sts.wins, sts.titles))
stp=drv_mod.standing("Alain Prost", E88, cs, upto=3)
check(not stp.won_title and stp.wins==28,
      "and Prost, beaten, is still on the twenty-eight he arrived with",
      "%d" % stp.wins)

print("\n15. A TITLE IS ANNOUNCED ONCE, IN THE ROUND IT WAS SETTLED")
# Hamilton wins the first three; the runner-up is a different man each time,
# so nobody behind him has banked a consistent second. Over four rounds that
# is mathematically settled with one to run; over five it is not. Both are
# the real `season.py` maths, not a restatement of it.
def rotated(n, first, rest):
    return rnd(n, [first] + rest[n-1:] + rest[:n-1])
CHASE=["Max Verstappen","Valtteri Bottas","Lando Norris"]
BIG=[rotated(i+1,"Lewis Hamilton",CHASE) for i in range(3)]
c5=FakeCareer(5,BIG)
check(not drv_mod.just_won_title("Lewis Hamilton",E21,c5,3),
      "three wins of five leaves too much on the table to call it")
c5b=FakeCareer(4,BIG)
check(drv_mod.just_won_title("Lewis Hamilton",E21,c5b,3),
      "three of four settles it, and it is announced in round three")
c5c=FakeCareer(4,BIG+[rotated(4,"Lewis Hamilton",CHASE)])
check(not drv_mod.just_won_title("Lewis Hamilton",E21,c5c,4),
      "and NOT announced again in round four")
# LAW 4 survives: an open season with no declared length can never claim it.
copen=FakeCareer(0,BIG)
check(not drv_mod.just_won_title("Lewis Hamilton",E21,copen,3),
      "a season with no declared length never claims a title at all")

print("\n16. THE LIVE POOLS RENDER, AND SAY THE RIGHT THING")
LIVE=("driver_title_first","driver_title_more","driver_first_win",
      "driver_win_tally")
sizes={c:len(lines_mod.pool(c)) for c in LIVE}
check(all(v>=6 for v in sizes.values()), "each live pool has 6+ lines",
      str(sizes))
blanks=[]
for cat,stx in ((("driver_title_more",st3)),("driver_title_first",stn),
                ("driver_first_win",stn),("driver_win_tally",st3)):
    for e in lines_mod.candidates(cat, E21):
        txt=lines_mod._sentence_case(safe_format(e["t"], stx.slots()))
        if "{" in txt or "  " in txt or " ," in txt or txt[:1].islower():
            blanks.append((cat,txt[:60]))
check(not blanks, "and every one of them renders cleanly", str(blanks[:3]))
# LAW 13 again, over the slots these pools use.
dets=[]
for c in LIVE:
    for e in lines_mod.pool(c):
        t=(e["t"] if isinstance(e,dict) else e).lower()
        for slot in ("titles","this_title","wins"):
            for det in ("a ","an ","the ","another "):
                if (det+"{"+slot+"}") in t: dets.append((c,t[:50]))
check(not dets, "with no determiner in front of a slot that carries one",
      str(dets[:2]))
check(all(cast_mod.can_say(cast_mod.PLAY,c) for c in LIVE)
      and all(cast_mod.can_say(cast_mod.HISTORIC_PLAY,c) for c in LIVE),
      "and both men in the play-by-play seat may deliver them")

print("\n17. THE BOOTH'S WRAP USES IT")
class WrapBooth(Booth):
    pass
b8=WrapBooth(); b8.season=c5b; b8._season_round={"n":3}
w=S(E21,GRID21+["Sergio Perez"]); w.leader=w.order[0]
cat,kw = b8._championship_call(w)
check(cat=="driver_title_more",
      "the championship beat becomes a TITLE call when one has been won", cat)
check(kw.get("this_title")=="an eighth" and kw.get("drv")=="Lewis Hamilton",
      "naming the right man and the right number", str(kw.get("this_title")))
cat2,kw2 = b8._tally_call(w)
check(cat2=="driver_win_tally" and kw2.get("nth_win")=="ninety-eighth",
      "and the win itself is placed in his career", "%s %s" % (cat2, kw2.get("nth_win")))
# Outside a career there is no banked result, so there is no running total to
# quote and the booth says nothing rather than quoting the historical figure.
b9=WrapBooth(); b9.season=None; b9._season_round=None
check(b9._tally_call(w)==(None,{}),
      "outside career mode the tally is silent, not stale")
b10=WrapBooth(); b10.season=FakeCareer(4,[]); b10._season_round={"n":1}
check(b10._tally_call(w)==(None,{}),
      "and a win that was never banked is never counted")

print("\n18. CONTINUITY — the booth remembers what it said last time")
# THE regression this section exists for, in the user's own words: you cannot
# take a maiden win in round two and be asked in round three whether you will
# ever win one. Everything the introductions are judged on must therefore run
# off the LIVE record, not the frozen one.
GRID88=["Alessandro Nannini","Ayrton Senna","Alain Prost","Nigel Mansell"]
nan = drv_mod.standing("Alessandro Nannini", E88, FakeCareer(5,[],"Nigel Mansell"))
check("driver_winless" in drv_mod.eligible(nan),
      "before he has won, Nannini is offered the winless line")
after = drv_mod.standing("Alessandro Nannini", E88,
                         FakeCareer(5,[rnd(1,GRID88)],"Nigel Mansell"))
check(not after.winless and "driver_winless" not in drv_mod.eligible(after),
      "the moment he wins one of your races he is NEVER called winless again")
check("driver_season_wins" in drv_mod.eligible(after),
      "and the booth has something better to say instead",
      str(drv_mod.eligible(after)))
check(after.slots()["swins"]=="one win",
      "phrased 'one win this season', not 'one wins'", after.slots()["swins"])
# The same for a man who wins the title: he stops being a nearly-man.
GRIDM=["Nigel Mansell","Ayrton Senna","Alain Prost","Nelson Piquet"]
cm=FakeCareer(3,[rnd(i+1,GRIDM) for i in range(3)],"Nigel Mansell")
man=drv_mod.standing("Nigel Mansell", E88, cm, upto=3)
elig=drv_mod.eligible(man)
check("driver_champion" in elig and "driver_winner" not in elig,
      "a Mansell who has won your title is a CHAMPION, not a nearly-man",
      str(elig))
check(man.slots()["titles"]=="a world champion",
      "and is introduced as one from then on", man.slots()["titles"])
# The introductions the booth actually generates must use the live record.
b11=WrapBooth(); b11.season=cm; b11._season_round={"n":4}
sess=S(E88,GRIDM); sess.player=sess.order[0]
cats=[c for c,_,_ in b11._driver_facts(sess, time.time())]
check("driver_winless" not in cats,
      "and the live booth never offers a winless line about any of them",
      str(cats))
kwm=next((kw for c,kw,_ in b11._driver_facts(sess, time.time())
          if kw.get("drv")=="Nigel Mansell"), {})
check(kwm.get("wins")=="sixteen wins",
      "the intro slots carry the running total, not the historical one",
      str(kwm.get("wins")))

# A career's `classified` lists hold the MOD's spelling of a name; the record
# holds the properly spelled one. Comparing those two strings directly loses
# every result belonging to a driver with an accent in his name — which is
# most of the interesting ones — and it does so SILENTLY.
ACCENTED=[("Kimi Raikkonen",E21,"Kimi Räikkönen"),
          ("Sergio Perez",E21,"Sergio Pérez"),
          ("Nico Hulkenberg",E25,"Nico Hülkenberg"),
          ("Carlos Sainz Jr.",E25,"Carlos Sainz"),
          ("Andrea DeCesaris",E88,"Andrea de Cesaris")]
lost=[]
for mod_spelling, era, canonical in ACCENTED:
    car=FakeCareer(5,[rnd(1,[mod_spelling,"Other One","Other Two"])],"Other One")
    stx=drv_mod.standing(mod_spelling, era, car)
    if stx is None or stx.season_wins != 1:
        lost.append((mod_spelling, canonical,
                     stx.season_wins if stx else None))
check(not lost,
      "a win is credited however the mod spells the winner's name",
      str(lost[:3]))

print("\n19. A ONE-OFF RACE IS NOT PART OF ANY CHAMPIONSHIP")
# A career stays loaded in the settings for as long as it exists, so a race
# run purely for fun still has one attached. It must not be credited to it:
# outside a career round the booth reads the HISTORY and nothing else, which
# is the right broadcast for a one-off anyway.
b12=WrapBooth(); b12.season=cm            # a career with three Mansell wins
b12._season_round=None                     # ...but this race is not in it
check(b12._active_career() is None,
      "a career race and a race for fun are different questions")
one=S(E88,GRIDM); one.player=one.order[0]
kw1=next((kw for c,kw,_ in b12._driver_facts(one, time.time())
          if kw.get("drv")=="Nigel Mansell"), {})
check(kw1.get("wins")=="thirteen wins",
      "so a one-off race quotes the thirteen he really had in 1988",
      str(kw1.get("wins")))
cats1=[c for c,_,_ in b12._driver_facts(one, time.time())]
check("driver_season_wins" not in cats1,
      "and never mentions a season this race is not part of", str(cats1))
check(b12._tally_call(one)==(None,{}),
      "a win in it is not counted towards anybody's career total")
check(b12._championship_call(one)==(None,{}),
      "and no championship is read out at the end of it")
# The same booth, once the race IS a career round, goes back to the running
# total. One flag, both behaviours.
b12._season_round={"n":3}
kw2=next((kw for c,kw,_ in b12._driver_facts(one, time.time()+400)
          if kw.get("drv")=="Nigel Mansell"), {})
check(kw2.get("wins")=="sixteen wins",
      "while a career round still gets the live sixteen", str(kw2.get("wins")))

print("\n20. A NOTE THAT THE SEASON HAS FALSIFIED GOES QUIET")
# Some hand-written clauses are only true until your career touches them.
hulk = drv_mod.lookup("Nico Hulkenberg", E25)
check(hulk.raw.get("note_void_on")=="podium",
      "Hulkenberg's 'no podium' record declares what would end it")
POD=["Lando Norris","Max Verstappen","Nico Hulkenberg","George Russell"]
ch=FakeCareer(5,[rnd(1,POD)],"Lando Norris")
h2=drv_mod.standing("Nico Hulkenberg", E25, ch)
check(h2.note=="" and "driver_note" not in drv_mod.eligible(h2),
      "and it is dropped the moment he finishes third in one of your races")
# A note with no `note_void_on` is a fact your season cannot reach.
check(bool(drv_mod.standing("Fernando Alonso", E25, ch).note),
      "while 'the oldest man on this grid' survives anything you do")
# Every note that COULD be falsified must say so. This is the check that
# catches the next note somebody adds without thinking it through.
VOIDABLE=("still no win","last win came","without a podium","start to his name",
          "yet to win","never won")
untagged=[]
for era in (E88,E21,E25):
    for d in drv_mod.roster(era):
        if not d.note:
            continue
        low=d.note.lower()
        if any(v in low for v in VOIDABLE) and not d.raw.get("note_void_on"):
            untagged.append((d.name, d.note))
check(not untagged,
      "every note whose truth your season could end declares note_void_on",
      str(untagged[:2]))

print("\n21. A NEW CAREER IS A CLEAN SLATE")
# The record a driver arrived with is HISTORY and is never written to. What a
# career adds lives in that career's own file and nowhere else, so starting a
# second 1988 season gives you a Mansell who has never won a championship —
# which is the only sane reading of "starting again".
#
# This runs through the real season.create/save/delete path rather than the
# fakes above, because the property being tested is about files.
import season as _s
made=[]
try:
    c_a=_s.create("open", me="Nigel Mansell", name="drivertest A", rounds=3)
    check(c_a is not None, "a career can be created")
    if c_a is not None:
        made.append(c_a.slug)
        for n in (1,2,3):
            c_a.data.setdefault("rounds",[]).append(
                {"n":n,"slug":"silverstone","pos":1,"laps":10,"race_laps":10,
                 "classified":[[x,i+1] for i,x in enumerate(GRIDM)]})
        c_a.save()
        sa=drv_mod.standing("Nigel Mansell", E88, c_a, upto=3)
        check(sa.titles==1 and sa.wins==16,
              "three wins in career A makes him champion, on sixteen wins",
              "%d wins / %d titles" % (sa.wins, sa.titles))

        c_b=_s.create("open", me="Nigel Mansell", name="drivertest B", rounds=3)
        if c_b is not None:
            made.append(c_b.slug)
            sb=drv_mod.standing("Nigel Mansell", E88, c_b)
            check(sb.titles==0 and sb.wins==13,
                  "a NEW 1988 career has him back on thirteen and no title",
                  "%d wins / %d titles" % (sb.wins, sb.titles))
            check("driver_winner" in drv_mod.eligible(sb)
                  and "driver_champion" not in drv_mod.eligible(sb),
                  "and he is introduced as a nearly-man again",
                  str(drv_mod.eligible(sb)))
            # ...while career A is untouched by career B existing.
            sa2=drv_mod.standing("Nigel Mansell", E88, c_a, upto=3)
            check(sa2.titles==1,
                  "with the first career's championship still intact")
    # Nothing anywhere writes to the historical record itself.
    raw=drv_mod.lookup("Nigel Mansell", E88)
    check(raw.wins==13 and raw.titles==0,
          "and drivers.json is never written to, whatever a career does",
          "%d wins / %d titles" % (raw.wins, raw.titles))
finally:
    for slug in made:
        _s.delete(slug)

print("\n22. THE CAR — what this KIND of machine is like")
# `car_character` is a plain line pool gated on era capability, not on a
# season we hold records for. That is the whole reason it exists in that
# shape: it has to reach the Group C race and the Super Touring grid and the
# GT3 field, so a one-off race for fun gets real colour about the machinery.
FIELDS = [
    ("F1 1988 Historic Edition", "Senna", ()),
    ("Formula 1 1992 Season by ASRC", "Mansell", ()),
    ("McLaren", "Norris", ("McLaren","Ferrari","Mercedes","Red Bull","Alpine",
                           "Aston Martin","Haas","Williams","Alfa Romeo",
                           "Alpha Tauri")),
    ("F1 Test 2025", "Verstappen", ()),
    ("BMW M4 GT3 2020", "BMW", ()),
    ("GT500", "HSV-010", ()),
    ("Group C", "962C", ()),
    ("BMW 320i STW", "BMW", ()),
    ("NASCAR 2023 Next Gen CUP", "x", ()),
    ("IndyCar_2014_Honda", "Dallara", ()),
    ("", "Howston_G4_1968", ()),
    ("", "March_M761_1976", ()),
]
thin=[]
for cls, nm, fc in FIELDS:
    e = era_mod.classify(cls, nm, field_classes=fc)
    n = len(lines_mod.candidates("car_character", e))
    if n < 3:
        thin.append((cls or nm, e.key, n))
check(not thin,
      "every kind of car the user owns has 3+ things said about it",
      str(thin))
# ...including the ones with no driver knowledge behind them at all. This is
# the answer to "I will not only be doing career races".
gt = era_mod.classify("BMW M4 GT3 2020", "BMW")
check(drv_mod.season_of(gt) is None
      and len(lines_mod.candidates("car_character", gt)) >= 3,
      "a GT3 field has no driver records and still has car colour",
      "%d lines" % len(lines_mod.candidates("car_character", gt)))
# CAPABILITY, NOT OUTCOME. The booth is calling a race the user is driving.
outcome=[]
for e in lines_mod.pool("car_character"):
    low=(e["t"] if isinstance(e,dict) else e).lower()
    for phrase in ("won the championship","won fifteen","dominated the season",
                   "took the title","won the constructors"):
        if phrase in low:
            outcome.append(low[:60])
check(not outcome, "and no car line gives away how the real season went",
      str(outcome[:2]))
# Nobody in this booth drove one of these.
fp=[]
for e in lines_mod.pool("car_character"):
    low=(e["t"] if isinstance(e,dict) else e).lower()
    for claim in ("i drove","when i raced","i remember driving","i've driven",
                  "i have driven","back when i","i raced"):
        if claim in low:
            fp.append(low[:60])
check(not fp, "and none of them has the analyst claiming he drove it",
      str(fp[:2]))

print("\n23. THE TEAM — what his car is like THIS year")
TEAMCATS=("team_strength","team_weakness","team_note")
sizes={c:len(lines_mod.pool(c)) for c in TEAMCATS}
check(all(v>=6 for v in sizes.values()), "each team pool has 6+ lines",
      str(sizes))
merc = drv_mod.standing("Lewis Hamilton", E21, None)
check(merc.club is not None and merc.club.name=="Mercedes",
      "a driver carries his team's record for that season",
      str(merc.club))
check(drv_mod.slots_for(merc,"team_strength") is not None,
      "Mercedes in 2021 have a strength worth naming")
h25 = drv_mod.standing("Lewis Hamilton", E25, None)
check(h25.club.name=="Ferrari",
      "and the SAME driver carries a different team in a different season",
      str(h25.club))
# A team with no weakness recorded must never draw a weakness line.
mcl = drv_mod.standing("Lando Norris", E25, None)
check(mcl.club.weakness=="" and drv_mod.slots_for(mcl,"team_weakness") is None,
      "a team with no weakness recorded is never given one")
# THE FRAME SWEEP. Each clause has to survive all six templates in its pool.
broken=[]; count=0
for era in (E88,E21,E25):
    for d in drv_mod.roster(era):
        st=drv_mod.standing(d.name, era, None)
        for cat in TEAMCATS:
            slots=drv_mod.slots_for(st,cat)
            if not slots:
                continue
            for e in lines_mod.candidates(cat, era):
                txt=lines_mod._sentence_case(safe_format(e["t"], slots))
                count+=1
                if ("{" in txt or "  " in txt or " ," in txt or " ." in txt
                        or txt[:1].islower() or ". ." in txt):
                    broken.append((d.team,cat,txt[:70]))
check(not broken, "%d team lines render cleanly in every frame" % count,
      str(broken[:2]))
# The clause contract itself, which is what makes the sweep above pass.
badclause=[]
for era in (E88,E21,E25):
    for d in drv_mod.roster(era):
        if d.club is None:
            continue
        for f in ("strength","weakness"):
            c=getattr(d.club,f)
            if c and (c[:1].isupper() or c.rstrip()[-1:] in ".!?" or "—" in c):
                badclause.append((d.club.name,f,c[:50]))
check(not badclause,
      "and every clause is a bare noun phrase, as the frames require",
      str(badclause[:2]))
# Team lines are in the driver FAMILY, so they cannot follow a driver fact
# straight away — the two together are one briefing (LAW 15).
from overlay_booth import DRIVER_CATS as _DC
check(all(c in _DC for c in TEAMCATS),
      "team lines share the driver-fact family gate")
check("car_character" not in _DC,
      "while car character is NOT in it — it applies to races with no "
      "driver records at all")

print("\n24. THE BOOTH REACHES BOTH LAYERS")
b13=WrapBooth(); b13.season=None; b13._season_round=None
sess21=S(E21,NAMES21)
cats13=[c for c,_,_ in b13._driver_facts(sess21, time.time())]
check(any(c in TEAMCATS for c in cats13),
      "the booth offers team character alongside the driver records",
      str([c for c in cats13 if c in TEAMCATS][:3]))
kwt=next((kw for c,kw,_ in b13._driver_facts(sess21, time.time())
          if c in TEAMCATS), {})
check(kwt.get("team") and (kwt.get("strength") or kwt.get("weakness")
                           or kwt.get("tnote")),
      "with the team's own clauses in the slots", str(kwt.get("team")))

print("\n25. THE CAREER DRIVER PICKER OFFERS THE WHOLE GRID")
# The bug: `career._fold_field` built the roster for a team-named
# championship out of `classified`, which is scoped to the PLAYER'S CLASS —
# and for these mods a class is one team. "Formula One 2021" therefore
# offered exactly two names, both McLarens.
import career as career_mod
F1_2021=["McLaren","Ferrari","Mercedes","Red Bull","Alpine","Aston Martin",
         "Haas","Williams","Alfa Romeo","Alpha Tauri"]
rows=[{"name":"Driver %d"%i, "cls":F1_2021[i//2], "pos":i+1, "cls_pos":(i%2)+1,
       "laps":50} for i in range(20)]
res={"slug":"montreal","cls":"McLaren","when":1,"cls_share":0.1,
     "field_classes":F1_2021,"me_raw":"Your Name","me":"",
     "classified":[("Driver 0",1),("Driver 1",2)],
     "grid_all":[(r["name"], r["pos"]) for r in rows],
     "pos":1,"grid":1,"field":2,"laps":50,"race_laps":50,"dnf":False,
     "winner":"Driver 0","best":90.0,"event":"","circuit":"","venue":"",
     "date":"","file":"x.xml","veh_driver":""}
# A TEMP STORE, NEVER THE REAL ONE. `History()` defaults to CAREER_PATH and
# loads it in __init__, so the bare constructor pulls in whatever the user's
# own career happens to hold — and this check counts drivers, so a real store
# that already knows this championship makes it read 40 instead of 20. It
# passed for months only because the machine's store had not seen one yet.
import tempfile as _tf
_cstore = os.path.join(_tf.mkdtemp(prefix="factortv_picker_"), "_career.json")
h=career_mod.History(_cstore); h.data.setdefault("classes",{})
h._fold_field(h.data, res)
label=next(k for k in h.data["classes"] if k.startswith("Formula One"))
got=h.data["classes"][label].get("drivers") or []
check(len(got)==20,
      "a team-named field records all twenty drivers, not the player's two",
      "%d in %r" % (len(got), label))
# ...while a real class keeps its own roster class-scoped, which is correct:
# a GT3 championship is not decided by the GTE cars sharing the circuit.
check(res["classified"] != res["grid_all"],
      "and `classified` stays class-scoped for everything else")
check(career_mod.VERSION >= 7,
      "the file version is bumped so existing careers rebuild",
      str(career_mod.VERSION))

print("\n26. AND IT IS SEEDED, SO IT WORKS BEFORE YOU HAVE RACED")
empty = drv_mod.picker_names([], "Formula One 2021", F1_2021)
check(len(empty)==20,
      "a career started on a fresh install still offers the whole 2021 grid",
      "%d names" % len(empty))
check("Lewis Hamilton" in empty and "Max Verstappen" in empty,
      "including the ones you would actually want to be")
check(len(drv_mod.picker_names([], "F1 1988 Historic Edition"))==31,
      "and the 1988 field, which is where this feature is most wanted")
# A mod we hold nothing for is passed through untouched — history is the only
# source for the other eighty on this machine.
stock=["Ted Moser","Gary Madew","Dave Martin"]
check(drv_mod.picker_names(stock, "StockCar 2018 X Series")==sorted(stock),
      "a mod we know nothing about keeps its own roster, unaltered")
check(drv_mod.picker_names([], "GT500")==[],
      "and gains nothing it has no business gaining")

print("\n27. ONE PERSON, ONE ENTRY — WHATEVER THE MOD CALLED HIM")
# The two sources spell people differently and a set union offers the same
# man twice. Identity has to resolve through `lookup`, not through folding:
# "Yuski Tsunoda" is a typo and "Kimi Antonelli" a short form, and neither
# folds to the canonical name while both resolve through the index.
MODNAMES=["Yuski Tsunoda","Kimi Antonelli","Carlos Sainz Jr","Nico Hulkenberg",
          "Alex Albon","Gabriel Bortoletto"]
merged=drv_mod.picker_names(MODNAMES, "F1 Test 2025")
dupes=[n for n in ("Yuski Tsunoda","Kimi Antonelli","Alex Albon",
                   "Gabriel Bortoletto") if n in merged]
check(not dupes, "no driver appears twice under two spellings", str(dupes))
canon=[n for n in ("Yuki Tsunoda","Andrea Kimi Antonelli","Alexander Albon",
                   "Gabriel Bortoleto","Nico Hülkenberg","Carlos Sainz")
       if n in merged]
check(len(canon)==6,
      "and each of them is offered under the name worth saying out loud",
      str([n for n in ("Yuki Tsunoda","Andrea Kimi Antonelli","Alexander Albon",
                       "Gabriel Bortoleto","Nico Hülkenberg","Carlos Sainz")
           if n not in merged]))
# A name the knowledge base does not hold survives — the mod's invented AI
# drivers are real entries in a real grid and you may want to race as one.
check("Fred Quirk" in drv_mod.picker_names(["Fred Quirk"], "F1 Test 2025"),
      "while a name we do not hold is kept exactly as the mod wrote it")


print("\n28. THE ELABORATED HISTORY LAYER")
# The short form states a record — "Verstappen has ten wins" — and averages
# ten words. The complaint was exact: "one statement and then theres no
# conversation, full stop". This is the same knowledge in the other register.
from overlay_booth import BoothMixin as _BM
HIST = _BM.HIST_ANSWER
missing=[c for c in HIST.values() if len(lines_mod.pool(c)) < 3]
check(not missing, "every elaborated answer pool has lines", str(missing))
short=[len(e["t"].split()) for e in
       (x for c in HIST for x in lines_mod.pool(c))]
long_=[len(e["t"].split()) for e in
       (x for c in HIST.values() for x in lines_mod.pool(c))]
check(sum(long_)/len(long_) > 2 * (sum(short)/len(short)),
      "and they are substantially longer than the short form",
      "%.0f words vs %.0f" % (sum(long_)/len(long_), sum(short)/len(short)))
check(max(long_) <= 32,
      "while still inside Chuck's character cap", "longest %d" % max(long_))
# EVERY ANSWER IS GATED THE SAME WAY THE SHORT FORM IS. A long line about the
# wrong driver is worse than a short one, not better.
check(all(c in drv_mod.CATEGORIES for c in HIST),
      "each elaborated answer hangs off a real drivers.CATEGORIES gate",
      str([c for c in HIST if c not in drv_mod.CATEGORIES]))
# The notes come in two grammatical shapes and only one frame fits both.
blanks=[]
for era in (E88,E21,E25):
    for d in drv_mod.roster(era):
        st = drv_mod.standing(d.name, era, None)
        for cat, ans in HIST.items():
            slots = drv_mod.slots_for(st, cat)
            if not slots:
                continue
            for e in lines_mod.candidates(ans, era):
                t = lines_mod._sentence_case(safe_format(e["t"], slots))
                if "{" in t or "  " in t or " ," in t or t[:1].islower():
                    blanks.append((d.name, ans, t[:70]))
check(not blanks, "every elaborated line renders for every driver it can "
      "be said about", str(blanks[:2]))
check(all(cast_mod.can_say(cast_mod.ANALYST, c) for c in HIST.values()),
      "the answers are Chuck's")
check(cast_mod.who_says("driver_ask")==cast_mod.PLAY
      and cast_mod.can_say(cast_mod.HISTORIC_PLAY,"driver_ask"),
      "the question is the play-by-play seat's, and Brett inherits it")
# ERA-NEUTRAL: a 1988 grid must get the same treatment as a 2025 one.
thin=[c for c in HIST.values()
      if len(lines_mod.candidates(c, E88)) < len(lines_mod.candidates(c, E25))]
check(not thin, "and nothing is gated away from a historic field", str(thin))


print("\n29. RACING AS A REAL DRIVER — THE BOOTH KNOWS WHO YOU ARE")
# A car carries TWO names. `name` is what rF2 reported; `display_name` is what
# the overlay will say out loud. For the AI they are the same. FOR THE PLAYER
# THEY ARE NOT: rF2 reports the profile name, usually the placeholder "Your
# Name", and the career's chosen driver name lives in `display_name`.
#
# Preferring `name` meant a career raced AS Max Verstappen produced no facts
# about Max Verstappen — the booth held his entire record and could not
# connect it to the car being driven. Which is the whole feature.
class PCar(object):
    id=99; place=1; started_place=1; cls="F1"; in_pits=False
    gap_ahead=1.0; gap_leader=0.0; is_player=True; damage=(0,)*8
    name="Your Name"                      # rF2's profile placeholder
    display_name="Max Verstappen"         # the career's chosen name
rec = BoothMixin._driver_record(PCar(), E25)
check(rec is not None and rec.name=="Max Verstappen",
      "a career raced as Max resolves to Max, not to the profile name",
      str(rec))
check(rec is not None and rec.titles==4 and rec.wins==63,
      "with his 2025 record — four titles, sixty-three wins",
      ("%s titles / %s wins" % (rec.titles, rec.wins)) if rec else "-")
check("driver_reigning" in drv_mod.eligible(rec),
      "so the booth can call the player the reigning champion, which he is",
      str(drv_mod.eligible(rec)))
# The SAME career name in a season Max was not champion of gets the 2021 man.
rec21 = BoothMixin._driver_record(PCar(), E21)
check(rec21 is not None and rec21.titles==0 and rec21.wins==10,
      "and the identical career in 2021 gets the 2021 record instead",
      ("%s titles / %s wins" % (rec21.titles, rec21.wins)) if rec21 else "-")
check("driver_reigning" not in drv_mod.eligible(rec21),
      "where he is emphatically NOT the reigning champion",
      str(drv_mod.eligible(rec21)))
# ...and a name that is nobody stays nobody, however it is carried.
class Nobody(PCar):
    display_name="Dante Kandasamy"
check(BoothMixin._driver_record(Nobody(), E25) is None,
      "while racing under your own name invents no history for you")
print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
