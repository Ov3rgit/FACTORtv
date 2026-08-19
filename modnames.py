# -*- coding: utf-8 -*-
"""
FACTORtv — what rFactor 2 actually CALLS a mod, read from rF2 itself.

    python modnames.py            -> dump the map, and where it came from

THE PROBLEM THIS EXISTS TO END
------------------------------
The FIA letter tells the driver which cars are eligible for his division, and
three times now it has named something that is not on the menu in the game:

  * "Kart Cup 2014", when the two selectable cars are "Kart Junior" and
    "Kart F1"
  * "Tatuus F4 2018", when the game lists **Tatuus F4-T014**
  * "GTR3 WORLD SERRIES", which was his spelling of a pack, not a car

Every one of them is the same fault: a FOLDER NAME is not a MENU NAME, and the
overlay only had the folder. Vehicle definitions live inside `.mas` archives
which are compressed and, for this Tatuus mod, encrypted outright — `car.mas`
does not even carry a readable file table — so the handover's long-standing
conclusion was that the real names can only ever come from the user.

That conclusion was WRONG, and pleasantly so. **The rF2 UI is an Electron app
and it caches its own content list as plain JSON**, keyed exactly the way this
problem needs:

    "content":[ { "name":"Tatuus_F4_2018", ... } ],
    "groupName":"Tatuus F4-T014"

`name` is the folder on disk. `groupName` is the words on the menu. One block
per installed package, and a pack that ships nine folders under one name — the
GT3 World Series — says so.

WHAT THIS IS NOT
----------------
**IT IS A CONVENIENCE, NEVER A DEPENDENCY.** It reads a browser cache: the file
names are arbitrary hashes, the cache can be evicted, and a UI update may
change the shape of it at any time. So:

  * every failure path returns an empty map, never an exception;
  * the answer is CACHED to `_modnames.json`, so a name learned once survives
    the cache being cleared;
  * `ladder.tier_cars` puts the CURATED `ui` names first regardless — those are
    words the user has confirmed with his own eyes, and nothing beats that.

A learned name is therefore better than the folder-derived guess it replaces
and worse than a name he has read on the screen himself, which is exactly where
it sits in the order.
"""
import json
import os
import re
import sys
import time

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(_DIR, "_modnames.json")

# Bump when the STORED SHAPE changes, so an old file is discarded rather than
# read wrongly — the same rule `career.VERSION` follows.
VERSION = 1

# Where the UI keeps its cache, relative to the game directory. Both the HTTP
# cache and the leveldb log carry the same JSON; the cache is the one that holds
# the whole list rather than the last thing looked at.
CACHE_DIRS = (
    os.path.join("UserData", "player", "LocalStorage", "Cache"),
    os.path.join("UserData", "player", "LocalStorage", "Local Storage",
                 "leveldb"),
)

# A cache file is only worth reading if it mentions one of the keys at all.
# Cheaper than parsing, and the cache holds megabytes of images.
#
# BOTH KEYS, and the first version had only the second — which skipped every
# file holding the per-CAR records and left the whole scan falling back to
# package names. The filter has to know about every source it is filtering for.
_MARKS = (b'"vehFile"', b'"groupName"')

# Sanity bounds on a menu name. A 200-character "name" is a description that
# happened to sit next to the key, and putting one in a letter would be worse
# than the folder it replaced.
NAME_MAX = 64

_cache = None


# A VEHICLE RECORD, matched as ONE pattern so the folder→name link is EXACT
# rather than inferred: `vehFile` is an absolute path into
# `Installed/Vehicles/<folder>/`, so nothing has to be associated with anything
# by position. `fullPathTree` is the menu path the UI navigates — "Karts, Kart
# Junior" — which is the actual answer to "what do I click".
#
# If a UI update reorders these fields the pattern stops matching and the
# package-level fallback carries it. That is the right failure: fewer names,
# never wrong ones.
_VEH = re.compile('"fullPathTree":"([^"]*)","vehFile":"([^"]*)"'
                  ',"engine":"[^"]*","manufacturer":"([^"]*)"')

_PKG = re.compile('"(name|groupName)"[ ]*:[ ]*"([^"]{1,%d})"' % NAME_MAX)

# These are Windows paths inside JSON, so the separator arrives doubled. Spelled
# out rather than escaped, because an escaped backslash in a pattern in a comment
# in a docstring is four levels of quoting nobody can read.
_SEP = chr(92)


def _folder_of(veh_path):
    """The vehicle FOLDER out of an absolute .veh path, or None."""
    parts = veh_path.replace(_SEP + _SEP, "/").replace(_SEP, "/").split("/")
    low = [p.lower() for p in parts]
    if "vehicles" in low:
        i = low.index("vehicles")
        if i + 1 < len(parts):
            return parts[i + 1] or None
    return None


def _clean_path(tree):
    """"Karts, Kart Junior" -> ("Karts", "Kart Junior").

    The separator is a comma, sometimes followed by a space and sometimes not —
    both spellings appear in the same cache, written by different mod authors.
    """
    out = []
    for part in (tree or "").split(","):
        part = part.strip()
        if part and len(part) <= NAME_MAX:
            out.append(part)
    return tuple(out)


def _cars(text):
    """Yield (folder, (level, level, ...)) for every vehicle record found."""
    for tree, veh, _manu in _VEH.findall(text):
        folder = _folder_of(veh)
        path = _clean_path(tree)
        if folder and path:
            yield folder, path


def _packages(text):
    """Yield (folder, package name) — the fallback when no car record parses.

    THE ORDER IN THE FILE IS THE PARSE: each block lists its `content` first and
    its `groupName` last, so names accumulate until a group closes them off.
    Weaker than a car record deliberately — a pack of nine GT3 cars has ONE
    package name and it is not the name of any car in it.
    """
    pend = []
    for m in _PKG.finditer(text):
        which, val = m.group(1), m.group(2).strip()
        if not val:
            continue
        if which == "name":
            pend.append(val)
        else:
            for folder in pend:
                yield folder, val
            pend = []


def scan(game_dir=None, mods=None):
    """{folder: menu name} learned from the rF2 UI's cache. {} if unreadable.

    `mods` is the list of folders that actually exist — the filter that keeps
    unrelated `"name"` keys out of the map. Without it every string in the cache
    beside a group name would look like a mod.
    """
    if not game_dir:
        try:
            import ladder as ladder_mod
            game_dir = ladder_mod.game_root()
        except Exception:
            game_dir = None
    if not game_dir:
        return {}
    if mods is None:
        try:
            import ladder as ladder_mod
            mods = ladder_mod.installed_mods(game_dir)
        except Exception:
            mods = None
    known = set(mods or ())
    out, packs = {}, {}
    for rel in CACHE_DIRS:
        d = os.path.join(game_dir, rel)
        if not os.path.isdir(d):
            continue
        try:
            names = os.listdir(d)
        except Exception:
            continue
        for fn in names:
            p = os.path.join(d, fn)
            try:
                if os.path.getsize(p) > 40 * 1024 * 1024:
                    continue           # an image blob, not a content list
                with open(p, "rb") as f:
                    raw = f.read()
            except Exception:
                continue
            if not any(m in raw for m in _MARKS):
                continue
            text = raw.decode("utf-8", "replace")
            for folder, path in _cars(text):
                if known and folder not in known:
                    continue
                got = out.setdefault(folder, [])
                if list(path) not in got:
                    got.append(list(path))
            for folder, pkg in _packages(text):
                if known and folder not in known:
                    continue
                if folder == pkg:
                    continue           # tells us nothing the folder did not
                packs.setdefault(folder, [[pkg]])
    # A CAR RECORD ALWAYS WINS. The package name is what the content manager
    # calls the download; the car record is what the SELECTION screen calls the
    # thing he actually has to click, and those are different strings for every
    # pack that ships more than one car.
    for folder, paths in packs.items():
        out.setdefault(folder, paths)
    return out


def _load():
    try:
        with open(STORE, "r", encoding="utf-8") as f:
            d = json.load(f)
        if int(d.get("version") or 0) != VERSION:
            return {}
        out = {}
        for k, v in (d.get("names") or {}).items():
            paths = [[str(x) for x in p if x] for p in v
                     if isinstance(p, (list, tuple))]
            if k and paths:
                out[k] = [p for p in paths if p]
        return out
    except Exception:
        return {}


def _save(names):
    try:
        with open(STORE, "w", encoding="utf-8") as f:
            json.dump({"version": VERSION, "when": int(time.time()),
                       "names": names}, f, indent=1, ensure_ascii=False)
    except Exception:
        pass


def names(game_dir=None, mods=None, refresh=False):
    """The map, learned and remembered. Cheap after the first call.

    **A NAME LEARNED ONCE IS KEPT.** The store is merged, never replaced, so
    clearing the game's cache — or a UI update changing its format — costs
    nothing already known. The only way a name changes is the user reinstalling
    a mod under a different one, and then the new scan wins.
    """
    global _cache
    if _cache is not None and not refresh:
        return _cache
    stored = _load()
    found = scan(game_dir, mods)
    if found:
        merged = dict(stored)
        merged.update(found)
        if merged != stored:
            _save(merged)
        stored = merged
    _cache = stored
    return _cache


def paths_for(folder, game_dir=None):
    """Every menu path this folder offers: [(level, level), ...]. Never raises."""
    if not folder:
        return []
    try:
        return [tuple(p) for p in (names(game_dir).get(folder) or ())]
    except Exception:
        return []


# How many separate cars a letter will name out of one folder before it stops
# listing them and names the GROUP instead. Three is a choice; sixty entries of
# an SMMG Formula 3 season is a database dump, and the thing he selects in the
# UI at that point is the group anyway.
LIST_MAX = 3


# How long a rendered path may get before its leading levels are dropped. A
# letter has to be readable; "GT3 World Series > Bmw M6 GT3 > Blancpain
# Endurance Series 2016" is a database row, not an instruction.
PATH_CHARS = 44


def _render(levels):
    """Levels as one string, shortened from the FRONT if it runs long.

    The front is the general end — a group he can see on the screen anyway — so
    dropping "GT3 World Series" costs less than dropping the car's own name. Two
    levels are always kept when there are two, because a bare model name with no
    group in front of it is the failure this module exists to fix.
    """
    parts = [p for p in levels if p]
    while len(parts) > 2 and len(" > ".join(parts)) > PATH_CHARS:
        parts.pop(0)
    return " > ".join(parts)


def pick_names(folder, game_dir=None, limit=LIST_MAX):
    """What to TELL HIM to look for, out of one folder. [] if we do not know.

    THE UI IS A TREE AND THE USEFUL LEVEL IS NOT ALWAYS THE SAME ONE — that is
    the whole difficulty, and taking the leaf gets it wrong for half the mods on
    this machine:

      Tatuus, Tatuus_F4-T014                                  leaf IS the car
      Karts, Kart Junior / Karts, Kart F1                     two cars, one folder
      GT3 World Series, Bmw M6 GT3, Blancpain Endurance 2016  leaf is a SERIES
      SMMG Formula 3, 2019..2024, TEAM                        leaf is a TEAM

    So the answer is the DEEPEST LEVEL AT WHICH EVERY PATH IN THE FOLDER
    AGREES — which is the identity of that folder in the tree, whatever depth it
    happens to sit at — plus the next level down when there are few enough of
    them to be worth listing. A folder holding two cars names both; a folder
    holding sixty liveries names the thing they are all inside.
    """
    got = paths_for(folder, game_dir)
    if not got:
        return []
    # The longest prefix common to every path.
    prefix = []
    for i in range(min(len(p) for p in got)):
        level = got[0][i]
        if all(p[i] == level for p in got):
            prefix.append(level)
        else:
            break
    depth = len(prefix)
    nxt = []
    for p in got:
        if len(p) > depth and p[depth] not in nxt:
            nxt.append(p[depth])
    if not prefix:
        # Nothing in common at all: list what there is and let the cap bite.
        return [_render(p) for p in got[:limit]]
    if nxt and len(nxt) <= limit:
        return [_render(prefix + [n]) for n in nxt]
    # Too many below it to list. The shared prefix is true of ALL of them, which
    # a truncated three-out-of-sixty is not.
    return [_render(prefix)]


def main():
    import ladder as ladder_mod
    mods = ladder_mod.installed_mods() or []
    print("installed vehicle folders: %d" % len(mods))
    live = scan(mods=mods)
    print("read from the rF2 UI cache: %d" % len(live))
    have = names(refresh=True)
    print("known after merging %s: %d\n" % (os.path.basename(STORE), len(have)))
    for folder in sorted(have):
        mark = " " if folder in live else "*"      # * = remembered, not re-read
        picked = pick_names(folder)
        n = len(have[folder])
        print("  %s %-34s -> %s%s"
              % (mark, folder[:34], "  |  ".join(picked),
                 ("   (of %d entries)" % n) if n > len(picked) else ""))
    missing = [m for m in mods if m not in have]
    print("\nno menu name for %d folder(s); those fall back to the tidied "
          "folder name" % len(missing))
    for m in missing[:12]:
        print("    %-34s -> %s" % (m[:34], ladder_mod.pretty_mod(m)))
    # WHAT THE FIA LETTER WILL ACTUALLY SAY, rung by rung. The letter is the
    # thing that was wrong, so the dump has to show the letter's own answer
    # rather than the map it is built from.
    print("\nWHAT THE FIA LETTER WILL NAME, PER RUNG")
    for pkey in ladder_mod.paths():
        for t in ladder_mod.tiers(pkey):
            cars = ladder_mod.tier_cars(t, mods)
            if cars:
                print("  %-13s %-16s %s"
                      % (pkey[:13], (t.get("name") or "")[:16],
                         " or ".join(n for n, _f in cars[:3])))


if __name__ == "__main__":
    main()
