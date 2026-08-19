# -*- coding: utf-8 -*-
"""
FACTORtv — a letter, rendered exactly as the inbox draws it.

    python mailshot.py            -> _mail_preview.png

Same method as `podiumshot.py` and `dashshot.py`: it opens the REAL mail page
on a real canvas and grabs the pixels, rather than re-drawing the layout in
PIL where it could quietly drift from the thing it is supposed to be showing.

It exists to answer one question a test cannot: does the letterhead READ.
The FIA mark is a JPEG on white with dark wordmark text, so it is drawn on a
light plate — and whether that looks like headed paper or like a mistake is
not something an assertion can tell you.
"""
import os
import sys
import tempfile
import tkinter as tk

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

PAD = 20
CW, CH = 700, 620


def _career():
    """A Formula 2 career with post from everybody who writes."""
    import season as S
    import inbox
    import programme as P
    import personal
    S.CAREER_DIR = tempfile.mkdtemp(prefix="factortv_mailshot_")
    c = S.create("open", me="Dante Kandasamy", rounds=5,
                 ladder_path="single_seater", tier_index=3)
    inbox.refresh(c)
    P.accept(c, "ferrari")
    for n in (1, 2, 3):
        order = ["Nicholas Latifi", "Luca Ghiotto", "Jack Aitken"]
        order.insert(0, c.me)
        c.record({"n": n, "slug": "t%d" % n, "pos": 1, "laps": 20,
                  "race_laps": 20,
                  "classified": [(nm, i + 1) for i, nm in enumerate(order)]})
    inbox.refresh(c)
    personal.refresh(c)
    import news
    news.refresh(c)
    return c


def _shot(career, mid, label):
    """One opened letter, as the menu draws it."""
    from PIL import ImageGrab
    import era as era_mod
    from overlay_common import TH, CHROMA, UI
    from overlay_draw import DrawMixin
    from overlay_panels import PanelsMixin
    from overlay_panel import TCanvas
    import career as career_mod

    UI.k = 1.25
    TH.apply(era_mod.skin_for(era_mod.classify("Formula 2 2019", "")))

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
            self.menu_page = "mail"
            self._menu_confirm = None
            self._menu_offset = 0
            self._mail_offset = 0
            self._mail_feed = "mail"
            self._mail_open = mid
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
    # references it, and the letterhead is held on the host. Discarding it
    # inline is what made the podium mark vanish from its first preview.
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
    print("   %s" % label)
    return img


def main():
    from PIL import Image
    import inbox
    c = _career()
    msgs = inbox.messages(c) + inbox.messages(c, feed="news")

    def find(pred):
        return next((m for m in msgs if pred(m)), None)


    want = [
        ("a news report - the station's own mark",
         find(lambda m: m.get("feed") == "news")),
        ("FIA letterhead", find(lambda m: "FIA" in (m.get("from") or ""))),
        ("Mel - no letterhead", find(lambda m: m.get("from") == "Mel")),
    ]
    imgs = []
    for label, m in want:
        if m is None:
            print("   (no %s found)" % label)
            continue
        imgs.append(_shot(c, m["id"], "%s  -  %s" % (label, m["subject"][:40])))
    if not imgs:
        print("nothing to draw")
        return 1
    sheet = Image.new("RGB", (max(i.width for i in imgs),
                              sum(i.height for i in imgs) + PAD * (len(imgs) - 1)),
                      "#11151b")
    y = 0
    for i in imgs:
        sheet.paste(i, (0, y))
        y += i.height + PAD
    out = os.path.join(_DIR, "_mail_preview.png")
    sheet.save(out)
    print("wrote %s  (%dx%d)" % (out, sheet.width, sheet.height))
    return 0


if __name__ == "__main__":
    sys.exit(main())
