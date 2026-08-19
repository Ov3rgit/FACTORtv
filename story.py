# -*- coding: utf-8 -*-
"""
FACTORtv — the race story.

The booth could always report a POSITION. What it could not do was answer the
question a real broadcast asks all afternoon:

    "Chuck, how has Leclerc's race been?"

That question needs a driver's whole afternoon in one object — where he
started, where he has been, what happened to him, whether he is going
forwards or backwards and whether any of it was his own fault. The pieces
were all being tracked somewhere in the booth; nothing put them together, so
the booth had eight conversations in a fifty-two minute race and not one of
them was about a driver.

WHY THIS IS A MODULE AND NOT MORE BOOTH CODE
--------------------------------------------
Two very different consumers need exactly the same read:

  * the mid-race conversation, where Miles asks and Chuck answers;
  * the wrap, where the top three get their races described and Chuck picks
    the man who impressed him.

Written twice they would drift, and the wrap would end up disagreeing with
what the booth said twenty minutes earlier — which is the specific way a
broadcast stops sounding like one intelligence.

THE ONE RULE
------------
An `Arc` states only what was MEASURED. Every field is either a number the
booth counted or None, and `headline()` returns None when a driver's race has
no shape worth describing — which is most drivers, most of the time. A
generic "he has had a solid afternoon" about a man who finished exactly where
he started is the filler this module exists to avoid.
"""

# How many places count as a real move rather than the noise of a pit cycle.
BIG_MOVE = 5
MOVE = 2

# A driver who has been off this many times is having a scrappy afternoon,
# and it is fair to say so. Below it, an off is an incident, not a pattern.
SCRAPPY_OFFS = 2

# Places lost from a driver's best position that count as a slide rather than
# a bad moment.
SLIDE = 4


class Arc(object):
    """One driver's race so far, as measured.

    Nothing here is inferred from a position alone: `grid` is where he
    started, `best`/`worst` are places he actually HELD (see the booth's
    `ARC_CONFIRM_TICKS`), and `offs` counts excursions the detector confirmed.
    """

    __slots__ = ("car", "name", "grid", "place", "best", "worst", "offs",
                 "led", "quali", "passes", "lost_places", "in_pits",
                 "retired", "field")

    def __init__(self, car, grid=0, place=0, best=0, worst=0, offs=0, led=0,
                 quali=None, passes=0, lost_places=0, field=0):
        self.car = car
        self.name = getattr(car, "display_name", "") or getattr(car, "name", "")
        self.grid = grid or 0
        self.place = place or 0
        self.best = best or place or 0
        self.worst = worst or place or 0
        self.offs = offs
        self.led = led
        # Where he qualified, when the booth watched the session that decided
        # it. None means we did not see qualifying and must not pretend to
        # know how it went — the grid slot is a fact, the STORY of qualifying
        # is not.
        self.quali = quali
        self.passes = passes
        self.lost_places = lost_places
        self.in_pits = bool(getattr(car, "in_pits", False))
        self.retired = bool(getattr(car, "retired", False))
        self.field = field or 0

    # -- the shape of it ----------------------------------------------------
    @property
    def gained(self):
        """Places up on the grid. Negative means he has gone backwards."""
        if not self.grid or not self.place:
            return 0
        return self.grid - self.place

    @property
    def recovered(self):
        """Places clawed back from his worst point."""
        return max(0, self.worst - self.place)

    @property
    def slid(self):
        """Places dropped from his best point."""
        return max(0, self.place - self.best)

    @property
    def scrappy(self):
        return self.offs >= SCRAPPY_OFFS

    @property
    def clean(self):
        return self.offs == 0

    def headline(self):
        """The single truest thing about this driver's afternoon, or None.

        Returned as a category name so the caller can pick a pool. Ordered by
        how much it actually says: what happened to him beats where he is,
        and where he is beats the fact that he is still going.

        None is a real answer and the common one. A driver who started
        seventh, ran seventh and finished seventh has no story, and inventing
        one for him is exactly the padding this module refuses to do.
        """
        if self.retired:
            return "story_out"
        if self.led and self.place == 1:
            return "story_led"
        # A recovery from a genuinely bad moment is the best story on the
        # grid, and it beats simply having gained places — the shape is the
        # point, not the arithmetic.
        if self.recovered >= BIG_MOVE:
            return "story_recovery"
        if self.slid >= SLIDE and self.offs:
            return "story_undone"
        if self.slid >= SLIDE:
            return "story_slide"
        if self.gained >= BIG_MOVE:
            return "story_charge"
        if self.gained <= -BIG_MOVE:
            return "story_dropping"
        if self.scrappy:
            return "story_scrappy"
        if self.gained >= MOVE:
            return "story_progress"
        if self.gained <= -MOVE:
            return "story_losing"
        # Qualifying is the last thing worth reaching for, and only when it
        # was genuinely notable — it is the one part of the weekend the booth
        # would otherwise never mention again.
        if self.quali and self.quali.get("notable"):
            return "story_from_quali"
        if self.grid and self.place and self.grid == self.place and self.clean:
            return "story_holding"
        return None

    def __repr__(self):
        return "<Arc %s grid=%s now=%s best=%s worst=%s offs=%d led=%d>" % (
            self.name, self.grid, self.place, self.best, self.worst,
            self.offs, self.led)


def of(booth, s, car):
    """Build the Arc for one car from everything the booth has been counting.

    The booth is passed rather than its individual dictionaries so this can
    grow to read more of them without every caller changing.
    """
    st = (getattr(booth, "_story", None) or {}).get(getattr(car, "id", None))
    return Arc(
        car,
        grid=getattr(car, "started_place", 0),
        place=getattr(car, "place", 0),
        best=(st or {}).get("best", 0),
        worst=(st or {}).get("worst", 0),
        offs=(getattr(booth, "_off_count", None) or {}).get(
            getattr(car, "id", None), 0),
        led=(getattr(booth, "_led_laps", None) or {}).get(
            getattr(car, "id", None), 0),
        quali=(getattr(booth, "_quali_story", None) or {}).get(
            _key(getattr(car, "display_name", "")
                 or getattr(car, "name", ""))),
        field=getattr(s, "num_cars", 0) or len(getattr(s, "order", ()) or ()),
    )


def _key(name):
    """Driver names are the only handle that survives a session change — car
    ids do not. Folded so a mod's spacing cannot break the match."""
    return "".join((name or "").lower().split())


def field(booth, s, top=None):
    """Arcs for the running order, best story first.

    `top` limits how deep to look. The ordering is by how much each driver
    has to say rather than by position, because "who has had an interesting
    race" and "who is winning" are different questions and the booth already
    has a dozen ways to answer the second.
    """
    cars = list(getattr(s, "order", ()) or ())
    if top:
        cars = cars[:top]
    arcs = [of(booth, s, c) for c in cars]
    return sorted([a for a in arcs if a.headline()],
                  key=_interest, reverse=True)


def _interest(a):
    """How much this driver's race is worth talking about.

    Deliberately not the same as his position. A man in fourteenth who has
    climbed nine places and been off twice is a better story than the man in
    third who has been in third all afternoon — and the second man is already
    covered by every other category the booth has.
    """
    n = 0
    n += a.recovered * 3
    n += abs(a.gained) * 2
    n += a.slid * 2
    n += a.offs * 2
    if a.led:
        n += 4
    if a.quali and a.quali.get("notable"):
        n += 3
    # A slight bias to the front, because the viewer can see those cars.
    if a.place and a.place <= 6:
        n += 3
    return n


def quali_note(pos, field_n, late, improved):
    """What to remember about a driver's qualifying session.

    Stored at the end of qualifying and read back during the race, which is
    the only way the booth can ever refer to a session that has already
    ended. `notable` is the gate on saying anything at all: an ordinary
    qualifying session is not worth bringing up on lap forty.
    """
    pos = int(pos or 0)
    if not pos:
        return None
    note = {"pos": pos, "field": int(field_n or 0),
            "late": bool(late), "improved": int(improved or 0)}
    # Pole is always worth a mention. So is a lap that arrived at the death,
    # and so is a big jump up the order in the closing minutes — those are
    # the three things that make a qualifying session a story rather than a
    # result.
    note["notable"] = bool(pos == 1 or late or (improved or 0) >= 3)
    return note
