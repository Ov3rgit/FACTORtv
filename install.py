# -*- coding: utf-8 -*-
"""
FACTORtv — set up a fresh machine.

    python install.py                       do everything it can
    python install.py --plugin <file.dll>   ...and install the plugin from a file
    python install.py --check               say what is missing, change nothing

WHAT IT DOES
------------
Three things, none of which a tester should have to work out from a README:

1. **The artwork.** Division logos and the news photographs go into
   `Pictures\\Factor Overlay\\<Division>\\<Category>\\`, which is where
   `newsart.py` looks. They ship inside the release under `art/`.
2. **The shared-memory plugin.** rFactor 2 publishes NOTHING without it, so this
   finds the game, checks whether the plugin is there, and installs it from a
   file if one is handed over.
3. **Says what is still missing**, in the order it matters, with the exact paths.

WHY THE PLUGIN IS NOT IN THE ZIP
--------------------------------
It is somebody else's work under the GNU GPL v3 — TheIronWolf's rF2 Shared Memory
Map Plugin. Shipping a GPL binary is allowed and it comes with obligations
attached (the licence text, and an offer of source), and a LINK carries none of
them while costing the tester one download. So this script tells you exactly where
it goes and will install it for you once you have it:

    https://github.com/TheIronWolfModding/rF2SharedMemoryMapPlugin/releases

That is also the reason it is worth doing this way round rather than mine: the
upstream release is always the current build, and this overlay was written against
3.7.15.1.
"""
import os
import shutil
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
ART_SRC = os.path.join(_DIR, "art")
PLUGIN_NAME = "rFactor2SharedMemoryMapPlugin64.dll"
PLUGIN_URL = ("https://github.com/TheIronWolfModding/rF2SharedMemoryMapPlugin"
              "/releases")
PLUGIN_TAIL = os.path.join("Bin64", "Plugins")


def art_dest():
    """`Pictures\\Factor Overlay`, the folder `newsart.py` reads."""
    home = os.path.expanduser("~")
    return os.path.join(home, "Pictures", "Factor Overlay")


def find_game():
    """rFactor 2's install folder, or "". Asks the overlay's own finder first."""
    try:
        sys.path.insert(0, _DIR)
        import ladder as ladder_mod
        got = ladder_mod.game_root()
        if got and os.path.isdir(os.path.join(got, "Bin64")):
            return got
    except Exception:
        pass
    # The common Steam layouts, in the order they are common. A guess that is
    # checked against the disk is not a guess.
    for drive in ("C:", "D:", "E:", "F:"):
        for tail in (r"\SteamLibrary\steamapps\common\rFactor 2",
                     r"\Program Files (x86)\Steam\steamapps\common\rFactor 2",
                     r"\Steam\steamapps\common\rFactor 2"):
            p = drive + tail
            if os.path.isdir(os.path.join(p, "Bin64")):
                return p
    return ""


def copy_art(check=False):
    """Put the artwork where the overlay looks for it. Returns (copied, total)."""
    if not os.path.isdir(ART_SRC):
        print("  art: nothing bundled in this build — the overlay will draw no "
              "logos, which is a supported state")
        return (0, 0)
    dest = art_dest()
    n = done = 0
    for root, _dirs, files in os.walk(ART_SRC):
        for fn in files:
            n += 1
            src = os.path.join(root, fn)
            rel = os.path.relpath(src, ART_SRC)
            dst = os.path.join(dest, rel)
            if os.path.exists(dst):
                continue
            done += 1
            if check:
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            # NEVER OVERWRITE. A tester may have added his own photographs, and
            # this script running twice must not throw them away.
            shutil.copy2(src, dst)
    where = "would copy" if check else "copied"
    print("  art: %s %d of %d file(s) into %s" % (where, done, n, dest))
    return (done, n)


def plugin_state(game):
    """(installed, path). An empty game folder answers (False, "")."""
    if not game:
        return (False, "")
    p = os.path.join(game, PLUGIN_TAIL, PLUGIN_NAME)
    return (os.path.isfile(p), p)


def install_plugin(game, src, check=False):
    ok, dst = plugin_state(game)
    if not dst:
        print("  plugin: rFactor 2 not found, so there is nowhere to put it")
        return False
    if not os.path.isfile(src):
        print("  plugin: %s is not a file" % src)
        return False
    if check:
        print("  plugin: would install %s -> %s" % (os.path.basename(src), dst))
        return True
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if ok:
        # KEEP WHAT WAS THERE. Somebody else's plugin build may be newer than the
        # one being handed over, and an overlay installer that silently downgrades
        # a component of the game is not one anybody should trust.
        shutil.copy2(dst, dst + ".backup")
        print("  plugin: existing copy kept as %s.backup" % PLUGIN_NAME)
    shutil.copy2(src, dst)
    print("  plugin: installed -> %s" % dst)
    return True


def main():
    check = "--check" in sys.argv
    src = ""
    if "--plugin" in sys.argv:
        i = sys.argv.index("--plugin")
        if i + 1 < len(sys.argv):
            src = sys.argv[i + 1]
    try:
        sys.path.insert(0, _DIR)
        import version
        head = "FACTORtv %s" % version.full()
    except Exception:
        head = "FACTORtv"
    print("%s — setup%s\n" % (head, " (check only)" if check else ""))

    game = find_game()
    print("  game: %s" % (game or "NOT FOUND — is rFactor 2 installed?"))
    copy_art(check=check)
    ok, dst = plugin_state(game)
    if src:
        install_plugin(game, src, check=check)
        ok, dst = plugin_state(game)
    elif ok:
        print("  plugin: already installed at %s" % dst)
    else:
        print("  plugin: NOT INSTALLED")
        print("      1. download it:  %s" % PLUGIN_URL)
        print("      2. put %s in:" % PLUGIN_NAME)
        print("         %s" % (os.path.join(game, PLUGIN_TAIL) if game
                              else r"<rFactor 2>\Bin64\Plugins"))
        print("      3. or re-run:    python install.py --plugin <the .dll>")
        print("      ...then enable it in rF2's launcher: Settings -> Plugins")

    print("\n  next:")
    print("      pip install -r requirements.txt")
    print("      python verify_plugin.py        (is the game publishing?)")
    print("      python factor_tv.py           (or Start FACTORtv.bat)")
    print("\n  Read SETUP.md. The two things that break a first run are the "
          "plugin\n  above and the voices, which need an internet connection.")


if __name__ == "__main__":
    main()
