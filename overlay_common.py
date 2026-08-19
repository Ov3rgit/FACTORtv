# -*- coding: utf-8 -*-
"""
FACTORtv — shared foundation.

Theme tokens, the live skin that follows the era on track, and the small pure
helpers everything needs. Imports nothing from the overlay's own modules
except `era`, so it can never be part of an import cycle. Constants and pure
functions only: anything touching a tk widget, a win32 handle or live session
state belongs in the engine.

The theme is not a fixed palette. `Theme` is a mutable holder whose values are
swapped when the era changes, so draw code reads `TH.accent` and gets the
1968 amber or the 2025 cyan without knowing which era it is in.
"""
import re
import threading

import era as era_mod

# Fully transparent key colour. Must be a colour used nowhere else in the UI,
# hence the near-black-but-not-black value: pure #000000 appears in shadows
# and would punch holes through them.
CHROMA = "#010102"
WIN_ALPHA = 0.92

# --------------------------------------------------------------------------
# brand
#
# Sampled from the supplied Factor.png so the overlay and the logo are the
# same two colours rather than approximately the same two colours.
# --------------------------------------------------------------------------
BRAND_NAVY = "#1b3a5c"
BRAND_NAVY_DEEP = "#0d1b2a"
BRAND_CYAN = "#4fe0e8"
BRAND_WHITE = "#ffffff"

UPDATE_MS = 50            # 20 Hz: fast enough for event detection, cheap to draw
ROW_H = 24                # base row height, before the global UI scale
MAX_ROWS = 24


class _Scale(object):
    """Global UI scale, set once by the engine from settings.

    A mutable holder rather than a constant so every panel can multiply by
    `UI.k` without the scale having to be threaded through every draw call.
    """
    __slots__ = ("k",)

    def __init__(self):
        self.k = 1.0

    def __call__(self, n):
        return int(round(n * self.k))


UI = _Scale()


# --------------------------------------------------------------------------
# LAYOUT LAW
#
# Everything hugs an EDGE. The middle of the screen belongs to the driver.
#
# This is not a style preference, it is the difference between an overlay you
# can race with and one you turn off. A panel in the central band sits exactly
# where the apex, the braking marker and the car in front are, and no amount
# of usefulness makes up for not being able to see the corner.
#
# `KEEP_CLEAR` is that rule as a number: the fraction of the screen, measured
# from the centre, that no persistent panel may enter. Panels that appear only
# when the car is stationary or the session is over (the podium, the
# "waiting for rFactor 2" notice) are exempt — there is nothing to obstruct.
#
# tests/paneltest.py asserts this against every panel, so a future layout
# change cannot quietly creep back into the driving view.
# --------------------------------------------------------------------------
KEEP_CLEAR_X = 0.30       # +/- 30% of width around centre
KEEP_CLEAR_Y = 0.34       # +/- 34% of height around centre
EDGE = 18                 # base margin from the screen edge, before UI scale


# THE CORNER CONTROL STRIP — the hamburger, the envelope, and the mode badge
# under them. Everything that wants to sit in the top-left has to clear it, and
# it lives HERE rather than in one of the panel modules because two different
# files draw into that corner: `overlay_panels` puts the controls there and
# `overlay_draw` puts the status box beside them.
#
# It exists because they collided. `draw_status` was written to clear a single
# 30px hamburger, the envelope was later added in exactly the space it was
# clearing, and the badge went underneath both — so on a loading screen the
# status box sat on top of the one control the user needed at that moment.
# A shared measurement cannot drift the way two hardcoded offsets did.
CONTROL_BTN = 30        # the square buttons
CONTROL_GAP = 6         # between them, and under them
CONTROL_BADGE_H = 24    # the mode badge
CONTROL_BADGE_W = 150
# THE STRIP IS AS WIDE AS ITS WIDEST MEMBER, which is the badge and not the
# button row — the first version measured the buttons, and the badge (150px
# against their 66) went straight back under the status box. A strip that only
# measures part of itself is not a strip.
CONTROL_W = max(CONTROL_BTN * 2 + CONTROL_GAP, CONTROL_BADGE_W)
CONTROL_H = CONTROL_BTN + CONTROL_GAP + CONTROL_BADGE_H


def keep_clear_rect(game_rect):
    """The central box no persistent panel may overlap."""
    gx, gy, gw, gh = game_rect
    cx, cy = gx + gw / 2.0, gy + gh / 2.0
    return (cx - gw * KEEP_CLEAR_X, cy - gh * KEEP_CLEAR_Y,
            cx + gw * KEEP_CLEAR_X, cy + gh * KEEP_CLEAR_Y)

# Gap (seconds) inside which a car behind can genuinely make a move stick.
# Beyond it, "he's about to pounce" is crying wolf. Shared by the engineer's
# defend call and the objective threat check so both stay honest.
STRIKE_GAP = 0.8

# A position must hold this long before the booth will call it a pass.
PLACE_CONFIRM_S = 0.35

_RADIO_LOCK = threading.Lock()

VK_CONTROL, VK_SHIFT = 0x11, 0x10
VK_Q, VK_O, VK_E, VK_M, VK_D, VK_C, VK_R, VK_T = (0x51, 0x4F, 0x45, 0x4D,
                                                  0x44, 0x43, 0x52, 0x54)
VK_V = 0x56
VK_S = 0x53
VK_LBUTTON = 0x01
# Answering the career prompt. Modifier-gated like every other hotkey, so a
# bare Y or N in the game's own bindings can never be stolen.
VK_Y, VK_N = 0x59, 0x4E


class Theme(object):
    """Live palette. Mutated in place when the era changes so every drawing
    call sees the new colours on the next frame without being re-plumbed."""

    __slots__ = ("panel", "panel2", "border", "accent", "accent2", "text",
                 "dim", "you", "leader", "best", "good", "warn", "bad",
                 "dial", "font", "grain", "era_key", "era_label", "name")

    def __init__(self):
        self.apply(era_mod.SKINS["modern"])

    def apply(self, skin):
        for k in self.__slots__:
            if k in skin:
                setattr(self, k, skin[k])
        self.name = skin.get("name", "modern")
        self.era_key = skin.get("era_key", "")
        self.era_label = skin.get("era_label", "")

    def follow(self, era):
        """Re-skin to match an Era. Returns True if anything changed, so the
        engine can invalidate cached art only when it really needs to."""
        skin = era_mod.skin_for(era)
        if skin.get("era_key") == self.era_key and skin.get("name") == self.name:
            return False
        self.apply(skin)
        return True


TH = Theme()

# Per-driver colours for radio cards and the map. Ordered so adjacent
# positions get visually distinct hues rather than neighbouring ones.
DRIVER_COLORS = [
    "#ff3b3b", "#4fd6e0", "#ffb000", "#8a6dff", "#4fd13a",
    "#ff7a1a", "#29a8ff", "#e85aff", "#16c98a", "#ffe24d",
    "#ff5db4", "#b964ff", "#00c2c7", "#b6e02e", "#ff6f61",
    "#5ad1b0", "#c98a3c", "#9fd8ff", "#c3a6ff", "#88c057",
]

# HELMET COLOURS — one entry per `icon_helmet_N.png`, in that order, each
# taken from the dominant colour of the artwork itself.
#
# The radio card used to pick its colour from a hash of the driver's name and
# its helmet from a DIFFERENT hash of the same name, so a driver with a red
# name card wore a green helmet. Both now come from one index (see
# `overlay_rival.helmet_for`), and this list is what keeps the two agreeing —
# so if the artwork is ever changed, change these to match or the card will
# lie about the picture next to it.
HELMET_COLORS = [
    "#ff3b3b",   # 1  red
    "#ff7a1a",   # 2  orange
    "#3ade4a",   # 3  green
    "#4fe0e8",   # 4  cyan
    "#3d7bff",   # 5  blue
    "#a24dff",   # 6  purple
    "#ff4de0",   # 7  magenta
    "#ff3d7a",   # 8  rose
    "#ffe24d",   # 9  yellow
]

# Tyre compound colours. rF2 compound NAMES are mod-defined free text, so
# these are matched by substring rather than by index — an index table would
# be wrong for every mod that does not happen to share ISI's ordering.
TYRE_COLORS = [
    (r"hyper|ultra\s*soft|c5", "#ff4dd2"),
    (r"super\s*soft|c4", "#ff4d4d"),
    (r"\bsoft\b|\bs\b|c3", "#e03131"),
    (r"\bmedium\b|\bm\b|c2", "#f1c40f"),
    (r"\bhard\b|\bh\b|c1", "#e9ecef"),
    (r"inter", "#69db7c"),
    (r"\bwet\b|rain|full\s*wet", "#4dabf7"),
    (r"slick|dry", "#c9d1d9"),
]


def tyre_color(name):
    n = (name or "").lower()
    for pat, col in TYRE_COLORS:
        if re.search(pat, n):
            return col
    return "#9aa3ad"


def tyre_short(name):
    """One or two letters for the tower's compound column."""
    n = (name or "").lower()
    for pat, short in ((r"hyper", "HY"), (r"ultra", "US"), (r"super\s*soft", "SS"),
                       (r"inter", "I"), (r"full\s*wet|\bwet\b|rain", "W"),
                       (r"\bsoft\b|^s$", "S"), (r"\bmedium\b|^m$", "M"),
                       (r"\bhard\b|^h$", "H")):
        if re.search(pat, n):
            return short
    return (name or "")[:2].upper()


# --------------------------------------------------------------------------
# formatting helpers
# --------------------------------------------------------------------------
def fmt_lap(t):
    """m:ss.mmm, or a dash when there is no time yet."""
    if t is None or t <= 0:
        return "--:--.---"
    m = int(t // 60)
    s = t - m * 60
    return "%d:%06.3f" % (m, s) if m else "%.3f" % s


def spoken_gap(g):
    """A gap as a commentator SAYS it, not as a timing screen shows it.

    Lived in both `BoothMixin` and `RadioMixin` as byte-identical copies —
    a LAW 9 violation that was harmless only by luck. The MRO resolves
    `self._gap` to the booth's for both mixins, so editing the radio's copy
    changed nothing at all, silently. One home, one definition.
    """
    if g is None:
        return "--"
    if g >= 1.0:
        return "%.1f seconds" % g
    t = int(round(g * 10))
    # Rounding sub-0.05s to "0 tenths" reads as a broken readout. Below a
    # tenth there is no useful number to give, only a description.
    if t <= 0:
        return "right on your tail"
    return "1 tenth" if t == 1 else "%d tenths" % t


def spoken_lap(t):
    """A lap time as it is said out loud: no leading zeros, no placeholder.

    Distinct from `fmt_lap`, which is for the TIMING PANEL and returns
    "--:--.---" for a missing time — a caption reads that fine and a
    synthesiser does not. This returns "" instead, and the line that would
    have used it is gated (LAW 5).
    """
    if not t:
        return ""
    m = int(t // 60)
    s = t - m * 60
    return "%d:%06.3f" % (m, s) if m else "%.3f" % s


def fmt_delta(d):
    """Signed delta with an explicit sign, for sector comparisons."""
    if d is None:
        return "--.---"
    return "%+.3f" % d


def fmt_clock(secs):
    if secs is None or secs < 0:
        return "--:--"
    secs = int(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


# The lookbehind excludes a DECIMAL POINT as well as a digit. Without it
# "2.1 seconds" ends in "1 seconds" and was rewritten to "2.1 second" — which
# is how "2.1 second off the pace" went to air.
_ONE_PLURAL = re.compile(
    r"(?<![\d.])1 (lap|minute|second|corner|tenth|place|position|car|warning|"
    r"point|degree|stop|stint)s\b")


def _fix_plural(text):
    """Collapse '1 laps' -> '1 lap'.

    Templates hardcode the plural because they read correctly for n>=2, but a
    race-ending target always clamps to a single lap, so 1 was the only
    ungrammatical case left. The lookbehind keeps '11 laps' and '21 laps'
    untouched, and the noun whitelist stops it mangling anything that
    legitimately reads '1 ...s'.
    """
    return _ONE_PLURAL.sub(r"1 \1", text)


def safe_format(tmpl, kw):
    """str.format that never raises on a missing key — blanks it instead.

    Dialogue templates are data, not code. One typo in a JSON pool must not
    take the whole booth down mid-race.
    """
    class _D(dict):
        def __missing__(self, k):
            return ""
    try:
        return _fix_plural(tmpl.format_map(_D(kw)))
    except Exception:
        return tmpl


def shade(hexc, f):
    """Lighten (f>1) or darken (f<1) a #rrggbb colour."""
    try:
        h = hexc.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return hexc
    r, g, b = (max(0, min(255, int(v * f))) for v in (r, g, b))
    return "#%02x%02x%02x" % (r, g, b)


def mix(a, b, t):
    """Blend two hex colours; t=0 gives a, t=1 gives b."""
    try:
        ah, bh = a.lstrip("#"), b.lstrip("#")
        ar, ag, ab = (int(ah[i:i + 2], 16) for i in (0, 2, 4))
        br, bg, bb = (int(bh[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return a
    t = max(0.0, min(1.0, t))
    return "#%02x%02x%02x" % (int(ar + (br - ar) * t),
                              int(ag + (bg - ag) * t),
                              int(ab + (bb - ab) * t))


def heat_color(frac, cold="#4dabf7", ok="#69db7c", hot="#ff4d4d"):
    """Cold -> optimal -> hot ramp for tyre and brake temperatures.

    frac is 0 at stone cold, 0.5 at the optimal window, 1 at overheating.
    """
    if frac is None:
        return "#4a5560"
    if frac <= 0.5:
        return mix(cold, ok, frac * 2.0)
    return mix(ok, hot, (frac - 0.5) * 2.0)


def wear_color(w):
    """Tyre life colour. rF2 reports wear as 1.0 new -> 0.0 destroyed."""
    if w is None:
        return "#4a5560"
    if w > 0.7:
        return "#69db7c"
    if w > 0.45:
        return "#c8d94a"
    if w > 0.25:
        return "#e6a23c"
    return "#ff4d4d"


def ordinal(n):
    if n is None:
        return ""
    if 10 <= (n % 100) <= 20:
        return "%dth" % n
    return "%d%s" % (n, {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


def spoken_place(n):
    """How a commentator says a position out loud."""
    if not n:
        return ""
    return {1: "the lead", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
            6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth",
            10: "tenth"}.get(n, "P%d" % n)


def spoken_rank(n):
    """A position as a RANK — "first", "second" — not as a race position.

    `spoken_place` returns "the lead" for 1, which is right for the road
    ("Verstappen takes the lead") and wrong inside a phrase about a class:
    "and the lead in the GT3 class" instead of "and first in the GT3 class".
    Two different jobs, two functions.
    """
    if not n:
        return ""
    return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
            6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth",
            10: "tenth"}.get(n, "%s" % ordinal(n))


def bubble_h(n_lines):
    """Radio bubble height for n message lines. Shared by the stacking maths
    and the drawn box so the two can never disagree.

    UI-scaled, because the text inside it is: an unscaled height with scaled
    19px lines overflowed the card at anything above 1.0x, which is half of
    why the engineer's longer calls appeared to be cut off."""
    return UI(42) + UI(19) * n_lines
