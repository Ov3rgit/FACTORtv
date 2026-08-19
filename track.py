# -*- coding: utf-8 -*-
"""
FACTORtv — track identity and knowledge.

Turns whatever rF2 calls the circuit into a canonical slug, so the booth can
look up what it knows about the actual place.

Why this needs a module rather than a dict
------------------------------------------
Track knowledge is about the REAL CIRCUIT, not the game — Eau Rouge is Eau
Rouge whether the mod is called "Belgium", "Spa-Francorchamps 2020" or
"ISI_Belgium_1966". That is what makes this content worth writing: it
survives every mod, every re-release and every sim.

But rF2 names are a mess, and each one breaks a different naive approach:

    "Belgium"                     no mention of Spa at all
    "SaoPaulo GP"                 the city, not the circuit's usual name
    "HockenheimRing GP"           run-together capitals, layout suffix
    "LeMans91"                    no separator, a year glued on
    "Brianza_1966"                the TOWN Monza sits in
    "MonteCarlo_1966"             fine, but the modern one is "Monaco"
    "Portugal 2009"               which Portuguese circuit?

So resolution is alias-first (explicit, unambiguous) then fuzzy, and anything
unresolved returns None — at which point the booth simply says nothing about
the track. A confident fact about the wrong circuit is far worse than silence.

LAYOUT VARIANTS deliberately collapse to the same slug. Hockenheim GP and
Hockenheim Short are the same place with the same history; only the corner
list would differ, and getting that subtly wrong is worse than being general.
"""
import json
import os
import re
import sys

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(_DIR, "lines_data", "tracks.json")

# Explicit aliases, checked first. Keyed on a normalised substring: if the
# cleaned track name CONTAINS the key, it resolves. Ordered longest-first at
# match time so "monte carlo" cannot be shadowed by "carlo".
ALIASES = {
    # rF2's name           canonical slug
    "belgium": "spa",
    "spa": "spa",
    "francorchamps": "spa",
    "monza": "monza",
    "brianza": "monza",             # the town Monza sits in
    "autodromo nazionale": "monza",
    "saopaulo": "interlagos",
    "sao paulo": "interlagos",
    "interlagos": "interlagos",
    "carlos pace": "interlagos",
    "hockenheim": "hockenheim",
    "zandvoort": "zandvoort",
    "lemans": "lemans",
    "le mans": "lemans",
    "sarthe": "lemans",
    "daytona": "daytona",
    "montecarlo": "monaco",
    "monte carlo": "monaco",
    "monaco": "monaco",
    "bathurst": "bathurst",
    "panorama": "bathurst",
    "mount panorama": "bathurst",
    "silverstone": "silverstone",
    "suzuka": "suzuka",
    "imola": "imola",
    "nurburg": "nurburgring",
    "nordschleife": "nordschleife",
    "indianapolis": "indianapolis",
    "brickyard": "indianapolis",
    "road america": "roadamerica",
    "elkhart": "roadamerica",
    "lime rock": "limerock",
    "limerock": "limerock",
    "portland": "portland",
    "sepang": "sepang",
    "malaysia": "sepang",
    "portimao": "portimao",
    "algarve": "portimao",
    "portugal": "portimao",
    "estoril": "estoril",
    "kyalami": "kyalami",
    "bahrain": "bahrain",
    "sakhir": "bahrain",
    "montreal": "montreal",
    "villeneuve": "montreal",
    "longford": "longford",
    # Circuits carried for IDENTITY ONLY. The booth can NAME these and a
    # season calendar can point at them, but tracks.json holds no lore for
    # them, so the scene-setting and lore lines simply never fire — which
    # is the same silence an entirely unknown circuit gets.
    "albert park": "albertpark",
    "melbourne": "albertpark",
    "jeddah": "jeddah",
    "corniche": "jeddah",
    "miami": "miami",
    "catalunya": "catalunya",
    "barcelona": "catalunya",
    "montmelo": "catalunya",
    "red bull ring": "redbullring",
    "spielberg": "redbullring",
    "a1ring": "redbullring",
    "osterreichring": "redbullring",
    "hungaroring": "hungaroring",
    "mogyorod": "hungaroring",
    "baku": "baku",
    "azerbaijan": "baku",
    "americas": "cota",
    "cota": "cota",
    "austin": "cota",
    "las vegas": "vegas",
    "losail": "losail",
    "lusail": "losail",
    "qatar": "losail",
    "sochi": "sochi",
    "istanbul": "istanbul",
    "paul ricard": "paulricard",
    "castellet": "paulricard",
    "magny": "magnycours",
    "mugello": "mugello",
    "misano": "misano",
    "vallelunga": "vallelunga",
    "adelaide": "adelaide",
    "phillip island": "phillipisland",
    "fuji": "fuji",
    "motegi": "motegi",
    "okayama": "okayama",
    "aida": "okayama",
    "shanghai": "shanghai",
    "yas": "yasmarina",
    "abu dhabi": "yasmarina",
    "singapore": "singapore",
    "marina bay": "singapore",
    "mexico": "mexico",
    "hermanos rodriguez": "mexico",
    "zolder": "zolder",
    "hockenheimring": "hockenheim",
    "salzburgring": "salzburgring",
    "anderstorp": "anderstorp",
    "kaenon": None,                 # fictional; explicitly unknown
    # THE REST OF WHAT THE USER ACTUALLY HAS INSTALLED. 27 of his 49
    # circuits resolved to nothing, so the booth read the folder name
    # aloud and said nothing else. The real ones get full entries; the
    # fictional rFactor 2 stock tracks get a NAME and nothing else,
    # because there is nothing true to say about a place that does not
    # exist — and a name alone still turns a file path into a broadcast.
    "atlanta motorsports": "atlanta",
    "sardian heights": "sardianheights",
    "sardianheights": "sardianheights",
    "mountain peak": "mountainpeak",
    "loch drummond": "lochdrummond",
    "mountainpeak": "mountainpeak",
    "lochdrummond": "lochdrummond",
    "apple valley": "applevalley",
    "jacksonville": "jacksonville",
    "mills metro": "millsmetro",
    "lost valley": "lostvalley",
    "south shore": "southshore",
    "applevalley": "applevalley",
    "eagle creek": "eaglecreek",
    "botniaring": "botniaring",
    "maastricht": "maastricht",
    "palm beach": "palmbeach",
    "millsmetro": "millsmetro",
    "lostvalley": "lostvalley",
    "tiger moth": "tigermoth",
    "eaglecreek": "eaglecreek",
    "atlantamp": "atlanta",
    "palmbeach": "palmbeach",
    "joesville": "joesville",
    "tigermoth": "tigermoth",
    "brookdale": "brookdale",
    "matsusaka": "matsusaka",
    "northside": "northside",
    "superkart": "quebeckart",
    "berlinfe": "berlinfe",
    "alabama": "alabama",
    "nolamp": "nola",
    "lester": "lester",
    "toban": "toban",
    # Five more that `_norm` mangles in ways the obvious alias misses:
    # "AtlantaMP_2014" splits to "atlanta mp"; "CF1L_BAHRAJN" misspells
    # Bahrain; the noise filter eats the "south" out of "South Shore" and the
    # "circuit" out of the Formula E test track. Aliases have to match what
    # `_norm` ACTUALLY produces, not what the folder is called.
    "atlanta mp": "atlanta",
    "bahrajn": "bahrain",
    "formula e test": "formulaetest",
    "super kart": "quebeckart",
    "shore": "southshore",
    "mores": "mores",
    "nola": "nola",
}

# Layout/decoration words stripped before matching.
_NOISE = re.compile(
    r"\b(gp|grand prix|circuit|international|raceway|speedway|national|club|"
    r"short|long|full|layout|classic|historic|endurance|oval|road course|"
    r"combined|chicane|no chicane|rallycross|east|west|north|south|"
    r"[0-9]{2,4}|v[0-9]|rev[a-z]?)\b", re.I)
_SEPS = re.compile(r"[_\-/.,()\[\]]+")

_data = None


def _norm(name):
    """Fold an rF2 track name into something matchable.

    Splits run-together capitals ("HockenheimRing" -> "hockenheim ring")
    before lowercasing, because rF2 mod authors camel-case constantly and a
    plain lower() would leave "hockenheimring" unmatched against the alias
    "hockenheim ring".
    """
    s = name or ""
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)      # HockenheimRing -> ...
    s = re.sub(r"(?<=[A-Za-z])(?=[0-9])", " ", s)   # LeMans91 -> LeMans 91
    s = _SEPS.sub(" ", s).lower()
    s = _NOISE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _slugify(raw):
    """A stable key for a circuit nobody has written an entry for. "" if empty.

    Deliberately NOT the same shape as a curated slug — it keeps the digits a
    curated slug drops, because for an unknown track the year in the folder name
    may be the only thing separating two layouts of the same place.
    """
    n = re.sub(r"[^a-z0-9]+", "_", (raw or "").lower()).strip("_")
    return n[:48]


def resolve(name):
    """rF2 track name -> canonical slug, or None if we do not recognise it.

    None is a valid, common answer and must stay cheap: the user can install
    any track ever made, and the booth's correct behaviour on an unknown
    circuit is to say nothing about it.
    """
    n = _norm(name)
    if not n:
        return None
    # Longest alias first, so "monte carlo" beats "carlo" and
    # "road america" beats "america".
    for key in sorted(ALIASES, key=len, reverse=True):
        if key in n:
            return ALIASES[key]
    # Fuzzy: a known slug appearing as a bare word.
    for slug in load():
        if re.search(r"\b%s\b" % re.escape(slug), n.replace(" ", "")):
            return slug
    return None


def load():
    global _data
    if _data is None:
        try:
            with open(DATA, "r", encoding="utf-8") as f:
                _data = json.load(f)
        except Exception:
            _data = {}
        _data.pop("_comment", None)
    return _data


_installed = None


def installed(force=False):
    """The set of circuit slugs actually INSTALLED in rF2.

    Read from `<game>/Installed/Locations`, which is one folder per track,
    and resolved through the same alias table live session names use — so
    "ISI_Belgium_1966" and "Silverstone_1991" both land on the slug a season
    calendar refers to.

    This exists because a calendar of circuits the user does not own is not a
    calendar. The shipped F1 2025 preset has 24 rounds; on the development
    machine only 8 of them are installed, and a "3-round season" built from
    the front of that list was Australia, China and Japan — none of which
    could be raced. A round you cannot run is a round that never happens, and
    it blocks the season behind it for ever.

    Returns an empty set if the game cannot be found, which callers must
    treat as "unknown", NOT as "you own nothing".
    """
    global _installed
    if _installed is not None and not force:
        return _installed
    _installed = set()
    try:
        import career as career_mod
        res = career_mod.find_results_dir()
        if not res:
            return _installed
        root = os.path.abspath(os.path.join(res, os.pardir, os.pardir,
                                            os.pardir))
        loc = os.path.join(root, "Installed", "Locations")
        for name in os.listdir(loc):
            slug = resolve(name)
            if slug:
                _installed.add(slug)
    except Exception:
        pass
    return _installed


_TRACK_YEAR = re.compile(r"(?:^|[^0-9])((?:19|20)\d{2})(?:[^0-9]|$)")
# A two-digit RANGE, which is how some mods date a layout that stood for
# several seasons: "Le Mans 91-96". The first year is the one to use — it is
# when that road came into being, and it is the conservative end.
_TRACK_RANGE = re.compile(r"(?:^|[^0-9])([0-9]{2})\s*-\s*([0-9]{2})(?:[^0-9]|$)")

# LAYOUTS WHOSE YEAR CANNOT BE PARSED AT ALL, confirmed by the user against
# his own install. Keyed on a normalised substring, like ALIASES.
#
# Guessing at these would be worse than leaving them undated — an undated
# layout gets the undated facts only, which is fewer facts and none of them
# wrong. So this table is only ever filled in from something CHECKED, never
# from a pattern that looks plausible.
LAYOUT_YEARS = {
    # "T78" is the 1978 forest circuit: two enormous straights into the
    # woods, the Ostkurve, and then the Motodrom. Without a year it was
    # getting the modern Spitzkehre facts filtered out (good) and the forest
    # facts filtered out too (not good) — three generic lines in total.
    #
    # Keyed on what `_norm` ACTUALLY produces, which is "t hockenheimring":
    # the noise filter strips any run of 2-4 digits, so the 78 is gone by the
    # time this table is consulted. Matching the folder name instead of the
    # normalised form is the mistake that made this table do nothing.
    "t hockenheimring": 1978,
    # Albert Park as shipped by Sephi: the layout .mas files inside it are
    # `layout2019GP` and `layout2019GT`, and the user confirmed it is the
    # 2019 road — which is the one BEFORE the 2021 reprofile, so it still has
    # the turn nine/ten chicane and the old narrow turn one. The folder name
    # carries no year at all, which is exactly what this table is for.
    #
    # Keyed on what `_norm` produces for "Melbourne_BySephiAt", which splits
    # the run-together capitals: "melbourne by sephi at". Keying it on the
    # folder name would silently match nothing, as the Hockenheim entry
    # already found out.
    "melbourne by sephi": 2019,
}


def _scrape_year(raw):
    """The layout year out of an rF2 content name, or None.

    "ISI_Belgium_1966" -> 1966. "Le Mans 91-96" -> 1991, the start of the
    range. Anything genuinely unparseable stays None, and an undated layout
    gets the undated facts only: fewer facts, none of them wrong.
    """
    n = _norm(raw)
    for key, yr in LAYOUT_YEARS.items():
        if key in n:
            return yr
    for m in _TRACK_YEAR.finditer(raw or ""):
        y = int(m.group(1))
        if 1900 <= y <= 2099:
            return y
    m = _TRACK_RANGE.search(raw or "")
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        # Only a plausible SPAN, ascending, both in the same century. "91-96"
        # is a layout; "24-7" is not, and neither is a car number.
        if 0 < a < b <= 99:
            return (1900 + a) if a > 30 else (2000 + a)
    return None


class Track(object):
    """What we know about the circuit currently loaded."""

    __slots__ = ("slug", "name", "raw", "known", "_d", "year", "key")

    def __init__(self, raw):
        self.raw = raw or ""
        self.slug = resolve(raw)
        self._d = load().get(self.slug or "", {})
        self.known = bool(self._d)
        self.name = self._d.get("name") or _pretty(raw)
        # AN IDENTITY, EVEN WHEN WE KNOW NOTHING ABOUT THE PLACE.
        #
        # `slug` is None for a circuit the alias table has never heard of, and
        # `known` is False, and both of those are right: the booth must say
        # nothing about a track it cannot recognise. But a CAREER ROUND has to be
        # recorded against something, and "we have no trivia about this place" is
        # a completely different question from "this race did not happen".
        #
        # The user's own report: a Formula 4 round at "ANA - INDY GRAND PRIX",
        # which nothing here recognises, and every attempt to start it reported
        # the career as paused — no prompt, no round, nothing recorded, in an
        # OPEN season whose whole definition is "N races, ANY circuit".
        #
        # So `key` is always usable: the canonical slug where there is one, and a
        # normalised form of the raw name where there is not. Two different
        # tracks cannot collide on it, and the same track is stable across
        # sessions, which is all a round number needs.
        self.key = self.slug or _slugify(raw)
        # WHICH LAYOUT THIS IS. rF2 content names the year — "ISI_Belgium_1966",
        # "Silverstone_1991", "Monza_2021" — and it matters enormously,
        # because a historic circuit is not a shorter version of the modern
        # one, it is a different road. Spa in 1966 was fourteen kilometres.
        self.year = _scrape_year(self.raw)

    def facts(self):
        """Facts true of THIS LAYOUT.

        A fact may carry `year: [lo, hi]`, exactly as a dialogue line does,
        and is then only offered for a layout inside that range. Without it,
        the modern Spa entry told the booth the lap was "over seven
        kilometres, the longest on the calendar" — over a 1966 circuit that
        was fourteen kilometres long. That is not a small wrongness: it is
        the kind the user can see out of the cockpit.

        A layout with no year in its name gets the undated facts only, which
        is the safe direction.
        """
        out = []
        for f in self._d.get("facts", ()):
            if isinstance(f, str):
                out.append(f)
                continue
            span = f.get("year")
            if span and self.year and not (span[0] <= self.year <= span[1]):
                continue
            if span and not self.year:
                continue        # undated layout: only undated facts
            out.append(f.get("t", ""))
        return [f for f in out if f]

    def corners(self):
        """The corners of THIS LAYOUT, in lap order.

        The default list is the CURRENT road. Using it for a historic layout
        names corners that do not exist yet: Silverstone's includes Village,
        the Loop and the Wellington Straight — the Arena section built in
        2010 — and `corner()` was naming them during a 1991 race.
        """
        for block in self._d.get("corners_history") or ():
            span = block.get("year") or ()
            if (self.year and len(span) == 2
                    and span[0] <= self.year <= span[1]):
                return block.get("corners") or []
        return self._d.get("corners", [])

    def character(self):
        """One-line description of what the circuit demands. Used by the
        analyst as colour and by the engineer as a setup note."""
        return self._d.get("character", "")

    def overtaking(self):
        return self._d.get("overtaking", "")

    def sector(self, n):
        """What sector `n` (1, 2 or 3) of this circuit asks of a driver.

        A clause, used verbatim, completing "...that is where it is going,
        <clause>". Empty for a circuit we hold no sector notes for, and the
        engineer then simply names the sector without coaching — which is the
        correct failure, because a corner named in the wrong sector is worse
        than no corner at all.

        A sector clause describes a piece of ROAD, so it dates exactly like
        the corner list does — `sectors_history` overrides the default set
        for a layout inside its year range. Zandvoort is why: the modern
        third sector is "power on early in the banked last corner", and the
        banking was built in 2020. Told over the 2017 layout that is a
        coaching note about a corner the driver cannot see.
        """
        secs = None
        for block in self._d.get("sectors_history") or ():
            span = block.get("year") or ()
            if (self.year and len(span) == 2
                    and span[0] <= self.year <= span[1]):
                secs = block.get("sectors")
                break
        if secs is None:
            secs = self._d.get("sectors") or []
        return secs[n - 1] if 1 <= n <= len(secs) else ""

    def country(self):
        return self._d.get("country", "")

    def corner(self, frac):
        """The named corner at a fraction (0..1) around the lap.

        Approximate by design — corners are listed in order and mapped evenly,
        which is wrong in detail but right in sequence. Good enough for "into
        Eau Rouge" and never claims a distance it does not have.
        """
        c = self.corners()
        if not c or frac is None:
            return ""
        i = int(max(0.0, min(0.999, frac)) * len(c))
        return c[i]

    def __repr__(self):
        return "<Track %s known=%s %r>" % (self.slug, self.known, self.raw)


def _pretty(raw):
    """A presentable name when we have no data — strip the layout noise but
    keep the mod's own capitalisation.

    THE YEAR COMES OUT. A layout year is how this module decides which road
    it is looking at; it is not part of the circuit's NAME and must never be
    said out loud. "Welcome to Silverstone 1991" during a 1988 championship
    tells the viewer he is driving a re-run rather than a season — the year
    on the folder is production metadata leaking into the broadcast.

    Only a run of digits is removed here, not the rest of `_NOISE`: "GP" and
    "National" genuinely distinguish two layouts a user may have installed,
    and dropping them would announce both of them as the same circuit.
    """
    s = _SEPS.sub(" ", raw or "")
    s = re.sub(r"\b(?:19|20)?[0-9]{2}(?:\s*-\s*[0-9]{2})?\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or "Unknown"


if __name__ == "__main__":
    # Every track name this user's installation can actually produce.
    samples = [
        "Zandvoort 2021", "HockenheimRing GP", "HockenheimRing DTM",
        "Belgium", "ISI_Belgium_1966", "SaoPaulo GP", "LeMans91",
        "Le Mans 91-96 Virtua_LM", "Daytona International Speedway",
        "JM_Daytona_Speedway_2022", "Monza_2021", "Brianza_1966",
        "MonteCarlo_1966", "3PA_Bathurst_2014", "Indianapolis_2020",
        "Road_America_2019", "LimeRockPark_2021", "Portland_2019",
        "ISI_Montreal_2000", "BahrainIC_2022", "Malaysia_2007",
        "Portugal_2009", "Longford_1967", "Kyalami", "Kyalami 9 Hour",
        "TobanRP_2016", "Lester 2.0",
    ]
    d = load()
    print("%d circuits in the knowledge base\n" % len(d))
    print("%-34s %-14s %s" % ("rF2 NAME", "SLUG", "KNOWN"))
    unknown = 0
    for s_ in samples:
        t = Track(s_)
        if not t.known:
            unknown += 1
        print("%-34.34s %-14s %s" % (s_, t.slug or "-",
                                     ("yes  " + t.name) if t.known else "no"))
    print("\n%d/%d resolved to knowledge" % (len(samples) - unknown, len(samples)))
