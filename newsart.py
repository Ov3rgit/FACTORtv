# -*- coding: utf-8 -*-
"""
FACTORtv — pictures for the news feed.

The user's own photographs, dropped into a folder tree and picked up without
a line of configuration:

    Pictures/Factor Overlay/<Division>/<Category>/*.jpg

THE CATEGORIES ARE TONES, NOT EVENTS, AND THAT IS THE WHOLE DESIGN.
"Drama", "On track", "Podiums or wins" describe the KIND of story, so the
picture is atmosphere and it never makes a claim. The moment an image is tied
to a specific event — a shot of a particular car attached to "Kandasamy takes
the title" — it becomes a factual assertion the reader can check, and it is
wrong the first time the photograph shows the wrong machinery. Every rule in
this module exists to keep that line intact.

NEVER ON MAIL. Only the news feed takes pictures. The story ending works
because the personal letters are indistinguishable from licensing statements
(`inboxtest.py` section 11 asserts it), and the moment a letter CAN have a
picture, "which ones have pictures" is a thing the reader sorts by — and
Mel's letters either stand out or conspicuously do not. News is a separate
tab with a separate contract, so it is free.

FOLDER-DRIVEN, LIKE `mynames.json` AND THE STING BANK. Adding a division is
making a folder; adding a photograph is dropping a file in. Nothing here is
declared in code, because a list of filenames in Python is a list somebody
has to keep in step with a directory, and it will not be kept in step.

A MISSING FOLDER IS SILENCE, NOT AN ERROR. A division nobody has photographed
falls back to `Generic`, and a career with no pictures at all renders exactly
the text-only feed that exists today.
"""
import os
import re
import sys

# --------------------------------------------------------------------------
# Where the pictures live.
#
# Under the user's own Pictures folder rather than beside the executable,
# deliberately: they are HIS files, they are large, and keeping them outside
# the program means a rebuild never touches them and packaging never has to
# collect them.
# --------------------------------------------------------------------------
FOLDER_NAME = "Factor Overlay"
GENERIC = "generic"

# The one folder that is not a division: a single mark per division, shown in
# the corner of the screen for as long as he is in that championship. Never a
# candidate for an article picture — `CATEGORY` below only ever names the
# three tones, so this cannot be picked by accident.
LOGO = "logo"

# WHAT HE TYPED, AND WHAT THE LADDER CALLS IT.
#
# Folder names are for a human reading a file browser; division names are for
# a commentator reading them out. "F1" is the obvious thing to call a folder
# and "Formula One" is the only sane thing for Miles to say, so neither is
# wrong and something has to bridge them. Folded on both sides, so case and
# punctuation are already handled — this is only for names that genuinely
# differ.
ALIASES = {
    "f1": "Formula One",
    "f2": "Formula 2",
    "f3": "Formula 3",
    "f4": "Formula 4",
    "formulaone": "F1",
    "formula1": "F1",
    "indy": "IndyCar",
    "nascar": "NASCAR",
    "supergt500": "Super GT500",
    "gt500": "Super GT500",
    "stockcarx": "Stock Car X",
    "hothatch": "Hot hatch",
    "touringcars": "Touring cars",
    "clubracer": "Club racer",
}

# PIL reads all of these. `.jfif` is a JPEG with an unusual extension - it is
# what a browser saves as, so it is what a folder of downloaded photographs
# is full of - and `.webp` is what most modern motorsport sites serve.
EXTS = (".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp")

# THE STORY KIND DECIDES THE TONE, and the mapping is deliberately coarse:
# three buckets is what a person can realistically photograph, and a fourth
# would mostly go unfilled.
#
# Anything not named here gets no picture at all. `did_you_know` is the case
# that matters: it is real motorsport history about somebody else's era
# entirely, and a photograph of this season's grid attached to a fact about
# Le Mans in 1971 is the one combination that reads as a lie.
CATEGORY = {
    # The result, and the reward for it.
    "news_title_first": "podiums or wins",
    "news_title_more": "podiums or wins",
    "news_first_win": "podiums or wins",
    "news_win_tally": "podiums or wins",
    "news_streak_podium": "podiums or wins",
    "news_status_champion": "podiums or wins",
    "news_status_multi": "podiums or wins",
    "news_status_legend": "podiums or wins",
    # The racing.
    "news_quali_pole": "on track",
    "news_quali_row": "on track",
    "news_climb": "on track",
    "news_form": "on track",
    "news_lead_change": "on track",
    "news_lead_gap": "on track",
    "news_dominance": "on track",
    "news_retro": "on track",
    "news_profile": "on track",
    "news_fame": "on track",
    # The needle.
    "news_needle": "drama",
    "news_rivalry": "drama",
    "news_rivalry_ai": "drama",
    "news_status_riser": "drama",
    "news_status_contender": "drama",
    "news_period": "drama",
}

_cache = {}          # folded (division, category) -> [paths]
_root_cache = None


def _fold(s):
    """Case, spacing and punctuation all removed.

    The user's own folders are `On Track`, `On track`, `Podiums Or wins`,
    `Podiums or Wins` and `drama` - which is exactly what a human typing
    twenty-five folder names produces, and none of it should matter. Matching
    on the folded form means he never has to go back and rename anything.
    """
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def root():
    """The pictures folder, or None if the user has not made one."""
    global _root_cache
    if _root_cache is not None:
        return _root_cache or None
    home = os.path.expanduser("~")
    for base in (os.path.join(home, "Pictures"), home):
        p = os.path.join(base, FOLDER_NAME)
        if os.path.isdir(p):
            _root_cache = p
            return p
    _root_cache = ""
    return None


def _subdir(parent, wanted):
    """A child directory whose folded name matches, or None.

    Tries the name it was given and then its alias, so a folder called `F1`
    answers to the division called `Formula One` without anybody renaming
    anything.
    """
    if not parent or not wanted:
        return None
    wants = [_fold(wanted)]
    alias = ALIASES.get(wants[0])
    if alias:
        wants.append(_fold(alias))
    try:
        entries = os.listdir(parent)
    except OSError:
        return None
    for want in wants:
        for entry in entries:
            full = os.path.join(parent, entry)
            if os.path.isdir(full) and _fold(entry) == want:
                return full
    return None


def brand(name):
    """A named organisation's mark — the FIA, and anything like it later.

    Kept apart from `logo()` because it is not a division: the FIA writes to
    a driver in every championship he ever enters, so its letterhead does not
    change when he is promoted.

    Looked for as a top-level folder whose folded name matches (so "FIA LOGO"
    answers to "FIA"), with the images directly inside it rather than under a
    category — because there is only one of them and a category would be a
    folder containing one folder.
    """
    base = root()
    if not base or not name:
        return None
    want = _fold(name)
    try:
        entries = os.listdir(base)
    except OSError:
        return None
    for entry in entries:
        folded = _fold(entry)
        if not (folded == want or folded.startswith(want)):
            continue
        d = os.path.join(base, entry)
        if not os.path.isdir(d):
            continue
        try:
            files = sorted(f for f in os.listdir(d)
                           if f.lower().endswith(EXTS))
        except OSError:
            continue
        if files:
            return os.path.join(d, files[0])
    return None


def logo(division):
    """The division's mark, or None.

    One image, not a rotation: a championship has one logo and showing a
    different one each session would read as a bug rather than as variety.
    The first file in the folder wins, sorted, so which one it is does not
    depend on directory order.

    NO GENERIC FALLBACK, deliberately — unlike the article pictures. A
    photograph of somebody else's racing is atmosphere; somebody else's LOGO
    is a claim about which championship he is in, and being wrong about that
    is the mistake this product has already made once ("the 2000 Formula One
    season"). No folder, no mark.
    """
    base = root()
    d = _subdir(base, division) if base else None
    c = _subdir(d, LOGO) if d else None
    if not c:
        return None
    try:
        files = sorted(f for f in os.listdir(c)
                       if f.lower().endswith(EXTS))
    except OSError:
        return None
    return os.path.join(c, files[0]) if files else None


def images(division, category):
    """Every usable picture for this division and tone, sorted.

    SORTED, because the rotation below indexes into this list and an
    arbitrary directory order would hand the same article a different
    photograph on different machines - and, worse, after the user adds a
    file. A news item is stored once and re-read for the rest of the career;
    the picture on it has to be as stable as the words.
    """
    key = (_fold(division), _fold(category))
    if key in _cache:
        return _cache[key]
    out = []
    base = root()
    if base:
        for div in (division, GENERIC):
            d = _subdir(base, div)
            c = _subdir(d, category) if d else None
            if not c:
                continue
            try:
                out = sorted(
                    os.path.join(c, f) for f in os.listdir(c)
                    if f.lower().endswith(EXTS)
                    and os.path.isfile(os.path.join(c, f)))
            except OSError:
                out = []
            if out:
                break
    _cache[key] = out
    return out


def for_item(item, division):
    """The picture for one news item, or None.

    DETERMINISTIC ON THE ITEM'S OWN ID. The id is already deterministic (that
    is what stops `refresh()` doubling anything), so the same article shows
    the same photograph every time it is opened, for the life of the career.
    A random pick would re-roll the image every time the panel redrew, which
    is the visual equivalent of a letter rewriting itself.
    """
    kind = item.get("kind") if isinstance(item, dict) else None
    if not kind or item.get("feed") != "news":
        # NEVER ON MAIL. See the module docstring: the story depends on the
        # letters being indistinguishable from each other.
        return None
    cat = CATEGORY.get(kind)
    if not cat:
        return None
    pool = images(division, cat)
    if not pool:
        return None
    # ROTATE ON THE ROUND, NOT ON A HASH OF THE ID.
    #
    # A hash is stable, which is the property that matters, but it is also
    # uniform - and uniform over three images means collisions constantly. The
    # first preview drew the same photograph for two articles in the same
    # feed, which is precisely the repetition the news feed has already been
    # rewritten twice to avoid. Rotating on the round number walks the whole
    # folder before it comes back to the start, so a three-image category
    # covers three rounds and a reader sees a new picture each time.
    #
    # The kind is folded in so two DIFFERENT stories in the same round do not
    # both take the same slot, and the whole thing is still a pure function
    # of data already in the store - so the article shows the same picture
    # every time it is opened, for the life of the career.
    seed = 0
    for ch in str(kind):
        seed = (seed * 131 + ord(ch)) & 0xFFFFFFFF
    rnd = item.get("round") or 0
    try:
        rnd = int(rnd)
    except (TypeError, ValueError):
        rnd = 0
    return pool[(rnd + seed) % len(pool)]


def reset():
    """Forget the scan. Called when a career is loaded, so a folder added
    while the game was running is picked up without a restart."""
    global _root_cache
    _cache.clear()
    _root_cache = None


def report():
    """What is actually on disk, for the preview and for a sanity check."""
    base = root()
    if not base:
        return []
    rows = []
    for entry in sorted(os.listdir(base)):
        d = os.path.join(base, entry)
        if not os.path.isdir(d):
            continue
        for cat in sorted(os.listdir(d)):
            c = os.path.join(d, cat)
            if not os.path.isdir(c):
                continue
            n = len([f for f in os.listdir(c) if f.lower().endswith(EXTS)])
            rows.append((entry, cat, n))
    return rows


if __name__ == "__main__":
    base = root()
    print("pictures root:", base or "(none found)")
    total = 0
    for div, cat, n in report():
        known = (_fold(cat) in {_fold(v) for v in CATEGORY.values()}
                 or _fold(cat) == _fold(LOGO))
        print("  %-16s %-18s %2d image(s)%s"
              % (div, cat, n, "" if known else "   <- unknown category"))
        total += n
    print("%d images" % total)
