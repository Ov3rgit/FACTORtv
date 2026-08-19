# FACTORtv

A broadcast overlay and commentary booth for **rFactor 2** — timing graphics,
an era-adaptive telemetry dash, team radio and a fully voiced commentary team
that calls your race as it happens.

Successor to RacerTV (RaceRoom). Same idea, new channel, new look, and a much
stronger grip on *what kind of racing it is actually watching*.

---

## Status

Foundation and dash are built and verified. The broadcast layer is next.

| Module | State | What it does |
|---|---|---|
| `rf2_data.py` | **done**, layout verified | rF2 shared-memory reader (ctypes, pack=4) |
| `verify_plugin.py` | **done** | Self-check: plugin present, publishing, layout correct |
| `era.py` | **done**, tested | Era + discipline detection, capability gating, skins |
| `rf2_session.py` | **done**, gap maths tested | Raw buffers → clean session model |
| `overlay_common.py` | **done** | Theme tokens, live era skin, formatting helpers |
| `overlay_panel.py` | **done** | Click-through always-on-top window plumbing |
| `overlay_dash.py` | **done**, previewed | The telemetry cluster (speed, tyres, fuel, damage) |
| `overlay_draw.py` | **done** | Header, timing tower, relative, flags, status |
| `factor_tv.py` | **done**, runs | Engine: tick loop, panels, hotkeys, settings |
| `cast.py` | **done** | The team: personas, voice casting, what each may say |
| `lines.py` | **done**, tested | Pool loading, era gating, shuffle-bag selection |
| `lines_data/booth.json` | **started** | 156 booth lines across 32 categories |
| `tests/boothtest.py` | **done** | Headless director test — 10 assertions, all passing |
| `overlay_booth.py` | **done**, tested | The director: race phases, focus, bookends, crosstalk |
| `stings.py` | **done** | Pre-rendered instant audio (intro, lights-out, alerts, victory, outro) |
| `testrun.py` | **done** | Instrumented session logger |
| `overlay_radio.py` | **done**, tested | Race engineer + radio cards |
| `lines_data/engineer.json` | **started** | 106 engineer lines across 40 topics |
| `tests/radiotest.py` | **done** | Engineer restraint test — 8 assertions, all passing |
| `overlay_rival.py` | **done**, tested | Rival driver radio — 7 personas, helmets, accents |
| `overlay_panels.py` | **done**, tested | Sector strip, track map, podium, settings menu |
| `overlay_objective.py` | *to build* | Race objectives |
| `tts.py` | **done**, renders | Voice engine (edge-tts neural + radio FX, SAPI fallback) |


Run it with:

```bash
python factor_tv.py
```

Hotkeys (Ctrl+Shift+…): `S` **settings menu** · `O` hide/show · `E` tower ·
`V` relative · `T` dash · `C` commentary · `R` radio · `M` gap mode ·
`D` debug · `Q` quit.

---

## Setup — the one thing rFactor 2 needs

Unlike RaceRoom, **rFactor 2 publishes no telemetry on its own.** It is silent
until a plugin is installed. FACTORtv reads the buffers created by
TheIronWolf's `rFactor2SharedMemoryMapPlugin64.dll` (v3.7.15, GPLv3) — the
same plugin Crew Chief and SimHub use.

**This has already been installed on this machine:**

- `rFactor2SharedMemoryMapPlugin64.dll` copied into
  `…\rFactor 2\Bin64\Plugins\` (from your existing Crew Chief staging copy at
  `D:\plugins\rFactor 2\`)
- enabled in `…\UserData\player\CustomPluginVariables.JSON`, with
  `EnableDirectMemoryAccess: 1` for the extra pit/phase detail
- the original config was backed up next to it as
  `CustomPluginVariables.JSON.bak_<timestamp>`

**rFactor 2 loads plugins at startup only** — if the game was running when
this was installed, restart it.

To confirm everything works, with the game running and a session loaded:

```bash
python verify_plugin.py
```

It checks three separate things in order and tells you which one failed:
the plugin is installed, the plugin is publishing, and — the one that
matters — the struct layout is correct. A wrong layout does not crash, it
produces convincing nonsense, so that stage asserts on things that can only
be true if every byte offset lines up.

Also useful:

```bash
python rf2_data.py       # raw buffer dump
python rf2_session.py    # normalised live timing screen
python era.py            # era detection against known classes
python overlay_dash.py   # dash preview, no game needed
```

---

## Design notes

### Era adaptivity

The overlay reskins and re-words itself to match what is on track. This is not
decoration — it is a *capability* question. A booth that mentions DRS over a
1992 Williams, or battery deployment over a Brabham BT44, breaks the illusion
faster than any graphical flaw.

`era.py` classifies the field into a period and a discipline, then publishes a
set of capabilities. Every era-specific phrase and every dash widget is gated
on `era.has(...)`, so an old car gets a *compact* panel rather than a modern
layout with holes in it.

Verified against the classes actually present in your race results:

| Class string | → | Era | Skin | Notable gating |
|---|---|---|---|---|
| `Formula 1 1992 Season by ASRC` | | F1 1992 | nineties | active suspension + TC, **no** DRS/ERS/refuelling |
| `F1 Test 2025` | | F1 modern | modern | DRS, ERS, fuel flow, engine modes |
| `FSR 2026` | | FSR | modern | as above |
| `StockCar 2018 X Series` | | Stock Car | modern/stock | restarts, draft, refuel, **no** stages |
| `NASCAR 2023 Next Gen CUP` | | NASCAR Cup | modern/stock | + stages |
| `GT500`, `Alpine A110 GT4` | | GT | modern/gt | BoP, pit window, ABS/TC |
| `IndyCar_2014_*` | | IndyCar | modern | push-to-pass, ovals |
| `Mazda 787B` | | Group C | nineties/proto | fuel ration, headlights, **no** BoP/TC |
| `Brabham_1966`, `Howston_G4_1968` | | 1960s GP | classic | **nothing** — no wings, no slicks, no aids |

Unrecognised mods fall through to a deliberately bare capability set: better
mute than wrong.

### The telemetry dash

rFactor 2's own readout is a thin strip of digits. This replaces it with a
cluster that adapts its *instrument style* to the era:

- **analogue** (pre-1982) — sweeping needles, warm dial faces, no electronics.
  A 1968 car had a rev counter and a pit board, so that is what it gets.
- **hybrid** (1982–1999, stock cars) — digital speed against an analogue sweep.
- **digital** (2000+) — bar tacho, energy store, DRS state.

Common to all: per-corner **tyre life and temperature on the same tile**
(they are read together — a cold tyre with life left and a cooked tyre with
life left demand opposite responses), a brake-temp strip, **live fuel burn**
measured per completed lap with laps-remaining and a margin against the race
distance, and an **eight-zone damage diagram** driven by rF2's
`mDentSeverity`.

### The booth

**Miles Crawford** on play-by-play — carried over from RacerTV, same voice,
as the through-line between the two channels. **Chuck Brannigan** on
analysis: former NASCAR Cup champion, Carolina-raised, American. **Dean
Mackenzie** on the pit wall, Australian.

Each persona declares what it *does* and what it will **never** do, and the
director checks before assigning a line — the failure mode of a generated
booth is two voices saying interchangeable things, so Miles never analyses
tyre degradation and Chuck never calls a pass as it happens.

Chuck raced 1985–2006 in stock cars. That biography does real work: he speaks
about ovals, restarts and dirty air from experience and about single-seaters
as an interested outsider, and `spoke_from_memory()` gates which of those he
is allowed to claim.

Repetition is handled with a **shuffle bag** rather than random choice with a
short memory. Measured over the 13 overtake lines legal for modern F1:

| | unique lines in 13 draws |
|---|---|
| naive random | 9 |
| shuffle bag | **13** |

Bags are keyed by `(pool, period/discipline)` so the 1992 vocabulary and the
2025 vocabulary build up independently, and they persist across restarts so
relaunching the game doesn't restart the booth at its same four favourites.

Era gating is enforced at the candidate-set level: a line needing `drs` is
never *considered* for a 1966 car. Verified as zero anachronism leaks across
the four classes you race most.

### Layout law

**Everything hugs an edge. The middle of the screen belongs to the driver.**

This is not a style preference — a panel in the central band sits exactly
where the apex, the braking marker and the car in front are, and no amount of
usefulness makes up for not being able to see the corner.

`keep_clear_rect()` expresses it as a number (±30% of width, ±34% of height
around centre) and `tests/paneltest.py` asserts every persistent panel against
it, so a future layout change cannot quietly creep back into the driving view.
Only the podium, the settings menu and the "waiting for rFactor 2" notice are
exempt, because they appear when there is nothing to obstruct.

At 1920×1080, 1.25× scale:

| corner | panels |
|---|---|
| top-left | settings menu |
| top-centre | header |
| left edge | timing tower |
| bottom-left | track map, sector strip |
| right edge | relative panel |
| bottom-right | radio cards, telemetry dash |

### Rival radio

Seven archetypes — HOTHEAD, COCKY, VETERAN, DRAMATIC, JOKER, ROOKIE,
VILLAIN — assigned by a **stable hash of the driver's name**, so the same AI
is the same character with the same helmet and the same voice across every
session and every restart. A driver whose personality changed race to race
would not be a character, just a random generator.

Three rules stop it becoming noise: they only speak about **themselves**, only
when **you** were involved or close enough to have seen it, and **rarely** —
38s global cooldown, 150s per driver. Measured: 200 rapid position swaps
produce **1** transmission.

### Commentary flow

Ported from RacerTV, because a broadcast has a shape and an event-detector
does not. The race runs through four phases, and the phase decides how deep
into the field the booth will look:

| phase | when | focus depth |
|---|---|---|
| **opening** | lap 1 | top 5 — establish the order, ignore the midfield |
| **mid** | the body of the race | whole field — battles, strategy, colour |
| **late** | last 4 laps / final fifth | top 8 — narrow to what will decide it |
| **closing** | final lap | top 5 — the win, and nothing smaller |

That single gate is most of what makes it feel like television rather than a
telemetry reader: it is what stops a P14 scrap being narrated while the lead
changes hands.

**Stings.** A live edge-tts render takes 2–6 seconds, which is fine for
describing a situation and fatal for reacting to one. Seven groups of short,
name-free lines are rendered once at startup and cached to disk, so they land
on the moment: `intro`, `lightsout`, `restart`, `alert`, `victory`,
`chequered`, `outro` — 43 clips. An incident fires the name-free sting
instantly ("Oh, trouble — somebody's gone off!") and the booth names the
driver a beat later once the live render completes.

**Bookends.** The show opens with an intro and closes with a sign-off, after
which the booth goes silent — a broadcast ends, it does not trail off into
filler over an empty track.

**Race story.** Each driver's best/worst/current position is tracked all
race, so "P7" can become "started third, fell to twelfth, back up to
seventh".

### The race engineer

Dean talks to *you*, about *your* car, and only when he has something you could
act on. That is enforced structurally rather than by good intentions:

- Every call is a **state change**, not a status report. "Fuel is fine" said
  every lap is noise; "fuel just went marginal" is information. Each check
  tracks what it last told you and stays silent until that changes.
- **Hysteresis on every threshold**, so a tyre hovering on the edge of "worn"
  cannot trigger a call each time it crosses back and forth.
- He only ever reads the player's telemetry — he never mentions a car he
  could not see on a timing screen.

Measured in `tests/radiotest.py`: **300 unchanging ticks produce 0 calls**, a
tyre oscillating across the wear threshold is reported **once**, and a fuel
shortfall is called once and then not repeated while it persists.

### Voices

edge-tts neural voices, same engine as RacerTV, with its tuning ported
deliberately rather than re-derived — those values were settled by ear and
several of them were regressions at some point. The load-bearing ones:

- **Energy comes from rate and volume, not pitch.** Raising pitch to sound
  excited makes a commentator sound robotic and small.
- **Big moments swell continuously.** Clauses render separately for rising
  rate/pitch, then one smoothstep loudness envelope runs across the whole
  joined waveform — a per-clause gain step lands on a silence boundary, which
  is exactly where the ear notices it.
- **The band-pass stays wide** (220–5200 Hz, tanh drive 1.03). Narrower sounds
  more "radio" and destroys the accents that make the grid feel like people.
- **Static is scaled by the voice envelope**, so silences stay silent.

Casting matches the characters, not just the roles:

| | voice | why |
|---|---|---|
| Miles Crawford | `en-GB-RyanNeural` | the RacerTV commentator, kept deliberately for continuity |
| Chuck Brannigan | `en-US-RogerNeural` | ex-NASCAR champion, sixties; the oldest-sounding US male in the catalogue |
| Dean Mackenzie | `fr-FR-HenriNeural` | French — a native-language model reading English, the only way to get a real French accent |

Miles Crawford is deliberately **not** `en-GB-RyanNeural` — that is the voice
RacerTV used for its own play-by-play, so reusing it made FACTORtv sound like
a reskin of the old channel rather than a new one.

Rival drivers are cast by **nationality**, using the driver's own language
model to read the English radio line. That produces a genuine accent rather
than an approximation, because the model's phonetics really are that
language's — it is the only way to get a Dutch or Japanese accent at all,
since neither exists in the `en-*` catalogue:

| | | |
|---|---|---|
| Verstappen | `nl-NL-MaartenNeural` | Dutch |
| Tsunoda | `ja-JP-KeitaNeural` | Japanese |
| Leclerc | `fr-FR-HenriNeural` | French |
| Schumacher | `de-DE-ConradNeural` | German |
| Häkkinen | `fi-FI-HarriNeural` | Finnish |
| Piastri, Doohan | `en-AU-WilliamNeural` | Australian |
| Lawson | `en-NZ-MitchellNeural` | New Zealand |
| Hamilton, Russell, Bearman | `en-GB-RyanNeural` | British |

Assignment is deterministic on the name (not `hash()`, which Python
randomises per process), so a driver keeps their voice across restarts.

Three treatments, not two:

| | clicks | band-pass | why |
|---|---|---|---|
| Booth (Miles, Chuck) | no | no | heard in the room |
| Engineer (Dean) | yes | **no** | modern intercom — the filter flattens his prosody, and he's the voice you hear most |
| Rival drivers | yes | yes | sounds better on the chain, and separates them from your engineer instantly |

Measured: the band-pass removes 83% of 8 kHz content, which is precisely why
the engineer routes around it.

**New here:** a render cache keyed on (text, voice, rate, pitch, volume).
First render of a line ~2–6s; cached replay is instant, which removes most of
the lag between an event happening and it being called.

### Gaps

rF2 does publish `mTimeBehindNext`, and it is unusable for broadcast: scoring
updates at 5 Hz and the value is recomputed at timing lines, so it sits frozen
and then jumps. FACTORtv keeps a per-car timeline of *where each car was and
when*, then answers "how long ago was the car ahead standing where this car is
now?" — which is how real timing works, and why the gaps here move smoothly
and stay right through corners, pit cycles and lapped traffic.

### Things rF2 gets wrong that are fixed here

- `mSector` reports **0 for sector 3** — mapped once, in one place.
- `mLastSector2` is a **cumulative split from the lap start**, not a sector
  duration. Both S2 and S3 have to be derived or every sector after the first
  reads far too long.
- Telemetry and scoring are **separate buffers in different orders**, joined
  on `mID`, never on index.
- The stock profile leaves the driver called **"Your Name"** (yours currently
  is). An engineer must never say that out loud, so placeholder names are
  detected and replaced with a configurable display name.
- In replays nothing is flagged `mIsPlayer`, so identity falls through
  control type → profile name → race leader.

---

## Licence and credits

Fan-made, not affiliated with Studio 397 or Motorsport Games. Reads shared
memory only — it never writes to the game and cannot affect your race.

Shared memory provided by
[rF2SharedMemoryMapPlugin](https://github.com/TheIronWolfModding/rF2SharedMemoryMapPlugin)
by TheIronWolfModding (GPLv3), installed separately and not distributed here.
