"""Print what the booth would say across a synthetic 60-lap race.

Not an assertion test — a listening test. The only way to judge whether the
race flow works is to read a whole broadcast in order and see whether it
sounds like one.

    python tests/_transcript_demo.py [laps]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fakes import Booth, FakeSession, grid, run   # noqa: E402

LAPS = int(sys.argv[1]) if len(sys.argv) > 1 else 60

b = Booth()
cars = grid()
for c in cars:
    c.gap_ahead = 3.0
    c.gap_leader = 3.0 * (c.place - 1)
cars[1].gap_ahead = 0.9          # a live fight for the lead
cars[7].place, cars[7].started_place = 8, 12

s = FakeSession(cars, max_laps=LAPS, leader_laps=0, laps_left=LAPS)
run(b, s, ticks=8, step=3.0)
for lap in range(1, LAPS + 1):
    s = FakeSession(cars, max_laps=LAPS, leader_laps=lap, laps_left=LAPS - lap)
    for _ in range(10):
        run(b, s, ticks=1, step=4.0)

print("%d lines over %d laps\n" % (len(b.tts.said), LAPS))
for who, text in b.tts.said:
    print("%-8s %s" % (who, text))
