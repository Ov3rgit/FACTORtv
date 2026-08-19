# -*- coding: utf-8 -*-
"""
FACTORtv — the single entry point of the standalone build.

    FACTORtv.exe                 run the overlay
    FACTORtv.exe --install       set up this machine (plugin, art, rF2 switch)
    FACTORtv.exe --check         ...say what is missing and change nothing
    FACTORtv.exe --testrun       the overlay, writing _session_log.txt
    FACTORtv.exe --verify        is rFactor 2 publishing?
    FACTORtv.exe --voices        hear the cast without starting a session

WHY ONE EXE AND NOT FOUR
------------------------
A frozen Python build carries the interpreter, tkinter, PIL and the audio stack
with it — around 40MB before any of this project's own files. Four executables
would be four copies of that, in a zip a tester has to download over a phone
connection. So there is one binary and a first argument, and the `.bat` files are
one line each.

It also means the INSTALLER is inside the thing being installed, which removes
the last reason a tester would need Python: `--install` is the same code
`install.py` runs from source.
"""
import os
import sys


def _run():
    argv = [a.lower() for a in sys.argv[1:]]
    first = argv[0] if argv else ""

    if first in ("--install", "--setup", "install"):
        import install
        # `--check` and `--plugin <file>` are read from sys.argv by install
        # itself, so they pass straight through with nothing to translate.
        return install.main()

    if first in ("--check",):
        import install
        # A bare `--check` means "check the setup", which is the only thing here
        # there is to check.
        sys.argv = [sys.argv[0], "--check"]
        return install.main()

    if first in ("--testrun", "--log", "testrun"):
        import testrun
        return testrun.main()

    if first in ("--verify", "--plugin-check"):
        import verify_plugin
        return verify_plugin.main()

    if first in ("--voices", "--voicedemo"):
        import voicedemo
        return voicedemo.main()

    if first in ("--version", "-v"):
        import version
        print("FACTORtv %s" % version.full())
        return 0

    if first in ("--help", "-h", "/?"):
        print(__doc__.strip())
        return 0

    import factor_tv
    return factor_tv.main()


if __name__ == "__main__":
    # A FROZEN BUILD HAS NO CONSOLE TO SCROLL BACK THROUGH once it closes, and a
    # traceback that vanishes with the window is a bug report nobody can write.
    # So anything that escapes is printed and the window is held open.
    try:
        sys.exit(_run() or 0)
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        if getattr(sys, "frozen", False):
            print("")
            print("FACTORtv stopped with the error above. If you are reporting "
                  "it, run FACTORtv.exe --testrun and send _session_log.txt.")
            try:
                input("Press Enter to close...")
            except Exception:
                pass
        sys.exit(1)
