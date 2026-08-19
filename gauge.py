# -*- coding: utf-8 -*-
"""
FACTORtv — the instrument face, rendered properly.

WHY THIS EXISTS
---------------
Tk's canvas has no antialiasing. None: every line, arc and oval it draws has
hard pixel edges, and a rev counter is almost entirely lines, arcs and ovals.
That is the whole reason the dash "looked like pixel art" — it was not a
palette problem or a layout problem, it is the renderer.

So the instrument is drawn with PIL at `SS` times the final size and then
downscaled with LANCZOS, which is real antialiasing, and handed to the canvas
as a single image. Text is left to Tk, whose font rendering is already
antialiased by the platform.

It also cuts the item churn. Every panel does `canvas.delete("all")` and
rebuilds from scratch at 20 Hz, and a ring gauge is ~46 of those items on its
own; here it is one `create_image`. Measured on the millennium gauge, the
whole dash went from 113 canvas items a frame to 55, and a cached gauge costs
0.001 ms against 1.06 ms of tk primitives.

The cache is what makes that true, and `BUCKETS` is what keeps it finite: the
image depends only on the REV FRACTION, quantised to 1/96th. A miss costs
12-28 ms depending on the style, so filling the cache spreads a second or so
across the opening laps and no single frame overruns the 50 ms tick. Measured
end to end, the whole dash is 3.0 ms a frame with a 28 ms worst case.

COLOUR
------
The old gauges were cyan because cyan is the BROADCAST theme colour, and the
dash simply inherited it. But the tower and the timing screen are graphics
laid over a race, whereas the cluster is meant to be an INSTRUMENT — a thing
that exists in the car. Real ones are not cyan. They are near-black faces
with white markings, amber and red warning zones, and on a modern F1 wheel a
green-red-violet shift ladder.

So the palettes here are deliberately independent of `TH`: changing the
broadcast skin must not repaint the rev counter.
"""
import math
import threading
import time

from overlay_common import CHROMA

# WHAT THE INSTRUMENT IS COMPOSITED ONTO.
#
# It used to be CHROMA and only CHROMA, because the dash floated on the
# chroma-keyed window and every pixel that was not the gauge was the game
# showing through. The moment the dash was put on a CARD that stopped being
# true: the gauge arrived as a near-black square on a navy slab and read, in
# the user's words, "like a sticker on a card".
#
# So the ground is settable, and it is part of the CACHE KEY — the same
# picture on two different backgrounds is two different sets of pixels, and a
# cache that ignored that would serve the old ground after an era change.
_BACKDROP = CHROMA


def set_backdrop(colour):
    """Composite onto this colour from now on.

    The cache is cleared rather than keyed-and-kept: a backdrop changes at
    most once per session (when the era theme does), and holding two full sets
    of ~97 images to save one refill is the wrong trade in a process that has
    already been tuned for memory.
    """
    global _BACKDROP
    if colour and colour != _BACKDROP:
        _BACKDROP = colour
        _photo_cache.clear()

try:
    from PIL import Image, ImageDraw, ImageTk
    HAVE_PIL = True
except ImportError:                     # pragma: no cover - PIL is a hard dep
    HAVE_PIL = False

# Supersample factor. Rendered side by side at 1/2/3/4, SS=1 is obviously
# stair-stepped and 2, 3 and 4 are indistinguishable at the sizes the dash
# actually draws — so 4 was costing twice the render time of 3 for no visible
# difference. 3 keeps a margin for the larger UI scales.
SS = 3
# Rev quantisation, and therefore the cache ceiling: at most BUCKETS+1 images
# per (style, size). 1/96th of the range is ~135 rpm on a 13,000 rpm engine,
# finer than the eye resolves on a 200px dial.
BUCKETS = 96

_photo_cache = {}

# What the last cache miss cost, in milliseconds. `prewarm` uses it to refuse
# to START a render that will not fit in its budget; see the comment there.
# Seeded high so the very first budgeted call is cautious rather than
# optimistic — the first render of a session is also the slowest.
_last_render_ms = 20.0

# Background prewarm state. `_pending` holds finished PIL images waiting to be
# turned into PhotoImages, which can only happen on the Tk thread.
_lock = threading.Lock()
_pending = {}
_worker = {}

# How many finished images may queue up. A cap matters because the worker is
# faster than the drain: without one it would render all 97 buckets into
# memory in a couple of seconds, holding ~97 full-size RGB images at once for
# no benefit over holding a handful.
PENDING_MAX = 8


def _rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _dim(col, f):
    c = _rgb(col) if isinstance(col, str) else col
    return tuple(int(round(v * f)) for v in c)


def _mix(a, b, t):
    a = _rgb(a) if isinstance(a, str) else a
    b = _rgb(b) if isinstance(b, str) else b
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# --------------------------------------------------------------------------
# palettes — one per gauge style, realistic to the instrument being imitated
#
# `lit` / `unlit` are the tacho markers. `zone` is the ordered shift ladder
# used by the LED strip and by any dial that lights its markers in stages.
# --------------------------------------------------------------------------
_BASE_COLORS = {
    "face": "#0b0c0e",          # matte black, not navy
    "face_edge": "#2a2f36",
    "bezel": "#3c434c",
    "lit": "#f2f5f8",
    "unlit": "#2b3138",
    "num": "#e8ecf0",
    "num_dim": "#8d97a3",
    "needle": "#e6e9ec",
    "hub": "#c8ced6",
    "red": "#e02020",
    "amber": "#f0a020",
    "green": "#35c94a",
    "violet": "#8b5cf6",
    "blue": "#2f7fe0",
    # The colour the whole face turns at the shift point. MUST differ from
    # `red`, the over-the-limiter colour: if the two match, the cue cannot
    # tell you the one thing it exists to tell you.
    #
    # Amber is the default and belongs to the OLD instruments — a warm glow
    # on a painted dial, where a green LED would be an anachronism. Modern
    # cars override it: green for most, violet for the F1 box and the GT3
    # display, whose real ladders end blue/violet.
    "shift": "#f0a020",
}


def _pal(**kw):
    d = dict(_BASE_COLORS)
    d.update(kw)
    return d


GAUGE_COLORS = {
    # A current F1 wheel: carbon black, and a shift ladder that runs
    # green -> red -> violet. This is the real sequence on a modern car, and
    # it is the reason the strip needs no numbers at all.
    "modern": _pal(shift="#8b5cf6", zone=("#35c94a", "#e02020", "#8b5cf6"),
                   face="#08090b", bezel="#4a525c"),

    # LMP / GT displays: the same idea, calmer, amber in the middle.
    "endurance": _pal(shift="#35c94a", zone=("#35c94a", "#f0a020", "#e02020"),
                      face="#0a0b0d", bezel="#454c55"),

    # WEC / Le Mans. The ladder runs green-amber-red rather than the F1
    # green-red-violet: an endurance car is asking you to hold a rev ceiling
    # for six hours, not to chase the last 200 rpm on a qualifying lap.
    "lmp": _pal(shift="#35c94a", zone=("#35c94a", "#f0a020", "#e02020"),
                face="#0a0b0d", bezel="#4a525c"),

    # GT3: a Bosch display. White ring, black face, machined alloy bezel.
    "gt3": _pal(shift="#8b5cf6", lit="#f0f4f8", unlit="#2a3038", face="#0a0b0d",
                bezel="#98a2ad", amber="#f0a020", red="#e02020"),

    # DTM: white segments on carbon with a hard red block. The bezel is dark
    # anodised rather than bright alloy, which is most of what separates it
    # from the GT3 gauge at a glance.
    "dtm": _pal(shift="#35c94a", lit="#f4f6f8", unlit="#2e343c", face="#0b0c0e",
                bezel="#5a636d", red="#d81f1f"),

    # 2000s: a sporty round tacho. White ring on carbon inside a twin chrome
    # bezel, with a painted red arc. Amber lit markers made a 2005 car look
    # like a 1992 LED tacho, which is backwards.
    "millennium": _pal(shift="#35c94a", lit="#eef2f6", unlit="#2b3138", face="#0e0f12",
                       bezel="#7d8792", red="#d92626"),

    # Early 90s LED tachos were amber-orange, and the redline was a painted
    # block on the face rather than a colour change per segment.
    "nineties": _pal(lit="#ff9a1f", unlit="#3a2a14", face="#0e0f11",
                     bezel="#000000", red="#d81f1f"),

    # Turbo era: white printed scale, orange needle, red arc. The face is a
    # real dial, so the markings do NOT light up.
    "eighties": _pal(lit="#f0ece2", unlit="#6a6459", num="#f4f0e6",
                     needle="#ff7a1a", face="#131211", bezel="#6e6357",
                     red="#cc2222"),

    # A Smiths/Jaeger dial: matte black face, white numerals, chrome bezel,
    # a thin white needle. Nothing on it is coloured except the red arc.
    "seventies": _pal(lit="#efe9db", unlit="#645d50", num="#f2ecdd",
                      num_dim="#a89d88", needle="#f0eadc",
                      face="#141210", bezel="#8a8073", red="#c02a2a"),

    "classic": _pal(lit="#ece4d2", unlit="#5d574a", num="#f0e8d6",
                    num_dim="#a3987f", needle="#e8e0cc", face="#15130f",
                    bezel="#93887a", red="#b03030"),

    "vintage": _pal(lit="#e6ddc9", unlit="#575145", num="#eae1cd",
                    num_dim="#9c9179", needle="#e0d7c2", face="#141210",
                    bezel="#8d8274", red="#a83030"),

    # A Cup car tach: big white numerals, heavy machined bezel, red needle.
    "stock": _pal(shift="#35c94a", lit="#f4f6f8", unlit="#333a42", num="#ffffff",
                  needle="#e02020", face="#0d0e10", bezel="#8f98a3",
                  red="#e02020"),
}


def colors_for(style):
    return GAUGE_COLORS.get(style, GAUGE_COLORS["modern"])


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def _ring_gauge(d, size, r, sp, pal, rev, redline):
    """The circular instrument, drawn at supersampled scale."""
    cx = cy = size / 2.0
    s = SS
    start, sweep = sp["start"], sp["sweep"]
    t_out = r
    t_in = r - sp["mark_len"] * s
    ir = t_in - sp["face_gap"] * s

    # bezel
    kind = sp["bezel"]
    br = r + sp["bezel_gap"] * s
    if kind == "hex":
        # A polygon's clearance is its INRADIUS, not the radius its vertices
        # sit on, so a hexagon on circumradius r has flats at r*cos(30) —
        # inside the ticks. Scale up so the flats clear the markers.
        hr = br / math.cos(math.radians(30))
        pts = [(cx + hr * math.cos(math.radians(90 + i * 60)),
                cy - hr * math.sin(math.radians(90 + i * 60))) for i in range(6)]
        d.polygon(pts, outline=_rgb(pal["bezel"]), width=int(2 * s))
    elif kind == "double":
        d.ellipse((cx - br, cy - br, cx + br, cy + br),
                  outline=_rgb(pal["bezel"]), width=int(1.5 * s))
        d.ellipse((cx - br - 4 * s, cy - br - 4 * s, cx + br + 4 * s, cy + br + 4 * s),
                  outline=_dim(pal["bezel"], 0.6), width=int(1.5 * s))
    elif kind == "heavy":
        d.ellipse((cx - br - 3 * s, cy - br - 3 * s, cx + br + 3 * s, cy + br + 3 * s),
                  fill=_dim(pal["bezel"], 0.30), outline=_rgb(pal["bezel"]),
                  width=int(3 * s))
    elif kind == "ring":
        d.ellipse((cx - br, cy - br, cx + br, cy + br),
                  outline=_rgb(pal["bezel"]), width=int(2 * s))

    # FACE, including the shift cue.
    #
    # Glancing at a 10px band on the rim while braking is not realistic; a
    # face that changes colour is visible without moving your eyes off the
    # road. But it is a SHIFT IN THE FACE COLOUR, not a wash over the top —
    # drawn as an opaque tint after the markers it swamped them, turning a
    # 1992 tacho into a featureless orange disc at exactly the revs you most
    # need to read it. Mixed into the face and drawn first, the markers stay
    # legible and the cue still reads instantly.
    face = pal["face"]
    edge = pal["face_edge"]
    # EVERY gauge gets the cue, including the needle dials. It was gated to
    # the digital-centre ones, which left the 1970s and 1960s cars — the two
    # with no rev ladder and the least to read at a glance — as the only
    # instruments without it.
    if sp["shift_from"] <= rev <= sp["shift_to"]:
        face, edge = _mix(face, pal["shift"], 0.26), pal["shift"]
    elif rev > sp["shift_to"]:
        face, edge = _mix(face, pal["red"], 0.26), pal["red"]
    if sp["face"]:
        d.ellipse((cx - ir, cy - ir, cx + ir, cy + ir),
                  fill=_rgb(face) if isinstance(face, str) else face,
                  outline=_rgb(edge) if isinstance(edge, str) else edge,
                  width=int((3 if edge is not pal["face_edge"] else 1.5) * s))

    # redline as a painted arc on the face
    if sp["redline_kind"] == "block":
        # PIL measures arc angles CLOCKWISE from 3 o'clock and always draws
        # start -> end in that direction; the specs are counter-clockwise, so
        # every angle negates AND the two ends swap. Getting only the negation
        # right drew the complement — a red band around five-sixths of the
        # dial instead of the top sixth.
        rr = t_out - sp["mark_len"] * s * 0.5
        a_red = -(start + sweep * redline)      # where the red zone begins
        a_end = -(start + sweep)                # ...and the end of the sweep
        d.arc((cx - rr, cy - rr, cx + rr, cy + rr),
              start=a_red, end=a_end,
              fill=_rgb(pal["red"]), width=int(max(3, sp["mark_len"] - 2) * s))

    n = sp["marks"]
    for i in range(n):
        f = i / float(n - 1)
        a = math.radians(start + sweep * f)
        ca, sa = math.cos(a), -math.sin(a)
        major = sp["major_every"] and (i % sp["major_every"] == 0)
        lit = f <= rev

        if sp["redline_kind"] == "ticks" and f >= redline:
            col = _rgb(pal["red"]) if lit else _dim(pal["red"], 0.28)
        elif sp["redline_kind"] == "ticks" and f >= redline - 0.12:
            col = _rgb(pal["amber"]) if lit else _dim(pal["amber"], 0.26)
        elif not sp["fills"]:
            col = _rgb(pal["num"]) if major else _rgb(pal["lit"])
        else:
            col = _rgb(pal["lit"]) if lit else _rgb(pal["unlit"])

        wdt = int((sp["mark_w"] + (1 if major else 0)) * s)
        ln_in = t_in + (0 if major else sp["minor_inset"] * s)
        if sp["kind"] == "dot":
            rr = wdt
            px, py = cx + t_in * ca, cy + t_in * sa
            d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=col)
        else:
            d.line((cx + ln_in * ca, cy + ln_in * sa,
                    cx + t_out * ca, cy + t_out * sa), fill=col, width=wdt)

    if sp["needle"]:
        a = math.radians(start + sweep * rev)
        nl = ir - 4 * s
        ncol = _rgb(pal["red"]) if rev >= redline else _rgb(pal["needle"])
        wdt = int((4 if sp["needle"] == "thick" else 2) * s)
        # A counterweight tail is what makes a needle read as mechanical
        # rather than as a line drawn from the middle.
        d.line((cx - nl * 0.22 * math.cos(a), cy + nl * 0.22 * math.sin(a),
                cx + nl * math.cos(a), cy - nl * math.sin(a)),
               fill=ncol, width=wdt)
        hub = (5 if sp["needle"] == "thick" else 4) * s
        d.ellipse((cx - hub, cy - hub, cx + hub, cy + hub), fill=_rgb(pal["hub"]))


def _strip_gauge(d, size, r, sp, pal, rev, redline):
    """A modern F1 shift LADDER, not a dial.

    A current Formula One wheel has no round tacho — it has a horizontal row
    of shift LEDs above a rectangular screen, and that is the single most
    recognisable thing about the object. Drawing it as a circle made the 2025
    car look like a road-car rev counter.

    The ladder is read left to right and lights in three colour groups:
    green while it is still pulling, red at the shift point, violet on the
    limiter. The groups are equal thirds, which is how the real ones are set
    up before a team tunes them per circuit.
    """
    s = SS
    n = sp.get("leds", 15)
    gap = sp.get("led_gap", 3) * s
    w = size - 2 * sp.get("strip_pad", 6) * s
    lw = (w - gap * (n - 1)) / float(n)
    lh = sp.get("led_h", 13) * s
    x0 = (size - w) / 2.0
    y0 = sp.get("strip_pad", 6) * s
    zone = pal["zone"]

    for i in range(n):
        f = (i + 1) / float(n)
        col = zone[min(len(zone) - 1, int(i * len(zone) / float(n)))]
        on = rev >= f - 1.0 / n
        x = x0 + i * (lw + gap)
        rad = int(lw * 0.28)
        box = (x, y0, x + lw, y0 + lh)
        if on:
            d.rounded_rectangle(box, radius=rad, fill=_rgb(col))
            # A soft halo: an LED at full brightness bleeds into its
            # surround, and without it the strip reads as flat paint.
            d.rounded_rectangle((box[0] - s, box[1] - s, box[2] + s, box[3] + s),
                                radius=rad + s, outline=_dim(col, 0.45),
                                width=s)
        else:
            d.rounded_rectangle(box, radius=rad, fill=_dim(col, 0.13),
                                outline=_dim(col, 0.28), width=max(1, s // 2))

    # THE WHOLE BOX CHANGES COLOUR, exactly as the round dials do.
    #
    # The user's own finding, and it is the right one: a 10px band on the rim
    # is not what you read while braking, but a panel that changes colour is
    # visible in the corner of your eye without looking at it at all. The
    # round gauges had this and the F1 strip did not, so the one car with the
    # most to gain from a shift cue was the one without it.
    face, edge = pal["face"], pal["face_edge"]
    if sp["shift_from"] <= rev <= sp["shift_to"]:
        face, edge = _mix(face, pal["shift"], 0.30), pal["shift"]
    elif rev > sp["shift_to"]:
        face, edge = _mix(face, pal["red"], 0.34), pal["red"]
    hot = edge is not pal["face_edge"]

    top = y0 + lh + sp.get("screen_gap", 7) * s
    d.rounded_rectangle((x0, top, x0 + w, size - s), radius=6 * s,
                        fill=_rgb(face) if isinstance(face, str) else face,
                        outline=_rgb(edge) if isinstance(edge, str) else edge,
                        width=int((3 if hot else 1.5) * s))


def render(style, spec, w, h, rev, redline):
    """The instrument as an RGBA image, antialiased by supersampling."""
    pal = colors_for(style)
    size = int(max(w, h))
    big = size * SS
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if spec.get("shape") == "strip":
        _strip_gauge(d, big, big / 2.0, spec, pal, rev, redline)
    else:
        r = (big / 2.0) - int(6 * SS)      # room for the bezel
        _ring_gauge(d, big, r, spec, pal, rev, redline)
    return im.resize((size, size), Image.LANCZOS)


def photo(style, spec, w, h, rev, redline):
    """A cached Tk PhotoImage of the instrument.

    Cached on the QUANTISED rev fraction, so a car sweeping through the range
    reuses images almost every frame once the bucket has been seen. The
    PhotoImage is held by the cache — a canvas image item does not own its
    image, and dropping the last reference blanks the gauge.

    THE IMAGE IS FLATTENED TO RGB, and that is not a detail. Handing Tk an
    RGBA image with varied alpha takes ~65ms per image on this machine,
    against 0.3ms for the same picture as RGB — a 200x difference, and at 97
    cache entries the RGBA version spends six seconds of visible stutter
    filling the cache. (A uniform-alpha RGBA is fast, which is what made this
    hard to spot: it only shows up on a real gauge.)

    THE GROUND IT IS COMPOSITED ONTO IS `_BACKDROP`, not always the key. When
    the dash floated, flattening onto CHROMA and letting the key do the
    masking gave the same result as an alpha channel. Now that the dash sits
    on a card, the same trick has to composite onto the CARD — otherwise the
    instrument arrives as a near-black square on a navy slab.

    It works in both cases for the same reason: the antialiased edge pixels
    blend toward the ground rather than toward some bright colour, so there is
    no fringe. On a light ground this trick would halo badly.
    """
    if not HAVE_PIL:
        return None
    b = int(round(max(0.0, min(1.0, rev)) * BUCKETS))
    key = (style, int(w), int(h), b, round(redline, 3))
    p = _photo_cache.get(key)
    if p is None:
        im = render(style, spec, w, h, b / float(BUCKETS), redline)
        flat = Image.new("RGB", im.size, _rgb(_BACKDROP))
        flat.paste(im, (0, 0), im)
        p = _photo_cache[key] = ImageTk.PhotoImage(flat)
    return p


def prewarm_async(style, spec, w, h, redline, convert_ms=3.0):
    """Fill the cache WITHOUT spending frame time on the rendering.

    This replaces the time-boxed synchronous `prewarm` on the live overlay,
    and it is a deliberate reversal of a decision recorded in this file. The
    old reasoning was: "the expensive half is `ImageTk.PhotoImage`, which must
    run on the Tk thread anyway, so a background thread buys nothing." That
    was TRUE, and then the RGB-flatten fix cut the conversion from ~65ms to
    ~0.3ms — which moved the whole cost into `render()`, and `render()` is
    pure PIL with no Tk in it. The balance changed; the conclusion did not
    follow it until whole-frame profiling made the leftover obvious.

    So: the worker renders PIL images, the Tk thread converts a few per frame
    at 0.3ms each. Two things this fixes that a budget could not —

      * A time-boxed sync prewarm cannot fit a 12-28ms render into any budget
        smaller than itself, so it either overran the tick or, once it was
        made to refuse, never filled the cache at all — and an unfilled cache
        just moves the same stall into `photo()` as a lazy miss. Measured: 12
        misses in 300 frames, up to 10.9ms each, on the "fixed" version.
      * The work now happens during the garage and the formation lap, where
        there are frames to spare and nobody is looking at the rev counter.

    PIL releases the GIL for the heavy resampling, so the worker genuinely
    overlaps with drawing rather than merely interleaving with it.
    """
    if not HAVE_PIL:
        return 0
    sig = (style, int(w), int(h), round(redline, 3))
    with _lock:
        if _worker.get("sig") != sig:
            # A new car, size or skin. The old queue describes an instrument
            # that is no longer on screen, so it is dropped rather than
            # finished — otherwise a mid-session era change spends the next
            # ten seconds rendering the PREVIOUS car's dial.
            _worker["sig"] = sig
            _worker["spec"] = spec
            _pending.clear()
            _worker["next"] = 0
        if not _worker.get("alive"):
            _worker["alive"] = True
            t = threading.Thread(target=_render_loop, name="gauge-prewarm",
                                 daemon=True)
            _worker["thread"] = t
            t.start()

    # Convert what the worker has ready. Bounded per frame because 97 images
    # arriving at once is 30ms even at 0.3ms each — the spike this exists to
    # remove, in a new place.
    done = 0
    deadline = time.perf_counter() + convert_ms / 1000.0
    while True:
        with _lock:
            if not _pending:
                break
            key, im = _pending.popitem()
        _photo_cache[key] = ImageTk.PhotoImage(im)
        done += 1
        if time.perf_counter() >= deadline:
            break
    return done


def _render_loop():
    """Worker: render every missing bucket for the CURRENT instrument.

    Sleeps rather than exits when there is nothing to do, so a change of car
    does not have to start a thread before it can start filling. Only ever
    touches PIL and plain dicts — no Tk call happens here, which is the whole
    reason this is allowed to be a thread at all.
    """
    while True:
        with _lock:
            sig, spec = _worker.get("sig"), _worker.get("spec")
            pending_full = len(_pending) >= PENDING_MAX
        if sig is None or pending_full:
            time.sleep(0.05)
            continue
        style, w, h, redline = sig
        made = False
        for b in range(BUCKETS + 1):
            key = (style, w, h, b, redline)
            with _lock:
                if _worker.get("sig") != sig:
                    break               # the instrument changed under us
                if key in _photo_cache or key in _pending:
                    continue
            im = render(style, spec, w, h, b / float(BUCKETS), redline)
            flat = Image.new("RGB", im.size, _rgb(_BACKDROP))
            flat.paste(im, (0, 0), im)
            with _lock:
                if _worker.get("sig") == sig:
                    _pending[key] = flat
            made = True
            break                       # one at a time; re-check the queue cap
        if not made:
            time.sleep(0.05)            # cache complete: idle until it isn't


def prewarm(style, spec, w, h, redline, budget_ms=6.0):
    """Render a few not-yet-cached rev buckets, ahead of being asked for them.

    THIS IS THE FIX FOR THE STUTTER. A cache HIT is 0.001 ms but a MISS is
    12-28 ms, and while you are accelerating every frame lands in a bucket
    you have never used — so the first laps miss almost every frame and the
    gauge visibly lurches. Filling the cache lazily meant paying for it at
    exactly the moment the driver was looking at it.

    Called every frame from `draw_dash` with a small budget, so the work is
    spread across many frames instead of arriving in one. The budget is a
    TIME, not a count of buckets: a count cannot know what a bucket costs,
    and "six per frame" turned out to be 72 ms on the strip gauge — an 83 ms
    frame, which is worse than the stutter it was meant to remove. Time-boxed
    it overruns by at most one render.

    Deliberately not a background thread. The expensive half used to be
    `ImageTk.PhotoImage`, which must run on the Tk thread anyway, and the
    RGB flatten already cut that to 0.3 ms — so there is nothing left worth
    the complexity of one.
    """
    if not HAVE_PIL:
        return 0
    deadline = time.perf_counter() + budget_ms / 1000.0
    done = 0
    global _last_render_ms
    for b in range(BUCKETS + 1):
        key = (style, int(w), int(h), b, round(redline, 3))
        if key in _photo_cache:
            continue
        # CHECK THE BUDGET BEFORE STARTING, NOT AFTER FINISHING.
        #
        # The deadline test used to sit at the bottom of the loop, so this
        # function overran by a WHOLE render every time it stopped — a 6ms
        # budget that routinely cost 6 + 20ms. Whole-frame profiling caught
        # it: `draw_dash` measured a 4ms mean against a 17ms p95 and a 21ms
        # worst, and that tail is the visible stutter while accelerating,
        # which is exactly when the cache is cold and this loop is busiest.
        #
        # A render costs what the last one cost — the buckets differ only in
        # where a needle points — so the previous timing is a good enough
        # estimate to refuse to start one that will not fit.
        t0 = time.perf_counter()
        if t0 + _last_render_ms / 1000.0 > deadline:
            break
        im = render(style, spec, w, h, b / float(BUCKETS), redline)
        flat = Image.new("RGB", im.size, _rgb(_BACKDROP))
        flat.paste(im, (0, 0), im)
        _photo_cache[key] = ImageTk.PhotoImage(flat)
        done += 1
        _last_render_ms = (time.perf_counter() - t0) * 1000.0
        if time.perf_counter() >= deadline:
            break
    return done


def clear_cache():
    """Drop every cached image. Called when the era (and so the palette and
    geometry) changes — otherwise the cache would serve the previous car's
    instrument at the new car's size."""
    _photo_cache.clear()
    # The worker's in-flight queue is part of the cache. Left behind, it would
    # deliver the OLD instrument's images into the new cache a frame or two
    # after the skin changed, which is the same bug wearing a hat.
    with _lock:
        _pending.clear()
        _worker["sig"] = None
