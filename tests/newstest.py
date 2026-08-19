"""The news feeds: three of them, and only one is new knowledge.

The whole feature rests on a restraint rather than a capability. Any of these
headlines is easy to generate; what is hard is generating only the ones that
are TRUE of the season the user just drove, and never a second version of
something the booth has already said out loud.

  * MILESTONES come from `drivers.standing()` and `drivers.just_won_title()`
    — the booth's own functions. A parallel detector eventually disagrees with
    the first one, and the viewer believes the headline, because he can
    re-read it.
  * SEASON DRAMA is generated from the career store, so it cannot contradict
    the standings screen: it is computed from the same classifications.
  * PERIOD CONTROVERSY is knowledge, and it is the one that could lie. It may
    never narrate an event in his season, so it takes no slots at all.

    python tests/newstest.py
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import drivers as drivers_mod
import era as era_mod
import inbox
import news
import season as S

fails = []
def check(c, l, e=""):
    print(("  [ OK ] " if c else "  [FAIL] ") + l + (("  " + e) if e else ""))
    if not c:
        fails.append(l)


_tmp = tempfile.mkdtemp(prefix="factortv_news_")
S.CAREER_DIR = _tmp
CLS = "F1 Test 2025"


def _season(orders, me="Kandasamy", cls=CLS, length=None, **kw):
    """A career where each round finished in the given order."""
    c = S.create("open", me=me, rounds=length or len(orders), cls=cls, **kw)
    for i, order in enumerate(orders, start=1):
        pos = order.index(me) + 1 if me in order else len(order) + 1
        c.record({"n": i, "slug": "t%d" % i, "pos": pos, "laps": 20,
                  "race_laps": 20, "cls": cls,
                  "classified": [(nm, p + 1) for p, nm in enumerate(order)]})
    return c


def _kinds(c):
    return [m["kind"] for m in inbox.messages(c, feed="news")]


print("\n1. THE DATA OBEYS ITS OWN RULES")
errs = news.validate()
check(not errs, "news.json validates", "; ".join(errs[:3]))
check(len(news.kinds()) >= 8, "enough kinds to be a feed",
      "%d" % len(news.kinds()))
check(set(news.periods()) >= {"1988", "2021", "2025"},
      "period context exists for every season we hold records for",
      str(sorted(news.periods())))

print("\n2. AN ARTICLE IS AN ARTICLE")
short = []
for k in news.kinds():
    for i, t in enumerate(news._pool(k)):
        if len(t["body"]) < 2 or sum(len(p.split()) for p in t["body"]) < 60:
            short.append("%s[%d]" % (k, i))
for y, pool in news.periods().items():
    for i, t in enumerate(pool):
        if len(t["body"]) < 2 or sum(len(p.split()) for p in t["body"]) < 60:
            short.append("period %s[%d]" % (y, i))
check(not short, "every article is a paragraph or two", str(short[:4]))

print("\n2b. THE SAME HEADLINE TWICE IS A TEMPLATE")
# The user's verdict on the first version was exact: the repetition got bad
# enough that the personal mail became the thing he was WAITING for, which
# destroys the only mechanism the story has.
thin = [k for k in news.kinds() if len(news._pool(k)) < 2]
check(not thin, "every kind of article has more than one wording", str(thin))
check(len(news.trivia()) >= 8, "and there is a stock of real history to run",
      "%d facts" % len(news.trivia()))

print("\n2c. DID YOU KNOW — REAL, AND NEVER AHEAD OF ITS OWN SEASON")
# Inventing a fact to fill a feed is the one thing this product has refused
# from the first day. Each carries the year it became true, and a season can
# only be told a fact that was already true in it.
undated = [t["subject"] for t in news.trivia() if not t.get("since")]
check(not undated, "every fact is dated", str(undated[:2]))
early = _season([["A", "B", "Kandasamy"]] * 6, cls="F1 1988 Historic Edition")
news.refresh(early)
told = [m for m in inbox.messages(early, feed="news")
        if m["kind"] == "did_you_know"]
late = [m for m in told if "Group B" in m["subject"]]
check(not late, "a 1988 season is never told about the end of Group B",
      str([m["subject"] for m in told]))

print("\n3. EVERY KIND HAS SOMETHING THAT PUBLISHES IT")
# LAW 21. A template nothing generates is invisible and `validate()` calls it
# healthy, because the template is perfectly well formed.
src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "news.py"), encoding="utf-8").read()
orphans = [k for k in news.kinds() if ('"%s"' % k) not in src]
check(not orphans, "no template is unreachable", str(orphans))

print("\n4. THE SEASON'S OWN DRAMA, TRUE BY CONSTRUCTION")
c = _season([
    ["Max Verstappen", "Lando Norris", "Oscar Piastri", "Kandasamy"],
    ["Lando Norris", "Max Verstappen", "Kandasamy", "Oscar Piastri"],
    ["Lando Norris", "Oscar Piastri", "Max Verstappen", "Kandasamy"],
])
news.refresh(c)
ks = _kinds(c)
check("news_lead_change" in ks, "a new championship leader is news", str(ks))
lead = next(m for m in inbox.messages(c, feed="news")
            if m["kind"] == "news_lead_change")
table = c.standings(upto=2)
check(("%d points" % table[0][1]) in " ".join(lead["body"]),
      "and it quotes the table it came from, exactly",
      "table says %d" % table[0][1])
check(lead["round"] == 2,
      "never after round one, when somebody leads by definition",
      str(lead["round"]))

print("\n5. A LEAD IS ONLY NEWS WHEN IT IS CLOSING")
# Both halves are required. A gap that has been small all season is the SHAPE
# of the championship, not news about it — and a feed that reports the shape
# every round is filler.
runaway = _season([["A", "Kandasamy", "B"]] * 4, me="Kandasamy")
news.refresh(runaway)
check("news_lead_gap" not in _kinds(runaway),
      "a steady gap is not reported over and over", str(_kinds(runaway)))
closing = _season([["A", "B", "Kandasamy"], ["A", "B", "Kandasamy"],
                   ["B", "A", "Kandasamy"], ["B", "A", "Kandasamy"]])
news.refresh(closing)
check("news_lead_gap" in _kinds(closing),
      "a lead that is actually coming down is", str(_kinds(closing)))

print("\n6. DOMINANCE AND CONSISTENCY ARE DIFFERENT STORIES")
dom = _season([["A", "B", "Kandasamy"]] * 3)
news.refresh(dom)
check("news_dominance" in _kinds(dom), "three wins from three is a procession")
d = next(m for m in inbox.messages(dom, feed="news")
         if m["kind"] == "news_dominance")
check("three" in d["subject"] and not any(ch.isdigit() for ch in d["subject"]),
      "counted in words, because this is prose", d["subject"])
check("news_streak_podium" in _kinds(dom),
      "and the man who was there every time gets his own story")

print("\n6b. A PAPER WRITES ABOUT MORE THAN THE TABLE")
# The user, reading a whole career: the feed was "so boring and not anything
# like a real news article - they speak about drivers' performances and quali
# performances". Four more kinds, all read off the store: Saturday, a run of
# form, a recovery through the field, and a look back at the season so far.
sat = _season([["Kandasamy", "A", "B", "C"]] * 6, length=6)
for i in range(1, 7):
    sat.record_quali(i, 1 if i == 2 else 5, field=8, slug="t%d" % i)
news.refresh(sat)
ks = _kinds(sat)
check("news_quali_pole" in ks, "his pole gets a Saturday story", str(set(ks)))
poles = [m for m in inbox.messages(sat, feed="news")
         if m["kind"] == "news_quali_pole"]
check(len(poles) == 1,
      "ONE per season - a paper does not run 'quick again on Saturday' six "
      "times a year", str(len(poles)))
check("news_retro" in ks, "and the season gets looked back at, once")

form = _season([["A", "B", "Kandasamy", "C"],
                ["B", "A", "Kandasamy", "C"],
                ["A", "Kandasamy", "B", "C"],
                ["A", "B", "Kandasamy", "C"],
                ["Kandasamy", "A", "B", "C"],
                ["A", "Kandasamy", "B", "C"]], length=6)
news.refresh(form)
ks = _kinds(form)
check("news_form" in ks, "a run of podiums is a story about the man in it",
      str(set(ks)))
lead = form.standings()[0][0]
runs = [m for m in inbox.messages(form, feed="news")
        if m["kind"] == "news_form"]
check(all(lead not in m["subject"] for m in runs),
      "NEVER ABOUT THE CHAMPIONSHIP LEADER - that is the table read aloud",
      str([m["subject"] for m in runs]))

print("\n6c. AND ABOUT DRIVERS IT ACTUALLY KNOWS")
# `news_profile` quotes `drivers.standing()`, the same source the commentary
# uses, so the paper and the booth can never disagree about who somebody is.
real = _season([["Lando Norris", "Max Verstappen", "Kandasamy", "A"]] * 4,
               length=4)
news.refresh(real)
profiles = [m for m in inbox.messages(real, feed="news")
            if m["kind"] == "news_profile"]
check(profiles, "a driver with a real record gets written about",
      str([m["subject"] for m in profiles]))
made_up = _season([["Nobody At All", "Someone Else", "Kandasamy"]] * 4,
                  cls="GT3 World Series", length=4)
news.refresh(made_up)
check(not [m for m in inbox.messages(made_up, feed="news")
           if m["kind"] == "news_profile"],
      "and a driver with no record anywhere gets nothing invented for him")

print("\n6f. THE CURATED HALF OF A RISE")
# The status headlines say WHAT happened; these say what it is like — the
# photographs that have nothing to do with racing, the queue at the merchandise
# stand, somebody saying a name out loud that a young driver has not earned.
check(len(news.load().get("news_fame") or []) >= 4,
      "there is real colour written for the rise",
      str(len(news.load().get("news_fame") or [])))
famous = _season([["Kandasamy", "A", "B"]] * 8, length=8)
famous.data["ladder"] = {"path": "single_seater", "reached": 4, "results": {}}
famous.data["ladder_history"] = [{"name": "Formula 2", "pos": 1, "rounds": 6,
                                  "when": i} for i in range(4)]
news.refresh(famous)
ks = _kinds(famous)
check("news_fame" in ks, "a driver who is somebody gets written about",
      str(set(ks)))
# ...AND A DRIVER WHO IS NOBODY YET DOES NOT. Being told he is popular while
# still in karting is the kind of wrongness that makes a whole feed silly.
kid = _season([["Kandasamy", "A", "B"]] * 8, length=8)
kid.data["ladder"] = {"path": "single_seater", "reached": 0, "results": {}}
news.refresh(kid)
check("news_fame" not in _kinds(kid),
      "and a rookie in karting is never told he is popular with anybody",
      str(set(_kinds(kid))))

print("\n6g. COMPARISONS NAME REAL GREATS, AND ARE DATED")
# Every one is about what PEOPLE ARE SAYING about the player — the mood around
# a rising driver, which is a real thing a paper reports. None claims he has
# equalled anybody, and none asserts anything new about the great being named.
undated = [c["subject"] for c in news.comparisons() if not c.get("since")]
check(not undated, "every comparison carries the year it became sayable",
      str(undated[:2]))
check(len(news.comparisons()) >= 6, "and there are several",
      str(len(news.comparisons())))
old = [c for c in news.comparisons() if int(c["since"]) <= 1966]
check(all("Schumacher" not in " ".join(c["body"]) for c in old),
      "nothing sayable in 1966 names a driver who had not started yet")
comp = [m for m in inbox.messages(famous, feed="news")
        if m["kind"] == "news_compare"]
check(comp, "a rising driver draws one", str([m["subject"] for m in comp]))
body = " ".join(p for m in comp for p in m["body"]).lower()
check("better than" not in body and "greater than" not in body,
      "and it never claims he has beaten anybody's record", body[:60])

print("\n6h. RIVALRIES ARE PROVED, NOT ASSERTED")
# ONE DETECTOR, THREE RENDERINGS: `Career.rivals()` decides a rivalry exists,
# and the paper, the commentary and the standings all read it — so they can
# never disagree about who is fighting whom.
nose = _season([["Kandasamy", "Vinter", "Roth"], ["Vinter", "Kandasamy", "Roth"],
                ["Kandasamy", "Vinter", "Roth"], ["Vinter", "Kandasamy", "Roth"],
                ["Kandasamy", "Vinter", "Roth"], ["Vinter", "Kandasamy", "Roth"]],
               length=6)
riv = nose.rivals()
check(riv and {riv["a"], riv["b"]} == {"Kandasamy", "Vinter"},
      "two drivers who keep finishing together are a rivalry", str(riv))
check(riv["a"] == "Kandasamy", "and it is framed around the player")
news.refresh(nose)
check("news_rivalry" in _kinds(nose), "which the feed writes about",
      str(set(_kinds(nose))))
# A DOMINANT SEASON IS NOT A RIVALRY. Men who are close on points but never on
# the road together are having separate seasons.
alone = _season([["Kandasamy", "Vinter", "Roth"]] * 6, length=6)
r2 = alone.rivals()
check(not (r2 and "Kandasamy" in (r2["a"], r2["b"])),
      "a driver nobody can stay near has no rivalry", str(r2))
# ...but the fight BEHIND him is still a story, which is what he asked for.
check(r2 is None or not r2["player"],
      "while two AI drivers scrapping over fourth are their own story",
      str(r2))

print("\n6i. THE NEEDLE FOLLOWS THE FACTS")
# The spiky piece lands on a rivalry the reader has already been shown, rather
# than announcing one — which is the order a real paper works in.
# ROUND BY ROUND, the way a season is actually played — a backfill posts
# several rounds in one pass and would run both pieces at once.
live = S.create("open", me="Kandasamy", rounds=9, cls=CLS)
def _round(n, order):
    live.record({"n": n, "slug": "t%d" % n, "pos": order.index("Kandasamy") + 1,
                 "laps": 20, "race_laps": 20, "cls": CLS,
                 "classified": [(nm, p + 1) for p, nm in enumerate(order)]})
    news.refresh(live)
    return [m["kind"] for m in inbox.messages(live, feed="news")]

for i in range(1, 5):
    ks = _round(i, ["Kandasamy", "Vinter", "Roth"] if i % 2
                else ["Vinter", "Kandasamy", "Roth"])
check("news_rivalry" in ks, "the rivalry is reported once it is provable",
      str(set(ks)))
check("news_needle" not in ks,
      "and nobody is quoted on the weekend it is first reported",
      str(set(ks)))
for i in range(5, 9):
    ks = _round(i, ["Kandasamy", "Vinter", "Roth"] if i % 2
                else ["Vinter", "Kandasamy", "Roth"])
check("news_needle" in ks, "the quotes come once it has been on the page",
      str(set(ks)))


print("\n7. MILESTONES COME FROM THE BOOTH'S OWN FUNCTIONS")
# Not from a second detector. This is asserted the only way that means
# anything: the same question, asked of both, must give the same answer.
title = _season([["Kandasamy", "A", "B"]] * 3, length=3)
news.refresh(title)
e = era_mod.classify(CLS, "")
said = [nm for nm, _ in title.rounds[-1]["classified"]
        if drivers_mod.just_won_title(nm, e, title, 3)]
printed = [m for m in inbox.messages(title, feed="news")
           if m["kind"] in ("news_title_first", "news_title_more",
                            "news_champion")]

# THE BOOTH HAS TWO TITLE PATHS, AND THIS TEST ONLY KNEW ABOUT ONE.
#
# `_championship_call` announces a championship whenever `title_state()`
# says the maths is settled, and only UPGRADES the wording to the driver
# record when `just_won_title` also agrees. That is why the live log has
# Miles saying "Dante Kandasamy has won this championship" in a Clio Cup
# season where no driver on the grid has a record anywhere.
#
# Asserting the feed against `just_won_title` alone therefore encoded a
# narrower contract than the product has — and it was the reason the user
# won the Hot hatch title and read nothing about it: the only feed that
# could print a championship opened with `if era is None: return []`.
#
# The rule that actually matters is unchanged and is what is checked here:
# ONE SOURCE. The paper prints a title exactly when the booth would announce
# one, and picks the career-record wording exactly when the booth would.
decided = bool((title.title_state() or {}).get("decided"))
check(decided == bool(printed),
      "the feed prints a title exactly when the BOOTH would announce one",
      "decided=%s / news %d" % (decided, len(printed)))
record_worded = [m for m in printed
                 if m["kind"] in ("news_title_first", "news_title_more")]
# WHICH WORDING, AND THE LINE IS ABOUT WHAT CAN BE CHECKED.
#
# "The first of a career" is a claim about a record. For a real driver that
# record is `drivers.json` and `just_won_title` owns it. For the player it is
# THIS CAREER FILE, which counted every season he has finished — so the claim
# is true and he can go and read it in the record view.
#
# For anybody else it is neither, and inventing a career for a GT3 mod's AI
# is the one thing this product refuses (see section 8). So the invariant is
# not "only when `just_won_title` agrees", it is: the career-record wording
# is only ever used about somebody whose record we actually hold.
for m in record_worded:
    known = bool(said) or (title.me or "").lower() in m["subject"].lower()
    check(known,
          "the career-record wording is only used where a record exists",
          m["subject"])
check(len(printed) - len(record_worded) >= 0
      and all(m["kind"] == "news_champion" for m in printed
              if m not in record_worded),
      "...and anybody else's title is reported without a career claim")

# AN AI CHAMPION GETS THE NEUTRAL WORDING. The table is a fact; his career
# is not something this overlay has ever seen.
ai = _season([["A", "Kandasamy", "B"]] * 3, length=3)
news.refresh(ai)
ai_titles = [m for m in inbox.messages(ai, feed="news")
             if m["kind"] in ("news_champion", "news_title_first",
                              "news_title_more")]
check(ai_titles and all(m["kind"] == "news_champion" for m in ai_titles),
      "an AI champion is reported, and no career is invented for him",
      str([m["kind"] for m in ai_titles]))
check(len(printed) <= 1, "and never twice for one championship",
      str([m["subject"] for m in printed]))

print("\n7b. THE TITLE FIGHT, AND IT READS THE BOOTH'S OWN ARITHMETIC")
# `title_scenarios()` is proven exhaustively in `pointstest.py`. What is
# checked here is that the PAPER cannot say something the maths did not, and
# that the wording changes when the situation does.

W = ["Kandasamy", "Borda", "C", "D", "E", "F"]
L = ["Borda", "Kandasamy", "C", "D", "E", "F"]

fight = _season([W, L, W, L, W], length=6)
news.refresh(fight)
ks = _kinds(fight)
check(any(k.startswith("news_title_") for k in ks),
      "the run-in gets written about at all", str(set(ks)))

# LEVEL IS NOT A LEAD. `{gap}` was populated and the sentence was still
# false — "leads Borda by 0 points" about two men who are dead level. LAW 5
# is usually about an empty slot; this is the same failure with a slot that
# is full and wrong, which is harder to see and worse to read.
zero = [m for m in inbox.messages(fight, feed="news")
        if "by 0 points" in " ".join(m["body"]) or "0 points" in m["subject"]]
check(not zero, "a level championship is never reported as a lead",
      str([m["subject"] for m in zero[:2]]))

# WHEN THE ANSWER IS A WIN, SAY SO. "He needs to finish first or better" is
# not a sentence anybody says, and it is a genuinely different story from
# needing fifth: one is a target to manage, the other is a race to go and win.
must_win = [m for m in inbox.messages(fight, feed="news")
            if m["kind"] == "news_title_win"]
sc = fight.title_scenarios(upto=4)
if sc and sc.get("secure") == 1:
    check(must_win, "needing a win is its own piece, not an ordinal",
          str([m["subject"] for m in must_win]))
else:
    check(True, "needing a win is its own piece, not an ordinal", "(n/a)")

# AND NOTHING AT ALL WHEN THE MATHS CANNOT BE EXACT (LAW 4).
open_ended = S.create("open", me="Kandasamy", rounds=0, cls=CLS)
open_ended.record({"n": 1, "slug": "t1", "pos": 1, "laps": 20,
                   "race_laps": 20, "cls": CLS,
                   "classified": [(n, i + 1) for i, n in enumerate(W)]})
news.refresh(open_ended)
check(not [k for k in _kinds(open_ended) if k.startswith("news_title_")],
      "a season with no declared length claims no title arithmetic",
      str(set(_kinds(open_ended))))

# A POSITION IN PROSE IS WRITTEN OUT. "The number he has to remember is 7th"
# is the exact tell that makes a generated article read as generated.
check("7th" not in news._spoken_ordinal(7)
      and news._spoken_ordinal(7) == "seventh",
      "finishing positions are words, not digits",
      news._spoken_ordinal(7))


print("\n7c. A NEW NAME ON THE ENTRY LIST")
# Asked for: "there must also be news reports about 'there's a new face on the
# grid, Dante has joined the Formula 4 series' and then more specific ones
# depending on if I selected or got promoted — choices of words is important."
#
# He is right that the words ARE the feature. Arriving in a division is one
# event with five different meanings, and a feed that writes the same sentence
# for all of them has not been watching his career. `advance()` records which
# it was, so this reads a fact rather than inferring one.

def _rung(pos_each, path="single_seater", tier=0, length=3, me="Kandasamy"):
    car = S.create("open", me=me, rounds=length, ladder_path=path,
                   tier_index=tier)
    for i, pos in enumerate(pos_each, start=1):
        other = 1 if pos != 1 else 2
        car.record({"n": i, "slug": "t%d" % i, "pos": pos, "laps": 20,
                    "race_laps": 20,
                    "classified": [(me, pos), ("A Rival", other)]})
    return car


def _arrivals(c):
    return [m["kind"] for m in inbox.messages(c, feed="news")
            if m["kind"].startswith("news_arrival")]


deb = _rung([1])
news.refresh(deb)
check(_arrivals(deb) == ["news_arrival_debut"],
      "a career that begins here gets the new-face piece", str(_arrivals(deb)))

# PROMOTED AS CHAMPION IS A DIFFERENT ARRIVAL from promoted. `reigning` is
# only true while it IS the season just gone.
champ = _rung([1, 1, 1])
champ.advance("promote")
champ.record({"n": 1, "slug": "t1", "pos": 1, "laps": 20, "race_laps": 20,
              "classified": [("Kandasamy", 1), ("A Rival", 2)]})
news.refresh(champ)
check("news_arrival_champion" in _arrivals(champ),
      "the champion of the division below arrives as one",
      str(_arrivals(champ)))

# A SIDEWAYS MOVE IS NOT A PROMOTION and the piece must not congratulate him.
sw = _rung([1, 1, 1])
sw.advance("promote")
for _n in range(1, 4):
    sw.record({"n": _n, "slug": "t%d" % _n, "pos": 4, "laps": 20,
               "race_laps": 20,
               "classified": [("Kandasamy", 4), ("A Rival", 1)]})
sw.advance("switch", path_key="endurance", tier_index=1)
sw.record({"n": 1, "slug": "x1", "pos": 3, "laps": 20, "race_laps": 20,
           "classified": [("Kandasamy", 3), ("A Rival", 1)]})
news.refresh(sw)
check("news_arrival_switch" in _arrivals(sw),
      "a switch reads as a change of direction, not a step up",
      str(_arrivals(sw)))
promo_words = ("promotion", "steps up", "step up", "earned")
sw_text = " ".join(m["subject"] + " " + " ".join(m["body"])
                   for m in inbox.messages(sw, feed="news")
                   if m["kind"] == "news_arrival_switch").lower()
check(not any(w in sw_text for w in ("promotion confirmed", "steps up to")),
      "and never congratulates him on a promotion he did not get")

# ONE PIECE PER RUNG, however many seasons he spends there.
again = _rung([4, 4, 4])
news.refresh(again)
again.advance("retry")
again.record({"n": 1, "slug": "r1", "pos": 4, "laps": 20, "race_laps": 20,
              "classified": [("Kandasamy", 4), ("A Rival", 1)]})
news.refresh(again)
check(len(_arrivals(again)) <= 1,
      "staying for another season is not an arrival", str(_arrivals(again)))


# ...AND IT DOES NOT WAIT FOR HIM TO RACE FIRST.
#
# Reported by the user: joining a new division produced no article. The piece
# existed and could not be reached, because `refresh` returned empty for a
# season with no rounds and the arrival was generated inside the per-round
# loop — so the paper only noticed the new man AFTER he had raced. "There is a
# new face on the grid" is a week late by then.
fresh = S.create("open", me="Kandasamy", rounds=3,
                 ladder_path="single_seater", tier_index=0)
news.refresh(fresh)
check(_arrivals(fresh) == ["news_arrival_debut"],
      "the arrival piece lands BEFORE the first race of a division",
      str(_arrivals(fresh)))

joined = _rung([1, 1, 1])
joined.advance("promote")
news.refresh(joined)
check("news_arrival_champion" in _arrivals(joined),
      "and on the day he takes the seat above, not after his first race in it",
      str(_arrivals(joined)))


print("\n7d. THE LAST RACE OF THE SEASON IS NEWS ON ITS OWN")
# Asked for: "there wasn't a News report before the last race of the season to
# say something like 'This seasons last race is upon us'". Every other piece in
# this feed reports something that has HAPPENED, so a season with no title
# fight to write about reached its finale in silence.
#
# It can only fire when the penultimate round is banked: there is no calendar
# here, so nothing knows a race is coming until the one before it is stored.

def _finales(c):
    return [m for m in inbox.messages(c, feed="news")
            if m["kind"].startswith("news_finale")]


def _season_of(pat, rounds=5, me="Kandasamy", field=("Bellini", "Vasseur")):
    car = S.create("open", me=me, rounds=rounds, ladder_path="single_seater",
                   tier_index=0)
    for n, pos in enumerate(pat, start=1):
        order = list(field)
        order.insert(pos - 1, me)
        car.record({"n": n, "slug": "t%d" % n, "pos": pos, "laps": 20,
                    "race_laps": 20,
                    "classified": [(nm, i + 1) for i, nm in enumerate(order)]})
        news.refresh(car)
    return car


# A SEASON WITH THE TITLE STILL LIVE gets the preview, and it names how many
# men can still win it — counted from the points still on the table (LAW 17),
# never asserted.
open_ = _season_of([2, 3, 1, 2])
fin = _finales(open_)
check(len(fin) == 1 and fin[0]["kind"] == "news_finale_title",
      "a live championship gets the finale preview",
      str([m["kind"] for m in fin]))

# A SETTLED ONE GETS A DIFFERENT PIECE, because a paper that writes "it all
# comes down to Sunday" about a championship already won is the one thing this
# feed may never do.
gone = _season_of([1, 1, 1, 1])
fin = _finales(gone)
check(len(fin) == 1 and fin[0]["kind"] == "news_finale_decided",
      "a decided one is never written as a cliffhanger",
      str([m["kind"] for m in fin]))

# IT FIRES ONCE, and it fires BEFORE the last round rather than after it.
check(all(m["round"] == 4 for m in _finales(gone)),
      "and it is filed against the round before the last, not the last",
      str([m["round"] for m in _finales(gone)]))
_before = len(_finales(gone))
news.refresh(gone)
news.refresh(gone)
check(len(_finales(gone)) == _before,
      "refreshing does not file it again")

# THE ARITHMETIC PIECE WINS IF IT FIRED. `news_title_maths` and its siblings
# are this same preview with better information in them — what HE needs — and
# two articles about one afternoon is the repetition problem again.
maths = _season_of([1, 2, 1, 2])
kinds = [m["kind"] for m in inbox.messages(maths, feed="news")]
check(any(k in ("news_title_win", "news_title_maths", "news_title_finish")
          for k in kinds),
      "a driver who can settle it on Sunday gets the arithmetic piece",
      str([k for k in kinds if k.startswith("news_title")]))
check(not _finales(maths),
      "and NOT a second article about the same afternoon",
      str([m["kind"] for m in _finales(maths)]))

# A ONE-ROUND SEASON HAS NO BUILD-UP TO WRITE.
one = _season_of([1], rounds=1)
check(not _finales(one), "a single-round season gets no preview of itself")

# NO SLOT EVER AIRS EMPTY (LAW 5) — the same rule the letters follow, and the
# reason a wording that needs a gap is skipped when two men are level.
for _m in _finales(open_) + _finales(gone):
    _txt = _m["subject"] + " " + " ".join(_m["body"])
    check("{" not in _txt and "  " not in _txt,
          "the finale piece renders with every slot filled",
          _txt[:60])


print("\n8. IT NEVER INVENTS A RECORD FOR A DRIVER IT DOES NOT KNOW")
# THE ONE THING THIS PRODUCT REFUSES TO DO. A GT3 mod's AI has no history
# anywhere, so a milestone about him could only be invented — the season feed
# talks about the racing instead.
gt = _season([["Driver One", "Driver Two", "Kandasamy"]] * 3,
             cls="GT3 World Series")
news.refresh(gt)
ks = _kinds(gt)
check(not any(k in ("news_first_win", "news_win_tally", "news_title_first",
                    "news_title_more") for k in ks),
      "no career milestone for a driver with no career", str(ks))
check("news_dominance" in ks or "news_streak_podium" in ks,
      "but the season's own drama still runs, because it was watched", str(ks))

print("\n9. PERIOD CONTEXT IS NEVER ABOUT HIS SEASON")
# The line that has bitten three times. A period piece is paddock context —
# period-true, claims nothing about his races, and cannot be contradicted by
# his own standings.
slots = [t for y, pool in news.periods().items() for t in pool
         if "{" in " ".join(t["body"] + [t["subject"]])]
check(not slots, "no period piece takes a slot at all",
      str([t["subject"] for t in slots[:2]]))
p = [m for m in inbox.messages(c, feed="news") if m["kind"] == "period"]
check(p, "and a season in a year we hold gets some", str(len(p)))
names = ("Kandasamy", "Norris", "Verstappen", "Piastri")
check(not any(nm in " ".join(m["body"]) for m in p for nm in names),
      "naming nobody who is in his championship")
kart = _season([["A", "B", "Kandasamy"]] * 4, cls="Kart")
news.refresh(kart)
check(not any(k == "period" for k in _kinds(kart)),
      "a season in no year we hold gets none, rather than the wrong year's",
      str(_kinds(kart)))

print("\n10. IT SHARES THE INBOX'S GUARANTEES")
n = len(inbox.messages(c, feed="news"))
news.refresh(c); news.refresh(c)
check(len(inbox.messages(c, feed="news")) == n,
      "refresh is idempotent, like the mail", "%d -> %d"
      % (n, len(inbox.messages(c, feed="news"))))
mid = inbox.messages(c, feed="news")[0]["id"]
inbox.delete(c, mid)
news.refresh(c)
check(inbox.get(c, mid) is None, "a deleted article stays deleted")
check(all(m.get("feed") == "news" for m in inbox.messages(c, feed="news")),
      "and every article is tagged as news")
check(all((m.get("feed") or "mail") == "mail"
          for m in inbox.messages(c, feed="mail")),
      "while the mail tab is unpolluted by it")

print("\n11. THE TWO FEEDS ARE STILL THE SAME SHAPE")
# The story's camouflage rule survives the split: news and mail differ by ONE
# field, which every message carries. A field only some messages have is a
# field the archive can sort by, and sorting is one step from highlighting.
inbox.refresh(c)
shapes = {tuple(sorted(m)) for m in inbox.messages(c)}
check(len(shapes) == 1, "every message in the archive has identical fields",
      str(len(shapes)))

shutil.rmtree(_tmp, ignore_errors=True)
print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
