# -*- coding: utf-8 -*-
"""Render the REAL dash to a PNG, one era per strip, stacked.

`overlay_dash._preview()` opens a live tkinter window, which is the right tool
when you are tuning by eye but useless for comparing a change against what it
replaced.

Two things this does that the old side-by-side preview did not:

  * it drives `draw_dash()` itself, so the picture is the actual THREE-COLUMN
    cluster. The old preview stacked the gauge, tyres, fuel and damage
    vertically, which is not a layout the overlay has ever drawn — it was
    showing a dash that does not exist.
  * it grabs one era at a time and composes them with PIL, instead of laying
    five clusters across a single window. Five columns is wider than the
    screen, and a screen grab is clipped to the screen, so the last two eras
    were simply missing from the image.

    python dashshot.py [out.png]
"""
import os
import sys
import tkinter as tk

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

PAD = 20
LABEL_H = 22


class _FakePanel(object):
    """Stands in for the per-panel Toplevel. `draw_dash` only ever asks it
    for a canvas translated to the panel's origin."""

    def __init__(self, cv):
        self.cv = cv

    def canvas_at(self, x, y):
        from overlay_panel import TCanvas
        return TCanvas(self.cv, 0, 0)


class _Session(object):
    """The little of a Session that the dash actually reads."""

    def __init__(self, car, era):
        self.player = car
        self.player_era = era
        self.era = era
        self.laps_left = 14
        self.max_laps = 30
        self.timed = False
        self.time_left = None
        self.green = True


def _strip(era, car, out_path):
    """Grab one era's cluster. Returns a PIL image."""
    from PIL import ImageGrab
    import era as era_mod
    import overlay_dash as D
    from overlay_common import TH, CHROMA

    TH.apply(era_mod.skin_for(era))

    # CHROMA, not an arbitrary dark grey. The gauge image is flattened onto
    # the key colour so Tk can upload it as fast RGB, and in the real overlay
    # the panel keys that colour out. On a canvas of any OTHER colour the
    # flattened square shows up as a visible box behind every round gauge —
    # an artefact of the preview, but one that looks exactly like a bug.
    root = tk.Tk()
    root.configure(bg=CHROMA)

    # DrawMixin comes along for `_body` — the shared panel slab the dash now
    # sits on. Duplicating that drawing here instead would let the preview
    # drift away from what the overlay actually renders, which is the one
    # thing a preview must never do.
    from overlay_draw import DrawMixin

    class Host(D.DashMixin, DrawMixin):
        def __init__(self, cv):
            self.f_speed = ("Arial", 26, "bold")
            self.f_speed_sm = ("Arial", 14, "bold")
            self.f_gear = ("Arial", 22, "bold")
            self.f_gear_big = ("Arial", 38, "bold")
            self.f_small = ("Arial", 10, "bold")
            self.f_tiny = ("Arial", 8)
            self.fuel_model = D.FuelModel()
            self.fuel_model.laps = [2.4, 2.5, 2.45]
            self.show_dash = True
            self._cv = cv

        def _begin_panel(self, name, x, y, w, h, clickable=False):
            return _FakePanel(self._cv)

        def _dash_origin(self, w, h):
            # Top-left of OUR canvas, not the bottom-right of a screen.
            return (PAD, PAD)

        def _short_track(self, n):
            return n

        def _hide_panel(self, n):
            pass

    probe = Host(None)
    w, h = probe._dash_size(era)
    cw, ch = w + PAD * 2, h + PAD * 2
    cv = tk.Canvas(root, width=cw, height=ch, bg=CHROMA,
                   highlightthickness=0)
    cv.pack()
    host = Host(cv)
    host.draw_dash(_Session(car, era))

    # FORCE IT IN FRONT BEFORE GRABBING. ImageGrab takes whatever pixels are
    # on the screen at those coordinates, so if anything overlaps the window
    # the "screenshot of the overlay" is a screenshot of that instead.
    root.attributes("-topmost", True)
    root.lift()
    root.update_idletasks()
    root.update()
    root.after(400, root.quit)
    root.mainloop()
    root.update()
    x0, y0 = root.winfo_rootx(), root.winfo_rooty()
    img = ImageGrab.grab((x0, y0, x0 + cw, y0 + ch)).convert("RGB")
    root.destroy()
    return img


def shot(path, samples=None):
    from PIL import Image, ImageDraw
    import era as era_mod
    import overlay_dash as D

    samples = samples or D.PREVIEW_SAMPLES
    shots = []
    for i, (cls, nm) in enumerate(samples):
        e = era_mod.classify(cls, nm)
        shots.append((e, _strip(e, D.preview_car(i), path)))

    width = max(im.width for _e, im in shots)
    height = sum(im.height + LABEL_H for _e, im in shots)
    from overlay_common import CHROMA as _C
    out = Image.new("RGB", (width, height),
                    tuple(int(_C.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)))
    d = ImageDraw.Draw(out)
    y = 0
    for e, im in shots:
        d.text((PAD, y + 6), "%s   %s   dial=%s   gauge=%s"
               % (e.label, e.year, getattr(e, "skin", "?"),
                  D.gauge_style(e)), fill=(139, 163, 184))
        out.paste(im, (0, y + LABEL_H))
        y += im.height + LABEL_H
    out.save(path)
    print("wrote %s  %dx%d" % (path, out.width, out.height))


if __name__ == "__main__":
    shot(sys.argv[1] if len(sys.argv) > 1 else "_dash_preview.png")
