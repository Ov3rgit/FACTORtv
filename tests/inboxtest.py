"""The inbox: what gets sent, what it says, and what must never happen twice.

A career that only speaks through a commentary booth exists only while you are
driving. This is the other half — and it carries three burdens that a line pool
does not:

  * A LETTER IS PERMANENT. A spoken line with a hole in it is gone in four
    seconds; a letter with a hole in it sits in the archive for the rest of the
    career. So a missing fact kills the message rather than blanking the slot.
  * A NUMBER IN IT IS CHECKABLE. The user can open the standings. Every figure
    comes from the store, and is frozen at the moment it was sent.
  * IT IS ALSO THE STORY'S CAMOUFLAGE. The personal mail that arrives later
    must be indistinguishable from a licensing statement, which means nothing
    in the model may carry importance.

    python tests/inboxtest.py
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import inbox
import season as S

fails = []
def check(c, l, e=""):
    print(("  [ OK ] " if c else "  [FAIL] ") + l + (("  " + e) if e else ""))
    if not c:
        fails.append(l)


_tmp = tempfile.mkdtemp(prefix="factortv_inbox_")
S.CAREER_DIR = _tmp


def _career(results=(), length=3, path="single_seater", tier=2, name="Tester"):
    c = S.create("open", me=name, rounds=length,
                 ladder_path=path, tier_index=tier)
    for i, pos in enumerate(results, start=1):
        c.record({"n": i, "slug": "t%d" % i, "pos": pos, "laps": 20,
                  "race_laps": 20,
                  "classified": [(name, pos),
                                 ("A Rival", 1 if pos != 1 else 2)]})
    return c


print("\n1. THE DATA OBEYS ITS OWN RULES")
errs = inbox.validate()
check(not errs, "mail.json validates", "; ".join(errs[:3]))
check(len(inbox.kinds()) >= 10, "there are enough kinds of mail to be a life",
      "%d" % len(inbox.kinds()))

print("\n2. IT IS CORRESPONDENCE, NOT A NOTIFICATION")
# The user's ask, and it is a real constraint rather than a preference: the
# personal mail only lands because the player has been reading REAL LETTERS
# from people with jobs for a whole career.
short, thin = [], []
for kind, pool in inbox.load().items():
    for i, tpl in enumerate(pool):
        if len(tpl.get("body") or []) < 2:
            short.append("%s[%d]" % (kind, i))
        if sum(len(p.split()) for p in tpl.get("body") or []) < 60:
            thin.append("%s[%d]" % (kind, i))
check(not short, "every message is a paragraph or two", str(short[:4]))
check(not thin, "and none of them is a stub", str(thin[:4]))
senders = {t["from"] for pool in inbox.load().values() for t in pool}
check(len(senders) >= 4, "written by more than one kind of person",
      str(sorted(senders)))

print("\n3. EVERY KIND HAS SOMETHING THAT SENDS IT")
# LAW 21, in a new costume. A template nothing generates is invisible, and
# `validate()` calls it healthy because the template is perfectly well formed.
src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "inbox.py"), encoding="utf-8").read()
orphans = [k for k in inbox.kinds() if ('"%s"' % k) not in src]
check(not orphans, "no template is unreachable", str(orphans))

print("\n3b. MAIL IS NOT DIALOGUE")
# It very nearly was. `lines.load()` takes EVERY .json in lines_data/ and
# treats any list it finds as a pool of spoken lines — which is what lets a
# pool be extended across files. The other data files escaped only because
# their top-level values are dicts; mail.json's are lists, so twelve pools of
# email appeared in the booth's store the moment it was added. Nothing drew one
# because a letter has no "text" field, but the booth was one name collision
# away from reading a licensing statement on air.
import lines
leaked = [k for k in inbox.kinds() if k in lines.load()]
check(not leaked, "no kind of mail is loaded as a line pool", str(leaked))
check("mail.json" in lines.NOT_DIALOGUE,
      "and the loader is told so explicitly, not by luck of data shape")

print("\n4. A CAREER RECEIVES ITS POST")
c = _career([2, 1, 1])
new = inbox.refresh(c)
kinds = {m["kind"] for m in inbox.messages(c)}
check(len(new) >= 8, "a finished season generates a real inbox", "%d" % len(new))
check({"season_open", "title"} <= kinds
      and any(k.startswith("result_") for k in kinds),
      "entry, results and the championship all arrive", str(sorted(kinds)))
check(all(m["body"] and len(m["body"]) >= 2 for m in inbox.messages(c)),
      "and every one of them is a letter")

print("\n4b. THE FIA SAYS WHICH CAR TO LOAD")
# The overlay works out which division a session belongs to from the CarClass
# rF2 reports, so a driver who loads the wrong car gets an off-career race and
# no explanation. An entry pack listing eligible machinery is a real thing, and
# it puts the answer in his inbox instead of in a conversation.
import ladder as _L
_cars = _L.tier_cars(c.tier() or {})
elig = [m for m in inbox.messages(c) if m["kind"] == "eligible"]
if _cars:
    check(elig, "the entry pack includes a homologation list", str(len(elig)))
    body = " ".join(elig[0]["body"])
    check(all(f in body for _n, f in _cars[:4]),
          "naming the exact folders on his disk, not an alias",
          str([f for _n, f in _cars[:4]]))
    check("or and" not in body and "()" not in body,
          "and it reads like a sentence", body[:80])
else:
    check(not elig,
          "and says nothing at all when it cannot name a car",
          "no cars scanned")


# A HOMOLOGATION LIST IS A REFERENCE, NOT A SNAPSHOT — the one place rule 1 is
# wrong. Every number in a letter is frozen when sent, which is right for a
# result sheet whose value is that it says what was true that afternoon. This
# letter exists to be ACTED ON LATER, and the user was sent one naming "Tatuus
# F4 2018" for a car the game lists as "Tatuus_F4-T014": correcting the name did
# nothing for him, because the letter he already had kept the old wording.
#
# So the id carries a fingerprint of the LIST, and a changed list is re-issued.
_seen_before = list(c.data.get("mail_seen") or ())
_n_before = len([m for m in inbox.messages(c)
                 if m["kind"].startswith("eligible")])
inbox.refresh(c)
check(len([m for m in inbox.messages(c)
           if m["kind"].startswith("eligible")]) == _n_before,
      "an unchanged list is not re-issued on every refresh")

# Now the list itself changes — a car installed, or the real menu name learned.
_real_cars = _L.tier_cars
try:
    _L.tier_cars = lambda tier, mods=None: [("Something Else GT", "SE_GT_2019")]
    _fresh = inbox.refresh(c)
    _rev = [m for m in (_fresh or []) if m and m["kind"] == "eligible_revised"]
    check(bool(_rev), "a CHANGED list is re-issued",
          str([m["kind"] for m in (_fresh or []) if m]))
    # AND IT SAYS IT IS A REVISION. One first-issue wording opens "unchanged
    # from the version circulated with your entry pack", which is exactly false
    # on the letter that exists because the list changed — and two
    # identical-looking notices with different content in them is how a reader
    # learns to stop reading them.
    if _rev:
        _txt = (_rev[0]["subject"] + " " + " ".join(_rev[0]["body"])).lower()
        check(any(w in _txt for w in ("revised", "re-issued", "second issue",
                                      "correction", "supersede")),
              "and says so, rather than claiming to be unchanged",
              _rev[0]["subject"])
        check("Something Else GT" in " ".join(_rev[0]["body"]),
              "with the new list in it")
    check(not [m for m in (inbox.refresh(c) or []) if m
               and m["kind"] == "eligible_revised"],
          "and once only, not once per refresh")
finally:
    _L.tier_cars = _real_cars

# NOTHING TO LIST, NOTHING SENT — including no revision. A "you may run the
# following" notice with nothing following it is worse than no notice.
_real_cars = _L.tier_cars
try:
    _L.tier_cars = lambda tier, mods=None: []
    check(not [m for m in (inbox.refresh(c) or []) if m
               and m["kind"].startswith("eligible")],
          "an empty list is never sent as a revision either")
finally:
    _L.tier_cars = _real_cars

print("\n5. THE NUMBERS ARE THE ONES THAT WERE TRUE THAT WEEKEND")
# A result sheet that quietly reflects a championship position he reached three
# races later is a letter that rewrites itself. `title_state(upto=n)` is what
# stops it.
r1 = next(m for m in inbox.messages(c)
          if m["kind"].startswith("result_") and m["round"] == 1)
check("18 points" in " ".join(r1["body"]),
      "round one's sheet quotes round one's championship", " ".join(r1["body"])[-70:])
check("second" in " ".join(r1["body"]), "and the finish that produced it")
r3 = next(m for m in inbox.messages(c)
          if m["kind"].startswith("result_") and m["round"] == 3)
check("68 points" in " ".join(r3["body"]),
      "and round three's quotes round three's", " ".join(r3["body"])[-70:])

print("\n5b. THE SHEET DEPENDS ON WHAT HAPPENED")
# Sixty identical result letters is what turned the personal mail into the
# thing the player was WAITING for, which is the one thing it must never be.
mixed = _career([1, 3, 8, 12], length=4)
mixed.data["rounds"][3]["dnf"] = True
for r in mixed.data["rounds"]:
    r["field"] = 12
inbox.refresh(mixed)
by_round = dict((m["round"], m["kind"]) for m in inbox.messages(mixed)
                if m["kind"].startswith("result_"))
check(by_round.get(1) == "result_win", "a win gets the winner's letter",
      str(by_round))
check(by_round.get(2) == "result_podium", "a podium gets its own")
check(by_round.get(4) == "result_dnf",
      "AND A RETIREMENT IS CHECKED FIRST - a DNF classified twelfth is a "
      "retirement, not a bad race", str(by_round))
check(len(set(by_round.values())) >= 3, "so one career sees several",
      str(sorted(set(by_round.values()))))
twice = _career([1, 1, 1, 1], length=4)
inbox.refresh(twice)
wins = [tuple(m["body"]) for m in inbox.messages(twice)
        if m["kind"] == "result_win"]
check(len(set(wins)) > 1, "four wins are not four copies of one letter",
      "%d wordings from %d" % (len(set(wins)), len(wins)))

print("\n6. A MISSING FACT KILLS THE MESSAGE")
# Rule 2. `safe_format` blanks unknown keys, which is right for speech and
# wrong for a letter: "they wanted  and they have taken someone who had it"
# would sit in the archive for ever.
check(inbox._compose("missed", "x", {"series": "Formula 2"}) is None,
      "a letter that cannot be completed is not sent")
check(inbox._compose("season_open", "x",
                     {"series": "Formula 2", "rounds": 5}) is not None,
      "and one that can be, is")
check(inbox._ordinal(0) == "" and inbox._ordinal(None) == "",
      "no position is an empty string, never '0th'")
check(inbox._ordinal(3) == "third" and inbox._ordinal(21) == "21st",
      "and a position is a word while a word exists", inbox._ordinal(21))

print("\n6b. A SLOT THAT OPENS A SENTENCE IS STILL A SENTENCE")
# Found by reading a whole letter rather than by a test: "{pos} in the
# championship is not enough" rendered as "fifth in the championship...".
# A slot inherits its own case, so the fix is central — the same one
# `lines._sentence_case` is for.
m = inbox._compose("missed", "x", {"series": "Formula 3", "next": "Formula 2",
                                   "pos": "fifth", "need": "P3"})
check(m["body"][0].split(". ")[1].startswith("Fifth")
      if ". " in m["body"][0] else False,
      "a filled slot opening a sentence is capitalised",
      m["body"][0][:70])
check("P3" in " ".join(m["body"]),
      "and a slot that is not a sentence start is left exactly alone")

print("\n7. REFRESH IS IDEMPOTENT")
# It is called on every menu draw. Anything else would be a doubling bug that
# only shows up after an hour of play.
n = len(inbox.messages(c))
inbox.refresh(c); inbox.refresh(c); inbox.refresh(c)
check(len(inbox.messages(c)) == n, "three more refreshes post nothing",
      "%d -> %d" % (n, len(inbox.messages(c))))

print("\n8. A DELETED MESSAGE STAYS DELETED")
# The single most infuriating bug a mail feature can have.
mid = inbox.messages(c)[0]["id"]
check(inbox.delete(c, mid), "a message can be thrown away")
inbox.refresh(c)
check(inbox.get(c, mid) is None, "and refresh does not helpfully post it again")
check(not inbox.delete(c, "no-such-id"), "deleting nothing deletes nothing")

print("\n9. THE BADGE COUNTS WHAT HE HAS NOT SEEN")
check(inbox.unread(c) == len(inbox.messages(c)), "new mail is unread",
      str(inbox.unread(c)))
inbox.read(c, inbox.messages(c)[0]["id"])
check(inbox.unread(c) == len(inbox.messages(c)) - 1, "opening one clears one")
inbox.read_all(c)
check(inbox.unread(c) == 0, "and the whole inbox can be cleared at once")

print("\n10. THE ARCHIVE NEVER EATS UNREAD MAIL")
# An archive that silently drops the one message the user has not opened is a
# spectacular way to lose the ending of the story.
big = _career([1])
for i in range(inbox.KEEP + 20):
    big.data.setdefault("mail", []).append(
        {"id": "junk%d" % i, "kind": "result", "from": "x", "subject": "s",
         "body": ["a", "b"], "when": 1000 + i, "round": 0,
         "read": i % 2 == 0})
kept_unread = sum(1 for m in big.data["mail"] if not m.get("read"))
inbox._trim(big)
check(len(big.data["mail"]) <= inbox.KEEP or kept_unread > inbox.KEEP,
      "the archive is bounded", str(len(big.data["mail"])))
check(sum(1 for m in big.data["mail"] if not m.get("read")) == kept_unread,
      "and every unread message survived it")

print("\n11. PERSONAL MAIL MUST LOOK EXACTLY LIKE ADMIN MAIL")
# THE STORY'S WHOLE MECHANISM. By the time the important one arrives the player
# has been trained to skim, so nothing in the model may mark a message as
# important — no badge, no colour, no ceremony. If a field like this ever
# appears, the ending stops working.
fields = {k for m in inbox.messages(c) for k in m}
check(not (fields & {"priority", "important", "personal", "story", "colour"}),
      "no message carries importance", str(sorted(fields)))
check(len({m["kind"] for m in inbox.messages(c)}) > 1
      and all(set(m) == fields for m in inbox.messages(c)),
      "and every kind of mail has exactly the same shape")

print("\n12. A CAREER OFF THE LADDER STILL GETS ITS POST")
plain = S.create("open", me="Tester", rounds=3)
plain.record({"n": 1, "slug": "t1", "pos": 3, "laps": 20, "race_laps": 20,
              "classified": [("Tester", 3), ("A", 1), ("B", 2)]})
got = inbox.refresh(plain)
check(got, "an ordinary open season has an inbox too", "%d" % len(got))
check(any(m["kind"].startswith("result_") for m in inbox.messages(plain)),
      "with a result sheet naming its own championship")
check(not any(m["kind"] in ("promotion", "missed", "arc_win")
              for m in inbox.messages(plain)),
      "and nothing about a ladder it is not on")

shutil.rmtree(_tmp, ignore_errors=True)
print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
