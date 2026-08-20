# -*- coding: utf-8 -*-
"""
FACTORtv — the personal story.

WHAT IT IS
----------
A subtle overarching narrative that needs almost no lore to work. A driver
whose parents never believed in him; a sibling who writes now and then, warm
and awkward and mostly about nothing; a father who is ill and getting worse
across a career the driver is spending somewhere else. Near the end, one email
offers a chance to go and see him. Taking it costs a round of a championship he
is fighting for. Not taking it is also a choice.

It is told ENTIRELY through the inbox, it rides on machinery that already had a
reason to exist, and there is no story mode bolted on the side.

THE FIVE RULES IT IS BUILT ON
----------------------------
1. **THE CHOICE MUST COST A ROUND.** A free choice is not one. `season.
   record_absence()` simulates the race he misses so his rivals actually score,
   because a round where nobody scores leaves the standings exactly as they
   were and the dilemma is theatre.

2. **INDIFFERENCE, NOT MOCKERY.** The failure article does not make fun of a
   dying man. A cruel paper gives the player somewhere to put the feeling; a
   world that simply does not know who he was does not. It is a death notice
   compiled from a register, and it never mentions his championship.

3. **MISSABLE FAIRLY.** The personal mail looks EXACTLY like admin mail for the
   whole career — no badge, no colour, no ceremony — which is the mechanism:
   by the time the important one arrives the player has been trained by a
   hundred licensing statements to skim. The offer stays answerable for a round
   or two and then quietly does not.

4. **THE BOOTH NEVER KNOWS.** Nothing here is ever spoken. Miles and Chuck are
   not in on it. The only point where the two worlds touch is the final
   article, which is exactly why it works.

5. **PER CAREER, AND IT NEVER RE-FIRES.** State lives in the career file beside
   the ladder progress, so a fresh career genuinely replays it.

PACING
------
Beats key off RACES RUN and ARCS WON, never off a percentage: Touring has three
rungs and Single-Seater has five, so "90% through" is two very different
amounts of playing. The last beats and the offer are gated to the THIRD arc —
the user's own design, and the thesis of the whole thing: one championship is a
season or two, and this is a story about a man who gave the sport years.

THE ENDING IS FOUR MESSAGES AND NO MORE
---------------------------------------
Team principal, race engineer, a generated profile of the new champion, and the
article about his father. An ending that keeps going stops being an ending. The
four ENDINGS are the matrix — took the trip or did not, won the final title or
did not — and the sporting half is worded for which of those actually happened.
The profile only exists if he won it: sending "the newest champion" to a man who
finished second is the wrongness this product has spent months eliminating.
"""
import json
import os
import sys
import time

import inbox
import ladder as ladder_mod

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(_DIR, "lines_data", "personal.json")

# AT MOST ONE LETTER PER SEASON, and never in the opening rounds of one.
#
# The first version counted RACES, and the user's verdict after reading a whole
# career was that she had become "way too involved — basically sending an email
# at the end of every race". He is right and the cause is structural: a race
# counter knows nothing about the shape of a career, so it fires hardest
# exactly where the races are densest.
#
# A sibling writes a few times a year. The season is the unit she thinks in,
# because it is the unit HIS life is organised around, and she is writing to
# fit around it.
BEAT_ROUND = 2          # not before this round of a season — she leaves him be
FINAL_SEASON_BEATS = 3  # the run-in, where the thread has to finish

# Beats that may only arrive once he is on his third arc — the ones where the
# careful language starts. Reaching them early would tell the story to a man
# who has been racing for one season, and the timescale IS the story.
LATE_BEATS = 2

# How many recorded rounds the offer stays answerable for. Rule 3: it does not
# expire with a warning, a countdown or a colour. It simply stops being
# something he can do, the way it would.
OFFER_WINDOW = 2

# The offer needs a season with something left to lose. Fewer rounds remaining
# than this and missing one is not a sacrifice, it is a formality.
OFFER_MIN_LEFT = 2

# Races between the letters that come AFTER it is over. Far slower than the
# story was, because she is getting on with her life rather than reporting to
# him — and because a grief that files a weekly update is not a grief.
EPILOGUE_EVERY = 6

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


def beats():
    return load().get("beats") or []


def _pool(kind):
    return load().get(kind) or []


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------
def state(career):
    """The story's own state, stored beside the ladder in the career file."""
    return career.data.setdefault("story", {
        "beat": 0,          # how many beats have been sent
        "at_race": 0,       # the career race count when the last one was
        "offer": 0,         # the race count when the offer went out, 0 = never
        "answer": "",       # "yes", "no", or "" while it is still open
        "missed": 0,        # the round he did not attend, 0 = none
        "ended": 0,         # when the sporting half of the ending was sent
        "closed": 0,        # ...and when the article about his father was
    })


def races_run(career):
    """Every race of this career, including the seasons already archived."""
    return (sum(h.get("rounds") or 0
                for h in (career.data.get("ladder_history") or []))
            + len(career.rounds))


def _final_arc(career):
    """Is he on the third arc — the one the ending belongs to?"""
    return career.arcs_won >= ladder_mod.ENDING_ARCS - 1


def _at_the_top(career):
    p = career.ladder
    return bool(p is not None and p.at_top())


def rounds_left(career):
    total = career.total_rounds
    return max(0, total - len(career.rounds)) if total else 0


# ---------------------------------------------------------------------------
# the thread
# ---------------------------------------------------------------------------
def refresh(career, now=None):
    """Send anything the story has earned. Returns the new messages.

    Idempotent like everything else in the inbox — ids are deterministic and
    `mail_seen` remembers them — so this runs on every menu draw and after
    every recorded result without ever repeating itself.
    """
    if career is None or not career.on_ladder:
        # THE STORY BELONGS TO A CAREER THAT CLIMBS. An open season with no
        # path has no third arc, no ending, and no timescale for a man to lose
        # a decade to.
        return []
    st = state(career)
    now = now or time.time()
    out = []
    out += _beats(career, st, now)
    out += _milestones(career, st, now)
    out += _offer(career, st, now)
    out += _ending(career, st, now)
    out += _epilogue(career, st, now)
    out = [m for m in out if m]
    if out:
        inbox._trim(career)
        career.save()
    return out


def _post(career, kind, mid, when, pool=None, body=None, subject=None,
          sender=None, kw=None):
    """Compose through the inbox so a beat is indistinguishable from a
    licensing statement — same shape, same renderer, same archive.

    `kw` is almost always empty and that is the point: she writes about him, not
    about his results, and a letter full of slots would be a scoreboard from
    somebody who does not read them. The exception is a championship — she is
    told WHICH one, because "you've won the whole thing" is how it sounded in a
    pub and is not something the product should leave a reader to guess at.
    """
    if body is not None:
        tpl = [{"from": sender or "", "subject": subject or "",
                "body": list(body)}]
    else:
        tpl = pool if pool is not None else _pool(kind)
    return inbox._post(career, inbox._compose(
        kind, mid, kw or {}, when=when,
        feed=("news" if kind.startswith("ending_") else "mail"), pool=tpl))


def _season_no(career):
    """Which season of the career this is — the unit she writes in."""
    return len(career.data.get("ladder_history") or [])



# THE DEVELOPMENT YEAR. Two letters across it, paced against the programme's
# own beats — the only clock a year with no racing has. Two rather than one
# because she has more reason to write, and rather than four because the year
# is the quiet part of the story and should read like it.
DEV_YEAR_BEATS = 2
DEV_YEAR_EVERY = 2


def _in_dev_year(career):
    """Is he serving the development year right now?"""
    try:
        import programme as prog_mod
        return prog_mod.state(career) == prog_mod.DEV
    except Exception:
        return False


def _beats(career, st, now):
    """The sibling's letters, in order, ONE PER SEASON.

    THE SEASON IS THE UNIT, NOT THE RACE. The first version counted races, and
    after reading a whole career the user's verdict was that she had become
    "way too involved — basically sending an email at the end of every race".
    The cause is structural: a race counter knows nothing about the shape of a
    career, so it fires hardest exactly where the races are densest. Somebody
    who loves you and has a job of her own writes a few times a year, around
    the thing your life is organised by.

    Two exceptions, and both are the story rather than the schedule:

      * THE FINAL SEASON gets up to `FINAL_SEASON_BEATS`, spread out, because
        the thread has to finish before the offer can be made — and because
        somebody getting worse is written about more often.
      * THE LAST FEW BEATS STILL WAIT FOR THE THIRD ARC. The illness worsening
        has to happen across years of his life, not across one good season.
      * MILESTONES do not touch this count at all; they are events.
    """
    i = int(st.get("beat") or 0)
    all_beats = beats()
    if i >= len(all_beats):
        return []
    if i >= len(all_beats) - LATE_BEATS and not _final_arc(career):
        return []
    # THE GAP YEAR IS HERS.
    #
    # The thread paces on SEASONS, so a development year — no races, no
    # rounds, no season number moving — would stall it exactly where a real
    # sibling would write MORE: he is not racing, so for the first time in
    # years he is around.
    #
    # AND IT IS THE BEST THING THAT COULD HAVE HAPPENED TO THIS STORY. The
    # whole thesis is a man who took his obsession to the limit and had no
    # time for his family. A year with nothing to do, and he still does not
    # go home, says that far better than another letter sent between rounds.
    #
    # Paced on the development letters instead of on rounds, because those
    # are the only clock the year has.
    if _in_dev_year(career):
        seen = int(st.get("dev_beats") or 0)
        try:
            import programme as prog_mod
            read, _total = prog_mod.dev_letters(career)
        except Exception:
            return []
        dev = load().get("dev_beats") or []
        if not dev:
            return []
        if seen >= min(DEV_YEAR_BEATS, len(dev)):
            return []
        if read <= seen * DEV_YEAR_EVERY:
            return []
        # HER OWN LETTERS FOR THE YEAR, not the next one off the ordinary
        # thread. She has a different question during a season he is not
        # racing — what he actually does all day — and spending an ordinary
        # beat here would both waste it and read as though nothing had
        # changed. They do NOT consume a beat: the main thread picks up
        # exactly where it left off when he is back in a car.
        #
        # POSTED, NOT RETURNED. The first version handed the raw template
        # back to `refresh`, which counted it as sent and never wrote it to
        # the archive — so `_beats` reported two letters that did not exist
        # and the year was silent. Everything in this module goes through
        # `_post` so a beat is indistinguishable from a licensing statement,
        # which is the mechanism the whole ending depends on.
        m = _post(career, "beat", "beat:dev:%d" % seen, now, pool=[dev[seen]])
        if m is None:
            return []
        st["dev_beats"] = seen + 1
        return [m]

    rounds_done = len(career.rounds)
    if rounds_done < BEAT_ROUND:
        # Not in the first weekend of a new season. She knows what he is like
        # at the start of one.
        return []
    season = _season_no(career)
    sent = int(st.get("season_beats") or 0)
    if st.get("beat_season") != season:
        sent = 0
    left = len(all_beats) - i
    last_season = _final_arc(career) and _at_the_top(career)
    # THE LAST LETTER OUTRANKS THE SCHEDULE, so it is worked out HERE, above
    # the per-season budget and the spacing rule, and not below them. Both of
    # those can be spent: a final season that has already had its letters — a
    # fixed ten-round finale reached with the thread three notes short — would
    # return empty before ever looking at the rule that exists to rescue it,
    # and the offer waits on the thread. Ordinary letters are texture. The last
    # one is the story, and it is allowed to break the cadence to arrive.
    lastgasp = (last_season and i < len(all_beats) - 1
                and rounds_left(career) <= OFFER_MIN_LEFT + 1)
    # ONE A SEASON, TWO ONCE THE THIRD ARC STARTS, AND WHATEVER IS LEFT IN THE
    # LAST ONE. The cadence cannot simply be "one per season": thirteen beats
    # would then need thirteen seasons, the thread would still be arriving when
    # the career ended, and the offer — which waits for it — would never come.
    # So it loosens as the story tightens, which is also how it reads.
    allowed = left if last_season else (2 if _final_arc(career) else 1)
    if sent >= allowed and not lastgasp:
        return []
    if sent and not lastgasp:
        # Spread whatever a season is allowed ACROSS that season, so the
        # loosening never turns into three letters in a fortnight. The final
        # season aims to be done by the time the offer needs to go out.
        total = career.total_rounds or 6
        room = max(1, total - (OFFER_MIN_LEFT if last_season else 0))
        gap = max(1, room // max(1, allowed))
        if rounds_done - int(st.get("beat_round") or 0) < gap:
            return []
    # THE SEASON IS RUNNING OUT AND THE THREAD IS NOT FINISHED. Skip to the
    # last letter — the one where the language turns careful — because the
    # offer waits for it and a story that never reaches its own choice is a
    # worse failure than a couple of unsent notes about a boiler.
    #
    # This is the one place the schedule is allowed to lose content, and it
    # loses the RIGHT content: the ordinary letters are texture, the last one
    # is the story.
    if lastgasp:
        i = len(all_beats) - 1
    m = _post(career, "beat", "beat:%d" % i, now, pool=[all_beats[i]])
    if m is None:
        return []
    st["beat"] = i + 1
    st["beat_season"] = season
    st["season_beats"] = sent + 1
    st["beat_round"] = rounds_done
    st["at_race"] = races_run(career)
    return [m]


def _milestones(career, st, now):
    """She writes when something big happens, not only on a timer.

    The user's note, and he was right: *"she should also be aware enough to
    write after the biggest milestones — first karting championship win, then
    first final championship win."* A sibling who sends a letter about a boiler
    the week you won your first championship is not a sibling, she is a
    schedule. These fire off the SAME facts the rest of the product uses —
    `evaluate()` for the arc, the standings for the title — so she can never
    congratulate him on something that did not happen.

    They do not consume a beat. The ordinary thread keeps its own pace, and
    these land on top of it, which is exactly how it works when somebody you
    love is having a year.
    """
    out = []
    ev = career.evaluate() or {}
    done = st.setdefault("marks", [])
    # HIS FIRST CHAMPIONSHIP OF ANY KIND. Not the biggest one he will ever win
    # and by a distance the one that mattered most at the time.
    won = [h for h in (career.data.get("ladder_history") or [])
           if h.get("pos") == 1]
    if won and "first_title" not in done:
        done.append("first_title")
        # SHE NAMES IT, because he read her letter next to a dashboard that said
        # Formula One and could not tell what she thought he had won. Her voice
        # does not change: the division arrives secondhand, from the man in the
        # pub, which is exactly how she would have heard it.
        out.append(_post(career, "milestone_first_title",
                         "milestone:first_title", now,
                         kw={"won": (won[-1].get("name") or "")}))
    if len(won) > 1 and "promoted" not in done:
        done.append("promoted")
        out.append(_post(career, "milestone_promoted", "milestone:promoted",
                         now))
    if career.arcs_won and "arc" not in done:
        done.append("arc")
        out.append(_post(career, "milestone_arc", "milestone:arc", now))
    return [m for m in out if m]


def _offer(career, st, now):
    """The one that matters, and the two answers to it."""
    out = []
    if st.get("offer"):
        # Already out. All that can happen now is that it quietly stops being
        # answerable — no warning, no countdown, no colour. Rule 3.
        if (not st.get("answer")
                and races_run(career) - st["offer"] > OFFER_WINDOW):
            st["answer"] = "expired"
        return out
    if st.get("beat", 0) < len(beats()):
        return out                       # the thread has not finished arriving
    # AND NOT IN THE SAME BREATH AS HER LAST ONE. Two letters from the same
    # person in one afternoon, the second of them the one that matters, is a
    # writer arranging the plot rather than a sister sending an email. A race
    # has to have happened in between.
    #
    # SEASON-AWARE, because `beat_round` counts rounds WITHIN a season and a
    # bare comparison across the winter is meaningless — it would hold the
    # offer back for half of the following year for no reason a reader could
    # see. A letter last season is already a gap.
    if (st.get("beat_season") == _season_no(career)
            and len(career.rounds) <= int(st.get("beat_round") or 0)):
        return out
    if not (_final_arc(career) and _at_the_top(career)):
        return out
    if rounds_left(career) < OFFER_MIN_LEFT:
        return out
    m = _post(career, "offer", "offer", now)
    if m is not None:
        st["offer"] = races_run(career)
        out.append(m)
    return out


def offer_open(career):
    """Can he still answer? What the menu asks before drawing a reply row."""
    st = state(career)
    return bool(st.get("offer") and not st.get("answer"))


def answer(career, go):
    """Take the trip, or do not. Returns the messages that follow.

    GOING COSTS THE NEXT ROUND, immediately and visibly: the race is run
    without him and his rivals score. That is the whole dilemma, and it is
    why this is a confirmed action in the menu rather than a link in an email.
    """
    st = state(career)
    if not offer_open(career):
        return []
    now = time.time()
    if not go:
        st["answer"] = "no"
        m = _post(career, "reply_no", "reply_no", now)
        career.save()
        return [m] if m else []
    st["answer"] = "yes"
    n = len(career.rounds) + 1
    rnd = career.record_absence(n)
    st["missed"] = (rnd or {}).get("n") or 0
    m = _post(career, "reply_yes", "reply_yes", now)
    career.save()
    return [m] if m else []


# ---------------------------------------------------------------------------
# the ending
# ---------------------------------------------------------------------------
def _ending(career, st, now):
    """Four messages, and they do not all arrive at once.

    The sporting half lands with the result — the paddock reacting the same
    evening. The article about his father waits until he has actually READ one
    of them, which is the only honest way to pace it: four unread messages in
    one refresh is a credits roll, and the fourth one is then just the last one
    he clicks.
    """
    out = []
    if not (_final_arc(career) and _at_the_top(career)
            and career.season_done()):
        return out
    champion = (career.my_position() == 1)
    if not st.get("ended"):
        out.append(_post(career, "principal",
                         "ending:principal", now,
                         pool=_pool("principal_champion" if champion
                                    else "principal_close")))
        out.append(_post(career, "engineer", "ending:engineer", now + 1,
                         pool=_pool("engineer_champion" if champion
                                    else "engineer_close")))
        if champion:
            # ONLY IF HE WON IT. "The newest champion" about a man who
            # finished second is the exact kind of small wrongness that
            # destroys a career-defining article.
            prof = _profile(career)
            if prof:
                out.append(_post(career, "profile", "ending:profile", now + 2,
                                 body=prof[1], subject=prof[0],
                                 sender="FACTORtv News"))
        st["ended"] = int(now)
        return [m for m in out if m]
    if st.get("closed"):
        return out
    champion = (career.my_position() == 1)
    read_one = any(m.get("read") for m in inbox.messages(career)
                   if str(m.get("id", "")).startswith("ending:"))
    if not read_one:
        return out
    went = st.get("answer") == "yes"
    # THE DEDICATION IS THE POINT, and it has to know which career it is
    # closing. A piece about a championship dedicated to his father is false
    # if there is no championship, so the went-ending has two forms and the
    # first variant that fits is the one that runs. The stayed-ending has one
    # form and mentions neither him nor his season — indifference, not
    # mockery, and a paper that connected the two would have NOTICED him.
    kind = "ending_went" if went else "ending_missed"
    pool = _pool(kind)
    if went and not champion:
        pool = pool[1:] or pool
    m = _post(career, kind, "ending:father", now + 3, pool=pool)
    if m is not None:
        st["closed"] = int(now)
        # Where the epilogue counts from. Without it the first letter after
        # the funeral arrives in the same breath as the article about it.
        st["closed_at"] = races_run(career)
        out.append(m)
    return out


def _epilogue(career, st, now):
    """After the story ends, she keeps writing — rarely, and about the grief.

    The user's own design, and it earns its place twice over. A thread that
    stops the moment the plot is finished tells the player the person was a
    device; the letters that arrive months apart afterwards say she was not.
    And a career does not end at the ending — a completionist is still racing,
    and the rest of the inbox carries on around him exactly as before.

    FAR SLOWER THAN THE STORY WAS (`EPILOGUE_EVERY`). She is getting on with
    her life rather than reporting to him, which is the whole point of them.
    """
    if not st.get("closed"):
        return []
    i = int(st.get("epilogue") or 0)
    pool = _pool("epilogue")
    out = []
    if i < len(pool):
        since = races_run(career) - int(st.get("closed_at") or 0)
        # ONE PER SEASON HERE TOO, and a whole season between the first and the
        # ending. She is getting on with her life, which is the entire content
        # of these letters.
        if (since >= (i + 1) * EPILOGUE_EVERY
                and st.get("epi_season") != _season_no(career)):
            m = _post(career, "epilogue", "epilogue:%d" % i, now,
                      pool=[pool[i]])
            if m is not None:
                st["epilogue"] = i + 1
                st["epi_season"] = _season_no(career)
                out.append(m)
    # THE 100% LETTER. Winning all five divisions is a completionist's
    # achievement and the game has nothing else to give him for it — so it
    # gives him the one thing the story left open: she is all right now. It is
    # deliberately not announced anywhere, and a player who never finishes the
    # fifth division simply never learns it exists.
    if career.completion_pct() >= 1.0 and not st.get("bonus"):
        for j, tpl in enumerate(_pool("completion")):
            m = _post(career, "completion", "completion:%d" % j, now + j,
                      pool=[tpl])
            if m is not None:
                out.append(m)
        st["bonus"] = int(now)
    return out


def _profile(career):
    """The champion's own profile — GENERATED, never written.

    Every fact is one the overlay watched: the divisions he climbed, where he
    finished each of them, his wins, his seasons. **It must not invent a team
    name.** The store knows car classes and divisions, not entrants, and a
    made-up team is the one false note nobody would forgive in the article that
    closes a career.
    """
    r = career.resume()
    if not r:
        return None
    name = career.me or "The new champion"
    tier = r.get("tier_name") or "the championship"
    hist = [h for h in (r.get("history") or []) if h.get("name")]
    # THE CLIMB, in his own words as it were: the divisions in order, with
    # what he did in each. Written as a sentence rather than a list, because
    # this is a newspaper and not a results screen.
    steps = []
    for h in hist:
        pos = h.get("pos")
        steps.append("%s (%s)" % (h["name"],
                                  "champion" if pos == 1
                                  else "P%d" % pos if pos else "unfinished"))
    # WHERE HE STARTED MATTERS AS MUCH AS WHERE HE FINISHED. Taking the last
    # four divisions of a ten-season career told the reader he "came up
    # through GT3" — a man who spent five years climbing out of karting, with
    # the karting deleted. First two, then the most recent two.
    if len(steps) > 4:
        steps = steps[:2] + ["…"] + steps[-2:]
    climb = ", then ".join(steps).replace(", then …, then ", ", … , then ")
    
    titles = r.get("title_count") or 0
    body = [
        "%s is the champion of %s. The record behind that sentence is %d "
        "season%s of racing, %d start%s, %d win%s and %d podium%s — a career "
        "assembled a rung at a time rather than handed over, which is the only "
        "way anybody gets here and is not the way it is usually described."
        % (name, tier, r["seasons"] or 1, "" if (r["seasons"] or 1) == 1
           else "s", r["races"], "" if r["races"] == 1 else "s",
           r["wins"], "" if r["wins"] == 1 else "s",
           r["podiums"], "" if r["podiums"] == 1 else "s"),
    ]
    if climb:
        body.append(
            "He came up through %s. %s"
            % (climb,
               "That is %d championship%s across those divisions, and the "
               "thing worth noting about a route like that is how few drivers "
               "who start it are still in the sport at the end of it."
               % (titles, "" if titles == 1 else "s")
               if titles else
               "A route like that takes years, and most of the drivers who "
               "start it are not in the sport by the end of it."))
    else:
        body.append(
            "What the numbers do not record is the part everyone in this "
            "paddock already knows about him, which is that none of it was "
            "given to him and all of it took longer than he expected.")
    return ("%s is champion of %s" % (name, tier), body)


# ---------------------------------------------------------------------------
def validate():
    """The rules this thread has to obey, checked rather than trusted."""
    errs = []
    pools = dict(load())
    bs = pools.pop("beats", [])
    for i, t in enumerate(bs):
        pools["beat[%d]" % i] = [t]
    for kind, pool in pools.items():
        if not pool:
            errs.append("%s: empty" % kind)
        for i, tpl in enumerate(pool):
            where = kind if kind.startswith("beat[") else "%s[%d]" % (kind, i)
            for field in ("from", "subject", "body"):
                if not tpl.get(field):
                    errs.append("%s: missing %s" % (where, field))
            body = tpl.get("body") or []
            if len(body) < 2:
                errs.append("%s: %d paragraph(s)" % (where, len(body)))
            words = sum(len(p.split()) for p in body)
            if not 60 <= words <= 240:
                errs.append("%s: %d words" % (where, words))
            # RULE 3, MECHANICALLY. A slot is a way for a letter to fail to
            # send, and the personal thread is the one thing here that must
            # never fail to send because a fact was missing.
            #
            # ONE EXCEPTION, NAMED HERE RATHER THAN WAIVED. `{won}` is the
            # championship in her first-title letter: the player read "you've
            # won the whole thing" beside a dashboard that said Formula One and
            # could not tell what she thought he had won. The slot is safe
            # because the ONLY caller fills it from `ladder_history`, and a
            # letter about a first championship cannot be sent without one — but
            # it is allowed by name, in one pool, so the rule still holds
            # everywhere else.
            ALLOWED = {"milestone_first_title": ("{won}",)}
            text = " ".join(body + [tpl.get("subject", "")])
            for _ok in ALLOWED.get(kind, ()):
                text = text.replace(_ok, "")
            if "{" in text:
                errs.append("%s: takes a slot" % where)
    if len(bs) < 6:
        errs.append("only %d beats — the thread has to span a career" % len(bs))
    return errs


if __name__ == "__main__":
    bad = validate()
    print("%d beats, %d other pieces" % (len(beats()), len(load()) - 1))
    for k in sorted(load()):
        if k != "beats":
            print("  %-20s %d" % (k, len(load()[k])))
    print("validate: %s" % ("OK" if not bad else "\n  " + "\n  ".join(bad)))
