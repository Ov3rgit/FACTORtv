# -*- coding: utf-8 -*-
"""
FACTORtv — one place that says what this build is.

    import version; version.VERSION

WHY A FILE AND NOT A CONSTANT IN `factor_tv`
--------------------------------------------
The packager, the README and the overlay all have to agree, and three copies of
a version string is three chances to ship a build that lies about itself. This
one is read by `tools_package.py` to name the archive, so the zip and the code
inside it cannot disagree.

THE NUMBER MEANS WHAT IT SAYS. 0.0.1 is the first build that has ever left this
machine. It is a beta because the features are complete and the SESSIONS are not
— a great deal of this product has been verified by twenty-five test suites and
rendered previews rather than by being driven, and every serious bug this project
has had was found by driving it. A play tester is the point.
"""

VERSION = "0.0.1"
STAGE = "beta"

# What a tester is actually being asked to look at, in the order it matters.
# Kept here so the release notes and the setup guide cannot drift from it.
KNOWN_GAPS = (
    "The safety car sequence, the pass calls and the season-finale news have "
    "been heard in a test harness but not yet in a full live race.",
    "Division art and news photographs are the author's own files and are not "
    "shipped; without them the overlay simply draws no logo, which is a "
    "supported state rather than a fault.",
    "The 2020 test programme needs the F1 2020 by A&M mod from the Steam "
    "Workshop. Without it the development year still runs on letters alone.",
)


def full():
    """"0.0.1-beta", the string a human should see."""
    return "%s-%s" % (VERSION, STAGE) if STAGE else VERSION
