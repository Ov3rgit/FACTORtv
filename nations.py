# -*- coding: utf-8 -*-
"""
FACTORtv — where a driver is from.

The second of the three identity fields a career gets: name, NATIONALITY, home
circuit. It is one line of data and it buys two things nothing else can:

    "The young Australian, third on the grid."
    "And this is his home race."

WHY A HOME RACE IS DERIVED AND NOT ASKED FOR
--------------------------------------------
`tracks.json` already holds a country for 56 of the 68 circuits, so once a
driver has a nationality the home race falls out of data that was already
there. Asking him to nominate a circuit as well would be a second question
with a worse answer — he would have to know which of his installed tracks the
overlay recognises, and he would get it wrong for exactly the circuits where
the line matters most.

THE COMPARISON FOLDS A LEADING "THE", because the circuit data holds both
"United States" and "the United States" — twelve circuits under one spelling
and five under the other. A driver whose home race worked at Watkins Glen and
not at Sebring would be a bug nobody could explain.
"""
import json
import os
import sys

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(_DIR, "lines_data", "nations.json")

_data = None


def load(force=False):
    global _data
    if _data is None or force:
        try:
            with open(DATA, "r", encoding="utf-8") as f:
                _data = json.load(f)
        except Exception:
            _data = {}
        _data.pop("_comment", None)
    return _data


def nations():
    """Every nationality, in the order the menu should offer them."""
    return load().get("nations") or []


def _fold(country):
    """Fold a country name for comparison.

    Strips a leading article and case. That is the whole trick, and it is here
    rather than inline because the circuit data is inconsistent about it and
    the inconsistency is invisible until a home race silently does not fire.
    """
    # ANYTHING, NOT JUST A STRING. Callers pass whatever the circuit data
    # gave them, and one of them passed a bound METHOD — `Track.country` —
    # which raised here and, being called from the filler, took the booth off
    # the air for half a race. A name-folder is not the place to be fussy
    # about types: what is not a string has no name to fold.
    if not isinstance(country, str):
        country = ""
    s = country.strip().lower()
    return s[4:] if s.startswith("the ") else s


def find(country):
    """The nation entry for a country name, or None."""
    if not country:
        return None
    key = _fold(country)
    return next((n for n in nations() if _fold(n["country"]) == key), None)


def demonym(country):
    """"Australian" — a bare noun, for use after an article."""
    n = find(country)
    return n["demonym"] if n else ""


def adjective(country):
    n = find(country)
    return n["adj"] if n else ""


def is_home(country, circuit_country):
    """Is this circuit in this driver's country?

    Both sides folded. An unknown country on either side is False rather than
    a guess: twelve of the installed circuits have no country at all — the
    fictional rF2 stock tracks, which are in no country by definition — and a
    home race at Lost Valley would be a claim about a place that does not
    exist.
    """
    if not country or not circuit_country:
        return False
    return _fold(country) == _fold(circuit_country)


def validate():
    errs = []
    seen = set()
    for i, n in enumerate(nations()):
        for field in ("country", "demonym", "adj"):
            if not n.get(field):
                errs.append("nations[%d]: missing %s" % (i, field))
        key = _fold(n.get("country", ""))
        if key in seen:
            errs.append("nations[%d]: %s appears twice" % (i, n.get("country")))
        seen.add(key)
        # A DEMONYM IS A BARE NOUN. It is used as "the young {demonym}", so an
        # article in the data reads "the young the Australian".
        if n.get("demonym", "").lower().startswith(("a ", "an ", "the ")):
            errs.append("nations[%d]: demonym carries an article" % i)
    return errs


def coverage():
    """Which circuits a home race could ever fire at, for the menu and tests."""
    try:
        import track as track_mod
    except Exception:
        return {}
    out = {}
    for slug, t in (track_mod.load() or {}).items():
        if slug.startswith("_") or not isinstance(t, dict):
            continue
        c = t.get("country")
        if c and find(c):
            out.setdefault(find(c)["country"], []).append(slug)
    return out


if __name__ == "__main__":
    bad = validate()
    print("%d nations" % len(nations()))
    cov = coverage()
    print("%d of them have at least one circuit in the knowledge base:"
          % len(cov))
    for country, slugs in sorted(cov.items(), key=lambda kv: -len(kv[1])):
        print("  %-22s %2d  %s" % (country, len(slugs),
                                   ", ".join(sorted(slugs)[:5])))
    print("validate: %s" % ("OK" if not bad else "\n  " + "\n  ".join(bad)))
