# FACTORtv 0.0.1-beta

First build to leave the machine it was written on. A broadcast overlay and
commentary booth for **rFactor 2**: three voices, a timing tower, a telemetry
dash, six career ladders, an inbox, three news feeds, and a story told entirely
in correspondence.

**Download `FACTORtv-0.0.1-beta.zip` below** — not the source zip. It carries the
artwork and the installer.

## Setting it up

1. Install **TheIronWolf's rF2 Shared Memory Map plugin** into
   `<rFactor 2>\Bin64\Plugins\`:
   <https://github.com/TheIronWolfModding/rF2SharedMemoryMapPlugin/releases>
2. Unzip this release anywhere and run `INSTALL.bat` (or `python install.py`).

That is the whole setup. The installer copies the artwork where the overlay reads
it, **switches the plugin on in rF2's own config** — the step everybody misses,
because a plugin that is present but not enabled publishes nothing — installs the
three Python packages, and finishes by telling you READY or exactly what is
wrong. Close rFactor 2 before running it.

Then start the game, load a session, and run `Start FACTORtv.bat`.

Requires Windows 64-bit and Python 3.9+. Full detail in `SETUP.md`.

## Two things that will make it look broken and are not

**The voices need an internet connection.** They are Microsoft neural voices
fetched by edge-tts. If it cannot reach the service the overlay does not fail — it
falls back to Windows SAPI, which sounds like a 1998 screen reader. That is the
fallback, not the product.

**The first session is quiet in places.** Every line is rendered once and cached
locally; 280MB of audio is not shipped, so your machine builds its own. It settles
after a session or two.

## What to look at, in the order it is worth your time

1. **Anything the booth says that is not TRUE.** That is the only bug class here
   that really matters — a wrong claim costs more than silence.
2. **A safety car.** Deployed, pit lane closed, pit lane open, "safety car in this
   lap", the restart. Built from a single live log and never yet heard in a full
   race.
3. **Overtakes.** Take a place off somebody and see whether it gets called.
4. **A career.** New career → Ladder career → a path → races per season. Race a
   round, then read the inbox between sessions.

## If you find something

```
TEST RUN (logs a session).bat
```

Same overlay, but it writes `_session_log.txt`: every line that aired, what the
overlay thought the car and the season were, and every swallowed error with a
count. **Send that file.** Every hard bug in this project was found in it and none
of them by a test suite.

## Known gaps

* The safety car sequence, the pass calls and the season-finale news are verified
  by test harness and rendered preview rather than by a full live race.
* The 2020 junior-programme test year needs *F1 2020 by A&M* from the Steam
  Workshop. Without it the development year still runs, on letters alone.
* Division art is included, but if you delete it the overlay simply draws no
  logo — that is a supported state, not a fault.

25 test suites, all passing. 365 dialogue pools / 2,155 lines.
