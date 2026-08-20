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
* ONCE PER MACHINE, recorded in a marker file that nothing else writes, plus a
  settings flag for installs older than the marker. A settings row hands it back
  to anybody who wants it again.
* NEVER ON TRACK. It runs in the garage or on the menu. An introduction talking
  over a green flag is worse than no introduction, and this product has spent a
  lot of effort keeping the engineer off the grid.
* NO SKIP. It was skippable on any click, which made the one feature whose job is
  to explain the interface stop the moment somebody used the interface — and left
  the "heard it" record depending on which click came first. His call: *"just have
  it play ine once full, no ability skip or anything"*. Nine short lines, once.
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

# ...AND A FILE THAT ONLY THIS FEATURE EVER TOUCHES.
#
# `_settings.json` was the wrong home for "he has heard it". Every toggle in the
# product writes that file WHOLE, from one process's in-memory copy — so a second
# overlay instance holding an older copy silently reverts anything the first one
# recorded. That is exactly what happened: the introduction completed, wrote the
# flag, and a still-running instance from before the fix wrote its own settings
# back over it, taking the flag with it and reverting the volume to 0.35 in the
# same stroke. He reported it three times and was right every time.
#
# A marker file cannot be clobbered by an unrelated save, because nothing else
# writes it and it is only ever CREATED. The settings flag stays as a secondary
# record so an existing install is not asked to sit through it again.
MARK = os.path.join(_DIR, "_intro_done")

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
    """Has this machine heard it?

    EITHER RECORD IS ENOUGH. The marker file is the durable one; the settings flag
    is what installs from before the marker existed have. Absent from both means a
    fresh machine, which is the only sensible reading of nothing at all.
    """
    try:
        if os.path.exists(MARK):
            return True
        return bool((cfg or {}).get(FLAG))
    except Exception:
        return True          # cannot tell -> do not talk at somebody


def mark_done(cfg):
    """Record that it has been heard. Returns True if the settings need saving.

    THE MARKER IS WRITTEN FIRST AND UNCONDITIONALLY, because it is the record that
    survives; the settings flag is set as well and its save is somebody else's
    job. A failure to write either must not raise into the frame loop.
    """
    wrote = False
    try:
        if not os.path.exists(MARK):
            with io.open(MARK, "w", encoding="utf-8") as f:
                f.write("The introduction has been played. Delete this file to "
                        "hear it again, or use Play the introduction in the "
                        "settings menu.\n")
    except Exception:
        pass
    if cfg is not None and not cfg.get(FLAG):
        cfg[FLAG] = True
        wrote = True
    return wrote


def replay(cfg):
    """Hand it back. Returns True if there was anything to hand back.

    BOTH RECORDS GO, or the marker would refuse a replay the player just asked
    for.
    """
    try:
        if os.path.exists(MARK):
            os.remove(MARK)
    except Exception:
        pass
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
