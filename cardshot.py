# -*- coding: utf-8 -*-
"""Render the radio cards and the booth caption to a PNG, at several UI scales.

These are the two panels that carry SENTENCES, and they were the two that cut
words off the end. A screenshot at more than one scale is the only way to see
that, because the bug did not exist at 1.0x.

    python cardshot.py [out.png]
"""
import os
import sys
import time
import tkinter as tk

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

SCALES = (1.0, 1.25, 1.5)


def _longest_lines(n=3):
    """The most awkward things either voice can actually say."""
    import json
    import io
    picked = []
    for f in ("lines_data/engineer.json", "lines_data/booth.json"):
        try:
            d = json.load(io.open(os.path.join(_DIR, f), encoding="utf-8"))
        except Exception:
            continue
        for k, v in d.items():
            if k == "_comment" or not isinstance(v, list):
                continue
            for e in v:
                t = e.get("t") if isinstance(e, dict) else None
                if t:
                    picked.append(t)
    picked.sort(key=len, reverse=True)
    return picked[:n]


def shot(path):
    from PIL import Image, ImageGrab, ImageDraw
    import era as era_mod
    import cast as cast_mod
    from overlay_common import TH, UI
    from overlay_panel import TCanvas
    from overlay_radio import RadioMixin, _Msg
    from overlay_draw import DrawMixin

    texts = _longest_lines(3)
    shots = []

    for k in SCALES:
        UI.k = k
        e = era_mod.classify("F1 Test 2025", "Max Verstappen")
        TH.apply(era_mod.skin_for(e))

        root = tk.Tk()
        root.configure(bg="#05070a")
        W, H = int(560 * k), int(330 * k)
        cv = tk.Canvas(root, width=W, height=H, bg="#05070a",
                       highlightthickness=0)
        cv.pack()

        class Host(RadioMixin, DrawMixin):
            def __init__(self):
                self.root = root
                self.f_row = ("Arial", int(10 * k))
                self.f_tiny = ("Arial", int(8 * k))
                self.f_small = ("Arial", int(10 * k), "bold")
                self.radio_enabled = True
                self.show_dash = False
                self.tts = None
                self.game_rect = (0, 0, W, H)
                self._msgs = []
                self._icons = {}

            def _begin_panel(self, name, x, y, w, h, clickable=False):
                # Outline the panel so the PICTURE shows whether the text fits
                # the box, which is the entire point of this shot.
                cv.create_rectangle(x, y, x + w, y + h, outline="#2f4a63")

                class P(object):
                    def canvas_at(self, ax, ay):
                        return TCanvas(cv, 0, 0)
                return P()

            def _hide_panel(self, n):
                pass

            def _dash_reserved(self):
                return 0

        host = Host()
        now = time.time()
        for i, t in enumerate(texts):
            who = cast_mod.ENGINEER if i % 2 else cast_mod.PLAY
            host._msgs.append(_Msg(who, cast_mod.name_of(who), t, now,
                                   cast_mod.colour_of(who)))
        host.draw_radio(now)

        # FORCE IT IN FRONT BEFORE GRABBING. ImageGrab takes whatever pixels
        # are on the screen at those coordinates, so if anything overlaps the
        # window the "screenshot of the overlay" is a screenshot of that.
        root.attributes("-topmost", True)
        root.lift()
        root.update_idletasks()
        root.update()
        root.after(400, root.quit)
        root.mainloop()
        root.update()
        x0, y0 = root.winfo_rootx(), root.winfo_rooty()
        img = ImageGrab.grab((x0, y0, x0 + W, y0 + H)).convert("RGB")
        root.destroy()
        shots.append((k, img))

    UI.k = 1.0
    width = max(im.width for _k, im in shots)
    height = sum(im.height + 20 for _k, im in shots)
    out = Image.new("RGB", (width, height), (5, 7, 10))
    d = ImageDraw.Draw(out)
    y = 0
    for k, im in shots:
        d.text((8, y + 5), "UI scale %.2fx" % k, fill=(139, 163, 184))
        out.paste(im, (0, y + 20))
        y += im.height + 20
    out.save(path)
    print("wrote %s  %dx%d" % (path, out.width, out.height))
    for t in texts:
        print("  %3d chars  %s" % (len(t), t))


if __name__ == "__main__":
    shot(sys.argv[1] if len(sys.argv) > 1 else "_card_preview.png")
