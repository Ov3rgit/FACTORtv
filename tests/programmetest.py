"""The junior programme: three seats, a championship, and a year out.

    python tests/programmetest.py

THE ONE SCRIPTED ARC ON THE LADDER, and the only place this product tells a
story about a real team. So most of this file is about what it must NOT do:
never claim a team signed him as fact, never promise a seat the game cannot
deliver, never let two of the three choices lead to the same place, and never
survive into a career that did not earn it.

The shape is the user's own: three seats at the start of Formula 2, each
backed by a Formula One programme; win the championship and the seat is
offered with a development year attached; miss it and the programme waits one
more season and then stops waiting.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import inbox
import personal
import programme as P
import ladder as L
import season as S

fails = []
def check(c, l, e=""):
    print(("  [ OK ] " if c else "  [FAIL] ") + l + (("  " + e) if e else ""))
    if not c:
        fails.append(l)


_tmp = tempfile.mkdtemp(prefix="factortv_prog_")
S.CAREER_DIR = _tmp
ME = "Kandasamy"


# THE ARC NOW BEGINS ON THE FORMULA 3 RUNG, at the user's call: the F3 mod names
# real teams per entry, so a seat can be verified against what he selected in the
# game, and academies sign drivers INTO F3 and prove them in F2 — which is the
# real ladder rather than a compressed version of it.
F3_TIER = next(i for i, t in enumerate(L.tiers("single_seater"))
               if t["key"] == "f3")
F2_TIER = next(i for i, t in enumerate(L.tiers("single_seater"))
               if t["key"] == "f2")


def f3_career(rounds=3):
    """A career on the Formula 3 rung, where the arc is offered."""
    return S.create("open", me=ME, rounds=rounds,
                    ladder_path="single_seater", tier_index=F3_TIER)


def f2_career(rounds=3):
    """Signed, called up, and now racing Formula 2 — the state most of these
    sections were written against, reached the way the game reaches it.

    `rounds` is the length of the F2 season, so the F3 half is sized to leave
    exactly that many rounds after the call-up.
    """
    call_at = 4
    c = S.create("open", me=ME, rounds=rounds + call_at,
                 ladder_path="single_seater", tier_index=F3_TIER)
    return c


def to_f2(c, key="mercedes", pos=2):
    """Sign for a programme, race the Formula 3 half, take the call-up.

    THE JOURNEY, NOT A SHORTCUT. Setting the rung by hand would test a state the
    game cannot reach; this goes through `offer` -> `accept` -> the call-up letter,
    which is the only route that exists.
    """
    P.accept(c, key)
    for n in range(1, c.callup_round() + 1):
        race(c, pos, n)
    inbox.refresh(c)              # the letter is what moves him
    return c


# A REAL FIELD, because the programme's bar is now a POSITION IN THE STANDINGS
# rather than a win — and with two cars classified, "he finished fourth" makes him
# second in the table, which is not a test of anything.
FIELD = ("Marcus Vinter", "Theo Vasseur", "Sam Okonkwo", "Ahti Jyrki",
         "Norbert Truls")


def race(c, pos, n):
    order = list(FIELD)
    order.insert(max(0, pos - 1), ME)
    c.record({"n": n, "slug": "t%d" % n, "pos": pos, "laps": 20,
              "race_laps": 20,
              "classified": [(nm, i + 1) for i, nm in enumerate(order)]})


def season(c, pos, rounds=None):
    """Race whatever is LEFT of this season.

    Not "race N rounds": a called-up season already has its opening rounds on the
    board as absences, and a finale is a fixed ten whatever the career chose. Every
    caller here means "finish the season", so that is what this does.
    """
    total = c.total_rounds or rounds or 3
    done = {r.get("n") for r in c.rounds if r.get("n")}
    for n in range(1, total + 1):
        if n not in done:
            race(c, pos, n)


# ---------------------------------------------------------------------------
print("\n1. THE DATA OBEYS ITS OWN RULES")
errs = P.validate()
check(not errs, "programmes.json validates", "; ".join(errs[:3]))
check(len(P.all_programmes()) == 3, "there are exactly three seats",
      str(len(P.all_programmes())))

# TWO OF THE THREE MUST NOT LEAD TO THE SAME PLACE, or one of the choices is
# not a choice. `validate()` holds it; this states it as a fact of the file.
seats = [b.get("f1_seat") for _k, b in P.all_programmes()]
teams = [b.get("f1_team") for _k, b in P.all_programmes()]
check(len(set(seats)) == 3 and len(set(teams)) == 3,
      "each one leads to a different team and a different seat",
      str(list(zip(teams, seats))))

# HE ARRIVES ALONGSIDE SOMEBODY, NOT INSTEAD OF THEM. The seat he takes and
# the man he races are two different people, or the arrival letter tells him
# he is replacing his own team-mate.
bad = [k for k, b in P.all_programmes()
       if b.get("f1_seat") == b.get("f1_lead")]
check(not bad, "and he is never told he replaced his own team-mate", str(bad))


# ---------------------------------------------------------------------------
print("\n2. THE OFFER, AND WHEN IT IS NOT AVAILABLE")
c = f2_career()
check(P.state(c) == P.OFFERED, "arriving in Formula 2 opens the offer",
      P.state(c))
check(len(P.offer(c)) == 3, "all three seats are on the table",
      str([o["f2_team"] for o in P.offer(c)]))

# A DRIVER SIGNS BEFORE THE YEAR, NOT DURING IT. An offer that arrives after
# round four is a letter about a season already happening.
mid = f2_career()
race(mid, 1, 1)
check(not P.offer(mid), "a season already under way gets no offer")

# ...and it is not open to anybody who is not there.
kart = S.create("open", me=ME, rounds=3, ladder_path="single_seater",
                tier_index=0)
check(not P.offer(kart) and P.state(kart) == P.NONE,
      "a karting career is offered nothing", P.state(kart))
plain = S.create("open", me=ME, rounds=3)
check(P.state(plain) == P.NONE, "and a season with no ladder has no arc")

P.accept(c, "ferrari")
check(P.state(c) == P.SIGNED, "signing moves him on", P.state(c))
check(not P.offer(c), "and the offer closes behind him")
check(P.signed(c)[0] == "ferrari", "the programme is remembered")


# ---------------------------------------------------------------------------
print("\n2b. THE CALL-UP — Formula 3 to Formula 2, mid-season")
# The user's plot twist: signed into F3 by an academy, and four rounds in the
# academy's F2 team makes a change and puts him in the car for the rest of that
# year. It also solves the year problem — F3 2019 into F2 2019 is ONE season, not
# two arcs occupying the same period.
#
# HIS FIRST IDEA WAS A FATAL CRASH, drawn from Spa 2019, and it was dropped for a
# concrete reason: Juan Manuel Correa is in the F2 2019 mod's roster. He was
# critically injured in that crash. The seat logic names the man whose place is
# taken, so the arc could have handed the player HIS seat with a crash as the
# stated cause. "The team dropped him for form" gives identical mechanics — and
# NOBODY IS NAMED even so, because that is a claim about a real driver.
cu = f3_career(10)
check(P.on_f3(cu) and not P.on_f2(cu),
      "the arc is offered on the Formula 3 rung now")
check(all(o.get("f3_team") for o in P.offer(cu)) and P.offer(cu),
      "and every seat names a Formula 3 team he can actually select")
P.accept(cu, "ferrari")
check(not P.callup_ready(cu), "no call-up before he has raced")
for _n in (1, 2, 3):
    race(cu, 2, _n)
check(not P.callup_ready(cu), "nor three rounds in")
race(cu, 2, 4)
check(P.callup_ready(cu), "four rounds in, the seat opens")

_got = inbox.refresh(cu)
_call = [m for m in (_got or []) if m and m["kind"] == "prog_callup"]
check(bool(_call), "and the LETTER is what moves him")
_txt = " ".join(_call[0]["body"]) if _call else ""
check(_call and "Prema" in (_call[0]["subject"] + _txt),
      "naming the team whose car he is taking")
_real = ("Correa", "Hubert", "Latifi", "Ghiotto", "Aitken", "Mazepin", "Zhou")
check(not [n for n in _real if n in _txt],
      "and never naming the driver who lost the seat", _txt[:70])
check(P.on_f2(cu), "he is on the Formula 2 rung from that moment")

# THE SEASON HE JOINS IS ALREADY UNDER WAY. Two rounds simulated as ABSENCES —
# positions and points, never events — so the field has scored and he has not.
check(cu.total_rounds == 10, "a called-up season is a fixed ten rounds",
      str(cu.total_rounds))
check(len(cu.rounds) == 2, "with its opening rounds already run",
      str(len(cu.rounds)))
check(all((r.get("pos") or 0) == 0 for r in cu.rounds),
      "and he is not classified in any of them")
_st = cu.title_state() or {}
check((_st.get("leader_points") or 0) > 0 and not _st.get("my_points"),
      "so somebody leads the championship and he is on nothing",
      "leader %s on %s" % (_st.get("leader"), _st.get("leader_points")))
_hist = (cu.data.get("ladder_history") or [])[-1]
check(_hist.get("cut_short") and _hist.get("rounds") == 4
      and _hist.get("of") == 10,
      "and Formula 3 is recorded as CUT SHORT, four of ten",
      str({k: _hist.get(k) for k in ("rounds", "of", "cut_short")}))

# THE BAR IS A PODIUM, AND WHAT MAY BE SAID ABOUT IT IS DIFFERENT.
season(cu, 3)
check(P.season_verdict(cu) == P.WON,
      "third in the standings is what the academy asked for")
P.apply_verdict(cu)
inbox.refresh(cu)
_won = [m for m in inbox.messages(cu) if m["kind"].startswith("prog_won")]
check(_won and _won[0]["kind"] == "prog_won_callup",
      "and the letter is the PROMOTION one, not the championship one",
      str([m["kind"] for m in _won]))
_wtxt = " ".join(_won[0]["body"]).lower() if _won else ""
# NOT A KEYWORD SWEEP. The best of these letters says "nobody is calling you a
# champion and nor should you", which is the exact sentence wanted — so what must
# be absent is the CLAIM, not the word.
check("congratulations on the championship" not in _wtxt,
      "which never congratulates him on a championship he did not win",
      _wtxt[:80])
check("you are the champion" not in _wtxt and "champion of" not in _wtxt,
      "and never states he is one")
check("third" in _wtxt, "and says what he actually did")



# ---------------------------------------------------------------------------
print("\n3. WINNING IT MEANS WINNING IT")
# The ladder's own bar for leaving Formula 2 is third. The programme's bar is
# the championship — which is what puts two different stakes on the same
# afternoon, and is the whole reason the last round matters.
won = to_f2(f2_career(), "mercedes")
check(P.season_verdict(won) is None, "mid-season there is nothing to judge")
season(won, 1)
check(P.season_verdict(won) == P.WON, "first place wins the seat")

# THE BAR IS A PODIUM IN THE STANDINGS FOR A CALLED-UP SEASON, not the title:
# he arrives two rounds down with nothing on the board, so a championship is out
# of reach and a bar nobody can clear is not a bar. Fourth is the failure now.
third = to_f2(f2_career(), "red_bull")
season(third, 3)
check(P.season_verdict(third) == P.WON,
      "a podium in the championship is what a mid-season signing is asked for",
      str(P.season_verdict(third)))

fourth = to_f2(f2_career(), "red_bull")
season(fourth, 4)
check(P.season_verdict(fourth) == P.RETRY,
      "and fourth is not enough", str(P.season_verdict(fourth)))


# ---------------------------------------------------------------------------
print("\n4. THEY WAIT ONCE, AND THEN THEY STOP WAITING")
r = to_f2(f2_career(), "red_bull")
season(r, 4)
check(P.apply_verdict(r) == P.RETRY, "a missed season keeps the seat open")
check(r.data["programme"]["attempts"] == 2, "and is counted")
r.data["rounds"] = []; r.save()
season(r, 4)
check(P.apply_verdict(r) == P.DROPPED, "a second one ends it")
check(P.state(r) == P.DROPPED, "and that is where he stays", P.state(r))
# HE KEEPS RACING. Nothing in this product should ever refuse to let a man
# drive — the door is shut, the career is not.
check(r.on_ladder and r.tier(), "the career itself is untouched")


# ---------------------------------------------------------------------------
print("\n5. THE YEAR OUT")
P.apply_verdict(won)
check(P.state(won) == P.WON, "the seat is on the table")
check(P.seat(won) == ("Mercedes", "Valtteri Bottas", "Lewis Hamilton"),
      "and it names the team, the seat and the man beside him",
      str(P.seat(won)))
check(not P.seat_ready(won), "but it is not his yet")
check(P.take_deal(won), "taking the deal is his to take")
check(P.state(won) == P.DEV, "which starts the development year")

# THE YEAR HAS NO CLOCK, so it is not measured in time. It used to be measured
# in LETTERS alone; since the user found the F1 2020 mod it is measured in
# letters AND test outings, and both halves are required — see section 5b.
for i in range(P.DEV_BEATS):
    check(not P.seat_ready(won),
          "letter %d of %d and the seat is still not open" % (i + 1,
                                                              P.DEV_BEATS))
    P.advance_dev(won)
check(not P.seat_ready(won),
      "reading every letter is NOT the whole year any more")
for _slug in ("interlagos", "spa", "suzuka"):
    P.test_tick(won, _slug, laps=18, best=88.5)
check(P.seat_ready(won),
      "the seat opens when the letters are read AND the testing is done")


print("\n5b. THE TEST PROGRAMME — three practice outings in last year's car")
# The user found the F1 2020 mod and asked what the year out was for. His own
# design, and it is what junior drivers actually do — private testing in last
# season's car:
#
#   "can we make it so that they HAVE to set up a practice session for it to be
#    picked up properly ... SESSION TYPE: Practice, Car Class: Ferrari 2020 car
#    (depending on the path they chose) ... if they just start a practice and all
#    parameters are met then boom that will be a tick ... this way the practice
#    isn't completed by ending the session, just by starting it, so they can
#    choose how long they want to run for and which track also."
#
# THE PARAMETERS ARE CHECKABLE ON ARRIVAL, which is the whole reason it works:
# session type, car and circuit are all known the moment he is on track, so the
# overlay never judges whether he has tested ENOUGH.
t = to_f2(f2_career(), "mercedes")   # signed in F3, called up to F2
season(t, 1)                         # and won it from there
P.apply_verdict(t)
P.take_deal(t)
check(P.state(t) == P.DEV, "the development year is running")
st = P.test_state(t)
check(st["of"] == 3 and st["n"] == 0,
      "three outings, none of them served yet", str((st["n"], st["of"])))
check(st["team"] == "Mercedes",
      "against the car of the programme he signed for", st["team"])

# EVERY PARAMETER REFUSES FOR ITS OWN REASON, and the reason is returned rather
# than a bare False — a control that does nothing and says nothing is the exact
# complaint that produced this feature.
ok, why = P.test_check(t, kind="race", cls="Mercedes", year=2020,
                       slug="spa")
check(not ok and why, "a RACE is not a test outing", str(why))
ok, why = P.test_check(t, kind="practice", cls="Mercedes", year=2021,
                       slug="spa")
check(not ok and why, "and neither is this year's car", str(why))
ok, why = P.test_check(t, kind="practice", cls="Ferrari", year=2020,
                       slug="spa")
check(not ok and why, "nor somebody else's car", str(why))
ok, why = P.test_check(t, kind="practice", cls="Mercedes", year=2020,
                       slug="spa", on_track=False)
check(not ok and why, "nor sitting in the garage looking at it", str(why))
ok, why = P.test_check(t, kind="practice", cls="Mercedes", year=2020,
                       slug="spa")
check(ok and not why, "practice, the right car, on track — that is an outing",
      str(why))

# A CLASS THAT NAMES NO TEAM IS UNKNOWN, NOT WRONG. Same rule the seat follows:
# a mod that publishes one class for the whole field must not be able to stop
# the year progressing.
ok, why = P.test_check(t, kind="practice", cls="Formula One 2020", year=2020,
                       slug="spa")
check(ok, "a mod that does not name teams still counts", str(why))

# ONE OUTING PER CIRCUIT, which is what makes three outings three test days
# rather than three sessions at the same track.
P.test_tick(t, "spa", laps=20, best=104.2)
check(P.test_state(t)["n"] == 1, "the outing is banked")
check(P.test_tick(t, "spa") is None, "the same circuit cannot be used twice")
ok, why = P.test_check(t, kind="practice", cls="Mercedes", year=2020,
                       slug="spa")
check(not ok and why, "and it says so rather than silently ignoring him",
      str(why))
P.test_tick(t, "monza", laps=14, best=82.0)
check(P.test_state(t)["left"] == 1, "two down, one to go",
      str(P.test_state(t)))
check(not P.seat_ready(t), "and the seat is not open on two of three")

# WHAT HE DID IS KEPT, because the team's report is written from it — laps and a
# best lap, which the overlay watched. A test has no result to quote.
runs = (t.data.get("programme") or {}).get("test_runs") or []
check(len(runs) == 2 and runs[0]["laps"] == 20 and runs[0]["best"] > 0,
      "with the laps and the best lap of each run", str(runs[:1]))

# ...AND THE OUTINGS ALONE ARE NOT THE YEAR EITHER. Both halves, in both
# directions: this career has driven the testing and read nothing.
P.test_tick(t, "interlagos", laps=25, best=88.1)
check(P.test_state(t)["n"] == 3, "three outings served")
check(not P.seat_ready(t),
      "driving all three without a word from the team is not a year either")
for _i in range(P.DEV_BEATS):
    P.advance_dev(t)
check(P.seat_ready(t), "with both halves done, the seat is his")

# NOTHING TICKS OUTSIDE THE DEVELOPMENT YEAR.
check(P.test_tick(t, "kyalami") is None,
      "an outing after the seat is open changes nothing")
fresh = f2_career()
P.accept(fresh, "ferrari")
check(not P.test_wanted(fresh),
      "and a career that has not taken the deal is not testing")


# ---------------------------------------------------------------------------
print("\n6. THE LETTERS ARRIVE, AND EACH ONE ONCE")
c2 = f2_career()
inbox.refresh(c2)
kinds = [m["kind"] for m in inbox.messages(c2)]
check("prog_offer" in kinds, "the offer is written to him", str(set(kinds)))
P.accept(c2, "ferrari")
inbox.refresh(c2)
before = len(inbox.messages(c2))
for _ in range(4):
    inbox.refresh(c2)
check(len(inbox.messages(c2)) == before,
      "and refreshing four times posts nothing twice",
      "%d -> %d" % (before, len(inbox.messages(c2))))

# THE SENDER IS THE TEAM. `{team}` in a FROM line is the most visible slot
# failure available, because an inbox is a list of senders and subjects.
#
# Raced THROUGH the call-up: the seat letter only exists once the Formula 2 half
# has been won, and the Formula 2 half only exists once the academy has moved him
# into it.
for _n in range(1, c2.callup_round() + 1):
    race(c2, 2, _n)
inbox.refresh(c2)                    # the call-up letter moves him
season(c2, 1); P.apply_verdict(c2); inbox.refresh(c2)
senders = {m["from"] for m in inbox.messages(c2)}
check(not [s for s in senders if "{" in s],
      "no letter arrives from an unfilled slot", str(sorted(senders)))
check("Ferrari" in senders, "the team writes under its own name",
      str(sorted(senders)))


# ---------------------------------------------------------------------------
print("\n7. SHE WRITES THROUGH THE YEAR")
# The thread paces on SEASONS, so a year with no rounds would stall it exactly
# where a real sibling would write MORE — he is not racing, so for the first
# time in years he is around. And it sharpens the story's whole thesis: the
# year he had nothing to do is the year he still did not go home.
P.take_deal(c2)
mel = []
for _ in range(P.DEV_BEATS + 2):
    inbox.refresh(c2)
    for m in personal.refresh(c2):
        if m.get("from") == "Mel":
            mel.append(m["subject"])
check(mel, "she writes during the development year", str(mel))
check(len(mel) <= personal.DEV_YEAR_BEATS + 1,
      "and not once a week", "%d letters" % len(mel))

# POSTED, NOT JUST RETURNED. The first version handed the raw template back to
# `refresh`, which counted it as sent and never wrote it to the archive — so
# the year was silent while the code reported two letters.
archived = [m["subject"] for m in inbox.messages(c2) if m["from"] == "Mel"]
check(all(s in archived for s in mel),
      "and every one of them is in the archive", str(archived))


# ---------------------------------------------------------------------------
print("\n7b. THE SEAT IS A CAR, NOT A TEAM")
# The user: "make it so the races will only pick up for the teammate's car -
# if I'm locked in with Bottas then I HAVE to use Bottas's car to continue
# the F1 season arc." Two years of climbing bought one seat, and the other
# Mercedes is somebody else's.
#
# THE CLASS LOCK CANNOT DO THIS. Both cars report `Mercedes`; only the entry
# name differs, and rF2 names each one for its driver.
seat_c = to_f2(f2_career(), "mercedes")
season(seat_c, 1)
P.apply_verdict(seat_c); P.take_deal(seat_c)
# THE YEAR IS LETTERS AND TESTING NOW, so serving it means both — the seat is
# what this section is about and it cannot open on half a programme.
for _ in range(P.DEV_BEATS):
    P.advance_dev(seat_c)
for _slug in ("spa", "monza", "suzuka"):
    P.test_tick(seat_c, _slug, laps=20, best=99.0)
seat_c.data["rounds"] = []
seat_c.data["ladder"]["reached"] = 4      # Formula One
seat_c.save()
check(P.seat(seat_c) == ("Mercedes", "Valtteri Bottas", "Lewis Hamilton"),
      "the seat names the car and the man beside it", str(P.seat(seat_c)))
check(seat_c.match("spa", cls="Mercedes", year=2021,
                   vehicle="#77 - Valtteri Bottas"),
      "his own entry counts as a round")
check(not seat_c.match("spa", cls="Mercedes", year=2021,
                       vehicle="#44 - Lewis Hamilton"),
      "the other side of the garage does not")

# REFUSED ONLY WHEN HE IS POSITIVELY IN THE OTHER ONE. An entry string that
# names neither driver is unknown, not wrong - a mod that labels its cars
# some other way must not silently stop a career counting, which is the
# worst failure this module has.
check(seat_c.match("spa", cls="Mercedes", year=2021, vehicle="Mercedes W12"),
      "a name we cannot read falls through rather than refusing")
check(seat_c.match("spa", cls="Mercedes", year=2021, vehicle=""),
      "and so does no entry name at all")

# ...AND IT ONLY APPLIES ONCE THE SEAT IS ACTUALLY HIS. Before the
# development year is served there is nothing to be locked out of.
early = to_f2(f2_career(), "mercedes")
check(early.match("t1", cls="Formula 2 2019",
                  vehicle="#44 - Lewis Hamilton"),
      "in Formula 2 the seat lock does not apply yet")


print("\n8. NOTHING ABOUT IT SURVIVES A CAREER THAT DID NOT EARN IT")
fresh = f2_career()
check(P.state(fresh) == P.OFFERED and not P.signed(fresh)[0],
      "a new career starts the arc from the beginning", P.state(fresh))

shutil.rmtree(_tmp, ignore_errors=True)

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
