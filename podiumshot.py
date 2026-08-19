# -*- coding: utf-8 -*-
"""
FACTORtv — the end-of-session result card, rendered to a PNG.

    python podiumshot.py            -> _podium_preview.png

Same reason `dashshot.py` and `cardshot.py` exist, and the same method: it
draws with the REAL `draw_podium` on a real canvas and grabs the pixels.
Re-drawing the card in PIL would be quicker and would let the preview drift
from what the overlay actually renders, which is the one thing a preview must
never do.

Two things it exists to answer, neither of which a test can:

  * does the caption say the right thing for a QUALIFYING session — it said
    "RACE RESULT" until this week, because the panel was written for the flag
    at the end of a race and then reused for the end of every session;
  * does the division's mark READ at the size it is drawn, or does it crowd
    the venue name underneath it.
"""
import os
import sys
import tkinter as tk

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

PAD = 24


class _Car(object):
    def __init__(self, name, place, gap):
        self.display_name = self.name = name
        self.place = place
        self.gap_leader = gap
        self.is_player = (place == 3)
        self.in_pits = False
        self.best_lap = 70.0 + place
        self.cls = "Formula 2 2019"


class _Sess(object):
    def __init__(self, kind, track="Kyalami"):
        self.order = [_Car("Nicholas Latifi", 1, 0.0),
                      _Car("Luca Ghiotto", 2, 0.412),
                      _Car("Dante Kandasamy", 3, 1.088)]
        self.player = self.order[2]
        self.leader = self.order[0]
        self.finished = True
        self.valid = True
        self.kind = kind
        self.track = track
        self.classes = ["Formula 2 2019"]


def _shot(kind, division, cw=520, ch=260):
    """One card, as the overlay draws it."""
    from PIL import ImageGrab
    import era as era_mod
    from overlay_common import TH, CHROMA, UI
    from overlay_draw import DrawMixin
    from overlay_panels import PanelsMixin
    from overlay_panel import TCanvas

    UI.k = 1.25
    TH.apply(era_mod.skin_for(era_mod.classify("Formula 2 2019", "")))

    root = tk.Tk()
    root.configure(bg=CHROMA)
    cv = tk.Canvas(root, width=cw, height=ch, bg=CHROMA, highlightthickness=0)
    cv.pack()

    class _Div(object):
        """Just enough career for the card to find a division mark."""
        on_ladder = True
        name = division

        def evaluate(self):
            return {"tier_name": division}

    class Host(DrawMixin, PanelsMixin):
        def __init__(self):
            self.root = root
            # Centred in the canvas, which is what `draw_podium` does inside
            # the game rectangle.
            self.game_rect = (0, 0, cw, ch)
            for n, sz in (("f_small", 10), ("f_row", 10), ("f_tiny", 8)):
                setattr(self, n, ("Arial", int(sz * 1.25)))
            self.season = _Div()

        def _begin_panel(self, name, x, y, w, h, clickable=False):
            class P(object):
                def canvas_at(self_inner, ox, oy):
                    return TCanvas(cv, ox, oy)
            return P()

        def _hide_panel(self, n):
            pass

        def _short_track(self, n):
            return n

    # THE HOST HAS TO OUTLIVE THE DRAW. Tk drops an image the moment nothing
    # references it, and the card holds its logo on the host — so
    # `Host().draw_podium(...)` discarded the reference before the grab and
    # the mark simply vanished. The overlay keeps its host for the life of the
    # program, which is why this only bites the preview.
    host = Host()
    host.draw_podium(_Sess(kind))

    root.attributes("-topmost", True)
    root.lift()
    root.update_idletasks()
    root.update()
    root.after(350, root.quit)
    root.mainloop()
    root.update()
    x0, y0 = root.winfo_rootx(), root.winfo_rooty()
    img = ImageGrab.grab((x0, y0, x0 + cw, y0 + ch)).convert("RGB")
    root.destroy()
    return img


def main():
    from PIL import Image
    shots = [("quali", "Formula 2"), ("race", "Formula 2"),
             ("quali", "Karting")]
    imgs = [_shot(kind, div) for kind, div in shots]
    w = max(i.width for i in imgs)
    h = sum(i.height for i in imgs) + PAD * (len(imgs) - 1)
    sheet = Image.new("RGB", (w, h), "#11151b")
    y = 0
    for i in imgs:
        sheet.paste(i, (0, y))
        y += i.height + PAD
    out = os.path.join(_DIR, "_podium_preview.png")
    sheet.save(out)
    print("wrote %s  (%dx%d)" % (out, sheet.width, sheet.height))
    for kind, div in shots:
        print("   %-6s %s" % (kind, div))
    return 0


if __name__ == "__main__":
    sys.exit(main())
