# -*- coding: utf-8 -*-
"""
FACTORtv — build the release archive.

    python tools_package.py            -> dist/FACTORtv-0.0.1-beta.zip
    python tools_package.py --check    -> say what would go in, write nothing

WHAT THIS IS FOR
----------------
A tester's copy has to contain everything the overlay needs and NOTHING that
belongs to this machine. Those are two different lists and getting the second one
wrong is the expensive mistake: the career store, the settings, the shuffle bag,
the learned mod names and 280MB of rendered audio are all sitting in the working
folder, and a zip built with a wildcard ships somebody else's championship along
with the code.

So the manifest is EXPLICIT. Every file that goes in is named or matched by a
narrow rule, and anything unrecognised is reported rather than included — a new
file added next month will show up in `--check` as unclassified instead of
silently arriving in a release.

WHAT IS DELIBERATELY ABSENT
---------------------------
* `stings/` and `_voice_cache/` — 280MB of rendered speech, rebuilt on first run.
* The career store, settings and shuffle bag — see above.
* `_modnames.json` — what THIS rF2 install calls each mod. Correct here and
  wrong everywhere else; it rebuilds itself from the game's own cache.
* The division logos and news photographs. They are the author's own files, and
  several are marks belonging to other people — see SETUP.md. The overlay treats
  a missing art folder as a supported state and draws no logo.
"""
import io
import os
import sys
import zipfile

import version

_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(_DIR, "dist")

# Everything the overlay reads at runtime, by extension, at the top level.
CODE_EXT = (".py",)
ASSET_EXT = (".ttf", ".wav")

# Named top-level files that are neither code nor obviously an asset.
EXTRA = ("requirements.txt", "README.md", "SETUP.md", "THIRD_PARTY.md",
         "RELEASE_NOTES.md", ".gitignore")

# Whole directories that ship as they are.
# THE ARTWORK SHIPS. The user's call, and the release is free: the division
# logos and the news photographs go in `art/`, and `install.py` copies them into
# the tester's own Pictures folder — the overlay reads them from there, so a
# tester who adds his own is not fighting the installer.
DIRS = ("lines_data", "tests", "art")

# Top-level images the UI draws. Named by PREFIX rather than by extension so a
# screenshot dropped in the folder cannot ride along.
IMAGE_PREFIX = ("icon_", "Factor")

# IN THE REPOSITORY BUT NOT IN A TESTER'S ZIP. The handover is 4,500 lines of
# why-it-is-like-this written for whoever picks the project up next; it belongs in
# git and it is not something a play tester should have to receive to run a
# broadcast overlay.
REPO_ONLY = ("HANDOVER.md", "NEXT_SESSION.md")

# Never, whatever else matches.
NEVER = (
    "_settings.json", "_career.json", "_career.json.v6bak", "_bag.json",
    "_modnames.json", "_session_log.txt", "_transcript.log",
    "_career_preview.txt", "_menu_old.txt",
)
NEVER_DIRS = ("careers", "stings", "_voice_cache", "_voice_tmp", "__pycache__",
              "dist", "build", ".git")


def _skip_dir(rel):
    parts = rel.replace("\\", "/").split("/")
    return any(p in NEVER_DIRS for p in parts)


def collect():
    """(included, skipped, unclassified) — three lists of relative paths."""
    inc, skip, odd = [], [], []
    for root, dirs, files in os.walk(_DIR):
        dirs[:] = [d for d in dirs if d not in NEVER_DIRS]
        for fn in sorted(files):
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, _DIR)
            if _skip_dir(rel):
                continue
            top = rel.replace("\\", "/").split("/")[0]
            if fn in NEVER or fn in REPO_ONLY:
                skip.append(rel)
                continue
            if top in DIRS:
                # A GENERATED ARTEFACT IS RECOGNISED BY ITS EXTENSION, NOT BY ITS
                # NAME. The first rule here read "starts with an underscore",
                # which threw out `tests/_transcript_demo.py` and
                # `tests/_season_demo.py` — two of the preview tools the handover
                # tells the next person to run.
                if top == "art":
                    inc.append(rel)       # every file under art/ IS the payload
                else:
                    (skip if fn.endswith((".png", ".txt", ".log")) else
                     inc).append(rel)
                continue
            if os.sep in rel:
                odd.append(rel)          # a subfolder nobody has classified
                continue
            if fn.startswith("_") and fn.endswith((".png", ".txt", ".json")):
                skip.append(rel)
            elif fn.endswith(CODE_EXT) or fn.endswith(ASSET_EXT):
                inc.append(rel)
            elif fn.startswith(IMAGE_PREFIX):
                inc.append(rel)
            elif fn in EXTRA:
                inc.append(rel)
            elif fn.endswith(".bat"):
                inc.append(rel)
            else:
                odd.append(rel)
    return inc, skip, odd


def main():
    inc, skip, odd = collect()
    name = "FACTORtv-%s.zip" % version.full()
    print("FACTORtv %s — %d files to ship" % (version.full(), len(inc)))
    size = sum(os.path.getsize(os.path.join(_DIR, r)) for r in inc)
    print("  uncompressed: %.1f MB" % (size / 1048576.0))
    print("  left out:     %d file(s) of local state" % len(skip))
    for r in skip:
        print("      - %s" % r)
    if odd:
        # UNCLASSIFIED IS NOT THE SAME AS EXCLUDED, and it must be loud. A file
        # the manifest has never heard of is either a new asset that needs
        # shipping or private data that must not be — and only a person can say
        # which.
        print("  UNCLASSIFIED — decide before releasing:")
        for r in odd:
            print("      ? %s" % r)
    if "--check" in sys.argv:
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in inc:
            # EVERYTHING UNDER ONE FOLDER, so unzipping cannot scatter thirty
            # loose files into whatever directory the tester happened to be in.
            z.write(os.path.join(_DIR, rel),
                    os.path.join("FACTORtv-%s" % version.full(), rel))
    print("wrote %s  (%.1f MB compressed)"
          % (path, os.path.getsize(path) / 1048576.0))
    verify(path, inc)


def verify(path, inc):
    """Re-open the archive and prove every file in it matches the source.

    ASKED DIRECTLY — *"is the version I have now and the shipped version byte
    identical?"* — and it is the sort of question that deserves a check rather
    than an assurance. A zip is written by a loop, and a loop that skips a file,
    truncates one or picks up a half-saved editor buffer produces an archive that
    looks perfectly healthy from the outside.

    So: read every member back out of the finished archive, hash it, and hash the
    file on disk beside it. Anything that differs is named. This is cheap (a few
    megabytes of SHA-256) and it turns "it should be the same" into "these 181
    files are the same".
    """
    import hashlib
    root = "FACTORtv-%s" % version.full()
    bad, missing = [], []
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        for rel in inc:
            member = os.path.join(root, rel).replace("\\", "/")
            if member not in names:
                missing.append(rel)
                continue
            with z.open(member) as f:
                zipped = hashlib.sha256(f.read()).hexdigest()
            with open(os.path.join(_DIR, rel), "rb") as f:
                ondisk = hashlib.sha256(f.read()).hexdigest()
            if zipped != ondisk:
                bad.append(rel)
        extra = sorted(n for n in names
                       if os.path.relpath(n, root).replace("/", os.sep)
                       not in set(inc))
    if bad or missing or extra:
        for r in missing:
            print("  MISSING from the archive: %s" % r)
        for r in bad:
            print("  DIFFERS from the source:  %s" % r)
        for r in extra:
            print("  IN THE ARCHIVE AND NOT IN THE MANIFEST: %s" % r)
        print("  VERIFY FAILED — do not ship this archive")
        return False
    print("  verified: all %d files byte-identical to this working copy, and "
          "nothing else in the archive" % len(inc))
    return True


if __name__ == "__main__":
    main()
