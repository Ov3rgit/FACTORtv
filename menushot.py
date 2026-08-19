# -*- coding: utf-8 -*-
"""
FACTORtv — a menu page, rendered exactly as the overlay draws it.

    python menushot.py            -> _menu_preview.png

The same method as `mailshot.py`, `podiumshot.py` and `dashshot.py`: it opens
the REAL page on a real canvas and grabs the pixels. Re-drawing a menu in PIL
would be quicker and would let the preview drift from the thing it is meant to
be showing, which is the one thing a preview must never do.

It exists to answer a question no assertion can: the end-of-season decision is
now on the inbox page and marked, but WHETHER IT READS AS THE ONE THING ON THE
PAGE WAITING FOR HIM is a matter of how it looks next to nine letters. A test
can only say the flag is set.
"""
import os
import sys
import tempfile
import tkinter as tk

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

CW, CH = 620, 620
PAGES = ("career", "career_ladder")


def _career():
    """A karting season, won, with the Formula 4 seat waiting on it.

    This is the exact state the user reached: a division simulated to the end,
    a seat earned, and nothing in the game demanding he come and take it.
    """
    import season as S
    import inbox
    import news
    S.CAREER_DIR = tempfile.mkdtemp(prefix="factortv_menushot_")
    c = S.create("open", me="Dante Kandasamy", rounds=4,
                 ladder_path="single_seater", tier_index=0)
    c.data["nationality"] = "Australia"
    field = ["Marco Bellini", "Theo Vasseur", "Sam Okonkwo"]
    # THREE OF FOUR ROUNDS RACED, so the career page carries the row that decides
    # whether the NEXT one counts — the control that replaced the in-session card.
    for n in (1, 2, 3):
        order = [c.me] + field
        c.record({"n": n, "slug": "t%d" % n, "pos": 1, "laps": 18,
                  "race_laps": 18,
                  "classified": [(nm, i + 1) for i, nm in enumerate(order)]})
    inbox.refresh(c)
    news.refresh(c)
    return c


def _shot(career, page):
    """One menu page, as the overlay draws it. Returns a PIL image."""
    from PIL import ImageGrab
    import era as era_mod
    from overlay_common import TH, CHROMA, UI
    from overlay_draw import DrawMixin
    from overlay_panels import PanelsMixin
    from overlay_panel import TCanvas
    import career as career_mod

    UI.k = 1.25
    TH.apply(era_mod.skin_for(era_mod.classify("Kart", "")))

    root = tk.Tk()
    root.configure(bg=CHROMA)
    cv = tk.Canvas(root, width=CW, height=CH, bg=CHROMA, highlightthickness=0)
    cv.pack()

    class Host(DrawMixin, PanelsMixin):
        def __init__(self):
            self.root = root
            self.game_rect = (0, 0, CW, CH)
            for n, sz in (("f_small", 10), ("f_row", 10), ("f_tiny", 8)):
                setattr(self, n, ("Arial", int(sz * 1.25)))
            self.season = career
            self.career = career_mod.History()
            self.menu_open = True
            self.menu_page = page
            self._menu_confirm = None
            self._menu_offset = 0
            self._mail_offset = 0
            self._mail_feed = "mail"
            self._mail_open = None
            self.booth_enabled = self.radio_enabled = True
            self.rival_enabled = self.show_dash = True
            self.show_tower = self.show_relative = self.show_map = True
            self.show_sectors = True
            self.tower_rows = 16
            self.relative_rows = 3
            self.tower_interval = True
            self.cfg = {}

        def _begin_panel(self, name, x, y, w, h, clickable=False):
            class P(object):
                def canvas_at(self_inner, ox, oy):
                    return TCanvas(cv, ox, oy)
            return P()

        def _hide_panel(self, n):
            pass

        def _short_track(self, n):
            return n

    # THE HOST HAS TO OUTLIVE THE DRAW — Tk drops an image the instant nothing
    # references it, and any mark on the page is held on the host.
    host = Host()
    host.draw_settings()

    root.attributes("-topmost", True)
    root.lift()
    root.update_idletasks()
    root.update()
    root.after(350, root.quit)
    root.mainloop()
    root.update()
    x0, y0 = root.winfo_rootx(), root.winfo_rooty()
    img = ImageGrab.grab((x0, y0, x0 + CW, y0 + CH)).convert("RGB")
    root.destroy()
    return img


def main():
    from PIL import Image
    car = _career()
    ev = car.evaluate() or {}
    print("season: %s — complete=%s promoted=%s next=%s"
          % (car.name, ev.get("complete"), ev.get("promoted"),
             ev.get("next_name")))
    shots = [(p, _shot(car, p)) for p in PAGES]
    w = sum(im.width for _, im in shots) + 16 * (len(shots) - 1)
    out = Image.new("RGB", (w, max(im.height for _, im in shots)), (18, 18, 20))
    x = 0
    for _, im in shots:
        out.paste(im, (x, 0))
        x += im.width + 16
    path = os.path.join(_DIR, "_menu_preview.png")
    out.save(path)
    print("wrote %s  (%s)" % (path, ", ".join(p for p, _ in shots)))


if __name__ == "__main__":
    main()
