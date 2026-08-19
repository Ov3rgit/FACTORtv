# -*- coding: utf-8 -*-
"""
FACTORtv — era and discipline detection.

One job: look at what is actually on track and decide what KIND of racing
this is, so that both the skin and the commentary stop being generic.

Why this module exists at all
-----------------------------
A booth that says "he's got DRS open" over a 1992 Williams, or "watch the
battery deployment" over a Brabham BT44, destroys the illusion faster than
any graphical flaw. rF2 is a mod platform — the same overlay has to cover a
1968 Howston, a 1992 Mansell car, a 2025 hybrid, a Next Gen Cup car and a
GT500 in the same evening. So terminology is not decoration, it is a
capability question: does this car HAVE the thing I am about to mention?

Everything downstream asks this module rather than assuming. `era.has("drs")`
gates a whole family of commentary lines; `era.skin` picks the palette.

How detection works
-------------------
rF2 gives us two strings per car: mVehicleClass (e.g. "Formula 1 1992 Season
by ASRC") and mVehicleName (e.g. "Nigel Mansell"). Class is the useful one.
Detection runs in three passes, most specific first:

  1. Explicit rules for series we can name outright (the tables below).
  2. A year scraped out of the class/vehicle string, mapped to a period.
  3. Shape-of-the-name heuristics ("GT3", "Formula", "Stock") for unknown mods.

Pass 3 matters more than it looks: the user has 76 vehicle folders and can
add more at any time, so an unrecognised mod must still get a sane era rather
than falling back to modern-F1 vocabulary.
"""
import re

# --------------------------------------------------------------------------
# periods
#
# Boundaries are drawn where the RACING changed, not on round decades, because
# that is what the commentary needs to respect.
# --------------------------------------------------------------------------
PERIODS = [
    # key            label                 from  to    skin
    ("pioneer",     "the pioneer era",     1900, 1957, "vintage"),
    ("golden",      "the golden age",      1958, 1969, "classic"),
    ("wing",        "the wing era",        1970, 1981, "seventies"),
    ("turbo",       "the turbo era",       1982, 1988, "eighties"),
    ("v10",         "the V10 era",         1989, 1999, "nineties"),
    ("grooved",     "the early 2000s",     2000, 2008, "millennium"),
    ("modern",      "the modern era",      2009, 2013, "modern"),
    ("hybrid",      "the hybrid era",      2014, 2021, "modern"),
    ("ground",      "the ground-effect era", 2022, 2099, "modern"),
]

# Capabilities, by period, for OPEN-WHEEL cars. Other disciplines override.
# A capability that is absent is never mentioned by the booth or engineer.
_OPEN_WHEEL_CAPS = {
    "pioneer":  set(),
    "golden":   set(),
    "wing":     {"slicks", "wings"},
    "turbo":    {"slicks", "wings", "turbo", "refuel"},
    "v10":      {"slicks", "wings", "compounds"},
    "grooved":  {"slicks", "wings", "refuel", "compounds", "tc"},
    "modern":   {"slicks", "wings", "drs", "kers", "compounds", "tc"},
    "hybrid":   {"slicks", "wings", "drs", "ers", "compounds", "tc", "turbo",
                 "fuelflow", "engine_modes"},
    "ground":   {"slicks", "wings", "drs", "ers", "compounds", "tc", "turbo",
                 "fuelflow", "engine_modes"},
}


class Era(object):
    """The answer. Immutable once built; rebuilt whenever the class changes."""

    __slots__ = ("key", "label", "year", "period", "discipline", "skin",
                 "caps", "series", "raw_class", "confidence", "field_classes")

    def __init__(self, key, label, year, period, discipline, skin, caps,
                 series="", raw_class="", confidence="low", field_classes=()):
        self.key = key
        self.label = label
        self.year = year
        self.period = period
        self.discipline = discipline
        self.skin = skin
        self.caps = frozenset(caps)
        self.series = series
        self.raw_class = raw_class
        self.confidence = confidence
        self.field_classes = tuple(field_classes)

    def has(self, cap):
        """Does this car HAVE this thing? The gate for every piece of
        era-specific vocabulary in the booth and on the dash."""
        return cap in self.caps

    @property
    def multiclass(self):
        return len(self.field_classes) > 1

    @property
    def is_open_wheel(self):
        return self.discipline in ("f1", "formula", "indycar")

    @property
    def is_historic(self):
        return self.period in ("pioneer", "golden", "wing")

    @property
    def decade(self):
        return (self.year // 10 * 10) if self.year else None

    def decade_name(self):
        d = self.decade
        if not d:
            return ""
        return {1950: "the fifties", 1960: "the sixties", 1970: "the seventies",
                1980: "the eighties", 1990: "the nineties",
                2000: "the two-thousands", 2010: "the twenty-tens",
                2020: "the twenties"}.get(d, str(d) + "s")

    def __repr__(self):
        return ("<Era %s %s/%s year=%s skin=%s caps=%s>"
                % (self.key, self.discipline, self.period, self.year,
                   self.skin, ",".join(sorted(self.caps)) or "-"))


# --------------------------------------------------------------------------
# explicit series rules
#
# Ordered — first regex to match a vehicle class wins, so put the specific
# ones above the loose ones. These are keyed on classes seen in the user's
# own race results plus the common rF2 workshop content.
# --------------------------------------------------------------------------
_RULES = [
    # (regex on class,                  key,        label,                     year, discipline, series)
    (r"formula\s*1\s*1992|f1\s*1992|1992\s*season",
     "f1_1992", "1992 Formula One", 1992, "f1", "Formula One"),
    (r"\bf1\s*test\s*20(2\d)|formula\s*hybrid[-\s]*(\d\d)|asmg",
     "f1_modern", "Formula One", 2025, "f1", "Formula One"),
    (r"\bfsr\s*20(\d\d)", "fsr", "FSR", 2026, "f1", "FSR"),
    (r"stock\s*car.*x\s*series|stockcar\s*20(\d\d)",
     "stockcar_x", "Stock Car X Series", 2018, "stock", "Stock Car"),
    (r"nascar|next\s*gen\s*cup|cup\s*series",
     "nascar_cup", "NASCAR Cup", 2023, "stock", "NASCAR"),
    (r"indycar[_\s]*20(\d\d)|dallara\s*dw12|indy\s*car",
     "indycar", "IndyCar", 2014, "indycar", "IndyCar"),
    (r"formula\s*e", "formulae", "Formula E", 2023, "formula", "Formula E"),
    (r"\bgt500\b|super\s*gt", "gt500", "SUPER GT500", 2013, "gt", "SUPER GT"),
    (r"\bgte\b|\blmgte\b", "gte", "GTE", 2018, "gt", "GTE"),
    (r"\bgt3\b", "gt3", "GT3", 2019, "gt", "GT3"),
    (r"\bgt4\b|a110\s*gt4", "gt4", "GT4", 2021, "gt", "GT4"),
    (r"group\s*c|787b|962|956\b", "groupc", "Group C", 1990, "proto", "Group C"),
    # Le Mans Hypercar / LMDh — the current WEC top class. MUST sit above the
    # loose GT and shape rules: manufacturer names like "Ferrari 499P" and
    # "Porsche 963" otherwise trip the GT heuristic, and a Hypercar ends up
    # commentated as a GT3 car with no hybrid and no class structure.
    (r"hypercar|\blmh\b|\blmdh\b|gr010|499p|\b963\b|9x8|valkyrie",
     "hypercar", "Hypercar", 2023, "proto", "WEC"),
    (r"\blmp1\b", "lmp1", "LMP1", 2018, "proto", "WEC"),
    (r"\blmp[23]\b|oreca\s*07|prototype", "lmp", "Prototype", 2018, "proto",
     "Prototype"),
    # DTM. Matched EXPLICITLY, above the loose touring rule, because without
    # a rule of its own "DTM 2020" classified as `unknown` — which handed a
    # silhouette tin-top the modern Formula One steering-wheel display. The
    # 1990s cars were closer to Group A saloons and the 2012+ cars are
    # carbon-tubbed silhouettes, but both are touring cars for our purposes.
    (r"\bdtm\b|deutsche\s*tourenwagen|\bclass\s*1\b",
     "dtm", "DTM", 2020, "touring", "DTM"),
    (r"\bstw\b|\bbtcc\b|super\s*tour|touring\s*car|320i|s40\s*st",
     "touring", "Super Touring", 1998, "touring", "Super Touring"),
    (r"clio\s*cup|civic|megane|mini\s*cooper|caterham",
     "clubman", "club racing", 2013, "touring", ""),
    (r"tatuus|usf\s*2000|f4\b|formula\s*3|\bf3\b|skip\s*barber",
     "junior", "junior formula", 2018, "formula", ""),
    (r"formula\s*renault|formula\s*2|\bf2\b|formula\s*rc|fisir",
     "junior_sr", "formula racing", 2012, "formula", ""),
    (r"kart", "kart", "karting", 2014, "kart", ""),
]

# Vehicle-name (not class) hints for mods whose class string is useless —
# "Default" and "National" both showed up in the user's results.
_NAME_RULES = [
    # Separators are already folded to spaces by _norm(), so these use \s*.
    (r"mp4\s*13\b", "f1_1998", "1998 Formula One", 1998, "f1", "Formula One"),
    (r"mp4\s*8\b", "f1_1993", "1993 Formula One", 1993, "f1", "Formula One"),
    (r"march\s*m761|brabham\s*bt44|mclaren\s*m23|howston\s*diss",
     "f1_1975", "1970s Formula One", 1975, "f1", "Formula One"),
    (r"brabham\s*(19)?66|howston\s*g[46]|historic\s*challenge|eve\s*1968|spark\s*1968",
     "f1_1967", "1960s Grand Prix racing", 1967, "f1", "Grand Prix"),
    (r"mercedes\s*sls|safety\s*car", "safety", "safety car", 2012, "gt", ""),
]

# Discipline defaults where the open-wheel capability table does not apply.
#
# "formula" (the junior ladder) and "unknown" MUST be listed here. Without
# them they fall through to the open-wheel period table, which for anything
# built after 2014 hands out DRS, ERS, turbo and fuel-flow — so a Tatuus F4
# ends up being commentated as a hybrid F1 car. An unrecognised mod gets the
# deliberately bare set: better mute than wrong.
_DISCIPLINE_CAPS = {
    "stock": {"refuel", "stages", "restarts", "banking", "draft"},
    "gt": {"slicks", "refuel", "compounds", "tc", "abs", "bop", "pitwindow"},
    "proto": {"slicks", "refuel", "compounds", "tc", "abs", "bop", "pitwindow",
              "headlights"},
    "touring": {"slicks", "compounds", "contact"},
    "indycar": {"slicks", "wings", "refuel", "compounds", "ptp", "ovals"},
    "formula": {"slicks", "wings", "compounds"},
    "kart": set(),
    "unknown": {"slicks"},
}

# --------------------------------------------------------------------------
# CONSTRUCTOR NAMES AS A CLASS LIST
#
# Some F1 mods name `CarClass` per TEAM, so a 2021 grid arrives as ten
# "classes" called McLaren, Ferrari, Haas... and nothing in the rule table
# matches any of them. The live run classified that field as `unknown_2020`:
#
#     ERA  unknown_2020  disc=unknown year=2020  raw class: 'Haas'
#
# which is where "the 2020 Formula One grid" came from, and why the cars had
# no DRS and no ERS — discipline `unknown` gets `{"slicks"}` and nothing else.
#
# The team list is also a DATE. Each constructor raced under a given name for
# a known span, so the season is the year that the most of these names were
# on the grid together. That is a guess and is marked as one, but it is a far
# better guess than 2020-by-default, and the career lets you pin the season
# explicitly when it matters.
#
# Ranges are the span of the NAME, not of the organisation: Sauber becoming
# Alfa Romeo becoming Kick Sauber is three entries, because that is exactly
# what makes them useful for dating a grid.
_F1_TEAMS = {
    "ferrari": (1950, 2100),
    "mclaren": (1966, 2100),
    "williams": (1977, 2100),
    "mercedes": (2010, 2100),
    "red bull": (2005, 2100),
    "redbull": (2005, 2100),
    "haas": (2016, 2100),
    "alpine": (2021, 2100),
    "aston martin": (2021, 2100),
    "alpha tauri": (2020, 2023),
    "alphatauri": (2020, 2023),
    "toro rosso": (2006, 2019),
    "racing point": (2019, 2020),
    "force india": (2008, 2018),
    "alfa romeo": (2019, 2023),
    "kick sauber": (2024, 2025),
    "racing bulls": (2024, 2100),
    "visa cash app rb": (2024, 2024),
    "sauber": (1993, 2018),
    "renault": (2016, 2020),
    "lotus": (2012, 2015),
    "manor": (2015, 2016),
    "marussia": (2012, 2015),
    "caterham": (2012, 2014),
    "brawn": (2009, 2009),
    "toyota": (2002, 2009),
    "honda": (2006, 2008),
    "bmw sauber": (2006, 2009),
    "jordan": (1991, 2005),
    "benetton": (1986, 2001),
    "tyrrell": (1970, 1998),
    "ligier": (1976, 1996),
    "arrows": (1978, 2002),
    "minardi": (1985, 2005),
    "brabham": (1962, 1992),
    "lotus f1": (1958, 1994),
    "march": (1970, 1992),
    "osella": (1980, 1990),
    "footwork": (1991, 1996),
}

# TITLE-SPONSOR TELLS. Team names alone cannot separate some adjacent
# seasons — the 2021, 2022 and 2023 grids are the same ten constructors, and
# so are 2024 and 2025. But the full entrant names carry the sponsor, and
# those DO change: "Atlassian Williams" exists only in 2025. Checked against
# the joined class list and used only to pin a year the team set left
# ambiguous, never to override a year found in the mod's own name.
_F1_SEASON_TELLS = [
    (r"atlassian", 2025),
    (r"scuderia ferrari hp", 2025),
    (r"racing bulls(?!.*visa)", 2025),
    (r"visa cash app", 2024),
    (r"kick sauber", 2024),
    (r"alfa romeo f1 team orlen", 2022),
    (r"oracle red bull", 2022),
]


# How much of the field must be recognisable constructors before we believe
# the class list is a team list. Below this it is probably a coincidence — one
# GT field with a "Ferrari" class is not a Formula One grid.
F1_TEAM_SHARE = 0.5
F1_TEAM_MIN = 4          # ...and at least this many distinct teams


def _team_field(classes):
    """Is this class list a set of F1 constructors, and if so, which season?

    Returns (n_matched, n_total, year) or None. `year` is the season in which
    the most of these team names were simultaneously on the grid — the honest
    reading of "who is in this race".
    """
    names = [_norm(c) for c in classes if c]
    if len(names) < F1_TEAM_MIN:
        return None
    spans = []
    for n in names:
        for team, span in _F1_TEAMS.items():
            if team in n:
                spans.append(span)
                break
    if not spans or len(spans) < F1_TEAM_MIN:
        return None
    if len(spans) / float(len(names)) < F1_TEAM_SHARE:
        return None
    # Score every plausible season by how many of these names existed then.
    best_year, best_hits = None, -1
    for y in range(1950, 2031):
        hits = sum(1 for lo, hi in spans if lo <= y <= hi)
        # Ties go to the EARLIEST year: the ranges are open-ended for teams
        # still racing, so a late tie is an artefact of that rather than
        # evidence, and guessing early is the correctable direction.
        if hits > best_hits:
            best_year, best_hits = y, hits
    # A sponsor tell beats the team set when there is one, because it is
    # evidence about THIS season rather than about a span of them.
    blob = " ".join(names)
    for pat, yr in _F1_SEASON_TELLS:
        if re.search(pat, blob):
            best_year = yr
            break
    return (len(spans), len(names), best_year)


def team_field(classes):
    """Public: is this class list a set of F1 constructors? See `_team_field`.

    Exposed so the career can tell a TEAM-NAMED grid apart from a genuine
    multi-class race. Both have several small classes; only one of them is a
    single championship, and merging a GT4/Super Touring/GT500 grid into one
    "field" invents a championship that never happened.
    """
    return _team_field(classes)


_YEAR_RE = re.compile(r"(?:^|[^0-9])((?:19|20)\d{2})(?:[^0-9]|$)")
_SHORT_YEAR_RE = re.compile(r"'(\d\d)\b")
_SEPS = re.compile(r"[_\-/.]+")


def _norm(s):
    """Fold a mod's folder-style name into something the rules can match.

    rF2 content is named "McLaren_MP4_8_1993", "Tatuus_F3_T318_2018",
    "Historic Challenge_EVE_1968" — underscores everywhere. The rules are
    written with \\s*, which does NOT match an underscore, so without this
    every historic mod silently fell through to the shape heuristics and
    came out as discipline 'unknown'.
    """
    return _SEPS.sub(" ", (s or "").lower())


def _period_for(year):
    for key, label, lo, hi, skin in PERIODS:
        if lo <= year <= hi:
            return key, label, skin
    return "modern", "the modern era", "modern"


def _scrape_year(*texts):
    """Pull a plausible model year out of a class or vehicle string.

    rF2 mod authors put the year almost everywhere — "BMW_M4_GT3_2020",
    "Brabham_1966", "SC2018X_2018". Guarded to a sane racing range so a
    car number or a track length never gets read as a year.
    """
    for t in texts:
        if not t:
            continue
        for m in _YEAR_RE.finditer(t):
            y = int(m.group(1))
            if 1900 <= y <= 2099:
                return y
        m = _SHORT_YEAR_RE.search(t)
        if m:
            n = int(m.group(1))
            return 1900 + n if n > 30 else 2000 + n
    return None


def _shape_guess(cls, name):
    """Last resort for an unknown mod: guess discipline from the shape of the
    name. Deliberately conservative — an unknown car gets neutral vocabulary
    rather than a confident wrong guess."""
    t = ((cls or "") + " " + (name or "")).lower()
    if re.search(r"formula|\bf\d\b|open\s*wheel|grand\s*prix", t):
        return "formula"
    if re.search(r"stock|cup|late\s*model|truck", t):
        return "stock"
    if re.search(r"\bgt\b|gran\s*turismo|coupe|corvette|porsche|ferrari|"
                 r"lamborghini|aston|bentley|mclaren\s*7", t):
        return "gt"
    if re.search(r"proto|lmp|sport\s*car|roadster|radical", t):
        return "proto"
    if re.search(r"touring|sedan|hatch|civic|clio|golf", t):
        return "touring"
    return "unknown"


def classify(vehicle_class, vehicle_name="", field_classes=()):
    """Build an Era from one car's class/name strings.

    `field_classes` is every distinct class present in the session, used only
    to flag multi-class racing (which changes how gaps and positions are
    called — 'P4, and second in class' rather than a bare position).
    """
    cls = (vehicle_class or "").strip()
    name = (vehicle_name or "").strip()
    hay = _norm(cls + " " + name)

    key = label = series = None
    year = None
    discipline = None
    confidence = "low"

    # pass 1 — explicit series rules, class first then vehicle name
    for pat, k, lab, yr, disc, ser in _RULES:
        m = re.search(pat, hay)
        if m:
            key, label, year, discipline, series = k, lab, yr, disc, ser
            confidence = "high"
            # A rule may capture a two-digit year ("FSR 2026" -> 26); prefer
            # the real one in the string over the rule's default.
            for g in m.groups():
                if g and g.isdigit():
                    n = int(g)
                    year = 2000 + n if n < 100 else n
            break

    if key is None:
        for pat, k, lab, yr, disc, ser in _NAME_RULES:
            if re.search(pat, hay):
                key, label, year, discipline, series = k, lab, yr, disc, ser
                confidence = "high"
                break

    # pass 2 — scrape a year.
    #
    # A year found in the actual mod name always beats the rule's default,
    # because the rules are written per-FAMILY and the family spans years:
    # the historic rule answers "1967" for every pre-1970 car, so without
    # this a Brabham 1966 and a Howston 1968 would both be called 1967 and
    # the booth would date the race wrong by two seasons.
    scraped = _scrape_year(cls, name)
    if scraped:
        year = scraped
    if year is None:
        year = 2020

    # pass 2b — THE CLASS LIST IS A TEAM LIST.
    #
    # Runs before the shape guess and can rescue a field the rules missed
    # entirely, which is the common case for F1 mods that name CarClass per
    # constructor. It never overrides a matched rule: an explicit "F1 1988"
    # in the class string is better evidence than a set of team names.
    if key is None:
        teams = _team_field(field_classes)
        if teams is not None:
            _matched, _total, team_year = teams
            discipline = "f1"
            series = series or "Formula One"
            label = "Formula One"
            confidence = "guess"
            if not scraped:
                # Only when the strings themselves gave us nothing: a real
                # year in the mod name always beats an inference from who is
                # on the grid.
                year = team_year
            key = "f1_%d" % year

    # pass 3 — shape heuristics for unknown mods
    if discipline is None:
        discipline = _shape_guess(cls, name)
        confidence = "guess" if discipline != "unknown" else "none"
    if key is None:
        key = "%s_%d" % (discipline, year)
    if label is None:
        label = cls or "racing"

    period, period_label, skin = _period_for(year)

    # capabilities: discipline table wins, open-wheel falls back to period
    if discipline in _DISCIPLINE_CAPS:
        caps = set(_DISCIPLINE_CAPS[discipline])
        # even a GT car loses electronics if it is old enough
        if year < 1990:
            caps -= {"tc", "abs", "compounds", "bop", "pitwindow"}
        if year < 1970:
            caps -= {"slicks"}
    else:
        caps = set(_OPEN_WHEEL_CAPS.get(period, set()))

    # per-series corrections that the period table cannot know
    if key in ("f1_1992", "f1_1993"):
        # 1992-93 is the high-water mark of driver aids: active suspension,
        # traction control and semi-auto boxes were all legal, and all banned
        # for 1994. Refuelling was NOT allowed until 1994 either. Getting this
        # wrong is the single most likely era howler, so it is pinned here
        # rather than left to the period table.
        caps |= {"active_suspension", "tc", "semiauto"}
        caps -= {"refuel", "drs", "ers", "kers"}
    if key == "f1_1998":
        # Grooved tyres and narrow track from 1998; aids were gone by then.
        caps |= {"grooved", "refuel"}
        caps -= {"slicks", "active_suspension", "tc", "semiauto"}
    if key == "nascar_cup":
        caps |= {"stages", "restarts", "draft", "banking", "refuel"}
    if key == "stockcar_x":
        caps |= {"refuel", "restarts", "draft"}
        caps -= {"stages"}
    if key == "indycar":
        caps |= {"ptp", "ovals", "refuel"}
    if key in ("gte", "gt3", "gt500", "lmp", "lmp1", "lmgt3", "hypercar",
               "groupc"):
        caps |= {"pitwindow", "headlights", "traffic"}
    if key in ("hypercar", "lmp1"):
        # LMH and LMDh both run a hybrid system, and the top class is where
        # energy management is actually part of the racing. No DRS in WEC.
        caps |= {"ers", "engine_modes", "bop", "refuel", "fuelflow"}
        caps -= {"drs"}
    if key in ("hypercar", "lmgt3", "lmp", "lmp1", "gte"):
        # Multi-class endurance: traffic and class position are the story.
        caps |= {"nightracing"}
    if key == "groupc":
        # Group C ran on fuel allowance, not BoP, and long before spec
        # compound choices. It DID run at night, hence headlights.
        caps -= {"tc", "abs", "bop", "compounds"}
        caps |= {"fuelration", "headlights"}
    if key == "kart":
        caps = set()

    return Era(key=key, label=label, year=year, period=period,
               discipline=discipline, skin=skin, caps=caps, series=series or "",
               raw_class=cls, confidence=confidence,
               field_classes=tuple(sorted(set(field_classes))))


# --------------------------------------------------------------------------
# terminology
#
# The booth asks for a WORD, not a fact. Every entry here has a variant per
# era so the same event gets called the way that era called it.
# --------------------------------------------------------------------------
_TERMS = {
    "overtake_zone": {
        "golden": "under braking",
        "wing": "under braking",
        "turbo": "on the brakes",
        "v10": "on the brakes",
        "_": "into the braking zone",
    },
    "pace_note": {
        "golden": "a quick lap",
        "wing": "a quick lap",
        "_": "a strong lap",
    },
    "tyres": {
        "golden": "the rubber",
        "wing": "the tyres",
        "_": "the tyres",
    },
    "pit": {
        "golden": "the pits",
        "wing": "the pits",
        "_": "the pit lane",
    },
    "engineer": {
        "golden": "the pit board",
        "wing": "the pit board",
        "turbo": "the pit wall",
        "_": "the pit wall",
    },
    "fuel_save": {
        "golden": "nursing it home",
        "wing": "saving fuel",
        "_": "in fuel-save mode",
    },
}


def term(era, key):
    """Era-correct word for a concept. Falls back to the modern phrasing."""
    table = _TERMS.get(key)
    if not table:
        return key
    return table.get(era.period, table.get("_", key))


# --------------------------------------------------------------------------
# skins
#
# Palettes for the adaptive UI. Every skin keeps the FACTORtv identity —
# the logo's navy and cyan stay the structural colours — but the accent,
# warmth and instrument style shift with the era, so a 1968 broadcast reads
# as a 1968 broadcast without becoming a different product.
# --------------------------------------------------------------------------
SKINS = {
    "modern": {
        "name": "modern",
        "panel": "#0d1b2a", "panel2": "#0a1622", "border": "#1e3a52",
        "accent": "#4fe0e8", "accent2": "#2ba8c4", "text": "#eef4f8",
        "dim": "#8ba3b8", "you": "#ffd23f", "leader": "#5cc8ff",
        "best": "#c77dff", "good": "#69db7c", "warn": "#e6a23c",
        "bad": "#ff4d4d",
        "dial": "digital",          # instrument style for the dash
        "font": "condensed",
        "grain": 0.0,
    },
    "millennium": {
        "name": "millennium",
        "panel": "#101a26", "panel2": "#0b131c", "border": "#24405a",
        "accent": "#4fe0e8", "accent2": "#2f9fbc", "text": "#eaf2f7",
        "dim": "#87a0b4", "you": "#ffd23f", "leader": "#6cc4f5",
        "best": "#bb7dff", "good": "#6ddb7c", "warn": "#e6a23c",
        "bad": "#ff4d4d",
        "dial": "digital", "font": "condensed", "grain": 0.0,
    },
    "nineties": {
        # 1992: bold flat primaries, hard edges, the look of a Bernie-era
        # world feed caption. Cyan survives as the channel colour.
        "name": "nineties",
        "panel": "#0c2340", "panel2": "#08182c", "border": "#2f5f8f",
        "accent": "#4fe0e8", "accent2": "#ffd400", "text": "#ffffff",
        "dim": "#9fb6cc", "you": "#ffd400", "leader": "#ff3b30",
        "best": "#b06bff", "good": "#4cd964", "warn": "#ff9500",
        "bad": "#ff3b30",
        "dial": "hybrid", "font": "block", "grain": 0.03,
    },
    "eighties": {
        "name": "eighties",
        "panel": "#111a2e", "panel2": "#0b1222", "border": "#3a4f7a",
        "accent": "#4fe0e8", "accent2": "#ff7a1a", "text": "#f5f2e8",
        "dim": "#a49c8c", "you": "#ffb000", "leader": "#ff5c39",
        "best": "#c77dff", "good": "#7ed957", "warn": "#ffb000",
        "bad": "#e63946",
        "dial": "analogue", "font": "block", "grain": 0.05,
    },
    "seventies": {
        # 1970s: warm film stock, cream captions, amber instruments.
        "name": "seventies",
        "panel": "#1a1710", "panel2": "#12100b", "border": "#5a4a2e",
        "accent": "#e8b04f", "accent2": "#4fe0e8", "text": "#f6efdd",
        "dim": "#b0a184", "you": "#ffcf5c", "leader": "#e07b39",
        "best": "#c9a0ff", "good": "#9ccc65", "warn": "#e8a33d",
        "bad": "#d1495b",
        "dial": "analogue", "font": "serif", "grain": 0.10,
    },
    "classic": {
        # 1960s: near-monochrome, as if the colour feed barely exists.
        "name": "classic",
        "panel": "#17150f", "panel2": "#100e0a", "border": "#4a4232",
        "accent": "#d8c9a0", "accent2": "#4fe0e8", "text": "#f2ead6",
        "dim": "#a2977c", "you": "#e8d38a", "leader": "#c97a4a",
        "best": "#b9a3d6", "good": "#a3bf7a", "warn": "#d6a45c",
        "bad": "#b8494f",
        "dial": "analogue", "font": "serif", "grain": 0.14,
    },
    "vintage": {
        "name": "vintage",
        "panel": "#161310", "panel2": "#0f0d0a", "border": "#443c30",
        "accent": "#cbbb95", "accent2": "#4fe0e8", "text": "#eee5d2",
        "dim": "#998f78", "you": "#ddc98a", "leader": "#bb7048",
        "best": "#ab97c4", "good": "#96b070", "warn": "#c99a55",
        "bad": "#a8444a",
        "dial": "analogue", "font": "serif", "grain": 0.18,
    },
}

# Discipline overrides layered on top of the period skin — a Cup car in 2023
# should not look like an F1 car in 2023.
_DISCIPLINE_SKIN = {
    "stock": {"accent2": "#ff3b30", "you": "#ffd400", "dial": "hybrid",
              "font": "block"},
    "gt": {"accent2": "#7ed957", "dial": "digital"},
    "proto": {"accent2": "#7ed957", "dial": "digital"},
    "indycar": {"accent2": "#ff9500", "dial": "hybrid"},
}


def skin_for(era):
    """Full palette dict for an Era: period skin + discipline overrides."""
    base = dict(SKINS.get(era.skin, SKINS["modern"]))
    base.update(_DISCIPLINE_SKIN.get(era.discipline, {}))
    base["era_key"] = era.key
    base["era_label"] = era.label
    return base


def field_era(vehicles):
    """Decide the era for a whole session from every car in it.

    Uses the most common class rather than the player's own, so a multi-class
    grid is skinned by what the race mostly IS. The player's class is still
    reported separately for class-relative positions.
    """
    if not vehicles:
        return classify("", "")
    counts = {}
    for cls, nm in vehicles:
        counts.setdefault(cls or "", [0, nm])
        counts[cls or ""][0] += 1
    top = max(counts.items(), key=lambda kv: kv[1][0])
    return classify(top[0], top[1][1], field_classes=[c for c in counts if c])


if __name__ == "__main__":
    # Sanity dump against the classes actually seen in the user's results.
    samples = [
        ("Formula 1 1992 Season by ASRC", "Nigel Mansell"),
        ("F1 Test 2025", "Max Verstappen"),
        ("FSR 2026", "Alice Jackson"),
        ("StockCar 2018 X Series", "Ted Moser"),
        ("GT500", "HSV-010 GT500 2013"),
        ("Alpine A110 GT4", "GT4 FFSA 2021"),
        ("IndyCar_2014_Honda", "Dallara DW12"),
        ("VOLVO S40 ST", "VOLVO S40 ST"),
        ("BMW 320i STW", "BMW 320i STW"),
        ("National", "Mazda 787B"),
        ("Default", "McLaren_MP4_8_1993"),
        ("", "Brabham_1966"),
        ("", "Howston_G4_1968"),
        ("", "March_M761_1976"),
        ("", "NASCAR 2023 Next Gen CUP"),
        ("", "Tatuus_F4_2018"),
        ("", "Some_Unknown_Mod_2031"),
    ]
    w = max(len(a) or len(b) for a, b in samples)
    for cls, nm in samples:
        e = classify(cls, nm)
        print("%-32.32s %-24.24s -> %-14s %-9s %-10s %4d  %s"
              % (cls or "(none)", nm, e.key, e.discipline, e.skin, e.year,
                 ",".join(sorted(e.caps)) or "-"))
