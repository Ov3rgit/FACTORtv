"""Track knowledge: does the booth recognise the circuit and use it?"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import track as track_mod, era as era_mod, cast as cast_mod
from overlay_booth import BoothMixin

fails=[]
def check(c,l,e=""):
    print(("  [ OK ] " if c else "  [FAIL] ")+l+(("  "+e) if e else ""))
    if not c: fails.append(l)

print("\n1. NAME RESOLUTION (real rF2 track strings)")
CASES = [("Zandvoort 2021","zandvoort"),("Belgium","spa"),("ISI_Belgium_1966","spa"),
         ("SaoPaulo GP","interlagos"),("HockenheimRing GP","hockenheim"),
         ("LeMans91","lemans"),("Brianza_1966","monza"),("MonteCarlo_1966","monaco"),
         ("Malaysia_2007","sepang"),("Portugal_2009","portimao"),
         ("Kyalami 9 Hour","kyalami"),("3PA_Bathurst_2014","bathurst"),
         # These two used to be expected to resolve to NOTHING. They are
         # fictional rFactor 2 stock circuits, and the user has both
         # installed — so the booth read the folder name aloud, "TobanRP
         # 2016". They now resolve to an identity-only entry: a presentable
         # name and no lore whatsoever, which is a broadcast rather than a
         # file path.
         ("TobanRP_2016","toban"),("Lester 2.0","lester"),
         ("Some_Fictional_Circuit_2019",None)]
bad=[(r,e,track_mod.resolve(r)) for r,e in CASES if track_mod.resolve(r)!=e]
check(not bad, "%d/%d rF2 names resolve correctly" % (len(CASES)-len(bad),len(CASES)),
      str(bad[:3]))

print("\n2. UNKNOWN TRACK IS SILENT, NOT WRONG")
t = track_mod.Track("Some_Fictional_Circuit_2019")
check(not t.known, "unrecognised circuit reports known=False")
check(t.facts()==[] and t.character()=="", "and offers no facts to say")
check(t.name, "but still has a presentable name", repr(t.name))

print("\n3. KNOWLEDGE IS COMPLETE FOR EVERY CIRCUIT")
# Two kinds of entry live in tracks.json. A KNOWLEDGE entry must be complete —
# a circuit with a character line and no facts is a half-written circuit and
# that is what this test is for. An IDENTITY-ONLY entry exists so the booth
# can NAME the place and a season calendar can point at it; it carries no
# lore, the scene-setting and lore lines never fire for it, and demanding
# facts of it would only invite inventing some.
d = track_mod.load()
known = {s: v for s, v in d.items() if not v.get("identity_only")}
ident = {s: v for s, v in d.items() if v.get("identity_only")}
missing=[]
for slug,v in known.items():
    for field in ("name","country","character","facts","corners"):
        if not v.get(field): missing.append("%s.%s" % (slug,field))
check(not missing, "%d circuits all have name/country/character/facts/corners" % len(known),
      str(missing[:4]))
thin=[s for s,v in known.items() if len(v.get("facts",[]))<3]
check(not thin, "every circuit has 3+ facts", str(thin))
half=[s for s,v in ident.items() if v.get("facts") or v.get("character")]
check(not half, "%d identity-only circuits carry no half-written lore" % len(ident),
      str(half))
check(all(v.get("name") for v in ident.values()),
      "but every one of them can still be NAMED")
# A country is required only for identity-only circuits that are REAL. The
# fictional stock tracks have none, and inventing one would be inventing a
# fact about a place that does not exist.
noplace=[s for s,v in ident.items()
         if not v.get("fictional") and not v.get("country")]
check(not noplace, "and every real one still has a country", str(noplace))

print("\n4. CORNER LOOKUP BY LAP FRACTION")
spa = track_mod.Track("Belgium")
seq = [spa.corner(f) for f in (0.0,0.1,0.3,0.5,0.9)]
check(all(seq), "corner names resolve across the lap")
check(len(set(seq))>1, "and they differ around the lap", str(seq[:3]))
check(spa.corner(None)=="", "a missing fraction yields nothing, not a guess")

print("\n5. THE BOOTH USES IT")
class FakeTts:
    def __init__(s): s.said=[]; s.speaking=False
    def speak(s,t,who,intensity=0,build=False,name=""): s.said.append((who,t))
class Booth(BoothMixin):
    def __init__(s):
        s.booth_enabled=True; s.tts=FakeTts(); s.tracker=None; s.sting_bank=None
        s.booth_init()
    def _short_track(s,n): return n
    def _hide_panel(s,n): pass
class S:
    def __init__(s, raw):
        s.circuit=track_mod.Track(raw); s.track=raw
        s.era=era_mod.classify('F1 Test 2025','Max'); s.player_era=s.era
b=Booth()
import time
ok = b._track_line(S("Belgium"), time.time(), "character")
check(ok, "booth speaks the circuit's character", repr(b.tts.said[-1:]))
if b.tts.said:
    who,txt = b.tts.said[-1]
    check(who==cast_mod.ANALYST, "and it's the ANALYST who says it", who)
    check("Ardennes" in txt or "elevation" in txt or "committed" in txt,
          "with real Spa knowledge, not a generic line", txt[:60])
b2=Booth()
check(not b2._track_line(S("Some_Fictional_Circuit"), time.time(), "character"),
      "and says NOTHING about a circuit it doesn't know")

print("\n6. A HISTORIC LAYOUT IS A DIFFERENT ROAD, NOT A SHORTER ONE")
# The user has Spa 1966, Monza 1966, Monaco 1966, Silverstone 1991 and
# Longford 1967 installed. Every one of them was being told facts about a
# layout that did not exist yet — the modern Spa entry says the lap is "over
# seven kilometres, the longest on the calendar", and that aired over a 1966
# circuit which was fourteen kilometres of public road.
check(track_mod.Track("ISI_Belgium_1966").year==1966
      and track_mod.Track("Monza_2021").year==2021,
      "the layout year is read from the rF2 folder name")
# TWO WAYS A LAYOUT CAN BE DATED WITHOUT A FOUR-DIGIT YEAR, and both were
# added only after the user CONFIRMED what the folders are. Guessing at these
# would be worse than leaving them undated.
check(track_mod.Track("T78_Hockenheimring").year == 1978,
      "a confirmed layout with an unparseable name is dated from LAYOUT_YEARS",
      str(track_mod.Track("T78_Hockenheimring").year))
check(track_mod.Track("Le Mans 91-96 Virtua_LM").year == 1991,
      "and a two-digit range takes its FIRST year",
      str(track_mod.Track("Le Mans 91-96 Virtua_LM").year))
check(track_mod.Track("CF1L_BAHRAJN").year is None,
      "while a name with no year at all still yields None, not a guess",
      str(track_mod.Track("CF1L_BAHRAJN").year))
# The forest layout must now actually SEE the facts written for it — it was
# getting three generic lines because nothing could date it.
_h = track_mod.Track("T78_Hockenheimring")
check(any("forest" in f for f in _h.facts()),
      "so the 1978 Hockenheim is told about the forest circuit it is",
      str(len(_h.facts())) + " facts")
check(not any("Spitzkehre" in f for f in _h.facts()),
      "and not about the Spitzkehre, which was built in 2002")
check("the Ostkurve" in _h.corners(),
      "with the corners it actually had", str(_h.corners()[:3]))

leaks=[]
for raw, needle in (("ISI_Belgium_1966", "over seven kilometres"),
                    ("MonteCarlo_1966", "swimming pool")):
    for f in track_mod.Track(raw).facts():
        # the modern claim must be absent; a HISTORIC replacement is allowed
        # to mention the thing in order to say it does not exist yet
        if needle in f and "before" not in f.lower():
            leaks.append((raw, f[:60]))
check(not leaks, "no modern layout fact reaches a historic circuit", str(leaks))

# EACH HISTORIC LAYOUT HAS FACTS WRITTEN FOR IT — asked structurally, not by
# grepping the prose. The old version of this check looked for the literal
# words "1991 layout" in Silverstone's facts, and it broke the moment that
# fact was reworded to stop naming the year on air (§8). A test that fails
# when correct prose is edited is testing the wrong thing (LAW 20): what
# matters is that a fact exists whose year range CONTAINS this layout, which
# is what "written for it" actually means.
def _dated_for(raw):
    t = track_mod.Track(raw)
    d = track_mod.load().get(t.slug or "", {})
    return [f for f in d.get("facts", ())
            if isinstance(f, dict) and f.get("year")
            and f["year"][0] <= (t.year or 0) <= f["year"][1]]
HIST = ["ISI_Belgium_1966", "Brianza_1966", "MonteCarlo_1966",
        "Silverstone_1991", "Zandvoort_2017", "Melbourne_BySephiAt"]
missing = [raw for raw in HIST if not _dated_for(raw)]
check(not missing, "and each historic layout has facts written for it",
      str(missing))
check(any("seven kilometres" in f for f in track_mod.Track("Spa_2020").facts()),
      "while the modern circuit keeps the facts that are true of it")

# THE CORNER LIST IS PART OF THE LAYOUT TOO, and this was missed on the first
# pass. Silverstone's default list holds Village, the Loop, Aintree and the
# Wellington Straight — the Arena section, built in 2010 — and `corner()` was
# naming them during a 1991 race.
MODERN_ONLY = [("Silverstone_1991", ("Village", "the Loop", "Aintree",
                                     "the Wellington straight")),
               ("MonteCarlo_1966", ("the swimming pool", "Rascasse")),
               ("Brianza_1966", ("the first chicane", "Variante"))]
anach = []
for raw, bad in MODERN_ONLY:
    got = track_mod.Track(raw).corners()
    anach += [(raw, c) for c in bad if c in got]
check(not anach, "and a historic layout never names a corner built later",
      str(anach))
check("Copse" in track_mod.Track("Silverstone_1991").corners()
      and "Woodcote" in track_mod.Track("Silverstone_1991").corners(),
      "the 1991 lap has the corners it actually had")
check("Village" in track_mod.Track("Silverstone_2016").corners(),
      "while the modern lap keeps the Arena section")
check(track_mod.Track("Silverstone_1991").corner(0.2)
      != track_mod.Track("Silverstone_2016").corner(0.2),
      "so the same lap fraction names a different corner on each layout",
      "%s vs %s" % (track_mod.Track("Silverstone_1991").corner(0.2),
                    track_mod.Track("Silverstone_2016").corner(0.2)))

print("\n6b. NO CIRCUIT SAYS THE SAME THING TWICE")
# 34 near-duplicate pairs were created by adding facts on top of the existing
# ones without checking. `_facts_said` stops a fact repeating in a session; it
# cannot stop two DIFFERENT facts that say the same thing.
import difflib
def _span(f):
    """The years a fact is offered in. Undated means always."""
    if isinstance(f, str):
        return (0, 9999)
    y = f.get("year")
    return (y[0], y[1]) if y else (0, 9999)

def _overlap(a, b):
    return a[0] <= b[1] and b[0] <= a[1]

dupes = []
for slug, v in d.items():
    if not isinstance(v, dict):
        continue
    fs = v.get("facts", [])
    for i, fa in enumerate(fs):
        for fb in fs[i + 1:]:
            # ONLY FACTS A SINGLE LAYOUT COULD HEAR TOGETHER. Spa holds two
            # lines about the old fourteen-kilometre circuit — one in the
            # present tense for the 1966 layout and one as history for the
            # modern one — and they are gated to eras that cannot overlap.
            # Comparing raw text called those a duplicate; no listener can
            # ever hear both.
            if not _overlap(_span(fa), _span(fb)):
                continue
            a = fa if isinstance(fa, str) else fa.get("t", "")
            b = fb if isinstance(fb, str) else fb.get("t", "")
            if difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() > 0.55:
                dupes.append((slug, a[:40], b[:40]))
check(not dupes, "no LAYOUT hears two facts that say the same thing",
      str(dupes[:2]))

# ...and the historic layouts must not CONTRADICT themselves either, which is
# a different failure: two facts that are each fine and cannot both be true.
CONTRADICTIONS = [
    ("MonteCarlo_1966", "no run-off. A mistake is a barrier",
     "no barriers worth the name"),
    ("Brianza_1966", "crumbling", "still standing and still used"),
]
clash = []
for raw, a, b in CONTRADICTIONS:
    fs = track_mod.Track(raw).facts()
    if any(a in f for f in fs) and any(b in f for f in fs):
        clash.append(raw)
check(not clash, "and no historic layout contradicts itself", str(clash))

print("\n7. EVERY CIRCUIT THE USER OWNS RESOLVES TO SOMETHING")
_loc = os.path.join("D:", os.sep, "SteamLibrary", "steamapps", "common",
                    "rFactor 2", "Installed", "Locations")
if os.path.isdir(_loc):
    names = sorted(os.listdir(_loc))
    unk = [n for n in names if not track_mod.Track(n).known]
    check(not unk, "%d installed circuits, none unresolved" % len(names),
          str(unk[:4]))
    lore = [n for n in names if track_mod.Track(n).facts()]
    check(len(lore) >= len(names) // 2,
          "and most of them have real knowledge behind them",
          "%d of %d" % (len(lore), len(names)))
else:
    print("  [skip] rFactor 2 not installed on this machine")

print("\n8. THE LAYOUT YEAR IS FOR KNOWING WHICH ROAD IT IS, NEVER FOR SAYING")
# The user's rule, in his words: "the commentators mustn't explicitly state
# the year of track ... the year must just be used to know whether it's a
# modern or classic track". Racing a 1988 championship on the 1991 Silverstone
# and hearing "this is the 1991 layout" tells the viewer he is driving a
# re-run of somebody else's season instead of his own.
#
# The year on the folder is production metadata. It decides which facts and
# which corner names are true; it is not part of the circuit's identity and
# has no business on air.
import re as _re

_YEAR = _re.compile(r"\b(?:19|20)\d{2}\b")

# A NAME may never carry one, whether we know the circuit or not.
_named = [(r, track_mod.Track(r).name) for r in
          ("Silverstone_1991", "Zandvoort_2017", "ISI_Belgium_1966",
           "Melbourne_BySephiAt", "Botniaring_2017", "Le Mans 91-96 Virtua_LM",
           "SomeUnknownMod_2019_GP")]
_bad = [(r, n) for r, n in _named if _YEAR.search(n or "")]
check(not _bad, "no circuit NAME contains a year, known or unknown", str(_bad))
check(track_mod.Track("SomeUnknownMod_2019_GP").name == "SomeUnknownMod GP",
      "and an unknown mod keeps its layout word while losing the year",
      track_mod.Track("SomeUnknownMod_2019_GP").name)

# A DATED FACT may never state a year inside its own span. That is precisely
# the layout it is describing, so naming it is naming the layout year.
_said = []
for _slug, _d in track_mod.load().items():
    if not isinstance(_d, dict):
        continue
    for _f in _d.get("facts", ()):
        if isinstance(_f, str):
            continue
        _span, _t = _f.get("year"), _f.get("t", "")
        if not _span:
            continue
        for _y in _YEAR.findall(_t):
            if _span[0] <= int(_y) <= _span[1]:
                _said.append((_slug, _y, _t[:48]))
check(not _said, "no dated fact names a year from its own range", str(_said[:3]))

# And the end-to-end version, over the circuits the user actually owns: put
# each layout on air and check nothing it can say contains its own year.
if os.path.isdir(_loc):
    _leak = []
    for _r in sorted(os.listdir(_loc)):
        _t = track_mod.Track(_r)
        if not _t.year:
            continue
        _all = (_t.facts() + [_t.name, _t.character(), _t.overtaking()]
                + [_t.sector(i) for i in (1, 2, 3)] + list(_t.corners()))
        for _x in _all:
            if str(_t.year) in (_x or ""):
                _leak.append((_r, _x[:44]))
    check(not _leak, "and no installed layout can say its own year aloud",
          str(_leak[:3]))

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
