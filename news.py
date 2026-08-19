# -*- coding: utf-8 -*-
"""
FACTORtv — the news feed.

THREE FEEDS, AND ONLY ONE OF THEM IS NEW KNOWLEDGE
--------------------------------------------------
1. **MILESTONES.** A maiden win, a first title, a champion adding another.
   These already exist: the booth speaks them from `drivers.standing()` and
   `drivers.just_won_title()`. **This module calls those same functions.** It
   does not look at results and decide for itself what was a milestone —
   because a second detector eventually disagrees with the first, and a
   headline that contradicts what Chuck just said is worse than no headline.
   The viewer will believe the one he can re-read.

2. **HIS OWN SEASON'S DRAMA.** A new championship leader, a lead coming down,
   a man winning most of the rounds. Generated from the career store and TRUE
   BY CONSTRUCTION — no per-season content, and it works identically in
   karting and in Formula One, which is what a ladder needs.

3. **PERIOD CONTROVERSY.** Written per real season and era-gated. It obeys the
   rule that has bitten three times: NEVER NARRATE AN EVENT IN HIS SEASON THAT
   DID NOT HAPPEN. "Hamilton and Verstappen collide at Silverstone" is false if
   they did not, and he can check. So this arrives as PADDOCK CONTEXT — the row
   about the rear wings, the directive on pit stops — which is period-true,
   claims nothing about his races and cannot be contradicted by his standings.

IT SHARES THE INBOX'S MODEL, DELIBERATELY
-----------------------------------------
Same store, same composer, same idempotent ids, same delete. An article is a
message with `feed: "news"`, so everything the inbox already guarantees —
deterministic ids, a missing fact killing the message, deletion that sticks —
is guaranteed here for free rather than reimplemented slightly differently.

WHAT IT WILL NOT DO
-------------------
Invent a driver's record. A GT3 mod's AI has no history anywhere, so a
milestone about him can only be one this career watched happen — which is
exactly what `drivers._career_results` counts. Where there IS a real record
(1988, 2021, 2025) the historical baseline is used, and where there is not,
the feed talks about the season instead of the man.
"""
import json
import os
import sys

import drivers as drivers_mod
import era as era_mod
import inbox

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(_DIR, "lines_data", "news.json")

# Career win totals worth an article. A driver's fourth win is not news; his
# tenth is, and his hundredth is the only thing anybody talks about that
# weekend. Round numbers because that is genuinely how the sport reports it.
TALLY_MARKS = (10, 25, 50, 75, 100, 150)

# Rounds of dominance worth reporting, and the same idea: a third win is a good
# season, a fifth is a pattern, an eighth is a procession.
DOMINANCE_MARKS = (3, 5, 8, 12)

# ...and for a podium every single time out, which is a different story and a
# quieter one.
STREAK_MARKS = (3, 5, 8, 12)

# How close a championship has to get before it is news, as a fraction of a
# win. A lead of less than one victory is a lead that a single afternoon can
# erase, which is the moment a season stops being a procession.
TIGHT_LEAD = 1.0

# Rounds between period pieces. The paddock does not have a controversy every
# fortnight, and a feed that fires one every round reads as filler — which is
# precisely what feed 3 is there to avoid being.
PERIOD_EVERY = 2

# ...and between the "did you know" pieces. Offset from the period cadence so
# the two never land on the same weekend: a feed that publishes everything it
# has at once reads as a feed with nothing to say the rest of the time.
TRIVIA_EVERY = 3

_data = None


def load(force=False):
    global _data
    if _data is None or force:
        try:
            with open(DATA, "r", encoding="utf-8") as f:
                _data = json.load(f)
        except Exception:
            _data = {}
        _data.pop("_comment", None)
    return _data


def kinds():
    return sorted(k for k in load()
                  if k not in ("period", "did_you_know", "news_compare"))


def comparisons():
    """The "they are calling him the next X" pieces.

    ERA-GATED LIKE THE TRIVIA, and for a sharper reason: a 1966 season must
    never be told that somebody is the next Michael Schumacher. Each carries
    `since`, the year the comparison could be made at all.

    WHAT THEY ARE AND ARE NOT. Every one is about what PEOPLE ARE SAYING about
    the player — the mood around a rising driver, which is a real thing a
    paper reports. None of them claims he has equalled anybody, and none of
    them asserts anything new about the great being named: the real driver is
    a yardstick held up by somebody in the paddock, never a subject the feed
    makes a claim about. That is the same line `booth_archive.json` draws.
    """
    return load().get("news_compare") or []


def trivia():
    """The "did you know" pieces — real motorsport history, every one of them.

    Asked for directly, and the reason it is safe is the reason the driver
    records are: these are CHECKABLE. Each carries a `since` year — when the
    fact became true — and is only ever sent to a season at or after it, the
    same discipline a dated circuit fact follows. A 1966 career must never read
    about Group B, and inventing a fact to fill a feed is the one thing this
    product has refused from the first day.
    """
    return load().get("did_you_know") or []


def periods():
    return load().get("period") or {}


def _pool(kind):
    return load().get(kind) or []


def _career_era(career):
    """The era this championship is raced in, from the stored class.

    A career holds a CarClass string, and `era.classify` is the same function
    the live session uses — so a career whose class is "F1 Test 2025" resolves
    to the 2025 season here exactly as it does on track. A ladder rung with no
    matching era simply resolves to nothing, and the feed falls back to facts
    the season itself produced.
    """
    cls = career.data.get("cls") or ""
    if not cls:
        members = career.data.get("cls_any") or []
        cls = members[0] if members else ""
    if not cls:
        return None
    try:
        return era_mod.classify(cls, "")
    except Exception:
        return None


def _series_name(career, era):
    """What to call this championship in print.

    THE RUNG FIRST, because on a ladder that is what he is racing and it is
    the name the FIA wrote on his entry. Then the season's real name for a
    career in a year we hold, since "the 2025 Formula One championship" is
    what a paper would print. The career's own name is the last resort, and
    it is why this exists at all: an open career is called "6-race season",
    which reads perfectly well in a menu and absurdly in a headline.
    """
    tier = (career.evaluate() or {}).get("tier_name")
    if tier:
        # THE LAST TWO RUNGS CARRY THEIR YEAR, in print as on air. The paper
        # and the booth must never disagree about what the championship is
        # called, which is why this reads the same `ladder.named_year` rule
        # rather than a second copy of it.
        try:
            import ladder as ladder_mod
            prog = career.ladder
            yr = ladder_mod.named_year(
                (prog.tier() or {}) if prog is not None else None, era)
        except Exception:
            yr = None
        return ("%d %s" % (yr, tier)) if yr else tier
    label = drivers_mod.label(era) if era is not None else ""
    if label:
        # "the 2025 Formula One season" -> "2025 Formula One", which is what
        # the templates put their own article and noun around.
        return label.replace("the ", "", 1).replace(" season", "")
    # THE CAR CLASS BEFORE THE CAREER'S OWN NAME. An open career is named for
    # its length — "6-race season" — which reads perfectly well in the menu
    # that created it and absurdly in a headline: "the 6-race season
    # championship has three rounds to run". The class is what he is actually
    # racing and is what a paper would call it.
    cls = career.data.get("cls") or ""
    if not cls:
        members = career.data.get("cls_any") or []
        cls = members[0] if members else ""
    return cls or career.name or ""


def _spoken_count(n):
    """Counts in words, because this is prose and not a scoreboard.

    A COUNT AND A ROUND NUMBER ARE DIFFERENT THINGS and the templates keep
    them in different slots. "Round 2" is a label and stays a digit, the way
    every timing screen writes it; "three wins from three rounds" is prose and
    mixing the two — "three wins from 3 rounds" — is the first thing that
    makes a generated article read as generated.
    """
    words = ("zero", "one", "two", "three", "four", "five", "six", "seven",
             "eight", "nine", "ten", "eleven", "twelve", "thirteen",
             "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
             "nineteen", "twenty")
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    return words[n] if 0 <= n < len(words) else str(n)


def _post(career, kind, mid, kw, when=None, rnd=0, variant=0, pool=None):
    """One article, in a wording that varies with the round.

    THE SAME HEADLINE TWICE IS A TEMPLATE. A championship that changes hands
    three times in a season used to produce three identical articles, which is
    how a feed stops being read — and a feed nobody reads cannot do the one job
    it has, which is to make the final article land as news rather than as a
    device. `variant` defaults to the round, and `_compose_any` walks the pool
    so a wording that needs a fact this round does not have is skipped rather
    than dropping the article.
    """
    return inbox._post(career, inbox._compose_any(
        kind, mid, kw, variant=variant or rnd, when=when, rnd=rnd,
        feed="news", pool=pool if pool is not None else _pool(kind)))


def _leader_after(career, n):
    """(name, points) at the top of the table after round n, or (None, 0)."""
    table = career.standings(upto=n)
    return (table[0][0], table[0][1]) if table else (None, 0)


def _gap_after(career, n):
    table = career.standings(upto=n)
    return (table[0][1] - table[1][1]) if len(table) > 1 else None


def refresh(career, era=None, now=None):
    """Generate every article this career has earned. Returns the new ones.

    Idempotent, like `inbox.refresh` and for the same reason — it is called
    after every recorded result and on every draw of the news tab.

    `era` may be passed by a live session, which knows it exactly. Otherwise it
    is derived from the class the career stored.
    """
    if career is None:
        return []
    rounds = sorted(career.rounds, key=lambda r: r.get("n") or 0)
    era = era or _career_era(career)
    series = _series_name(career, era)
    base = "%s:%d" % ((career.evaluate() or {}).get("tier") or "none",
                      len(career.data.get("ladder_history") or []))
    before = len(career.data.get("mail") or [])
    new = []

    # THE SEASON NUMBER GOES INTO THE ROTATION. Without it a run of six-round
    # seasons picks the same wording for the same round every year — the
    # bodies were varied and the SUBJECT LINES were not, and an inbox is a
    # list of subject lines.
    sn = len(career.data.get("ladder_history") or [])

    # ARRIVING IN A DIVISION IS NOT A RESULT, AND IT USED TO NEED ONE.
    #
    # Reported by the user: joining a new division produced no article. The
    # piece existed with five wordings and could not reach him, because
    # `refresh` returned empty for a season with no rounds and the arrival was
    # generated inside the per-round loop — so the paper only noticed the new
    # man AFTER he had raced, which is a week late for "there is a new face on
    # the grid".
    #
    # This is the recurring shape in this project (`simulate_round` looking up
    # a class the first race fills in, `status()` counting archived seasons):
    # A LOOKUP KEYED ON STATE THAT DOES NOT EXIST YET. The arrival is keyed on
    # the RUNG, which exists the moment he is on it, so it belongs outside the
    # loop and above it.
    new += _arrival(career, 1, (rounds[0].get("when") if rounds else None) or now,
                    {"series": series, "round": 1}, base)
    for rnd in rounds:
        n = rnd.get("n") or 0
        when = rnd.get("when") or now
        kw = {"series": series, "round": n}
        new += _champion(career, n, when, kw, base)
        new += _title_fight(career, n, when, kw, base)
        new += _finale(career, n, when, kw, base, sn)
        new += _milestones(career, era, n, when, kw, base)
        new += _drama(career, n, when, kw, base, sn)
        new += _saturday(career, n, when, kw, base)
        new += _form(career, n, when, kw, base, sn)
        new += _retro(career, n, when, kw, base)
        new += _profile(career, era, n, when, kw, base)
        new += _status(career, n, when, kw, base)
        new += _fame(career, era, n, when, kw, base)
        new += _rivalry(career, n, when, kw, base, sn)
        new += _period(career, era, n, when, base)
        new += _trivia(career, era, n, when, base, sn)

    # SIGNING WITH A PROGRAMME IS NEWS, and it was not being reported: "there
    # was no news report about the choosing of the academy i went with". Also
    # outside the loop, because it happens BEFORE round one — a piece that
    # waited for a race would announce the signing after the season had
    # started, which is not how a signing is covered.
    new += _prog_signing(career, when=now)
    # THE CALL-UP IS THE BIGGEST MOVE IN THE ARC and the feed was silent on it.
    # It cannot go through `_arrival`, which fires on round one: a called-up
    # season has its first two rounds already gone as absences, so round one is
    # never new. It also must not reuse `news_arrival_promoted`, which says the
    # seat "was earned on results rather than granted" — true of a promotion and
    # the exact opposite of what happened here.
    new += _prog_callup(career, when=now)

    # THE YEAR OUT. Outside the per-round loop, because there are no rounds
    # in a development year — that is the whole point of it.
    new += _dev_year(career, when=now)

    new = [m for m in new if m]
    if len(career.data.get("mail") or []) != before:
        inbox._trim(career)
        career.save()
    return new


def _arrival(career, n, when, kw, base):
    """A new name on the entry list, and HOW he got there decides the piece.

    Asked for: *"there must also be news reports about 'there's a new face on
    the grid, Dante has joined the Formula 4 series' and then more specific
    ones depending on if I selected or got promoted — choices of words is
    important."*

    HE IS RIGHT THAT THE WORDS ARE THE FEATURE. Arriving in a division is one
    event with five completely different meanings, and a feed that writes "he
    has joined Formula 4" for all of them has not been watching his career:

      debut      nobody has heard of him, and that is the story
      promoted   he earned the seat by finishing high enough. Expected.
      champion   he arrives as the reigning champion of the division below,
                 which is a different arrival entirely - he is watched
      switch     he MISSED the cut and took another path. Not a promotion,
                 and the piece must not congratulate him for it
      newpath    a champion granted a new arc. Curiosity, not expectation

    `advance()` records which of them it was in `arrived_by`, so this reads a
    fact rather than inferring one from the shape of the results — two
    detectors would eventually disagree about whether a man was promoted.

    FIRST ROUND OF A RUNG ONLY, and the id carries the rung, so a career that
    spends four seasons in Formula 3 gets one arrival piece and not four.
    """
    # CALLED ONCE PER RUNG, NOT PER ROUND, and `refresh` is what guarantees it
    # — the id carries the rung, so a career that spends four seasons in
    # Formula 3 still gets one arrival piece. The `n` check stays as a
    # belt-and-braces against a future caller putting it back in a loop.
    if n != 1 or not getattr(career, "on_ladder", False):
        return []
    how = career.data.get("arrived_by")
    r = career.resume() or {}
    prog = career.ladder
    tier = (prog.tier() or {}) if prog is not None else {}
    k = dict(kw, drv=career.me or "", below=r.get("reigning") or "",
             series=kw.get("series") or tier.get("name") or "")
    if not how:
        # No record of an advance: this is where the career began.
        kind = "news_arrival_debut"
    elif how == "promote":
        # THE REIGNING CHAMPION IS A DIFFERENT ARRIVAL. `reigning` is only
        # true while it IS the season just gone, so a man who won Formula 4
        # two rungs ago does not get this.
        kind = ("news_arrival_champion" if r.get("reigning_now")
                and r.get("reigning") else "news_arrival_promoted")
    elif how == "switch":
        kind = "news_arrival_switch"
    elif how == "newpath":
        kind = "news_arrival_newpath"
    else:
        return []
    if kind == "news_arrival_champion" and not k["below"]:
        kind = "news_arrival_promoted"
    return [_post(career, kind, "arrival:%s" % base, k, when=when, rnd=n)]


def _title_fight(career, n, when, kw, base):
    """How the points are shaping the season, and what it may come down to.

    Asked for: *"news reports also talking about how the title fight is
    shaping out and how the points is molding it and what it may possibly
    come down to"*.

    IT READS `title_scenarios()`, WHICH IS THE SAME FUNCTION MILES READS.
    That is the whole reason this is safe to write at all: the arithmetic is
    proven exhaustively against every remaining permutation and returns None
    the moment it cannot be exact, so the paper cannot print a requirement
    the booth would contradict on the day — and cannot print one at all for a
    season that has no declared length.

    FROZEN WHEN SENT (the inbox's first rule). Every figure comes from
    `upto=n`, the table as it stood after THAT round, so the preview of a
    finale still says what was true when it was written even after the finale
    has been run and lost.

    Two pieces, and they are different stories:

    * `news_title_maths` — one round left, and it is now arithmetic. This is
      the piece that says "he needs fifth".
    * `news_title_fight` — the run-in, where it is still a fight rather than
      a sum. It names who can still win it and what stands between them.
    """
    sc = career.title_scenarios(upto=n)
    if not sc or sc.get("decided"):
        return []
    left, me = sc.get("left"), sc.get("me")
    done = (career.total_rounds or 0) - (left or 0)
    rival = sc.get("rival")
    if not rival:
        # Nobody can catch him and it is not yet mathematically over. There
        # is no fight to report, and inventing one is how a feed stops being
        # believed.
        return []
    k = dict(kw, drv=me, rival=rival,
             pts=sc.get("my_points") or 0,
             gap=abs((sc.get("my_points") or 0)
                     - (sc.get("rival_points") or 0)),
             left=left, n=_spoken_count(left))

    # LEVEL IS NOT A LEAD. `{gap}` was technically full and the sentence was
    # still false — "leads Borda by 0 points" about two men who are dead
    # level. LAW 5 is usually about an EMPTY slot; this is the same failure
    # with a slot that is populated and wrong, which is harder to spot and
    # worse to hear.
    if not k["gap"]:
        k.pop("gap", None)

    if left == 1 and sc.get("secure"):
        # A REQUIREMENT THAT SCORES NOTHING IS NOT A REQUIREMENT — the same
        # distinction the booth draws. "He needs to finish twelfth" is a
        # strange sentence when twelfth pays nothing.
        if sc.get("secure_any"):
            return [_post(career, "news_title_finish",
                          "titlemaths:%s:%d" % (base, n), k, when=when, rnd=n)]
        if sc["secure"] == 1:
            # "He needs to finish first or better" is not a sentence anybody
            # says. When the answer is a win, the piece has to be about a win
            # — and it is a genuinely different story from needing fifth: one
            # is a target to manage, the other is a race to go and win.
            return [_post(career, "news_title_win",
                          "titlemaths:%s:%d" % (base, n), k, when=when, rnd=n)]
        k["need"] = _spoken_ordinal(sc["secure"])
        return [_post(career, "news_title_maths",
                      "titlemaths:%s:%d" % (base, n), k, when=when, rnd=n)]

    # THE RUN-IN, AND IT SCALES WITH THE SEASON.
    #
    # The first version of this was `left in (2, 3)` — a fixed window, which
    # gives a six-round season and a twenty-four-round season exactly the same
    # coverage. That is right for the short one and badly wrong for the long
    # one: a championship four months in the building gets three paragraphs
    # about it.
    #
    # So the run-in is the last THIRD of the season, floored at three rounds
    # so a short season still gets a countdown:
    #
    #     6 rounds  -> the last 3      10 rounds -> the last 3
    #     12 rounds -> the last 4      24 rounds -> the last 8
    #
    # AND THEN IT IS PACED, because "reporting the title fight" every round of
    # an eight-round run-in is reporting the table, which is the shape of the
    # season rather than news about it — the exact failure the second
    # repetition pass was written to fix. Alternate rounds, so a long run-in
    # produces three or four pieces rather than eight.
    # A SHORT RUN-IN IS REPORTED EVERY ROUND; A LONG ONE ALTERNATES. Three
    # rounds out, every round genuinely is news. Eight rounds out, it is not,
    # and printing it weekly is the table with a headline on top.
    # ONE ROUND EARLIER THAN THE FIRST VERSION, at the user's call — a
    # championship starts feeling like a countdown before the arithmetic says
    # it should, and the paper is what makes that felt.
    #
    # The alternating case counts DOWN FROM THE START of the run-in rather
    # than off the parity of `left`, so moving the window also moves every
    # piece in it. Anchoring on `left % 2` instead left a long season firing
    # on exactly the same rounds as before, which is the sort of change that
    # looks applied and is not.
    run_in = max(4, (career.total_rounds or 0) // 3 + 1)
    paced = run_in <= 4 or ((run_in - left) % 2) == 0
    if 2 <= left <= run_in and done >= 2 and paced:
        k["chasers"] = _spoken_count(len(sc.get("chasers") or []) or 1)
        return [_post(career, "news_title_fight",
                      "titlefight:%s:%d" % (base, n), k, when=when, rnd=n)]
    return []



def _finale(career, n, when, kw, base, sn):
    """THE LAST RACE OF THE SEASON IS NEWS ON ITS OWN.

    Asked for directly: *"there wasn't a News report before the last race of
    the season to say something like 'This season's last race is upon us'"*.
    He is right that it was missing, and the reason is worth keeping — every
    other piece in this feed reports something that HAS happened, so a season
    with no title fight to write about arrived at its finale in silence.

    IT FIRES WHEN THE PENULTIMATE ROUND IS BANKED, which is the only moment a
    preview can exist: there is no calendar in this product and nothing knows a
    race is coming until the one before it is in the store. So "before the last
    race" means "the afternoon the second-to-last one finished", which is when a
    paper would write it anyway.

    THE ARITHMETIC PIECE WINS IF IT FIRED. `news_title_maths` and its two
    siblings are this same preview with better information in them — what HE
    needs — and two articles about one afternoon is the repetition pass all over
    again. So this defers to them by asking the store whether that id was
    posted, rather than by re-deriving the condition and eventually disagreeing
    with it.

    Three forms, and which one is true is a fact rather than a mood:

      title      the championship can still change hands. Named contenders.
      decided    it cannot. The season has a champion and one race left, and
                 pretending otherwise is the one thing this feed may never do.
      plain      the season length is known but the table cannot support a
                 claim either way — one entrant, or no points scored yet.
    """
    total = career.total_rounds or 0
    # THE ROUND BEFORE THE LAST. A one-round season has no build-up to write.
    if total < 2 or n != total - 1:
        return []
    if any(str(mid).startswith("titlemaths:%s:" % base)
           for mid in (career.data.get("mail_seen") or ())):
        return []
    st = career.title_state(upto=n) or {}
    k = dict(kw, round=total, series=kw.get("series") or "")
    leader, avail = st.get("leader"), st.get("points_available")
    table = st.get("table") or []
    if st.get("decided") and leader:
        k["champ"] = leader
        kind = "news_finale_decided"
    elif leader and avail is not None and len(table) > 1:
        # WHO CAN STILL WIN IT IS COUNTED, NOT ASSERTED (LAW 17). Everybody
        # within the points still on the table, which is exact — and it is the
        # only claim this piece makes about the championship.
        alive = [nm for nm, pts in table if (table[0][1] - pts) <= avail]
        k["leader"] = leader
        k["chasers"] = _spoken_count(max(1, len(alive) - 1))
        gap = table[0][1] - table[1][1]
        if gap:
            # LEVEL IS NOT A LEAD, and a filled slot can still be false — the
            # same trap `_title_fight` documents. A wording that needs a gap is
            # skipped when there is not one.
            k["gap"] = gap
        kind = "news_finale_title"
    else:
        kind = "news_finale"
    # ROTATE ON THE SEASON, NOT ON THE ROUND. `_post` defaults the wording to
    # the round number, and this piece always fires on the SAME round of every
    # season — so a ten-season career read the identical article ten times. The
    # same trap the trivia index and the retrospective's subject line both fell
    # into: a rotation keyed on something that does not vary is not a rotation.
    return [_post(career, kind, "finale:%s" % base, k, when=when, rnd=n,
                  variant=n + sn)]


def _prog_callup(career, when=None):
    """ONE piece when the seat above opens mid-season and he is put in it.

    WHAT IT MAY NOT SAY. He did not earn this on results and he has not won
    anything — he is a mid-season replacement who starts on nothing with two
    rounds already run. The same restraint the letters follow: this is a
    promotion in machinery, not an achievement, and the piece is about a team
    making a change.

    NOBODY IS NAMED. The driver who lost the seat is not identified, because the
    Formula 2 2019 grid is a real one and "dropped for form" is a claim about a
    real person's competence. The story is the vacancy, not the man.
    """
    try:
        import programme as prog_mod
    except Exception:
        return []
    if career.data.get("arrived_by") != "callup":
        return []
    key, block = prog_mod.signed(career)
    if not block:
        return []
    facts = prog_mod.rung_facts(career, prog_mod.F2_KEY)
    k = {"drv": career.me or "",
         "prog": block.get("name", ""),
         "f2team": block.get("f2_team", ""),
         "f3team": block.get("f3_team") or block.get("f2_team", ""),
         "champ": facts.get("champ", ""),
         "year": facts.get("year", ""),
         "car": facts.get("car", ""),
         "series": facts.get("champ", "")}
    return [_post(career, "news_prog_callup", "progcallup:%s" % key, k,
                  when=when)]


def _prog_signing(career, when=None):
    """ONE piece when he signs with a junior programme, before he has raced.

    Asked for: *"also there was no news report about the choosing of the
    academy i went with"* — and he was right, the feed covered his arrival on
    the rung and the seat above it and said nothing about the decision that
    connects them.

    IT IS ABOUT THE PROGRAMME, NOT THE CAR. Everybody on that grid has the same
    machinery, so the story of the signing is whose junior programme now has
    his name on a list, which is exactly the thing the player chose.

    NOTHING IS CLAIMED ABOUT THE DRIVER AHEAD OF HIM. The piece names the
    programme, the team and the championship — all of which are what they are —
    and says nothing about anybody's prospects, including his own.
    """
    try:
        import programme as prog_mod
    except Exception:
        return []
    key, block = prog_mod.signed(career)
    if not block:
        return []
    facts = prog_mod.rung_facts(career, prog_mod.F3_KEY)
    k = {"drv": career.me or "",
         "prog": block.get("name", ""),
         "f3team": block.get("f3_team") or block.get("f2_team", ""),
         "f2team": block.get("f2_team", ""),
         "f1team": block.get("f1_team", ""),
         "champ": facts.get("champ", ""),
         "year": facts.get("year", ""),
         "car": facts.get("car", ""),
         "series": facts.get("champ", "")}
    return [_post(career, "news_prog_signed", "progsigned:%s" % key, k,
                  when=when)]


def _dev_year(career, when=None):
    """ONE piece, looking ahead to the season he is about to start.

    Asked for directly: *"and then 1 news report, all eyes look to the 2021
    season, will the F2 development driver have taken the seat"*.

    ONE, and the number matters. The development year is deliberately quiet —
    it is the part of the story where nothing happens and the player feels it
    — so a feed that files a piece every time he opens his inbox would fill
    the silence the year exists to create.

    It lands LATE in the year rather than at the start of it, because it is a
    look ahead: written when the season is nearly over and the question is
    about to be answered.

    IT CLAIMS NOTHING IT CANNOT KNOW. The seat, the team and the driver he
    will race alongside all come from the programme he actually signed, and
    the piece is careful to be a QUESTION about whether it works out — which
    is the honest thing to write about a season nobody has driven yet.
    """
    try:
        import programme as prog_mod
    except Exception:
        return []
    if prog_mod.state(career) != prog_mod.DEV:
        return []
    read, total = prog_mod.dev_letters(career)
    key, block = prog_mod.signed(career)
    if not block:
        return []
    out = []

    # THE SEAT CHANGING HANDS IS ITS OWN STORY, and it belongs at the START
    # of the year rather than the end: a team announces a driver change when
    # it makes it, and the whole point of the development year is that he
    # then waits.
    #
    # IT IS A CLAIM ABOUT A REAL DRIVER, and the disclaimer is what makes it
    # sayable — the user's own ruling when the needle was built: the mod is a
    # dramatisation, driver RECORDS are real and checkable, everything else
    # about a real person here is invented. So the same restraint applies as
    # to the needle: this is about DRIVING and about a team's judgement of
    # it, never about anybody's character.
    if read and read <= 2:
        k0 = {"drv": career.me or "", "f1team": block.get("f1_team", ""),
              "seat": block.get("f1_seat", ""),
              "lead": block.get("f1_lead", ""),
              "series": block.get("f1_team", "")}
        m = _post(career, "news_seat_taken", "seattaken:%s" % key, k0,
                  when=when)
        if m:
            out.append(m)

    if read < max(1, total - 1):
        return out
    k = {"drv": career.me or "", "f1team": block.get("f1_team", ""),
         "lead": block.get("f1_lead", ""), "seat": block.get("f1_seat", ""),
         "series": block.get("f1_team", "")}
    return out + [_post(career, "news_dev_year", "devyear:%s" % key, k,
                        when=when)]


def _champion(career, n, when, kw, base):
    """THE CHAMPIONSHIP WAS WON, AND THE PAPER SAYS SO.

    The user won the Hot hatch title and no article was ever written about
    it. Two independent reasons, both structural, and this fixes the first:
    `_milestones` — the only feed that could produce a title headline — opens
    with `if era is None: return []`, and an era is only ever resolved for a
    season `drivers.json` holds, which means Formula One in 1988, 2021 or
    2025. So the feed built to announce championships could not announce one
    in ANY division of the ladder the whole product is about.

    THIS NEEDS NO DRIVER KNOWLEDGE AT ALL, which is exactly why it works
    everywhere. The champion is whoever is top of the final table, and that
    table is computed here from races this overlay timed — the same source
    the standings screen reads, so the headline cannot contradict it. That is
    the identical principle feed 2 already runs on, applied to the one result
    that matters most.

    ONLY AT THE END, and only once: a season that has run its full length has
    a final table, so first place in it is a fact rather than a projection
    (LAW 4 needs no help here — there are no rounds left). The id is
    deterministic like every other, so re-reading the tab cannot double it.

    THE PLAYER GETS THE CAREER FRAMING, THE AI DOES NOT. "The first of a
    career" is true of him because this career file counted his titles;
    about an AI it would be invention, and the one thing this product refuses
    is a fact about somebody it cannot check. So an AI champion gets
    `news_champion`, which claims nothing beyond the table.
    """
    if not career.season_done():
        return []
    if n != (career.total_rounds or 0):
        return []
    table = career.standings()
    if not table:
        return []
    who, pts = table[0][0], table[0][1]
    k = dict(kw, drv=who, n=_spoken_count(pts))
    me = career.me or ""
    if who and me and str(who).strip().lower() == str(me).strip().lower():
        # His own title, and the store knows how many he has. `title_count()`
        # includes this one, so "the first of a career" means exactly one.
        kind = ("news_title_first" if career.title_count() <= 1
                else "news_title_more")
    else:
        kind = "news_champion"
    return [_post(career, kind, "champion:%s:%d" % (base, n), k,
                  when=when, rnd=n)]


def _milestones(career, era, n, when, kw, base):
    """Feed 1 — and every one of these comes from the booth's own functions."""
    if era is None:
        return []
    out = []
    rnd = next((r for r in career.rounds if (r.get("n") or 0) == n), None)
    for who, pos in (rnd or {}).get("classified", ()):
        st = drivers_mod.standing(who, era, career, upto=n)
        if st is None:
            # No historical record for this man — most of most grids. A
            # running total is only worth printing when the number it counts
            # from is real, so the season feed talks about him instead.
            continue
        name = st.name
        k = dict(kw, drv=name)
        if drivers_mod.just_won_title(who, era, career, n):
            kind = ("news_title_first" if st.new_champion
                    else "news_title_more")
            out.append(_post(career, kind, "%s:%s:%d" % (kind, base, n), k,
                             when=when, rnd=n))
            continue
        if int(pos) != 1:
            continue
        # A WIN THIS ROUND. Which story it is depends on what he had before it,
        # and `Standing` has already worked that out for the booth.
        if st.first_win and st.season_wins == 1:
            out.append(_post(career, "news_first_win",
                             "news_first_win:%s:%s" % (base, _slug(name)), k,
                             when=when, rnd=n))
        elif st.wins in TALLY_MARKS:
            k = dict(k, n=_spoken_count(st.wins))
            out.append(_post(career, "news_win_tally",
                             "news_win_tally:%s:%d" % (_slug(name), st.wins),
                             k, when=when, rnd=n))
    return out


def _drama(career, n, when, kw, base, sn=0):
    """Feed 2 — the season's own story, and none of it needs any knowledge."""
    out = []
    leader, pts = _leader_after(career, n)
    if not leader:
        return out
    prev, _ = _leader_after(career, n - 1) if n > 1 else (None, 0)

    # A NEW MAN AT THE TOP. Only from round two — somebody leads after round
    # one by definition, and calling that a change is how a feed loses trust
    # in its first week.
    if n > 1 and prev and leader != prev:
        out.append(_post(career, "news_lead_change",
                         "news_lead_change:%s:%d" % (base, n),
                         dict(kw, drv=leader, pts=pts), when=when, rnd=n,
                         variant=n * 2 + sn))

    # A LEAD COMING DOWN. Both halves are required: it has to be close AND to
    # have got closer. A gap that has been small all season is the shape of the
    # championship, not news about it.
    gap = _gap_after(career, n)
    was = _gap_after(career, n - 1) if n > 1 else None
    win = career.points_for(1) or 25
    if (gap is not None and was is not None and gap < was
            and 0 < gap <= win * TIGHT_LEAD):
        out.append(_post(career, "news_lead_gap",
                         "news_lead_gap:%s:%d" % (base, n),
                         dict(kw, pts=gap), when=when, rnd=n,
                         variant=n * 2 + sn))

    # DOMINANCE, and a PODIUM EVERY TIME OUT — counted from the classifications
    # the championship itself is built from, so they cannot disagree with the
    # standings screen.
    wins, podiums = {}, {}
    done = 0
    for r in sorted(career.rounds, key=lambda r: r.get("n") or 0):
        if (r.get("n") or 0) > n:
            break
        done += 1
        for who, pos in r.get("classified", ()):
            if int(pos) == 1:
                wins[who] = wins.get(who, 0) + 1
            if int(pos) <= 3:
                podiums[who] = podiums.get(who, 0) + 1
    for who, count in sorted(wins.items()):
        if count in DOMINANCE_MARKS and count >= done * 0.6:
            out.append(_post(career, "news_dominance",
                             "news_dominance:%s:%s:%d" % (base, _slug(who),
                                                          count),
                             dict(kw, drv=who, n=_spoken_count(count),
                                  of=_spoken_count(done)), when=when, rnd=n,
                             variant=count + sn))
    # ONE STREAK STORY PER MARK, NOT ONE PER DRIVER. Early in a season three
    # men can all have perfect records, and publishing three near-identical
    # articles on the same afternoon is exactly the repetition that stops a
    # feed being read. THE PLAYER FIRST when he is one of them, because it is
    # his career this feed exists to narrate; otherwise the championship
    # leader, who is the one it means most about.
    perfect = [w for w, c in podiums.items() if c == done and c in STREAK_MARKS]
    if perfect:
        who = (career.me if career.me in perfect
               else (leader if leader in perfect else sorted(perfect)[0]))
        out.append(_post(career, "news_streak_podium",
                         "news_streak_podium:%s:%s:%d"
                         % (base, _slug(who), done),
                         dict(kw, drv=who, of=_spoken_count(done)),
                         when=when, rnd=n, variant=done + sn))
    return out


def _status(career, n, when, kw, base):
    """A headline when the sport's name for him changes.

    Rookie to riser to contender to champion to legend — the arc the user
    asked for, and the one thing a player who has ground his way up four
    divisions actually wants to see written down.

    IT READS THE SAME `status_changed()` THE BOOTH DOES, which both marks the
    change and refuses to report it twice. Two detectors would eventually
    disagree about when a man became a champion, and the paper would be
    arguing with Chuck about the afternoon the viewer just watched.

    ONLY UPWARDS, and only on the LAST round it could have happened — the
    status is read after the season's results are in, so this fires when the
    career state actually moved rather than on a schedule.
    """
    if not getattr(career, "on_ladder", False):
        return []
    # ONLY ON THE ROUND THE RISE ACTUALLY HAPPENED — which is the latest one
    # in the file, because the status is read as it stands NOW.
    #
    # `refresh()` walks every round from the first, and `status_changed()`
    # answers about the present, so the champion headline was being filed
    # against round ONE: an archive in which the driver became champion
    # before he had raced twice. Nothing about the article was wrong except
    # its date, which is the sort of thing a reader notices immediately and
    # cannot unsee.
    last = max((r.get("n") or 0) for r in career.rounds) if career.rounds else 0
    if n != last:
        return []
    risen = career.status_changed()
    if not risen:
        return []
    key, _label = risen
    kind = {"riser": "news_status_riser",
            "contender": "news_status_contender",
            "champion": "news_status_champion",
            "multi": "news_status_multi",
            "legend": "news_status_legend"}.get(key)
    if not kind:
        return []
    r = career.resume() or {}
    k = dict(kw, drv=career.me or "",
             below=r.get("reigning") or _last_division(career),
             titles=_spoken_count(r.get("title_count") or 0))
    return [_post(career, kind, "status:%s:%s" % (base, key), k,
                  when=when, rnd=n)]


# How many races after a status rise the colour pieces may follow. They are
# ABOUT the rise, so they have to arrive in its wake rather than in the same
# breath — a paper does not run the result and the profile on the same page.
FAME_AFTER = 2


def _fame(career, era, n, when, kw, base):
    """Life outside the car, and what the paddock is calling him.

    THE CURATED HALF of the rise. The status headlines say what happened; these
    say what it is like — the photographs that have nothing to do with racing,
    the queue at the merchandise stand, somebody saying a name out loud that a
    young driver has not earned yet.

    Gated on being SOMEBODY (contender and up) and on a rise having actually
    happened, so a driver who is still in karting is never told he is popular
    with anybody.
    """
    if not getattr(career, "on_ladder", False):
        return []
    st = (career.status() or ("", ""))[0]
    if st not in ("contender", "champion", "multi", "legend"):
        return []
    # ...AND IT HAS TO HAVE HAPPENED SOMEWHERE PEOPLE WERE WATCHING.
    #
    # A title alone is not fame. Winning the karting championship makes a
    # driver a champion — correctly, and the arc should say so — but nobody
    # outside that paddock has heard of him, and "his name is being said out
    # loud now" about a grassroots champion is the kind of wrongness that
    # makes a whole feed silly.
    #
    # This gate only became reachable when `status()` started counting the
    # season a driver is standing in: before that a karting champion stayed a
    # rookie until he had been promoted out of karting, so the register
    # filtered itself by accident. It is explicit now because the accident is
    # gone.
    prog = career.ladder
    tier = (prog.tier() or {}) if prog is not None else {}
    if tier.get("register") in ("grassroots", "archive"):
        return []
    risen_at = career.data.get("status_round") or 0
    if not risen_at:
        # First time we have seen him at this level: remember when, and say
        # nothing yet.
        career.data["status_round"] = n
        career.save()
        return []
    if n - risen_at != FAME_AFTER:
        return []
    out = []
    sn = len(career.data.get("ladder_history") or [])
    k = dict(kw, drv=career.me or "")
    out.append(_post(career, "news_fame", "fame:%s:%d" % (base, n), k,
                     when=when, rnd=n, variant=n + sn))
    # AND A COMPARISON, if we can date the season well enough to know which
    # names existed. No era, no comparison — the same refusal the trivia makes.
    year = None
    if era is not None:
        year = drivers_mod.season_of(era) or getattr(era, "year", None)
    if year:
        pool = [c for c in comparisons()
                if int(c.get("since") or 0) <= int(year)]
        if pool:
            i = (n + sn) % len(pool)
            out.append(_post(career, "news_compare",
                             "compare:%s:%d" % (base, n), k, when=when, rnd=n,
                             pool=[pool[i]]))
    return [m for m in out if m]


# How long a rivalry has to have been REPORTED before anybody is quoted about
# it. The facts come first and the needle follows, which is the order a real
# paper works in — and it means the spiky piece lands on a rivalry the reader
# has already been shown, rather than announcing one.
NEEDLE_AFTER = 2

# ...and how often it may run after that, plus a hard cap per season. A rivalry
# lasts a whole championship, and a piece that fired every round would exhaust
# every wording in the file inside one season and then start again — which is
# how a feature the user was excited about becomes the thing he skims.
#
# A paper does not run the same two men bickering every fortnight either. It
# runs it when something happens.
NEEDLE_EVERY = 3
NEEDLE_MAX = 2


def _rivalry(career, n, when, kw, base, sn):
    """The fight this season is actually about, and the noise around it.

    ONE DETECTOR, THREE RENDERINGS. `Career.rivals()` is the only thing that
    decides a rivalry exists — the same object the booth reads — so the paper,
    the commentary and the standings can never disagree about who is fighting
    whom. Two detectors would eventually produce a headline about a rivalry
    Chuck has never mentioned.
    """
    riv = career.rivals(upto=n)
    if not riv:
        return []
    out = []
    a, b = riv["a"], riv["b"]
    k = dict(kw, a=a, b=b, pts=riv["points"], n=riv["rounds"])
    # LEVEL IS NOT A GAP. "Separated by 0 points" is a sentence with a
    # populated slot and a false statement in it — the same failure the title
    # pieces have, and it only started happening here when the rivalry
    # detector became a STANDINGS rule: two men who are exactly level are now
    # a common answer, where the old on-the-road rule almost never produced
    # one. `_compose_any` walks the variants, so dropping the key makes it
    # choose a wording that does not need a number rather than dropping the
    # article.
    if not k["pts"]:
        k.pop("pts", None)
    kind = "news_rivalry" if riv["player"] else "news_rivalry_ai"
    m = _post(career, kind, "rivalry:%s:%s" % (base, _slug(a + b)), k,
              when=when, rnd=n, variant=n + sn)
    if m:
        out.append(m)
        career.data["rivalry_at"] = n
        career.data["needle_count"] = 0
        return out
    # ...AND THEN THE NEEDLE, once the fight has been on the page for a while.
    since = int(career.data.get("rivalry_at") or 0)
    gap = n - since
    if since and gap >= NEEDLE_AFTER and gap % NEEDLE_EVERY == 0:
        told = int(career.data.get("needle_count") or 0)
        if told < NEEDLE_MAX:
            m = _post(career, "news_needle",
                      "needle:%s:%s:%d" % (base, _slug(a + b), n), k,
                      when=when, rnd=n, variant=n + sn)
            if m:
                career.data["needle_count"] = told + 1
                out.append(m)
    return [m for m in out if m]


def _last_division(career):
    """The division he came up from, for a headline that names it."""
    hist = career.data.get("ladder_history") or []
    return hist[-1].get("name", "") if hist else ""


def _saturday(career, n, when, kw, base):
    """A qualifying story, from the qualifying results the career records.

    THE ONLY DRIVER WE HAVE SATURDAY DATA FOR IS THE PLAYER — `record_quali`
    stores his grid slot and the size of the field, and shared memory is long
    gone by the time this runs for anybody else. That is not a limitation
    worth apologising for: a feed that occasionally writes about HIS Saturday
    is a feed about his career, which is what this is.
    """
    q = career.quali_result(n)
    if not q or not q.get("pos"):
        return []
    pos, field = int(q["pos"]), int(q.get("field") or 0)
    who = career.me or ""
    if not who:
        return []
    if pos == 1:
        return [_post(career, "news_quali_pole", "quali:%s" % base,
                      dict(kw, drv=who), when=when, rnd=n, variant=n)]
    # A FRONT ROW IS NEWS, THE THIRD ROW IS NOT — and in a small field even
    # second is not, because half a grid of six is not an achievement.
    if pos <= 2 and field >= 6:
        return [_post(career, "news_quali_row", "quali:%s" % base,
                      dict(kw, drv=who, pos=_spoken_ordinal(pos)),
                      when=when, rnd=n, variant=n)]
    return []


def _form(career, n, when, kw, base, sn):
    """Somebody in the middle of a run, and somebody climbing out of a hole.

    Both are read off the last four rounds, which is what a paper would do,
    and both are about the RECENT past rather than the season total — the
    standings already say who is winning and a feed that only reports the
    standings has nothing to add.
    """
    out = []
    rounds = [r for r in sorted(career.rounds, key=lambda r: r.get("n") or 0)
              if (r.get("n") or 0) <= n]
    if len(rounds) < 4 or n % 2:
        return out
    window = rounds[-4:]
    pod = {}
    for r in window:
        for who, pos in r.get("classified", ()):
            if int(pos) <= 3:
                pod[who] = pod.get(who, 0) + 1
    leader, _pts = _leader_after(career, n)
    # NOT THE MAN WHO IS ALREADY WINNING. "The championship leader has been
    # quick lately" is not a story, it is the table read out loud.
    runs = sorted((c, w) for w, c in pod.items()
                  if c >= 3 and w != leader)
    if runs:
        count, who = runs[-1]
        out.append(_post(career, "news_form",
                         "form:%s:%s:%d" % (base, _slug(who), n),
                         dict(kw, drv=who, n=_spoken_count(count)),
                         when=when, rnd=n, variant=n + sn))
    # A RECOVERY: somebody who has climbed at least three places in the table
    # since the early rounds. The most-overlooked story in racing, because the
    # highlights only ever show the front.
    early = min(3, len(rounds))
    then = [nm for nm, _ in career.standings(upto=early)]
    now_t = [nm for nm, _ in career.standings(upto=n)]
    for who in now_t[:6]:
        if who in then:
            gain = then.index(who) - now_t.index(who)
            if gain >= 3 and who != leader:
                out.append(_post(career, "news_climb",
                                 "climb:%s:%s" % (base, _slug(who)),
                                 dict(kw, drv=who,
                                      pos=_spoken_ordinal(now_t.index(who) + 1)),
                                 when=when, rnd=n, variant=n + sn))
                break
    return out


def _retro(career, n, when, kw, base):
    """A look back, once, at the midpoint of a season.

    Asked for directly — "reports from older races that happened". A feed that
    only ever reports the last result has no memory, and a sport without a
    memory is a scoreboard.
    """
    total = career.total_rounds
    if not total or n != max(2, total // 2):
        return []
    leader, pts = _leader_after(career, n)
    if not leader:
        return []
    return [_post(career, "news_retro", "retro:%s" % base,
                  dict(kw, drv=leader, pts=pts, round=n), when=when, rnd=n,
                  variant=len(career.data.get("ladder_history") or []))]


def _profile(career, era, n, when, kw, base):
    """A piece about a driver's real record — the booth's own knowledge.

    Uses `drivers.standing()`, which is the same source the commentary quotes,
    so the paper and the booth can never disagree about who somebody is. A
    driver we hold no record for produces NOTHING: the alternative is inventing
    a career for a GT3 mod's AI, which is the one thing this product refuses.
    """
    if era is None or n % 4:
        return []
    rnd = next((r for r in career.rounds if (r.get("n") or 0) == n), None)
    for who, _pos in (rnd or {}).get("classified", ()):
        st = drivers_mod.standing(who, era, career, upto=n)
        if st is None or not st.note:
            continue
        return [_post(career, "news_profile",
                      "profile:%s:%s" % (base, _slug(st.name)),
                      dict(kw, drv=st.name, note=st.note), when=when, rnd=n)]
    return []


def _spoken_ordinal(n):
    """A finishing position, written the way prose writes it.

    IT USED TO STOP AT SIXTH and fall back to "7th", which is the exact tell
    that makes a generated article read as generated — "the number he has to
    remember is 7th" in the middle of a paragraph of English. A round number
    is a label and stays a digit ("Round 2"); a POSITION in a sentence is
    prose and is written out. Same rule, other half.
    """
    words = ("", "first", "second", "third", "fourth", "fifth", "sixth",
             "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth",
             "thirteenth", "fourteenth", "fifteenth", "sixteenth",
             "seventeenth", "eighteenth", "nineteenth", "twentieth")
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    return words[n] if 0 < n < len(words) else "%dth" % n


def _period(career, era, n, when, base):
    """Feed 3 — period context, one piece at a time and never about him."""
    if era is None or n % PERIOD_EVERY:
        return []
    year = drivers_mod.season_of(era)
    pool = periods().get(str(year or ""))
    if not pool:
        return []
    i = (n // PERIOD_EVERY) - 1
    if not 0 <= i < len(pool):
        return []
    return [_post(career, "period", "period:%s:%s:%d" % (base, year, i), {},
                  when=when, rnd=n, pool=[pool[i]])]


def _trivia(career, era, n, when, base, sn=0):
    """A piece of real history, on the rounds nothing else fills.

    ERA-GATED: it needs a season we can date, and a season at least as late as
    the fact. No era, no trivia — the right refusal rather than a missing
    feature, and the same one the period pieces make.
    """
    if n % TRIVIA_EVERY or era is None:
        return []
    year = drivers_mod.season_of(era) or getattr(era, "year", None)
    if not year:
        return []
    pool = [t for t in trivia() if int(t.get("since") or 0) <= int(year)]
    if not pool:
        return []
    # THE SEASON ADVANCES IT. Without this a six-round season can only ever
    # reach the first two facts, and reads the same two every year for a
    # decade — which is the exact repetition this feed was rebuilt to remove.
    i = ((n // TRIVIA_EVERY) - 1 + sn * 2) % len(pool)
    return [_post(career, "did_you_know", "trivia:%s:%d" % (base, n), {},
                  when=when, rnd=n, pool=[pool[i]])]


def _slug(name):
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())[:18]


def validate():
    """Same shape rules the mail obeys — it is the same reader."""
    errs = []
    pools = dict((k, _pool(k)) for k in kinds())
    for year, items in periods().items():
        pools["period %s" % year] = items
    for i, t in enumerate(comparisons()):
        pools["news_compare[%d]" % i] = [t]
        if not t.get("since"):
            errs.append("news_compare[%d]: no `since` year — a 1966 season "
                        "must never hear about a driver who did not exist yet"
                        % i)
    for i, t in enumerate(trivia()):
        pools["did_you_know[%d]" % i] = [t]
        if not t.get("since"):
            errs.append("did_you_know[%d]: no `since` year — an undated fact "
                        "can reach a season it was not true in" % i)
    for kind, pool in pools.items():
        if not pool:
            errs.append("%s: no variants" % kind)
        for i, tpl in enumerate(pool):
            where = "%s[%d]" % (kind, i)
            for field in ("from", "subject", "body"):
                if not tpl.get(field):
                    errs.append("%s: missing %s" % (where, field))
            body = tpl.get("body") or []
            if len(body) < 2:
                errs.append("%s: %d paragraph(s), wanted at least 2"
                            % (where, len(body)))
            words = sum(len(p.split()) for p in body)
            if not 60 <= words <= 220:
                errs.append("%s: %d words" % (where, words))
            # A PERIOD PIECE MAY NOT MENTION THE DRIVER OR HIS SEASON. It is
            # context about the sport that year, and the moment it takes a slot
            # it has started making claims about a championship it knows
            # nothing about.
            if kind.startswith("period") and "{" in " ".join(
                    body + [tpl.get("subject", "")]):
                errs.append("%s: a period piece must not take a slot" % where)
    return errs


if __name__ == "__main__":
    bad = validate()
    print("%d milestone/drama kinds, %d period seasons (%d pieces)"
          % (len(kinds()), len(periods()),
             sum(len(v) for v in periods().values())))
    for k in kinds():
        print("  %-20s %d variant(s)" % (k, len(_pool(k))))
    for y, v in sorted(periods().items()):
        print("  period %-13s %d pieces" % (y, len(v)))
    print("validate: %s" % ("OK" if not bad else "\n  " + "\n  ".join(bad)))
