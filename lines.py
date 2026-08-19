# -*- coding: utf-8 -*-
"""
FACTORtv — dialogue pools and line selection.

Loads the JSON in `lines_data/`, filters each pool down to lines that are
*legal for the car on track*, and picks one without repeating itself.

Line format
-----------
Every pool is a list of entries:

    {"t": "{a} goes through on {b}!",      template, {slots} filled by caller
     "i": 2,                               intensity 0..3 (drives voice + TTS)
     "needs": ["drs"],                     era capabilities that must exist
     "not":   ["refuel"],                  capabilities that must NOT exist
     "era":   ["v10", "ground"],           allowed periods
     "disc":  ["f1", "stock"],             allowed disciplines
     "who":   "ANALYST"}                   persona override

Only `t` is required. Everything else narrows when the line is allowed to be
used, and that is the mechanism that keeps a 1966 Brabham from being told it
has DRS: the line simply is not in the candidate set.

Repetition
----------
The previous overlay picked randomly with a short "don't repeat the last N"
memory, and it still felt repetitive — random selection revisits the same
three lines long before it touches the twentieth.

This uses a SHUFFLE BAG per pool: draw without replacement until the pool is
exhausted, then reshuffle. Every line gets used once before any is used
twice, which is what "varied" actually means to a listener. The bag survives
across sessions (`_bag.json`) so restarting the game does not restart the
booth's vocabulary at the same four favourites.

Because the legal candidate set changes with the era, bags are keyed by
(pool, era-signature) — the 1992 bag and the 2025 bag are independent, and
neither is polluted by lines the other cannot use.
"""
import json
import os
import random
import sys
import time

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_DIR, "lines_data")
BAG_PATH = os.path.join(_DIR, "_bag.json")

# FILES IN `lines_data/` THAT ARE NOT DIALOGUE.
#
# The loader takes EVERY .json in the folder and treats any list it finds as a
# pool of lines — which is what lets a pool be extended across files. The other
# data files (`tracks`, `drivers`, `seasons`, `ladders`) escaped that only
# because their top-level values happen to be dicts rather than lists.
# `mail.json` does not: its values are lists of letter templates, so twelve
# "pools" of email appeared in the booth's line store the moment it was added,
# and `python lines.py` reported them as broken entries.
#
# Nothing ever drew one — an entry with no text renders as nothing — but the
# booth was one collision away from reading a licensing statement on air.
#
# IT HAPPENED AGAIN WITH `news.json` THE VERY NEXT DAY, which is why this list
# is worth more than the fix that prompted it: ANY NEW DATA FILE IN
# `lines_data/` WHOSE VALUES ARE LISTS BELONGS HERE. The symptom is `python
# lines.py` reporting "entry with no template" for a name that is obviously
# not dialogue.
NOT_DIALOGUE = {"mail.json", "news.json", "personal.json",
                "nations.json", "mynames.json"}

# How long a specific line stays blocked after use, regardless of the bag.
# Stops the same call landing twice inside one incident when two events fire
# close together (a pass and a lead change are often the same moment).
RECENT_S = 45.0

_pools = {}
_missing = set()


def load(force=False):
    """Load every pool. Missing files are survivable — a booth with fewer
    categories is better than a booth that will not start."""
    global _pools
    if _pools and not force:
        return _pools
    _pools = {}
    if not os.path.isdir(DATA_DIR):
        return _pools
    for fn in sorted(os.listdir(DATA_DIR)):
        if not fn.endswith(".json") or fn in NOT_DIALOGUE:
            continue
        path = os.path.join(DATA_DIR, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            _missing.add("%s: %s" % (fn, e))
            continue
        if isinstance(data, dict):
            for k, v in data.items():
                # Leading underscore = documentation, not dialogue. Without
                # this the "_comment" block in each file becomes a pool the
                # booth can draw from, and eventually reads its own notes out
                # on air.
                if k.startswith("_") or not isinstance(v, list):
                    continue
                _pools.setdefault(k, []).extend(v)
    return _pools


def pool(name):
    return load().get(name, [])


def _entry(e):
    """Accept bare strings as well as dicts, so simple pools stay readable."""
    if isinstance(e, str):
        return {"t": e}
    return e if isinstance(e, dict) else {"t": ""}


def allowed(entry, era):
    """Is this line legal for the car currently on track?"""
    e = _entry(entry)
    if era is None:
        return not (e.get("needs") or e.get("era") or e.get("disc"))
    for cap in e.get("needs", ()):
        if not era.has(cap):
            return False
    for cap in e.get("not", ()):
        if era.has(cap):
            return False
    eras = e.get("era")
    if eras and era.period not in eras:
        return False
    disc = e.get("disc")
    if disc and era.discipline not in disc:
        return False
    yr = e.get("year")
    if yr and not (yr[0] <= (era.year or 0) <= yr[1]):
        return False
    return True


def candidates(name, era, max_intensity=None):
    out = []
    for e in pool(name):
        d = _entry(e)
        if not d.get("t"):
            continue
        if not allowed(d, era):
            continue
        if max_intensity is not None and d.get("i", 0) > max_intensity:
            continue
        out.append(d)
    return out


_topics = None


def topics(force=False):
    """The booth's CONVERSATION topics, from `crosstalk.json`.

    Loaded separately from the line pools because the shape is different: a
    topic is a question bound to its own answers, and the binding is the whole
    point. Pulling the answers into a flat pool — which is what the normal
    loader would do — gives you Chuck replying to a question about tyres with
    an opinion about the weather, which is worse than not having the feature.

    `load()` ignores this file's contents for exactly that reason: its topic
    values are dicts, not lists, and the one list in it is `_ack`, which is
    underscore-prefixed and therefore documentation as far as the pool loader
    is concerned.
    """
    global _topics
    if _topics is not None and not force:
        return _topics
    _topics = {"_ack": [], "topics": {}}
    path = os.path.join(DATA_DIR, "crosstalk.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        _missing.add("crosstalk.json: %s" % e)
        return _topics
    for k, v in data.items():
        if k == "_ack" and isinstance(v, list):
            _topics["_ack"] = v
        elif (not k.startswith("_") and isinstance(v, dict)
              and (v.get("q") or v.get("qa"))):
            _topics["topics"][k] = v
    return _topics


def topic_for(era, phase, avoid=(), race_ready=True):
    """Pick a topic that is legal for this car and makes sense right now.

    Returns (name, topic) or (None, None).

    Two gates, and they cover different mistakes. PHASE stops the booth
    asking "can he hold on?" on lap two. `race_ready` stops it asking
    anything that ASSESSES the race so far before enough of one has happened
    — "who's impressed you?" three laps in is a question about nothing, and
    it is the clearest way the booth sounds like it is reading a script
    rather than watching. Topics about the circuit, the cars or the weather
    are exempt: they are true from the first lap.
    """
    names = []
    for name, t in topics()["topics"].items():
        if name in avoid:
            continue
        if t.get("needs_race") and not race_ready:
            continue
        when = t.get("when")
        if when and phase not in when:
            continue
        if not allowed(t, era):
            continue
        names.append(name)
    if not names:
        return None, None
    entry = _bag.pick("topic|%s|%s" % (_era_sig(era), phase),
                      [{"t": n} for n in sorted(names)], avoid_recent=False)
    if entry is None:
        return None, None
    return entry["t"], topics()["topics"][entry["t"]]


def topic_line(name, part, kw=None, qi=None):
    """One beat of a conversation: `part` is "q", "a" or "ack".

    A topic may bind answers to a SPECIFIC question via `qa`, and where it
    does that binding is honoured — `qi` is the index of the question that
    was asked. This matters for anything not phrased as an open question: a
    shared answer pool replied to "Is Silverstone a driver's track?" with
    "Everything, and all at once", which answers a different question
    entirely and is exactly what made the booth sound like it was not
    listening to itself.

    Topics with no `qa` keep the flat `q`/`a` lists, which is correct when
    every question in the topic is open enough that any answer fits.
    """
    from overlay_common import safe_format
    t = topics()["topics"].get(name) or {}
    qa = t.get("qa")
    if qa:
        if part == "q":
            items = [p.get("q", "") for p in qa]
        elif part == "a":
            pair = qa[qi] if (qi is not None and 0 <= qi < len(qa)) else qa[0]
            items = pair.get("a") or []
        else:
            items = t.get("ack") or []
    else:
        items = t.get(part) or []
    if part == "ack" and not items:
        items = topics()["_ack"]
    items = [d for d in (_entry(e) for e in items) if d.get("t")]
    if not items:
        return ""
    e = _bag.pick("topic|%s|%s|%s" % (name, part, qi if qi is not None else "-"),
                  items)
    return safe_format(e["t"], kw or {}) if e else ""


def topic_question(name, kw=None):
    """Pick a question and report WHICH one, so its answer can match.

    Returns (text, index). The index is meaningless for topics without `qa`
    and is simply carried through.
    """
    from overlay_common import safe_format
    t = topics()["topics"].get(name) or {}
    qa = t.get("qa")
    src = [p.get("q", "") for p in qa] if qa else (t.get("q") or [])
    items = [d for d in (_entry(e) for e in src) if d.get("t")]
    if not items:
        return "", None
    e = _bag.pick("topic|%s|q" % name, items)
    if e is None:
        return "", None
    idx = next((i for i, d in enumerate(items) if d["t"] == e["t"]), None)
    return safe_format(e["t"], kw or {}), idx


class Bag(object):
    """Draw-without-replacement selection with cross-session persistence."""

    def __init__(self, path=BAG_PATH):
        self.path = path
        self.state = {}       # key -> list of remaining indices
        self.recent = {}      # template -> last-used timestamp
        self._dirty = False
        self._saved = 0.0
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.state = d.get("state", {})
            self.recent = d.get("recent", {})
        except Exception:
            self.state, self.recent = {}, {}

    def save(self, force=False):
        """Throttled: the booth speaks often and this is on the draw path."""
        now = time.time()
        if not force and (not self._dirty or now - self._saved < 20.0):
            return
        self._saved = now
        self._dirty = False
        # Only keep recent entries that still matter, or the file grows
        # without bound across a long career.
        cutoff = now - RECENT_S * 4
        self.recent = {k: v for k, v in self.recent.items() if v > cutoff}
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"state": self.state, "recent": self.recent}, f)
        except Exception:
            pass

    def pick(self, key, items, avoid_recent=True):
        """One entry from `items`, not seen since the bag last reshuffled.

        `key` must encode everything that changes the candidate set, or a bag
        built for one era will be indexed against another era's list and hand
        back the wrong line.
        """
        if not items:
            return None
        n = len(items)
        bag = self.state.get(key)
        if not bag or max(bag) >= n:
            bag = list(range(n))
            random.shuffle(bag)
        now = time.time()
        tried = []
        while bag:
            i = bag.pop()
            item = items[i]
            t = item.get("t", "")
            if avoid_recent and now - self.recent.get(t, 0.0) < RECENT_S:
                tried.append(i)      # skip, but keep it for this round
                continue
            self.state[key] = bag + tried
            self.recent[t] = now
            self._dirty = True
            self.save()
            return item
        # Everything left was too recent. Reshuffle and take the least
        # recently used, rather than saying nothing at all.
        pool_sorted = sorted(range(n), key=lambda i: self.recent.get(
            items[i].get("t", ""), 0.0))
        i = pool_sorted[0]
        fresh = list(range(n))
        random.shuffle(fresh)
        self.state[key] = [j for j in fresh if j != i]
        self.recent[items[i].get("t", "")] = now
        self._dirty = True
        self.save()
        return items[i]

    def reset_session(self):
        """Called on a new session. Keeps the bags (variety should carry
        across races) but clears the short-term recency block, so the first
        call of a new race is never suppressed by the last one."""
        self.recent = {}
        self._dirty = True


_bag = Bag()


def pick(name, era, kw=None, max_intensity=None, bag=None):
    """Choose and format one line.

    Returns (text, intensity, persona_override) or (None, 0, None) when no
    legal line exists — which is a valid outcome, not an error. Saying
    nothing is always better than saying something wrong for the era.
    """
    from overlay_common import safe_format
    cands = candidates(name, era, max_intensity)
    if not cands:
        return None, 0, None
    key = "%s|%s" % (name, _era_sig(era))
    e = (bag or _bag).pick(key, cands)
    if e is None:
        return None, 0, None
    return _sentence_case(safe_format(e["t"], kw or {})), \
        e.get("i", 0), e.get("who")


def _sentence_case(text):
    """Capitalise the first letter of a rendered line.

    A template that OPENS on a slot inherits that slot's case, and several
    slots are lowercase prose: `{gap}` is "3 tenths", `{pos}` is "twelfth",
    `{dur}` is "half a minute". So "{g2} covering the front row" aired — and
    was captioned — as "a tenth covering the front row".

    Fixed here rather than by editing the 31 lines that currently open on
    one, because the next line anybody writes would reintroduce it. Lines
    opening on a name or a number are unaffected: those are already
    capitalised or begin with a digit.
    """
    if not text:
        return text
    out = list(text)
    start = True                 # are we at the beginning of a sentence?
    for i, ch in enumerate(out):
        if start:
            if ch.isalpha():
                out[i] = ch.upper()
                start = False
            elif not ch.isspace() and ch not in "\"'(":
                start = False    # a digit or symbol opens it; leave alone
        # Sentence-ending punctuation arms the next letter. This matters
        # because slots land mid-line too: "Improvement. {pos} on the sheet"
        # rendered as "Improvement. fourth on the sheet".
        if ch in ".!?":
            start = True
    return "".join(out)


def _era_sig(era):
    """Bag key component. Uses the things that change which lines are legal,
    not the whole era — otherwise every year would get its own bag and the
    variety would never build up."""
    if era is None:
        return "none"
    return "%s/%s" % (era.period, era.discipline)


def reset_session():
    _bag.reset_session()


def flush():
    _bag.save(force=True)


def stats():
    """Pool sizes, for the smoke test and the debug HUD."""
    p = load()
    return {k: len(v) for k, v in sorted(p.items())}


def validate():
    """Structural check over every pool.

    Catches the mistakes that are invisible until a specific era loads: a
    template with an unclosed brace, a capability that no era can ever
    provide (so the line is dead), or a pool that is empty for a whole
    discipline.
    """
    import era as era_mod
    problems = []
    known_caps = set()
    for caps in era_mod._OPEN_WHEEL_CAPS.values():
        known_caps |= set(caps)
    for caps in era_mod._DISCIPLINE_CAPS.values():
        known_caps |= set(caps)
    known_caps |= {"active_suspension", "semiauto", "grooved", "fuelration",
                   "stages", "restarts", "draft", "banking", "ptp", "ovals",
                   "headlights", "traffic", "pitwindow", "bop", "nightracing",
                   "contact"}
    periods = {k for k, _, _, _, _ in era_mod.PERIODS}

    for name, entries in load().items():
        if not entries:
            problems.append("pool '%s' is empty" % name)
        for e in entries:
            d = _entry(e)
            t = d.get("t", "")
            if not t:
                problems.append("%s: entry with no template" % name)
                continue
            if t.count("{") != t.count("}"):
                problems.append("%s: unbalanced braces in %r" % (name, t[:50]))
            for cap in list(d.get("needs", ())) + list(d.get("not", ())):
                if cap not in known_caps:
                    problems.append("%s: unknown capability %r in %r"
                                    % (name, cap, t[:40]))
            for p in d.get("era", ()):
                if p not in periods:
                    problems.append("%s: unknown period %r" % (name, p))
    return problems


if __name__ == "__main__":
    load()
    st = stats()
    if not st:
        print("No pools found in %s" % DATA_DIR)
        sys.exit(1)
    print("%d pools, %d lines total" % (len(st), sum(st.values())))
    for k, v in st.items():
        print("  %-24s %d" % (k, v))
    probs = validate()
    if probs:
        print("\n%d problem(s):" % len(probs))
        for p in probs[:40]:
            print("  " + p)
    else:
        print("\nAll pools valid.")
