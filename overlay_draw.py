# -*- coding: utf-8 -*-
"""
FACTORtv — broadcast panels.

The timing tower, header, relative panel, flags and status furniture. Every
method here is a mixin on the Overlay and draws into a `Panel` obtained from
`self._begin_panel(...)`, so each panel owns its own click-through window.

House style, so panels stay consistent as more are added:

  * Nothing is boxed unnecessarily. Panels get a body only where text needs
    to survive being drawn over bright scenery; the cyan spine on the left
    edge is the FACTORtv signature and carries the era accent.
  * Colour means one thing at a time. Gold = you, blue = leader, purple =
    session best, green = personal best. Anything else is white or dim.
  * Every number that can be missing has a dash, never a zero. A "0.000" gap
    reads as a real measurement; "--.---" reads as "not known yet", which is
    what it is for the first lap of every session.
"""
import cast as cast_mod
from cast import colour_of as cast_colour, name_of as cast_name
from overlay_common import (CONTROL_BTN, CONTROL_GAP, CONTROL_W, TH, EDGE,
                            MAX_ROWS, ROW_H, UI,
                            fmt_clock, fmt_lap, mix, shade, tyre_short,
                            tyre_color)
from rf2_session import fmt_gap

# Session index -> the label a broadcast would put on screen.
# Only the BOOTH is subtitled in the centre caption. The engineer and the
# drivers have their own radio cards on the right; putting them in both
# places at once was one of the things that made the screen feel confused.
CAPTIONED = (cast_mod.PLAY, cast_mod.HISTORIC_PLAY, cast_mod.ANALYST)

# How long a caption lingers after the audio stops, so a short call can be
# read rather than flashing past.
CAPTION_HOLD = 1.6

# The caption box. Narrow on purpose: it lives on the bottom edge beside the
# track map, and a wide band there would be back in the driver's eyeline —
# which is what it was doing across the middle of the screen.
CAPTION_W = 330

SESSION_LABEL = {
    "test": "TESTING", "practice": "PRACTICE", "quali": "QUALIFYING",
    "warmup": "WARM-UP", "race": "RACE", "unknown": "SESSION",
}


class DrawMixin(object):

    # -- primitives ---------------------------------------------------------
    def _body(self, c, x, y, w, h, spine=True, fill=None):
        """Standard panel body: dark slab, thin border, accent spine."""
        c.create_rectangle(x, y, x + w, y + h, fill=fill or TH.panel,
                           outline=TH.border, width=1)
        if spine:
            c.create_rectangle(x, y, x + 3, y + h, fill=TH.accent, outline="")

    def _row_bg(self, c, x, y, w, h, tint=None, alpha=0.5):
        c.create_rectangle(x, y, x + w, y + h,
                           fill=mix(TH.panel, tint, alpha) if tint
                           else shade(TH.panel, 1.18), outline="")

    def _label(self, c, x, y, text, fill=None, font=None, anchor="nw"):
        return c.create_text(x, y, text=text, anchor=anchor,
                             fill=fill or TH.dim, font=font or self.f_tiny)

    # -- header --------------------------------------------------------------
    def draw_header(self, s):
        """Everything on ONE line, in a bar sized to its content.

        The two-line version stacked the track over the session label and
        cramped both — at a glance you could not read either. A broadcast
        banner is a single strip: logo, circuit, series, session, lap. So the
        bar grows to fit rather than the text shrinking to fit the bar.
        """
        h = UI(44)
        pad = UI(14)
        gap = UI(18)

        trk = self._short_track(s.track).upper()
        series = (s.era.series.upper() if s.era and s.era.series else "")
        sess = SESSION_LABEL.get(s.kind, "SESSION")

        if s.max_laps:
            right = "LAP %d/%d" % (min(s.leader_laps + 1, s.max_laps),
                                   s.max_laps)
        elif s.time_left is not None:
            right = fmt_clock(s.time_left)
        else:
            right = ""

        # Segments laid out left to right, each measured so nothing collides.
        segs = [(trk, self.f_small, TH.text)]
        if series:
            segs.append((series, self.f_tiny, TH.dim))
        segs.append((sess, self.f_tiny, TH.dim))

        logo_w = getattr(self, "logo_w", 0) or UI(78)
        body_w = sum(self._text_w(t, f) for t, f, _ in segs)
        body_w += gap * len(segs)
        right_w = self._text_w(right, self.f_small) if right else 0
        w = pad + logo_w + gap + body_w + right_w + pad

        gx, gy, gw, gh = self.game_rect
        x, y = gx + (gw - w) / 2.0, gy + UI(8)
        p = self._begin_panel("header", x, y, w, h)
        c = p.canvas_at(x, y)
        self._body(c, x, y, w, h)

        mid = y + h / 2.0
        if getattr(self, "logo_img", None) is not None:
            c.create_image(x + pad + logo_w / 2.0, mid, image=self.logo_img)
        else:
            c.create_text(x + pad, mid, text="FACTORtv", anchor="w",
                          fill=TH.text, font=self.f_logo)

        tx = x + pad + logo_w + gap
        for i, (text, font, col) in enumerate(segs):
            c.create_text(tx, mid, text=text, anchor="w", fill=col, font=font)
            tx += self._text_w(text, font)
            if i < len(segs) - 1:
                # Thin separator, vertically centred — cheaper to read than a
                # middot and it does not compete with the type.
                c.create_line(tx + gap / 2, y + UI(12), tx + gap / 2,
                              y + h - UI(12), fill=shade(TH.border, 1.3))
            tx += gap

        if right:
            c.create_text(x + w - pad, mid, text=right, anchor="e",
                          fill=TH.text, font=self.f_small)

        if s.green and s.kind == "race":
            self._live_bug(c, x + w - pad, y + h + UI(6))

    def _live_bug(self, c, x, y):
        w, h = UI(46), UI(16)
        c.create_rectangle(x - w, y, x, y + h, fill=TH.bad, outline="")
        c.create_text(x - w / 2.0, y + h / 2.0, text="LIVE", fill="#ffffff",
                      font=self.f_tiny)

    def _font_obj(self, font):
        """A measuring Font, cached.

        `tkfont.Font(...)` is not free, and wrapping a radio card measures
        once per word per frame. Built fresh every call it turned text
        wrapping into the most expensive thing on the panel.
        """
        cache = getattr(self, "_font_cache", None)
        if cache is None:
            cache = self._font_cache = {}
        key = tuple(font) if isinstance(font, (list, tuple)) else str(font)
        f = cache.get(key)
        if f is None:
            import tkinter.font as tkfont
            f = cache[key] = tkfont.Font(root=self.root, font=font)
        return f

    def _text_w(self, text, font):
        """Measure a string, so panels can be sized from their content."""
        try:
            return self._font_obj(font).measure(text or "")
        except Exception:
            return int(len(text or "") * UI(7))

    def _wrap_px(self, text, px, font, max_lines=4):
        """Wrap to a PIXEL width, measuring the real font.

        The old `_wrap` counted CHARACTERS against a hardcoded column count,
        which is wrong twice over: the glyph widths depend on whichever font
        actually loaded, and the column count does not move with the UI
        scale. At 1.25x a 40-column radio line overflowed a 330px card and
        the ends of sentences were simply cut off the side.

        Overlong text is ELLIPSISED, never silently dropped. `_wrap` used to
        `return out[:3]`, so a line that needed a fourth row lost its last
        words with nothing on screen to say it had happened.
        """
        words = (text or "").split()
        if not words:
            return []
        px = max(px, UI(40))
        out, cur = [], ""
        for word in words:
            trial = (cur + " " + word).strip()
            if cur and self._text_w(trial, font) > px:
                out.append(cur)
                cur = word
            else:
                cur = trial
        if cur:
            out.append(cur)
        if max_lines and len(out) > max_lines:
            out = out[:max_lines]
            last = out[-1]
            while last and self._text_w(last + "...", font) > px:
                last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
            out[-1] = last + "..."
        return out

    # -- timing tower ---------------------------------------------------------
    def draw_tower(self, s):
        """The running order down the left edge.

        Shows interval to the car ahead by default — that is the number that
        tells you whether a pass is coming. Gap to leader is available but
        secondary; a tower of leader gaps hides every actual battle.
        """
        order = s.order
        if not order:
            return
        rows = order[:self.tower_rows]
        w = UI(250 if not s.multiclass else 268)
        head = UI(22)
        rh = UI(ROW_H)
        h = head + len(rows) * rh + UI(6)
        gx, gy, gw, gh = self.game_rect
        x, y = gx + UI(EDGE), gy + UI(78)
        p = self._begin_panel("tower", x, y, w, h)
        c = p.canvas_at(x, y)
        self._body(c, x, y, w, h)

        self._label(c, x + UI(10), y + UI(6), "POS")
        self._label(c, x + UI(52), y + UI(6), "DRIVER")
        self._label(c, x + w - UI(10), y + UI(6),
                    "INTERVAL" if self.tower_interval else "LEADER",
                    anchor="ne")

        ry = y + head
        for car in rows:
            self._tower_row(c, x, ry, w, car, s)
            ry += rh

    def _tower_row(self, c, x, y, w, car, s):
        me = car is s.player
        lead = car.place == 1
        rh = UI(ROW_H)
        mid = y + rh / 2.0 - 1

        if me:
            self._row_bg(c, x + 3, y, w - 3, rh - 1, TH.you, 0.30)
        elif lead:
            self._row_bg(c, x + 3, y, w - 3, rh - 1, TH.leader, 0.16)

        # Position block
        pos_col = TH.you if me else (TH.leader if lead else TH.text)
        c.create_rectangle(x + 3, y, x + UI(32), y + rh - 1,
                           fill=shade(TH.panel, 0.7), outline="")
        c.create_text(x + UI(18), mid, text=str(car.place),
                      fill=pos_col, font=self.f_small)

        # Places gained/lost since the grid — the cheapest way to show a
        # story developing without any extra panel.
        g = car.places_gained or 0
        if g:
            c.create_text(x + UI(42), mid,
                          text=("▲" if g > 0 else "▼"),
                          fill=TH.good if g > 0 else TH.bad, font=self.f_tiny)

        name = car.display_name or "?"
        c.create_text(x + UI(54), mid, text=name[:18], anchor="w",
                      fill=TH.text if not car.in_pits else TH.dim,
                      font=self.f_row)

        rx = x + w - UI(10)
        # Pit status replaces the gap: a car in the pit lane has no
        # meaningful interval, and showing a frozen one is a lie.
        if car.in_pits:
            c.create_text(rx, mid, text="PIT", anchor="e",
                          fill=TH.warn, font=self.f_row)
        elif car.place == 1:
            c.create_text(rx, mid, text="LEADER", anchor="e",
                          fill=TH.leader, font=self.f_tiny)
        else:
            gap = car.gap_ahead if self.tower_interval else car.gap_leader
            txt = fmt_gap(gap, car.laps_down if not self.tower_interval else 0)
            c.create_text(rx, mid, text=txt, anchor="e",
                          fill=TH.text, font=self.f_row)

        # Compound chip, only where the era actually has compound choice.
        if s.era and s.era.has("compounds") and car.tyre_front:
            short = tyre_short(car.tyre_front)
            if short:
                cxp = x + w - UI(78)
                r = UI(8)
                c.create_oval(cxp - r, mid - r, cxp + r, mid + r,
                              fill=shade(TH.panel, 0.6),
                              outline=tyre_color(car.tyre_front), width=2)
                c.create_text(cxp, mid, text=short,
                              fill=tyre_color(car.tyre_front), font=self.f_tiny)

        if car.purple_lap:
            c.create_rectangle(x + w - 4, y + 2, x + w - 1, y + rh - 3,
                               fill=TH.best, outline="")

    # -- relative -------------------------------------------------------------
    def draw_relative(self, s):
        """The cars immediately around you, by time on track.

        Distinct from the tower: in a race with lapped traffic the car
        physically behind you may be six positions up the order, and that is
        exactly the car about to affect your lap.
        """
        me = s.player
        if me is None or not s.order:
            return
        i = None
        for k, cc in enumerate(s.order):
            if cc is me:
                i = k
                break
        if i is None:
            return
        n = self.relative_rows
        lo, hi = max(0, i - n), min(len(s.order), i + n + 1)
        rows = s.order[lo:hi]
        if len(rows) < 2:
            return

        w = UI(230)
        head = UI(20)
        rh = UI(ROW_H)
        h = head + len(rows) * rh + UI(6)
        gx, gy, gw, gh = self.game_rect
        x, y = gx + gw - w - UI(EDGE), gy + UI(78)
        p = self._begin_panel("relative", x, y, w, h)
        c = p.canvas_at(x, y)
        self._body(c, x, y, w, h)
        self._label(c, x + UI(10), y + UI(5), "RELATIVE")
        self._label(c, x + w - UI(10), y + UI(5), "GAP", anchor="ne")

        ry = y + head
        for car in rows:
            mine = car is me
            mid = ry + rh / 2.0 - 1
            if mine:
                self._row_bg(c, x + 3, ry, w - 3, rh - 1, TH.you, 0.30)
            c.create_text(x + UI(12), mid, text=str(car.place),
                          anchor="w", fill=TH.you if mine else TH.dim,
                          font=self.f_tiny)
            c.create_text(x + UI(38), mid,
                          text=(car.display_name or "?")[:16], anchor="w",
                          fill=TH.text, font=self.f_row)
            if not mine:
                # Signed relative time: negative = ahead of you.
                d = self._relative_gap(s, me, car)
                c.create_text(x + w - UI(10), mid,
                              text=("%+.1f" % d) if d is not None else "--",
                              anchor="e",
                              fill=TH.good if (d or 0) > 0 else TH.warn,
                              font=self.f_row)
            ry += rh

    def _relative_gap(self, s, me, other):
        """Seconds between two cars on the road, signed.

        Uses the order's cumulative intervals rather than the raw distance so
        it agrees with the tower. Disagreeing numbers in two panels is worse
        than a slightly coarser one.
        """
        try:
            a = s.order.index(me)
            b = s.order.index(other)
        except ValueError:
            return None
        if a == b:
            return 0.0
        lo, hi = (a, b) if a < b else (b, a)
        total = 0.0
        for k in range(lo + 1, hi + 1):
            total += s.order[k].gap_ahead or 0.0
        return total if b < a else -total

    # -- flags ----------------------------------------------------------------
    def draw_flags(self, s):
        """Only ever shows a flag that is actually flying."""
        flags = []
        if s.full_course_yellow or s.yellow in (1, 2, 3, 4):
            flags.append(("FULL COURSE YELLOW", TH.warn, TH.panel))
        elif any(s.yellow_sectors):
            secs = [str(i + 1) for i, v in enumerate(s.yellow_sectors) if v]
            flags.append(("YELLOW  SECTOR %s" % "/".join(secs), TH.warn,
                          TH.panel))
        if s.player is not None and s.player.blue_flag:
            flags.append(("BLUE FLAG", TH.leader, "#ffffff"))
        if s.finished:
            flags.append(("CHEQUERED FLAG", "#ffffff", TH.panel))
        if not flags:
            self._hide_panel("flags")
            return

        w, rowh = 260, 26
        h = len(flags) * rowh
        gx, gy, gw, gh = self.game_rect
        x, y = gx + (gw - w) / 2.0, gy + 66
        p = self._begin_panel("flags", x, y, w, h)
        c = p.canvas_at(x, y)
        for i, (txt, bg, fg) in enumerate(flags):
            ry = y + i * rowh
            c.create_rectangle(x, ry, x + w, ry + rowh - 2, fill=bg, outline="")
            c.create_text(x + w / 2, ry + rowh / 2 - 1, text=txt, fill=fg,
                          font=self.f_small)

    # -- status / no-data -----------------------------------------------------
    def draw_status(self, s, plugin_ok):
        """The one panel that is allowed to appear when nothing else can.

        Its job is to answer "why is there no overlay?" without the user
        having to go and read a log — the failure modes here are all
        recoverable and all have a specific fix.
        """
        msg = sub = None
        if not plugin_ok:
            msg = "WAITING FOR rFACTOR 2"
            sub = "shared memory not found — is the game running?"
        elif s is None or not s.valid:
            msg = "NO SESSION DATA"
            sub = "load a session, a race or a replay"
        elif s.num_cars == 0:
            msg = "NO CARS ON TRACK"
            sub = "%s — waiting for the field" % (s.track or "")
        elif not getattr(s, "on_air", True):
            # Distinct from "no data": the game IS running and we can see the
            # session, it simply has not started yet. Saying so is more
            # useful than a generic wait message.
            msg = "STANDING BY"
            sub = "%s — waiting for the session to go live" % (
                s.circuit.name if getattr(s, "circuit", None) else s.track)
        if msg is None:
            # Cleared, not just hidden: the menu reads this, and a stale
            # "no cars on track" sitting on the settings page while a race is
            # running is worse than the card ever was.
            self._status_msg = None
            self._hide_panel("status")
            return False

        # A COLOURED SQUARE IN THE CONTROL STRIP, NOT A CARD.
        #
        # The user: "the NO CARS ON TRACK card looks crazy out of place, maybe
        # it can just be like a colour coded square dot next to the email
        # icon". He is right — it is a 330px slab that appears over the game
        # (and over the desktop, before the game is up) to say something that
        # is true for a few seconds and needs no reading.
        #
        # BUT ITS JOB SURVIVES. This panel exists to answer "why is there no
        # overlay?" without anybody opening a log, and a bare dot cannot say
        # "shared memory not found — is the game running?". So the words move
        # into the menu (see `_rows_main`), where there is room for them and
        # where somebody looking for an explanation will actually go.
        self._status_msg = (msg, sub)
        col = {
            # Nothing we can do until the game is up: the only state that is
            # arguably a fault rather than a wait.
            "WAITING FOR rFACTOR 2": TH.bad,
            "NO SESSION DATA": TH.warn,
            "NO CARS ON TRACK": TH.dim,
            "STANDING BY": TH.good,
        }.get(msg, TH.dim)

        sz = UI(CONTROL_BTN)
        gx, gy, gw, gh = self.game_rect
        # THIRD IN THE ROW, after the hamburger and the envelope, and inside
        # the SAME shared strip they measure from — so the next control added
        # to that corner moves this one instead of landing on top of it. That
        # collision has already happened once here.
        x = gx + UI(EDGE) + (sz + UI(CONTROL_GAP)) * 2
        y = gy + UI(EDGE)
        p = self._begin_panel("status", x, y, sz, sz)
        c = p.canvas_at(x, y)
        c.create_rectangle(x, y, x + sz, y + sz, fill=TH.panel,
                           outline=shade(TH.border, 1.1))
        m = UI(8)
        c.create_rectangle(x + m, y + m, x + sz - m, y + sz - m,
                           fill=col, outline="")
        return True

    # -- caption (lower third) --------------------------------------------------
    def draw_caption(self, now):
        """What the booth is saying, subtitled.

        Named and colour-coded per speaker, because with two voices the
        viewer otherwise has to work out who is talking from the accent
        alone — and the whole point of the cast is that they are distinct
        people with different jobs.
        """
        # THE CAPTION IS DRIVEN ONLY BY WHAT IS AUDIBLE, AND ONLY BY THE BOOTH.
        #
        # Two bugs lived here. First, the caption was set when a line was
        # QUEUED — seconds before anyone hears it, since a render takes 2-6s
        # and the booth queues a question and its answer together — so the
        # subtitles ran ahead of the voices.
        #
        # Then, when playback finished, the drawing fell back to that stale
        # queued caption, which was often an OLDER line still inside its
        # display window. The subtitle therefore jumped back to something
        # already said: the "repeating" captions. The fallback is gone.
        #
        # And the engineer is not the booth. Every persona passes through
        # `now_playing`, so keying the centre caption off it put Dean's radio
        # in the commentary subtitle as well as on his own card. Only the
        # booth seats are subtitled here.
        live = getattr(self.tts, "now_playing", None)
        if live and live[0] in CAPTIONED:
            who, text, _started = live
            self._cap_last = (text, who, now)
        elif live:
            # SOMETHING ELSE IS TALKING. The engineer is not captioned here —
            # he has his own card — but the hold below does not know that, so
            # it kept the booth's previous line on screen for the whole of
            # Dean's call. You heard one voice and read another: the caption
            # was out of sync with the audio by however long ago Miles last
            # spoke. Whoever is audible owns the screen, so if it is not a
            # booth seat, the booth caption goes away.
            self._hide_panel("caption")
            return
        else:
            # Hold the last line briefly after the audio stops, so a short
            # call is readable rather than flashing past.
            held = getattr(self, "_cap_last", None)
            if not held or now - held[2] > CAPTION_HOLD:
                self._hide_panel("caption")
                return
            text, who = held[0], held[1]
        p = cast_colour(who)
        name = cast_name(who)

        # A BOX ON THE BOTTOM EDGE, BESIDE THE TRACK MAP — not a full-width
        # band across the screen.
        #
        # The wide centred version was the last thing sitting in the driver's
        # eyeline: 720px of subtitle straight through the middle of the road,
        # and wide enough to reach the telemetry dash, which is why it kept
        # having to dodge it and why the cluster appeared to shift about. A
        # narrower box tucked against the bottom furniture is out of the way
        # and never has to move.
        #
        # Positioned from the ACTUAL rectangles the map and sector strip
        # published this frame, so it sits beside whatever is really there
        # and closes up when one of them is switched off.
        gx, gy, gw, gh = self.game_rect
        w = UI(CAPTION_W)
        lh = UI(19)
        # Measured against the real text area — the box is `w` wide but the
        # text starts UI(12) in and needs the same clearance on the right.
        lines_out = self._wrap_px(text, w - UI(24), self.f_row)
        h = UI(26) + len(lines_out) * lh

        left = gx + UI(EDGE)
        for rect in (getattr(self, "_map_rect", None),
                     getattr(self, "_sector_rect", None)):
            if rect:
                left = max(left, rect[0] + rect[2] + UI(10))
        x = left
        y = gy + gh - h - UI(EDGE)

        # Never encroach on the dash: if the gap between the bottom-left
        # furniture and the cluster is too narrow, sit above the dash instead
        # of overlapping it.
        dash = getattr(self, "_dash_rect", None)
        if dash and x + w > dash[0] - UI(8):
            x = min(x, max(gx + UI(EDGE), dash[0] - w - UI(8)))
        pan = self._begin_panel("caption", x, y, w, h)
        c = pan.canvas_at(x, y)
        self._body(c, x, y, w, h, spine=False)
        c.create_rectangle(x, y, x + 4, y + h, fill=p, outline="")
        c.create_text(x + UI(12), y + UI(13), text=name.upper(), anchor="w",
                      fill=p, font=self.f_tiny)
        ty = y + UI(30)
        for ln in lines_out:
            c.create_text(x + UI(12), ty, text=ln, anchor="w", fill=TH.text,
                          font=self.f_row)
            ty += lh

    def _caption_cols(self, w):
        """How many characters fit across the caption box.

        Measured rather than assumed: the box is sized in scaled pixels and
        the font is whatever loaded, so a hard-coded column count wraps
        badly at other UI scales.
        """
        avg = max(1.0, self._text_w("abcdefghijklmnopqrstuvwxyz",
                                    self.f_row) / 26.0)
        return max(16, int((w - UI(26)) / avg))

    @staticmethod
    def _wrap(text, width):
        words = (text or "").split()
        out, cur = [], ""
        for w in words:
            if len(cur) + len(w) + 1 > width:
                out.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            out.append(cur)
        return out[:3]

    # -- helpers --------------------------------------------------------------
    def _short_track(self, name):
        """Trim rF2's verbose layout names down to something broadcast-sized.

        rF2 reports e.g. "Zandvoort 2021" and "HockenheimRing GP"; the year
        and layout suffix are noise in a header that already says what
        session it is.
        """
        n = (name or "").strip()
        if not n:
            return "UNKNOWN"
        for suffix in (" GP", " Grand Prix", " Circuit", " International",
                       " Speedway", " DTM", " SHORT1", " Layout"):
            if n.endswith(suffix):
                n = n[:-len(suffix)]
        parts = n.split()
        if len(parts) > 1 and parts[-1].isdigit() and len(parts[-1]) == 4:
            parts = parts[:-1]
        return " ".join(parts) or n
