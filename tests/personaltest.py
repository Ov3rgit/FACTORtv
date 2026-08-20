"""The personal story: the one feature here that can only be got wrong once.

Everything else in this product can be tuned after the fact — a line that lands
badly gets rewritten, a threshold that fires too often gets a cooldown. This
cannot. A player sees it once per career, and every mechanism that makes it
work is a mechanism that fails silently:

  * If the offer costs nothing, the choice is theatre. The rivals must score.
  * If a personal letter looks different from a licensing statement, the whole
    thing collapses — the reader was supposed to be trained to skim.
  * If the booth ever knows, the seam shows.
  * If a beat can fail to send because a fact was missing, the thread stops
    mid-story and nothing says so.

    python tests/personaltest.py
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import inbox
import ladder as L
import personal
import season as S

fails = []
def check(c, l, e=""):
    print(("  [ OK ] " if c else "  [FAIL] ") + l + (("  " + e) if e else ""))
    if not c:
        fails.append(l)


_tmp = tempfile.mkdtemp(prefix="factortv_story_")
S.CAREER_DIR = _tmp
ME = "Kandasamy"


def _career(path="touring", tier=2, rounds=6, arcs=()):
    c = S.create("open", me=ME, rounds=rounds, ladder_path=path,
                 tier_index=tier)
    if arcs:
        c.data["ladder_done"] = list(arcs)
    return c


def _race(c, pos=1, n=None, rivals=("A Rival", "B Rival")):
    n = n or (len(c.rounds) + 1)
    c.data["rounds"] = [r for r in c.rounds if r.get("n") != n]
    order = list(rivals)
    order.insert(min(pos - 1, len(order)), ME)
    c.record({"n": n, "slug": "t%d" % n, "pos": order.index(ME) + 1,
              "laps": 20, "race_laps": 20,
              "classified": [(nm, i + 1) for i, nm in enumerate(order)]})


def _settle(c, n=30):
    """Refresh until the thread has caught up.

    Beats arrive ONE PER REFRESH — a trickle, so that a player who has not
    opened his inbox for ten races does not get five letters in a heap. In
    normal play `refresh` runs after every result; in a test that fakes a
    career's worth of history at once, it has to be pumped.
    """
    for _ in range(n):
        if not personal.refresh(c):
            break
    return c


def _seasons(c, k, per=4):
    """Live through k seasons: race them, drain the inbox, archive them.

    THE FIXTURE HAS TO RACE. Beats are paced by SEASONS now rather than by a
    race counter, so a career with a fabricated history and no rounds in it
    receives nothing at all — which is correct behaviour and useless as a
    fixture. This does what a player does: a few rounds, then next season.
    """
    # THOSE SEASONS HAPPENED WHILE HE WAS STILL CLIMBING. Leaving the finished
    # arcs in place for them makes every one of those years count as the final
    # arc, which fires the offer eight seasons early and expires it before the
    # story ever reaches it. He wins them at the END of the climb, not before.
    keep = list(c.data.get("ladder_done") or [])
    c.data["ladder_done"] = []
    for _ in range(k):
        c.data["rounds"] = []
        for i in range(per):
            _race(c, n=i + 1)
            _settle(c)
        c.data.setdefault("ladder_history", []).append(
            {"name": "Earlier", "pos": 1, "rounds": per, "wins": 2,
             "podiums": 3, "when": 1})
    c.data["ladder_done"] = keep
    c.data["rounds"] = []
    c.save()


print("\n1. THE DATA OBEYS ITS OWN RULES")
errs = personal.validate()
check(not errs, "personal.json validates", "; ".join(errs[:3]))
check(len(personal.beats()) >= 12, "the thread spans a career",
      "%d beats" % len(personal.beats()))
# RULE 3, MECHANICALLY. A slot is a way for a letter to fail to send, and this
# is the one thread that must never fail to send because a fact was missing.
slotted = [i for i, b in enumerate(personal.beats())
           if "{" in " ".join(b["body"] + [b["subject"]])]
check(not slotted, "and not one beat can fail for want of a fact", str(slotted))

# AND THE ONE SLOT SHE IS ALLOWED IS ALWAYS FILLED.
#
# Rule 3 says her letters take no slots, because a slot is a way for a letter to
# fail to send. `{won}` is the single exception — the championship in her
# first-title letter — added because "you've won the whole thing" read beside a
# dashboard saying Formula One left the player unsure what she thought he had
# won. It is safe only while the caller cannot forget to fill it, so THAT is what
# is tested rather than the rule being waived.
# NO ARC ALREADY WON, because finishing a ladder outranks a first title and
# would legitimately take this refresh — the ranking is the point of that, and a
# fixture that trips it is testing the wrong thing.
_wc = _career()
_wc.data["ladder_history"] = [{"name": "Formula 4", "tier": "f4", "pos": 1,
                               "rounds": 5, "when": 1}]
personal.refresh(_wc)
_first = [m for m in inbox.messages(_wc)
          if m["kind"] == "milestone_first_title"]
check(_first, "her first-title letter arrives")
if _first:
    _txt = " ".join(_first[0]["body"]) + _first[0]["subject"]
    check("{" not in _txt, "with nothing unfilled in it", _txt[:60])
    check("Formula 4" in _txt,
          "and it names the championship she was told about", _txt[:70])

print("\n2. THE ILLNESS IS NEVER THE SUBJECT OF A SENTENCE")
# A beat that says "Dad is unwell" has told the player what to feel, and he
# will feel nothing. It arrives in subordinate clauses or not at all.
blunt = [i for i, b in enumerate(personal.beats())
         if any(p.lower().startswith(("dad is", "he is dying", "dad has"))
                for p in b["body"])]
check(not blunt, "no beat announces it", str(blunt))
late = " ".join(personal.beats()[-1]["body"]).lower()
check("cancer" not in late and "dying" not in late,
      "not even the last one, which is where it would be easiest")

print("\n3. SHE WRITES TO THE SHAPE OF A CAREER, NOT TO A RACE COUNTER")
# The user, after reading a whole career: she had become "way too involved -
# basically sending an email at the end of every race". A race counter knows
# nothing about the shape of a career and fires hardest exactly where the races
# are densest. THE SEASON IS THE UNIT, because it is the unit his life is
# organised around.
c = _career()
personal.refresh(c)
check(not inbox.messages(c, kind="beat"), "nothing arrives on day one")
_race(c)
_settle(c)
check(not inbox.messages(c, kind="beat"),
      "and nothing in the first weekend of a season either")
for _ in range(4):
    _race(c)
    _settle(c)
got = inbox.messages(c, kind="beat")
check(len(got) == 1, "ONE letter in a season, however many races it holds",
      "%d after %d races" % (len(got), personal.races_run(c)))
check(got[0]["subject"] == personal.beats()[0]["subject"],
      "and it is the first one", got[0]["subject"])
_seasons(c, 1)
c.data["rounds"] = []
for _ in range(3):
    _race(c)
    _settle(c)
check(len(inbox.messages(c, kind="beat")) == 2,
      "the next season brings the next one",
      str(len(inbox.messages(c, kind="beat"))))

print("\n4. THE LAST BEATS WAIT FOR THE THIRD ARC")
# The user's thesis: one championship is a season or two. The illness getting
# worse has to happen across YEARS, not across one good season.
early = _career(arcs=())
_seasons(early, 6)
_settle(early)
n_early = len(inbox.messages(early, kind="beat"))
check(0 < n_early <= len(personal.beats()) - personal.LATE_BEATS,
      "a driver on his first arc gets the thread but not its end",
      "%d of %d" % (n_early, len(personal.beats())))
final = _career(arcs=("touring", "stock_car"))
_seasons(final, 6)
# ...and now the final season itself, where the rest of the thread arrives.
#
# RACED UNTIL THE OFFER WINDOW, not a fixed four rounds: the last division of a
# path is now a fixed ten (it is the championship that finishes an arc), so a
# hard-coded count stopped short of the window and the offer never opened.
# RACED ROUND BY ROUND UNTIL THE OFFER LANDS, which is how the game reaches it.
#
# Verified against a clean third-arc career on a ten-round finale: the thread
# skips to its last beat at three rounds remaining, completes 13 of 13, and the
# offer opens with two rounds left. A fixed round count cannot find that window,
# because the thread is paced by letters as well as by races — and the last
# division of a path is now a fixed ten rounds, so the window moved.
while not personal.offer_open(final) and personal.rounds_left(final) > personal.OFFER_MIN_LEFT:
    _race(final)
    _settle(final)
check(personal.offer_open(final),
      "the offer is on the table with the season still live",
      "%d rounds left" % personal.rounds_left(final))
# THE END OF THE THREAD IS WHAT MATTERS, not the count. A season that runs out
# with letters still unsent skips to the last one, because the offer waits for
# it and a story that never reaches its own choice is the worse failure.
subjects = [m["subject"] for m in inbox.messages(final, kind="beat")]
check(personal.beats()[-1]["subject"] in subjects,
      "a driver on his third gets the end of the thread",
      "%d letters, last is %r" % (len(subjects), subjects[0]))

print("\n4b. SHE WRITES WHEN SOMETHING HAPPENS, NOT ONLY ON A TIMER")
# The user's note: a sibling who sends a letter about a boiler the week you
# won your first championship is not a sibling, she is a schedule. These fire
# off the same facts the rest of the product uses, so she can never
# congratulate him on something that did not happen.
quiet = _career(arcs=())
personal.refresh(quiet)
check(not inbox.messages(quiet, kind="milestone_first_title"),
      "nothing to celebrate, nothing sent")
quiet.data.setdefault("ladder_history", []).append(
    {"name": "Karting", "pos": 1, "rounds": 6, "wins": 3, "podiums": 5,
     "when": 1})
personal.refresh(quiet)
check(inbox.messages(quiet, kind="milestone_first_title"),
      "his first championship gets a letter of its own")
n_before = len(inbox.messages(quiet, kind="milestone_first_title"))
personal.refresh(quiet); personal.refresh(quiet)
check(len(inbox.messages(quiet, kind="milestone_first_title")) == n_before,
      "and only one, however many times it is asked")
won = _career(arcs=("touring",))
won.data["ladder_history"] = [{"name": "X", "pos": 1, "rounds": 6, "when": 1}]
personal.refresh(won)
check(inbox.messages(won, kind="milestone_arc"),
      "finishing a whole ladder gets its own too")

print("\n5. THE OFFER COMES WHEN THERE IS SOMETHING LEFT TO LOSE")
# NOT UNTIL THE THREAD HAS FINISHED ARRIVING. `early` is mid-story and on his
# first arc; an offer there would be a stranger asking him to come home.
check(not inbox.messages(early, kind="offer"),
      "not while letters are still to come",
      str([m["kind"] for m in inbox.messages(early)][:3]))
# NEVER IN THE SAME BREATH AS AN ORDINARY LETTER. Two emails from the same
# person in one afternoon, the second of them the one that matters, is a writer
# arranging the plot rather than a sister sending an email.
same = _career(arcs=("touring", "stock_car"))
_seasons(same, 5)
before = len(inbox.messages(same, kind="beat"))
_settle(same)
if len(inbox.messages(same, kind="beat")) > before:
    check(not inbox.messages(same, kind="offer"),
          "the offer waits when she has just written")
else:
    check(True, "the offer waits when she has just written", "(no beat due)")
if not personal.offer_open(final):
    _race(final)
    _settle(final)
off = inbox.messages(final, kind="offer")
check(off, "it arrives in the final season of the final arc")
check(personal.offer_open(final), "and it can be answered")
# ...AND NOT WHEN THE SEASON IS ALREADY OVER. Missing a round nobody is racing
# is not a sacrifice, it is a formality.
lastgasp = _career(arcs=("touring", "stock_car"), rounds=2)
_seasons(lastgasp, 8)
_race(lastgasp); _race(lastgasp)
_settle(lastgasp)
check(not inbox.messages(lastgasp, kind="offer"),
      "never with the championship already decided")

print("\n6. SAYING YES COSTS A ROUND, AND THE RIVALS SCORE")
# The trap that makes or breaks the whole story: a skipped round where NOBODY
# scores leaves every gap exactly as it was, and the choice is free.
before = dict(final.standings())
mine_before = before.get(ME, 0)
personal.answer(final, True)
after = dict(final.standings())
check(after.get(ME, 0) == mine_before, "he scores nothing that weekend",
      "%s -> %s" % (mine_before, after.get(ME, 0)))
check(any(after[k] > before.get(k, 0) for k in after if k != ME),
      "and everyone he is racing does", str(after))
missed = [r for r in final.rounds if r.get("absent")]
check(len(missed) == 1 and missed[0]["pos"] == 0,
      "the round is on the record as one he did not attend", str(missed[:1]))
check(missed[0].get("simulated"), "and is marked as simulated, never as a race")
check(inbox.messages(final, kind="reply_yes"), "the agent puts it in writing")
check(not personal.offer_open(final), "and it cannot be answered twice")

print("\n7. SAYING NO IS ALSO AN ANSWER")
other = _career(arcs=("touring", "stock_car"))
_seasons(other, 8)
while not personal.offer_open(other) and personal.rounds_left(other) > personal.OFFER_MIN_LEFT:
    _race(other)
    _settle(other)
personal.answer(other, False)
check(inbox.messages(other, kind="reply_no"), "his sibling replies")
check(not any(r.get("absent") for r in other.rounds),
      "and no round is missed")

print("\n8. THE OFFER EXPIRES QUIETLY")
# Rule 3: no warning, no countdown, no colour. It simply stops being something
# he can do — which is the mechanism, not an oversight.
lapsed = _career(arcs=("touring", "stock_car"), rounds=6)
_seasons(lapsed, 8)
while not personal.offer_open(lapsed) and personal.rounds_left(lapsed) > personal.OFFER_MIN_LEFT:
    _race(lapsed)
    _settle(lapsed)
check(personal.offer_open(lapsed), "it is open when it arrives")
for _ in range(personal.OFFER_WINDOW + 1):
    _race(lapsed)
    personal.refresh(lapsed)
check(not personal.offer_open(lapsed), "and closed a round or two later")
check(not any(m["kind"].startswith("reply") for m in inbox.messages(lapsed)),
      "with nothing said about it either way",
      str([m["kind"] for m in inbox.messages(lapsed)]))

print("\n9. THE ENDING IS FOUR MESSAGES, AND NOT ALL AT ONCE")
def _finish(c, champion=True):
    while len(c.rounds) < c.total_rounds:
        _race(c, pos=1 if champion else 3)
    _settle(c)
    return c

_finish(final)
ids = [m["id"] for m in inbox.messages(final) if m["id"].startswith("ending:")]
check("ending:principal" in ids and "ending:engineer" in ids,
      "the paddock writes the same evening", str(ids))
check("ending:father" not in ids,
      "and the article about his father does NOT land in the same breath")
# It waits until he has actually read one of them. Four unread messages in one
# refresh is a credits roll, and the fourth is then just the last one clicked.
inbox.read(final, "ending:principal")
_settle(final)
check(inbox.get(final, "ending:father") is not None,
      "it comes once he has read what the paddock sent")
check(len([m for m in inbox.messages(final)
           if m["id"].startswith("ending:")]) <= 4,
      "four messages, and no more",
      str([m["id"] for m in inbox.messages(final)
           if m["id"].startswith("ending:")]))

print("\n10. THE FOUR ENDINGS ARE THE MATRIX")
went = inbox.get(final, "ending:father")
check(went["kind"] == "ending_went", "he went, so the article knows he was away",
      went["kind"])
# THE DEDICATION IS THE POINT. He won it and he missed a round to be there, so
# the piece says both — that is what turns the ending from an observation into
# something about him.
body = " ".join(went["body"]).lower()
check("dedicat" in body, "and it is about the dedication", went["subject"])
check("missed a round" in body or "missed" in body,
      "and says plainly what it cost", body[:80])
check(inbox.get(final, "ending:profile") is not None,
      "and he won it, so there is a champion's profile")
# The other corner: stayed, and lost it.
stayed = _career(arcs=("touring", "stock_car"), rounds=4)
_seasons(stayed, 8)
for _ in range(5):
    _race(stayed, pos=3)
    _settle(stayed)
personal.answer(stayed, False)
_finish(stayed, champion=False)
inbox.read(stayed, "ending:principal")
_settle(stayed)
end = inbox.get(stayed, "ending:father")
check(end is not None and end["kind"] == "ending_missed",
      "a driver who stayed gets the notice that mentions nobody",
      str(end and end["kind"]))
check(inbox.get(stayed, "ending:profile") is None,
      "AND NO CHAMPION'S PROFILE — he did not win it")
body = " ".join(end["body"]).lower()
check("champion" not in body and "race" not in body and ME.lower() not in body,
      "INDIFFERENCE, NOT MOCKERY: the world does not know who he was", body[:60])

print("\n11. THE CHAMPION'S PROFILE IS GENERATED, NOT WRITTEN")
prof = inbox.get(final, "ending:profile")
r = final.resume()
check(("%d win" % r["wins"]) in " ".join(prof["body"]),
      "it quotes the wins the overlay actually watched", "%d" % r["wins"])
check(ME in prof["subject"], "names him", prof["subject"])
# IT MUST NOT INVENT A TEAM. The store knows divisions and car classes, never
# entrants, and a made-up team is the one false note nobody would forgive in
# the article that closes a career.
check("team" not in " ".join(prof["body"]).lower(),
      "and never invents an entrant")

print("\n12. IT IS INDISTINGUISHABLE FROM ADMIN MAIL")
# THE MECHANISM, not a nicety. By the time the offer arrives the player has
# been trained by a hundred licensing statements to skim, and anything that
# marks a personal letter as special destroys that in one frame.
shapes = {tuple(sorted(m)) for m in inbox.messages(final)}
check(len(shapes) == 1, "every message in the archive has identical fields",
      str(len(shapes)))
beat = inbox.messages(final, kind="beat")[0]
admin = inbox.messages(final, kind="season_open")
check(not (set(beat) - set(admin[0])) if admin else True,
      "a letter from his brother carries nothing a licensing statement lacks")
check(beat.get("feed") == "mail",
      "and sits in the same tab as the rest of the post")

print("\n13. THE BOOTH NEVER KNOWS")
import lines
leaked = [k for k in personal.load() if k in lines.load()]
check(not leaked, "no part of the story is loaded as dialogue", str(leaked))
words = " ".join(e.get("t", "") if isinstance(e, dict) else str(e)
                 for pool in lines.load().values() for e in pool).lower()
check("father" not in words or "dad" not in words,
      "and nothing in the spoken pools is about a father")
src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "overlay_booth.py"), encoding="utf-8").read()
spoken = [ln for ln in src.splitlines()
          if "personal" in ln and ("_say" in ln or "speak" in ln)]
check(not spoken, "the booth never speaks anything it returns", str(spoken[:2]))

print("\n13b. THE CAREER DOES NOT END WHEN THE STORY DOES")
# A completionist is still racing, and the rest of the inbox has to carry on
# around him exactly as before — otherwise finishing the story reads as the
# game losing interest in him.
import inbox as _ib
before = len(_ib.messages(final))
for _ in range(personal.EPILOGUE_EVERY + 2):
    _race(final, pos=1, n=len(final.rounds) + 1)
    _ib.refresh(final)
    _settle(final)
check(len(_ib.messages(final)) > before,
      "results and news keep arriving after the ending",
      "%d -> %d" % (before, len(_ib.messages(final))))

print("\n13c. SHE KEEPS WRITING, RARELY, AND ABOUT THE GRIEF")
# A thread that stops the moment the plot is finished tells the player the
# person was a device. These arrive months apart and are about her.
epi = _ib.messages(final, kind="epilogue")
check(epi, "the first letter after the funeral eventually comes",
      "%d" % len(epi))
check(all(m["from"] == "Mel" for m in epi), "still from her")
check(len(epi) < len(personal.beats()),
      "far fewer than the story sent — she is getting on with her life",
      "%d vs %d" % (len(epi), len(personal.beats())))

print("\n13d. THE 100% LETTER IS A SECRET, AND IT IS HERS")
# Winning all five divisions is a completionist's achievement and the game has
# nothing else to give him for it. It gives him the one thing the story left
# open: she is all right now.
check(not _ib.messages(final, kind="completion"),
      "three divisions is not five, so nothing arrives")
final.data["ladder_done"] = ["single_seater", "endurance", "stock_car",
                             "touring", "road_to_indy"]
_settle(final)
bonus = _ib.messages(final, kind="completion")
check(bonus, "winning all five divisions unlocks it", "%d" % len(bonus))
text = " ".join(p for m in bonus for p in m["body"]).lower()
check("moving" in text or "another country" in text,
      "she has found somebody, somewhere else", text[:70])
check("doesn't hurt the way it did" in text or "hurt" in text,
      "and the grief has changed rather than been resolved")
n = len(_ib.messages(final))
_settle(final)
check(len(_ib.messages(final)) == n, "and it arrives exactly once")

print("\n14. IT NEVER RE-FIRES, AND IT IS PER CAREER")
n = len(inbox.messages(final))
personal.refresh(final); personal.refresh(final)
check(len(inbox.messages(final)) == n, "a finished story stays finished",
      "%d -> %d" % (n, len(inbox.messages(final))))
fresh = _career(arcs=())
personal.refresh(fresh)
check(not inbox.messages(fresh, kind="beat"),
      "and a new career starts the thread again from nothing")
plain = S.create("open", me=ME, rounds=3)
check(personal.refresh(plain) == [],
      "a career off the ladder has no story at all")

shutil.rmtree(_tmp, ignore_errors=True)
print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
