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
# WHERE THE ARC BEGINS, AND IT MOVED. It used to open on the Formula 2 rung; it
# now opens on FORMULA 3, at the user's call and for two good reasons:
#
#   * the F3 mod names REAL TEAMS per entry — ART, Prema, Carlin, Trident and the
#     rest — so a seat can be verified against what he actually selected in the
#     game, the same way the Formula One seat already is;
#   * academies sign drivers INTO F3 and prove them in F2, which is the real
#     ladder rather than a compressed version of it.
F3_KEY = "f3"
_YEAR = __import__("re").compile(r"(?:19|20)[0-9][0-9]")
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


def _on_rung(career, key):
    if career is None or not getattr(career, "on_ladder", False):
        return False
    prog = career.ladder
    tier = (prog.tier() or {}) if prog is not None else {}
    return tier.get("key") == key


def on_f2(career):
    """Is this career sitting on the Formula 2 rung right now?"""
    return _on_rung(career, F2_KEY)


def on_f3(career):
    """...and the rung the arc now STARTS on."""
    return _on_rung(career, F3_KEY)


# THE CALL-UP. Four rounds into the Formula 3 season, the academy's Formula 2
# team makes a change and he finishes the year in the bigger car.
#
# NOBODY IS NAMED. "Dropped for form" is a claim about a real person's competence,
# and the F2 2019 field is a real grid — so the letter says the team has made a
# change and never says who. The one thing this product may not do is state
# something false about a real driver.
CALLED = "called"       # the F2 seat is his, mid-season, and he is in it

# WHAT A CALLED-UP SEASON HAS TO DELIVER. Not the championship: he arrives with
# two rounds already gone and nothing on the board, so a title is out of reach and
# a bar nobody can clear is not a bar. The user's call — *"the target be like
# finish P3 in the standings"* — and it is the right shape, because it is what a
# team actually asks of a mid-season signing: be on the podium of the
# championship by December and the seat above is yours.
#
# IT ALSO CHANGES WHAT MAY BE SAID. Clearing this is a PROMOTION EARNED, never a
# championship won, and the letters that mark it are their own pool for exactly
# that reason.
CALLUP_BAR = 3


def rumour_due(career):
    """How much of the call-up rumour is owed: 0, 1 or 2.

    THE CALL-UP USED TO ARRIVE WITH NO WARNING. He asked for the build-up in as
    many words — *"after the first race there should be an email from my agent
    saying a seat call up might be on the cards"* — and he is right that an event
    nobody saw coming is not a narrative.

    Two beats, and they ESCALATE rather than repeat: after his first round it is
    people asking questions, and on the round before the seat actually changes it
    is a decision expected before the next race. A rumour that says the same
    thing twice is an echo, which is worse than one beat.

    Counted from rounds RACED rather than from a date, like everything else in
    this arc, so a player who simulates is told the same story as one who drives.
    """
    if career is None:
        return 0
    b = _block(career)
    if b.get("stage") != SIGNED or b.get("called"):
        return 0
    if not on_f3(career):
        return 0
    done = len({r.get("n") for r in career.rounds if r.get("n")})
    when = career.callup_round() or 0
    if not when or done < 1:
        return 0
    # The second beat lands on the round BEFORE the call, so the two never
    # arrive together — and a season too short for that gets one beat, not none.
    return 2 if (when > 1 and done >= when - 1) else 1


def callup_ready(career):
    """Should the call-up letter go out now?

    Signed to a programme, still on the F3 rung, and far enough into the season
    for a seat to be worth opening.
    """
    if career is None:
        return False
    b = _block(career)
    if b.get("stage") != SIGNED or b.get("called"):
        return False
    return on_f3(career) and bool(career.callup_due())


def _f2_field(career):
    """Names to fill the rounds he missed, or () if we do not know any.

    Read from what the overlay has actually SEEN — `career.py` folds every result
    file on the machine, so the Formula 2 grid is known the moment he has loaded
    the mod once. Nothing is invented: no roster, no simulated rounds, and the
    season simply starts clean.
    """
    try:
        import career as career_mod
        import ladder as ladder_mod
        hist = career_mod.History()
        prog = career.ladder
        want = (prog.path, prog.reached + 1) if prog is not None else None
        if not want:
            return ()
        for cls, blk in (hist.data.get("classes") or {}).items():
            try:
                if ladder_mod.tier_of(car_class=cls) != want:
                    continue
            except Exception:
                continue
            names = [n for n in ((blk or {}).get("drivers") or ())
                     if n and n != career.me]
            if names:
                return tuple(sorted(names))
    except Exception:
        pass
    return ()


def take_callup(career):
    """Move him into the F2 seat for the rest of the season. True if it happened.

    THE LETTER IS WHAT DOES IT, so a player who never opens his post is not
    quietly moved to another championship — the same rule the development year's
    beats follow.
    """
    if not callup_ready(career):
        return False
    if career.callup(names=_f2_field(career)) is None:
        return False
    b = dict(_block(career))
    b["called"] = True
    career.data["programme"] = b
    career.save()
    return True


def called_up(career):
    """Was he PUT in this seat mid-season rather than starting the year in it?

    Public because the flag lives on the career block and `signed()` returns the
    static programme definition out of `programmes.json` — a caller reaching for
    `signed(career)[1].get("called")` gets None however called up he is, which
    is exactly how the news feed came to file a mid-season replacement as an
    outright champion.
    """
    return bool(_block(career).get("called"))


def state(career):
    """Where he is in the programme story. Never raises."""
    b = _block(career)
    st = b.get("stage") or NONE
    if st != NONE:
        return st
    return OFFERED if on_f3(career) else NONE


def signed(career):
    """The programme he is on, as (key, block), or (None, None)."""
    b = _block(career)
    k = b.get("key")
    return (k, get(k)) if k else (None, None)


def bar_state(career):
    """Where he stands against the podium bar, or None if it cannot be read.

    {"pos", "bar", "gap", "rival", "left", "holding"} — every number MEASURED off
    the table, and None the moment one of them cannot be. A called-up driver is
    judged on finishing third, so this is the only arithmetic that matters to him
    all season and it belongs in one place: the booth says it out loud, the news
    writes it up, and two implementations of it would eventually disagree in
    public.

    ONLY FOR A CALLED-UP SEASON. A driver who contested the whole championship is
    judged on winning it, and `_title_fight` already covers that fight.
    """
    if career is None or not called_up(career) or not on_f2(career):
        return None
    table = list(career.standings() or ())
    me = career.me or ""
    mine = None
    place = 0
    for i, (name, pts) in enumerate(table):
        if name == me:
            mine, place = pts, i + 1
            break
    if mine is None or not place:
        return None
    bar = CALLUP_BAR
    total = career.total_rounds or 0
    left = max(0, total - len(career.rounds))
    holding = place <= bar
    # THE MAN WHO MATTERS is whoever he is measured against: the driver holding
    # the bar if he is below it, the driver chasing him if he is on it.
    other = table[place] if holding and place < len(table) else (
        table[bar - 1] if not holding and len(table) >= bar else None)
    if other is None:
        return None
    gap = abs(mine - other[1])
    return {"pos": place, "bar": bar, "gap": gap, "rival": other[0],
            "left": left, "holding": holding, "points": mine}


def rung_facts(career, key=None):
    """What to CALL the seat he is being offered: {"champ", "car", "year"}.

    Asked for after he took a seat and could not tell what he had taken:
    *"it wasnt speicifc to what year, there are so many f3 years so which car
    am i talking lol?"* — a fair complaint about a letter that said "the
    Formula 2 season" while offering a Formula 3 drive, and named no car at
    all.

    THE CAR NAME COMES OFF HIS OWN DISK, through `ladder.tier_cars`, which is
    the same source the eligible-machinery letter uses. The question he is
    really asking is "what do I select in the game", and only the folders he
    actually owns can answer that. Nothing installed means no car named,
    because a letter that names a car he does not have is worse than a letter
    that names none.

    THE YEAR IS READ, NEVER PICKED. It comes out of the mod alias of the rung
    the call-up leads to — `f 2 2019` says 2019 in the content itself — so the
    story's year is whatever the cars in the game actually are. No year in the
    aliases, no year in the letter.
    """
    out = {"champ": "", "car": "", "year": "", "mod": ""}
    if career is None or not getattr(career, "on_ladder", False):
        return out
    try:
        import ladder as ladder_mod
    except Exception:
        return out
    prog = career.ladder
    if prog is None:
        return out
    tiers = list(ladder_mod.tiers(prog.path) or [])
    key = key or (prog.tier() or {}).get("key") or ""
    tier = None
    for t in tiers:
        if t.get("key") == key:
            tier = t
            break
    if tier is None:
        return out
    out["champ"] = tier.get("name", "") or ""
    try:
        cars = ladder_mod.tier_cars(tier) or []
    except Exception:
        cars = []
    # ONE CAR IS THE ANSWER, several is a list, none is a silence.
    out["car"] = ", ".join(nice for nice, _folder in cars[:3])
    # AND THE MOD IT LIVES IN, because "Formula 3" is what the car is called
    # and "SMMG Formula 3 Series" is where he has to look to find it. On this
    # rung those two strings are nearly the same word, which is exactly why
    # the letter needs both to be of any use.
    out["mod"] = cars[0][1] if cars else ""
    for t in tiers:
        if t.get("key") != F2_KEY:
            continue
        for alias in t.get("mods", ()):
            m = _YEAR.search(alias.replace(" ", ""))
            if m:
                out["year"] = m.group(0)
                break
    return out


def offer(career):
    """The three seats, or [] if this is not the moment for them.

    Offered on the Formula 3 rung and only before a season has been raced:
    a driver signs for a team BEFORE the year, and offering him a seat after
    round four is a letter about a season that is already happening.
    """
    if not on_f3(career) or state(career) not in (OFFERED,):
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
    if b is None or not on_f3(career) or career.rounds:
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
    # THE LADDER CAN MOVE HIM BEFORE ANYBODY ASKS. Winning Formula 2 promotes him
    # on the ladder's own rules, which archives the season — and if the verdict
    # had not been banked by then, `on_f2` is false for ever and the arc is
    # stranded at `signed` forever after. That is exactly what happened to him:
    # champion of Formula 2, in a Formula One car, with the programme still
    # thinking he was mid-season.
    #
    # So a season that has GONE is judged from the record it left behind.
    if not on_f2(career):
        for h in reversed(career.data.get("ladder_history") or ()):
            if h.get("tier") != F2_KEY:
                continue
            pos = int(h.get("pos") or 0)
            if not pos:
                return None
            bar = CALLUP_BAR if called_up(career) else 1
            if pos <= bar:
                return WON
            return RETRY if int(b.get("attempts") or 1) < MAX_ATTEMPTS \
                else DROPPED
        return None
    # ONLY THE FORMULA 2 SEASON IS JUDGED. The arc now begins on the F3 rung, and
    # without this an F3 season that ran its full length — a call-up he never got
    # because the season was too short, say — would be marked against the
    # programme's Formula 2 bar and could end the whole story on the wrong
    # championship.
    if not on_f2(career):
        return None
    if not career.season_done():
        return None
    pos = career.my_position()
    # THE BAR DEPENDS ON HOW HE GOT HERE. A driver who was called up mid-season
    # is judged on a podium in the standings; one who contested the whole
    # championship is judged on winning it.
    bar = CALLUP_BAR if _block(career).get("called") else 1
    if pos and pos <= bar:
        return WON
    return RETRY if int(b.get("attempts") or 1) < MAX_ATTEMPTS else DROPPED


def _judged_key(career):
    """Which season a verdict would be about, as a stable id.

    A season is judged ONCE. It used to be judged on every inbox refresh, which
    was harmless while the verdict could only be read from a live season — the
    stage moved to RETRY and the live season was still there to be re-judged to
    the same answer. Recovering a verdict from `ladder_history` broke that: the
    archived season never changes, so every refresh judged it again, and
    `attempts` climbed one per menu draw. Two refreshes turned one missed season
    into a dropped career.
    """
    # IT IDENTIFIES THE SEASON, AND NOTHING THAT THE VERDICT ITSELF CHANGES.
    #
    # The attempt counter looked like the obvious discriminator and is exactly
    # wrong: applying a verdict increments it, so the key moved and the next
    # refresh judged the same season again — one missed season became a dropped
    # career, which is the bug this guard exists to stop.
    #
    # The first round's timestamp is the season's own identity. Two attempts at
    # the same rung are two different sets of rounds however alike they look, and
    # nothing downstream of a verdict touches them.
    b = _block(career)
    if on_f2(career):
        # HOW MANY SEASONS HAVE BEEN ARCHIVED, plus how many rounds this one has.
        #
        # A timestamp was the first attempt and is not reliable: `when` is whole
        # seconds, so two seasons raced inside one second are indistinguishable.
        # Starting a season is what archives the last one, so the length of
        # `ladder_history` is a monotonic season counter that nothing downstream
        # of a verdict touches.
        return "live:%d:%d" % (len(career.data.get("ladder_history") or ()),
                               len(career.rounds))
    for h in reversed(career.data.get("ladder_history") or ()):
        if h.get("tier") == F2_KEY:
            return "hist:%s" % (h.get("when") or h.get("rounds") or "?")
    return ""


def apply_verdict(career):
    """Bank the verdict at the end of an F2 season. Returns the new stage.

    ONCE PER SEASON, recorded by `judged`, because this is called on every inbox
    refresh and a verdict is not a thing that can be arrived at twice.
    """
    v = season_verdict(career)
    if v is None:
        return None
    b = dict(_block(career))
    seen = _judged_key(career)
    if seen and b.get("judged") == seen:
        return b.get("stage")
    if seen:
        b["judged"] = seen
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
