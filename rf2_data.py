# -*- coding: utf-8 -*-
"""
rFactor 2 shared-memory reader for FACTORtv.

rFactor 2 publishes NOTHING on its own — unlike RaceRoom's built-in "$R3E"
block, rF2 is silent until a plugin is installed. Everything here reads the
buffers created by TheIronWolf's `rFactor2SharedMemoryMapPlugin64.dll`
(v3.7.15, GPLv3), which is the de-facto standard used by Crew Chief and
SimHub. If the plugin is missing or disabled, no buffer exists and every
read returns None — that is the "plugin not installed" state, not an error.

Layout notes that matter, because getting any of them wrong yields
convincing-looking garbage rather than a clean failure:

  * `#pragma pack(push, 4)` wraps the whole plugin header, so EVERY struct
    here is _pack_ = 4. Under natural alignment the doubles would gain
    padding and every offset past the first few fields would drift.
  * Each mapped buffer starts with a version block — two uint32s,
    mVersionUpdateBegin / mVersionUpdateEnd — BEFORE the payload. The plugin
    writes begin, then the body, then end. Reading a snapshot where the two
    disagree means we caught a torn frame mid-write; `read()` retries.
  * Windows `long` is 32-bit, so `long` -> c_int32 (NOT c_long semantics from
    a POSIX habit). MSVC `bool` is 1 byte.
  * rF2ScoringInfo embeds two raw pointers. We are always x64 here, so they
    are 8 bytes each; on x86 they would be 4 and every field after
    mLapDist would shift.

Run directly to dump live data (requires rFactor 2 running with the plugin):
    python rf2_data.py
"""
import ctypes
import time
from ctypes import wintypes

MAX_MAPPED_VEHICLES = 128
MAX_MAPPED_IDS = 512
MAX_STATUS_MSG_LEN = 128
MAX_RULES_INSTRUCTION_MSG_LEN = 96

MM_TELEMETRY = "$rFactor2SMMP_Telemetry$"
MM_SCORING = "$rFactor2SMMP_Scoring$"
MM_RULES = "$rFactor2SMMP_Rules$"
MM_EXTENDED = "$rFactor2SMMP_Extended$"

I32 = ctypes.c_int32          # C `long` on Windows
U32 = ctypes.c_uint32         # C `unsigned long` on Windows
U64 = ctypes.c_uint64         # ULONGLONG
I16 = ctypes.c_int16
U16 = ctypes.c_uint16
U8 = ctypes.c_ubyte
S8 = ctypes.c_byte            # signed char
B8 = ctypes.c_bool            # MSVC bool, 1 byte
F32 = ctypes.c_float
F64 = ctypes.c_double
CH = ctypes.c_char


class Base(ctypes.Structure):
    _pack_ = 4                # #pragma pack(push, 4)


# --------------------------------------------------------------------------
# enums (plain ints in the struct; these are for readability at call sites)
# --------------------------------------------------------------------------
class GamePhase:
    GARAGE = 0
    WARMUP = 1
    GRIDWALK = 2
    FORMATION = 3
    COUNTDOWN = 4
    GREEN = 5
    FCY = 6
    STOPPED = 7
    OVER = 8


class YellowState:
    INVALID = -1
    NONE = 0
    PENDING = 1
    PIT_CLOSED = 2
    PIT_LEAD_LAP = 3
    PIT_OPEN = 4
    LAST_LAP = 5
    RESUME = 6
    RACE_HALT = 7


class FinishStatus:
    NONE = 0
    FINISHED = 1
    DNF = 2
    DQ = 3


class Control:
    NOBODY = -1
    PLAYER = 0
    AI = 1
    REMOTE = 2
    REPLAY = 3


class PitState:
    NONE = 0
    REQUEST = 1
    ENTERING = 2
    STOPPED = 3
    EXITING = 4


class Flap:
    """Rear flap (rF2's name for DRS) legality."""
    DISALLOWED = 0
    DETECTED = 1
    ALLOWED = 2


# rF2 session index -> what it actually is. rF2 packs practice, qualifying
# and race into one integer range rather than a type enum.
SESSION_TEST_DAY = 0
SESSION_PRACTICE = range(1, 5)       # 1-4  Practice 1..4
SESSION_QUALIFY = range(5, 9)        # 5-8  Qualifying 1..4
SESSION_WARMUP = 9
SESSION_RACE = range(10, 14)         # 10-13 Race 1..4


def session_kind(n):
    """Collapse rF2's session index into 'test'/'practice'/'quali'/'warmup'/
    'race'. Everything downstream branches on this, never on the raw int."""
    if n == SESSION_TEST_DAY:
        return "test"
    if n in SESSION_PRACTICE:
        return "practice"
    if n in SESSION_QUALIFY:
        return "quali"
    if n == SESSION_WARMUP:
        return "warmup"
    if n in SESSION_RACE:
        return "race"
    return "unknown"


# --------------------------------------------------------------------------
# shared structs
# --------------------------------------------------------------------------
class rF2Vec3(Base):
    _fields_ = [("x", F64), ("y", F64), ("z", F64)]


class rF2Wheel(Base):
    _fields_ = [
        ("mSuspensionDeflection", F64),
        ("mRideHeight", F64),
        ("mSuspForce", F64),
        ("mBrakeTemp", F64),
        ("mBrakePressure", F64),
        ("mRotation", F64),
        ("mLateralPatchVel", F64),
        ("mLongitudinalPatchVel", F64),
        ("mLateralGroundVel", F64),
        ("mLongitudinalGroundVel", F64),
        ("mCamber", F64),
        ("mLateralForce", F64),
        ("mLongitudinalForce", F64),
        ("mTireLoad", F64),
        ("mGripFract", F64),
        ("mPressure", F64),
        ("mTemperature", F64 * 3),        # inner / middle / outer, Kelvin
        ("mWear", F64),                   # 1.0 = new, 0.0 = gone
        ("mTerrainName", CH * 16),
        ("mSurfaceType", U8),
        ("mFlat", B8),
        ("mDetached", B8),
        ("mStaticUndeflectedRadius", U8),
        ("mVerticalTireDeflection", F64),
        ("mWheelYLocation", F64),
        ("mToe", F64),
        ("mTireCarcassTemperature", F64),
        ("mTireInnerLayerTemperature", F64 * 3),
        ("mExpansion", U8 * 24),
    ]


class rF2VehicleTelemetry(Base):
    _fields_ = [
        ("mID", I32),
        ("mDeltaTime", F64),
        ("mElapsedTime", F64),
        ("mLapNumber", I32),
        ("mLapStartET", F64),
        ("mVehicleName", CH * 64),
        ("mTrackName", CH * 64),
        ("mPos", rF2Vec3),
        ("mLocalVel", rF2Vec3),
        ("mLocalAccel", rF2Vec3),
        ("mOri", rF2Vec3 * 3),
        ("mLocalRot", rF2Vec3),
        ("mLocalRotAccel", rF2Vec3),
        ("mGear", I32),
        ("mEngineRPM", F64),
        ("mEngineWaterTemp", F64),
        ("mEngineOilTemp", F64),
        ("mClutchRPM", F64),
        ("mUnfilteredThrottle", F64),
        ("mUnfilteredBrake", F64),
        ("mUnfilteredSteering", F64),
        ("mUnfilteredClutch", F64),
        ("mFilteredThrottle", F64),
        ("mFilteredBrake", F64),
        ("mFilteredSteering", F64),
        ("mFilteredClutch", F64),
        ("mSteeringShaftTorque", F64),
        ("mFront3rdDeflection", F64),
        ("mRear3rdDeflection", F64),
        ("mFrontWingHeight", F64),
        ("mFrontRideHeight", F64),
        ("mRearRideHeight", F64),
        ("mDrag", F64),
        ("mFrontDownforce", F64),
        ("mRearDownforce", F64),
        ("mFuel", F64),                   # litres remaining
        ("mEngineMaxRPM", F64),
        ("mScheduledStops", U8),
        ("mOverheating", B8),
        ("mDetached", B8),
        ("mHeadlights", B8),
        ("mDentSeverity", U8 * 8),        # 0=none 1=some 2=more, 8 body zones
        ("mLastImpactET", F64),
        ("mLastImpactMagnitude", F64),
        ("mLastImpactPos", rF2Vec3),
        ("mEngineTorque", F64),
        ("mCurrentSector", I32),
        ("mSpeedLimiter", U8),
        ("mMaxGears", U8),
        ("mFrontTireCompoundIndex", U8),
        ("mRearTireCompoundIndex", U8),
        ("mFuelCapacity", F64),
        ("mFrontFlapActivated", U8),
        ("mRearFlapActivated", U8),
        ("mRearFlapLegalStatus", U8),
        ("mIgnitionStarter", U8),
        ("mFrontTireCompoundName", CH * 18),
        ("mRearTireCompoundName", CH * 18),
        ("mSpeedLimiterAvailable", U8),
        ("mAntiStallActivated", U8),
        ("mUnused", U8 * 2),
        ("mVisualSteeringWheelRange", F32),
        ("mRearBrakeBias", F64),
        ("mTurboBoostPressure", F64),
        ("mPhysicsToGraphicsOffset", F32 * 3),
        ("mPhysicalSteeringWheelRange", F32),
        ("mBatteryChargeFraction", F64),
        ("mElectricBoostMotorTorque", F64),
        ("mElectricBoostMotorRPM", F64),
        ("mElectricBoostMotorTemperature", F64),
        ("mElectricBoostWaterTemperature", F64),
        ("mElectricBoostMotorState", U8),
        ("mExpansion", U8 * 111),
        ("mWheels", rF2Wheel * 4),        # FL, FR, RL, RR
    ]


class rF2ScoringInfo(Base):
    _fields_ = [
        ("mTrackName", CH * 64),
        ("mSession", I32),
        ("mCurrentET", F64),
        ("mEndET", F64),
        ("mMaxLaps", I32),
        ("mLapDist", F64),                # track length, metres
        ("pointer1", U8 * 8),             # x64 only; 4 bytes on x86
        ("mNumVehicles", I32),
        ("mGamePhase", U8),
        ("mYellowFlagState", S8),
        ("mSectorFlag", S8 * 3),
        ("mStartLight", U8),
        ("mNumRedLights", U8),
        ("mInRealtime", B8),
        ("mPlayerName", CH * 32),
        ("mPlrFileName", CH * 64),
        ("mDarkCloud", F64),
        ("mRaining", F64),
        ("mAmbientTemp", F64),
        ("mTrackTemp", F64),
        ("mWind", rF2Vec3),
        ("mMinPathWetness", F64),
        ("mMaxPathWetness", F64),
        ("mGameMode", U8),
        ("mIsPasswordProtected", B8),
        ("mServerPort", U16),
        ("mServerPublicIP", U32),
        ("mMaxPlayers", I32),
        ("mServerName", CH * 32),
        ("mStartET", F32),
        ("mAvgPathWetness", F64),
        ("mExpansion", U8 * 200),
        ("pointer2", U8 * 8),
    ]


class rF2VehicleScoring(Base):
    _fields_ = [
        ("mID", I32),
        ("mDriverName", CH * 32),
        ("mVehicleName", CH * 64),
        ("mTotalLaps", I16),
        ("mSector", S8),                  # 0=sector3, 1=sector1, 2=sector2
        ("mFinishStatus", S8),
        ("mLapDist", F64),                # metres around the lap
        ("mPathLateral", F64),
        ("mTrackEdge", F64),
        ("mBestSector1", F64),
        ("mBestSector2", F64),
        ("mBestLapTime", F64),
        ("mLastSector1", F64),
        ("mLastSector2", F64),
        ("mLastLapTime", F64),
        ("mCurSector1", F64),
        ("mCurSector2", F64),
        ("mNumPitstops", I16),
        ("mNumPenalties", I16),
        ("mIsPlayer", B8),
        ("mControl", S8),
        ("mInPits", B8),
        ("mPlace", U8),
        ("mVehicleClass", CH * 32),
        ("mTimeBehindNext", F64),
        ("mLapsBehindNext", I32),
        ("mTimeBehindLeader", F64),
        ("mLapsBehindLeader", I32),
        ("mLapStartET", F64),
        ("mPos", rF2Vec3),
        ("mLocalVel", rF2Vec3),
        ("mLocalAccel", rF2Vec3),
        ("mOri", rF2Vec3 * 3),
        ("mLocalRot", rF2Vec3),
        ("mLocalRotAccel", rF2Vec3),
        ("mHeadlights", U8),
        ("mPitState", U8),
        ("mServerScored", U8),
        ("mIndividualPhase", U8),
        ("mQualification", I32),
        ("mTimeIntoLap", F64),
        ("mEstimatedLapTime", F64),
        ("mPitGroup", CH * 24),
        ("mFlag", U8),                    # 0=green, 6=blue
        ("mUnderYellow", B8),
        ("mCountLapFlag", U8),
        ("mInGarageStall", B8),
        ("mUpgradePack", U8 * 16),
        ("mPitLapDist", F32),
        ("mBestLapSector1", F32),
        ("mBestLapSector2", F32),
        ("mExpansion", U8 * 48),
    ]


class rF2PhysicsOptions(Base):
    _fields_ = [
        ("mTractionControl", U8),
        ("mAntiLockBrakes", U8),
        ("mStabilityControl", U8),
        ("mAutoShift", U8),
        ("mAutoClutch", U8),
        ("mInvulnerable", U8),
        ("mOppositeLock", U8),
        ("mSteeringHelp", U8),
        ("mBrakingHelp", U8),
        ("mSpinRecovery", U8),
        ("mAutoPit", U8),
        ("mAutoLift", U8),
        ("mAutoBlip", U8),
        ("mFuelMult", U8),
        ("mTireMult", U8),
        ("mMechFail", U8),
        ("mAllowPitcrewPush", U8),
        ("mRepeatShifts", U8),
        ("mHoldClutch", U8),
        ("mAutoReverse", U8),
        ("mAlternateNeutral", U8),
        ("mAIControl", U8),
        ("mUnused1", U8),
        ("mUnused2", U8),
        ("mManualShiftOverrideTime", F32),
        ("mAutoShiftOverrideTime", F32),
        ("mSpeedSensitiveSteering", F32),
        ("mSteerRatioSpeed", F32),
    ]


class rF2TrackedDamage(Base):
    _fields_ = [
        ("mMaxImpactMagnitude", F64),
        ("mAccumulatedImpactMagnitude", F64),
    ]


class rF2VehScoringCapture(Base):
    _fields_ = [
        ("mID", I32),
        ("mPlace", U8),
        ("mIsPlayer", B8),
        ("mFinishStatus", S8),
    ]


class rF2SessionTransitionCapture(Base):
    _fields_ = [
        ("mGamePhase", U8),
        ("mSession", I32),
        ("mNumScoringVehicles", I32),
        ("mScoringVehicles", rF2VehScoringCapture * MAX_MAPPED_VEHICLES),
    ]


# --------------------------------------------------------------------------
# top-level mapped buffers
#
# Every one of these begins with the plugin's version block. The plugin bumps
# mVersionUpdateBegin, writes the body, then matches mVersionUpdateEnd to it.
# begin != end in a snapshot == we read mid-write.
# --------------------------------------------------------------------------
class rF2Telemetry(Base):
    _fields_ = [
        ("mVersionUpdateBegin", U32),
        ("mVersionUpdateEnd", U32),
        ("mBytesUpdatedHint", I32),
        ("mNumVehicles", I32),
        ("mVehicles", rF2VehicleTelemetry * MAX_MAPPED_VEHICLES),
    ]


class rF2Scoring(Base):
    _fields_ = [
        ("mVersionUpdateBegin", U32),
        ("mVersionUpdateEnd", U32),
        ("mBytesUpdatedHint", I32),
        ("mScoringInfo", rF2ScoringInfo),
        ("mVehicles", rF2VehicleScoring * MAX_MAPPED_VEHICLES),
    ]


class rF2Extended(Base):
    _fields_ = [
        ("mVersionUpdateBegin", U32),
        ("mVersionUpdateEnd", U32),
        ("mVersion", CH * 12),
        ("is64bit", B8),
        ("mPhysics", rF2PhysicsOptions),
        ("mTrackedDamages", rF2TrackedDamage * MAX_MAPPED_IDS),
        ("mInRealtimeFC", B8),
        ("mMultimediaThreadStarted", B8),
        ("mSimulationThreadStarted", B8),
        ("mSessionStarted", B8),
        ("mTicksSessionStarted", U64),
        ("mTicksSessionEnded", U64),
        ("mSessionTransitionCapture", rF2SessionTransitionCapture),
        ("mDisplayedMessageUpdateCapture", CH * 128),
        ("mDirectMemoryAccessEnabled", B8),
        ("mTicksStatusMessageUpdated", U64),
        ("mStatusMessage", CH * MAX_STATUS_MSG_LEN),
        ("mTicksLastHistoryMessageUpdated", U64),
        ("mLastHistoryMessage", CH * MAX_STATUS_MSG_LEN),
        ("mCurrentPitSpeedLimit", F32),
        ("mSCRPluginEnabled", B8),
        ("mSCRPluginDoubleFileType", I32),
        ("mTicksLSIPhaseMessageUpdated", U64),
        ("mLSIPhaseMessage", CH * MAX_RULES_INSTRUCTION_MSG_LEN),
        ("mTicksLSIPitStateMessageUpdated", U64),
        ("mLSIPitStateMessage", CH * MAX_RULES_INSTRUCTION_MSG_LEN),
        ("mTicksLSIOrderInstructionMessageUpdated", U64),
        ("mLSIOrderInstructionMessage", CH * MAX_RULES_INSTRUCTION_MSG_LEN),
        ("mTicksLSIRulesInstructionMessageUpdated", U64),
        ("mLSIRulesInstructionMessage", CH * MAX_RULES_INSTRUCTION_MSG_LEN),
        ("mUnsubscribedBuffersMask", I32),
        ("mHWControlInputEnabled", B8),
        ("mWeatherControlInputEnabled", B8),
        ("mRulesControlInputEnabled", B8),
        ("mPluginControlInputEnabled", B8),
    ]


TELEMETRY_SIZE = ctypes.sizeof(rF2Telemetry)
SCORING_SIZE = ctypes.sizeof(rF2Scoring)
EXTENDED_SIZE = ctypes.sizeof(rF2Extended)


def cstr(raw):
    """Decode a fixed char[] to str, stopping at the first NUL.

    rF2 leaves whatever was previously in the buffer past the terminator, so
    trusting the full array gives trailing junk on shorter names.
    """
    if isinstance(raw, bytes):
        raw = raw.split(b"\x00", 1)[0]
        return raw.decode("utf-8", errors="replace").strip()
    return ""


def kelvin_c(k):
    """rF2 reports every temperature in Kelvin. 0.0 means 'not reported'
    rather than absolute zero, so pass it through as None."""
    if not k:
        return None
    return k - 273.15


# --------------------------------------------------------------------------
# the reader
# --------------------------------------------------------------------------
_k32 = ctypes.windll.kernel32
_FILE_MAP_READ = 0x0004
_k32.OpenFileMappingW.restype = wintypes.HANDLE
_k32.OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
_k32.MapViewOfFile.restype = ctypes.c_void_p
_k32.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                               wintypes.DWORD, ctypes.c_size_t]
_k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
_k32.CloseHandle.argtypes = [wintypes.HANDLE]


class _Buffer:
    """One memory-mapped buffer, held open for the process lifetime.

    Uses OpenFileMappingW and NEVER CreateFileMapping. This is not a style
    preference — it is the whole correctness of the module:

      * Python's `mmap.mmap(-1, size, tagname)` CREATES a pagefile-backed
        mapping when none exists. With the game shut, that silently
        conjures a zero-filled region under the plugin's own name, so
        "is the plugin there?" answers yes forever and every field reads 0.
      * Worse, we would then be squatting on the name the plugin wants at
        startup, which is exactly how consumers end up starving the game of
        telemetry.

    OpenFileMapping fails cleanly when the mapping does not exist, which is
    the honest answer to "is rFactor 2 running with the plugin loaded?".

    The handle and view are held open for the life of the process. rF2's
    plugin, like RaceRoom, only keeps publishing while a consumer holds the
    mapping — open/close per read leaves no consumer present between reads.
    """

    def __init__(self, name, struct_t):
        self.name = name
        self.struct_t = struct_t
        self.size = ctypes.sizeof(struct_t)
        self._h = None
        self._view = None

    def _open(self):
        # Plain name first (normal single-player). The plugin's
        # DedicatedServerMapGlobally option moves the buffers into the
        # Global namespace, so fall back to that before giving up.
        for nm in (self.name, "Global\\" + self.name.lstrip("\\")):
            h = _k32.OpenFileMappingW(_FILE_MAP_READ, False, nm)
            if not h:
                continue
            view = _k32.MapViewOfFile(h, _FILE_MAP_READ, 0, 0, self.size)
            if not view:
                _k32.CloseHandle(h)
                continue
            self._h, self._view = h, view
            return True
        return False

    def open(self):
        return self._view is not None or self._open()

    def read(self, retries=3):
        """Return a torn-free snapshot, or None if the buffer is unavailable.

        The plugin does not lock. It brackets each write with a version
        counter, so a snapshot whose begin and end disagree was copied while
        the plugin was mid-write and must be discarded.
        """
        if self._view is None and not self._open():
            return None
        snap = None
        for _ in range(retries):
            try:
                raw = ctypes.string_at(self._view, self.size)
            except Exception:
                # The game exited and took the mapping with it. Drop the
                # stale handle so the next tick can re-attach on relaunch.
                self.close()
                return None
            snap = self.struct_t.from_buffer_copy(raw)
            if snap.mVersionUpdateBegin == snap.mVersionUpdateEnd:
                return snap
            time.sleep(0.001)
        # Every attempt tore. Hand back the last one anyway: a consistently
        # torn buffer means the plugin is writing far faster than we read,
        # and stale-but-usable beats a frozen overlay.
        return snap

    def close(self):
        if self._view:
            _k32.UnmapViewOfFile(self._view)
            self._view = None
        if self._h:
            _k32.CloseHandle(self._h)
            self._h = None


class RF2Reader:
    """Reads the plugin's Telemetry / Scoring / Extended buffers.

    `scoring` is the authoritative view of the session (order, laps, gaps,
    flags) at 5 Hz; `telemetry` is the fast car data at 50 Hz. They are
    separate buffers written at different rates, so they are read separately
    and correlated by mID rather than by array index — the plugin does NOT
    guarantee the two arrays are in the same order.
    """

    def __init__(self):
        self.tele_buf = _Buffer(MM_TELEMETRY, rF2Telemetry)
        self.score_buf = _Buffer(MM_SCORING, rF2Scoring)
        self.ext_buf = _Buffer(MM_EXTENDED, rF2Extended)

    def open(self):
        """True if the plugin is present. Scoring is the one we insist on —
        telemetry alone cannot tell us what session we are in."""
        return self.score_buf.open()

    @property
    def plugin_present(self):
        return self.score_buf.open()

    def scoring(self):
        return self.score_buf.read()

    def telemetry(self):
        return self.tele_buf.read()

    def extended(self):
        return self.ext_buf.read()

    def close(self):
        self.tele_buf.close()
        self.score_buf.close()
        self.ext_buf.close()


def telemetry_by_id(tele):
    """Map mID -> rF2VehicleTelemetry for correlating against scoring.

    Index-matching the two buffers looks like it works and then silently
    mixes up cars when the field changes, because the plugin fills telemetry
    in the order the sim reports physics, not in scoring order.
    """
    if tele is None:
        return {}
    out = {}
    for i in range(max(0, min(tele.mNumVehicles, MAX_MAPPED_VEHICLES))):
        v = tele.mVehicles[i]
        out[v.mID] = v
    return out


def fmt_time(t):
    if t is None or t <= 0:
        return "--:--.---"
    m = int(t // 60)
    s = t - m * 60
    return "%d:%06.3f" % (m, s) if m else "%.3f" % s


def _dump():
    print("struct sizes: telemetry=%d scoring=%d extended=%d"
          % (TELEMETRY_SIZE, SCORING_SIZE, EXTENDED_SIZE))
    r = RF2Reader()
    if not r.open():
        print("Could not open '%s'." % MM_SCORING)
        print("Is rFactor 2 running, with rFactor2SharedMemoryMapPlugin64.dll")
        print("installed in Bin64\\Plugins and enabled in CustomPluginVariables.JSON?")
        return
    while True:
        s = r.scoring()
        if s is None:
            print("scoring read failed; retrying...")
            time.sleep(1)
            continue
        tele = telemetry_by_id(r.telemetry())
        ext = r.extended()
        si = s.mScoringInfo
        print("\x1b[2J\x1b[H", end="")
        if ext is not None:
            print("plugin v%s  dma=%s" % (cstr(ext.mVersion),
                                          bool(ext.mDirectMemoryAccessEnabled)))
        print("track: %s   length=%.0fm" % (cstr(si.mTrackName), si.mLapDist))
        print("session=%d (%s)  phase=%d  realtime=%s  cars=%d"
              % (si.mSession, session_kind(si.mSession), si.mGamePhase,
                 bool(si.mInRealtime), si.mNumVehicles))
        print("ET=%.1f  end=%.1f  maxlaps=%d  yellow=%d  air=%.1fC track=%.1fC rain=%.2f"
              % (si.mCurrentET, si.mEndET, si.mMaxLaps, si.mYellowFlagState,
                 si.mAmbientTemp, si.mTrackTemp, si.mRaining))
        print("-" * 96)
        print("%2s %-22s %-18s %3s %10s %10s %6s %5s %s"
              % ("P", "DRIVER", "CLASS", "LAP", "LAST", "BEST", "SPD", "FUEL", "PIT"))
        vs = [s.mVehicles[i] for i in range(max(0, min(si.mNumVehicles,
                                                       MAX_MAPPED_VEHICLES)))]
        vs.sort(key=lambda v: v.mPlace if v.mPlace > 0 else 999)
        for v in vs:
            t = tele.get(v.mID)
            spd = 0.0
            fuel = 0.0
            if t is not None:
                lv = t.mLocalVel
                spd = (lv.x ** 2 + lv.y ** 2 + lv.z ** 2) ** 0.5 * 3.6
                fuel = t.mFuel
            print("%2d %-22.22s %-18.18s %3d %10s %10s %6.1f %5.1f %s%s"
                  % (v.mPlace, cstr(v.mDriverName), cstr(v.mVehicleClass),
                     v.mTotalLaps, fmt_time(v.mLastLapTime),
                     fmt_time(v.mBestLapTime), spd, fuel,
                     "Y" if v.mInPits else " ",
                     "  <-- YOU" if v.mIsPlayer else ""))
        time.sleep(0.5)


if __name__ == "__main__":
    _dump()
