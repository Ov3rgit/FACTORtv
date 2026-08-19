# -*- coding: utf-8 -*-
"""
FACTORtv — session normalisation.

Turns the two raw plugin buffers into the single tidy picture the rest of the
overlay consumes. Everything above this line thinks in "cars, positions,
gaps, sectors"; only this module knows that rF2 stores sector 3 as index 0.

The three things rF2 makes genuinely hard
-----------------------------------------

1. GAPS. rF2 does give mTimeBehindNext / mTimeBehindLeader, and it is
   tempting to just draw those. They are unusable for broadcast: scoring
   updates at 5 Hz, and the values are recomputed at timing lines, so the
   number sits frozen for a second and then jumps. Real timing screens work
   by remembering WHERE each car was and WHEN, then asking "how long ago was
   the car ahead standing where the car behind is now?". That is what
   `_Timeline` does, and it is why gaps here move smoothly and stay right
   through corners, pit cycles and lapped traffic.

2. CORRELATION. Telemetry and scoring are separate buffers written at
   different rates, and the vehicle arrays are NOT in the same order. They
   are joined on mID, never on index.

3. IDENTITY. In replays and monitor mode no car is flagged mIsPlayer at all,
   and rF2's default profile leaves the driver called "Your Name" — which an
   engineer must never say out loud. Both are resolved here so no other
   module has to think about it.
"""
import time
from collections import deque

import era as era_mod
import rf2_data as R
import track as track_mod

# How long a position swap must hold before it counts as an overtake. rF2
# scoring can flicker two cars' places for a single update when they are
# side by side at a timing line; without this the booth calls a pass that
# never happened, then calls it back.
PLACE_CONFIRM_S = 0.35

# Timeline retention. Long enough to measure a gap of over a minute (lapped
# traffic), short enough that 40 cars never cost real memory.
TIMELINE_S = 150.0
TIMELINE_MIN_DT = 0.05      # don't store faster than 20 Hz

# rF2 leaves these in the profile by default. An engineer calling the driver
# "Your Name" is worse than calling them nothing.
PLACEHOLDER_NAMES = {"your name", "your nickname", "player", "driver",
                     "default", "unnamed", "new driver", ""}

# rF2's mSector is not what you would guess: 0 means "in sector 3".
SECTOR_FROM_RF2 = {0: 3, 1: 1, 2: 2}

# rF2Wheel.mSurfaceType, from rF2's InternalsPlugin.hpp:
#   0 dry  1 wet  2 grass  3 dirt  4 gravel  5 rumblestrip  6 special
# A KERB IS NOT AN EXCURSION. Rumblestrip has to count as on-track or every
# driver taking a normal apex is "off", which is the fastest way to spend the
# booth's credibility. Anything not in this set — including value 6 and any
# value a future build invents — is also treated as on-track: the failure we
# can afford is missing an off, not inventing one.
ON_TRACK_SURFACES = frozenset((0, 1, 5, 6))


def is_placeholder(name):
    return (name or "").strip().lower() in PLACEHOLDER_NAMES


class _Timeline(object):
    """Where one car was, and when.

    Stores (race_distance, elapsed_time) samples so we can answer
    "when was this car at distance D?" by interpolation. Race distance is
    cumulative across laps, so it increases monotonically and the lookup
    never has to special-case the start/finish line.
    """

    __slots__ = ("pts",)

    def __init__(self):
        self.pts = deque()

    def add(self, dist, et):
        p = self.pts
        if p and et - p[-1][1] < TIMELINE_MIN_DT:
            return
        # A reset, a teleport to the garage or a session restart makes
        # distance go backwards. The history is meaningless across that, so
        # drop it rather than interpolate through the discontinuity.
        if p and dist < p[-1][0] - 1.0:
            p.clear()
        p.append((dist, et))
        cutoff = et - TIMELINE_S
        while p and p[0][1] < cutoff:
            p.popleft()

    def time_at(self, dist):
        """Elapsed time at which this car was at `dist`, or None if that is
        outside the retained history."""
        p = self.pts
        if len(p) < 2 or dist < p[0][0] or dist > p[-1][0]:
            return None
        # Walk from the newest end: the answer is nearly always recent.
        prev = None
        for i in range(len(p) - 1, -1, -1):
            d, t = p[i]
            if d <= dist:
                if prev is None:
                    return t
                d2, t2 = prev
                if d2 == d:
                    return t
                f = (dist - d) / (d2 - d)
                return t + f * (t2 - t)
            prev = (d, t)
        return None

    def clear(self):
        self.pts.clear()


class Car(object):
    """One car's normalised state for this tick."""

    __slots__ = (
        "id", "slot", "name", "display_name", "cls", "vehicle", "place",
        "place_class", "laps", "lap_dist", "race_dist", "in_pits", "pit_state",
        "pit_stops", "penalties", "finish_status", "control", "is_player",
        "is_ai", "best_lap", "last_lap", "cur_s1", "cur_s2", "last_s1",
        "last_s2", "last_s3", "best_s1", "best_s2", "best_s3", "sector",
        "gap_leader", "gap_ahead", "gap_behind", "laps_down", "speed",
        "in_garage", "under_yellow", "blue_flag", "started_place",
        "places_gained", "lap_start_et", "time_into_lap", "est_lap",
        "car_number", "tyre_front", "tyre_rear", "fuel", "fuel_cap",
        "rpm", "max_rpm", "gear", "damage", "tyre_wear", "tyre_temp",
        "brake_temp", "flap", "battery", "headlights", "on_pit_lap",
        "last_lap_valid", "count_lap",
        "purple_lap", "purple_s1", "purple_s2", "purple_s3",
        "pos", "wheels_off", "surface",
    )

    def __init__(self):
        for s in self.__slots__:
            setattr(self, s, None)
        self.laps = 0
        self.place = 0
        self.gap_leader = 0.0
        self.gap_ahead = 0.0
        self.gap_behind = 0.0
        self.laps_down = 0
        self.places_gained = 0
        self.speed = 0.0
        self.purple_lap = False
        self.purple_s1 = self.purple_s2 = self.purple_s3 = False
        # 0..4. None means we have no telemetry for this car and therefore do
        # not know — which is NOT the same as "on track", and callers must
        # treat it as unknown rather than folding it into zero.
        self.wheels_off = None
        self.surface = ()

    def __repr__(self):
        return "<Car P%s %s %+.3f>" % (self.place, self.display_name,
                                       self.gap_ahead or 0.0)


class Session(object):
    """The whole normalised picture for one tick."""

    __slots__ = (
        "valid", "track", "track_len", "kind", "session_index", "phase",
        "phase_name", "green", "countdown", "finished", "in_realtime",
        "et", "end_et", "time_left", "max_laps", "leader_laps", "laps_left",
        "timed", "cars", "order", "player", "leader", "num_cars", "era",
        "player_era", "multiclass", "yellow", "yellow_sectors", "full_course_yellow",
        "sector_flags_raw",
        "air_temp", "track_temp", "raining", "wetness", "dark",
        "best_lap_time", "best_lap_driver", "best_s1", "best_s2", "best_s3",
        "started", "replay", "pit_speed_limit", "classes", "circuit",
        "on_air", "status_message", "status_message_new",
    )

    def __init__(self):
        for s in self.__slots__:
            setattr(self, s, None)
        self.valid = False
        self.cars = {}
        self.order = []
        self.classes = []
        self.yellow_sectors = (0, 0, 0)
        self.sector_flags_raw = (0, 0, 0)

    def car_ahead(self, car):
        i = car.place - 1
        return self.order[i - 1] if 0 < i < len(self.order) else None

    def car_behind(self, car):
        i = car.place - 1
        return self.order[i + 1] if 0 <= i < len(self.order) - 1 else None

    def in_class(self, cls):
        return [c for c in self.order if c.cls == cls]


_PHASE_NAMES = {
    0: "garage", 1: "warmup", 2: "gridwalk", 3: "formation", 4: "countdown",
    5: "green", 6: "full course yellow", 7: "stopped", 8: "over",
}


class SessionTracker(object):
    """Stateful normaliser. Call `update()` once per tick.

    Holds everything that cannot be derived from a single snapshot: position
    history for gaps, starting grid for places-gained, sector bests, and the
    confirmation timers that stop position flicker becoming a fake overtake.
    """

    def __init__(self, display_name=None):
        self.reader = R.RF2Reader()
        self.display_name = display_name   # overrides rF2's "Your Name"
        self._timelines = {}               # mID -> _Timeline
        self._grid = {}                    # mID -> starting place
        self._place_pending = {}           # mID -> (place, since_et)
        self._place_confirmed = {}         # mID -> place
        self._best_s = [None, None, None]  # session best sector times
        self._best_lap = None
        self._best_lap_id = None
        self._session_sig = None           # detects a session change
        self._era = None
        self._era_sig = None
        self._last_et = 0.0
        self._status_ticks = None          # mTicksStatusMessageUpdated seen

    # -- lifecycle ---------------------------------------------------------
    @property
    def plugin_present(self):
        return self.reader.plugin_present

    def close(self):
        self.reader.close()

    def _reset(self):
        """A new session wipes every piece of carried state. Missing this is
        how a fresh race inherits the last one's grid and reports everybody
        as having gained twenty places on lap one."""
        self._timelines.clear()
        self._grid.clear()
        self._place_pending.clear()
        self._place_confirmed.clear()
        self._best_s = [None, None, None]
        self._best_lap = None
        self._best_lap_id = None

    # -- main --------------------------------------------------------------
    def update(self):
        s = Session()
        raw = self.reader.scoring()
        if raw is None:
            return s
        si = raw.mScoringInfo
        n = max(0, min(si.mNumVehicles, R.MAX_MAPPED_VEHICLES))

        # A change of track, session index or car count means a new session.
        sig = (R.cstr(si.mTrackName), si.mSession, round(si.mLapDist))
        if sig != self._session_sig:
            self._session_sig = sig
            self._reset()
        # Time running backwards is a restart of the same session.
        if si.mCurrentET < self._last_et - 5.0:
            self._reset()
        self._last_et = si.mCurrentET

        tele = R.telemetry_by_id(self.reader.telemetry())

        s.valid = True
        s.track = R.cstr(si.mTrackName)
        # Resolved circuit identity + knowledge. Cached on the tracker because
        # alias resolution is pure string work but runs every tick otherwise.
        if getattr(self, "_circuit_raw", None) != s.track:
            self._circuit_raw = s.track
            self._circuit = track_mod.Track(s.track)
        s.circuit = self._circuit
        s.track_len = si.mLapDist or 1.0

        # THE GAME'S OWN TRACK-LIMITS MESSAGE. rF2 writes the on-screen
        # warning text — "INVALID LAP - TRACK LIMITS", "CUT TRACK", and so on
        # — into `mStatusMessage` and bumps `mTicksStatusMessageUpdated` each
        # time a new one is posted. That is GROUND TRUTH from the sim itself,
        # not an inference from a speed drop, and until now nothing read it.
        #
        # `status_message_new` is True for exactly the tick the message
        # changed — edge-triggered (LAW 1), so a message that stays on screen
        # is not re-announced every tick it is displayed.
        #
        # IT LIVES IN THE EXTENDED BUFFER, NOT IN SCORING. This read was
        # written as `si.mStatusMessage` and `si` is `mScoringInfo`, which has
        # no such field — so it raised AttributeError on EVERY TICK, and
        # because the tracker read is the second thing `_tick_body` does, the
        # whole overlay drew nothing at all. The plugin puts the status
        # message, its tick counter and the history message in `rF2Extended`,
        # a separate memory map with its own handle.
        #
        # The extended buffer is optional in a way scoring is not: a user
        # running an older plugin build may not have it mapped, and `read()`
        # returns None for an absent mapping. So an absent buffer means no
        # ground truth and the surface detector carries the feature alone —
        # which is exactly how it behaved before this was written.
        ext = self.reader.extended()
        s.status_message = R.cstr(ext.mStatusMessage) if ext is not None else ""
        ticks = ext.mTicksStatusMessageUpdated if ext is not None else 0
        s.status_message_new = bool(
            s.status_message and ticks and ticks != self._status_ticks)
        if ticks:
            self._status_ticks = ticks
        s.session_index = si.mSession
        s.kind = R.session_kind(si.mSession)
        s.phase = si.mGamePhase
        # THE NUMBER WHEN THE NAME IS UNKNOWN. A log line reading "phase=?" was
        # the only clue to four separate attempts at the career prompt, and it
        # withheld the one thing that would have identified the problem.
        s.phase_name = _PHASE_NAMES.get(si.mGamePhase,
                                        "?%s" % si.mGamePhase)
        s.green = si.mGamePhase == R.GamePhase.GREEN
        s.countdown = si.mGamePhase in (R.GamePhase.FORMATION,
                                        R.GamePhase.COUNTDOWN,
                                        R.GamePhase.GRIDWALK)
        s.finished = si.mGamePhase == R.GamePhase.OVER
        s.started = si.mGamePhase >= R.GamePhase.GREEN

        # ON AIR — is there actually a session happening worth broadcasting?
        #
        # rF2 publishes a populated scoring buffer while the track is still
        # LOADING and while you sit in the garage, which meant the booth
        # opened the show and started talking over a loading screen. Two
        # conditions have to hold:
        #
        #   mInRealtime   the driver is on track, not in the menus. This is
        #                 the game's own answer to "is the sim running", and
        #                 it is False through loading and in the garage.
        #   phase         past GARAGE. Gridwalk onward is a real session.
        #
        # Everything that SPEAKS is gated on this. Panels still draw, because
        # a timing tower during a formation lap is useful and silent.
        s.on_air = bool(si.mInRealtime) and si.mGamePhase > R.GamePhase.GARAGE
        s.in_realtime = bool(si.mInRealtime)
        s.et = si.mCurrentET
        s.end_et = si.mEndET
        s.max_laps = si.mMaxLaps if 0 < si.mMaxLaps < 10000 else 0
        s.timed = not s.max_laps
        s.time_left = max(0.0, si.mEndET - si.mCurrentET) if si.mEndET > 0 else None
        s.num_cars = n
        s.air_temp = si.mAmbientTemp
        s.track_temp = si.mTrackTemp
        s.raining = si.mRaining
        s.wetness = si.mAvgPathWetness
        s.dark = si.mDarkCloud
        # Same for the overall state: -1 is Invalid, 0 is NoFlag.
        s.yellow = max(0, si.mYellowFlagState)
        s.full_course_yellow = si.mGamePhase == R.GamePhase.FCY
        # SECTOR FLAGS ARE NOT A YELLOW INDICATOR ON THEIR OWN.
        #
        # This has now been wrong twice. First `mSectorFlag` was passed
        # through raw, so -1 ("not reported") read as truthy and the booth
        # called phantom yellows for a whole race. Clamping negatives to zero
        # fixed that case and not the real one: in the 2026-08-16 live run the
        # field sat at 11/1/2 for the entire race while `mYellowFlagState` was
        # 0 and nothing whatever was happening —
        #
        #     FLAGS  yellow_state=0  sectors=(11, 11, 11)  fcy=False  green
        #
        # — so the overlay showed YELLOW SECTOR 1/2/3 permanently. Whatever
        # rF2 is publishing there, it is not a boolean "local yellow here".
        #
        # So the SESSION's own flag state is the authority on whether there is
        # a yellow at all, and the sector array is only consulted to say WHICH
        # sector once that is established. When the session says green, the
        # sectors are green, whatever numbers are in the array.
        raw_sectors = tuple(max(0, si.mSectorFlag[i]) for i in range(3))
        s.sector_flags_raw = raw_sectors
        flagged = s.yellow > 0 or s.full_course_yellow
        s.yellow_sectors = raw_sectors if flagged else (0, 0, 0)

        if n == 0:
            return s

        vs = [raw.mVehicles[i] for i in range(n)]

        # -- build cars ----------------------------------------------------
        for v in vs:
            c = self._build_car(v, tele.get(v.mID), s, si)
            s.cars[c.id] = c

        # -- running order --------------------------------------------------
        # Trust rF2's mPlace: it already applies the session's own rules
        # (race distance in a race, best lap in qualifying), which we would
        # otherwise have to reimplement per session type and get wrong.
        s.order = sorted(s.cars.values(),
                         key=lambda c: c.place if c.place > 0 else 9999)
        s.leader = s.order[0] if s.order else None

        # -- identity -------------------------------------------------------
        s.player = self._resolve_player(s, si)

        # -- era ------------------------------------------------------------
        s.classes = sorted({c.cls for c in s.order if c.cls})
        esig = tuple(s.classes)
        if esig != self._era_sig:
            self._era_sig = esig
            self._era = era_mod.field_era([(c.cls, c.vehicle) for c in s.order])
        s.era = self._era
        # A TEAM-NAMED GRID IS NOT A MULTICLASS RACE.
        #
        # Several F1 mods name `CarClass` per constructor, so a 2021 grid
        # arrives as ten "classes" called McLaren, Ferrari, Haas... and a
        # plain count says multiclass. It is one championship of twenty cars,
        # and treating it otherwise gave every driver a class position of
        # first or second — his position within his own two-car team.
        #
        # Harmless while nothing read `place_class`. The moment the booth
        # starts calling class positions it becomes "Verstappen leads the
        # race, and he is second in class", which is nonsense. `era.team_field`
        # is the same test career.py uses to tell the two apart.
        s.multiclass = (len(s.classes) > 1
                        and era_mod.team_field(s.classes) is None)
        s.player_era = (era_mod.classify(s.player.cls, s.player.vehicle,
                                         s.classes)
                        if s.player else s.era)

        # -- laps / distance -------------------------------------------------
        s.leader_laps = s.leader.laps if s.leader else 0
        if s.max_laps and s.leader:
            s.laps_left = max(0, s.max_laps - s.leader.laps)

        # -- timelines and gaps ---------------------------------------------
        for c in s.order:
            tl = self._timelines.get(c.id)
            if tl is None:
                tl = self._timelines[c.id] = _Timeline()
            # A car in the garage or pits is not making progress we can time
            # against; recording it would corrupt the interpolation.
            if not c.in_garage:
                tl.add(c.race_dist, s.et)
        self._compute_gaps(s)

        # -- class positions -------------------------------------------------
        if s.multiclass:
            per = {}
            for c in s.order:
                per.setdefault(c.cls, 0)
                per[c.cls] += 1
                c.place_class = per[c.cls]
        else:
            for c in s.order:
                c.place_class = c.place

        # -- grid, gains, purple ---------------------------------------------
        self._track_grid(s)
        self._track_bests(s)
        return s

    # -- per-car ------------------------------------------------------------
    def _build_car(self, v, t, s, si):
        c = Car()
        c.id = v.mID
        c.name = R.cstr(v.mDriverName)
        c.cls = R.cstr(v.mVehicleClass)
        c.vehicle = R.cstr(v.mVehicleName)
        c.place = v.mPlace
        c.laps = max(0, v.mTotalLaps)
        c.lap_dist = v.mLapDist
        # Cumulative distance. rF2 briefly reports the previous lap's
        # distance with the new lap count at the line, which would make the
        # value jump a full lap; clamping lap_dist into [0, track_len] keeps
        # it monotonic.
        ld = min(max(v.mLapDist, 0.0), s.track_len)
        c.race_dist = c.laps * s.track_len + ld
        c.in_pits = bool(v.mInPits)
        c.pit_state = v.mPitState
        c.pit_stops = v.mNumPitstops
        c.penalties = v.mNumPenalties
        # WHETHER THIS LAP WILL COUNT, straight from the sim.
        #
        # `mCountLapFlag`: 0 = do not count the lap, 1 = count the lap but not
        # its time, 2 = count both. Anything under 2 means the time is not
        # going on the timesheet — which is what a driver means by "they took
        # my lap away", and it is a NUMBER rather than a piece of on-screen
        # English that has to be pattern-matched.
        #
        # This finally gives `last_lap_valid` an honest source. It has been
        # declared in these slots and never assigned since the module was
        # written, which is exactly why the deleted-lap call was refused for
        # so long.
        c.count_lap = v.mCountLapFlag
        c.last_lap_valid = (v.mCountLapFlag >= 2)
        c.finish_status = v.mFinishStatus
        c.control = v.mControl
        c.is_player = bool(v.mIsPlayer)
        c.is_ai = v.mControl == R.Control.AI
        c.in_garage = bool(v.mInGarageStall)
        c.under_yellow = bool(v.mUnderYellow)
        c.blue_flag = v.mFlag == 6
        c.lap_start_et = v.mLapStartET
        c.time_into_lap = v.mTimeIntoLap
        c.est_lap = v.mEstimatedLapTime
        c.sector = SECTOR_FROM_RF2.get(v.mSector, 1)
        c.laps_down = v.mLapsBehindLeader
        # World position, for the track map. rF2's Y is vertical, so the
        # ground plane the map draws is (X, Z) — using (X, Y) would render
        # every circuit as a flat line at the elevation profile.
        c.pos = (v.mPos.x, v.mPos.z)

        c.best_lap = v.mBestLapTime if v.mBestLapTime > 0 else None
        c.last_lap = v.mLastLapTime if v.mLastLapTime > 0 else None
        c.cur_s1 = v.mCurSector1 if v.mCurSector1 > 0 else None
        c.cur_s2 = v.mCurSector2 if v.mCurSector2 > 0 else None
        c.last_s1 = v.mLastSector1 if v.mLastSector1 > 0 else None
        c.last_s2 = v.mLastSector2 if v.mLastSector2 > 0 else None
        # rF2 reports sector 2 as a CUMULATIVE split from the lap start, not
        # as a sector duration. Both the S2 shown on the tower and S3 have to
        # be derived, or every sector time after the first reads far too long.
        if c.last_s1 and c.last_s2 and c.last_s2 > c.last_s1:
            c.last_s2 = c.last_s2 - c.last_s1
        if c.last_lap and v.mLastSector2 > 0 and c.last_lap > v.mLastSector2:
            c.last_s3 = c.last_lap - v.mLastSector2
        # mBestLapSector1/2 are the sectors OF THE BEST LAP, not the driver's
        # best individual sectors, so the three add up to `best_lap` and the
        # third is derivable. That distinction is the whole reason these are
        # safe to talk about: a "theoretical best" split into three sectors
        # from three different laps describes a lap nobody drove.
        c.best_s1 = v.mBestLapSector1 if v.mBestLapSector1 > 0 else None
        bs2 = v.mBestLapSector2
        if c.best_s1 and bs2 > c.best_s1:
            c.best_s2 = bs2 - c.best_s1
        if c.best_lap and bs2 > 0 and c.best_lap > bs2:
            c.best_s3 = c.best_lap - bs2

        if t is not None:
            lv = t.mLocalVel
            c.speed = (lv.x ** 2 + lv.y ** 2 + lv.z ** 2) ** 0.5 * 3.6
            c.fuel = t.mFuel
            c.fuel_cap = t.mFuelCapacity
            c.rpm = t.mEngineRPM
            c.max_rpm = t.mEngineMaxRPM
            c.gear = t.mGear
            c.car_number = None
            c.tyre_front = R.cstr(t.mFrontTireCompoundName)
            c.tyre_rear = R.cstr(t.mRearTireCompoundName)
            c.damage = tuple(t.mDentSeverity)
            c.tyre_wear = tuple(w.mWear for w in t.mWheels)
            c.tyre_temp = tuple(
                R.kelvin_c(sum(w.mTemperature) / 3.0) for w in t.mWheels)
            c.brake_temp = tuple(R.kelvin_c(w.mBrakeTemp) for w in t.mWheels)
            c.flap = t.mRearFlapActivated
            c.battery = t.mBatteryChargeFraction
            c.headlights = bool(t.mHeadlights)
            # Per-wheel surface. This is the one thing rF2 gives us that the
            # RaceRoom overlay never had: an excursion is a FACT here, not an
            # inference from a speed drop. A car that runs wide onto tarmac
            # runoff and keeps its foot in loses no speed at all, so the old
            # speed-drop detector was silent for exactly the moments a booth
            # most wants to call.
            c.surface = tuple(w.mSurfaceType for w in t.mWheels)
            c.wheels_off = sum(1 for x in c.surface
                               if x not in ON_TRACK_SURFACES)
        else:
            c.tyre_wear = (1.0, 1.0, 1.0, 1.0)
            c.tyre_temp = (None,) * 4
            c.brake_temp = (None,) * 4
            c.damage = (0,) * 8

        c.display_name = self._nice_name(c)
        return c

    def _nice_name(self, c):
        """The name we are willing to say out loud.

        rF2's stock profile leaves the human driver called "Your Name". The
        overlay substitutes the configured name, and failing that falls back
        to something an engineer can plausibly say rather than reading the
        placeholder aloud.
        """
        if c.is_player or c.control == R.Control.PLAYER:
            if self.display_name:
                return self.display_name
            if is_placeholder(c.name):
                return "Driver"
        if is_placeholder(c.name):
            return "Car %d" % (c.place or 0)
        return c.name

    # -- identity -----------------------------------------------------------
    def _resolve_player(self, s, si):
        """Who are we following?

        mIsPlayer is the right answer when driving. In a replay or on the
        monitor nothing is flagged, so fall back through control type, then
        the profile name, then the leader — an overlay following nobody is
        worse than one following the front of the race.
        """
        for c in s.order:
            if c.is_player:
                return c
        for c in s.order:
            if c.control == R.Control.PLAYER:
                return c
        pname = R.cstr(si.mPlayerName)
        if pname and not is_placeholder(pname):
            for c in s.order:
                if c.name == pname:
                    return c
        return s.leader

    # -- gaps ---------------------------------------------------------------
    def _compute_gaps(self, s):
        """Time gaps by asking when the car ahead stood where this car is now.

        Falls back to a distance/speed estimate only when the timeline cannot
        answer (first seconds of a session, or a car that just left the pits),
        because a plausible estimate beats a blank column.
        """
        leader = s.leader
        for i, c in enumerate(s.order):
            c.gap_leader = 0.0 if c is leader else self._gap_between(leader, c, s)
            ahead = s.order[i - 1] if i > 0 else None
            c.gap_ahead = self._gap_between(ahead, c, s) if ahead else 0.0
        for i, c in enumerate(s.order):
            behind = s.order[i + 1] if i < len(s.order) - 1 else None
            c.gap_behind = behind.gap_ahead if behind else 0.0

    def _gap_between(self, ahead, behind, s):
        if ahead is None or behind is None or ahead is behind:
            return 0.0
        delta = ahead.race_dist - behind.race_dist
        # Lapped cars: report the time gap on the road, and let laps_down
        # carry the lap difference. Mixing the two produces the classic
        # "+1:23.456" that is really a lap and a bit.
        if delta > s.track_len:
            delta = delta % s.track_len
        tl = self._timelines.get(ahead.id)
        if tl is not None:
            t_then = tl.time_at(behind.race_dist)
            if t_then is not None:
                g = s.et - t_then
                if 0.0 <= g < 600.0:
                    return g
        spd = max(behind.speed or 0.0, 30.0) / 3.6
        return max(0.0, delta) / spd

    # -- grid and gains ------------------------------------------------------
    def _track_grid(self, s):
        """Remember the starting order once, then report places gained.

        Captured at the last moment before the green rather than on the first
        green tick, because rF2 shuffles places during the formation lap.

        ONLY A SANE ORDER IS EVER CAPTURED. In the garage, and for a tick or
        two either side of a session change, rF2 reports P255 for cars that
        have no position yet — the 2026-08-16 log is full of

            SANITY FAIL places not contiguous 1..N: [255, 255, 255, ...]

        Captured as a grid, that turns into `places_gained = 254`, and the
        booth then reports overtake counts and recovery drives that never
        happened. A snapshot with any nonsense in it is discarded whole
        rather than partly trusted: half a grid is not a grid.
        """
        n = len(s.order)
        if not s.started and n:
            places = [c.place for c in s.order]
            sane = (all(0 < p <= n for p in places)
                    and len(set(places)) == n)
            if sane:
                self._grid = {c.id: c.place for c in s.order}
        for c in s.order:
            c.started_place = self._grid.get(c.id) or 0
            # No grid means no claim. Reporting zero gains is honest;
            # inventing them from a placeholder is not.
            c.places_gained = ((c.started_place - c.place)
                               if c.started_place else 0)

    def _track_bests(self, s):
        """Session-best lap and sectors, and the purple flags that follow."""
        for c in s.order:
            if c.best_lap and (self._best_lap is None
                               or c.best_lap < self._best_lap - 1e-4):
                self._best_lap = c.best_lap
                self._best_lap_id = c.id
            for i, v in enumerate((c.last_s1, c.last_s2, c.last_s3)):
                if v and v > 0 and (self._best_s[i] is None
                                    or v < self._best_s[i] - 1e-4):
                    self._best_s[i] = v
        s.best_lap_time = self._best_lap
        s.best_s1, s.best_s2, s.best_s3 = self._best_s
        bl = s.cars.get(self._best_lap_id)
        s.best_lap_driver = bl.display_name if bl else None
        for c in s.order:
            c.purple_lap = bool(self._best_lap and c.best_lap
                                and abs(c.best_lap - self._best_lap) < 1e-4)
            c.purple_s1 = bool(self._best_s[0] and c.last_s1
                               and abs(c.last_s1 - self._best_s[0]) < 1e-4)
            c.purple_s2 = bool(self._best_s[1] and c.last_s2
                               and abs(c.last_s2 - self._best_s[1]) < 1e-4)
            c.purple_s3 = bool(self._best_s[2] and c.last_s3
                               and abs(c.last_s3 - self._best_s[2]) < 1e-4)

    # -- overtake confirmation ------------------------------------------------
    def confirmed_places(self, s):
        """Positions that have HELD for PLACE_CONFIRM_S.

        Two cars side by side at a timing line can swap places for a single
        scoring update. Reporting that as an overtake means the booth calls a
        pass and then immediately calls it back, which reads as a bug even
        though the data really did say so.
        """
        out = {}
        now = s.et
        for c in s.order:
            pend = self._place_pending.get(c.id)
            if pend is None or pend[0] != c.place:
                self._place_pending[c.id] = (c.place, now)
                out[c.id] = self._place_confirmed.get(c.id, c.place)
                continue
            if now - pend[1] >= PLACE_CONFIRM_S:
                self._place_confirmed[c.id] = c.place
            out[c.id] = self._place_confirmed.get(c.id, c.place)
        return out


def fmt_gap(g, laps_down=0):
    """Broadcast gap formatting: laps first, then time."""
    if laps_down and laps_down > 0:
        return "+%d LAP%s" % (laps_down, "" if laps_down == 1 else "S")
    if g is None:
        return "--.---"
    if g >= 60.0:
        return "+%d:%06.3f" % (int(g // 60), g % 60)
    return "+%.3f" % g


def _dump():
    """Live console view of the normalised session."""
    tr = SessionTracker()
    if not tr.plugin_present:
        print("Plugin buffers not found. Is rFactor 2 running?")
        print("Run  python verify_plugin.py  for a full diagnosis.")
        return
    while True:
        s = tr.update()
        if not s.valid:
            print("no scoring data...")
            time.sleep(1)
            continue
        print("\x1b[2J\x1b[H", end="")
        e = s.era
        print("%s  |  %s  |  phase=%s  cars=%d"
              % (s.track, s.kind.upper(), s.phase_name, s.num_cars))
        print("era: %s (%s %d, skin=%s)  caps=%s"
              % (e.label, e.discipline, e.year, e.skin,
                 ",".join(sorted(e.caps)) or "-"))
        if s.multiclass:
            print("MULTICLASS: %s" % ", ".join(s.classes))
        if s.max_laps:
            print("lap %d/%d" % (s.leader_laps + 1, s.max_laps))
        elif s.time_left is not None:
            print("time left %d:%02d" % (s.time_left // 60, s.time_left % 60))
        print("best lap %s by %s" % (R.fmt_time(s.best_lap_time),
                                     s.best_lap_driver or "-"))
        print("-" * 92)
        print("%2s %-22s %-16s %3s %10s %10s %9s %6s %s"
              % ("P", "DRIVER", "CLASS", "LAP", "INTERVAL", "LEADER",
                 "BEST", "KM/H", ""))
        for c in s.order[:24]:
            tag = ""
            if c is s.player:
                tag = "<-- YOU"
            elif c.in_pits:
                tag = "PIT"
            print("%2d %-22.22s %-16.16s %3d %10s %10s %9s %6.0f %s%s"
                  % (c.place, c.display_name, c.cls, c.laps,
                     fmt_gap(c.gap_ahead) if c.place > 1 else "LEADER",
                     fmt_gap(c.gap_leader, c.laps_down) if c.place > 1 else "-",
                     R.fmt_time(c.best_lap), c.speed or 0,
                     "*" if c.purple_lap else " ", tag))
        time.sleep(0.25)


if __name__ == "__main__":
    try:
        _dump()
    except KeyboardInterrupt:
        pass
