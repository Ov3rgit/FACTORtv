"""Career history test.

Builds synthetic rF2 result XMLs in a temp folder — nothing here touches the
real game files, so the numbers are known and the test means something on a
machine with no rFactor 2 installed.

What matters most is THE LAW: rF2 writes a result file whether you took the
chequered flag or quit on lap two, and a career that records the second is
worse than no career at all.

    python tests/careertest.py
"""
import os, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import career as career_mod
import lines as lines_mod
import track as track_mod
from fakes import Booth, FakeSession, grid

fails = []
def check(cond, label, extra=""):
    print(("  [ OK ] " if cond else "  [FAIL] ") + label + (("  " + extra) if extra else ""))
    if not cond:
        fails.append(label)


DRIVER = """  <Driver>
   <Name>%(name)s</Name>
   <CarClass>%(cls)s</CarClass>
   <GridPos>%(grid)d</GridPos>
   <Position>%(pos)d</Position>
   <ClassPosition>%(pos)d</ClassPosition>
   <Laps>%(laps)d</Laps>
   <BestLapTime>92.5</BestLapTime>
   <FinishStatus>%(status)s</FinishStatus>
   <Points>0</Points>
   <VehName>%(veh)s</VehName>
   <TeamName>%(team)s</TeamName>
   <isPlayer>%(me)d</isPlayer>
  </Driver>
"""

def write_result(dirname, fname, venue, cls, player_pos, player_laps,
                 race_laps=20, field=8, status="Finished Normally",
                 when=1000, run_laps=None, ai_status="Finished Normally"):
    """`run_laps` is how far the FIELD actually got, defaulting to the full
    scheduled distance. Setting it lower is what a restart looks like on disk:
    everybody stops at the same lap, so no single driver looks abandoned.

    THE STATUSES DEFAULT TO A RACE THAT REACHED THE FLAG, because that is what
    an ordinary result file contains and every fixture here means "a race that
    happened". THE LAW now requires somebody to have finished — an abandoned
    session is written by passing status="None" and ai_status="None", which is
    exactly what rF2 leaves behind after a restart."""
    # The player is always the row flagged isPlayer, exactly as rF2 writes it
    # — the name is "Your Name" on this machine and must never be what
    # identifies him.
    # A player position outside the field means no isPlayer row is written at
    # all, and the result is then correctly discarded for a reason that has
    # nothing to do with what the test was checking. Fail loudly instead.
    assert 1 <= player_pos <= field, "player_pos %d outside a %d-car field" % (
        player_pos, field)
    rows = []
    for i in range(1, field + 1):
        me = (i == player_pos)
        rows.append(DRIVER % {
            # rF2 reports the PROFILE name for the player, which is usually
            # the untouched placeholder — and the car is named after the
            # driver whose seat it is.
            "name": "Your Name" if me else "AI Driver %d" % i,
            "veh": "Williams  05-Nigel Mansell" if me else "#%d Car" % i,
            "team": "Williams" if me else "Team %d" % i,
            "cls": cls, "grid": i, "pos": i,
            "laps": player_laps if me else (race_laps if run_laps is None
                                            else run_laps),
            "status": status if me else ai_status, "me": 1 if me else 0})
    xml = ("""<?xml version="1.0"?>
<rFactorXML>
 <RaceResults>
  <DateTime>%d</DateTime>
  <TimeString>2026/01/01 12:00:00</TimeString>
  <TrackVenue>%s</TrackVenue>
  <TrackEvent>%s Grand Prix</TrackEvent>
  <RaceLaps>%d</RaceLaps>
  <Race>
%s  </Race>
 </RaceResults>
</rFactorXML>
""" % (when, venue, venue, race_laps, "".join(rows)))
    with open(os.path.join(dirname, fname), "w", encoding="utf-8") as f:
        f.write(xml)


tmp = tempfile.mkdtemp(prefix="factortv_career_")
store = os.path.join(tmp, "_career.json")
F1 = "F1 Test 2025"
OLD = "Formula 1 1992 Season by ASRC"

try:
    print("\n1. THE LAW — only a completed race counts")
    write_result(tmp, "a.xml", "Montreal", F1, 4, 20, race_laps=20, when=100)
    # He quit on lap two; the AI raced on and took the flag.
    write_result(tmp, "b.xml", "Montreal", F1, 8, 2, race_laps=20, when=200,
                 status="None")
    h = career_mod.History(store)
    h.scan(tmp)
    check(h.races == 1, "the race he finished is recorded", "%d race(s)" % h.races)
    rec = h.at("montreal", F1)
    check(rec and rec.get("visits") == 1,
          "and the race he quit on lap two left no trace at all",
          str(rec and rec.get("visits")))
    check(rec and rec.get("best") == 4,
          "so his 'worst result here' is not a race he never ran",
          "best=%s" % (rec or {}).get("best"))

    print("\n2. A REAL RETIREMENT IS A REAL RESULT")
    write_result(tmp, "c.xml", "Montreal", F1, 7, 17, race_laps=20,
                 status="DNF", when=300)
    h = career_mod.History(store)
    h.scan(tmp)
    rec = h.at("montreal", F1)
    check(rec.get("visits") == 2, "retiring at four-fifths distance counts",
          "visits=%d" % rec.get("visits"))
    check(rec.get("last_dnf") is True, "and is marked as a retirement")
    check(rec.get("best") == 4, "a DNF does not become a 'best finish'",
          "best=%s" % rec.get("best"))

    print("\n3. AGGREGATES")
    write_result(tmp, "d.xml", "Montreal", F1, 1, 20, when=400)
    write_result(tmp, "e.xml", "Zandvoort", F1, 3, 20, when=500)
    h = career_mod.History(store)
    h.scan(tmp)
    rec = h.at("montreal", F1)
    check(rec["wins"] == 1 and rec["best"] == 1, "a win is counted",
          "wins=%d best=%d" % (rec["wins"], rec["best"]))
    check(rec["last"] == 1, "and 'last time out' is the most recent race",
          "last=%s" % rec["last"])
    check(h.at("zandvoort", F1)["podiums"] == 1, "a third is a podium")
    check(h.data["races"] == 4, "four results across two circuits",
          str(h.data["races"]))

    print("\n4. RESCANNING DOES NOT DOUBLE-COUNT")
    before = h.races
    h.scan(tmp)
    h2 = career_mod.History(store)
    h2.scan(tmp)
    check(h2.races == before, "a second scan adds nothing",
          "%d -> %d" % (before, h2.races))

    print("\n5. CLASS IS NOT A DETAIL")
    write_result(tmp, "f.xml", "Zandvoort", OLD, 1, 20, when=600)
    h = career_mod.History(store)
    h.scan(tmp)
    same = h.at("zandvoort", OLD)
    other = h.at("zandvoort", F1)
    check(same["same_class"] and same["wins"] == 1,
          "a win in the 1992 car is a win in the 1992 car")
    check(other["same_class"] is True and other.get("wins", 0) == 0,
          "and is NOT claimable in the 2025 car",
          "wins=%s" % other.get("wins", 0))
    unknown = h.at("zandvoort", "Some GT3 Field")
    check(unknown is not None and not unknown["same_class"],
          "an unraced class still knows he has been to the circuit")

    print("\n6. THE BOOTH ONLY CLAIMS WHAT IT CAN BACK")
    b = Booth()
    b.career = h
    cars = grid()
    me = cars[0]
    me.is_player = True
    me.cls = F1
    s = FakeSession(cars, circuit=track_mod.Track("Montreal"))
    s.player = me
    cat, kw = b._career_call(s)
    check(cat == "career_won_here", "a win here is the strongest claim", str(cat))
    text, _, _ = lines_mod.pick(cat, s.era, kw)
    check(bool(text), "and there is a line for it", repr(text))

    # An unraced circuit. "First time at Silverstone" is only worth saying
    # once there is a career for it to contrast with — on race two of a new
    # career every circuit is a first visit and the observation is noise.
    s2 = FakeSession(cars, circuit=track_mod.Track("Silverstone"))
    s2.player = me
    real_races = h.data["races"]
    h.data["races"] = 2
    cat2, _ = b._career_call(s2)
    check(cat2 is None,
          "early in a career, an unraced circuit produces NOTHING", str(cat2))
    h.data["races"] = real_races
    cat2b, _ = b._career_call(s2)
    check(cat2b == "career_first_visit",
          "later on, a genuinely new circuit is worth remarking on", str(cat2b))

    b.career = None
    cat3, _ = b._career_call(s)
    check(cat3 is None, "and no career at all is survivable", str(cat3))

    print("\n7. THE DRIVER ROSTER")
    h = career_mod.History(store)
    h.scan(tmp)
    names = h.drivers(F1)
    # The one driver a result file can never list as an opponent is the one
    # the player IS — but the car carries his name.
    check("Nigel Mansell" in names,
          "the driver the player's own car is named after is included",
          ", ".join(names[:4]))
    check(not any(n.lower() == "your name" for n in names),
          "and rF2's profile placeholder is not", str(names[:6]))

    print("\n8. A VehName THAT NAMES A CAR IS NOT A DRIVER")
    for veh, expect in (("Williams  05-Nigel Mansell", "Nigel Mansell"),
                        ("#230 Masatomo Shimizu", "Masatomo Shimizu"),
                        ("63 Gary Madew", "Gary Madew"),
                        ("Lotus-Ford #12", ""),
                        ("Honda HSV-010 GT #002", ""),
                        ("21GT4FRA| #110 Team CMR", ""),
                        ("USF 2000 #07", ""),
                        ("Orange", "")):
        got = career_mod._veh_driver(veh, "Lotus", "Honda HSV-010 GT")
        check(got == expect, "%-28s -> %r" % (repr(veh), expect),
              "" if got == expect else "got %r" % got)

    print("\n9. AN UNKNOWN CIRCUIT IS NOT AN ERROR")
    write_result(tmp, "g.xml", "Some Private Test Track", F1, 2, 20, when=700)
    h = career_mod.History(store)
    n = h.scan(tmp)
    check(h.races == 6, "it still counts towards the overall record",
          str(h.races))
    check(not [k for k in h.data["tracks"] if "Private" in k],
          "but is not filed under a circuit the booth cannot name")

    print("\n10. A RESTART IS NOT A RACE, AND ITS LEADER IS NOT A WINNER")
    # THE BUG THIS SECTION EXISTS FOR, found by the user in a live session:
    # "I never ever won a race at Albert Park with Lando, only ever did a
    # quali session" — and the booth said "a winner at Albert Park already".
    #
    # His store held THREE wins there, every one from a fifteen-lap race
    # restarted after ONE lap. `MIN_SHARE` compares the player against the
    # WINNER, so when the whole field abandons together everybody's share is
    # 100% and the test passes trivially. It was written to catch "you quit
    # while the others finished" and is blind to "everybody stopped at once".
    rtmp = tempfile.mkdtemp(prefix="factortv_restart_")
    rstore = os.path.join(rtmp, "_career.json")
    try:
        # The exact shape of the real file: 15 scheduled, 1 run, player P1.
        write_result(rtmp, "restart.xml", "Albert Park", F1, 1, 1,
                     race_laps=15, run_laps=1, when=100,
                     status="None", ai_status="None")
        h = career_mod.History(rstore)
        h.scan(rtmp)
        check(h.races == 0,
              "a 15-lap race abandoned after ONE lap is not a race",
              "%d race(s)" % h.races)
        check(h.data.get("wins", 0) == 0,
              "so leading it is not a win — the phantom the user heard",
              "%d win(s)" % h.data.get("wins", 0))
        check(h.at("albertpark", F1) is None,
              "and the circuit has no history from it at all")

        # A quarter distance is still a restart. 26% is the real figure from
        # one of his files.
        write_result(rtmp, "quarter.xml", "Albert Park", F1, 1, 4,
                     race_laps=15, run_laps=4, when=200,
                     status="None", ai_status="None")
        h = career_mod.History(rstore)
        h.scan(rtmp)
        check(h.races == 0, "nor is one abandoned at a quarter distance",
              "%d race(s)" % h.races)

        # ...but an honest retirement in a race that WAS run still counts, and
        # that is the whole reason the threshold is generous rather than
        # demanding a chequered flag.
        # He retired, but he STAYED — the AI took the flag, so this is a real
        # race with a real retirement in it.
        write_result(rtmp, "real.xml", "Albert Park", F1, 2, 10,
                     race_laps=15, run_laps=15, status="DNF", when=300)
        h = career_mod.History(rstore)
        h.scan(rtmp)
        check(h.races == 1, "a retirement in a race that FINISHED is a race",
              "%d race(s)" % h.races)
        rec = h.at("albertpark", F1)
        check(rec and rec.get("last_dnf") is True,
              "and his retirement in it is recorded as one")
        check(rec and not rec.get("wins"),
              "with no win attached to the circuit", str(rec and rec.get("wins")))

        # THE FLAG OVERRIDES THE LAP COUNT. A genuinely shortened race that
        # somebody FINISHED is a race whatever its length — the lap rule alone
        # would throw it away.
        stmp = tempfile.mkdtemp(prefix="factortv_short_")
        try:
            write_result(stmp, "short.xml", "Montreal", F1, 1, 3,
                         race_laps=20, run_laps=3,
                         status="Finished Normally",
                         ai_status="Finished Normally", when=100)
            h2 = career_mod.History(os.path.join(stmp, "_career.json"))
            h2.scan(stmp)
            check(h2.races == 1,
                  "a short race somebody actually FINISHED still counts",
                  "%d race(s)" % h2.races)
            check(h2.data.get("wins", 0) == 1,
                  "and winning that one is a real win",
                  "%d win(s)" % h2.data.get("wins", 0))
        finally:
            shutil.rmtree(stmp, ignore_errors=True)
    finally:
        shutil.rmtree(rtmp, ignore_errors=True)

finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n11. WHAT YOU MAY RACE IS NOT WHAT YOU HAVE WON")
# LAW 3: context is free, RECORDING is confirmed — and the two must not share
# a gate. Tightening THE LAW to "somebody must have finished" cut the store
# from 68 races to 2, and because the New Career class list was built only
# from folded RESULTS it took the menu down with it: two selectable classes
# out of eighty-two installed car mods. The user asked where they had gone.
#
# Owning a car and having won in it are different claims. Getting the first
# wrong costs a line in a menu; getting the second wrong costs the broadcast.
ctmp = tempfile.mkdtemp(prefix="factortv_ctx_")
try:
    cstore = os.path.join(ctmp, "_career.json")
    # A restart: nobody finished, so it is NOT a result...
    write_result(ctmp, "abandoned.xml", "Spa", "GT3 2020", 3, 1,
                 race_laps=15, run_laps=1, when=100,
                 status="None", ai_status="None")
    h = career_mod.History(cstore)
    h.scan(ctmp)
    check(h.races == 0, "an abandoned session is still not a race",
          "%d race(s)" % h.races)
    names = [c["name"] for c in h.classes()]
    check("GT3 2020" in names,
          "...but the car class is still offered as a championship", str(names))
    check(h.data["classes"]["GT3 2020"].get("races", 0) == 0,
          "with an honest race count of zero",
          str(h.data["classes"]["GT3 2020"].get("races")))
    check(len(h.drivers("GT3 2020")) >= 3,
          "and the grid it ran against, so a career can pick a name from it",
          "%d drivers" % len(h.drivers("GT3 2020")))

    # A QUALIFYING session counts as context too. The user's own words: he had
    # "only ever done a quali session" in a car — which is still a car he owns
    # and a grid he can race.
    qtmp = tempfile.mkdtemp(prefix="factortv_q_")
    try:
        qstore = os.path.join(qtmp, "_career.json")
        with open(os.path.join(qtmp, "q.xml"), "w", encoding="utf-8") as f:
            rows = "".join(DRIVER % {
                "name": "Your Name" if i == 1 else "AI %d" % i,
                "veh": "car", "team": "T", "cls": "LMP2 2024",
                "grid": i, "pos": i, "laps": 5, "status": "None",
                "me": 1 if i == 1 else 0} for i in range(1, 7))
            f.write('<?xml version="1.0"?><rFactorXML><RaceResults>'
                    '<DateTime>500</DateTime><TrackVenue>Spa</TrackVenue>'
                    '<RaceLaps>0</RaceLaps><Qualify>%s</Qualify>'
                    '</RaceResults></rFactorXML>' % rows)
        hq = career_mod.History(qstore)
        hq.scan(qtmp)
        check(hq.races == 0, "a qualifying session is never a race result")
        check("LMP2 2024" in [c["name"] for c in hq.classes()],
              "but it does tell us the user owns that grid",
              str([c["name"] for c in hq.classes()]))
    finally:
        shutil.rmtree(qtmp, ignore_errors=True)

    # A SOLO RUN IS NOT A CHAMPIONSHIP. One car alone covers 100% of its own
    # field and sails past every share test there is; the first version of
    # this offered "Mazda 787B" and "National" as seasons with a grid of
    # nobody.
    stmp = tempfile.mkdtemp(prefix="factortv_solo_")
    try:
        write_result(stmp, "solo.xml", "Spa", "Mazda 787B", 1, 2,
                     race_laps=15, run_laps=2, field=1, when=600,
                     status="None", ai_status="None")
        hs = career_mod.History(os.path.join(stmp, "_career.json"))
        hs.scan(stmp)
        check("Mazda 787B" not in [c["name"] for c in hs.classes()],
              "a car taken out alone is not offered as a season",
              str([c["name"] for c in hs.classes()]))
    finally:
        shutil.rmtree(stmp, ignore_errors=True)
finally:
    shutil.rmtree(ctmp, ignore_errors=True)

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
