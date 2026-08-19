# -*- coding: utf-8 -*-
"""
FACTORtv — a whole career, as text.

    python careerdemo.py            # three arcs, everything he would receive
    python careerdemo.py 1          # just the first arc, for a quicker read

Drives a complete ladder career through the REAL modules — `season.record`,
`inbox.refresh`, `news.refresh`, `personal.refresh`, `Career.advance` — and
prints every message in the order it would actually arrive. Nothing here is
mocked or hand-written: if a letter reads badly, it reads badly in the game.

WHY THIS EXISTS
---------------
`_transcript_demo.py` does the same job for the booth, and for the same reason:
a test can prove a message was generated and cannot tell you whether it is
worth reading. This is the only way to see whether a career hangs together —
whether the dry mail is dry enough for the personal thread to hide in, whether
the news feed repeats itself, whether the ending arrives with any weight.

THE CAREER IT DRIVES is the shape the design assumes: the full climb once, then
two shorter professional careers, then the ending. The results are scripted so
the read-through is stable — a career that came out differently every run would
be impossible to review.
"""
import os
import shutil
import sys
import tempfile
import time

import inbox
import ladder as ladder_mod
import news
import personal
import season as season_mod

ME = "Dante Kandasamy"
RIVALS = ("Marcus Vinter", "Elias Roth", "Tomas Halvard", "Ryan Okafor")

# What he does in each season, as a finishing position per round. Scripted so
# a read-through is stable: the same story every time, which is what makes it
# reviewable. The shape is a career — scrappy at the bottom, then quick.
# THE RUNGS HAVE TO BE CONTIGUOUS. A promotion moves a driver ONE rung, so a
# script that jumps GT3 -> Prototype silently fails to advance and replays the
# same season — which is exactly what the first version of this file did.
SEASONS = [
    ("single_seater", 0, [3, 2, 4, 1, 2, 1]),      # karting, wins it
    ("single_seater", 1, [4, 2, 3, 1, 2, 1]),      # Formula 4
    ("single_seater", 2, [2, 3, 1, 1, 4, 1]),      # Formula 3
    ("single_seater", 3, [1, 2, 1, 3, 1, 1]),      # Formula 2
    ("single_seater", 4, [2, 1, 3, 1, 1, 1]),      # Formula One — ARC ONE
    ("endurance", 2, [1, 2, 1, 1, 3, 1]),          # GT3, joined as a pro
    ("endurance", 3, [2, 1, 1, 2, 1, 1]),          # GTE
    ("endurance", 4, [1, 1, 2, 1, 1, 1]),          # Prototype — ARC TWO
    ("stock_car", 2, [2, 1, 1, 3, 1, 1]),          # Stock Car Pro
    ("stock_car", 3, [1, 2, 1, 1, 2, 1]),          # NASCAR — ARC THREE
]

WRAP = 78


def wrap(text, indent="    "):
    out, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > WRAP:
            out.append(indent + line)
            line = word
        else:
            line = (line + " " + word) if line else word
    if line:
        out.append(indent + line)
    return "\n".join(out)


def show(m, log):
    log.append("")
    log.append("    +%s+" % ("-" * (WRAP - 2)))
    log.append("    | %-*s |" % (WRAP - 4, ("NEWS" if m.get("feed") == "news"
                                            else "MAIL") + "   " + m["from"]))
    log.append("    | %-*s |" % (WRAP - 4, m["subject"][:WRAP - 4]))
    log.append("    +%s+" % ("-" * (WRAP - 2)))
    for para in m["body"]:
        log.append(wrap(para, "    "))
        log.append("")


def race(car, n, pos):
    """One round, with a plausible field around the player.

    THE CLASS MATTERS AND THE FIRST VERSION LEFT IT OUT. A live session always
    reports one, `Career.record` locks it on the first round, and `news.py`
    dates the season from it — so without it the demo produced no period pieces
    and no "did you know" at all, which is not what the game does.
    """
    tier = car.tier() or {}
    cls = (tier.get("classes") or [""])[0]
    order = [r for r in RIVALS]
    order.insert(min(pos - 1, len(order)), ME)
    # QUALIFYING IS PART OF A WEEKEND and the feed reads it, so the demo has
    # to run one — without it the Saturday stories never appear and the
    # read-through misrepresents what a season looks like.
    car.record_quali(n, max(1, pos - 1), field=len(RIVALS) + 1,
                     slug="circuit%d" % n)
    car.record({"n": n, "slug": "circuit%d" % n, "event": "", "cls": cls,
                "when": time.time(), "pos": order.index(ME) + 1,
                "laps": 24, "race_laps": 24, "field": len(order),
                "classified": [(nm, i + 1) for i, nm in enumerate(order)],
                "fastest": order[0]})


def drain(car, log, answer_offer=True):
    """Everything the career has to say right now, in arrival order."""
    seen = {m["id"] for m in inbox.messages(car)}
    inbox.refresh(car)
    news.refresh(car)
    for _ in range(6):
        if not personal.refresh(car):
            break
    fresh = [m for m in inbox.messages(car) if m["id"] not in seen]
    for m in sorted(fresh, key=lambda m: (m.get("when") or 0, m["id"])):
        show(m, log)
        # READING IS PART OF THE FLOW, and the ending depends on it: the
        # article about his father is held back until he has opened something
        # the paddock sent.
        inbox.read(car, m["id"])
    if personal.offer_open(car):
        log.append("")
        log.append("    >>> HE ANSWERS: %s" % ("GO — and misses the next round"
                                               if answer_offer else "stays"))
        for m in personal.answer(car, answer_offer):
            show(m, log)
            inbox.read(car, m["id"])


def main(arcs=3, answer_offer=True):
    tmp = tempfile.mkdtemp(prefix="factortv_demo_")
    season_mod.CAREER_DIR = tmp
    log = []
    car = None
    try:
        for idx, (path, tier, results) in enumerate(SEASONS):
            if car is None:
                car = season_mod.create("open", me=ME, rounds=len(results),
                                        ladder_path=path, tier_index=tier)
            ev = car.evaluate() or {}
            log.append("")
            log.append("=" * WRAP)
            log.append("  %s — %s" % ((ev.get("path_name") or "").upper(),
                                      (ev.get("tier_name") or "").upper()))
            log.append("  %d race season   |   divisions won: %d   |   career %d%%"
                       % (len(results), ev.get("arcs_won") or 0,
                          round((ev.get("career_pct") or 0) * 100)))
            log.append("=" * WRAP)
            drain(car, log, answer_offer)
            for i, pos in enumerate(results, start=1):
                if any(r.get("n") == i for r in car.rounds):
                    continue        # the round he missed for his father
                race(car, i, pos)
                log.append("")
                log.append("    -- round %d: P%d --" % (i, pos))
                drain(car, log, answer_offer)
            ev = car.evaluate() or {}
            log.append("")
            log.append("    == season over: P%s in the championship ==" %
                       (ev.get("pos") or "?"))
            drain(car, log, answer_offer)
            if car.arcs_won + (1 if ev.get("arc_done") else 0) >= arcs:
                # THE CAREER IS OVER. The ending has already been drained
                # above; anything after it would be the credits rolling twice.
                if ev.get("arc_done"):
                    log.append("")
                    log.append("    == %s WON — the career ends here ==" %
                               (ev.get("path_name") or "").upper())
                break
            nxt = SEASONS[idx + 1] if idx + 1 < len(SEASONS) else None
            if nxt is None:
                break
            if nxt[0] != path:
                moved = car.advance("newpath", path_key=nxt[0],
                                    tier_index=nxt[1], rounds=len(nxt[2]))
            elif ev.get("promoted"):
                moved = car.advance("promote", rounds=len(nxt[2]))
            else:
                moved = car.advance("retry", rounds=len(nxt[2]))
            if moved is None:
                log.append("")
                log.append("    !! could not move to %s/%d — script and rules "
                           "disagree" % (nxt[0], nxt[1]))
                break
            drain(car, log, answer_offer)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "\n".join(log)


if __name__ == "__main__":
    arcs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    stay = "--stay" in sys.argv
    text = main(arcs, answer_offer=not stay)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "_career_preview.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    print("\n\nwritten to %s" % out)
