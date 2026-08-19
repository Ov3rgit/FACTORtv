# -*- coding: utf-8 -*-
"""
FACTORtv — the cast.

Who talks, how they sound, and what they are allowed to know. Kept apart from
the dialogue pools because a persona is a *constraint on writing*, not a bag
of lines: when a new event is added, this file decides which of them should
be the one to call it.

The team
--------
Two in the booth, one on the pit wall, plus the drivers themselves.

  MILES CRAWFORD   play-by-play, MODERN racing (2000 on). Carried over from
                   RacerTV deliberately — he is the through-line between the
                   two channels, same voice, same delivery. Describes what is
                   happening, in the moment, and never explains. Short
                   clauses under pressure. No racing career of his own.

  BRETT CALLOWAY   play-by-play, HISTORIC racing (before 2000). Also from
                   RacerTV, where he was the pundit; here he leads. A WEC
                   champion — endurance and sportscars, never Formula One.
                   He and Chuck are MODERN broadcasters presenting archive
                   footage: neither of them was at the race they are calling,
                   and neither may claim to have been.

  CHUCK BRANNIGAN  analysis. Former NASCAR Cup champion, Carolina-raised,
                   two titles and a long career in stock cars before a late
                   run in sports cars. American, warm, unhurried, and blunt
                   when a driver deserves it. His background is doing real
                   work: he speaks about ovals, restarts and dirty air from
                   experience, and about single-seaters as an interested
                   outsider. He never calls the action; he answers it.

  DEAN MACKENZIE   race engineer. Dry, unflappable, calm British. Talks only to
                   you, only on the radio, and only about your car. He is not
                   a commentator and never narrates the race for its own
                   sake.

Why the split matters
---------------------
The failure mode of a generated booth is two voices saying interchangeable
things. Every persona here has something it will NOT do, and the director
consults `can_say()` before assigning a line. Miles never analyses tyre
degradation; Chuck never calls a pass as it happens; Dean never mentions a
car he cannot see from the pit wall.
"""

PLAY = "PLAY"
ANALYST = "ANALYST"
ENGINEER = "ENGINEER"
DRIVER = "DRIVER"

# --------------------------------------------------------------------------
# THE PLAY-BY-PLAY SEAT
#
# `PLAY` is a ROLE, not a person, and two different men sit in it:
#
#   MILES CRAWFORD    modern racing, 2000 onwards
#   BRETT CALLOWAY    historic racing, before 2000
#
# This is deliberately a seat rather than a second persona key. Every
# dialogue pool, every `can_say()` rule, every crosstalk pairing and every
# `who_says()` lookup in the director talks about PLAY — so swapping the
# occupant changes the voice, the name and the colour on the caption, and
# NOTHING else has to know it happened. Adding a parallel persona would have
# meant duplicating all of that and keeping the two copies in step for ever.
#
# `set_era()` is called once per session by the director. Between sessions the
# seat holds whoever was last cast, which is correct: a session that never
# reports an era keeps the commentator the previous one had.
# --------------------------------------------------------------------------
HISTORIC_BEFORE = 2000

_seat_historic = False


def set_era(era):
    """Cast the play-by-play seat for this session. Returns True if historic.

    Unknown or missing years fall to MODERN. That is the safer default by a
    distance: Miles calling a historic race sounds like a normal broadcast,
    whereas Brett framing a 2025 race as archive footage is nonsense the
    viewer can see through immediately.
    """
    global _seat_historic
    year = getattr(era, "year", None)
    _seat_historic = bool(year and year < HISTORIC_BEFORE)
    return _seat_historic


def is_historic():
    return _seat_historic


def occupant(key):
    """Which persona record is actually in this seat right now."""
    if key == PLAY and _seat_historic:
        return HISTORIC_PLAY
    return key

# --------------------------------------------------------------------------
# voices
#
# edge-tts neural voices, chosen for contrast rather than realism: the two
# booth voices have to be separable through a car engine and a set of
# speakers. Same accent for both was tested and is genuinely hard to follow,
# so the pairing is deliberately mixed.
#
# `rate`/`pitch` are the resting values. The director raises rate with
# intensity, so these are the FLOOR, not the average.
# --------------------------------------------------------------------------
VOICES = {
    # Miles Crawford — English. Deliberately the SAME voice RacerTV used, at
    # the user's request: he is the continuity between the two channels, so
    # sounding identical is the point rather than a problem.
    # RESTING VALUES MATCHED TO CHUCK, at the user's ear.
    #
    # Miles sat at +8%/+2Hz against Chuck's +4%/+0Hz, and because the hype
    # ladder in tts.py ADDS to these, he was ~4% faster than Chuck at every
    # intensity and pitch-shifted at all of them. Both showed: "sped up and
    # robotic", against an analyst who "sounds super natural".
    #
    # The pitch offset was the worse half. tts._HYPE's own comment says why:
    # Azure's neural voices are modelled at their own pitch, shifting them is
    # resampling, and resampling is what makes a good voice sound processed.
    # Chuck was the only booth voice never shifted at rest, which is exactly
    # why he was the only one that sounded real.
    PLAY: {
        "voice": "en-GB-RyanNeural",
        "rate": "+4%", "pitch": "+0Hz",
        "fallback": "en-GB-ThomasNeural",
    },
    # Chuck Brannigan — American, ex-NASCAR Cup champion.
    #
    # AndrewMultilingual, not Roger. Azure tags its voices with intended
    # personality and the difference is not subtle: Roger is "Lively", an
    # older and thinner model that reads like a station ident, while Andrew
    # is "Warm, Confident, Authentic, Honest" and belongs to the newest
    # generation. For a man who won championships and now explains them, the
    # second description is the brief.
    #
    # NB: NOT "en-US-DavisNeural" — that name does not exist in the edge
    # catalogue and silently drops the analyst to robotic offline SAPI.
    ANALYST: {
        # Andrew is naturally measured, and the -3% written here to make him
        # sound unhurried tipped him over into ponderous. An analyst should
        # sound considered, not slow — those are different things, and the
        # difference is roughly seven points of speaking rate.
        "voice": "en-US-AndrewMultilingualNeural",
        "rate": "+4%", "pitch": "+0Hz",
        "fallback": "en-US-BrianMultilingualNeural",
    },
    # Dean Mackenzie — the RacerTV engineer voice, brought back at the user's
    # request because it worked. Calm British male.
    #
    # He was briefly en-NZ-MitchellNeural, chosen only to avoid sounding like
    # RacerTV's Brett Calloway. That constraint is gone now that Brett is
    # openly back as the historic commentator, so the engineer returns to the
    # voice that was always the better one. Mackenzie is a Scottish name, so
    # the character survives the change of accent unaltered.
    ENGINEER: {
        "voice": "en-GB-ThomasNeural",
        "rate": "+0%", "pitch": "+0Hz",
        "fallback": "en-NZ-MitchellNeural",
        "radio_fx": True,          # clicks + level, but NOT the band-pass
    },
}

# Brett Calloway — the historic play-by-play seat. RacerTV's pundit voice,
# now leading the commentary on pre-2000 racing.
HISTORIC_PLAY = "HISTORIC_PLAY"
VOICES[HISTORIC_PLAY] = {
    # Same resting values as Miles and Chuck — see the note on PLAY.
    "voice": "en-AU-WilliamNeural",
    "rate": "+4%", "pitch": "+0Hz",
    "fallback": "en-GB-RyanNeural",
}

# Rival driver pool, used when we cannot place a nationality. Mixed accents on
# purpose — a grid that all sounds like one person is worse than a grid with
# approximate accents.
#
# Every entry is checked against the live catalogue at import (see
# `_verify_voices`), because a typo here is invisible: an unknown voice does
# not raise, it just falls back to offline SAPI and sounds broken.
DRIVER_VOICES = [
    "en-US-EricNeural", "en-AU-WilliamMultilingualNeural",
    "en-IE-ConnorNeural", "en-US-RogerNeural",
    "en-NZ-MitchellNeural", "en-US-SteffanNeural", "en-CA-LiamNeural",
    "en-ZA-LukeNeural", "en-US-BrianNeural", "en-IN-PrabhatNeural",
    "en-KE-ChilembaNeural", "en-SG-WayneNeural", "en-US-AndrewNeural",
    "en-HK-SamNeural", "en-PH-JamesNeural", "en-TZ-ElimuNeural",
]

DRIVER_VOICES_F = [
    "en-GB-SoniaNeural", "en-US-AriaNeural", "en-AU-NatashaNeural",
    "en-IE-EmilyNeural", "en-GB-LibbyNeural", "en-US-JennyNeural",
    "en-NZ-MollyNeural", "en-ZA-LeahNeural", "en-CA-ClaraNeural",
    "en-US-MichelleNeural", "en-IN-NeerjaNeural", "en-KE-AsiliaNeural",
]

# Voices belonging to the principals. A rival must NEVER be cast from these:
# hearing a back-marker answer the radio in the play-by-play commentator's
# exact voice reads as a bug, not as a coincidence.
#
# PRIMARY voices only — NOT the fallbacks. The catalogue has exactly two en-GB
# male voices, so reserving Ryan *and* Thomas emptied the British pool
# entirely and sent Hamilton, Russell and Bearman off to Singaporean and
# Filipino accents. A fallback only fires if the catalogue is unreachable, and
# in that situation a voice collision is the least of the problems.
RESERVED_VOICES = {"en-GB-RyanNeural", "en-US-AndrewMultilingualNeural",
                   "en-GB-ThomasNeural", "en-AU-WilliamNeural"}

# Drivers whose nationality we know but whose accent the catalogue cannot
# supply (Dutch, Italian, Japanese, Brazilian...). A strongly-marked wrong
# accent is worse than a neutral one — Verstappen with a Kenyan voice is a
# bigger error than Verstappen sounding generically English — so these draw
# from a deliberately unmarked pool.
NEUTRAL_VOICES = [
    "en-US-EricNeural", "en-US-BrianNeural", "en-US-SteffanNeural",
    "en-US-AndrewNeural", "en-CA-LiamNeural",
]
NEUTRAL_VOICES_F = [
    "en-US-AriaNeural", "en-US-JennyNeural", "en-US-MichelleNeural",
    "en-CA-ClaraNeural",
]

# rF2 does not report driver gender, and sim grids are overwhelmingly
# male-named, so the default is male and this list is the exception set. It
# only has to cover the AI names that actually appear — a mis-gendered voice
# is jarring in a way a merely-wrong accent is not.
FEMALE_FIRST_NAMES = {
    "samantha", "alice", "kelly", "kim", "sandra", "susan", "linda", "karen",
    "emma", "sarah", "sara", "laura", "julia", "anna", "maria", "sophie",
    "chloe", "jessica", "rachel", "hannah", "megan", "amy", "claire",
    "natalie", "danielle", "michelle", "nicole", "leah", "molly", "aria",
    "jenny", "clara", "emily", "sonia", "libby", "maisie", "natasha",
    "victoria", "elena", "carmen", "ines", "tatiana", "simona", "jamie",
}

# Nationality -> the best available English accent.
#
# edge-tts has no Dutch- or Italian-accented English, so only the anglophone
# nationalities can actually be matched. Those that can are worth doing: with
# the F1 2025 mod the grid is real drivers, and hearing Piastri answer in an
# Australian accent and Lawson in a New Zealand one is a large immersion win
# for a very small table. Everyone else is distributed deterministically.
NATION_VOICES = {
    # Anglophone: a native English locale.
    "GB": ["en-GB-ThomasNeural"],
    "US": ["en-US-EricNeural", "en-US-BrianNeural", "en-US-SteffanNeural",
           "en-US-AndrewNeural"],
    "AU": ["en-AU-WilliamNeural"],
    "NZ": [],          # reserved for the engineer; NZ rivals go neutral
    "IE": ["en-IE-ConnorNeural"],
    "CA": ["en-CA-LiamNeural"],
    "ZA": ["en-ZA-LukeNeural"],
    "IN": ["en-IN-PrabhatNeural"],
    "NG": ["en-NG-AbeoNeural"],
    "KE": ["en-KE-ChilembaNeural"],
    "SG": ["en-SG-WayneNeural"],
    "HK": ["en-HK-SamNeural"],
    "PH": ["en-PH-JamesNeural"],

    # Non-anglophone: the driver's OWN language voice, reading the English
    # radio line. This produces a genuine foreign accent rather than an
    # approximation, because the voice model's phonetics are actually that
    # language's. It is the technique RacerTV used for its whole rival grid
    # and the note there records that it is "the flavour that landed".
    #
    # These locales are absent from the en-* catalogue, so a Dutch or Japanese
    # accent is simply unobtainable any other way.
    "NL": ["nl-NL-MaartenNeural"],
    "IT": ["it-IT-DiegoNeural"],
    "DE": ["de-DE-ConradNeural"],
    "AT": ["de-DE-ConradNeural"],          # Austrian -> German
    "FR": ["fr-FR-HenriNeural"],
    "MC": ["fr-FR-HenriNeural"],           # Monaco -> francophone
    "BE": ["fr-BE-GerardNeural"],
    "ES": ["es-ES-AlvaroNeural"],
    "BR": ["pt-BR-AntonioNeural"],
    "AR": ["es-AR-TomasNeural"],
    "JP": ["ja-JP-KeitaNeural"],
    "FI": ["fi-FI-HarriNeural"],
    "TH": ["th-TH-NiwatNeural"],
    "PL": ["pl-PL-MarekNeural"],
    "SE": ["sv-SE-MattiasNeural"],
    "CZ": ["cs-CZ-AntoninNeural"],
    "DK": ["da-DK-JeppeNeural"],
    "MX": ["es-MX-JorgeNeural"],
}

# Female equivalents, same principle.
NATION_VOICES_F = {
    "GB": ["en-GB-SoniaNeural"], "US": ["en-US-AriaNeural"],
    "AU": ["en-AU-NatashaNeural"], "NZ": ["en-NZ-MollyNeural"],
    "IE": ["en-IE-EmilyNeural"], "CA": ["en-CA-ClaraNeural"],
    "ZA": ["en-ZA-LeahNeural"], "IN": ["en-IN-NeerjaNeural"],
    "NL": ["nl-NL-ColetteNeural"], "IT": ["it-IT-ElsaNeural"],
    "DE": ["de-DE-KatjaNeural"], "FR": ["fr-FR-DeniseNeural"],
    "ES": ["es-ES-ElviraNeural"], "BR": ["pt-BR-FranciscaNeural"],
    "JP": ["ja-JP-NanamiNeural"], "FI": ["fi-FI-NooraNeural"],
}

# Real drivers whose nationality we can place, so the accent is right rather
# than merely different. Surname-keyed and lowercased at lookup: rF2 mods vary
# the given-name formatting ("Carlos Sainz Jr.", "Andrea Kimi Antonelli") but
# the surname is stable.
DRIVER_NATION = {
    # F1 2025 grid — anglophone entries are the ones that actually change
    # anything; the rest are recorded so they at least stay stable.
    "hamilton": "GB", "russell": "GB", "norris": "GB", "bearman": "GB",
    "piastri": "AU", "doohan": "AU",
    "lawson": "NZ",
    "stroll": "CA",
    "verstappen": "NL", "antonelli": "IT", "leclerc": "MC",
    "sainz": "ES", "alonso": "ES", "gasly": "FR", "ocon": "FR",
    "hadjar": "FR", "hulkenberg": "DE", "tsunoda": "JP",
    "bortoleto": "BR", "colapinto": "AR", "albon": "TH",
    # 1992 grid
    "mansell": "GB", "brundle": "GB", "herbert": "GB", "hill": "GB",
    "patrese": "IT", "capelli": "IT", "morbidelli": "IT", "fittipaldi": "BR",
    "moreno": "BR", "schumacher": "DE", "wendlinger": "AT", "berger": "AT",
    "alesi": "FR", "comas": "FR", "boutsen": "BE", "hakkinen": "FI",
    "belmondo": "FR", "mccarthy": "GB",
}

PERSONAS = {
    PLAY: {
        "name": "Miles Crawford",
        "short": "Crawford",
        "role": "play-by-play",
        "colour": "#ffcf33",
        # What he is for. The director only offers him these categories.
        "does": {
            "start", "overtake", "leadchange", "battle", "spin", "offtrack",
            "fastlap", "pit", "penalty", "yellow", "flag", "lastlap", "win",
            "podium", "position", "recovery", "closing", "grid", "session",
            "crash", "retire", "milestone", "traffic", "restart",
            # Race flow: where we are, who's where, what just came back.
            "pregrid", "race_duration", "lap_report", "lap_milestone",
            "time_remaining", "retake", "midpack", "midpack_recovery",
            "podium_watch", "summary", "standings", "final_laps",
            "win_charge", "win_comeback", "win_duel", "win_wire",
            "quali_deleted", "incident_react",
            # The end of qualifying. The sheet, the grid and where the player
            # ended up are REPORTS; the verdict on them is not, and lives
            # with the analyst below.
            "quali_over_pole", "quali_over_solo", "quali_over_top3",
            "quali_over_top2", "quali_over_player", "quali_over_signoff",
            "crosstalk_q", "podium_final", "signoff", "broadcast",
            "broadcast_archive",
            # THE STATION ITSELF. The ident, the plug for the other channel
            # and the nod to the sister station are all continuity — the
            # play-by-play seat's job, never the analyst's. Brett inherits
            # the whole set at import, so FACTORtv Classic has its own
            # continuity announcer without a parallel list to keep in step.
            "broadcast_promo", "broadcast_racertv",
            "broadcast_promo_archive", "broadcast_racertv_archive",
            # The past. Miles sets the scene with it; Chuck judges it.
            "career_won_here", "career_podium_here", "career_back",
            "career_been_here", "career_first_visit", "career_dnf_here",
            "career_form", "grid_progress", "grid_slipped",
            "archive_open", "archive_watch",
            # Who a driver IS. Miles introduces people — a record is a fact
            # to be reported, and reporting is his half of the booth. The
            # lines in `booth_driver.json` that are a JUDGEMENT about a
            # driver carry "who": "ANALYST" and go to Chuck instead.
            "driver_reigning", "driver_chasing", "driver_champion",
            "driver_favourite", "driver_winner", "driver_winless",
            "driver_rookie", "driver_new_team", "driver_note",
            "driver_season_wins",
            # Asking Chuck how a driver's race has gone. The question is
            # Miles's; every answer pool is Chuck's, below.
            "story_ask", "wrap_ask_impressed", "driver_ask",
            # Class positions are the running order in a mixed race, so they
            # are reported like any other position. The two that JUDGE what
            # traffic costs carry "who": "ANALYST".
            "class_lead", "class_pos", "class_battle", "class_traffic",
            # The championship implication is a REPORT of exact numbers, so
            # it belongs to the play-by-play seat. `champ_next` is a
            # judgement about what those numbers mean and is Chuck's.
            "champ_extends", "champ_closes",
            # ...and what the car is like. A team characteristic is reported;
            # the lines that JUDGE one carry "who": "ANALYST".
            "team_strength", "team_weakness", "team_note",
            # Ribbing the analyst. Miles only: a man cannot dig at himself.
            "booth_dig",
            # And the running totals: whose championship this is, and where
            # the win just taken sits in his career. A record is a fact, so
            # it is reported — this is the same seat that calls the win.
            "driver_title_first", "driver_title_more", "driver_first_win",
            "driver_win_tally",
            # The season: round numbers and standings are reported, not
            # analysed, so they belong to Miles.
            "season_round", "season_round_open", "season_round_anytrack",
            "season_launch", "season_launch_open",
            "season_opener", "season_midway", "season_late",
            "season_here", "season_here_dnf", "season_here_won",
            "season_finale", "title_lead", "title_chase",
            "championship_after", "championship_lead", "title_decided",
            # The title arithmetic. Play-by-play, not analysis: it is a
            # statement of what is required, and Miles is the one watching
            # the order change.
            "title_needs", "title_needs_finish", "title_live", "title_lost",
            # The incident family and the long fight — all of these are Miles
            # calling what he can see, whatever else was going on.
            "ranwide", "offtrack_cut", "offtrack_more", "offtrack_chaos",
            "offtrack_late", "overtake_long", "battle_sustained",
            # The rest of the fight. A queue for one place, two men trading
            # it, and the moment somebody finally gets away with it — all of
            # them are the play-by-play seat describing the road, which is
            # why none of them belong to the analyst.
            "battle_three", "battle_traded", "pulling_away", "battle_escaped",
            # The team-mate, and the junior programme that put him there.
            "mate_ahead", "mate_behind", "mate_pass", "mate_passed",
            "mate_quali_up", "mate_quali_down", "mate_record",
            "mate_record_races",
            "prog_stake", "prog_last_chance", "prog_debut", "prog_measured",
            # What kind of racing this is. Miles sets the scene; Chuck
            # answers it, which is the split everywhere else in the booth.
            "div_kart", "div_f4", "div_f3", "div_f2", "div_f1", "div_hatch",
            # Qualifying and practice: a timesheet is reported, not analysed.
            "quali_start", "practice_start", "quali_pole", "quali_fastlap",
            "quali_improve", "quali_final", "quali_count", "quali_standings",
            "quali_nobody", "quali_onlyone", "quali_pits", "quali_solo",
            "quali_open_laps", "practice_note",
        },
        # What he must never do — these belong to the analyst, and letting him
        # have them is exactly how two voices become one voice.
        "never": {
            "analysis", "strategy", "tyre_theory", "history", "lore",
            "car_tech", "verdict",
            # Era lore is written in the first person — "I'd have needed an
            # engineering degree" — and belongs to the man who actually
            # raced. Miles was reading Chuck's memories aloud because the
            # category was in neither persona's list and fell through to him.
            "analysis_era",
        },
        "max_words": 22,          # he is calling, not explaining
    },
    ANALYST: {
        "name": "Chuck Brannigan",
        "short": "Brannigan",
        "role": "analysis",
        "colour": "#5cc8ff",
        "does": {
            "analysis", "analysis_era", "strategy", "tyre_theory", "history",
            "lore", "car_tech", "verdict", "praise", "criticism", "stat",
            "context",
            "crosstalk_a", "prediction",
            # Reading the race rather than reporting it. All of these are
            # judgements, which is why none of them are Miles's.
            "insight_lead_big", "insight_lead_slim", "insight_podium_fight",
            "insight_field_spread", "insight_laps_left", "podium_lock",
            "arc_cost", "arc_recovered", "booth_joke", "race_verdict",
            # Levity. Chuck carries most of it — a dry observation is a
            # judgement, and judgements are his half of the booth. The lines
            # where the play-by-play seat ribs HIM are `booth_dig`, which is
            # Miles-only for the obvious reason.
            "analyst_dig", "dig_stuck", "dig_wide",
            "offtrack_ack", "archive_era", "quali_lap_praise",
            # THE INCIDENT IDENTIFICATION. He cut in with the alert, so he
            # owes the viewer the name — and handing the reply to the
            # play-by-play seat is what makes the sequence a booth rather
            # than one man announcing twice.
            "incident_id_off", "incident_id_spin", "incident_cut_id",
            # What a driver has to DO with the grid slot he has just earned
            # is a judgement, not a result.
            "quali_over_verdict",
            # What a practice session is FOR is a judgement, not a report.
            "quali_goals",
            # Chuck gets the driver lines that assess a man rather than state
            # his record. He is allowed the whole family so that a line
            # marked "who": "ANALYST" can actually reach him — `can_say`
            # is what decides, and an override he is not allowed is ignored.
            "driver_reigning", "driver_chasing", "driver_champion",
            "driver_favourite", "driver_winner", "driver_winless",
            "driver_rookie", "driver_new_team", "driver_note",
            "driver_season_wins",
            "team_strength", "team_weakness", "team_note", "car_character",
            # THE RACE STORY. Every answer is a judgement about how somebody
            # has driven, which is the definition of Chuck's half of the
            # booth. `story_ask` is deliberately NOT here — a man does not
            # ask himself the question.
            "story_recovery", "story_charge", "story_slide", "story_undone",
            "story_scrappy", "story_led", "story_dropping", "story_progress",
            "story_losing", "story_holding", "story_out", "story_from_quali",
            "wrap_impressed", "champ_next",
            "class_pos", "class_battle", "class_traffic",
            # The elaborated history answers. Every one is a judgement about
            # what a record MEANS, which is Chuck's half of the booth.
            "hist_reigning", "hist_chasing", "hist_champion", "hist_winner",
            "hist_winless", "hist_rookie", "hist_new_team", "hist_favourite",
            "hist_season_wins", "hist_note",
            "driver_title_first", "driver_title_more", "driver_first_win",
            "driver_win_tally",
        },
        # `win` is Miles's moment, but a CHAMPIONSHIP is a summing-up, and
        # these four are stated as records rather than called as they happen.
        # Chuck is allowed them so a line marked "who": "ANALYST" can reach
        # him; the rest still default to Miles.
        "never": {"overtake", "leadchange", "spin", "crash", "start", "win"},
        "max_words": 32,          # he gets room to make a point
        # Eras he lived through: he speaks from memory inside this window and
        # from research outside it. The booth's lore lines branch on this, so
        # he never claims to have raced against a 1967 field.
        "raced_from": 1985,
        "raced_to": 2006,
        "discipline": "stock",
    },
    # Brett Calloway occupies the same SEAT as Miles, so his `does` and
    # `never` sets are copied from PLAY at import (below) rather than written
    # out again — two lists that had to be kept in step would drift the first
    # time a category was added.
    HISTORIC_PLAY: {
        "name": "Brett Calloway",
        "short": "Calloway",
        "role": "play-by-play",
        "colour": "#ffcf33",
        "does": set(),          # filled from PLAY below
        "never": set(),         # filled from PLAY below
        "max_words": 22,
        # A WEC champion. His authority is endurance and sportscars, which is
        # a different seat entirely from Chuck's stock cars — between them
        # they cover most of what a historic grid can be, and neither of them
        # has ever driven a Formula One car.
        "raced_from": 1994,
        "raced_to": 2014,
        "discipline": "sportscar",
    },
    ENGINEER: {
        "name": "Dean Mackenzie",
        "short": "Deano",
        "role": "race engineer",
        "colour": "#4fe0e8",
        "does": {
            "fuel", "tyres", "damage", "limits", "pit", "target", "gap",
            "sector", "weather", "warn", "encourage", "instruct",
            # Career awareness: he knows your name, the round, and where you
            # qualified — the last of which happened in a session that has
            # already ended.
            "greet", "quali_recall", "grid_recall",
        },
        "never": {"analysis", "lore", "overtake", "history"},
        "max_words": 18,          # radio calls are short or they get ignored
    },
}


# Brett does the same job as Miles, so he is allowed and forbidden exactly
# what Miles is. Copied once, at import, from the single definition.
PERSONAS[HISTORIC_PLAY]["does"] = set(PERSONAS[PLAY]["does"])
PERSONAS[HISTORIC_PLAY]["never"] = set(PERSONAS[PLAY]["never"])


def persona(key):
    """The persona record for a key, resolving PLAY to whoever is in the seat.

    Everything downstream — captions, names, colours, voices — goes through
    here, which is why swapping the commentator for a historic race needs no
    changes anywhere else.
    """
    return PERSONAS.get(occupant(key), PERSONAS[PLAY])


def name_of(key):
    return persona(key).get("name", "")


def colour_of(key):
    return persona(key).get("colour", "#ffffff")


def can_say(key, category):
    """Is this persona allowed to deliver this category of line?

    `never` beats `does`, so adding a category to both is a safe way to
    retire it from a persona without hunting down every pool entry.
    """
    p = persona(key)
    if category in p.get("never", ()):
        return False
    return category in p.get("does", ())


def who_says(category, prefer=None):
    """Pick the persona for a category.

    `prefer` is honoured only if that persona is actually allowed the
    category — the caller usually knows who it wants, but the constraint
    wins, because that is the whole point of having one.
    """
    if prefer and can_say(prefer, category):
        return prefer
    for key in (PLAY, ANALYST, ENGINEER):
        if can_say(key, category):
            return key
    return PLAY


def spoke_from_memory(era):
    """True if Dale actually raced in this era.

    Gates the difference between "I remember these things being a handful"
    and "they say these were a handful" — claiming first-hand experience of a
    1966 Brabham is the analyst's version of mentioning DRS in 1968.
    """
    p = persona(ANALYST)
    y = getattr(era, "year", None)
    if not y:
        return False
    return p["raced_from"] <= y <= p["raced_to"]


def _stable_seed(name):
    """A stable index from a driver's name.

    Deliberately not `hash()`: Python randomises string hashing per process,
    so a driver would get a different voice every time the overlay restarted.
    """
    n = 0
    for ch in (name or ""):
        n = (n * 131 + ord(ch)) & 0xFFFFFFFF
    return n


def nation_of(name):
    """Best guess at a driver's nationality from their name, or None.

    Matches on any whitespace-separated token so it works for "Carlos Sainz
    Jr." and "Andrea Kimi Antonelli" alike.
    """
    for tok in (name or "").lower().replace(".", " ").split():
        if tok in DRIVER_NATION:
            return DRIVER_NATION[tok]
    return None


def voice_for(key, seed=0, name=""):
    """Voice config for a persona.

    Rival drivers are placed by NATIONALITY where we can identify them, so
    Piastri answers in an Australian accent and Lawson in a New Zealand one.
    Where we cannot (a Dutch or Japanese driver has no matching English
    accent in the catalogue, and an AI with an invented name has no
    nationality at all) they are distributed deterministically across the
    pool — so the grid still sounds like different people, and each of them
    keeps the same voice for the whole weekend.
    """
    if key == DRIVER:
        female = is_female(name)
        nat = nation_of(name)
        pool = None
        if nat:
            # Known nationality: use that nation's own voice. For non-English
            # nationalities this is a native-language model reading English,
            # which is what produces a real accent rather than an approximation.
            table = NATION_VOICES_F if female else NATION_VOICES
            pool = [v for v in table.get(nat, []) if v not in RESERVED_VOICES]
            if not pool:
                pool = NEUTRAL_VOICES_F if female else NEUTRAL_VOICES
        if not pool:
            pool = DRIVER_VOICES_F if female else DRIVER_VOICES
        pool = [v for v in pool if v not in RESERVED_VOICES] or pool
        idx = (_stable_seed(name) if name else seed) % len(pool)
        return {"voice": pool[idx], "rate": "+0%", "pitch": "+0Hz",
                "radio_fx": True}
    # Resolved through the seat, so a historic session speaks in Brett's
    # voice everywhere the director asked for PLAY.
    return dict(VOICES.get(occupant(key), VOICES[PLAY]))


def is_female(name):
    """Guess gender from the given name. Male is the default.

    rF2 publishes no gender, and a mis-gendered voice is far more jarring
    than a merely-wrong accent, so this errs toward the overwhelmingly common
    case and treats the female list as an explicit exception set.
    """
    toks = (name or "").lower().replace(".", " ").split()
    return bool(toks) and toks[0] in FEMALE_FIRST_NAMES


def _verify_voices(available=None):
    """Check every configured voice against the real edge-tts catalogue.

    Exists because an unknown voice name does not raise — edge-tts simply
    fails and the engine drops to offline SAPI, so the only symptom is one
    character sounding robotic while the others are fine. That is exactly how
    the analyst shipped with a non-existent "en-US-DavisNeural" and nobody
    noticed for a while.

    Returns a list of problems; empty means everything resolves.
    """
    if available is None:
        try:
            import asyncio
            import edge_tts
            available = {v["ShortName"]
                         for v in asyncio.run(edge_tts.list_voices())}
        except Exception as e:
            return ["could not reach the voice catalogue: %s" % e]
    def ok(v):
        """Listed voices are fine; unlisted ones get a real render attempt.

        edge-tts's catalogue is NOT exhaustive — en-AU-WilliamNeural is absent
        from list_voices() and renders perfectly. Rejecting on absence alone
        would drop working voices, so absence only triggers a live check.
        """
        if v in available:
            return True
        try:
            import asyncio as _a
            import edge_tts as _e

            async def _try():
                n = 0
                async for ch in _e.Communicate("test", v).stream():
                    if ch["type"] == "audio":
                        n += len(ch["data"])
                return n
            return _a.run(_try()) > 0
        except Exception:
            return False

    bad = []
    for key, cfg in VOICES.items():
        for field in ("voice", "fallback"):
            v = cfg.get(field)
            if v and not ok(v):
                bad.append("%s %s: %s" % (key, field, v))
    for pool_name, pool in (("DRIVER_VOICES", DRIVER_VOICES),
                            ("DRIVER_VOICES_F", DRIVER_VOICES_F),
                            ("NEUTRAL_VOICES", NEUTRAL_VOICES),
                            ("NEUTRAL_VOICES_F", NEUTRAL_VOICES_F)):
        for v in pool:
            if not ok(v):
                bad.append("%s: %s" % (pool_name, v))
    for tbl_name, tbl in (("NATION_VOICES", NATION_VOICES),
                          ("NATION_VOICES_F", NATION_VOICES_F)):
        for nat, vs in tbl.items():
            for v in vs:
                if not ok(v):
                    bad.append("%s[%s]: %s" % (tbl_name, nat, v))
    return bad


if __name__ == "__main__":
    print("FACTORtv cast\n")
    for key in (PLAY, ANALYST, ENGINEER):
        p = persona(key)
        v = VOICES[key]
        print("  %-9s %-16s %-32s %s" % (key, p["name"], v["voice"], p["role"]))
    print("\nverifying voices against the live catalogue...")
    probs = _verify_voices()
    if probs:
        print("  %d PROBLEM(S):" % len(probs))
        for b in probs:
            print("    - " + b)
    else:
        print("  all configured voices exist.")
    print("\nrival casting:")
    names = ("Lewis Hamilton", "George Russell", "Oscar Piastri",
             "Jack Doohan", "Liam Lawson", "Lance Stroll", "Oliver Bearman",
             "Max Verstappen", "Yuki Tsunoda", "Charles Leclerc",
             "Nigel Mansell", "Michael Schumacher", "Mika Hakkinen",
             "Ted Moser", "Samantha Speed", "Alice Jackson", "Kim Blechmann")
    seen = {}
    for nm in names:
        cfg = voice_for(DRIVER, name=nm)
        v = cfg["voice"]
        print("  %-20s %-3s %-4s %s" % (nm, nation_of(nm) or "-",
                                        "F" if is_female(nm) else "M", v))
        seen.setdefault(v, []).append(nm)
    print()
    clash = [v for v in seen if v in RESERVED_VOICES]
    print("  rivals using a principal's voice: %s" % (clash or "none"))
    dupes = {v: n for v, n in seen.items() if len(n) > 1}
    print("  shared voices: %s" % (dupes or "none"))
    # stability across runs is the whole point of _stable_seed
    again = {nm: voice_for(DRIVER, name=nm)["voice"] for nm in names}
    print("  stable across calls: %s"
          % all(again[nm] == voice_for(DRIVER, name=nm)["voice"] for nm in names))

# NOTE: there used to be an `intensity_voice()` here that added +6% rate and
# +3Hz pitch per intensity level. It was DEAD CODE — nothing ever called it —
# and worse, it was a trap: it looked like the excitement knob, so anyone
# tuning the delivery would have edited it and heard no change at all. The
# real ladder is `tts._HYPE`, which is added on top of the resting values in
# VOICES above.
