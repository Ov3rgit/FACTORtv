# Next session — paste this as the first message

---

**FIRST, BEFORE ANYTHING ELSE: read `_session_log.txt` in full.** It is the record
of the last time the overlay was actually driven, and its first line now names the
BUILD it came from. Every hard bug in this project was found in that file and
almost none by a test suite; when the log and your model of the system disagree,
the log is right. Then read `HANDOVER.md` — it is ~5,900 lines and nearly every
question you are about to have is answered in it. The newest sections are at the
top of the "what changed" run and are the ones that matter.

**Then check the build stamp.** `python tools_stamp.py --show` says what this
working copy would be stamped; `version.stamped()` says what it currently claims.
The shipped zips on the GitHub release carry the stamp of the commit they were
built from, so a bug report can always be matched to code.

---

## WHERE THE PROJECT IS (end of 2026-08-20)

**26 test suites, green twice in a row. Both archives shipped and byte-verified.**
The tester (Paul Van Rooyen in the release, Dante Kandasamy / Over Boy in the
author's copy) has the standalone exe from
`https://github.com/Ov3rgit/FACTORtv/releases/tag/v0.0.1-beta`.

The user is **starting a fresh playthrough of the junior single-seater arc** and
will report against it. He has asked, more than once and in these words, for the
thing to keep in mind:

> *"the commentary is the actual main gameplay, and most of what happens in the arc
> needs to happen or be said on track"*

An arc beat that exists only as an email is not finished.

### The junior arc, end to end, all built

F3 2019 → mid-season call-up → F2 2019 → the seat won → 2020 development year →
2021 in Bottas's Mercedes. Every beat has a voice: the booth, the engineer, the
agent/team/FIA post, the news feed, and Mel. There is a design document for it —
an artifact titled **The Junior Arc** — laying out every beat in firing order; ask
the user for the link if you need it.

### What was fixed on 2026-08-20, and what it taught

Read these in `HANDOVER.md` before touching the arc. They are the session's real
output, more than the features:

  * **`apply_verdict` and `take_deal` were called by NOTHING but the test suite.**
    The whole arc past Formula 2 was unreachable by playing. Every beat had a
    passing unit test, because each test called the transition it was testing.
    `programmetest` §7m now walks the arc through `inbox.refresh`, `news.refresh`
    and the dashboard's click handler and never calls a transition itself. **If a
    state machine ever gets added, that is the test to write first.**
  * **Two dead buttons and a dead route**, found by pressing them: `page_career_new`
    where the router knows `page_new`, and `confirm:simulate` where the handler
    knows `sim_round`. Both audits now live in `paneltest` — every `page_` key
    against the router's table, every action key against the click handler. The
    action audit immediately found "Close career" dead since long before.
  * **Removing the last route to a feature.** The career left the settings page and
    took the only door with it: the trophy button was hidden when no career
    existed, and the way to start one had just been deleted. Check what still
    *leads* to a feature, not just whether it works.
  * **Bookkeeping behind an output gate**, four times: qualifying below the on-air
    gate, a settle needing the winner's flag, a result needing the leader to
    finish, and the tutorial's "heard" flag behind the green-flag check. Anything
    that REMEMBERS goes above the gate; anything that SPEAKS goes below.
  * **A verdict must be judged once.** Applying it on every refresh made the arc
    reachable and introduced worse: an archived season never changes, so every
    menu draw judged it again and one missed season became a dropped career in two
    clicks. The key must identify the SEASON and contain nothing the verdict
    itself can move (not the attempt counter — applying it increments that; not a
    timestamp — the store keeps whole seconds).
  * **A panel is a window, and a window clips.** `place()` clamps a panel onto the
    desktop; drawing translated by the origin the CALLER asked for cut off exactly
    the edge that had been hanging off screen.

## HOUSE RULES THAT COST SOMETHING TO LEARN

  * **Read the rendered output, not the test result.** The faults tests cannot see
    are the ones that matter: a letter offering "the Formula 2 season" on the
    Formula 3 rung, "the The eighties season", "a ART Grand Prix seat", a bar
    saying "first is where he needs to finish" when the bar is third. Drive a
    season and print what it files.
  * **A test whose setup makes the answer inevitable is worse than no test.** The
    seat-gate test passed an empty circuit slug, so `match` refused everything and
    three refusal checks passed without testing anything.
  * **A stub that omits a dependency does not prove a refusal.** A probe with
    `career=None` reported "race them once first" and nearly sent the user chasing
    a blocking rule that did not apply to him.
  * **Edit a data file as DATA.** A text substitution over raw JSON injected
    unescaped quotes into string values and broke four suites in one command.
  * **The shell eats backslashes in heredocs.** Build `"\n"` with `chr(92)`, or use
    the Write tool. One lost continuation left a 120-character line in `season.py`
    for two days.
  * **Mel is the one voice with no expertise** and that is her whole job. A fact
    about racing reaches her from a person, never from her own understanding, and
    every letter turns to family before it ends.

## WHAT IS PROBABLY NEXT

1. **He is playing the arc now.** Expect reports. Ask for `_session_log.txt` and
   his `careers/*.json` before theorising.
2. **The next division's arc.** He wants to build one, which is why the design
   document exists. Everything hangs off four triggers — a rung, a programme
   stage, a round number, and a measurement off the standings — so a new path
   needs its own teams, bar and voice, not new machinery. Carry over the discipline
   that every beat is driven by a STAGE rather than a date.
3. **Open question he raised and has not decided:** the 2020 development year has
   no on-track voice at all, because commentary is off in practice and he races
   nothing else. The 2021 opening lines carry it instead. Worth deciding
   deliberately if he wants the year audible.
4. **`careers/` is gitignored.** His live career is repaired and mid-arc; do not
   edit it without asking, and copy it to a temp dir before experimenting.
