# -*- coding: utf-8 -*-
"""
FACTORtv — careers and championships.

`career.py` remembers every race you have ever run, keyed by circuit. This is
the layer above it: a SEASON, with a calendar, a round number, a points table
and a title fight. It is what turns

    "Third for Kandasamy."

into

    "Round six of twenty-four, and that podium moves Kandasamy to within
     twelve points of the championship lead."

Three rules this module exists to enforce
-----------------------------------------
1. ONLY A COMPLETED RACE COUNTS. Identical to `career.MIN_SHARE`: a result is
   recorded at the chequered flag, with the player classified, having covered
   at least half the winner's distance. Restarts and abandoned races leave no
   trace. A championship that silently banks the race you quit on lap two is
   worse than having no championship, because the standings are then wrong in
   a way the user cannot see and cannot fix.

2. CONTEXT IS AUTOMATIC, RECORDING IS CONFIRMED. Knowing this is round six
   costs nothing if it is wrong — it is one sentence. Writing a result into a
   championship is destructive, so it is the thing the user is asked about,
   and it is asked BEFORE the race rather than in the moment of the flag.

3. NEVER STATE TITLE MATHS THAT IS NOT EXACTLY TRUE. `title_state()` returns
   the real numbers — points available, whether the leader can still be
   caught — and the booth says nothing when they do not support a claim. Same
   discipline as the era gating: the user can check this against the timing
   screen and his own memory, so being approximately right is being wrong.

A career may also be a RUNG OF A LADDER
---------------------------------------
`ladder.py` owns where a championship SITS — that Formula 4 is one rung above
karting, and that fifth is enough to leave one and nowhere near enough to
leave another. This module is where that meets a season actually being driven:
a career carries a `ladder` block, every season it runs is a season at one
rung, and at the end of it `evaluate()` says whether the next seat was earned.

Two rules govern everything down there, and both are LAW 3 wearing new
clothes:

  * EVALUATING IS FREE, ADVANCING IS CONFIRMED. `evaluate()` reads and writes
    nothing, so it can be called on every menu draw. `advance()` archives the
    season and moves the driver, which cannot be undone by racing again — so
    it is only ever called from a confirmed action.
  * A MISSED CUT IS NOT A DEAD END. He may stay and go again, or take a
    sideways seat on another path. `evaluate()` returns all three options and
    decides none of them.

Points are computed here, not read from rF2
-------------------------------------------
rF2's `Points` field is only populated inside its own championships — on the
development machine 89 of 132 races awarded zero to every driver — and the
table varies per mod. So points come from the preset's own table, scored on
finishing position. See `lines_data/seasons.json`.
"""
import glob
import json
import os
import re
import sys
import time

import ladder as ladder_mod
import track as track_mod

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
CAREER_DIR = os.path.join(_DIR, "careers")
PRESET_PATH = os.path.join(_DIR, "lines_data", "seasons.json")

# Same law as career.MIN_SHARE, restated here because this module is the one
# that writes to a championship and the number must not drift between them.
from career import MIN_SHARE      # noqa: E402  (deliberate, see above)

# Fraction of a season after which it counts as the run-in. Same idea as the
# race's LATE_FRACTION, one level up.
SEASON_LATE = 0.7

# How many qualifying results to keep. Only the recent ones are ever quoted.
QUALI_KEEP = 40

# `load()` DISCARDS A CAREER WHOSE VERSION DOES NOT MATCH, so this is bumped
# only when an old file would be read WRONGLY — never merely because a field
# was added. The ladder block is read through `.get` with a default, so a
# career saved before ladders existed loads unchanged and simply has no path.
VERSION = 1

_presets = None


def presets():
    """The shipped calendars. Missing file is survivable: a career system
    with no presets simply offers nothing to start."""
    global _presets
    if _presets is not None:
        return _presets
    try:
        with open(PRESET_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    _presets = {k: v for k, v in data.items()
                if not k.startswith("_") and isinstance(v, dict)}
    return _presets


def _slugify(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_") or "career"


def list_careers():
    """Every saved career, newest first, as light summaries for the menu."""
    out = []
    try:
        paths = glob.glob(os.path.join(CAREER_DIR, "*.json"))
    except Exception:
        return out
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        out.append({
            "slug": os.path.splitext(os.path.basename(p))[0],
            "name": d.get("name", "?"),
            "preset": d.get("preset", ""),
            "done": len(d.get("rounds", [])),
            "total": len(d.get("calendar", [])),
            "created": d.get("created", 0),
        })
    return sorted(out, key=lambda c: -c.get("created", 0))


def buildable(preset_key):
    """The rounds of a preset that can actually be raced on this machine.

    A calendar of circuits the user does not own is not a calendar. The
    shipped F1 2025 preset has 24 rounds and only 8 of them were installed on
    the development machine — so a season built from the front of the list
    began with three Grands Prix that could never be started, and the second
    of them would have blocked the championship for ever.

    Falls back to the FULL calendar when the game cannot be found, because
    "we could not detect your tracks" must not silently become "you own
    nothing".
    """
    pre = presets().get(preset_key) or {}
    cal = [dict(r) for r in pre.get("calendar", [])]
    have = track_mod.installed()
    if not have:
        return cal
    return [r for r in cal if r.get("slug") in have]


def create(preset_key, me="", name=None, rounds=0, only_installed=True,
           cls="", cls_any=(), ladder_path="", tier_index=0):
    """Start a career from a preset. Returns the Career, or None.

    `rounds` trims the calendar to the first N rounds — a short season, which
    is what most people actually want when trying the feature out or checking
    whether the commentary hangs together across a few races. 0 keeps the
    whole thing.

    `only_installed` drops rounds whose circuit is not installed (see
    `buildable`). On by default, and it should stay that way: the alternative
    is a season with unreachable rounds in it.

    `cls` locks the car class up front. Empty means "decide on the first
    race", which is the older behaviour and still the right default for
    anyone who has not raced enough for the class list to be useful.

    `ladder_path` starts the career on a ladder, at `tier_index` — which is 0
    for anybody beginning at the bottom, and is only ever non-zero for a
    driver taking a sideways move onto another path. A ladder career leaves
    `cls` EMPTY on purpose: the rung already says which cars belong to it, in
    both of the two names a car has, and locking the exact CarClass string as
    well would mean a season could only ever be raced in the one chassis that
    happened to be loaded first.

    Order is always PRESERVED — this is a real run of consecutive rounds from
    a real calendar, not a random sample, which is what makes it feel like a
    season rather than a playlist.
    """
    pre = presets().get(preset_key)
    if not pre:
        return None
    # An OPEN season has no calendar to filter or trim: `rounds` is simply how
    # many races it runs, and they can be anywhere. This is the format that
    # actually fits how the game gets played — you pick a track you fancy, in
    # the car you are racing, and it becomes the next round — and it is
    # immune to the whole "do you own this circuit" problem.
    if pre.get("open"):
        cal = []
    else:
        cal = (buildable(preset_key) if only_installed
               else [dict(r) for r in pre.get("calendar", [])])
    if rounds and cal:
        cal = cal[:rounds]
    # Rounds are renumbered after filtering, so a five-round season runs 1..5
    # rather than 4, 8, 12, 13, 16 — the number the booth says out loud has
    # to match the season the user is actually driving.
    for i, r in enumerate(cal, start=1):
        r["round"] = i
    # A rung is checked before anything is written. An index off the end of a
    # path is a caller bug, and creating the career anyway would leave a
    # driver standing on a tier that does not exist.
    tier = None
    if ladder_path:
        ts = ladder_mod.tiers(ladder_path)
        if not (0 <= tier_index < len(ts)):
            return None
        tier = ts[tier_index]
    existing = {c["slug"] for c in list_careers()}
    base = _slugify(name or (tier or {}).get("name")
                    or pre.get("name") or preset_key)
    slug, n = base, 1
    while slug in existing:
        n += 1
        slug = "%s_%d" % (base, n)
    data = {
        "version": VERSION,
        # A ladder career is NAMED FOR THE RUNG, because that is the thing the
        # driver is in: "Formula 4", not "10-race season". The name is rewritten
        # by `advance()` every time he moves, so the menu always says where he
        # actually is.
        "name": ((tier["name"] if tier
                  else "%d-race season" % rounds
                  if pre.get("open") and rounds
                  else (name or pre.get("name") or preset_key)
                  + ("" if len(cal) >= len(pre.get("calendar", []))
                     else " (%d)" % len(cal)))
                 + ("" if n == 1 else " #%d" % n)),
        "preset": preset_key,
        "created": int(time.time()),
        # Who the user is racing AS. Defaults to their settings name; a
        # career can override it so the whole broadcast — booth and engineer
        # alike — calls them by the name of the driver whose car they are in.
        "me": me or "",
        "driver": "",
        # Whether this career expects qualifying sessions. Drives whether the
        # engineer talks about grid slots and previous quali results at all.
        "quali": True,
        # The car class this championship is for. Chosen up front when the
        # user knows, otherwise locked by the first recorded round — either
        # way a GT3 field can never wander into an F1 championship and
        # rewrite the standings.
        "cls": cls or "",
        # The constructor classes a team-named field stands for. Empty for an
        # ordinary single-class championship.
        "cls_any": list(cls_any or []),
        "open": bool(pre.get("open")),
        # For an open season this is the whole shape of it: N races, any
        # circuit. 0 means genuinely open-ended, with no total and therefore
        # no title maths — see `total_rounds`.
        "length": int(rounds or 0) if pre.get("open") else 0,
        "points": list(pre.get("points") or [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]),
        "fastest_lap": bool(pre.get("fastest_lap")),
        "calendar": cal,
        "rounds": [],
    }
    if ladder_path:
        data["ladder"] = ladder_mod.Progress(ladder_path,
                                             tier_index).to_json()
        # Seasons already completed on this ladder, newest last. Kept as
        # SUMMARIES rather than whole seasons: the standings of a karting year
        # three rungs ago is not something anything will ever read back, and a
        # career file that grows without bound is a career file that eventually
        # fails to save.
        data["ladder_history"] = []
    c = Career(slug, data)
    c.save()
    return c


def load(slug):
    if not slug:
        return None
    path = os.path.join(CAREER_DIR, "%s.json" % slug)
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return None
    if d.get("version") != VERSION:
        return None
    return Career(slug, d)


def delete(slug):
    """Remove a career for good. Returns True if a file went away."""
    if not slug:
        return False
    path = os.path.join(CAREER_DIR, "%s.json" % slug)
    try:
        os.remove(path)
        return True
    except OSError:
        return False



def _names_driver(vehicle, name):
    """Does this rF2 entry belong to that driver?

    Entry names are free text per mod — "#77 - Valtteri Bottas" in the 2021
    Formula One mod — so this asks whether the driver's surname appears in
    it rather than trying to parse a format nobody guarantees.

    Folded through `drivers._fold`, which is the ONE name-folder in this
    product: two folders eventually disagree, and then the store and the
    booth disagree about who somebody is.
    """
    if not vehicle or not name:
        return False
    try:
        import drivers as _drv
        hay = _drv._fold(vehicle)
        parts = [p for p in str(name).split() if len(p) > 2]
        return any(_drv._fold(p) in hay for p in parts[-1:] or parts)
    except Exception:
        return False


class Career(object):
    """One season in progress."""

    def __init__(self, slug, data):
        self.slug = slug
        self.data = data

    # -- shape -------------------------------------------------------------
    @property
    def name(self):
        return self.data.get("name", "?")

    @property
    def is_open(self):
        return bool(self.data.get("open"))

    @property
    def calendar(self):
        return self.data.get("calendar", [])

    @property
    def rounds(self):
        return self.data.get("rounds", [])

    @property
    def total_rounds(self):
        """How many rounds this season has, or 0 when that is unknowable.

        An open season of a DECLARED length knows its total perfectly well —
        five races is five races, whatever circuits they turn out to be — so
        it gets round numbers and title maths like any other. Only a season
        with no declared length returns 0, and returning a made-up total for
        that is how the booth ends up saying "round six of six" for ever.
        """
        if self.is_open:
            return int(self.data.get("length") or 0)
        return len(self.calendar)

    @property
    def me(self):
        """The name this career is raced under — the career's own driver name
        if one was chosen, else the user's settings name."""
        return self.data.get("driver") or self.data.get("me", "")

    @property
    def uses_quali(self):
        return bool(self.data.get("quali", True))

    @property
    def nationality(self):
        """The country this driver races under, or "".

        One of the three identity fields, and the only one that is not a name.
        Empty is a real answer — a career started before this existed, or a
        driver who never picked one — and everything downstream stays silent
        rather than guessing at a flag.
        """
        return self.data.get("nationality", "")

    def set_nationality(self, country):
        self.data["nationality"] = country or ""
        self.save()

    def set_driver(self, name):
        """Race under this name. Empty restores the settings name."""
        self.data["driver"] = name or ""
        self.save()

    def set_quali(self, on):
        self.data["quali"] = bool(on)
        self.save()

    def quali_result(self, n=None):
        """The qualifying result for a round, or the most recent one.

        Returns {"n", "pos", "field", "slug"} or None. This is what lets the
        engineer open a session with "last time out you put it fourth" — a
        thing he cannot know from shared memory, because it happened in a
        session that has already ended.
        """
        qs = self.data.get("quali_results") or []
        if n is not None:
            return next((q for q in qs if q.get("n") == n), None)
        return qs[-1] if qs else None

    def record_quali(self, n, pos, field=0, slug="", mate_pos=0, mate=""):
        """Bank a qualifying position. Replaces any earlier one for the round
        — a re-run qualifying session is the one that counts.

        `mate_pos` is the team-mate's slot on the same sheet, where there is
        a team-mate at all. Saturday is where a team-mate comparison is at
        its cleanest — same car, same fuel, one lap each — so it is worth
        keeping even though the race result is the thing that scores.
        """
        if not pos:
            return None
        qs = [q for q in (self.data.get("quali_results") or [])
              if q.get("n") != n]
        rec = {"n": n, "pos": int(pos), "field": int(field or 0),
               "slug": slug, "when": int(time.time())}
        if mate_pos:
            rec["mate_pos"] = int(mate_pos)
            rec["mate"] = mate or ""
        qs.append(rec)
        qs.sort(key=lambda q: q.get("n", 0))
        self.data["quali_results"] = qs[-QUALI_KEEP:]
        self.save()
        return rec

    def save(self):
        try:
            os.makedirs(CAREER_DIR, exist_ok=True)
            path = os.path.join(CAREER_DIR, "%s.json" % self.slug)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=1)
            os.replace(tmp, path)
        except Exception:
            pass

    # -- matching a live session -------------------------------------------
    def _programme_seat(self):
        """(the seat he was given, the man in the other car), or None.

        Only once the development year is served and the seat is actually
        his — before that there is nothing to be locked out of.
        """
        try:
            import programme as prog_mod
        except Exception:
            return None
        if prog_mod.state(self) != prog_mod.SEAT:
            return None
        got = prog_mod.seat(self)
        if not got:
            return None
        _team, mine, theirs = got
        return (mine, theirs) if (mine and theirs) else None

    def match(self, slug, cls=None, year=None, vehicle=""):
        """Which round of this season the loaded session is, if any.

        Returns {"n", "event", "slug", "done"} or None. `done` means this
        round already has a result — the user is re-running it, which is
        allowed and which the prompt will say out loud.

        `year` is the SEASON the live session is running, where the era could
        date it. Only used by a rung that locks its year — Formula One is
        2021 in this career and only 2021 — and ignored entirely everywhere
        else, including when it is None.

        `vehicle` is the ENTRY he loaded — rF2 names each one for its driver
        ("#77 - Valtteri Bottas"). Used only by a junior-programme seat, which
        is a specific car rather than a team: the whole arc is about earning
        THAT seat, so turning up in the other side of the garage is not a
        round of it.
        """
        if not slug:
            return None
        # Class lock. Without it, a GT3 race at Spa counts as the Belgian
        # Grand Prix and rewrites an F1 championship.
        #
        # `cls_any` is the TEAM-NAMED case: the championship is the whole
        # Formula One field, so a car in any of its constructor "classes"
        # belongs to it. Without this a 2021 career could never match at all,
        # because the player's class is "McLaren" and the season is not.
        # THE RUNG IS A LOCK TOO, and where it applies it is the better one: a
        # rung names every class that belongs to it, so a Formula 4 season is
        # not tied for ever to whichever chassis happened to load first.
        #
        # ONLY A CLASS THAT RESOLVES TO A DIFFERENT RUNG IS REFUSED. A class
        # `ladders.json` has never heard of is UNKNOWN, not wrong — the car
        # lists are curated by hand and will always trail what is installed —
        # and refusing those would make a career silently stop counting the
        # first time he races something the file does not happen to name.
        prog = self.ladder
        if prog is not None and cls:
            at = ladder_mod.tier_of(car_class=cls)
            if at is not None and at != (prog.path, prog.reached):
                return None
            # ...AND A RUNG MAY LOCK ITS SEASON YEAR.
            #
            # Formula One is 2021 in this career and only 2021: the climb is
            # pointed at that season, and a driver who arrives and finds he
            # could equally have raced 2025 has arrived somewhere generic.
            #
            # REFUSED ONLY WHEN THE YEAR IS KNOWN. An era that cannot be
            # dated falls through exactly as an unknown class does — because
            # the alternative is a career that silently stops counting, which
            # is the worst failure this module has and the one THE LAW was
            # rewritten to prevent.
            years = (prog.tier() or {}).get("years")
            if years and year and not (years[0] <= int(year) <= years[1]):
                return None

            # ...AND A PROGRAMME SEAT IS A CAR, NOT A TEAM.
            #
            # The user: "make it so the races will only pick up for the
            # teammate's car — if I'm locked in with Bottas then I HAVE to use
            # Bottas's car to continue the F1 season arc." He is right that
            # this is what the arc means: two years of climbing bought one
            # seat, and the other Mercedes is somebody else's.
            #
            # THE CLASS LOCK CANNOT DO IT. Both cars report `Mercedes`, so
            # the constructor is identical and only the entry name differs.
            #
            # REFUSED ONLY WHEN HE IS POSITIVELY IN THE OTHER ONE. A vehicle
            # string that names neither driver is unknown, not wrong, and
            # falls through — the same discipline as the year and the class,
            # and for the same reason: a career that silently stops counting
            # is the worst failure this module has.
            seat = self._programme_seat()
            if seat and vehicle:
                mine, theirs = seat
                if theirs and _names_driver(vehicle, theirs)                         and not _names_driver(vehicle, mine):
                    return None

        locked = self.data.get("cls")
        members = self.data.get("cls_any") or []
        if members:
            if cls and cls not in members:
                return None
        elif locked and cls and cls != locked:
            return None

        done_slugs = [r.get("slug") for r in self.rounds]
        if self.is_open:
            # A repeat circuit is a NEW round, unless it is the round just
            # raced — in which case the user is re-running the one they were
            # unhappy with. A season of "five races, anywhere" may perfectly
            # well include the same track twice, and treating the second visit
            # as a re-run silently swallowed a race: five races driven, four
            # rounds recorded.
            if done_slugs and done_slugs[-1] == slug:
                n = len(self.rounds)
                return {"n": n, "event": self.rounds[-1].get("event", ""),
                        "slug": slug, "done": True}
            total = self.total_rounds
            if total and len(self.rounds) >= total:
                # The season is complete. Further races are just races.
                return None
            return {"n": len(self.rounds) + 1, "event": "", "slug": slug,
                    "done": False}

        # Fixed calendar: prefer the earliest round at this circuit that has
        # not been raced. A calendar with two visits to one circuit (the 2021
        # Red Bull Ring double-header) then fills in order.
        raced = {}
        for r in self.rounds:
            raced[r.get("n")] = True
        first_done = None
        for i, rnd in enumerate(self.calendar, start=1):
            if rnd.get("slug") != slug:
                continue
            if not raced.get(i):
                return {"n": i, "event": rnd.get("event", ""), "slug": slug,
                        "done": False}
            if first_done is None:
                first_done = {"n": i, "event": rnd.get("event", ""),
                              "slug": slug, "done": True}
        return first_done

    def phase(self, n=None):
        """Where in the SEASON we are — the same idea as a race's phase.

        A season has a shape and a booth should know it: the opener where
        nobody has a point, the settling early rounds, the halfway mark, the
        run-in where the title starts to close, and the finale. Without this
        every round sounds identical except for its number.

        Returns None when the season has no declared length, because none of
        those words mean anything without an end.
        """
        total = self.total_rounds
        n = n or (len(self.rounds) + 1)
        if not total:
            return "opener" if n == 1 else None
        if n <= 1:
            return "opener"
        if n >= total:
            return "finale"
        frac = float(n) / total
        # Halfway is a MOMENT, not a band: the round that sits on or just past
        # the midpoint, and only in a season long enough for one to exist.
        if total >= 4 and n == (total + 1) // 2:
            return "midway"
        if frac >= SEASON_LATE:
            return "late"
        return "early"

    def visits(self, slug):
        """Rounds of THIS season already raced at this circuit.

        A season with no fixed calendar can revisit a track, and "we were
        here in round two as well" is a thing only the career knows.
        """
        return [r for r in self.rounds if r.get("slug") == slug]

    def next_round(self):
        """The round the season expects next, for the menu."""
        if self.is_open:
            total = self.total_rounds
            if total and len(self.rounds) >= total:
                return None
            return {"n": len(self.rounds) + 1, "event": "", "slug": ""}
        raced = {r.get("n") for r in self.rounds}
        for i, rnd in enumerate(self.calendar, start=1):
            if i not in raced:
                return {"n": i, "event": rnd.get("event", ""),
                        "slug": rnd.get("slug", "")}
        return None

    # -- recording ---------------------------------------------------------
    def record(self, result):
        """Bank a completed race. Returns the stored round, or None.

        THE LAW lives here. `result` must carry `laps` and `race_laps` so this
        can refuse a race the player did not actually complete — the caller is
        not trusted to have checked, because the caller is the thing most
        likely to be wrong.
        """
        if not result or not result.get("pos"):
            return None
        won = result.get("race_laps") or 0
        if won <= 0 or (result.get("laps") or 0) < won * MIN_SHARE:
            return None
        n = result.get("n") or (len(self.rounds) + 1)
        rnd = {
            "n": n,
            "slug": result.get("slug", ""),
            "event": result.get("event", ""),
            "when": int(result.get("when") or time.time()),
            "pos": result["pos"],
            "grid": result.get("grid", 0),
            "field": result.get("field", 0),
            "dnf": bool(result.get("dnf")),
            "laps": result.get("laps", 0),
            "classified": [list(x) for x in result.get("classified", [])],
            "fastest": result.get("fastest", ""),
        }
        # THE ROUND IS BUILT FIELD BY FIELD, NOT COPIED — deliberately, so a
        # caller cannot smuggle arbitrary keys into the store. Which means
        # anything new has to be named here or it is silently dropped: the
        # team-mate arrived recorded, survived as far as this dict, and
        # vanished, so the season head-to-head read nil-nil for ever while
        # the qualifying half (which has its own writer) worked perfectly.
        for k in ("team", "mate", "mate_pos"):
            if result.get(k):
                rnd[k] = result[k]
        # Re-running a round REPLACES it rather than adding a second result
        # for the same race, or a season could be farmed by repeating the
        # circuit you happen to be quick at.
        self.data["rounds"] = [r for r in self.rounds if r.get("n") != n]
        self.data["rounds"].append(rnd)
        self.data["rounds"].sort(key=lambda r: r.get("n", 0))
        if not self.data.get("cls") and result.get("cls"):
            self.data["cls"] = result["cls"]
        if not self.data.get("me") and result.get("me"):
            self.data["me"] = result["me"]
        self.save()
        return rnd

    # --- SIMULATING A ROUND -------------------------------------------------
    #
    # The user's call, and the reasoning is his: "the game physics is tricky to
    # master in every division and for purposes of testing I don't have time to
    # be getting good."
    #
    # So in the FIRST TWO RUNGS of a path — the learning divisions — a
    # simulated result is generous: he finishes near the front, and a season
    # of simulated rounds earns the promotion. Above that the sim is honest
    # and reports his own form, because by then the career is a record of what
    # he can actually do and flattering it would make the whole climb
    # meaningless.
    SIM_LEARN_TIERS = 2      # rungs from the bottom that get the kind result
    SIM_LEARN_BEST = 1
    SIM_LEARN_WORST = 4      # ...so a P5 promotion bar is always cleared
    SIM_WOBBLE = 2           # places either side of his average, above that

    def _sim_seed(self, n):
        """A stable number for this career and this round.

        DETERMINISTIC, for the reason `record_absence` already documents: a
        random result would mean reloading the save produced a different
        season, and a championship that changes when you look at it twice is
        not a championship.
        """
        h = 0
        for ch in "%s|%s|%d" % (self.slug or "", self.me or "", int(n or 0)):
            h = (h * 131 + ord(ch)) & 0xFFFFFFFF
        return h

    def simulate_round(self, n=None, slug="", event="", names=None):
        """Race a round without driving it. Returns the stored round, or None.

        The sibling of `record_absence`: same simulated field, same rule, but
        he is IN the result rather than absent from it.

        THE RULE THAT MAKES IT SAFE IS UNCHANGED — a simulated round produces
        FINISHING POSITIONS AND POINTS, NEVER EVENTS. No collisions, no spins,
        no fastest lap, nothing the booth may narrate as though it watched.
        It moved the standings; that is all it did.

        AND IT IS NOT HIS DRIVING RECORD. `career.py` — which answers "his
        best result at this circuit" — is never touched by this, because that
        question is about races he drove. The championship counts it; his
        history does not.

        It carries no qualifying result either, which is what keeps the
        engineer honest for free: "last time out you put it fourth" reads
        `quali_result()`, and a simulated round never writes one.
        """
        n = n or (len(self.rounds) + 1)
        # WHO IS IN IT. Form from the rounds already raced, or a roster handed
        # in by the caller for a season that has not started yet — he may want
        # to simulate from round one, which has no form to work from.
        tally = {}
        for rnd in self.rounds:
            for name, pos in rnd.get("classified", ()):
                if name == self.me:
                    continue
                got = tally.setdefault(name, [0, 0])
                got[0] += int(pos)
                got[1] += 1
        if tally:
            field = sorted(tally, key=lambda k: (tally[k][0] / float(tally[k][1]), k))
        else:
            field = [x for x in (names or []) if x and x != self.me]
        if not field:
            # No form and no roster: there is no championship to simulate a
            # round of, and inventing a grid would be inventing opponents.
            return None

        # WHERE HE FINISHES.
        seed = self._sim_seed(n)
        prog = self.ladder
        tier_i = prog.reached if prog is not None else None
        learning = tier_i is not None and tier_i < self.SIM_LEARN_TIERS
        if learning:
            span = self.SIM_LEARN_WORST - self.SIM_LEARN_BEST + 1
            pos = self.SIM_LEARN_BEST + (seed % span)
        else:
            mine = [int(r.get("pos") or 0) for r in self.rounds
                    if r.get("pos") and not r.get("absent")]
            avg = (sum(mine) / float(len(mine))) if mine else (len(field) / 2.0)
            wobble = (seed % (self.SIM_WOBBLE * 2 + 1)) - self.SIM_WOBBLE
            pos = int(round(avg)) + wobble
        pos = max(1, min(pos, len(field) + 1))

        order = list(field)
        order.insert(pos - 1, self.me)
        rnd = {
            "n": n,
            "slug": slug,
            "event": event,
            "when": int(time.time()),
            "pos": pos,
            "grid": 0,
            "field": len(order),
            "dnf": False,
            "laps": 0,
            "classified": [[nm, i + 1] for i, nm in enumerate(order)],
            # NO FASTEST LAP. It is an event, and a simulated round has none.
            "fastest": "",
            # THE MARK THAT KEEPS EVERYTHING ELSE HONEST. Read by the record
            # views and by anything that wants to know whether he was there.
            "simulated": True,
        }
        self.data["rounds"] = [r for r in self.rounds if r.get("n") != n]
        self.data["rounds"].append(rnd)
        self.data["rounds"].sort(key=lambda r: r.get("n", 0))
        self.save()
        return rnd

    def record_absence(self, n=None, slug="", event=""):
        """Bank a round the player did not attend. Returns the stored round.

        THE ONLY WAY A CHOICE CAN COST HIM ANYTHING. A skipped round where
        nobody scores is free: his total is lower and so is everybody else's,
        and the gaps in the standings are exactly what they were. For missing a
        race to mean what it means in real life, THE RACE HAS TO HAPPEN — his
        rivals score, he scores nothing, and he comes back to a championship
        that moved without him.

        So the field is SIMULATED, and the rule that makes that safe is
        narrow: **a simulated round produces finishing positions and points,
        never events.** No collisions, no drama, nothing the booth may narrate
        as though it watched. This is not the rule about never inventing an
        event in his season being broken — that rule is about contradicting
        something he WITNESSED, and he was not there. There is no result file
        and no memory to contradict.

        The order comes from FORM: the average finishing position each driver
        has actually managed in this championship, best first. Deterministic on
        purpose. A random order would make the most consequential race of the
        story a dice roll, and the same save would produce a different season
        every time it was reloaded.
        """
        n = n or (len(self.rounds) + 1)
        # Every driver who has appeared, and how he has actually gone.
        tally = {}
        for rnd in self.rounds:
            for name, pos in rnd.get("classified", ()):
                if name == self.me:
                    continue
                got = tally.setdefault(name, [0, 0])
                got[0] += int(pos)
                got[1] += 1
        if not tally:
            # Nobody has raced yet, so there is no form to simulate from and
            # no championship to miss. Refusing is better than inventing a
            # grid: the story's cost has to be a real one.
            return None
        order = sorted(tally, key=lambda k: (tally[k][0] / float(tally[k][1]),
                                             k))
        rnd = {
            "n": n,
            "slug": slug,
            "event": event,
            "when": int(time.time()),
            # NOT CLASSIFIED, and that is the honest record of what happened.
            # `pos` 0 keeps him out of every points sum, out of the win and
            # podium counts, and out of the standings entirely.
            "pos": 0,
            "grid": 0,
            "field": len(order),
            "dnf": False,
            "laps": 0,
            "absent": True,
            "simulated": True,
            "classified": [(nm, i + 1) for i, nm in enumerate(order)],
            "fastest": "",
        }
        self.data["rounds"] = [r for r in self.rounds if r.get("n") != n]
        self.data["rounds"].append(rnd)
        self.data["rounds"].sort(key=lambda r: r.get("n", 0))
        self.save()
        return rnd

    def drop_last(self):
        """Undo the most recently recorded round. The escape hatch for a race
        that was counted and should not have been."""
        if not self.rounds:
            return None
        rnd = sorted(self.rounds, key=lambda r: r.get("when", 0))[-1]
        self.data["rounds"] = [r for r in self.rounds if r is not rnd]
        self.save()
        return rnd

    # -- the championship --------------------------------------------------
    def points_for(self, pos):
        tbl = self.data.get("points") or []
        return tbl[pos - 1] if 0 < pos <= len(tbl) else 0

    def standings(self, upto=None):
        """[(name, points), ...] best first, from recorded rounds only.

        `upto` computes the table AS IT STOOD after round `upto`, ignoring
        anything later. That is what lets the booth tell "the title has just
        been settled" apart from "the title was settled two rounds ago" —
        without it, a championship decided at round eight is announced again
        at rounds nine and ten as though it had only just happened.
        """
        tally, seen = {}, {}
        rounds = ([r for r in self.rounds if (r.get("n") or 0) <= upto]
                  if upto is not None else self.rounds)
        for rnd in rounds:
            for name, pos in rnd.get("classified", ()):
                tally[name] = tally.get(name, 0) + self.points_for(int(pos))
                seen[name] = seen.get(name, 0) + 1
            fl = rnd.get("fastest")
            if fl and self.data.get("fastest_lap"):
                # F1's rule: the point only goes to a driver finishing in the
                # points. Awarding it to a car that finished eighteenth is the
                # kind of small wrongness that destroys trust in the whole
                # table.
                pos = dict((n, int(p)) for n, p in rnd.get("classified", ())).get(fl)
                if pos and self.points_for(pos):
                    tally[fl] = tally.get(fl, 0) + 1
        self._seen = seen
        return sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))

    # --- RIVALRY IS A STANDINGS FACT ---------------------------------------
    # The user's call, and it is a better rule than the one it replaces:
    # "after 4 races if someone is close to you in the standings, then they
    # will become your rival for that season — use the actual standings as a
    # way of telling us who is whose closest rival."
    #
    # The old rule ALSO required the two men to have finished within two
    # places of each other in most of the last four rounds. That is a real
    # thing, and it made rivalries rare and fiddly to reason about: two
    # drivers can be having a season-long championship fight while rarely
    # being on the same piece of road, which is most title fights in the
    # sport's history. The table is what a season is actually decided on, so
    # the table decides who the rivalry is between.
    RIVAL_AFTER = 4         # rounds, before anybody is anybody's rival
    RIVAL_ADJACENT = True   # they must be NEXT TO EACH OTHER in the table
    # ...and close enough on points that the fight is real. A leader eighty
    # points clear has no rival, he has a procession, and telling him he has
    # one is the sort of claim his own standings screen contradicts.
    RIVAL_POINTS = 1.0      # multiples of a win

    # A table long enough that "he needs to finish in the top N" is a
    # sentence rather than a list. Beyond this the honest answer is "he needs
    # to score", and the booth says that instead.
    SCENARIO_MAX = 12

    def title_scenarios(self, upto=None, field=None):
        """What the leader has to DO, and it is only ever exact arithmetic.

        The user asked for the whole thing: *"the championship leader has
        qualified P12, this means they will need to at least finish P5 or
        higher in tomorrow's race to secure the season win"*, and then the
        rival-dependent version — P5 if this man wins, P8 if he is second.

        THIS IS THE MOST DANGEROUS FEATURE IN THE PRODUCT AND IT IS WORTH
        SAYING WHY. Every other claim the booth makes is about something that
        already happened; this one is a claim about what WILL be enough, and
        the listener can check it at the flag. One missed permutation and the
        booth tells a man he has won a championship he has not won. So:

        * NOTHING IS RETURNED UNLESS IT IS PROVEN. `secure` is the position
          that wins the title against EVERY remaining result by every driver,
          not the likely case. Where that cannot be computed, the answer is
          None and the booth says something qualitative instead (LAW 4).
        * STRICTLY MORE POINTS, NEVER EQUAL. `standings()` breaks a tie
          alphabetically, which is a sort order and not a countback rule —
          this product does not model one. So a tie is NOT a title, and the
          maths refuses to treat it as one. That costs a sentence occasionally
          and it can never be wrong.
        * A DRIVER WHO CANNOT BE CAUGHT IS NOT "SECURING" ANYTHING. If it is
          already decided, `secure` is 0: he needs to finish nowhere at all.

        Returns None when the season has no declared length, no points table,
        or no rounds left — all three are real, common states.

        `field` is how many cars are on the grid, when the caller knows; it
        only limits how far down the scenario table runs.
        """
        total = self.total_rounds
        table = self.standings(upto)
        pts_tbl = self.data.get("points") or []
        if not total or not table or not pts_tbl:
            return None
        done = len([r for r in self.rounds
                    if upto is None or (r.get("n") or 0) <= upto])
        left = total - done
        if left <= 0:
            return None

        me = self.me
        pts = dict(table)
        if me not in pts:
            return None
        my = pts[me]
        # Only drivers who can still mathematically pass him matter. The rest
        # of the grid is noise in this calculation and including them makes
        # the worst case wrong in the safe direction, which is fine, but it
        # also makes "who is he racing" unanswerable.
        win = self.points_for(1)
        ceiling = win * left
        chasers = [(n, p) for n, p in table
                   if n != me and p + ceiling > my]
        n_slots = min(self.SCENARIO_MAX, field or self.SCENARIO_MAX)

        def _beats_all(my_after, my_slot, fixed=None):
            """Does `my_after` survive the best anybody else can still do?

            `fixed` pins one driver to one finishing slot — that is what makes
            a conditional scenario ("if Borda wins") exact rather than a
            guess. Everybody else takes the best slot still available, and
            wins everything remaining after this round.
            """
            taken = {my_slot}
            if fixed:
                taken.add(fixed[1])
            for n, p in chasers:
                if fixed and n == fixed[0]:
                    slot = fixed[1]
                else:
                    slot = 1
                    while slot in taken:
                        slot += 1
                # NOT marked as taken: each chaser is tested against the best
                # slot available to HIM, because any one of them could be the
                # man who takes it. Allocating them one after another would
                # quietly assume an order nobody has raced yet.
                best = p + self.points_for(slot) + win * (left - 1)
                if my_after <= best:      # STRICTLY MORE. A tie is not a win.
                    return False
            return True

        # Already done?
        if _beats_all(my, 0):
            return {"decided": True, "secure": 0, "left": left,
                    "me": me, "my_points": my, "rival": None, "ifs": []}

        # THE WORST FINISH THAT STILL WINS IT, which is what "he needs P5"
        # means — not the best one, which is always P1 and tells nobody
        # anything. Points fall as the position drops, so the answer is the
        # LARGEST p that survives, and searching downwards finds it first.
        secure = None
        for p in range(n_slots, 0, -1):
            if _beats_all(my + self.points_for(p), p):
                secure = p
                break

        # THE CONDITIONAL TABLE, and only on the last round of the season.
        # With two rounds to go "P5 if he wins" is not a fact, it is a fact
        # about one of two races, and stating it flat is the kind of small
        # wrongness this whole module exists to avoid.
        ifs = []
        rival = chasers[0][0] if chasers else None
        if left == 1 and rival:
            for q in range(1, min(n_slots, 6) + 1):
                need = None
                for p in range(n_slots, 0, -1):
                    if p == q:
                        continue          # two cars cannot take one place
                    if _beats_all(my + self.points_for(p), p,
                                  fixed=(rival, q)):
                        need = p
                        break
                # A REQUIREMENT THAT SCORES NOTHING IS NOT A REQUIREMENT.
                # "He needs to finish twelfth" is a strange sentence when
                # twelfth pays no points: what is actually true is that this
                # result of the rival's cannot beat him however the afternoon
                # goes. The caller needs to say that instead, so it is
                # flagged rather than left as a number to be read out.
                ifs.append({"rival_pos": q, "need": need,
                            "any": bool(need and not self.points_for(need))})

        return {"decided": False, "secure": secure, "left": left,
                "secure_any": bool(secure and not self.points_for(secure)),
                "me": me, "my_points": my, "rival": rival,
                "rival_points": chasers[0][1] if chasers else None,
                "chasers": [n for n, _p in chasers], "ifs": ifs}

    def team_mate_record(self, upto=None):
        """The season head-to-head with the man in the other car, or None.

        Returns {"mate", "races_up", "races_down", "quali_up", "quali_down",
        "rounds"} — the number that every Formula One paddock looks at first,
        and the only comparison in the sport with nothing to explain it away:
        same car, same team, same information.

        TRUE BY CONSTRUCTION, like the rest of the season feed. Both halves
        are counted from rounds this overlay recorded, so it cannot disagree
        with the standings screen — and it says nothing at all where there is
        no team-mate to compare against, which is every division outside the
        Formula One mods (see `BoothMixin._team_mate` for why).

        DNFs COUNT AS NOTHING EITHER WAY. A retirement is not a beating; a
        head-to-head that treats one as a win is a statistic that flatters
        whoever's car happened to hold together, and this is a measure of
        driving.
        """
        rounds = [r for r in self.rounds
                  if upto is None or (r.get("n") or 0) <= upto]
        mate = ""
        up = down = qup = qdown = 0
        seen = 0
        for r in rounds:
            mp, mine = r.get("mate_pos"), r.get("pos")
            if not mp or not mine or r.get("dnf"):
                continue
            mate = mate or r.get("mate") or ""
            seen += 1
            if mine < mp:
                up += 1
            elif mp < mine:
                down += 1
        for q in (self.data.get("quali_results") or []):
            if upto is not None and (q.get("n") or 0) > upto:
                continue
            mp, mine = q.get("mate_pos"), q.get("pos")
            if not mp or not mine:
                continue
            mate = mate or q.get("mate") or ""
            if mine < mp:
                qup += 1
            elif mp < mine:
                qdown += 1
        if not mate or not (seen or qup or qdown):
            return None
        return {"mate": mate, "races_up": up, "races_down": down,
                "quali_up": qup, "quali_down": qdown, "rounds": seen}

    def rivals(self, upto=None):
        """The two drivers this season is actually between, or None.

        Returns {"a", "b", "points", "rounds", "player"} — `a` is the player
        when he is in it, because the feed and the booth both frame it around
        him when they can.

        TRUE BY CONSTRUCTION, which is the whole point. A rivalry here is not
        a mood somebody decided to write about: it is two drivers who have
        finished within `RIVAL_NEAR` places of one another in most of the last
        `RIVAL_WINDOW` rounds AND who are close in the championship. Both
        halves are needed — men who are close in points but never on the road
        together are having separate seasons, and two cars that circulate
        nose-to-tail in fourteenth are not a title fight.
        """
        done = len([r for r in self.rounds
                    if upto is None or (r.get("n") or 0) <= upto])
        if done < self.RIVAL_AFTER:
            return None
        table = self.standings(upto)
        if len(table) < 2:
            return None
        win = (self.points_for(1) or 25) * self.RIVAL_POINTS

        # ADJACENT IN THE TABLE, and close enough on points to be a fight.
        # Walking neighbouring pairs is the whole detector: it is what a
        # reader means by "who is he up against", it needs no per-round
        # analysis, and it cannot disagree with the standings screen because
        # it IS the standings screen.
        best = None
        for i in range(len(table) - 1):
            a, apts = table[i]
            b, bpts = table[i + 1]
            gap = abs(apts - bpts)
            if gap > win:
                continue
            mine = self.me in (a, b)
            # THE PLAYER'S RIVALRY WINS, then the closest fight, then the one
            # further up the table. It is his career; a feed that leads on two
            # AI drivers while he is in a scrap of his own has its priorities
            # the wrong way round — and when he is dominant, this finds the
            # fight BEHIND him, which is what he asked for.
            rank = (1 if mine else 0, -gap, -i)
            if best is None or rank > best[0]:
                best = (rank, {"a": a, "b": b, "points": gap,
                               "rounds": done, "player": mine,
                               # Where in the table the fight is. A scrap for
                               # the championship lead and one for eleventh
                               # are not the same story, and only the caller
                               # knows which it wants to tell.
                               "place": i + 1})
        if best is None:
            return None
        out = best[1]
        if out["player"] and out["b"] == self.me:
            out["a"], out["b"] = out["b"], out["a"]
        return out

    def appearances(self, name):
        """How many recorded rounds this driver actually started.

        The booth uses this before naming an AI title rival: rF2 fields are
        only as consistent as the mod, and a driver who has appeared in two of
        eleven rounds is not in a championship fight, he is a guest.
        """
        n = 0
        for rnd in self.rounds:
            if any(d == name for d, _ in rnd.get("classified", ())):
                n += 1
        return n

    def title_state(self, upto=None):
        """The real title maths, or None when there is not enough season to
        do any. Every field here is exact — the booth is allowed to quote it
        directly, which is only safe because nothing is estimated.

        `upto` freezes the season after that round; see `standings`.
        """
        table = self.standings(upto)
        if not table:
            return None
        done = len({r.get("n") for r in self.rounds
                    if upto is None or (r.get("n") or 0) <= upto})
        left = max(0, self.total_rounds - done) if self.total_rounds else None
        best = self.points_for(1) + (1 if self.data.get("fastest_lap") else 0)
        avail = (left * best) if left is not None else None
        leader, lead_pts = table[0]
        me = self.me
        mine = dict(table).get(me)
        my_pos = next((i + 1 for i, (n, _) in enumerate(table) if n == me), None)
        return {
            "leader": leader,
            "leader_points": lead_pts,
            "second": table[1][0] if len(table) > 1 else "",
            "second_points": table[1][1] if len(table) > 1 else 0,
            "me": me,
            "my_points": mine,
            "my_place": my_pos,
            "my_gap": (lead_pts - mine) if mine is not None else None,
            "rounds_done": done,
            "rounds_left": left,
            "points_available": avail,
            # "Mathematically still alive" is a claim, so it is only made when
            # the number of remaining rounds is actually known.
            "can_catch": (None if avail is None or mine is None
                          else (lead_pts - mine) <= avail),
            "decided": (avail is not None and len(table) > 1
                        and (lead_pts - table[1][1]) > avail),
            "table": table,
        }

    # -- the ladder --------------------------------------------------------
    @property
    def ladder(self):
        """This career's ladder Progress, or None when it is not on a path.

        A FRESH OBJECT EVERY TIME, deliberately. A cached one held by the
        panel would go on describing the rung the driver was standing on
        before he was promoted, and the menu redraws far more often than a
        career changes. Mutating what this returns changes nothing on disk —
        `_put_ladder` is the only thing that writes.
        """
        d = self.data.get("ladder")
        return ladder_mod.Progress.from_json(d) if d else None

    def _put_ladder(self, prog):
        self.data["ladder"] = prog.to_json()

    @property
    def on_ladder(self):
        return bool(self.data.get("ladder"))

    def tier(self):
        """The rung this season is being raced at, or None."""
        p = self.ladder
        return p.tier() if p is not None else None

    @property
    def register(self):
        """How the booth should SOUND here — grassroots, junior, professional,
        archive — or "" off a ladder. A tone, never a knowledge base."""
        t = self.tier()
        return (t or {}).get("register", "")

    def season_done(self):
        """Has this season run its full length?

        Only a season with a DECLARED total can ever be finished, which is the
        same refusal `total_rounds` and `phase()` make: an open-ended career
        has no last round, so there is no moment at which a promotion could be
        judged, and claiming one would be inventing an end date.
        """
        total = self.total_rounds
        return bool(total) and len(self.rounds) >= total

    def my_position(self, upto=None):
        """Where the player stands in his own championship, or None.

        None is a real answer and it happens: a season whose rounds recorded
        no classification carrying his name has no position for him, and this
        is the number a promotion is judged on.
        """
        st = self.title_state(upto)
        return (st or {}).get("my_place")

    def evaluate(self, mods=None):
        """Where this ladder season stands, and what it opens. Writes nothing.

        Safe to call on every menu draw, which is the point: the driver can
        see all season what the next seat costs and whether he is currently
        clearing it. `complete` is what separates a live standing from a
        verdict — only a finished season promotes anybody.

        `mods` filters the sideways offers to cars that are installed. None
        means do not filter, and that is the right default for a machine that
        has never scanned (see `ladder.known_mods`).
        """
        p = self.ladder
        if p is None:
            return None
        tier = p.tier() or {}
        nxt = p.next_tier()
        pos = self.my_position()
        done = self.season_done()
        need = p.needs()
        idx = p.reached
        if mods is None:
            mods = ladder_mod.known_mods()
        return {
            "path": p.path,
            "path_name": (ladder_mod.path(p.path) or {}).get("name", ""),
            "tier": tier.get("key", ""),
            "tier_name": tier.get("name", ""),
            "register": tier.get("register", ""),
            "index": idx,
            "pos": pos,
            "needs": need,
            "complete": done,
            "top": nxt is None,
            "next": (nxt or {}).get("key", ""),
            "next_name": (nxt or {}).get("name", ""),
            # `earned` is the LIVE answer all season and the VERDICT once the
            # season is done. Keeping them one field would mean the menu could
            # not say "as it stands, that is enough" before the last round.
            "earned": p.earned(pos),
            "promoted": bool(done and p.earned(pos)),
            # FINISHING A PATH IS WINNING ITS LAST CHAMPIONSHIP. Reaching the
            # top rung is not it — see `ladder.ARC_WIN`.
            "arc_done": bool(done and p.won_arc(pos)),
            "rungs_left": p.rungs_left(),
            "paths_won": list(self.paths_won),
            "arcs_won": self.arcs_won,
            "career_pct": self.career_pct(),
            "completion_pct": self.completion_pct(),
            "career_over": self.career_over,
            # Offered only once a path is actually finished. The FIA grants
            # permission to compete elsewhere; it does not hand it out to a
            # driver who is still climbing.
            "next_paths": (self.paths_available(mods)
                           if done and p.won_arc(pos) else []),
            # Offered whether or not he was promoted: a driver who made it can
            # still fancy sportscars instead, and refusing to show him the
            # option would make the ladder a corridor.
            "sideways": ladder_mod.sideways(p.path, idx, mods),
        }

    @property
    def paths_won(self):
        """Paths whose final championship this driver has won."""
        return list(self.data.get("ladder_done") or [])

    @property
    def arcs_won(self):
        """How many of the five arcs are finished. Counted against the real
        paths only, so a stray key in the file cannot inflate it."""
        real = ladder_mod.career_paths()
        return len({k for k in self.paths_won if k in real})

    def career_pct(self):
        """How far through THIS CAREER he is, 0.0-1.0.

        Measured against the ENDING — `ladder.ENDING_ARCS`, three divisions —
        because that is what a career is here: the climb, and then two more
        professional careers on top of it, and by then a man has given the
        sport his life. That is the story the fourth message is about.
        """
        n = ladder_mod.ENDING_ARCS
        return min(1.0, self.arcs_won / float(n)) if n else 0.0

    def completion_pct(self):
        """How much of a 100% RECORD is done — all five arcs.

        TWO FIGURES, BOTH TRUE, NEITHER PRETENDING TO BE THE OTHER. Three of
        five is not ninety per cent of anything, and the records view can show
        a man most of the way through his career while being well short of
        having won everything. Printing one number for both would make one of
        them a lie the other screen contradicts.
        """
        total = len(ladder_mod.career_paths())
        return min(1.0, self.arcs_won / float(total)) if total else 0.0

    @property
    def career_over(self):
        """Has he finished the career — three arcs?

        FINISHED, NOT LOCKED. He may keep racing afterwards and the remaining
        arcs still count toward the 100%. Nothing in this product should ever
        refuse to let a man drive.
        """
        return self.arcs_won >= ladder_mod.ENDING_ARCS

    def paths_available(self, mods=None):
        """Paths he may take up next, with where he could join each.

        [{"key", "name", "sub", "entries": [(tier_index, name, register)]}].
        A path already finished is not offered again — the arc is done and
        there is nothing left in it to win.
        """
        cur = (self.data.get("ladder") or {}).get("path", "")
        done = set(self.paths_won)
        if mods is None:
            mods = ladder_mod.known_mods()
        out = []
        for key, p in ladder_mod.career_paths().items():
            if key == cur or key in done:
                continue
            entries = [(i, t["name"], t.get("register", ""))
                       for i, t in ladder_mod.entry_options(key, mods)]
            if not entries:
                continue
            out.append({"key": key, "name": p.get("name", key),
                        "sub": p.get("sub", ""), "entries": entries})
        return out

    def advance(self, choice="promote", path_key="", tier_index=0,
                rounds=None):
        """End this ladder season and start the next one. Returns the new tier.

        DESTRUCTIVE, AND NOT AUTOMATIC. It archives the season's standings and
        clears the rounds, which no amount of racing can undo — so it belongs
        behind the menu's confirmation, exactly as deleting a career does.
        `evaluate()` is the free half; this is the confirmed half.

        Three choices, which are the three things a driver can actually do at
        the end of a season:

          "promote"  take the seat above. Refused unless it was earned, so a
                     miscounted click cannot skip a rung.
          "retry"    stay and go again. The season below is remembered at the
                     position it finished, because that IS his record.
          "switch"   take a seat on another path. `path_key`/`tier_index` come
                     straight from `evaluate()["sideways"]`.
          "newpath"  the FIA's permission to compete elsewhere, and it is only
                     granted to a driver who has WON the final championship of
                     the path he is on. `tier_index` is his choice of entry —
                     the bottom of the new path or its first professional
                     rung, both offered because neither is obviously right.

        The difference between "switch" and "newpath" is the difference
        between giving up on an arc and finishing one. A switch is what a
        driver does when the seat above him did not come; it abandons the path
        and the arc goes unfinished. A new path is a reward, and only it
        counts toward the 100%.

        A season that is not finished advances nowhere. Half a championship is
        not a championship, and the position it would be judged on is the
        standing of a table that is still moving.
        """
        p = self.ladder
        if p is None or not self.season_done():
            return None
        pos = self.my_position()
        cur = p.tier() or {}
        # THE RESULT IS RECORDED WHATEVER HE DOES NEXT. It is what he finished
        # the season at, and the divisions view reads it back for ever.
        if pos:
            p.results[cur.get("key", "")] = int(pos)
        if choice == "promote":
            if not p.earned(pos):
                return None
            p.promote()
        elif choice in ("switch", "newpath"):
            ts = ladder_mod.tiers(path_key)
            if not (0 <= tier_index < len(ts)):
                return None
            if choice == "newpath":
                if not p.won_arc(pos):
                    return None
                # THE ARC IS BANKED BEFORE THE DRIVER MOVES. It is what the
                # 100% counts and what the booth will say about him for the
                # rest of his career, and it is the one thing here that
                # leaving the path cannot take away.
                won = self.data.setdefault("ladder_done", [])
                if p.path not in won:
                    won.append(p.path)
            # RESULTS DO NOT TRAVEL. `Progress.results` is keyed by tier and
            # read back as "how that season went" in the divisions view of the
            # path he is now on — carrying karting's result onto the Road to
            # Indy would put a result against a rung he has never raced.
            p = ladder_mod.Progress(path_key, tier_index)
        elif choice != "retry":
            return None
        self._archive_season(cur, pos)
        self._put_ladder(p)
        self._start_rung(p.tier() or {}, rounds, how=choice)
        self.save()
        return p.tier()

    # -- what the sport calls him ------------------------------------------
    #
    # THE REWARD FOR CLIMBING, and it costs nothing to be true. A player who
    # spends ten seasons getting from karting to Formula One should not still
    # be "the driver in fourth" — and the sport has its own vocabulary for
    # exactly this, which moves as a career does.
    #
    # EVERY THRESHOLD IS SOMETHING THIS OVERLAY WATCHED. Titles are seasons it
    # scored, divisions are rungs it recorded him climbing. Nothing here is a
    # difficulty setting or an achievement counter bolted on the side; it is a
    # reading of the same store the standings come from.
    STATUS = (
        # key           label              from
        ("legend",      "Legend"),         # 3+ championships
        ("multi",       "Multiple champion"),
        ("champion",    "Champion"),
        ("contender",   "Contender"),
        ("riser",       "Riser"),
        ("rookie",      "Rookie"),
    )

    def won_live_season(self):
        """Has he won the season that is IN THE FILE RIGHT NOW?

        THE BUG THIS EXISTS TO FIX. `status()` counted `ladder_history`, which
        is written by `advance()` — so on the afternoon the user actually won
        the Hot hatch championship he was still, according to every part of
        this product, a rookie. `status_changed()` returned None, the booth's
        arrival line never fired and the paper never ran the headline. He got
        a letter about it and nothing else, because the mail path reads the
        store directly. The title existed; the only thing that had not
        happened was him clicking "End of season" in a menu.

        A SEASON THAT HAS RUN ITS FULL LENGTH HAS A FINAL TABLE, so first
        place in it is a fact, not a projection. That is why this needs no
        `decided` test the way a mid-season claim does (LAW 4): there are no
        rounds left to change it.

        READING IS FREE, ARCHIVING IS CONFIRMED (LAW 3). This writes nothing
        and is safe on every menu draw; `advance()` remains the only thing
        that banks a season, and once it has, `rounds` is cleared and this
        returns False — so a title can never be counted twice.
        """
        if not self.season_done():
            return False
        st = self.title_state() or {}
        return st.get("my_place") == 1

    def title_count(self):
        """Championships won — archived, plus the one he is standing in.

        One place computes this, because the booth, the news feed, the record
        view and the status arc must never disagree about how many titles a
        man has.
        """
        n = sum(1 for h in (self.data.get("ladder_history") or [])
                if h.get("pos") == 1)
        return n + (1 if self.won_live_season() else 0)

    # -- THE HISTORIC TOUR, EARNED -------------------------------------------
    #
    # The user's idea: *"can those races be unlocked through an invite the player
    # receives after completing their championship, so if I beat 2021 then I get
    # invited to compete in the 1988 F1 season as a reward as well."*
    #
    # It fits because the tour was already the odd one out. `career_paths()`
    # excludes it from the 100% — nobody is promoted from 1966 to 1975, so there
    # is no final championship to win — and that is exactly what makes it the
    # right thing to give away: the one path with nothing to lose by being
    # optional.
    #
    # HIS THREE DECISIONS, and they settle the whole design:
    #   * FORMULA ONE ONLY. Winning the top rung of the single-seater path is
    #     what invites him. A NASCAR champion being invited to a 1988 Grand Prix
    #     season is a stranger sentence than it looks.
    #   * ONE ERA PER CHAMPIONSHIP. Four rewards rather than one.
    #   * IT COUNTS FOR NOTHING. Recorded like any season, outside the 100%.
    TOUR_FROM_PATH = "single_seater"

    def f1_titles(self):
        """Championships won in the TOP rung of the single-seater path.

        Read from the archive plus the season he is standing in, exactly as
        `title_count` does — for the same reason, which is that on the afternoon
        he actually wins it nothing has been archived yet.
        """
        try:
            import ladder as ladder_mod
            ts = ladder_mod.tiers(self.TOUR_FROM_PATH)
        except Exception:
            return 0
        if not ts:
            return 0
        top = ts[-1].get("key")
        n = 0
        for h in (self.data.get("ladder_history") or ()):
            if h.get("tier") == top and h.get("pos") == 1:
                n += 1
        prog = self.ladder
        if (prog is not None and prog.path == self.TOUR_FROM_PATH
                and (prog.tier() or {}).get("key") == top
                and self.won_live_season()):
            n += 1
        return n

    def tour_state(self):
        """{"unlocked": [keys], "owed": n, "next": (index, tier) or None}.

        WRITES NOTHING. The count is derived from titles, so it cannot drift out
        of step with what the rest of the product believes about his career —
        and `tour_grant` is the only thing that banks an era, called by the
        letter that tells him about it.
        """
        try:
            import ladder as ladder_mod
            eras = ladder_mod.tour_eras()
        except Exception:
            eras = []
        got = [str(k) for k in (self.data.get("tour_unlocked") or ()) if k]
        owed = max(0, self.f1_titles() - len(got))
        nxt = None
        if owed:
            for i, t in eras:
                if t.get("key") not in got:
                    nxt = (i, t)
                    break
        return {"unlocked": got, "owed": owed if nxt else 0, "next": nxt,
                "titles": self.f1_titles(), "eras": eras}

    def tour_grant(self, key):
        """Bank one era as unlocked. Returns True if this call did it.

        ONE PLACE WRITES, and it is called where the invitation is SENT — so an
        era he has been invited to is an era he has a letter about, and there is
        no way to unlock something silently.
        """
        if not key:
            return False
        got = [str(k) for k in (self.data.get("tour_unlocked") or ()) if k]
        if key in got:
            return False
        got.append(key)
        self.data["tour_unlocked"] = got
        self.save()
        return True

    def tour_open(self, tier_key):
        """May he race this era? Every era is invitation-only until it is won."""
        return str(tier_key or "") in [
            str(k) for k in (self.data.get("tour_unlocked") or ()) if k]

    def status(self):
        """(key, label) — what the booth and the papers should call him.

        Ordered from the top down, because a man who has three titles is a
        legend whatever else is also true of him.

        THE UNTITLED HALF IS THE INTERESTING PART. "Rookie" has to stop being
        true at some point even without a championship, or a driver who
        climbed three divisions the hard way is still being called a rookie in
        Formula 2 — which is the exact opposite of the reward this exists to
        give. So a driver who has been PROMOTED becomes a riser, and one who
        has reached a professional division becomes a contender, titles or no.
        """
        titles = self.title_count()
        if titles >= ladder_mod.ENDING_ARCS:
            return "legend", "Legend"
        if titles >= 2:
            return "multi", "Multiple champion"
        if titles >= 1:
            return "champion", "Champion"
        prog = self.ladder
        # A SEASON HE HAS FINISHED IS A SEASON BEHIND HIM, whether or not he
        # has been back to the menu to bank it. Same reason as `title_count`:
        # the arc is supposed to reward what he has done, and "have you
        # clicked End of season yet" is not something he did.
        done = len(self.data.get("ladder_history") or [])
        if self.season_done():
            done += 1
        if prog is not None:
            tier = prog.tier() or {}
            # A PROFESSIONAL SEAT IS A CONTENDER whatever else is true — but
            # only once he has a season behind him. A driver who ENTERED a
            # path at its professional rung (the reward for finishing another
            # one) is not a contender on the strength of the entry alone.
            if tier.get("register") == "professional" and done:
                return "contender", "Contender"
            # SEASONS COMPLETED, NOT RUNGS REACHED. `reached` is non-zero for
            # anybody who joined a path partway up, so reading it here called
            # a man in his very first season a Riser — the exact opposite of
            # the arc this exists to give, which has to START at rookie.
            if done:
                return "riser", "Riser"
        return "rookie", "Rookie"

    def status_changed(self):
        """The status if it has just risen, else None. Marks it as seen.

        WRITES, and only this. The news feed and the booth both want "he has
        just become a champion" and neither should have to remember it — one
        place remembers, and it is the place that already persists.
        """
        key, label = self.status()
        order = [k for k, _l in self.STATUS][::-1]
        was = self.data.get("status") or "rookie"
        if key == was:
            return None
        # ONLY UPWARDS. Nothing in a career can take a championship away, but
        # a sideways move onto a new path drops him back to a junior division
        # — and "Dante Kandasamy has been demoted to Riser" is a headline no
        # sport has ever run.
        if order.index(key) < order.index(was):
            return None
        self.data["status"] = key
        self.save()
        return key, label

    def resume(self):
        """Everything true about this driver's career so far, for the booth.

        "The reigning Formula 3 champion, and this is his first race in
        Formula 2" is the line this exists for — and the far bigger one, once
        a driver has been climbing for a while: a man in Formula One who won
        NASCAR four seasons ago. Most of the gameplay is the commentary, so
        the booth knowing where somebody came from is worth more than another
        panel.

        EVERY FIGURE HERE WAS WATCHED. Titles are seasons this overlay
        recorded and scored; `seasons` counts seasons actually completed;
        `races` counts rounds banked under THE LAW. Nothing is a claim about
        the real world, which is why it is safe at any rung and in any era —
        it is the one kind of driver knowledge a fictional GT4 grid can have.

        Returns None off a ladder: an ordinary open career has no arc, and
        "his career" would then mean whatever happens to be in one save file.
        """
        if not self.on_ladder:
            return None
        hist = self.data.get("ladder_history") or []
        titles = [h for h in hist if h.get("pos") == 1]
        arcs = [k for k in self.paths_won]
        cur = self.evaluate() or {}
        # The seasons already banked, PLUS the one being raced. A record that
        # ignores the current season is a record that is wrong all year and
        # right for the ten minutes after a promotion.
        wins = (sum(h.get("wins") or 0 for h in hist)
                + sum(1 for r in self.rounds if (r.get("pos") or 0) == 1))
        podiums = (sum(h.get("podiums") or 0 for h in hist)
                   + sum(1 for r in self.rounds
                         if 0 < (r.get("pos") or 0) <= 3))
        return {
            "seasons": len(hist),
            "races": sum(h.get("rounds") or 0 for h in hist) + len(self.rounds),
            "wins": wins,
            "podiums": podiums,
            "history": list(hist),
            "titles": [(h.get("name", ""), h.get("when", 0)) for h in titles],
            "title_count": len(titles),
            # The most recent title, which is the one worth saying: "the
            # reigning Formula 3 champion" only means anything about the
            # season just gone.
            # THE LAST TITLE IN HISTORY ORDER, not the newest timestamp.
            #
            # `max(titles, key=when)` returns the FIRST of any tie, and the
            # timestamps tie constantly: seasons archived in the same second
            # — which is every quick career and every simulated one — made a
            # man who had just won Formula 4 "the reigning Karting champion".
            # `ladder_history` is appended in order, so its last title is the
            # most recent one by construction, with no clock involved.
            "reigning": titles[-1].get("name") if titles else "",
            # ...and only while it IS the season just gone. A man who won F3
            # two rungs ago is not the reigning anything.
            "reigning_now": bool(titles and hist and titles[-1] is hist[-1]),
            "arcs_won": arcs,
            "arc_names": [(ladder_mod.path(k) or {}).get("name", k)
                          for k in arcs],
            "career_pct": self.career_pct(),
            "status": self.status()[0],
            "status_label": self.status()[1],
            "tier_name": cur.get("tier_name", ""),
            "path_name": cur.get("path_name", ""),
            "since": int(self.data.get("created") or 0),
        }

    def _archive_season(self, tier, pos):
        """Keep a summary of the season just finished, and only a summary.

        WINS AND PODIUMS ARE COUNTED HERE OR THEY ARE LOST FOR EVER. The next
        line of `_start_rung` wipes `rounds`, so this is the last moment the
        season's races exist — and "eleven wins across his career" is exactly
        the sentence the records view and the champion's profile are for. The
        summary is small on purpose (a whole season of classifications per rung
        would grow the save without bound), so what it keeps has to be chosen
        rather than assumed.
        """
        st = self.title_state() or {}
        wins = sum(1 for r in self.rounds if (r.get("pos") or 0) == 1)
        podiums = sum(1 for r in self.rounds if 0 < (r.get("pos") or 0) <= 3)
        self.data.setdefault("ladder_history", []).append({
            "path": (self.data.get("ladder") or {}).get("path", ""),
            "tier": tier.get("key", ""),
            "name": tier.get("name", ""),
            "pos": pos,
            "points": st.get("my_points"),
            "rounds": len(self.rounds),
            "wins": wins,
            "podiums": podiums,
            "when": int(time.time()),
        })

    def _start_rung(self, tier, rounds=None, how=None):
        """Wipe the season and open a new one at this rung.

        THE CLASS LOCK MUST GO WITH IT. `cls` is filled in by the first race a
        season records, so carrying it across would lock a Formula 4 season to
        the karting class and then match nothing for the rest of the career —
        a career that silently stops counting, which is the worst failure this
        module has.
        """
        self.data["name"] = tier.get("name") or self.data.get("name", "")
        self.data["rounds"] = []
        self.data["quali_results"] = []
        self.data["cls"] = ""
        self.data["cls_any"] = []
        # ...AND THE CAR HE CHOSE GOES WITH IT. A new division is a new
        # question: the Clio he picked for Hot hatch means nothing in Touring
        # cars, and leaving it set would have the FIA telling him to load a
        # car that is not eligible for the championship he has been promoted
        # into.
        self.data.pop("car_pick", None)
        # HOW HE GOT HERE, because the paper needs a different sentence for
        # each way of arriving and only `advance()` knows which it was.
        # Earning a seat, taking a different path after missing the cut, and
        # a champion being granted a new arc are three different stories, and
        # a feed that writes "he has joined Formula 4" for all three has not
        # been watching his career.
        if how:
            self.data["arrived_by"] = how
        else:
            self.data.pop("arrived_by", None)
        if rounds:
            self.data["length"] = int(rounds)

    # -- which car he is racing this season ---------------------------------
    def car_pick(self):
        """(pretty name, folder) he chose for this rung, or None."""
        p = self.data.get("car_pick")
        if not p or not isinstance(p, (list, tuple)) or len(p) != 2:
            return None
        return (p[0], p[1])

    def pick_car(self, folder, name=None):
        """Choose the car for this season. Written, and not lightly.

        Asked for as an RPG beat: *"instead of it telling me which car is
        eligible, give the player a select option ... let the player pick
        which between these 2 they will race in"*.

        IT IS A CHOICE FOR THE WHOLE SEASON, and the binding is the class
        lock that already exists rather than a second one invented here. The
        first race a season records fills in `cls`, and from then on `match()`
        refuses anything else — so picking a car and racing it IS binding, by
        the mechanism the module already trusts.

        WHY NOT ENFORCE IT BEFORE THE FIRST RACE. A pick is a FOLDER name and
        a live session reports a CarClass; the two are different names for a
        car and `ladders.json` only maps them one-to-one on some rungs (Hot
        hatch does, Touring cars does not — `volvo s40` has no class alias).
        Refusing a session on a mapping that is right for some divisions and
        guesswork for others would risk a career that silently stops counting,
        which is the worst failure this module has and the one THE LAW was
        rewritten to prevent. So the pick decides what he loads and what the
        letters say; the class lock decides what counts.
        """
        if not folder:
            return None
        # THE NAME IS PASSED IN WHERE THERE IS ONE, because a folder does not
        # always identify a car. `Kart_cup_2014` holds both "Kart Junior" and
        # "Kart F1", so deriving the name from the folder would store the same
        # thing for two different choices — and tell him to go and select
        # "Kart Cup 2014", which is not on the menu in the game.
        pretty = name
        if not pretty:
            try:
                import ladder as ladder_mod
                pretty = ladder_mod.pretty_mod(folder)
            except Exception:
                pretty = folder
        self.data["car_pick"] = [pretty, folder]
        self.save()
        return (pretty, folder)


if __name__ == "__main__":
    print("presets:")
    for k, v in presets().items():
        print("  %-10s %-14s %d rounds%s"
              % (k, v.get("name", ""), len(v.get("calendar", [])),
                 "  (open)" if v.get("open") else ""))
    cs = list_careers()
    print("\ncareers: %s" % ("none" if not cs else ""))
    for c in cs:
        print("  %-18s %-16s round %d/%s"
              % (c["slug"], c["name"], c["done"], c["total"] or "?"))
