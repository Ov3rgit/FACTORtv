# -*- coding: utf-8 -*-
"""
FACTORtv — career history.

What this gives the booth
-------------------------
Everything else in this product describes the race that is happening. This
describes the ones that already did, which is the difference between

    "P3 for Kandasamy."
    "Third for Kandasamy — his best finish at Montreal, and his third podium
     in five visits."

The booth cannot say the second sentence from shared memory. It needs a
memory of its own.

Where the data comes from
-------------------------
rFactor 2 writes a full result XML for every session to

    <game>\\UserData\\Log\\Results\\YYYY_MM_DD_HH_MM_SS-nnRn.xml

and it contains more than we need: venue, the real event name ("Canadian
Grand Prix"), car class, and every driver with grid slot, finishing position,
laps, best lap and a DNF flag. So the career is not something the user
maintains — it is something already on disk that nobody was reading. On this
machine there were 293 result files sitting there before a line of this
module existed, so a career starts populated rather than empty — though only
a small fraction of them are races anybody finished. See THE LAW.

THE LAW: ONLY A COMPLETED RACE COUNTS
-------------------------------------
rF2 writes a result file whether you took the chequered flag or quit on lap
two, and they are indistinguishable in every field except the lap count. That
matters more than it sounds: a career that records abandoned attempts is
worse than no career at all, because the booth then says "his worst result
here was nineteenth" about a race the user restarted and never ran.

So a result is only recorded when the player covered at least `MIN_SHARE` of
the winner's distance. Restarts, test runs and races quit in disgust leave no
trace. A genuine retirement at three-quarter distance IS recorded — that is a
real result and the booth should know about it — and is marked `dnf` so it is
never described as a finish.

...AND THAT TEST ALONE IS NOT ENOUGH, WHICH TOOK A LIVE RUN TO SEE.
`MIN_SHARE` is RELATIVE: it compares the player against the winner, so it
catches "you quit while the others finished" and is completely blind to
"EVERYBODY stopped after one lap". When a race is restarted the whole field
abandons together, so every driver's share of the winner's distance is 100%
and the test passes trivially. The user's own store held **three wins at
Albert Park from one-lap races** — he restarted a fifteen-lap race four times,
was nominally leading after the first lap each time, and the career recorded
each of those as a victory. The booth then told him he was "a winner at Albert
Park already" in a season where the man he was driving as had never won a
Grand Prix at all.

So there is a second, ABSOLUTE test, and the user set its bar himself: "I
restart a lot because of crashing, so a race result should only be captured
when FINISHED." `FinishStatus` reads "Finished Normally" for anyone who took
the chequered flag and is empty for every driver in an abandoned session — so
if nobody finished, nothing is recorded, however many laps had been run.

That is stricter than any lap threshold and it is the right rule for this
user: a crash-out and a race run to the flag produce files identical in shape,
and the only thing separating them is whether anybody was still there at the
end. It also handles the honest retirement correctly — retire and WAIT, the AI
take the flag, the file has finishers, and the DNF is kept as the real result
it is. Quit immediately and it is as if the race never happened, which is what
he wants.

`RUN_SHARE` / `RUN_MIN_LAPS` survive only as a fallback for a file with no
status data at all. That does not occur in any of the 293 files on this
machine, but silently discarding every race on an older mod would be a worse
failure than the one being guarded against.

The numbers here are why this matters: of 68 files that passed the relative
test, **55 had run under a QUARTER of their scheduled distance** and only TWO
ever reached the flag. The store held 68 races and five wins; the honest
figure is two races and one win.

The same law applies to the live path when it is built: record at the
chequered flag, never at any earlier point.

Points are NOT taken from rF2
-----------------------------
The XML has a `Points` field and it looks authoritative. It is not: rF2 only
populates it for sessions launched inside one of its own championships, and
89 of the 132 races on this machine award zero to every driver. The table
also varies by mod — 8/5/3/2/1 for GT500, 20/14/10/8 for the F1 mods. So
championship points are computed from finishing position against a table the
career owns, and this field is ignored.
"""
import glob
import json
import re
import os
import sys
import threading
import xml.etree.ElementTree as ET

import era as era_mod
import track as track_mod

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
CAREER_PATH = os.path.join(_DIR, "_career.json")

# Fraction of the winner's distance the player must have covered for the race
# to have happened at all. Half is deliberately generous: the failure being
# guarded against is the lap-two restart, not the honest retirement.
MIN_SHARE = 0.5

# ...and the ABSOLUTE half of THE LAW: how much of the race's OWN SCHEDULED
# distance has to have been run before the thing counts as a race at all.
#
# Half. A race abandoned at 26% of its distance is a restart whatever the
# classification says, and a driver leading it has not won anything. The
# generous direction is deliberate on the other side too: a genuine race that
# ran 60% of its laps before the user retired is real, and is recorded as a
# DNF exactly as it always was.
RUN_SHARE = 0.5

# For a TIMED race `RaceLaps` is 0 — there is no scheduled lap count to be a
# share of — so the absolute test falls back to a floor in laps. Three is the
# same figure `_enough_race` uses in the booth for "has enough happened to
# talk about", and for the same reason.
RUN_MIN_LAPS = 3

# How many recent results to keep in full. The aggregates are what the booth
# actually reads; this is for "his last three races" style lines and for
# rebuilding aggregates if their shape ever changes.
RECENT_KEEP = 60

# Share of a grid a class must have covered at least once to count as a
# championship class rather than a team label. See `History.classes`.
CLASS_SHARE = 0.4

# Classes never offered as a championship, whatever the history says.
#
# Curated by the user, not inferred: these are real classes with real results
# behind them, so no share or race-count rule would drop them. "F1 Test 2025"
# is rF2's own shipped test content rather than a season anybody races, and
# the other two are one-off mods. Matched case-insensitively.
HIDE_CLASSES = {
    "f1 test 2025",
    "formula 1 1992 season by asrc",
    "fsr 2026",
}

# How many names to remember per class. Enough to cover a full grid and its
# reserves; more than that is a menu nobody can page through.
ROSTER_KEEP = 60

# Smallest grid a session must have before the class it ran is offered as a
# championship. A car taken out alone makes a one-entry class covering 100% of
# its own field, which passes every share test there is — and a season against
# nobody is not a season. Three matches `_fold_field`'s own floor.
CONTEXT_MIN_FIELD = 3

# Bumped to 5 when team-named grids started being recorded as a FIELD as well
# as as individual team "classes". An old file has neither `field_classes` on
# its results nor the grouped entry, and a rescan is a couple of seconds on a
# background thread rather than a migration nobody can test.
# Bumped to 7 on 2026-08-17: `_fold_field` was building the driver roster for
# a team-named championship out of `classified`, which is scoped to the
# player's own class — two McLarens rather than the twenty-car grid. Existing
# `_career.json` files hold that truncated roster, and `load()` discards a
# file whose version does not match, so raising this is what rebuilds them.
# Bumped to 8 on 2026-08-17 when THE LAW gained its absolute half (a race must
# have been FINISHED by somebody), which invalidates every aggregate built
# under the old test — the user's store held 68 races and five wins against a
# true figure of two and one.
# Bumped to 9 the same day: car classes are now learned from files THE LAW
# rejects as well (see `_fold_context`), because tightening the law had taken
# the whole New Career menu down to two entries.
VERSION = 9


def find_results_dir(cfg=None):
    """Locate rF2's results folder.

    Explicit setting first, then Steam's own registry entry and library list,
    then the obvious guesses. Returns None rather than raising: a machine
    without rFactor 2 installed is a perfectly normal place to run the tests.
    """
    if cfg:
        p = cfg.get("results_dir")
        if p and os.path.isdir(p):
            return p
    tail = os.path.join("steamapps", "common", "rFactor 2",
                        "UserData", "Log", "Results")
    roots = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE,
                           r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    val = winreg.QueryValueEx(
                        k, "SteamPath" if hive == winreg.HKEY_CURRENT_USER
                        else "InstallPath")[0]
                    if val:
                        roots.append(val)
            except OSError:
                pass
    except Exception:
        pass
    # Steam keeps additional install drives in libraryfolders.vdf. Parsed by
    # hand because the format is trivial and pulling in a VDF library for four
    # lines of quoted paths would be absurd.
    for r in list(roots):
        vdf = os.path.join(r, "steamapps", "libraryfolders.vdf")
        try:
            with open(vdf, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if '"path"' in line:
                        parts = line.split('"')
                        if len(parts) >= 4:
                            roots.append(parts[3].replace("\\\\", "\\"))
        except Exception:
            pass
    roots += ["%s:\\SteamLibrary" % d for d in "CDEFGH"]
    roots += ["%s:\\Program Files (x86)\\Steam" % d for d in "CD"]
    for r in roots:
        p = os.path.join(r, tail)
        if os.path.isdir(p):
            return p
    return None


# Words that mean a VehName is describing a CAR or a TEAM rather than a
# person. Deliberately short: this only has to reject the shapes rF2 mods
# actually produce, and a false reject merely leaves a name out of a menu.
_NOT_A_NAME = {
    "team", "racing", "motorsport", "motorsports", "gt", "gte", "gt3", "gt4",
    "lmp", "cup", "sport", "sports", "engineering", "autosport", "f1",
    "formula", "usf", "stw", "nascar", "edition", "series", "works",
}


def _veh_driver(vehname, team="", cartype=""):
    """The DRIVER's name out of rF2's VehName, or "" when there isn't one.

    This exists for one reason: the car the player is driving is the one
    driver who never appears in the opponent list. Race as Mansell in the
    1988 mod and Mansell is missing from every result — he is you. But the
    car itself is named after him:

        VehName = "Williams  05-Nigel Mansell"

    Mods use the field for wildly different things, though —

        "#230 Masatomo Shimizu"   a person
        "63 Gary Madew"           a person
        "Lotus-Ford #12"          a car
        "Honda HSV-010 GT #002"   a car
        "21GT4FRA| #110 Team CMR" a team
        "Orange"                  a livery

    — so anything that does not look like a person is rejected. Being wrong
    here only puts a bad entry in a menu, but a menu of car models would make
    the feature useless, so the test is deliberately strict: at least two
    words, alphabetic, capitalised, no car or team vocabulary, and not simply
    a restatement of the team or car type.
    """
    v = (vehname or "").strip()
    if not v:
        return ""
    # "Williams  05-Nigel Mansell" -> the part after the car number.
    m = re.search(r"\d+\s*-\s*(.+)$", v)
    if m:
        v = m.group(1)
    v = re.sub(r"[#|]", " ", v)
    words = [w for w in v.split() if not w.isdigit()]
    if len(words) < 2:
        return ""
    for w in words:
        if any(ch.isdigit() for ch in w):
            return ""
        if w.lower().strip(".,") in _NOT_A_NAME:
            return ""
        if not w[:1].isupper() or not w.replace("-", "").replace("'", "").isalpha():
            return ""
    name = " ".join(words)
    low = name.lower()
    if low and (low in (team or "").lower() or low in (cartype or "").lower()):
        return ""
    return name


def _text(node, tag, default=""):
    if node is None:
        return default
    v = node.findtext(tag)
    return default if v is None else v.strip()


def _int(node, tag, default=0):
    try:
        return int(float(_text(node, tag) or default))
    except (TypeError, ValueError):
        return default


def parse_result(path):
    """One race result file -> a dict, or None if it is not a usable race.

    Returns None for practice-only weekends, empty classifications, and — the
    important one — races the player did not actually complete. See THE LAW
    in the module docstring.
    """
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return None
    rr = root.find("RaceResults")
    if rr is None:
        return None
    race = rr.find("Race")
    if race is None:
        return None
    drivers = race.findall("Driver")
    if not drivers:
        return None

    rows = []
    player = None
    for d in drivers:
        row = {
            "name": _text(d, "Name"),
            "pos": _int(d, "Position"),
            "grid": _int(d, "GridPos"),
            "laps": _int(d, "Laps"),
            "cls": _text(d, "CarClass"),
            "car": _text(d, "CarType"),
            "best": _float(d, "BestLapTime"),
            "dnf": _text(d, "FinishStatus").upper() == "DNF",
            # Kept raw as well: "Finished Normally" is how the file records
            # that the chequered flag actually fell, which is the only
            # unambiguous evidence that this session was a race rather than
            # an abandoned attempt. See THE LAW below.
            "status": _text(d, "FinishStatus"),
            # Class position matters in multiclass, where outright position is
            # not the result anybody quotes.
            "cls_pos": _int(d, "ClassPosition") or _int(d, "Position"),
            "veh": _text(d, "VehName"),
            "team": _text(d, "TeamName"),
        }
        rows.append(row)
        if _text(d, "isPlayer") == "1":
            player = row
    if player is None or not player["pos"]:
        return None

    # THE LAW. The winner's lap count is the race distance actually run, which
    # is more reliable than RaceLaps — a timed race has no lap target, and a
    # race cut short still has a winner who did the full distance of it.
    won_laps = max((r["laps"] for r in rows), default=0)
    if won_laps <= 0 or player["laps"] < won_laps * MIN_SHARE:
        return None

    # THE ABSOLUTE HALF OF THE LAW: DID THIS RACE ACTUALLY HAPPEN?
    #
    # The relative test above compares the player with the winner, so a
    # restart — where the WHOLE FIELD stops at the same moment — passes it
    # trivially at 100%. That is where three phantom Albert Park wins came
    # from: a fifteen-lap race abandoned after ONE lap, with the player
    # nominally leading.
    #
    # Two signals, and they answer different questions.
    #
    # 1. DID THE FLAG FALL? `FinishStatus` reads "Finished Normally" for a
    #    driver who took the chequered flag and is empty for everyone in an
    #    abandoned session. When somebody finished, this was a race, whatever
    #    its length — which is the case a lap-count rule gets wrong for a
    #    genuinely shortened race.
    finished_seen = any("finished" in (r["status"] or "").lower()
                        for r in rows)
    have_status = any((r["status"] or "").strip() for r in rows)
    if have_status:
        # THE USER'S OWN RULE, and he is the authority on his own habits: "I
        # restart a lot because of crashing, so a race result should only be
        # captured when finished."
        #
        # That is stricter than any lap-count threshold and it is the right
        # call. A game that crashes out mid-race leaves a file identical in
        # shape to a race run to the flag; the only thing that separates them
        # is whether anybody was still there at the end. Nobody finished =
        # nothing happened, however many laps had been run.
        #
        # Note this also drops a retirement the user did not sit through —
        # correctly. If he retires and WAITS, the AI take the flag, the file
        # records finishers and his DNF is kept as the real result it is.
        if not finished_seen:
            return None
    else:
        # NO STATUS DATA AT ALL. Not seen in any of the 293 files on this
        # machine, but an older mod or plugin build could omit the field, and
        # silently discarding every race would be a worse failure than the one
        # being guarded against. Fall back to the distance test.
        sched = _int(rr, "RaceLaps")
        if sched > 0:
            if won_laps < sched * RUN_SHARE:
                return None
        elif won_laps < RUN_MIN_LAPS:
            # Timed race: no scheduled lap count to be a share of, so a floor.
            return None

    venue = _text(rr, "TrackVenue")
    circuit = track_mod.Track(venue)
    field = [r for r in rows if r["cls"] == player["cls"]] or rows
    return {
        "file": os.path.basename(path),
        "when": _int(rr, "DateTime"),
        "date": _text(rr, "TimeString"),
        "venue": venue,
        "slug": circuit.slug if circuit.known else "",
        "circuit": circuit.name if circuit.known else venue,
        # rF2's own event name is a gift: "Canadian Grand Prix" is exactly
        # what a commentator would call it, and no other source has it.
        "event": _text(rr, "TrackEvent"),
        "cls": player["cls"],
        # The player's RAW rF2 name, so it can be kept out of the opponent
        # roster. It is usually the profile placeholder "Your Name", which
        # was appearing in the driver picker as though it were a real driver.
        "me_raw": player["name"],
        # ...and the driver the player's CAR is named after, which is the one
        # name a result file can never supply as an opponent.
        "veh_driver": _veh_driver(player.get("veh"), player.get("team"),
                                  player.get("car")),
        # What SHARE of the grid was in the player's class. Some mods name a
        # class per TEAM — 20 cars across 10 "classes" — and for those a
        # class is not a championship at all. The share is the only reliable
        # way to tell the two apart, and it is recorded per result so the
        # judgement can be made from history rather than guessed at.
        "cls_share": (float(len(field)) / len(rows)) if rows else 0.0,
        # EVERY class in the race, not just the player's. For a mod that
        # names a class per TEAM this is the only thing that identifies what
        # the race actually WAS — ten "classes" called McLaren, Ferrari,
        # Haas... are one Formula One grid, and the set of them dates it.
        "field_classes": sorted({r["cls"] for r in rows if r.get("cls")}),
        # WHO DRIVES FOR WHOM. `TeamName` has been parsed onto every row
        # since this function was written and read by nothing at all — and it
        # is the only route to a team-mate in a championship whose CarClass
        # is the SERIES rather than the constructor, which is every division
        # except the two Formula One mods.
        "teams": dict((r["name"], r["team"]) for r in rows
                      if r.get("name") and r.get("team")),
        "pos": player["cls_pos"],
        "grid": player["grid"],
        "laps": player["laps"],
        "race_laps": won_laps,
        "dnf": player["dnf"],
        "best": player["best"],
        "field": len(field),
        "winner": next((r["name"] for r in field if r["cls_pos"] == 1), ""),
        "classified": [(r["name"], r["cls_pos"]) for r in
                       sorted(field, key=lambda r: r["cls_pos"] or 99)],
        # EVERY DRIVER IN THE RACE, not only the player's class.
        #
        # `classified` is deliberately class-scoped — a GT3 championship is
        # not decided by the GTE cars sharing the circuit. But a TEAM-NAMED
        # field is one championship of twenty cars wearing ten class labels,
        # and `_fold_field` needs all twenty. Reading `classified` there gave
        # it the player's two team-mates and nothing else, which is why the
        # driver picker for "Formula One 2021" offered exactly two names.
        "grid_all": [(r["name"], r["pos"]) for r in
                     sorted(rows, key=lambda r: r["pos"] or 99)],
    }


def _float(node, tag, default=None):
    try:
        return float(_text(node, tag))
    except (TypeError, ValueError):
        return default


class History(object):
    """Everything the booth is allowed to claim about the past.

    Aggregates are kept per circuit AND per circuit-and-class, because "he won
    here" means something different in a 1992 Williams and a 2025 McLaren.
    The booth prefers the class-specific record and falls back to the generic
    one with generic wording.
    """

    def __init__(self, path=CAREER_PATH):
        self.path = path
        self.data = {"version": VERSION, "seen": {}, "races": 0, "wins": 0,
                     "podiums": 0, "dnfs": 0, "tracks": {}, "recent": [],
                     "classes": {}}
        self.ready = False
        self._lock = threading.Lock()
        self.load()

    # -- persistence -------------------------------------------------------
    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("version") == VERSION:
                self.data = d
        except Exception:
            pass

    def save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=1)
            os.replace(tmp, self.path)
        except Exception:
            pass

    # -- building ----------------------------------------------------------
    def scan_async(self, results_dir):
        """Scan on a daemon thread. The overlay must be usable immediately,
        and 150 XML files is a second or two of parsing on a cold cache."""
        threading.Thread(target=self.scan, args=(results_dir,),
                         daemon=True).start()

    def scan(self, results_dir):
        """Fold every unseen result into the aggregates. Incremental: files
        already counted are skipped by name, so this is cheap on every run
        after the first."""
        if not results_dir or not os.path.isdir(results_dir):
            self.ready = True
            return 0
        added = 0
        seen = self.data.setdefault("seen", {})
        for path in sorted(glob.glob(os.path.join(results_dir, "*.xml"))):
            name = os.path.basename(path)
            if name in seen:
                continue
            res = parse_result(path)
            # Unusable files are remembered too, or every startup re-parses
            # every practice session ever run.
            seen[name] = 1 if res else 0
            if res:
                self._fold(res)
                added += 1
            else:
                # CONTEXT IS FREE; RECORDING IS CONFIRMED (LAW 3).
                #
                # A file THE LAW rejects is not a result, but it is still
                # evidence that the user owns these cars and has driven them.
                # Which car classes to OFFER as a championship is a menu
                # question: getting it wrong costs a line in a list, while
                # getting a WIN wrong costs the broadcast its credibility.
                # Those two things must not share a gate.
                #
                # This is not hypothetical. Tightening THE LAW to "somebody
                # must have finished" cut the store from 68 races to 2, and
                # because the class list was built only from folded RESULTS it
                # took the whole New Career menu with it — the user was left
                # with two selectable classes out of eighty-two installed car
                # mods, and asked where they had gone.
                self._fold_context(path)
        with self._lock:
            self.data["recent"] = sorted(
                self.data["recent"], key=lambda r: r.get("when", 0)
            )[-RECENT_KEEP:]
        self.ready = True
        if added:
            self.save()
        return added

    def team_of(self, name, cls):
        """Which team a driver was last seen driving for in this class.

        THE LIVE SESSION CANNOT SEE THIS. rF2's scoring gives a CarClass and
        nothing else, and for every championship except the two Formula One
        mods the class is the SERIES — all thirteen Formula 2 cars report
        "Formula 2 2019". The entrant is only ever in the result file, so the
        pairings are learned from history and applied live.

        LAST SEEN, deliberately: a driver who changes team should be reported
        at his new one, and the most recent file is the one that knows.

        Returns "" when nothing has been learned, which is the honest answer
        for a grid that has never been raced or recorded.
        """
        if not name or not cls:
            return ""
        cl = (self.data.get("classes") or {}).get(cls) or {}
        teams = cl.get("teams") or {}
        if name in teams:
            return teams[name]
        # Folded, because the live display name and the result file's spelling
        # differ for exactly the reasons `drivers._is` exists: accents, Jr.,
        # and mods that write a name two ways.
        # `drivers._fold` is the ONE name-folder in this product, and using
        # it here rather than writing a second one is the whole point: two
        # folders eventually disagree, and then the booth and the store
        # disagree about who somebody is.
        import drivers as _drv
        want = _drv._fold(name)
        for k, v in teams.items():
            if _drv._fold(k) == want:
                return v
        return ""

    def team_for_entry(self, vehicle, cls):
        """Which team the LOADED CAR belongs to, or "" if it cannot be known.

        The live session names the entry after its driver — `2019 - #06 Nicholas
        Latifi` — and says nothing about the entrant. `team_of` knows the pairing
        from the result files, so the two together turn "which car is he in" into
        "whose car is he in", which is the question the junior arc rests on.

        "" IS A REAL ANSWER and every caller has to treat it as "cannot tell"
        rather than as "wrong team". A grid nobody has raced yet has no pairings
        at all, and a career that silently stops counting is the worst failure
        this store has.
        """
        if not vehicle or not cls:
            return ""
        drv = _veh_driver(vehicle, cartype=cls)
        return self.team_of(drv, cls) if drv else ""

    def team_mates(self, cls):
        """{driver: team} for this class, or {} if nothing is known."""
        cl = (self.data.get("classes") or {}).get(cls) or {}
        return dict(cl.get("teams") or {})

    def _fold_context(self, path):
        """Learn WHICH CARS the user owns from a file that is not a result.

        Records the class, its share of the grid and the driver roster —
        everything the New Career menu needs — and touches no total, no win,
        no podium and no circuit record. A restart, a practice session and a
        qualifying run all say the same true thing: this grid exists on this
        machine and the user has driven it.

        QUALIFYING COUNTS HERE, and that matters: the user's own report was
        that he had "only ever done a quali session" in a car. That is still
        a car he owns and a grid he can race, so it belongs in the menu even
        though there is no result anywhere on disk.
        """
        try:
            root = ET.parse(path).getroot()
        except Exception:
            return
        rr = root.find("RaceResults")
        if rr is None:
            return
        # Any session section will do — Race, Qualify, Practice1, Warmup.
        drivers, me_cls = [], ""
        for sec in list(rr):
            ds = sec.findall("Driver")
            if not ds:
                continue
            for d in ds:
                nm, cl = _text(d, "Name"), _text(d, "CarClass")
                drivers.append((nm, cl, _text(d, "isPlayer") == "1",
                                _text(d, "VehName"), _text(d, "TeamName")))
                if _text(d, "isPlayer") == "1":
                    me_cls = cl
            break
        if not drivers or not me_cls:
            return
        # A SOLO SESSION IS NOT A CHAMPIONSHIP. Going out alone in a car makes
        # a one-entry "class" that covers 100% of its own field and sails past
        # the share filter — the first pass offered "Mazda 787B" and
        # "National" as seasons to race, each with a grid of nobody. A
        # championship needs opponents, and `_fold_field` already uses three
        # as the floor for the same reason.
        if len(drivers) < CONTEXT_MIN_FIELD:
            return
        field = len(drivers)
        same = [d for d in drivers if d[1] == me_cls]
        share = (len(same) / float(field)) if field else 0.0
        when = _int(rr, "DateTime")
        with self._lock:
            d = self.data
            cl = d.setdefault("classes", {}).setdefault(
                me_cls, {"races": 0, "share": 0.0, "last": 0})
            # `races` deliberately NOT incremented: nothing was raced. The
            # entry exists so the class can be chosen, and the menu's race
            # count stays honest at zero until one is actually finished.
            cl["share"] = max(cl.get("share", 0.0), share)
            cl["last"] = max(cl.get("last", 0), when)
            roster = set(cl.get("drivers") or [])
            for nm, cls_, is_me, veh, team in drivers:
                if cls_ != me_cls or is_me or not nm:
                    continue
                roster.add(nm)
            roster.discard("")
            cl["drivers"] = sorted(roster)[:ROSTER_KEEP]
            # WHO DRIVES FOR WHOM — the one thing the live session cannot see.
            #
            # `TeamName` is in every result file and has been parsed all
            # along, and nothing has ever used it. It is the ONLY route to a
            # team-mate in a championship whose CarClass is the series rather
            # than the constructor, which is every division except the two
            # Formula One mods: in Formula 2 all thirteen cars report
            # "Formula 2 2019" and the entrant exists only here.
            #
            # LEARNED FROM ANY SESSION, including a qualifying run, for the
            # same reason the roster is: it says something true about a grid
            # that exists on this machine, and it costs nothing to be wrong
            # about — a stale pairing means one silent line, never a false
            # claim about a result.
            #
            # NOT A VERSION BUMP. `load()` DISCARDS a career whose version
            # does not match, so bumping would delete the user's store to add
            # a field that is read through `.get` and whose absence simply
            # means "we have not learned this yet".
            teams = dict(cl.get("teams") or {})
            for nm, cls_, is_me, _veh, team in drivers:
                if cls_ == me_cls and nm and team:
                    teams[nm] = team
            if teams:
                cl["teams"] = teams
            # A TEAM-NAMED GRID is one championship here too, by exactly the
            # same test the result path uses — otherwise a 2021 field learned
            # from a restart offers ten teams and no season.
            if share < CLASS_SHARE:
                classes = sorted({c for _n, c, _m, _v, _t in drivers if c})
                if era_mod.team_field(classes) is not None:
                    self._fold_field(d, {
                        "cls": me_cls, "when": when,
                        "field_classes": classes,
                        "cls_share": share,
                        "me_raw": next((n for n, _c, m, _v, _t in drivers if m), ""),
                        "me": "",
                        "classified": [],
                        "grid_all": [(n, i + 1) for i, (n, _c, m, _v, _t)
                                     in enumerate(drivers) if not m],
                        "veh_driver": "",
                    }, counted=False)

    def _fold(self, res):
        """Add one result to the running totals."""
        with self._lock:
            d = self.data
            d["races"] = d.get("races", 0) + 1
            if res["dnf"]:
                d["dnfs"] = d.get("dnfs", 0) + 1
            elif res["pos"] == 1:
                d["wins"] = d.get("wins", 0) + 1
            if not res["dnf"] and res["pos"] <= 3:
                d["podiums"] = d.get("podiums", 0) + 1
            if res["slug"]:
                for key in (res["slug"], "%s|%s" % (res["slug"], res["cls"])):
                    self._fold_track(d["tracks"].setdefault(key, {}), res)
            # A TEAM-NAMED FIELD IS ONE CHAMPIONSHIP, NOT TEN.
            #
            # When the player's class covers only a sliver of the grid, the
            # mod is naming a class per team and no single one of them is a
            # championship — the live 2021 run offered the user nothing to
            # pick, so the career never locked to anything and never matched
            # a round. The whole grid is recorded as its own entry instead,
            # labelled by era, which is also the name the user wants to see:
            # "Formula One 2021", not "Haas".
            self._fold_field(d, res)
            cl = d.setdefault("classes", {}).setdefault(
                res["cls"], {"races": 0, "share": 0.0, "last": 0})
            cl["races"] += 1
            cl["share"] = max(cl["share"], res.get("cls_share", 0.0))
            cl["last"] = max(cl.get("last", 0), res["when"])
            # The roster this class races against. It is the only source of
            # real driver names the product has, and it is what lets a career
            # be run under a name from the grid — "I want to be Mansell" —
            # without the overlay ever needing a text box.
            roster = set(cl.get("drivers") or [])
            skip = {res.get("me_raw") or "", res.get("me") or ""}
            roster.update(n for n, _p in res.get("classified", ())
                          if n and n not in skip)
            if res.get("veh_driver"):
                roster.add(res["veh_driver"])
            roster.discard("")
            cl["drivers"] = sorted(roster)[:ROSTER_KEEP]
            # WHO DRIVES FOR WHOM — the one thing the live session cannot see.
            #
            # `TeamName` is in every result file and has been parsed all
            # along, and nothing has ever used it. It is the ONLY route to a
            # team-mate in a championship whose CarClass is the series rather
            # than the constructor, which is every division except the two
            # Formula One mods: in Formula 2 all thirteen cars report
            # "Formula 2 2019" and the entrant exists only here.
            #
            # LEARNED FROM ANY SESSION, including a qualifying run, for the
            # same reason the roster is: it says something true about a grid
            # that exists on this machine, and it costs nothing to be wrong
            # about — a stale pairing means one silent line, never a false
            # claim about a result.
            #
            # NOT A VERSION BUMP. `load()` DISCARDS a career whose version
            # does not match, so bumping would delete the user's store to add
            # a field that is read through `.get` and whose absence simply
            # means "we have not learned this yet".
            # In the RESULT path the rows come from `parse_result`, which
            # carries the team on each one — so the same pairings are learned
            # here, from the file that actually recorded a race.
            teams = dict(cl.get("teams") or {})
            teams.update(res.get("teams") or {})
            if teams:
                cl["teams"] = teams
            d["recent"].append({
                "when": res["when"], "slug": res["slug"], "cls": res["cls"],
                "pos": res["pos"], "grid": res["grid"], "field": res["field"],
                "dnf": res["dnf"], "event": res["event"],
                "winner": res["winner"],
            })

    @staticmethod
    def _fold_track(t, res):
        t["visits"] = t.get("visits", 0) + 1
        t["event"] = res["event"] or t.get("event", "")
        if res["dnf"]:
            t["dnfs"] = t.get("dnfs", 0) + 1
        else:
            if res["pos"] == 1:
                t["wins"] = t.get("wins", 0) + 1
            if res["pos"] <= 3:
                t["podiums"] = t.get("podiums", 0) + 1
            b = t.get("best")
            if b is None or res["pos"] < b:
                t["best"] = res["pos"]
        # "Last time out" is the most-quoted fact in this whole module, so it
        # is stored explicitly rather than derived from `recent` — which is
        # capped and may not reach back far enough.
        if res["when"] >= t.get("last_when", 0):
            t["last_when"] = res["when"]
            t["last"] = res["pos"]
            t["last_dnf"] = res["dnf"]

    # -- reading -----------------------------------------------------------
    def at(self, slug, cls=None):
        """The record at this circuit. Class-specific if we have one, else
        the circuit overall, tagged so the caller knows which it got."""
        if not slug:
            return None
        t = self.data.get("tracks", {})
        if cls:
            rec = t.get("%s|%s" % (slug, cls))
            if rec and rec.get("visits"):
                r = dict(rec)
                r["same_class"] = True
                return r
        rec = t.get(slug)
        if rec and rec.get("visits"):
            r = dict(rec)
            r["same_class"] = False
            return r
        return None

    def _fold_field(self, d, res, counted=True):
        """Record the WHOLE GRID as a pickable championship, when the class
        list is really a team list.

        Only for fields the class share says are team-named. A genuine
        multi-class race (GT3 and GTE together at Spa) is left alone: those
        classes ARE separate championships and merging them would be wrong.
        """
        members = res.get("field_classes") or []
        if res.get("cls_share", 1.0) >= CLASS_SHARE or len(members) < 3:
            return
        # A GENUINE MULTI-CLASS RACE IS NOT A TEAM-NAMED FIELD, and the share
        # test alone cannot tell them apart: both look like several small
        # classes. Requiring the classes to be recognisable CONSTRUCTORS is
        # what separates them. Without this, a grid of "Alpine A110 GT4, BMW
        # 320i STW, GT500, VOLVO S40 ST" was merged into a single invented
        # championship called "SUPER GT500 2013".
        if era_mod.team_field(members) is None:
            return
        e = era_mod.classify(res.get("cls") or "", res.get("veh_driver") or "",
                             members)
        label = e.label or "field"
        if e.year and str(e.year) not in label:
            label = "%s %d" % (label, e.year)
        grp = d.setdefault("classes", {}).setdefault(
            label, {"races": 0, "share": 1.0, "last": 0, "members": []})
        # `counted=False` is the context path: the grid is learned so it can
        # be PICKED, but nothing was raced, so the race count stays honest.
        if counted:
            grp["races"] += 1
        # A field entry covers the field by definition, which is what lets it
        # past the share filter that (correctly) rejects each team.
        grp["share"] = 1.0
        grp["last"] = max(grp.get("last", 0), res["when"])
        grp["members"] = sorted(set(grp.get("members") or []) | set(members))
        # THE WHOLE GRID, because that is what this entry IS. `classified` is
        # scoped to the player's class, which for a team-named field is his
        # two-car team — so this used to record a "Formula One 2021"
        # championship whose driver roster was the two McLarens.
        roster = set(grp.get("drivers") or [])
        skip = {res.get("me_raw") or "", res.get("me") or ""}
        roster.update(n for n, _p in (res.get("grid_all")
                                      or res.get("classified") or ())
                      if n and n not in skip)
        if res.get("veh_driver"):
            roster.add(res["veh_driver"])
        roster.discard("")
        grp["drivers"] = sorted(roster)[:ROSTER_KEEP]

    def classes(self, min_share=CLASS_SHARE):
        """Car classes worth offering as a CHAMPIONSHIP, most recent first.

        Filtered by how much of a grid the class has ever covered. A mod that
        labels every team as its own class produces twenty cars in ten
        "classes", and locking a season to one of those locks it to a team —
        the standings would then be computed from two drivers. A real class
        covers most of the field it appears in at least once.
        """
        out = []
        for name, c in (self.data.get("classes") or {}).items():
            if not name or c.get("share", 0.0) < min_share:
                continue
            if name.strip().lower() in HIDE_CLASSES:
                continue
            out.append({"name": name, "races": c.get("races", 0),
                        "share": c.get("share", 0.0),
                        "last": c.get("last", 0),
                        # The team classes this entry stands for, when it is
                        # a whole field rather than a single class. Empty for
                        # an ordinary class, and the career stores it so a
                        # race can be matched against any member.
                        "members": list(c.get("members") or [])})
        return sorted(out, key=lambda c: -c["last"])

    def drivers(self, cls=None):
        """Driver names seen racing in this class, alphabetically.

        Sourced from rF2's own result files, so they are the real names of
        the real grid — which is what makes "race as Nigel Mansell" possible
        without the overlay ever having to accept typed input.
        """
        classes = self.data.get("classes") or {}
        if cls:
            return list((classes.get(cls) or {}).get("drivers") or [])
        out = set()
        for c in classes.values():
            out.update(c.get("drivers") or [])
        return sorted(out)

    def form(self, n=3, cls=None):
        """The last `n` results, most recent first. The basis of "third
        podium in a row" and "he hasn't finished since Spa"."""
        rows = [r for r in reversed(self.data.get("recent", []))
                if not cls or r.get("cls") == cls]
        return rows[:n]

    @property
    def races(self):
        return self.data.get("races", 0)


def summary(history):
    """One line for the debug HUD and the smoke test."""
    d = history.data
    return ("%d races, %d wins, %d podiums, %d DNFs, %d circuits"
            % (d.get("races", 0), d.get("wins", 0), d.get("podiums", 0),
               d.get("dnfs", 0),
               len([k for k in d.get("tracks", {}) if "|" not in k])))


if __name__ == "__main__":
    rd = find_results_dir()
    print("results dir: %s" % (rd or "NOT FOUND"))
    h = History()
    added = h.scan(rd)
    print("%d new result(s)" % added)
    print(summary(h))
    for key, t in sorted(h.data["tracks"].items()):
        if "|" in key:
            continue
        print("  %-14s visits=%-3d best=%-4s last=%-4s wins=%d"
              % (key, t.get("visits", 0), t.get("best", "-"),
                 t.get("last", "-"), t.get("wins", 0)))
