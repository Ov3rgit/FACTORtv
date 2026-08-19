"""Anachronism sweep: can any line reach a car that lacks the thing it names?

The checker's word->capability map is the fiddly part. Several obvious-looking
mappings are WRONG and produce false alarms:

  * "tow" / "slipstream" is NOT the `draft` capability. Every car with
    bodywork has a slipstream; `draft` means pack racing on a superspeedway.
  * "restart" the noun (a race resuming after a caution) is not the
    `restarts` capability (the NASCAR-style procedure).
  * "rear wing" is only DRS if it is opening. Sitting behind someone's rear
    wing just means they have one — which is what `wings` is for.
  * NEGATION inverts the claim entirely. "No traction control to save him
    there" is CORRECT on a car without traction control — it is the whole
    point of the line. Flagging it was the checker misreading English, not
    the pool being wrong.

So the map below tests only words that genuinely IMPLY a capability, and
negated mentions are skipped.
"""
import re
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import era as era_mod, lines as lines_mod

# (phrase, capability it genuinely requires)
IMPLIES = [
    ("drs", "drs"),
    ("rear wing opens", "drs"),
    ("rear wing open", "drs"),
    ("push-to-pass", "ptp"),
    ("deployment", "ers"),
    ("energy harvest", "ers"),
    ("battery", "ers"),
    ("stage points", "stages"),
    ("active suspension", "active_suspension"),
    ("grooved", "grooved"),
    ("turbo lag", "turbo"),
    ("traction control", "tc"),
    ("rear wing", "wings"),
    ("refuel", "refuel"),
]

CLASSES = [
    ("F1 Test 2025", "Max Verstappen"),
    ("FSR 2026", "Alice Jackson"),
    ("Formula 1 1992 Season by ASRC", "Nigel Mansell"),
    ("StockCar 2018 X Series", "Ted Moser"),
    ("", "NASCAR 2023 Next Gen CUP"),
    ("GT500", "HSV-010 GT500 2013"),
    ("IndyCar_2014_Honda", "Dallara DW12"),
    ("", "Tatuus_F4_2018"),
    ("", "March_M761_1976"),
    ("", "Brabham_1966"),
    ("National", "Mazda 787B"),
]

leaks = []
checked = 0
print("\nANACHRONISM SWEEP")
for cls, nm in CLASSES:
    e = era_mod.classify(cls, nm)
    n = 0
    for pool in lines_mod.stats():
        for c in lines_mod.candidates(pool, e):
            n += 1
            t = c["t"].lower()
            for phrase, cap in IMPLIES:
                if phrase not in t:
                    continue
                # "no <thing>" / "without <thing>" asserts the ABSENCE, so the
                # line is only legal when the car genuinely lacks it.
                negated = re.search(r"\b(no|without|never any)\s+" +
                                    re.escape(phrase), t)
                if negated:
                    if e.has(cap):
                        leaks.append((e.key, pool, "NOT " + cap, c["t"]))
                elif not e.has(cap):
                    leaks.append((e.key, pool, cap, c["t"]))
    checked += n
    print("  %-26.26s %-12s %4d legal lines" % (e.label, e.key, n))

print("\n  %d lines checked across %d classes" % (checked, len(CLASSES)))
if leaks:
    print("  %d LEAK(S):" % len(leaks))
    for k, pool, cap, t in leaks[:20]:
        print("    %-12s %-18s needs %-18s %r" % (k, pool, cap, t[:52]))
else:
    print("  no anachronisms.")

# Every class must have enough to say to survive a race.
thin = []
for cls, nm in CLASSES:
    e = era_mod.classify(cls, nm)
    for pool in ("overtake", "battle", "analysis", "win", "start"):
        n = len(lines_mod.candidates(pool, e))
        if n < 5:
            thin.append((e.key, pool, n))
print()
if thin:
    print("  THIN POOLS (fewer than 5 legal lines):")
    for k, pool, n in thin:
        print("    %-12s %-12s %d" % (k, pool, n))
else:
    print("  every class has 5+ lines in each core pool.")

fails = len(leaks) + len(thin)
print(chr(10) + "CHUCK NEVER CLAIMS TO HAVE DRIVEN THE CAR ON SCREEN")
# He is a NASCAR Cup champion who raced stock cars 1985-2006. He has never
# driven a Formula One car, and on an archive race he was not even there —
# so "I remember the wheel fighting you everywhere" about a 1988 F1 car is
# false twice over. The observation is always allowed; the memory is not,
# unless the line is explicitly gated to his own discipline.
import glob, os, re, json, io as _io
CLAIM = re.compile(r"(i remember|i raced|i ran a|i drove|when i drove|"
                   r"i had one|back in my day i)", re.I)
claims = []
for f in glob.glob(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "lines_data", "*.json")):
    d = json.load(_io.open(f, encoding="utf8"))
    for cat, pool in d.items():
        if not isinstance(pool, list) or cat.startswith("_"):
            continue
        for e in pool:
            if isinstance(e, dict) and CLAIM.search(e.get("t", ""))                     and e.get("disc") != ["stock"]:
                claims.append((os.path.basename(f), cat, e["t"][:50]))
if claims:
    fails += 1
    print("  [FAIL] a line has him remembering a car he never drove  %s"
          % str(claims[:2]))
else:
    print("  [ OK ] no line has him remembering a car he never drove")

print("\n" + ("FAILED: %d" % fails if fails else "ALL PASSED"))
sys.exit(1 if fails else 0)
