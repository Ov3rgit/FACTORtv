# -*- coding: utf-8 -*-
"""
FACTORtv — where does a frame actually go?

    python frametime.py             360 frames, 16 cars, the default dash
    python frametime.py 600 24      600 frames, a 24-car field

The speedo lag has been "mitigated, never proven fixed" through two sessions,
and both mitigations were guesses at the gauge — the one panel that had ever
been benchmarked, and which measured 4.3ms with zero frames over the tick.
Shrinking the thing you already measured is how a bottleneck survives a fix.

So this times EVERY stage of the real `_tick_body`, on the real Overlay, over
a synthetic race — the same one `preview.py` drives. It reports mean, p95 and
worst per stage, the frames that blew the tick budget, and what the whole
frame cost against `UPDATE_MS`. A panel that is slow only occasionally is the
one that causes visible lag, so the tail matters more than the mean and both
are printed.

WHAT COUNTS AS LAG HERE. The overlay redraws every `UPDATE_MS` (50ms, 20Hz).
Tk is single-threaded, so any frame whose work exceeds that budget delays the
next one — and a speedo that updates late is exactly what "lag" looks like.
A mean well under budget with a fat tail still lags; that is why p95 and the
over-budget count are the headline numbers rather than the average.
"""
import sys
import time

import factor_tv
import preview
from overlay_common import UPDATE_MS

# The stages of `_tick_body`, in the order it calls them. Timed by wrapping
# the bound method on the instance, so this measures the real code path and
# stays correct if a stage grows a new panel inside it.
STAGES = ("draw_header", "draw_flags", "draw_tower", "draw_relative",
          "draw_dash", "draw_sectors", "draw_map", "draw_podium",
          "draw_career_prompt", "draw_menu_button", "draw_settings",
          "update_booth", "update_radio", "update_rivals", "release_cards",
          "draw_caption", "draw_radio", "_sweep_panels")


def _pct(xs, p):
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))]


def _report(title, rows, frames, budget):
    print("\n" + title)
    print("  %-20s %8s %8s %8s %8s  %s"
          % ("stage", "mean", "p95", "worst", "share", "over budget"))
    total = sum(sum(v) for v in rows.values()) / max(1, frames)
    for name in sorted(rows, key=lambda n: -sum(rows[n])):
        v = rows[name]
        if not v:
            continue
        mean = sum(v) / len(v)
        if mean < 0.01 and _pct(v, 0.99) < 0.5:
            continue                       # noise; not worth a line
        over = sum(1 for x in v if x > budget)
        print("  %-20s %7.2f%s %7.2f%s %7.2f%s %7.1f%%  %s"
              % (name, mean, "ms", _pct(v, 0.95), "ms", max(v), "ms",
                 100.0 * mean / max(0.001, total),
                 ("%d frames" % over) if over else "-"))
    return total


def main():
    frames = int(sys.argv[1]) if len(sys.argv) > 1 else 360
    cars = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    ov = factor_tv.Overlay()
    sess = preview.Session()
    if cars:
        # A bigger field is the case that was never benchmarked: the gauge
        # costs the same for 8 cars as for 32, but the tower, relative and
        # map all scale with the grid.
        sess.cars_list = sess.cars_list[:cars] if len(sess.cars_list) >= cars \
            else sess.cars_list
    # Audio off. A render blocks nothing here (tts is queued on its own
    # thread) but the point is to time DRAWING, and stings hitting the disk
    # mid-measurement is noise in someone else's units.
    ov.booth_enabled = False
    ov.radio_enabled = False
    ov.rival_enabled = False

    class _FakeTracker(object):
        plugin_present = True
        def update(self):
            return sess.update()
        def confirmed_places(self, s):
            return {c.id: c.place for c in s.order}
        def close(self):
            pass
    ov.tracker = _FakeTracker()
    ov._lock_to_game = lambda: False
    ov.menu_open = False

    rows = {n: [] for n in STAGES}

    def wrap(name):
        fn = getattr(ov, name)
        def timed(*a, **kw):
            t0 = time.perf_counter()
            try:
                return fn(*a, **kw)
            finally:
                rows[name].append((time.perf_counter() - t0) * 1000.0)
        return timed
    for n in STAGES:
        if hasattr(ov, n):
            setattr(ov, n, wrap(n))

    whole = []
    # A few warm-up frames first. The first frame builds every panel, loads
    # fonts and fills the gauge cache cold — real, but it happens once and
    # averaging it in hides the steady state that the user actually sits in.
    for _ in range(20):
        ov._tick_body()
        ov.root.update()
    for name in rows:
        rows[name] = []

    t_start = time.perf_counter()
    for _ in range(frames):
        t0 = time.perf_counter()
        ov._tick_body()
        # Tk does the actual painting in `update()`, and leaving it out is how
        # a benchmark reports a fast frame that looks slow on screen: the
        # canvas work is queued during the draw calls and PAID here.
        ov.root.update()
        whole.append((time.perf_counter() - t0) * 1000.0)
    wall = time.perf_counter() - t_start

    budget = float(UPDATE_MS)
    print("FACTORtv frame profile — %d frames, budget %.0fms (%.0fHz)"
          % (frames, budget, 1000.0 / budget))
    _report("PER STAGE", rows, frames, budget)

    over = [x for x in whole if x > budget]
    print("\nWHOLE FRAME")
    print("  mean %.2fms   p95 %.2fms   p99 %.2fms   worst %.2fms"
          % (sum(whole) / len(whole), _pct(whole, 0.95),
             _pct(whole, 0.99), max(whole)))
    print("  over budget: %d of %d frames (%.1f%%)"
          % (len(over), len(whole), 100.0 * len(over) / len(whole)))
    print("  sustained rate: %.1f fps (a full tick allows %.0f)"
          % (len(whole) / wall, 1000.0 / budget))
    print("\n  A frame over budget delays the next one — that IS the lag.")
    try:
        ov.root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main() or 0)
