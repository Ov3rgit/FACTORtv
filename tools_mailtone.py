# -*- coding: utf-8 -*-
"""
FACTORtv — generate the new-mail tone.

    python tools_mailtone.py        # writes stings/mail.wav

A two-note blip, a fifth apart, about a fifth of a second. Written in code
rather than shipped as a downloaded asset for the same reason the rest of this
product is: it can be re-tuned in one line, it has no licence attached to it,
and anybody reading the repository can see exactly what it is.

THREE THINGS IT DELIBERATELY IS NOT. It is not a chime with a tail — a
lingering sound over a race means somebody is trying to get your attention,
and mail is never urgent. It is not loud: the peak is a fifth of full scale,
under the commentary rather than over it. And it is not a rising fanfare,
which is a reward sound; this is a notification, and the difference is the
whole reason the story's mail can hide among the admin.
"""
import math
import os
import struct
import wave

RATE = 44100
PEAK = 0.20             # a fifth of full scale — under the booth, never over
NOTES = ((880.0, 0.075), (1318.5, 0.115))     # A5 then E6, a fifth apart


def tone(freq, secs):
    n = int(RATE * secs)
    out = []
    for i in range(n):
        t = i / float(RATE)
        # A short attack and a fast decay. A square-edged blip clicks; a slow
        # fade sounds like a doorbell, which is the thing this must not be.
        env = min(1.0, i / (RATE * 0.004)) * (1.0 - (i / float(n))) ** 1.6
        out.append(PEAK * env * math.sin(2.0 * math.pi * freq * t))
    return out


def main():
    samples = []
    for freq, secs in NOTES:
        samples.extend(tone(freq, secs))
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "stings", "mail.wav")
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32767))
            for v in samples))
    print("wrote %s — %.2fs" % (path, len(samples) / float(RATE)))


if __name__ == "__main__":
    main()
