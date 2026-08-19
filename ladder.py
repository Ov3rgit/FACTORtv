# -*- coding: utf-8 -*-
"""
FACTORtv — career ladders.

WHAT THIS IS FOR
----------------
`season.py` knows what happened in a championship. `career.py` knows what has
happened across all of them. Neither knows where a championship SITS — that
Formula 4 is a rung above karting and three below Formula One, that finishing
fifth is enough to leave one and not nearly enough to leave another.

That is the whole content of a career: not the race you are in, but the one
you are trying to earn. This module owns it.

    ladder.paths()                every path, in menu order
    ladder.tier_of(cls, veh)      which rung a car belongs to
    ladder.state(path, results)   where you are, and what the next seat needs

TWO NAMES FOR A CAR, AND THEY ARE NOT THE SAME NAME
---------------------------------------------------
A tier lists `mods` (installed folder names) and `classes` (the CarClass
string rF2 publishes). Both are needed and they answer different questions:

  * The FOLDER name is known before a car has ever been loaded, because it is
    just a directory on disk. That is what lets the New Career menu draw a
    whole ladder on a fresh install, including rungs the user has never
    touched.
  * The CLASS string is what a LIVE session gives us — from shared memory,
    every tick, in practice, qualifying and race alike. That is what credits a
    result to a rung.

The class cannot be read off the disk: vehicle definitions live inside
compressed `.mas` archives, exactly as track layouts do. Hence two keys.

WHY THE CAR LISTS ARE CURATED AND NOT SCANNED
---------------------------------------------
Installed does not mean raceable, and nothing on disk says which is which.
The paid GT3 cars are fully downloaded and identical in shape to free content
— same folders, same `.mas` files, 188MB apiece — and simply will not load
without the licence. A scan would offer a whole tier the user cannot race. So
`ladders.json` is hand-kept and the scan only ever suggests.

WHAT THIS MODULE WILL NOT DO
----------------------------
It does not invent driver knowledge. There is no real record behind a GT3
mod's AI or a karting field, and writing one would be the single thing this
product refuses to do. A ladder season's facts are EARNED instead: the career
already records every classification, and `drivers._career_results` already
counts wins and podiums for any name out of them. By round six the booth can
say "three wins already this season" because it watched, not because somebody
typed it.
"""
import json
import os
import re
import sys

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(_DIR, "lines_data", "ladders.json")

# Where rF2 keeps installed cars, relative to the game root that `career.py`
# already knows how to find. Only used to answer "does he own this rung"; a
# missing folder is a normal answer, not an error.
VEHICLES_TAIL = os.path.join("Installed", "Vehicles")

# WHAT FINISHES A PATH. Not reaching the top rung — WINNING it. Reaching
# Formula One and finishing eighth is a career and it is not a finished story,
# and the whole shape of a ladder is that the last step is the hardest. A 100%
# career is every one of these won, which is why the bar has to be the same on
# all of them.
ARC_WIN = 1

# HOW MANY ARCS MAKE A CAREER. Three of the five, and it is a story decision
# rather than a balance one: one championship is a season or two, which is
# nowhere near long enough to be a man who gave his life to this. Three
# divisions is years. Winning the other two afterwards is completionism and
# carries no ending — see HANDOVER, THE ENDING IS FOUR MESSAGES.
ENDING_ARCS = 3

_data = None
_installed = None


def load(force=False):
    global _data
    if _data is None or force:
        try:
            with open(DATA, "r", encoding="utf-8") as f:
                _data = json.load(f)
        except Exception:
            _data = {"paths": {}}
        _data.pop("_comment", None)
    return _data


def paths():
    """Every path, in the order the menu should offer them."""
    return load().get("paths", {})


def path(key):
    return paths().get(key)


def career_paths():
    """The paths a 100% career is counted over — every one but the tour.

    The historic path is BONUS CONTENT and deliberately outside all of this:
    nobody is promoted from 1966 to 1975, so there is no final championship to
    win and no arc to finish. Counting it would make 100% unreachable by
    construction, which is a worse bug than it sounds — the completion figure
    is what the story beats key off.
    """
    return {k: p for k, p in paths().items() if not p.get("tour")}


def entry_options(key, mods=None):
    """Where a proven driver may join this path: [(tier_index, tier), ...].

    Two seats, and the choice is his. A Formula One champion starting again in
    karting is absurd; forcing him straight into GT3 quietly deletes two thirds
    of a path he might have wanted to drive. So the bottom rung and the first
    PROFESSIONAL rung are both offered, and they collapse to one entry when a
    path's bottom rung is already professional.
    """
    ts = tiers(key)
    if not ts:
        return []
    out = [(0, ts[0])]
    for i, t in enumerate(ts):
        if t.get("register") == "professional":
            if i:
                out.append((i, t))
            break
    if mods is not None:
        out = [(i, t) for i, t in out if tier_installed(t, mods)]
    return out


def tiers(key):
    p = path(key)
    return list(p.get("tiers", ())) if p else []


def _norm(s):
    """Fold a mod folder or class name into something matchable.

    The same shape `track._norm` uses, and for the same reason: rF2 content
    names are camel-cased, underscored, versioned and inconsistent, and a
    plain lower() leaves half of them unmatched. Kept as a separate copy
    rather than imported because the noise words differ — a car name may
    legitimately contain "GT" or "Cup", which a circuit name may not.
    """
    s = s or ""
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)      # camelCase -> camel Case
    s = re.sub(r"(?<=[A-Za-z])(?=[0-9])", " ", s)   # F4Cup -> F4 Cup
    s = re.sub(r"[^A-Za-z0-9]+", " ", s).lower()
    return " %s " % re.sub(r"\s+", " ", s).strip()


def _hit(needle, hay):
    """Is this alias present as a whole token run inside `hay`?

    Substring alone is wrong here in a way it is not for circuits: "f1" sits
    inside "f150", "gt3" inside "gt350", and a car matched to the wrong rung
    credits a season to a championship the driver never entered. Both sides
    are normalised to space-padded strings, so a plain `in` on the padded
    needle IS a token test.

    ...AND THE SAME WORD FOLDS TWO WAYS DEPENDING ON ITS CASING. `_norm`
    splits camelCase, so "IndyCar" becomes "indy car" while "INDYCAR" and
    "indycar" stay whole — and rF2 content uses all three. The alias
    "indycar" therefore missed the class string "IndyCar" completely, which
    is a rung silently matching nothing.

    So there is a second pass with the spaces taken out of both sides. It is
    gated on length because a squashed compare has no token boundaries left
    to respect: at four characters and up a false hit needs a real coincidence
    ("indycar" inside something else), while at three "gt3" would happily
    match "gt350" and put a road car in a GT3 championship.
    """
    n = _norm(needle)
    if not n.strip():
        return False
    if n in hay:
        return True
    flat = n.replace(" ", "")
    return len(flat) >= 4 and flat in hay.replace(" ", "")


def tier_of(car_class="", vehicle=""):
    """Which rung this car belongs to, as (path_key, tier_index), or None.

    Tries the CLASS first — it is what a live session actually reports, and it
    is the more specific of the two. The vehicle/mod name is the fallback for
    the menu, where no session exists yet.

    LONGEST ALIAS WINS. "gt3" and "gt3 world series" both match the GT3 rung
    and that is harmless, but "sc2018" and "sc2018x" are DIFFERENT rungs of
    the stock-car path, and matching the shorter one first would promote a
    driver out of a series he is still in.
    """
    best = None
    for pkey, p in paths().items():
        for i, t in enumerate(p.get("tiers", ())):
            for field, value in (("classes", car_class), ("mods", vehicle)):
                if not value:
                    continue
                hay = _norm(value)
                for alias in t.get(field, ()):
                    if _hit(alias, hay):
                        n = len(alias)
                        if best is None or n > best[0]:
                            best = (n, pkey, i)
    return (best[1], best[2]) if best else None


def game_root():
    """Where rFactor 2 is installed, or "". Found from its own results folder.

    ONE PLACE ASKS THIS QUESTION. `installed_mods` used to work it out inline
    and `modnames` needs the same answer for a different subfolder — two copies
    of a path walk is two things to get wrong the day the layout changes.
    """
    try:
        import career as career_mod
        res = career_mod.find_results_dir()
        if res:
            return os.path.abspath(os.path.join(res, os.pardir, os.pardir,
                                                os.pardir))
    except Exception:
        pass
    return ""


def installed_mods(game_dir=None, force=False):
    """Folder names under Installed/Vehicles. Empty if unreadable.

    An empty list is a normal answer — the tests run on machines with no
    rFactor 2 — and every caller treats "unknown" as "do not claim".

    IT FINDS THE GAME ITSELF WHEN NOBODY TELLS IT WHERE, exactly as
    `track.installed()` does, and that is not a convenience. The first version
    required a `game_dir` from the caller and NOTHING EVER PASSED ONE, so the
    scan never ran, every rung answered "no car", and the divisions view told
    a man with eighty mods installed that he owned nothing. The panel test
    caught it because it renders the real rows rather than trusting the
    function to be called correctly.
    """
    global _installed
    if _installed is not None and not force:
        return _installed
    out = []
    roots = [game_dir] if game_dir else []
    if not roots:
        root = game_root()
        if root:
            roots.append(root)
    for root in roots:
        try:
            out = sorted(os.listdir(os.path.join(root, VEHICLES_TAIL)))
            break
        except Exception:
            out = []
    _installed = out
    return out


def known_mods():
    """The scanned install list, or None if nothing has ever scanned.

    UNKNOWN IS NOT THE SAME AS NONE, and this is the accessor that keeps them
    apart. `installed_mods()` caches whatever it was last asked for — so
    calling it with no game directory (which is what any caller that does not
    know one would do) permanently caches an EMPTY list, and every later
    "which of these cars do you own" answers nothing. Callers that only want
    to filter when a real scan exists ask here instead, and pass None
    onwards to mean "do not filter".
    """
    return _installed if _installed else None


# A YEAR ON ITS OWN, once the separators have gone. The first version tried to
# strip years straight out of the folder name with a word boundary and did
# nothing at all: UNDERSCORE IS A WORD CHARACTER, so "ClioCup_2010" has no
# boundary between the underscore and the 2. Separators first, then years.
_MOD_YEAR = re.compile(r"(?:^|\s)(?:19|20)\d\d(?=\s|$)")


def pretty_mod(folder):
    """A mod folder as something a person would say.

    "Renault_MeganeTrophyII_2013" -> "Renault Megane Trophy II". The rF2 UI
    shows its own names and this is not trying to reproduce them exactly; it is
    trying to be recognisable enough that a driver can find the car in a list.
    THE FOLDER IS ALWAYS QUOTED ALONGSIDE IT for the same reason — a tidy name
    that turns out to match two mods is worse than an ugly one that matches
    exactly the one on his disk.
    """
    s = re.sub(r"[_\-]+", " ", folder or "")
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
    s = _MOD_YEAR.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


# WHICH RUNGS ARE NAMED WITH THEIR YEAR.
#
# Asked for directly: "for the sake of the career and the story arc I want it
# to be year specific and mentioned in commentary for F2 and F1 — that 2021
# season is iconic and it will work better for players to feel like they are
# working towards it."
#
# THIS IS AN EXCEPTION THE PRODUCT ALREADY MAKES, not a new one. The rule
# that a mod's year is production metadata — "for knowing, never for saying"
# — is about the ROAD: a 1991 Silverstone layout must never announce itself,
# because that would tell a driver he is re-running somebody else's season.
# A SEASON year is the opposite: `season_launch` has always said "the opening
# round of the 1988 Formula One season", because that championship is his and
# it is the one thing here he is genuinely entitled to be told about.
#
# Only the last two rungs of the single-seater path, and only in a career:
# "the 2019 Formula 2 season" and "the 2021 Formula One season" are the two
# the whole climb is pointed at. Karting and Formula 4 stay year-free, where
# a year would be the mod's rather than the story's.
YEAR_RUNGS = frozenset(("f2", "f1"))


def named_year(tier, era):
    """The year to put in front of this rung's name, or None.

    DECLARED PER RUNG IN THE DATA, not listed in code. `YEAR_RUNGS` was the
    first version and it hardcoded the two single-seater rungs — which is
    wrong the moment a second path wants the same treatment, and the user
    wants exactly that: "for all other promotions I want to follow the same
    sort of arc for the last two divisions."
    #
    A rung asks for it with `"year_name": true`, and the year itself comes
    from the era the session reports. `YEAR_RUNGS` survives as the default
    for a file written before the flag existed.

    None whenever it cannot be known exactly — an era with no year, or a rung
    that does not ask. Same discipline as everything else that quotes a
    number: silence beats a guess.
    """
    if not tier:
        return None
    wants = tier.get("year_name")
    if wants is None:
        wants = tier.get("key") in YEAR_RUNGS
    if not wants:
        return None
    year = getattr(era, "year", None)
    return int(year) if year else None


def tier_cars(tier, mods=None):
    """Which installed cars are eligible for this rung: [(pretty, folder)].

    Answered from the FOLDERS ON DISK rather than from the curated alias list,
    because the question a driver is actually asking is "what do I select in
    the game" and an alias is not something he can select. An empty list is a
    real answer — he owns nothing for this rung, or nothing has scanned — and
    every caller has to treat it as "say nothing" rather than "he owns
    nothing".
    """
    mods = installed_mods() if mods is None else mods
    ui = tier.get("ui") or {}
    out = []
    for m in mods:
        hay = _norm(m)
        for alias in tier.get("mods", ()):
            if not _hit(alias, hay):
                continue
            # ONE FOLDER CAN HOLD SEVERAL SELECTABLE CARS, and the folder name
            # cannot tell you their names. `Kart_cup_2014` is the whole
            # karting mod and the rF2 UI offers "Kart Junior" and "Kart F1"
            # out of it — so the letter told the user to look for "Kart Cup
            # 2014", which is not a thing he can select, and he could not
            # find it.
            #
            # THE NAMES CANNOT BE READ OFF THE DISK. Vehicle definitions live
            # inside compressed (here, encrypted) .mas archives, which is the
            # same reason class names have never been readable. So `ui` is a
            # CURATED map from a mod alias to what the game actually shows,
            # filled in only from what the user has confirmed seeing —
            # exactly how the car lists themselves are maintained. No entry
            # means fall back to the tidied folder name, which is a guess and
            # is quoted with the folder beside it for that reason.
            names = ui.get(alias)
            if not names:
                # ...AND THE GAME CAN BE ASKED. `modnames` reads the rF2 UI's
                # own content cache, which pairs each installed folder with the
                # menu path the UI navigates to it by — "Karts, Kart Junior".
                # That is the answer this comment above says cannot be got from
                # disk, and it was right about the `.mas` archives and wrong
                # about the game: the UI is an Electron app and it writes its
                # list out as JSON.
                #
                # IT SITS BETWEEN THE TWO EXISTING SOURCES, and the order is the
                # whole point: a CURATED name is a word the user has read on his
                # own screen and beats everything; a LEARNED name is the game's
                # own string and beats a guess; the tidied folder name is the
                # guess, and it is what put "Tatuus F4 2018" in a letter about a
                # car the game calls "Tatuus_F4-T014".
                try:
                    import modnames as modnames_mod
                    names = modnames_mod.pick_names(m)
                except Exception:
                    names = None
            if names:
                out.extend((n, m) for n in names)
            else:
                out.append((pretty_mod(m), m))
            break
    # ONE NAME, ONCE. Two folders can carry the same car under the same menu
    # name — his two Corvette C6 installs do — and "Corvette C6 or Corvette C6"
    # reads as a broken letter rather than as a choice.
    seen, uniq = set(), []
    for name, folder in out:
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        uniq.append((name, folder))
    return uniq


def tier_installed(tier, mods=None):
    """Does the user own a car for this rung?

    Answers from FOLDER NAMES, which is the only thing knowable before a car
    has been driven — and deliberately not from whether he can actually race
    it, because that is not on disk (see the module docstring). A rung whose
    cars are paid DLC he does not own is removed from `ladders.json` by hand,
    which is the only honest way to know.
    """
    mods = installed_mods() if mods is None else mods
    hay = [_norm(m) for m in mods]
    for alias in tier.get("mods", ()):
        for h in hay:
            if _hit(alias, h):
                return True
    return False


class Progress(object):
    """Where a driver stands on one path.

    `reached` is the highest tier INDEX he has earned a seat in. `results` is
    the finishing position he took in each tier he has completed, keyed by
    tier key — which is what the next seat is judged on.
    """

    __slots__ = ("path", "reached", "results")

    def __init__(self, path_key, reached=0, results=None):
        self.path = path_key
        self.reached = reached
        self.results = dict(results or {})

    # -- the rules ---------------------------------------------------------
    def tier(self):
        """The rung he is on now."""
        ts = tiers(self.path)
        return ts[self.reached] if 0 <= self.reached < len(ts) else None

    def next_tier(self):
        ts = tiers(self.path)
        n = self.reached + 1
        return ts[n] if n < len(ts) else None

    def at_top(self):
        """Is he in the final championship of this path?"""
        return self.next_tier() is None

    def rungs_left(self):
        """Rungs still above him.

        THE STORY BEATS KEY OFF THIS, not off a percentage. Touring has three
        tiers and Single-Seater has five, so "90% through" is two very
        different amounts of playing — and a beat that lands three seasons
        early on one path has no shape at all.
        """
        return max(0, len(tiers(self.path)) - 1 - self.reached)

    def won_arc(self, finish_pos):
        """Does finishing `finish_pos` FINISH this path? Top rung only."""
        return bool(self.at_top() and finish_pos and finish_pos <= ARC_WIN)

    def needs(self):
        """Championship position required for the NEXT seat, or None at the top.

        Attached to the tier being ENTERED rather than the one being left,
        because that is how it reads to a driver: Formula 2 wants a top-three
        man, whoever he is and wherever he comes from.
        """
        nxt = self.next_tier()
        if nxt is None:
            return None
        # A tour has no bar at all — see `historic` in the data. Every era is
        # open, because nobody is promoted out of 1966.
        if (path(self.path) or {}).get("tour"):
            return None
        return nxt.get("needs")

    def earned(self, finish_pos):
        """Does finishing `finish_pos` in the current tier earn the next seat?

        A missed cut is not a dead end — see `season`/the inbox: he may stay
        and go again, or take a sideways move onto another path. This only
        answers the promotion question.
        """
        need = self.needs()
        if need is None:
            return False
        return bool(finish_pos) and finish_pos <= need

    def promote(self, finish_pos=None):
        """Move up a rung, recording what the season below finished at."""
        cur = self.tier()
        if cur is not None and finish_pos:
            self.results[cur["key"]] = int(finish_pos)
        if self.next_tier() is not None:
            self.reached += 1
        return self.tier()

    def unlocked(self):
        """Every tier, with whether it is open and what it would take.

        This is what the inbox's divisions view is drawn from: what he has
        access to, and what is still to earn.
        """
        out = []
        ts = tiers(self.path)
        tour = bool((path(self.path) or {}).get("tour"))
        for i, t in enumerate(ts):
            out.append({
                "key": t["key"], "name": t["name"], "index": i,
                "open": tour or i <= self.reached,
                "current": (not tour) and i == self.reached,
                "needs": None if (tour or i == 0) else t.get("needs"),
                "result": self.results.get(t["key"]),
                "installed": tier_installed(t),
            })
        return out

    # -- persistence -------------------------------------------------------
    def to_json(self):
        return {"path": self.path, "reached": self.reached,
                "results": dict(self.results)}

    @classmethod
    def from_json(cls, d):
        d = d or {}
        return cls(d.get("path") or "", int(d.get("reached") or 0),
                   d.get("results"))


def sideways(path_key, tier_index, mods=None):
    """Paths offering a comparable seat to somebody who missed his promotion.

    The consolation that is not a consolation: miss the Formula 2 seat and a
    GT3 team calls instead. It is only interesting because the paths genuinely
    cross at that level in the real world, so the offer has to be matched on
    REGISTER — a professional rung for a professional rung — rather than on
    tier number, which means nothing across paths of different lengths.

    `tier_index` is the rung he is ON, and the offer is pitched at the one he
    MISSED — which is a rung higher. A driver who just failed to make Formula
    One should be hearing from GT3 and IndyCar teams, not from Formula 4:
    matching the register he is currently in would offer him a sideways move
    that is really a demotion. This is also how it goes in the real world,
    where the Formula 2 midfield ends up in sportscars every single year.

    `mods` filters to what is installed. UNKNOWN IS NOT THE SAME AS NONE:
    passing None means "do not filter", because an empty install list is what
    a machine without rFactor 2 reports, and silently offering nothing there
    turns a career dead end into a feature that never fires. The engine passes
    the real list; everything else gets the whole set.
    """
    ts = tiers(path_key)
    if not (0 <= tier_index < len(ts)):
        return []
    missed = ts[tier_index + 1] if tier_index + 1 < len(ts) else ts[tier_index]
    reg = missed.get("register")
    out = []
    for pkey, p in paths().items():
        if pkey == path_key or p.get("tour"):
            continue
        for i, t in enumerate(p.get("tiers", ())):
            if t.get("register") != reg:
                continue
            if mods is not None and not tier_installed(t, mods):
                continue
            out.append((pkey, i, t["name"]))
            break
    return out


def validate():
    """Every rule this data has to obey, checked rather than assumed."""
    errs = []
    for pkey, p in paths().items():
        ts = p.get("tiers") or []
        if not ts:
            errs.append("%s: no tiers" % pkey)
            continue
        if not p.get("tour") and ts[0].get("needs") is not None:
            errs.append("%s: entry tier must need nothing" % pkey)
        prev = None
        for t in ts:
            for field in ("key", "name", "register"):
                if not t.get(field):
                    errs.append("%s/%s: missing %s" % (pkey, t.get("key"), field))
            if not t.get("mods") and not t.get("classes"):
                errs.append("%s/%s: no way to match a car"
                            % (pkey, t.get("key")))
            n = t.get("needs")
            if n is not None:
                if not 1 <= n <= 30:
                    errs.append("%s/%s: implausible needs %r"
                                % (pkey, t.get("key"), n))
                # THE BAR RISES. A rung that is easier to reach than the one
                # below it is a typo, and it would let a driver skip the
                # hardest part of his own career by accident.
                if prev is not None and n > prev:
                    errs.append("%s/%s: needs %d is easier than the rung below (%d)"
                                % (pkey, t.get("key"), n, prev))
                prev = n
    keys = [t["key"] for p in paths().values() for t in p.get("tiers", ())]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    if dupes:
        errs.append("tier keys are not unique: %s" % ", ".join(dupes))
    return errs


if __name__ == "__main__":
    bad = validate()
    for p_key, p in paths().items():
        print("\n%s — %s" % (p["name"].upper(), p["sub"]))
        for t in p["tiers"]:
            need = t.get("needs")
            print("   %-18s %-14s %s" % (
                t["name"], t["register"],
                "entry" if need is None else "needs P%d below" % need))
    print("\n%d paths, %d tiers" % (
        len(paths()), sum(len(p["tiers"]) for p in paths().values())))
    print("validate: %s" % ("OK" if not bad else "\n  " + "\n  ".join(bad)))
