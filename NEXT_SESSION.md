# Next session — paste this as the first message

**We are building the arc for the next division.** The single-seater arc is
finished, driven and shipped; the job now is a second one, and the real work is
deciding what is *data* and what is *code* before writing a word of dialogue.

---

## FIRST, THE RITUAL

1. **`_session_log.txt`** in full. Its first line names the build that wrote it.
   Every hard bug in this project came from that file and almost none from a test.
   When the log and your model disagree, the log is right.
2. **`HANDOVER.md`** — ~6,000 lines. The newest sections are at the top of the
   "what changed" run and are the ones that matter. Do not skim the laws.
3. `python tools_stamp.py --show` to see what this working copy would stamp as.

**26 suites, green twice, both archives shipped.** Sweep before and after
everything: `for f in tests/*test*.py; do python "$f" | tail -1; done`.

---

## THE ONE RULE THAT SHAPES EVERY DECISION

> *"the commentary is the actual main gameplay, and most of what happens in the arc
> needs to happen or be said on track"*

An arc beat that exists only as an email is not finished. When the junior arc was
audited against this, the booth turned out not to know about the call-up rumour it
was commentating over, and the engineer had a stock greeting for a driver's first
Formula One session. Assume the same gaps in whatever gets built next, and check
for them deliberately.

---

## THE REFERENCE IMPLEMENTATION

The junior arc — F3 2019 → mid-season call-up → F2 2019 → the seat won → 2020
development year → 2021 in Bottas's Mercedes — is laid out beat by beat in an
artifact titled **The Junior Arc** (ask him for the link). Read that before
designing a second one; it is the shape to copy or deliberately depart from.

**It runs on six triggers and nothing else:**

| Trigger | Where it lives | What it drives |
|---|---|---|
| the RUNG he is on | `career.ladder.tier()["key"]` | which beats are even possible |
| the STAGE of the programme | `career.data["programme"]["stage"]` | the whole story order |
| ROUNDS RACED this season | `len(career.rounds)` | the rumour, the call-up, pacing |
| a MEASUREMENT off the table | `programme.bar_state()` | the chase, on air and in print |
| the ENTRANT of the car loaded | `Career.team_for_entry()` | whether a round counts at all |
| OUTINGS driven | `programme.test_state()["n"]` | the development year's pace |

Every beat is driven by a stage rather than a date, which is what stops the story
getting ahead of the driving. **Keep that.**

---

## WHAT PORTS, AND WHAT IS WELDED TO FORMULA ONE

`programme.py` is 800 lines and about a third of it assumes this specific ladder:

* `F3_KEY`, `F2_KEY`, `F1_KEY` — the three rungs, by name.
* `CALLUP_BAR = 3`, `CALLUP_ROUNDS = 10`, `CALLUP_AFTER`/`CALLUP_MIN`.
* `TEST_YEAR = 2020`, `TEST_MOD = "F1_AM_2020"`, `TEST_OUTINGS = 3`.
* Block fields in `programmes.json`: `f3_team`, `f2_team`, `f1_team`, `f1_seat`,
  `f1_lead`.
* `season._programme_team()` and `_programme_seat()` map rungs to those fields.
* `_programme_holds()` hard-codes `nxt["key"] == "f1"`.

**Everything else is already generic**: the pools, the stage machine, the letters,
the news, the seat gate, `bar_state`, the dashboard rows, `apply_verdict`.

### Two ways forward — recommendation first

**A. Make the arc data-driven (recommended).** One `arcs.json` entry per path:
the three rung keys, the bar, the round counts, the test year/mod/outings, and the
names of the block fields. `programme.py` then reads the arc for the career's path
and the F1 constants become defaults for the single-seater entry. Cost: a day of
careful refactoring with the suites as the net. Benefit: every future path is
data, and `programmetest` §7m already proves the whole thing end to end.

**B. A second module** (`programme_indy.py`) sharing the pools. Cheaper to start,
and it means two state machines to keep in step for ever. This project already
learned what happens when two rulebooks agree by accident — the ladder promoted a
driver past the development year the programme had promised him.

Do **A**, and do the refactor *before* writing any dialogue: the shape of the data
decides what the letters can say.

---

## THE FOUR REMAINING PATHS, AND THE STORY EACH ONE WANTS

Ask him which. They are not equally close to the junior arc:

**`road_to_indy` — USF2000 → Indy Pro 2000 → Indy Lights → IndyCar.** The closest
sibling: a junior ladder into a top series, real teams, real scholarship money.
Two things it can do that the junior arc cannot — the **scholarship** (winning
USF2000 literally buys the next season, which makes a championship mean money
rather than a phone call), and the **Indy 500 rookie orientation programme**, a
real institution of phased speed runs that maps onto the test-outing mechanic
better than the invented development year did. Recommend this one.

**`endurance` — Club racer → GT4 → GT3 → GTE → Prototype.** The most interesting
and the least portable: endurance is about a CO-DRIVER and a factory contract, not
a seat somebody else loses. The arc beat is being paired with a professional who is
quicker than you, and the bar is not a championship position but whether the team
trusts you with the night stint. Needs its own machinery for shared cars.

**`stock_car` — Stock Car Junior → Stock Car X → Stock Car Pro → NASCAR.** Ovals
change the vocabulary completely and the booth already has stock-car era lines. The
natural arc is a development contract with a Cup team and a part-season of
substitute drives.

**`touring` — Hot hatch → Touring cars → Super GT500.** Three rungs and a jump to
Japan, which is a story about leaving rather than climbing.

---

## HOUSE RULES FOR WRITING THE NEW ARC

* **Never state something false about a real driver.** The whole product rests on
  it. A seat changing hands says the team made a change and never that anybody was
  insufficient; a replaced driver is named only where the fiction requires it, and
  never judged. Both Bottas pieces are the model.
* **Measured numbers only.** `bar_state` returns None when a gap cannot be read and
  every caller says nothing. A piece that cannot get its number is not filed.
* **Mel has no expertise and that is her job.** A fact about racing reaches her
  from a person, never from her own understanding, and every letter turns to family
  before it ends. Her knowledge grows only where a normal person's would: she had
  heard of Formula One and nothing else. For Indy, she would have heard of the
  Indy 500 and no other race — use that.
* **One letter per refresh from her**, biggest first. Three in one afternoon is a
  writer arranging a plot.
* **The pools are gated on era, not on career.** A booth line cannot be made
  conditional on a stage — if it can air in the wrong situation, it must be true in
  both. That is why a `div_f2` line had to be reworded rather than gated.

---

## THE BUG CLASSES THAT COST THIS PROJECT THE MOST

Written out because every one of them will be available again in a new arc:

1. **A state machine nothing invokes.** `apply_verdict` and `take_deal` were called
   only by the tests, which called them themselves — so every beat had a passing
   unit test and the arc was unreachable by playing. **Write the
   walk-through-the-doors test first** (`programmetest` §7m: `inbox.refresh`,
   `news.refresh`, and the dashboard's click handler, never a transition directly).
2. **Keys nothing dispatches.** A nav key not in the router's table silently lands
   on the settings page; an action key not in the click handler silently does
   nothing. Both audits are in `paneltest` — extend them, do not bypass them.
3. **Bookkeeping behind an output gate.** Four separate instances. Anything that
   REMEMBERS goes above the on-air/green-flag gates; anything that SPEAKS goes
   below.
4. **Judging the same season twice.** A verdict keyed on anything the verdict
   itself changes (the attempt counter) or on anything coarse (a whole-second
   timestamp) re-fires. Key on the season's identity.
5. **State in a file somebody else rewrites whole.** The introduction played on
   every launch for two days because "he has heard it" lived in `_settings.json`,
   which any toggle rewrites from one process's in-memory copy. Durable state that
   only one feature owns gets its own file (`_intro_done`).
6. **Removing the last route to a feature.** The career left the settings page and
   took the only door with it.
7. **A test whose setup makes the answer inevitable.** An empty circuit slug made
   `match` refuse everything, so three refusal checks passed without testing
   anything.

---

## PRACTICALITIES

* **`careers/` is gitignored.** His live career is mid-arc: Formula 2 won, the seat
  accepted or about to be, the 2020 development year next. Copy it to a temp
  `CAREER_DIR` before experimenting; never edit it without asking.
* **`_intro_done` and `_settings.json`** are his machine's state. Never shipped.
* **Build and ship:** `python tools_stamp.py` then PyInstaller, then
  `python tools_package.py` and `--exe`, then `gh release upload ... --clobber`
  using the credential from `git credential fill`. Both archives verify
  byte-identical before they go.
* **The release** is `v0.0.1-beta` on `Ov3rgit/FACTORtv`, one tester (Paul Van
  Rooyen in the shipped names, Dante Kandasamy / Over Boy in the author's copy).
* **The shell eats backslashes in heredocs.** Build `"\n"` with `chr(92)` or use
  the Write tool. Edit data files as DATA through `json.load`/`json.dump` — a text
  substitution over raw JSON broke four suites in one command.
