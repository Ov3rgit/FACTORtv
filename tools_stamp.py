# -*- coding: utf-8 -*-
"""
FACTORtv — stamp this working copy with the build it is about to become.

    python tools_stamp.py            -> writes BUILD into version.py
    python tools_stamp.py --show     -> print what it WOULD write, change nothing
    python tools_stamp.py --clear    -> back to "dev"

WHY THIS EXISTS
---------------
Two copies of `0.0.1-beta` were indistinguishable. The archive keeps its
filename, the version string never moves, and a tester re-downloading the same
link ends up with a folder that cannot tell you what is in it. When he then
reports a bug, the first question — is this against today's code? — had no answer
except a size comparison.

WHAT IT WRITES
--------------
The date and the short commit: `2026-08-19.a7d14d5`. Both, because the date is
what a human says out loud ("the Tuesday build") and the commit is what actually
identifies the code. A dirty tree gets a `+` on the end, because a build made
from uncommitted edits is not the commit it claims to be and pretending otherwise
is the one thing a stamp must never do.

RUN IT BEFORE PYINSTALLER. The exe compiles `version.py` in, so a stamp applied
afterwards would be in the source and the zips but not in the thing the tester
actually runs.
"""
import io
import os
import re
import subprocess
import sys
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(_DIR, "version.py")


def _git(*args):
    try:
        out = subprocess.check_output(("git",) + args, cwd=_DIR,
                                      stderr=subprocess.STDOUT)
        return out.decode("utf-8", "replace").strip()
    except Exception:
        return ""


def stamp_for():
    """The stamp this working copy deserves, right now."""
    day = time.strftime("%Y-%m-%d")
    head = _git("rev-parse", "--short", "HEAD")
    if not head:
        # NO GIT, NO CLAIM ABOUT A COMMIT. The date alone is still worth having.
        return day
    dirty = bool(_git("status", "--porcelain"))
    return "%s.%s%s" % (day, head, "+" if dirty else "")


def write(value):
    """Set BUILD. Returns the old value."""
    src = io.open(PATH, encoding="utf-8").read()
    m = re.search(r'^BUILD = "([^"]*)"', src, re.M)
    if not m:
        raise SystemExit("version.py has no BUILD line to set")
    was = m.group(1)
    src = src[:m.start()] + 'BUILD = "%s"' % value + src[m.end():]
    io.open(PATH, "w", encoding="utf-8").write(src)
    return was


def main():
    args = sys.argv[1:]
    want = "dev" if "--clear" in args else stamp_for()
    if "--show" in args:
        print(want)
        return
    was = write(want)
    print("BUILD  %s -> %s" % (was, want))
    if want.endswith("+"):
        print("  NOTE: uncommitted changes — the stamp says so, on purpose.")


if __name__ == "__main__":
    main()
