# -*- coding: utf-8 -*-
"""
FACTORtv — the first-run introduction, spoken by the race engineer.

    import tutorial
    tutorial.steps()          -> [{"t": ..., "point": ...}, ...]
    tutorial.done(cfg)        -> has this machine heard it?
    tutorial.mark_done(cfg)   -> ...it has now
    tutorial.replay(cfg)      -> and it may hear it again

Asked for directly: *"when someone first launches there can be voice tutorial on
what buttons do what, so like the first load they will get a caption card being
narrated by the enginner to show them exactly how to use it"*.

WHY THE ENGINEER AND NOT THE BOOTH
----------------------------------
The commentators describe a race to a viewer. The engineer talks TO the driver
and tells him what to do about things — which is exactly what an introduction is.
It also costs nothing in the fiction: a man on the pit wall explaining where the
switches are is a thing that happens on a first day.

THE RULES THIS MODULE EXISTS TO HOLD
------------------------------------
* ONCE. A flag in `_settings.json`, so it survives a restart, and a settings row
  can hand it back to anybody who wants it again.
* NEVER ON TRACK. It runs in the garage or on the menu. An introduction talking
  over a green flag is worse than no introduction, and this product has spent a
  lot of effort keeping the engineer off the grid.
* SKIPPABLE, and skipping it counts as having heard it. A player who clicks to
  make it stop has told you something.
* ONE LINE AT A TIME, gated on the speech actually finishing rather than on a
  timer, or nine lines arrive as one noise.

The script itself lives in `lines_data/tutorial.json` — ordered, because it is a
sequence rather than a pool. Nothing here rotates.
"""
import io
import json
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(_DIR, "lines_data", "tutorial.json")

# The flag's name in `_settings.json`. Kept here so the overlay, the settings
# page and the tests cannot disagree about the spelling of it.
FLAG = "intro_done"

# Marks a step can point at. A step naming anything else marks nothing, which is
# a silence rather than a fault — the same rule the line data follows everywhere.
POINTS = ("menu", "trophy")

_steps = None


def steps(force=False):
    """The script, in order. [] if the file is missing or unreadable.

    An empty script is a supported state: the overlay simply has no
    introduction, which is what a corrupt file should cost.
    """
    global _steps
    if _steps is not None and not force:
        return _steps
    out = []
    try:
        with io.open(PATH, encoding="utf-8") as f:
            data = json.load(f)
        for st in (data.get("steps") or ()):
            t = (st.get("t") or "").strip()
            if not t:
                continue
            pt = st.get("point") or ""
            out.append({"t": t, "point": pt if pt in POINTS else ""})
    except Exception:
        out = []
    _steps = out
    return out


def done(cfg):
    """Has this machine heard it? Missing flag means no, which is the default
    state of a fresh install and the only sensible reading of an absent key."""
    try:
        return bool((cfg or {}).get(FLAG))
    except Exception:
        return True          # cannot tell -> do not talk at somebody


def mark_done(cfg):
    """Record that it has been heard, or skipped. Returns True if it changed."""
    if cfg is None or cfg.get(FLAG):
        return False
    cfg[FLAG] = True
    return True


def replay(cfg):
    """Hand it back. Returns True if there was anything to hand back."""
    if cfg is None:
        return False
    cfg[FLAG] = False
    return True


def validate():
    """Problems with the script, as a list of strings. [] when it is sound."""
    errs = []
    sc = steps(force=True)
    if not sc:
        errs.append("no steps at all")
    for i, st in enumerate(sc):
        where = "step %d" % (i + 1)
        n = len(st["t"].split())
        # A SPOKEN LINE HAS A LENGTH. Forty words is fifteen seconds of one
        # voice talking without a pause, which is where a listener leaves.
        if n > 40:
            errs.append("%s: %d words" % (where, n))
        if "{" in st["t"]:
            # NO SLOTS. Every other line in this product fills them from a live
            # session; this one plays before there is anything to fill them
            # from, so a template here would air with the braces showing.
            errs.append("%s: has a {slot}" % where)
    return errs
