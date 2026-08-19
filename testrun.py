# -*- coding: utf-8 -*-
"""
FACTORtv — instrumented test run.

Launches the overlay with full logging so a real session can be reviewed
afterwards rather than remembered. Everything lands in `_session_log.txt`.

    python testrun.py

Then drive (or watch a replay), and quit with Ctrl+Shift+Q. The log is
written continuously, so it survives a crash or a hard kill.

What gets recorded, and why each matters for a first live run:

  PLUGIN     the three-stage self-check, so a bad run can be blamed on the
             plugin rather than on the overlay
  SESSION    track, session type, car count, and the ERA the detector chose —
             the single most likely thing to be wrong on unseen content
  SANITY     periodic assertions against live data: gaps monotonic down the
             order, sector times plausible, positions contiguous. These are
             the checks `verify_plugin.py` cannot make without a moving field
  EVENT      every booth/radio event detected, with the line chosen, so
             misfires and repetition are both visible after the fact
  ERROR      full tracebacks, which the live overlay deliberately swallows
"""
import os
import sys
import time
import traceback

_DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(_DIR, "_session_log.txt")

_t0 = time.time()


def log(tag, msg):
    line = "[%7.1fs] %-8s %s" % (time.time() - _t0, tag, msg)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
    except Exception:
        pass
    try:
        print(line)
    except Exception:
        pass


def banner(t):
    log("", "")
    log("====", t)


class Recorder(object):
    """Watches the overlay and writes down anything worth reviewing."""

    def __init__(self, ov):
        self.ov = ov
        self.last_sig = None
        self.last_sanity = 0.0
        self.last_heartbeat = 0.0
        self.spoken = []
        self.errors = 0
        self.max_cars = 0
        self.eras_seen = set()
        self._wrap_tts()

    def _wrap_tts(self):
        """Intercept speech so every aired line is logged with its persona."""
        real = self.ov.tts.speak

        def spy(text, persona="PLAY", intensity=0, seed=0, build=False,
                priority=1, name=""):
            self.spoken.append((time.time() - _t0, persona, text))
            log("SAY", "%-8s i=%d%s  %s" % (persona, intensity,
                                            " BUILD" if build else "", text))
            return real(text, persona, intensity=intensity, seed=seed,
                        build=build, priority=priority, name=name)
        self.ov.tts.speak = spy

        # STINGS TOO. They do not go through `speak` — they are pre-rendered
        # audio played straight from disk — so a log built only from `speak`
        # cannot answer the one question a test run is most often asked:
        # "did the welcome and the lights-out actually air?" Every line in the
        # first log of this session was a live render, and whether the intro
        # sting played was simply unknowable from it.
        bank = getattr(self.ov, "sting_bank", None)
        if bank is not None:
            real_play = bank.play

            def sting_spy(group, interrupt=False):
                text = real_play(group, interrupt=interrupt)
                if text:
                    self.spoken.append((time.time() - _t0, "STING", text))
                    log("STING", "%-8s %s%s"
                        % (group, "CUT-IN " if interrupt else "", text))
                else:
                    # A miss matters as much as a hit: it means the cache was
                    # not warm and the moment went out on a live render, or
                    # not at all.
                    log("STING", "%-8s (no clip cached)" % group)
                return text
            bank.play = sting_spy

    def tick(self, s):
        now = time.time()

        if s is None or not s.valid:
            if now - self.last_heartbeat > 15.0:
                self.last_heartbeat = now
                log("WAIT", "no session data (plugin present=%s)"
                    % self.ov.tracker.plugin_present)
            return

        sig = (s.track, s.session_index, s.phase, s.num_cars)
        if sig != self.last_sig:
            self.last_sig = sig
            e = s.era
            log("SESSION", "%s | %s | phase=%s | %d cars"
                % (s.track, s.kind, s.phase_name, s.num_cars))
            # ON AIR is the gate on everything the booth says, and it is the
            # usual explanation for a silent opening: rF2 reports
            # mInRealtime False until the driver is actually on track, which
            # on some entry paths is not until the green flag itself.
            # How many lines have dropped to the offline voice. A robotic
            # voice appearing "at random" is this number climbing, and
            # without it the only symptom is a user saying it sounded wrong.
            falls = getattr(self.ov.tts, "sapi_falls", 0)
            if falls:
                log("VOICE", "%d line(s) fell back to the offline voice"
                    % falls)
            log("ONAIR", "on_air=%s in_realtime=%s phase=%s"
                % (getattr(s, "on_air", "?"), getattr(s, "in_realtime", "?"),
                   s.phase_name))
            if e is not None:
                log("ERA", "%s  disc=%s year=%s skin=%s conf=%s"
                    % (e.key, e.discipline, e.year, e.skin, e.confidence))
                log("ERA", "  caps: %s" % (", ".join(sorted(e.caps)) or "none"))
                log("ERA", "  raw class: %r" % e.raw_class)
                self.eras_seen.add(e.key)
            if s.multiclass:
                log("ERA", "  MULTICLASS: %s" % ", ".join(s.classes))
            if s.player is not None:
                log("PLAYER", "%s  P%s  class=%r"
                    % (s.player.display_name, s.player.place, s.player.cls))

        self.max_cars = max(self.max_cars, s.num_cars)

        if now - self.last_heartbeat > 30.0:
            self.last_heartbeat = now
            me = s.player
            log("STATE", "lap %s/%s  P%s  fuel=%s  gap_ahead=%s  spoken=%d"
                % (s.leader_laps, s.max_laps or "-",
                   me.place if me else "-",
                   ("%.1f" % me.fuel) if me and me.fuel is not None else "-",
                   ("%.3f" % me.gap_ahead) if me and me.gap_ahead else "-",
                   len(self.spoken)))

        # Flag state changes, with the raw numbers. rF2 kept a sector flag
        # raised for a whole race and there was no way to tell from the log
        # whether that was real or a misread field.
        flags = (s.yellow, tuple(s.yellow_sectors), s.full_course_yellow)
        if flags != getattr(self, "_last_flags", None):
            self._last_flags = flags
            log("FLAGS", "yellow_state=%s sectors=%s fcy=%s phase=%s"
                % (s.yellow, s.yellow_sectors, s.full_course_yellow,
                   s.phase_name))

        if now - self.last_sanity > 20.0:
            self.last_sanity = now
            self._sanity(s)

    def _sanity(self, s):
        """Assertions that need a live, moving field.

        These are the checks the static verifier cannot make. A failure here
        usually means a struct offset is subtly wrong in a way that still
        produces plausible-looking numbers.
        """
        bad = []
        order = s.order
        if not order:
            return

        places = [c.place for c in order]
        if places != sorted(places):
            bad.append("order not sorted by place: %s" % places[:8])
        if places and places != list(range(1, len(places) + 1)):
            bad.append("places not contiguous 1..N: %s" % places[:8])

        # Gap to leader must not decrease as you go down the order.
        gl = [c.gap_leader for c in order if c.gap_leader is not None]
        drops = [i for i in range(1, len(gl)) if gl[i] < gl[i - 1] - 0.5]
        if drops:
            bad.append("gap-to-leader decreases at %d point(s)" % len(drops))

        for c in order:
            if c.lap_dist is not None and not (-50 <= c.lap_dist <= s.track_len + 50):
                bad.append("%s lap_dist %.0f outside track %.0f"
                           % (c.display_name, c.lap_dist, s.track_len))
            if c.best_lap and not (10.0 < c.best_lap < 900.0):
                bad.append("%s best lap implausible %.3f"
                           % (c.display_name, c.best_lap))
            if c.last_s1 and c.last_s2 and c.last_lap:
                tot = (c.last_s1 or 0) + (c.last_s2 or 0) + (c.last_s3 or 0)
                if abs(tot - c.last_lap) > 0.5:
                    bad.append("%s sectors %.3f do not sum to lap %.3f"
                               % (c.display_name, tot, c.last_lap))
            if c.speed is not None and not (0 <= c.speed < 450):
                bad.append("%s speed %.0f implausible" % (c.display_name, c.speed))

        me = s.player
        if me is not None:
            if me.tyre_wear and any(w is not None and not (0 <= w <= 1.0)
                                    for w in me.tyre_wear):
                bad.append("tyre wear outside 0..1: %s" % (me.tyre_wear,))
            if me.tyre_temp:
                ts = [t for t in me.tyre_temp if t is not None]
                if ts and not all(-30 < t < 350 for t in ts):
                    bad.append("tyre temps implausible: %s" % (ts,))
            if me.fuel is not None and me.fuel_cap and me.fuel > me.fuel_cap + 1:
                bad.append("fuel %.1f exceeds capacity %.1f"
                           % (me.fuel, me.fuel_cap))

        if bad:
            for b in bad[:6]:
                log("SANITY", "FAIL " + b)
        else:
            log("SANITY", "ok (%d cars, gaps/sectors/telemetry all plausible)"
                % len(order))

    def summary(self):
        banner("SUMMARY")
        log("RESULT", "ran %.1f minutes" % ((time.time() - _t0) / 60.0))
        log("RESULT", "eras seen: %s" % (", ".join(sorted(self.eras_seen)) or "none"))
        log("RESULT", "max cars: %d" % self.max_cars)
        log("RESULT", "lines spoken: %d" % len(self.spoken))
        falls = getattr(self.ov.tts, "sapi_falls", 0)
        log("RESULT", "offline-voice fallbacks: %d%s"
            % (falls, "  <-- edge-tts was failing" if falls else ""))
        log("RESULT", "errors: %d" % self.errors)
        if self.spoken:
            by = {}
            for _, p, _t in self.spoken:
                by[p] = by.get(p, 0) + 1
            log("RESULT", "by persona: %s"
                % ", ".join("%s=%d" % kv for kv in sorted(by.items())))
            texts = [t for _, _, t in self.spoken]
            uniq = len(set(texts))
            log("RESULT", "unique lines: %d / %d (%.0f%%)"
                % (uniq, len(texts), 100.0 * uniq / len(texts)))
            # Repetition is the thing most worth reviewing after a real race.
            counts = {}
            for t in texts:
                counts[t] = counts.get(t, 0) + 1
            rep = sorted(((n, t) for t, n in counts.items() if n > 1),
                         reverse=True)[:8]
            if rep:
                log("RESULT", "most repeated:")
                for n, t in rep:
                    log("RESULT", "   %dx  %s" % (n, t))
            banner("FULL TRANSCRIPT")
            for ts, p, t in self.spoken:
                log("LINE", "%7.1fs %-8s %s" % (ts, p, t))


def main():
    try:
        os.remove(LOG)
    except Exception:
        pass

    banner("FACTORtv TEST RUN  %s" % time.strftime("%Y-%m-%d %H:%M:%S"))

    # --- stage 1: the plugin -------------------------------------------------
    banner("PLUGIN CHECK")
    import rf2_data as R
    r = R.RF2Reader()
    if not r.open():
        # Waits indefinitely rather than timing out. This script is meant to be
        # launched BEFORE the game, and Steam plus the launcher plus loading a
        # session can easily exceed any timeout worth setting — a run that
        # gives up while the game is still loading is worse than useless.
        log("PLUGIN", "not found yet — waiting for rFactor 2.")
        log("PLUGIN", "  Start the game and load a session; this will attach.")
        log("PLUGIN", "  (Ctrl+C here to abort.)")
        waited = 0
        while not r.open():
            time.sleep(1.0)
            waited += 1
            if waited % 30 == 0:
                log("PLUGIN", "  still waiting... %dm%02ds"
                    % (waited // 60, waited % 60))
            if waited == 90:
                log("PLUGIN", "  NOTE: if the game is already running, the")
                log("PLUGIN", "  plugin did not load. rF2 reads its plugin list")
                log("PLUGIN", "  at startup ONLY — restart the game.")
        log("PLUGIN", "attached after %dm%02ds" % (waited // 60, waited % 60))
    ext = r.extended()
    log("PLUGIN", "OK — buffers open. plugin v%s dma=%s"
        % (R.cstr(ext.mVersion) if ext else "?",
           bool(ext.mDirectMemoryAccessEnabled) if ext else "?"))
    r.close()

    # --- stage 2: run --------------------------------------------------------
    banner("RUNNING (drive, then quit with Ctrl+Shift+Q)")
    import factor_tv
    ov = factor_tv.Overlay()
    rec = Recorder(ov)
    log("SETUP", "engine=%s  fonts=%s" % (ov.tts.engine, ov.f_small[0]))
    log("SETUP", "booth=%s radio=%s dash=%s"
        % (ov.booth_enabled, ov.radio_enabled, ov.show_dash))

    real_tick = ov._tick_body

    def wrapped():
        try:
            real_tick()
            rec.tick(getattr(ov, "_last_session", None))
        except Exception:
            rec.errors += 1
            log("ERROR", traceback.format_exc().replace("\n", " | ")[-2000:])
    ov._tick_body = wrapped

    # The overlay does not keep its session around; capture it as it goes.
    real_update = ov.tracker.update

    _seen_msgs = set()

    def capture():
        s = real_update()
        ov._last_session = s
        # EVERY STATUS MESSAGE rF2 PUBLISHES, ONCE EACH.
        #
        # The track-limits backstop and the deleted-lap call both key off the
        # sim's own on-screen text, and the exact wording is NOT documented
        # anywhere — the keyword lists in `overlay_booth` (the
        # `_track_limits_ground_truth` gate and `DELETED_WORDS`) are an
        # educated guess. One qualifying session with a few laps thrown away
        # settles it exactly, and guessing twice is worse than logging once.
        #
        # Logged de-duplicated: the same message is published for as long as
        # it is on screen, and a per-tick log would be the whole file.
        msg = getattr(s, "status_message", "") or ""
        if msg and msg not in _seen_msgs:
            _seen_msgs.add(msg)
            log("STATUSMSG", repr(msg))
        return s
    ov.tracker.update = capture

    try:
        ov.run()
    except KeyboardInterrupt:
        pass
    except Exception:
        rec.errors += 1
        log("ERROR", traceback.format_exc().replace("\n", " | ")[-2000:])
    finally:
        rec.summary()
        log("", "")
        log("DONE", "log written to %s" % LOG)
    return 0


if __name__ == "__main__":
    sys.exit(main())
