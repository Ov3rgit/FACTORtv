# FACTORtv 0.0.1-beta — setting it up

A broadcast overlay and commentary booth for **rFactor 2**: three voices, a
timing tower, a telemetry dash, a career that climbs six ladders, an inbox and
three news feeds.

## Which download

| | |
|---|---|
| **`FACTORtv-0.0.1-beta-standalone.zip`** | **Start here.** Nothing to install — no Python, no packages. Unzip, run `INSTALL.bat`, race. |
| `FACTORtv-0.0.1-beta.zip` | The source build. Needs Python 3.9+ with *Add python.exe to PATH* ticked. For anybody who wants to read or change the code. |

Everything below applies to both; where they differ it says so.

---

## 0. Run the installer. That is the whole setup.

**Double-click `INSTALL.bat`.** One run, nothing to download first — the plugin
ships inside the build. (From source: `python install.py`. In the standalone
build the same thing is `FACTORtv.exe --install`.)

In one run it:

* copies the artwork into `Pictures\Factor Overlay\...` where the overlay reads
  it — never overwriting anything you have added yourself;
* finds rFactor 2 and installs the shared-memory plugin from `plugin/` into
  `Bin64\Plugins` — backing up anything already there;
* **switches the plugin ON in rF2's own config**, which is the step people miss —
  a plugin that is present but not enabled publishes nothing, and the overlay then
  sits there saying it is waiting for the game;
* installs the three Python packages;
* and finishes by telling you either READY or exactly what is still wrong.

It is safe to run twice, and `--check` changes nothing. Close rFactor 2 before
running it, or the game may write over the plugin setting on its way out.

If you have already downloaded the plugin DLL, hand it over and the installer
puts it in the right place:

```bash
FACTORtv.exe --install --plugin C:\Users\you\Downloads\rFactor2SharedMemoryMapPlugin64.dll
```

`python install.py --check` says what is missing and changes nothing.

---

## 1. The shared-memory plugin (the installer does this — here is what it did)

The overlay reads rFactor 2 through **TheIronWolf's rF2 Shared Memory Map
plugin**, and rF2 publishes nothing without it: without the plugin the overlay
starts, draws its menu, and sits there saying it is waiting for the game.

It is bundled in `plugin/` with its GPL licence text and a link to its source —
see `THIRD_PARTY.md`. The reason it is bundled rather than linked is that the
upstream project has never attached a binary to a release, so "download it" is
advice that ends in a search.

The file belongs at:

```
<your rFactor 2>\Bin64\Plugins\rFactor2SharedMemoryMapPlugin64.dll
```

Then it has to be ENABLED. rF2 records that in
`UserData\player\CustomPluginVariables.JSON` under `" Enabled"` — note the
leading space, which is rF2's own spelling — and `install.py` sets it for you.
By hand it is **Settings → Plugins** in rF2's launcher.

To check the whole chain:

```bash
python verify_plugin.py
```

That prints whether the buffers are open, and it is worth running before you
report anything as broken.

---

## 2. Python — the SOURCE build only

**The standalone build needs none of this.** The interpreter, tkinter, Pillow and
the audio stack are inside the executable.

From source: Windows 64-bit, **Python 3.9 or newer** (developed on 3.13), and

```bash
pip install -r requirements.txt
```

which is pillow, edge-tts and miniaudio. Everything else — the entire UI, the
shared-memory reader — is standard library. `INSTALL.bat` runs it for you and
tells you plainly if Python is missing or was installed without the PATH box
ticked, which is the box everybody misses.

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

Double-click **`Start FACTORtv.bat`** — or `FACTORtv.exe` directly in the
standalone build, `python factor_tv.py` from source. Start the game, load a
session, and the overlay attaches on its own.

**If you are reporting a bug, use this instead:**

```
TEST RUN (logs a session).bat
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

**The voices are not bundled and cannot be** — see step 3. Bundling the plugin
has no bearing on them: the plugin publishes the game's telemetry, the voices come
from a Microsoft service over the internet, and the two share nothing. The overlay
prints a `VOICES` line on the first rendered call saying which it got.

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
