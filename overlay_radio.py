# -*- coding: utf-8 -*-
"""
FACTORtv — team radio.

Dean Mackenzie on the pit wall, and the radio cards that show what was said.

Dean is not a second commentator
-------------------------------
The booth narrates the race; Dean talks to YOU, about YOUR car, and only when
he has something you could act on. That distinction is enforced structurally
rather than by good intentions:

  * He only ever reads the player's telemetry. He never mentions a car he
    could not see on a timing screen, and never describes a battle he is not
    part of.
  * Every call is a STATE CHANGE, not a status report. "Fuel is fine" said
    every lap is noise; "fuel just went marginal" is information. Each check
    below tracks what it last told you and stays quiet until that changes.
  * Hysteresis on every threshold. A tyre hovering on the edge of "worn"
    would otherwise trigger a call every time it crossed back and forth.

The information/annoyance tradeoff is the whole design. An engineer who
speaks constantly gets muted, at which point he conveys nothing at all.
"""
import os
import time

import cast as cast_mod
import lines as lines_mod
from overlay_common import (EDGE, STRIKE_GAP, TH, UI, bubble_h, shade,
                            spoken_gap, spoken_lap,
                            spoken_place as _spoken)

# Minimum gap between ANY two engineer calls. Longer than the booth's,
# because radio interrupts the driver rather than accompanying the picture.
# Radio card geometry, at 1.0x UI scale. `RADIO_TEXT_INSET` is the distance
# from the card's left edge to the start of the text — the accent spine, the
# padding and the speaker icon — and both the wrapping and the drawing derive
# from it so they cannot disagree about how much room the words have.
RADIO_CARD_W = 340
RADIO_TEXT_INSET = 58
RADIO_LINE_H = 19

# QUALIFYING. The engineer's window on a timed session.
QUALI_LAST_CALL = 150.0     # seconds left when "one more lap" is worth saying
QUALI_SECTOR_MIN = 0.08     # below this a sector deficit is noise
QUALI_SECTOR_SHARE = 0.55   # ...and it must dominate, or he is just slower
# A lap only counts as "scruffy" if it was a real attempt. Outside this band
# it is an out-lap, an in-lap or an aborted run, none of which are worth a
# word — and all of which he was commenting on.
SCRUFFY_MIN = 1.001
SCRUFFY_MAX = 1.020
# How much the sector deficit must move before the same diagnosis is worth
# repeating. Below this it is the same sentence about the same problem.
SECTOR_NEWS = 0.15

# How long before the SAME sector diagnosis is worth repeating. Four minutes:
# long enough that it is not nagging, short enough that a driver working on
# one part of the lap hears it more than once in a session. Capped for the
# session by TOPIC_MAX as well — see the re-arm comment in `_quali_radio`.
SECTOR_REPEAT = 240.0

# THE SLIDE DOWN THE ORDER. How many places the player has to lose, against
# the best he has held recently, before the engineer says anything about it.
# Three, and it has to HOLD: rF2 republishes scrambled-but-valid orders around
# a restart and at session changes (see the rF2 quirks table), and a call
# about four places lost that were never lost is worse than silence.
PLACES_SLID = 3
PLACES_SLID_HOLD = 6.0     # seconds the drop must persist before he believes it
PLACES_SLID_GAP = 150.0    # and how long before he will mention it again

RADIO_COOLDOWN = 8.0
URGENT_RADIO_COOLDOWN = 4.0

# Per-topic cooldowns. Deliberately long: these are conditions that persist,
# and repeating them does not make them more true.
TOPIC_COOLDOWN = {
    "fuel": 75.0, "tyres": 70.0, "temps": 60.0, "damage": 45.0,
    "gap": 40.0, "defend": 25.0, "limits": 30.0, "pit": 20.0,
    "encourage": 110.0, "pace": 55.0, "energy": 60.0, "flag": 30.0,
    "brakes": 150.0,
    "incident": 30.0, "recovery": 90.0,
    # Tied to completing a lap rather than to a clock, so these are floors
    # against two quick laps in a row, not the thing that paces them.
    "q_lap": 8.0, "q_sector": 70.0, "q_flag": 300.0, "q_miss": 45.0,
    "q_time": 8.0,
    # The every-lap race readout. A floor only — it is paced by crossing the
    # line, not by a clock — but long enough that a short circuit does not
    # get a call every forty seconds on top of everything else.
    "lapinfo": 55.0,
}

# HOW MANY TIMES HE MAY RAISE THE SAME SUBJECT IN ONE SESSION.
#
# A cooldown paces a repeated call; it does not stop one. Brake temperature,
# tyre temperature and track limits are CONDITIONS — they persist for a whole
# race, and a driver who is told about them nine times has been told nothing
# eight times. The live run had brakes mentioned fifteen times.
#
# Only nagging topics are capped. Anything the driver can act on right now
# (fuel, the car behind, a pit call, the flag) is uncapped, because those are
# information rather than commentary on his driving.
TOPIC_MAX = {
    "brakes": 3, "temps": 3, "limits": 3, "tyres": 4, "pace": 4,
    "encourage": 2, "recovery": 2,
    # Coaching is welcome and still finite. Four sector calls is a session's
    # worth of "you are losing it here"; beyond that he is repeating himself
    # at a driver who has already heard him.
    "q_sector": 4, "slide": 3,
}

# How far back to look for the place you held BEFORE an off. Long enough to
# cover the excursion and the cars streaming past, short enough that it is not
# reaching back into an unrelated part of the race.
OFF_LOOKBACK_S = 20.0
RECOVERY_MIN_S = 25.0      # don't call it a recovery ten seconds later
RECOVERY_GIVEUP_S = 420.0  # after seven minutes it is just the race

# Thresholds, with separate trigger and clear points so a value sitting on
# the boundary cannot chatter.
TYRE_WORN = 0.45
TYRE_WORN_CLEAR = 0.55
TYRE_GONE = 0.22
# A threat is "gone" well beyond the strike gap, not just outside it. Clearing
# at STRIKE_GAP itself would let a gap oscillating around 0.8s re-arm the
# defend call every few seconds, which is the repetition it exists to stop.
STRIKE_CLEAR = 2.5
TYRE_COLD_C = 55.0
TYRE_HOT_C = 115.0
BRAKE_HOT_C = 700.0
# ...AND THE POINT AT WHICH HE IS ALLOWED TO WORRY AGAIN.
#
# There was no clear threshold at all: above 700 armed the warning and
# anything at or below re-armed it. Brake temperature crosses 700 on EVERY
# LAP of a circuit like Montreal — hot into the chicane, cooling down the
# straight — so the engineer re-warned every lap. Fifteen of his forty-five
# lines in the live run were about brakes, in three sentences repeated three
# times each, and that is the whole of the "monotone and repetitive"
# complaint. He has to see them genuinely COOL before he mentions it again.
BRAKE_HOT_CLEAR = 560.0
FUEL_TIGHT_L = 1.5      # litres of margin below which fuel is "tight"
FUEL_CRITICAL_L = -0.5

RADIO_HOLD = 7.0        # how long a radio card stays on screen

# How long a card waits for its line to become audible before being dropped.
# A render can fail, and a session change flushes the audio queue — either
# way the card must not survive to ambush the next session with a message
# about a race that has already finished. Comfortably longer than the worst
# observed render (2-6s) plus anything queued ahead of it.
CARD_WAIT_MAX = 25.0

# --------------------------------------------------------------------------
# HOW HE SOUNDS
#
# The user said Dean was "very monotone and a bit robotic". Half of that was
# REPETITION and is fixed elsewhere (BRAKE_HOT_CLEAR, TOPIC_MAX). The other
# half is his REGISTER: 381 lines averaging eight words, a quarter of them
# using the driver's name and one in ten containing a warm word. That is a
# dashboard being read aloud.
#
# Real pit-to-car radio is not wordier than that — it is FRAMED. An engineer
# opens with the driver's name, acknowledges, and softens an instruction he
# does not need answered this second.
#
# So rather than rewriting 381 lines into something longer, the information
# is wrapped. `_frame()` prepends an opener some of the time, which is how
# the real thing sounds: the same clipped fact, delivered by a person.
FRAME_CHANCE = 0.45

# `{drv}` here is the FIRST NAME (see `_rkw`) — an engineer says "okay
# Lando", never "okay Lando Norris".
#
# NOTHING HERE ACKNOWLEDGES THE DRIVER. "Understood" and "copy that" were the
# obvious openers and both are wrong for this product: rival and driver radio
# were removed, so the player never transmits and Dean has nothing to be
# acknowledging. An engineer replying to silence is worse than a flat one.
# How long the pit wall waits for the driver's own race to end before it signs
# him off anyway. A car coasting to the line takes tens of seconds; one parked
# in the garage never finishes at all, and he is still owed a word.
ENG_FINISH_WAIT = 45.0

ENG_OPENERS = [
    "Okay {drv},", "Right,", "{drv},", "Okay,", "Right then,",
    "So,", "{drv} —", "Listen,", "Now then,",
]


class _Msg(object):
    __slots__ = ("who", "name", "text", "at", "colour", "icon")

    def __init__(self, who, name, text, at, colour, icon=None):
        self.who, self.name, self.text = who, name, text
        self.at, self.colour, self.icon = at, colour, icon


# TRACK LIMITS detection. Same inference the booth uses for an excursion — a
# hard speed drop with the car still moving — and the same conservatism: a
# missed one costs nothing, an invented one makes the engineer a nag.
LIMITS_DROP = 30.0          # km/h lost in one tick
LIMITS_SPEED = 130.0        # ...and still under this afterwards
LIMITS_WARN = 2             # excursions before he mentions it
LIMITS_SERIOUS = 4          # ...and before he gets firm about it
LIMITS_RESET = 300.0        # a clean five minutes wipes the slate


class RadioMixin(object):

    def radio_init(self):
        self._radio_last = 0.0
        self._topic_last = {}
        self._topic_n = {}         # topic -> how often he has raised it
        self._framed_last = False  # was the last call framed? never two running
        self._msgs = []
        self._eng_state = {}       # topic -> last state reported
        self._greeted = False
        self._eng_said_start = False
        self._eng_said_finish = False
        self._eng_flag_at = None
        self._prev_player = None
        self._icons = _load_icons()
        # Cards waiting for their line to become audible. See `_push_msg`.
        self._pending_cards = []

    def radio_new_session(self):
        """Forget what was said in the session that just ended.

        The per-topic budget and the state machine are both SESSION-scoped:
        having already mentioned the brakes three times in qualifying must not
        silence the engineer for the race. Named with the `radio_` prefix
        because the booth has its own `_new_session` and LAW 9 exists.
        """
        self._topic_n = {}
        self._topic_last = {}
        self._eng_state = {}
        self._pending_cards = []
        # Rival state is session-scoped too: a catchphrase used in qualifying
        # must be available again for the race, and the end-of-session card
        # has to be able to fire once more. Guarded because the rival mixin
        # is optional on a host that only wants the engineer.
        if hasattr(self, "_quoted"):
            self._quoted = set()
            self._rival_result_done = False
            self._rival_seen = {}
        self._greeted = False
        self._eng_said_start = False
        self._eng_said_finish = False
        self._eng_flag_at = None
        self._prev_player = None

    # -- main ----------------------------------------------------------------
    # -- the first-run introduction -------------------------------------------
    #
    # Between two lines of it the player is looking at a caption and a marked
    # button, which is the only teaching this product does. The rules it has to
    # hold are in `tutorial.py`; this is the loop.
    TUT_GAP = 1.1            # a beat between lines, so nine do not run together

    def update_tutorial(self, s):
        """Speak the next line of the introduction, if it is owed one.

        DRIVEN FROM ABOVE THE ON-AIR GATE, because the whole point is that it
        happens before he goes on track — in the garage, or on the menu with no
        session at all. `update_radio` returns immediately when off air, which is
        exactly when this has to work.
        """
        import tutorial as tut
        cfg = getattr(self, "cfg", None)
        if cfg is None or tut.done(cfg):
            return
        if not getattr(self, "radio_enabled", True):
            # NO VOICE, NO LESSON. A player who has switched the engineer off has
            # said something, and shouting the introduction at him anyway is not
            # a welcome. It stays owed until he turns him back on.
            return
        # NEVER OVER A GREEN FLAG. `s` is None on the menu, which is the calmest
        # moment there is and a fine time to talk.
        if s is not None and (getattr(s, "started", False)
                              or getattr(s, "green", False)):
            return
        script = tut.steps()
        i = getattr(self, "_tut_i", 0)
        if i >= len(script):
            if tut.mark_done(cfg):
                self._tut_save()
            self._tut_point = ""
            return
        now = time.time()
        if getattr(self, "tts", None) is not None and self.tts.speaking:
            return
        if now - getattr(self, "_tut_last", 0.0) < self.TUT_GAP:
            return
        step = script[i]
        try:
            self.tts.speak(step["t"], cast_mod.ENGINEER, intensity=0)
            self._push_msg(cast_mod.ENGINEER, step["t"], now)
        except Exception:
            # A VOICE THAT WILL NOT PLAY MUST NOT WEDGE THE INTRODUCTION. The
            # caption is the half that teaches; losing the audio costs a line,
            # never the sequence (LAW 22).
            pass
        self._tut_point = step.get("point") or ""
        self._tut_i = i + 1
        self._tut_last = now

    def tutorial_stop(self, heard=False):
        """Skip the rest of it. A click is an answer, so skipping counts."""
        import tutorial as tut
        self._tut_i = len(tut.steps())
        self._tut_point = ""
        if tut.mark_done(getattr(self, "cfg", None)):
            self._tut_save()

    def tutorial_replay(self):
        """Hand it back, from the top."""
        import tutorial as tut
        tut.replay(getattr(self, "cfg", None))
        self._tut_i = 0
        self._tut_last = 0.0
        self._tut_point = ""
        self._tut_save()

    def _tut_save(self):
        try:
            import factor_tv
            factor_tv.save_settings(self.cfg)
        except Exception:
            pass

    def update_radio(self, s):
        if not self.radio_enabled or s is None or not s.valid:
            return
        if not getattr(s, "on_air", True):
            return
        me = s.player
        if me is None:
            return
        now = time.time()
        era = s.player_era or s.era

        events = self._engineer_events(s, me, era, now)
        self._prev_player = _PlayerSnap(me)
        if not events:
            return
        events.sort(key=lambda e: -e[0])
        for prio, topic, cat, kw in events:
            if self._radio(cat, topic, kw, s, now, prio):
                return

    # -- the engineer ---------------------------------------------------------
    def _engineer_events(self, s, me, era, now):
        """Everything Dean might say, as (priority, topic, category, slots).

        Each check returns a call only on a CHANGE of state, which is what
        keeps him from reading the same dashboard aloud every lap.
        """
        out = []
        p = self._prev_player

        # --- session bookends ------------------------------------------------
        # THE GREETING BELONGS TO PRACTICE AND QUALIFYING, NOT THE RACE.
        #
        # There is no room for it on a grid: the gap between going on air and
        # lights out is a few seconds, and the booth owns those — a welcome,
        # the circuit, the grid, the start. An engineer talking across that is
        # clutter, and in the live run he lost the race to it anyway.
        #
        # `_greeted` is set only once the line has ACTUALLY AIRED. It used to
        # be set the moment the greeting was offered, so when `_radio` refused
        # it — cooldown, or something more urgent that tick — the greeting was
        # discarded and never came back. That is why he "barely talks" at the
        # start of a session.
        if (not self._greeted and s.kind in ("quali", "practice")
                and self._radio_ready(now)):
            cat, kw = self._greet_career(s, me)
            if self._radio(cat, "greet", kw, s, now, 10):
                self._greeted = True
            return []

        # QUALIFYING IS HIS SESSION TOO. Everything below this point is about
        # a race — fuel to the flag, tyre life, the car behind — and none of
        # it applies to a timed run, so he greeted the driver and then went
        # silent for twenty minutes.
        if s.kind in ("quali", "practice", "test"):
            return self._quali_radio(s, me, p, now)

        if s.green and s.kind == "race" and not self._eng_said_start:
            # AFTER LIGHTS OUT, not before. This is his first word of a race
            # and it is worth more here — by now there is something to say
            # about how the start actually went.
            self._eng_said_start = True
            self._greeted = True
            gained = me.places_gained or 0
            if gained > 0:
                return [(90, "start", "eng_start_gain",
                         self._rkw(s, me, n=gained,
                                   pos=_spoken(me.place)))]
            if gained < 0:
                return [(90, "start", "eng_start_loss",
                         self._rkw(s, me, pos=_spoken(me.place)))]
            return [(90, "start", "eng_start",
                     self._rkw(s, me, pos=_spoken(me.place)))]

        if s.finished and not self._eng_said_finish:
            # HIS RACE MAY NOT BE OVER YET, AND THE FLAG IS NOT HIS.
            #
            # This fired the instant the WINNER crossed the line and read out
            # `me.place` — which for a driver still on the road is where he
            # happens to be, not where he finished. The user's log: "P4 at the
            # end. Good, honest race, Dante." while he was coasting on an empty
            # tank, twelve seconds before he was classified TENTH.
            #
            # So it waits for the game's own answer (`mFinishStatus`), with a
            # cap so a driver who parks in the garage still gets signed off.
            # The flag is a moment for the BOOTH — the race really has ended —
            # and the pit wall's summary of HIS afternoon is a different thing,
            # owed a few seconds later.
            if (not getattr(me, "finish_status", 0)
                    and (now - (self._eng_flag_at or now)) < ENG_FINISH_WAIT):
                if self._eng_flag_at is None:
                    self._eng_flag_at = now
                return out
            self._eng_said_finish = True
            if me.place == 1:
                return [(100, "finish", "eng_win", self._rkw(s, me))]
            if me.place <= 3:
                return [(100, "finish", "eng_podium", self._rkw(s, me))]
            cat = "eng_finish_good" if me.place <= 10 else "eng_finish_poor"
            return [(100, "finish", cat, self._rkw(s, me))]

        if not s.green:
            return out

        if s.max_laps and s.laps_left == 1:
            out.append((85, "flag", "eng_lastlap", self._rkw(s, me)))

        # --- damage -----------------------------------------------------------
        dents = list(me.damage or ())
        if dents:
            worst = max(range(len(dents)), key=lambda i: dents[i])
            sev = dents[worst]
            # The peak has to come DOWN when the car is repaired. It only ever
            # ratcheted up, so after one heavy hit and a stop to fix it, fresh
            # damage below that old peak was never reported for the rest of
            # the race — the engineer went quiet exactly when he was needed.
            if sev < self._eng_state.get("damage", 0):
                self._eng_state["damage"] = sev
            if sev > self._eng_state.get("damage", 0):
                self._eng_state["damage"] = sev
                from overlay_dash import DAMAGE_ZONES
                zone = DAMAGE_ZONES[worst] if worst < len(DAMAGE_ZONES) else ""
                cat = "eng_damage_heavy" if sev > 1 else "eng_damage_light"
                out.append((80 if sev > 1 else 55, "damage", cat,
                            self._rkw(s, me, zone=zone)))

        # --- fuel --------------------------------------------------------------
        # Only meaningful once the burn model has measured real laps, and only
        # in a race — nobody needs a fuel strategy in practice.
        if s.kind == "race" and me.fuel is not None:
            need = s.laps_left
            margin = self.fuel_model.enough_for(me.fuel, need)
            if margin is not None and need:
                state = ("critical" if margin < FUEL_CRITICAL_L
                         else "tight" if margin < FUEL_TIGHT_L else "ok")
                if state != self._eng_state.get("fuel"):
                    prev = self._eng_state.get("fuel")
                    self._eng_state["fuel"] = state
                    if state == "critical":
                        short = max(1, int(abs(margin) /
                                           max(0.1, self.fuel_model.per_lap or 1)))
                        out.append((88, "fuel", "eng_fuel_critical",
                                    self._rkw(s, me, n=short)))
                    elif state == "tight":
                        out.append((60, "fuel", "eng_fuel_tight",
                                    self._rkw(s, me)))
                    elif prev in ("tight", "critical"):
                        # Only worth saying "we're fine now" if he previously
                        # told you it was a problem.
                        out.append((40, "fuel", "eng_fuel_save_ok",
                                    self._rkw(s, me)))

        # --- tyres -------------------------------------------------------------
        wear = [w for w in (me.tyre_wear or ()) if w is not None]
        if wear and era.has("slicks") or wear:
            lo = min(wear)
            state = self._eng_state.get("tyres", "ok")
            if lo < TYRE_GONE and state != "gone":
                self._eng_state["tyres"] = "gone"
                out.append((78, "tyres", "eng_tyres_gone", self._rkw(s, me)))
            elif lo < TYRE_WORN and state == "ok":
                self._eng_state["tyres"] = "worn"
                out.append((50, "tyres", "eng_tyres_worn",
                            self._rkw(s, me, pct=int(lo * 100))))
            elif lo > TYRE_WORN_CLEAR and state != "ok":
                # Hysteresis gap, and a fresh set after a stop.
                self._eng_state["tyres"] = "ok"

        temps = [t for t in (me.tyre_temp or ()) if t is not None]
        if temps and me.laps > 0:
            hot = max(temps)
            cold = min(temps)
            tstate = self._eng_state.get("temps", "ok")
            if hot > TYRE_HOT_C and tstate != "hot":
                self._eng_state["temps"] = "hot"
                out.append((45, "temps", "eng_tyre_hot", self._rkw(s, me)))
            elif cold < TYRE_COLD_C and tstate != "cold":
                self._eng_state["temps"] = "cold"
                out.append((45, "temps", "eng_tyre_cold", self._rkw(s, me)))
            elif TYRE_COLD_C < cold and hot < TYRE_HOT_C:
                self._eng_state["temps"] = "ok"

        brakes = [b for b in (me.brake_temp or ()) if b is not None]
        if brakes:
            hot_b = max(brakes)
            if hot_b > BRAKE_HOT_C and self._eng_state.get("brakes") != "hot":
                self._eng_state["brakes"] = "hot"
                out.append((42, "brakes", "eng_brakes_hot", self._rkw(s, me)))
            elif hot_b < BRAKE_HOT_CLEAR:
                # Only once they have genuinely cooled. Anything between the
                # two thresholds leaves the state alone, which is what stops
                # the every-lap re-arm.
                self._eng_state["brakes"] = "ok"

        # --- pit stop ----------------------------------------------------------
        if p is not None:
            if me.in_pits and not p.in_pits:
                self._eng_state["tyres"] = "ok"      # assume a fresh set
                self.fuel_model.reset()
            if not me.in_pits and p.in_pits:
                out.append((70, "pit", "eng_pit_out", self._rkw(s, me)))

        # --- racing -------------------------------------------------------------
        # A car sitting behind you is a CONDITION, not an event, and the topic
        # cooldown alone made it level-triggered (LAW 1): over a six-minute
        # battle a 25s cooldown aired "car behind is faster" thirteen times in
        # one race. He warns you once per THREAT — the same car has to fall out
        # of range (with hysteresis, so a gap hovering on the line cannot
        # chatter) or be replaced by somebody else before he says it again.
        behind = s.car_behind(me)
        threat = self._eng_state.get("defend")     # (slot, armed?)
        if behind is not None and not behind.in_pits:
            g = behind.gap_ahead or 99.0
            who, armed = threat if threat else (None, False)
            if behind.id != who:                   # a new car is the threat
                who, armed = behind.id, False
            if g > STRIKE_CLEAR:
                armed = False                      # dropped away — re-arm
            elif g < STRIKE_GAP and not armed:
                armed = True
                out.append((72, "defend", "eng_defend",
                            self._rkw(s, me, rival=behind, gap=spoken_gap(g))))
            self._eng_state["defend"] = (who, armed)
        else:
            self._eng_state.pop("defend", None)

        ahead = s.car_ahead(me)
        if ahead is not None and not ahead.in_pits and p is not None:
            g = me.gap_ahead or 99.0
            was = p.gap_ahead or 99.0
            if g < 6.0 and was - g > 0.25:
                out.append((38, "gap", "eng_gap_closing",
                            self._rkw(s, me, rival=ahead, gap=spoken_gap(g))))
            elif g < 12.0 and g - was > 0.25:
                out.append((30, "gap", "eng_gap_losing",
                            self._rkw(s, me, rival=ahead, gap=spoken_gap(g))))
            if era.has("drs") and g < 1.0:
                out.append((34, "energy", "eng_drs_available", self._rkw(s, me)))

        # --- excursions and recovery ---------------------------------------------
        # A rolling place history. The place at the MOMENT of an off is already
        # the damaged one — by the time all four wheels are back on the tarmac
        # the cars behind have gone by — so the recovery target has to come
        # from before it happened.
        hist = self._eng_state.setdefault("places", [])
        hist.append((now, me.place))
        del hist[:max(0, len(hist) - 400)]

        # Published by the booth's surface-truth detector so there is exactly
        # one place that decides what an excursion IS. Consumed here, which is
        # what stops a single off being reported twice.
        off = getattr(self, "player_off", None)
        if off is not None:
            kind, _at = off
            self.player_off = None
            if kind in ("spin", "offtrack", "ranwide") and s.green:
                was = min([pl for t, pl in hist if now - t < OFF_LOOKBACK_S]
                          or [me.place])
                self._eng_state["off_place"] = was
                self._eng_state["off_at"] = now
                # SEVERITY DECIDES THE TONE, and this was the missing half of
                # the engineer's off-track response.
                #
                # A spin or a real excursion (all four wheels off) is a
                # moment he has to check you are all right about — "are you
                # okay? talk to me". A tidy-up that ran wide or clipped a
                # track-limits line cost places, not confidence, and asking
                # if the driver is okay about THAT reads as him not having
                # watched what actually happened. He is encouraging instead:
                # "keep your head down and do what you can".
                if kind == "ranwide":
                    out.append((60, "incident", "eng_offtrack_light",
                                self._rkw(s, me)))
                else:
                    out.append((84, "incident", "eng_incident",
                                self._rkw(s, me)))

        # THE RECOVERY. He only offers one if there was something to recover
        # from — an off that cost you nothing gets no congratulations, because
        # praise for a place you never lost is worse than silence.
        was = self._eng_state.get("off_place")
        if was is not None and s.green:
            since = now - self._eng_state.get("off_at", 0.0)
            if me.place <= was and since > RECOVERY_MIN_S:
                self._eng_state.pop("off_place", None)
                out.append((40, "recovery", "eng_recovery",
                            self._rkw(s, me, pos=_spoken(me.place))))
            elif since > RECOVERY_GIVEUP_S:
                # He is not going to bring it up half an hour later.
                self._eng_state.pop("off_place", None)

        # --- THE SLIDE DOWN THE ORDER ------------------------------------------
        # The user's report: "the race engineer didn't pick up that I lost a
        # lot of places, he should be aware and tell me that I need to recover".
        #
        # He was aware of exactly one kind of place loss — the kind that
        # follows an off, tracked as `off_place` above. A driver who is simply
        # being passed, lap after lap, on old tyres or a bad balance, got
        # nothing: there was no call in the product for it. That is the most
        # ordinary bad afternoon in racing and the one a driver most wants
        # acknowledged.
        out.extend(self._slide_call(s, me, now))

        # --- WHERE THE LAP TIME IS GOING, IN A RACE ---------------------------
        # Sector coaching existed only in qualifying. Asked for directly: "I
        # didn't hear any of the track and sector coaching when I was in quali
        # or race session". A race is longer than a qualifying session and a
        # driver has far more laps to act on it, so withholding it there was
        # the wrong way round.
        out.extend(self._race_sector_call(s, me, p, now))

        # --- pace ---------------------------------------------------------------
        if p is not None and me.laps > p.laps and me.last_lap:
            if me.purple_lap:
                out.append((65, "pace", "eng_fastlap", self._rkw(s, me)))
            elif me.best_lap and abs(me.last_lap - me.best_lap) < 1e-3:
                out.append((44, "pace", "eng_pb",
                            self._rkw(s, me, t=spoken_lap(me.last_lap))))
            elif me.best_lap and me.last_lap > me.best_lap * 1.03:
                out.append((20, "pace", "eng_slow_lap", self._rkw(s, me)))
            else:
                out.append((15, "encourage", "eng_encourage", self._rkw(s, me)))

            # THE LAP READOUT, EVERY LAP.
            #
            # With the driver radio gone he is the only information channel
            # left, and a real engineer gives you your time and your position
            # every time you cross the line. He was only speaking when
            # something CHANGED, which over a race is a handful of calls.
            # Lower priority than any of the above, so a fastest lap or a
            # warning still wins the tick — this is what he says when there
            # is nothing more urgent, which is most laps.
            ahead = s.car_ahead(me)
            behind = s.car_behind(me)
            if ahead is not None and not ahead.in_pits:
                out.append((12, "lapinfo", "eng_lap_ahead",
                            self._rkw(s, me, rival=ahead,
                                      t=spoken_lap(me.last_lap),
                                      pos=_spoken(me.place),
                                      gap=self._qgap(me.gap_ahead))))
            elif behind is not None and not behind.in_pits:
                out.append((12, "lapinfo", "eng_lap_behind",
                            self._rkw(s, me, rival=behind,
                                      t=spoken_lap(me.last_lap),
                                      pos=_spoken(me.place),
                                      gap=self._qgap(behind.gap_ahead))))
            else:
                out.append((12, "lapinfo", "eng_lap_time",
                            self._rkw(s, me, t=spoken_lap(me.last_lap),
                                      pos=_spoken(me.place))))

        # --- officialdom ---------------------------------------------------------
        if me.penalties and me.penalties > self._eng_state.get("pens", 0):
            self._eng_state["pens"] = me.penalties
            out.append((82, "limits", "eng_penalty", self._rkw(s, me)))

        # TRACK LIMITS. `eng_limits_warn` and `eng_limits_serious` have been
        # sitting in the pool unused since the engineer was written, because
        # nothing counted excursions — so the only limits call he could ever
        # make was after a penalty had already been issued, which is too late
        # to be any use to the driver.
        #
        # rF2 exposes no "limits warning" count, so this is inferred the same
        # way the booth infers an excursion: a big speed drop while green and
        # out of the pits. Deliberately conservative, and it counts REPEATS
        # rather than reacting to each one — a single wide moment is racing,
        # a habit is what gets you a penalty.
        prev_speed = self._eng_state.get("speed")
        speed = getattr(me, "speed", None) or 0.0
        self._eng_state["speed"] = speed
        if (prev_speed and s.green and not me.in_pits
                and prev_speed - speed > LIMITS_DROP
                and speed < LIMITS_SPEED):
            if now - self._eng_state.get("limit_at", 0.0) > LIMITS_RESET:
                self._eng_state["limits"] = 0
            n = self._eng_state.get("limits", 0) + 1
            self._eng_state["limits"] = n
            self._eng_state["limit_at"] = now
            if n >= LIMITS_SERIOUS:
                out.append((70, "limits", "eng_limits_serious",
                            self._rkw(s, me, n=n)))
            elif n >= LIMITS_WARN:
                out.append((45, "limits", "eng_limits_warn",
                            self._rkw(s, me, n=n)))

        if s.full_course_yellow or any(s.yellow_sectors):
            if self._eng_state.get("yellow") != True:
                self._eng_state["yellow"] = True
                out.append((76, "flag", "eng_yellow", self._rkw(s, me)))
        else:
            self._eng_state["yellow"] = False

        return out

    def _greet_career(self, s, me):
        """Open the session, using the career if there is one.

        Deliberately quiet when there is nothing to add: a greeting that says
        "last time out you were fourth" is worth having, and one that invents
        a weekend is not. No career, no quali on record, or qualifying turned
        off for this career — and he simply says hello.
        """
        kw = self._rkw(s, me)
        career = getattr(self, "season", None)
        if career is None:
            return "eng_greeting", kw
        # WHAT HE IS WORKING WITH. The booth calls him a rookie; the man on the
        # pit wall does something more useful with the same fact — he tells him
        # what to do about it. "You're new to this, get up to speed with the
        # track and don't overdrive" is an engineer's sentence; "the rookie,
        # and nobody knows what he'll become" is a broadcaster's.
        #
        # It replaces the greeting on the FIRST session of a division, where a
        # driver's standing in the sport is the most useful thing his engineer
        # can be thinking about, and gets out of the way afterwards so the
        # career greeting can do its own job.
        # A CAR HE HAS NEVER TESTED. The engineer is the one voice who would
        # mention that, and the call-up letter says in as many words that there
        # is no test — so the first session in it gets his own opening, and the
        # brief gets restated after that with the number in it.
        #
        # It goes ABOVE the status greeting because "you are a riser, get up to
        # speed" is the wrong thing to say to a driver sitting in a car he has
        # not driven.
        try:
            import programme as prog_mod
            if prog_mod.called_up(career):
                driven = [r for r in career.rounds if not r.get("absent")]
                if not driven:
                    return "eng_callup_first", kw
                bar = prog_mod.bar_state(career)
                if bar:
                    import drivers as drivers_mod
                    kw.update({
                        "pos": drivers_mod.spoken_ordinal(bar["pos"]),
                        "bar": drivers_mod.spoken_ordinal(bar["bar"]),
                        "gap": drivers_mod.spoken_number(bar["gap"]),
                        "rival": bar["rival"],
                        "left": drivers_mod.spoken_number(bar["left"]),
                    })
                    return "eng_callup_bar", kw
        except Exception:
            pass
        if getattr(career, "on_ladder", False) and not career.rounds:
            cat = {"rookie": "eng_status_rookie", "riser": "eng_status_riser",
                   "contender": "eng_status_contender",
                   "champion": "eng_status_champion",
                   "multi": "eng_status_multi",
                   "legend": "eng_status_legend"}.get(career.status()[0])
            if cat:
                return cat, kw
        rnd = career.next_round() or {}
        kw["n"] = rnd.get("n") or 0
        kw["total"] = career.total_rounds or 0
        # The very first session of a career gets its own opening, because
        # "last time out you were fourth" is not available and "round one of
        # five" is not what an engineer says on the morning of a new season.
        if not career.rounds and (rnd.get("n") or 1) <= 1:
            return "eng_season_open", kw
        if not career.uses_quali:
            return "eng_greeting_career", kw
        last = career.quali_result()
        if not last or not last.get("pos"):
            return "eng_greeting_career", kw
        from overlay_common import spoken_place
        kw["pos"] = spoken_place(last["pos"])
        # THIS weekend's qualifying, if it has already happened, versus a
        # previous round's. "You put it fourth yesterday" and "last time out
        # you were fourth" are different sentences and only one is true.
        here = getattr(s, "circuit", None)
        same = here is not None and last.get("slug") == here.slug
        if s.kind == "race" and same:
            return "eng_grid_recall", kw
        return "eng_quali_recall", kw

    # -- speaking --------------------------------------------------------------
    def _radio_ready(self, now):
        """Is the radio free to say something unhurried right now?

        Used by the greeting, which is worth retrying rather than dropping:
        it waits for a genuinely quiet moment instead of being spent on the
        first tick and lost.
        """
        return (now - self._radio_last > RADIO_COOLDOWN
                and not self.tts.speaking)

    def _radio(self, cat, topic, kw, s, now, prio):
        gap = URGENT_RADIO_COOLDOWN if prio >= 75 else RADIO_COOLDOWN
        if now - self._radio_last < gap:
            return False
        if now - self._topic_last.get(topic, 0.0) < TOPIC_COOLDOWN.get(topic, 30.0):
            return False
        cap = TOPIC_MAX.get(topic)
        if cap is not None and self._topic_n.get(topic, 0) >= cap:
            return False
        if self.tts.speaking and prio < 80:
            return False

        era = s.player_era or s.era
        text, intensity, _ = lines_mod.pick(cat, era, kw)
        if not text:
            return False
        text = self._frame(text, kw, prio)
        self.tts.speak(text, cast_mod.ENGINEER, intensity=intensity)
        self._radio_last = now
        self._topic_last[topic] = now
        self._topic_n[topic] = self._topic_n.get(topic, 0) + 1
        self._push_msg(cast_mod.ENGINEER, text, now)
        return True

    def _frame(self, text, kw, prio):
        """Wrap a call the way a person would say it.

        Not every time, and never on an urgent one — "okay Lando, you have
        just been hit" is a man reading from a card. The value is the
        VARIATION: the same instruction arriving sometimes bare and sometimes
        with his name on the front is what stops him sounding like a warning
        light.

        Never applied to a line that already carries the driver's name, or he
        says it twice in one breath.
        """
        import random
        if prio >= 70:
            return text                     # urgent: just say the thing
        if self._framed_last:
            self._framed_last = False       # never two running
            return text
        if random.random() > FRAME_CHANCE:
            return text
        name = kw.get("drv") or ""
        if name and name in text[:26]:
            return text
        opener = random.choice(ENG_OPENERS)
        if "{drv}" in opener:
            if not name:
                return text
            opener = opener.replace("{drv}", name)
        # LOWERCASE THE ORIGINAL FIRST WORD, but only where that is safe.
        # "DRS enabled" must not become "drs enabled", and a line opening on
        # a slot must not be touched at all — the slot fills with a name.
        #
        # The letters have to be extracted first: `"That's".isalpha()` is
        # False because of the apostrophe, which silently skipped the
        # lowercasing and produced "Right, That's your quickest so far."
        first = text.split(None, 1)[0]
        letters = "".join(ch for ch in first if ch.isalpha())
        if (not text.startswith("{") and letters
                and not letters.isupper()):
            text = text[0].lower() + text[1:]
        self._framed_last = True
        return "%s %s" % (opener, text)

    def _push_msg(self, who, text, now, label=None, icon=None, spoken=True):
        """Queue a radio card.

        `label`/`icon` let a rival supply their OWN name and helmet — the
        engineer is one fixed character, but a driver card has to identify
        which of twenty people just spoke.

        THE CARD WAITS FOR THE AUDIO. `tts.speak()` only ENQUEUES, and a
        render takes two to six seconds — so pushing the card here, straight
        after the speak call, put Dean's words on screen several seconds
        before Dean said them. That is the desync the user reported, and it
        is the same mistake the booth caption already had fixed for it
        (`overlay_draw` keys the subtitle off `tts.now_playing`).

        `spoken=False` is for cards that are never voiced at all — the rival
        driver cards, which are a graphic and nothing else. Those appear
        immediately, because there is no audio for them to wait for.
        """
        if spoken:
            self._pending_cards.append((who, text, label, icon, now))
            return
        self._card_now(who, text, now, label, icon)

    def release_cards(self, now):
        """Move any pending card to the screen once its line is audible.

        Called every frame. Matches on the TEXT rather than on order, because
        the booth and the engineer share one audio queue and a card must not
        be released by somebody else's line coming up.

        A card whose line never becomes audible — the render failed, or the
        queue was flushed by a session change — is dropped after
        `CARD_WAIT_MAX`, rather than sitting in the queue waiting to ambush a
        later session.
        """
        if not self._pending_cards:
            return
        live = getattr(self.tts, "now_playing", None)
        playing = live[1] if live else None
        keep = []
        for who, text, label, icon, queued in self._pending_cards:
            if playing is not None and text == playing:
                self._card_now(who, text, now, label, icon)
                continue
            if now - queued > CARD_WAIT_MAX:
                continue            # never became audible; drop it
            keep.append((who, text, label, icon, queued))
        self._pending_cards = keep

    def _card_now(self, who, text, now, label=None, icon=None):
        """Put a card on screen this instant."""
        from overlay_common import HELMET_COLORS
        if label:
            # The card colour comes from the SAME index as the helmet, so the
            # name on the card and the picture beside it always agree. They
            # used to be two independent hashes of the same name, which meant
            # a driver with a red card wore a green helmet — small, but it is
            # the kind of wrongness a viewer notices immediately.
            from overlay_rival import helmet_for
            colour = HELMET_COLORS[(helmet_for(label) - 1) % len(HELMET_COLORS)]
        else:
            colour = cast_mod.colour_of(who)
        self._msgs.append(_Msg(who, label or cast_mod.name_of(who), text, now,
                               colour,
                               icon if icon is not None
                               else self._icons.get("engineer")))
        del self._msgs[:-3]

    def _quali_radio(self, s, me, p, now):
        """The engineer during a timed session.

        His job here is different from a race: there is no strategy, nobody to
        defend from and no fuel to eke out. There is a sheet, and the only
        things he can usefully tell you are where you are on it, how much you
        need to find, which part of the lap you are losing it in, and how long
        is left.

        Everything is edge-triggered on YOUR OWN lap completing (LAW 1) — a
        position on a timesheet is a standing state, and reporting it on a
        cooldown is how the race engineer became a metronome.
        """
        out = []

        # -- YOUR OFF, AND YOUR LAP ------------------------------------------
        # FIRST, and before the sheet is even consulted. These are the two
        # things the driver has just experienced, and both were silent: the
        # excursion code that publishes `player_off` only ran in the race
        # detector, and this function returns long before the race path that
        # consumes it. So a driver could put it in the gravel on a hot lap and
        # hear nothing at all from the man whose job is to talk to him.
        #
        # Handled ahead of `sheet`, because an empty sheet returns early — and
        # the first off of a session usually happens before anybody has set a
        # time, which is exactly when it would have been dropped again.
        off = getattr(self, "player_off", None)
        if off is not None:
            kind, _at = off
            self.player_off = None
            if kind in ("spin", "offtrack", "ranwide") and s.green:
                # SEVERITY DECIDES THE TONE here as it does in a race, but the
                # COST is different and the race lines say so out loud: "lost
                # a few places there" is wrong on a Saturday. What an off
                # costs in qualifying is the lap.
                if kind == "ranwide":
                    out.append((60, "incident", "eng_offtrack_quali",
                                self._rkw(s, me)))
                else:
                    # A spin or all four wheels off is still "are you okay".
                    # That question is about the driver, not the session.
                    out.append((84, "incident", "eng_incident",
                                self._rkw(s, me)))

        # THE LAP ITSELF, when the game has taken it away. Separate from the
        # off above because they are two different pieces of news and neither
        # implies the other — you can run wide and keep the lap, and you can
        # lose a lap without a visible excursion.
        if getattr(self, "player_lap_deleted", None) is not None:
            self.player_lap_deleted = None
            out.append((78, "incident", "eng_lap_deleted", self._rkw(s, me)))

        sheet = sorted((c for c in s.order if c.best_lap),
                       key=lambda c: c.best_lap)
        if not sheet:
            return out
        pole = sheet[0]

        # -- THE FLAG ---------------------------------------------------------
        # He signs the session off. Asked for directly: the chequered flag in
        # qualifying triggered nothing at all — not the booth, not the
        # engineer — so the session simply stopped.
        #
        # Highest priority he has here, and once only: this is the last thing
        # he says before the car comes in, and it is the summary of everything
        # the session was about.
        if s.finished and not self._eng_state.get("q_done"):
            self._eng_state["q_done"] = True
            idx = next((i for i, c in enumerate(sheet) if c.id == me.id), None)
            if idx is not None:
                pos = idx + 1
                field = len(sheet)
                # GRADED AGAINST THE FIELD, not against a fixed position. P8
                # is a good afternoon in a twenty-car field and a poor one in
                # a ten-car field, and an engineer who congratulates you for
                # the same number either way is reading a table.
                if pos <= max(3, field * 0.2):
                    cat = "eng_quali_done_good"
                elif pos <= max(6, field * 0.6):
                    cat = "eng_quali_done_ok"
                else:
                    cat = "eng_quali_done_poor"
                out.append((92, "q_flag", cat,
                            self._rkw(s, me, pos=self._sheet_place(pos),
                                      t=spoken_lap(me.best_lap))))
        me_idx = next((i for i, c in enumerate(sheet) if c.id is me.id), None)

        # -- a completed lap ---------------------------------------------------
        if p is not None and me.laps > p.laps and me.last_lap:
            improved = bool(me.best_lap and p.best_lap
                            and me.best_lap < p.best_lap - 1e-4)
            if me_idx == 0 and improved:
                out.append((80, "q_lap", "eng_quali_pole",
                            self._rkw(s, me, t=spoken_lap(me.best_lap))))
            elif improved and me_idx is not None:
                # The gap that matters is to the man AHEAD of you on the
                # sheet, not to pole — that is the one you can actually take.
                nxt = sheet[me_idx - 1]
                out.append((62, "q_lap", "eng_quali_lap",
                            self._rkw(s, me, pos=self._sheet_place(me_idx + 1),
                                      rival=nxt,
                                      t=spoken_lap(me.best_lap),
                                      gap=self._qgap(me.best_lap
                                                     - nxt.best_lap))))
            elif not improved and me.best_lap and me.last_lap:
                # THE LAP TIME, ALWAYS. Even a lap that beat nothing is
                # information: it is how you know whether the change you
                # made worked. He only spoke on an improvement before, which
                # in a fifteen-minute session was twice.
                off = me.last_lap - me.best_lap
                out.append((40, "q_time", "eng_quali_time",
                            self._rkw(s, me, t=spoken_lap(me.last_lap),
                                      gap=self._qgap(off),
                                      pos=self._sheet_place((me_idx or 0) + 1))))

            # WHERE YOU ARE LOSING IT. Only against the pole man, only when
            # both full splits exist, and only when one sector is genuinely
            # the problem — "you're losing a bit everywhere" is true far more
            # often and says nothing.
            worst = self._quali_weak_sector(me, pole)
            if worst is not None:
                n_sec, lost, dominant = worst
                sec = ("sector one", "sector two", "sector three")[n_sec - 1]
                # EDGE-TRIGGERED ON THE DIAGNOSIS (LAW 1). "You're losing it
                # in sector two" is a standing fact for as long as it stays
                # true, and on a clock alone he repeated the identical
                # finding seven times in a session. He says it again when the
                # sector changes, or when the deficit has moved enough to be
                # worth another word.
                # ...OR WHEN IT HAS SIMPLY BEEN A LONG TIME.
                #
                # Edge-triggering alone made this almost inaudible: the user
                # drove a full qualifying session and the whole live log
                # contains ONE sector call, because his weak sector never
                # changed and his deficit never moved 0.15s. But a driver who
                # is still losing sector two eight minutes later is exactly
                # the driver who wants telling again — the diagnosis is not
                # stale news, it is the thing he is working on.
                #
                # So there is a re-arm as well as an edge, and `TOPIC_MAX`
                # caps the total for the session. Trigger, clear AND budget,
                # which is what LAW 18 asks for.
                was = self._eng_state.get("q_weak")
                said_at = self._eng_state.get("q_weak_at", -1e9)
                if (was is None or was[0] != sec
                        or abs(was[1] - lost) >= SECTOR_NEWS
                        or now - said_at > SECTOR_REPEAT):
                    self._eng_state["q_weak"] = (sec, lost)
                    self._eng_state["q_weak_at"] = now
                    # WHAT THAT SECTOR ACTUALLY ASKS OF HIM. From the circuit
                    # itself, and empty for one we hold no notes on — in which
                    # case he names the sector and says nothing more, rather
                    # than coaching a corner he might be putting in the wrong
                    # third of the lap.
                    circ = getattr(s, "circuit", None)
                    coach = circ.sector(n_sec) if circ is not None else ""
                    cat = ("eng_quali_sector" if dominant
                           else "eng_quali_sector_spread")
                    if coach:
                        cat += "_coach"
                    out.append((48, "q_sector", cat,
                                self._rkw(s, me, sec=sec, coach=coach,
                                          gap=self._qgap(lost))))

        # -- the clock ----------------------------------------------------------
        rem = getattr(s, "time_left", None)
        if (rem is not None and 0 < rem < QUALI_LAST_CALL
                and not self._eng_state.get("q_final")):
            self._eng_state["q_final"] = True
            out.append((70, "q_flag", "eng_quali_final",
                        self._rkw(s, me,
                                  pos=self._sheet_place((me_idx or 0) + 1))))
        return out

    @staticmethod
    def _sheet_place(i):
        """Position on a TIMESHEET, spoken.

        Not `spoken_place`, which renders 1 as "the lead" — correct in a race
        and wrong in qualifying, where it produced "you're the lead" and
        "still the lead on the sheet". A timesheet has a top, not a leader.
        """
        return "top of the sheet" if i <= 1 else _spoken(i)

    def _slide_call(self, s, me, now):
        """He has noticed you going backwards, and says so.

        THE REFERENCE IS THE BEST YOU HAVE HELD, not the place you started
        from. A driver who qualified nineteenth, climbed to twelfth and then
        slid to sixteenth has lost four places in the part of the race he is
        actually living in; measured against his grid slot he is three to the
        GOOD, and an engineer who congratulated him there would be reading a
        spreadsheet rather than watching.

        Three guards, and each one is a way this becomes annoying or wrong:

          * IT MUST HOLD (`PLACES_SLID_HOLD`). rF2 publishes complete but
            scrambled orders around restarts and session changes — the same
            quirk that produced "thirty places clawed back" about a man who
            started third. A drop that evaporates in two ticks was never real.
          * IT RESETS ITS OWN REFERENCE once mentioned, so a long slide is
            reported in steps rather than re-announced with a bigger number
            every lap.
          * `TOPIC_MAX["slide"]` caps it. A genuinely terrible afternoon is
            still only worth three mentions; after that he is narrating.
        """
        out = []
        if not s.green or s.kind != "race" or me.in_pits:
            return out
        place = me.place
        if not place or place > 250:            # 255 = no position yet
            return out
        best = self._eng_state.get("slide_best")
        if best is None or place < best:
            # A new high-water mark clears any pending slide: he is going the
            # right way and there is nothing to recover from.
            self._eng_state["slide_best"] = place
            self._eng_state.pop("slide_since", None)
            return out
        lost = place - best
        if lost < PLACES_SLID:
            self._eng_state.pop("slide_since", None)
            return out
        since = self._eng_state.get("slide_since")
        if since is None:
            self._eng_state["slide_since"] = now
            return out
        if now - since < PLACES_SLID_HOLD:
            return out
        if now - self._eng_state.get("slide_at", -1e9) < PLACES_SLID_GAP:
            return out
        self._eng_state["slide_at"] = now
        self._eng_state["slide_best"] = place    # report in steps, not totals
        self._eng_state.pop("slide_since", None)
        # Reuse the off-recovery machinery: having been told he has lost
        # places, getting them back is worth a word, and that is exactly what
        # `eng_recovery` already says.
        self._eng_state.setdefault("off_place", best)
        self._eng_state.setdefault("off_at", now)
        return [(46, "slide", "eng_places_lost",
                 self._rkw(s, me, n=("one place" if lost == 1
                                     else "%d places" % lost),
                           pos=_spoken(place)))]

    def _race_sector_call(self, s, me, p, now):
        """Which part of the lap is costing you, during a race.

        The same diagnosis `_quali_radio` makes, against the SESSION'S BEST
        LAP rather than against pole — in a race there is no pole, and the
        quickest man out there is the honest benchmark for "where is my lap
        time going".

        Offered only on a completed lap (LAW 1: it is news when the lap that
        produced it is news), only when the deficit is real, and capped by the
        same `q_sector` budget the qualifying version uses — they are the same
        subject and a driver does not care which session he heard it in.
        """
        out = []
        if not s.green or s.kind != "race" or me.in_pits:
            return out
        if p is None or me.laps <= p.laps or not me.last_lap:
            return out
        best = min((c for c in s.order if c.best_lap and c.id != me.id),
                   key=lambda c: c.best_lap, default=None)
        if best is None:
            return out
        worst = self._quali_weak_sector(me, best)
        if worst is None:
            return out
        n_sec, lost, dominant = worst
        sec = ("sector one", "sector two", "sector three")[n_sec - 1]
        was = self._eng_state.get("r_weak")
        said_at = self._eng_state.get("r_weak_at", -1e9)
        if (was is not None and was[0] == sec
                and abs(was[1] - lost) < SECTOR_NEWS
                and now - said_at <= SECTOR_REPEAT):
            return out
        self._eng_state["r_weak"] = (sec, lost)
        self._eng_state["r_weak_at"] = now
        circ = getattr(s, "circuit", None)
        coach = circ.sector(n_sec) if circ is not None else ""
        cat = "eng_quali_sector" if dominant else "eng_quali_sector_spread"
        if coach:
            cat += "_coach"
        # Below the every-lap readout's neighbours but above nothing: a
        # warning, a pit call or the car behind all still win the tick.
        return [(38, "q_sector", cat,
                 self._rkw(s, me, sec=sec, coach=coach,
                           gap=self._qgap(lost)))]

    @staticmethod
    def _quali_weak_sector(me, pole):
        """The one sector the player is really losing to pole in.

        All three splits or nothing on both cars: two sectors out of three is
        the shape of an answer that sounds authoritative and is wrong. And
        `best_s1`/`best_s2`/`best_s3` are the sectors OF THE BEST LAP, so they
        describe a lap that was actually driven.
        """
        if me.id == pole.id:
            return None
        g = lambda c, n: getattr(c, n, None)
        a = (g(me, "best_s1"), g(me, "best_s2"), g(me, "best_s3"))
        b = (g(pole, "best_s1"), g(pole, "best_s2"), g(pole, "best_s3"))
        if not all(a) or not all(b):
            return None
        d = [a[i] - b[i] for i in range(3)]
        i = max(range(3), key=lambda k: d[k])
        lost = d[i]
        if lost <= QUALI_SECTOR_MIN:
            return None
        # DOMINANT OR SPREAD — BOTH ARE WORTH SAYING, AND THEY ARE DIFFERENT
        # SENTENCES.
        #
        # This used to return None unless one sector carried 55% of the
        # deficit, which is rare: a driver two tenths down everywhere is the
        # normal case and got nothing at all. In a whole live qualifying
        # session the sector call never fired once.
        #
        # So the worst sector is always named, and the CALLER is told whether
        # it dominates. "You are losing it all in sector two" and "you are a
        # couple down everywhere, most of it in sector two" are both true,
        # and only one of them is true at a time.
        total = sum(x for x in d if x > 0)
        if total <= 0:
            return None
        dominant = (lost / total) >= QUALI_SECTOR_SHARE
        return (i + 1, lost, dominant)

    @staticmethod
    def _qgap(g):
        """A timesheet margin. Not `_gap`, which bottoms out at "right on your
        tail" — true of a car behind you, meaningless about a lap time."""
        if g is None:
            return ""
        g = abs(g)
        if g >= 1.0:
            return "a second" if round(g, 1) == 1.0 else "%.1f seconds" % g
        t = int(g * 100 + 0.5)
        if t >= 10:
            tenths = int(g * 10 + 0.5)
            if tenths >= 10:
                return "a second"
            return "a tenth" if tenths == 1 else "%d tenths" % tenths
        if t <= 0:
            return "nothing at all"
        return "a hundredth" if t == 1 else "%d hundredths" % t

    def _rkw(self, s, me, rival=None, **extra):
        """Slot dictionary for a RADIO line.

        Named `_rkw`, not `_kw`, because BoothMixin also defines `_kw` and
        sits earlier in the Overlay's MRO — so `self._kw(...)` inside the
        radio resolved to the BOOTH's version, which has a different
        signature. `rival=` fell through to **extra as a raw Car object and
        the engineer read its repr aloud: "<Car P9 Lewis Hamilton +0.525> is
        right behind you."
        """
        kw = {
            # FIRST NAME ONLY. A race engineer says "okay Lando", never "okay
            # Lando Norris" — the full name is broadcast language, and it is
            # the booth's job, not his. Falls back to the whole string when
            # there is only one word, which covers a surname-only profile
            # name and every single-word alias.
            "drv": _first_name(me.display_name),
            "pos": _ordinal(me.place),
            "rival": rival.display_name if rival is not None else "",
            "laps": s.laps_left or 0,
            "fuel": "%.1f" % (me.fuel or 0.0),
        }
        kw.update(extra)
        return kw



    # -- radio cards -------------------------------------------------------------
    def draw_radio(self, now):
        """Stacked radio cards, bottom-right, newest at the bottom.

        Drawn even while the line is still being spoken so the text and the
        audio arrive together — a card that appears after the voice has
        finished reads as lag.
        """
        live = [m for m in self._msgs if now - m.at < RADIO_HOLD]
        if not live:
            self._hide_panel("radio")
            return
        # UI-SCALED. A fixed 330 while every font on the card scales with the
        # UI meant the text outgrew the box at anything above 1.0x, which is
        # what cut the ends off Dean's sentences.
        w = UI(RADIO_CARD_W)
        cards = []
        for m in live:
            # The text column is not the card: the accent spine, the icon and
            # the right-hand padding take RADIO_TEXT_INSET out of it. Wrapping
            # against the full width overflowed by exactly that much.
            lines_out = self._wrap_px(m.text, w - UI(RADIO_TEXT_INSET),
                                      self.f_row)
            cards.append((m, lines_out, bubble_h(len(lines_out))))
        h = sum(c[2] + 6 for c in cards)
        gx, gy, gw, gh = self.game_rect
        # Stacked above the dash on the right edge, never beside it.
        x = gx + gw - w - UI(EDGE)
        y = gy + gh - h - self._dash_reserved() - UI(EDGE + 10)
        p = self._begin_panel("radio", x, y, w, h)
        c = p.canvas_at(x, y)

        ry = y
        for m, lines_out, ch in cards:
            fade = max(0.25, 1.0 - (now - m.at) / RADIO_HOLD)
            self._radio_card(c, x, ry, w, ch, m, lines_out, fade)
            ry += ch + 6

    def _radio_card(self, c, x, y, w, h, m, lines_out, fade):
        body = shade(TH.panel, 0.9)
        c.create_rectangle(x, y, x + w, y + h, fill=body, outline=TH.border)
        c.create_rectangle(x, y, x + 4, y + h, fill=m.colour, outline="")
        ix = x + UI(14)
        r = UI(12)
        if m.icon is not None:
            c.create_image(ix + r, y + h / 2, image=m.icon)
        else:
            c.create_oval(ix, y + h / 2 - r, ix + 2 * r, y + h / 2 + r,
                          fill=shade(TH.panel, 0.6), outline=m.colour)
        # Derived from the same constant the wrap used, so the text can never
        # be laid out to one width and drawn at another.
        tx = x + UI(RADIO_TEXT_INSET) - UI(10)
        c.create_text(tx, y + UI(14), text=m.name.upper(), anchor="w",
                      fill=m.colour, font=self.f_tiny)
        ty = y + UI(30)
        for ln in lines_out:
            c.create_text(tx, ty, text=ln, anchor="w", fill=TH.text,
                          font=self.f_row)
            ty += UI(RADIO_LINE_H)

    def _dash_reserved(self):
        """Vertical space the dash occupies, so cards never overlap it.

        Taken from the dash's ACTUAL drawn rectangle, published by
        `draw_dash`. Re-deriving it from `_dash_size(era)` meant guessing
        with a possibly-stale era, and returning 0 whenever that guess failed
        — which put the radio cards straight across the speedo.
        """
        if not self.show_dash:
            return 0
        rect = getattr(self, "_dash_rect", None)
        if not rect:
            return 0
        gx, gy, gw, gh = self.game_rect
        # Distance from the bottom of the screen to the top of the dash.
        return max(0, (gy + gh) - rect[1])


class _PlayerSnap(object):
    __slots__ = ("in_pits", "laps", "gap_ahead", "place", "fuel", "best_lap")

    def __init__(self, c):
        self.in_pits = c.in_pits
        self.laps = c.laps
        self.gap_ahead = c.gap_ahead
        self.place = c.place
        self.fuel = getattr(c, "fuel", None)
        # Needed by the qualifying calls, which fire on the edge of YOUR best
        # lap improving. Without it the previous tick has nothing to compare
        # against and every completed lap reads as an improvement.
        self.best_lap = getattr(c, "best_lap", None)


# Particles that belong to the SURNAME, not to a forename. "Max van der
# Linde" is Max; "Van Amersfoort" on its own is not a first name at all.
_NAME_PARTICLES = {"van", "von", "de", "da", "di", "du", "del", "della",
                   "der", "den", "la", "le", "mc", "mac", "st"}


def _first_name(name):
    """The name a race engineer would actually use on the radio."""
    parts = (name or "").split()
    if len(parts) < 2:
        return name or ""
    first = parts[0]
    # A leading particle means the whole thing is a surname, so there is no
    # forename to shorten to and the full name is the honest answer.
    if first.lower().strip(".") in _NAME_PARTICLES:
        return name
    return first


def _ordinal(n):
    if not n:
        return ""
    if 10 <= (n % 100) <= 20:
        return "P%d" % n
    return {1: "P1", 2: "P2", 3: "P3"}.get(n, "P%d" % n)


_ICON_CACHE = {}


def _load_icons():
    """Radio-card art, if Pillow and the PNGs are both present.

    Optional by design: a missing icon falls back to a drawn disc rather than
    taking the radio panel down.
    """
    if _ICON_CACHE:
        return _ICON_CACHE
    try:
        from PIL import Image, ImageTk
    except Exception:
        return _ICON_CACHE
    here = os.path.dirname(os.path.abspath(__file__))
    for key, fn in (("engineer", "icon_engineer.png"),):
        p = os.path.join(here, fn)
        if not os.path.exists(p):
            continue
        try:
            im = Image.open(p).convert("RGBA").resize((28, 28), Image.LANCZOS)
            # The engineer artwork is solid BLACK, which is invisible against
            # a dark radio card — the headset simply was not there. Recoloured
            # at load rather than in the file so the source art stays editable
            # and the alpha channel (which carries the actual shape) is the
            # only thing that matters.
            _ICON_CACHE[key] = ImageTk.PhotoImage(_tint(im, (255, 255, 255)))
        except Exception:
            pass
    return _ICON_CACHE


def _tint(im, rgb):
    """Recolour every pixel, keeping the alpha. The shape lives in the alpha
    channel, so the RGB can be replaced wholesale without touching edges."""
    alpha = im.getchannel("A")
    from PIL import Image
    flat = Image.new("RGBA", im.size, rgb + (255,))
    flat.putalpha(alpha)
    return flat
