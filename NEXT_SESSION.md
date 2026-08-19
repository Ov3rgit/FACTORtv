# Next session — paste this as the first message

---

**FIRST, BEFORE ANYTHING ELSE: read `_session_log.txt` in full.** It is deleted
between runs, so if it exists it is the record of the last time the overlay was
actually driven. Every hard bug in this project was found there and none by a
test suite; when the log and your model of the system disagree, the log is
right. Then read `HANDOVER.md` in full — it is long and nearly every question
you are about to have is answered in it.

**A very large amount was built on 2026-08-19 and NONE of it has been heard.**
The pass stings, the battle layers, the title arithmetic, the team-mate
comparison, the junior programme, the division-aware lines, the pictures and
the letterheads are all verified by twenty-five green suites and rendered
previews, and by nothing else. Ask for `python testrun.py` early.

## What you are building: NON-OVERLAPPING ARCS

Formula 2 and Formula One now behave the way the user wants every path's last
two divisions to behave:

* the booth names the season — *"the 2019 Formula 2 season"*, *"the 2021
  Formula One season"* — because a championship is his to be told about, which
  is the same exception `season_launch` has always made;
* the rung locks that season, so racing the 2025 mod is not a round of it;
* a junior-programme arc runs across the two, ending in a specific seat.

He wants the same shape on Endurance, Touring, Stock Car and Road to Indy, with
the mod years chosen so **no two arcs occupy the same period** — his example is
a 2012 GT3 season into a 2017 WEC one.

### The machinery is already built and is pure data

In `lines_data/ladders.json`, per rung:

```json
"year_name": true          the booth says the year
"years": [2017, 2017]      only that season counts as a round
"ui": {"alias": ["What the game actually calls it"]}
```

`ladder.named_year()` reads the first, `season.match()` reads the second, and
`ladder.tier_cars()` reads the third. **No code change is needed to add a
path.**

### Start by asking him two things

1. **Which years he has settled on**, per path. Two collisions already exist
   and are the reason this is worth doing: Road to Indy runs backwards (2018
   Indy Lights into a 2014 IndyCar) and Touring's 2020 → 2021 sits on top of
   the single-seater arc. The table of what is installed is in the OPEN
   QUESTIONS section of the handover.
2. **What the game lists** for any multi-season mod, in its own words. The
   `.mas` archives are compressed and cannot be read, so a mod's real names
   only ever come from him or from a result file. This has bitten three times
   in one session — "Kart Cup 2014" was not on the menu, the car he needed was
   called "Kart Junior".

Do not edit `ladders.json` before both answers. A wrong `years` lock stops a
career counting, which is the worst failure that module has.

### Then, and only then

A second junior-programme arc. `programme.py` is written for the single-seater
path — three Formula 2 seats leading to a Formula One team — and the stage
machine is not path-specific, but the CONTENT is. A GT3-to-WEC version needs
its own seats, its own letters and its own development beat, and all of them
depend on which seasons exist.

## Do not relitigate these

Every one was decided with the user, most after a live log or a rendered
preview. They are recorded with their reasoning in `HANDOVER.md`.

* **The seat is a car, not a team.** Once the programme seat is his, a round
  driven in the other side of the garage does not count.
* **A simulated round produces positions and points, never events** — and the
  first two rungs of a path are deliberately generous, because the physics
  ladder is steep and testing should not require mastering it.
* **Rivalry is a standings fact**: adjacent in the table, within a win, after
  four rounds.
* **Pictures never go on mail; letterheads do.** The inbox LIST stays
  identical, which is where the story's skim-training happens.
* **One goodbye per session**, and it is the ending phrase.
* **The status form is gated on context**, not on frequency, and defaults to
  the surname.

## The two hardest lessons, still true

1. **A fake cannot falsify a field name** (LAW 0). Anything reading shared
   memory gets a real-struct test — see `tests/buffertest.py`.
2. **A pool with no caller is invisible and `lines.py` calls it healthy** (LAW
   21). This project has now broken it SEVEN times, twice on 2026-08-19 — once
   with pools that had shipped unreachable for months, and once with a pool
   written that same session. `tests/passtest.py` §1b greps for an EMITTING
   context rather than a mention, because a name in a constants dict fooled the
   first sweep.

## Run everything, two or three times, after every change

```bash
for t in flowtest boothtest lifecycletest radiotest rivaltest paneltest eratest tracktest careertest seasontest offtracktest qualitest drivertest humourtest storytest stationtest buffertest laddertest inboxtest newstest personaltest careerboothtest passtest pointstest programmetest; do echo "$t: $(python tests/$t.py 2>&1 | tail -1)"; done
```

And validate the data: `python lines.py`, `python ladder.py`, `python news.py`,
`python inbox.py`, `python personal.py`, `python programme.py`,
`python newsart.py`.

## Seeing it without driving

```bash
python newsshot.py     # news articles with his own photographs
python mailshot.py     # a letter, with its letterhead
python podiumshot.py   # the end-of-session result card
python preview.py --live   # the booth, out loud
```

All of them draw with the REAL panel and screenshot it. Never re-draw a layout
in PIL to preview it — the preview must not be able to drift from what the
overlay renders.
