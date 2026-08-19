# -*- coding: utf-8 -*-
"""
FACTORtv — hear the cast.

Speaks a representative line for each principal, plus a couple of rivals, so
the voices can be judged the way they will actually be heard: through the same
render chain, the same limiting, and the same radio treatment as in a race.

    python voicedemo.py

Nothing here is a special case. It calls the real engine, so if a voice sounds
wrong here it will sound wrong on track.
"""
import sys
import time

import cast as cast_mod
import tts as tts_mod

# (label, persona, driver name for casting, text, intensity, build)
SCRIPT = [
    ("Miles Crawford  (play-by-play, calm)", cast_mod.PLAY, "",
     "Good afternoon, and welcome to FACTORtv, live from Zandvoort.", 0, False),

    ("Miles Crawford  (play-by-play, flat out)", cast_mod.PLAY, "",
     "Down the inside! Verstappen has him! That is the move for the lead "
     "of the Grand Prix!", 3, True),

    ("Chuck Brannigan (analysis)", cast_mod.ANALYST, "",
     "He's short-shifting to protect the rears, and it's the right call. "
     "On the ovals this is where you'd be looking for a push.", 0, False),

    ("Chuck Brannigan (verdict)", cast_mod.ANALYST, "",
     "Hard but fair. He left him just enough room. Just.", 0, False),

    ("Dean Mackenzie  (engineer, routine)", cast_mod.ENGINEER, "",
     "Fuel's on target, tyres look stable. Keep the rhythm.", 0, False),

    ("Dean Mackenzie  (engineer, urgent)", cast_mod.ENGINEER, "",
     "Box this lap, box this lap. He's in your mirrors, three tenths.",
     2, False),

    ("Rival — Verstappen (Dutch)", cast_mod.DRIVER, "Max Verstappen",
     "He pushed me clean off the road out there!", 2, False),

    ("Rival — Hamilton (British)", cast_mod.DRIVER, "Lewis Hamilton",
     "Alright, he's through. No panic, long race yet.", 1, False),

    ("Rival — Tsunoda (Japanese)", cast_mod.DRIVER, "Yuki Tsunoda",
     "Move! He's holding me up!", 2, False),
]


def main(only=None):
    t = tts_mod.Tts()
    if t.engine != "edge":
        print("edge-tts unavailable — this would be the offline SAPI fallback.")
        print(tts_mod._EDGE_ERR)

    print("Rendering %d lines...\n" % len(SCRIPT))
    rendered = []
    script = [r for r in SCRIPT if not only or only.lower() in r[0].lower()]
    for label, persona, name, text, inten, build in script:
        cfg = cast_mod.voice_for(persona, name=name)
        job = {"text": text, "persona": persona, "intensity": inten,
               "seed": 0, "build": build, "prio": 1, "epoch": 0, "seq": 0,
               "name": name}
        try:
            wav = t._render(job)
        except Exception as e:
            print("  FAILED %s: %s" % (label, e))
            continue
        rendered.append((label, cfg["voice"], text, wav))
        print("  %-42s %s" % (label, cfg["voice"]))

    print("\nPlaying...\n")
    for label, voice, text, wav in rendered:
        print("  %-42s %s" % (label, voice))
        print("      %s" % text)
        try:
            if tts_mod.winsound and wav:
                tts_mod.winsound.PlaySound(wav, tts_mod.winsound.SND_FILENAME)
        except Exception:
            pass
        time.sleep(0.35)

    print("\nDone.")
    t.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None) or 0)
