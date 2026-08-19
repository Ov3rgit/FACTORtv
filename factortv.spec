# -*- mode: python ; coding: utf-8 -*-
"""
FACTORtv — the standalone build.

    pyinstaller --noconfirm factortv.spec       -> dist/FACTORtv/FACTORtv.exe

WHY A SPEC FILE AND NOT A COMMAND LINE
--------------------------------------
Three things about this build are not defaults, and every one of them was a real
failure in the predecessor (RacerTV) before it was written down:

1. `contents_directory='.'` — PyInstaller 6 puts bundled data in an `_internal`
   subfolder by default. EVERY MODULE IN THIS PROJECT resolves its data relative
   to `sys.executable` when frozen (`lines_data/`, `art/`, `plugin/`, the fonts),
   so with the default layout the overlay starts and finds no dialogue at all.
   This flattens it: the exe and its data sit in one folder, exactly as they do
   when running from source.

2. `PIL._tkinter_finder` is a HIDDEN IMPORT. Pillow reaches tkinter through it
   dynamically, so the analysis cannot see it — and without it every
   `ImageTk.PhotoImage` call fails at runtime, which is the instrument, the
   division logos and every news photograph.

3. The data files are listed EXPLICITLY rather than by glob. A wildcard over this
   folder would sweep up `_settings.json`, `careers/`, `_career.json` and 280MB
   of rendered speech — the author's own career, shipped to a stranger. Same
   reasoning as `tools_package.py`, which has the same list for the same reason.

ONE BINARY, MANY ENTRY POINTS. `main.py` dispatches on the first argument, so the
installer, the logging run and the voice demo are all the same executable —
four separate builds would be four copies of a 40MB interpreter.
"""
import os

block_cipher = None
HERE = os.path.abspath(os.getcwd())


def tree(folder):
    """Every file under `folder`, mapped to the same relative place beside the
    exe. Used for the three folders that are entirely payload."""
    out = []
    for root, _dirs, files in os.walk(os.path.join(HERE, folder)):
        if "__pycache__" in root:
            continue
        for fn in files:
            src = os.path.join(root, fn)
            dest = os.path.relpath(root, HERE)
            out.append((src, dest))
    return out


datas = []
datas += tree("lines_data")        # every line the booth can say
datas += tree("art")               # division logos and news photographs
datas += tree("plugin")            # the shared-memory plugin and its licence
datas += [(os.path.join(HERE, f), ".") for f in (
    "ChakraPetch-Bold.ttf", "ChakraPetch-Regular.ttf",
    "ChakraPetch-SemiBold.ttf", "Michroma-Regular.ttf",
    "Factor.png",
    "icon_engineer.png", "icon_helmet_1.png", "icon_helmet_2.png",
    "icon_helmet_3.png", "icon_helmet_4.png", "icon_helmet_5.png",
    "icon_helmet_6.png", "icon_helmet_7.png", "icon_helmet_8.png",
    "icon_helmet_9.png",
    "requirements.txt", "SETUP.md", "THIRD_PARTY.md", "RELEASE_NOTES.md",
) if os.path.exists(os.path.join(HERE, f))]

a = Analysis(
    ["main.py"],
    pathex=[HERE],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # Pillow finds tkinter dynamically; see the note above.
        "PIL._tkinter_finder",
        # Reached by name from `main.py`'s dispatch, so the analysis cannot see
        # them from the import graph either.
        "factor_tv", "testrun", "install", "verify_plugin", "voicedemo",
        # THE VOICES. `tts.py` imports edge-tts inside a try block, so the
        # analysis never sees it and a frozen build silently reports
        # `_HAVE_EDGE = False` — which means every line falls back to the robotic
        # Windows voice. That is the single worst way this build could fail,
        # because it looks like the product rather than like a packaging bug.
        "edge_tts", "aiohttp", "certifi",
        # ...AND PLAYBACK. `miniaudio` is a cffi binding, so it needs the
        # `_cffi_backend` C extension that nothing imports by name.
        "_cffi_backend", "cffi", "miniaudio",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Nothing in this project imports them, and they are large.
        "numpy", "matplotlib", "pytest", "setuptools", "pip",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FACTORtv",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # THE CONSOLE STAYS, for a beta. It carries the plugin status, the VOICES
    # line that says whether the neural voices were reached, and any traceback —
    # and a tester with a silent window has nothing to send back. It can be
    # minimised; the overlay's own panels are separate always-on-top windows.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    # TRAP 1, AND IT IS SET ON *EXE*, NOT ON COLLECT. PyInstaller 6 reads this
    # off the EXE instance (`COLLECT.__init__` does
    # `self.contents_directory = arg.contents_directory`), so setting it on
    # COLLECT is accepted silently and does nothing — the first build put every
    # data file in `_internal/` and the overlay would have found no dialogue at
    # all. Flattened here so the exe and its data sit in one folder, exactly as
    # they do when running from source.
    contents_directory=".",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FACTORtv",
)
