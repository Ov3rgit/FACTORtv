# -*- coding: utf-8 -*-
"""
FACTORtv — the CAREER DASHBOARD, rendered exactly as the overlay draws it.

    python careershot.py          -> _career_preview.png

NOT `dashshot.py`, which is the TELEMETRY dash and already owns that name — the
first version of this file overwrote it.

The same method as `menushot.py`, `mailshot.py` and `podiumshot.py`: it opens the
REAL page on a real canvas and grabs the pixels. Redrawing the dashboard in PIL
would be quicker and would let the preview drift from the thing it is meant to be
showing, which is the one thing a preview must never do.

WHY THIS ONE EXISTS
-------------------
The dashboard replaced a career page the user described as *"just a bunch of
words"*, and every question worth asking about it is visual: do the four tiles
read at a glance, is the ring legible at 30px, does the division's mark survive
being dark ink on a dark card, and does the season-over decision look like the one
thing on the page waiting for him. No assertion answers any of those. Three of
them were WRONG in the first draft and only the picture said so.

Two states, side by side, because they are the two shapes the page takes:

  * a season part-run, with the junior programme's podium bar on it
  * a season finished, with the next seat waiting

CLOSE THE OVERLAY FIRST. This grabs a screen region, so a running FACTORtv draws
its own panels over the top and you get a photograph of both at once.
"""
import os
import sys
import tempfile

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

import menushot                                            # noqa: E402

# TALL AND NARROW, because the dashboard is a column and the point of the shot is
# whether it FITS. The first version of the page ran off the bottom of a 1080p
# screen and this is the harness that showed it.
menushot.CW, menushot.CH = 380, 820


def _mid_season():
    """Called up to Formula 2, chasing the podium bar for the Formula One seat."""
    import season as S
    import inbox
    import news
    import programme as P
    S.CAREER_DIR = tempfile.mkdtemp(prefix="factortv_dash_")
    c = S.create("open", me="Dante Kandasamy", rounds=6,
                 ladder_path="single_seater", tier_index=2)
    inbox.refresh(c)
    P.accept(c, "mercedes")
    inbox.refresh(c)
    field = ["Jack Aitken", "Guanyu Zhou", "Dorian Boccolacci",
             "Nyck de Vries", "Luca Ghiotto"]
    n = 0
    # THE JOURNEY, NOT A SHORTCUT: the call-up letter is what moves him, so the
    # Formula 3 rounds have to actually be raced with the inbox refreshing.
    while not P.called_up(c) and n < 6:
        n += 1
        order = list(field)
        order.insert(1, "Dante Kandasamy")
        c.record({"n": n, "slug": "montreal", "event": "Montreal GP",
                  "pos": 2, "laps": 12, "race_laps": 12, "field": 6,
                  "classified": [(nm, i + 1) for i, nm in enumerate(order)]})
        inbox.refresh(c)
        news.refresh(c)
    for _ in range(2):
        order = list(field)
        order.insert(4, "Dante Kandasamy")
        c.record({"n": len(c.rounds) + 1, "slug": "spa",
                  "event": "Spa-Francorchamps", "pos": 5, "laps": 14,
                  "race_laps": 14, "field": 6,
                  "classified": [(nm, i + 1) for i, nm in enumerate(order)]})
        inbox.refresh(c)
        news.refresh(c)
    return c


def _season_over():
    """A karting season raced to the flag, with the Formula 4 seat waiting."""
    import inbox
    import news
    c = menushot._career()
    field = ["Otto Rasmussen", "Kaya Marchetti", "Ines Duval", "Milo Fenn"]
    while len(c.rounds) < (c.total_rounds or 0):
        order = list(field)
        order.insert(0, "Dante Kandasamy")
        c.record({"n": len(c.rounds) + 1, "slug": "kyalami",
                  "event": "Kyalami", "pos": 1, "laps": 10, "race_laps": 10,
                  "field": 5,
                  "classified": [(nm, i + 1) for i, nm in enumerate(order)]})
        inbox.refresh(c)
        news.refresh(c)
    return c


def main():
    from PIL import Image
    shots = []
    for label, car in (("mid-season, chasing the bar", _mid_season()),
                       ("season over, seat waiting", _season_over())):
        shots.append(menushot._shot(car, "dash"))
        print("  rendered: %s" % label)
    gap = 20
    w = sum(i.width for i in shots) + gap * (len(shots) - 1)
    h = max(i.height for i in shots)
    out = Image.new("RGB", (w, h), (24, 26, 30))
    x = 0
    for i in shots:
        out.paste(i, (x, 0))
        x += i.width + gap
    path = os.path.join(_DIR, "_career_preview.png")
    out.save(path)
    print("wrote %s" % path)


if __name__ == "__main__":
    main()
