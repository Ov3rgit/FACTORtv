# rF2 Shared Memory Map Plugin — included here, and not ours

`rFactor2SharedMemoryMapPlugin64.dll`, version **3.7.15.1**, by
**TheIronWolfModding**, under the **GNU General Public License v3.0** — the full
text is beside it in `LICENSE-rF2SharedMemoryMapPlugin.txt`.

* Source: <https://github.com/TheIronWolfModding/rF2SharedMemoryMapPlugin>

## Why it is bundled

Because there is nowhere to send you. That repository has never attached a
binary to a release — every release from 3.0.0.1 to 3.7.14.2 has zero assets —
so "download the plugin" is advice that ends in a search rather than a file. The
binary here is unmodified, it is the exact build FACTORtv was developed against,
and shipping it with its licence and a link to its source is what the GPL asks
for.

`install.py` finds this folder on its own and installs it, so nobody has to know
any of the above to use the overlay.

## What FACTORtv does with it

The plugin publishes rFactor 2's telemetry, scoring and extended state as named
Windows shared-memory maps. FACTORtv opens those by name through `ctypes` and
reads them. There is no linkage, no header and no code of the plugin's in this
project — the two are independent programs sharing a memory-mapped file, which
is why the GPL applies to the plugin and not to the overlay.
