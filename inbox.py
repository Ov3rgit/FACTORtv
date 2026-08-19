# -*- coding: utf-8 -*-
"""
FACTORtv — the inbox.

WHAT IT IS FOR
--------------
A career that only ever speaks to you through a commentary booth is a career
that only exists while you are driving. The inbox is the other half: the FIA
confirming an entry, a team manager sending the result sheet, an agent telling
you the seat did not come. It is where a career is READ rather than heard, and
it is the anchor everything later hangs on — the news feeds, the divisions
view, and eventually a story told entirely in correspondence.

    inbox.refresh(career)      generate anything the career has earned
    inbox.messages(career)     newest first
    inbox.unread(career)       count, for the badge
    inbox.read(career, mid)    mark one read
    inbox.delete(career, mid)  and it does not come back

THE THREE RULES THIS MODULE EXISTS TO KEEP
------------------------------------------
1. EVERY NUMBER COMES FROM THE CAREER STORE, AND IS FROZEN WHEN IT IS SENT.
   "You are second on fifty-four points" is checkable — the user can open the
   standings — so it is filled in at the moment the mail is generated and
   never recomputed. A letter that silently updates itself is not a letter.

2. A MISSING FACT KILLS THE MESSAGE, IT DOES NOT BLANK THE SLOT. `lines.py`
   uses `safe_format`, which blanks unknown keys, and that is right for speech
   where a half-line is survivable. It is wrong here: "they wanted P and they
   have taken someone who had it" is a letter with a hole in it, and it sits
   in the archive for the rest of the career. `_fill` returns None instead and
   the message is simply not sent.

3. GENERATION IS IDEMPOTENT AND DELETION IS PERMANENT. Every message has a
   DETERMINISTIC id built from the event that caused it, so `refresh()` can be
   called on every menu draw without ever doubling anything. `mail_seen`
   records every id ever generated, so a message the user deleted stays
   deleted — without it the next refresh would post it straight back, which is
   the single most infuriating bug a mail feature can have.

WHY THE PERSONAL MAIL WILL LOOK EXACTLY LIKE THIS
-------------------------------------------------
It has to. The story's whole mechanism is that by the time the important
message arrives the player has been trained to skim — so there is no badge, no
colour and no ceremony separating a letter from his brother from a licensing
statement. That is why the dry mail is written properly rather than stubbed:
it is not filler around the story, it IS the camouflage.
"""
import json
import os
import re
import sys
import time

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(_DIR, "lines_data", "mail.json")

# How many messages a career keeps. An archive is a feature; an unbounded list
# in a save file that is rewritten after every race is not. Oldest READ mail is
# dropped first, and unread mail is never dropped — the one thing the user has
# not seen is the one thing that must survive.
KEEP = 120

# Rounds between routine notices, so the dry mail is a background rather than a
# stream. Both are per season and both are deliberately unlike each other: a
# licence statement is quarterly-feeling, a steward's notice arrives once.
LICENCE_EVERY = 3
STEWARD_AFTER = 2

# Rounds between the general notices from race direction. Offset from the
# licence cadence on purpose: two bureaucracies writing to a driver on the same
# weekend is how an inbox starts feeling generated.
NOTICE_EVERY = 3

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
    return sorted(load().keys())


# ---------------------------------------------------------------------------
# filling
# ---------------------------------------------------------------------------
_SLOT = re.compile(r"\{(\w+)\}")


def _fill(text, kw):
    """Render one paragraph, or None if the store cannot supply a slot.

    Rule 2 above. The refusal is the feature: a letter is read once and then
    sits in an archive, so a hole in it is permanent in a way a spoken line
    never is.
    """
    out = []
    pos = 0
    for m in _SLOT.finditer(text):
        key = m.group(1)
        val = kw.get(key)
        if val is None or val == "":
            return None
        out.append(text[pos:m.start()])
        out.append(str(val))
        pos = m.end()
    out.append(text[pos:])
    return "".join(out)


def _SENTENCE_START(_m):
    return _m.group(0).upper()


_AFTER_STOP = re.compile(r"(?:^|(?<=[.!?]\s))[a-z]")


def _sentence_case(text):
    """Capitalise anything that begins a sentence.

    THE SAME BUG `lines._sentence_case` EXISTS FOR, and it turned up here on
    the first letter that was read end to end: "{pos} in the championship is
    not enough" rendered as "fifth in the championship is not enough". A slot
    inherits its own case, and a template that opens on one inherits nothing
    at all — so this is done centrally rather than by asking every template
    author to remember which slot might land first.

    Applied AFTER filling, deliberately. Doing it in the template would mean
    "Fifth" appearing mid-sentence somewhere else, and the same clause has to
    work in both positions.
    """
    return _AFTER_STOP.sub(_SENTENCE_START, text or "")


def _compose_any(kind, mid, kw, variant=0, pool=None, **rest):
    """Compose, trying each variant until one can actually be filled.

    A VARIANT MAY ASK FOR A FACT THAT DOES NOT EXIST YET — {behind} means
    nothing to a championship leader — and without this that letter would
    simply not be sent, so the driver in the lead would silently receive fewer
    result sheets than everybody else. Walking the pool keeps the writing free
    to use whatever a template needs, while `_fill`'s refusal keeps the letters
    honest. The starting point is `variant`, so the rotation still varies.
    """
    have = load().get(kind) if pool is None else pool
    for i in range(len(have or ())):
        m = _compose(kind, mid, kw, variant=variant + i, pool=have, **rest)
        if m is not None:
            return m
    return None


def _compose(kind, mid, kw, variant=0, when=None, rnd=0, feed="mail",
             pool=None):
    """Build one message from its template, or None if a fact is missing.

    `feed` is "mail" or "news", and EVERY message carries it — including the
    ones that could not possibly be news. A field present on some messages and
    absent on others is a field the archive can sort by, and sorting is one
    step from highlighting: see the personal-mail rule at the top of this
    module. `pool` lets another module (`news.py`) supply its own templates
    while sharing this composer, so there is one renderer and one set of
    rules about missing facts.
    """
    pool = load().get(kind) if pool is None else pool
    if not pool:
        return None
    tpl = pool[variant % len(pool)]
    subject = _fill(tpl.get("subject", ""), kw)
    if subject is None:
        return None
    body = []
    for para in tpl.get("body", ()):
        p = _fill(para, kw)
        if p is None:
            return None
        body.append(_sentence_case(p))
    if not body:
        return None
    # THE SENDER IS A SLOT TOO. Most letters are from a fixed department, but
    # the junior-programme ones come from whichever Formula One team he signed
    # for — and an unfilled `{team}` in the FROM line is the most visible slot
    # failure available, because the inbox list is nothing but senders and
    # subjects.
    #
    # FILLED WITH THIS MODULE'S OWN `_fill`, which REFUSES rather than
    # blanking - the same rule the paragraphs follow, so a letter whose sender
    # cannot be resolved is not sent at all rather than arriving from nobody.
    # (`lines.safe_format` is the SPEECH rule and is deliberately the
    # opposite: it blanks, because a spoken line is gone in a second and a
    # letter sits in an archive for the rest of the career. It is also not
    # imported here, and reaching for it raised on the first programme letter
    # ever composed.)
    frm = tpl.get("from", "")
    if "{" in frm:
        frm = _fill(frm, kw)
        if frm is None:
            return None
    return {"id": mid, "kind": kind, "feed": feed,
            "from": frm,
            "subject": subject, "body": body,
            "when": int(when or time.time()), "round": int(rnd or 0),
            "read": False}


# ---------------------------------------------------------------------------
# the store
# ---------------------------------------------------------------------------
def messages(career, kind=None, feed=None):
    """Everything in the inbox, newest first.

    `feed` filters to one tab. A message written before the feeds existed has
    no field at all, so it reads as mail — which is what it was.
    """
    ms = list((career.data.get("mail") or []))
    if kind:
        ms = [m for m in ms if m.get("kind") == kind]
    if feed:
        ms = [m for m in ms if (m.get("feed") or "mail") == feed]
    return sorted(ms, key=lambda m: (-(m.get("when") or 0), m.get("id", "")))


def unread(career, feed=None):
    return sum(1 for m in (career.data.get("mail") or [])
               if not m.get("read")
               and (not feed or (m.get("feed") or "mail") == feed))


def get(career, mid):
    return next((m for m in (career.data.get("mail") or [])
                 if m.get("id") == mid), None)


def read(career, mid, on=True):
    m = get(career, mid)
    if m is None:
        return False
    m["read"] = bool(on)
    career.save()
    return True


def read_all(career, feed=None):
    for m in (career.data.get("mail") or []):
        if not feed or (m.get("feed") or "mail") == feed:
            m["read"] = True
    career.save()


def delete(career, mid):
    """Remove one message for good.

    The id stays in `mail_seen`, so the next `refresh()` does not helpfully
    post it again. That is rule 3 and it is not optional — a deleted message
    that returns is worse than no delete button at all.
    """
    ms = career.data.get("mail") or []
    keep = [m for m in ms if m.get("id") != mid]
    if len(keep) == len(ms):
        return False
    career.data["mail"] = keep
    career.save()
    return True


def _post(career, msg):
    """Add a message if its id has never been generated before."""
    if msg is None:
        return None
    seen = career.data.setdefault("mail_seen", [])
    if msg["id"] in seen:
        return None
    seen.append(msg["id"])
    career.data.setdefault("mail", []).append(msg)
    return msg


def _trim(career):
    """Hold the archive to `KEEP`, dropping the OLDEST READ mail first.

    Unread mail is never dropped. The one message the user has not opened is
    the one the whole story depends on him being able to find, and an archive
    that silently eats it to save disk space would be a spectacular way to
    lose the ending.
    """
    ms = career.data.get("mail") or []
    if len(ms) <= KEEP:
        return
    ms.sort(key=lambda m: (m.get("when") or 0, m.get("id", "")))
    over = len(ms) - KEEP
    kept = []
    for m in ms:
        if over and m.get("read"):
            over -= 1
            continue
        kept.append(m)
    career.data["mail"] = kept


# ---------------------------------------------------------------------------
# generation
# ---------------------------------------------------------------------------
def _prior_eligible(career, base, fingerprint):
    """Has a DIFFERENT eligible list already been sent for this rung?

    Read from `mail_seen` rather than from the archive, because a deleted letter
    was still sent — he read it, loaded a car from it, and the correction is
    still owed to him.
    """
    want = "eligible:%s" % base
    for mid in (career.data.get("mail_seen") or ()):
        rest = str(mid)[len(want):] if str(mid).startswith(want) else None
        if rest is None:
            continue
        # THE ID SHAPE CHANGED WHEN THE FINGERPRINT WAS ADDED, so a letter sent
        # by an older build has no fingerprint at all — and that letter is
        # precisely the one carrying the wrong car name. An empty remainder is a
        # legacy id and counts.
        #
        # The remainder must be empty or start with a colon: a career whose base
        # is "f4:1" would otherwise match "eligible:f4:11" from an eleventh
        # season, which is a different rung entirely.
        if rest == "" or (rest.startswith(":")
                          and rest != ":" + fingerprint):
            return True
    return False


def _cars_fingerprint(career):
    """A short, stable tag for the eligible-car list. "" when there is none.

    Short because it goes in a message id and ids are read in logs; stable
    because it is sorted, so the same list in a different scan order is the same
    letter and does not re-issue.
    """
    try:
        phrase = _cars_phrase(career)
    except Exception:
        return ""
    if not phrase:
        return ""
    import hashlib
    return hashlib.sha1(phrase.encode("utf-8")).hexdigest()[:8]


def _cars_phrase(career):
    """The eligible cars for this rung, as a readable list, or "".

    WHAT HE ACTUALLY NEEDS TO KNOW. The overlay works out which division a
    session belongs to from the CarClass rF2 reports — so a driver who loads
    the wrong car gets an off-career race and no explanation. The paperwork is
    the honest place to say it: an entry pack that lists eligible machinery is
    a real thing, and it means the answer is in his inbox rather than in this
    conversation.

    The FOLDER IS QUOTED alongside the tidy name, because the tidy name is a
    guess at what the game calls it and the folder is not.
    """
    try:
        import ladder as ladder_mod
    except Exception:
        return ""
    tier = career.tier() if hasattr(career, "tier") else None
    if not tier:
        return ""
    cars = ladder_mod.tier_cars(tier)
    if not cars:
        # Nothing scanned, or nothing owned. Either way this is a claim we
        # cannot make, and `_fill` will drop the letter rather than send one
        # with an empty list in it.
        return ""
    # The folder is quoted only when it ADDS something. "STK 488 GT3 (STK 488
    # GT3)" is a parenthesis doing no work, and a letter full of those reads
    # like a machine wrote it — which is exactly the impression the whole
    # inbox is built to avoid.
    bits = [nice if nice == folder else "%s (%s)" % (nice, folder)
            for nice, folder in cars[:4]]
    over = len(cars) - len(bits)
    if len(bits) == 1:
        listed = bits[0]
    else:
        # "A, B or C" — and the overflow is appended AFTER the conjunction
        # rather than joined into it, because "B or and 4 others" is what
        # happens when it is not.
        listed = "%s or %s" % (", ".join(bits[:-1]), bits[-1])
    if over:
        listed += ", and %d other%s on the same list" % (
            over, "" if over == 1 else "s")
    return listed


def _facts(career):
    """Everything a template may ask for, from the store and nowhere else."""
    ev = career.evaluate() or {}
    st = career.title_state() or {}
    kw = {
        "drv": career.me or "",
        "series": ev.get("tier_name") or career.name or "",
        "path": ev.get("path_name") or "",
        "rounds": career.total_rounds or "",
        # WORDS, NOT DIGITS, and each slot in the shape its sentences need.
        # "You are 2 in the championship" is a spreadsheet; "you are second"
        # is a letter. `need` goes the other way and stays a grid reference —
        # "they wanted P2" is how a paddock says it, and an ordinal there
        # ("they wanted second") reads as a result rather than a requirement.
        "pos": _ordinal(st.get("my_place")),
        "pts": st.get("my_points") if st.get("my_points") is not None else "",
        "need": ("P%d" % ev["needs"]) if ev.get("needs") else "",
        "next": ev.get("next_name") or "",
        "races": len(career.rounds),
        "cars": _cars_phrase(career),
        "seasons": len(career.data.get("ladder_history") or []) + 1,
    }
    return kw, ev


def _season_no(career):
    """Which season of this career we are in. The id needs it: a driver who
    stays down and races Formula 3 twice must get two entry confirmations,
    not one, and they cannot share an id."""
    return len(career.data.get("ladder_history") or [])


def refresh(career, now=None):
    """Generate everything this career has earned and not yet been sent.

    Safe to call on every menu draw and on every recorded result — the ids are
    deterministic, so nothing is ever posted twice. Returns the new messages.

    THE ORDER MATTERS ONLY FOR TIMESTAMPS. Everything is derived from state
    the store already holds, so a career that was raced before the inbox
    existed simply receives its back-mail on the first refresh rather than
    nothing at all.
    """
    if career is None:
        return []
    before = len(career.data.get("mail") or [])
    kw, ev = _facts(career)
    sn = _season_no(career)
    tier = (ev.get("tier") or "none")
    base = "%s:%d" % (tier, sn)
    now = now or time.time()
    new = []

    # -- the season starts --------------------------------------------------
    if kw["series"]:
        new.append(_post(career, _compose_any(
            "season_open", "season_open:%s" % base, kw, variant=sn, when=now)))
        # WHICH CAR TO LOAD. Sent once per season, right at the top, and
        # dropped silently when the cars cannot be listed — a "you may run the
        # following" notice with nothing following it is worse than no notice.
        # THE ONE LETTER THAT IS A REFERENCE LIST RATHER THAN A SNAPSHOT.
        #
        # Rule 1 of this module — every number is frozen when sent — is right
        # for a result sheet, whose whole value is that it says what was true
        # that afternoon. It is WRONG here: a homologation list exists to be
        # acted on later, and the user was sent one naming "Tatuus F4 2018"
        # when the game lists "Tatuus_F4-T014". Fixing the name did not help
        # him, because the letter he already had kept the old wording.
        #
        # So the id carries a fingerprint of the LIST. If the eligible cars
        # change — he installs one, or the overlay learns what the game really
        # calls them — the FIA re-issues the list, which is what a governing
        # body does. If nothing changed the id is identical and nothing is
        # sent, so this cannot become a letter that arrives every refresh.
        _fp = _cars_fingerprint(career)
        # A REVISION SAYS SO. One of the first-issue wordings opens "unchanged
        # from the version circulated with your entry pack", which is exactly
        # false on the letter that exists BECAUSE the list changed — and a
        # second identical-looking notice with different content in it is how a
        # reader learns to stop reading them. Governing bodies re-issue lists;
        # they do it under a different heading.
        _kind = ("eligible_revised"
                 if _fp and _prior_eligible(career, base, _fp) else "eligible")
        new.append(_post(career, _compose_any(
            _kind, "eligible:%s:%s" % (base, _fp), kw, variant=sn, when=now)))
        # A seat letter is for a rung he has ARRIVED at. The bottom of a path
        # is where everybody starts and nobody is welcomed to it.
        if ev.get("index"):
            new.append(_post(career, _compose_any(
                "seat", "seat:%s" % base, kw, variant=sn, when=now)))

    # -- THE HISTORIC TOUR, EARNED ------------------------------------------
    #
    # One era per Formula One championship, at the user's instruction, and the
    # invitation is where it is BANKED: an era he can race is an era he has a
    # letter about, so there is no way to unlock something silently.
    #
    # It reads `tour_state()`, which derives the count from titles rather than
    # keeping its own — the same discipline the milestones follow, and the reason
    # the paper and the menu can never disagree about which eras are open.
    try:
        tour = career.tour_state()
    except Exception:
        tour = None
    if tour and tour.get("next"):
        _idx, _era = tour["next"]
        m = _post(career, _compose_any(
            "tour_invite", "tour:%s" % _era.get("key", _idx),
            dict(kw, era=_era.get("name", "")),
            variant=len(tour.get("unlocked") or ()), when=now))
        if m:
            new.append(m)
            career.tour_grant(_era.get("key", ""))

    # -- the junior programme -----------------------------------------------
    # The scripted arc out of Formula 2. Every letter is driven by a STAGE
    # rather than by a round number, so the story cannot get ahead of the
    # racing — and the ids carry the stage, so a refresh on every menu draw
    # posts nothing twice.
    new += _programme_mail(career, base, kw, now)

    # -- the season runs ----------------------------------------------------
    for i, rnd in enumerate(sorted(career.rounds, key=lambda r: r.get("n", 0))):
        n = rnd.get("n") or (i + 1)
        # THE FIGURES ARE THE ONES THAT WERE TRUE THAT WEEKEND. `title_state`
        # is asked for the table AS IT STOOD after this round, not for today's
        # — a result sheet that quietly reflects a championship position he
        # reached three races later is a letter that rewrites itself.
        st = career.title_state(upto=n) or {}
        rkw = dict(kw)
        rkw.update({
            "round": n,
            "rpos": _ordinal(rnd.get("pos")),
            "pos": _ordinal(st.get("my_place")),
            "pts": (st.get("my_points")
                    if st.get("my_points") is not None else ""),
        })
        when = rnd.get("when") or now
        # THE SHEET DEPENDS ON WHAT HAPPENED. A team manager who writes the
        # same paragraph after a victory and after a shunt is a team manager
        # nobody believes in — and sixty identical result sheets are what
        # turned the personal mail into the thing the player was waiting for,
        # which is the one thing it must never be.
        new.append(_post(career, _compose_any(
            _result_kind(rnd), "result:%s:%d" % (base, n), rkw, variant=n,
            when=when, rnd=n)))
        if n % LICENCE_EVERY == 0:
            new.append(_post(career, _compose_any(
                "licence", "licence:%s:%d" % (base, n), rkw,
                variant=n // LICENCE_EVERY + sn, when=when, rnd=n)))
        if n == 1:
            new.append(_post(career, _compose_any(
                "testing", "testing:%s" % base, rkw, variant=sn, when=when,
                rnd=n)))
        # A NOTICE FROM RACE DIRECTION on the rounds nothing else covers. The
        # FIA is the loudest voice in a real driver's inbox and it was the
        # quietest in this one — two kinds, endlessly repeated. Six more, on
        # their own cadence so they do not arrive in a clump with the licence
        # statements.
        if n % NOTICE_EVERY == 1 and n > 1:
            new.append(_post(career, _compose_any(
                "fia_notice", "fia_notice:%s:%d" % (base, n), rkw,
                variant=n + sn, when=when, rnd=n)))
        if n == STEWARD_AFTER:
            new.append(_post(career, _compose_any(
                "steward", "steward:%s" % base, rkw, variant=sn, when=when,
                rnd=n)))

    # -- the season ends ----------------------------------------------------
    #
    # Only ever from `evaluate()`, which is the one place that knows what a
    # season was worth. Nothing here decides anything: the seat is offered by
    # post and taken in the menu, exactly as the promotion itself is.
    if ev.get("complete"):
        if ev.get("pos") == 1:
            new.append(_post(career, _compose_any(
                "title", "title:%s" % base, kw, variant=sn, when=now)))
        if ev.get("arc_done"):
            new.append(_post(career, _compose_any(
                "arc_win", "arc_win:%s" % base, kw, when=now)))
            new.append(_post(career, _compose_any(
                "newpath", "newpath:%s" % base, kw, when=now)))
        elif ev.get("promoted"):
            new.append(_post(career, _compose_any(
                "promotion", "promotion:%s" % base, kw, variant=sn, when=now)))
        elif ev.get("needs"):
            new.append(_post(career, _compose_any(
                "missed", "missed:%s" % base, kw, when=now)))
            if ev.get("sideways"):
                new.append(_post(career, _compose_any(
                    "sideways", "sideways:%s" % base, kw, when=now)))

    new = [m for m in new if m]
    if len(career.data.get("mail") or []) != before:
        _trim(career)
        career.save()
    return new


def _result_kind(rnd):
    """Which result letter a round has earned.

    Five outcomes, because they are five different afternoons. A retirement is
    checked FIRST — a DNF classified eleventh is a retirement, not a bad race,
    and telling a driver his consistency was encouraging when the engine let go
    is the kind of wrongness that stops a whole inbox being read.
    """
    if rnd.get("dnf"):
        return "result_dnf"
    pos = int(rnd.get("pos") or 0)
    field = int(rnd.get("field") or 0)
    if pos == 1:
        return "result_win"
    if 0 < pos <= 3:
        return "result_podium"
    # POINTS IS RELATIVE TO THE FIELD, not a fixed number. Sixth of twenty is a
    # decent afternoon; sixth of six is last, and a letter congratulating him
    # on it would be read exactly once.
    if pos and pos <= 10 and (not field or pos <= max(3, field * 0.5)):
        return "result_points"
    return "result_low"


def _ordinal(n):
    """'third', for a finishing position. Words, not digits — this is prose.

    Returns "" for a missing position rather than "0th", which `_fill` then
    treats as a missing fact and drops the whole message. That is the right
    answer: a result sheet with no result on it is not a result sheet.
    """
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    words = ("", "first", "second", "third", "fourth", "fifth", "sixth",
             "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth",
             "thirteenth", "fourteenth", "fifteenth", "sixteenth",
             "seventeenth", "eighteenth", "nineteenth", "twentieth")
    if n < len(words):
        return words[n]
    suffix = "th" if 4 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(
        n % 10, "th")
    return "%d%s" % (n, suffix)


# ---------------------------------------------------------------------------
def validate():
    """Rules the mail data has to obey, checked rather than assumed."""
    errs = []
    for kind, pool in load().items():
        if not pool:
            errs.append("%s: no variants" % kind)
            continue
        for i, tpl in enumerate(pool):
            where = "%s[%d]" % (kind, i)
            for field in ("from", "subject", "body"):
                if not tpl.get(field):
                    errs.append("%s: missing %s" % (where, field))
            body = tpl.get("body") or []
            # A PARAGRAPH OR TWO, because that is what correspondence is. One
            # short paragraph is a notification, and the whole reason the
            # inbox works is that it does not read like one.
            if len(body) < 2:
                errs.append("%s: %d paragraph(s), wanted at least 2"
                            % (where, len(body)))
            words = sum(len(p.split()) for p in body)
            if words < 60:
                errs.append("%s: only %d words" % (where, words))
            if words > 220:
                errs.append("%s: %d words, too long to read on a panel"
                            % (where, words))
            for para in body:
                # LAW 13, and the narrow version of it. A determiner in front
                # of {series} is correct — "the Formula 3 season" — because
                # that slot is a bare noun. It is only wrong in front of the
                # slots that CARRY their own word: {pos}/{rpos} render as
                # "second", so "finished a {rpos}" reads "finished a second",
                # and {need} renders as "P2".
                for slot in ("pos", "rpos", "need"):
                    for det in ("a {%s}", "an {%s}", "the {%s}"):
                        if (det % slot) in para:
                            errs.append("%s: determiner in front of {%s}"
                                        % (where, slot))
    return errs


if __name__ == "__main__":
    bad = validate()
    n = sum(len(v) for v in load().values())
    print("%d kinds, %d templates" % (len(load()), n))
    for kind, pool in sorted(load().items()):
        w = sum(len(p.split()) for t in pool for p in t["body"]) // len(pool)
        print("  %-12s %d variant(s)  ~%d words" % (kind, len(pool), w))
    print("validate: %s" % ("OK" if not bad else "\n  " + "\n  ".join(bad)))


DEV_KINDS = ("prog_dev1", "prog_dev2", "prog_dev3", "prog_dev4", "prog_dev5")


def _spoken_int(n):
    """Small counts as words. "3 outings" in a letter reads as a spreadsheet."""
    return ("zero", "one", "two", "three", "four", "five", "six",
            "seven")[n] if 0 <= int(n or 0) <= 7 else str(int(n or 0))


def _fmt_lap(t):
    """A lap time as a driver says it, or "" when there is none to say."""
    try:
        t = float(t or 0)
    except Exception:
        return ""
    if t <= 0:
        return ""
    return "%d:%06.3f" % (int(t // 60), t % 60) if t >= 60 else "%.3f" % t


def _pretty_slug(slug):
    """A circuit slug as a name. The store keeps slugs; a letter needs words."""
    if not slug:
        return ""
    try:
        import track as track_mod
        got = track_mod.resolve(slug)
        if got is not None and getattr(got, "name", ""):
            return got.name
    except Exception:
        pass
    return " ".join(w.capitalize() for w in str(slug).replace("_", " ").split())


def _test_car_name(state):
    """What the game calls the test car, with the team in front of it.

    THE TEAM AND THE MOD ARE TWO DIFFERENT FACTS. rF2 publishes the CONSTRUCTOR
    as the CarClass for these mods, so "Mercedes" is what he picks in the car
    list — but he has to find the 2020 mod first, and only the game knows what
    that is called. `modnames` reads it out of the UI's own cache.
    """
    import programme as prog_mod
    team = (state or {}).get("team") or ""
    try:
        import modnames as modnames_mod
        got = modnames_mod.pick_names(prog_mod.TEST_MOD)
    except Exception:
        got = None
    mod = (got or [""])[0]
    if team and mod:
        return "%s, in %s" % (team, mod)
    return team or mod or "%d car" % prog_mod.TEST_YEAR


def _spoken_ordinal(n):
    """"third", for a letter. Positions are prose in correspondence — "P3 in the
    championship" is a timing screen, not a sentence somebody writes to you."""
    words = ("", "first", "second", "third", "fourth", "fifth", "sixth",
             "seventh", "eighth", "ninth", "tenth")
    n = int(n or 0)
    return words[n] if 0 < n < len(words) else ("%dth" % n if n else "")


def _programme_mail(career, base, kw, now):
    """The junior-programme thread. See `programme.py` for the state machine.

    ONE LETTER PER STAGE, and the stage is the id — so this is idempotent for
    free and a player who sits on a decision for six rounds is not written to
    again about it.

    IT NEVER INVENTS THE OUTCOME. The seat letters name a real car in a real
    mod on his disk, because the point of them is to tell him what to select;
    what he actually drove is read back from the result afterwards, the same
    rule the car pick follows.
    """
    try:
        import programme as prog_mod
    except Exception:
        return []
    st = prog_mod.state(career)
    if st in (prog_mod.NONE,):
        return []
    key, block = prog_mod.signed(career)
    out = []
    k = dict(kw)
    if block:
        k.update({
            "prog": block.get("name", ""),
            "f2team": block.get("f2_team", ""),
            # The arc starts on the F3 rung now, and the same three teams run in
            # both championships — which is exactly why these seats work.
            "f3team": block.get("f3_team") or block.get("f2_team", ""),
            "f1team": block.get("f1_team", ""),
            "seat": block.get("f1_seat", ""),
            "lead": block.get("f1_lead", ""),
            # The letters that come from the team are signed by the team, and
            # `{team}` is the `from` line rather than a slot in the prose.
            "team": block.get("f1_team", ""),
        })
    if st == prog_mod.OFFERED and prog_mod.offer(career):
        out.append(_post(career, _compose_any(
            "prog_offer", "prog:offer:%s" % base, k, when=now)))
        return [m for m in out if m]
    if not block:
        return []
    if st in (prog_mod.SIGNED, prog_mod.RETRY, prog_mod.WON, prog_mod.DEV,
              prog_mod.SEAT, prog_mod.DROPPED):
        out.append(_post(career, _compose_any(
            "prog_signed", "prog:signed:%s" % key, k, when=now)))
    # THE CALL-UP. Four rounds into the Formula 3 season the academy's Formula 2
    # team makes a change, and he finishes the year in the bigger car. THE LETTER
    # IS WHAT MOVES HIM — a player who never opens his post is not quietly
    # transferred to another championship, which is the same rule the development
    # year's beats follow.
    #
    # NOBODY IS NAMED. "Dropped for form" is a claim about a real person's
    # competence and the Formula 2 2019 grid is a real one, so the letter says the
    # team has made a change and never says who.
    if prog_mod.callup_ready(career):
        m = _post(career, _compose_any(
            "prog_callup", "prog:callup:%s" % key, k, when=now))
        if m:
            out.append(m)
            prog_mod.take_callup(career)

    if st == prog_mod.RETRY:
        out.append(_post(career, _compose_any(
            "prog_retry", "prog:retry:%s:%d" % (
                key, int((career.data.get("programme") or {}).get(
                    "attempts") or 1)), k, when=now)))
    if st == prog_mod.DROPPED:
        out.append(_post(career, _compose_any(
            "prog_dropped", "prog:dropped:%s" % key, k, when=now)))
    if st in (prog_mod.WON, prog_mod.DEV, prog_mod.SEAT):
        # A PROMOTION EARNED IS NOT A CHAMPIONSHIP WON, and the letter must not
        # blur them. The user was explicit: *"if I meet the requirements then the
        # commentator mustn't say 'he has won the F2 championship', it must be
        # along the story of being promoted."* A driver called up mid-season
        # clears a PODIUM bar, so unless he genuinely finished first the wording
        # comes from its own pool, which says so in as many words.
        _pos = career.my_position() or 0
        _called = bool((career.data.get("programme") or {}).get("called"))
        _kind = ("prog_won_callup" if _called and _pos != 1 else "prog_won")
        out.append(_post(career, _compose_any(
            _kind, "prog:won:%s" % key,
            dict(k, pos=_spoken_ordinal(_pos) if _pos else ""), when=now)))
    if st == prog_mod.DEV:
        # THE SPEC SHEET, ONCE, AT THE TOP OF THE YEAR. The user asked for the
        # parameters IN the letter — session type and car — because the feature
        # is unusable if he has to guess what to load, and guessing what to load
        # is the thing that has gone wrong four times now. `{car}` is what the
        # GAME lists the mod as, read from its own UI cache, so the letter names
        # a string he can see on screen.
        tst = prog_mod.test_state(career)
        # A COUNT IS PROSE AND A LABEL IS A NUMBER. "Test 1 of three" is the
        # exact tell that makes generated writing read as generated, so the
        # spoken form and the digit are two different slots.
        kt = dict(k, of=_spoken_int(tst["of"]), ofn=tst["of"],
                  car=_test_car_name(tst))
        out.append(_post(career, _compose_any(
            "prog_test", "prog:test:%s" % key, kt, when=now)))
        # ...AND A REPORT AFTER EACH OUTING, written from the laps and the best
        # lap the overlay watched. A test has no result, so the letter quotes
        # neither a position nor a comparison against anybody.
        for i, run in enumerate((career.data.get("programme") or {})
                                .get("test_runs") or (), start=1):
            left = tst["of"] - i
            kr = dict(kt, n=i, circuit=_pretty_slug(run.get("slug", "")),
                      laps=int(run.get("laps") or 0),
                      best=_fmt_lap(run.get("best")),
                      left=("%s to go." % _spoken_int(left) if left
                            else "That is the running done."))
            # ROTATED ON THE OUTING. Three debriefs in identical words is one
            # debrief sent three times, and the inbox is a list of subjects.
            m = _post(career, _compose_any(
                "prog_test_run", "prog:testrun:%s:%d" % (key, i), kr,
                variant=i - 1, when=now))
            if m:
                out.append(m)
        # THE YEAR ARRIVES ONE LETTER AT A TIME. A trickle, not a heap: five
        # beats delivered in one refresh is a montage, and the whole point of
        # the year is that it is slow.
        # NAMED, NOT BUILT. `"prog_dev%d" % n` is invisible to the
        # reachability check that greps this module for every template it
        # ships — and that check is the one thing standing between a pool and
        # LAW 21, which this project has broken four times. A literal tuple
        # costs nothing and can be seen.
        read, _total = prog_mod.dev_letters(career)
        n = min(read + 1, len(DEV_KINDS))
        m = _post(career, _compose_any(
            DEV_KINDS[n - 1], "prog:dev:%s:%d" % (key, n), k, when=now))
        if m:
            out.append(m)
            prog_mod.advance_dev(career)
    if st == prog_mod.SEAT:
        out.append(_post(career, _compose_any(
            "prog_seat", "prog:seat:%s" % key, k, when=now)))
    return [m for m in out if m]
