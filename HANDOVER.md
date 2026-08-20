# FACTORtv — session handover

Paste this whole file as the first message of a new session.

---

## FIRST STEP, BEFORE ANYTHING ELSE: READ THE LOG

**Read `_session_log.txt` in full before you write a line of code, before you
plan, and before you answer any question about the booth.** It is the record of
the last time the overlay was actually driven, and it is the only source in
this project that reports what the product DID rather than what it is supposed
to do.

This is a rule written from losses. Three separate bugs here were invisible to
fifteen green test suites and obvious in the first thirty lines of the log:

* the booth calling a USF2000 career "the 2000 Formula One season"
* the entire pre-qualifying sequence being thrown away before a word of it aired
* a career line raising 2,618 times, taking the commentary off the air for half
  a race

In every case the tests passed because the tests asserted MY MODEL of the
system and the log recorded the system. **Where they disagree, the log is
right.** If the user reports something and the log contradicts your
explanation, your explanation is wrong.

What to look for, in this order:

| grep for | what it tells you |
|---|---|
| `ERROR` | a swallowed traceback. Read the LAST frames — the first four are always the tick. |
| `[booth]` | a fenced source that failed (see THE FENCE below). Carries an `xN` count. |
| `SAY` | every line that AIRED, with persona and intensity. Silence here is the symptom. |
| `ERA` | what the overlay decided the car and season are. `raw class:` is what rF2 actually said. |
| `PLAYER` | the player's place and class string. Both have been nonsense (`P255`, `'Championship'`). |
| `SANITY FAIL` | the field data itself is inconsistent this tick. |

**A long gap between `SAY` lines is the single most important thing in the
file.** The user reports it as "there was no commentary for half the session",
and it has never once been his connection.

Then: **delete `_session_log.txt` before asking him to drive again**, so the
next log is about the next run and not megabytes of the last bug.

---

## What this is

**FACTORtv** — a broadcast overlay and commentary booth for **rFactor 2**.
Successor to **RacerTV** (RaceRoom). Working folder:

```
C:\Users\Administrator\rfactor Overlay
```

Two other folders matter and are already granted:

| path | what it is |
|---|---|
| `D:\R3EOverlay` | **RacerTV — the blueprint.** ~11k lines of proven Python and ~118KB of dialogue in `lines_data/`. Read it before writing new lines. |
| `D:\SteamLibrary\steamapps\common\rFactor 2` | the game — 49 tracks, 82 car mods installed |

The user is **Dante Kandasamy**. In a career he races under a chosen driver
name instead (see CAREERS below). His rF2 profile still says "Your Name",
which is detected as a placeholder and substituted — do not "fix" that by
reading the profile.

**What he is trying to get to:** *"I want to enter a race and feel like I'm
part of the world and the broadcast."* Everything below serves that. When a
choice is between more features and the three voices sounding alive and
CORRECT, choose the second.

---

## State: it works, and it has been driven

20,100 lines of Python. **277 dialogue pools / 1724 lines**, plus 15
conversation topics, **72 real drivers, 38 teams and 41 signature quotes**
across three seasons, and **68 circuits / 288 facts**. Fifteen test suites,
all passing — and run them 2-3 times, not once: several are randomised and
flakiness has bitten repeatedly (see LAWS 20-21).

(The "242 pools / 1346 lines" in the previous handover was wrong — `lines.py`
reports the real figure and it is the only source worth quoting.)

**As of 2026-08-19: 365 pools / 2155 lines, 25 test suites** (`lines.py` is the only figure worth quoting). The counts in
the paragraph above are from 2026-08-17 and are kept because the note about
quoting `lines.py` rather than a handover is the part that matters.

**WHAT HAS BEEN HEARD, AND WHAT HAS NOT.** A Kyalami session on 2026-08-18
(Clio Cup, quali + a much-restarted race) and a karting session on 2026-08-19
are the only live runs behind any of this. The karting log is what produced
"The rookie, the rookie" and the status line that claimed to have watched him
drive. **Everything built on 2026-08-19 — the pass stings, the battle layers,
the title arithmetic, the team-mate, the junior programme, the division
lines, the pictures — has never been heard in a live session.** Ask for
`python testrun.py` early and read the log; it has answered more in ten
minutes than reasoning about the code has in an hour, every single time.

Verified over live sessions on 2026-08-16: a 47-minute historic run
(Silverstone 1991, F1 1988 mod, 31 cars) and a 2021 F1 qualifying session at
Montreal at 23:20. **`_session_log.txt` is overwritten each run and is the RELIABLE record** —
its `SAY` lines are every line that aired, with voice and intensity.

**`_transcript.log` APPENDS across sessions and has time-only stamps, no
dates.** An earlier handover said it was overwritten; it is not. Analysing it
by clock time silently blends runs from different days — a 1988 race was
nearly reported as part of a 2021 one. Use the session log.

READ THEM FIRST when the user reports something. They have answered nearly
every question faster than reasoning about the code has.

```bash
python tests/boothtest.py      # director: phases, focus, suppression
python tests/flowtest.py       # race flow, conversation, quali, incidents
python tests/lifecycletest.py  # intro / formation / restart / win / outro
python tests/radiotest.py      # engineer restraint
python tests/rivaltest.py      # rival cards (silent — see below)
python tests/paneltest.py      # panel layout + keep-clear law
python tests/eratest.py        # anachronism sweep, 10k+ candidate lines
python tests/tracktest.py      # circuit resolution
python tests/careertest.py     # career history + THE LAW
python tests/seasontest.py     # championships, title maths, season shape
python tests/offtracktest.py   # excursions: surface truth, grading, silence
python tests/qualitest.py      # the timesheet as a story
python tests/drivertest.py     # who these people are: truth, gating, airing
python tests/humourtest.py     # levity, and mostly when it is FORBIDDEN
python tests/storytest.py      # race stories, the two-hander, the wrap
python tests/stationtest.py    # FACTORtv, Classic, and the RacerTV nod
python tests/buffertest.py     # the session reader vs the REAL rF2 structs
python tests/laddertest.py     # ladders, the car pick, and simulating a round
python tests/inboxtest.py      # the inbox: what is sent, and what never doubles
python tests/newstest.py       # the three news feeds, and what they refuse to print
python tests/personaltest.py   # the story: pacing, the cost, the four endings
python tests/careerboothtest.py # the booth knowing whose career this is
python tests/passtest.py       # the pass: stings, the retry queue, battle layers
python tests/pointstest.py     # title arithmetic, brute-forced; rivalries; team-mate
python tests/programmetest.py  # the junior programme, F2 to a Formula One seat
python ladder.py               # the six paths, dumped + validated
python inbox.py                # the mail templates, counted + validated
python news.py                 # the news templates, counted + validated
python personal.py             # the story thread, counted + validated
python lines.py                # pool counts + validation
python drivers.py              # the driver knowledge base, dumped + validated
```

**Run them after every change.** Several were caught only because a test
encoded a rule that had been broken.

### Seeing it without driving

```bash
python preview.py                      # real overlay, synthetic race, silent
python preview.py --live               # ...WITH audio: booth, radio, stings
python preview.py --live --historic    # a pre-2000 field: Brett in the chair
python tests/_transcript_demo.py 60    # a whole race as text
python tests/_season_demo.py 3         # three rounds of a career, as text
python careerdemo.py                   # a WHOLE ladder career's mail, news and story
python testrun.py                      # instrumented live run -> _session_log.txt
python voicedemo.py [name]             # hear the cast
python dashshot.py                     # every era's dash -> _dash_preview.png
python frametime.py                    # where a frame actually goes, per panel
python cardshot.py                     # radio cards at 1.0/1.25/1.5x UI scale
python newsshot.py                     # news articles WITH his photographs
python podiumshot.py                   # the end-of-session result card
python mailshot.py                     # a letter, with its letterhead
python menushot.py                     # a menu page (inbox + career)
python modnames.py                     # what the GAME calls each mod
python newsart.py                      # what pictures are on disk, per division
python programme.py                    # the three seats, dumped + validated
```

`--live` exists because a transcript cannot answer whether it FEELS like a
broadcast. Nobody can judge pacing or delivery by reading.

---

## THE LAWS

Violating any of these has regressed the product at least once.

0. **A FAKE CANNOT FALSIFY A FIELD NAME.** Every suite but `buffertest.py`
   feeds the booth a `FakeSession` whose attributes all exist because the fake
   defines them. That is right for testing what the booth SAYS and blind to
   the layer beneath it. `rf2_session.update()` read `si.mStatusMessage` — and
   `mStatusMessage` is on `rF2Extended`, a different memory map — so it raised
   AttributeError on EVERY TICK, drew nothing at all, and filled the console
   with the same traceback twenty times a second. **Sixteen suites passed the
   whole time.** The structs are plain ctypes and instantiate zeroed with no
   game running, so there is no excuse: anything reading shared memory gets a
   real-struct test. See `tests/buffertest.py`, which reproduces the exact
   AttributeError when the fix is reverted, and §1b, which scans the source
   for the same mistake on branches no test takes.

1. **Edge-triggered, not level-triggered.** A yellow flag was announced every
   20s for a whole race because the condition stayed true. Announce CHANGES.
2. **Only a COMPLETED race counts, and the test must be ABSOLUTE.** rF2
   writes a result file whether you took the flag or quit on lap two. A career
   that records abandoned attempts says "his worst result here was
   nineteenth" about a race that was restarted. `career.MIN_SHARE` = 50% of
   the winner's distance — but that is RELATIVE and therefore blind to a
   RESTART, where the whole field stops together and everybody's share is
   100%. That blindness put three phantom wins in the user's store, all from
   one-lap races. A race now only counts if somebody actually FINISHED it
   (`FinishStatus`). Restated in `season.record()` because the caller is the
   thing most likely to be wrong. See §5b-vi.
3. **Context is free; RECORDING is confirmed.** Knowing this is round six
   costs a sentence if wrong. Writing to a championship cannot be undone by
   racing again.
4. **Never state maths that is not exactly true.** `title_state()` returns
   real numbers and `None` when it cannot know. An open season with no
   declared length never claims a total, a rounds-left or a decided title.
5. **Never let a slot air empty.** `safe_format` blanks missing keys, so
   `"Top of the sheets, and it's {drv} by {gap}!"` aired as "by !" when the
   first driver set a time with nobody to be ahead of. If a slot can be
   empty, do not put it in the template — or gate the line.
6. **Era capability gating.** `era.has("drs")` before any DRS line. Zero
   anachronisms across 10k+ candidate lines is asserted in `eratest.py`.
7. **Test the CATEGORY, not the prose** — except where the prose IS the rule
   (see the archive rules and Chuck's biography), which `eratest.py` and
   `flowtest.py` §17 do check by grepping text.
8. **Layout law** — everything hugs an edge; the centre belongs to the
   driver. `keep_clear_rect()`, asserted in `paneltest.py`.
9. **Mixin method names must be unique.** `BoothMixin._kw` shadowed
   `RadioMixin._kw` and the engineer read a Python repr aloud on air.
10. **Snapshot before early returns.** Bookends returning before `_snapshot()`
    lost the first overtake of every race.
11. **A flag must be set when a line AIRS, not when it is offered.**
    `_greeted` was set the moment a greeting was offered, so when the radio
    refused it that tick it was discarded for ever.
12. **A VALID order can still be a WRONG order.** `_places_sane` rejects P255
    and duplicates, but a standing start also publishes complete 1..N
    permutations in which cars hold places they never ran. `worst` only
    grows, so one such tick is permanent — that is "30 places clawed back by
    Alain Prost" about a man who started third. A place must hold for
    `ARC_CONFIRM_TICKS` before the arc believes it.
13. **Never put a determiner in front of a slot.** The margin slots carry
    their own article ("a tenth", "a second"), so "another {g3}" aired as
    "another a tenth". And a template that OPENS on a slot inherits that
    slot's case: `lines._sentence_case` fixes it centrally because 31
    templates open on one.
14. **A pool line must stand alone.** The bag can draw any line first, so a
    line written as a follow-up ("Neither of them is leaving anything on the
    table") airs as an orphan about nobody.
15. **Every line pool needs testing for the CATEGORY, but shared cooldowns
    need testing for the FAMILY.** `quali_standings` and `quali_top3` are
    both correct and aired back to back saying the same three names.
16. **A NUMBER IS NOT A FACT UNTIL THE LISTENER KNOWS WHAT IT IMPLIES.**
    "Two and a half bar of boost and a hundred and fifty litres to do the
    whole race on" is a correct statement of the 1988 regulations and told
    the user nothing — he asked what it meant. Every figure has to arrive
    with its consequence attached: *"a hundred and fifty litres for the whole
    race and no refuelling, so these drivers are turning the boost down and
    saving fuel while they race each other."* The same applies to jargon —
    "a low-rake car" is a term you either know or you do not, and a clause
    cannot lean on another line to explain it (LAW 14). A researched fact
    that has to be looked up is worse than no fact, because it sounds like
    the booth is showing off rather than telling you something.
17. **ONE SLOT NAME, ONE MEANING — ACROSS A WHOLE POOL.** The `stat` pool
    used `{n}` for laps-led, lead-changes AND cars-running, and the single
    caller filled it with `len(s.order)`. So "that's 20 laps in front" aired
    in a FIFTEEN-lap race: it was the size of the grid. Split into one pool
    per fact, each with its own slot and its own measurement. And if a line
    asserts something ("the top three are within a second"), something has to
    have measured it — two lines in that pool were pure assertion.
18. **HYSTERESIS ON EVERY THRESHOLD, INCLUDING THE ONE YOU FORGOT.**
    `BRAKE_HOT_C` had a trigger and no clear point, so a value that crosses
    it every lap — which brake temperature does, on every circuit — re-armed
    the warning every lap. Fifteen of the engineer's forty-five lines in one
    race were about brakes. Both a `_CLEAR` threshold AND a per-session
    `TOPIC_MAX` budget: a cooldown paces a repeated call, it does not stop
    one, and a condition that lasts all race needs both.
19. **A CARD MUST WAIT FOR ITS AUDIO.** `tts.speak()` only enqueues and a
    render takes 2-6s, so a radio card pushed straight after the speak call
    is on screen seconds before the voice. `release_cards()` holds it until
    `tts.now_playing` matches its text. The booth caption already did this;
    the cards did not. Rival cards pass `spoken=False` — they are never
    voiced, so they must not wait for audio that will never come.

20. **TEST WHICH POOL A LINE CAME FROM, NEVER WHAT WORDS ARE IN IT.**
    `_bag.json` persists across runs, so a pool draws a DIFFERENT line each
    time a test runs. Two checks written this session grepped the rendered
    prose for keywords and both were flaky — passing and failing at random,
    because one correct line in the pool happened not to use the word. A
    structural check cannot drift as prose is edited either.
21. **A POOL WITH NO CALLER IS INVISIBLE, AND `lines.py` CALLS IT HEALTHY.**
    Three times in one session: `booth_joke` (5 lines, never offered by any
    filler), and `incident` / `frustrated` / `pumped` / `pit` / `praise` in
    `rival.json` (40 lines, no trigger emitted any of them). The lines are
    valid, so validation passes; they are simply unreachable. `rivaltest.py`
    now greps the trigger source for every event name in the data file.
    **When you add a pool, prove something calls it.**
22. **A COLOUR SOURCE THAT RAISES COSTS A LINE, NEVER THE BROADCAST.** The
    booth is many independent sources feeding one ranker, and the filler asks
    all of them on every quiet tick. One wrong `getattr` in the career source
    therefore silenced the ENTIRE commentary for half a race — 2,618 swallowed
    tracebacks — and it read to the user as the overlay being switched off.
    Every source runs behind `_guard`, which returns a fallback and REPORTS
    the fault (deduplicated, with a count) instead of aborting the tick.
    A swallowed exception with no name is how the same bug survives two
    sessions of looking for it.
24. **NEVER COMPARE A FILTERED SIGNAL WITH AN UNFILTERED ONE.** Both sides of
    a delta must come out of the same filter, or the edge lands in the gap
    between them. `gained = p.place - newp` compared last tick's RAW place
    against this tick's DE-BOUNCED place; the de-bounce lags by seven ticks, so
    a real pass read as zero on the tick it happened and minus one on the next.
    **Every overtake call in the product was dead from the day the confirmation
    was added**, and twenty-five suites were green throughout because every one
    of them faked `confirmed_places` into the identity function (LAW 0, again).
    When you add a hysteresis, a confirmation or a hold, grep every comparison
    against the value it filters and convert them in the same change.
23. **READ THE LOG BEFORE YOU THEORISE.** Every hard bug in this project was
    found in `_session_log.txt` and none of them by a test suite. When the log
    and your model of the system disagree, the log is right. See the top of
    this file.
---

## rF2 DATA QUIRKS — all learned the hard way

These are the traps. Every one produced a visible bug.

| what | reality |
|---|---|
| `mPlace` | **255** for any car without a position yet — garage, pre-grid, and a tick or two after green. Folded into an arc it produced "he's climbed 31 places" on lap two. |
| classification | can be **scrambled** for a tick around a standing start and session changes. `_places_sane()` requires 1..N, no duplicates, before anything REMEMBERS a place. |
| `mSectorFlag` | **not a yellow indicator.** Sat at 11/1/2 for a whole race with `mYellowFlagState` 0. The session flag state is authoritative; sectors only name WHICH sector during a real yellow. |
| `Points` (XML) | only populated inside rF2's own championships — **89 of 132 races award zero to everyone** — and the table varies per mod. Points are computed from finishing position instead. |
| `CarClass` | some mods name a class **per TEAM**: 20 cars across 10 "classes". Locking a season to one locks it to a team. Guarded by `CLASS_SHARE = 0.4` in both `career.py` and `overlay_booth.py`. |
| `VehName` | names the DRIVER for some mods (`"Williams  05-Nigel Mansell"`) and the CAR for others (`"Honda HSV-010 GT #002"`). `career._veh_driver()` accepts only person-shaped strings. |
| `.mas` archives | vehicle `.veh` files are compressed — and for some mods ENCRYPTED, with no readable file table — so installed CLASS NAMES cannot be read from them. The class list comes from result XMLs. **The UI's MENU NAMES can be read, from the rF2 UI's own JSON cache — see `modnames.py`.** |
| `mInRealtime` | False through loading and in the garage. On some entry paths it only becomes true AT the green flag, leaving no room for a pre-race sequence. |
| result XMLs | `UserData\Log\Results\*.xml` — venue, real event name, class, grid, position, laps, best lap, DNF, `isPlayer`. The career is built from these. |
| `mSurfaceType` | **per wheel, for every car**, in telemetry. An excursion is a FACT here, not an inference — this is the one thing rF2 gives that RacerTV never had. 0 dry 1 wet 2 grass 3 dirt 4 gravel 5 kerb 6 special. A KERB IS NOT AN OFF. |
| `mBestLapSector1/2` | the sectors **of the best lap**, not best individual sectors — so the three add to `best_lap` and are safe to talk about. A "theoretical best" split across three laps describes a lap nobody drove. |
| `CarClass` per team | 2021/2025 F1 mods report `McLaren`, `Haas`, `Ferrari`... Nothing matched, so the era fell to `unknown_2020` — that is where "welcome to the 2020 season" and the missing DRS/ERS came from. `era._team_field()` reads the constructor list as a field AND dates the season from it. |
| `mTotalLaps` | can go backwards a lap and return (3→2→3 in the 2021 log). Anything edge-triggered on lap completion must tolerate it. |
| `mLapDist` | briefly NEGATIVE on the pit approach (-104 on a 4370m track). Harmless so far, but it is real and it is in every log. |
| `mStatusMessage` | **in `rF2Extended`, not in scoring.** So are `mTicksStatusMessageUpdated`, `mLastHistoryMessage`, `mCurrentPitSpeedLimit` and `mSCRPluginEnabled`. Three buffers are mapped — Telemetry, Scoring, Extended — and reading a field off the wrong one is an AttributeError on every tick, not a wrong value. `reader.extended()` returns None when an older plugin build has not mapped it, which must degrade the feature rather than raise. |

---

## THE INSTRUMENT — `gauge.py`

Rewritten this session; the dash no longer draws its own gauge.

**SIZE lives in `overlay_dash.Dash.GAUGE_R`, not here** — one knob, and every
other dimension (`H_SPEED_DIGITAL`, `COL_GAUGE`, `gauge_clear`, the flanking
pills) derives from it, so changing it needs no other edits. It went 96 -> 62
-> 68 on 2026-08-17 across two user requests. Cost is PIXELS and pixels go as
the SQUARE of the radius, so 68 is 50% of the original render cost. Verify a
size change with `python dashshot.py` and `python tests/paneltest.py` — the
latter asserts the keep-clear law still holds and that text/numbers still fit.

**Tk's canvas has no antialiasing at all.** That was the whole of the "looks
like pixel art" complaint — not palette, not layout, the renderer. The
instrument is now drawn with PIL at `SS`=3 and downscaled with LANCZOS, then
blitted as ONE `create_image`. Text stays with Tk, which is already
antialiased.

Two things learned the hard way and easy to undo by accident:

* **Flatten to RGB before handing Tk the image.** An RGBA PhotoImage with
  varied alpha takes ~65ms; the same picture as RGB takes 0.3ms. A 200x
  difference. Transparency survives because the panel is CHROMA-keyed and
  CHROMA is near-black, like the instrument faces — on a light key this
  would halo badly.
* **Pre-warm the cache, time-boxed.** A cache hit is 0.001ms, a miss 12-28ms,
  and while accelerating every frame lands in a fresh bucket — so lazy
  filling paid for itself exactly when the driver was looking at it.
  Budgeting by COUNT gave an 83ms frame, worse than the problem.

Gauge styles are picked by `gauge_style()` from the PERIOD SKIN, not from
`is_historic` (which means pre-1980 and let a 1990 Group C car through to an
LED shift ladder). `modern` and `lmp` are LED strips; the rest are rings.

**The shift cue is the feature the user singled out as most useful.** The
whole face changes colour. Violet for the F1 box and GT3, green for the other
modern cars, amber for the period dials, red on the limiter for all of them.
`shift` must NEVER equal `red` — WEC and DTM had both red and the two states
were indistinguishable. `paneltest` asserts every gauge changes and that no
palette uses one colour for both.

---

### "THE 2000 FORMULA ONE SEASON" — a live, game-breaking bug (2026-08-18)

The user started a **USF2000** career, and the booth opened qualifying with
*"the 2000 Formula One season"*.

**THE CAUSE, EXACTLY.** `_series_name` was a `@staticmethod` taking only the
session — **it had no access to the career at all** — so it inferred a name
from the CAR: `era.classify("USF2000")` reads the "2000" as a year and the
chassis as a single-seater, and the fallback turned that into a Formula One
season a quarter of a century ago.

**A GUESS ABOUT WHICH CHAMPIONSHIP HE IS DRIVING IS NOT A SMALL WRONGNESS.**
It is the line that exists to tell him career mode is running, and getting it
wrong tells him the overlay has no idea what he is doing.

**THE CHAMPIONSHIP NAMES ITSELF. THE CAR NEVER NAMES IT.** The order is now:

1. **The division**, for a ladder career — "USF2000", "Hot hatch", "Formula 3".
   The name on his own entry list, which is what he asked for: *"they must use
   the car class name as the title for the season"*.
2. **The locked car class** of a plain career.
3. A series `era.py` genuinely recognises BY NAME, with its year — this is
   what keeps "2025 Formula One" correct.
4. **The class of the car on track** — a real string off the grid rather than a
   category invented from one. This alone fixes the one-off case: a USF2000
   race with no career now says "USF2000".
5. A discipline word, and only for a season that can genuinely be dated.

The old guess survives at the bottom because it is right for the mods it was
written for (the 1988 F1 field has no series string and IS the 1988 Formula One
season) — and **it can no longer reach a career**, so by the time anything gets
that far there is no championship left to be wrong about.

`careerboothtest.py` §1b pins all four divisions by name and asserts USF2000 is
never called Formula One again.

### VARIANTS IN PROPORTION TO HOW OFTEN A POOL FIRES (2026-08-18)

The user, after every content pass in this session: *"please make everything we
added unique and not dry ... repetitiveness will be a real killer here."*

**THE ANSWER IS NOT A FLAT NUMBER, IT IS A RULE**, and `careerboothtest.py`
§1c now encodes it so the next pool added has to answer the question rather
than inherit whatever felt like enough on the day:

| fires | needs | examples |
|---|---|---|
| **every session** of a division he sits in for seasons | 5+ | `status_*`, `reg_*`, `ladder_rivalry`, `ladder_needle` |
| a few times a season | 3+ | `ladder_home`, `ladder_climb`, `ladder_record` |
| once in a career | 3+ | `status_arrival`, `ladder_home_win` — **a career is replayed** |

**AND NO TWO LINES IN A POOL MAY OPEN WITH THE SAME FOUR WORDS.** Six wordings
that all begin "{drv} is" are one wording with six endings, and the shuffle bag
cannot save a pool whose lines are indistinguishable by the time the listener
has heard four words of them.

`status_rookie` went from four lines to **nine** — it is the most-heard pool in
the file, because a driver is a rookie for an entire arc.

**THE REAL KILLER WAS A CADENCE, NOT A COUNT.** `news_needle` fired EVERY ROUND
once a rivalry existed, which would exhaust every wording inside one season and
then start again. It now runs at most **twice a season, every third round**
(`NEEDLE_EVERY`, `NEEDLE_MAX`) — because a paper does not run the same two men
bickering every fortnight either. It runs it when something happens.

Measured over the same ten-season career: **142 news items, 76 distinct
subjects**, against 89 items from eight kinds when this session started.

### RIVALRIES, THE NEEDLE, AND THE DISCLAIMER (2026-08-18)

Asked for: *"news stories about rivalries and jealousy — this is a very
narcissistic sport."* Built as three renderings of ONE detector.

**`Career.rivals()` IS THE ONLY THING THAT DECIDES A RIVALRY EXISTS**, and the
paper, the commentary and the standings all read it — so they can never
disagree about who is fighting whom. It is **true by construction**: two
drivers who have finished within two places of each other in most of the last
four rounds AND who are within a win's points of one another. Both halves are
required. Men who are close on points but never on the road together are having
separate seasons; two cars circulating nose-to-tail in fourteenth are not a
title fight.

**The player's rivalry wins, then the closest fight.** When he is dominant the
detector finds the scrap BEHIND him — which is what he asked for: *"it doesn't
have to be just for the player."*

**THE FACTS FIRST, THE NEEDLE AFTER** (`NEEDLE_AFTER` = 2 rounds). The spiky
piece lands on a rivalry the reader has already been shown rather than
announcing one, which is the order a real paper works in.

**THE BOOTH ONLY MENTIONS A PRESS CONFERENCE THAT WAS PUBLISHED.** `ladder_needle`
checks the archive for a `news_needle` article before saying "he had a few
things to say about you this week" — so the commentary can never refer to an
event the player cannot go and read. That is the same rule as everywhere else,
applied across two features instead of within one.

### I REFUSED THE INVENTED QUOTES, AND THE USER OVERRULED ME — correctly

My first version gated the needle to FICTIONAL drivers only, on the grounds
that a fabricated quote attributed to a real person is exactly what this
product refuses. The user's answer: *"the mod is just a dramatization ... if
you really want you can add a small disclaimer."*

**He is right, and the reasoning is worth keeping.** The rule this product
actually needs is *never state something FALSE that the user can check* — a
made-up championship, a race result that did not happen, a record that is
wrong. An obviously in-world quote in a fictional career is not a claim about
the real world at all, it is a dramatisation, and every racing game with a
rival system does it. The disclaimer settles the remaining ambiguity.

**Two restraints I kept anyway**, and both are craft rather than caution:

* **The needle is only ever about DRIVING** — pace, form, whether a rival has
  earned his reputation yet. Never anybody's character or private life. Real
  paddock needle is almost always about the racing, and a driver who insults
  another man's character reads as a cartoon.
* **`DISCLAIMER` is a PAGE, not small print.** On the main menu AND on the news
  tab, because a disclaimer filed three menus from the thing it is about is a
  disclaimer for the author's benefit. It also draws the line the product
  actually holds: **driver records are real and checkable; everything else
  about a real person here is invented.**

### ROOKIE TO LEGEND — the status arc (2026-08-18)

The user's ask, and it is the reward the whole ladder was missing: *"players
will work hard trying to get through the ranks, and a commentary line or news
report goes a long way in rewarding a player."*

`Career.status()` returns one of six, and **every threshold is something this
overlay watched him cross**:

| | when |
|---|---|
| **Rookie** | no completed seasons |
| **Riser** | a season behind him, no title |
| **Contender** | racing in a professional division |
| **Champion** | one championship |
| **Multiple champion** | two |
| **Legend** | three — `ladder.ENDING_ARCS`, the same number that ends a career |

**SEASONS COMPLETED, NOT RUNGS REACHED.** The first version read
`Progress.reached`, which is non-zero for anybody who JOINED a path partway up
— so a man in his very first season was already a "Riser", which is the exact
opposite of an arc that has to start at rookie.

**`status_changed()` WRITES, AND IT IS THE ONLY THING THAT DOES.** The booth
and the news feed both want "he has just become a champion", and neither should
have to remember it; one place remembers, so they can never disagree about the
afternoon the viewer just watched. **It only ever rises** — a sideways move
drops a driver into a junior division, and no sport has ever run the headline
"Kandasamy demoted to Riser".

**THE FLAG MOMENT IS THE POINT OF ALL OF IT.** `status_arrival` fires in the
four seconds after the chequered flag of the race that made him champion:

> *"From rookie to champion. Dante Kandasamy has had a meteoric rise in this
> sport, and I cannot wait to see what he does next."*

It cannot fire twice for one championship (the status is marked), a second
title gets `status_arrival_more` instead — which is not the same sentence —
and nothing of the kind is ever said mid-race.

**Five news kinds** ride the same signal: `news_status_riser` ("A rookie no
longer"), `contender` ("From nowhere to the front"), `champion` ("The rise
of…"), `multi`, `legend` ("The making of…"). They read `status_changed()`
rather than detecting a rise themselves, for the reason the milestones do: two
detectors eventually disagree, and the paper ends up arguing with Chuck.

**Where the status sits in the booth's order**: below the record lines, because
"eleven wins" is a harder fact than "champion"; above the nationality, because
what he has DONE beats where he is from.

### THE WHOLE PRE-QUALIFYING SEQUENCE WAS BEING THROWN AWAY (2026-08-18)

The user reported it twice: *"I didn't hear any mention of Rookie or anything
when I started the first quali."* The first fix — reordering `_ladder_call` so
a debutant is introduced before the seat above him is discussed — was correct
and changed nothing he could hear, **because the line was never being refused.
The entire pre-session sequence was being discarded before a word of it aired.**

```python
if events and max(PRIORITY...) >= PRE_YIELD:
    self._pre = []        # <- the whole programme, binned
```

**A QUALIFYING SESSION IS NOTHING BUT NEWS FROM THE FIRST TICK.** The sheet is
already full when the overlay attaches, those events outrank `PRE_YIELD`, and
so welcome / season / career / circuit were dropped every single time. In a
RACE the queue survives because the grid is quiet before the green.

It now **YIELDS THE TICK RATHER THAN THE PROGRAMME**: news still beats the
script, the sequence resumes when the sheet goes quiet, and `PRE_HOLD` (150s)
stops it dribbling out long after the moment has passed.

**MY UNIT TEST WAS THE PROBLEM, AND IT IS LAW 0 IN A NEW COSTUME.** I proved
`_ladder_call` returns `status_rookie` by calling it directly on a hand-built
Booth. It does. What no test did was run the REAL pre-quali path with live
events in the session — which is the only place the bug exists.
`qualitest.py` §16 now drives thirty ticks of a genuine qualifying session with
a full timesheet and asserts the rookie line and the season launch actually
air.

### THE ENGINEER KNOWS THE STATUS TOO (2026-08-18)

Asked for: *"if the race engineer could also be like, 'you're a rookie so just
get up to speed with the track and don't overdrive'."*

Six pools — `eng_status_rookie` through `eng_status_legend` — replacing the
greeting on the FIRST session of a division, where a driver's standing is the
most useful thing his engineer can be thinking about.

**IT IS HIS REGISTER, NOT THE BOOTH'S**, and that is the whole difference. The
booth says "the rookie, and nobody knows what he'll become". Dean does
something useful with the same fact: *"You're new to this. Get up to speed with
the track first — don't overdrive it."* A status in the booth is colour; a
status on the pit wall is ADVICE, and his 18-word cap keeps it that way.

### THREE THINGS FOUND BY DRIVING IT (2026-08-18)

**1. "That's proper racecraft, isn't it Chuck?" — IN A QUALIFYING SESSION.**
The `racecraft` topic had `"session"` in its `when` list. Every question in it
is about making a pass stick and every answer is about the man being passed,
which is nonsense on a Saturday when a driver is alone on the circuit looking
for two tenths. **One word in one list**, and every suite was green — because
the leak was in the DATA. `qualitest.py` §15 now sweeps every topic offered in
a qualifying session for race-only language. The `weather` topic was caught by
the same sweep: it asked what the weather was doing to "this RACE" and had an
answer about a two-stop.

**2. A brand new career never said the word "rookie".** The pre-race beat of
his first-ever USF2000 qualifying session opened with the PROMOTION line —
"there is a seat above this championship and P5 is what it costs" — because
that branch sat above the status call. Wrong sentence for the first minute of a
career: what a viewer needs on a debut is **who this man is**, and the seat
above is a thing to talk about once he has started racing for it. A driver with
no seasons and no rounds now gets `status_rookie` first.

**3. THE DASH ON A CARD NEEDED TIGHTENING, AND THE TIGHTENING BROKE THE OLD
GAUGES.** Both halves are worth keeping:

* Spacing is now two constants — `PAD_OUT` (6) and `GAP_COL` (7) — rather than
  seven scattered `UI(10)`s. Generous spacing was right while the dash FLOATED
  over the road, where the picture separates the blocks for you; on a card the
  same spacing reads as elements adrift in a panel.
* **THE GAUGE COLUMN RESERVED SPACE FOR PILLS THAT MIGHT EXIST**, not for the
  ones that do. Measured on the rendered preview: 64px of dead space against
  the card edge and 68px between the instrument and the damage block. It is
  computed per era now — and a STRIP gauge draws its DRS and ERS *inside* the
  screen, so it reserves nothing at all.
* **...WHICH THEN CLIPPED THE GEAR ON EVERY PRE-1980 CAR.** `_dash_analogue`
  draws the gear block OUTSIDE the dial to the left, and the column did not
  know. It is a flanking readout in everything but name, so `pill_sides` now
  reports it — and the offset itself was an unscaled `22`, which put it in a
  different place at every UI scale the user might run.

**The measurement mattered more than the fix, twice.** Both the dead space and
the clipping were found by rendering `dashshot.py` and counting pixels — empty
vertical bands inside the card, and ink against the border. `paneltest.py` now
checks the same geometry directly, so neither can come back silently.

### THE BUG THAT TOOK THE BOOTH OFF THE AIR (2026-08-18)

Reported as *"there was just no commentary for almost more than half of that
session"* and, in the same breath, *"I pulled up behind P1 to battle him for
the lead and the commentators said nothing"*. **Both were one bug.**

`Track.country` **is a method**. The home-race check in `_ladder_call` read it
as an attribute:

```python
nations_mod.is_home(nat, getattr(circuit, "country", ""))   # WRONG
```

`is_home` was handed a function object and raised in `_fold`. That would cost
one line — except **`_filler` asks for a career line on every quiet tick**, so
the exception aborted the whole filler each time. The log holds **2,618
identical tracebacks**. Everything the filler builds — battles, closing,
standings, track colour — was assembled and then discarded, tick after tick.
The lead battle he is complaining about WAS detected correctly, packaged with
its gap and its position, and thrown away eighty lines later by the raise.

Three things worth carrying forward:

* **The home-race line had never once fired.** The check raised every time it
  was reached, from the day it was written. A feature can be dead on arrival
  and still look implemented.
* **A method read as an attribute is truthy.** No `AttributeError` at the read,
  no `None` to check — it fails a long way downstream, in a utility with no
  idea who called it. `nations._fold` now refuses anything that is not a string
  rather than raising: a name-folder is the wrong place to be strict about
  types.
* `Track` has **six methods and zero properties** — `character`, `corner`,
  `corners`, `country`, `facts`, `overtaking`, `sector`. Sweep for bare
  attribute reads of these before touching circuit code.

### THE PASS WAS BEING DETECTED AND THROWN AWAY (2026-08-19)

The user: *"priority overtakes are still not being called, I literally took the
podium spot and the commentators said nothing."* He is right, and the mechanism
is exact.

`_say` refuses anything under priority 80 while audio is playing. `overtake` is
**60**. Detection is edge-triggered with no queue behind it. So a pass made
while Miles was mid-sentence was detected, packaged with its victim and its
position, and **binned on that tick, permanently**. In his own log at 3768s he
took P3 while the booth was talking about Borda and Juliano. `leadchange` (85)
is the only pass category that has ever survived a busy booth.

**THIS IS §5b-iii IN A SECOND PLACE.** The incident sting silencing its own
explanation was the same rule doing the same damage, and the fix is the shape
that already worked: `_overtake_report` speaks **sting, call, verdict in ONE
breath**, so the sequence cannot lose a tick to itself or to anything else.

**IT BYPASSES ONE RULE AND ONE ONLY.** The first version skipped every
cooldown, and `boothtest.py` §3 caught it in the first run: forty swaps
produced **sixty lines**. A booth that calls every place change the instant it
happens is not a fix for a booth that called none of them, it is the same
failure inverted. It now honours the global and per-category cooldowns and
bypasses only "never talk over the previous line" — and a refusal costs
nothing, because the caller falls through to the queue below.

**EVERY OTHER PASS GETS A FEW SECONDS INSTEAD OF NONE.** `_pending_pass` holds
a call for `PASS_RETRY` (6s) and re-offers it each tick until it airs or stops
being news. Cleared where it AIRS, not where it was offered — LAW 11 applied to
a retry.

**THREE THINGS WERE BUILT AND UNREACHABLE.** This is the fourth, fifth and
sixth dead pool this project has found (LAW 21):

| | |
|---|---|
| the `pass` stings | **six lines, rendered to disk at every startup since the sting module was written.** `_sting` had only ever been called for `lastlap` and `retire`, so not one of them has ever played. |
| `pulling_away` | six lines, a priority and a cooldown, **no emitter anywhere** — and it is the exact line the user asked for by name. |
| `photo` stings | three lines, still unreached. Left alone: there is no photo-finish detector to hang them on. |

**THE STING GATE IS THE WHOLE DESIGN** (`PASS_STING_PLACES` = 3, plus any pass
involving the player either way round). The user's call, and the reason it is a
gate rather than a volume knob: a sting cuts through everything, so if every
pass fires one the sting stops meaning anything and the brake-temperature
problem is rebuilt in the commentary.

**THE LAYERS OF A FIGHT**, all in `lines_data/booth_battle.json` and all
era-neutral by construction — three cars fighting over one corner is the one
thing about this sport that has never changed:

* **`pulling_away`** — the resolution. A fight that lasted `BATTLE_RESOLVE_MIN`
  and ended with the defender **escaping rather than being passed**. The gap
  crosses `STRIKE_GAP` out of every last corner on every circuit, so an escape
  needs a bigger threshold AND a hold (`BATTLE_CLEAR_GAP` / `BATTLE_CLEAR_HOLD`)
  — trigger and clear point, LAW 18. **A rival pitting is not somebody pulling
  away**, and the timing screen would say so.
* **`battle_three`** — three cars for one place, held for `THREE_WAY_HOLD`. Not
  two adjacent battles: the middle man is in both of them and cannot commit
  forward without opening the door behind, which is the entire situation.
* **`battle_traded`** — the same two men swapping a place `TRADE_MIN` times
  inside `TRADE_WINDOW`. Counted per PAIR at detection, so the number is true
  whether or not the booth got to say it (LAW 17). **The lead is exempt**: a
  lead changing hands repeatedly is already the biggest call the booth owns.

`tests/passtest.py` holds all of it, and **§3 is the failure mode itself** — a
pass made with `tts.speaking` True. Twenty-two suites were green while this bug
was live, and none of them could have caught it for one reason worth keeping:
every one of them asserts what the booth says when it is FREE TO SPEAK. Not one
drove it while it was busy.

### THE FENCE — one broken source cannot silence the booth (2026-08-18)

Asked directly: *"so you sure the commentary won't break again if I try
again?"* The honest answer is no, and that answer is why this exists.

The booth is a pipeline of independent sources — battles, the career, the
circuit, the archive — feeding one ranker. Any one of them raising used to
abort the entire tick. Because the filler is the most frequent caller in the
product, **a fault in a constantly-firing source is indistinguishable from the
commentary being switched off**, and `update_booth` swallowed the traceback at
the top of the tick so nothing said otherwise.

`BoothMixin._guard(label, fn, *a, fallback=...)` runs one source. If it raises:

* it returns `fallback`, and the OTHER sources on that tick still rank and air
  — a broken source costs its own line, never the broadcast;
* it reports through `_log`, **deduplicated by fault signature with a count** —
  first three occurrences, then 10 / 100 / 1000. The bug above would have
  produced five log lines instead of 2,618;
* a NEW fault is never hidden behind an old one: the signature is the last
  frame plus the exception.

`_pre_stage` has the same fence with one addition — it names the STAGE that
failed and puts it back on the front of the queue **once**, so a transient
failure on a half-built first tick delays the rookie line by a beat instead of
losing it. A stage that fails twice is genuinely broken and is dropped.

`_log(tag, msg)` writes to the console and appends to `_session_log.txt` when
it exists. It is the channel for *"it was attempted and it failed"*, which is
the thing the overlay previously had no way of saying.

**Do not remove either fence to "surface errors properly".** The errors were
already being swallowed — by the catch-all in `update_booth`, silently. The
fence is what makes them visible.

### A FIGHT FOR THE LEAD OUTRANKS A MIDFIELD MOVE ANYWHERE IN A RACE (2026-08-18)

`LATE_FRONT_BONUS` (60) was gated to the `late` and `closing` phases, so for
the entire body of a race a P4 overtake scored **76** against a lead battle's
**70**. Raised twice by the user, and he is right on the merits: a fight for
the lead on lap nine is not colour to be weighed against a midfield pass, it is
the race.

`FRONT_BONUS` (34) now applies in every phase. Scores: mid-race lead battle
**100** vs P4 overtake **76**; closing laps still **126**. Both bonuses stay
gated on `_front_fight_live` — a leader nine seconds clear is a procession, not
a fight — and on the top two places, so the wide view of the race survives
everywhere except the one place it is being decided.

`flowtest.py` had been asserting the OLD rule (*"the override does NOT apply
mid-race"*). It was replaced with the new contract rather than worked around.
**A test that encodes a decision the user has since reversed is not protection,
it is a fossil.**

### THE BOOTH CALLS HIM BY WHAT HE IS (2026-08-18)

Asked for as: *"the booth should basically call me by two things, either my
name or my status — either 'Dante Kandasamy', 'The Rookie', 'Dante Kandasamy
the Rookie' or 'The Rookie Dante Kandasamy'"*, and *"that first mention of me
[should come] the first time I'm mentioned — let's say it's a quali and I spin
off track, then 'That's Dante Kandasamy off the road there', 'that's the new
rookie this season'"*.

* `_status_form(s, name)` decorates the PLAYER's name only, and only inside a
  ladder career. The first mention in a session is `"Dante Kandasamy, the
  rookie,"` or `"the rookie Dante Kandasamy"`; afterwards it is his name, with
  the bare status form returning about one mention in five. The choice is
  seeded on the session, so a line composed five times before it airs keeps one
  wording. It re-arms at every new status level, because the label comes from
  `career.status()`.
* Wired into `_kw` through `nms()`, so **every pool gets it for free** — the
  spin call, the overtake call, the engineer's report. This is also why
  templates must never write a determiner before a slot: `"the {drv}"` becomes
  "the the rookie".
* **LAW 11 applies and is easy to get wrong here.** `_kw` composes far more
  lines than the booth ever speaks. The flag flips in `_say` AFTER the line
  airs, never in `_kw` — otherwise the introduction is spent on a sentence
  nobody heard. `careerboothtest.py` §21 asserts this against the SOURCE of
  `_kw`.
* `_status_call` fires the follow-up thought 2.5s later — who he is and what
  may come of him — reusing the same six `STATUS_CATS` pools the pre-session
  career beat draws on. Whichever route says it first sets `_status_told` and
  blocks the other for that session. Not forced: a real incident outranks an
  introduction, and it waits for the next gap, giving up after 90s.

### TESTING: THE MISTAKE I MADE THREE TIMES (2026-08-18)

The rookie line was reported missing **twice**, and I "fixed" it twice without
fixing it, because my test called `_ladder_call` directly on a hand-built
`Booth` shim instead of running the real pre-qualifying path. The shim also
overrode `_kw`. **Both bugs lived in exactly the code the shim replaced.**

This is LAW 0 wearing a new costume, and it is the most expensive habit in this
project:

* A shim that overrides the method under suspicion tests the shim.
* Where a unit test cannot reach the real path, **assert against the SOURCE**.
  §21 greps the body of `_kw` for `_status_named = True` — crude, and it holds
  a property no shim could.
* Reproduce the FAILURE MODE, not the fix. §24 makes a source raise on purpose
  and asserts the booth keeps working.
* When the user reports the same thing twice, **the second report means the
  diagnosis was wrong, not that the fix was incomplete.**
* `testrun.py` truncated tracebacks to 600 characters — which is exactly the
  four frames ABOVE the interesting one. It keeps the tail now. A diagnostic
  that discards the diagnosis is worse than none, because it looks like one.

### THE DASH SITS ON A CARD (2026-08-18)

`_dash_body` used to draw nothing on purpose — the panel window is
chroma-keyed, so an empty body let the instruments float over the road. The
comment left behind said a future opaque mode had one obvious place to live,
and this was it. The user tried the floating version in the car and asked for
the card: **the rest of the overlay is a set of slabs, and one element with
different rules reads as an element nobody finished.**

**AND THE GAUGE CAME OUT AS A STICKER.** `gauge.photo()` flattens its RGBA
render onto an opaque colour — a 200x speedup over handing Tk an alpha image —
and that colour was CHROMA, which was invisible while the dash floated and is a
near-black square on a navy card. `gauge.set_backdrop()` now takes the panel
colour, **it is part of the cache key**, and the cache is cleared when it
changes so an era switch cannot serve the old ground.

`dashshot.py`'s stub host had to gain `DrawMixin` for the shared `_body`.
Duplicating that drawing in the preview instead would let the preview drift
from what the overlay renders, which is the one thing a preview must never do.

## THE BOOTH KNOWS WHOSE CAREER THIS IS — built 2026-08-18

`lines_data/booth_ladder.json` (11 pools), `BoothMixin._ladder_call` and
`_register_call`, a `career` beat in the pre-race running order, and
`tests/careerboothtest.py`.

Asked for directly: *"the commentary is a big part of the gameplay and pushing
the story of the player's career."* Until this, the booth knew the race, the
circuit, the cars and 72 real drivers — and nothing at all about the career
being played. A man in his third season of Formula 3, who won karting two years
ago with a Formula 2 seat riding on the afternoon, was "the driver in fourth".

**EVERY FACT IT SAYS WAS WATCHED.** `Career.resume()` and `evaluate()` —
seasons this overlay recorded, races it timed, championships it scored.
Nothing is looked up and nothing is invented, **which is exactly why it works
on a fictional GT4 grid**: we are not claiming anything about the AI, we are
talking about the man the viewer is driving, whose whole record we have. This
is the answer to the problem that made ladder commentary look impossible.

**ORDERED BY WHAT THE CLAIM IS WORTH RIGHT NOW**, not by how impressive it is:

| | |
|---|---|
| `ladder_last_chance` | final round, promotion on the line — beats everything |
| `ladder_reigning` | first race up, as the champion of the division below |
| `ladder_first_race` | first race up, without one |
| `ladder_title_run` | two rounds left with a seat still in play |
| `ladder_promotion` | pre-race: what the seat above costs |
| `ladder_arc` / `ladder_record` / `ladder_climb` | what he has done |

A first-season driver gets NOTHING — no padding, the same discipline the real
driver records follow. `ladder_reigning` is only true while it IS last season
(`resume()["reigning_now"]`); a man who won Formula 4 two rungs ago is not the
reigning anything.

**REGISTER IS A TONE, NOT A KNOWLEDGE BASE**, and that is what makes the
grassroots rungs presentable at all. `reg_grassroots` / `reg_junior` /
`reg_professional` say what KIND of racing this is — *"nobody out there is
being paid to do this"* — which needs no history whatsoever. A club meeting
sounds like a club meeting without anybody inventing a club driver's
biography. **The historic tour gets none of them**: it already has its own
programme in `booth_archive.json` with Brett in the chair, and a second voice
over it is two shows at once.

**WHERE IT AIRS:**

* A **`career` beat in `PRE_RACE` and `PRE_QUALI`**, immediately after the
  season beat — "round four of six" and "and a Formula 2 seat rides on it" are
  one thought. Before the circuit beat, because a viewer wants to know who he
  is watching before he is told where they are.
* As **colour in the race**, with the driver briefing, ranked on staleness like
  everything else — and therefore **behind the opening and closing phase
  gates**, because a career fact during the run to the flag is the booth
  looking away from the race. `careerboothtest.py` §9 asserts the ordering in
  the source itself.
* **`LADDER_FAMILY_GAP` = 420s across all eleven pools** (LAW 15). "No
  television money in this paddock" followed by "he came up through every rung
  of this" is one thought said twice, which is why the register lines are in
  the family rather than beside it.

**THE SAME GATE THE DRIVER RECORDS USE**: a career stays loaded in the settings
for as long as it exists, so a race that is not one of its rounds says nothing
about it. Without that, a one-off race for fun gets a broadcast about a
championship it has nothing to do with.

**Still not heard in a live session.** Verified by direct calls and by
rendering every line against a real career, not by driving one — the same
caveat §5c carries, and the same fix: `python testrun.py`.

## THE CAST — settled, do not change without asking

`PLAY` is a **seat**, not a person. Two men sit in it, resolved by era in
`cast.set_era()` / `occupant()`:

| | voice | when |
|---|---|---|
| **Miles Crawford** — play-by-play | `en-GB-RyanNeural` | 2000 onwards |
| **Brett Calloway** — play-by-play | `en-AU-WilliamNeural` | before 2000 (`HISTORIC_BEFORE`) |
| **Chuck Brannigan** — analyst | `en-US-AndrewMultilingualNeural` @ +4% | always |
| **Dean Mackenzie** — engineer | `en-GB-ThomasNeural` | always |

Brett's `does`/`never` sets are COPIED from Miles at import — two
hand-maintained lists would drift. Every pool, `can_say()` and `who_says()`
still says `PLAY`, so swapping the man changes voice, name and caption colour
and nothing else. **Do not add a parallel persona key.**

**Biographies constrain what they may say:**

* Chuck is a **NASCAR Cup champion, stock cars 1985–2006**. He has never
  driven a Formula One car. "I remember the wheel fighting you everywhere"
  about a 1988 F1 car is false twice over — `eratest.py` greps for
  first-person driving claims not gated to `disc: ["stock"]`.
* Brett is a **WEC champion** — endurance and sportscars, also never F1.
* Neither of them was AT an archive race. They are modern broadcasters
  presenting old footage; they do not know how it ends (the user is driving
  it), and they never name a year, a circuit's history or a real result.
  Those rules are written into `lines_data/booth_archive.json` and asserted
  in `flowtest.py` §17.

**Voice lessons already paid for:**

* An unknown voice name does NOT raise — it silently falls back to robotic
  offline SAPI. `en-US-DavisNeural` does not exist. `_verify_voices()` live
  renders anything absent from `list_voices()`.
* **Any edge-tts failure also falls back to SAPI**, which is what a "robotic
  female voice at random points" actually is. `_render` now retries — same
  voice, then the fallback voice, then SAPI — and counts every fallback in
  `tts.sapi_falls`, which `testrun.py` logs. The 47-minute run had **1**.
* Pitch shifting is what makes neural voices sound fake. Energy comes from
  rate and volume. **This was proved by ear**: the user reported Miles and
  Brett sounding "sped up and robotic" while Chuck "sounds super natural".
  Miles sat at +8%/+2Hz against Chuck's +4%/+0Hz, and because `tts._HYPE`
  ADDS to the resting values he was faster at every intensity and pitch-
  shifted at all of them. Chuck was the only booth voice never shifted at
  rest. **All three now share Chuck's resting values — do not raise them.**
* There was a dead `cast.intensity_voice()` that added +6% rate and +3Hz per
  level and was called by nothing. It has been deleted, because it LOOKED
  like the excitement knob: anyone tuning delivery would have edited it and
  heard no change. The real ladder is `tts._HYPE`.
* Changing any rate or pitch invalidates the audio cache (it is part of the
  key), so the next session re-renders. That is expected, not a fault.
* Rival driver AUDIO is removed entirely — edge-tts has no Dutch or Italian
  accented English and a full grid came out as a few approximations. The
  cards and captions stay as a graphic.

---

## THE SHAPE OF A BROADCAST

* **`PRE_RACE`** = intro → archive → season → scene → history → grid → format,
  drained a beat at a time by `_pre_stage()`. The green flag is a hard cut: if
  the intro has not aired, welcome and lights-out become the same beat. News
  also ends it (`PRE_YIELD`).
* **`POST_RACE`** = podium → championship → verdict → signoff, then the outro
  sting.
* **`_race_phase()`** scales with length: a 5-lap dash gets one opening lap
  and a two-lap run-in, a 60-lap race gets a settling lap and eight. Timed
  races phase on the clock. `_length_class()` reads MINUTES, not laps.
* **THE PHASE CONTROLS TWO DIFFERENT THINGS, and they are easy to confuse.**
  `FOCUS_LIMIT` controls how DEEP into the field the booth will look
  (opening=5, mid=99, late=8, closing=5). Separately, `_filler()` now
  withholds the whole COLOUR tail (driver history, car/team character,
  circuit facts, jokes, `story_ask`/`driver_ask`) during `opening` and
  `closing` — that is what fixed "the commentary is very random right after
  lights out". A phase change may need one, the other, or both: widening
  what the booth LOOKS at is `FOCUS_LIMIT`; changing what it may TALK ABOUT
  is `_filler`. See WHAT TO DO NEXT §5c for the work still outstanding here.
* **Filler rotates by STALENESS, not priority** (`_rank_filler`). Strict
  priority meant the same four categories won every slot. A change of voice
  is worth 30s of staleness, which cut the longest same-voice run from 5 to 2.
* **Claims about the race so far need a race** — `_enough_race()`: 3 laps AND
  15% distance. A midfield FIGHT is callable from lap one; a recovery DRIVE
  is not.
* **Conversations**: `lines_data/crosstalk.json`. A topic may bind answers to
  each question (`qa`) — required for anything not open-ended, or "Is
  Silverstone a driver's track?" draws "Everything, and all at once".
  Question and answer are queued in the SAME breath: `tts.speak()` only
  enqueues and a render takes 2–6s, so scheduling the reply for later meant
  it landed in the silence its own render created.
* **Captions follow the AUDIO** (`tts.now_playing`), never the queue, and
  only for booth seats — the engineer has his own card. They live in a narrow
  box on the bottom edge beside the track map, positioned from the rectangles
  the map and sector strip publish each frame.

---

## CAREERS

Two layers, both built.

**`career.py` — history.** Folds rF2's result XMLs into `_career.json`:
per-circuit and per-class visits / wins / podiums / best / last / DNFs, plus
a driver roster per class. Scanned on a daemon thread at startup. Feeds
`career_won_here`, `career_back`, `career_first_visit` and the driver picker.

**`season.py` — championships.** Careers live in `careers/*.json`; presets in
`lines_data/seasons.json`.

* **Format:** New Career is preset → length → car class → driver name.
* **FIXED CALENDARS ARE GONE.** The `f1_2021` / `f1_2025` presets were
  removed at the user's instruction on 2026-08-16, and for a good reason
  found in his log: his 2021 career was a five-circuit calendar and he raced
  at Montreal, which was not on it, so `match()` returned None and the whole
  career was invisible for the session — no round, no prompt, no context.
  **The only format is the OPEN season, and the season's identity lives in
  the CAR CLASS.** Do not reintroduce calendars.
* **A TEAM-NAMED GRID IS ONE CHAMPIONSHIP.** The 2021/2025 mods name a class
  per constructor, so "McLaren" covers two cars of twenty and no single class
  passes `CLASS_SHARE` — the picker offered nothing at all. `_fold_field()`
  records the whole grid as one entry labelled by era ("Formula One 2021"),
  and the career stores its constructors in `cls_any` so any of them matches.
  Guarded by `era.team_field()` so a GENUINE multi-class race (GT4 + STW +
  GT500) is not merged into an invented championship.
* `career.HIDE_CLASSES` is a user-curated blocklist — three real classes the
  user does not want offered. Not inferable from any rule; leave it alone
  unless he asks.
* **The good format is the OPEN season with a declared length**: *N races,
  any circuit, one car class*. No calendar to own, immune to which tracks are
  installed, and because the total is known it still gets round numbers and
  exact title maths. Prefer it.
* Fixed calendars (`f1_2025`, `f1_2021`) are filtered to circuits actually
  installed (`track.installed()` reads `Installed/Locations`) and renumbered
  1..N. On this machine F1 2025 yields 8 runnable rounds of 24.
* A repeat circuit in an open season is a NEW round, unless it is the round
  just raced — that is a re-run and replaces it.
* `Career.phase()` gives the season its own shape: opener / early / midway /
  late / finale, driving `season_midway`, `season_late`, `season_finale`.
* `season_launch` fires on the first session of a career, in QUALI as well as
  the race, so career mode is audible: *"Welcome to the opening round of the
  1988 Formula One season — 5 rounds, and one of them will decide a
  champion."*
* Qualifying results are recorded (`record_quali`) so the engineer can open a
  session with where you qualified last time.
* Recording happens ONCE, at the chequered flag, in the win bookend.

**The menu** (`overlay_panels.py`) has pages: main, career, career_new,
career_len, career_cls, career_name, career_load, career_delete, confirm.
Everything destructive routes through confirm. It works with no session
loaded — that is when a career gets configured.

---

## WHAT TO DO NEXT

In the order the user signalled on 2026-08-16, after testing 1988, 2021 and
2025 F1. Items 1-3 are all CONTENT and all in one theme: the booth knows the
race but knows nothing about the SPORT.

### 1. Real-world motorsport knowledge — BUILT (2026-08-17). See DRIVERS below.

### 2. Era-specific car and team character — BUILT (2026-08-17). See CARS AND TEAMS below.

### 3. Jokes, banter and digs — BUILT (2026-08-17). See LEVITY below.

### 4. Track facts — DONE (2026-08-17). See CIRCUITS below.

### 5. Speedo lag — DIAGNOSED AND FIXED 2026-08-17. Stop shrinking the gauge.

The honest fix this section demanded for two sessions was finally done:
`frametime.py` instruments **every stage of the real `_tick_body`** on the
real Overlay against `preview.py`'s synthetic race, and reports mean/p95/worst
per panel plus whole-frame cost against the tick budget.

```bash
python frametime.py            # 360 frames, per-stage + whole-frame
```

**The gauge was never the bottleneck.** It measured 4.3ms, which is why two
sessions of shrinking it never fixed anything. Four real causes, all found by
measuring, all fixed:

| | was | now |
|---|---|---|
| whole frame, mean | 33.5ms | **21.0ms** |
| p95 / worst | 43.7 / 59.6ms | **26.2 / 35.5ms** |
| frames over the 50ms budget | 4-5 in 300 | **0 in 300** |
| `draw_map` | 4.5ms | 0.74ms |
| `draw_dash` p95 / worst | 17.2 / 20.9ms | 3.1 / 5.4ms |

1. **THE TICK PERIOD WAS NOT A PERIOD.** `tick()` ended with
   `after(UPDATE_MS, ...)`, which is 50ms after the frame FINISHES — so the
   real cadence was work + 50ms ≈ 82ms, or **12Hz for a panel set nominally
   running at 20**. This is the single biggest cause of "the speedo lags": it
   was not a late value, it was a redraw rate. Now scheduled from the frame
   START (`max(1, UPDATE_MS - spent)`), which is a true 20Hz. The 1ms floor is
   load-bearing — an overrunning frame must still yield to Tk.
2. **The map redrew a static outline with up to 4000 `create_oval` calls,
   twenty times a second.** It is now baked into one image and blitted as a
   single `create_image`, exactly as `gauge.py` does, with the same RGB-flatten
   and supersample lessons. Keyed on a BUCKET of the point count
   (`MAP_BAKE_STEP`) so a cloud that is still growing does not rebuild every
   frame. This was the most expensive panel in the product, for a picture
   identical to the one before it.
3. **`gauge.prewarm` overran its budget by a whole render, every time.** The
   deadline was checked at the BOTTOM of the loop, so a 6ms budget cost 6+20ms
   — and a cold cache coincides exactly with hard acceleration, which is when
   the gauge is being looked at.
4. **So the render moved off the Tk thread entirely** (`prewarm_async`). This
   REVERSES a decision recorded in `gauge.py` — "nothing left worth the
   complexity of a thread" — and the reversal is correct because the
   RGB-flatten fix had already cut the Tk half from 65ms to 0.3ms, moving the
   whole cost into `render()`, which is pure PIL. Making the sync budget
   stricter instead was tried first and was WORSE: it starved the prewarm, the
   cache never completed (76 of 97 buckets after 300 frames) and the same
   stall reappeared as lazy `photo()` misses. The cache now fills in ~2.5s and
   lazy misses only happen in the first second of a session.

**`GAUGE_R` is no longer the lever, and there is no reason to touch it again.**
If lag is reported, run `frametime.py` first. The next candidates are
`draw_tower` (3.9ms, scales with grid size) and Tk's own repaint, which is
roughly a third of the frame and is what the per-stage numbers do NOT include
— compare the stage sum against the whole-frame mean to see it.

### 5a. Speedo lag — the ORIGINAL section, kept for its reasoning

Never reproduced in a benchmark (gauge alone: 4.3ms mean, 0 frames over the
50ms tick), so the real fix — instrumenting per-panel draw time across a full
20-car frame — was never done. What happened instead, on the user's own
request, is `overlay_dash.Dash.GAUGE_R` was cut **96 -> 62 -> 68** across two
asks in the same session (35% down, then back up ~10%). Since the gauge is a
PIL image at supersample `SS=3`, cost is pixels, which is radius SQUARED:
68² / 96² = **50% of the original pixel cost** — a real, structural win
whether or not the gauge was ever the actual bottleneck. If the user reports
lag again, `GAUGE_R` is the fastest lever, but the honest fix is still to
instrument the whole frame — do not keep guessing at the gauge indefinitely.

### 5b. Off-track detection and the engineer's reaction — BUILT 2026-08-17

The user's report, in his own words: RacerTV played a sting from the pundit
the instant someone ran wide ("Sorry to cut you off, Miles, but there's been
an incident"), THEN the named call ("Nigel Mansell runs wide there"), THEN
the engineer — encouraging for a small one ("Lost a few places, keep your
head down"), checking in for a big one ("Are you okay? Tell me if the car
feels fine"). None of that was happening. Three real gaps, all now fixed and
tested in `tests/offtracktest.py` §9-12:

1. **The sting only fired for `"spin"`, never `"offtrack"`.** A car with all
   four wheels off got no cut-in at all — see `overlay_booth.py`, the
   `if ev in ("spin", "offtrack"):` block (search for "STING FIRST, NAME
   SECOND" — both severities now call `_incident_sting` before naming
   anyone, same as RacerTV).
2. **rF2's own track-limits warning was never read.** It lives in
   `mStatusMessage` / `mTicksStatusMessageUpdated` in the **EXTENDED** buffer
   (`rF2Extended`), which is its own memory map with its own handle — NOT in
   scoring, and reading it off `mScoringInfo` is what took the whole overlay
   down on its first live launch (2026-08-17; see LAW 0). It was
   present in `rf2_data.py` the whole time, unused. Now surfaced as
   `Session.status_message` / `status_message_new` (edge-triggered) in
   `rf2_session.py`, and consumed by `BoothMixin._track_limits_ground_truth`
   as a BACKSTOP for the case the surface detector can miss (a car that runs
   wide onto grippy tarmac and loses no speed). Keyword-gated to
   "track limit" / "cut track" / "off track" / "exceeded track" so a penalty
   or pit-instruction message sharing the same buffer is never mistaken for
   an off.
3. **The engineer had exactly one tone.** `eng_incident` ("are you okay?")
   fired for everything or nothing. Added `eng_offtrack_light` in
   `engineer.json` for a tidy-up — *"Lost a few places there. Keep your head
   down and do what you can."* Severity now splits on the SAME `kind` the
   booth already grades excursions by: `spin`/`offtrack` -> `eng_incident`,
   `ranwide` -> `eng_offtrack_light`. See `overlay_radio.py`, the
   "SEVERITY DECIDES THE TONE" comment in the excursion-handling block.

**A testing lesson worth keeping**: the first version of the severity test
matched the RENDERED text, and it was flaky against `_frame()`'s random
opener/lowercasing (see LAW 20/21 below — this is the third time in one
session a text-match test went flaky for the same reason). Fixed by
monkey-patching `RadioMixin._radio` to record which CATEGORY was chosen,
never comparing strings. Confirmed stable over 12+ runs.

### 5b-ii. QUALIFYING GOT NONE OF IT — fixed 2026-08-17 (second pass)

The user, after driving it: *"I was in a quali and I went off while trying to
do a lap, and neither did the commentators say anything about firstly going
off the track and secondly chalking off a lap, but also the race engineer who
I would've expected to tell me about the track limits ... didn't say
anything."*

**All three silences were ONE structural cause.** Every excursion check lived
inline inside `_detect`, and a qualifying session is routed to
`_quali_detect` — a completely separate function. So for a whole qualifying
session nothing looked at the surface at all. And because `player_off` is
published by that code and nowhere else, the engineer was silenced by the same
omission: he was not missing lines, he was never told.

* **`_excursion_events()` is now its own method**, called from BOTH detectors.
  An off is an off in any session; what CHANGES is what it costs, and that is
  the caller's business.
* **The booth's incident pools needed no qualifying variant.** `ranwide` and
  the offtrack pools are written about the MOMENT — "runs wide there and
  bleeds a little time" — and never about places lost, so they are as true on
  a hot lap as in a race. Checked before assuming it.
* **The ENGINEER's did.** `eng_offtrack_light` says "lost a few places there",
  which is a race sentence: an off on a Saturday costs a LAP. New
  `eng_offtrack_quali` — *"That's the lap gone. Take a breath, cool the tyres
  and set up another one."* A spin or four wheels off still gets
  `eng_incident` ("are you okay"), because that question is about the driver,
  not the session.
* **`_quali_radio` consumes `player_off` FIRST, before the sheet.** An empty
  sheet returns early, and the first off of a session usually happens before
  anybody has set a time — which would have dropped it all over again.

**A sting-ordering bug fell out of this.** `_stings` was bound lazily inside
`_bookends`, and `_tick_body` runs DETECTION BEFORE BOOKENDS — so on the
opening tick of a session the bank was still None while the detectors ran, and
an incident on that tick got no alert. Now bound on first use by
`_sting_bank()`, so the ordering dependency is gone rather than moved.

### 5b-iii. THE INCIDENT SEQUENCE — sting, name, reaction (2026-08-17)

**A STING WAS SILENCING THE LINE THAT EXPLAINED IT.** The live log settles it:
three alerts in one qualifying session, and not one of them ever followed by
a name.

```
[1861.5s] STING    alert     Wait — we've got a car in trouble!
[1861.5s] SAY      ENGINEER  Are you okay? Talk to me.
                             ...and nothing else. Ever.
```

The mechanism is exact and reproducible: `offtrack` carries PRIORITY 50,
`_say` refuses anything under 80 while audio is playing, and **the sting is
audio**. So the alert reliably killed its own explanation, and because
detection is edge-triggered there was no second chance. The `ranwide` calls
aired fine all session — because `ranwide` fires no sting.

The fix is the shape the user asked for: *"the sting from the pundit ... then
the pundit must also report on the incident directly after that ... then Miles
will say 'unfortunate for him, let's hope he recovers'"*. `_incident_report`
speaks all three beats **in one breath**, the way the crosstalk two-hander
already does, so nothing can lose its own tick:

| beat | who | pool |
|---|---|---|
| the interruption | sting (ANALYST caption) | `alert` |
| the name | **Chuck** | `incident_id_off` / `incident_id_spin` |
| the reply | **Miles** | `incident_react` |

* **The pundit names it because the pundit interrupted.** He owes the viewer
  the identification, and it hands the play-by-play seat a reply to make —
  which is what turns an announcement into a booth, and makes the caption
  colour change with the voice.
* **Cutting into a conversation keeps its apology**, in the other direction.
  `offtrack_cut` is Miles apologising to Chuck and is now the wrong way round,
  so `incident_cut_id` is the mirror. **It never names the man being
  interrupted** — `PLAY` is a seat and Brett holds it before 2000, so "sorry
  Miles" would be wrong half the time. `offtrack_cut` can safely say "Chuck"
  because the analyst chair has one occupant; this direction cannot.
* **The alert stings were rewritten as INTERRUPTIONS.** The old set was mostly
  exclamations ("Ooh, that's a mistake!"), which is a reaction to something
  already described. Six lines in the user's own register were added: "Hold on
  — there's been an incident!", "Sorry to cut in...".
* Escalation is unchanged: `INCIDENT_SEQ_GAP` (14s) means a second incident
  inside the window falls through to the single-call path and still gets
  `offtrack_more` / `offtrack_chaos`. Only the first is a sequence.

### 5b-iv. THE BOOTH'S TWO KNOWLEDGE SOURCES WERE CONTRADICTING EACH OTHER

From the same log, twenty minutes apart, about the same man:

```
[1235.7s] Lando Norris is still looking for that first Grand Prix win.
[2342.1s] This is happy ground for Lando Norris — a winner at Albert Park already.
```

**Both lines were "correct".** The first is Norris's real 2021 record from
`drivers.py`. The second is `career.py` reporting that the USER has won at
Albert Park, wearing the name he races under. A viewer cannot see the seam and
simply hears the booth contradict itself.

`_record_denies_win()` is the rule: **when the two sources disagree about a
WIN, the driver record wins**, because it is the one the booth has already
been quoting all session and the one a viewer can check. Only the win
collides — "you have raced here", "you were on the podium here", "you retired
here last time" are claims about the user's own weekend history that nothing
in `drivers.py` contradicts, and they are untouched. Silent for any driver
outside the three seasons `drivers.json` holds.

**Also fixed from the same log**: `hist_reigning` contained *"Doing it twice
is a different problem"* — written for a first-time champion and aired about a
SEVEN-time one. Now "doing it again", which is true at any number.

**The underlying data was re-audited and is correct.** All three seasons check
out as of each opener: Hamilton 95 wins / 7 titles and Verstappen 10 in 2021,
Senna 6 and Prost 28 in 1988, Hamilton 105 and Norris 4 in 2025, every team
right. The two errors the user heard were both structural, not data.

### 5b-v. THE ENGINEER: THE SLIDE, AND COACHING IN A RACE

* **He noticed only one kind of place loss.** `off_place` tracks what an
  excursion cost; a driver simply being passed lap after lap got nothing —
  the most ordinary bad afternoon in racing, and the one a driver most wants
  acknowledged. `_slide_call` + `eng_places_lost`. THE REFERENCE IS THE BEST
  PLACE HELD, not the grid slot: a man who qualified nineteenth, climbed to
  twelfth and slid to sixteenth has lost four places in the race he is
  actually living in. Guarded by `PLACES_SLID_HOLD` (a drop must PERSIST —
  rF2 publishes scrambled-but-valid orders around restarts), it resets its own
  reference so a long slide is reported in steps rather than re-announced with
  a bigger number, and `TOPIC_MAX["slide"]` caps it at three.
* **Sector coaching was qualifying-only.** `_race_sector_call` runs the same
  diagnosis against the session's best lap instead of pole — a race has no
  pole, and the quickest man out there is the honest benchmark. Shares the
  `q_sector` budget, because it is the same subject and a driver does not care
  which session he heard it in.
* **And it was nearly inaudible even in qualifying**: one sector call in a
  whole live session, because it was edge-triggered on the diagnosis CHANGING
  and the user's weak sector never changed. `SECTOR_REPEAT` (4 min) re-arms
  the same finding — a driver still losing sector two eight minutes later is
  exactly the driver who wants telling again. Trigger, re-arm AND budget,
  which is what LAW 18 actually asks for.

### 5b-vi. THE RESTART BUG — three phantom wins, and 20 laps led on lap 5

The user: *"I never ever won a race at Albert Park with Lando, only ever did a
quali session."* He was right, and the earlier fix (`_record_denies_win`) had
patched the symptom rather than the cause.

**`career.py` had recorded three wins at Albert Park from ONE-LAP races.**
THE LAW's `MIN_SHARE` test is RELATIVE — it compares the player against the
winner, so it catches "you quit while the others finished" and is completely
blind to "EVERYBODY stopped at once", which is exactly what a restart is.
Every driver's share of the winner's distance is 100%, the test passes, and
whoever is nominally P1 after one lap of fifteen has "won".

The evidence, from his own results folder:

| | |
|---|---|
| files passing the old law | 68 |
| ...that ran under a QUARTER of their scheduled distance | **55** |
| ...that ever reached the chequered flag | **2** |
| store before / after | 68 races, 5 wins -> **2 races, 1 win** |

**The new rule is the user's own**: *"I restart a lot because of crashing, so
a race result should only be captured when finished."* `FinishStatus` reads
"Finished Normally" for anyone who took the flag and is empty for every driver
in an abandoned session — so if nobody finished, nothing is recorded, however
many laps were run. It handles the honest retirement correctly: retire and
WAIT, the AI take the flag, and the DNF is kept as the real result it is.
`RUN_SHARE`/`RUN_MIN_LAPS` survive only as a fallback for a file with no
status data at all (not seen in any of the 293 files here).

**`career.VERSION` is 8**, which is what rebuilds an existing `_career.json`.

**THE SAME CAUSE PRODUCED "Hamilton has led this Grand Prix for 20 laps" on
lap 5 of a 15-lap race** — a restart the booth had not noticed, leaving the
previous attempt's tally in place and adding to it. Two fixes, deliberately
both:

* `RESTART_ET_DROP` — the session clock going BACKWARDS is now a restart
  signal in the booth, the same one `rf2_session._reset` already trusts. The
  old green -> pre-green test needs the booth to SEE a tick in the gap, and a
  crash-restart that comes straight back to a grid does not give it one.
  `_new_session` wipes everything including the engineer's state.
* `_count_led` now CLAMPS to the laps actually run. Nobody can have led more
  laps than the leader has completed, so the number cannot be wrong even if a
  restart is missed some other way. LAW 17: a number said out loud has to be
  one something measured.

### 5b-viii. ...AND THAT TOOK THE NEW CAREER MENU WITH IT

Immediately after the fix above, the user: *"where did all the other car
classes go?"* The New Career menu offered **two** classes out of eighty-two
installed car mods.

Self-inflicted, and the lesson is LAW 3 with a sharper edge: **context is
free, RECORDING is confirmed — so they must not share a gate.** The class list
was built only from folded RESULTS, so tightening THE LAW to "somebody must
have finished" took the menu down with the store.

Owning a car and having won in it are different claims. Getting the first
wrong costs a line in a list; getting the second wrong costs the broadcast its
credibility. `_fold_context()` now learns the class, its share of the grid and
the driver roster from every file THE LAW **rejects**, and touches no total,
no win, no podium and no circuit record.

* **Qualifying sessions count as context**, which matters directly: the user's
  own report was that he had "only ever done a quali session" in a car. That
  is still a car he owns and a grid he can race.
* **`races` stays at zero** for a class learned this way, so the menu's own
  race count remains honest.
* **A SOLO RUN IS NOT A CHAMPIONSHIP** (`CONTEXT_MIN_FIELD` = 3). One car
  alone covers 100% of its own field and sails past every share test there is
  — the first version offered "Mazda 787B" and "National" as seasons with a
  grid of nobody.
* A team-named grid is still folded into one championship by the same
  `era.team_field` test the result path uses, or a 2021 field learned from a
  restart would offer ten teams and no season.

Result on this machine: 8 championships offered (Formula One 2021 and 2025,
GT500, GT-R GT500 2013, F1 1988, LMP1, IndyCar 2014, StockCar 2018 X Series),
against 2 recorded races. **`career.VERSION` is 9.**

### 5b-vii. THE END OF QUALIFYING — a session that just stopped

Asked for directly: *"there is a chequered flag when the session is over, and
the commentators and race engineer never get triggered their outro lines"*.
Nothing fired at all: the last thing aired was whatever colour was in the
queue, then silence through the flag and the final order.

`POST_QUALI` is the race wrap's counterpart, drained by the same
`_post_stage` machinery:

| beat | who | |
|---|---|---|
| `pole` | Miles | who took it and by how much |
| `frontrow` | Miles | the top three as a GRID, not a timesheet |
| `qverdict` | **Chuck** | what a driver has to do with the slot he has |
| `yours` | Miles | where the PLAYER ended up — no other beat covers it |
| `qsignoff` | Miles | see you for the race |

* **It is handled BEFORE the race wrap** in `_bookends`, because `s.finished`
  is true for any session type and the win call would otherwise fire on a
  qualifying session that has no winner, only a pole.
* **THE ORDER COMES FROM `_sheet`, NOT `s.order`.** In a timed session rF2's
  position field is as often the running order on the road as the
  classification, so reading `s.order[0]` as the pole man announces pole for
  whoever happened to be in front when the flag fell. `qualitest.py` §13 puts
  the quickest man LAST on the road and checks he still gets pole.
* **`yours` is skipped when the player took pole** (the first beat already
  said it) and when he set no time at all.
* **The engineer signs off too** — `eng_quali_done_good/ok/poor`, graded
  against the SIZE OF THE FIELD rather than a fixed position, because P8 is a
  good afternoon in twenty cars and a poor one in ten.
* **The result is banked AT THE FLAG**, before anything is said about it:
  "quali results must be remembered when a session finishes", and the
  engineer reads it back a session later when shared memory no longer holds
  it.

### `quali_deleted` — built, and the refusal that was reversed

The handover listed this under **Deliberately NOT built**: `last_lap_valid` is
declared in `rf2_session.Car` and never assigned, so there was no honest
source, and *"a phantom deletion the timing screen contradicts costs more than
the line is worth"*. That reasoning was right and **its premise has expired**:
the extended buffer's `mStatusMessage` is the sim's own on-screen warning,
which is where a deletion is announced to the driver, and it is now read.

So the line exists and stays gated on the game saying it — no message, no
call, never an inference. `offtracktest.py` §15 holds all of it, including
that a race gets no deletion call and that three deletions in a row are one
piece of news (`QUALI_DELETED_GAP`).

**THE SIM PUBLISHED NO STATUS MESSAGE AT ALL IN THE FIRST LIVE RUN.** The
40-minute session log (plugin v3.7.15.1) contains **zero** `STATUSMSG` lines
across a full qualifying session and three race starts. So either this plugin
build never writes `mStatusMessage`, or it only writes it for events the user
did not trigger. Until a run produces one, BOTH features that depend on it —
the deleted-lap call and the track-limits backstop — have no data at all, and
the surface detector is carrying excursions on its own (which it did, well:
every off in that log was caught by `mSurfaceType`).

**SO THE SOURCE WAS CHANGED TO A NUMBER.** `mCountLapFlag` is per-vehicle in
scoring, on a struct already read every tick: **0** = do not count the lap,
**1** = count the lap but not its time, **2** = count both. Below 2 means the
time is not going on the sheet, which is exactly what a driver means by "they
took my lap away" — and it needs no pattern-matching on English. It is now the
PRIMARY source, edge-triggered on the transition and only from a lap that WAS
counting, because the flag also sits low in the pits and on an out-lap.

**It also gives `last_lap_valid` an honest source at last.** That slot has
been declared in `rf2_session.Car` and never assigned since the module was
written, and its absence is the whole reason this call was refused for so
long. Both are now filled from the flag.

The status message is kept as a SECONDARY path — it costs nothing and is the
only source left if a future plugin build stops publishing the flag.

**THE MESSAGE WORDING REMAINS A GUESS** (it has never been observed): `DELETED_WORDS` in
`overlay_booth.py` matches "invalid" / "deleted" / "cancelled" and so on
alongside the word "lap", and nothing documents what rF2 actually writes.
**`testrun.py` now logs every distinct status message it sees as `STATUSMSG`**
— one qualifying session with a few laps thrown away answers it exactly. If
the calls still do not fire, read those lines first and add the real phrase;
that is the whole fix. The same applies to `_track_limits_ground_truth`'s
keyword gate.

### 5c. Commentary phase structure — COMPLETE 2026-08-17 (second pass)

The two items left open below are now BUILT. Read the original section for the
reasoning; this is what changed.

**`settling` is a real phase**, between `opening` and `mid`, with
`FOCUS_LIMIT["settling"] = 12`. On a 40-lap race the shape verified end to end
is: laps 1-2 `opening`, laps 3-4 `settling`, then `mid`.

* It is checked AFTER `late` and `closing` in `_race_phase()`, and **only when
  a mid-race survives it** (`(L - late_laps) > settle_end`). Without that
  guard a five-lap dash went opening -> settling -> late with **no `mid` at
  all** — the booth would never once open up. `flowtest.py` §20 holds both.
* `SETTLE_LAPS = 2`, added to `open_laps`, which is already length-scaled — so
  the broadening lands at lap 3 or 4 with no second length table to keep in
  step with the first.
* **Settling is a DEPTH change, not a licence for colour.** `_filler()` offers
  the driver/team briefing and `car_character` and then returns: no trivia, no
  jokes, no `story_ask`/`driver_ask`, no `interview`. What IS opened up is the
  racing — `lap_report` and the `midpack` battle block now accept `settling`
  alongside `mid`, which is the "other battles around the field" that was
  asked for. Overtakes staying top priority needed no change; `PRIORITY`
  already did it.
* No crosstalk topic declares `settling` in its `when`, so conversations
  simply do not start there. That is intended, and it is why `interview` is
  still gated to `mid`/`late`.

**The lead fight in the run-in now overrides everything.** `LATE_FRONT_BONUS`
= 60, applied by `_front_bonus()` in BOTH ranking paths (the real-event sort
and `_rank_filler`'s `score`). The check the handover asked for was done and
the existing weighting was NOT enough: a battle for the lead scored
`PRIORITY 40 + PLACE_WEIGHT 30 = 70` against a P4 overtake's `60 + 16 = 76`,
so the booth could describe a midfield pass while the race was being decided.

Three deliberate limits, all tested in `flowtest.py` §21:

* Only in `late` and `closing`. Mid-race the wide view is the entire point.
* Only places 1 and 2.
* Only while the leader is actually being hunted — `_front_fight_live()` asks
  whether P2 is inside `STRIKE_GAP`, and is settled ONCE per tick into
  `self._front_fight` so a real event and a filler line cannot disagree about
  it. It is a live gap test rather than "was a battle event detected", because
  the override has to hold for the whole run to the flag, not just on the tick
  a detector fired.

**Still not heard in a live session** — verified by `_transcript_demo`-style
runs through real phase transitions, not by ear. See OPEN QUESTIONS.

<details><summary>Original section, for the reasoning behind it</summary>

### 5c (original). Commentary has no PHASE STRUCTURE beyond position depth

The user's ask, precisely: **lap 1** — focus almost entirely on the fight for
the lead into turn one and the next few corners. **Around lap 3** — start
broadening to other battles around the field, but overtakes stay top
priority. **Normal mid-race** — as it is now. **Approaching the end** —
narrow back to the front: any podium battles, or if P1 has run away but
there's a fight for P2. **If there's a fight for P1 in the closing laps**,
that overrides everything else regardless of what else is happening.

**What already existed, before today**: `_race_phase()` (search
`overlay_booth.py`) already computes `opening` / `mid` / `late` / `closing`,
scaled by race length via `_length_class()`. `FOCUS_LIMIT` already narrows
which POSITIONS the booth will look at per phase (opening=5, mid=99,
late=8, closing=5). Real events (overtakes, battles) already outrank filler
by `PRIORITY`, and `PLACE_WEIGHT` already biases toward the front. So the
skeleton of a phase system was there — what was missing is that FILLER
(colour: driver facts, car facts, circuit trivia, jokes, `story_ask`,
`driver_ask`) had NO phase awareness at all, so the moment there was one
quiet tick in lap one, a driver-history fact was exactly as likely to fill
it as anything about the race. That is the "very random right after lights
out" the user reported.

**Fixed today, in `BoothMixin._filler()`** (`overlay_booth.py`): the whole
colour tail (multiclass ambient info excepted) is now withheld during
`self._phase == "opening"`, and the driver/story/levity/car/circuit tail is
withheld during `"closing"` too — `_flow_filler()`'s phase-aware bits
(`podium_watch`, `insight_laps_left`, etc.) still run in both, because those
ARE the race. Verified directly:

```
opening: ['standings', 'podium_watch', 'insight_field_spread', 'summary',
          'stat_covered', 'broadcast']
closing: ['standings', 'insight_laps_left', 'podium_watch',
          'insight_field_spread', 'summary', 'stat_covered', 'broadcast']
mid:     (colour categories present, as before)
```

**IMPORTANT BUG CAUGHT WHILE BUILDING THIS, watch for the same shape again**:
the first version put the `if self._phase == "closing": return out` guard
AFTER `_driver_facts()` / `story_ask` / `driver_ask` / `_levity()` had
already been appended — so closing still got all of it. The fix was moving
the guard immediately after `_class_filler()`, BEFORE any of the colour
appends. Always verify a phase gate by calling `_filler()` directly with
`b._phase` set by hand and printing the category list, the way the snippet
above does — trusting the diff to be in the right place is exactly what
produced the bug.

**What is NOT yet built, and is the real remaining work**:

* **The "settling in around lap 3" broadening** the user described does not
  exist as its own concept. Today's fix only distinguishes `opening` (fully
  narrow) from everything else (`mid` onward, unrestricted). The user wants
  a THIRD state between them: laps 1-2 (or however `_race_phase` currently
  scales "opening") stay nearly silent except the lead fight; then a
  "settling" window — roughly lap 3 onward — should widen `FOCUS_LIMIT` from
  its opening value toward the mid-race one gradually, or in one step, while
  STILL keeping overtakes/battles as the dominant category (this part
  already works via `PRIORITY`). This likely wants a new phase name
  (`"settling"`?) inserted between `opening` and `mid` in `_race_phase()`,
  with its own `FOCUS_LIMIT` entry narrower than `mid`'s 99 — NOT a filler
  change, a POSITION-DEPTH change.
* **Late-phase priority is not yet re-ordered for "podium battles first,
  P1 battle overrides everything."** `FOCUS_LIMIT["late"] = 8` already
  narrows depth, and `PLACE_WEIGHT` already biases toward the front, but
  there is no explicit rule that a fight for the LEAD in the last few laps
  should outrank a call about, say, P7. Check whether `PLACE_WEIGHT`'s
  existing weighting already produces this in practice (it may — a
  `leadchange`/`battle` event for P1 already carries `PRIORITY["leadchange"]
  = 85`, higher than everything except `win`) before building anything new.
  If real testing shows it is not enough, the lever is `_rank_filler`'s
  `score()` function and/or a dedicated late-phase boost keyed off whether
  `s.order[0].gap_ahead` (the gap BEHIND the leader, i.e. is he being
  chased) is inside `STRIKE_GAP`.
* **None of this has been heard.** Everything above is verified by direct
  function calls with hand-set `self._phase`, not by driving a real or
  synthetic race through the phase transitions end to end. `_transcript_demo.py`
  or a real `testrun.py` session is the way to actually judge whether lap 1
  now sounds tightly focused and whether the closing laps read as a proper
  run to the flag.

</details>

### 6. Smaller, known

* **Sprint races / half points** — not modelled in `season.py`.
* **Backfilling a season** from result XMLs.
* ~~Multiclass~~ — DONE 2026-08-17. See MULTICLASS below.
* **Endurance**: no stints, driver changes or night running.
* **Packaging**: no `.spec` file. RacerTV's documents two traps —
  `contents_directory='.'` and `hiddenimports=['PIL._tkinter_finder']`.
  Collect `lines_data/`, `stings/`, `*.ttf`, `icon_*.png`, `Factor.png`,
  `radio_click.wav`.
* ~~LAW 9 violation~~ — FIXED 2026-08-17. `_gap`/`_lap` are now
  `overlay_common.spoken_gap` / `spoken_lap`, and `paneltest.py` walks all
  three mixins for ANY duplicate name so the next one is caught the day it
  is written. `spoken_lap` returns "" for no time where `fmt_lap` returns
  "--:--.---" — a caption reads the dashes fine and a synthesiser does not.

### Deliberately NOT built

* ~~**`quali_deleted`**~~ — BUILT 2026-08-17 once an honest source appeared.
  The refusal was correct while it stood: `last_lap_valid` is declared in
  `rf2_session.Car` and never assigned, and a phantom deletion the timing
  screen contradicts costs more than the line is worth. The extended buffer's
  `mStatusMessage` is the sim announcing the deletion itself, so the line is
  now gated on that and never inferred. See §5b-ii.
* **`career_won_here` for a driver's real history** — beyond the user's own
  results, there is no data.

---

## DRIVERS — the booth knows who these people are

`drivers.py` + `lines_data/drivers.json` + `lines_data/booth_driver.json`.
Built 2026-08-17 against the user's framing: *"Lewis the 7 time world
champion chasing his 8th championship this season, will he be able to do
it?"*

**Scope is 1988, 2021 and 2025. 71 drivers.** Adding a season is adding a
block to `drivers.json` and touching no code — but do not add a season you
are not prepared to check by hand.

**EVERY NUMBER IS AS OF THE FIRST RACE OF THAT SEASON.** Prost has 28 wins in
1988 and 51 at the end of his career; only the 28 is true on the grid at
Silverstone. That tense is the whole design:

* A career total is a false claim in a historic season.
* A live within-season standing cannot be known — the season being raced is
  the user's own invented one, and `season.py` is the only thing that knows
  anything about it. Nothing in `booth_driver.json` may sound like it knows
  how this year is going; `drivertest.py` §7 greps for it.

**Three gates, and each one is a way this could have gone wrong:**

1. **Era.** `drivers.season_of()` requires discipline `f1`/`formula` AND a
   year we hold. A GT3 car in 2021 is not the 2021 Formula One season, and
   Mansell in the 1992 mod resolves to nothing even though we hold a 1988
   record for him.
2. **Name.** Folding handles accents, spacing and Jr./Sr. — the mods ship
   "Andrea DeCesaris", "Rene Arnoux", "Nico Hulkenberg", "Carlos Sainz Jr.".
   `alias` covers what folding cannot ("Bortoletto" for Bortoleto). A bare
   surname resolves only while it is unique in that season; two Schumachers
   would poison the surname for BOTH rather than resolving it to one.
3. **Category.** `drivers.CATEGORIES` is a predicate per pool, and
   `slots_for()` returns None rather than a dict with a blank in it. That is
   LAW 5 at the source: without it `safe_format` would air "chasing , and he".

**`contender` is an editorial flag and it earns its place.** Without it the
booth asks whether Alonso can take a third world championship out of a 2025
Aston Martin. Only Senna/Prost (1988), Hamilton/Verstappen (2021) and
Verstappen/Norris/Piastri (2025) carry it.

**`note` is one hand-written clause per driver**, used verbatim, no terminal
stop. Anything true of exactly one man lives there — "in red for the first
time in his career", "with more Grand Prix starts than any driver in history
without a podium" — because a schema general enough to express those is a
schema nobody could keep correct.

### The record is LIVE — history plus your career

The half that makes it more than a trivia file. `drivers.Standing` adds what
has happened in the user's career to the historical baseline:

* Race as Hamilton in 2021, win three, and the third is **his ninety-eighth**,
  not his third.
* Take the championship as him and it is **his eighth**.
* Take it as Mansell in 1988 and it is **his first** — and his sixteenth win.
* **It applies to the AI identically.** An AI Senna winning your 1988 title is
  a first world championship for Ayrton Senna, and an AI Norris winning a race
  in 2021 is the first Grand Prix win of his career.

Five pools for it: `driver_title_first`, `driver_title_more`,
`driver_first_win`, `driver_win_tally`, `driver_season_wins`.

**CONTINUITY IS FOR CAREER RACES ONLY.** A career stays loaded in the
settings for as long as it exists, so a one-off race run for fun still has
one attached — and crediting that race to a championship it was never part of
is wrong twice over. `_active_career()` is the gate: it returns the career
only when `_season_round` is set, which `_season_arm` does only when the
circuit and class actually match a round.

Outside a career the booth reads pure history and nothing else, which is the
right broadcast for a one-off anyway: who these drivers were, not how a
season they are not in is going. Same grid, same booth, two behaviours:

| | one-off | career round 4 |
|---|---|---|
| Mansell | "runner-up in each of the last two championships" | "three wins to his name this season" |
| his win count | thirteen | sixteen |
| the wrap | no tally, no standings | tally + championship |

`drivertest.py` §19 holds both halves against the same booth object.

**CONTINUITY WITHIN a career — and this is the part that is easy to break.** The
INTRODUCTIONS are judged on the live record too, not just the wrap lines.
`drivers.CATEGORIES` takes a `Standing`, never a `Driver`, and
`_driver_facts()` passes `self.season`. Without that, a driver who took his
maiden win in round two is still "still looking for that first win" in round
three — the booth visibly not watching its own championship. So:

* `Standing.winless` counts YOUR races. It goes false the instant he wins.
* `driver_winner` is gated on the HISTORICAL wins, so a man whose only
  victory is one of yours gets `driver_season_wins` ("one win this season")
  instead of a line implying a career behind it.
* A first-time champion stops being offered `driver_winner` and starts being
  offered `driver_champion`, phrased from the new total.

### The career driver picker

**Fixed 2026-08-17: it offered two names for a 2021 or 2025 season.**
`career._fold_field` built the roster for a team-named championship out of
`classified`, which is scoped to the PLAYER'S CLASS — and for these mods a
class is one team, so "Formula One 2021" offered both McLarens and nobody
else. `parse_result` now also returns `grid_all` (every driver in the race,
by overall position) and `_fold_field` uses it. `classified` stays
class-scoped, which is right for a genuine multi-class race.

**`career.VERSION` is now 7**, which is what rebuilds existing `_career.json`
files — `load()` discards a file whose version does not match. Bump it again
if you ever change what `_fold` records.

**The picker is also SEEDED from `drivers.json`** via `drivers.picker_names`,
so a fresh install offers the whole 1988 / 2021 / 2025 grid before a single
race has been run. History is merged in, not replaced: it is the only source
for the other eighty mods on this machine.

**Identity goes through `lookup`, not through folding.** The 2025 mod ships
"Yuski Tsunoda" (a typo) and "Kimi Antonelli" (a short form); neither folds
to the canonical name, both resolve through the surname and alias index, and
a fold-only merge offered Tsunoda twice in the same menu. The canonical
spelling wins, because whichever name is picked is what the engineer says out
loud for the whole career.

**A NEW CAREER IS A CLEAN SLATE, and that is deliberate.** `drivers.json` is
read-only history and nothing ever writes to it; what a career adds lives in
that career's own file. Start a second 1988 season and Mansell is back on
thirteen wins with no title, while the first career's championship is
untouched. Two careers in the same season are completely independent.

**Do not "improve" this into a global achievement store.** A driver's record
is a function of (history, THIS career), and the moment it becomes a function
of everything the user has ever done, restarting a season stops meaning
anything and the 1988 grid slowly fills up with champions who never were.
`drivertest.py` §21 runs the real create/save/delete path to hold it.

**`note_void_on` in `drivers.json`** declares what falsifies a hand-written
clause: `win`, `podium` or `start`. Hülkenberg's record for starts without a
podium ends at his first podium; Arnoux's "last win came five seasons ago"
ends at his next win. A note without it is a fact your season cannot reach.
`drivertest.py` §19 greps for notes that look falsifiable and are untagged —
**when you add a note, ask what would make it false.**

**Names in `classified` are the MOD's spelling** ("Nico Hulkenberg"), the
record's is the canonical one ("Nico Hülkenberg"). Every comparison against a
career result folds both sides (`drivers._is`). Comparing them directly loses
every result belonging to a driver with an accent, silently — it did, and
§18 now tests for it.

**The maths is never done in `drivers.py`.** `season.Career` owns it, exactly,
including the refusal to call a title settled when the remaining points are
unknown (LAW 4) — an open season with no declared length can never announce a
championship, and that is correct. `drivers.standing()` only reads it.

**`season.standings()` and `title_state()` now take `upto=`** — the table as it
stood after round N. That is what `just_won_title()` needs: a championship
settled at round three is enormous news at round three and old news at round
four, and a booth that announces it three times has stopped being believed.
Do not remove the parameter.

**The win tally is gated on the win being BANKED**, not on the win happening.
`season_wins` counts recorded rounds, so outside career mode and after a race
that failed THE LAW it is silent rather than quoting a total that excludes the
race the viewer just watched.

**Where it airs:**

* A new `who` beat in `PRE_RACE` and `PRE_QUALI`, straight after `grid`.
  Introduces the man on pole. `force=True`, because this is the moment the
  fact is worth most.
* A new `tally` beat in `POST_RACE`, after `podium` — where this win sits in
  his career.
* The `championship` beat becomes a TITLE call when one has just been won:
  `_championship_call` returns `driver_title_first` / `driver_title_more`
  instead of the generic `title_decided`.
* As filler in the race and in qualifying, ranked on staleness like the rest
  of the colour. Roughly 5 lines in 85 over a 40-lap race.

**Three restraints, all of which will look removable and are not:**

* `DRIVER_FAMILY_GAP` = 150s across the WHOLE family (LAW 15). Every one of
  these is the same kind of sentence; `driver_reigning` and `driver_chasing`
  are both correct and back to back they are a man reading a record book.
* Once per driver per category per session, marked when the line AIRS and not
  when it is offered (LAW 11).
* `DRIVER_FOCUS` = 10. A fact about the man running nineteenth is true and
  worthless. The player is always in scope wherever he is running.

**The rule that governs any change here:** a false claim about Senna breaks
immersion harder than silence about Senna. If you cannot write a line that is
true for every driver its category can select, do not write the line.

---

## CARS AND TEAMS

Built 2026-08-17 from: *"These 2021 cars were beasts, Mercedes are extremely
quick on the straights ... Red Bull cars are very good at cornering."*

**TWO LAYERS, AND THE SPLIT IS THE WHOLE DESIGN.**

### `car_character` — what this KIND of car is like

`lines_data/booth_cars.json`. **A plain line pool, deliberately** — it needed
no new code and no new data format, because `lines.allowed()` already gates on
exactly what decides whether a sentence about a car is true: `disc`, `era`,
`year`, `needs`, `not`.

That shape is why it reaches **every car the user owns**, not just the three
Formula One seasons: a Group C race gets fuel-ration racing, a GT3 field gets
balance of performance and the pit window, a Next Gen Cup car gets its
independent rear suspension. **This is the layer that makes a one-off race
worth listening to**, and `drivertest.py` §22 asserts twelve different fields
each have 3+ things said about them.

### `team_strength` / `team_weakness` / `team_note` — what HIS car is like

In `drivers.json`, under each season's `teams`. Reached through the DRIVER,
because that is what the booth is looking at: a car on track with a name
attached. `drivers.Team` is bound to each `Driver` at load as `.club`.

Only exists for 1988 / 2021 / 2025 — these are the differences BETWEEN teams
in one season, which is knowledge, not inference.

**A clause must be a bare noun phrase.** It has to survive six frames —
"Mercedes have {s}", "The problem at X is {w}", "{w}, that is what X are up
against" — so no capital, no full stop, no dash continuation, and no pronoun
pointing at a clause in a different line. Lotus's weakness said "never made
proper use of *that engine*" and only parsed next to the strength line (LAW
14). `drivers.validate()` now enforces the shape and `drivertest.py` §23
renders all 570 combinations.

**CAPABILITY, NOT OUTCOME**, in both layers. The booth may say Mercedes have
the straight-line speed; it may not say who won the constructors'
championship. The user is driving this season and the timing screen would
contradict it — the same rule as `booth_archive.json`.

### Facts that were nearly wrong

Three car lines were tightened after a check, and one of them mattered:

* **"Fifteen hundred horsepower"** for the turbo era is a 1985–86 qualifying
  figure. **1988 capped boost at 2.5 bar and 150 litres** — roughly 650bhp —
  so the line was wrong in exactly the season the user tests on. Now gated
  `year: [1982, 1987]`, with a separate 1988 line about the boost limit.
* Ground-effect minimum weight is 798kg (2022-24) and 800kg (2025), so "the
  wrong side of eight hundred kilos" was out by two. Now "the best part of
  eight hundred kilos before it takes on any fuel".
* "The fastest sportscars ever built" for Group C is arguable against a
  modern Hypercar over a lap. The top-speed claim alone is not.

### Ranking

Team lines are in `DRIVER_CATS` — they share the driver-fact family gate,
because "Hamilton, a seven-time champion" followed by "Ferrari have a strong
race car" is two halves of one briefing. `car_character` is NOT in it: it
applies to races with no driver records at all, and gating it on the driver
family would silence it exactly where it is the only thing available.

`_driver_facts` offers **one fact about the man and one about his car** per
driver. Taking only the first eligible category meant the team layer never
surfaced for anybody — there is always a driver fact ranked above it.

---

## MULTICLASS

`Car.place_class` had been computed on every tick since the session module
was written and **read by nothing at all**. A GT3 car leading its class while
running ninth overall was called "ninth", which is not his race.

**A bug was hiding behind that.** `s.multiclass` was `len(s.classes) > 1`, so
a **team-named F1 grid counted as ten classes** and every driver got a class
position of first or second — his position within his own two-car team.
Harmless only because nothing read it. `era.team_field()` is now the gate,
the same test `career.py` uses to tell the two apart.

Four pools — `class_lead`, `class_pos`, `class_battle`, `class_traffic` —
offered only in a genuine mixed race:

> Piastri is fifth on the road, and first in the GT3 class.
> Traffic for Piastri. In this kind of racing, how you deal with that IS the race.

**`spoken_rank` is not `spoken_place`.** The latter returns "the lead" for 1,
which is right for the road ("Verstappen takes the lead") and wrong inside a
phrase about a class ("and the lead in the GT3 class"). Two jobs, two
functions.

---

## CIRCUITS — and the historic layouts

Rewritten 2026-08-17. **68 circuits, 334 facts**, up from 42 and 110.

### All 49 of the user's installed tracks now resolve

They did not: **27 of 49 resolved to nothing**, and the booth read the folder
name aloud — "TobanRP 2016", "ISI LostValley 2014". They split two ways:

* **Real circuits** the alias table did not know (Botniaring, Maastricht,
  Atlanta, NOLA, Palm Beach) got full entries.
* **Fictional rFactor 2 stock tracks** (Toban, Lost Valley, Joesville, Tiger
  Moth, Lester, the 3PA club circuits) got `identity_only` + `fictional`:
  a presentable NAME and nothing else. There is nothing true to say about a
  place that does not exist. **A name alone is still worth having** — "we're
  at Lost Valley" is a broadcast, "ISI LostValley 2014" is a file path.

`fictional` exists so the test can demand a country of every real
identity-only circuit without demanding one of a place that has none.

### A HISTORIC LAYOUT IS A DIFFERENT ROAD, NOT A SHORTER ONE

The important correctness fix. The user has **Spa 1966, Monza 1966, Monaco
1966, Silverstone 1991, Longford 1967 and Hockenheim 1978** installed, and
every one was being told facts about a layout that did not exist yet. The
modern Spa entry says the lap is *"over seven kilometres, the longest on the
calendar"* — and that aired over a 1966 circuit that was **fourteen
kilometres of public road**.

**A fact may now carry `year: [lo, hi]`**, exactly as a dialogue line does,
and **`corners_history` does the same for the corner list**. `Track.year` is
scraped from the rF2 folder name — a four-digit year, a two-digit range
("Le Mans 91-96" -> 1991), or `LAYOUT_YEARS` for the ones neither can reach.

**`LAYOUT_YEARS` is only ever filled in from something the user has
CONFIRMED**, never from a pattern that looks plausible. It holds one entry:
`T78_Hockenheimring` -> 1978, the forest circuit. Undated is the safe state —
it yields the undated facts only, which is fewer facts and none of them
wrong. Its key is `"t hockenheimring"`, because `_norm` strips any run of 2-4
digits and the 78 is gone by the time the table is consulted; keying it on
the folder name made the table do nothing at all.

The corner list was missed on the first pass and is just as bad: Silverstone's
default list holds Village, the Loop, Aintree and the Wellington Straight —
the **Arena section, built in 2010** — and `Track.corner()` was naming them
during a 1991 race. Historic corner lists exist for Silverstone pre-2010, Spa
1966 (Burnenville, Masta, Stavelot), Monza pre-chicanes (Curva Grande, the
Lesmos, Vialone), Monaco pre-1973 (the Gasworks hairpin) and the Hockenheim
forest layout (the Ostkurve, the Motodrom).

THE RULE: a fact about the **place** — its history, its geography, what it
was built on, who died there — stays undated and is true of every layout. A
fact about the **road** — how long it is, which corners it has, how fast it
is — carries a year range. A layout with no year in its name gets the undated
facts only: fewer facts, none of them wrong.

### It took three passes, and the leaks were not obvious

The first sweep caught lap length and the swimming pool. A keyword audit
afterwards found four more in Monza alone, none of which reads as
layout-specific until you look:

| leaked into 1966 Monza | why it is wrong |
|---|---|
| "the banking still stands, crumbling" | it was still **in use** in 1966 |
| "low downforce means the car is quick on the straights" | **wings arrive in 1968** |
| "Ascari is a fast left-right-left" | the Variante Ascari is a **chicane built in 1972** |
| "a Grand Prix every year since 1950 bar one" | the missed year was **1980** |

Monaco 1966 was being told BOTH "a mistake is a barrier, every single time"
AND "there were no barriers worth the name in this era" — a straight
self-contradiction. `tracktest.py` §6b now checks for that class of failure
separately, because two facts can each be fine and still not both be true.

**I also created 44 near-duplicate facts** by adding on top of the existing
ones without checking — the exact repetition this content was meant to cure,
and some of them CONFLICTED on numbers (the Nordschleife's corner count,
Bathurst's elevation). All removed, keeping the more defensible figure.

The duplicate test compares only facts whose year ranges **overlap**: Spa
holds two lines about the fourteen-kilometre circuit, one in the present
tense for 1966 and one as history for the modern layout, and no listener can
ever hear both.

Historic layouts have their own facts written for them — the old Spa through
Malmedy and Stavelot, Monza before the chicanes with the banking still in
use, Monaco before the swimming pool complex, the 1991 Silverstone redesign.
`tracktest.py` §6 asserts no modern fact reaches a historic circuit and §7
walks the user's actual install directory.

### THE LAYOUT YEAR IS FOR KNOWING, NEVER FOR SAYING (2026-08-17)

The user's rule, in his words: *"when they speak about era specific tracks,
like when I'm playing the 1988 career mode and I'm using the 1991 track, the
commentators mustn't explicitly state the year of track ... the year must just
be used to know whether it's a modern or classic track."*

He is right, and it is the same rule `booth_archive.json` already states for
the archive channel. The year on an rF2 folder is production metadata. It
decides which facts and which corner names are true; announcing it tells the
viewer he is driving a re-run of somebody else's season rather than his own.
Three leaks, all now closed and held by `tracktest.py` §8:

* **`_pretty()` kept the digits**, so any circuit the alias table did not
  know was announced as "Botniaring 2017". Now strips runs of digits — but
  ONLY digits, because "GP" and "National" genuinely distinguish two layouts
  a user may have installed side by side.
* **Two Silverstone facts said it outright** — "This is the 1991 layout..."
  and "Nigel Mansell won here in 1991..." — plus one each at Spa and
  Longford. All reworded to describe the road without dating it. The rule the
  test encodes: **a dated fact may never name a year inside its own span**,
  because that span IS the layout it is describing.
* The end-to-end check walks the user's install and asserts no layout can say
  its own year through any channel: name, facts, character, sectors, corners.

A season year is different and stays: `season_launch` saying "the opening
round of the 1988 Formula One season" is HIS championship, which is the one
thing here that is genuinely his to be told about.

### Albert Park and Zandvoort — both installed as HISTORIC roads (2026-08-17)

The user added Albert Park and Zandvoort, "and that also comes with the
historical versions". Both existing entries described the MODERN layout only,
and in both cases the layout he actually has is the older one — so every fact
was about a road he was not driving.

* **`Melbourne_BySephiAt` is the 2019 layout** (its own layout files are
  `layout2019GP` / `layout2019GT`, and he confirmed 2019). The folder carries
  no year at all, so it needed a `LAYOUT_YEARS` entry — keyed on
  `"melbourne by sephi"`, which is what `_norm` actually produces. The 2021
  reprofile fact is now gated 2021+; the 2019 road keeps its turn nine
  chicane, its narrow middle sector and its own corner list.
* **`Zandvoort_2017` is the pre-Dromo layout, and the banking is the whole
  point of the modern one.** Four banking facts, the banked-corner names
  (Arie Luyendyk, the Kumho corner) and the third-sector coaching note were
  all being told over a circuit that is flat. Now split: undated facts about
  the dunes and Tarzan, 2020+ facts about the banking, and pre-2020 facts
  about a last corner with nothing to help the car.

**`sectors_history` is new**, and it is `corners_history` for the engineer's
coaching clauses. Zandvoort is why: "power on early in the banked last corner"
is a note about a corner the 2017 driver cannot see. A sector clause describes
a piece of ROAD, so it dates exactly like a corner list does.

### Sector coaching

Every one of the 42 circuits with knowledge has `sectors` — three short
clauses, one per timing sector, for the engineer. See THE ENGINEER.

---

## A CAR HAS TWO NAMES, AND THE PLAYER'S DIFFER

`car.name` is what rF2 reported. `car.display_name` is what the overlay is
willing to say out loud. **For the AI they are the same. FOR THE PLAYER THEY
ARE NOT** — rF2 reports the profile name, usually the placeholder "Your
Name", and the career's chosen driver name lives in `display_name`.

Every knowledge lookup preferred `name`, so **a career raced AS Max
Verstappen produced no facts about Max Verstappen**: the booth held his
entire record and could not connect it to the car being driven. Which is the
whole feature.

`BoothMixin._driver_record()` tries both and is the ONLY way the booth should
resolve a car to a record. `drivertest.py` §29 holds it.

---

## TWO REGISTERS FOR THE SAME KNOWLEDGE

`booth_driver.json` STATES a record: "Verstappen has ten wins." Mean line
length **ten words**. The complaint was exact — *"one statement and then
theres no conversation, full stop"*.

`booth_history.json` is the same knowledge said the other way: Miles asks,
Chuck explains at length what the record MEANS. Mean **27 words**, capped at
Chuck's 32. `BoothMixin.HIST_ANSWER` maps each `drivers.CATEGORIES` gate to
its long answer.

**Both are kept.** A quick fact is right when the booth is busy; a
conversation is right when it is not. And every gate is the one the short
form already uses, so a long line can no more be said about the wrong driver
than a short one can.

**`_history_report` sorts by who has been asked about LEAST.** Taking the
first driver with an unused angle gave the leader all five of his in a row
before a second man was mentioned — the same repetition complaint in a new
costume. The sort resolves to the CANONICAL name, because `_hist_told` is
keyed by it and sorting on the mod's spelling silently does nothing.

**`{note}` has two grammatical shapes** — "the youngest race winner this
sport has ever had" is a noun phrase, "with more race wins than anyone in the
sport's history" is prepositional. Only the frame they were written for
(`{drv}, {note}.`) fits both. A template that embeds the note in a new
sentence produces "This is a driver the youngest race winner..." for half the
grid.

---

## DRIVER CARDS — reactive, and their own words

Reworked 2026-08-17. The complaint: they "don't really show up that often"
and should react to spins, damage, performance in quali and the race, and
carry famous quotes.

**FIVE EVENT TYPES HAD LINES AND NO TRIGGER.** `incident`, `frustrated`,
`pumped`, `pit` and `praise` — 40 lines between them, dead since the file was
written. Only `overtaken`, `caught`, `damage` and `blocked` were ever emitted.
**This is the third time this session a pool with no caller has turned up**
(`booth_joke`, `eng_quali_sector` in effect, and now these), so
`rivaltest.py` greps `overlay_rival.py` for every event name in `rival.json`
and fails on any that nothing can emit. `lines.py` cannot catch this — the
lines are valid, they are simply unreachable.

New triggers, all still requiring the player to be near enough to have seen
it: an excursion (`wheels_off` plus a speed drop), a stop, a race going badly
(`Arc.slid` or `offs`), a race going well (`Arc.recovered`), and grudging
respect when the player takes the session's best lap.

**`_rival_arc()` reads the SAME `story.Arc` the booth commentates from.** A
card saying a driver is furious about a race he is winning would be the
clearest possible sign that nothing is really watching.

### Signature lines

`quotes` in `drivers.json`, keyed by driver AND occasion (`win`, `pole`,
`podium`, `good`, `bad`, `incident`). Max gets "simply lovely" for a pole or
a win and never for a bad afternoon; Lando gets Smooth Operator for a good
run. 41 quotes across 22 drivers.

**Rare on purpose.** `QUOTE_CHANCE` = 0.55, once per driver per session, and
only on an occasion that fits. The whole value of a catchphrase is that it is
rare — fired at random it turns a character into a parrot.

**The 1988 set is deliberately thin and deliberately not presented as
verbatim.** Team radio barely existed; the surviving quotes are from
interviews. Those entries are what a driver would plausibly say on the radio,
not a claim about something he said.

---

## THE ENGINEER'S REGISTER — the half I had not fixed

Asked directly whether he had been made to sound more natural, the answer was
**no**: the earlier pass fixed WHY he repeated (`BRAKE_HOT_CLEAR`,
`TOPIC_MAX`) and never touched HOW he speaks.

Measured: **381 lines, mean 8.3 words, 24% using the driver's name, 10%
containing any warm word.** That is a dashboard being read aloud.

**Real pit radio is not wordier — it is FRAMED.** So rather than rewriting
381 lines, `_frame()` wraps them: an opener ("Okay Lewis,", "Right,",
"Lewis —") on roughly 45% of calls, never twice running.

* **Never on an urgent call.** "Okay Lando, you have just been hit" is a man
  reading from a card.
* **Nothing acknowledges the driver.** "Understood" and "copy that" were the
  obvious openers and both are wrong here: rival and driver radio were
  removed, the player never transmits, and an engineer replying to silence
  is worse than a flat one.
* **Lowercasing the original first word needs the LETTERS extracted.**
  `"That's".isalpha()` is False because of the apostrophe, which silently
  skipped it and produced "Right, That's your quickest so far." Acronyms
  (`DRS enabled`) and lines opening on a slot are left alone entirely.

---

## THE RACE STORY — `story.py`

Built 2026-08-17. The complaint was exact: in a 52-minute live race the booth
held **eight conversations and not one was about a driver**, and the wrap was
four lines that said nothing about how anybody had driven.

`story.Arc` is one driver's whole afternoon in one object — grid, now, best,
worst, offs, laps led, and how qualifying went. **A module rather than more
booth code because two consumers need the identical read**: the mid-race
two-hander and the wrap. Written twice they drift, and the wrap ends up
disagreeing with what the booth said twenty minutes earlier.

**`Arc.headline()` returns None when a driver's race has no shape**, which is
most drivers most of the time. A generic "he has had a solid afternoon" about
a man who finished where he started is the padding this exists to avoid.

**`_interest()` is deliberately not position.** A man in fourteenth who has
climbed nine places is a better story than the man who has been third all
afternoon — and the second is already covered by every other category.

### The lines are longer, and that is the point

> *"they just give one statement and then theres no conversation, its like
> 'Max is a 9 time race winner' full stop"*

A story line is **two clauses: what happened, then what it means or costs**.
Chuck's answers run to his full 32-word cap. Mean length across the pools is
23 words against roughly 12 elsewhere in the product.

**ERA-NEUTRAL BY CONSTRUCTION.** Nothing in `booth_story.json` names a piece
of equipment, a regulation or a decade, so every line is legal in 1966 and in
2025 and Brett delivers all of it. `storytest.py` §6 asserts no story line is
gated away from a 1988 field. A race story is the one thing about this sport
that has never changed.

### Qualifying is remembered

`_quali_story` is keyed by driver NAME — car ids do not survive a session
change — and is **cleared only when a new qualifying session starts**, never
on the way into the race. That is the whole point: the user took pole late in
a session he was proud of and the booth never referred to it again.
`story.quali_note()` gates `notable` on pole, a late benchmark, or a big
climb; an ordinary session is not brought up on lap forty.

### The wrap

`POST_RACE` is now seven beats: podium, tally, **topraces**, **impressed**,
championship, verdict, signoff. Four lines became eight.

* **`topraces`** describes how the podium got there, using the same arcs.
  It picks the man with the most to say rather than the winner — the winner
  already has the win call, the podium read and the verdict.
* **`impressed`** is Chuck's own drive of the day and is **never the winner**.
  The booth has a dozen ways to praise him; what a viewer cannot get anywhere
  else is which OTHER drive was worth watching.
* **The championship implication carries real numbers.** `champ_extends` /
  `champ_closes` quote the gap and the rounds left, and `_big_lead()` scales
  "a cushion" against what is still available using the career's own points
  table. An open season that cannot count its rounds offers none of it —
  LAW 4 doing its job, not a missing feature.

### Two bugs this surfaced

* `{left}` already contains its noun, so "{left} rounds" aired as
  "7 rounds rounds" (LAW 13, again).
* `_career_results` compared names with its own folded-key set instead of
  `_is`, so a classification holding only a SURNAME counted no wins at all —
  silently. One comparison, used everywhere, or `standing` and
  `just_won_title` end up disagreeing about who somebody is.

---

## THE ENGINEER — what was wrong with him

Reworked 2026-08-17 after the user said he "sounds very monotone and a bit
robotic, also very repetitive". **It was not the voice.** Of 45 lines in a
live race, 15 were about brake temperature, in three sentences repeated three
times each.

**`BRAKE_HOT_C` had a trigger and no clear threshold** (LAW 18). Brake temps
cross 700C on every lap of every circuit — hot into the corner, cool on the
straight — so the warning re-armed lap after lap. Now `BRAKE_HOT_CLEAR` = 560,
its own 150s cooldown, and a **`TOPIC_MAX` per-session budget**. Simulated
over 25 laps of temps crossing the threshold every lap: **15 mentions -> 3**.

`TOPIC_MAX` caps only NAGGING topics — brakes, temps, limits, tyres, pace,
encouragement, recovery. Anything the driver can act on right now (fuel, the
car behind, a pit call, a flag) is uncapped, because that is information
rather than commentary on his driving. Reset per session by
`radio_new_session()`, which the booth calls from `_new_session`.

### The sector call never fired. Not once.

`_quali_weak_sector` required ONE sector to carry 55% of the deficit before
it would say anything. A driver two tenths down everywhere — the normal case
— got total silence, through a whole qualifying session.

It now always names the worst sector and tells the caller whether it
**dominates**, which selects between two families:

| | |
|---|---|
| `eng_quali_sector[_coach]` | "All of it is sector two. That is Stowe, braking into a corner that keeps turning." |
| `eng_quali_sector_spread[_coach]` | "Down a little everywhere, most in sector three. That is the last chicane, kerb without the wall." |

**Both are true, and only one is true at a time.** The old rule survives: he
must never claim the lap was lost in one place when it was not.

### Track coaching

`sectors` in `tracks.json` — three clauses per circuit, one per timing
sector, on all 25 circuits with full knowledge. `Track.sector(n)`.

**Written per circuit, never derived from the corner list.** Sector
boundaries are not evenly spaced by corner count, and naming a corner in the
wrong third of the lap is exactly the small wrongness that stops the engineer
being believed. A circuit without them gets `eng_quali_sector` without the
`_coach` suffix: he names the sector and stops.

**Dean's cap is 18 words and the clauses obey it.** The first draft wrote
30-word clauses — that is Chuck's register, not his. A pit-wall call is short
or it gets talked over, and the long-form circuit detail already lives in
`character` and `facts` for the booth to use.

### A note on test flakiness

`_bag.json` persists across runs, so which line a pool draws VARIES BETWEEN
TEST RUNS. A qualitest check that grepped the rendered prose for keywords
passed and failed at random. **Test which POOL a line came from, not what
words are in it** — structural, and it does not drift as prose is edited.

---

## LEVITY — jokes, banter and digs

Built 2026-08-17 from: *"wheres the jokes and banter and little digs? its nice
to have some comedic moments on track"*.

`lines_data/booth_humour.json`, 53 lines across five pools, plus
`_levity_ok()` in the booth. **`tests/humourtest.py` is mostly a test of
SILENCE**, and that is the right shape for it.

**THE COST IS ASYMMETRIC, AND IT DICTATES THE WHOLE DESIGN.** A joke that
lands adds a little. A joke over a driver sitting in a wrecked car destroys
the illusion in one line and nothing said afterwards repairs it — the viewer
now knows nobody is really watching. So levity is **gated, not cooled down**:

* `_levity_ok()` is a **hard veto checked before a line is even offered**, not
  a ranking. A joke that merely LOSES the tick to an incident is still a joke
  that was offered while somebody was in the wall, and the next quiet tick
  would air it. `humourtest.py` §11 asserts the veto is upstream.
* Refuses: within 100s of any incident or nameless alert, under any yellow,
  in the `closing` phase, in the `late` phase of a title decider, before the
  race has settled, and while the player is off, damaged or in the pits.
* On top of that, `HUMOUR_CATS` share a 210s family gate (LAW 15) — five
  correct categories that are all "the booth being light".

**WHO MAY BE THE JOKE.** This is the editorial rule and it is what makes the
feature safe:

| | allowed |
|---|---|
| the two of them | always — nobody in it is trying to drive a car |
| the situation | always — traffic, the pit wall, the sport in general |
| a driver's driving | only when GROUNDED in something observed |
| the player | yes, deliberately — but not while he is in trouble |

**A dig must be grounded in something the viewer also saw.** That is the
difference between a joke and a sneer. `dig_stuck` needs a stalemate lasting
twice `LONG_FIGHT`; `dig_wide` needs `DIG_WIDE_OFFS` = **three** separate
excursions, because two is unlucky and three is a pattern the viewer has
noticed as well. A clean race produces no digs at anybody, and that is tested.

**The player IS fair game for being slow.** Being off the pace is racing, not
a misfortune, and a booth that never ribs the man driving is a press officer.
The gate covers the cases where he is actually having a bad afternoon.

**Never**: nationality, appearance, age as an insult, intelligence, or
anything reading as contempt rather than affection. These are real people,
several of them dead, and the booth likes all of them. §10 greps for it.

**`booth_joke` was already there — five lines, and NOTHING EVER OFFERED IT.**
Dead since it was written. Worth remembering when adding a pool: a category
with no caller is invisible, and `lines.py` reports it as healthy because the
lines are valid. It also has to live in exactly one file — the loader EXTENDS
a pool across files, so it was about to be doubled.

`booth_dig` (Miles ribbing Chuck) is PLAY-only for the obvious reason, and
Brett inherits it, so a historic race is not humourless.

---

## THE STATION — FACTORtv, FACTORtv Classic, and RacerTV

Built 2026-08-17 from: *"lines about FACTORtv, like them saying 'FACTORtv
airing the 2021 f1 season and you can also catch Brett on FACTORtv Classic'
... and easter eggs that nod to RacerTV, like them saying RacerTV is their
sister station"*.

32 lines across six pools, tested in `tests/stationtest.py`.

**THE TWO CHANNELS ARE THE TWO SEATS, AND THAT IS WHY THIS WORKS.**
`cast.set_era` already puts Brett in the chair before 2000 and Miles after —
so FACTORtv Classic is not an invention, it is a NAME for something the
product already does. The cross-promotion describes a real product:

| channel | who | pools |
|---|---|---|
| **FACTORtv** | Miles | `broadcast`, `broadcast_promo`, `broadcast_racertv` |
| **FACTORtv Classic** | Brett | `broadcast_archive`, `broadcast_promo_archive`, `broadcast_racertv_archive` |

**Nobody plugs the channel he is sitting on.** Miles points viewers at
Classic, where Brett is; Brett points them back at the modern season, which is
Miles's. Chuck works both, which is a joke available to each of them. All six
pools are PLAY-only and Brett inherits the set at import, so there is no
parallel list to drift.

**The ident may name the season; the archive may not.** "Every race of the
2025 Formula One season, live here on FACTORtv" is the line the user asked
for, and it is gated `year: [2000, 2099]` for TWO reasons that both bite:
`booth_archive.json` rule 3 forbids an archive broadcast stating a year, and
`_series_name` falls back to the word "field" when era.py cannot date the car
— an ungated line would air "airing the field season", which is LAW 5 with a
slot that is technically non-empty.

**The RacerTV nod is an easter egg and is built like one.** 1500s cooldown,
the lowest priority of anything in the product, and never explained. Both men
came up through it, so both may nod to it. It never names the game RacerTV was
built for — that is breaking the fourth wall rather than nodding through it,
and `stationtest.py` §7 greps for it.

**All six share `STATION_FAMILY_GAP` = 300s (LAW 15)** — three correct
categories that all mean "the booth is talking about itself" are a promo reel
back to back. The gate is checked ONCE, upstream, where the group is offered.
Measured: about two station lines per fifteen minutes of racing. **If the user
wants more of them, `STATION_FAMILY_GAP` is the knob** — the lines exist and
are gated, not missing.

**Two lines were LAW 14 orphans on the first draft** ("taught me that line",
"would have called that one") — both written as replies to a line that never
happened, because the bag can draw any line first. `stationtest.py` §4 greps
for deictic phrases.

---

## CAREER LADDERS — `ladder.py` (started 2026-08-17)

The user's idea: a career that CLIMBS. Karting to Formula One, and five other
paths beside it. `ladder.py` + `lines_data/ladders.json` + `laddertest.py` are
built and green; the rest is designed and not yet written.

**Six paths, 25 rungs, every car already installed on his machine.** Nothing
needed downloading — the Tatuus mods alone are two complete ladders (the
European single-seater one and the American Road to Indy).

**THE BAR RISES, AND THAT IS HIS DESIGN.** `needs` is the championship
position required IN THE TIER BELOW to earn a seat: fifth gets you out of
karting, second gets you into Formula One. It is attached to the tier being
ENTERED because that is how it reads to a driver. `validate()` rejects a rung
easier to reach than the one under it.

**Two names for a car, and they are not the same name.** `mods` are installed
FOLDER names — knowable before a car has ever been loaded, so the menu can
draw a cold-start ladder. `classes` are the CarClass string, which is what a
LIVE session reports (in practice and qualifying as well as races) and how a
result is credited. The class cannot be read off disk: vehicle definitions
live in compressed `.mas` archives, exactly as track layouts do.

**INSTALLED DOES NOT MEAN RACEABLE, AND NOTHING ON DISK SAYS WHICH.** The paid
GT3 cars sit fully downloaded — 188MB apiece, same folder shape, same `.mas`
files as free content — and will not load without the licence. A scan would
confidently offer a tier the user cannot race. So the car lists are CURATED in
`ladders.json` and the folder scan only ever suggests. `laddertest.py` §10
asserts no paid GT3 car is on the GT3 rung.

**THE MATCHING TRAP, caught by the test.** `SC2018X` and `SC2018` are two
different rungs of the stock-car path — a substring match taking the first hit
promotes a driver out of a series he is still in, invisibly, because both
answers look reasonable. Longest alias wins. And `_norm` splits camelCase, so
"IndyCar" folds to "indy car" while "INDYCAR" stays whole and the alias
matched neither: `_hit` has a second, space-squashed pass, gated at four
characters so "gt3" can never match "gt350".

**A MISSED PROMOTION IS NOT A DEAD END.** The user's call: stay and go again,
or take a different path. `sideways()` offers seats matched on REGISTER, and
pitched at the rung he MISSED rather than the one he is on — a driver who just
failed to make Formula One hears from GT3 and IndyCar, not from Formula 4.
Tier NUMBER means nothing across paths of different lengths.

### STEP 1 — `season.py` WIRING: BUILT 2026-08-18. It is driveable.

A career can now BE a rung. Pick a path in the menu, race a season at the
bottom rung, and at the end of it the seat above is offered or it is not.
`laddertest.py` §11-16 holds all of it, through the real create/record/advance
path against a throwaway careers directory.

**A LADDER CAREER IS AN OPEN SEASON WITH A PATH ATTACHED.** No new preset, no
calendar: `create("open", rounds=N, ladder_path=..., tier_index=...)` stores a
`ladder` block (`ladder.Progress.to_json()`) beside everything else. Each rung
runs a season of the same declared length, which is what gives it round numbers
and exact title maths — an open-ended career could never finish a season and so
could never promote anybody. `season_done()` refuses on exactly that ground.

**`VERSION` IS STILL 1, ON PURPOSE.** `load()` DISCARDS a career whose version
does not match, so bumping it would delete the user's existing careers. The
ladder block is read through `.get` with a default; an old file loads unchanged
and simply has no path. Bump only when an old file would be read WRONGLY.

**EVALUATING IS FREE, ADVANCING IS CONFIRMED** — LAW 3 in new clothes, and it
is why they are two methods. `Career.evaluate()` writes nothing and is called
on every menu redraw, so the driver can see all season what the seat costs and
whether he is currently clearing it (`earned` is the live answer, `promoted`
the verdict — one field could not say both). `advance()` archives the standings
and clears the season, which no amount of racing can undo, so it routes through
the confirm page like a delete.

**`advance()` takes the three things a driver can actually do**: `promote`
(refused unless earned, so a mis-click cannot skip a rung), `retry`, and
`switch` onto a path from `evaluate()["sideways"]`. The season's finishing
position is recorded into `Progress.results` in ALL THREE cases — it is his
record whatever he does next — and the season itself is archived as a SUMMARY
in `ladder_history`, never in full. A career file that grows without bound is a
career file that eventually fails to save.

**THE CLASS LOCK MUST BE CLEARED WHEN THE RUNG CHANGES.** `cls` is filled in by
the first race a season records, so carrying karting's class into Formula 4
would match nothing for the rest of the career — a career that silently stops
counting, which is the worst failure this module has. `_start_rung` clears
`cls`, `cls_any`, `rounds` and `quali_results`.

**THE RUNG IS A LOCK ON `match()` TOO, and only in one direction.** A class
that resolves to a DIFFERENT rung is refused (a GT3 race is not a round of a
karting championship); a class `ladders.json` has never heard of is UNKNOWN,
not wrong, and falls through. The car lists are curated by hand and will always
trail what is installed, so refusing the unknown would stop a career counting
the first time he races something the file does not happen to name.

**`ladder.known_mods()` is new and it exists to keep UNKNOWN and NONE apart.**
`installed_mods()` caches whatever it was last asked for, so calling it with no
game directory — which is what any caller that does not know one would do —
permanently caches an EMPTY list and every later "do you own this" answers no.
`known_mods()` returns None when nothing has ever scanned, and None means "do
not filter".

**`Career.ladder` returns a FRESH `Progress` every call.** A cached one held by
the panel would go on describing the rung he was standing on before he was
promoted, and the menu redraws far more often than a career changes. Mutating
what it returns changes nothing; `_put_ladder` is the only thing that writes.

**Menu:** New career -> *Ladder career* -> path -> races per season. Three new
pages (`career_path`, `career_plen`, `career_ladder`), all in `paneltest.py`'s
page sweep. **A ladder career skips the class page deliberately** — the rung
already names every car that belongs to it, in both of the two names a car has.
The career page carries a live rung/next-seat readout, and an *End of season*
entry appears only once the season is actually complete.

`Career.register` is on the object ready for step 2 onward — grassroots /
junior / professional / archive. It is a TONE for the booth, never a knowledge
base.

### 100% COMPLETION AND THE FIA UNLOCK — BUILT 2026-08-18

The user's design, in his words: *"to get 100 percent they need to have won
each of their respective final championships ... then the FIA grants them
permission to compete in the next one of their choice"*.

**AN ARC IS FINISHED BY WINNING ITS LAST CHAMPIONSHIP, NOT BY REACHING IT**
(`ladder.ARC_WIN`). Reaching Formula One and finishing eighth is a career and
it is not a finished story. `evaluate()["arc_done"]` is the flag, and it is
separate from `promoted` for the obvious reason: the top rung promotes nobody.

**100% COUNTS PATHS, NOT RACES OR RUNGS.** He does not have to drive every
division — there are far too many — he has to finish every arc. Five paths;
`career_pct()` is finished arcs over `ladder.career_paths()`, which **excludes
the historic tour**. The tour is bonus content with no final championship to
win, and counting it would put 100% permanently out of reach — which matters
more than it sounds, because the story beats key off completion.

**`newpath` IS NOT `switch`, AND THE DIFFERENCE IS THE WHOLE POINT.** A switch
is what a driver does when the seat above him did not come: it abandons the
path and the arc goes unfinished. A new path is a REWARD, granted only to a
driver who won the final championship, and only it banks into `ladder_done`
and counts toward the 100%. `advance("newpath")` refuses otherwise.

**He is offered TWO ENTRY POINTS on the new path** (`ladder.entry_options`):
the bottom rung, or the first PROFESSIONAL rung. Both, because neither is
obviously right — a Formula One champion racing karts again is absurd, and
forcing him into GT3 quietly deletes two thirds of a path he might have wanted
to drive. They collapse to one entry when a path's bottom rung is already
professional.

**RESULTS DO NOT TRAVEL BETWEEN PATHS.** `Progress.results` is keyed by tier
and read back as "how that season went" in the divisions view of the path he
is now on, so carrying a karting result onto the Road to Indy would show a
result against a rung he has never raced. The season summaries in
`ladder_history` keep the real record.

### THE BOOTH'S CAREER KNOWLEDGE — `Career.resume()` (data built 2026-08-18)

Asked for directly: *"the commentators should also know if the player has won
championships from other divisions and how long their career run has been ...
most of the gameplay comes from the commentary"*.

`resume()` is the truth layer for it, and the lines are step 3. It returns the
titles won, the reigning one, the arcs finished, seasons, races and where he is
now — "the reigning Formula 3 champion, and this is his first race in Formula
2", and the bigger one: a man in Formula One who won NASCAR four seasons ago.

* **EVERY FIGURE WAS WATCHED.** Titles are seasons this overlay recorded and
  scored. Nothing is a claim about the real world, which is why this is the one
  kind of driver knowledge a fictional GT4 grid can have — and why it needs no
  entry in `drivers.json`, which is the thing the ladder must never grow.
* **`reigning` is only true while it IS the season just gone.** A man who won
  Formula 3 two rungs ago is not the reigning anything; `reigning_now` says
  which it is.
* **THE CAREER FILE IS THE TRUTH, THE INBOX IS A VIEW OF IT.** The user's
  framing was that the booth knows his history "based on his inbox" — but the
  archive has a delete button in his own spec, so history stored in mail is
  history a delete can erase. `resume()` reads the career store; the inbox will
  render the same facts.
* Returns None off a ladder: an ordinary open career has no arc, and "his
  career" would then mean whatever happens to be in one save file.

### THE MISSED ROUND — decided 2026-08-18, built with the story (step 4)

The story's one choice costs **a whole race worth of points**, and the trap
found while designing it is worth keeping: **if the round is simply skipped,
nobody scores and the choice is free.** His rivals must have raced while he was
away, or the standings are identical to what they were and the dilemma is
theatre.

So the missed round is **SIMULATED**: the field finishes in roughly the order
their season's form implies, they bank real points, he banks none, and he comes
back to a championship that moved without him.

**AND IT MAY HAPPEN IN A REAL-NAMED SEASON.** The first draft of this refused
that, citing the rule about never narrating an event in his season that did not
happen. The user pushed back and he was right: that rule is about
CONTRADICTING SOMETHING HE WITNESSED, and a round he was not at has no witness
and no result file. The championship table was never rF2's — every point in it
is computed here, from his races. So the sharpened rule is narrower:

> **A simulated round produces finishing positions and points, never events.**
> No collisions, no drama, nothing the booth can narrate as though it watched.
> It moved the standings; that is all it did.

The historic tour is excluded, but not because of that rule — it has no
progression at all. Note that **the top rung of the single-seater path IS
Formula One**, raced in the `F1_AM` mods with real drivers, so a simulated
round will land in a field of real names. That is fine under the rule above.

**The booth may know he MISSED A ROUND — it is a fact of its own standings —
and must never know why.**

### THE NASCAR AND GT3 RUNGS ARE REAL NOW (2026-08-18)

Both were placeholder aliases matching nothing. The user installed the packs
and the folders are `NR2019` and nine cars prefixed **`STK `** — which is the
FREE GT3 World Series pack, not the paid Studio 397 GT3 cars. Those paid
folders are still on disk (`McLaren_720S_GT3_2018`, `Mercedes_AMG_GT3_2017`
and the rest), still unlistable, and `laddertest.py` §10 still holds them off
the rung.

Three lessons from wiring two names in:

* **The name a user reads in the rF2 UI is not a folder name.** He reported
  "GTR3 WORLD SERRIES" and "NASCAR 2019"; the folders are `STK …` and
  `NR2019`. Neither had ever appeared as a `CarClass` in any of his 293 result
  XMLs either, because he had not yet raced them. **Check
  `Installed/Vehicles` sorted by mtime** — newly unpacked content is at the
  top and answers this in one command.
* **`cup` was an alias on the NASCAR rung and it was a live bug.** It matched
  `Kart_cup_2014` and `ClioCup_2010` — both rung ONE of other paths — and
  only escaped notice because a longer alias happened to win each time. Now
  `cup series`. An alias short enough to be a common English word is a trap
  whatever `_hit`'s token rules do.
* **An alias must not depend on a spelling being right.** "GTR3 WORLD SERRIES"
  matched nothing while "GTR3 WORLD SERIES" matched; the bare alias `gtr3` is
  immune to the rest of the string and does not collide with `GT-R GT500
  2013`, which still resolves to Super GT500. Same for `stk`, which is a
  whole token in all nine folder names and appears nowhere else on the disk.

### STEP 2 — THE INBOX: BUILT 2026-08-18

`inbox.py` + `lines_data/mail.json` + `tests/inboxtest.py`, plus an envelope
button and two menu pages. Twelve kinds of mail, sixteen templates.

**IT IS CORRESPONDENCE, NOT NOTIFICATIONS**, at the user's explicit
instruction: *"make sure all the emails and notifications and articles are
detailed enough, I want a paragraph or two, it must be realistic."* `body` is a
LIST OF PARAGRAPHS and `validate()` **fails a template with fewer than two of
them, or under 60 words** — which is a real constraint, not decoration: the
personal mail only lands later because the player has spent a career reading
letters from people with jobs. The upper bound is 220 words, because a panel
has to render it.

Register per sender, and it is what makes them read as real: **FIA**
bureaucratic and passive (notifies, never advises), **team** brisk and specific
(the car, next week), **agent** transactional and slightly pushy (deals, seats).

**THREE RULES THE MODULE EXISTS TO KEEP:**

1. **EVERY NUMBER COMES FROM THE STORE, AND IS FROZEN WHEN SENT.** A result
   sheet asks `title_state(upto=n)` — the table as it stood after THAT round —
   so round one's letter says "second on 18 points" for ever. A letter that
   quietly reflects a position he reached three races later is a letter that
   rewrites itself.
2. **A MISSING FACT KILLS THE MESSAGE.** `lines.safe_format` blanks unknown
   keys, which is right for speech and wrong here: "they wanted  and they have
   taken someone who had it" would sit in the archive for the rest of the
   career. `_fill` returns None and the message is simply not sent.
3. **GENERATION IS IDEMPOTENT, DELETION IS PERMANENT.** Ids are deterministic,
   so `refresh()` runs on every menu draw and after every recorded result
   without doubling anything. `mail_seen` keeps every id ever generated, so a
   deleted message does not come back — the most infuriating bug a mail feature
   can have.

**THE ARCHIVE NEVER EATS UNREAD MAIL.** `_trim` holds it to `KEEP` = 120 by
dropping the oldest READ message first. The one letter the user has not opened
is the one the whole story depends on him being able to find.

**PERSONAL MAIL MUST LOOK EXACTLY LIKE ADMIN MAIL, and that is now enforced by
a test rather than by intention.** `inboxtest.py` §11 asserts no message
carries `priority`/`important`/`personal`/`story`/`colour` and that every kind
has the identical shape. The list shows a dot for unread and nothing else. **If
this ever starts flagging what matters, the ending stops working.**

**Where it lives:** an envelope beside the hamburger, top-left, with an unread
count. NOT the top-right the user first pictured — that corner is the relative
panel, which he uses every lap. In-session it is a BADGE ONLY; the reading
happens in the menu, out of the car. Radio is now, in-car, spoken; mail is
between sessions, out of car, read.

* The mail pages draw WIDER (`MAIL_W` 470) than the rest of the menu, because
  they are the only pages with prose on them, and a new `text` row kind has its
  own tighter height — twenty body lines at menu spacing is a panel taller than
  the screen.
* Opening a letter marks it read at the moment it is OPENED (LAW 11).
* **Deleting one letter has no confirm page**, deliberately unlike deleting a
  career: it is one message, and a dialog on every delete makes tidying an
  inbox a chore.

**THREE BUGS THIS SHOOK OUT, all of the kind only a build surfaces — and the
third was found by READING A WHOLE LETTER, which no test was going to do:**

* **A SLOT THAT OPENS A SENTENCE INHERITS ITS OWN CASE.** "{pos} in the
  championship is not enough" rendered as "fifth in the championship is not
  enough". This is exactly the bug `lines._sentence_case` exists for, and the
  fix is the same shape: `inbox._sentence_case` capitalises after filling, and
  centrally, rather than asking every template author to guess which slot might
  land first. Doing it in the template instead would put "Fifth" in the middle
  of some other sentence.

* **LAW 9 AGAIN, WITHIN AN HOUR OF THE LAW BEING QUOTED.** `DrawMixin._wrap`
  already existed — three-line cap, for the caption box — and a `_wrap` added
  to `PanelsMixin` shadowed it. The letter body came out empty. It is now the
  module-level `wrap_mail()`: **a helper that belongs to no class cannot
  collide with one that does.**
* **`lines.py` WAS LOADING `mail.json` AS DIALOGUE.** The loader takes every
  `.json` in `lines_data/` and treats any list it finds as a pool — that is
  what lets a pool be extended across files. `tracks`, `drivers`, `seasons` and
  `ladders` escaped only because their top-level values are DICTS. Mail's are
  lists, so twelve pools of email joined the booth's store and `python
  lines.py` reported them as broken entries. Nothing ever drew one (a letter
  has no `text` field) but the booth was one name collision away from reading a
  licensing statement on air. **`lines.NOT_DIALOGUE` is now explicit, and any
  new data file whose values are lists belongs in it.**

**The NEWS tab, the RECORD view and the DIVISIONS view are all built** — see
step 3 below.

### STEP 3 — THE NEWS FEEDS: BUILT 2026-08-18

`news.py` + `lines_data/news.json` + `tests/newstest.py`. Eight generated
kinds, seven period pieces across 1988 / 2021 / 2025, rendered into a NEWS tab
beside the inbox.

**IT SHARES THE INBOX'S MODEL RATHER THAN COPYING IT.** An article is a message
with `feed: "news"` — same store, same composer, same deterministic ids, same
delete-stays-deleted. Everything the mail already guarantees is guaranteed here
for free instead of reimplemented slightly differently. **Every message carries
`feed`, including the ones that could not possibly be news**: a field present on
some messages and absent on others is a field the archive can sort by, and
sorting is one step from highlighting — which is the thing the story cannot
survive.

**FEED 1, MILESTONES: THE SAME FUNCTIONS THE BOOTH USES.** `drivers.standing()`
and `drivers.just_won_title()`, not a second detector reading results and
deciding for itself. `newstest.py` §7 asserts it the only way that means
anything — the same question asked of both must give the same answer. A
parallel detector eventually disagrees, and **the viewer believes the headline,
because he can re-read it.**

**FEED 2, THE SEASON'S OWN DRAMA: TRUE BY CONSTRUCTION.** A new championship
leader, a lead coming down, a procession, a podium every time out — all
computed from the same `classified` lists the standings are, so they cannot
contradict the standings screen. No per-season content, so it works identically
in karting and in Formula One, which is exactly what a ladder needs.

* **A lead is only news when it is CLOSING.** Both halves are required — close
  AND closer than last round. A gap that has been small all season is the
  SHAPE of the championship, not news about it, and a feed that reports the
  shape every round is filler.
* **No lead change is ever reported after round one**, where somebody leads by
  definition.
* Dominance and podium streaks fire at marks (3, 5, 8, 12) rather than every
  round, so a runaway season produces a few articles and not fifteen.

**FEED 3, PERIOD CONTROVERSY: THE ONE THAT COULD LIE.** Era-gated, written per
real season, and **it takes no slots at all** — `validate()` rejects a period
piece containing `{`. That is the mechanical form of the rule that has bitten
three times: it is paddock context (the rear-wing row, the pit-stop directive,
the fuel limit), period-true, claiming nothing about his races and therefore
impossible for his own standings to contradict. A season in a year we do not
hold gets NO period piece rather than another year's.

**A COUNT AND A ROUND NUMBER ARE DIFFERENT THINGS.** "Round 2" is a label and
stays a digit, the way every timing screen writes it; a count is prose and is
written out. The first draft mixed them — *"three wins from 3 rounds"* — which
is the exact tell that makes a generated article read as generated. Different
slots (`{n}`, `{of}` vs `{round}`), and a test.

**`_series_name` exists because "6-race season" reads absurdly in a headline.**
The rung first (it is what the FIA wrote on his entry), then the season's real
name for a year we hold ("2025 Formula One"), then the career's own name.

**AND `lines.py` SWALLOWED `news.json` TOO** — the same trap as `mail.json`,
one day later. `lines.NOT_DIALOGUE` now names both, and the comment there is
the general rule: **any new data file in `lines_data/` whose values are lists
belongs in it.** The symptom is `python lines.py` reporting "entry with no
template" for a name that is obviously not dialogue.

### THE RECORD AND DIVISIONS VIEWS — BUILT 2026-08-18

Both read straight from the objects the RULES read, which is the whole design:
`Career.resume()` and `Progress.unlocked()`. A rung cannot appear open on the
divisions screen and refuse him at the season's end, and the record cannot say
something the booth does not, because there is one source.

* **The record shows BOTH percentages and labels them** — career progress runs
  to three divisions, a 100% record to five.
* **It lists the SEASONS, not just the totals.** A man who won Formula 4 and
  then finished fifth in Formula 3 twice has a story no total can show.
* **A rung he owns no car for says so** rather than being hidden. Knowing the
  path continues into cars he has not got is information; hiding it makes the
  ladder look shorter than it is.

**TWO REAL BUGS THE VIEWS EXPOSED, both invisible until something rendered:**

* **`_archive_season` was throwing away the season's wins.** `_start_rung`
  wipes `rounds` on the very next line, so the archive summary was the last
  moment those races existed — and "eleven wins across his career" is exactly
  what the record view and the champion's profile are for. Wins and podiums are
  counted into the summary now. A small summary is right; WHAT it keeps has to
  be chosen rather than assumed.
* **NOTHING EVER SCANNED THE VEHICLE FOLDER.** `ladder.installed_mods()`
  required a `game_dir` from its caller and no caller ever passed one, so the
  scan never ran, every rung answered "no car", and the divisions view told a
  man with ninety-one mods installed that he owned nothing. It now finds the
  game itself exactly as `track.installed()` does. **The panel test caught it
  because it renders the real rows** rather than trusting the function to be
  called correctly — the same lesson as LAW 0, one layer up.

### STEP 4 — THE STORY: BUILT 2026-08-18

`personal.py` + `lines_data/personal.json` + `tests/personaltest.py`. Eight
sibling beats, the offer, two replies, four ending pieces and a generated
champion's profile. **`personaltest.py` is mostly a test of things that must
NOT happen**, which is the right shape for it — this is the one feature that
can only be got wrong once, because a player sees it a single time per career.

**THE COST IS REAL, AND `season.record_absence()` IS WHY.** Saying yes
simulates the round he misses: his rivals score, he scores nothing, and he
returns to a championship that moved without him. A skipped round where NOBODY
scores leaves every gap exactly as it was — the choice would be theatre. The
order comes from FORM (each driver's average finishing position so far) and is
DETERMINISTIC on purpose: the most consequential race of the story must not be
a dice roll, and the same save must not produce a different season each time it
is loaded. The round is stored `pos: 0`, `absent: True`, `simulated: True` — out
of every points sum, win count and podium count.

**PACING KEYS OFF RACES AND ARCS, NEVER A PERCENTAGE.** One beat per refresh —
a trickle, not a catch-up, so a player who ignores his inbox for ten races gets
them one at a time rather than five in a heap with the careful late ones next
to the cheerful early ones. The last two beats and the offer are gated to the
THIRD arc, which is the user's own thesis: one championship is a season or two,
and this is a story about a man who gave the sport years.

**THE OFFER NEEDS A SEASON WITH SOMETHING LEFT TO LOSE** (`OFFER_MIN_LEFT`).
Missing a round of a championship already decided is not a sacrifice, it is a
formality. It stays answerable for two rounds and then **expires with no
warning, no countdown and no colour** — that is the mechanism, not an
oversight.

**THE ENDING IS FOUR MESSAGES AND THEY DO NOT ARRIVE TOGETHER.** The principal
and the engineer land with the result — the paddock reacting the same evening.
The article about his father waits until he has actually READ one of them,
which is the only honest way to pace it: four unread messages in one refresh is
a credits roll, and the fourth is then just the last one he clicks.

**THE MATRIX IS REAL, AND THE SPORTING HALF IS WORDED FOR IT.**
`principal_close` and `engineer_close` exist because "congratulations,
champion" to a man who finished second is exactly the wrongness this product
has spent months eliminating — and **the champion's profile is not sent at all
unless he won it**. So: went/stayed × won/lost, four endings, all four tested.

**THE PROFILE IS GENERATED FROM `Career.resume()`** — seasons, starts, wins,
podiums, and the divisions he climbed with what he did in each. **It must not
invent a team name**: the store knows divisions and car classes, never
entrants, and a made-up team is the one false note nobody would forgive in the
article that closes a career. `personaltest.py` §11 greps for it.

**THE ILLNESS IS NEVER THE SUBJECT OF A SENTENCE.** It arrives in subordinate
clauses about tablets, appointments, the television being on with the sound
off. A beat that says "Dad is unwell" has told the player what to feel, and he
will feel nothing. §2 greps for the blunt version.

**NOT ONE BEAT TAKES A SLOT** — `validate()` rejects any that does. A slot is a
way for a letter to fail to send, and this is the one thread that must never
fail to send because a fact was missing. It is also why a sibling never writes
your surname at you.

**AND IT IS STILL INDISTINGUISHABLE FROM ADMIN MAIL.** Same store, same
composer, same fields, same tab, no marker of any kind. §12 asserts a letter
from his brother carries nothing a licensing statement lacks. **If that ever
stops being true, the ending stops working** — the reader was supposed to have
been trained to skim.

**THE BOOTH STILL NEVER KNOWS.** §13 checks three ways: no part of the story
loads as dialogue (`lines.NOT_DIALOGUE` now names `personal.json` too — the
third file to fall into that trap), nothing in the spoken pools is about a
father, and `overlay_booth.py` never passes anything from this module to
`_say`. The only point the two worlds touch is the final article.

### READING A WHOLE CAREER — `careerdemo.py` (2026-08-18)

Ten seasons, three arcs, every message in arrival order, through the REAL
modules — `season.record`, `inbox.refresh`, `news.refresh`,
`personal.refresh`, `Career.advance`. Nothing is mocked: **if a letter reads
badly here it reads badly in the game.** Output also lands in
`_career_preview.txt`.

The results are SCRIPTED so the read-through is stable. A career that came out
differently every run would be impossible to review, which is the whole point
of the file.

**IT CAUGHT TWO THINGS A TEST NEVER WOULD:**

* **A promotion moves ONE rung.** The first script jumped GT3 -> Prototype,
  `advance("promote")` did nothing, and the same season replayed silently.
  The demo now reports "script and rules disagree" rather than looping.
* **The champion's profile deleted where he came from.** It listed the last
  four divisions, so a man who spent five years climbing out of karting "came
  up through GT3". It now shows the first two and the most recent two.

**Volume, measured over the whole career**: 241 messages — 89 news, 152 mail,
9 of them from his brother. That is about four a race, which reads as a real
inbox. If the news feed ever feels heavy, `news.DOMINANCE_MARKS` and
`STREAK_MARKS` are the knobs, and a dominant season is what makes it loudest.

### THE VOLUME SLIDER — and the knob that did nothing (2026-08-18)

Asked for: *"can I have a volume slider please? I want to be able to lower the
volume on the commentary."*

**IT WAS A DEAD KNOB.** `Tts.volume` had been stored since the class was
written, `factor_tv` had been passing `cfg["volume"]` (0.9) into it since the
first day, and **nothing ever read it**. Exactly the shape of the deleted
`cast.intensity_voice`: the setting anybody would reach for, changing nothing,
so a user lowering it would reasonably conclude the feature was broken. It was.

**THE PCM IS SCALED, NOT THE SYNTHESIS.** edge-tts takes a volume argument, but
that value is part of the RENDER CACHE KEY — so moving a slider would
invalidate every cached line and re-render the lot, one 2-6 second render at a
time, exactly while the user is fiddling with it. `Tts._scaled()` scales the
finished 16-bit PCM instead:

* Instant, and it leaves the expensive render cache untouched.
* It applies to the STINGS and the mail tone too, which were mixed against the
  commentary and have to stay in proportion.
* Scaled copies are cached beside the originals in **5% buckets**, so a
  repeated line at a settled volume costs nothing after the first play.
* `v * v`, not `v` — perceived loudness, so half on the slider sounds like half.
* Any failure returns the ORIGINAL file. A line the user cannot hear because
  the scaler broke is far worse than one louder than he wanted.

**A `slider` ROW KIND**, and a click anywhere on the bar sets the level. The
menu has never handled a drag and does not need to: one click is a complete
interaction, and a drag over a panel sitting on top of a running game is a way
to lose the pointer. The bar's own ends travel INSIDE the hit key, because the
row that drew them is long gone by the time a click arrives.

### YOUR OWN DRIVER NAMES — `lines_data/mynames.json` (2026-08-18)

Neither source the picker draws on can contain a name the user invented: one is
what rF2 reported in his own results, the other is the record book. A ladder
career is usually raced as somebody who does not exist, and **the menu cannot
take typed input** — the overlay never holds the keyboard. So the names live in
a file he can edit, seeded with the two he asked for.

**THE MERGE IS IN THE MENU, NOT IN `drivers.py`.** The first version put it in
`picker_names` and broke four assertions in `drivertest.py` §26 — correctly, as
it turns out: that function is the knowledge layer and its contract is "who is
really on this grid", which an invented name is not part of. `_rows_name`
stacks his own names on top, first, de-duplicated.

**These names get no record and no history**, and that is the same refusal as
everywhere else. What they DO get is everything the overlay watches: race a
season under one and the booth will say how many wins it has this year,
because it counted them.

### NATIONALITY, AND THE HOME RACE (2026-08-18)

The design always said the player's identity is THREE FIELDS — name,
nationality, home circuit — and only the name had been built. The user noticed:
*"you didn't include pick my ladder career driver nationality? it will be a
nice touch when I'm doing a home race and the commentators were aware."*

`nations.py` + `lines_data/nations.json` (40 countries), a picker in the career
menu, and three new booth pools.

**THE HOME CIRCUIT IS DERIVED, NOT ASKED FOR — so the third field costs the
player nothing.** `tracks.json` already holds a country for 56 of 68 circuits,
so once a driver has a nationality the home race falls out of data that was
already there. Asking him to nominate a circuit as well would be a second
question with a worse answer: he would have to know which of his installed
tracks the overlay recognises, and he would get it wrong for exactly the
circuits where the line matters most.

**THE COMPARISON FOLDS A LEADING "THE".** The circuit data holds twelve
circuits under "United States" and five under "the United States" — a home race
that fired at Watkins Glen and not at Sebring would be a bug nobody could
explain.

**Three pools, and they sit at opposite ends of the order:**

* `ladder_home` — pre-race, and it outranks everything except a season being
  decided that afternoon. It is a fact about the DAY rather than about the man,
  which is why it belongs in the build-up and not on lap thirty.
* `ladder_home_win` — after the flag, and it is the most valuable line in the
  file. Ask any driver which victory he would take.
* `ladder_nation` — bottom of the order, deliberately. Atmosphere must never
  displace a fact about what he has actually done.

**A DEMONYM IS A BARE NOUN** ("Australian"), because the lines put their own
article in front of it, and `adj` is separate because "a Australian licence" is
not a sentence. `validate()` rejects a demonym carrying an article.

**No nationality, no claim.** A career that never picked one says nothing about
where he is from and has no home race — it never guesses from the driver's
name. The picker marks which countries actually have circuits in the knowledge
base, so a player choosing one with none can see he has picked atmosphere
rather than a feature.

### THE FIA SAYS WHICH CAR TO LOAD (2026-08-18)

The user, trying to start a Hot hatch season: *"what car does the hot hatch
season fall under? I tried to start a game."* **He should never have had to
ask.** The overlay works out which division a session belongs to from the
CarClass rF2 reports, so loading the wrong car produces an off-career race and
no explanation — and the answer was sitting on his own disk the whole time.

`eligible` is a new FIA notice, sent once at the top of every season, listing
the installed cars that belong to the rung: *"Eligible machinery — Hot hatch …
Clio Cup (ClioCup_2010) or Renault Megane Trophy II
(Renault_MeganeTrophyII_2013)."*

* **Answered from the FOLDERS ON DISK, not from the curated alias list.** The
  question is "what do I select in the game", and an alias is not something he
  can select.
* **The folder is quoted beside the tidy name** — the tidy name is a guess at
  what rF2 calls it and the folder is not — **but only when it adds something**.
  "STK 488 GT3 (STK 488 GT3)" is a parenthesis doing no work.
* **Nothing scanned, nothing sent.** `_fill` drops a letter with an empty list
  in it, which is exactly right: a "you may run the following" notice with
  nothing following it is worse than no notice.

**A `` BUG WORTH REMEMBERING**: the first `pretty_mod` stripped years with
`(?:19|20)\d\d` and stripped nothing at all, because **underscore is a
word character** — "ClioCup_2010" has no boundary between the `_` and the `2`.
Separators first, then years.

### THE CORNER, AND THE MAIL TONE (2026-08-18)

**THE TOP-LEFT COLLIDED WITH ITSELF.** `draw_status` was written to clear a
single 30px hamburger; the envelope was added later into exactly the gap it was
leaving, and the mode badge went underneath both. On a loading screen — which
is precisely when the status box is on show — it covered the one control the
user needed, and his report was "I can barely even see the email button".

**`overlay_common.CONTROL_*` is now one shared strip** and every panel in that
corner measures from it: the two buttons, the badge under them, the status box
beside them, and the menu opening below the lot. **The strip is as wide as its
WIDEST member** — the first fix measured the button row (66px) and the badge
(150px) went straight back under the status box. A strip that only measures
part of itself is not a strip.

`paneltest.py` checks the RECTANGLES for overlap rather than the arithmetic,
because the arithmetic is what was wrong both times.

**NEW MAIL: a tone and a bubble.** `stings/mail.wav` is generated by
`tools_mailtone.py` — two notes a fifth apart, 0.19s, peaking at a fifth of
full scale. Written in code rather than shipped as a download so it can be
re-tuned in one line and has no licence attached.

* **Triggered by the unread count GOING UP**, not by a flag. Mail is generated
  in three different places (a banked result, the panel refreshing, the story)
  and a flag would have to be set correctly in all three.
* **NEVER OVER THE COMMENTARY.** A sting interrupts on purpose — it exists to
  land at the moment of the event. Mail is never urgent, so `_mail_ping` does
  the opposite: if anyone is speaking, the letter waits silently and the bubble
  does the work alone.
* **The bubble sits BESIDE the button, not on it** — the unread count is
  already on the envelope, and two marks in one 30px square is a mess.
* A missing wav is silence, not an error.

### THE MODE BADGE — which game am I in? (2026-08-18)

Asked for directly: a way to know whether the main campaign is running, a
plain season, or nothing. Three states, drawn as a pill under the two buttons:

| | when | colour |
|---|---|---|
| **CAMPAIGN** | a ladder career — story, divisions, a rung to climb | accent |
| **SEASON** | a championship with no ladder attached | good |
| **OFF-CAREER** | a career is loaded and THIS race is not one of its rounds | warn |
| **NO CAREER** | one-off races; nothing is recorded | dim |

**THE OFF-CAREER STATE IS THE ONE WORTH HAVING.** A career stays loaded for as
long as it exists, so jumping into a random race in a different car is the
normal thing to do — and in that session nothing records, the booth says
nothing about the championship, and the only way to know used to be inferring
it afterwards from a standings table that did not move. It reads
"armed, but no round": `_season_armed` goes true once the booth has decided
which round this session is, so armed-with-no-round is exactly that state.

It carries the ROUND as well, because "which mode" and "how far in" are the
same question to a driver about to start a session. **It hides while the menu
is open**, because the menu opens in exactly that spot — moving the menu
instead would move the thing the user is actually looking at.

### THE REPETITION PASS — 2026-08-18, after reading a whole career

The user read `_career_preview.txt` end to end and the verdict was the one
piece of feedback that mattered most: *"there is WAY too much repetition ...
the MEL emails became something I looked forward to, which is a problem because
it isn't supposed to be something the player is waiting for."*

**THAT IS THE MECHANISM FAILING, NOT A POLISH ITEM.** The story works only
because a career of licensing statements has trained the player to skim. A
background dull enough to skim is the goal; a background so repetitive that the
personal mail becomes the reward is the opposite, and it makes the offer
impossible to miss — which is the one thing it must be able to be.

**Four changes, and the third is the one that was actually visible:**

1. **THE RESULT SHEET DEPENDS ON THE RESULT.** One template sent after every
   round became five kinds — `result_win`, `result_podium`, `result_points`,
   `result_low`, `result_dnf` — with three wordings each. A team manager who
   writes the same paragraph after a victory and after a shunt is a team
   manager nobody believes in. **The retirement is checked FIRST**: a DNF
   classified twelfth is a retirement, not a bad race.
2. **MORE OF EVERYTHING ELSE.** `fia_notice` is new (six notices from race
   direction — parc fermé, the briefing, transponders, entry fees, medical
   equipment, the pit lane), on its own cadence so two bureaucracies never
   write on the same weekend. Every news kind gained wordings.
3. **A REPEATED SUBJECT LINE IS THE REPETITION THE PLAYER ACTUALLY SEES.** Two
   letters can have completely different bodies and still read as one letter
   sent twice, because **an inbox is a list of subjects**. Every variant now
   has its own subject, and `news` rotates on the SEASON as well as the round —
   without that, six-round seasons reproduced season one's headlines every
   year. Measured over the same career: 103 distinct subjects out of 259
   messages before, 113 of 224 after, with the biggest offenders gone.
4. **ONE STREAK STORY PER MARK, NOT ONE PER DRIVER.** Early in a season three
   men can all have perfect records; publishing three near-identical articles
   on one afternoon is the exact failure this pass exists to fix. The player
   first when he is one of them, else the championship leader.

**`_compose_any` walks the variants** until one can be filled, so a wording may
now ask for a fact that does not exist yet (`{behind}` means nothing to a
leader) without the letter being silently dropped.

### DID YOU KNOW — real history, era-gated (2026-08-18)

Asked for directly, and it is safe for the same reason the driver records are:
**these are checkable.** Ten pieces of genuine motorsport history — the 1971 Le
Mans distance record, the six-wheeled Tyrrell, the Targa Florio, Brabham in his
own car, Fangio's four manufacturers.

**EACH CARRIES `since`, THE YEAR THE FACT BECAME TRUE**, and is only ever sent
to a season at or after it — the same discipline a dated circuit fact follows.
A 1988 career is never told about the end of Group B. **No era, no trivia**,
which is the right refusal rather than a missing feature. `validate()` rejects
an undated fact.

### MEL — the thread, the milestones, and what happens after (2026-08-18)

* **Thirteen beats, not eight**, and the new ones carry what the user asked
  for: who this driver is. The kart still under a sheet in the garage with his
  handwriting on the tyre rack. Timing himself running to the shops aged
  eleven. The biscuit tin with the entry fees in it and the double shifts that
  filled it.
* **SHE WRITES WHEN SOMETHING HAPPENS, NOT ONLY ON A TIMER.**
  `milestone_first_title`, `milestone_promoted`, `milestone_arc` fire off the
  same facts the rest of the product uses, so she can never congratulate him on
  something that did not happen. A sibling who sends a letter about a boiler
  the week you won your first championship is not a sibling, she is a schedule.
  **They do not consume a beat** — the ordinary thread keeps its own pace.
* **THE THREAD QUICKENS AT THE END.** Thirteen beats at one every four races
  needs a fifty-race career before the offer can be sent, and a story that
  cannot finish is worse than a short one. In the final arc at the top rung the
  remaining letters come one per race — which is also how it goes when somebody
  is getting worse.
* **THE ENDING IS NOW A DEDICATION.** The user's call, and it is much better
  than what was there: if he went, the article is about a championship
  dedicated to his father, and says plainly that he missed a round to be with
  him and that the points very nearly cost him the title. **It has two forms**
  — champion and not — because a piece about a dedicated championship is false
  if there is no championship. If he did not go, the cold notice is unchanged.
* **THE CAREER DOES NOT END WHEN THE STORY DOES.** Mail and news carry on
  exactly as before, and `epilogue` adds four letters at a far slower cadence
  (`EPILOGUE_EVERY` = 6 races) about how she is handling it — the house, the
  months that vanish, going back to the karting place. A thread that stops the
  moment the plot is finished tells the player the person was a device.
* **THE 100% LETTER IS A SECRET AND IT IS HERS.** Winning all five divisions
  has nothing else to give a completionist, so it gives him the one thing the
  story left open: she has met somebody, she is moving abroad, and it does not
  hurt the way it did. It is never announced anywhere; a player who does not
  finish the fifth division never learns it exists.

### THE SECOND REPETITION PASS — 2026-08-18, and it was a PACING problem

The user read the rebuilt career and found the same fault in a new place:
*"Mel is way too involved now, she's basically sending an email at the end of
every race"*, and *"still way too much repetition with news reports"*.

**MEL WRITES TO THE SHAPE OF A CAREER NOW, NOT TO A RACE COUNTER.** That was
the actual bug and it was structural: a race counter knows nothing about the
shape of a career, so it fires hardest exactly where the races are densest —
which is the run-in, which is where she was least supposed to be chatty.

| | |
|---|---|
| unit | the SEASON, because it is the unit his life is organised around |
| ordinary cadence | one letter a season, never before round 2 |
| third arc | two a season — she is writing more because he is worse |
| final season | whatever is left, spread across the rounds |
| measured | **15 letters across a ten-season career** |

**AND THE THREAD IS ALLOWED TO SKIP.** If the last season is running out with
letters unsent, `_beats` jumps to the FINAL one — the offer waits on it, and a
story that never reaches its own choice is a worse failure than two unsent
notes about a boiler. This is the one place the schedule may lose content, and
it loses the right content.

**THE OFFER NEVER ARRIVES IN THE SAME BREATH AS AN ORDINARY LETTER.** Two
emails from the same person in one afternoon, the second of them the one that
matters, is a writer arranging the plot rather than a sister sending an email.
Season-aware: a letter *last* season is already a gap, and comparing round
counts across the winter would hold the offer back for half a year for no
reason a reader could see.

### THE NEWS FEED WRITES LIKE A PAPER NOW (2026-08-18)

*"They speak about drivers' performances and quali performances, and also
general news about famous drivers."* Four new kinds, all read off the store:

* **`news_quali_pole` / `news_quali_row`** — Saturday, from `record_quali`.
  **The player is the only driver we have Saturday data for**, and that is not
  worth apologising for: a feed that writes about HIS Saturday is a feed about
  his career. **One per season** — a paper does not run "quick again on
  Saturday" six times a year.
* **`news_form`** — a run of podiums in the last four rounds, and **never
  about the championship leader**, because that is the table read out loud.
* **`news_climb`** — somebody who has climbed three places in the standings
  since the early rounds. The least-reported story in racing.
* **`news_retro`** — a look back at the midpoint. A feed that only reports the
  last result has no memory, and a sport without a memory is a scoreboard.
* **`news_profile`** — a driver's real record, quoting `drivers.standing()`,
  **the same source the commentary uses**, so the paper and the booth can never
  disagree about who somebody is. A driver we hold no record for produces
  NOTHING rather than an invented career.

**Two rotation bugs found by measuring rather than by reading:** the trivia
index could only ever reach the first two facts in a six-round season (it now
advances with the season, so a decade does not read the same two), and the
retrospective's subject was identical every year.

Measured across the same ten-season career: **114 news items, 53 distinct
subjects; 167 letters, 75 distinct** — against 89 items from eight kinds
before.

### THE STORY — as designed 2026-08-17

The user's own narrative, and the brief he set for it: *"a subtle overarching
narrative that doesn't need much lore for it to have an effect"*. It is told
ENTIRELY through the inbox, and it rides on infrastructure that already has a
reason to exist — there is no story mode bolted on the side.

**The shape.** A driver whose parents never believed in him, who moved away and
worked himself into the ground to buy the first seat. The mother is already
dead when it starts. Across the career the sibling writes now and then — warm,
awkward, mostly about nothing — and a careful reader notices the father is ill
and getting worse while the driver becomes a champion somewhere else. Near the
end an email offers one chance to go and see him. Taking it is a choice; so is
never opening it.

**THE PAYOFF IS A NEWS ARTICLE, and there are two of them.** Went: a tribute
piece, the last race dedicated to him. Did not: a small item about a man whose
last request nobody answered.

**Three craft rules, agreed with the user:**

1. **THE CHOICE MUST COST A ROUND.** Saying yes was originally free, and a free
   choice is not one. Missing a race — with the standings showing exactly what
   it was worth — is the dilemma the whole story has been building toward, and
   it makes the other ending mean "you chose the championship" rather than
   "you failed to read your mail".
2. **INDIFFERENCE, NOT MOCKERY.** The failure article was to make fun of the
   dying man. A paper being cruel gives the player somewhere to put the
   feeling; a world that simply does not know who he was does not. Quieter,
   and it lands.
3. **MISSABLE FAIRLY.** The personal emails must look EXACTLY like admin mail
   for the whole career — no badge, no colour, no ceremony. That is the
   mechanism: by the time the important one arrives the player has been
   trained to skim them. It stays actionable for a round or two, then quietly
   does not.

**The 95% is what makes the 5% work.** The inbox must be genuinely dry the rest
of the time — superlicence points, testing days, seat announcements, steward
notices — written straight, because the personal mail only lands against that
background. The illness is never the subject of a sentence; it arrives in a
subordinate clause about tablets and recorded races.

### THE ENDING IS FOUR MESSAGES — specified by the user 2026-08-18

Recorded before step 3 begins, because everything built from here has to leave
room for it.

**WHEN IT FIRES: THREE ARCS WON, AND ONCE PER CAREER EVER.** The user's call,
and his reasoning is the story's whole thesis: *"I want it to be like he took
his obsession to the absolute limit and didn't even have time for his family."*
One championship is a season or two — nowhere near long enough for a man to
lose a decade. **Three divisions is years, and years is the point.**

An earlier draft of this section said the FIRST arc and that was wrong for
exactly that reason. What survives from it is the refusal to gate on 100%:

* **Only the single-seater path ends in Formula One.** "The newest World
  Champion" is wrong for four arcs out of five, so the profile piece is
  GENERATED PER DIVISION — NASCAR champion, GT3 champion, World Champion.
* Arcs four and five are the completionist 100%, with **no story attached**.
  The sporting half (principal, engineer, profile) arrives again, correctly
  worded for that division; the father story does not. It is spent, and it
  lives in the career file so a fresh career genuinely replays it.

**THE CAREER IS FINISHED AT THREE, NOT LOCKED.** He may keep racing, and the
records view says what he did. Nothing in this product should ever refuse to
let a man drive.

**THE STORY PACES ACROSS THE THIRD ARC.** The decline spans the whole of it and
the offer lands in its FINAL SEASON, where missing a round costs a title he is
actually fighting for. Coarse pacing is arcs remaining; fine pacing is rungs,
then rounds.

**THREE ARCS IS A LOT OF RACING, AND THE THING THAT SAVES IT ALREADY EXISTS.**
On ten-round seasons this is on the order of a hundred races. `entry_options`
lets a champion join a new path at its PROFESSIONAL rung — built as the
non-committal option, and it turns out to be the mechanism the whole timescale
depends on: the full climb once, then two shorter professional careers. **The
inbox should say so when the choice is offered**; a player who takes the
grassroots entry three times has signed up for something he was not told the
length of.

**TWO FIGURES, BOTH TRUE, NEITHER PRETENDING TO BE THE OTHER.** Three of five
is not 90% of anything, and the records view must not print a number it
contradicts. Career progress is measured against its ENDING (three arcs);
"100% completion" is a separate line for all five.

**THE FOUR ENDINGS ARE A MATRIX**, agreed with the user: *took the trip or did
not* × *won the final title or did not*. Both facts are already tracked, and it
is what turns the failure case into a real ending rather than a lose state.

**A PACING CONSEQUENCE**: the offer email must arrive BEFORE the final season
is over, or the choice cannot cost a round in a season that still matters. The
beats therefore key off rungs remaining AND rounds remaining in the last one.

The player receives exactly **four** things, and no more:

| | who | what |
|---|---|---|
| 1 | **Team Principal** | well done, what a season, written as a man who has been there all year |
| 2 | **Race Engineer** | congratulations, and what an honour it has been |
| 3 | **News report** | the newest World Champion: a snapshot of his career — the cars he has been with, his best performances |
| 4 | **News story** | the father. The reveal, and the only branch |

**FOUR MESSAGES IS THE SPEC. Not five, not a montage.** An ending that keeps
going stops being an ending, and the fourth one only lands because the three
before it have already finished the sporting story.

Notes on each, and the reasoning is as much the deliverable as the content:

* **The engineer's is the one that will do the damage, and it works because of
  a constraint that already exists.** Dean's radio cap is 18 words — a pit call
  is short or it gets talked over. An email is the only place in the entire
  product where he can say more than that, and the whole career has trained the
  player to hear him in clipped fragments. **Do not let him sound like the team
  principal.** He should be worse at writing than at talking to a driver.
* **The champion's profile is GENERATED, not written.** Every fact in it is
  already in the store: `Career.resume()` has titles, seasons, races and the
  arcs finished; `ladder_history` has each division and where he finished it;
  the rounds hold his best results. **It must not invent a team name** — the
  store knows car classes and divisions, not entrants, and a made-up team is
  the one false note that would sit in a career-defining article.
* **Nobody in the paddock knows about the father.** The principal and the
  engineer write about racing, because that is all they have ever known about.
  The article is the ONLY place the two worlds touch, and that is exactly why
  it works — see THE BOOTH NEVER KNOWS.
* **The failure variant stays indifferent** (craft rule 2). Not cruel, not
  pointed: a world that simply does not know who he was. It must not mention
  his championship at all — a paper that connects the two has noticed, and the
  whole point is that nobody did.

**Two structural rules:**

* **Beats key off RUNGS REMAINING, not a percentage.** Touring has three tiers
  and Single-Seater has five, so "90% through" is two very different amounts of
  playing.
* **Per career, and it never re-fires.** State lives in the career file beside
  the ladder progress, which also means a fresh career genuinely replays it —
  the replayability the user is after.

**THE BOOTH NEVER KNOWS.** Miles and Chuck are not in on it. The story stays in
the inbox, and the only point where the two worlds touch is that final article
— which is exactly why it works.

### What is designed and NOT yet built

* **The inbox.** The user's own spec: a notification hub top-right that is also
  an archive (with delete), the anchor for story progression, a NEWS tab, his
  results and records, and which divisions are unlocked. Two constraints found
  by reading the layout: **the top-right is already the relative panel**
  (`overlay_draw.py:323`), and **you cannot read email at 200mph**. Both
  resolve the same way — a small unread badge during a session, and the inbox
  itself only out of the car, where the relative panel has nothing to show.
* **Keep the inbox and the radio apart.** Radio is now, in-car, spoken. Inbox
  is between sessions, out-of-car, read. The engineer never emails about a
  braking point.
* **Emails are fiction and that is fine** — a made-up agent writing to a
  made-up driver invents nothing about a real person. But any NUMBER in an
  email or headline must come from the career store, or the standings screen
  contradicts it.
* **NO NEW DRIVER KNOWLEDGE FOR THE LADDER SERIES, and this is the point.**
  `drivers.json` works because it holds real people with checkable records. A
  GT3 mod's AI has no record anywhere, and writing one would be inventing
  facts. Ladder seasons EARN theirs instead: `drivers._career_results` already
  counts wins, podiums and starts for ANY name out of the career's own
  `classified` lists, so "three wins already this season" is true because the
  overlay watched it happen.
* **The milestone news the user asked for ALREADY EXISTS as booth lines** —
  `driver_first_win`, `driver_title_first`, `driver_title_more`, and
  `just_won_title()`. The news tab must be a second RENDERING of those same
  events rather than a parallel detector, or a headline will eventually
  contradict what Chuck just said.
* **Register per rung, not knowledge per rung**: grassroots / junior /
  professional / archive, declared on each tier. Karting commentary is not F1
  commentary, but that is a TONE, and tone is cheap.
* **The player's own identity is THREE FIELDS and no more**: name (exists
  already), nationality, home circuit. Every field is something the booth must
  be able to say truthfully AND interestingly, and a backstory questionnaire
  produces facts nobody can use. "The young Australian, and this is his home
  race" earns its keep; a favourite colour does not. The far bigger prize is
  free — his TRAJECTORY out of the career store: "the reigning Formula 3
  champion, and this is his first race in Formula 2."

### THE NEWS TAB — three feeds, one of which already exists

1. **MILESTONES — already built, do not rebuild.** `driver_first_win`,
   `driver_title_first`, `driver_title_more`, `just_won_title()`. These are the
   exact things the user asked for ("Lando's first win", "Lewis takes his
   eighth"), and `drivers.Standing` already applies them to the AI identically
   to the player. The news tab renders the SAME event the booth speaks. A
   second detector would eventually print a headline contradicting Chuck.
2. **HIS OWN SEASON'S DRAMA — generated, and true by construction.** Two
   drivers repeatedly close in the standings, a second collision between the
   same pair, one team winning six of seven. All of it comes from data the
   booth already keeps, needs no per-season content, and works identically in
   karting and Formula One.
3. **PERIOD CONTROVERSY — written per real season, era-gated.** 2021 hands it
   over: the flexi-wing row, the pit-stop directive, tyre pressures, engine
   penalties, the cost cap. 1988 has the turbo ban coming and Senna–Prost
   curdling. This is KNOWLEDGE, like driver records, and belongs in a data
   file beside `drivers.json`.

**THE LINE, and it is the same one that has bitten three times: never narrate
an event in HIS season that did not happen.** "Hamilton and Verstappen collide
at Silverstone" is false if they did not, and the user can see the standings.
So real-season drama arrives as PADDOCK CONTEXT — "rival teams have asked the
FIA to look again at the rear-wing tests" — which is period-true, claims
nothing about his race, and still sets the mood. Fictional ladder grids have
no such constraint: invent freely, because nobody real is being accused.

### BUILD ORDER (agreed with the user)

Each layer must have something real underneath it before the next goes on, and
the user can drive it after step 1 rather than waiting for all of it.

1. ~~**`season.py` wiring**~~ — DONE 2026-08-18. See the section above.
2. ~~**The inbox panel**~~ — DONE 2026-08-18. Badge, archive, delete and the
   dry admin mail are built; the results/records and divisions views are not,
   and belong with step 3.
3. ~~**The news feeds**~~ — DONE 2026-08-18. All three feeds are built; the
   results/records and divisions views of the inbox are not.
4. ~~**The story beats**~~ — DONE 2026-08-18. `personal.py`. All four steps of
   the build order are complete.

---

## THE FIRST-RUN INTRODUCTION, AND THREE DASHBOARD FAULTS HE FOUND BY USING IT

### THE ENGINEER EXPLAINS THE BUTTONS, ONCE

His idea: *"when someone first launches there can be voice tutorial on what
buttons do what ... narrated by the enginner"*. The engineer is the right voice —
the booth describes a race to a viewer, the engineer tells the DRIVER what to do,
which is what an introduction is.

`tutorial.py` holds the state and the rules; `lines_data/tutorial.json` holds nine
ordered steps. **It is a SCRIPT, not a pool** — the only sequenced dialogue in the
product, so it is a list and nothing rotates. Each step may `point` at `menu` or
`trophy`, and that button is ringed in green while the line plays: "top left is
the menu" teaches far less than the menu lighting up as he says it.

The rules are the feature:

  * ONCE, on a flag in `_settings.json`, with a settings row to hand it back.
  * NEVER over a green flag. It runs in the garage or on the menu with no session
    at all, driven from ABOVE the on-air gate.
  * ANY CLICK ends it, and skipping counts as heard: a player pressing things has
    told you he does not need this.
  * ONE LINE AT A TIME, gated on the voice actually finishing rather than on a
    timer, or nine lines arrive as one noise.
  * RADIO OFF, NO LESSON — and it stays OWED rather than being marked heard, so
    it is still there when he turns the engineer back on.

`tests/tutorialtest.py` drives all of that.

### THE INTRODUCTION'S TWO FAULTS, BOTH FOUND BY RUNNING IT

**It played on every launch.** The flag is written by the tick AFTER the last
line — and that tick returned at the green-flag gate, because he pressed drive the
moment the engineer stopped talking. Nothing was ever saved.

**RECORDING THAT SOMETHING HAPPENED IS NOT SPEAKING**, and it must not sit behind
a gate that exists to stop the talking. The completion check now runs above every
other gate. This is the FOURTH instance of one mistake in this project — the other
three were qualifying banked below the on-air gate, a settle that needed the
winner's flag, and a result that needed the leader to finish. The shape is always
the same: **bookkeeping hung off a condition that exists to control output.**

**And nothing was ever highlighted.** Each corner button is a Toplevel *exactly
the size of the button*, so a ring drawn three pixels outside it is clipped by the
window and never reaches the screen. The tutorial's pointer had never been
visible — and neither had the season-over ring I added to the trophy earlier the
same evening, which explains why he never mentioned seeing that either.

`_mark_button` draws INSIDE the edges: a coloured ring inset by its own width,
plus a dark one hard against the border, because these buttons sit on whatever the
game happens to be drawing and one line can vanish into it. Green for the
tutorial's pointer, accent for a season waiting to be decided.

**The lesson for any future mark on a corner control:** the canvas is not the
screen. A panel is a window, and a window clips.

## THE LADDER NOW HOLDS THE DOOR FOR THE PROGRAMME

*"oh yes i wa ssuposed to do a year of development"*.

Winning Formula 2 promoted him to Formula One on the LADDER's own rules, while the
programme had told him in writing that he sits out a year first. **Two rulebooks
agreeing by accident, and the ladder's was quicker** — so he was in a Formula One
car with the story still owing him 2020, and the development year, the test
programme and the whole Bottas beat were skipped.

Two gates, both in `season.py`:

  * `_programme_holds()` — `evaluate()` reports `earned` but NOT `promoted` while
    a programme sits between the championship and the seat, and `held` says why
    so a screen can explain it. Only when the next rung is Formula One: a
    programme driver still climbing to F2 is promoted like anybody else.
  * A DEVELOPMENT YEAR HAS NO ROUNDS IN IT. `match` refuses a Formula One round
    while the stage is DEV. The letter says he does not step into the car until
    2021, and a round banked during that year would be the story's own premise
    contradicted by the table underneath it.

### AND THE TEST THAT SHOULD HAVE EXISTED ALL ALONG

`programmetest` §7m walks the arc from the Formula 3 offer to the seat using ONLY
what a player touches — `inbox.refresh`, `news.refresh`, and the dashboard's click
handler. It never calls `apply_verdict` or `take_deal`.

**That is the whole lesson of this session.** Every beat of this arc had a unit
test, every one of them passed, and the arc was unreachable — because each test
called the transition itself. A test that drives the state machine directly
proves the machine works. Only a test that goes through the product's own doors
proves the product does.

## MEL LEARNS THE SPORT SLOWLY, AND NEVER ITS STRUCTURE

He caught the first draft of her Formula 2 letter saying *"there is exactly one
category above this one. One."* &mdash; and was right to: *"she sounds very clued up
about the sports whereas she shouldnt know too much about it but learn more about
motorsports as the carrer advances"*.

**She is the one voice in this product with no expertise, and that is the whole
job she does.** Everything else &mdash; the booth, the engineer, the news, the team
&mdash; is fluent. She is what the career sounds like to somebody who loves him and
does not follow it, and the moment she can explain the ladder she stops being that.

The curve her letters follow:

  * **Karting, Formula 4** &mdash; she knows nothing and says so. *"I don't understand a
    single part of how it works and I'm not going to pretend to."*
  * **Formula 2** &mdash; she knows the FACT and not what it means. The significance
    arrives secondhand, from a man at work she does not entirely trust: *"oh, that
    is basically the one below the top"*, and she has no idea whether he is right.
  * **Formula One** &mdash; the only rung she had heard of before he left, because
    everybody has. *"I have heard of it my entire life without ever once watching
    it, which I realise is going to have to change now."*
  * **After that** &mdash; she picks up words, never the shape. She may know what a
    podium is by the end. She never knows how many categories there are.

**Two rules for writing her:** a fact about racing reaches her from a person, never
from her own understanding; and every letter turns to family before it ends &mdash;
Dad, the pub, the pharmacy, the spare room. That is what she is actually writing
about.

## MEL LEARNS THE SPORT SLOWLY, AND NEVER ITS STRUCTURE

He caught the first draft of her Formula 2 letter saying *"there is exactly one
category above this one. One."* and was right to: *"she sounds very clued up about
the sports whereas she shouldnt know too much about it but learn more about
motorsports as the carrer advances"*.

**She is the one voice in this product with no expertise, and that is the whole
job she does.** The booth, the engineer, the news feed and the team are all
fluent. She is what a career sounds like to somebody who loves him and does not
follow it — and the moment she can explain the ladder, she stops being that.

The curve her letters follow:

  * **Karting, Formula 4** — she knows nothing and says so. *"I don't understand a
    single part of how it works and I'm not going to pretend to."*
  * **Formula 2** — she knows the FACT and not what it means. The significance
    arrives secondhand from a man at work she does not entirely trust: *he told me
    it is basically the one below the top... I have no idea whether he is right.*
  * **Formula One** — the only rung she had heard of before he left, because
    everybody has. *"I have heard of it my entire life without ever once watching
    it, which I realise is going to have to change now."*
  * **After that** — she picks up words, never the shape. She might know what a
    podium is by the end. She never learns how many categories there are.

**Two rules for writing her.** A fact about racing reaches her from a PERSON,
never from her own understanding. And every letter turns to family before it ends
— Dad, the pub, the pharmacy, the spare room — because that is what she is
actually writing about.

### AND A DATA FILE IS EDITED AS DATA

The first attempt at normalising her quote marks ran a text substitution over the
raw JSON and injected unescaped double quotes into string values, breaking
`personal.json` for four suites in one command. `json.load`, edit, `json.dump` —
the parser knows how to escape and a regex does not.

## THE ARC WAS NEVER WIRED UP — five reports, one root cause

He won Formula 2, moved into Formula One, and reported: no letter about replacing
Bottas, no news story about a seat that big changing hands, no mention that he
must drive the Mercedes, and the dashboard calling him CHAMPION of a championship
he had not won.

**`apply_verdict` AND `take_deal` WERE CALLED BY NOTHING BUT THE TEST SUITE.**
Every piece of the arc past Formula 2 existed and none of it was reachable by
playing: the programme could not leave `signed`, so no development year, no seat,
no `prog_won`, no `news_seat_taken`. The tests passed because they called the
functions themselves — which proves the function works and says nothing about
whether the product ever calls it.

**That is the third distinct shape of this failure in two days.** A dead
navigation key, a dead action key, and now a whole feature nothing invokes. The
audits added for the first two check that a button's key is dispatched; nothing
checks that a state machine's transitions are ever driven. If a fourth turns up,
that is the guard to write.

### AND IT FAILED A SECOND TIME FOR A SECOND REASON

With the verdict applied, the letter still did not arrive: `prog_won` fills a
position slot from `career.my_position()`, and by then the ladder had promoted him
into an empty Formula One season — no rounds, no position, empty slot, and the
inbox DROPS a letter with a missing fact. The biggest letter in the arc was being
discarded for want of a number it was asking the wrong season for. It reads the
archived season now.

`season_verdict` can also recover from `ladder_history`, because the ladder
promotes on its own rules and archives the season as it goes — so a verdict that
was not banked before the promotion had nowhere left to look.

### THE REST OF THE LIST

  * **"CHAMPION" beside the division.** `status()` is a CAREER standing, and the
    header printed it straight after the division, so a Formula 2 champion in a
    Formula One car read as the Formula One champion. A standing is now named with
    the championship it was won in — "Formula 2 champion" — or not shown.
  * **The F1 mark had a plate.** `_logo_ink` used an absolute threshold, and the
    Formula One mark measures 0.40: dark in the abstract, and still LIGHTER than
    the card it sits on. Plating is decided by contrast against the actual ground
    now, so only karting gets one.
  * **The top-right mark was clipped.** `place()` clamps a panel back onto the
    desktop; `canvas_at` translated the drawing by the origin the CALLER asked
    for. A clamped window therefore drew its contents offset by however far it
    moved, cutting off exactly the edge that had been hanging off the screen. It
    draws at the placed origin now — a whole-class fix, not just this mark.
  * **The homologation list never said which entry was his.** The FIA does not
    care which of a category's cars a competitor enters and a team cares about
    nothing else, so the TEAM now writes: the entrant on the junior arc, and at
    Mercedes the second car, "the one Valtteri Bottas was in".
  * **Mel said "you've won the whole thing".** True and ambiguous. She names the
    division now, secondhand from the man in the pub, which is how she would have
    heard it. It needed the ONE slot her letters are allowed — declared by name in
    `validate` rather than the rule being waived, with a test that the caller
    cannot forget to fill it.

## THE SEAT GATE — a rival's car is not a round of his season

He went looking for this one on purpose: *"i started the next quakyfying session
in a DAMS F2 car instead to see if the campaign would shut off if i was not in the
right car and sadly it didnt which is very imersion breaking"*.

He was right, and it is the gate the whole arc rests on. **The seat lock only ever
covered FORMULA ONE** — `_programme_seat`, which works on DRIVER names because
both Mercedes report the same constructor. Formula 2 and Formula 3 put the entire
grid in ONE class, so the class lock cannot tell ART Grand Prix from DAMS, and
nothing else was looking.

**THE ENTRANT IS NOT IN THE LIVE SESSION.** rF2's scoring gives `mVehicleName` —
`2019 - #06 Nicholas Latifi` — which names the driver of the entry and never the
team. The team is only in the result XML (`TeamName`), and `Career.team_of`
already learned those pairings from his own files: his store knows the entire 2019
Formula 2 grid, Latifi at DAMS and Mazepin at ART. `team_for_entry` turns "which
car is he in" into "whose car is he in", the booth passes it to `Season.match`,
and `_programme_team` says which entrant this rung's rounds belong to.

    ART car   -> round 3 counts
    DAMS car  -> OFF-CAREER
    unknown   -> counts

**REFUSED ONLY WHEN THE CAR POSITIVELY BELONGS TO SOMEBODY ELSE.** An entrant
nothing has learned about falls through, exactly like an unknown class and an
unknown year: a career that stops counting for want of a fact is a worse failure
than one that counts a race it should not have.

`_same_team` compares by CONTAINMENT after folding, because the real spellings do
not line up — "Sauber Junior Team by Charouz" against "Charouz", "ART Grand Prix"
against "ART GP". A gate that shuts a career down over a missing word is worse
than no gate.

The log now names the reason too: *"off-career — that is a DAMS car and your seat
is at ART Grand Prix"*. Off-career with a list of facts leaves him guessing which
one was wrong, and this is the one refusal a player will actively go and test.

### AND THE TEST THAT ALMOST LIED

The first version of that test passed a slug taken from an unraced round of an
open season — which is `""`, and `match` refuses everything when the circuit is
empty. **The three REFUSAL checks passed without testing anything.** A test whose
setup makes the answer inevitable is worse than no test: it reports the feature
working. The accepts failing is the only reason I looked.

### A DEAD BUTTON, AND THE AUDIT THAT FOUND A SECOND ONE

*"the simulate rounds button isnt working"*. The dashboard asked for
`confirm:simulate` — a key pattern I invented that nothing dispatches. The real
keys are `sim_round` and `drop_last`, and `sim_round` also puts up its own
confirmation and refuses with a REASON (`_sim_blocked`), which the dashboard was
not showing either. Both rows drew, both highlighted, neither did anything.

He guessed it was because he had not raced in Formula 2 yet. It was not: in his
overlay the grid resolves — `Formula 2 2019` is a class the store has seen, with
twelve drivers at his rung — and a copy of his save simulates round three as P4
the moment the key is right. **My first probe said "race them once first" only
because the harness passed `career=None`**, which forces an empty grid. Worth
remembering: a stub that omits a dependency does not prove a refusal.

**THE PAGE AUDIT COULD NOT CATCH THIS** — it validates `page_` keys against the
router, and this was an action. So there is now a second audit: every action key
any page offers must appear in the click handler or the toggle table. It
immediately found **"Close career", dead since before the dashboard existed** —
the row said `career_close`, the action is `career_none`, and the KeyError out of
`_menu_toggle` was swallowed by the overlay's own exception guard.

That is the argument for the audit in one line: **nobody had ever pressed Close
career, so nobody knew.** The guard understands the three dispatch shapes — a
literal key, a `prefix:` split into an act, and a slider whose key is a name
rather than a command.

### TWO BARS ON ONE SEASON, AND THE SCREEN READ THE WRONG ONE

*"im in F2 and on the progress line it says P2 as the goal the achieve to prgress
but it is supposed to be p3 and above"*.

My first move was to change `ladders.json` so Formula One asks for third, and
**five checks in `laddertest` immediately said no.** They were right:

  * §2 protects the entry bar ESCALATING up the path — 5, 4, 3, 2. Making the
    last step 3 flattens it.
  * §13 is a whole section called "missing the cut is not a dead end": third in
    Formula 2 is a fine season and NOT a Formula One seat, which is what produces
    the sideways move to another path.

So there are genuinely two bars on that season and both are correct:

  * the LADDER wants **second** from a driver with no programme;
  * the ARC wants **third**, because a podium being enough is *what having an
    academy behind you is for*.

That is good design and it was already in the code. **The bug was that the
dashboard read the wrong one of the two** — `bar_state` returns None until he has
scored, and the screen then fell through to the ladder's number for a different
thing. A called-up driver now sees "Formula One seat — needs P3" from the moment
he arrives, and the measured version once there is a gap to measure.

**Reverting my own data change was the fix.** A test suite that stops a change is
doing its job, and the right response is to read what it is protecting rather
than to update it.

### AND THE BASE VOLUME IS 65%

*"the intro race engineer is very soft, can we have the base volume at 65"*. The
engineer is not attenuated — the introduction speaks at the calm rung like the
rest of his lines. The cause was the master volume sitting at 35% in his own
settings. `DEFAULTS["volume"]` is now 0.65 so nobody has to go and find it, and a
first-run introduction is the first thing anybody hears: if that is quiet, the
product is quiet.

### "ANY CLICK ENDS IT" FOUGHT THE SCRIPT'S OWN INSTRUCTION

*"you said it was a click to end it, but i need to click the trophy thing whcih i
do then it ends it, so i dont know what you mean"*.

The script says **open the trophy and start a career** — and "any click ends the
introduction" included that click. Doing what the engineer just asked cancelled
him mid-sentence. The rule and the content were written an hour apart and neither
knew about the other.

**Opening the menu or the trophy IS the tutorial working.** The two button
branches at the top of `menu_click` return before the stop is ever reached;
everything below it — a row, a toggle, a page — is a player who has started doing
something of his own, and being talked at through that is the tutorial nobody
finishes.

Worth keeping as a design note beyond this feature: **a dismissal rule has to know
what the thing it is dismissing asked for.** "Any interaction cancels" is only
correct when the thing being cancelled never invites an interaction.

### AND THEN HE USED THE DASHBOARD

**New career and Load career went to the settings page.** The router maps the name
after `page_` through a table and falls back to `"main"` for anything it does not
recognise — so a mistyped key does not fail, it silently lands on settings. The
dashboard asked for `page_career_new`; the router knows `page_new`. The suite
passed because **the tests asserted the keys I had invented rather than the keys
the router understands.** Every page is now walked against the router's own table
and a nav key that resolves to the fallback is a failure.

**Back went to the wrong place from five pages.** The inbox returned to settings;
the standings, results, record and divisions returned to the old career page. All
five had moved onto the dashboard and none of their exits had. The router audit
CANNOT catch this and the distinction is the useful part: those keys were all
valid pages — they were the wrong pages. **Where a Back button goes is a fact
about the ROUTE**, so `paneltest` now writes the route down: a page reached only
from the dashboard goes back to the dashboard, a sub-page goes back to its parent.
Divisions is reached from both the dashboard and the record, so it remembers which
(`_div_back`) — the same trick `_ladder_back` already used.

**The tiles looked like a forgotten career.** He put the career record page beside
the dashboard: the record said 13 races, 2 wins, 6 podiums; the dashboard said 0
wins, 0 podiums, no points, no position. Both were right — the tiles were THIS
SEASON and his season was two simulated absences with nothing raced. A dashboard
that appears to have forgotten a career is worse than one with a row too many, so
there are now two labelled rows, and the career row reads `resume()` — the same
source the record page and the booth use, so the three cannot disagree.

Points he has not scored are **0**, not a dash: a dash hides a number this code
knows. A position he does not hold stays a dash, because he genuinely is not in the
table.

---

## THE CAREER DASHBOARD — and the door that nearly got bricked up

His verdict on the career page, with a dashboard screenshot for reference:
*"theres literally not much happening there and its all just a bunch of words ...
Can we have a career dashboard instead, and then the Email icon lives insde the
dashboard instead and then the email icon truns into a Trophy icon instead, and
then we take out career in the settings tab?"*

He was right. Thirty grey rows of sentences, in which the four facts he actually
wanted — championship position, points, how far through the season, whether there
is post — were the same size and colour as "Nationality".

### WHAT THE DASHBOARD IS

`_rows_dash`, on page `dash`, top to bottom in the order he cares:

  1. **A header card** — the division's mark, his name, the division, his status,
     and a RING for season progress. "4/10" is a number to read; a ring is a
     thing to see.
  2. **Four tiles** — champ, points, wins, podiums.
  3. **A target bar** — the Formula One seat with the measured gap
     (`programme.bar_state`), or promotion against the rung's requirement. The
     season's POINT, drawn as a target rather than written as a sentence.
  4. **Inbox and News**, with counts, flagged when they hold something.
  5. **THIS WEEKEND** — the round, whether it counts, simulate. When the season
     has ended this whole section collapses to the one accent row that takes the
     next seat.
  6. **THE RECORD** — championship, results, career record, divisions.
  7. **Manage career** — everything touched once a season.

Four new row kinds carry it: `head`, `tiles`, `bar`, `band` (plus `gap`). The
renderer is a row-list with a `kind` dispatch, so a dashboard is new KINDS rather
than a new drawing path — the click hit-boxes, scrolling and page routing all
keep working untouched.

**THE FIRST VERSION WAS TALLER THAN THE SCREEN**, which defeats the entire point
of a dashboard. That is what `_rows_manage` exists for: nationality, undo,
delete, close, new and load are once-a-season things and they are one row deeper.

### THE TROPHY, AND WHY IT IS ALWAYS DRAWN

The envelope became a trophy and now opens the dashboard rather than the post.
Drawn with polygons like every other mark here — a 30px icon that needs a PNG is
a 30px icon that can go missing. Two passes: the first bowl was a half-ellipse
and came out lopsided with a handle reading as a loop, and the count badge sat on
top of the handles (it is bottom-right now, where a trophy is narrow).

**AND THEN THE BUG THAT MATTERED.** The envelope had always been hidden when no
career existed — correct, while the way to START one was Settings → Career → New
career. Removing the career from settings deleted that row and left the product
with **no route to a career at all**: no button, and a settings page that no
longer mentions careers. He hit it in minutes: *"now we have moved the career so
there is no way to activate the email icon"*.

The trophy is permanent, career or not, and the dashboard's no-career state is
new / load / bring one across from an older copy. **When you remove the last
route to a feature, the thing to check is not whether the feature still works —
it is whether anything on screen still leads to it.** `paneltest` now drives the
button's real drawing code with `season = None` and asserts it is clickable and
never hidden.

### THE MARKS NEEDED MEASURING, NOT A RULE

The header logo is the player's own file. The Formula 2 mark is light ink and
reads on the dark card; karting is dark maroon line-art and was nearly invisible.
A blanket light plate would have fixed karting and made the Formula One mark
vanish, since that one is largely dark on white too. So `_logo_ink` MEASURES the
mean luminance of the pixels that are actually opaque, and anything below 0.42
gets a plate: karting 0.09, F3 0.35, F4 0.39, F1 0.40 — plate; F2 0.43 — straight
on the card. Cached per path, because the header redraws every frame the
dashboard is open and answering means opening the file.

No art, no gap: the text starts where the mark would have ended.

---

## A RETIREMENT IS A RESULT — the tester's missing round two

Paul *"ran out of feul at the redbull ring kart race doing round 2 but the the
race result never recorded or anyhting"*.

**The only place a race result was ever written is the winner's flag.**
`_season_record` is called from `if s.finished and not self._said_win` — game
phase OVER — and from `_season_resettle`, which only exists after that. A driver
stopped on track with an empty tank, who then leaves the session because there is
nothing else to do when the car will not move, never reaches either. The
championship simply had no round two.

This is the THIRD distinct failure in the same family, and they all read the same
way: something that has to happen at the end of a session was hung off an event
that only fires when the session ends cleanly.

  1. Qualifying was banked below the on-air gate, which closes at phase OVER.
  2. A pending settle carried no round, so it landed on the next one.
  3. A result only existed if the LEADER finished while he watched.

`_season_retire` banks on `mFinishStatus` — HIS race, not the winner's — the
moment it is set. 1 is finished, 2 and 3 are retirements, and all three mean the
result exists.

**IT IS PROVISIONAL AND THAT IS THE POINT.** The rest of the field's
classification is their running order, because the race is still going, so the
flag path overwrites it with the real one — `record` replaces a round with the
same number. No result letter is sent on a provisional figure, because a letter
is frozen when it is sent. What this guarantees is that HIS result cannot be lost
by leaving a session there is no reason to stay in: **a provisional table is a
smaller wrongness than a missing race.**

### THE PROVISIONAL PLACE IS NOT HIS PLACE ON THE ROAD

The first version of this fix banked `me.place`, and that is a flattering lie: a
driver who retires while running ninth is not ninth, because every car still
circulating is going to finish ahead of him. Banked as ninth, and he leaves the
session — which is exactly what a driver with no fuel does — and he keeps ninth
AND the points for it. **The same error as the P4 banked for a tenth-place
finish, in a new place, introduced by the fix for the missing round.**

So a provisional classification puts the stopped cars at the back, ranked by the
distance they actually covered, and the cars behind them move up.

**ONLY WHEN THE FIELD IS ALREADY A CLEAN 1..N.** Two earlier attempts were wrong:

  * Renumbering the whole field unconditionally RENUMBERED A CLASS
    CHAMPIONSHIP. `field` is filtered by class, so its places are rF2's absolute
    ones with gaps (3, 7, 9, 12) — reindexing those turned fourth on the road
    into third, and `lifecycletest` §13 caught it.
  * Demoting only the retirement left a HOLE where he had been and placed him
    thirteenth of twelve.

When the places are not a clean set, nothing is touched and the road position
stands, which is what this has always done. At the FLAG none of it applies: rF2's
own classification is authoritative and already puts retirements where they
belong.

### RESTARTING IS THE SAME ROUND, AND NOTHING HAD TO BE ADDED FOR IT

His question, and it is the right one to ask of anything that banks early: *"what
about restarting? how does it tell the difference?"*

It does not have to, because **a round is keyed on the CIRCUIT, not on the
session.** `Season.match` returns the most recent round when its slug is the one
loaded, flagged `done: True`, and `record` replaces a round with the same number.
A restart therefore lands on the round it just banked and the new result
overwrites the old one — retirement replaced by finish, and one weekend stays one
round however many times it is restarted. `_new_session` already detects the
restart itself (green to pre-green, or the session clock going backwards), which
clears `_season_done` and `_season_retired` so the new run can bank at all.

**THE FLIP SIDE, and it is a real limitation:** in an open season, two CONSECUTIVE
rounds at the same circuit collide — the second one is read as a re-run of the
first and overwrites it. That is the same rule working as designed, and it is the
price of restart detection needing no cooperation from the player. If somebody
wants back-to-back rounds at one track it needs an explicit "this is a new round"
action rather than a cleverer guess.

### STATUS 1 IS NOT A RETIREMENT

`mFinishStatus`: 0 still going, **1 finished normally**, 2 and 3 the retirements.
The demotion above treated every non-zero value as stopped, so a driver who
crossed the line FIRST was banked as last of the field — a race win recorded as
twelfth, because the man who had finished was placed behind eleven cars still
circulating. Only 2 and 3 demote.

Three wrong versions of one twenty-line function, each caught by a test written
before it was believed: renumbering a class field, leaving a hole and a
thirteenth of twelve, and demoting the winner. **The lesson is not "be careful" —
it is that the provisional-classification problem has more cases than it looks
like, and every one of them is a wrong number in somebody's championship.**

### A BOUNDARY THIS DELIBERATELY DOES NOT CROSS

Quitting a race WITHOUT retiring — alt-F4, or back to the monitor while the car
is still healthy — still records nothing, because `mFinishStatus` is 0 and the
game's position on it is that he has not finished anything. That is a design
choice rather than an oversight: a player who abandons a session has not had a
result, and turning every exit into a DNF would bank one on somebody who left a
race he was treating as practice. If a rage-quit should cost a DNF, that is a new
rule and needs saying out loud before it is written.

### AND NOTHING NEEDS REPAIRING ON HIS MACHINE

Because the round was never recorded, round two is still the NEXT round. He
updates and races it again. There is no phantom to remove and no archive to
correct — the failure that lost the result is also what makes it recoverable by
simply driving it.

---

## THE COMMENTARY IS THE GAME — read this before building another arc beat

His steer, and it reorders the priorities of everything in this project:

> *"remremeber the commentary is the actual main gameplay, and most of what
> happens in the arc needs to happen or be said on track"*

The junior arc had been built letters-first. Every beat existed — the offer, the
signing, the call-up, the verdict, the chase — and almost all of it lived in the
inbox and the news feed, which are the RECORD. The booth, which is the GAME, did
not know the biggest move in the arc had happened: he asked whether the
commentators would mention going from F3 to F2 and the answer was no.

**So the test for a new arc beat is no longer "is it in the story". It is "can he
hear it while he is driving".**

What was added, at his instruction (he said yes to both questions: the booth MAY
say why the seat came free, and the standings chase DOES get on-air coverage):

  * `prog_callup_debut` — his first session in the car, once. It says he was in
    Formula 3 a fortnight ago, that the team made a change, and that he has had
    no test. NOBODY IS NAMED, the same restraint the letters keep.
  * `prog_callup_stake` — replaces `prog_stake` all season for a called-up
    driver, because a replacement is not auditioning for the same thing.
  * `prog_bar_chase` / `prog_bar_hold` — the chase, out loud, with the position,
    the gap, the rival and the rounds left in the sentence.
  * `prog_callup_last` — the final round with the seat on it.
  * `eng_callup_first` / `eng_callup_bar` — the engineer is the one voice who
    would mention a car the driver has never tested, and he restates the brief
    with the number in it. It sits ABOVE the status greeting, because "you are a
    riser, get up to speed" is the wrong thing to say to a man in a car he has
    not driven.

**`programme.bar_state()` IS THE ONLY MEASUREMENT.** The booth says it, the
engineer says it, and the news feed writes it up — three voices, one arithmetic,
because two implementations of "how far off third is he" would eventually
disagree in public. It returns None the moment any part cannot be read (he has
not scored yet, the table has no third place), and every caller treats that as
"say nothing".

### AND ONE LINE THAT WAS FLATLY WRONG FOR HIM

`div_f2` contained *"A driver who wins Formula 2 usually gets a chance. A driver
who finishes third usually does not, and everybody out there can do that
arithmetic."* His bar IS third — the booth would have told the viewer that what
his programme asked of him is not enough.

Reworded rather than gated, and the reason matters: **booth line gates are
era-based** (`year`, `disc`, `needs`) and know nothing about a career. A line that
cannot be made conditional has to be true in every case it can air.

---

## UPDATING WITHOUT LOSING A CAREER

Saves live in `careers/` beside the executable — `_DIR` is
`dirname(sys.executable)` when frozen — so the folder a player extracts into
decides whether he can still see his championship. Windows suggests a NEW folder
every time, and `FACTORtv-0.0.1-beta (2)` starts with an empty career screen while
the real one sits next door. Nothing is destroyed, and there is no way for him to
know that.

Neither archive contains save data of any kind (checked, not assumed: no
`careers/`, no `_settings.json`, no `_bag.json`), so **extracting over the
existing folder and replacing files is completely safe** and that is what the
user is telling his tester to do. `SETUP.md` now has an "Updating" section saying
exactly that, including the one rule that matters: do not delete the old folder
first.

Belt as well as braces, at his instruction: `season.orphan_careers()` looks one
directory up when this copy has no careers of its own and reports any it finds
beside it, and the career screen offers to bring them across.

  * IT OFFERS, IT NEVER ACTS. Importing somebody's championship without being
    asked is worse than one click, and the row names the folder it found so he
    can judge whether the answer is the right one.
  * IT NEVER OVERWRITES. A name already in use here is skipped.
  * NOTHING IS OFFERED once this copy has a career, so it cannot invite a player
    to merge two copies of the same season.
  * It is a HEURISTIC and the row reads like one. A player who extracted
    somewhere unrelated still has to copy the folder by hand, which `SETUP.md`
    tells him how to do.

**A broad `except` hid the first version completely.** `orphan_careers` used
`io.open` and `season.py` does not import `io`, so every call raised NameError
into `except Exception: _ORPHANS = []` and the feature silently found nothing. The
test caught it; reading the code did not. A bare `except Exception` around a whole
function body will swallow a typo as readily as a missing file.

### AND HIS SAVE WAS REPAIRED

Rolled back to the Formula 3 rung at his instruction, with round one rebuilt from
**rF2's own results XML** rather than from anything the overlay wrote — the
overlay is what got it wrong. `2026_08_19_20_01_04-84R1.xml`: Montreal GP, 13
starters, sixth over seven laps, finished normally. The seven letters about a
promotion that had not happened were withdrawn along with their `mail_seen`
entries, so they will arrive properly when the call-up actually comes at round
three. rF2 files him as "Your Name"; the career name is substituted on the way in.

---

## ONE RACE, TWO ROUNDS — the phantom weekend (LAW 0)

**He was right and the archive was wrong.** He said *"I never raced 2 F3 rounds? I
only did round 1 then was promoted on the second round"*, and his save recorded
`rounds: 2, points: 12` for Formula 3. The log:

    [2100.9s] RESULT  settled P6  status=1 laps=7      <- the race he drove
    [2342.1s] SESSION  | test | phase=garage | 0 cars  <- he left the race
              RESULT  settled P10 status=1 laps=6      <- nobody's race

`_season_settle` exists to correct a result while HIS race finishes after the
winner's flag — the fuel-out fix. It was a tuple of `(started, last_place)` and
carried **no round number**. Once round one was banked, the next arm matched the
next UNRACED round, so the leftover pending write landed on **round two** with
stale data. `record` replaces a round with the same number, which is why this
looked safe: it was never the same number.

Then `callup_due` counted two rounds done and promoted him out of a championship
he had raced once. The missing result letter I chased first was a symptom two
levels down from this.

The pending settle now carries the round it was created for and is dropped —
never redirected — if the armed round has changed or the session has no field.

**THIS IS LAW 0 AT ITS PLAINEST.** The store held a race that did not happen, and
everything downstream was honest about it: the standings, the archive, the
promotion, the letters. A fake cannot be allowed to falsify, and this one
falsified a championship and a career move.

### THE TEST SUITES WERE WRITING INTO HIS LOG

23 lines of zandvoort and "F1 Test 2025" sat in the middle of the log he sent —
my own suites, appending while he drove, because `_log` writes to
`_session_log.txt` whenever the file exists and the file persists between runs.
Evidence that has to be argued with before it can be read is worth much less than
it looks. `_LIVE_RUN` is a whitelist of the entry points that create the file —
`main.py`, `testrun.py`, the frozen exe — rather than a test-detector, because a
detector only catches the runners I thought of.

### AND A NOTE ON HOW THIS WAS FOUND

I diagnosed the missing letter, said the result itself was fine, and he
contradicted the premise. The save agreed with him. **Read the numbers in the
save against what the player says he did before explaining anything** — twelve
points across two rounds was visible in the first dump of that file, and I
explained the letter instead of asking why there were two rounds at all.

---

## WHAT THE 20:03 LOG SAID — the call-up, driven

The three fixes from the 18:26 log are all confirmed live in this one:
`ERA junior disc=formula year=2019 conf=high` on the F3 rung, `GRID captured 13
of 13` off the countdown with Lawson on pole where he actually started, and
`SEASON round 1 of Formula 3 at montreal — this session counts`. Then he took the
call-up and reported three things.

### THE CALL CAME AFTER TWO RACES

`callup_round` was `min(CALLUP_AFTER, max(1, total // 2))`, and half-distance on
the five-round season he chose is round **two** — so the entire Formula 3
campaign was one result and one telephone call. `CALLUP_MIN = 3` is his own
number: *"i think we need to comeplete 3 races of F3 first"*.

A season too short to hold three races AND a round to be called up from now gets
no call-up at all — he finishes F3 and is promoted the ordinary way, which is a
real outcome rather than a compressed version of this one.

### THE STORY WAS UNDERNEATH THE ADMIN

*"the emails for F2 came but ninde really specicief how and why i got the F2
seat, it was just boom you are now in F2"*.

The call-up letter did explain it, in detail. Then five ordinary
start-of-season letters arrived on top of it, and the newest and most prominent
thing in his inbox was **"Delighted to have you with us for the Formula 2
season"** followed by a **test day allocation** — while the call-up letter three
messages down says in as many words *"you get no test in it"*.

So the arrival letters now know how he arrived. `season_open_callup` registers a
mid-season substitution and states that points already awarded to the seat are
not transferable; `seat_callup` opens with "You are in this car because we took
somebody else out of it"; and no test day is allocated for a season entered by
call-up. **A letter contradicting another letter in the same inbox is worse than
either of them alone.**

### THE FEED WAS ONE TAB AWAY AND NOTHING SAID SO

*"also there was NO news reports about it ether"* — and `news_prog_callup` was in
his save, on the news feed, as the newest item in it. It was never missing; it
was on a tab he had no reason to open, while the inbox he WAS looking at
collected six letters about the same weekend. The tab-switch row now carries the
other feed's unread count and reads as hot when there is something in it.

**Diagnosis note for next time:** `inbox.messages()` sorts by timestamp, so
slicing it by index does NOT give arrival order. Reading it that way made three
Formula 3 letters look like they had arrived after the call-up. Tracing
`inbox._post` is the way to answer when something was written.

### AND ONE THING NOBODY REPORTED

The race that EARNS the call-up had no result sheet. `_programme_mail` ran above
the result loop, and taking the call-up archives the F3 season and replaces
`career.rounds` — so the most consequential weekend in the arc was the only one
he never got a letter about. The programme block now runs last, and that ordering
is load-bearing.

---

## WHAT THE 18:26 LOG SAID — six findings, five of them faults

He drove the F3 season and the arc worked live: `prog_offer` -> `prog_signed` ->
`news_prog_signed` are all in `careers/karting.json`, he is signed with the
Mercedes programme, and the booth used it on air. Overtakes fired hard all race,
including the traded-places escalation. Then the log answered six questions.

### THE GRID WAS THE GARAGE ORDER — reported twice

*"they once again thought the race leader started from the bottm and gained 12
places when he didn't"*.

`_track_grid` captured **the last sane order before the green**, and the garage
order is sane: places 1..N, nothing missing, nothing repeated. It is also
nothing whatever to do with where anybody starts. On a weekend where rF2
published nothing usable during the countdown, the garage snapshot was the one
that survived, and every `places_gained` in the race was measured against it.

Capture is now restricted to `s.kind == "race" and s.countdown` — FORMATION,
COUNTDOWN and GRIDWALK, the only phases in which a car's position IS its grid
slot. No snapshot from those means no grid, which every caller already handles.

**AND `win_charge` INVENTED THE SLOT WHEN IT WAS MISSING**: `started_place or
(1 + places_gained)`. That is the arithmetic that puts a front-row start at the
back of the field, in the one line that airs to the race winner. `_has_grid`
exists precisely to gate lines that mention the grid, and this pair — the charge
and the comeback — were the two that skipped it.

### SATURDAY WAS NEVER BANKED — the third instance of one mistake

He qualified P13 at Montreal; `quali_results` in the save was empty.
`_quali_bank` waits for `s.finished`, true only at game phase OVER — which is
the same moment rF2 drops `mInRealtime`, so `on_air` goes false and
`update_booth` returns above the call. The engineer's "last time out you put it
fourth" could never have worked, and Saturday's news had no data.

**THE RULE, because this is the third time:** anything that REMEMBERS belongs in
`_season_pre_arm` with the housekeeping, above the on-air gate. Anything that
SPEAKS belongs below it. A gate that closes at the end of the session cannot be
trusted to hold work that has to happen at the end of the session.

### THE F3 RUNG HAD NO ERA AT ALL

`ERA unknown_2019 disc=unknown conf=none`, raw class `SMMGF3_2019`. The pattern
was `\bf3\b`, and there is no word boundary between "SMMG" and "F3". `F2_2019`
matched all along, which is why one of the two looked right. The tokens are now
anchored on what FOLLOWS them — `f3(?![0-9a-z])` — which also fixed `FR35_2014`,
`FR2.0`, and **`F1_AM_2020`, the car the whole development year is built on**.

### A TWO-LINE POOL IS A REPEAT WAITING TO HAPPEN

One analyst line aired six times in a single qualifying session. The bag and the
recency window were both working: `analysis_era` had exactly TWO entries legal
for a modern single-seater, so it alternated. Karting — where every career
begins — had ONE, and GT3 had one. Twenty-one lines added across formula, kart,
GT, touring and stock, gated so they are era-true rather than merely new.

LAW 21 is about pools nothing can reach. This is its other half: **a pool the
filter narrows to one is not a pool**, and the only way to see it is to count
candidates per era rather than per file.

### THE LOG COULD NOT ANSWER ITS OWN FIRST QUESTION

A successful arm logged nothing, so "this is round one" and "the match failed
and I never told you" produced identical logs. It now says which round, or names
the circuit, class and year it could not match. The captured grid is logged once
per session for the same reason: this bug has now been reported twice with
nothing in the log either time to settle it.

250 of the log's 669 lines were `SANITY FAIL` noise — the P255 placeholder every
car reports in the garage, and the negative lap distance of a car sitting in its
box behind the timing line. Both checks now wait for green, and the lap-distance
check skips cars in the pits.

### AND ONE THING THAT WAS NOT A FAULT

Nothing was recorded from the race because he quit with it still running. There
was no result to bank.

---

## WHAT CHANGED ON 2026-08-19 (fourth session) — F3, THE CALL-UP, AND A FIXED FINALE

### THE JUNIOR PROGRAMME NOW STARTS IN F3, AND HE IS CALLED UP MID-SEASON

He asked to start the arc on the F3 rung, because the official F3 cars are
already in the game and the seat is believable. So `programme.py` offers on
`F3_KEY = "f3"` (`_on_rung`, `on_f3`) with `f3_team` names out of
`programmes.json`.

Then the plot twist. His first idea was a fatal crash opening the F2 seat, built
on the real 2019 Spa weekend — no driver named, no circuit named, an easter egg
of the year. I recommended against it and he agreed: the 2019 F2 roster this
project already ships includes a driver who was in that crash and survived it
badly, so a career-advancing "seat opens up" letter would be sitting next to his
name in our own standings. **The team drops its driver for form instead.**

  * `CALLUP_AFTER = 4` — no letter before the fourth F3 round.
  * `callup_round()`, `callup_due()`, `callup(tier_index=None, names=None)`.
  * The F3 season is archived `cut_short` with `of` set, so the record says
    four of ten rather than pretending it was a whole year.
  * `_start_rung(..., CALLUP_ROUNDS, how="callup")`, then `record_absence()` for
    `CALLUP_SIM = 2` rounds. He starts on **0 points** with the leader already
    scoring, and those two rounds are positions and points — never events.
  * The bar is **P3 in the standings**, not the title: `CALLUP_BAR = 3`, applied
    in `season_verdict` only when `_block(career).get("called")`.
  * The letter is `prog_won_callup`. `programmetest.py` §2b asserts no line in
    it congratulates him on a championship he did not win, and that "Prema" is
    named while Correa, Hubert, Latifi, Ghiotto, Aitken, Mazepin and Zhou are
    not.

### THE FEED NOW COVERS THE ARC, AND KNOWS WHAT HE ACTUALLY DID

He took one of the three seats and could not tell what he had taken — *"it
wasnt speicifc to what year, there are so many f3 years so which car am i
talking lol?"* The offer letter still described "the Formula 2 season" from when
the arc started a rung higher, and named no car. `programme.rung_facts()` now
answers three questions off his own installation: the championship, the car and
the mod it lives in (through `ladder.tier_cars`, the same source the eligible
letter uses) and the year, READ out of the F2 mod alias `f 2 2019` rather than
picked. No aliases with a year in them, no year in the letter.

Then the news, which was covering none of it. Six new pools:

  * `news_prog_signed` — choosing the academy, which he reported as missing.
  * `news_prog_callup` — the biggest move in the arc, previously unreported. It
    cannot go through `_arrival`, which fires on round one: a called-up season
    has rounds one and two already gone as absences. It also must not borrow
    `news_arrival_promoted`, which says the seat "was earned on results rather
    than granted" — true of a promotion, the exact opposite of this.
  * `news_prog_bar` / `news_prog_won` / `news_prog_late_win` — the verdict, and
    **which of the three it is matters more than anything else in this arc.**
    Clearing a podium bar is not winning a championship, winning one outright is,
    and a mid-season replacement who wins it anyway is a third thing that
    neither of the other two can describe without saying something false. All
    three are reachable, so all three are written.
  * `news_prog_missed` / `news_prog_dropped` — another go, and the end of it.
  * `news_prog_chase` / `news_prog_hold` — the months in between, which nothing
    was writing: he is not fighting for a title, so `_title_fight` stays silent.

**`signed()` RETURNS THE STATIC PROGRAMME DEFINITION.** It reads
`programmes.json` and knows nothing about this career, so
`signed(career)[1].get("called")` is None however called up he is — which is
exactly how the first draft of the verdict piece filed a mid-season replacement
as an outright champion, in the one place the user had explicitly warned about.
`programme.called_up(career)` exists so no caller has to know the difference.

Two faults were caught by reading a driven season back rather than by a test:
the hold piece said "first is precisely where he needs to finish" about a man
leading the championship (the requirement is third, and the sentence reused the
wrong slot), and the chase piece asserted the title was "gone" — a sum it had
not done and cannot do.

### THE LAST TWO GAPS — the winter, and the era

`news_prog_interest` covers the only moment in the arc that is about something
UNDECIDED: three programmes circling a driver who has not signed. It fires while
he is on the F3 rung with an offer open and no rounds raced, and it promises
nothing, because being talked about is not being signed.

`news_tour_open` covers the invitation, which was arriving as a single email
despite being the biggest reward in the product. It READS `tour_unlocked` and
grants nothing — `tour_grant` is called where the letter is sent, and two places
banking the same era is how a career ends up with one it cannot remember winning.
It also says plainly that the tour counts towards nothing, per the user's ruling.

One wording fault, again caught by reading the output rather than by a test: the
eras are named "The eighties", so "the {era} season" rendered as "the The
eighties season". The news slot strips the article; the invitation LETTER uses
the name standalone and keeps it.

### THE LAST SEASON OF EVERY DIVISION IS TEN ROUNDS, AND HE CANNOT CHOOSE

His words: the challenge gap before F1. `FINALE_ROUNDS = 10`,
`CALLUP_ROUNDS = 10`, `_is_finale(tier)`; forced in `_start_rung` and in
`create()` when `tier_index` is the last tier and this is not a historic tour.
Simulating those rounds is still allowed — the point is the length, not the
labour.

### THE LAST LETTER NOW OUTRANKS THE SCHEDULE — a real bug the fixed finale found

`personal.py` paces the sister's thread with a per-season budget (`allowed`) and
a spacing rule (`gap`), and below both of them sat the rule that exists to make
sure the thread always finishes: skip to the last beat when the season is
running out. **Below** them. So a finale that had already spent its letters
returned empty before it ever reached the rescue, the thread stalled three notes
short, and `_offer` — which waits for the thread — never opened. On a six-round
season the budget happened to be generous enough to hide it; the fixed ten-round
finale exposed it.

The condition is now computed as `lastgasp` directly under `last_season`, above
both gates, and both gates defer to it. Ordinary letters are texture; the last
one is the story, and it is allowed to break the cadence to arrive.

Two of the six `personaltest.py` failures were the fixture (a fixed
`for _ in range(5)` loop cannot find a window that moved), so those sections now
drive the season the way the game does — race, settle, repeat, until the offer is
on the table or the window closes. The rest were this bug.

---

## WHAT CHANGED ON 2026-08-19 (third session) — THE SAFETY CAR, THE PASS, AND THE FLAG

He drove it. `_session_log.txt` from 10:31 is the first log this project has had
since the pass work was written, and it answered four reports in one read —
including the discovery that **the headline feature of the product had been dead
since the day it was built.** Read the section under LAW 24 first.

### THE HISTORIC TOUR AS A REWARD — BUILT 2026-08-19

The user's idea: *"you know we have the historic races, can those races be
unlocked through an invite the player receives after completing their
championship, so if I beat 2021 then I get invited to compete in the 1988 F1
season as a reward as well."*

**IT FITS BECAUSE THE TOUR WAS ALREADY THE ODD ONE OUT.** `career_paths()`
excludes the historic path from the 100% — it has no final championship to win,
and counting it would put completion permanently out of reach. That is exactly
what makes it the right thing to give away: the one path with nothing to lose by
being optional.

The machinery is nearly there too. `advance("newpath")` is already granted only
to a driver who WON the final championship of a path, and it is already framed
in-world as the FIA granting permission to compete elsewhere. An invitation to
1988 is that mechanic with different words, delivered the way every other reward
in this career is — as a letter.

**HIS THREE ANSWERS, WHICH SETTLE THE DESIGN:**

1. **FORMULA ONE ONLY.** Winning the top championship of the single-seater path
   is what invites him. He was explicit: *"specific, so F1 to F1 historic."* A
   NASCAR champion being invited to a 1988 Grand Prix season is a stranger
   sentence than it first looks.
2. **ONE ERA PER CHAMPIONSHIP WON.** Not the whole tour at once — four rewards
   instead of one, and the eighties is the one to unlock first because a 2021
   champion being handed the Senna-Prost season is the best version of this.
3. **IT COUNTS FOR NOTHING.** A bonus, recorded normally but outside the 100%,
   exactly as the tour is today. The reward is the invitation and the racing.

**AS BUILT.** `Career.f1_titles()` counts wins of the TOP rung of the
single-seater path — from the archive plus the season he is standing in, exactly
as `title_count` does and for the same reason: on the afternoon he wins it,
nothing has been archived yet. `tour_state()` derives what is owed from that
count and WRITES NOTHING, so the menu and the paper can never disagree about
which eras are open.

**THE INVITATION IS WHERE THE ERA IS BANKED.** `tour_grant` is called by the
letter that announces it — `tour_invite`, three wordings from the FIA's Heritage
Commission — so an era he can race is an era he has a letter about, and there is
no way to unlock something silently. The same pattern `advance_dev` follows.

**`TOUR_ORDER` IS EIGHTIES, NINETIES, SEVENTIES, SIXTIES**, not the order in the
data file, which is chronological. Chronological is the right way to READ a tour
and the wrong way to give one away: a 2021 champion handed the Senna-Prost season
is the best version of this reward, and a reward that opens with its weakest item
is a worse one.

**A LOCKED ERA IS STILL LISTED**, with "win Formula One" beside it — the same
reasoning as the divisions view naming a rung he owns no car for. Knowing the
content exists is information; hiding it makes the game look smaller than it is.

**THE UNLOCKS TRAVEL INTO THE NEW CAREER FILE**, and this is the one place the
"a new career is a clean slate" rule is deliberately bent. It has to be: taking up
the invitation MEANS starting a career on the tour, so an invitation that did not
carry across would be unusable by construction. Only the eras already earned are
copied, and nothing else.

`laddertest.py` §18 holds all of it, including the two refusals that matter: a
NASCAR champion is not invited to 1988, and the tour is still outside
`career_paths()`, so **the 100% arithmetic is untouched** — which is what made
this safe to add this late.

### THE DEVELOPMENT YEAR IS DRIVEN NOW — the 2020 test programme

The user found F1 2020 by A&M on the workshop and asked what the year out was
for. The gap in the arc is exactly 2020 (F2 2019 -> year out -> F1 2021), and his
own design for filling it is better than the letters it replaces, because it is
what junior drivers actually do — private testing in last season's car:

> *"can we make it so that they HAVE to set up a practice session for it to be
> picked up properly ... SESSION TYPE: Practice, Car Class: Ferrari 2020 car
> (depending on the path they chose) ... if they just start a practice and all
> parameters are met then boom that will be a tick ... this way the practice
> isn't completed by ending the session, just by starting it, so they can choose
> how long they want to run for and which track also."*

**THE PARAMETERS ARE CHECKABLE ON ARRIVAL, and that is the whole reason it
works.** Session type, car and circuit are all known the moment he is on track,
so the overlay never has to judge whether he has tested ENOUGH — the programme
states its terms, he meets them, the tick lands. A lap threshold would have made
the overlay the referee of his own test day.

**IT IS THE TEAM'S CAR, AND THAT IS A REAL PARAMETER.** These A&M mods publish
the CONSTRUCTOR as the CarClass — his career store learned "McLaren" and
"Mercedes" from 2021 races — and `F1_AM_2020` ships one `.MAS` per team
(FERRARI, MERCEDES, REDBULL, ...), which is all three programmes covered.

| refused because | the badge says |
|---|---|
| it is a race or a qualifying session | `TEST — practice only` |
| the car is this year's | `TEST — 2020 car` |
| the car is somebody else's team | `TEST — Mercedes car` |
| the circuit has already been used | `TEST — a new circuit` |
| he is in the garage watching | `TEST — get on track` |
| nothing is wrong | `TEST — 1/3 outings` |

**A REASON, NEVER A BARE REFUSAL.** `test_check` returns why, and the mode badge
shows it — the lesson from the sim-round button that did nothing and said
nothing. A fourth badge state was the right home for it: a test day is not a
round and not off-career, and what he needs to know is whether this session
counts.

**STRICT WHERE IT CAN VERIFY, LENIENT WHERE IT CANNOT** — the same rule `match()`
follows for the seat. A class naming a DIFFERENT team is refused; a class naming
no team at all is unknown rather than wrong, so a mod that publishes one class
for the whole field cannot stop the year progressing.

**ONE OUTING PER CIRCUIT.** Three outings at three different tracks, the user's
call, and it is what stops the year being three sessions in ten minutes without
anybody deciding it should be.

**BOTH HALVES OPEN THE SEAT.** `_maybe_seat` requires the letters read AND the
outings served. Either alone can be walked straight through: five emails without
loading the car is not a development year, and three tests with no word from the
team is not a story. This REVERSED the old contract, and `programmetest.py` §5
was updated rather than worked around — a test encoding a decision the user has
since changed is a fossil.

**THE LETTER IS AN INSTRUCTION SHEET**, because the feature is unusable if he has
to guess what to load — and guessing what to load has gone wrong four times now.
`prog_test` carries the parameters as a block, with `{car}` filled from what the
GAME calls the mod (`modnames`), and `prog_test_run` reports each outing from the
laps and best lap the overlay watched. **A test has no result, so neither letter
quotes a position or a comparison against anybody.**

**AND IT INHERITS THE PRACTICE RULE FOR FREE.** A test outing IS a practice
session, so the booth is already silent for it and the engineer already runs it.
The tick therefore lives in the frame (`_test_watch`) rather than in the booth: it
must not sit behind a gate that is guaranteed to be shut, and it must not depend
on the commentary being switched on.

### THE RELEASE CARRIES THE TESTER'S NAME, NOT THE AUTHOR'S

`lines_data/mynames.json` is the list of names a career can be raced under, and it
exists because THE OVERLAY NEVER HOLDS THE KEYBOARD — the menu cannot take typed
input, so a name a player invented has to come from a file he edits.

Shipping the author's list means a tester picking a name out of somebody else's
career, so `tools_package.py` SUBSTITUTES it on the way into an archive
(`RELEASE_NAMES`) and the working copy is left alone. Substituted rather than
edited, because that file is used here every day and a build step must not disturb
it — and the verification compares the archive against the SUBSTITUTION rather
than against the file on disk, so "byte-identical" stays a real claim and the one
rewritten file is named in the build report.

**STILL OWED, AND THE USER HAS ASKED FOR IT: a way for a player to use his own
name without editing a file.** The constraint is real — the overlay is
click-through and never takes focus, so there is no text entry anywhere in it. The
options worth weighing when it is built:

* **rF2's own profile name.** The game knows who is driving, and the tracker
  already substitutes it for "Your Name" everywhere. Offering it in the picker
  costs nothing and needs no typing. The profile name lives under
  `UserData\player\`, and it was NOT at the top level of that folder on this
  machine — so where it can be read from is the first thing to establish.
* **An on-screen keyboard in the menu.** The panel machinery already handles
  clicks and pages, so a 30-key grid is a page like any other. Slow to type on,
  and the only option that needs nothing outside the overlay.
* **A first-run text file** with a clear prompt, which is what happens today —
  the difference would be telling him about it rather than expecting him to find
  it.

Whichever it is, the shipped list stays a list: a career raced under an invented
name gets no record and no history, only what the overlay watched, and that rule
is what keeps `drivers.json` honest.

### THE FIRST BUILD TO LEAVE THIS MACHINE — 0.0.1-beta

A play tester needs a copy, so: `git init`, `version.py`, `requirements.txt`,
`SETUP.md`, `tools_package.py`, tag `v0.0.1-beta`. 130 files tracked, 127 in the
zip, 1.1MB.

**THE MANIFEST IS EXPLICIT AND ANYTHING UNRECOGNISED IS REPORTED, NOT
INCLUDED.** A zip built with a wildcard from this folder ships the career store,
the settings, the shuffle bag, the learned mod names and 280MB of rendered
speech. `python tools_package.py --check` lists what would go in, what is being
left out, and — loudly — anything the manifest has never heard of, because a new
file is either an asset that needs shipping or private data that must not be, and
only a person can say which.

**WHAT IS DELIBERATELY ABSENT**: `stings/` and `_voice_cache/` (rebuilt on first
run), all career and settings state, `_modnames.json` (correct here and wrong
everywhere else), the handover and this file (they belong in git, not in a
tester's zip), and **the division art** — those files include marks belonging to
the FIA and others, and `newsart` already treats a missing folder as a supported
state.

**THE TESTER'S FIRST DEPENDENCY IS NOT PYTHON, IT IS THE PLUGIN.** rF2 publishes
nothing without The Iron Wolf's shared-memory plugin, so SETUP.md opens with it
and `verify_plugin.py` is the check. The second is an internet connection: same
voice names give identical output, and the failure mode is a silent fall back to
SAPI, which is what "the voices sound robotic" actually means.

**STILL OWED BY THE USER**: a licence for the repository, whether it is public or
private, and whether any art ships at all. All three are his to decide and none
of them can be inferred. The commit identity is set REPO-LOCAL only.

### PRACTICE IS THE ENGINEER'S SESSION, AND THE PROMPT COMES IN THE GARAGE

Two asks, one afternoon, and both are structural rather than content.

**NOBODY BROADCASTS A PRACTICE SESSION.** Asked for directly: *"if it is a
practice session then disable all commentary, lets just have the race engineer
and driver, but for quali and race sessions then we must have commentary."* He is
right, and it is the same reasoning that keeps the inbox out of the car: there is
no crowd at a practice session, no result, and no timing screen worth showing, so
a booth narrating one is the first thing in this product that does not happen in
real life. `BOOTH_SILENT = ("practice", "test")` returns out of `update_booth`
before anything can speak. **Nothing had to be written for the other half** —
`_quali_radio` already covers practice, so deleting a caller turned the session
into the pit wall. `_quali_bank` was already gated to `kind == "quali"`, so no
qualifying result depended on that path.

It also means the 2020 test outings, when they are built, inherit the right
behaviour for free: a test outing IS a practice session.

**THE CAREER PROMPT WAS LATE, AND THE ON-AIR GATE WAS WHY.** Asked for: *"can we
not have the prompt come up when we are in the pit screen before the event
starts, as I will at least have time to accept and read it properly."*

`s.on_air` is `mInRealtime AND phase > GARAGE`. It is the rule that stops the
intro airing over a loading screen and it is RIGHT ABOUT SPEAKING — but the round
was being matched underneath it, so the overlay did not know which round the
session was until he was already on track, and the Y/N card appeared as the
lights went out. The one moment he cannot read anything.

`_season_pre_arm` now runs ABOVE the gate and does the three things that say
nothing: notice a new session or a restart, match the round, and remember the
green/elapsed state the restart test needs. **Arming is free** (LAW 3: context is
free, RECORDING is confirmed) and everything it needs — circuit, class, year —
rF2 publishes while he sits in the garage. Race sessions only, here; qualifying
arms on the normal path where it always did, because a quali session has nothing
to confirm.

A side effect worth having: a restart is now noticed in the garage rather than
once the car is on track, which is where the last race's state should have been
cleared all along.

### ...AND THAT FIX SHIPPED BROKEN FOR ONE SESSION. `promptshot.py`

The user, after driving it: *"I should've just left the previous race check Y/N
system cause it messed up how you accept races — this time when I loaded into the
garage I didn't get the prompt, nothing."* His screenshot showed the badge reading
**OFF-CAREER / "Formula 4 paused"** on round one of a Formula 4 season.

**MOVING THE ARMING EARLIER PUT IT AHEAD OF THE DATA IT NEEDS.** `_season_arm`
gives up silently when the circuit is not resolved, and the flag was set FIRST:

```python
self._season_armed = True     # <- before
self._season_arm(s)           # <- ...which then could not decide
```

rF2 publishes the circuit and the CarClass a beat after the session appears, and
in the garage that gap is seconds. So "I cannot tell yet" was frozen into "this is
not a round" for the whole race — no prompt, nothing recorded, and a badge
confidently reporting a paused career.

**A LOOKUP KEYED ON STATE THAT DOES NOT EXIST YET**, for the fourth time in this
project. `_can_arm()` now requires the three things `Career.match` actually reads
— a circuit the overlay can name, the player, and a non-empty car class — and
otherwise tries again next tick. **The green flag is the deadline**: whatever is
known by then is the answer, because never deciding is worse than deciding wrongly
(nothing downstream would ever record or refuse).

**AND THE ASSERTION TEST PASSED THROUGHOUT**, because it called `season_prompt()`
directly on a hand-built session — which is the half that was never broken. The
user's response is the lesson, and he was right to ask for it:

> *"you should do a test, like a fake preview test if someone loads into a garage
> does the prompt even show to begin with"*

`promptshot.py` drives the REAL `update_booth` over a garage session — tick one
with nothing published, tick two with the circuit and class arriving — then draws
with the real `draw_career_prompt` and screenshots it. **It fails on an empty
frame**, measured as ink spread, so "the card is on screen" is a fact rather than
an inference. A picture cannot be fooled by a shim three layers below the bug.

Add it to the preview tools list: it belongs beside `menushot.py` and
`dashshot.py`, and it is the only one that asserts rather than just showing.

### A CIRCUIT THE OVERLAY HAS NEVER HEARD OF IS STILL A ROUND

Reported after the arming fix: *"everytime I press drive now it says career
paused."* His Formula 4 season had reached **"ANA - INDY GRAND PRIX"**, which
nothing in `tracks.json` recognises.

**`_season_arm` REFUSED UNLESS `circuit.known`, AND THAT IS THE WRONG QUESTION
ASKED OF THE WRONG FIELD.** `known` means "we hold facts about this place" — it
gates the trivia, the corner names and the character lines, correctly. It has
nothing to do with whether a race counts. So an open season — whose entire
definition is *N races, ANY circuit, one car class* — silently stopped counting at
the first unrecognised track, with no prompt and an OFF-CAREER badge at every
attempt.

His own question cut to it: *"doesn't the overlay recognize events by car?"* It
does. **THE CAR IDENTIFIES THE CHAMPIONSHIP; THE CIRCUIT IS ONLY WHAT THE ROUND IS
FILED UNDER.**

`Track.key` is new and always usable: the canonical slug where there is one, a
normalised form of the raw name where there is not. `slug` and `known` are
untouched, so the booth still says nothing about a place it cannot recognise —
which is the distinction that was collapsed:

| | means | gates |
|---|---|---|
| `known` | we hold facts about this place | trivia, corners, character |
| `slug` | the canonical entry, or None | the facts table |
| `key` | an identity, always | rounds, results, his own history there |

**IT APPLIES TO EVERY CAREER SHAPE, AND THEY STILL DIFFER CORRECTLY.** A ladder
career IS an open season with a path attached, so a campaign round now counts
anywhere. A FIXED-CALENDAR season still has to recognise the track, because there
the round IS the Brazilian Grand Prix at Interlagos — `Career.match` decides that,
and an unknown circuit legitimately matches nothing. What was wrong was the booth
refusing to ask.

`career.visits()` and the history lookup take the key too, so "we were here in
round two as well" works at an unknown circuit — a claim about HIS results there,
never about the place.

**AND THE CIRCUIT IS READ DEFENSIVELY** (`getattr(circuit, "key", "")`). A missing
attribute on a circuit must never be why the booth stops working, and `Track` is
not the only thing that has ever been handed to that method — two test fixtures
had their own.

### ...AND THE FRAME NEVER REACHED IT. THE THIRD CAUSE OF ONE SYMPTOM

The user, after the second fix: *"the prompt only comes up after I press drive,
and it's the same basically as before, which tells me the overlay doesn't pick it
up until you're out on track."* He was right for the third time, and he had
correctly identified the layer each time.

**`draw_status` CLAIMS THE WHOLE TICK WHENEVER THE SESSION IS NOT LIVE.** Its
not-live branch draws the menu furniture and returns — so in the garage
`update_booth` was never CALLED AT ALL, and every clever thing done inside it was
irrelevant. Moving the arming above the on-air gate fixed nothing, because the
gate above THAT was the frame itself.

```python
if self.draw_status(s, plugin):
    self.draw_menu_button() ... self.draw_settings()
    return                     # <- the career prompt is thirty lines below here
```

That branch now also runs `update_booth`, `_test_watch` and
`draw_career_prompt`. Calling the booth there is safe by construction: it returns
at its own on-air gate before anything can be SPOKEN, which is what that gate has
always been for — so the cost is one arming decision and the benefit is a prompt
in the pit screen.

**THE SAME SYMPTOM HAD THREE INDEPENDENT CAUSES**, stacked, and each fix exposed
the next:

| | cause | symptom |
|---|---|---|
| 1 | the round was matched under the on-air gate | prompt appeared as the lights went out |
| 2 | the armed flag was set before the data arrived | no prompt at all; OFF-CAREER on round one |
| 3 | the frame returned before reaching the card | prompt only after pressing Drive |

**AND THE PREVIEW WAS COMPLICIT IN THE THIRD.** `promptshot.py` called
`draw_career_prompt` directly, which passed while the game showed nothing —
exactly the failure it was written to prevent, one layer up. It now drives the
frame's not-live branch, **read out of `factor_tv.py`'s own source** rather than
copied by hand, and asserts that the `career` panel is among the ones drawn. It
was checked by deleting the call and confirming the preview fails: a test that
cannot fail is not a test.

One trap while writing that: splitting the source on `"return"` cut the branch
short inside a COMMENT containing "returns", found no calls, and reported a
working frame as broken. Split on the statement, not the word.

### THE FOURTH CAUSE: THE PROMPT WAS WAITING FOR A CAR CLASS

*"Nah still same story — I will start quali, then when I say next session I will
be in the pit screen and nothing happens until I press drive, and then only the
prompt will show up."*

Three fixes in, and he was still right. The remaining cause is the one that could
not be fixed by running things earlier: **`season_prompt` refused until the round
had been MATCHED, and matching needs the car class — which rF2 does not reliably
publish, or even a player, until the car is on track.** So no amount of arming
earlier could produce a card in the pit screen; the input was not there to arm
with.

**SO THE QUESTION CHANGED, AND IT IS A BETTER QUESTION.** The card asks *may this
count*, and that is answerable before the session has been identified:

* the prompt now offers `career.next_round()` when nothing has been matched yet;
* an answer is remembered as an INTENTION (`_season_pref`) and applied by
  `_season_arm` when there is finally something to apply it to — a "no" given in
  the pit screen was previously accepted and silently dropped, which is worse
  than not asking;
* if the class turns out to belong to another division, `_season_round` stays
  None and NOTHING RECORDS. The answer simply had nothing to apply to, which is
  exactly the same outcome as today.

Asking early is therefore free, and it is the only version of this a driver can
read in time.

**AND THE LOG NOW NAMES THE MISSING INPUT.** Three fixes were spent guessing
which field rF2 had withheld:

```
SEASON   cannot decide the round yet — player=yes cars=12 circuit=NO class='F1 Test 2025'
```

That line would have ended this in one run instead of four. When a decision is
deferred on data somebody else publishes, LOG WHICH FIELD — the alternative is
what happened here.

### THE IN-SESSION PROMPT IS GONE. THE DECISION LIVES IN THE MENU

Four attempts, four different causes, one symptom. The user, correctly, stopped
asking for a fix and asked the right question instead: *"is there a better way to
do this or is how it's set up now the only viable way?"*

**THE FOURTH CAUSE, FOR THE RECORD, AND IT IS THE BEST ARGUMENT FOR REMOVING THE
FEATURE.** `s.started` is `mGamePhase >= GREEN`, and rF2 publishes a phase OUTSIDE
0..8 in the pit screen after moving to the next session — his log said `phase=?`
in exactly the place the card was missing. An unrecognised phase therefore counted
as "the race has begun", and the prompt refuses once a race is under way. Pressing
Drive moved the phase to `gridwalk` and the card appeared. `_PHASE_NAMES` now
prints the NUMBER for an unknown phase, because "phase=?" withheld the one fact
that would have identified this on the first read.

**EVERY ONE OF THE FOUR WAS THE SAME DESIGN FAULT.** The decision was being asked
for in a window the GAME controls, out of data the game publishes when it feels
like it, while the driver is about to drive. No amount of moving it earlier could
fix that, and the log proves the pattern: matched under the on-air gate, armed
before the data arrived, never reached by the frame, refused on a phase nobody
recognises.

**SO IT IS A ROW ON THE CAREER PAGE**, `Round N counts`, and the user's shape for
it: *"a choice that needs clicking before a round like how we did the F4 seat
acceptance ... to switch it off it must be done by either turning that off or
closing the career."*

* `Career.round_counts(n)` / `set_round_counts(n, yes)` — **in the career file**,
  because session state is wiped when rF2 moves from qualifying to the race, which
  is the window every previous attempt died in.
* **ONLY THE EXCEPTIONS ARE STORED** (`rounds_off`). Default is to count, per the
  law that a race which quietly failed to count is unrecoverable while one that
  counted wrongly is one click from undone — and an old career file needs no
  migration.
* **A SWITCHED-OFF ROUND IS OFF-CAREER, NOT MERELY UNRECORDED.** His framing, and
  he is right: *"if I want to do a random race I just switch it off and the
  commentary system and race engineer will know."* `_season_arm` drops the match
  entirely, so the booth says nothing about the championship, the engineer loses
  his round talk, no qualifying result is banked, and the badge reads OFF-CAREER.
  A booth calling something "round two of the Formula 4 season" while nothing
  records is contradicting the standings screen.
* Switching it in the menu clears `_season_armed`, so a change made while sitting
  in the garage takes effect immediately rather than at the next session change.

**WHAT WENT WITH IT**: `season_prompt`, `season_answer`, `draw_career_prompt`, the
Ctrl+Shift+Y/N hotkeys, `_season_asked`, `_season_pref` and `promptshot.py`. Dead
code around a removed feature is a LAW 21 hazard; there is nothing left of it.

**WHICH SESSIONS THIS AFFECTS**, since it was asked directly:

| session | writes | governed by the switch |
|---|---|---|
| practice | nothing at all | n/a |
| qualifying | grid slot and the team-mate comparison, no points | it is context — but a switched-off round banks no quali result either, because there is no round |
| race | the championship result, at the chequered flag only | yes |

### EVERY OVERTAKE CALL IN THE PRODUCT WAS DEAD — one expression

Reported as *"the overtaking priority system isn't working at all"*. He drove
from thirteenth to the LEAD in a seven-lap race with thirteen cars and heard
nothing; the log holds no pass sting of any kind across a whole session.

```python
gained = p.place - newp      # last tick's RAW place vs this tick's CONFIRMED
```

`confirmed_places` de-bounces a position over `PLACE_CONFIRM_S` (0.35s) so a
flicker at a timing line cannot become a phantom pass (LAW 12). A tick is 50ms,
so the confirmed place lags the raw one by about seven ticks — and the two
therefore differ by exactly one only when a pass is seven ticks old, which is a
thing the raw snapshot forgot six ticks ago. **Every real pass produced
`gained == 0` on the tick it happened, `-1` on the next, and `0` for ever
after.** The edge never existed.

`_Snap` carries `conf` now, `_detect` settles the confirmed map into `_conf_now`
once per tick, `_snapshot` reads it, and both sides of the subtraction come out
of the same filter. `_who_was` had the same fault in its second half — the victim
was looked up in a different instant from the pass, and a pass with no victim is
discarded, so that alone would have silenced everything a second time.

**AND EVERY SUITE FAKED THE FILTER AWAY.** `FakeTracker.confirmed_places`
returns the raw places, in `passtest.py` and `boothtest.py` both. Twenty-five
green suites, and not one of them had ever run a pass through the thing that
decides whether a pass exists. `passtest.py` §11 uses the REAL
`confirmed_places` on a bare tracker with session time advancing, and asserts a
pass is detected exactly once, that a sub-threshold flicker is still detected
never, and that the call names both men.

### LAW 24 — NEVER COMPARE A FILTERED SIGNAL WITH AN UNFILTERED ONE

Both sides of a delta must come from the same filter, or the edge lands in the
gap between them and no code is obviously wrong. The de-bounce was right, the
snapshot was right, and the subtraction between them was silent, permanent and
invisible to every test.

This is the same shape as LAW 0 and it is worth stating separately: LAW 0 is
about a fake that cannot falsify what it replaces, and this is about two real
signals that cannot legally be subtracted. When you add a filter — a hysteresis,
a confirmation, a hold — grep for every comparison against the value it filters
and convert them all in the same commit.

### THE SAFETY CAR — 6m22s of it, and one wrong line

Reported as *"a safety car deployed towards the end of the race and there was 0
commentary involved"* and *"when the safety car ended it was on the last lap of
the race and that sort of drama needs to be commentated on"*. He is right twice.

**THE DATA WAS ALL THERE AND ONE BOOLEAN OF IT WAS BEING READ.** His log:

```
[1610.7s] SAY   PLAY  Waved yellows. No overtaking.      <- and that was all
[1610.7s] FLAGS yellow_state=1  fcy=True                 deployed
[1654.5s] FLAGS yellow_state=2                           pit lane CLOSED
[1737.9s] FLAGS yellow_state=3                           open, lead lap
[1857.1s] FLAGS yellow_state=4                           pit lane OPEN
[1874.5s] FLAGS yellow_state=5                           safety car in this lap
[1992.1s] FLAGS yellow_state=6  fcy=False                GREEN — on lap 6 of 7
```

`mYellowFlagState` is a six-state machine and it is a broadcast running order.
The overlay read `full_course_yellow` as a bool, called the generic `yellow`
pool — *"waved yellows"*, which is not what a full course yellow is — and threw
the rest away.

`_safety_call` is edge-triggered on the STATE (LAW 1, which the old
level-triggered yellow already taught this file once): deployed with the
analyst's reply in the same breath, pit lane shut, pit lane open, safety car in
this lap, green. `lines_data/booth_safety.json` is 11 pools / 44 lines, era-
neutral by construction — a bunched field behind a pace car is the same event in
1966 and 2025, so Brett delivers all of it.

**THE RESTART ON THE LAST LAP IS ITS OWN EVENT**, priority 96, above everything
except the win. One lap, a bunched field, no time to plan anything — it is not
an ordinary restart with a different lap count, and `sc_green_last` exists
because what he got was the most dramatic thing that can happen to a race and it
went uncalled.

**AND THE SIX MINUTES OF SILENCE WERE STRUCTURAL, NOT A CONTENT GAP.** `_filler`
opens `if not s.green: return out` — so under a full course yellow the entire
colour tail is switched off, at exactly the moment a real broadcast talks most.
The gate is right about RACING (no battles, no passes, nobody is racing) and was
wrong about everything else. Under a safety car it now offers the bunched field,
the wait once it has run past `SC_LONG`, and the standings — the order being
what the restart is about to decide. Nothing from `_flow_filler`: a gap behind a
safety car is a bus queue.

**NOTHING IN THIS SET CLAIMS TO KNOW WHY.** The overlay knows the field has been
neutralised, not whether somebody is in the wall. Causes belong to the incident
detector, which has its own sting; this owns the consequence.

### THE FLAG IS THE WINNER'S, NOT HIS — a wrong result in the championship

Reported as *"I managed to take the lead but then I also ran out of fuel before
the flag and then the wrong race result was recorded as I only finished 10th"*.
The log, twelve seconds apart:

```
[2097.6s] PLAYER  Dante Kandasamy  P4         <- banked into the championship
[2109.4s] STATE   lap 7/7  P10  fuel=0.0      <- where he actually finished
```

`_season_record` fired on `s.finished` and read `me.place`. **`s.finished` means
the WINNER crossed the line.** A car coasting on an empty tank has not finished
anything, and its position on the road at that instant is not a result — rF2's
own result file for that race says P10, 7 laps, Finished Normally.

**THIS IS LAW 2'S OTHER HALF.** That law asks whether the RACE was completed;
this asks whether HE completed it. `mFinishStatus` is the game's own answer and
was already being read into `Car.finish_status`.

* The result is still banked at the flag, so the wrap's standings include the
  race — but it is **provisional** while his own race is running, and
  `_season_resettle` follows him down the order, re-banking on CHANGE (`record`
  replaces a round with the same number, so it is a correction and not a second
  result). It stops when the game classifies him, or after
  `RESULT_SETTLE_MAX`, and logs `RESULT` when it settles.
* **NO POST UNTIL THE RESULT IS FINAL.** A result sheet quotes his finishing
  position and is frozen when sent, so a letter written off a provisional place
  would sit in the archive congratulating him on a fourth place he did not get.
  `_season_record(final=False)` writes the store and holds the post.
* **THE ENGINEER WAITED TOO.** `eng_finish_good` read `me.place` at the flag and
  said *"P4 at the end. Good, honest race, Dante"* to a man who was about to be
  classified tenth. It now waits for his finish status, capped by
  `ENG_FINISH_WAIT` so a driver who parks in the garage is still signed off.

**HIS EXISTING ROUND WAS REPAIRED FROM THE RESULT FILE** — P4 to P10, with the
full 13-car classification, so the standings are right for everybody in the
race and not just for him. Backup in the session scratchpad. `dnf` stayed false,
because rF2 says he finished.

**STILL OPEN, AND WORTH DOING**: reconciling every stored round against the
result XML when it appears. `career.parse_result` already reads those files and
they are the definitive classification — it would make the store self-correcting
even if the overlay is closed before the player finishes. The live path is fixed;
this would be the belt to its braces.

## WHAT CHANGED ON 2026-08-19 (second half) — THE END OF A SEASON, AND THE MARK

Four things the user reported after simulating a karting season to its end and
taking the Formula 4 seat. Every one was something he SAW, and two were bugs no
suite could have caught, because no suite has to FIND something on a menu.

### THE DECISION THAT ENDS A SEASON WAS HIDDEN

Reported as: *"to progress forward I have to go back to the career screen
through the settings tab ... I almost didn't even see the option to take the F4
seat, it's virtually hidden, there should be a visual tell."*

**A CAMPAIGN THAT CANNOT CONTINUE WITHOUT HIM HAS TO SAY SO.** Everything else
in this product happens by driving; the end of a season is the one moment that
needs him to come and choose something, and it was a grey row nine down a page
two menus in, reading "End of season".

`PanelsMixin._ladder_waiting()` is the single answer and every surface reads it,
so they can never disagree about whether something is waiting:

| where | what it does |
|---|---|
| the **mode badge**, on screen | **SEASON OVER** / "seat waiting", in `TH.good` |
| the **inbox page** | a `hot` row above the letters: *"Take the Formula 4 seat"* |
| the **career page** | the same row, named the same way |
| the **settings row** | Career, marked, noted "season over" |

* **IT NAMES THE SEAT.** `_waiting_label()` returns "Take the Formula 4 seat",
  never "a decision is waiting" — a tell that does not say what it is about is a
  puzzle. Four states: the seat earned, an arc won (choose a new path), the top
  division, and the cut missed.
* **`evaluate()` WRITES NOTHING**, which is the property that makes this safe to
  ask on every frame — the same one the rung readout already relies on. It sits
  behind a `try` for the reason LAW 22 exists: the caller here is the DRAWING
  code, and a raising source must never be why the overlay stops painting.
* **A `hot` ROW IS CHROME, AND CHROME MAY SHOUT.** Accent plate, accent note, a
  bar down its left. **No MESSAGE may ever have it**: the inbox list stays a
  uniform run of subject lines, because that is the mechanism the story's ending
  depends on. `paneltest.py` asserts the decision row carries no message id and
  that no letter on that page is flagged.
* Back from the end-of-season page returns to whichever page he came from.

**AND THE MODE BADGE HAD A DEAD BRANCH.** `CAMPAIGN` was written INSIDE the
off-career branch, below an unconditional reassignment — so a ladder career
racing a legitimate round was labelled "SEASON", and **OFF-CAREER, the state the
badge exists to warn about, could never be shown at all.** Two states, two
branches. A branch that overwrites its own answer is not a branch, and this one
had been shipping since the badge was written.

### THE DIVISION'S MARK WAS CUT OFF, AND RINGED IN BLACK

Two separate faults in one graphic, both photographed by the user.

**THE WINDOW RECT IS NOT THE PICTURE.** `find_game_window` returned
`GetWindowRect`, which includes the title bar and — on Windows 10/11 — invisible
resize borders that sit OUTSIDE the visible frame. A 1920-wide windowed rF2 on a
1920-wide screen therefore reports a rect several pixels wider than the display,
starting at a negative x, so every panel hugging the RIGHT edge is placed past
the edge of the screen and clipped by it. `client_rect()` reads `GetClientRect` +
`ClientToScreen` instead, and `_lock_to_game` intersects the result with the
screen so a window dragged half off it cannot hide a panel either. **In
borderless and fullscreen the two rects are identical, which is exactly why this
survived so long** — that is the mode everything was built against.

**THE BLACK RING WAS ALPHA BLENDING AGAINST A CHROMA KEY.**
`-transparentcolor` is BINARY: a pixel is either exactly `#010102` and the game
shows through, or it is opaque. A LANCZOS resize leaves every edge pixel partly
transparent, and blending those onto a near-black ground produced a fringe the
key could not remove — 1,488 such pixels on the Formula 4 mark, worst of all
over bright scenery. The edge is now KEYED rather than blended
(`LOGO_ALPHA_CUT` = 128): above the cut a pixel keeps its own colour, below it
the ground shows through. Aliased edges are the price of a binary key and they
are invisible next to a halo. **A real ground still takes the blend** — on a
letterhead or a menu row the soft edge is correct, and it is what keeps a 22px
mark legible.

**AND THE LOGO CACHE HAD BEEN POISONING ITSELF.** `_logo_photo` built its cache
key, then reused the name `key` for the chroma RGB tuple — so every chroma mark
was stored under the wrong key and **re-opened, re-cropped, re-resized and
re-walked pixel by pixel on every frame**, twenty times a second, for a picture
identical to the one before it. This is LAW 9 one scope down: a name collision
inside a function, with no shadowing warning of any kind.

### THE PAPER SAID NOTHING BEFORE THE LAST RACE

Asked for: *"there wasn't a News report before the last race of the season to
say something like 'This season's last race is upon us'"*.

**EVERY OTHER PIECE IN THAT FEED REPORTS SOMETHING THAT HAS HAPPENED**, so a
season with no title fight to write about reached its finale in silence.
`news._finale` fires when the PENULTIMATE round is banked — there is no calendar
in this product, so nothing knows a race is coming until the one before it is in
the store, and "before the last race" can only mean "the afternoon the
second-to-last one finished". That is when a paper would write it anyway.

* **THE ARITHMETIC PIECE WINS IF IT FIRED.** `news_title_maths` and its two
  siblings are this same preview with better information in them — what HE needs
  — and two articles about one afternoon is the repetition pass all over again.
  It defers by asking the store whether that id was posted, rather than by
  re-deriving the condition and eventually disagreeing with it.
* **THREE FORMS, AND WHICH ONE IS TRUE IS A FACT.** `news_finale_title` (the
  title can still change hands, with the contenders COUNTED from the points still
  on the table — LAW 17), `news_finale_decided` (it cannot; a paper writing "it
  all comes down to Sunday" about a settled championship is the one thing this
  feed may never do), and `news_finale` for a table that cannot support either
  claim. Three wordings each.
* **IT ROTATES ON THE SEASON, NOT THE ROUND.** `_post` defaults the wording to
  the round number, and this piece always fires on the same round of every
  season — so a ten-season career read the identical article ten times. The same
  trap the trivia index and the retrospective's subject line both fell into: **a
  rotation keyed on something that does not vary is not a rotation.** Found by
  reading `_career_preview.txt`, not by a test.

### JOINING A DIVISION ONLY REACHED THE PAPER AFTER HE HAD RACED

Reported as: *"when I join a new division I should see a report about it too."*
The piece existed with five wordings and could not reach him: `news.refresh`
returned empty for a season with no rounds, and the arrival was generated inside
the per-round loop. So the paper noticed the new man only AFTER his first race,
which is a week late for "there is a new face on the grid".

**A LOOKUP KEYED ON STATE THAT DOES NOT EXIST YET** — the same shape as
`simulate_round` reading a class the first race fills in, `installed_mods()`
caching an empty list, and `status()` counting only archived seasons. The arrival
is keyed on the RUNG, which exists the moment he is on it, so it is generated
once, above the loop. **Ask what the key is filled in BY, and whether that has
happened yet.**

It applies to his live career: a `news_arrival_promoted` piece — *"Promotion
confirmed: Dante Kandasamy to Formula 4"* — lands on the next menu draw.

### THE GAME CAN BE ASKED WHAT IT CALLS A CAR — `modnames.py`

Reported for the fourth time: *"the email says Tatuus F4 2018 but there is a
bunch of different F4 cars and none of them is named that."* The game lists
**Tatuus_F4-T014**.

**THIS HANDOVER SAID THIS WAS IMPOSSIBLE, AND IT WAS WRONG.** The claim — in
`ladder.tier_cars`, in the rF2 DATA QUIRKS table and in OPEN QUESTIONS as a
thing "still owed by the user" — was that a mod's real names can only ever come
from him or from a result file, because vehicle definitions live in `.mas`
archives. The archives really are unreadable: `Tatuus_F4_2018\1.14\car.mas`
starts `66 31 05 44` and carries no plaintext file table at all, so it is
encrypted rather than merely compressed. Its `.mft` manifest repeats the folder
name and nothing else.

**BUT THE rF2 UI IS AN ELECTRON APP, AND IT CACHES ITS OWN CONTENT LIST AS
PLAIN JSON.** In `UserData\player\LocalStorage\Cache`:

```json
"fullPathTree":"Karts, Kart Junior",
"vehFile":"D:\\...\\Installed\\Vehicles\\Kart_cup_2014\\1.02\\01K.VEH",
"engine":"...","manufacturer":"..."
```

`vehFile` names the FOLDER and `fullPathTree` is the menu path the UI navigates
by. **93 of his 94 installed folders resolve**, including every case that has
bitten this project:

| folder | what the letter used to say | what the game calls it |
|---|---|---|
| `Tatuus_F4_2018` | Tatuus F4 2018 | **Tatuus > Tatuus_F4-T014** |
| `Kart_cup_2014` | Kart Cup 2014 | **Karts > Kart Junior**, **Karts > Kart F1** |
| `STK BMW M6 GT3` | STK BMW M6 GT3 | GT3 World Series > Bmw M6 GT3 |
| `SMMG Formula 3 Series` | SMMG Formula 3 Series | SMMG Formula 3 (2019-2024 × 10 teams) |
| `NR2019` | NASCAR 2019 | NASCAR 2019 Stockcar > 2019 Ford Mustang … |

That last row also answers the other thing OPEN QUESTIONS lists as owed by the
user — the SMMG Formula 3 mod's selectable seasons. They are 2019 to 2024, ten
teams each, and nobody had to be asked.

**THE USEFUL LEVEL OF THE TREE IS NOT ALWAYS THE SAME ONE, and that is the whole
difficulty.** Taking the leaf gets it wrong for half these mods: for the GT3
pack the leaf is a SERIES ("Blancpain Endurance Series 2016") and for SMMG it is
a TEAM. So `pick_names` returns **the deepest level at which every path in the
folder agrees** — the folder's identity in the tree, whatever depth it sits at —
plus the next level down when there are few enough of them to list. A folder
holding two cars names both; a folder holding sixty liveries names the thing
they are all inside.

**IT IS A CONVENIENCE, NEVER A DEPENDENCY**, because it reads a browser cache:
hash filenames, evictable, and one UI update from changing shape. So every
failure path returns an empty map rather than raising, names are remembered in
`_modnames.json` (merged, never replaced, so a name learned once survives the
cache being cleared), and the ORDER in `tier_cars` is:

1. **the curated `ui` name** — a word the user has read on his own screen, and
   nothing beats that;
2. **the learned name** — the game's own string;
3. **the tidied folder name** — the guess that started all this.

The package-level `groupName` is parsed too, as a last resort, and is
deliberately weaker: a pack of nine GT3 cars has ONE package name and it is not
the name of any car in it.

**A test fixture, not the real game.** `laddertest.py` §17 writes a synthetic
cache into a temp directory — that is the only way to test the shapes that are
NOT on this disk (a truncated record, a comma with no space, a folder that is
not installed) and it means the suite still runs on a machine with no rFactor 2.

### A HOMOLOGATION LIST IS A REFERENCE, NOT A SNAPSHOT

Fixing the name did nothing for the letter he already had, and that is rule 1 of
`inbox.py` working exactly as designed: every number is frozen when sent. **That
rule is right for a result sheet and wrong for this one letter.** A result sheet
is valuable BECAUSE it says what was true that afternoon; a homologation list
exists to be acted on later, and one naming a car that cannot be selected fails
at its only job.

So the `eligible` id now carries an eight-character fingerprint of the list. A
changed list — a car installed, or the real menu name learned — is **re-issued**;
an unchanged one has an identical id and is not, so this can never become a
letter that arrives on every refresh.

**AND A REVISION SAYS IT IS ONE.** `eligible_revised` (three wordings) exists
because one first-issue wording opens *"unchanged from the version circulated
with your entry pack"*, which is exactly false on the letter that exists BECAUSE
the list changed. Two identical-looking notices with different content in them is
how a reader learns to stop reading them — and this inbox depends on him reading
them. One of the three even admits the department got a name wrong, which is the
in-world version of what actually happened.

`_prior_eligible` reads `mail_seen` rather than the archive, because a deleted
letter was still sent — he read it, loaded a car from it, and the correction is
still owed. It also handles the id shape from BEFORE the fingerprint existed,
which is precisely the letter carrying the wrong name.

### EVERY RUNG PICKS ITS OWN SEASON LENGTH

Asked for: *"can we not choose race length also when we get a promotion? for
example if I want to do only a 3 race season for karting but then a 5 race
season for F4."*

**`advance(rounds=)` AND `_start_rung` HAVE TAKEN A LENGTH SINCE THE LADDER WAS
WIRED, AND NOTHING EVER PASSED ONE** — so every rung inherited the number chosen
once at the top of the career. A defensible default and a poor rule: the whole
point of a ladder is that its divisions are not the same size of commitment, and
a driver asking for three rounds of karting is not asking for three rounds of
Formula One. The model layer needed no change at all; the MENU never asked.

* **A `Next season length` row on the end-of-season page**, beside the four
  choices it governs — the seat above, another go at this division, a switch, a
  new path. It applies to whichever he takes, which is why it does not live on
  any one of them.
* **It defaults to the length he has been racing**, so a driver who never opens
  the page gets exactly the behaviour the career had before it existed. That is
  asserted, because a "harmless addition" that changes an unattended path is not
  harmless.
* **`nextlen:0` is "same as this season", not zero races.** It clears the pending
  choice rather than storing a number, so changing his mind twice cannot leave a
  literal zero in a career file.
* **THE CONFIRMATION SAYS HOW LONG.** "Move up to Formula 4? (5 races)" — the
  length is chosen a page earlier and applied by the same click, so a
  confirmation naming only half of what is about to happen is not one.
* **THE CHOICE IS SPENT WHERE IT IS USED**, not remembered: a pending length left
  lying around would silently re-apply at the next promotion, which is a length
  he picked two divisions ago. Same rule as LAW 11, one layer up.
* `SEASON_LENGTHS` is the same **3 / 5 / 10** the new-career page offers. One
  vocabulary for "how long is a season", so the number means what it meant when
  he started. If he wants 6 or 8, that tuple is the only edit.
* The archived summary keeps the length the season **actually ran** to, so a
  career of 3-, 5- and 10-round divisions reads back correctly in the record.

`paneltest.py` drives this through the real clicks — `page_nextlen`,
`nextlen:5`, `adv:promote`, `confirm_yes` — rather than calling `advance`
directly, because the half that was missing was the menu, and a test that skips
the menu tests the half that already worked.

### `menushot.py`

A fourth preview tool, on the same rule as the other three: it opens the REAL
menu page on a real canvas and grabs the pixels. It exists because no assertion
can answer whether the seat row READS as the one thing on the page waiting for
him, sitting above nine letters that look alike on purpose.

## WHAT CHANGED ON 2026-08-19 — THE PASS, THE POINTS, AND THE ARC

A large session driven entirely by things the user heard or saw. Read the
`_session_log.txt` note at the top of this file first: two of the bugs below
were invisible to twenty-five green suites and obvious in one line of what
actually aired.

### THE PASS WAS BEING DETECTED AND THROWN AWAY

Reported as *"I literally took the podium spot and the commentators said
nothing"*, and the mechanism is exact. `_say` refuses anything under priority
80 while audio is playing, `overtake` is 60, and detection is edge-triggered
with **no queue behind it** — so a pass made while Miles was mid-sentence was
packaged with its victim and its position and then dropped for ever. Same
mechanism 5b-iii documents for the incident sting silencing its own
explanation, in a second place.

Two halves, because passes are not all worth the same:

* `_overtake_report` speaks sting, call and verdict in ONE breath (the shape
  `_incident_report` uses). Gated to passes into the top three and to any
  pass involving the PLAYER — a sting that fires for everything stops meaning
  anything, which is the brake-temperature problem in a new costume.
* Everything else goes on `_pending_pass` for `PASS_RETRY` (6s) and is
  re-offered until it airs or stops being news.

**IT BYPASSES ONE RULE AND ONE ONLY.** The first version skipped every
restraint and forty swaps produced sixty lines; `boothtest.py` §3 caught it
immediately. A booth that calls every place change instantly is not a fix for
one that called none of them, it is the same failure inverted.

**THREE PIECES OF DEAD CONTENT WERE FOUND HERE** (LAW 21, and the count is now
seven). The `pass` stings — six lines, rendered to disk on every startup since
the module was written — had never once been played, because `_sting` was only
ever called for `lastlap` and `retire`. `pulling_away` had six lines, a
priority and a cooldown and no emitter at all. And wiring it up revealed that
**all six of its lines air with an empty slot**, because nothing had ever drawn
them: an unreachable pool is not merely silent, it is untested prose.

It also turned out to be written about the LEADER edging clear ("at the front",
"away from the field"), which is nonsense about a fight for seventh — so
`battle_escaped` is the resolution of a named fight and `pulling_away` keeps
its real subject.

New battle grammar in `lines_data/booth_battle.json`: `battle_three` (a queue
for one place, where the middle man is the story), `battle_traded` (the same
two men swapping it `TRADE_MIN` times), and the escape above. The escape has a
trigger AND a clear point held for `BATTLE_CLEAR_HOLD` — the gap crosses
`STRIKE_GAP` every lap of every race (LAW 18) — and refuses when the man in
front simply pitted.

### THE POINTS, AND THE MOST DANGEROUS FUNCTION IN THE PRODUCT

`Career.title_scenarios()` answers "what does he need this afternoon", up to
and including the rival-dependent table the user asked for ("P5 if Borda
wins"). Everything else the booth says is about something that has already
happened; this is a claim about what WILL be enough, and the listener checks
it at the flag.

* **NOTHING IS RETURNED UNLESS IT IS PROVEN.** `secure` wins the title against
  every remaining result by every driver, not the likely case.
* **STRICTLY MORE POINTS, NEVER EQUAL.** `standings()` breaks a tie
  alphabetically, which is a sort order and not a countback rule — this product
  does not model one, so a tie is not a title.
* `tests/pointstest.py` does not assert the reasoning. It **brute-forces** every
  finishing position against every permutation of what the chasers could score,
  and fails if the closed form and the enumeration disagree.

The booth speaks it only on the CROSSINGS (`title_live` / `title_lost`, as he
moves in and out of the required position); the paper carries it in
`news_title_maths` / `news_title_win` / `news_title_finish` /
`news_title_fight`. **The run-in scales with the season** — the last third,
floored at three rounds, alternating when long — because a fixed window gave a
24-race championship the same two paragraphs as a 6-race one.

### RIVALRY IS A STANDINGS FACT NOW

At the user's instruction: after `RIVAL_AFTER` (4) rounds, his rival is
whoever is ADJACENT in the table and within a win's points. The old rule also
required the two men to have finished near each other on the road, which made
rivalries rare and missed the commonest shape of a real title fight — two
drivers level on points who are seldom in the same part of the circuit.

### THE CHAMPIONSHIP NEWS THAT NEVER FIRED

He won the Hot hatch title and read nothing about it. **Two independent
structural causes:**

1. `_milestones` — the only feed that could print a title — opens with
   `if era is None: return []`, and an era only resolves for a season
   `drivers.json` holds. So the feed built to announce championships could not
   announce one in ANY division of the ladder. `news._champion()` reads the
   final table instead and needs no driver knowledge at all.
2. `status()` counted ARCHIVED seasons, so on the afternoon he won it he was
   still a rookie — `status_changed()` returned None and neither the booth's
   arrival line nor the headline could fire. `title_count()` now includes the
   season he is standing in: a season that has run its full length has a final
   table, so first place in it is a fact rather than a projection.

An AI champion gets `news_champion`, which claims nothing about a career this
overlay has never seen. And `_status` fires on the LAST round rather than
whichever the loop reached first, which had it filing the champion headline
against round one.

### THE MAN IN THE OTHER SIDE OF THE GARAGE

`BoothMixin._team_mate` — the most F1 thing in the sport, and nearly free. For
the Formula One mods rF2 reports the CONSTRUCTOR as the CarClass, so the
team-mate is the other car sharing the player's class.

**EVERYWHERE ELSE THE CLASS IS THE SERIES** — all thirteen Formula 2 cars
report "Formula 2 2019" — so `_team_mate_learned` reads pairings that
`career.py` folds out of `<TeamName>` in the result files. That field had been
parsed since the module was written and used by nothing. One session with a
grid on it, including a qualifying run, teaches the whole championship.

`Career.team_mate_record()` counts the season head-to-head from rounds this
overlay recorded. **A DNF counts for neither of them** — a head-to-head that
scores a retirement flatters whoever's car held together.

**A bug worth remembering:** `Career.record()` builds its round dict FIELD BY
FIELD rather than copying the result, deliberately, so a caller cannot smuggle
keys into the store. Anything new has to be named there or it vanishes
silently — the team-mate reached the store and disappeared, so the race half of
the head-to-head read nil-nil for ever while the qualifying half, which has its
own writer, worked perfectly.

### THE JUNIOR PROGRAMME — `programme.py`

The user's own design, and the one scripted arc on the ladder. Three seats at
the start of Formula 2, each backed by a Formula One junior programme; win the
championship and the seat is offered with a DEVELOPMENT YEAR attached; miss it
and the programme waits one more season and then stops waiting. He always takes
the SECOND seat, alongside an established number one.

* **WINNING MEANS FINISHING FIRST**, not merely earning promotion. The ladder's
  bar for leaving F2 is third; the programme's is the championship, which puts
  two different stakes on the same afternoon.
* **THE YEAR HAS NO CLOCK.** This product has no calendar and a "year" is only
  ever "the next season you race" — which, during a year out, never happens. So
  it arrives as five letters (`DEV_BEATS`) and the seat opens when they are
  read. The user chose this over simulating a season.
* **MEL WRITES THROUGH IT**, with two beats of her own (`dev_beats` in
  `personal.json`) rather than spending the ordinary thread. It is the best
  thing that could have happened to that story: the year he had nothing to do
  is the year he still did not go home.
* `news_seat_taken` reports the displaced driver losing his seat — sayable for
  the reason the needle is, and held to the same restraint: about DRIVING and a
  team's judgement of it, never about character. `news_dev_year` looks ahead to
  the season he is about to start.

**THE SEAT IS A CAR, NOT A TEAM.** `match()` takes the `vehicle` string — rF2
names each entry for its driver ("#77 - Valtteri Bottas") — and refuses a round
driven in the OTHER side of the garage. Refused only when he is positively in
the other one: an entry naming neither driver is unknown, not wrong, and falls
through.

**AND THE BOOTH NAMES WHOEVER IS REALLY THERE.** The programme's stored lead is
the EXPECTATION; `_team_mate` is the FACT. If he loads Hamilton's car instead of
Bottas's, the lines say Bottas.

### THE LAST TWO RUNGS CARRY THEIR YEAR

Asked for because 2021 is iconic and the climb should point at it. **This is
the exception the product already makes**: "a year is for knowing, never for
saying" is about the ROAD — a 1991 Silverstone layout announcing itself tells a
driver he is re-running somebody else's season — whereas a SEASON year is his,
which is why `season_launch` has always said "the opening round of the 1988
Formula One season".

Declared per rung in `ladders.json` (`year_name: true`), NOT listed in code, so
any path can have it. `years: [lo, hi]` locks which season counts — Formula One
is 2021 and only 2021 — and refuses only when the year is KNOWN, because a
career that silently stops counting is the worst failure `season.py` has.

### DIVISION-AWARE COMMENTARY

Reported as Chuck being offered a go in a rookie kart and answering that he
would be two seconds off. Two faults:

* The `era` crosstalk topic had **no discipline gate at all**, and every answer
  assumes the car is faster and harder than a Cup car. Now gated to
  formula/proto/gt, with `era_junior` for karting, touring and stock cars where
  his honest answer is a better one.
* **`era.classify` CANNOT TELL AN F4 FROM AN F1 CAR** — both are discipline
  `formula`, period `hybrid`. No era gate can ever make Miles say "these F4
  cars", so `lines_data/booth_division.json` is keyed on the LADDER RUNG
  (`div_kart`, `div_f4`, …). A rung with no pool says nothing.

### SIMULATING A ROUND

`Career.simulate_round()` — the sibling of `record_absence()`, except he is IN
the result. The rule is unchanged and narrow: **positions and points, never
events.** No fastest lap, no retirement, nothing the booth may narrate as though
it watched. It never touches `career.py`, so it does not become his history at a
circuit, and it writes no qualifying result — which is what keeps "last time out
you put it fourth" honest for free.

**THE FIRST TWO RUNGS ARE GENEROUS** (`SIM_LEARN_TIERS`), at the user's
instruction: the physics ladder is steep and a simulated season in a learning
division earns the promotion. Above that it reports his own form. Deterministic
per (career, round), so reloading cannot reroll it.

**IT REFUSED SILENTLY, AND THAT IS THE PATTERN TO WATCH FOR.** Reported as
*"I press sim round and then yes and nothing happens"*. The grid was looked up
from `career.data["cls"]` — the season's LOCKED class — which is filled in by
the first race a season RECORDS. A career that has not raced has none, and
that is exactly the career somebody wants to simulate from: the lookup found
nothing, there was no grid, and `simulate_round` returned None with no way for
the user to know why.

**A LOOKUP KEYED ON STATE THAT DOES NOT EXIST YET IS THE RECURRING SHAPE HERE.**
It is the same failure as `installed_mods()` caching an empty list, as the
class list being built only from recorded results, and as `status()` counting
only archived seasons. Ask what the key is filled in BY, and whether that has
happened yet.

The grid comes from the RUNG now (`PanelsMixin._sim_grid`): any class
`career.py` has ever seen that resolves to the division he is standing in —
the same roster the New Career driver picker uses.

**AND THE SIM IS NOT A SHORTCUT PAST SETTING UP A CAREER.** He could reach the
button before choosing a car or a nationality, which banks a result for a
season that is not configured. `_sim_blocked()` returns a REASON rather than a
bare False, and the row shows it: *"pick a nationality"*, *"pick a car first"*,
*"race them once first"* when the division has no roster because its cars have
never been loaded. A disabled control that does not say why is the thing he
actually complained about.

**A SIMULATED TITLE COUNTS IN `resume()` LIKE A DRIVEN ONE.** In-world it is
true and it was his choice; it does soften "every fact was watched", and the
user was told. `simulated: True` is on every such round if that ever needs
separating.

### PICTURES — `newsart.py`

His own photographs, in `Pictures/Factor Overlay/<Division>/<Category>/`. Three
tones — Drama, On track, Podiums or wins — because a picture tied to a specific
event becomes a factual claim, and atmosphere cannot be wrong. Rotation is on
the ROUND so a folder is walked before it repeats.

* **NEVER ON MAIL** for the pictures themselves. `for_item` refuses anything not
  on the news feed: the ending works because the personal letters are
  indistinguishable, and "which ones have pictures" is a thing a reader sorts by.
* **LETTERHEAD IS DIFFERENT AND IS SAFE.** The FIA, the team and FACTORtv carry
  a mark on an OPENED letter; the inbox LIST is untouched, which is where the
  skim-training happens. Derived at draw time, never stored, so `inboxtest.py`
  §11 still holds.
* The division mark also sits top-right of the screen (`draw_division_logo`) and
  on the end-of-session result card — which now says QUALIFYING RESULT rather
  than RACE RESULT after a qualifying session.
* **A MARK WITH NO TRANSPARENCY KEEPS ITS OWN GROUND** — the FIA logo is a JPEG
  on white with dark wordmark text, so it is drawn on a light plate. Keying the
  white out would make the words invisible; compositing onto the panel colour
  would put a white box there.
* **CHROMA IS EXACT.** `-transparentcolor` keys #010102 precisely, so artwork
  pixels landing on it are nudged — and ONLY those. The first version nudged the
  background too, which is deliberately that colour, and put a black box behind
  every logo.
* **TRIM THE TRANSPARENT MARGIN BEFORE SCALING.** Downloaded logos carry wildly
  different padding; without the crop, "56 pixels tall" meant something
  different for every division.

### THE ENDING PHRASE, AND STATUS NAMING

* **The show said goodbye twice, every session.** Every line in `signoff` AND
  `quali_over_signoff` was a farewell, and then the outro sting said goodbye
  again — four seconds apart in the live log. Those pools state the RESULT now
  and the outro is the one designated ending: *"And that's it from FACTORtv."*
  `lifecycletest.py` greps every wrap pool for farewell language.
* **"The rookie" nineteen times against thirty-three uses of his name was a
  BUG, not a ratio.** The seed was `hash((name, self._pre_at))` — constant for
  the whole session — so "one mention in five" was all of them or none. It seeds
  on lines actually aired now, defaults to the SURNAME, and the status form is
  gated to `STATUS_APT`: categories where the status and the sentence are the
  same thought.
* **"The rookie, the rookie."** The template is `"The rookie, {drv}."`, written
  when `{drv}` was always a name — LAW 13 exactly. `STATUS_SELF` names the pools
  whose prose already states the status; they always get a name.
* **A status line must not claim to have watched him drive.** One fired in the
  pre-quali sequence of a first session — *"something about the way he is
  placing this car"* — thirty seconds before anybody had set a lap.

### MOD NAMES: THREE TRAPS IN ONE SESSION

* **`Kart_cup_2014` holds TWO selectable cars**, "Kart Junior" and "Kart F1",
  and the folder cannot name either. The letter told him to look for "Kart Cup
  2014", which is not on the menu in the game. Real names are CURATED in
  `ladders.json` under `ui`, filled in only from what he has confirmed seeing.
* **`_norm` splits camelCase**, so `F2_2019` and `ASR_2017_F2_Championship` BOTH
  contain " f 2 " — a bare `f2` alias would have put the unwanted 2017 mod on the
  rung. The year is in the alias.
* **A rung listing every car that fits is not a choice, it is a list.** F2 and F3
  were offering five cars each, four of them the wrong series. One car per rung
  where the championship is a specific one.

### PREVIEW TOOLS ADDED

`newsshot.py`, `podiumshot.py`, `mailshot.py`. All three draw with the REAL
panel on a real canvas and grab the pixels, exactly as `dashshot.py` does —
re-drawing a layout in PIL is quicker and lets the preview drift from what the
overlay renders, which is the one thing a preview must never do.

**A trap that only bites tooling:** Tk drops an image the instant nothing
references it, and these panels hold their logo on the HOST. `Host().draw(...)`
discards the host before the screenshot, and the mark simply vanishes. The real
overlay keeps its host for the life of the program.

## WHAT CHANGED THIS SESSION (2026-08-16, second half)

Read this before assuming anything above is stale.

* **`gauge.py` is new** — the whole instrument. See THE INSTRUMENT above.
* **Engineer**: 41 categories / 110 lines -> **53 / 361**. He is now the only
  information channel (driver radio is gone), so he reads your lap back on
  EVERY completed lap in both quali and race, with the gap to whoever you are
  racing. Low priority, so anything urgent still wins the tick. He uses
  **first names only** (`_first_name`) — an engineer never says a surname.
* **Off-track detection** is real, from `mSurfaceType`. Grades spin /
  offtrack / ranwide, and reports on the way BACK so the grading knows how
  bad it got. Publishes `player_off` for the engineer.
* **Qualifying is a programme**: top three with real margins, how big a pole
  margin is (measured against the RUNNER-UP, not the improvement), duels for
  pole, the tail of the sheet, and WHERE a lap was won from real sector
  splits.
* **Broadcast priority**: events are ranked by category AND by the position
  they concern (`PLACE_WEIGHT`). A P2 overtake now outranks a P8 one; before
  they tied and filler ranked purely on staleness.
* **Text fitting**: `_wrap_px` measures pixels and the real font instead of
  counting characters, and ellipsises instead of silently dropping words.
* **Captions**: when a non-booth voice is audible the booth caption HIDES
  rather than holding a stale line. That was the audio/caption desync.
* **`dashshot.py` / `cardshot.py`** render the real panels to PNG. Use them —
  several bugs were only visible in a picture, and several more only at UI
  scale 1.25x.

---

## OPEN QUESTIONS — START HERE

**THE WORK IN FLIGHT (2026-08-19): NON-OVERLAPPING ARCS.** The user wants
every path's last two rungs to get the treatment Formula 2 and Formula One
now have — a named season year in the commentary, and a `years` lock so only
that season counts — with the mod years chosen so no two arcs occupy the same
period. His words: *"I can always go look for a year that makes sense ... I
can get the 2012 GT3 season and then get the 2017 WEC pack."*

**THE MACHINERY IS BUILT AND IS PURE DATA.** A rung asks for its year with
`"year_name": true` and locks the season with `"years": [lo, hi]`, both in
`lines_data/ladders.json`. Nothing in code needs to change to add a path.
What is needed is (a) the mods, which are his to install, and (b) one curated
`ui` name per rung so the FIA letter names a car he can actually select.

The state of it, from `ladder.tier_cars` against his install:

| path | last two rungs | installed | locked |
|---|---|---|---|
| Single-Seater | F2 → F1 | F2_2019 → F1_AM_2021 | yes, 2019 → 2021 |
| Road to Indy | Indy Lights → IndyCar | Tatuus 2018 → Dallara **2014** | no |
| Endurance | GTE → Prototype | Corvette **2009** → Audi R18 **2016** | no |
| Stock Car | Pro → NASCAR | SC2018 → NR2019 / 2023 | no |
| Touring | Touring cars → GT500 | BMW 330 **2020** → GT500 **2021** | no |

**Two collisions are already visible** and are the reason this is worth
doing: Road to Indy runs BACKWARDS (2018 Lights into a 2014 IndyCar), and
Touring's 2020 → 2021 sits on top of the single-seater arc.

A suggested allocation, agreed as a shape rather than as specific mods:
Endurance 2012 → 2017, Touring 2013 → 2015, Stock Car 2018 → 2019,
Single-Seater 2019 → 2021 (locked), Road to Indy 2022 → 2024.

**NOTHING IN THE STORE ENFORCES THE TIMELINE** — there is no calendar — so
this is a narrative constraint satisfied by choosing mods. Ask him which years
he has settled on before editing anything.

**A SECOND ARC IS DESIGNED AND NOT BUILT.** `programme.py` is written for the
single-seater path specifically: three Formula 2 seats leading to a Formula
One team. He wants "the same sort of arc" on the other paths. It generalises
along the same seams — the programmes are data, the stage machine is not
path-specific — but the CONTENT is (F2 teams, F1 seats, a development year),
and a GT3-to-WEC version needs its own. Do not start it before the years are
settled, because the seats depend on which seasons exist.

**One thing still owed by the user:** the years above. The SMMG Formula 3
names are no longer owed — `modnames.py` reads them out of the rF2 UI's own
cache (2019-2024, ten teams each), and every other rung's menu names with
them.

---

**THE PREVIOUS WORK IN FLIGHT: THE CAREER LADDER.** `ladder.py` is built and green;
everything above it is designed, agreed with the user in detail, and not
written. Start at BUILD ORDER in the CAREER LADDERS section — step 1 is
`season.py` wiring, which makes the ladder driveable on its own. The user has
approved every design decision recorded there; do not relitigate them, and do
not start with the inbox UI, which is step 2 for a reason.

**Two things still owed by the user, neither blocking:** the installed folder
names for **rF2 NASCAR 2019** and **GT3 World Series v1.20** (placeholder
aliases are in `ladders.json` and marked), and nothing else.

**THE SINGLE MOST IMPORTANT FACT ABOUT THIS HANDOVER**: an enormous amount
was built on 2026-08-17 and **almost none of it has been heard in a live
session**. The driver knowledge base, the story system, the wrap, the driver
cards and quotes, the engineer's new register and sector coaching, the track
facts, the card/audio sync fix, the off-track sting chain, the phase gating —
all of it is verified by tests and direct function calls, none of it by
driving. **Ask the user for a `python testrun.py` session early**, then read
`_session_log.txt`. That will answer more in ten minutes than reasoning about
the code will in an hour, and several of these features could be subtly wrong
in ways only hearing them reveals.

* **Speedo lag** — see §5. DIAGNOSED AND FIXED: the frame was running at 12Hz
  because the tick delay was added after the work, and the map was redrawing
  a static outline with 4000 canvas items a frame. Whole frame 33.5ms -> 21ms,
  zero frames over budget. **The user has not seen this yet** — it is the
  first thing to ask about, and `python frametime.py` is the tool if it is
  still not right. Do not touch `GAUGE_R`.
* **Commentary phase structure** — see §5c. NOW COMPLETE: opening/closing
  gates, the `settling` phase, and the late-race lead-fight override are all
  in and tested. **None of it has been heard.** The phase shape is verified by
  driving a synthetic 40-lap race through the transitions, which is a real
  check of the boundaries but says nothing about whether lap one SOUNDS
  tightly focused. This is the first thing to listen for in the next
  `testrun.py`.
* **A booth that JOINS a race in progress dumps its unfired distance marks** —
  starting at lap 30 of 40 produced "past quarter distance" on lap 37, one
  mark per lap boundary. `_distance_mark` only ever skips a mark once it has
  fired it. Unreachable in a race watched from the start; noticed while
  testing the closing phase, not fixed, and worth a guard (skip any mark
  already passed on the first lap the booth sees) if the user ever starts the
  overlay mid-session.
* **Audio cannot be verified from here.** Sync, delivery and whether two
  voices sound like one room are for the user to judge with
  `preview.py --live`.
* The **gauge appearing to move** has not recurred and the caption can no
  longer reach the cluster. Treat as closed.

---

## HOUSE STYLE

Match the surrounding code. Comments explain WHY, especially where a value
was tuned or a simpler approach failed — most of the constants in this
project encode a bug that has already happened once. Prose in dialogue is
British broadcast English. When a fix is a guess, say so; when a log answers
the question, quote it.

Ask before changing the cast, the UI layout or the dash — all three are
settled and the user is happy with them.
