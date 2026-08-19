# -*- coding: utf-8 -*-
"""
FACTORtv — pre-rendered stings.

A sting is a short, NAME-FREE line rendered once to disk and played the
instant something happens.

Why they have to exist
----------------------
A live edge-tts render takes 2-6 seconds. For most commentary that is fine —
the booth is describing a situation that persists. But for the handful of
moments where timing IS the content, it is fatal:

  * LIGHTS OUT. The call has to land as the lights go out, not four seconds
    into the run to turn one.
  * AN INCIDENT. "Oh, trouble!" three seconds after the spin is not a
    reaction, it is a report.
  * THE WIN. The roar goes with the line being crossed.

So these lines are rendered ahead of time, on a background thread at startup,
and cached to disk keyed on (voice, text). Changing a voice re-renders
automatically because the key changes; nothing needs invalidating by hand.

They are deliberately NAME-FREE. A sting cannot know who spun, so it never
claims to — the booth follows up a beat later with the name once the live
render completes. That two-stage delivery is what makes the reaction feel
immediate and the detail feel considered.
"""
import hashlib
import os
import random
import sys
import threading

import cast as cast_mod

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
STING_DIR = os.path.join(_DIR, "stings")

# Which persona voices each group.
STING_PERSONA = {
    "intro": cast_mod.PLAY,
    "lastlap": cast_mod.PLAY,
    "pass": cast_mod.PLAY,
    "retire": cast_mod.PLAY,
    "photo": cast_mod.PLAY,
    "lightsout": cast_mod.PLAY,
    "alert": cast_mod.ANALYST,
    "victory": cast_mod.PLAY,
    "chequered": cast_mod.PLAY,
    "outro": cast_mod.PLAY,
    "restart": cast_mod.PLAY,
}

STING_LINES = {
    # Opening the broadcast. Airs before any live line, so the show starts the
    # instant the session does rather than after a render.
    "intro": [
        "You're watching FACTORtv. Let's go racing.",
        "This is FACTORtv, and we are live.",
        "Welcome along to FACTORtv.",
        "FACTORtv, on air — and it's race day.",
        "Good afternoon, and welcome to FACTORtv.",
        "This is FACTORtv. Strap in.",
    ],

    # The single most timing-critical line in the whole product.
    "lightsout": [
        "And they're away!",
        "Lights out — and away we go!",
        "We are racing!",
        "Green flag, green flag — go, go, go!",
        "And the race is on!",
        "They're gone! Down to turn one!",
        "The flag drops — and we're racing!",
        "Away they go, and it's frantic already!",
    ],

    "restart": [
        "Green flag! We're racing again!",
        "And we're back to green!",
        "Racing resumes!",
    ],

    # Name-free by necessity: at the moment of the moment we do not yet know
    # who it was. The pundit names them in the very next beat — see
    # `BoothMixin._incident_report`, which speaks the alert, the
    # identification and the play-by-play reply as one queued sequence.
    #
    # THESE ARE AN INTERRUPTION AND SHOULD SOUND LIKE ONE. The user's brief
    # was "hold on, there's been an incident": a man cutting across his
    # colleague to stop the broadcast, not a reaction to something already
    # described. The lines that open with an address to the room — "hold on",
    # "sorry to cut in", "forgive me" — do that job best, which is why
    # several were added; the original set was mostly exclamations, and an
    # exclamation is a reaction rather than an interruption.
    "alert": [
        "Hold on — there's been an incident!",
        "Sorry to cut in, but we've got an incident!",
        "Forgive me — something's happened out there!",
        "Hold on, hold on — trouble on track!",
        "Let me stop you there — there's been an incident!",
        "Apologies — we've got a car in trouble!",
        "Oh, trouble — somebody's gone off!",
        "Ooh, that's a mistake!",
        "Whoa — a big moment there!",
        "Oh dear, someone's run wide!",
        "Hang on — that's a spin!",
        "That's a lock-up, and straight on!",
        "Trouble on track!",
        "Ooh — someone's lost the back end!",
        "A wobble, and off the circuit!",
        "Deep into the run-off for somebody!",
        "Oh, that's gone wrong!",
        "Wait — we've got a car in trouble!",
    ],

    "victory": [
        "He's done it!",
        "That's the chequered flag!",
        "He takes it!",
        "And it's victory!",
        "He's won the race!",
        "Across the line, and it's done!",
    ],

    "chequered": [
        "The chequered flag is out.",
        "That's the flag.",
        "And we're done.",
    ],

    # THE LAST LAP. Timing is the content here exactly as it is at the start:
    # "final lap" arriving four seconds late lands after the moment it was
    # describing, and the viewer is already watching the run to the flag.
    "lastlap": [
        "Last lap!",
        "This is the final lap!",
        "One lap to go!",
        "Last time around!",
    ],

    # A PASS AS IT HAPPENS. Name-free by necessity — at the moment two cars
    # cross there is no time to render who. The booth names them a beat later.
    "pass": [
        "He's through!",
        "That's a move!",
        "Side by side!",
        "Round the outside!",
        "He's got him!",
        "Brilliant move!",
    ],

    # A CAR STOPPING. Different from the offtrack alert: this is somebody's
    # race ending, and it deserves its own reaction rather than "ooh".
    "retire": [
        "And that's a car stopping!",
        "Somebody's day is done!",
        "That's a retirement!",
        "He's out — that's over.",
    ],

    # THE FLAG DROPPING ON A CLOSE ONE.
    "photo": [
        "Photo finish!",
        "That's too close to call!",
        "On the line!",
    ],

    # Closing the broadcast — the counterpart to the intro.
    # THE ENDING PHRASE. One designated line that closes the session, and
    # nothing airs after it — `_signed_off` mutes the whole tick the moment
    # this plays (see `update_booth`).
    #
    # IT IS THE ONLY GOODBYE IN THE PRODUCT, and that is the fix. Every line
    # in `signoff` used to be a farewell as well — "and that's our race",
    # "thanks for watching", "we'll see you at the next one" — so the show
    # said goodbye twice in a row, every session, and the live log has the
    # two of them four seconds apart. Those pools now state the RESULT and
    # this states the end. One of each.
    #
    # A sting rather than a live line because it is fixed text: it needs no
    # slots, it must never be refused by a cooldown, and pre-rendering means
    # it lands the moment the show is over rather than six seconds later.
    "outro": [
        "And that's it from FACTORtv.",
        "And that's it from FACTORtv. Goodbye.",
        "That's it from FACTORtv. See you next time.",
        "And that is it from FACTORtv. Thanks for watching.",
        "From all of us at FACTORtv, goodbye.",
    ],
}


# --------------------------------------------------------------------------
# THE ARCHIVE BROADCAST
#
# Pre-2000 racing is presented as footage from the archive, called live by
# Brett Calloway with Chuck alongside. Only the groups whose WORDING has to
# change are listed here; everything else is era-neutral and is simply
# rendered in Brett's voice as well as Miles's.
#
# The rule these are written to, and it is easy to break: Brett and Chuck are
# MODERN broadcasters presenting old footage. They were not there. They do
# not know how it ends. Nothing here names a year, a circuit or a result,
# because the cars and tracks in any given session are approximations of a
# period rather than a reconstruction of a specific event.
# --------------------------------------------------------------------------
STING_LINES_HISTORIC = {
    "intro": [
        "You're watching FACTORtv Classic.",
        "This is FACTORtv Classic, and we're going back.",
        "Welcome to FACTORtv Classic — a fixture from the archive.",
        "FACTORtv Classic. Let's watch this one again.",
        "From the FACTORtv archive. Let's go racing.",
        "This is FACTORtv Classic, and it's about to begin.",
    ],
    "outro": [
        # Brett's half of the same rule: one goodbye, and it names HIS
        # channel. `cast.set_era` puts him in the chair before 2000, so the
        # ending phrase changes with the man saying it and nothing else has
        # to know.
        "And that's it from FACTORtv Classic.",
        "And that's it from FACTORtv Classic. Goodbye.",
        "That's it from the FACTORtv archive. See you next time.",
        "And that is it from FACTORtv Classic. Thanks for watching.",
    ],
}


class Stings(object):
    """Disk-cached instant audio, with anti-repeat selection."""

    def __init__(self, tts):
        self.tts = tts
        self.clips = {}          # (persona, group) -> [(path, text), ...]
        self._bags = {}          # key -> remaining indices
        self.ready = False
        try:
            os.makedirs(STING_DIR, exist_ok=True)
        except Exception:
            pass
        # Built on a daemon thread: rendering ~40 clips takes a couple of
        # minutes on first run, and the overlay must be usable immediately.
        # Anything that fires before the cache is warm simply skips its sting
        # and uses the normal live path.
        threading.Thread(target=self._build, daemon=True).start()

    def _build(self):
        if self.tts.engine != "edge":
            return
        total = 0
        for group, lines in STING_LINES.items():
            for persona, lines in self._variants(group, lines):
                total += self._build_group(group, persona, lines)
        self.ready = total > 0

    def _variants(self, group, lines):
        """Every (persona, texts) pair this group has to be rendered as.

        The play-by-play seat has two occupants, and a sting is pre-rendered
        audio in one specific voice — so both have to exist on disk before
        either session type can open. A historic session that had to render
        its welcome live would lose the one thing stings are for.

        Groups whose wording changes for an archive broadcast take their text
        from `STING_LINES_HISTORIC`; the rest ("we are racing!", "oh,
        trouble!") are era-neutral and are simply voiced by whoever is in the
        seat.
        """
        persona = STING_PERSONA.get(group, cast_mod.PLAY)
        out = [(persona, lines)]
        if persona == cast_mod.PLAY:
            out.append((cast_mod.HISTORIC_PLAY,
                        STING_LINES_HISTORIC.get(group, lines)))
        return out

    def _build_group(self, group, persona, lines):
        """Render one group in one voice. Returns how many clips it now has.

        Keyed on (voice, text) as before, so the two occupants of the
        play-by-play seat cannot collide even where they say the same words.
        """
        cfg = cast_mod.voice_for(persona)
        voice = cfg.get("voice")
        clips = []
        for txt in lines:
            h = hashlib.md5(("%s|%s" % (voice, txt)).encode("utf-8"))
            path = os.path.join(STING_DIR,
                                "%s_%s.wav" % (group, h.hexdigest()[:10]))
            if not os.path.exists(path):
                if not self._render(txt, persona, path):
                    continue
            if os.path.exists(path):
                clips.append((path, txt))
        if clips:
            self.clips[(persona, group)] = clips
        return len(clips)

    def _render(self, text, persona, path):
        """Render one sting through the normal voice chain.

        Reuses the engine's own render so a sting is processed identically to
        a live line — same intensity ladder, same limiting. A sting that
        sounded different from the booth around it would stand out as canned.
        """
        try:
            job = {"text": text, "persona": persona, "intensity": 2,
                   "seed": 0, "build": False, "prio": 1, "epoch": 0,
                   "seq": 0, "name": ""}
            wav = self.tts._render(job)
            if wav and os.path.exists(wav):
                import shutil
                shutil.copyfile(wav, path)
                return True
        except Exception:
            pass
        return False

    def pick(self, group):
        """Choose a clip without repeating until the group is exhausted.

        Resolved through the SEAT: a pre-2000 session gets Brett's rendering
        of the group, and — where the wording differs — the archive-framed
        text rather than the live one.
        """
        persona = cast_mod.occupant(STING_PERSONA.get(group, cast_mod.PLAY))
        clips = self.clips.get((persona, group))
        if not clips:
            # No historic rendering cached yet (first run in that era), so
            # fall back to the modern one rather than opening the show in
            # silence.
            persona = STING_PERSONA.get(group, cast_mod.PLAY)
            clips = self.clips.get((persona, group))
        if not clips:
            return None, None, persona
        key = "%s|%s" % (persona, group)
        bag = self._bags.get(key)
        if not bag:
            bag = list(range(len(clips)))
            random.shuffle(bag)
        i = bag.pop()
        self._bags[key] = bag
        path, text = clips[i]
        return path, text, persona

    def play(self, group, interrupt=False):
        """Fire a sting NOW. Returns its text, or None if unavailable.

        The caller uses the returned text for the on-screen caption, so the
        subtitle and the audio always match even though the audio never went
        through the queue.
        """
        path, text, persona = self.pick(group)
        if not path:
            return None
        if interrupt:
            self.tts.interrupt()
        self.tts.play_file(path, persona, text)
        return text
