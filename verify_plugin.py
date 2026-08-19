# -*- coding: utf-8 -*-
"""
FACTORtv — shared-memory self-check.

Proves three separate things, in order, and says which one failed:

  1. The plugin is installed and enabled       (can we open the buffers?)
  2. The plugin is actually publishing          (are the version counters moving?)
  3. Our struct layout is CORRECT               (does the data mean anything?)

Step 3 is the one that matters. A wrong `_pack_`, a missed field or an x86/x64
pointer-width mistake does not crash — it yields plausible-looking nonsense.
So instead of trusting the read, this asserts on things that can only be true
if every offset lines up: track and driver names must decode as text, lap
distance must fall inside the track length, tyre temperatures must be in a
survivable range, positions must form a contiguous 1..N set, and so on.

Usage — with rFactor 2 running and a session loaded (a replay is fine):
    python verify_plugin.py
"""
import ctypes
import sys
import time

import rf2_data as R

PASS = "  [ OK ] "
FAIL = "  [FAIL] "
WARN = "  [warn] "

_fails = []
_warns = []


def check(cond, label, detail=""):
    if cond:
        print(PASS + label + (("  " + detail) if detail else ""))
    else:
        print(FAIL + label + (("  " + detail) if detail else ""))
        _fails.append(label)
    return bool(cond)


def warn(cond, label, detail=""):
    if cond:
        print(PASS + label + (("  " + detail) if detail else ""))
    else:
        print(WARN + label + (("  " + detail) if detail else ""))
        _warns.append(label)
    return bool(cond)


def printable(s):
    """True if the string looks like a real name rather than reinterpreted
    float bytes. Garbage from a bad offset is almost always control chars or
    replacement characters, so this is a sharp test in practice."""
    if not s:
        return False
    return all(32 <= ord(c) < 127 or c.isalpha() for c in s) and "�" not in s


def hdr(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)


def main():
    hdr("1. STRUCT LAYOUT (static, no game needed)")
    check(ctypes.sizeof(R.rF2Vec3) == 24, "rF2Vec3 is 24 bytes")
    check(ctypes.sizeof(R.rF2Wheel) == 260, "rF2Wheel is 260 bytes",
          "got %d" % ctypes.sizeof(R.rF2Wheel))
    check(ctypes.sizeof(R.rF2VehicleTelemetry) == 1888,
          "rF2VehicleTelemetry is 1888 bytes",
          "got %d" % ctypes.sizeof(R.rF2VehicleTelemetry))
    check(ctypes.sizeof(R.rF2PhysicsOptions) == 40, "rF2PhysicsOptions is 40 bytes")
    check(R.rF2VehicleTelemetry._pack_ == 4, "pack(4) in force")
    check(ctypes.sizeof(ctypes.c_void_p) == 8,
          "running 64-bit Python (ScoringInfo embeds 8-byte pointers)",
          "pointer width %d" % ctypes.sizeof(ctypes.c_void_p))
    print("       telemetry buffer %d B | scoring %d B | extended %d B"
          % (R.TELEMETRY_SIZE, R.SCORING_SIZE, R.EXTENDED_SIZE))

    hdr("2. PLUGIN PRESENT")
    r = R.RF2Reader()
    if not check(r.open(), "opened '%s'" % R.MM_SCORING):
        print()
        print("  The buffer does not exist. That means one of:")
        print("    - rFactor 2 is not running")
        print("    - rFactor2SharedMemoryMapPlugin64.dll is not in Bin64\\Plugins")
        print("    - it is there but ' Enabled' is 0 in CustomPluginVariables.JSON")
        print("    - the game was already running when the plugin was installed")
        print("      (rF2 loads plugins at startup only — restart the game)")
        return 1

    ext = r.extended()
    if ext is not None:
        v = R.cstr(ext.mVersion)
        check(printable(v), "plugin reports its version", repr(v))
        warn(bool(ext.mDirectMemoryAccessEnabled),
             "DirectMemoryAccess on (extra pit/phase detail)")
    warn(r.tele_buf.open(), "telemetry buffer open")

    hdr("3. PLUGIN IS PUBLISHING")
    s0 = r.scoring()
    if not check(s0 is not None, "scoring buffer readable"):
        return 1
    v0 = s0.mVersionUpdateEnd
    t0 = r.telemetry()
    tv0 = t0.mVersionUpdateEnd if t0 is not None else 0
    print("       watching version counters for 3s...")
    time.sleep(3.0)
    s1 = r.scoring()
    t1 = r.telemetry()
    moved_s = s1 is not None and s1.mVersionUpdateEnd != v0
    moved_t = t1 is not None and t1.mVersionUpdateEnd != tv0
    warn(moved_s, "scoring counter advancing",
         "%d -> %d" % (v0, s1.mVersionUpdateEnd if s1 else -1))
    warn(moved_t, "telemetry counter advancing",
         "%d -> %d" % (tv0, t1.mVersionUpdateEnd if t1 else -1))
    if not (moved_s or moved_t):
        print()
        print("  Counters are frozen. The plugin is loaded but the game is not")
        print("  running a session — load a race, practice or replay and re-run.")

    s = s1 or s0
    si = s.mScoringInfo

    hdr("4. LAYOUT IS CORRECT (data has to MEAN something)")
    trk = R.cstr(si.mTrackName)
    check(printable(trk), "track name decodes as text", repr(trk))
    check(1000.0 < si.mLapDist < 30000.0,
          "track length is plausible", "%.1f m" % si.mLapDist)
    n = si.mNumVehicles
    check(0 <= n <= R.MAX_MAPPED_VEHICLES, "vehicle count in range", "%d" % n)
    check(0 <= si.mGamePhase <= 8, "game phase in enum range", "%d" % si.mGamePhase)
    check(-1 <= si.mYellowFlagState <= 7, "yellow flag state in enum range",
          "%d" % si.mYellowFlagState)
    check(0 <= si.mSession <= 15, "session index in range",
          "%d (%s)" % (si.mSession, R.session_kind(si.mSession)))
    warn(-30.0 < si.mAmbientTemp < 60.0, "ambient temp sane",
         "%.1f C" % si.mAmbientTemp)
    warn(-30.0 < si.mTrackTemp < 80.0, "track temp sane", "%.1f C" % si.mTrackTemp)

    if n == 0:
        print()
        print("  No cars in the session, so per-car checks are skipped.")
        print("  Load a session with cars on track and re-run for a full pass.")
        return 0 if not _fails else 1

    vs = [s.mVehicles[i] for i in range(min(n, R.MAX_MAPPED_VEHICLES))]

    names_ok = sum(1 for v in vs if printable(R.cstr(v.mDriverName)))
    check(names_ok == len(vs), "every driver name decodes as text",
          "%d/%d" % (names_ok, len(vs)))
    cls_ok = sum(1 for v in vs if printable(R.cstr(v.mVehicleClass)))
    check(cls_ok == len(vs), "every vehicle class decodes as text",
          "%d/%d" % (cls_ok, len(vs)))

    places = sorted(v.mPlace for v in vs)
    check(places == list(range(1, len(vs) + 1)),
          "positions form a contiguous 1..N set",
          "got %s" % (places[:8] + ["..."] if len(places) > 8 else places))

    dist_ok = all(-50.0 <= v.mLapDist <= si.mLapDist + 50.0 for v in vs)
    check(dist_ok, "every car's lap distance is inside the track length")

    check(all(-1 <= v.mControl <= 3 for v in vs), "control type in enum range")
    check(all(0 <= v.mSector <= 2 for v in vs), "sector index in enum range")
    players = [v for v in vs if v.mIsPlayer]
    warn(len(players) == 1, "exactly one car flagged as the player",
         "%d" % len(players))

    hdr("5. TELEMETRY CORRELATION")
    tele = R.telemetry_by_id(r.telemetry())
    if not warn(bool(tele), "telemetry buffer has vehicles"):
        print("  (telemetry is empty in some replay/monitor states — not fatal)")
    else:
        matched = sum(1 for v in vs if v.mID in tele)
        check(matched > 0, "scoring IDs match telemetry IDs",
              "%d/%d matched" % (matched, len(vs)))
        t = tele.get(players[0].mID) if players else list(tele.values())[0]
        check(printable(R.cstr(t.mVehicleName)), "telemetry vehicle name decodes",
              repr(R.cstr(t.mVehicleName)))
        check(0 < t.mEngineMaxRPM < 25000, "max RPM plausible",
              "%.0f" % t.mEngineMaxRPM)
        check(-2 <= t.mGear <= 10, "gear in range", "%d" % t.mGear)
        check(0.0 <= t.mFuel <= 250.0, "fuel litres plausible", "%.1f" % t.mFuel)
        check(0.0 < t.mFuelCapacity <= 250.0, "fuel capacity plausible",
              "%.1f" % t.mFuelCapacity)
        wear = [w.mWear for w in t.mWheels]
        check(all(0.0 <= x <= 1.0 for x in wear), "tyre wear is a 0..1 fraction",
              "%s" % ["%.3f" % x for x in wear])
        temps = [R.kelvin_c(w.mTemperature[1]) for w in t.mWheels]
        warn(all(x is None or -20.0 < x < 300.0 for x in temps),
             "tyre temps sane once converted from Kelvin",
             "%s C" % ["%.0f" % x if x is not None else "-" for x in temps])
        brk = [R.kelvin_c(w.mBrakeTemp) for w in t.mWheels]
        warn(all(x is None or -20.0 < x < 1400.0 for x in brk),
             "brake temps sane", "%s C" % ["%.0f" % x if x is not None else "-"
                                           for x in brk])
        check(all(0 <= d <= 16 for d in t.mDentSeverity),
              "damage zone severities in range",
              "%s" % list(t.mDentSeverity))
        compound = R.cstr(t.mFrontTireCompoundName)
        warn(printable(compound) or compound == "", "tyre compound name decodes",
             repr(compound))

    hdr("RESULT")
    if _fails:
        print("  %d CHECK(S) FAILED — the reader is NOT trustworthy yet:" % len(_fails))
        for f in _fails:
            print("     - " + f)
        return 1
    print("  All hard checks passed. The struct layout is correct.")
    if _warns:
        print("  %d soft warning(s) (usually just session state):" % len(_warns))
        for w in _warns:
            print("     - " + w)
    print()
    print("  Live snapshot:")
    print("     %s  |  %s  |  %d cars"
          % (trk, R.session_kind(si.mSession), n))
    top = sorted(vs, key=lambda v: v.mPlace if v.mPlace > 0 else 999)[:5]
    for v in top:
        print("     P%-2d %-24s %-20s best %s"
              % (v.mPlace, R.cstr(v.mDriverName), R.cstr(v.mVehicleClass),
                 R.fmt_time(v.mBestLapTime)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
