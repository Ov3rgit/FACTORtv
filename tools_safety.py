# -*- coding: utf-8 -*-
"""Writes lines_data/booth_safety.json — the safety car sequence.

Every beat here is a STATE rF2 publishes and the overlay had never read:
mYellowFlagState 1..6 plus the FCY game phase. The user's log holds the whole
machine ticking over across six minutes and twenty-two seconds while the booth
said one line about "waved yellows" and then went quiet.

ERA-NEUTRAL BY CONSTRUCTION. Nothing here names a piece of equipment or a
regulation, because a bunched field behind a pace car is the same event in 1966
and in 2025 — the same rule `booth_story.json` follows, and it is what lets
Brett deliver all of it.

NOTHING HERE CLAIMS TO KNOW WHY. The overlay knows a full course yellow is out;
it does not know whether somebody is in the wall at turn four or a dog is on the
circuit. Lines that guess at a cause would be wrong most of the time, and the
one thing this booth may never be is confidently wrong.
"""
import io
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "lines_data")

PLAY, ANALYST = 2, 2

DATA = {
    "_comment": (
        "THE SAFETY CAR. Beats keyed off rF2's own mYellowFlagState: 1 pending, "
        "2 pit lane closed, 3 pit lane open for the lead lap, 4 pit lane open, "
        "5 the safety car's last lap, 6 resume. Nothing here names a cause — the "
        "overlay knows the field has been neutralised, not why — and nothing "
        "names equipment or a decade, so every line is legal in any era and "
        "Brett delivers all of it."),

    # 1. DEPLOYED. The biggest call in the set: everything about the race just
    # changed, and a viewer needs to be told in one sentence.
    "sc_out": [
        {"t": "Safety car! The safety car is out, and this race has just been reset.", "i": 3},
        {"t": "And here comes the safety car. Everything anybody had built up out there has just gone.", "i": 3},
        {"t": "Full course yellow. The safety car is deployed and the field will be gathered up behind it.", "i": 3},
        {"t": "Safety car deployed. Whatever the order was, it is about to be a queue.", "i": 3},
        {"t": "We are under a full course yellow. Slow down, hold position, and wait to be told.", "i": 2},
        {"t": "The safety car is out. Nobody passes anybody until we are green again.", "i": 2},
    ],

    # Chuck's reply to the deployment: what it MEANS. This is the beat the user
    # is missing — the sting-and-a-name is a fact, and the analyst is the one
    # who says what it costs.
    "sc_out_why": [
        {"t": "This is the moment a comfortable afternoon becomes a fight again. Every gap anybody has earned out there is about to be worth nothing at all.", "i": 2, "who": "ANALYST"},
        {"t": "The leader will hate this more than anybody. He has spent the whole race building something and it is being handed back to the man behind him.", "i": 2, "who": "ANALYST"},
        {"t": "Watch what this does to the men who were struggling. A safety car is the closest thing this sport has to a second chance, and some of them have just been given one.", "i": 2, "who": "ANALYST"},
        {"t": "The hard part now is temperature. Tyres and brakes go off behind a safety car, and the restart asks everything of a car that has been crawling for two laps.", "i": 2, "who": "ANALYST"},
        {"t": "Nobody enjoys this. You cannot warm the car, you cannot see what is happening in front, and you know the whole race is about to start again from wherever you happen to be.", "i": 2, "who": "ANALYST"},
    ],

    # 2. THE PIT LANE IS CLOSED. Real, and only rF2 knows it.
    "sc_pits_shut": [
        {"t": "The pit lane is closed. Anybody who wanted to stop has just been told no.", "i": 2},
        {"t": "Pit lane closed under the safety car — you stay out there whether you like it or not.", "i": 2},
        {"t": "And the pits are shut. That is a problem for anybody who was a lap away from stopping.", "i": 2},
    ],

    # 4. ...AND OPEN AGAIN. The strategic beat of the whole period.
    "sc_pits_open": [
        {"t": "The pit lane is open. If anybody is coming in, it is now.", "i": 3},
        {"t": "Pits are open — and this is the cheapest stop anybody will get all afternoon.", "i": 3},
        {"t": "Pit lane open. Watch the entry, because a stop under a safety car costs a fraction of what it costs under green.", "i": 3},
        {"t": "The pits are open behind the safety car, and every team on the wall is doing the same arithmetic right now.", "i": 2},
    ],

    # 5. THE SAFETY CAR IS IN THIS LAP. The tension beat.
    "sc_ending": [
        {"t": "The safety car is in at the end of this lap. Get ready — this is where a race is won and lost.", "i": 3},
        {"t": "Safety car in this lap. The leader controls the restart from here and everybody behind him knows it.", "i": 3},
        {"t": "This is the last lap behind the safety car. Tyres are cold, brakes are cold, and the racing is about to begin again.", "i": 3},
        {"t": "Safety car in. Whatever happens at the restart, it happens in the next couple of corners.", "i": 3},
    ],

    "sc_ending_why": [
        {"t": "The man in front has one job and it is a hard one: keep the pack behind him until he decides, and then be gone before anybody can react.", "i": 2, "who": "ANALYST"},
        {"t": "This is the most dangerous ninety seconds of any race. Cold tyres, a bunched field, and eleven drivers who all think they can win it from here.", "i": 3, "who": "ANALYST"},
        {"t": "Everybody will be weaving, getting heat into the tyres, watching the car in front rather than the flag. That is how restarts go wrong.", "i": 2, "who": "ANALYST"},
    ],

    # 6. GREEN.
    "sc_green": [
        {"t": "Green flag! We are racing again!", "i": 4},
        {"t": "And it is green — the safety car has gone and this race is live!", "i": 4},
        {"t": "Green, green, green! Everybody is free to race.", "i": 4},
        {"t": "The safety car is gone and we are back to racing. Watch the first corner.", "i": 3},
    ],

    # THE RESTART THAT LANDS ON THE LAST LAP. Its own pool, because it is its own
    # event — the user got exactly this and it went uncalled.
    "sc_green_last": [
        {"t": "Green — and it is the last lap! One lap, a bunched field, and a race to win from here!", "i": 4},
        {"t": "The safety car is in and we go green for the final lap. Everything comes down to one lap!", "i": 4},
        {"t": "Green flag, last lap! Whatever anybody planned, it is now a one-lap sprint to the flag!", "i": 4},
        {"t": "One lap left and we are racing! You could not ask for a worse — or better — time for a restart!", "i": 4},
    ],

    "sc_green_last_why": [
        {"t": "There is no strategy left. Whoever is bravest into the next corner probably wins this, and whoever is greediest probably does not finish it.", "i": 3, "who": "ANALYST"},
        {"t": "A single lap. No time to build a gap, no time to plan a move — just whatever they can take, right now.", "i": 3, "who": "ANALYST"},
    ],

    # COLOUR WHILE THE FIELD CIRCULATES. The user's complaint was SILENCE for six
    # minutes, and a broadcast does not go quiet behind a safety car — it is when
    # a broadcast talks most. Paced by the booth's own cooldowns.
    "sc_field": [
        {"t": "The whole field is together again, nose to tail behind the safety car.", "i": 2},
        {"t": "Everything that was spread across the circuit is now one queue, and the racing gaps have gone.", "i": 2},
        {"t": "Look at that train of cars. Every one of them a couple of lengths from the next.", "i": 2},
        {"t": "The order will not change while we are like this, but what happens after it will.", "i": 2},
        {"t": "They are circulating slowly, and every driver out there is thinking about one thing only: the restart.", "i": 2},
    ],

    "sc_wait": [
        {"t": "Still behind the safety car, and still nothing anybody can do about it.", "i": 1},
        {"t": "We wait. The clock runs and nobody is racing.", "i": 1},
        {"t": "Another lap of this before anybody can think about the flag.", "i": 1},
        {"t": "The field trundles round, and the tyres get colder.", "i": 1},
    ],
}


def main():
    path = os.path.join(OUT, "booth_safety.json")
    io.open(path, "w", encoding="utf-8").write(
        json.dumps(DATA, indent=1, ensure_ascii=False) + "\n")
    n = sum(len(v) for v in DATA.values() if isinstance(v, list))
    print("wrote %s — %d pools / %d lines"
          % (path, len([k for k in DATA if not k.startswith("_")]), n))


if __name__ == "__main__":
    main()
