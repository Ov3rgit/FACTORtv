# -*- coding: utf-8 -*-
"""
FACTORtv — the first-run introduction.

Asked for: *"when someone first launches there can be voice tutorial on what
buttons do what, so like the first load they will get a caption card being
narrated by the enginner to show them exactly how to use it"*.

What is worth testing here is not that it speaks — it is the four rules that stop
it being the kind of tutorial people resent: once, never on track, skippable, and
one line at a time.
"""
import os
import sys
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_DIR))
sys.path.insert(0, _DIR)

import cast as cast_mod                                    # noqa: E402
import overlay_radio as R                                  # noqa: E402
import tutorial as T                                       # noqa: E402

fails = []


def check(cond, label, detail=""):
    print("  [%s] %s%s" % (" OK " if cond else "FAIL", label,
                           "  " + detail if detail else ""))
    if not cond:
        fails.append(label)


class _TTS(object):
    """The voice, and whether it is busy — which is what paces the script."""

    def __init__(self):
        self.speaking = False
        self.said = []

    def speak(self, text, who, intensity=0):
        self.said.append((who, text))
        self.speaking = True          # ...until the test says otherwise


class _Sess(object):
    def __init__(self, started=False, green=False):
        self.started = started
        self.green = green
        self.valid = True
        self.on_air = False


class Host(R.RadioMixin):
    """Enough overlay to run the introduction and record what it did."""

    def __init__(self):
        self.cfg = {}
        self.tts = _TTS()
        self.radio_enabled = True
        self.msgs = []
        self.saved = 0
        self._tut_i = 0
        self._tut_last = 0.0
        self._tut_point = ""

    def _push_msg(self, who, text, now):
        self.msgs.append((who, text))

    def _tut_save(self):
        self.saved += 1


def _run(h, s=None, ticks=60):
    """Pump the loop, finishing each line as a real voice would."""
    for _ in range(ticks):
        h.update_tutorial(s)
        h.tts.speaking = False        # the line has finished playing
        h._tut_last = 0.0             # ...and the beat between lines has passed


print("1. THE SCRIPT ITSELF")
check(T.steps(), "there is an introduction to play",
      "%d steps" % len(T.steps()))
check(not T.validate(), "and it obeys its own rules", str(T.validate()))
check(all(st["point"] in ("",) + T.POINTS for st in T.steps()),
      "every step points at something that exists, or at nothing")
check(any(st["point"] == "trophy" for st in T.steps()),
      "the trophy is pointed at, because it is the one nobody would guess")
check(any(st["point"] == "menu" for st in T.steps()), "and so is the menu")
_words = " ".join(st["t"] for st in T.steps()).lower()
check("trophy" in _words and "career" in _words,
      "it names the trophy and the career in words as well as marks")
# NO SLOTS. It plays before there is a session to fill them from.
check("{" not in _words, "and nothing in it is a template")

print("\n2. IT PLAYS ONCE, IN ORDER, ONE LINE AT A TIME")
h = Host()
h.update_tutorial(None)
check(len(h.tts.said) == 1, "the first tick says ONE line, not nine",
      "%d said" % len(h.tts.said))
check(h.tts.said[0][0] == cast_mod.ENGINEER, "and it is the engineer",
      str(h.tts.said[0][0]))
# WHILE HE IS TALKING, NOTHING ELSE IS SAID. The gate is the voice finishing,
# not a timer — nine lines on a timer arrive as one noise.
h.update_tutorial(None)
h.update_tutorial(None)
check(len(h.tts.said) == 1, "and it waits for him to finish before the next",
      "%d said" % len(h.tts.said))
_run(h, None)
check(len(h.tts.said) == len(T.steps()),
      "the whole script arrives, in order",
      "%d of %d" % (len(h.tts.said), len(T.steps())))
check([t for _w, t in h.tts.said] == [st["t"] for st in T.steps()],
      "and it is the script, in the order it was written")
check(T.done(h.cfg), "then it marks itself heard", str(h.cfg))
check(h.saved >= 1, "and writes that to the settings file")
_before = len(h.tts.said)
_run(h, None)
check(len(h.tts.said) == _before,
      "and never plays again, however long the overlay runs",
      "%d then %d" % (_before, len(h.tts.said)))

print("\n3. AND A SECOND LAUNCH HEARS NOTHING")
h2 = Host()
h2.cfg = {T.FLAG: True}
_run(h2, None)
check(not h2.tts.said, "a machine that has heard it is left alone",
      str(len(h2.tts.said)))

print("\n4. NEVER OVER A GREEN FLAG")
# The engineer has spent a lot of effort staying off the grid, and an
# introduction talking across a race start is worse than no introduction.
for _label, _s in (("a green session", _Sess(started=True, green=True)),
                   ("a car already out", _Sess(started=True))):
    h3 = Host()
    _run(h3, _s)
    check(not h3.tts.said, "silent during %s" % _label,
          str(len(h3.tts.said)))
# ...BUT THE GARAGE IS FINE, and so is having no session at all.
h4 = Host()
_run(h4, _Sess(started=False))
check(len(h4.tts.said) == len(T.steps()),
      "and it plays in the garage, which is where a driver reads things",
      "%d lines" % len(h4.tts.said))

print("\n5. IT POINTS AT THE THING IT IS TALKING ABOUT")
h5 = Host()
seen = []
for _ in range(len(T.steps()) * 3):
    h5.update_tutorial(None)
    seen.append(h5._tut_point)
    h5.tts.speaking = False
    h5._tut_last = 0.0
check("trophy" in seen, "the trophy is marked while it is described",
      str([x for x in seen if x][:3]))
check("menu" in seen, "and so is the menu")
check(h5._tut_point == "", "and nothing is left marked at the end",
      repr(h5._tut_point))

print("\n6. A CLICK ENDS IT, AND THAT COUNTS AS HEARD")
h6 = Host()
h6.update_tutorial(None)
check(len(h6.tts.said) == 1, "one line has been said")
h6.tutorial_stop()
h6.tts.speaking = False
_run(h6, None)
check(len(h6.tts.said) == 1, "and skipping stops the rest of it",
      "%d said" % len(h6.tts.said))
check(T.done(h6.cfg), "a player who skipped it has told you something",
      str(h6.cfg))
check(h6._tut_point == "", "and no button is left glowing")

print("\n7. NO ENGINEER, NO LESSON — AND IT STAYS OWED")
# Somebody who has switched the engineer off has said something; shouting the
# introduction at him anyway is not a welcome.
h7 = Host()
h7.radio_enabled = False
_run(h7, None)
check(not h7.tts.said, "nothing is said with the radio switched off",
      str(len(h7.tts.said)))
check(not T.done(h7.cfg), "and it is not marked heard, because it was not",
      str(h7.cfg))
h7.radio_enabled = True
_run(h7, None)
check(len(h7.tts.said) == len(T.steps()),
      "so it is still there when he turns him back on",
      "%d lines" % len(h7.tts.said))

print("\n8. IT CAN BE ASKED FOR AGAIN")
h8 = Host()
h8.cfg = {T.FLAG: True}
h8.tutorial_replay()
check(not T.done(h8.cfg), "replay hands it back", str(h8.cfg))
_run(h8, None)
check(len(h8.tts.said) == len(T.steps()), "and the whole thing plays again",
      "%d lines" % len(h8.tts.said))
check(h8.saved >= 1, "with the flag written both ways")

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
