# -*- coding: utf-8 -*-
"""
FACTORtv — the junior programme, and the road out of Formula 2.

THE USER'S OWN DESIGN, and it is the one part of the ladder that is scripted
rather than general:

  1. At the start of a Formula 2 season he is offered THREE SEATS, each backed
     by a different Formula One junior programme. Which he takes decides which
     door opens later.
  2. Finish the season and the programme responds. Win it and the seat is
     offered — but not for next year: he commits to A DEVELOPMENT YEAR first
     and starts in the 2021 season.
  3. Miss it and the programme keeps faith ONCE. A second failure and it is
     over; he keeps racing, but that door is shut for this career.
  4. He always takes the SECOND SEAT, alongside an established number one.

WHY THIS IS A MODULE AND NOT MORE LADDER CODE
---------------------------------------------
`ladder.py` owns where a championship SITS and knows nothing about stories.
This is a state machine with four terminal states and a memory, and it writes
to the career file — which is exactly the shape `personal.py` already has for
the family thread. Keeping it separate means the ladder stays general: every
other path on it is untouched by any of this.

WHAT IT REFUSES TO DO
---------------------
* CLAIM A REAL TEAM SIGNED HIM. Every letter is in-world, the career is a
  dramatisation, and `DISCLAIMER` already draws that line for the whole
  product. The programmes are written as BACKING a Formula 2 entrant, which
  is how junior academies actually work, rather than as owning one.
* PROMISE A SEAT IT CANNOT DELIVER. rF2 decides which car he loads, not this
  overlay — so the seat is an OFFER and an instruction about what to select,
  never an assertion that he is in it. What he actually drove is read back
  from the result, the same rule the car pick follows.
* SURVIVE A DIFFERENT CAREER. It lives in the career file, so a fresh career
  genuinely replays it.

THE SECOND SEAT IS THE POINT
----------------------------
He arrives alongside a champion in the same machinery, and from that moment
the booth's team-mate comparison — the only measurement in this sport with
nothing to explain it away — is running against one of the best drivers in
the game. That is what the whole climb has been for.
"""
import json
import os
import sys

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(_DIR, "lines_data", "programmes.json")

# The rung this happens on. Written as a KEY rather than an index because the
# single-seater path could gain a rung and an index would silently move.
F2_KEY = "f2"
F1_KEY = "f1"

# How many seasons the programme will wait. The user's call: "another F2
# season, seat still open" — and then it is over. One retry is what makes the
# first season matter without ending a career on one bad year.
MAX_ATTEMPTS = 2

# The stages, in order. `state()` returns one of these.
NONE = "none"           # not on the F2 rung, or never offered
OFFERED = "offered"     # three seats on the table, nothing chosen
SIGNED = "signed"       # racing F2 for a programme
RETRY = "retry"         # missed it once; the seat is still open
DROPPED = "dropped"     # missed it twice; that door is shut
WON = "won"             # won F2 - the F1 seat has been offered
DEV = "dev"             # took the deal, serving the development year
SEAT = "seat"           # the development year is done; the seat is his

_data = None


def load(force=False):
    global _data
    if _data is None or force:
        try:
            with open(DATA, "r", encoding="utf-8") as f:
                _data = json.load(f)
        except Exception:
            _data = {}
        _data.pop("_note", None)
    return _data


def all_programmes():
    """[(key, block)] in a stable order, so the three seats are always
    offered in the same order and a save cannot reshuffle them."""
    d = load()
    return sorted((k, v) for k, v in d.items() if isinstance(v, dict))


def get(key):
    return load().get(key or "")


def _block(career):
    return (career.data.get("programme") or {}) if career is not None else {}


def on_f2(career):
    """Is this career sitting on the Formula 2 rung right now?"""
    if career is None or not getattr(career, "on_ladder", False):
        return False
    prog = career.ladder
    tier = (prog.tier() or {}) if prog is not None else {}
    return tier.get("key") == F2_KEY


def state(career):
    """Where he is in the programme story. Never raises."""
    b = _block(career)
    st = b.get("stage") or NONE
    if st != NONE:
        return st
    return OFFERED if on_f2(career) else NONE


def signed(career):
    """The programme he is on, as (key, block), or (None, None)."""
    b = _block(career)
    k = b.get("key")
    return (k, get(k)) if k else (None, None)


def offer(career):
    """The three seats, or [] if this is not the moment for them.

    Offered on the Formula 2 rung and only before a season has been raced:
    a driver signs for a team BEFORE the year, and offering him a seat after
    round four is a letter about a season that is already happening.
    """
    if not on_f2(career) or state(career) not in (OFFERED,):
        return []
    if career.rounds:
        return []
    return [dict(b, key=k) for k, b in all_programmes()]


def accept(career, key):
    """Take one of the three seats. Returns the block, or None.

    WRITES, and it is the decision the rest of the arc hangs on — so the
    caller puts it behind a confirmation, exactly as the car pick and the
    career delete are.
    """
    b = get(key)
    if b is None or not on_f2(career) or career.rounds:
        return None
    career.data["programme"] = {"key": key, "stage": SIGNED, "attempts": 1}
    career.save()
    return b


def season_verdict(career):
    """What the programme makes of the season just finished.

    Returns one of WON / RETRY / DROPPED, or None if there is nothing to
    judge yet. WRITES NOTHING — the same split `evaluate()` and `advance()`
    make on the ladder, and for the same reason: this is read on every menu
    draw.

    WINNING IT MEANS FINISHING FIRST, not merely earning promotion. The
    ladder's own bar for leaving Formula 2 is third; the programme's bar is
    the championship, which is what makes the two different stakes on the
    same afternoon.
    """
    b = _block(career)
    if b.get("stage") not in (SIGNED, RETRY):
        return None
    if not career.season_done():
        return None
    pos = career.my_position()
    if pos == 1:
        return WON
    return RETRY if int(b.get("attempts") or 1) < MAX_ATTEMPTS else DROPPED


def apply_verdict(career):
    """Bank the verdict at the end of an F2 season. Returns the new stage.

    Called once, when the season is complete — idempotent, because it only
    ever moves a stage forward and each move is recorded.
    """
    v = season_verdict(career)
    if v is None:
        return None
    b = dict(_block(career))
    if v == WON:
        b["stage"] = WON
    elif v == RETRY:
        b["stage"] = RETRY
        b["attempts"] = int(b.get("attempts") or 1) + 1
    else:
        b["stage"] = DROPPED
    career.data["programme"] = b
    career.save()
    return b["stage"]


def take_deal(career):
    """Accept the development year. Returns True if it was his to take.

    THE COST IS A YEAR, and it is the whole point of the beat: the seat is
    real and it is not for now. He agrees to a season out and starts in 2021.
    """
    b = dict(_block(career))
    if b.get("stage") != WON:
        return False
    b["stage"] = DEV
    b["dev_read"] = 0
    career.data["programme"] = b
    career.save()
    return True


def dev_letters(career):
    """How many development-year letters have been read, and how many exist.

    THE YEAR HAS NO CLOCK TO HANG ON, and that is a real problem rather than
    a detail: this product has no calendar, and a "year" is only ever "the
    next season you race" — which, during a year out, does not happen. So the
    user's call was that it arrives as CORRESPONDENCE: a short arc of letters
    he reads through, and the seat opens when they are done.

    Nothing here counts races, because there are none to count.
    """
    b = _block(career)
    return int(b.get("dev_read") or 0), len(load().get("_dev_beats") or ()) or DEV_BEATS


# How many letters the development year is made of. Enough to feel like a
# season away and few enough that it cannot outstay the moment it exists to
# create.
DEV_BEATS = 5


def advance_dev(career):
    """One development-year beat has landed. Returns the new count."""
    b = dict(_block(career))
    if b.get("stage") != DEV:
        return None
    n = int(b.get("dev_read") or 0) + 1
    b["dev_read"] = n
    career.data["programme"] = b
    _maybe_seat(career, b)
    career.save()
    return n


# ---------------------------------------------------------------------------
# THE TEST PROGRAMME — the development year, driven
#
# The user found the F1 2020 mod and asked the obvious question: the year out
# sits in 2020, so what is it for? His own answer is better than the letters it
# replaces, and it is what junior drivers actually do — TPC, private testing in
# last season's car:
#
#   "can we make it so that they HAVE to set up a practice session for it to be
#    picked up properly ... SESSION TYPE: Practice, Car Class: Ferrari 2020 car
#    (depending on the path they chose) ... if they just start a practice and all
#    parameters are met then boom that will be a tick ... this way the practice
#    isn't completed by ending the session, just by starting it, so they can
#    choose how long they want to run for and which track also."
#
# THE PARAMETERS ARE CHECKABLE ON ARRIVAL, which is what makes this work: the
# session type, the car and the circuit are all known the moment he is on track,
# so the overlay never has to judge whether he has tested ENOUGH. The programme
# states its terms; he meets them; the tick lands.
#
# IT IS THE TEAM'S OWN CAR. These A&M Formula One mods publish the CONSTRUCTOR
# as the CarClass — his career store has learned "McLaren" and "Mercedes" from
# 2021 races — and the 2020 mod ships one .MAS per team, so "the Ferrari 2020
# car" is a real parameter rather than a wish.
TEST_OUTINGS = 3         # the user's number
TEST_YEAR = 2020         # the car is last season's, which is the whole point

# The mod that carries it, for the letter. A folder name, so `modnames` can turn
# it into whatever the game lists it as.
TEST_MOD = "F1_AM_2020"


def _fold(x):
    return "".join(ch for ch in (x or "").lower() if ch.isalnum())


def test_state(career):
    """Where the test programme stands. Always a dict, never None.

    `done` is a list of CIRCUIT SLUGS rather than a count, because the outings
    have to be at three different circuits and the store is the only thing that
    knows which ones are spent.
    """
    b = _block(career)
    done = [str(x) for x in (b.get("tests") or []) if x]
    key, block = signed(career)
    return {
        "stage": b.get("stage") or NONE,
        "done": done,
        "n": len(done),
        "of": TEST_OUTINGS,
        "team": (block or {}).get("f1_team", "") if block else "",
        "programme": (block or {}).get("name", "") if block else "",
        "left": max(0, TEST_OUTINGS - len(done)),
    }


def test_wanted(career):
    """Is the career in the middle of a test programme right now?"""
    st = test_state(career)
    return st["stage"] == DEV and st["left"] > 0


# Why an outing does not count, in the fewest words that name the fix. A
# disabled thing that does not say why is the thing he actually complained about
# — see `_sim_blocked`, which learned this the same way.
NEED_PRACTICE = "practice only"
NEED_CAR = "%d car" % TEST_YEAR
NEED_TEAM = "%s car"
NEED_TRACK = "a new circuit"
NEED_TRACKSIDE = "get on track"


def test_check(career, kind=None, cls="", year=None, slug="", on_track=True):
    """(ok, why) for one live session against the programme's parameters.

    Strict about what it can verify and lenient about what it cannot, which is
    the same rule `match()` follows for the seat: a class that names a DIFFERENT
    team is refused, and a class that names no team at all is unknown rather than
    wrong. A mod that publishes one class for the whole field must not be able to
    stop the year progressing.
    """
    st = test_state(career)
    if st["stage"] != DEV or not st["left"]:
        return False, None                  # nothing to tick; say nothing
    if (kind or "") != "practice":
        return False, NEED_PRACTICE
    if year and int(year) != TEST_YEAR:
        return False, NEED_CAR
    team = _fold(st["team"])
    got = _fold(cls)
    if team and got and team not in got:
        # It names A team, and it is not his. Every other constructor in the
        # mod folds to something that does not contain his team's name.
        if _looks_like_team(cls):
            return False, NEED_TEAM % st["team"]
    if slug and slug in st["done"]:
        return False, NEED_TRACK
    if not on_track:
        return False, NEED_TRACKSIDE
    return True, None


# The constructors these mods ship, which is how "this class names a team" is
# answered without guessing. Read from the FOLDER, so a mod that adds a team
# needs no edit here — the fallback list covers the case where nothing scanned.
_TEAM_WORDS = ("ferrari", "mercedes", "redbull", "mclaren", "alpine", "renault",
               "alfaromeo", "alphatauri", "astonmartin", "racingpoint", "haas",
               "williams", "toro", "sauber", "force")


def _looks_like_team(cls):
    got = _fold(cls)
    return any(w in got for w in _TEAM_WORDS)


def test_tick(career, slug, laps=0, best=None):
    """Bank one completed outing. Returns the new state, or None if refused.

    THE CIRCUIT IS THE KEY. One outing per circuit, so the three are genuinely
    three test days rather than three sessions at the same track — the user's
    call, and it is what a real test programme looks like.
    """
    b = dict(_block(career))
    if b.get("stage") != DEV:
        return None
    done = [str(x) for x in (b.get("tests") or []) if x]
    if not slug or slug in done or len(done) >= TEST_OUTINGS:
        return None
    done.append(slug)
    b["tests"] = done
    # WHAT HE DID, kept for the team's report. Laps and a best lap are facts the
    # overlay watched; there is no result, because a test has none.
    runs = list(b.get("test_runs") or [])
    runs.append({"slug": slug, "laps": int(laps or 0),
                 "best": float(best) if best else 0.0})
    b["test_runs"] = runs
    career.data["programme"] = b
    _maybe_seat(career, b)
    career.save()
    return test_state(career)


def _maybe_seat(career, b):
    """Open the seat when the programme is genuinely served.

    BOTH HALVES. The letters are the year passing and the outings are the work;
    reading five emails without ever loading the car is not a development year,
    and driving three tests without the team ever writing is not a story. The
    user asked for both and he is right — either one alone can be walked
    straight through.
    """
    if b.get("stage") != DEV:
        return False
    letters = int(b.get("dev_read") or 0) >= DEV_BEATS
    outings = len([x for x in (b.get("tests") or []) if x]) >= TEST_OUTINGS
    if letters and outings:
        b["stage"] = SEAT
        career.data["programme"] = b
        return True
    return False


def seat_ready(career):
    """Is the Formula One seat now his to take?"""
    return _block(career).get("stage") == SEAT


def seat(career):
    """(team, the driver he replaces, the team-mate) or None.

    ALWAYS THE SECOND SEAT — the user's call, and the right one: he is the
    junior arrival alongside an established number one, which is both how it
    works and what gives the booth somebody to measure him against for years.
    """
    _k, b = signed(career)
    if not b:
        return None
    return (b.get("f1_team", ""), b.get("f1_seat", ""), b.get("f1_lead", ""))


def validate():
    """Data errors, as a list of strings. Empty means the file is sound."""
    errs = []
    d = load(force=True)
    if len(all_programmes()) != 3:
        errs.append("expected exactly three programmes, found %d"
                    % len(all_programmes()))
    for key, b in all_programmes():
        for field in ("name", "f2_team", "f1_team", "f1_seat", "f1_lead"):
            if not b.get(field):
                errs.append("%s: missing %s" % (key, field))
        # THE SEAT AND THE TEAM-MATE MUST BE TWO DIFFERENT PEOPLE, or the
        # arrival letter tells him he is replacing the man he is driving
        # alongside.
        if b.get("f1_seat") and b.get("f1_seat") == b.get("f1_lead"):
            errs.append("%s: replacing his own team-mate" % key)
    # ...and no two programmes may lead to the same seat, or two of the three
    # choices are the same choice.
    seats = [b.get("f1_seat") for _k, b in all_programmes()]
    if len(set(seats)) != len(seats):
        errs.append("two programmes lead to the same seat: %s" % seats)
    return errs


if __name__ == "__main__":
    errs = validate()
    for key, b in all_programmes():
        print("%-10s %-22s -> %s, replacing %s alongside %s"
              % (key, b.get("f2_team", "?"), b.get("f1_team", "?"),
                 b.get("f1_seat", "?"), b.get("f1_lead", "?")))
    print("%d programmes, %d development letters" % (len(all_programmes()),
                                                     DEV_BEATS))
    print("validate: " + ("OK" if not errs else "; ".join(errs)))
    sys.exit(1 if errs else 0)
