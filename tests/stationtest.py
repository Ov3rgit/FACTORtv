"""FACTORtv as a STATION: the ident, the other channel, and the old one.

Asked for directly: lines "like them saying things like 'FACTORtv airing the
2021 f1 season and you can also catch Brett on FACTORtv Classic'", plus
"easter eggs that nod to RacerTV ... their sister news station".

The content is easy; the constraints are the test. A station ident is the
lowest-value thing the booth can say — it competes with an actual race — and
the failure modes are all the ones this product has already paid for once:

  * a pool nothing calls (LAW 21)
  * a line that only parses next to another line (LAW 14)
  * three correct categories that all mean "the booth is talking about
    itself" airing back to back as a promo reel (LAW 15)
  * an archive broadcast stating a year (booth_archive.json, rule 3)
  * a man plugging a channel he is currently sitting on

    python tests/stationtest.py
"""
import os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import era as era_mod, cast as cast_mod, lines as lines_mod
import overlay_booth as ob
from fakes import FakeSession, Booth, grid

fails = []
def check(c, l, e=""):
    print(("  [ OK ] " if c else "  [FAIL] ") + l + (("  " + e) if e else ""))
    if not c:
        fails.append(l)

MODERN = era_mod.classify("F1 2021", "Max Verstappen")
CLASSIC = era_mod.classify("F1 1988 Historic Edition", "Ayrton Senna")

MAIN = ("broadcast", "broadcast_promo", "broadcast_racertv")
CLASSIC_CATS = ("broadcast_archive", "broadcast_promo_archive",
                "broadcast_racertv_archive")

print("\n1. EVERY POOL HAS LINES, AND SOMETHING CALLS IT")
# LAW 21. `booth_joke` sat in this product with five valid lines and no
# caller, and `lines.py` reported it healthy the whole time, because the
# lines WERE valid — they were simply unreachable. The only honest check is
# to grep the trigger source for the category name.
_src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "overlay_booth.py"), encoding="utf-8").read()
for cat in MAIN + CLASSIC_CATS:
    check(len(lines_mod.pool(cat)) >= 4,
          "%s has lines" % cat, "%d" % len(lines_mod.pool(cat)))
    check('"%s"' % cat in _src,
          "...and overlay_booth.py can actually emit it")

print("\n2. THE TWO CHANNELS ARE THE TWO SEATS")
# FACTORtv Classic is not an invention: `cast.set_era` puts Brett in the chair
# before 2000, so the archive channel is a description of what the product
# already does. Which means the split must follow the seat exactly.
cast_mod.set_era(MODERN)
check(not cast_mod.is_historic(), "a 2021 field is the main channel")
cast_mod.set_era(CLASSIC)
check(cast_mod.is_historic(), "a 1988 field is FACTORtv Classic")

# NOBODY PLUGS THE CHANNEL HE IS SITTING ON. Miles points at Classic, where
# Brett is; Brett points at the main channel, where Miles is.
_main_txt = " ".join(e["t"] for e in lines_mod.pool("broadcast_promo"))
_cls_txt = " ".join(e["t"] for e in lines_mod.pool("broadcast_promo_archive"))
check("Brett" in _main_txt and "Miles" not in _main_txt,
      "the main channel plugs Brett on Classic, and never Miles")
check("Miles" in _cls_txt and "Brett Calloway" not in _cls_txt,
      "and Classic plugs Miles on the main channel, never Brett himself")

print("\n3. AN ARCHIVE BROADCAST STATES NO YEAR")
# booth_archive.json rule 3, and the same rule the user restated for track
# layouts: "say 'this era', never 'the 1988 season'". A season year is his
# own championship's to announce, not the archive channel's.
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
for cat in CLASSIC_CATS:
    bad = [e["t"][:44] for e in lines_mod.candidates(cat, CLASSIC)
           if _YEAR.search(e["t"])]
    check(not bad, "%s never names a year" % cat, str(bad))

# The MODERN ident may name the season — that is the line the user asked for
# verbatim — but only where a year actually exists to name.
_series = [e for e in lines_mod.pool("broadcast") if "{series}" in e["t"]]
check(_series, "the main ident can name the championship",
      "%d lines" % len(_series))
_ungated = [e["t"][:40] for e in _series
            if "{series}" in e["t"] and not e.get("year")
            and "the {series} season" in e["t"]]
check(not _ungated,
      "and every 'the {series} season' line is gated to a dated era",
      str(_ungated))
# `_series_name` falls back to the word "field" when era.py cannot date the
# car, so an ungated season line would air "the field season".
check(all(e.get("year") for e in lines_mod.pool("broadcast")
          if "{series} season" in e["t"]),
      "which is what stops 'airing the field season' reaching air")

print("\n4. A LINE STANDS ALONE (LAW 14)")
# The bag can draw any line in a pool first, so a line written as a follow-up
# airs as an orphan about nothing. Two of the RacerTV lines were exactly that
# on the first draft — "taught me that line", "would have called that one" —
# and both read as replies to a line that never happened.
DEICTIC = re.compile(r"\b(that line|that one|then too|as well as that|"
                     r"like that one|the same way)\b", re.I)
orphan = []
for cat in MAIN + CLASSIC_CATS:
    for e in lines_mod.pool(cat):
        if DEICTIC.search(e["t"]):
            orphan.append((cat, e["t"][:46]))
check(not orphan, "no station line points at a line before it", str(orphan[:3]))

print("\n5. THE FAMILY GATE (LAW 15)")
# Three correct categories that all mean "the booth is talking about the
# broadcast instead of the race". `quali_standings` and `quali_top3` were both
# correct too, and aired back to back saying the same three names.
check(set(ob.STATION_CATS) == set(MAIN + CLASSIC_CATS),
      "every station category is in the family", str(ob.STATION_CATS))
check(ob.STATION_FAMILY_GAP >= 240,
      "and the family shares a gap of minutes, not seconds",
      "%.0fs" % ob.STATION_FAMILY_GAP)

def _flow_cats(b, s, now):
    return [c for c, _kw, _x in b._flow_filler(s, now, s.order[0],
                                               s.order[1], 1.2)]

# Back to the main channel. §2 left the cast on Classic, and the seat is
# global state — which is the point of it, but it means a test that changes
# the era has changed it for everything after.
cast_mod.set_era(MODERN)

b = Booth()
b._phase, b._length, b._field_size = "mid", "normal", 12
s = FakeSession(grid(), max_laps=40, leader_laps=20, laps_left=20)
now = time.time()
offered = _flow_cats(b, s, now)
check(any(c in MAIN for c in offered),
      "the station is offered on a quiet mid-race tick",
      str([c for c in offered if c in MAIN]))

# Now say one, and the whole family goes quiet — not just the one that aired.
b._cat_last["broadcast"] = now
after = _flow_cats(b, s, now + 30.0)
check(not any(c in ob.STATION_CATS for c in after),
      "and after ONE of them airs, none of the family is offered again",
      str([c for c in after if c in ob.STATION_CATS]))
later = _flow_cats(b, s, now + ob.STATION_FAMILY_GAP + 1)
check(any(c in MAIN for c in later),
      "until the family gap has passed", str([c for c in later if c in MAIN]))

print("\n6. IT LOSES TO THE RACE, ALWAYS")
# Continuity is the lowest-value thing in the product. An ident that can
# outrank an overtake is a station promo with a race behind it.
for cat in MAIN + CLASSIC_CATS:
    check(ob.PRIORITY.get(cat, 99) < ob.PRIORITY["overtake"],
          "%s ranks below an overtake" % cat,
          "%d vs %d" % (ob.PRIORITY.get(cat, 99), ob.PRIORITY["overtake"]))
check(ob.PRIORITY["broadcast_racertv"] < ob.PRIORITY["broadcast"],
      "and the easter egg is the lowest of the lot")
check(ob.COOLDOWNS["broadcast_racertv"] >= 1200,
      "the RacerTV nod is RARE — that is the whole value of an easter egg",
      "%.0fs" % ob.COOLDOWNS["broadcast_racertv"])

print("\n7. THE SISTER STATION IS A NOD, NOT A CROSSOVER")
_all_rtv = " ".join(e["t"] for c in ("broadcast_racertv",
                                     "broadcast_racertv_archive")
                    for e in lines_mod.pool(c))
check("RacerTV" in _all_rtv, "RacerTV is named")
# It is a real product with a real host game, and naming that would be the
# booth breaking the fourth wall rather than nodding through it.
for word in ("RaceRoom", "rFactor", "R3E", "sim", "game"):
    check(word.lower() not in _all_rtv.lower(),
          "and never mentions %s" % word)
# Both men came up through it, so both may nod to it. Chuck may not: he is
# the analyst, and the whole station family belongs to the PLAY seat.
for cat in MAIN + CLASSIC_CATS:
    check(cast_mod.who_says(cat) == cast_mod.PLAY,
          "%s belongs to the play-by-play seat" % cat,
          cast_mod.who_says(cat))

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
