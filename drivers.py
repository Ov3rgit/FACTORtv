# -*- coding: utf-8 -*-
"""
FACTORtv — real-world driver knowledge.

The booth knows the race perfectly and knows nothing about the SPORT. It can
tell you Hamilton is third and closing; it cannot tell you he is a seven-time
world champion chasing an eighth, which is the sentence that makes a
broadcast sound like a broadcast rather than a telemetry reader.

This module is that missing half. It is deliberately small, deliberately
narrow, and built around one rule:

    A FALSE CLAIM ABOUT SENNA COSTS MORE THAN SILENCE ABOUT SENNA.

Everything here is therefore gated three times over. A fact is only reachable
if (a) the season is one we actually have data for, (b) the era detected on
track matches that season, and (c) the driver's name resolves unambiguously.
Any of those failing returns None, and None means the booth says nothing at
all — there is no generic fallback and there must never be one, because a
generic fallback is exactly how a made-up statistic gets on air.

Scope
-----
THREE SEASONS ONLY: 1988, 2021, 2025. That is what the user tests on, and the
point of this pass is to prove the structure before it is widened. Adding a
season is adding a block to `lines_data/drivers.json` and nothing else —
there is no code here that knows about any particular year.

What a fact IS
--------------
Every number in the data file is the driver's record **as of the first race
of that season** — wins and titles he had already taken when he arrived. That
choice matters and it is the only one that can be defended:

  * A career total ("Prost, fifty-one wins") is FALSE in 1988. He had 28.
  * A live within-season standing ("Hamilton leads by 12 points") cannot be
    known, because the season being raced is the user's own invented one.

So the tense is fixed for every line in `booth_driver.json`: what a driver
brought WITH him. "Prost, twenty-eight wins and two titles already" is true
on the grid at Silverstone in 1988 no matter what the user does to the
championship afterwards, and it stays true in the last round.

Name matching
-------------
Mods spell names their own way. The 1988 field arrives as "Andrea DeCesaris"
and "Rene Arnoux"; the 2025 mod ships "Gabriel Bortoletto" and "Carlos Sainz
Jr.". So matching folds accents, drops punctuation, spaces and suffixes, and
each entry may carry explicit `alias` spellings for the cases folding cannot
reach. A surname alone resolves only when it is unique in that season — the
whole point is to avoid confident wrong answers, and two Schumachers on one
grid is exactly the shape of that mistake.
"""
import json
import os
import re
import sys
import unicodedata

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(_DIR, "lines_data", "drivers.json")

# Disciplines this knowledge can apply to. A GT car in 2021 is not the 2021
# Formula One season, and "Alonso, two-time world champion" over a Hypercar
# would be true of the man and wrong about the race.
_DISCIPLINES = ("f1", "formula")

# Name suffixes and honorifics that are never part of the identity.
_SUFFIXES = ("jr", "jnr", "junior", "sr", "snr", "senior", "ii", "iii")

_NON_ALPHA = re.compile(r"[^a-z]+")


def _fold(s):
    """A name reduced to the letters that identify it.

    Accents go (Hulkenberg / Hülkenberg), punctuation goes (Sainz Jr.),
    spacing goes (DeCesaris / de Cesaris). What is left is comparable across
    every mod's spelling of the same person.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("ø", "o").replace("ß", "ss")
    parts = [p for p in _NON_ALPHA.split(s) if p and p not in _SUFFIXES]
    return "".join(parts)


def _surname(s):
    """The last meaningful word of a name, folded. Empty for a single word —
    a mononym is not a surname we can safely match on."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    words = [w for w in _NON_ALPHA.split(s.lower()) if w and w not in _SUFFIXES]
    if len(words) < 2:
        return ""
    return words[-1]


# --------------------------------------------------------------------------
# spoken numbers
#
# The booth SAYS these. "95 wins" is read back by edge-tts as "ninety-five"
# reliably enough, but "his 8th" is not — it comes out as "his eight-th" often
# enough to be worth never risking. So anything that goes into a template is
# rendered as words here.
# --------------------------------------------------------------------------
_UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven",
          "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
          "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety"]
# Ordinals are built by rewriting the LAST word of the spoken number, which
# is the only approach that survives three digits: "win number one hundred and
# six" becomes "the one hundred and sixth", and a driver in his second career
# with Hamilton's baseline will get there. Anything not in this table takes a
# plain "th", which is correct for thirteen through nineteen.
_ORD_SUFFIX = {
    "zero": "zeroth", "one": "first", "two": "second", "three": "third",
    "four": "fourth", "five": "fifth", "six": "sixth", "seven": "seventh",
    "eight": "eighth", "nine": "ninth", "ten": "tenth", "eleven": "eleventh",
    "twelve": "twelfth", "twenty": "twentieth", "thirty": "thirtieth",
    "forty": "fortieth", "fifty": "fiftieth", "sixty": "sixtieth",
    "seventy": "seventieth", "eighty": "eightieth", "ninety": "ninetieth",
    "hundred": "hundredth",
}
_LAST_WORD = re.compile(r"[a-z]+$")


def spoken_number(n):
    """A count, as a commentator would say it. Falls back to digits above
    the range where words stay natural."""
    if n is None:
        return ""
    n = int(n)
    if n < 0 or n > 999:
        return str(n)
    if n < 20:
        return _UNITS[n]
    if n < 100:
        t, u = divmod(n, 10)
        return _TENS[t] + ("-" + _UNITS[u] if u else "")
    h, r = divmod(n, 100)
    return _UNITS[h] + " hundred" + (" and " + spoken_number(r) if r else "")


def spoken_ordinal(n):
    """"eighth", for "chasing an eighth title"; "one hundred and sixth" for a
    win tally. Built from the spoken number so it never disagrees with it."""
    if n is None:
        return ""
    words = spoken_number(n)
    m = _LAST_WORD.search(words)
    if not m:
        return words
    last = m.group(0)
    return words[:m.start()] + _ORD_SUFFIX.get(last, last + "th")


def _article(word):
    """"an eighth", "a fifth". Only ever applied to our own number words, so
    the vowel test is safe — there is no "a one-armed" case to worry about."""
    return "an" if word[:1] in "aeiou" else "a"


def titles_phrase(n):
    """"a seven-time world champion" — the article included, because LAW 13
    says the template may not supply one.

    Shared by the historical record and the live one, and that is the reason
    it is a function: a driver who arrives with seven titles and wins another
    becomes an EIGHT-time champion, and "a eight-time" is the kind of small
    wrongness that a listener hears immediately. The article has to be
    computed from the number, not written into the sentence.
    """
    if not n:
        return ""
    if n == 1:
        return "a world champion"
    word = spoken_number(n)
    return "%s %s-time world champion" % (_article(word), word)


# --------------------------------------------------------------------------
# the record
# --------------------------------------------------------------------------
class Team(object):
    """What a team's car is like THIS SEASON.

    Present tense and about the machinery, never the results: the booth is
    calling a race the user is driving, so "Mercedes have the straight-line
    speed" is fair and "Mercedes won the constructors' championship" is both
    a spoiler and contradicted by the timing screen.
    """

    __slots__ = ("name", "season", "strength", "weakness", "note")

    def __init__(self, name, season, d):
        self.name = d.get("name") or name
        self.season = season
        self.strength = d.get("strength") or ""
        self.weakness = d.get("weakness") or ""
        self.note = d.get("note") or ""

    def slots(self):
        return {"team": self.name, "strength": self.strength,
                "weakness": self.weakness, "tnote": self.note}

    def __repr__(self):
        return "<Team %s %d>" % (self.name, self.season)


class Driver(object):
    """One driver's record as of the first race of one season.

    Every attribute is either a fact from the data file or None. There are no
    computed guesses: `wins` is None when we do not know it, and a None makes
    every line that mentions wins ineligible rather than printing a zero.
    """

    __slots__ = ("name", "season", "team", "titles", "wins", "podiums",
                 "starts", "rookie", "champion_years", "note", "tag",
                 "new_team", "contender", "raw", "club")

    def __init__(self, name, season, d):
        self.raw = d
        self.name = d.get("name") or name
        self.season = season
        self.team = d.get("team") or ""
        self.titles = d.get("titles")
        self.wins = d.get("wins")
        self.podiums = d.get("podiums")
        self.starts = d.get("starts")
        self.rookie = bool(d.get("rookie"))
        self.champion_years = tuple(d.get("champion_years") or ())
        # A single hand-written clause, used verbatim. This is where anything
        # that is true of exactly one driver lives — "back after two years
        # away", "the most starts in the sport's history" — because a data
        # schema general enough to express those would be a schema nobody can
        # keep correct.
        self.note = d.get("note") or ""
        self.tag = d.get("tag") or ""
        self.new_team = bool(d.get("new_team"))
        # Is he expected to fight for THIS season's title? An editorial call,
        # and the gate on the "chasing an eighth" family. Without it the booth
        # asks whether Alonso can take a third world championship from an
        # Aston Martin in 2025, which is not a broadcast, it is a daydream.
        self.contender = bool(d.get("contender"))
        # The team's own record for this season, bound at load. A driver is
        # the only route to it: the booth is looking at a CAR on track, and
        # the thing it knows about that car is who is driving it. Bound here
        # rather than looked up on demand so the category predicates can ask
        # about the machinery without needing the era passed to them.
        self.club = None

    # -- derived phrasing ---------------------------------------------------
    #
    # Rendered here rather than in the templates so that the pools stay
    # readable and, more importantly, so the plural and the article are
    # decided ONCE. A template that says "a {n}-time champion" is a
    # determiner in front of a slot, which is LAW 13.

    @property
    def is_champion(self):
        return bool(self.titles)

    @property
    def reigning(self):
        """Did he win the title in the season immediately before this one?"""
        return bool(self.champion_years
                    and max(self.champion_years) == self.season - 1)

    @property
    def winless(self):
        """Known to have never won a race. False when wins are unknown — an
        absent number must never become a claim that he has never won."""
        return self.wins == 0

    def titles_phrase(self):
        """"a world champion" / "a seven-time world champion"."""
        return titles_phrase(self.titles)

    def next_title(self):
        """"an eighth" — the title he would be taking THIS season."""
        if self.titles is None:
            return ""
        o = spoken_ordinal(self.titles + 1)
        return "%s %s" % (_article(o), o)

    def wins_phrase(self):
        if self.wins is None:
            return ""
        if self.wins == 0:
            return "no wins"
        if self.wins == 1:
            return "one win"
        return "%s wins" % spoken_number(self.wins)

    def slots(self):
        """Template slots for this driver.

        Every value is a finished English fragment or an empty string. An
        empty string is what makes a line ineligible — see `eligible()` — so
        nothing here may invent a placeholder.
        """
        d = {
            "drv": self.name,
            "team": self.team,
            "titles": self.titles_phrase(),
            "ntitles": spoken_number(self.titles) if self.titles else "",
            "next_title": self.next_title(),
            "wins": self.wins_phrase(),
            "nwins": spoken_number(self.wins) if self.wins else "",
            "podiums": (spoken_number(self.podiums)
                        if self.podiums is not None else ""),
            "starts": (spoken_number(self.starts)
                       if self.starts is not None else ""),
            "note": self.note,
            "yr": str(self.season),
        }
        # Team clauses ride along in every slot dict. They cannot air on
        # their own — only a `team_*` category can draw a template that uses
        # them, and `CATEGORIES` refuses those unless the clause exists.
        if self.club is not None:
            d.update(self.club.slots())
        return d

    def __repr__(self):
        return "<Driver %s %d titles=%s wins=%s>" % (
            self.name, self.season, self.titles, self.wins)


# --------------------------------------------------------------------------
# the data file
# --------------------------------------------------------------------------
_data = None
_index = {}          # season -> {"full": {...}, "sur": {...}, "drivers": [...]}
_problems = []


def load(force=False):
    """Read `drivers.json` and build the per-season name indexes.

    A missing or broken file is survivable and produces an empty knowledge
    base — every lookup then returns None, and the booth simply never reaches
    for a driver fact. That is the correct failure: quieter, not wronger.
    """
    global _data, _index, _problems
    if _data is not None and not force:
        return _data
    _data, _index, _problems = {}, {}, []
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        _problems.append("drivers.json: %s" % e)
        return _data

    for skey, block in (raw.get("seasons") or {}).items():
        try:
            season = int(skey)
        except (TypeError, ValueError):
            _problems.append("season key %r is not a year" % skey)
            continue
        teams = {}
        for tname, t in (block.get("teams") or {}).items():
            if not isinstance(t, dict):
                _problems.append("%s/%s: team entry is not an object"
                                 % (skey, tname))
                continue
            teams[_fold(tname)] = Team(tname, season, t)
        full, sur, dupes, people = {}, {}, set(), []
        for name, d in (block.get("drivers") or {}).items():
            if not isinstance(d, dict):
                _problems.append("%s/%s: entry is not an object" % (skey, name))
                continue
            drv = Driver(name, season, d)
            drv.club = teams.get(_fold(drv.team))
            people.append(drv)
            keys = [name, drv.name] + list(d.get("alias") or ())
            for k in keys:
                fk = _fold(k)
                if fk:
                    full[fk] = drv
            # Surnames are indexed only while they stay unique. The second
            # driver to claim one poisons it for both, which is the whole
            # safety property: a grid with two Schumachers resolves NEITHER
            # from a bare surname rather than resolving both to one of them.
            s = _surname(drv.name)
            if s:
                if s in sur and sur[s] is not drv:
                    dupes.add(s)
                sur[s] = drv
            for a in (d.get("alias") or ()):
                sa = _surname(a)
                if sa and sa not in sur:
                    sur[sa] = drv
        for s in dupes:
            sur.pop(s, None)
        _index[season] = {"full": full, "sur": sur, "drivers": people,
                          "teams": teams,
                          "label": block.get("label") or str(season),
                          "series": block.get("series") or ""}
        _data[season] = block
    return _data


def seasons():
    """Which seasons we have data for."""
    load()
    return sorted(_index.keys())


def season_of(era):
    """The season this era IS, or None.

    Both gates live here: the discipline must be single-seater, and the year
    must be one we have. `era.year` is the mod's own year where the strings
    carried one and an inference from the constructor list otherwise, which
    is exactly the level of confidence this needs — the 2021 grid is dated
    from the team names and that is the case this whole feature exists for.
    """
    load()
    if era is None:
        return None
    if getattr(era, "discipline", "") not in _DISCIPLINES:
        return None
    year = getattr(era, "year", None)
    if year in _index:
        return year
    return None


def lookup(name, era):
    """The record for this driver in this era, or None.

    None is the normal, expected answer — most names on most grids are AI
    filler, and the correct behaviour for those is silence.
    """
    season = season_of(era)
    if season is None or not name:
        return None
    idx = _index[season]
    fk = _fold(name)
    if not fk:
        return None
    hit = idx["full"].get(fk)
    if hit is not None:
        return hit
    # A surname alone, only where it is unambiguous in this season. The name
    # we were handed may BE a bare surname ("Verstappen" — some mods list the
    # grid that way), in which case `_surname` refuses it for having only one
    # word and the folded string is the surname itself.
    sur = _surname(name) or fk
    return idx["sur"].get(sur)


def roster(era):
    """Every driver we know about in this era. Empty when the era is not one
    of ours."""
    season = season_of(era)
    if season is None:
        return []
    return list(_index[season]["drivers"])


def quote(name, era, occasion):
    """This driver's signature radio line for this kind of moment, or "".

    Empty is the normal answer: most drivers have no catchphrase, most
    moments are not an occasion, and a line fired at the wrong one turns a
    character into a parrot. The caller decides how RARELY to reach for this;
    all this does is refuse to supply one that does not fit.
    """
    d = lookup(name, era)
    if d is None:
        return ""
    qs = (d.raw.get("quotes") or {}).get(occasion) or []
    return qs[0] if qs else ""


def has_quotes(name, era):
    d = lookup(name, era)
    return bool(d is not None and d.raw.get("quotes"))


def names_for_class(cls, members=()):
    """Every real driver we hold for the season a car class belongs to.

    The career's driver picker is built from rF2's own result files, which is
    right — they are the real grid, whatever mod it came from. But it means
    the list is empty until you have raced, and short until you have raced a
    few times: a fresh install offers nobody, and "I want to race as
    Hamilton" is a thing you want to do on the first race, not the fifth.

    So for the three seasons we actually hold, the roster seeds the picker.
    `members` is the career's `cls_any` — the constructor list — which is
    what dates a team-named grid at all.

    Returns [] for anything we have no records for, and the picker falls back
    to history alone, exactly as before.
    """
    import era as era_mod
    e = era_mod.classify(cls or "", "", field_classes=tuple(members or ()))
    return sorted(d.name for d in roster(e))


_MINE = None


def my_names(force=False):
    """Names the user typed into `lines_data/mynames.json`.

    Neither source the picker draws on can contain a name he invented: one is
    what rF2 reported in his own results, the other is the record book. A
    career raced as somebody who does not exist is the normal case for a
    ladder, so the list has to be editable — and a file he can open is a far
    better answer than a menu that cannot take typed input (the overlay never
    holds the keyboard; see `_rows_name`).
    """
    global _MINE
    if _MINE is not None and not force:
        return _MINE
    _MINE = []
    try:
        path = os.path.join(_DIR, "lines_data", "mynames.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for n in (data.get("names") or []):
            if isinstance(n, str) and n.strip():
                _MINE.append(n.strip())
    except Exception:
        pass
    return _MINE


def picker_names(seen, cls, members=()):
    """The career menu's driver list: history and knowledge base, merged.

    THE USER'S OWN NAMES ARE NOT MERGED HERE. `my_names()` holds invented
    names and this function is the knowledge layer — `drivertest.py` §26 holds
    it to returning exactly the roster a season has and nothing else, which is
    the right contract for a thing that answers "who is really on this grid".
    The MENU stacks his own names on top; see `_rows_name`.

    `seen` is what rF2's result files reported. Returns one entry per person,
    spelled the way we would want it said out loud.

    IDENTITY GOES THROUGH `lookup`, NOT THROUGH FOLDING. Folding equates
    spellings that differ by accent, punctuation or spacing, and that is not
    enough here — the 2025 mod ships "Yuski Tsunoda" (a typo) and "Kimi
    Antonelli" (a short form), and both fold to something different from the
    canonical name while resolving perfectly well through the surname and
    alias index. A fold-only merge offered the user Tsunoda twice in the same
    menu, under both spellings.

    Where both sources have a person, the KNOWN spelling wins: whichever name
    is chosen is what the engineer says out loud for the rest of the career,
    and "Yuski" is not a name.
    """
    import era as era_mod
    e = era_mod.classify(cls or "", "", field_classes=tuple(members or ()))
    known = roster(e)
    if not known:
        # Nothing held for this season, so history is the only source and it
        # is passed through untouched — it is the real grid for the other
        # eighty mods on this machine.
        return sorted({n for n in seen if n})

    out = {}
    for n in seen:
        if not n:
            continue
        hit = lookup(n, e)
        out[hit.name if hit is not None else _fold(n)] = (
            hit.name if hit is not None else n)
    for d in known:
        out[d.name] = d.name
    return sorted(out.values())


def label(era):
    """"the 1988 Formula One season" — the season's own name, for lines that
    frame a fact in its season."""
    season = season_of(era)
    if season is None:
        return ""
    return _index[season]["label"]


# --------------------------------------------------------------------------
# choosing what to say
# --------------------------------------------------------------------------
#
# Each pool in `booth_driver.json` needs particular facts to exist, and a line
# whose facts are missing must never be offered. This table is that
# requirement, expressed once, in code rather than in the data — because it
# is the piece that keeps a blank slot off the air (LAW 5) and a rule that
# important should not live in a file anyone can edit casually.
#
# THE PREDICATE TAKES A `Standing`, NOT A `Driver`, AND THAT IS THE WHOLE
# POINT OF CONTINUITY.
#
# A `Driver` is frozen history. Judged on one, a man who took his first
# Grand Prix win in round two of your career is still "still looking for that
# first win" in round three — which is the single most obvious way this
# feature could make the booth look like it is not watching. A `Standing` is
# the record as it stands right now, so `winless` stops being true the moment
# he wins, and `driver_winner` starts being true in the same instant.
CATEGORIES = {
    # He has titles, and could take another this season.
    "driver_champion":  lambda d: d.titles is not None and d.titles >= 1,
    # He won the LAST one. Different sentence entirely, and the strongest
    # thing the booth can say about anybody on the grid.
    "driver_reigning":  lambda d: d.reigning,
    # A multiple champion going for a specific number, and in a car that
    # could plausibly deliver it. Kept separate from `driver_champion` so the
    # count can be named without every champion line having to carry it.
    "driver_chasing":   lambda d: (d.titles is not None and d.titles >= 2
                                   and d.contender),
    # Expected to be in the title fight. A prediction, and the lines say so —
    # nothing here claims to know how the user's season ends.
    "driver_favourite": lambda d: d.contender,
    # Wins but no title — the nearly men, and the best colour on any grid.
    # Gated on the HISTORICAL wins, not the live ones: a driver whose only
    # victory is one of yours belongs to `driver_season_wins`, which says so
    # ("one win this season") instead of implying a career behind it. The
    # {wins} slot is still the live total, so Prost winning one of your races
    # moves to twenty-nine.
    "driver_winner":    lambda d: (d.titles == 0
                                   and (getattr(d, "base", d).wins or 0) >= 1),
    # Still looking for the first one. Mansell in 1988, Norris in 2021 —
    # and NOT either of them once they have won one of your races.
    "driver_winless":   lambda d: d.winless and not d.rookie,
    "driver_rookie":    lambda d: d.rookie,
    # What he has done in YOUR season. The positive half of continuity: the
    # booth not only stops calling him winless, it starts saying why.
    "driver_season_wins": lambda d: getattr(d, "season_wins", 0) >= 1,
    # A hand-written clause. Always last, always exact.
    "driver_note":      lambda d: bool(d.note),
    "driver_new_team":  lambda d: d.new_team and bool(d.team),
    # WHAT HIS CAR IS LIKE THIS YEAR. Reached through the driver because that
    # is what the booth is looking at — a car on track with a name attached.
    # `car_character` in booth_cars.json covers what the whole FIELD is like
    # and needs none of this; these three are the differences between the
    # teams within one season, which only exist for seasons we hold.
    "team_strength":    lambda d: bool(d.club and d.club.strength),
    "team_weakness":    lambda d: bool(d.club and d.club.weakness),
    "team_note":        lambda d: bool(d.club and d.club.note),
}


def eligible(driver):
    """Which categories this driver can legally support, most interesting
    first. Order is the editorial judgement: what is the single most
    remarkable true thing about this man?"""
    if driver is None:
        return []
    # What this season has done to him comes FIRST. A man who won last time
    # out is more interesting than a man who was runner-up in 1986, and the
    # viewer was there for one of those.
    order = ["driver_season_wins", "driver_reigning", "driver_chasing",
             "driver_champion", "driver_note", "driver_new_team",
             "driver_favourite", "driver_winner", "driver_winless",
             "driver_rookie",
             # The machinery comes after the man. A driver's record is the
             # more interesting fact about a car going past, and a team's
             # character is the thing that explains what it then does.
             "team_note", "team_strength", "team_weakness"]
    return [c for c in order if CATEGORIES[c](driver)]


def slots_for(driver, category):
    """Slots for one line, or None if the category is not legal for him.

    Going through here rather than calling `slots()` directly is what stops a
    "chasing an eighth" template being filled for a driver with no titles —
    `safe_format` would blank the slot and air "chasing , and he" instead of
    refusing.
    """
    if driver is None or category not in CATEGORIES:
        return None
    if not CATEGORIES[category](driver):
        return None
    return driver.slots()


# --------------------------------------------------------------------------
# THE RECORD, LIVE
#
# Everything above is history: what a driver brought to the season. That is
# only half of what a broadcast knows. The other half is what has happened
# since — and in this product "since" means the user's own career, where he
# might be driving as Hamilton and might be about to win a title Hamilton
# never won.
#
# So the number the booth says is the SUM: ninety-five wins in 2021, plus the
# three you have taken as him this season, is ninety-eight. And when the
# championship is mathematically settled in his favour, that is his eighth.
#
# This applies to the AI as much as to the player. If Senna takes the title
# in your 1988 career, that is a FIRST world championship for Ayrton Senna,
# and it is the biggest sentence the booth will say all season.
#
# The maths is never done here. `season.Career` owns it, exactly, including
# the refusal to claim a title is settled when the remaining points are
# unknown (LAW 4) — this only reads it and adds the history on top.
# --------------------------------------------------------------------------
class Standing(object):
    """A driver's record RIGHT NOW: history plus this career.

    `base` is the historical record and never changes. Everything else is
    what the season has added to it.
    """

    __slots__ = ("base", "name", "season_wins", "wins", "titles",
                 "won_title", "new_champion", "first_win", "note")

    def __init__(self, base, season_wins=0, won_title=False, note=None):
        self.base = base
        self.name = base.name
        self.season_wins = season_wins
        # The running totals — the numbers a commentator would actually say.
        self.wins = (base.wins or 0) + season_wins
        self.titles = (base.titles or 0) + (1 if won_title else 0)
        self.won_title = won_title
        # "His first" is the sentence that matters most, and it is only
        # sayable because the historical baseline is known to be zero. A
        # driver we hold no record for produces no Standing at all, so there
        # is no case where this is guessed.
        self.new_champion = won_title and (base.titles or 0) == 0
        self.first_win = season_wins > 0 and (base.wins or 0) == 0
        # A note can go stale. "Whose last win came five seasons ago" is no
        # longer true of a René Arnoux who has just won one of your races, and
        # a booth that keeps saying it has stopped watching. `note_void_on` in
        # the data file declares what falsifies each clause; `standing()`
        # blanks it when that has happened.
        self.note = base.note if note is None else note

    # -- everything history alone decides ----------------------------------
    #
    # Delegated rather than copied, so there is exactly one place each of
    # these is true. A rookie who wins a race is still in his rookie season;
    # a reigning champion is reigning because of LAST year, whatever happens
    # in this one.
    @property
    def rookie(self):
        return self.base.rookie

    @property
    def team(self):
        return self.base.team

    @property
    def new_team(self):
        return self.base.new_team

    @property
    def club(self):
        return self.base.club

    @property
    def contender(self):
        return self.base.contender

    @property
    def reigning(self):
        return self.base.reigning

    @property
    def winless(self):
        """Never won a race — INCLUDING this career's races.

        This is the property the whole continuity question turns on. Win your
        first as Mansell in round two and he stops being winless from round
        three onwards, because the booth is reading a running total rather
        than a frozen record.
        """
        return self.wins == 0

    def next_title(self):
        """The title he is TAKING — 'an eighth'. Only meaningful when he has
        just won one, so it counts the title including this one."""
        o = spoken_ordinal(self.titles)
        return "%s %s" % (_article(o), o)

    def slots(self):
        d = self.base.slots()
        d.update({
            "wins": ("one win" if self.wins == 1
                     else "%s wins" % spoken_number(self.wins)),
            "nwins": spoken_number(self.wins),
            "nth_win": spoken_ordinal(self.wins),
            "titles": titles_phrase(self.titles),
            "ntitles": spoken_number(self.titles) if self.titles else "",
            "this_title": self.next_title() if self.won_title else "",
            "note": self.note,
            # "one win this season", not "one wins this season". The plural
            # is decided here for the same reason the article is: a template
            # that hardcodes it is wrong for exactly one value, and one is
            # the value a first-time winner has.
            "swins": ("one win" if self.season_wins == 1
                      else "%s wins" % spoken_number(self.season_wins)),
            "nseason_wins": spoken_number(self.season_wins),
        })
        return d

    def __repr__(self):
        return "<Standing %s wins=%d(+%d) titles=%d%s>" % (
            self.name, self.wins, self.season_wins, self.titles,
            " NEW" if self.won_title else "")


def _keys_of(base):
    """Every folded spelling that means this driver.

    A career's `classified` lists hold whatever the MOD calls him — "Nico
    Hulkenberg", "Carlos Sainz Jr.", "Andrea DeCesaris" — while the record's
    canonical name is the properly spelled one. Comparing those two strings
    directly silently loses every result belonging to a driver whose name
    carries an accent, which is most of the interesting ones. So the compare
    is always folded, and against the aliases too.
    """
    keys = {_fold(base.name)}
    for a in (base.raw.get("alias") or ()):
        keys.add(_fold(a))
    keys.discard("")
    return keys


def _is(name, base):
    """Does this classification entry refer to this driver?

    A SURNAME COUNTS, because a career's `classified` list holds whatever the
    mod wrote and some of them write only the surname. Folding the full name
    alone missed those entirely and silently: the driver's wins were simply
    never counted, and the wrap went quiet rather than saying anything wrong.
    Matched the same way `lookup` matches, so the two can never disagree
    about who somebody is.
    """
    fk = _fold(name)
    if fk in _keys_of(base):
        return True
    return _surname(base.name) == (_surname(name) or fk)


def _career_results(career, base, upto=None):
    """(wins, podiums, starts) for this driver in this career.

    Read from the same `classified` lists the championship table is built
    from, so a win that counts for points counts here too — and a race the
    player abandoned was never recorded at all (THE LAW), so it cannot show
    up as somebody else's victory either.
    """
    wins = podiums = starts = 0
    for rnd in getattr(career, "rounds", ()) or ():
        if upto is not None and (rnd.get("n") or 0) > upto:
            continue
        for who, pos in rnd.get("classified", ()):
            # Through `_is`, not a folded-key set: some mods write only the
            # surname into the classification, and a set built from the full
            # name misses those silently — the driver's wins are simply never
            # counted and the wrap goes quiet instead of saying anything
            # wrong. One comparison, used everywhere, so `standing` and
            # `just_won_title` can never disagree about who somebody is.
            if not _is(who, base):
                continue
            starts += 1
            p = int(pos)
            if p == 1:
                wins += 1
            if p <= 3:
                podiums += 1
    return wins, podiums, starts


# What falsifies a hand-written note. A note is a clause about the man as he
# ARRIVED, and some of those stop being true the moment the season touches
# them: Hülkenberg's record for starts without a podium ends at his first
# podium, and Arnoux's "last win came five seasons ago" ends at his next win.
#
# Declared per note in `drivers.json` as `note_void_on`. Anything without one
# is a fact about the past that the present cannot reach — "the youngest race
# winner this sport has ever had" stays true however your season goes.
_NOTE_VOIDS = {
    "win": lambda w, p, st: w > 0,
    "podium": lambda w, p, st: p > 0,
    "start": lambda w, p, st: st > 0,
}


def standing(name, era, career, upto=None):
    """This driver's live record, or None.

    None whenever we hold no history for him — which is most of the grid, and
    the point: a running total is only worth saying when the number it starts
    from is real. "That's his fourth win" about a driver whose career began
    before this season is a lie by omission.
    """
    base = lookup(name, era)
    if base is None:
        return None
    if career is None:
        return Standing(base)
    try:
        st = career.title_state(upto)
    except TypeError:
        # An older Career without the `upto` argument. Better a standing
        # without the title than no standing at all.
        st = career.title_state()
    won = bool(st and st.get("decided") and _is(st.get("leader") or "", base))
    wins, podiums, starts = _career_results(career, base, upto)
    note = base.note
    void = _NOTE_VOIDS.get(base.raw.get("note_void_on") or "")
    if note and void and void(wins, podiums, starts):
        note = ""
    return Standing(base, wins, won, note=note)


def just_won_title(name, era, career, round_n):
    """Did this driver clinch the championship IN the round just finished?

    Compares the season as it stands against the season as it stood one round
    ago. A title settled at round eight is enormous news at round eight and
    old news at round nine, and a booth that announces it three times has
    stopped being believed.
    """
    if career is None or not round_n:
        return False
    now = standing(name, era, career, upto=round_n)
    if now is None or not now.won_title:
        return False
    before = standing(name, era, career, upto=round_n - 1)
    return not (before is not None and before.won_title)


def validate():
    """Structural check over the data file, for the test suite.

    The checks are the mistakes that produce a WRONG line rather than a
    missing one: a champion with no years listed cannot be tested for
    "reigning", and a year outside the season is a typo that would date the
    title wrong on air.
    """
    load()
    probs = list(_problems)
    for season in sorted(_index):
        idx = _index[season]
        for d in idx["drivers"]:
            w = "%d/%s" % (season, d.name)
            if d.titles is None:
                probs.append("%s: no title count — every driver needs one, "
                             "use 0" % w)
            elif d.titles != len(d.champion_years):
                probs.append("%s: %d titles but %d champion_years"
                             % (w, d.titles, len(d.champion_years)))
            for y in d.champion_years:
                if y >= season:
                    probs.append("%s: champion_years %d is not before the "
                                 "%d season" % (w, y, season))
            if d.wins is None:
                probs.append("%s: no win count" % w)
            elif d.titles and d.wins == 0:
                probs.append("%s: a champion with no wins" % w)
            if d.rookie and d.wins:
                probs.append("%s: a rookie with wins" % w)
            if d.rookie and d.titles:
                probs.append("%s: a rookie with titles" % w)
            if d.starts is not None and d.rookie and d.starts:
                probs.append("%s: a rookie with %d starts" % (w, d.starts))
            if d.podiums is not None and d.wins is not None \
                    and d.podiums < d.wins:
                probs.append("%s: fewer podiums (%d) than wins (%d)"
                             % (w, d.podiums, d.wins))
            if d.note and d.note.rstrip()[-1:] in ".!?":
                probs.append("%s: note ends in punctuation — it is a clause, "
                             "not a sentence: %r" % (w, d.note))
            if d.team and d.club is None:
                probs.append("%s: races for %r, which has no team entry — the "
                             "team lines can never reach him"
                             % (w, d.team))
        # TEAM CLAUSES MUST BE BARE NOUN PHRASES.
        #
        # Each one has to survive six different frames — "X have {s}", "The
        # problem at X is {w}", "{w}, that is what X are up against" — so a
        # capital letter, a full stop or an em-dash continuation breaks at
        # least one of them. Checked here rather than left to a reading,
        # because it reads fine in whichever frame you happened to try.
        drivers_teams = {d.team for d in idx["drivers"] if d.team}
        for tname, team in idx["teams"].items():
            w = "%d/%s" % (season, team.name)
            if team.name not in drivers_teams:
                probs.append("%s: no driver races for this team, so nothing "
                             "can ever reach it" % w)
            for field in ("strength", "weakness"):
                c = getattr(team, field)
                if not c:
                    continue
                if c[:1].isupper():
                    probs.append("%s.%s: starts with a capital — it is a "
                                 "clause inside a sentence: %r" % (w, field, c))
                if c.rstrip()[-1:] in ".!?":
                    probs.append("%s.%s: ends in a full stop: %r"
                                 % (w, field, c))
                if "—" in c or " - " in c:
                    probs.append("%s.%s: contains a dash continuation, which "
                                 "breaks the frames that append to it: %r"
                                 % (w, field, c))
            if team.strength and team.strength == team.weakness:
                probs.append("%s: strength and weakness are the same clause"
                             % w)
    return probs


def stats():
    load()
    return {s: len(_index[s]["drivers"]) for s in sorted(_index)}


if __name__ == "__main__":
    load()
    st = stats()
    if not st:
        print("No driver data in %s" % DATA_PATH)
        sys.exit(1)
    for season in sorted(_index):
        print("\n=== %s (%d drivers) ==="
              % (_index[season]["label"], len(_index[season]["drivers"])))
        for d in sorted(_index[season]["drivers"], key=lambda x: x.name):
            print("  %-26s %-16s %-30s %s"
                  % (d.name, d.team[:16], ", ".join(eligible(d))[:30],
                     d.note[:40]))
    probs = validate()
    if probs:
        print("\n%d problem(s):" % len(probs))
        for p in probs:
            print("  " + p)
    else:
        print("\nAll driver data valid.")
