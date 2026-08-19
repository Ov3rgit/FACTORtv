# -*- coding: utf-8 -*-
"""
FACTORtv — rival driver radio.

The other cars key the mic about their own race. This is the cheapest way to
make an AI grid feel like twenty people rather than twenty lap times, and it
is also the easiest thing in the whole product to overdo.

Three rules keep it from becoming noise
---------------------------------------

1. THEY ONLY SPEAK ABOUT THEMSELVES, AND ONLY WHEN IT INVOLVES YOU. A rival
   complaining about a battle three laps down the road is a fact you cannot
   use. Every trigger here either happened TO the player or happened to a car
   the player can see.

2. ONE VOICE PER DRIVER, FOR EVER. Persona, helmet and voice are all derived
   from a stable hash of the driver's name, so the same AI is the same
   character across every session and every restart. A driver whose
   personality changes race to race is not a character, it is a random
   generator.

3. THEY ARE RARE. A grid of twenty with a 20-second cooldown each would still
   produce a transmission every second. The global cooldown here is long, and
   most triggers additionally require the player to be directly involved.

Personas are the RacerTV archetypes — HOTHEAD, COCKY, VETERAN, DRAMATIC,
JOKER, ROOKIE, VILLAIN — because they cover the recognisable range of racing
temperaments with the fewest categories.
"""
import os
import time

import cast as cast_mod
import lines as lines_mod
from overlay_common import STRIKE_GAP

PERSONAS = ["HOTHEAD", "COCKY", "VETERAN", "DRAMATIC", "JOKER", "ROOKIE",
            "VILLAIN"]

# Long on purpose. Rival radio is seasoning, not the meal.
RIVAL_COOLDOWN = 38.0
PER_DRIVER_COOLDOWN = 150.0

# How close a car must be for the player to plausibly have seen its incident.
WITNESS_GAP = 4.0

HELMET_COUNT = 9

# HOW OFTEN A SIGNATURE LINE IS REACHED FOR.
#
# The whole value of a catchphrase is that it is rare. Max saying "simply
# lovely" after a pole is a moment; Max saying it after every good lap is a
# parrot. So a quote needs an occasion that fits AND this roll AND a driver
# who has not already used his this session.
QUOTE_CHANCE = 0.55


def persona_for(name):
    """Stable persona from the driver's name.

    Not `hash()`: Python randomises string hashing per process, so a driver's
    personality would change every time the overlay restarted.
    """
    n = 0
    for ch in (name or ""):
        n = (n * 131 + ord(ch)) & 0xFFFFFFFF
    return PERSONAS[n % len(PERSONAS)]


def helmet_for(name):
    """Stable helmet icon index (1..9) for the radio card."""
    n = 0
    for ch in (name or ""):
        n = (n * 17 + ord(ch)) & 0xFFFFFFFF
    return (n % HELMET_COUNT) + 1


class RivalMixin(object):

    def rival_init(self):
        self._quoted = set()        # drivers who have used their line today
        self._rival_best = None     # who held the session best lap last tick
        self._rival_result_done = False
        self._rival_last = 0.0
        self._rival_seen = {}          # car id -> last time they spoke
        self._rival_prev = {}          # car id -> (place, in_pits, damage)
        self._helmets = _load_helmets()

    # -- main ------------------------------------------------------------------
    def update_rivals(self, s):
        if not self.rival_enabled or s is None or not s.valid or not s.green:
            return
        if not getattr(s, "on_air", True):
            return
        me = s.player
        if me is None:
            return
        now = time.time()
        # THE END OF A SESSION IS THE BEST MOMENT A CATCHPHRASE HAS, and it
        # happens after the green flag has gone — so it is checked before the
        # normal trigger sweep rather than inside it.
        if self._rival_result(s, now):
            return
        events = self._rival_events(s, me, now)
        self._rival_snapshot(s)
        if not events:
            return
        events.sort(key=lambda e: -e[0])
        for prio, car, event in events:
            if self._rival_say(car, event, s, now):
                return

    def _rival_snapshot(self, s):
        """Record this tick's baseline.

        The PLAYER's place is recorded here too, not inside `_rival_events`.
        It used to be captured after that method's early return, so on the
        first tick it was never set at all — and since every pass trigger
        requires a previous player position, the first overtake involving the
        player was always missed.
        """
        self._rival_prev = {
            # `getattr` throughout: a car with no telemetry this tick has no
            # speed and no surface data, and the snapshot must not be the
            # thing that decides whether the cards work at all.
            c.id: (c.place, c.in_pits, max(getattr(c, "damage", None) or (0,)),
                   getattr(c, "speed", None) or 0.0,
                   getattr(c, "wheels_off", 0) or 0)
            for c in s.order if not c.is_player
        }
        if s.player is not None:
            self._rival_me_place = s.player.place
        self._rival_best = self._session_best(s)

    @staticmethod
    def _session_best(s):
        """Which car holds the best lap of the session, by id, or None."""
        run = [c for c in (getattr(s, "order", ()) or ())
               if getattr(c, "best_lap", None)]
        if not run:
            return None
        return min(run, key=lambda c: c.best_lap).id

    # -- triggers ---------------------------------------------------------------
    def _rival_events(self, s, me, now):
        """What would make a rival reach for the radio button?

        Deliberately narrow. The two that carry almost all the value are
        "you just passed me" and "I just passed you", because those are the
        moments the player was actually part of.
        """
        out = []
        prev = self._rival_prev
        if not prev:
            return out

        me_prev = getattr(self, "_rival_me_place", None)

        for c in s.order:
            if c.is_player or c.in_pits:
                continue
            p = prev.get(c.id)
            if p is None:
                continue
            old_place, old_pits, old_dmg = p[0], p[1], p[2]
            old_speed = p[3] if len(p) > 3 else 0.0

            # --- the player passed them --------------------------------------
            if (c.place == old_place + 1 and me_prev is not None
                    and me.place == old_place):
                out.append((90, c, "overtaken"))
                continue

            # --- they passed the player --------------------------------------
            if (c.place == old_place - 1 and me_prev is not None
                    and me.place == old_place):
                out.append((88, c, "caught"))
                continue

            # Everything below needs the player to be near enough to have
            # plausibly witnessed it, or the transmission is about a race the
            # player cannot see.
            near = abs((c.gap_leader or 0.0) - (me.gap_leader or 0.0))
            if near > WITNESS_GAP:
                continue

            # --- fresh damage --------------------------------------------------
            dmg = max(c.damage or (0,))
            if dmg > old_dmg and dmg > 0:
                out.append((70, c, "damage"))
                continue

            # --- he has just been off ------------------------------------------
            #
            # THE EVENT TYPES WERE ALREADY WRITTEN AND NOTHING EMITTED THEM.
            # `incident`, `frustrated`, `pumped`, `pit` and `praise` had 40
            # lines between them and no trigger — dead since the file was
            # written, exactly like `booth_joke`. A pool with no caller is
            # invisible, and `lines.py` reports it as healthy.
            off = getattr(c, "wheels_off", 0) or 0
            drop = old_speed - (getattr(c, "speed", None) or 0.0)
            if off >= 2 and drop > 25.0:
                out.append((78, c, "incident"))
                continue

            # --- into the pits --------------------------------------------------
            if c.in_pits and not old_pits:
                out.append((30, c, "pit"))
                continue

            # --- stuck behind the player, losing time -------------------------
            behind = s.car_behind(me)
            if behind is c and (c.gap_ahead or 99.0) < STRIKE_GAP:
                out.append((40, c, "blocked"))
                continue

            # --- grudging respect for a lap you just set -----------------------
            #
            # The last of the five event types that had lines and no trigger.
            # Gated on the player ACTUALLY having the best lap of the session,
            # so a rival never congratulates him on nothing — and edge-
            # triggered on taking it, because holding it is a state.
            if (self._rival_best != self._session_best(s)
                    and self._session_best(s) == getattr(me, "id", None)):
                out.append((26, c, "praise"))
                continue

            # --- his race is going badly, and he can see it -------------------
            #
            # Grounded in the arc rather than in a mood: a man who has lost
            # real places, or been off more than once, has something to be
            # frustrated about. Low priority — it is a state, not an event,
            # and the cooldowns are what keep it occasional.
            arc = self._rival_arc(c)
            if arc is not None:
                if arc.slid >= 4 or arc.offs >= 2:
                    out.append((18, c, "frustrated"))
                    continue
                if arc.recovered >= 4 or arc.gained >= 4:
                    out.append((16, c, "pumped"))
                    continue
        return out

    def _rival_result(self, s, now):
        """A signature line at the moment it belongs to.

        Pole at the end of qualifying, a win or a podium at the flag. Fires
        once per session for one driver — the man the result actually belongs
        to — because a grid full of catchphrases at the same moment is a
        novelty toy rather than a broadcast.
        """
        if self._rival_result_done or not getattr(s, "finished", False):
            return False
        order = list(getattr(s, "order", ()) or ())
        if not order:
            return False
        top = order[0]
        if top.is_player:
            # The player has an engineer for this. A card from himself would
            # be very strange.
            self._rival_result_done = True
            return False
        occasion = "pole" if s.kind in ("quali", "practice") else "win"
        if self._rival_quote(top, occasion, s, now):
            self._rival_result_done = True
            return True
        self._rival_result_done = True
        return False

    def _rival_quote(self, car, occasion, s, now):
        """Put a driver's own words on screen, if he has any for this moment.

        Returns False for almost everybody: most drivers have no signature
        line, most moments are not an occasion, and the roll refuses more
        than half of what is left. That is the intended hit rate.
        """
        import random
        import drivers as drivers_mod
        name = car.display_name or car.name
        if name in self._quoted:
            return False
        era = getattr(s, "player_era", None) or getattr(s, "era", None)
        text = drivers_mod.quote(name, era, occasion)
        if not text:
            return False
        if random.random() > QUOTE_CHANCE:
            # Refused this time, and NOT marked as used — he may get another
            # occasion later in the session, which is the point of rolling.
            return False
        self._quoted.add(name)
        self._rival_last = now
        self._rival_seen[car.id] = now
        self._push_msg(cast_mod.DRIVER, text, now, label=name,
                       icon=self._helmets.get(helmet_for(name)), spoken=False)
        return True

    def _rival_arc(self, car):
        """This rival's race so far, if the booth has been tracking it.

        The booth and the rival cards live on the same host, so the arc the
        commentary is built from is the arc a driver reacts to — which is the
        point. A card saying he is furious about a race he is winning would
        be the clearest possible sign that nothing is really watching.
        """
        try:
            import story as story_mod
        except Exception:
            return None
        if not hasattr(self, "_story"):
            return None
        return story_mod.of(self, None, car)

    # -- the card ----------------------------------------------------------------
    def _rival_say(self, car, event, s, now):
        """Put a rival's reaction ON SCREEN. It is never spoken.

        Rival radio used to be voiced, and it was the weakest thing in the
        product: edge-tts has no Dutch- or Italian-accented English, so a grid
        of twenty drivers came out as a handful of approximate accents that
        fooled nobody and pulled against the three voices that do work. The
        card is worth keeping — it identifies who is annoyed with whom, and it
        looks like a broadcast graphic — so the text stays and the audio goes.

        The consequence to remember: this no longer competes for the audio
        channel at all, so it does not check `tts.speaking` and does not
        interrupt the booth. It is a caption.
        """
        if now - self._rival_last < RIVAL_COOLDOWN:
            return False
        if now - self._rival_seen.get(car.id, 0.0) < PER_DRIVER_COOLDOWN:
            return False

        name = car.name or car.display_name or ""
        persona = persona_for(name)
        era = s.player_era or s.era

        # Persona-specific pool first, then the shared fallback. Not every
        # archetype has a line for every event, and a missing pool must mean
        # "this character doesn't react to that", not a crash.
        text, intensity, _ = lines_mod.pick(
            "rival_%s_%s" % (persona, event), era,
            {"drv": car.display_name, "pos": car.place})
        if not text:
            text, intensity, _ = lines_mod.pick(
                "rival_ANY_%s" % event, era, {"drv": car.display_name})
        if not text:
            return False

        self._rival_last = now
        self._rival_seen[car.id] = now
        # Label and helmet are derived from the SAME string, or the card's
        # colour and its picture disagree — see `overlay_common.HELMET_COLORS`.
        who = car.display_name
        # NEVER VOICED, so it must not wait for audio that will never come.
        # Rival radio is a graphic (see the note above): the text goes up the
        # instant it is chosen, while the engineer's card waits for Dean to
        # actually start speaking.
        self._push_msg(cast_mod.DRIVER, text, now, label=who,
                       icon=self._helmets.get(helmet_for(who)), spoken=False)
        return True


_HELMET_CACHE = {}


def _load_helmets():
    """The helmet art for rival radio cards.

    Optional: without Pillow or the PNGs the cards fall back to a drawn disc
    rather than the radio panel failing.
    """
    if _HELMET_CACHE:
        return _HELMET_CACHE
    try:
        from PIL import Image, ImageTk
    except Exception:
        return _HELMET_CACHE
    here = os.path.dirname(os.path.abspath(__file__))
    for i in range(1, HELMET_COUNT + 1):
        p = os.path.join(here, "icon_helmet_%d.png" % i)
        if not os.path.exists(p):
            continue
        try:
            im = Image.open(p).convert("RGBA").resize((28, 28), Image.LANCZOS)
            _HELMET_CACHE[i] = ImageTk.PhotoImage(im)
        except Exception:
            pass
    return _HELMET_CACHE
