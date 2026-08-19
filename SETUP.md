# FACTORtv 0.0.1-beta — setting it up

A broadcast overlay and commentary booth for **rFactor 2**: three voices, a
timing tower, a telemetry dash, a career that climbs six ladders, an inbox and
three news feeds.

Run step 0, then read the four numbered steps. Step 1 is the one everything
else depends on, and it is the one people skip.

---

## 0. Run the installer first

```bash
python install.py
```

Or double-click `INSTALL.bat`. It copies the artwork where the overlay looks for
it, finds your rFactor 2, and tells you whether the plugin below is in place —
with the exact path if it is not. It never overwrites anything you already have,
so it is safe to run twice.

If you have already downloaded the plugin DLL, hand it over and the installer
puts it in the right place:

```bash
python install.py --plugin \path\to\rFactor2SharedMemoryMapPlugin64.dll
Factor2SharedMemoryMapPlugin64.dll
```

`python install.py --check` says what is missing and changes nothing.

---

## 1. The shared-memory plugin (without this, nothing works)

The overlay reads rFactor 2 through **The Iron Wolf's rF2 Shared Memory Map
plugin**. rF2 publishes nothing without it, so the overlay will start, draw its
menu, and then sit there saying it is waiting for the game.

Install the plugin into:

```
<your rFactor 2>\Bin64\Plugins\rFactor2SharedMemoryMapPlugin64.dll
```

Then enable it in rF2's own launcher under **Settings → Plugins**. To check it
from here:

```bash
python verify_plugin.py
```

That prints whether the buffers are open, and it is worth running before you
report anything as broken.

---

## 2. Python and three packages

Windows, 64-bit, **Python 3.9 or newer** (developed on 3.13). Then:

```bash
pip install -r requirements.txt
```

That is pillow, edge-tts and miniaudio. Everything else — the entire UI, the
memory reader — is standard library.

---

## 3. The voices need an internet connection

**This is the thing most likely to make your copy sound different from mine.**

The three voices are Microsoft neural voices fetched through `edge-tts`:

| | voice | who |
|---|---|---|
| Miles Crawford | `en-GB-RyanNeural` | play-by-play, 2000 onwards |
| Brett Calloway | `en-AU-WilliamNeural` | play-by-play, before 2000 |
| Chuck Brannigan | `en-US-AndrewMultilingualNeural` | analyst, always |
| Dean Mackenzie | `en-GB-ThomasNeural` | race engineer |

Same voice names, same rates, same output — **as long as edge-tts can reach the
service**. If it cannot, the overlay does not fail: it falls back to Windows SAPI,
and SAPI is the robotic voice you may have heard in old TTS demos. So if your
commentary sounds like a 1998 screen reader, that is the fallback and not the
product. Check the console for `sapi` lines and check your connection.

**The first few minutes of your first session will be quiet in places.** Every
line is rendered once and cached to `_voice_cache/`, and the stings are rendered
at startup into `stings/`. Neither ships with the build (they are 280MB together)
so your machine builds its own. It settles after a session or two.

To hear the cast before driving anything:

```bash
python voicedemo.py
python preview.py --live
```

---

## 4. Run it

```bash
python factor_tv.py
```

Or use `Start FACTORtv.bat`. Start the game, load a session, and the overlay
attaches on its own.

**If you are reporting a bug, run this instead:**

```bash
python testrun.py
```

Identical overlay, but it writes `_session_log.txt` — every line that aired, what
the overlay thought the car and the season were, every swallowed error with a
count. **Send me that file.** Every hard bug in this project was found in it and
none of them by a test suite; a description of what went wrong is worth much less
than the log of it going wrong.

The log is overwritten each run, so it is always about the session you just drove.

### Keys

| | |
|---|---|
| `Ctrl+Shift+S` | the menu (also the hamburger, top-left) |
| `Ctrl+Shift+O` | hide / show the overlay |
| `Ctrl+Shift+C` | commentary on / off |
| `Ctrl+Shift+R` | team radio on / off |
| `Ctrl+Shift+Y` / `N` | answer the "count this race?" prompt |
| `Ctrl+Shift+D` | debug readout |
| `Ctrl+Shift+Q` | quit |

---

## What is NOT in the build, and is not a fault

**The artwork ships, but it is not where the overlay reads it until you run
the installer.** `art/` in this build holds the division logos and the news
photographs; the overlay reads them from `Pictures/Factor Overlay/<Division>/
<Category>/` in your own user folder, and `install.py` is what copies them
across. Add your own photographs to those folders if you like — the installer
never overwrites, and `python newsart.py` prints what it can see. With no art at
all the overlay draws no logo, which is a supported state rather than a fault.

**No career, no settings, no rendered audio.** All local state, all rebuilt.

**The plugin is not bundled**, for the reason in `THIRD_PARTY.md`: it is
somebody else's work under the GPL, a link discharges every obligation that
shipping the binary would carry, and the upstream release is always the current
build. The installer will place it for you.

**The 2020 test programme needs a mod.** F1 2020 by A&M, from the Steam Workshop.
Without it the junior-programme development year still runs, on letters alone.

---

## What to look at, in the order it is worth your time

1. **Drive a qualifying session and a race in the same car**, and listen for
   whether the booth ever says something that is not true. That is the only bug
   class in this product that matters — a wrong claim costs more than silence.
2. **A safety car**, if you can provoke one. The whole sequence — deployed, pit
   lane, "safety car in this lap", the restart — was built from one log and has
   never been heard live.
3. **Overtakes.** Take a place off somebody and see whether it is called.
4. **A career**: New career → Ladder career → a path → races per season. Then
   race a round and read the inbox between sessions.

Things known to be unfinished are listed in `version.py`.
