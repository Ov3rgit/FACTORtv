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
import json
import os
import shutil
import subprocess
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


# rF2'S OWN PLUGIN SWITCH. A DLL in Bin64\Plugins is a plugin the game has
# NOTICED; it does nothing until it is also enabled, and this is where rF2 keeps
# that. Copying the file is only half the job.
PLUGIN_CFG = os.path.join("UserData", "player", "CustomPluginVariables.JSON")

# THE KEY HAS A LEADING SPACE. `" Enabled"`, not `"Enabled"` — that is what rF2
# writes and what it reads back, and a copy without the space is a setting the
# game ignores while looking perfectly correct in a text editor.
ENABLED_KEY = " Enabled"

# What a fresh entry looks like. Only the switch and the fast read path, because
# an installer that quietly turns on somebody else's debug options has overstepped.
PLUGIN_DEFAULTS = {ENABLED_KEY: 1, "EnableDirectMemoryAccess": 1}


def enable_plugin(game, check=False):
    """Switch the plugin on in rF2's own config. Returns (ok, message).

    THE SECOND STEP NOBODY DOCUMENTS. Copying the DLL is half of it: rF2 lists a
    newly-seen plugin as DISABLED and publishes nothing until it is switched on,
    so a tester who follows every instruction still ends up with an overlay that
    says it is waiting for the game. That is the single most likely support
    question this release will produce, and it is one value in a JSON file.
    """
    if not game:
        return (False, "rFactor 2 not found")
    path = os.path.join(game, PLUGIN_CFG)
    try:
        cfg = {}
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                cfg = json.load(f)
        blk = cfg.get(PLUGIN_NAME)
        if not isinstance(blk, dict):
            # Never launched, or a profile that has not seen this plugin. The
            # game READS this file; it does not require having written it.
            blk = dict(PLUGIN_DEFAULTS)
        if int(blk.get(ENABLED_KEY) or 0) == 1:
            return (True, "already on in rF2's own config")
        if check:
            return (True, "would switch it on in %s" % PLUGIN_CFG)
        blk[ENABLED_KEY] = 1
        cfg[PLUGIN_NAME] = blk
        if os.path.isfile(path):
            # A BACKUP FIRST. This is the game's file, not ours, and it carries
            # every other plugin's settings with it.
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                before = f.read()
            with open(path + ".factortv.bak", "w", encoding="utf-8") as f:
                f.write(before)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return (True, "switched ON (close rF2 first, or it will write over this)")
    except Exception as e:
        return (False, "could not edit %s — do it in rF2's launcher: %s"
                % (PLUGIN_CFG, e))


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


def deps(check=False):
    """Install the three Python packages, so ONE RUN IS THE WHOLE SETUP.

    `--no-deps` skips it, because anybody running this inside a managed
    environment has his own opinion about pip and is entitled to it. A failure
    here is reported and survived: everything else this script did is still
    valid, and the one command that fixes it is printed rather than implied.
    """
    if "--no-deps" in sys.argv:
        print("  packages: skipped (--no-deps)")
        return True
    req = os.path.join(_DIR, "requirements.txt")
    if not os.path.isfile(req):
        return True
    try:
        import PIL, edge_tts, miniaudio            # noqa: F401
        print("  packages: pillow, edge-tts and miniaudio already installed")
        return True
    except Exception:
        pass
    if check:
        print("  packages: would run pip install -r requirements.txt")
        return True
    print("  packages: installing pillow, edge-tts, miniaudio ...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                               "-r", req])
        print("  packages: done")
        return True
    except Exception as e:
        print("  packages: FAILED (%s)" % e)
        print("      run it yourself:  pip install -r requirements.txt")
        return False


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

    if ok:
        # THE SWITCH, not just the file. Reported either way, because "installed"
        # and "on" are two different states, and only one of them publishes data.
        _on, _why = enable_plugin(game, check=check)
        print("  plugin switch: %s" % _why)
    deps(check=check)
    # ONE RUN HAS TO BE ENOUGH. If the plugin was already installed when this
    # script ran — which is the normal case if the tester does that first — then
    # everything above is now done, and the closing lines should say what to DO
    # rather than hand over a second list of chores.
    ready = bool(ok) and os.path.isdir(art_dest())
    print("")
    if ready:
        print("  READY. Start rFactor 2, load a session, and run:")
        print("      Start FACTORtv.bat          (or: python factor_tv.py)")
        print("")
        print("  Reporting a bug? Use  TEST RUN (logs a session).bat  instead")
        print("  and send me _session_log.txt — it is worth more than a "
              "description.")
    else:
        print("  NOT READY — deal with the plugin lines above, then run this "
              "again.")
        print("      python verify_plugin.py     is rF2 publishing yet?")
    print("")
    print("  The two things that break a first run are the plugin above and the")
    print("  voices, which need an internet connection. Both are in SETUP.md.")


if __name__ == "__main__":
    main()
