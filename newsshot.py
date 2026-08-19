# -*- coding: utf-8 -*-
"""
FACTORtv — render news articles to a PNG, exactly as the panel will draw them.

    python newsshot.py            -> _news_preview.png

Same reason `dashshot.py` and `cardshot.py` exist: several bugs in this
project were only ever visible in a picture. A news article with a photograph
is a LAYOUT, and no amount of reading the text tells you whether the headline
survives next to a 16:9 image at the panel's real width.

THE CONTENT IS REAL. The articles come out of `news.py` against a real career
file, and the pictures come out of `newsart.py` against the user's own
folders — so if a headline reads badly here, it reads badly in the game. The
one thing this cannot show is the surrounding menu chrome.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

import newsart
import season as season_mod
import inbox as inbox_mod
from overlay_common import TH
from overlay_panels import MAIL_WRAP, wrap_mail

_DIR = os.path.dirname(os.path.abspath(__file__))

# The panel draws at MAIL_W=470 logical pixels. Rendered at 2x here purely so
# the preview is legible on a desktop — every proportion is the real one, so
# what fits here fits there.
SCALE = 2
CARD_W = 470 * SCALE
PAD = 14 * SCALE
IMG_H = int((CARD_W - PAD * 2) * 9 / 16)      # one aspect ratio, cropped to


def _font(name, size):
    p = os.path.join(_DIR, name)
    if os.path.exists(p):
        return ImageFont.truetype(p, size * SCALE)
    return ImageFont.load_default()


F_KICKER = _font("ChakraPetch-SemiBold.ttf", 9)
F_HEAD = _font("ChakraPetch-Bold.ttf", 15)
F_BODY = _font("ChakraPetch-Regular.ttf", 10)
F_META = _font("ChakraPetch-Regular.ttf", 8)


def _fit(path, w, h):
    """Cover-crop to the card's aspect ratio.

    Cover rather than fit: a letterboxed photograph in a panel that is
    already a slab reads as a picture that did not belong there. Cropping
    loses some of the image and keeps the layout honest, which is the right
    trade for atmosphere.
    """
    im = Image.open(path).convert("RGB")
    sw, sh = im.size
    scale = max(w / float(sw), h / float(sh))
    im = im.resize((max(1, int(sw * scale)), max(1, int(sh * scale))),
                   Image.LANCZOS)
    x = (im.width - w) // 2
    y = (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def card(item, division):
    """One article, drawn the way the panel will draw it."""
    body = item.get("body") or []
    lines = []
    for para in body:
        lines.extend(wrap_mail(para, MAIL_WRAP) or [""])
        lines.append("")
    lines = lines[:-1] if lines else lines

    pic = newsart.for_item(item, division)
    h = PAD
    if pic:
        h += IMG_H + PAD
    h += 13 * SCALE + 4 * SCALE            # kicker
    head = wrap_mail(item.get("subject", ""), 34) or [""]
    h += len(head) * 21 * SCALE + 6 * SCALE
    h += len(lines) * 15 * SCALE + PAD

    img = Image.new("RGB", (CARD_W, int(h)), TH.panel)
    d = ImageDraw.Draw(img)
    y = PAD

    if pic:
        try:
            img.paste(_fit(pic, CARD_W - PAD * 2, IMG_H), (PAD, y))
            # A hairline in the accent colour, so the photograph reads as
            # part of the slab rather than pasted on top of it.
            d.rectangle([PAD, y, CARD_W - PAD - 1, y + IMG_H - 1],
                        outline=TH.border, width=1)
            y += IMG_H + PAD
        except Exception as exc:               # a bad file is not a crash
            d.text((PAD, y), "[unreadable: %s]" % exc, font=F_META, fill=TH.bad)
            y += 20 * SCALE

    kicker = "%s   ROUND %s" % (division.upper(), item.get("round") or "-")
    d.text((PAD, y), kicker, font=F_KICKER, fill=TH.accent)
    y += 13 * SCALE + 4 * SCALE

    for ln in head:
        d.text((PAD, y), ln, font=F_HEAD, fill=TH.text)
        y += 21 * SCALE
    y += 6 * SCALE

    for ln in lines:
        d.text((PAD, y), ln, font=F_BODY, fill=TH.dim if not ln else TH.text)
        y += 15 * SCALE
    return img


def main():
    print("pictures root:", newsart.root() or "(none)")
    # `list_careers()` returns summary DICTS, not names - the menu needs the
    # round counts to draw its rows. The slug is the thing `load()` takes.
    car = None
    for row in (season_mod.list_careers() or []):
        c = season_mod.load(row["slug"] if isinstance(row, dict) else row)
        if c is not None:
            car = c
            break
    if car is None:
        print("no career found - run one season first")
        return 1

    # Read through `inbox.messages()`, which is the accessor the panel
    # itself uses. Reading the career's raw dict here would be a SECOND view
    # of the archive, and two views of one store drift.
    items = [m for m in inbox_mod.messages(car)
             if m.get("feed") == "news"]
    if not items:
        print("that career has no news items yet")
        return 1

    # Preview against the divisions the user has actually photographed, so
    # the sheet shows real pictures rather than the fallback.
    # ONE DIVISION, because that is how a career reads: a season of Hot
    # hatch shows Hot hatch photographs and nothing else. Rotating the
    # division per card made a prettier sheet and a dishonest one.
    div = (car.name or "Generic")
    if not newsart.images(div, "on track"):
        # Nothing photographed for the career's own division yet, so preview
        # against one the user HAS shot rather than showing the empty case.
        have = [d for d, _c, _n in newsart.report()]
        div = have[0] if have else "Generic"
        print("no pictures for %r yet - previewing as %r"
              % (car.name, div))
    order = [div]

    cards = []
    for i, item in enumerate(items[:6]):
        cards.append(card(item, order[i % len(order)]))

    gap = 12 * SCALE
    cols = 2
    rows = (len(cards) + cols - 1) // cols
    colw = CARD_W + gap
    heights = [0] * cols
    for i, c in enumerate(cards):
        heights[i % cols] += c.height + gap
    sheet = Image.new("RGB", (colw * cols + gap, max(heights) + gap),
                      TH.panel2 if hasattr(TH, "panel2") else "#0d1b2a")
    ys = [gap] * cols
    for i, c in enumerate(cards):
        col = i % cols
        sheet.paste(c, (gap + col * colw, ys[col]))
        ys[col] += c.height + gap

    out = os.path.join(_DIR, "_news_preview.png")
    sheet.save(out)
    print("wrote %s  (%dx%d, %d articles)"
          % (out, sheet.width, sheet.height, len(cards)))
    for i, item in enumerate(items[:6]):
        pic = newsart.for_item(item, order[i % len(order)])
        print("  %-22s %-34s %s"
              % (item.get("kind"), item.get("subject", "")[:34],
                 os.path.basename(pic) if pic else "(no picture)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
