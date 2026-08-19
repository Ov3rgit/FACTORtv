"""The session reader against the REAL shared-memory structs.

WHY THIS FILE EXISTS. Every other suite feeds the booth a `FakeSession` — a
plain Python object where every attribute exists because the fake defines it.
That is the right shape for testing what the booth SAYS, and it is completely
blind to the layer underneath: whether `SessionTracker.update()` reads fields
that are actually on the structs rF2 publishes.

It was blind to a real one. The track-limits ground truth was written as

    s.status_message = R.cstr(si.mStatusMessage)

and `si` is `mScoringInfo`, which has no such field — the plugin puts the
status message in `rF2Extended`, a different memory map. So it raised
AttributeError on EVERY TICK. The tracker read is the second thing
`_tick_body` does, so the whole overlay drew nothing at all, and the console
filled with the same traceback twenty times a second. Fifteen suites passed
throughout, because not one of them touched a real struct.

The structs are plain ctypes and instantiate zeroed WITHOUT the game running,
so this costs nothing and needs no rFactor 2:

    python tests/buffertest.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rf2_data as R
import rf2_session as RS

fails = []
def check(c, l, e=""):
    print(("  [ OK ] " if c else "  [FAIL] ") + l + (("  " + e) if e else ""))
    if not c:
        fails.append(l)


class RealStructReader(object):
    """A reader that hands back REAL, zeroed rF2 structs.

    This is the whole point: the objects have exactly the fields the plugin
    publishes and not one more, so any attribute the session layer invents
    raises the same AttributeError it would raise in a live race.
    """
    def __init__(self, cars=3, extended=True):
        self.sc = R.rF2Scoring()
        self.te = R.rF2Telemetry()
        self.ex = R.rF2Extended() if extended else None
        self.sc.mScoringInfo.mNumVehicles = cars
        self.te.mNumVehicles = cars
        self.sc.mScoringInfo.mLapDist = 5000.0
        self.sc.mScoringInfo.mNumTrackSectors = 3
        for i in range(cars):
            v = self.sc.mVehicles[i]
            v.mID = i + 1
            v.mPlace = i + 1
            v.mTotalLaps = 3
            v.mIsPlayer = 1 if i == 0 else 0
            self.te.mVehicles[i].mID = i + 1

    plugin_present = True
    def scoring(self):
        return self.sc
    def telemetry(self):
        return self.te
    def extended(self):
        return self.ex
    def close(self):
        pass


print("\n1. EVERY FIELD THE SESSION READS EXISTS ON THE REAL STRUCT")
# A full update against real structs. Any wrong field name is an
# AttributeError here, exactly as it is in a race.
t = RS.SessionTracker(display_name="Dante Kandasamy")
t.reader = RealStructReader()
err = None
try:
    s = t.update()
except Exception as e:                                  # noqa: BLE001
    err = e
check(err is None, "a full update() runs against real zeroed structs",
      "%s: %s" % (type(err).__name__, err) if err else "")

if err is None:
    check(s.valid or not s.valid, "and returns a Session")
    # Tick it several times: the second pass takes the branches that compare
    # against remembered state, which the first cannot reach.
    err2 = None
    try:
        for i in range(4):
            t.reader.sc.mScoringInfo.mCurrentET = 10.0 * (i + 1)
            for j in range(3):
                t.reader.sc.mVehicles[j].mTotalLaps = 3 + i
            s = t.update()
    except Exception as e:                              # noqa: BLE001
        err2 = e
    check(err2 is None, "and keeps running across repeated ticks",
          "%s: %s" % (type(err2).__name__, err2) if err2 else "")

print("\n1b. INCLUDING THE FIELDS ON BRANCHES THIS TEST NEVER TAKES")
# §1 only proves the lines it executed. A field read inside a branch that
# needs a pit stop, a yellow or a finished race is just as wrong and would
# wait for a race to reveal itself — which is precisely how the status
# message survived to a live launch. So: read the source and check every
# `si.mX` / `ext.mX` against the real struct, whether or not it ran.
#
# COMMENTS AND STRINGS MUST COME OUT FIRST. The fix for this bug documents
# the trap by NAMING it — "this was written as `si.mStatusMessage`" — and a
# naive grep flags that comment as the bug it is warning about.
import io as _io
import re as _re
import tokenize as _tokenize

_path = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "rf2_session.py")
_code = []
with open(_path, "rb") as _f:
    for _tok in _tokenize.tokenize(_f.readline):
        if _tok.type not in (_tokenize.COMMENT, _tokenize.STRING):
            _code.append(_tok.string)
_code = " ".join(_code)

_wrong = []
for _var, _st in (("si", R.rF2ScoringInfo), ("ext", R.rF2Extended)):
    for _m in _re.finditer(r"\b%s\.(m[A-Za-z0-9_]+)" % _var, _code):
        if not hasattr(_st, _m.group(1)):
            _wrong.append("%s.%s" % (_var, _m.group(1)))
check(not _wrong, "every si./ext. field in the source exists on its struct",
      str(sorted(set(_wrong))))

print("\n2. THE STATUS MESSAGE COMES FROM THE EXTENDED BUFFER")
# The specific bug. `mStatusMessage` and its tick counter are rF2Extended
# fields; scoring has neither, and asking scoring for them is what took the
# overlay down.
check(not hasattr(R.rF2ScoringInfo, "mStatusMessage"),
      "mScoringInfo does NOT carry it — this is the trap")
check(hasattr(R.rF2Extended, "mStatusMessage")
      and hasattr(R.rF2Extended, "mTicksStatusMessageUpdated"),
      "rF2Extended carries the message and its tick counter")

t2 = RS.SessionTracker()
t2.reader = RealStructReader()
t2.reader.ex.mStatusMessage = b"INVALID LAP - TRACK LIMITS"
t2.reader.ex.mTicksStatusMessageUpdated = 1234
s2 = t2.update()
check("TRACK LIMITS" in (s2.status_message or ""),
      "the message is read from where it actually lives", s2.status_message)
check(s2.status_message_new,
      "and a new tick counter makes it edge-triggered news")
# LAW 1: the same message must not be re-announced while it stays on screen.
s3 = t2.update()
check(not s3.status_message_new,
      "the SAME message on the next tick is not news again (LAW 1)")
t2.reader.ex.mTicksStatusMessageUpdated = 1235
check(t2.update().status_message_new, "a genuinely new one is")

print("\n3. NO EXTENDED BUFFER IS A DEGRADED FEATURE, NOT A CRASH")
# An older plugin build may not map it. `read()` returns None for an absent
# mapping, and the correct response is to fall back to the surface detector —
# which is how excursions worked before the ground truth was added at all.
t3 = RS.SessionTracker()
t3.reader = RealStructReader(extended=False)
err3 = None
try:
    s4 = t3.update()
except Exception as e:                                  # noqa: BLE001
    err3 = e
check(err3 is None, "update() survives a missing extended buffer",
      "%s: %s" % (type(err3).__name__, err3) if err3 else "")
if err3 is None:
    check(s4.status_message == "" and not s4.status_message_new,
          "and simply reports no ground truth")

print("\n4. THE OVERLAY'S OWN TICK SURVIVES THE READ")
# The reason this bug was total rather than partial: the tracker read is the
# second thing `_tick_body` does, so an exception there costs every panel.
# `tick()` catches it and keeps scheduling, which is correct — the overlay
# must not die mid-race — but it means a bad read is a silent blank screen
# plus a console full of tracebacks, which is what the user saw.
import factor_tv
src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "factor_tv.py"), encoding="utf-8").read()
check("self.tracker.update() if plugin else None" in src,
      "the tracker read still happens before any drawing")
check("except Exception:" in src and "self.root.after" in src,
      "and a failure there is caught rather than killing the overlay")

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
