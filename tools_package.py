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
DIRS = ("lines_data", "tests", "art", "plugin")

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


# ---------------------------------------------------------------------------
# THE ONE FILE THAT IS REWRITTEN ON THE WAY INTO AN ARCHIVE
#
# `lines_data/mynames.json` is the author's own list of driver names — the career
# menu cannot take typed input (the overlay never holds the keyboard), so the
# names a player can race under live in a file he edits. Shipping the author's
# list means a tester picking a name from somebody else's career.
#
# So the release carries the TESTER'S name instead, and the working copy keeps
# the author's. Substituted here rather than by editing the file, because the
# file is used every day on this machine and a build step must not disturb it.
#
# IT IS STILL VERIFIED. The check below compares the archive against this
# substitution rather than against the file on disk, so "byte-identical" stays a
# real claim and this one file is named in the report.
RELEASE_NAMES = ("Paul Van Rooyen",)
MYNAMES = os.path.join("lines_data", "mynames.json")


def release_overrides():
    """{relative path: bytes} — what an archive carries instead of the file."""
    import json
    src = os.path.join(_DIR, MYNAMES)
    try:
        with io.open(src, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    data["names"] = list(RELEASE_NAMES)
    body = json.dumps(data, indent=1, ensure_ascii=False) + chr(10)
    return {MYNAMES: body.encode("utf-8")}


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
                if top in ("art", "plugin"):
                    inc.append(rel)       # these folders ARE the payload
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


# THE STANDALONE BUILD. `dist_exe/FACTORtv` as PyInstaller leaves it, minus
# anything a test run left behind — a tester should not receive my rendered audio
# or my session logs, and `_voice_cache` alone would double the download.
EXE_DIR = os.path.join(_DIR, "dist_exe", "FACTORtv")
EXE_NEVER = ("_settings.json", "_career.json", "_bag.json", "_modnames.json",
             "_session_log.txt", "_transcript.log")
EXE_NEVER_DIRS = ("_voice_cache", "_voice_tmp", "stings", "careers")


def package_exe():
    """Zip the standalone build. Returns the path, or "" if it is not built.

    NO PYTHON, NO PIP, NO DEPENDENCIES. The whole point of this archive is that a
    tester unzips it, double-clicks INSTALL.bat and races — so it must not carry
    a single file that only makes sense on the machine that built it.
    """
    if not os.path.isdir(EXE_DIR):
        print("no standalone build — run:")
        print("    python -m PyInstaller --noconfirm --distpath dist_exe "
              "--workpath build factortv.spec")
        return ""
    name = "FACTORtv-%s-standalone.zip" % version.full()
    root = "FACTORtv-%s" % version.full()
    files, dropped = [], []
    for dirpath, dirs, fns in os.walk(EXE_DIR):
        dirs[:] = [d for d in dirs if d not in EXE_NEVER_DIRS]
        for fn in fns:
            rel = os.path.relpath(os.path.join(dirpath, fn), EXE_DIR)
            if fn in EXE_NEVER or fn.endswith(".log"):
                dropped.append(rel)
                continue
            files.append(rel)
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    over = release_overrides()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            member = os.path.join(root, rel)
            key = rel.replace("/", os.sep)
            if key in over:
                z.writestr(member, over[key])
            else:
                z.write(os.path.join(EXE_DIR, rel), member)
    if over:
        print("  substituted for the release: %s -> %s"
              % (", ".join(sorted(over)), ", ".join(RELEASE_NAMES)))
    raw = sum(os.path.getsize(os.path.join(EXE_DIR, r)) for r in files)
    print("FACTORtv %s STANDALONE — %d files" % (version.full(), len(files)))
    print("  uncompressed: %.1f MB" % (raw / 1048576.0))
    if dropped:
        print("  left out %d file(s) of local state: %s"
              % (len(dropped), ", ".join(dropped[:4])))
    print("wrote %s  (%.1f MB compressed)"
          % (path, os.path.getsize(path) / 1048576.0))
    # THE SAME PROOF THE SOURCE ARCHIVE GETS. A build nobody verified is a build
    # nobody should send.
    import hashlib
    bad = []
    with zipfile.ZipFile(path) as z:
        for rel in files:
            member = os.path.join(root, rel).replace(chr(92), "/")
            with z.open(member) as f:
                a = hashlib.sha256(f.read()).hexdigest()
            key = rel.replace("/", os.sep)
            if key in over:
                b = hashlib.sha256(over[key]).hexdigest()
            else:
                with open(os.path.join(EXE_DIR, rel), "rb") as f:
                    b = hashlib.sha256(f.read()).hexdigest()
            if a != b:
                bad.append(rel)
    if bad:
        for r in bad:
            print("  DIFFERS: %s" % r)
        print("  VERIFY FAILED — do not ship this archive")
        return ""
    print("  verified: all %d files byte-identical to the build" % len(files))
    return path


def main():
    if "--exe" in sys.argv:
        package_exe()
        return
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
    over = release_overrides()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in inc:
            # EVERYTHING UNDER ONE FOLDER, so unzipping cannot scatter thirty
            # loose files into whatever directory the tester happened to be in.
            member = os.path.join("FACTORtv-%s" % version.full(), rel)
            if rel in over:
                z.writestr(member, over[rel])
            else:
                z.write(os.path.join(_DIR, rel), member)
    if over:
        print("  substituted for the release: %s -> %s"
              % (", ".join(sorted(over)), ", ".join(RELEASE_NAMES)))
    print("wrote %s  (%.1f MB compressed)"
          % (path, os.path.getsize(path) / 1048576.0))
    verify(path, inc, over)


def verify(path, inc, over=None):
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
    over = over or {}
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
            if rel in over:
                # Verified against what it is MEANT to be, not against the file
                # on disk — which is the author's list and is supposed to differ.
                ondisk = hashlib.sha256(over[rel]).hexdigest()
            else:
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
