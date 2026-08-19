# Third-party components

## rF2 Shared Memory Map Plugin — required, and NOT bundled

FACTORtv reads rFactor 2 through **TheIronWolf's rF2 Shared Memory Map
Plugin**, version 3.7.15.1 or newer.

* Source and releases: <https://github.com/TheIronWolfModding/rF2SharedMemoryMapPlugin>
* Licence: **GNU General Public License v3.0**
* Copyright: TheIronWolfModding

**It is deliberately not included in this release.** Redistributing a GPL binary
is permitted and carries obligations with it — the licence text, and an offer of
the corresponding source — and a link discharges all of them while costing you
one download. `python install.py --plugin <file.dll>` will put it in the right
place once you have it.

**FACTORtv does not link against it.** The plugin publishes named Windows
shared-memory maps; this overlay opens those by name through `ctypes` and reads
them. There is no linkage, no header, and no code of the plugin's in this
project — the two programs communicate the way any two independent programs
share a memory-mapped file.

## Fonts

* **Chakra Petch** and **Michroma** — SIL Open Font License 1.1, bundled.

## Python packages

`pillow`, `edge-tts`, `miniaudio` — installed by pip, each under its own
licence. See `requirements.txt`.

## Voices

The three commentary voices and the engineer are Microsoft neural voices,
fetched at runtime by `edge-tts`. Nothing is bundled and nothing is cached in
this repository — your machine renders and caches its own audio on first run.

## Artwork

The division logos and photographs under `art/` are supplied for use with this
overlay. Marks belonging to championships and their organisers remain the
property of their owners; they are used here to label the division a driver is
racing in, and nothing in this project claims any association with them.
