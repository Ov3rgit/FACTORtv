# -*- coding: utf-8 -*-
"""
FACTORtv — the telemetry dash.

rFactor 2's own readout is a thin strip of digits that tells you almost
nothing while you are busy driving. This replaces it with a proper cluster:
speed and gear, a rev arc that actually warns you, per-corner tyre life AND
temperature, live fuel burn with laps-remaining, and a damage diagram.

Everything here is era-adaptive, because a single cluster design cannot be
right for both a 1966 Brabham and a 2025 hybrid.

The gauge is driven by a SPEC table (`GAUGE_SPECS`, picked by `gauge_style`),
not by a handful of branches. That distinction was learned the hard way: an
earlier version had three looks separated mainly by palette, and the 2025,
1992 and stock-car gauges were indistinguishable at a glance. Distinction has
to live in the geometry — sweep angle, marker shape, bezel treatment, whether
the face carries a printed scale, whether a needle exists at all:

    modern      hexagonal bezel, 52 fine ticks, full 270 deg
    endurance   twin ring, dense ticks — GT and prototypes
    millennium  twin ring, softer than the current cars
    nineties    20 fat slabs with real gaps, 240 deg, solid red block
    eighties    wide spokes, shallow sweep, needle AND digits
    stock       heavy machined bezel, fat blocks — a Cup car is not an F1 car
    seventies   printed scale that does NOT light up, thin needle, numbers
    classic     11 sparse dots, no redline colour, smallest dial

`fills` is the line between the two families: an electronic tacho lights its
markers up with revs, a mechanical dial has a fixed printed scale with a
needle sweeping over it.

Capability gating matters as much as styling. The ERS readout is not merely
hidden on a 1992 car, it is never laid out at all — `era.has("ers")` decides
whether the space exists, so the cluster is compact on an old car instead of
being a modern layout with holes in it.

Run standalone to preview every era side by side without the game:
    python overlay_dash.py
"""
import math
import time

import gauge as gauge_mod
from overlay_common import (TH, UI, EDGE, UPDATE_MS, heat_color, mix, shade,
                            wear_color)

# Tyre temperature window, in Celsius, per discipline. rF2 does not publish an
# optimal figure (it is per-mod tyre data), so the dash needs its own
# reference or every tyre reads "cold" forever. These are the broad windows
# each kind of tyre actually works in.
TYRE_WINDOW = {
    "f1": (85.0, 110.0),
    "formula": (70.0, 95.0),
    "indycar": (80.0, 105.0),
    "gt": (75.0, 100.0),
    "proto": (75.0, 100.0),
    "stock": (70.0, 95.0),
    "touring": (70.0, 95.0),
    "kart": (50.0, 75.0),
    "unknown": (70.0, 100.0),
}
# Period tyres run cooler, but not as much cooler as the first guess of
# 50-80 C assumed — that window painted every corner of a historic car solid
# red from the out-lap onward, which is no signal at all. Widened to a range
# a 1960s-70s slick/crossply actually works in.
TYRE_WINDOW_HISTORIC = (60.0, 100.0)

BRAKE_WINDOW = {
    "f1": (350.0, 750.0),
    "formula": (250.0, 550.0),
    "indycar": (300.0, 650.0),
    "gt": (300.0, 650.0),
    "proto": (300.0, 650.0),
    "stock": (250.0, 550.0),
    "touring": (250.0, 550.0),
    "unknown": (250.0, 600.0),
}

# rF2's mDentSeverity is 8 zones read clockwise from the nose. The plugin
# inherits this from the ISI internals and does not name them, so the mapping
# is pinned here once rather than guessed at each call site.
DAMAGE_ZONES = ["nose", "front right", "right", "rear right",
                "tail", "rear left", "left", "front left"]


# --------------------------------------------------------------------------
# gauge specs
#
# One entry per era/discipline look. Distinction is carried by GEOMETRY, not
# by palette: sweep angle, marker shape, bezel, whether the face is numbered,
# whether a needle exists, and how the redline is drawn. Two gauges that share
# a colour scheme but differ on these read as different instruments; two that
# share these but differ on colour do not.
#
#   kind         line | block | dot     shape of each marker
#   fills        True  = markers light up with revs (electronic tacho)
#                False = markers are a fixed printed scale (mechanical dial)
#   redline_kind ticks | block | none
#   centre       digital (big number in the middle) | dial (number low, needle)
# --------------------------------------------------------------------------
_GAUGE_BASE = {
    "shape": "ring",   # ring | strip
    "start": 225.0, "sweep": -270.0, "marks": 44, "kind": "line",
    "mark_len": 9, "mark_w": 2, "minor_inset": 3, "major_every": 0,
    "face": True, "face_shade": 0.72, "face_gap": 5, "face_nums": 0,
    "num_inset": 8, "bold_nums": False, "needle": None, "needle_col": None,
    "bezel": "none", "bezel_gap": 4, "centre": "digital", "fills": True,
    "redline_kind": "ticks", "redline_at": 0.96, "r_scale": 1.0,
    # SHIFT BAND — the window where an upshift is actually optimal, as a
    # fraction of max RPM. rF2 publishes no per-car optimal shift point, so
    # this is the honest general answer: the last stretch before the limiter.
    #
    # The three zones must READ as a sequence, and an earlier version had the
    # purple band sitting INSIDE the red one, which says two contradictory
    # things about the same revs. So:
    #
    #     below shift_from   cyan     still pulling, hold it
    #     shift_from..to     PURPLE   shift now
    #     above shift_to     red      past it, you are on the limiter
    #
    # `redline_at` is therefore the same number as `shift_to`, and any spec
    # that overrides one should override the other.
    "shift_from": 0.86, "shift_to": 0.96,
}


def _spec(**kw):
    d = dict(_GAUGE_BASE)
    d.update(kw)
    return d


GAUGE_SPECS = {
    # 2014+ F1 / FSR — NOT a dial. A current Formula One wheel has a
    # horizontal ladder of shift LEDs above a rectangular screen, and that
    # silhouette is the single most recognisable thing about the object. It
    # was drawn as a circular gauge, which made the 2025 car read as a road
    # car. `shape` switches renderer; the ring keys below are unused for it.
    "modern": _spec(shape="strip", leds=15, led_gap=3, led_h=13,
                    strip_pad=6, screen_gap=7,
                    marks=52, mark_w=2, mark_len=9, bezel="hex", bezel_gap=6,
                    major_every=13),

    # LE MANS / WEC — a Hypercar or an LMP2 has the same kind of wheel as an
    # F1 car: a shift ladder over a rectangular screen. Shares the strip
    # renderer at the user's suggestion, with its own ladder (fewer, wider
    # LEDs and a green-amber-red sequence) so a prototype is still not an F1
    # car at a glance.
    "lmp": _spec(shape="strip", leds=12, led_gap=4, led_h=14,
                 strip_pad=6, screen_gap=7),

    # GT3 — the Bosch/Cosworth display in every current GT car: a dense white
    # ring on a black face inside a heavy machined bezel, with the shift
    # colours living in the last third of the sweep rather than in a ladder.
    "gt3": _spec(marks=48, mark_w=2, mark_len=10, bezel="heavy", bezel_gap=5,
                 major_every=12, redline_at=0.95, shift_from=0.85,
                 shift_to=0.95, r_scale=0.98),

    # DTM — a silhouette tin-top, and deliberately the most aggressive of the
    # modern round gauges: fewer, fatter segments and a shallower sweep, so a
    # Class 1 car cannot be mistaken for the GT3 beside it on the same grid.
    "dtm": _spec(marks=26, kind="block", mark_w=5, mark_len=13, minor_inset=0,
                 sweep=-250.0, start=215.0, bezel="ring", bezel_gap=5,
                 redline_kind="block", redline_at=0.94, shift_from=0.85,
                 shift_to=0.94, r_scale=0.97),

    # 2000-2013 — a SPORTY ROUND gauge, which is what the cars of that decade
    # actually had: a fine white tacho ring on a carbon face inside a twin
    # chrome bezel, with a red arc rather than a colour-changing ladder. The
    # previous amber segment ring read as a 1990s LED tacho and made a 2005
    # car look older than a 1992 one.
    "millennium": _spec(marks=44, mark_w=2, mark_len=10, bezel="double",
                        bezel_gap=5, major_every=11, redline_kind="block",
                        redline_at=0.95, shift_from=0.85, shift_to=0.95,
                        r_scale=0.96),

    # 1989-1999 — chunky segment tacho: few, fat slabs with real gaps, a
    # tighter sweep and a solid red block instead of red ticks. Nothing about
    # this silhouette can be confused with the modern fine ring.
    "nineties": _spec(marks=20, kind="block", mark_w=7, mark_len=13,
                      minor_inset=0, sweep=-240.0, start=210.0,
                      redline_kind="block", redline_at=0.94, shift_from=0.84, shift_to=0.94, bezel="none",
                      face_shade=0.6),

    # Turbo era — wide spokes, shallow sweep, needle AND digits.
    "eighties": _spec(marks=16, kind="block", mark_w=6, mark_len=15,
                      minor_inset=0, sweep=-220.0, start=200.0,
                      needle="thick", redline_kind="block", redline_at=0.94, shift_from=0.84, shift_to=0.94,
                      bezel="ring", face_shade=0.55),

    # 1970s — a proper mechanical dial: printed scale that does NOT light up,
    # numbers on the face, thin needle, number read low on the dial.
    "seventies": _spec(marks=31, kind="line", mark_w=1, mark_len=8,
                       minor_inset=4, major_every=3, sweep=-250.0,
                       start=215.0, fills=False, needle="thin",
                       face_nums=5, num_inset=4, redline_kind="block",
                       redline_at=0.95, shift_from=0.86, shift_to=0.95, bezel="ring", centre="dial",
                       r_scale=0.94),

    # 1960s — sparse dot markers, no redline colour at all, smallest dial.
    # Deliberately the quietest instrument on the list.
    "classic": _spec(marks=11, kind="dot", mark_w=2, mark_len=7,
                     sweep=-240.0, start=210.0, fills=False, needle="thin",
                     face_nums=5, num_inset=5, redline_kind="none",
                     bezel="none", centre="dial", r_scale=0.93,
                     face_shade=0.5),

    "vintage": _spec(marks=9, kind="dot", mark_w=2, mark_len=7, sweep=-220.0,
                     start=200.0, fills=False, needle="thin", face_nums=4,
                     num_inset=5, redline_kind="none", bezel="none",
                     centre="dial", r_scale=0.9, face_shade=0.5),

    # Stock car — heavy machined bezel and bold numerals ON the face. Same
    # era as a modern F1 car, completely different object.
    "stock": _spec(marks=30, kind="block", mark_w=5, mark_len=11,
                   minor_inset=0, bezel="heavy", bezel_gap=5,
                   redline_kind="block", redline_at=0.94, shift_from=0.84, shift_to=0.94, face_shade=0.45,
                   r_scale=0.98),

    # Prototypes / GT — twin ring, dense but calmer than an F1 car.
    "endurance": _spec(marks=46, bezel="double", r_scale=0.97),
}


def gauge_style(era):
    """Which gauge spec an Era gets.

    Discipline wins over period, because a 2023 Cup car and a 2023 F1 car are
    the same era and must not share an instrument. Everything else falls back
    to the period skin name, so any new mod lands somewhere sensible.
    """
    if era.discipline == "stock":
        return "stock"
    name = era_skin_name(era)

    # A discipline only claims its own instrument for the PERIOD that
    # actually had it, and the period skin is the test — NOT `is_historic`,
    # which means pre-1980 (pioneer/golden/wing) and so happily let a 1990
    # Group C car through to a modern LED shift ladder.
    #
    # gt and proto also used to share one "endurance" gauge, so a GT3 car and
    # a Hypercar in the same race carried the same instrument — the one place
    # the distinction matters most.
    if name == "modern":
        if era.discipline == "proto":
            return "lmp"            # WEC: the F1 strip, its own ladder
        if era.discipline == "gt":
            return "gt3"
        if era.discipline == "touring":
            return "dtm"
    elif name == "millennium":
        # The 2000s get ROUND instruments across the board; the shift ladder
        # belongs to the cars that actually carried one.
        if era.discipline == "gt":
            return "gt3"
        if era.discipline == "touring":
            return "dtm"
        return "millennium"

    return name if name in GAUGE_SPECS else "modern"


def era_skin_name(era):
    return getattr(era, "skin", "modern")


def _win_for(era, table, historic=None):
    if historic is not None and era.is_historic:
        return historic
    return table.get(era.discipline, table["unknown"])


def temp_frac(c, lo, hi):
    """Map a temperature onto 0=cold, 0.5=in the window, 1=overheating."""
    if c is None:
        return None
    if c <= lo:
        return max(0.0, 0.5 * (c / lo)) if lo else 0.0
    if c >= hi:
        return min(1.0, 0.5 + 0.5 * (c - hi) / max(1.0, hi * 0.25))
    return 0.5


class FuelModel(object):
    """Live fuel burn, measured rather than assumed.

    rF2 reports litres in the tank and nothing else, so consumption has to be
    observed. Sampling per completed lap (not per tick) is what makes the
    number stable: within a lap the reading swings with tank slosh and with
    the difference between a pit-lane crawl and a qualifying lap.
    """

    def __init__(self, window=5):
        self.window = window
        self.laps = []            # litres burned per completed lap
        self._lap = None
        self._fuel_at_lap = None

    def reset(self):
        self.laps = []
        self._lap = None
        self._fuel_at_lap = None

    def update(self, lap_number, fuel):
        if fuel is None or lap_number is None:
            return
        if self._lap is None:
            self._lap, self._fuel_at_lap = lap_number, fuel
            return
        if lap_number > self._lap:
            used = self._fuel_at_lap - fuel
            # A refuel makes this negative and an out-lap makes it tiny;
            # both would poison the average, so only plausible burns count.
            if 0.05 < used < 30.0:
                self.laps.append(used)
                del self.laps[:-self.window]
            self._lap, self._fuel_at_lap = lap_number, fuel
        elif fuel > self._fuel_at_lap + 1.0:
            self._fuel_at_lap = fuel      # refuelled mid-lap

    @property
    def per_lap(self):
        if not self.laps:
            return None
        return sum(self.laps) / len(self.laps)

    def laps_left(self, fuel):
        p = self.per_lap
        if not p or fuel is None:
            return None
        return fuel / p

    def enough_for(self, fuel, laps_to_go):
        """None = unknown, else litres of margin (negative means short)."""
        p = self.per_lap
        if not p or fuel is None or laps_to_go is None:
            return None
        return fuel - p * laps_to_go


class DashMixin(object):
    """Draws the cluster. Mixed into the Overlay so it shares `self`."""

    # How much of the tick to leave for the rest of the frame — the panels
    # drawn after the dash, plus Tk's own repaint, which is roughly a third
    # of a frame and is paid after every draw call has returned.
    FRAME_RESERVE_MS = 22.0

    def _frame_headroom_ms(self):
        """Milliseconds this frame can still spend without missing the tick.

        Zero when the frame is already late, which is the honest answer: a
        frame that has overrun has nothing spare to prewarm with, and stealing
        from it makes the next one late as well.
        """
        t0 = getattr(self, "_frame_t0", None)
        if t0 is None:
            return 6.0                  # not instrumented: the old fixed budget
        spent = (time.perf_counter() - t0) * 1000.0
        return max(0.0, UPDATE_MS - spent - self.FRAME_RESERVE_MS)

    # -- public ------------------------------------------------------------
    def draw_dash(self, s):
        """Full cluster for the followed car, in THREE columns.

            [   gauge   ] [ damage ] [ tyres / brakes / fuel ]

        Damage sits in the middle rather than on its own row underneath. It
        is a small, tall graphic — a car seen from above — so it fits the gap
        between the round instrument and the stacked numbers, and putting it
        there removes a whole row of height from the panel.

        The gauge is the largest element and sits hard left, because it is
        the one thing read at a glance mid-corner; everything to its right is
        read on a straight.
        """
        car = s.player if s else None
        if car is None or not self.show_dash:
            return
        era = s.player_era or s.era
        style = TH.dial

        self.fuel_model.update(car.laps, car.fuel)

        w, h = self._dash_size(era)
        x, y = self._dash_origin(w, h)
        # PUBLISHED so other panels can keep clear of it. The radio cards and
        # the caption used to derive the dash's size independently and get it
        # wrong, which is how cards ended up drawn across the speedo.
        self._dash_rect = (x, y, w, h)
        p = self._begin_panel("dash", x, y, w, h)
        c = p.canvas_at(x, y)

        # THE INSTRUMENT IS COMPOSITED ONTO WHATEVER THIS PANEL IS. Set
        # before anything is drawn, because a stale backdrop is a black square
        # on a navy card — which is exactly how this was found.
        gauge_mod.set_backdrop(TH.panel)
        self._dash_body(c, x, y, w, h)

        pad = UI(self.PAD_OUT)
        top = y + pad
        gauge_w, gauge_left = self.gauge_col(era)
        dmg_w = self.COL_DAMAGE
        gap = UI(self.GAP_COL)

        gx0 = x + pad
        dx0 = gx0 + gauge_w + gap
        tx0 = dx0 + dmg_w + gap
        tw = w - (tx0 - x) - pad

        # -- column 1: the instrument -----------------------------------------
        #
        # The sub-draws centre the gauge on (x + w/2). Shifting the ORIGIN by
        # half the pill imbalance puts that centre where the instrument
        # actually belongs — so a car with DRS and no ERS does not sit visibly
        # left of its own column — without any of them knowing about pills.
        pill_shift = gauge_left - (gauge_w - 2 * self.gauge_clear - gauge_left)
        gx0 = gx0 + pill_shift / 2.0
        if style == "analogue":
            self._dash_analogue(c, gx0, top, gauge_w, car, era, s)
        elif style == "hybrid":
            self._dash_hybrid(c, gx0, top, gauge_w, car, era, s)
        else:
            self._dash_digital(c, gx0, top, gauge_w, car, era, s)

        # -- column 2: damage ---------------------------------------------------
        self._dash_damage(c, dx0, top, dmg_w, car, era)

        # -- column 3: the slow-moving numbers ---------------------------------
        yy = top
        yy += self._dash_tyres(c, tx0, yy, tw, car, era) + UI(10)
        self._dash_fuel(c, tx0, yy, tw, car, era, s)

    # -- geometry -----------------------------------------------------------
    # Block heights, kept as named constants because _dash_size and the
    # draw methods MUST agree. When they drifted apart the damage readout
    # was laid out past the bottom edge of its own panel.
    # THE INSTRUMENT'S RADIUS, and the one knob that sizes it.
    #
    # 96 -> 62 on 2026-08-17 (35% smaller, for the lag he reported: the gauge
    # is a PIL image rendered at SS=3 and downscaled, so cost is in PIXELS
    # and pixels go as the square of this number — 0.65^2 = 0.42, a 58% cut).
    # Then 62 -> 68 the same day: still noticeably smaller than the original
    # 96 and a comfortable 58% of the pixel cost (0.71^2 = 0.51), rather than
    # the 42% the first cut left it at.
    GAUGE_R = 68          # base; multiplied by the global UI scale
    H_SPEED_DIGITAL = 2 * GAUGE_R + 18
    H_SPEED_DIAL = 2 * GAUGE_R + 18
    H_TYRES = 12 + 2 * 30 + 5 + 16      # label + 2 rows + gap + brake strip
    H_FUEL = 15 + 12 + 16
    H_DAMAGE = 16 + 74 + 38
    PAD = 11
    BEZEL_CLEAR = 12

    # THE CARD'S OWN SPACING, and it is two knobs rather than seven hardcoded
    # UI(10)s scattered through the sizer and the drawing code.
    #
    # It floated over the road until today, and generous spacing is right for
    # something with no edges — the picture separates the blocks for you. On a
    # CARD the same spacing reads as a panel with elements adrift in it, which
    # is what the user saw: "way too much space between the elements, and
    # there's too much padding on the card too".
    #
    # Both are deliberately small. The card supplies the separation now; the
    # gaps only have to stop two blocks touching.
    PAD_OUT = 6           # card edge to content
    GAP_COL = 7           # between the three columns

    @property
    def gauge_r(self):
        return UI(self.GAUGE_R)

    PILL_W = 46

    @property
    def gauge_top_extent(self):
        """How far the drawn instrument reaches ABOVE its centre.

        A hex bezel's top VERTEX sits at (r + gap) / cos(30), well beyond the
        ring itself. Positioning the gauge from `r` alone therefore placed its
        centre too low and let the bezel poke out of the top of the column,
        leaving the instrument visually slumped relative to the tyre and
        damage blocks beside it.
        """
        return self.gauge_r * 1.16 + UI(8)

    @property
    def gauge_clear(self):
        """Distance from the gauge centre at which a flanking pill may start.

        Derived, not guessed. A hex bezel is drawn with its circumradius
        scaled by 1/cos(30) so its FLAT sides clear the tick marks, which
        pushes its horizontal extent past `r`. The 1.10 covers that; the
        constant is the breathing room on top.
        """
        return self.gauge_r * 1.10 + UI(self.BEZEL_CLEAR)

    def pill_sides(self, era):
        """(left, right) — which flanking pills this car actually gets.

        DRS sits on the left, ERS on the right, P2P on the left for the cars
        that have it. A 1966 Brabham has none of them.
        """
        if era is None:
            return False, False
        # A STRIP GAUGE CARRIES ITS OWN PILLS. The LED-ladder styles draw DRS
        # and ERS inside the strip, under the screen — so reserving flanking
        # space for them leaves the column with two pill-shaped holes in it,
        # which is precisely the dead space measured on the preview. Only the
        # RING gauges have anything beside them.
        spec = GAUGE_SPECS.get(gauge_style(era), GAUGE_SPECS["modern"])
        if spec.get("shape") == "strip":
            return False, False
        # THE PERIOD DIALS HAVE A GEAR BLOCK BESIDE THEM, not a pill — but it
        # occupies the same space and the column has to reserve it. Tightening
        # the column without this clipped the gear digit against the card
        # border on every pre-1980 car, which is exactly what the user saw.
        if TH.dial == "analogue":
            return True, bool(era.has("ers"))
        left = bool(era.has("drs") or era.has("ptp"))
        right = bool(era.has("ers"))
        return left, right

    def gauge_col(self, era):
        """(column width, left pill width) for this car's instrument.

        THE COLUMN RESERVES SPACE FOR PILLS THAT EXIST, NOT FOR PILLS THAT
        MIGHT. It used to reserve BOTH slots unconditionally, so a car with no
        DRS and no ERS — and every car with only one of them — got a column
        with a pill-shaped hole in it. Measured on the rendered preview, that
        was 64px of dead space against the card edge and 68px between the
        instrument and the damage block, which is exactly what the user saw:
        "do you see how much space there is between the gauge and the damage
        zones, and between the gauge and the border of the card?"

        The gauge is then centred on the space it actually occupies rather than
        on the column, which is what stops an asymmetric pill set (DRS but no
        ERS) leaving the instrument visibly off-centre.
        """
        left, right = self.pill_sides(era)
        pill = UI(self.PILL_W)
        lw = pill if left else 0
        rw = pill if right else 0
        return int(2 * self.gauge_clear + lw + rw + UI(2)), lw

    @property
    def COL_GAUGE(self):
        """Widest the instrument column can be — both pills present.

        Kept for callers that have no era to hand. `gauge_col` is the honest
        one and is what the layout uses.
        """
        return int(2 * (self.gauge_clear + UI(self.PILL_W)) + UI(2))

    @property
    def COL_DAMAGE(self):
        """Width of the damage column — the car plan plus its status text."""
        return UI(104)

    def _dash_size(self, era):
        """Three columns; height is whichever column is tallest.

        Damage moved out of its own full-width row and into the middle
        column, which took a whole block of height out of the panel.
        """
        style = TH.dial
        # Measured from the drawn extent, so a bezel change cannot silently
        # push the instrument outside its own panel.
        col_gauge = int(self.gauge_top_extent * 2 + UI(4))
        col_right = self.H_TYRES + self.PAD + self.H_FUEL
        col_dmg = self.H_DAMAGE
        tallest = max(col_gauge, UI(col_right), UI(col_dmg))
        h = UI(self.PAD_OUT) + tallest + UI(self.PAD_OUT)
        gauge_w, _left = self.gauge_col(era)
        w = (UI(self.PAD_OUT) + gauge_w + UI(self.GAP_COL)
             + self.COL_DAMAGE + UI(self.GAP_COL) + UI(186)
             + UI(self.PAD_OUT))
        return w, h

    def _dash_origin(self, w, h):
        """Bottom-right corner, hard against the edges.

        An earlier version pushed this toward the centre to make it easier to
        read at a glance. That was the wrong trade: it put a 490px panel in
        the middle-right of the screen, directly over the apex on every
        right-hander. The readability problem was really a SIZE problem, and
        it is solved by the global UI scale instead — the cluster is now half
        again as large as it was, in the corner where it belongs.

        See LAYOUT LAW in overlay_common: the centre of the screen is the
        driver's.
        """
        gx, gy, gw, gh = self.game_rect
        return (gx + gw - w - UI(EDGE), gy + gh - h - UI(EDGE))

    def _dash_body(self, c, x, y, w, h):
        """The dash sits on a card, like every other panel.

        THIS HOOK EXISTED FOR EXACTLY THIS. It used to draw nothing on
        purpose: the panel window is chroma-keyed, so an empty body let the
        instruments float over the road, which reads as broadcast furniture
        rather than a bolted-on utility. The comment left behind said a future
        opaque mode had one obvious place to live, and this is it.

        The user tried the floating version in the car and asked for the card
        back — "I thought I wanted it transparent but let's rather just have
        it on a card like everything else". He is right for a reason worth
        recording: the rest of the overlay is a set of slabs, and ONE element
        with different rules reads as an element that has not been finished.
        Consistency beats the nicer-in-isolation option.

        `_body` is the same slab the tower, the relative panel and the menu
        use — same fill, same border, same accent spine — so it cannot drift
        away from them.
        """
        self._body(c, x, y, w, h)

    # -- speed blocks --------------------------------------------------------
    def _rev_frac(self, car):
        mx = car.max_rpm or 0.0
        if not mx:
            return 0.0
        return max(0.0, min(1.0, (car.rpm or 0.0) / mx))

    def _side_pill(self, c, x, y, w, text, value, on=None, col=None):
        """A small floating readout beside the gauge.

        No enclosing panel — just a tinted capsule, so it sits on the picture
        the way a broadcast bug does.
        """
        h = 16
        fill = shade(TH.panel, 0.85) if not on else (col or TH.good)
        c.create_rectangle(x, y, x + w, y + h, fill=fill,
                           outline=shade(TH.border, 1.1))
        c.create_text(x + 5, y + h / 2, text=text, anchor="w",
                      fill=TH.panel if on else TH.dim, font=self.f_tiny)
        if value is not None:
            c.create_text(x + w - 5, y + h / 2, text=value, anchor="e",
                          fill=TH.panel if on else TH.text, font=self.f_tiny)
        return h

    def _dash_digital(self, c, x, y, w, car, era, s):
        """Modern: LED shift ladder over a screen, or a fine-segment ring."""
        r = self.gauge_r
        # Top-aligned with the neighbouring columns: the centre is placed a
        # full bezel-height down, not merely a radius.
        cx, cy = x + w / 2.0, y + self.gauge_top_extent
        style = gauge_style(era)
        sp = GAUGE_SPECS.get(style, GAUGE_SPECS["modern"])
        self._gauge(c, cx, cy, r, self._rev_frac(car), car.speed, car.gear,
                    style)

        has_drs = era.has("drs")
        has_ers = era.has("ers") or era.has("kers")
        pw = UI(self.PILL_W)

        if sp.get("shape") == "strip":
            # DRS and ERS belong ON the screen. Flanking a rectangular display
            # with floating pills is not what the object looks like, and in a
            # narrow column they hung outside the panel entirely.
            size = int(2 * r * sp["r_scale"] + UI(14))
            half = size / 2.0
            # Everything sits INSIDE the screen. The first version hung the
            # charge percentage below the pill, which put it outside the
            # screen rectangle and, in the corner of the actual overlay,
            # outside the panel.
            row = cy + half - UI(sp["strip_pad"]) - UI(26)
            inner = half - UI(14)
            # Wider than the flanking pills: these carry a label AND a value,
            # and at the flanking width "ERS" and "62%" printed over the top
            # of each other.
            pw = UI(self.PILL_W + 20)
            if has_drs:
                self._side_pill(c, cx - inner, row, pw, "DRS", None,
                                on=bool(car.flap), col=TH.good)
            if has_ers:
                b = car.battery
                bx0 = cx + inner - pw
                # The charge goes in the pill's own value slot rather than
                # under it, so the label and its number cannot be read apart.
                self._side_pill(c, bx0, row, pw, "ERS",
                                None if b is None else "%d%%" % (b * 100))
                if b is not None:
                    b = max(0.0, min(1.0, b))
                    c.create_rectangle(bx0, row + UI(15), bx0 + pw,
                                       row + UI(20),
                                       fill=shade(TH.panel, 0.8),
                                       outline=shade(TH.border, 1.1))
                    c.create_rectangle(bx0 + 1, row + UI(16),
                                       bx0 + 1 + (pw - 2) * b, row + UI(19),
                                       fill=TH.accent2, outline="")
            return 2 * r + 12

        # Flanking readouts for the ring gauges. The clearance has to beat the
        # BEZEL, not the ring: the hex corners stand ~6px proud of r, so a 4px
        # gap left the pills touching it. There is deliberately no GEAR pill —
        # the gear is already the largest thing in the middle of the gauge.
        clear = self.gauge_clear
        px = cx - clear - pw
        py = cy - 20
        if has_drs:
            self._side_pill(c, px, py, pw, "DRS", None, on=bool(car.flap),
                            col=TH.good)
        if has_ers:
            b = car.battery
            rx = cx + clear
            self._side_pill(c, rx, py, pw, "ERS", None)
            if b is not None:
                c.create_text(rx + pw / 2, py + 26,
                              text="%d%%" % (b * 100), fill=TH.text,
                              font=self.f_tiny)
                c.create_rectangle(rx, py + 33, rx + pw, py + 39,
                                   fill=shade(TH.panel, 0.8),
                                   outline=shade(TH.border, 1.1))
                c.create_rectangle(rx + 1, py + 34,
                                   rx + 1 + (pw - 2) * max(0.0, min(1.0, b)),
                                   py + 38, fill=TH.accent2, outline="")
        return 2 * r + 12

    def _dash_hybrid(self, c, x, y, w, car, era, s):
        """1982-1999 and stock cars: chunkier spokes, same centred readout."""
        r = self.gauge_r
        # Top-aligned with the neighbouring columns: the centre is placed a
        # full bezel-height down, not merely a radius.
        cx, cy = x + w / 2.0, y + self.gauge_top_extent
        self._gauge(c, cx, cy, r, self._rev_frac(car), car.speed, car.gear,
                    gauge_style(era))
        if era.has("ptp"):
            self._side_pill(c, x, cy - 8, 52, "P2P", None)
        return 2 * r + 12

    def _dash_analogue(self, c, x, y, w, car, era, s):
        """Instruments, not a data screen.

        A 1968 driver had a rev counter and a pit board, so this is a numbered
        dial with a real needle and the speed read off the face — nothing that
        implies live telemetry existed.
        """
        r = self.gauge_r
        # Top-aligned with the neighbouring columns: the centre is placed a
        # full bezel-height down, not merely a radius.
        cx, cy = x + w / 2.0, y + self.gauge_top_extent
        self._gauge(c, cx, cy, r, self._rev_frac(car), car.speed, car.gear,
                    gauge_style(era))
        g = car.gear
        gtxt = "N" if g == 0 else ("R" if g and g < 0 else str(g or "-"))
        # UI-SCALED, and it was not. A bare 22 puts the gear block in a
        # different place relative to the dial at every scale the user might
        # run, and at 1.25 it sat hard against the column edge.
        gxp = cx - r - UI(24)
        c.create_text(gxp, cy - UI(4), text=gtxt, fill=TH.accent,
                      font=self.f_gear)
        c.create_text(gxp, cy + UI(16), text="GEAR", fill=TH.dim,
                      font=self.f_tiny)
        return 2 * r + 12

    # -- the gauge ------------------------------------------------------------
    def _gauge(self, c, cx, cy, r, rev_frac, speed, gear, style,
               redline=None):
        """A free-floating instrument, built from a per-era SPEC.

        The GRAPHIC is rendered by `gauge.py` with PIL and blitted as a single
        cached image; only the numbers are drawn by the canvas. Two reasons,
        both of which the old all-canvas version got wrong:

          * Tk has no antialiasing, and an instrument made of ~200 hard-edged
            lines and arcs looks like pixel art no matter what colour it is.
          * Those ~200 items were deleted and recreated at 20 Hz, every
            frame, which is where the stutter came from.

        Geometry still lives in the spec table, because colour alone is not
        distinction: an earlier version had the 2025, 1992 and stock-car
        gauges all reading as "circle plus cyan ticks".
        """
        sp = GAUGE_SPECS.get(style, GAUGE_SPECS["modern"])
        if redline is None:
            redline = sp["redline_at"]
        rev_frac = max(0.0, min(1.0, rev_frac or 0.0))
        rr = r * sp["r_scale"]
        size = int(2 * rr + UI(14))

        # Fill the cache AHEAD of being asked. A miss costs 12-28ms and
        # every frame of an acceleration lands in a bucket never used before,
        # so lazy filling paid for itself at exactly the wrong moment — which
        # is what made the gauge lurch instead of sweep.
        # Fill it with the time THIS FRAME actually has left, not with a fixed
        # 6ms. A render is 12-28ms and can never fit in 6, so the old budget
        # was always overrun by a whole one — the dash measured a 4ms mean
        # against a 21ms worst, and that spike IS the stutter, because a cold
        # cache and hard acceleration are the same moment. Frames are ~22ms
        # against a 50ms tick, so there is real headroom most of the time;
        # when there is not, prewarming waits rather than blowing the budget.
        gauge_mod.prewarm_async(style, sp, size, size, redline,
                                convert_ms=min(3.0, self._frame_headroom_ms()))
        img = gauge_mod.photo(style, sp, size, size, rev_frac, redline)
        if img is not None:
            # The cache owns the reference; a canvas image item does not, and
            # letting it be collected blanks the gauge.
            c.create_image(cx, cy, image=img)

        shifting = sp["shift_from"] <= rev_frac <= sp["shift_to"]
        over = rev_frac > sp["shift_to"]
        gtxt = "N" if gear == 0 else ("R" if gear and gear < 0 else str(gear or "-"))

        if sp.get("shape") == "strip":
            # Numbers live in the screen BELOW the LED ladder, laid out from
            # the same constants the renderer used so the two cannot drift.
            #
            # THE GEAR IS THE BIG NUMBER. On a real F1 wheel it dominates the
            # display and the speed is secondary — the driver knows how fast
            # he is going, what he needs at a glance is which gear he is in.
            # Drawn the other way round it read as a road-car speedometer.
            top = cy - size / 2.0
            sc0 = top + UI(sp["strip_pad"] + sp["led_h"] + sp["screen_gap"])
            sc1 = cy + size / 2.0 - UI(sp["strip_pad"])
            # The bottom strip is reserved for DRS/ERS by `_dash_digital`, so
            # the numbers are centred in what is LEFT, not in the whole
            # screen — otherwise the gear sat on top of the pills.
            mid = (sc0 + (sc1 - UI(34))) / 2.0
            gcol = TH.bad if over else (TH.warn if shifting else TH.text)
            # Spacing is set by the GEAR's font, not by guesswork: at 38pt it
            # is tall enough that a 12px stack put "KM/H" through the top of
            # the numeral.
            c.create_text(cx, mid + UI(14), text=gtxt, fill=gcol,
                          font=self.f_gear_big)
            c.create_text(cx, mid - UI(30), text="%d" % (speed or 0),
                          fill=TH.text, font=self.f_speed_sm)
            c.create_text(cx, mid - UI(16), text="KM/H", fill=TH.dim,
                          font=self.f_tiny)
            return

        ir = rr - sp["mark_len"] - sp["face_gap"]
        if sp["centre"] == "dial":
            # The needle owns the middle, so the number lives low on the face.
            # Sized from the face radius rather than fixed: the period dials
            # are deliberately different sizes, and one hardcoded font left
            # "KM/H" hanging over the rim of the smallest.
            fam = self.f_speed_sm[0]
            fs = max(9, min(16, int(ir * 0.36)))
            c.create_text(cx, cy + ir * 0.42, text="%d" % (speed or 0),
                          fill=TH.text, font=(fam, fs, "bold"))
            c.create_text(cx, cy + ir * 0.72, text="KM/H", fill=TH.dim,
                          font=(fam, max(6, fs - 6)))
            # Numbers printed on the dial face. Only ever on a needle dial: a
            # printed scale exists so you can read a needle against it, and
            # with a big digital figure in the middle there is nothing to read
            # it against — they simply collided with the speed readout.
            if sp["face_nums"]:
                self._face_numbers(c, cx, cy, ir, sp)
        else:
            c.create_text(cx, cy - UI(10), text="%d" % (speed or 0),
                          fill=TH.text, font=self.f_speed)
            c.create_text(cx, cy + UI(12), text="KM/H", fill=TH.dim,
                          font=self.f_tiny)
            c.create_line(cx - UI(18), cy + UI(23), cx + UI(18), cy + UI(23),
                          fill=shade(TH.border, 1.2))
            gcol = TH.warn if shifting else (TH.bad if over else TH.text)
            c.create_text(cx, cy + UI(34), text=gtxt, fill=gcol,
                          font=self.f_gear)

    def _face_numbers(self, c, cx, cy, ir, sp):
        """The printed scale on a mechanical dial."""
        steps = sp["face_nums"]
        start, sweep = sp["start"], sp["sweep"]
        # The centre readout's footprint. Any scale number landing inside it
        # is dropped: the first and last markings sit at the ends of the
        # sweep, which on a bottom-gap dial is exactly where the speed and its
        # unit go. Testing the actual position rather than hardcoding "skip 0
        # and 10" keeps it correct for any sweep a later spec uses.
        rx0, rx1 = cx - 30, cx + 30
        ry0, ry1 = cy + ir * 0.22, cy + ir * 0.92
        for i in range(steps + 1):
            f = i / float(steps)
            a = math.radians(start + sweep * f)
            nr = ir - sp["num_inset"]
            nx = cx + nr * math.cos(a)
            ny = cy - nr * math.sin(a)
            if rx0 <= nx <= rx1 and ry0 <= ny <= ry1:
                continue
            c.create_text(nx, ny, text=str(int(round(f * 10))),
                          fill=TH.text if sp["bold_nums"] else TH.dim,
                          font=self.f_small if sp["bold_nums"] else self.f_tiny)

    # -- tyres ---------------------------------------------------------------
    def _dash_tyres(self, c, x, y, w, car, era):
        """Four corners: life as a bar, temperature as the fill colour.

        Wear and temperature are deliberately on the SAME tile. They are read
        together in practice — a cold tyre with life left and a cooked tyre
        with life left demand opposite responses — and splitting them into two
        widgets made the driver do the correlation.
        """
        lo, hi = _win_for(era, TYRE_WINDOW, TYRE_WINDOW_HISTORIC)
        c.create_text(x, y, text="TYRES", anchor="nw", fill=TH.dim,
                      font=self.f_tiny)
        c.create_text(x + w, y, text="%d-%d C" % (lo, hi), anchor="ne",
                      fill=shade(TH.dim, 0.8), font=self.f_tiny)
        top = y + 12
        tw, th = 62, 30
        # A tight 2x2 that reads as ONE car. The first draft spread the
        # columns to the full panel width, which stopped looking like a set
        # of tyres and started looking like four unrelated gauges.
        gap_x = 26
        gx0 = x + (w - (2 * tw + gap_x)) / 2.0
        wear = car.tyre_wear or (None,) * 4
        temp = car.tyre_temp or (None,) * 4
        # rF2 wheel order is FL, FR, RL, RR — the same order this grid draws.
        for i in range(4):
            col_i, row_i = i % 2, i // 2
            tx = gx0 + col_i * (tw + gap_x)
            ty = top + row_i * (th + 4)
            t_c = temp[i]
            frac = temp_frac(t_c, lo, hi)
            fill = mix(shade(TH.panel, 0.5), heat_color(frac), 0.5)
            c.create_rectangle(tx, ty, tx + tw, ty + th, fill=fill,
                               outline=TH.border)
            wv = wear[i]
            if wv is not None:
                c.create_text(tx + 4, ty + 4, text="%d%%" % round(wv * 100),
                              anchor="nw", fill=TH.text, font=self.f_small)
                bw = int((tw - 6) * max(0.0, min(1.0, wv)))
                c.create_rectangle(tx + 3, ty + th - 6, tx + 3 + bw, ty + th - 3,
                                   fill=wear_color(wv), outline="")
            if t_c is not None:
                c.create_text(tx + tw - 4, ty + 5, text="%d" % round(t_c),
                              anchor="ne",
                              fill=TH.bad if (frac or 0) > 0.85 else TH.text,
                              font=self.f_tiny)
        # Brake temperatures live under the tyres rather than in their own
        # block: they are read in the same glance and only matter as "one
        # corner is way off the others".
        blo, bhi = _win_for(era, BRAKE_WINDOW)
        bt = car.brake_temp or (None,) * 4
        by = top + 2 * th + 4 + 2
        c.create_text(x, by + 5, text="BRK", anchor="w", fill=TH.dim,
                      font=self.f_tiny)
        seg_w = (w - 34) / 4.0
        for i in range(4):
            v = bt[i]
            f = temp_frac(v, blo, bhi)
            sx = x + 30 + i * seg_w
            c.create_rectangle(sx, by, sx + seg_w - 3, by + 11,
                               fill=mix(shade(TH.panel, 0.5), heat_color(f), 0.6),
                               outline=TH.border)
            if v is not None:
                c.create_text(sx + (seg_w - 3) / 2, by + 5,
                              text="%d" % round(v), fill=TH.text,
                              font=self.f_tiny)
        return 12 + 2 * th + 4 + 2 + 14

    # -- fuel -----------------------------------------------------------------
    def _dash_fuel(self, c, x, y, w, car, era, s):
        """Litres, burn rate and how many laps that actually buys.

        The laps-remaining figure is the one that matters, and it is only
        honest once a couple of laps have been measured — until then it says
        so rather than printing a confident guess.
        """
        label = "FUEL" if not era.has("fuelration") else "FUEL ALLOWANCE"
        cap = car.fuel_cap or 0.0
        fuel = car.fuel or 0.0
        frac = (fuel / cap) if cap else 0.0

        # Burn stats share the LABEL row, not the bar. Drawing them over the
        # bar meant the text sat on top of the fill and its outline, which is
        # the single worst legibility offence on the whole cluster.
        per = self.fuel_model.per_lap
        if per:
            left = self.fuel_model.laps_left(fuel)
            txt = "%.2f L/lap  %.1f laps" % (per, left or 0.0)
            need = s.laps_left if s and s.laps_left else None
            margin = self.fuel_model.enough_for(fuel, need)
            fg = TH.dim
            if margin is not None:
                fg = TH.good if margin > 0.5 else TH.bad
                txt += "  %+.1fL" % margin
        else:
            txt = "measuring burn..."
            fg = TH.dim

        # THREE rows, not two. The burn stats and the litres figure were both
        # right-aligned — the stats on the label row, the litres on the bar —
        # and at narrow widths "measuring burn..." ran straight through
        # "40.4 L". Giving the stats their own row below the bar removes the
        # collision entirely instead of hoping the strings stay short.
        c.create_text(x, y, text=label, anchor="nw", fill=TH.dim,
                      font=self.f_tiny)
        c.create_text(x + w, y, text="%.1f L" % fuel, anchor="ne",
                      fill=TH.text, font=self.f_small)

        by = y + UI(15)
        bh = UI(12)
        c.create_rectangle(x, by, x + w, by + bh, fill=shade(TH.panel, 0.6),
                           outline=TH.border)
        col = TH.good if frac > 0.35 else (TH.warn if frac > 0.15 else TH.bad)
        if frac > 0:
            c.create_rectangle(x + 1, by + 1, x + 1 + (w - 2) * min(1.0, frac),
                               by + bh - 1, fill=col, outline="")
        c.create_text(x, by + bh + UI(9), text=txt, anchor="w", fill=fg,
                      font=self.f_tiny)
        return UI(15) + bh + UI(16)

    # -- damage ---------------------------------------------------------------
    def _dash_damage(self, c, x, y, w, car, era):
        """A car plan view with the eight rF2 dent zones shaded by severity.

        Laid out as a COLUMN — label, car, status underneath — so it fits
        between the round gauge and the stacked numbers. A silhouette rather
        than a list, because damage is a spatial fact: "front left" reads
        instantly as a picture and needs parsing as text.
        """
        c.create_text(x, y, text="DAMAGE", anchor="nw", fill=TH.dim,
                      font=self.f_tiny)
        dents = list(car.damage or (0,) * 8)
        if len(dents) < 8:
            dents += [0] * (8 - len(dents))

        bw, bh = UI(46), UI(74)
        bx = x + (w - bw) / 2.0
        by = y + UI(16)

        def sev_col(v):
            # An undamaged zone must still be VISIBLE — painting it a shade
            # off the panel colour made the car shape disappear entirely and
            # left only the damage legible, which says nothing about WHERE.
            if v <= 0:
                return shade(TH.panel, 1.9)
            if v == 1:
                return TH.warn
            return TH.bad

        t = UI(11)
        zones = [
            (bx + t, by, bw - 2 * t, t),                       # 0 nose
            (bx + bw - t, by, t, t * 2),                       # 1 front right
            (bx + bw - t, by + t * 2, t, bh - 4 * t),          # 2 right
            (bx + bw - t, by + bh - t * 2, t, t * 2),          # 3 rear right
            (bx + t, by + bh - t, bw - 2 * t, t),              # 4 tail
            (bx, by + bh - t * 2, t, t * 2),                   # 5 rear left
            (bx, by + t * 2, t, bh - 4 * t),                   # 6 left
            (bx, by, t, t * 2),                                # 7 front left
        ]
        c.create_rectangle(bx + t, by + t, bx + bw - t, by + bh - t,
                           fill=shade(TH.panel, 1.25), outline=TH.border)
        # A chevron, not the word "FRONT" — the tub is too narrow for type
        # and the label clipped to "RON", which looked like a render fault.
        mx = bx + bw / 2.0
        c.create_polygon(mx, by + t + UI(6), mx - UI(6), by + t + UI(15),
                         mx + UI(6), by + t + UI(15),
                         fill=shade(TH.panel, 1.7), outline="")
        for i, (zx, zy, zw, zh) in enumerate(zones):
            c.create_rectangle(zx, zy, zx + zw, zy + zh, fill=sev_col(dents[i]),
                               outline=shade(TH.panel, 0.9))

        sy = by + bh + UI(8)
        worst = max(range(8), key=lambda i: dents[i])
        if dents[worst] > 0:
            n_hit = sum(1 for d in dents if d > 0)
            c.create_text(x + w / 2.0, sy, text=DAMAGE_ZONES[worst].upper(),
                          fill=sev_col(dents[worst]), font=self.f_small)
            c.create_text(x + w / 2.0, sy + UI(14),
                          text=("heavy" if dents[worst] > 1 else "light")
                          + (" x%d" % n_hit if n_hit > 1 else ""),
                          fill=sev_col(dents[worst]), font=self.f_tiny)
        else:
            c.create_text(x + w / 2.0, sy, text="CLEAN", fill=TH.good,
                          font=self.f_small)
        return UI(16) + bh + UI(30)


# --------------------------------------------------------------------------
# standalone preview
#
# Renders every era's cluster side by side with synthetic data, so the dash
# can be designed and checked without launching rFactor 2 and without waiting
# for a session that happens to have damage or worn tyres in it.
# --------------------------------------------------------------------------
class _Fake(object):
    pass


def preview_car(seed):
    """A synthetic car for the dash preview. Shared with `dashshot.py` so the
    live window and the captured PNG are showing the same instrument."""
    c = _Fake()
    c.speed = 180 + seed * 17
    c.rpm = 9000 + seed * 400
    c.max_rpm = 13000
    c.gear = 4 + (seed % 3)
    c.fuel = 42.0 - seed * 3
    c.fuel_cap = 100.0
    c.battery = 0.62
    c.flap = seed % 2
    c.laps = 12
    c.tyre_wear = (0.92 - seed * .07, 0.88 - seed * .07,
                   0.71 - seed * .06, 0.66 - seed * .06)
    c.tyre_temp = (88 + seed * 6, 95 + seed * 7, 104 + seed * 5, 112 + seed * 8)
    c.brake_temp = (420, 430, 380, 390)
    c.damage = (0, 1, 0, 0, 0, 0, 2, 1) if seed % 2 else (0,) * 8
    return c


PREVIEW_SAMPLES = [
    ("F1 Test 2025", "Max Verstappen"),
    ("Hypercar 2023", "WEC Driver"),
    ("GT3 2020", "GT Driver"),
    ("DTM 2020", "Tin-top Driver"),
    ("Formula 1 2008 Season", "Lewis Hamilton"),
    ("Formula 1 1992 Season by ASRC", "Nigel Mansell"),
    ("StockCar 2018 X Series", "Ted Moser"),
    ("", "March_M761_1976"),
    ("", "Brabham_1966"),
]


def _preview():
    import tkinter as tk
    import era as era_mod
    from overlay_panel import TCanvas

    fake_car = preview_car
    samples = PREVIEW_SAMPLES

    root = tk.Tk()
    root.title("FACTORtv dash preview")
    root.configure(bg="#05070a")
    cv = tk.Canvas(root, width=len(samples) * 290 + 20, height=430,
                   bg="#05070a", highlightthickness=0)
    cv.pack()

    class Host(DashMixin):
        def __init__(self):
            self.f_speed = ("Arial", 26, "bold")
            self.f_speed_sm = ("Arial", 14, "bold")
            self.f_gear = ("Arial", 22, "bold")
            self.f_gear_big = ("Arial", 38, "bold")
            self.f_small = ("Arial", 10, "bold")
            self.f_tiny = ("Arial", 8)
            self.fuel_model = FuelModel()
            self.fuel_model.laps = [2.4, 2.5, 2.45]

    host = Host()
    for i, (cls, nm) in enumerate(samples):
        e = era_mod.classify(cls, nm)
        TH.apply(era_mod.skin_for(e))
        car = fake_car(i)
        x = 10 + i * 290
        y = 40
        w, h = host._dash_size(e)
        tc = TCanvas(cv, 0, 0)
        cv.create_text(x + 4, 18, text="%s  (%s, %s)" % (e.label, e.year, TH.dial),
                       anchor="nw", fill="#8ba3b8", font=("Arial", 9, "bold"))
        host._dash_body(tc, x, y, w, h)
        cx, cy, iw = x + 12, y + 10, w - 24
        style = TH.dial
        if style == "analogue":
            used = host._dash_analogue(tc, cx, cy, iw, car, e, None)
        elif style == "hybrid":
            used = host._dash_hybrid(tc, cx, cy, iw, car, e, None)
        else:
            used = host._dash_digital(tc, cx, cy, iw, car, e, None)
        yy = cy + used + 8
        yy += host._dash_tyres(tc, cx, yy, iw, car, e) + 8
        yy += host._dash_fuel(tc, cx, yy, iw, car, e, None) + 8
        host._dash_damage(tc, cx, yy, iw, car, e)

    root.mainloop()


if __name__ == "__main__":
    _preview()
