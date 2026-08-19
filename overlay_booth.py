# -*- coding: utf-8 -*-
"""
FACTORtv — the director.

Watches the session tick by tick, decides what is worth saying, who says it,
and — hardest of all — when to stay quiet.

The problem this solves
-----------------------
Detecting events is easy. A racing session generates dozens of "facts" a
second, and a booth that reports all of them is unlistenable. Almost
everything here is therefore suppression rather than detection:

  * PRIORITY. Events compete. A lead change outranks a routine gap update, so
    only the best candidate on a tick is spoken and the rest are discarded
    rather than queued — a queued fact is a stale fact by the time it airs.

  * COOLDOWNS. Per-category and global. Without the global one the booth
    talks continuously; without the per-category one it finds one thing it
    likes and says it every lap.

  * FOCUS. The booth cannot watch 24 cars. It follows the player and the
    front of the race, and only strays for something genuinely big. This is
    also what stops the "P17 passes P18" problem, where the most eventful
    part of the field is the part nobody cares about.

  * CONFIRMATION. Position swaps must hold (see `SessionTracker`) before they
    count. Calling a pass and then calling it back reads as a bug.

Detection notes
---------------
rF2 does not flag spins or offtracks. They are inferred: a large heading
change with a big speed drop is a spin; a sudden lap invalidation with the
car still moving is an excursion. Both are deliberately conservative — a
missed spin costs nothing, a phantom spin destroys trust in the whole booth.
"""
import io
import os
import time

import cast as cast_mod
import era as era_mod
import drivers as drivers_mod
import nations as nations_mod
import lines as lines_mod
import story as story_mod
import stings as stings_mod
from overlay_common import (STRIKE_GAP, spoken_place, spoken_gap,
                            spoken_lap, spoken_rank)
from rf2_session import fmt_gap

# Global gap between ANY two booth lines. The single most important number
# here: too low and the booth never draws breath, too high and it misses the
# race. Scaled down for high-priority events.
GLOBAL_COOLDOWN = 7.0
URGENT_COOLDOWN = 2.0

# Per-category cooldowns. A category is silent for this long after it fires,
# which is what stops the booth latching onto one kind of event.
COOLDOWNS = {
    "overtake": 6.0, "overtake_multi": 20.0, "leadchange": 12.0,
    "battle": 25.0, "closing": 30.0, "pulling_away": 45.0,
    "fastlap": 15.0, "spin": 8.0, "offtrack": 12.0, "retire": 10.0,
    "pit": 10.0, "yellow": 20.0, "penalty": 15.0, "traffic": 40.0,
    "green_again": 15.0,
    # Each safety-car beat happens ONCE per deployment, so these are floors
    # against a state that flickers rather than pacing for repetition — except
    # the two colour pools, which are paced like any other filler.
    "sc_out": 30.0, "sc_green": 20.0, "sc_green_last": 20.0,
    "sc_ending": 20.0, "sc_pits_open": 30.0, "sc_pits_shut": 30.0,
    "sc_field": 45.0, "sc_wait": 60.0,
    "milestone": 90.0, "standings": 60.0, "analysis": 35.0,
    "analysis_era": 120.0, "strategy": 90.0, "verdict": 20.0,
    "praise": 60.0, "criticism": 60.0, "recovery": 45.0,
    "final_laps": 60.0, "session": 300.0, "restart": 15.0,
    "track_fact": 150.0, "track_character": 240.0,
    # Race-flow categories. Long cooldowns by design: these are the booth
    # filling honest dead air, and dead air is preferable to a booth that
    # reads the running order every thirty seconds.
    "retake": 8.0, "midpack": 70.0, "midpack_recovery": 150.0,
    "lap_report": 45.0, "lap_milestone": 300.0, "time_remaining": 240.0,
    "insight_lead_big": 110.0, "insight_lead_slim": 70.0,
    "insight_podium_fight": 100.0, "insight_field_spread": 150.0,
    "insight_laps_left": 90.0,
    "podium_watch": 90.0, "podium_lock": 300.0,
    "arc_cost": 150.0, "arc_recovered": 120.0,
    "summary": 200.0,
    "stat_laps_led": 200.0, "stat_lead_changes": 180.0,
    "stat_running": 260.0, "stat_covered": 240.0,
    # LEVITY. Long, and sharing a family gate on top (see HUMOUR_CATS): the
    # difference between a booth with a sense of humour and a comedy podcast
    # is entirely how often it reaches for one.
    "booth_joke": 260.0, "booth_dig": 300.0, "analyst_dig": 300.0,
    "dig_stuck": 240.0, "dig_wide": 200.0,
    "podium_final": 60.0, "race_verdict": 60.0, "signoff": 60.0,
    "battle_sustained": 60.0, "overtake_long": 10.0, "ranwide": 20.0,
    # The layers of a fight. `battle_three` and `battle_traded` are rarer
    # events than a plain battle and are allowed to be, but they describe a
    # situation that PERSISTS - so they need a real cooldown or the queue
    # that lasts ten laps gets narrated every twenty-five seconds.
    "battle_three": 90.0, "battle_traded": 80.0,
    # THE DIVISION. Said rarely: it is true all season, so it is context
    # rather than news, and a booth that keeps explaining what Formula 4 is
    # has stopped watching the race.
    "div_kart": 400.0, "div_f4": 400.0, "div_f3": 400.0, "div_f2": 400.0,
    "div_f1": 400.0, "div_hatch": 400.0,
    "prog_stake": 420.0, "prog_last_chance": 300.0,
    "prog_debut": 600.0, "prog_measured": 420.0,
    # THE TEAM-MATE. The comparison is true all afternoon, so it is the
    # cadence that keeps it a fact rather than a nag — see MATE_CATS, which
    # puts the whole family behind one gate as well (LAW 15).
    "mate_ahead": 240.0, "mate_behind": 240.0,
    "mate_pass": 20.0, "mate_passed": 20.0,
    "mate_quali_up": 300.0, "mate_quali_down": 300.0,
    # The season record. Said rarely: it is a standing fact, not news,
    # and it only changes once a weekend.
    "mate_record": 600.0, "mate_record_races": 600.0,
    "battle_escaped": 55.0,
    "offtrack_cut": 12.0, "offtrack_more": 8.0, "offtrack_chaos": 25.0,
    "offtrack_late": 20.0,
    # Qualifying. Longer than a race's equivalents: a session where nothing
    # happens for two minutes at a time needs a booth that can be quiet.
    "quali_pole": 8.0, "quali_fastlap": 20.0, "quali_improve": 25.0,
    "quali_final": 300.0, "quali_count": 90.0, "quali_standings": 75.0,
    "quali_nobody": 60.0, "quali_onlyone": 90.0, "quali_pits": 120.0,
    "quali_lap_sector": 55.0, "quali_lap_allround": 60.0,
    "quali_top3": 95.0, "quali_all_run": 1e9, "quali_margin_big": 45.0,
    "quali_margin_slim": 45.0,
    "quali_duel": 150.0, "quali_tail": 200.0, "quali_offpace": 220.0,
    "quali_player_offpace": 240.0,
    # A deletion is news every time it happens; the pacing is done by
    # QUALI_DELETED_GAP at the source, which is where the "three in a row at
    # the same corner" case is actually handled.
    "quali_deleted": 40.0,
    # The end-of-qualifying wrap. Scripted beats, forced past the cooldown
    # like the race wrap is, so these numbers only matter if one ever reaches
    # the filler path.
    "quali_over_pole": 600.0, "quali_over_solo": 600.0,
    "quali_over_top3": 600.0, "quali_over_top2": 600.0,
    "quali_over_verdict": 600.0, "quali_over_player": 600.0,
    "quali_over_signoff": 600.0,
    "quali_solo": 150.0, "quali_open_laps": 180.0, "quali_goals": 200.0,
    # The past. Said once at the top of the show and rarely again — a booth
    # that keeps bringing up last season is not watching this race.
    "career_won_here": 400.0, "career_podium_here": 400.0,
    "career_back": 400.0, "career_been_here": 400.0,
    "career_first_visit": 400.0, "career_dnf_here": 400.0,
    "career_form": 300.0, "quali_lap_praise": 45.0,
    "grid_progress": 150.0, "grid_slipped": 180.0,
    "archive_open": 600.0, "archive_era": 150.0, "archive_watch": 200.0,
    # The season. Said once at the top and once at the wrap; a booth that
    # keeps returning to the points table is not watching this race.
    "season_round": 600.0, "season_round_open": 600.0, "season_opener": 600.0,
    "season_launch": 900.0, "season_launch_open": 900.0,
    "season_round_anytrack": 600.0, "season_midway": 600.0,
    "season_late": 600.0, "season_here": 400.0, "season_here_dnf": 400.0,
    "season_here_won": 400.0,
    "season_finale": 600.0, "title_lead": 600.0, "title_chase": 600.0,
    # THE ARITHMETIC IS SAID ONCE. It does not change during a session, so
    # a second telling is the same sentence with nothing new in it.
    "title_needs": 900.0, "title_needs_finish": 900.0,
    # ...but CROSSING the line can happen more than once in a race, and
    # each crossing is real news. Short enough to call a genuine swing,
    # long enough that a car wobbling either side of the place does not
    # produce a stream of them.
    "title_live": 45.0, "title_lost": 45.0,
    "championship_after": 120.0, "championship_lead": 120.0,
    "title_decided": 120.0,
    # WHO THESE PEOPLE ARE. Long cooldowns, and a longer FAMILY gate on top
    # (see DRIVER_CATS): the booth may introduce a driver, it may not read a
    # record book. Every one of these is also once-per-driver-per-session.
    "driver_reigning": 240.0, "driver_chasing": 220.0,
    "driver_champion": 200.0, "driver_favourite": 220.0,
    "driver_winner": 190.0, "driver_winless": 190.0,
    "driver_rookie": 200.0, "driver_new_team": 210.0, "driver_note": 170.0,
    "driver_season_wins": 180.0,
    # THE RACE STORY. A report on one driver's afternoon, as a two-hander.
    # Long, because the whole point is that it is an occasion rather than a
    # filler line, and once per driver per race on top of that.
    "story_ask": 200.0,
    # MULTICLASS. Only ever offered in a genuine mixed-class race, which
    # `s.multiclass` now means — a team-named F1 grid is one championship.
    "class_lead": 150.0, "class_pos": 120.0, "class_battle": 60.0,
    "class_traffic": 90.0,
    # The elaborated history two-hander. Its own gate, separate from the
    # short-form DRIVER_CATS family, because they are different registers of
    # the same knowledge and one does not exhaust the other.
    "driver_ask": 230.0,
    # Wrap beats. Scripted and forced, so these only matter if one somehow
    # reaches the filler path.
    "wrap_impressed": 600.0, "champ_extends": 300.0, "champ_closes": 300.0,
    "champ_next": 300.0,
    # The machinery. Same family as the driver facts and the same restraint —
    # a booth that explains every car on the grid is a technical briefing.
    "team_strength": 230.0, "team_weakness": 230.0, "team_note": 210.0,
    "car_character": 200.0,
    # The running totals. These are scripted wrap beats, not filler — they
    # fire once at the flag and are forced past the cooldown anyway. The
    # numbers here only matter if one somehow reaches the filler path.
    "driver_title_first": 600.0, "driver_title_more": 600.0,
    "driver_first_win": 300.0, "driver_win_tally": 300.0,
    "practice_note": 150.0, "quali_start": 300.0, "practice_start": 300.0,
    "interview": 150.0, "pregrid": 300.0, "race_duration": 300.0,
    "broadcast": 420.0, "broadcast_archive": 420.0,
    # THE NETWORK. Longer than the ident, because an ident tells a viewer who
    # arrived late what he is watching and these do not — they are flavour.
    # The easter egg is the longest of anything in the product: the whole
    # value of a nod to the old station is that it is a surprise, and a
    # surprise on a five-minute timer is a running joke.
    "broadcast_promo": 900.0, "broadcast_promo_archive": 900.0,
    "broadcast_racertv": 1500.0, "broadcast_racertv_archive": 1500.0,
}

# How long a full course yellow has to run before the booth remarks on the WAIT
# itself. Two minutes: long enough that it is genuinely dragging, short enough
# that the user's six-minute period gets a few of them rather than one.
SC_LONG = 120.0

# SESSION TYPES THE BOOTH DOES NOT COVER. Nobody broadcasts a practice session:
# no crowd, no result, and a booth narrating one is the first thing here that
# does not happen in real life. The engineer runs those sessions instead, which
# he already did. "test" is rF2's no-session state (garage, no track, no cars).
BOOTH_SILENT = ("practice", "test")

# Higher wins when several events fire on the same tick.
PRIORITY = {
    "win": 100, "lastlap": 90, "leadchange": 85, "spin": 80, "retire": 78,
    "start": 95, "start_chaos": 88, "restart": 82, "yellow": 75,
    "overtake_multi": 70, "overtake": 60, "penalty": 55, "offtrack": 50,
    "fastlap": 45, "podium": 65, "battle": 40, "recovery": 38, "pit": 35,
    "green_again": 74,
    # THE SAFETY CAR. Deployment and the restart are top-of-the-race calls: the
    # whole order has just been reset, and a green flag on the last lap is the
    # single most dramatic thing that can happen to a race. The colour while the
    # field circulates sits down with the filler, because it IS filler — the
    # difference is that behind a safety car there is nothing else to say.
    "sc_out": 92, "sc_green_last": 96, "sc_green": 86,
    "sc_ending": 84, "sc_pits_open": 60, "sc_pits_shut": 52,
    "sc_field": 22, "sc_wait": 12,
    "closing": 30, "traffic": 28, "final_laps": 42, "milestone": 20,
    "standings": 18, "session": 25,
    # THE RESOLUTION OF A FIGHT IS NOT COLOUR, IT IS THE END OF A STORY THE
    # BOOTH HAS BEEN TELLING. At 15 this sat below the standings and could
    # never win a tick against anything - which, together with having no
    # emitter at all, is why the escape has never once been called. Above
    # both battle pools (the fight) and below `overtake` (a pass is still the
    # bigger news), because that is the order those three things matter in.
    "pulling_away": 58,
    # Three cars for one place outranks a plain battle: it is the same
    # situation with a queue behind it, and the queue is the point.
    "battle_three": 46,
    # Two men swapping a place over and over is the best thing a midfield
    # can produce, and it is rare enough to be worth interrupting for.
    "battle_traded": 58,
    # A PASS ON YOUR OWN TEAM-MATE IS NOT AN ORDINARY PASS. It is the same
    # car, so it is the one overtake in the race that cannot be explained
    # away by machinery — above every other pass, below a lead change.
    "mate_pass": 78, "mate_passed": 78,
    "mate_ahead": 24, "mate_behind": 24,
    "mate_quali_up": 40, "mate_quali_down": 40,
    "mate_record": 23, "mate_record_races": 23,
    # The programme is what the season is FOR, so it sits with the career
    # lines it belongs to rather than with the colour.
    "div_kart": 16, "div_f4": 16, "div_f3": 16, "div_f2": 16,
    "div_f1": 16, "div_hatch": 16,
    "prog_stake": 30, "prog_last_chance": 44, "prog_debut": 46,
    "prog_measured": 28,
    # The resolution of a named fight - the payoff for a battle the booth
    # has been telling the story of. Same worth as the leader escaping.
    "battle_escaped": 58,
    "analysis": 12, "analysis_era": 10, "strategy": 11, "verdict": 14,
    "track_fact": 16, "track_character": 17,
    "praise": 13, "criticism": 13,
    # A retake is a hotter moment than the pass that provoked it — the fight
    # is the story, not the position.
    "retake": 68,
    # Flow and colour. These only ever compete with each other: anything real
    # outranks all of them, which is the intended relationship.
    "interview": 26, "lap_milestone": 22, "time_remaining": 21,
    "insight_laps_left": 21, "insight_lead_slim": 20, "lap_report": 19,
    "insight_podium_fight": 19, "arc_recovered": 18, "midpack_recovery": 17,
    "midpack": 16, "arc_cost": 16, "podium_lock": 15, "insight_lead_big": 14,
    "podium_watch": 13, "summary": 12, "insight_field_spread": 9,
    "stat_laps_led": 10, "stat_lead_changes": 11, "stat_running": 9,
    "stat_covered": 9,
    # The lowest priority of anything in the product, by design: every real
    # thing on track outranks every joke, always.
    "booth_joke": 7, "booth_dig": 6, "analyst_dig": 6,
    "dig_stuck": 8, "dig_wide": 8,
    "broadcast": 8, "broadcast_archive": 8,
    # Below the ident, which is already the bottom of the pile. Continuity
    # loses to every single thing that is actually happening on track.
    "broadcast_promo": 5, "broadcast_promo_archive": 5,
    "broadcast_racertv": 4, "broadcast_racertv_archive": 4,
    "pregrid": 60, "race_duration": 55,
    # Story-aware win calls. Same moment as `win`, told with the arc that got
    # them there.
    "win_charge": 100, "win_comeback": 100, "win_duel": 100, "win_wire": 100,
    # The incident family. Chaos outranks a single spin because "several cars
    # are off" is the bigger fact; the apology for cutting in outranks both,
    # since by then the booth is already talking over itself.
    "offtrack_chaos": 86, "offtrack_cut": 84, "offtrack_more": 52,
    "offtrack_late": 34, "ranwide": 33,
    # A pass that ended a long fight is worth more than the fight was.
    "overtake_long": 66, "battle_sustained": 44,
    # Qualifying. Provisional pole is that session's lead change, and is
    # ranked to match; the rest is colour competing only with itself.
    "quali_pole": 85, "quali_fastlap": 60, "quali_improve": 40,
    "quali_final": 58, "quali_start": 55, "practice_start": 55,
    "quali_standings": 20, "quali_count": 14, "quali_onlyone": 16,
    # A duel for pole outranks a single fast lap: it is the story of the
    # session rather than an event in it. The margin calls sit just under
    # the pole call they qualify, so they land as a follow-up, not instead.
    "quali_duel": 62, "quali_margin_big": 50, "quali_margin_slim": 48,
    "quali_lap_sector": 46, "quali_lap_allround": 46,
    "quali_top3": 22, "quali_tail": 13, "quali_offpace": 12,
    "quali_player_offpace": 17,
    # Above every other qualifying line. A lap being taken away is the single
    # most consequential thing that can happen in a timed session, and it is
    # news the driver may not otherwise know.
    "quali_deleted": 72,
    # The flag in qualifying is the moment of the session.
    "quali_over_pole": 95, "quali_over_solo": 95, "quali_over_top3": 66,
    "quali_over_top2": 66, "quali_over_verdict": 60, "quali_over_player": 64,
    "quali_over_signoff": 30,
    "quali_nobody": 15, "quali_pits": 11, "quali_solo": 13,
    "quali_open_laps": 12, "quali_goals": 10, "practice_note": 11,
    # History outranks the rest of the colour: it is the one thing said in
    # the whole broadcast that no other overlay can say at all.
    "career_won_here": 30, "career_podium_here": 29, "career_back": 28,
    "career_dnf_here": 28, "career_been_here": 27, "career_first_visit": 26,
    "career_form": 24, "grid_progress": 23, "grid_slipped": 22,
    "archive_open": 58, "archive_era": 11, "archive_watch": 10,
    # Above the track history: which round of a championship this is outranks
    # what happened here last year.
    # A CHAMPIONSHIP BEING DECIDED ON THE ROAD OUTRANKS EVERYTHING BUT THE
    # FLAG ITSELF. It is the reason the viewer is watching the last race of
    # a season, and a pass for seventh cannot be allowed to talk over it.
    "title_live": 88, "title_lost": 88,
    "title_needs": 36, "title_needs_finish": 36,
    "season_opener": 34, "season_finale": 34, "title_lead": 33,
    "title_chase": 33, "season_round": 32, "season_round_open": 32, "season_round_anytrack": 32,
    "season_launch": 40, "season_launch_open": 40,
    "season_midway": 35, "season_late": 34,
    "season_here": 31, "season_here_dnf": 31, "season_here_won": 31,
    "title_decided": 64, "championship_lead": 63, "championship_after": 62,
    # Who a driver IS ranks just above the circuit trivia and just below the
    # career history, which is the right order: what happened to YOU here
    # beats what this man did before you ever met him, and both beat the
    # length of the pit straight.
    "driver_reigning": 21, "driver_chasing": 21, "driver_champion": 20,
    "driver_note": 20, "driver_new_team": 19, "driver_favourite": 19,
    "driver_winner": 18, "driver_rookie": 18, "driver_winless": 17,
    # What he has done in YOUR season outranks what he did before it.
    "driver_season_wins": 23,
    # Above the rest of the colour: a driver's race is the most interesting
    # thing the booth can talk about when nothing is happening in front of
    # it, and it is the thing a viewer cannot get from the timing screen.
    "story_ask": 27,
    # A class position is the real result in a mixed race, so these rank
    # with the running order rather than with the colour.
    "class_battle": 41, "class_pos": 24, "class_lead": 23,
    "class_traffic": 27,
    "driver_ask": 25,
    "wrap_impressed": 61, "champ_extends": 62, "champ_closes": 62,
    "champ_next": 60,
    # The car ranks under the man. A record is about a person the viewer is
    # watching; a car characteristic is context for what that person does.
    "team_note": 17, "team_strength": 16, "team_weakness": 16,
    "car_character": 15,
    # A world championship is the biggest thing that happens in this sport,
    # and a first Grand Prix win is the second biggest. Ranked with the win
    # calls they follow rather than with the colour they are built from.
    "driver_title_first": 99, "driver_title_more": 99,
    "driver_first_win": 97, "driver_win_tally": 66,
}

# The driver-fact FAMILY.
#
# LAW 15: testing each of these categories on its own proves nothing, because
# they are all the same KIND of sentence. `driver_reigning` and
# `driver_chasing` are both correct, both about the champion, and back to back
# they are a man reading a record book at you. So the whole family shares one
# gate, and it is long.
# THE CAREER FAMILY. Every one of these is the booth talking about the man
# whose career this is, and back to back they are a man reading a CV (LAW 15).
# The register lines are in it too: "no television money in this paddock"
# followed by "he came up through every rung of this" is one thought said
# twice.
LADDER_CATS = (# THE JUNIOR PROGRAMME IS A CAREER LINE. "There is a Formula
               # One programme watching this car" and "a seat above this
               # category is on the line" are one thought, so they share the
               # family gate rather than being able to follow each other.
               "prog_stake", "prog_last_chance", "prog_debut",
               "prog_measured",
               "ladder_first_race", "ladder_reigning", "ladder_climb",
               "ladder_record", "ladder_arc", "ladder_promotion",
               "ladder_last_chance", "ladder_title_run",
               "ladder_home", "ladder_home_win", "ladder_nation",
               "status_rookie", "status_riser", "status_contender",
               "status_champion", "status_multi", "status_legend",
               "status_arrival", "status_arrival_more",
               "ladder_rivalry", "ladder_needle",
               "reg_grassroots", "reg_junior", "reg_professional")

# The six lines that say what he IS. Split out of the family above because
# the booth tracks whether one has been said this session: they answer a
# question a viewer asks once — "who is this?" — and answering it twice is
# how a broadcast sounds like it is not listening to itself.
STATUS_CATS = ("status_rookie", "status_riser", "status_contender",
               "status_champion", "status_multi", "status_legend")

# How long after the first mention of his name the booth adds what he is.
# Long enough to be a second thought rather than the same breath.
STATUS_FOLLOW = 2.5

# WHERE THE STATUS BELONGS, AND IT IS AN EDITORIAL LIST RATHER THAN A RULE.
#
# The user: "they should only casually address his status rather than
# repeatedly call him a rookie ... I also want it being used in correct
# context and not just randomly."
#
# The test is whether the status and the sentence are the same thought. "That
# is the rookie off at turn four" works because a rookie going off IS the
# story; so does a first podium, a promotion on the line, or the booth
# introducing his career. "The rookie is four tenths down in sector two" is a
# badge stapled to a gap, and hearing it forty times in an afternoon is what
# he was complaining about.
#
# ANYTHING NOT NAMED HERE GETS A NAME. That default is deliberate: a new pool
# has to ASK for the status form, so the next category added cannot quietly
# join the list by accident.
# ONE THOUGHT, SAID ONCE (LAW 15). Every one of these is "the man in the
# other side of the garage", and two of them back to back is the booth
# labouring a point it has already made.
MATE_CATS = ("mate_ahead", "mate_behind", "mate_pass", "mate_passed",
             "mate_quali_up", "mate_quali_down",
             "mate_record", "mate_record_races")
MATE_FAMILY_GAP = 200.0

# ...AND THE POOLS THAT SAY IT THEMSELVES MUST NOT ALSO BE HANDED IT.
#
# A LIVE BUG, heard in a karting session: "The rookie, the rookie. And Chuck,
# there is something about the way he is placing this car..." The template is
# `"The rookie, {drv}."` — written when `{drv}` was always a NAME — and the
# status form then filled the slot with the status as well.
#
# This is LAW 13 in its exact documented form: never put a determiner in front
# of a slot, because the slot carries its own article. The margin slots
# learned it first ("another a tenth"); this is the same mistake with a
# person instead of a gap.
#
# So the rule is: a pool whose PROSE states what he is gets a NAME in the
# slot. These are the lines that exist to announce the status — having it
# twice in one sentence is not emphasis, it is a bug the listener can hear.
STATUS_SELF = frozenset((
    "status_rookie", "status_riser", "status_contender",
    "status_champion", "status_multi", "status_legend",
    "status_arrival", "status_arrival_more",
    "driver_reigning",
))

STATUS_APT = frozenset((
    # A mistake, and the kind of mistake a status explains.
    "spin", "offtrack", "ranwide", "offtrack_more", "offtrack_chaos",
    "incident_id_off", "incident_id_spin", "offtrack_late",
    # What he has done, and what it is worth.
    "podium", "win", "fastlap", "recovery", "arc_recovered", "arc_cost",
    "title_live", "title_lost", "title_needs", "title_needs_finish",
    # The career beats. These are ABOUT who he is, so the status is the
    # subject rather than a decoration.
    "ladder_arc", "ladder_record", "ladder_climb", "ladder_promotion",
    "ladder_first_race", "ladder_reigning", "ladder_last_chance",
    "ladder_title_run", "ladder_home", "ladder_home_win", "ladder_nation",
    "status_arrival", "status_arrival_more",
    "status_rookie", "status_riser", "status_contender",
    "status_champion", "status_multi", "status_legend",
    # A sentinel for `_ladder_call`, which builds ONE slot dictionary and
    # returns a dozen different categories out of it — so the aptness is a
    # property of the whole function rather than of the branch taken. Every
    # line it can produce is about his career, which is precisely where the
    # status belongs.
    "_career",
))


# How long the whole family waits between lines. Long, because this is COLOUR
# about a career rather than news about a race, and because the facts do not
# change during a session — a second one five minutes later would be the same
# man being introduced twice.
LADDER_FAMILY_GAP = 420.0

DRIVER_CATS = ("driver_reigning", "driver_chasing", "driver_champion",
               "driver_favourite", "driver_winner", "driver_winless",
               "driver_rookie", "driver_new_team", "driver_note",
               "driver_season_wins",
               # The team lines are in the FAMILY too. "Hamilton, a seven-time
               # champion" followed by "Ferrari have a strong race car" is two
               # halves of the same briefing, and back to back they are a man
               # reading a programme out rather than calling a race.
               "team_strength", "team_weakness", "team_note")

# Minimum silence between ANY two driver facts, whatever the category.
DRIVER_FAMILY_GAP = 150.0

# How deep into the field the booth will introduce a driver at all. A fact
# about the man running nineteenth is true and worthless — the viewer cannot
# see him. The player is always in scope regardless of where he is running,
# because he is the one person the viewer is definitely watching.
DRIVER_FOCUS = 10

# How deep to look for a driver whose race is worth reporting on. Deeper than
# DRIVER_FOCUS, because a recovery drive in fourteenth is a better story than
# anything happening in fourth — and it is the one the viewer cannot see.
STORY_FOCUS = 16

# --------------------------------------------------------------------------
# RACE PHASES  —  the shape of a broadcast
#
# A real booth does not cover the field evenly for two hours. It follows the
# STORY, and the story has a shape:
#
#   OPENING   lap 1. Lock onto the front. Everything is happening at once and
#             the viewer needs the order established, not a P14 scrap.
#   SETTLING  the couple of laps after that. The race has an order now, so the
#             booth widens to the fights that formed behind the leaders — but
#             not yet to the whole field, and not yet to colour. This is the
#             state the user asked for in his own words: "around lap 3, start
#             broadening to other battles around the field, but overtakes stay
#             top priority". Overtakes staying on top is PRIORITY's job and
#             already works; what was missing was a depth between 5 and 99.
#   MID       the body of the race. Open up: battles anywhere, strategy,
#             colour, the wider field, era and track context.
#   LATE      final fifth. Narrow again to the places that will decide it.
#   CLOSING   final lap. The win, and nothing else that isn't enormous.
#
# `FOCUS_LIMIT` is that shape expressed as a number: the deepest position the
# booth will bother commentating in each phase. This single gate is what stops
# the overlay narrating a midfield scrap while the lead is changing, and it is
# the piece that most made RacerTV feel like a broadcast rather than a
# telemetry reader.
# --------------------------------------------------------------------------
FOCUS_LIMIT = {"opening": 5, "settling": 12, "mid": 99, "late": 8, "closing": 5}

# THE FIGHT FOR THE LEAD IN THE RUN TO THE FLAG OUTRANKS EVERYTHING.
#
# `PLACE_WEIGHT` biases toward the front everywhere, but it is a gentle bias:
# a battle for the lead (PRIORITY 40 + 30) scored 70 against a P4 overtake's
# 76, so the booth could be describing a midfield pass while the race was
# being decided in front of it. In the closing stages that is not a ranking
# error, it is the wrong broadcast. This bonus applies only in `late` and
# `closing`, only to the top two places, and only while the leader is actually
# being chased — a leader eleven seconds clear is not a fight and boosting him
# would just shout about a procession.
LATE_FRONT_BONUS = 60
LATE_FRONT_PLACES = (1, 2)

# ...and a smaller one for the SAME fight earlier in the race. Reported from a
# live session: *"I pulled up behind P1 to battle him for the lead and the
# commentators said nothing"*. A fight for the lead on lap nine is not colour
# to be weighed against a midfield pass — it is the race — and the old bonus
# was gated on the closing phase, so for the whole body of a race a P4
# overtake outscored it. Smaller than the late bonus because a mid-race lead
# fight can still be interrupted by a genuine incident, which is right; large
# enough that nothing routine outranks it.
FRONT_BONUS = 34

# How long the settling window lasts, in laps, once the opening is over. Two,
# because the opening is one lap on a sprint and two on anything longer, which
# puts the broadening at lap three or four — the "around lap 3" that was
# asked for, without a second length table to keep in step with the first.
SETTLE_LAPS = 2

# Fraction of a timed race remaining below which it counts as "late".
LATE_FRACTION = 0.18

# --------------------------------------------------------------------------
# RACE LENGTH  —  the same shape stretched over a different span
#
# The phase model above was only ever exercised on a 17-lap sprint, where
# fixed lap thresholds happen to work. They do not generalise:
#
#   a 5-lap race    "last four laps are late" makes 80% of the race late,
#                   and opening and closing very nearly touch.
#   a 60-lap race   "mid" becomes fifty laps of the same handful of filler
#                   categories, which is the single most boring failure mode
#                   this booth has.
#   an endurance    the story spans hours; a booth pitched at sprint urgency
#                   for three hours is exhausting, and one pitched at sprint
#                   cooldowns leaves enormous silences it has nothing to fill.
#
# So phases are computed from PROGRESS, and the boundaries themselves scale
# with the length. `_length_class` then adjusts the two things that actually
# need to differ by length: how deep the booth looks into the field, and how
# often it is allowed to reach for colour.
# --------------------------------------------------------------------------
LENGTHS = ("sprint", "normal", "long", "endurance")

# What a lead MEANS, in seconds. Below the slim figure the leader is being
# hunted; above the big one he is managing a race rather than racing one.
SLIM_LEAD = 1.5
BIG_LEAD = 9.0

# How soon a place has to come back for it to count as a retake rather than
# an unrelated pass.
RETAKE_WINDOW = 30.0

# How long two cars have to be locked together before the fight itself is the
# story — and before the pass that ends it counts as a breakthrough rather
# than a routine move.
LONG_FIGHT = 40.0

# --- THE PASS IS A MOMENT, AND A MOMENT NEEDS AUDIO ON IT ------------------
# A pass was detected correctly and then thrown away: `_say` refuses anything
# under priority 80 while audio is playing, `overtake` is 60, and detection is
# edge-triggered with no second chance. So the user took a podium place while
# Miles was mid-sentence and the booth never mentioned it at all. This is the
# same mechanism 5b-iii documents for the incident sting silencing its own
# explanation, turning up in a second place.
#
# The fix has two halves, because passes are not all worth the same:
#   * the ones that MATTER get the incident treatment - a sting and the named
#     call spoken in ONE breath, so nothing can lose the tick;
#   * every other pass gets a few seconds to find a gap, instead of being
#     binned on the tick it happened.
PASS_STING_PLACES = 3    # a pass INTO this place or better earns the sting
PASS_SEQ_GAP = 11.0      # ...and two of them inside this are one sequence
PASS_RETRY = 6.0         # how long an ordinary pass keeps trying to air.
                         # Beyond this it is not news: the viewer has watched
                         # the order change on the tower already.

# --- HOW A FIGHT ENDS ------------------------------------------------------
# `pulling_away` has six lines, a priority and a cooldown, and NOTHING has
# ever emitted it - the fourth dead pool found in this project (LAW 21). It
# is the resolution the user asked for by name: "if someone is battling for 2
# cars and finally pulls away then the commentator must say 'and he manages
# to pull away securing the position'".
#
# A fight only has a resolution worth calling if it was a fight worth
# watching, hence the minimum. And the escape has to be REAL: the gap crosses
# STRIKE_GAP every lap on every circuit, so a defender counts as clear only
# once he is half as far again beyond it and has STAYED there. Trigger and
# clear point, LAW 18, on a threshold that would otherwise re-arm out of
# every last corner.
BATTLE_RESOLVE_MIN = 14.0
BATTLE_CLEAR_GAP = STRIKE_GAP * 1.5
BATTLE_CLEAR_HOLD = 3.0

# Three cars covered by this, for this long, is a different story from two
# fights that happen to be adjacent - it is a queue, and everybody in it is
# racing the same piece of road.
THREE_WAY_HOLD = 9.0

# A place changing hands this often between the same two cars stops being a
# pass and becomes the story of their afternoon.
TRADE_MIN = 3
TRADE_WINDOW = 150.0

# Where "the midfield" starts. A driver inside this is being watched by the
# booth already, so "nobody has mentioned him" is not true of them.
MIDPACK_FROM = 5

# Share of the grid a car class must cover before it is treated as a real
# class rather than a team label. Mirrors `career.CLASS_SHARE`.
CLASS_SHARE = 0.4

# Before this much racing has happened, the booth may not make claims ABOUT
# the race so far — recoveries, arcs, "having a great afternoon". Two laps in
# there is nothing to have had a great afternoon during, and the viewer can
# see that. Both gates apply; see `_enough_race`.
# How many consecutive ticks a place must hold before the ARC believes it.
# At 20 Hz this is 150ms — invisible for a real overtake, and long enough to
# reject the scrambled-but-valid orders rF2 publishes around a standing
# start, which is what produced "30 places clawed back" about a man who
# started third.
ARC_CONFIRM_TICKS = 3

# How far the session clock has to jump BACKWARDS before it is read as a
# restart. Five seconds, matching `rf2_session._reset`'s own threshold: the
# clock never rewinds inside a single run of a session, and the margin only
# has to absorb the jitter of two buffers written at different rates.
RESTART_ET_DROP = 5.0

# WHERE ON THE ROAD IT HAPPENED IS PART OF HOW BIG IT IS.
#
# A real broadcast drops a midfield scrap the moment the fight for second
# gets interesting. The booth ranked events by CATEGORY alone, so a P8
# overtake and a P2 overtake were worth exactly the same, and filler ranked
# purely on staleness — which is how a podium battle lost the microphone to a
# midfield line that happened to be older. This is the missing weight: a
# bonus, in priority points, for the position the event concerns.
PLACE_WEIGHT = {1: 30, 2: 26, 3: 22, 4: 16, 5: 13, 6: 10, 7: 7, 8: 5}
PLACE_WEIGHT_TAIL = 2

STORY_MIN_LAPS = 3
STORY_MIN_FRACTION = 0.15

# Places gained or lost against the grid before it is worth remarking on.
GRID_MOVE = 3

# Incidents inside this window are one event, not several — that is what
# turns "he's off" into "and another one" into "it's chaos out there".
CHAOS_WINDOW = 14.0

# When a late identification is still worth giving: long enough after the
# alert that the immediate call clearly did not happen, soon enough that the
# viewer still remembers the incident.
LATE_ID = (6.0, 30.0)

# Minimum gap between any two pre-rendered stings. They are name-free and
# interchangeable, so several in quick succession stop sounding like
# reactions and start sounding like a soundboard.
STING_GAP = 9.0

# Minimum gap between two full incident SEQUENCES. Longer than STING_GAP: a
# sequence is three beats and the best part of ten seconds of audio, so two
# of them overlapping is the booth talking over itself about two different
# cars. A second incident inside this window still gets its single named call
# through the ordinary event path.
INCIDENT_SEQ_GAP = 14.0

# Seconds left in qualifying when it becomes "last chance for a flyer".
QUALI_FINAL = 120.0

# When a benchmark lap in qualifying is worth remarking on. See
# `_quali_lap_notable` — the point is that an early pole means nothing.
QUALI_LATE_FRACTION = 0.4     # session this far from the end, or closer
QUALI_RUN_FRACTION = 0.6      # ...or this much of the field has set a time
QUALI_BIG_GAIN = 0.4          # ...or the lap took this many seconds out
QUALI_PRAISE_CHANCE = 0.8     # how often a notable lap actually draws a word

# HOW BIG A POLE MARGIN IS. Measured against the RUNNER-UP's actual lap, not
# against the improvement on the old benchmark: a driver can take half a
# second off his own time and still be a hundredth ahead of the next man.
QUALI_BIG_MARGIN = 0.30       # a dominant lap
QUALI_SLIM_MARGIN = 0.06      # ...and one that barely counts

# WHERE A LAP WAS WON. If one sector accounts for this much of the time
# gained, that sector IS the story; below it the driver found time
# everywhere, which is a different and better thing to say.
QUALI_SECTOR_SHARE = 0.55

# A FIGHT FOR POLE. One change at the top is a fast lap; several between the
# same two drivers is a duel. The window stops a scrap early in the session
# still reading as a duel half an hour later.
QUALI_DUEL_SWAPS = 3          # changes at the top inside the window
QUALI_DUEL_WINDOW = 420.0     # ...within seven minutes
QUALI_DUEL_CD = 150.0         # and don't call it again immediately

# THE BOTTOM OF THE SHEET. Every one of these is a guard against saying
# something false: a four-car test session has no "tail", and a driver who
# has not run yet is not slow, he is absent.
# Share of the field still without a time before "everyone is in the pits"
# is a story rather than simply the session being over.
QUALI_PITS_WAITING = 0.25

QUALI_TAIL_MIN_FIELD = 10     # a real field, not a private test
QUALI_TAIL_SHARE = 0.7        # this much of it must have set a time
QUALI_TAIL_FROM = 12          # the player is "down the order" from here
QUALI_OFFPACE_S = 1.0         # ...and this far off pole to be off the pace

# How many recorded races a driver needs before "first time at this circuit"
# is worth saying. On race one of a career every circuit is a first visit,
# and the observation means nothing.
FIRST_VISIT_AFTER = 5

# Rounds that must be in the books before the championship table is worth
# mentioning. Two races in, a "title fight" is an artefact of the calendar.
TITLE_TALK_AFTER = 3

# Any of these naming a driver discharges the debt the nameless alert sting
# created. Used to decide whether the booth still owes an identification.
INCIDENT_CATS = {"spin", "offtrack", "ranwide", "offtrack_cut",
                 "offtrack_more", "offtrack_chaos", "offtrack_late",
                 "retire", "penalty"}

# Colour-category cooldowns are multiplied by this. A long race needs the
# booth to talk MORE between events, not less, because there is more dead air
# to carry and the same six lines will not stretch across an hour.
COLOUR_SCALE = {"sprint": 1.25, "normal": 1.0, "long": 0.72, "endurance": 0.6}

# Minimum silence before the booth is allowed to fill. Longer than the global
# cooldown, and LONGER on a long race, not shorter: the point of scaling the
# per-category cooldowns down is that filler is more VARIED over three hours,
# not that there is more of it.
FILLER_GAP = {"sprint": 12.0, "normal": 15.0, "long": 18.0, "endurance": 22.0}

# --------------------------------------------------------------------------
# LEVITY
#
# The user asked for it directly: "wheres the jokes and banter and little
# digs? its nice to have some comedic moments on track". He is right, and a
# booth with no lightness in it is exhausting over an hour.
#
# But humour is the single easiest thing in this product to get catastrophically
# wrong, because the cost is asymmetric. A joke that lands adds a little. A
# joke over a driver sitting in a wrecked car destroys the whole illusion in
# one line, and no amount of good commentary afterwards repairs it — the
# viewer now knows nobody is really watching.
#
# So levity is GATED, not cooled down. The gate is a hard veto, checked before
# a joke is even offered, and it is deliberately generous: silence is free.
#
#   an incident         nothing funny for a while after ANY off, spin or
#                       retirement, whoever it happened to
#   a yellow            the race is neutralised because something went wrong
#   the closing phase   the end of a race is not the place, and the end of a
#                       CHAMPIONSHIP is really not
#   the player in
#   trouble             he is the one person who cannot be laughed at, because
#                       he is the one person actually having a bad afternoon
#
# The one thing this deliberately does NOT gate on is the player being slow.
# Being off the pace is not a misfortune, it is racing, and a booth that never
# ribs the man driving is not a booth, it is a press officer.
# --------------------------------------------------------------------------
LEVITY_AFTER_INCIDENT = 100.0   # quiet for this long after anything goes wrong
LEVITY_MIN_LAPS = 3             # ...and never before the race has settled

# THE HUMOUR FAMILY (LAW 15). Five correct categories that are all "the booth
# being light", and back to back they are a comedy show with a race on in the
# background. One of these every few minutes at most, whichever it is.
HUMOUR_CATS = ("booth_joke", "booth_dig", "analyst_dig", "dig_stuck",
               "dig_wide")
HUMOUR_FAMILY_GAP = 210.0

# THE STATION FAMILY (LAW 15, again). The ident, the plug for the other
# channel and the nod to the sister station are three correct categories that
# are all "the booth talking about the broadcast instead of the race". Back to
# back they are a station promo reel — the exact failure `quali_standings` and
# `quali_top3` produced, in a different costume.
#
# The archive variants are IN THE SAME FAMILY as the modern ones even though
# only one set can ever air in a session, because the gate is keyed on time
# rather than on which pool won: one family, one clock, no way for a change of
# seat to reset it.
# What rF2's own status message says when it takes a lap away. Matched with
# the word "lap" alongside, because "invalid" on its own appears in messages
# that are not about a lap at all — and a driver told his lap has gone when it
# has not is precisely the wrongness that kept this feature unbuilt.
#
# THESE ARE A BEST GUESS AT THE SIM'S WORDING and the first thing to check
# against a real session: `testrun.py` logs every status message it sees under
# STATUSMSG, so one qualifying run answers it exactly. Adding a phrase here is
# the whole fix if the real text differs.
DELETED_WORDS = ("invalid", "deleted", "disallow", "not count", "no time",
                 "cancelled", "canceled")

# One deletion call per this many seconds. Track limits at a circuit with a
# nasty exit can delete three laps in a row, and a booth that announces each
# one is a rules commentary rather than a broadcast.
QUALI_DELETED_GAP = 45.0

STATION_CATS = ("broadcast", "broadcast_archive",
                "broadcast_promo", "broadcast_promo_archive",
                "broadcast_racertv", "broadcast_racertv_archive")
STATION_FAMILY_GAP = 300.0

# How many separate excursions before a driver becomes fair game for it.
# Two is unlucky; three is a pattern the viewer has also noticed, which is
# what makes the line land instead of look mean.
DIG_WIDE_OFFS = 3

# How much staleness a change of voice is worth when ranking filler. Roughly
# half a minute: enough to break up a monologue, not enough to hand the
# microphone to someone with nothing to say.
HANDOVER_BONUS = 30.0

# Categories that COLOUR_SCALE applies to: the ones the booth reaches for when
# nothing happened. Event categories are never stretched — an overtake is as
# urgent in hour three as it is on lap two.
COLOUR_CATS = {
    "analysis", "analysis_era", "strategy", "standings", "milestone",
    "track_fact", "track_character", "session", "interview",
    "insight", "lap_report", "midpack", "broadcast",
    "stat_laps_led", "stat_lead_changes", "stat_running", "stat_covered",
    "broadcast_archive",
    "broadcast_promo", "broadcast_promo_archive",
    "broadcast_racertv", "broadcast_racertv_archive",
    "archive_era", "archive_watch",
    "driver_reigning", "driver_chasing", "driver_champion", "driver_favourite",
    "driver_winner", "driver_winless", "driver_rookie", "driver_new_team",
    "driver_note", "driver_season_wins",
    "class_lead", "class_pos", "class_traffic",
    "team_strength", "team_weakness", "team_note", "car_character",
    "booth_joke", "booth_dig", "analyst_dig", "dig_stuck", "dig_wide",
}

# How long after a play-by-play call the analyst may respond, and how often
# he takes the opportunity. Crosstalk is what makes two voices feel like a
# conversation rather than two independent narrators.
# --------------------------------------------------------------------------
# THE TOP OF THE SHOW  —  a running order, not three racing checks
#
# "Welcome to FACTORtv — we're at Zandvoort — here's the grid — and it's a
# forty-lap race" is ONE sequence with an order, and it has to survive being
# cut off at any point by the green flag, because the booth does not control
# when the session starts.
# --------------------------------------------------------------------------
PRE_RACE = ("intro", "archive", "season", "career", "scene", "history",
            "grid", "who", "format")
PRE_QUALI = ("intro", "archive", "season", "career", "scene", "who", "qstart")
PRE_RACE_GAP = 1.6

# Event priority that ends the running order early. Set above the colour
# categories and below nothing that matters: anything the booth would call
# news outranks the script.
PRE_YIELD = 55

# How long the pre-session sequence waits for a gap before giving up. Long
# enough to survive a busy opening — a qualifying session is nothing but news
# for the first minute — and short enough that the welcome never lands halfway
# through a session it was supposed to open.
PRE_HOLD = 150.0

# And the same at the other end: the flag is not the end of the programme.
# Longer beats here, because nothing is competing for the time and a wrap
# delivered at race pace sounds like a man in a hurry to leave.
# THE WRAP. Four beats was not a wrap — podium, standings, one verdict,
# goodbye — and it said nothing about how anybody had actually driven.
#
#   topraces   how the men on the podium got there, in their own words
#   impressed  Chuck's own pick, and deliberately NOT the winner
#
# Both reuse the mid-race story machinery, so a driver described as
# recovering on lap thirty is described the same way at the flag.
POST_RACE = ("podium", "tally", "topraces", "impressed", "championship",
             "verdict", "signoff")
POST_RACE_GAP = 3.0

# THE END OF QUALIFYING. The same shape as the race wrap and for the same
# reason: the flag falls, the sheet is final, and a broadcast says so.
#
#   pole      who is on it, and by how much
#   frontrow  the top three read as a grid rather than a timesheet
#   verdict   Chuck on what a driver has to do with the slot he has
#   yours     where the PLAYER ended up, which no other beat covers
#   signoff   see you tomorrow
POST_QUALI = ("pole", "frontrow", "qverdict", "yours", "qsignoff")

CROSSTALK_WINDOW = 4.0

# A booth CONVERSATION — Miles asks, Chuck answers, Miles takes it back.
# Beats are short because a pause between question and answer sounds like a
# satellite delay, and the whole exchange times out because a reply that
# arrives after the race has moved on is not a reply.
CONVO_BEAT = 1.3
CONVO_TIMEOUT = 25.0
CONVO_ACK = 0.5

CROSSTALK_CATS = {
    "overtake": ("verdict", 0.45),
    "overtake_multi": ("verdict", 0.7),
    "leadchange": ("verdict", 0.6),
    "spin": ("criticism", 0.6),
    "offtrack": ("criticism", 0.35),
    "fastlap": ("praise", 0.4),
    "retake": ("verdict", 0.5),
    # NB there is deliberately NO entry here for `quali_pole` /
    # `quali_fastlap`. A benchmark lap draws a reaction only when
    # `_quali_lap_notable()` says the session has matured enough for it to
    # mean anything, and `_quali_detect` calls `_maybe_crosstalk` itself once
    # that test passes. Listing them here as well would let every lap through
    # by the generic route and quietly defeat the whole gate — which is
    # exactly what it did the first time.
    "overtake_long": ("praise", 0.6),
    "battle_sustained": ("analysis", 0.5),
    # Somebody has to say "hope they're all right" — and after the booth has
    # cut its own conversation short to report it, an answer from the other
    # chair is what closes the loop.
    "offtrack_cut": ("offtrack_ack", 0.8),
    "offtrack_chaos": ("offtrack_ack", 0.6),
    "ranwide": ("offtrack_ack", 0.3),
    "pit": ("strategy", 0.5),
    "battle": ("analysis", 0.35),
    # THE END OF A FIGHT DESERVES THE VERDICT MORE THAN THE START OF ONE
    # DOES. "He held him off for eight laps and got away with it" is exactly
    # the sentence the analyst chair exists for, so this is the highest
    # chance in the table outside the incident acknowledgements.
    "pulling_away": ("praise", 0.65),
    "battle_traded": ("verdict", 0.6),
    "battle_three": ("analysis", 0.5),
    "mate_pass": ("verdict", 0.7),
    "mate_passed": ("verdict", 0.7),
    "mate_quali_up": ("analysis", 0.5),
    "mate_quali_down": ("analysis", 0.5),
    "battle_escaped": ("praise", 0.65),
}


class _Snap(object):
    """Last tick's view of one car, for delta detection.

    `place` is what rF2 said this tick. `conf` is the place that had HELD long
    enough to be believed — and THE TWO MUST NEVER BE COMPARED WITH EACH OTHER.
    That comparison is what silenced every overtake call in the product; see
    `_detect`.
    """
    __slots__ = ("place", "conf", "laps", "in_pits", "best", "speed",
                 "finished", "lap_valid", "sector")

    def __init__(self, c, conf=None):
        self.place = c.place
        self.conf = c.place if conf is None else conf
        self.laps = c.laps
        self.in_pits = c.in_pits
        self.best = c.best_lap
        self.speed = c.speed or 0.0
        self.finished = c.finish_status
        self.sector = c.sector


class BoothMixin(object):
    """Commentary direction. Mixed into the Overlay."""

    def booth_init(self):
        self._prev = {}
        self._last_spoke = 0.0
        self._cat_last = {}
        self._pending_caption = None
        self._reaction_for = None   # (call, answer, chance) armed by a detector
        self._said_start = False
        self._said_lastlap = False
        self._said_win = False
        self._session_key = None
        self._best_lap_seen = None
        self._battle_since = {}
        # Which side of the title-deciding position he was on last tick.
        # None means 'not applicable / not yet known', which is what stops
        # the first tick of a session announcing a crossing that never
        # happened (LAW 1 needs a BEFORE as well as an AFTER).
        self._title_side = None
        self._mate_last = -1e9   # the team-mate family gate
        # A pass that could not air on the tick it happened, kept alive for a
        # few seconds so a busy booth delays it instead of losing it.
        self._pending_pass = []     # [(cat, kw, car, expires)]
        self._pass_sting_at = 0.0
        # Fights that ENDED without a pass, waiting to be called.
        self._battle_done = []      # [(chaser, defender, held)]
        self._battle_clear = {}     # car id -> when the gap first opened up
        self._three_since = None    # (ids tuple, when) - a queue for one place
        self._trades = {}           # frozenset(pair) -> [times a place changed]
        self._was_green = False
        self._last_et_seen = 0.0
        self._yellow_on = False
        # THE SAFETY CAR: the last state seen, and when it came out.
        self._sc_state = 0
        self._sc_since = None
        self._phase = "mid"
        self._front_fight = False
        self._length = None
        self._length_at = 0
        self._field_size = 0
        self._said_intro = False
        self._signed_off = False
        self._said_chequered = False
        self._yellow_on = False
        # NOTHING SURVIVES A SESSION CHANGE, including a safety car. A state
        # left set would have the next race believing it is already neutralised.
        self._sc_state = 0
        self._sc_since = None
        self._arm_waited = False
        self._intro_at = 0.0
        self._pre = []              # pre-race running order, stages remaining
        self._pre_failed = set()    # stages that raised, one retry each
        self._status_named = False  # has his name been said this session
        self._status_told = False   # ...and has what he is been said
        self._status_follow = 0.0   # when the first mention aired
        self._pre_last = 0.0
        self._post = []             # the wrap, stages remaining
        self._convo = None          # exchange in progress
        self._convo_done = set()    # topics already used this session
        self._last_lap_seen = -1
        self._marks_done = set()    # distance / clock marks already called
        self._last_pass = None      # (passer, passed, place, when)
        self._last_voice = None     # who spoke last, for turn-taking
        self._incidents = []        # times of recent incidents, for clustering
        self._sting_at = 0.0        # when the nameless alert last fired
        self._sting_any = 0.0       # ...and when ANY sting last fired
        self._named_incident = True  # has the alert been followed up by name?
        self._q_best = None         # session-best lap in qualifying
        self._q_pole = None         # who holds it
        self._q_bests = {}          # car id -> their own best, for improvements
        self._q_pole_hist = []      # (car id, when) each change at the top
        self._q_duel_at = 0.0       # last "they are trading pole" call
        self._q_all_run = False     # "everyone has a time" already said?
        self._q_bench_secs = None   # sectors of the standing benchmark lap
        self._q_final = False
        self._q_set = 0
        self._q_banked = False
        self._q_climb = {}           # car id -> places climbed late in quali
        # HOW QUALIFYING WENT, for the whole grid, kept ACROSS the session
        # change into the race. That is the entire reason it exists: the
        # user took pole late in a session he was proud of and the booth
        # never referred to it again.
        self._quali_story = {}
        self._story_told = set()     # drivers already reported on this race
        self._hist_told = {}         # driver -> history angles already used
        self._season_armed = False   # has this session been matched yet?
        self._season_round = None    # which round of the career this is
        self._season_count = False   # ...and whether it will be recorded
        self._season_asked = False
        self._said_launch = False    # the "career mode is running" opener
        self._season_done = False    # result banked, once, at the flag
        # HIS RACE MAY NOT BE OVER WHEN THE RACE IS. See `_season_settle`.
        self._season_settle = None    # (started, last place written) or None
        self._story = {}            # car id -> {best, worst, now} place arc
        self._led_laps = {}         # car id -> laps completed while leading
        self._lead_changes = 0      # how many times the lead has actually moved
        self._led_seen = -1         # last leader-lap count credited
        self._facts_said = {}       # circuit slug -> facts already aired
        self._driver_said = {}      # driver name -> facts already aired
        self._off_watch = {}        # car id -> [max_wheels, ref_spd, min_spd, since]
        self._off_last = {}         # car id -> when we last called them off
        self._off_count = {}        # car id -> how many separate offs, for a dig
        self.player_off = None      # (kind, when) handed to the engineer
        # When rF2 last took a lap away from the player. Handed to the
        # engineer the same way `player_off` is, and cleared by him.
        self.player_lap_deleted = None
        self._q_deleted_at = -1e9
        self._q_count_flag = None
        self._stings = None
        self._caption = None
        self._caption_until = 0.0

    # -- main ---------------------------------------------------------------
    def _can_arm(self, s):
        """Is there enough published yet to decide which round this is?

        The three things `_season_arm` and `Career.match` actually read: a
        circuit the overlay can name, the player, and his car's CLASS — which is
        what a rung is matched on. rF2 publishes them a beat apart from the
        session appearing, and in the garage the gap is seconds rather than
        milliseconds.

        A career that does not exist needs no data: there is nothing to match, so
        that answer is available immediately and correctly.
        """
        car = getattr(self, "season", None)
        if car is None:
            return True
        me = getattr(s, "player", None)
        circuit = getattr(s, "circuit", None)
        return bool(me is not None
                    and circuit is not None and getattr(circuit, "known", False)
                    and (getattr(me, "cls", "") or "").strip())

    def _season_pre_arm(self, s, now):
        """Session housekeeping that must happen BEFORE anything is spoken.

        Three things belong here and none of them says a word:

        * NOTICING A NEW SESSION OR A RESTART, so the last race's arcs and
          "we have already said the start" are cleared. Noticing it only once
          the car is on track is noticing it late.
        * MATCHING THE ROUND, which is what the career prompt is waiting for.
        * remembering the green/elapsed state the restart test needs.

        It is deliberately dull. `update_booth` returns above the speaking gate
        for a session in the garage, and everything below that gate stays there.
        """
        # A RESTART keeps the same track and session index, so keying on
        # those alone meant the booth called the start once and then stayed
        # silent through every subsequent restart. The live test had four
        # green flags and exactly one start call. Going back to a pre-green
        # phase after having been green is the reliable restart signal.
        key = (s.track, s.session_index)
        et = getattr(s, "et", None) or 0.0
        if key != self._session_key:
            self._session_key = key
            self._new_session(s)
        elif self._was_green and not s.started:
            self._new_session(s)
        elif et < self._last_et_seen - RESTART_ET_DROP:
            # THE CLOCK GOING BACKWARDS IS A RESTART, and it is the signal
            # `rf2_session._reset` already trusts for exactly this.
            #
            # The green -> pre-green test above needs the booth to SEE a tick
            # in the gap between the two, and the user restarts constantly
            # because the game crashes on him — a restart that comes back
            # straight to a green grid, or one where the pre-green window
            # falls between two 20Hz ticks, left the booth carrying the whole
            # of the abandoned race: its arcs, its overtakes, its "we've
            # already said the start". Session elapsed time cannot go
            # backwards inside one run of a session, so this cannot false-fire.
            self._new_session(s)
        self._was_green = s.started
        self._last_et_seen = et
        if not self._season_armed and s.kind == "race":
            # ONCE PER SESSION — BUT NOT UNTIL THE ANSWER CAN BE KNOWN.
            #
            # THIS BROKE THE PROMPT, and the mistake is the one this file warns
            # about most often. Moving the arming into the garage put it ahead of
            # the data it needs: `_season_arm` gives up silently when the circuit
            # is not resolved yet, and because the flag was set FIRST, "I cannot
            # tell yet" was frozen into "this is not a round" for the whole
            # session. The user got no prompt at all and an OFF-CAREER badge
            # reading "Formula 4 paused" on a race that was round one.
            #
            # A LOOKUP KEYED ON STATE THAT DOES NOT EXIST YET — the same shape as
            # `simulate_round` reading a class the first race fills in, and
            # `installed_mods` caching an empty list. Ask what the key is filled
            # in BY, and whether that has happened yet.
            #
            # So the flag is set only when the decision was actually possible,
            # and otherwise it is tried again next tick. The deadline is the
            # green flag: by then the answer is whatever it is, and an honest
            # OFF-CAREER beats never deciding.
            #
            # RACE ONLY, HERE. Qualifying arms on the normal path below, where it
            # always did.
            if self._can_arm(s) or s.started:
                self._season_armed = True
                self._season_arm(s)
            elif not getattr(self, "_arm_waited", False):
                self._arm_waited = True
                self._log("SEASON", "holding the round decision until the "
                                    "circuit and car are published")

    def update_booth(self, s):
        if not self.booth_enabled or s is None or not s.valid:
            return
        # PRACTICE IS THE ENGINEER'S SESSION, NOT THE BOOTH'S.
        #
        # Asked for directly: *"if it is a practice session then disable all
        # commentary, lets just have the race engineer and driver, but for
        # quali and race sessions then we must have commentary."*
        #
        # He is right on the merits, and it is the same reasoning that puts the
        # inbox out of the car: NOBODY BROADCASTS A PRACTICE SESSION. There is
        # no crowd, no timing screen worth showing and no result — a booth
        # narrating one is the first thing in this product that does not happen
        # in real life. What a driver has in a practice session is his engineer,
        # and Dean already runs timed sessions (`_quali_radio` covers practice),
        # so the whole session becomes the pit wall by deleting a caller rather
        # than by writing anything.
        #
        # NOTHING IS LOST BY LEAVING EARLY. `_quali_bank` is already gated to
        # `kind == "quali"`, so no qualifying result depended on this path, and
        # a session change wipes the booth's state anyway.
        if s.kind in BOOTH_SILENT:
            return

        # WHICH ROUND THIS IS, DECIDED IN THE GARAGE — before the on-air gate.
        #
        # Asked for: *"you know how I start a race then I get a prompt for
        # either Y/N for this race to be counted towards career ... can we not
        # have the prompt come up when we are in the pit screen before the event
        # starts, as I will at least have time to accept and read it properly."*
        #
        # THE CAUSE WAS THE GATE BELOW, NOT THE PROMPT. `on_air` is
        # `mInRealtime AND phase > GARAGE` — it is the rule that stops the intro
        # airing over a loading screen, and it is right about SPEAKING. But the
        # round was being matched underneath it, so the overlay did not know
        # which round the session was until he was already on track, and the
        # card appeared as the lights went out — the one moment he cannot read
        # anything.
        #
        # ARMING IS FREE (LAW 3: context is free, RECORDING is confirmed). It
        # decides which round this is and writes nothing, and everything it
        # needs — the circuit, the car class, the year — rF2 publishes while he
        # is sitting in the garage. So it moves above the gate and the prompt
        # arrives with the pit screen, which is where a decision belongs.
        #
        # The session-change check comes with it: a change noticed only once the
        # car is on track is a change noticed late, and `_new_session` is what
        # clears the last race's state.
        now = time.time()
        self._season_pre_arm(s, now)

        # Nothing airs until the session is genuinely live. Without this the
        # intro fired over the loading screen and the whole broadcast was
        # already a minute old by the time the car reached the grid.
        if not getattr(s, "on_air", True):
            return

        # Once the booth has signed off, the broadcast is OVER. Anything after
        # the wrap is a programme that would not exist.
        if self._signed_off:
            return

        # Length is settled once per session, not per tick: it depends on the
        # leader's pace, which only firms up after a few laps, and a booth
        # whose cadence changes underneath it mid-race reads as erratic.
        if self._length is None or self._length_at < 3:
            self._length = self._length_class(s)
            self._length_at = (s.leader_laps or 0)
        self._field_size = s.num_cars or len(s.order)
        # Cast the play-by-play seat. Miles calls modern racing; Brett calls
        # anything before 2000 as an archive fixture. Done here rather than in
        # `_new_session` because the era is not always classified on the tick
        # a session first appears.
        cast_mod.set_era(s.player_era or s.era)
        if not self._season_armed:
            # Once per session. A no-match is a real answer and must not be
            # retried every tick for the length of a race.
            self._season_armed = True
            self._season_arm(s)
        self._phase = self._race_phase(s)
        # Settled once per tick and read by both ranking paths, so a real
        # event and a filler line cannot disagree about whether the lead is
        # being fought over.
        self._front_fight = self._front_fight_live(s)
        self._track_story(s)

        # Detection and the snapshot run FIRST, unconditionally. An earlier
        # version let the bookends return before `_snapshot`, which meant the
        # tick that opened the broadcast never recorded a baseline — so the
        # next tick had nothing to diff against and the first overtake of
        # every race was silently lost.
        # A NON-RACE session is a different programme, not a quiet race.
        #
        # Running race detection over qualifying was actively wrong: in a
        # timed session "position" is timesheet order, so every improved lap
        # re-orders the field and the booth called each one as an overtake —
        # "Leclerc goes through on Russell!" for a car that was in the pits.
        # Practice and qualifying now have their own detection entirely.
        if s.kind in ("quali", "practice", "test", "warmup"):
            events = self._quali_detect(s, now)
        else:
            events = self._detect(s, now)
        self._snapshot(s)
        # Credit the leader with the lap he has just completed. Sits beside
        # the snapshot because it has the same contract: it must run on every
        # tick, whatever the booth decides to say, or the number goes wrong
        # in exactly the ways nobody notices until it is on air.
        self._count_led(s)

        # HIS RESULT, FOLLOWED UNTIL IT IS REALLY HIS RESULT.
        self._season_resettle(s, now)

        # Fight timers are swept AFTER detection and before anything reads
        # them for filler. The order matters: a pass is only visible once the
        # positions have already swapped, so detection needs the state as it
        # was while the two cars were still fighting. Sweeping first wiped
        # exactly the history that makes a pass a breakthrough rather than a
        # routine move.
        self._update_battles(s, now)

        # WHAT HE IS, straight after the first time he was named. The booth
        # has just said "that is Dante Kandasamy, the rookie, off at turn
        # four"; this is the sentence that follows it — who the man is and
        # what may come of him — and it is the reason a viewer joining in
        # qualifying knows whose season this is.
        #
        # It runs BEFORE the bookends because it is owed to a line that has
        # already aired, and it is not forced: a genuine incident outranks an
        # introduction, and the introduction simply waits for the next gap.
        if (self._status_follow and not self._status_told
                and now - self._status_follow >= STATUS_FOLLOW):
            cat, kw = self._status_call(s)
            if cat and self._say(cat, kw, s, now):
                return
            if now - self._status_follow > 90.0:
                self._status_follow = 0.0

        if self._bookends(s, now, events):
            return

        # Chuck's reply to the last call was queued with it, so nothing has
        # to be spoken here — only its CAPTION, which has to appear when the
        # line is heard rather than when it went into the queue.
        if self._pending_caption and now >= self._pending_caption[2]:
            text, who, _ = self._pending_caption
            self._pending_caption = None
            self._show_caption(text, who, now)

        # A conversation in progress is finished before anything routine is
        # started — half an exchange is worse than none. Real news abandons
        # it, because two men discussing tyre wear over a crash is the single
        # most damning thing a booth can do.
        if self._convo:
            if events and max(PRIORITY.get(e[0], 0) for e in events) >= 50:
                self._convo = None
            elif self._continue_convo(s, now):
                return

        if not events:
            # Filler has to breathe. `GLOBAL_COOLDOWN` is the floor for
            # REPORTING a race; it is far too short for talking about one.
            # Without a separate gate the booth fills every seven seconds for
            # an hour, because there is always some colour category off
            # cooldown somewhere — which is how a broadcast becomes a podcast.
            if now - self._last_spoke < FILLER_GAP.get(self._length or "normal",
                                                       15.0):
                return
            # FENCED. The filler is the tick that runs when nothing is
            # happening, which makes it both the most frequent caller in the
            # booth and the one whose failure is hardest to notice — silence
            # during a quiet spell looks exactly like a quiet spell.
            events = self._guard(
                "filler",
                lambda: self._rank_filler(
                    self._quali_filler(s, now)
                    if s.kind in ("quali", "practice", "test", "warmup")
                    else self._filler(s, now), now),
                fallback=[]) or []
        else:
            # Category priority FIRST, then where it happened. Two overtakes
            # are the same category, and the one for second place is the
            # bigger story than the one for eighth.
            events.sort(key=lambda e: -(PRIORITY.get(e[0], 0)
                                        + self._place_bonus(e)
                                        + self._front_bonus(e)))
        if not events:
            return

        for cat, kw, subject in events:
            if cat == "driver_ask":
                if self._history_report(s, now):
                    return
                continue
            if cat == "story_ask":
                # An exchange, not a line — same contract as `interview`:
                # `_story_report` speaks both halves itself and stamps its
                # own cooldown, because a question with no answer is worse
                # than neither.
                if self._story_report(s, now):
                    return
                continue
            if cat == "interview":
                # An exchange is not a line, so it does not go through `_say`
                # — but it obeys the same cooldown, which is why the category
                # timestamp is stamped inside `_start_convo`.
                if (now - self._last_spoke >= GLOBAL_COOLDOWN
                        and not self.tts.speaking
                        and now - self._cat_last.get("interview", 0.0)
                        >= COOLDOWNS["interview"] * COLOUR_SCALE.get(
                            self._length or "normal", 1.0)
                        and self._start_convo(s, now)):
                    return
                continue
            if cat in ("track_fact", "track_character"):
                if self._track_line(s, now,
                                    "character" if cat == "track_character"
                                    else "fact"):
                    return
                continue
            if cat in DRIVER_CATS:
                if self._driver_line(cat, kw, s, now):
                    self._maybe_crosstalk(cat, kw, now, s)
                    return
                continue
            if self._say(cat, kw, s, now):
                # It aired, so it stops queueing. Cleared HERE rather than
                # where it was offered, because a line that was composed and
                # refused is a line the viewer never heard - LAW 11, applied
                # to a retry rather than to a flag.
                key = kw.get("_pass_key")
                if key is not None:
                    self._pending_pass = [
                        p for p in self._pending_pass
                        if p[1].get("_pass_key") != key]
                self._maybe_crosstalk(cat, kw, now, s)
                return

    # -- flow -----------------------------------------------------------------
    def _length_class(self, s):
        """How long is this race, in broadcast terms?

        Measured in minutes rather than laps, because a lap count means
        nothing on its own — fifteen laps of the Nordschleife is a longer
        broadcast than fifty laps of Brands Hatch. Lap races are converted
        using the leader's own pace once there is one, and a nominal 100
        seconds a lap before that.
        """
        if s.kind != "race":
            return "normal"
        mins = None
        if s.max_laps:
            pace = getattr(s, "best_lap_time", None) or 100.0
            mins = (s.max_laps * pace) / 60.0
        elif getattr(s, "end_et", None):
            mins = s.end_et / 60.0
        if mins is None:
            return "normal"
        if mins < 12:
            return "sprint"
        if mins < 35:
            return "normal"
        if mins < 75:
            return "long"
        return "endurance"

    def _progress(self, s):
        """How far through the race we are, 0..1, or None if unknowable."""
        if s.max_laps:
            return min(1.0, (s.leader_laps or 0) / float(s.max_laps))
        rem, dur = getattr(s, "time_left", None), (getattr(s, "end_et", 0.0) or 0.0)
        if rem is None or not dur:
            return None
        return min(1.0, max(0.0, 1.0 - rem / dur))

    def _race_phase(self, s):
        """Where in the arc of the race we are.

        The boundaries SCALE. A sprint gets a one-lap opening and a two-lap
        run-in; an hour-long race gets a couple of settling laps at the top
        and the last eight to build the finish. Both are the same shape, told
        over a different span, which is what a real broadcast does.
        """
        # Practice and qualifying have no arc to be at a point in. They get
        # their own phase name so that conversation topics can be gated on
        # it — "who wins this?" is a nonsense question in free practice.
        if s.kind in ("quali", "practice", "test", "warmup"):
            return "session"
        if s.kind != "race" or not s.started:
            return "mid"
        laps_done = s.leader_laps or 0

        if s.max_laps:
            L = s.max_laps
            togo = L - laps_done
            # Opening is lap one, plus a settling lap on anything long. On a
            # five-lap dash there is no room for a settling lap and the booth
            # has to be in the race immediately.
            open_laps = 1 if L <= 12 else 2
            if laps_done < open_laps:
                return "opening"
            if togo <= 1:
                return "closing"
            # Late is a proportion, floored at two laps so even a sprint gets
            # a run-in, and capped at eight so an endurance race does not
            # spend its last hour in "final laps" mode.
            late_laps = min(8, max(2, int(0.18 * L + 0.999)))
            if togo <= late_laps:
                return "late"
            # SETTLING. Checked after late and closing so a short race never
            # spends its run-in "settling in" — on a five-lap dash the flag is
            # the only thing that matters and `late` owns those laps.
            #
            # AND IT ONLY EXISTS IF THERE IS A MID-RACE LEFT AFTER IT. On a
            # five-lap race the opening and the run-in already touch, and
            # inserting a settling window there would delete the middle of the
            # race entirely — the booth would go from lights-out focus
            # straight to run-in focus and never once open up.
            settle_end = open_laps + SETTLE_LAPS
            if laps_done < settle_end and (L - late_laps) > settle_end:
                return "settling"
            return "mid"

        # Timed. The clock is the only truth here; laps are incidental.
        rem = getattr(s, "time_left", None)
        dur = getattr(s, "end_et", 0.0) or 0.0
        if rem is not None and rem <= 0:
            return "closing"
        if laps_done < 1:
            return "opening"
        if rem is not None and dur:
            # A fixed final minute is "closing" regardless of length: that is
            # the run to the flag whether the race was ten minutes or six
            # hours.
            if rem <= 60.0:
                return "closing"
            if rem / dur < LATE_FRACTION:
                return "late"
        elif laps_done < 2:
            return "opening"
        if laps_done < 1 + SETTLE_LAPS:
            return "settling"
        return "mid"

    def _focus(self, place):
        """Is this position worth commentating in the current phase?

        The limit widens with the size of the field — "top five" in a
        twelve-car grid is the front third of the race, and in a
        thirty-two-car grid it is a sliver — and with the length, because an
        endurance broadcast that only ever looks at the podium places has
        nothing to talk about for two of its three hours.
        """
        if not place:
            return False
        limit = FOCUS_LIMIT.get(self._phase, 99)
        if limit < 99:
            field = self._field_size or 0
            if field > 20:
                limit = max(limit, int(field * 0.28))
            if self._length in ("long", "endurance"):
                limit += 3
        return place <= limit

    def _track_story(self, s):
        """Each driver's arc: best place, worst place, where they are now.

        Cheap per-tick bookkeeping that turns "P7" into "started third, fell
        to twelfth, back up to seventh" — which is the difference between
        reporting a position and telling a race.
        """
        # GREEN, not merely "started". `started` is phase >= GREEN, which also
        # covers full-course yellow, "stopped", "over" and the unknown phase
        # rF2 briefly reports while swapping sessions — and during that swap
        # the order can still be the previous session's, or nothing at all.
        # That transient is where "everybody wrote Senna off when he fell to
        # thirty-first" came from, about a man who qualified on pole and led
        # every lap: for one tick he was scored last, and the arc believed it.
        if s.kind != "race" or not s.green:
            return
        # AND THE ORDER HAS TO MAKE SENSE. Guarding P255 and out-of-range
        # places was not enough: for a tick or two around a standing start
        # rF2 can report a scrambled classification in which a car briefly
        # holds a place it never actually ran. One such tick is permanent,
        # because `worst` only ever grows — which is how a 31-car race
        # produced "that's 30 places clawed back by Alain Prost" about a man
        # who led from the front.
        #
        # A real classification is 1..N with no duplicates. Anything else is
        # skipped whole; the arc simply learns nothing that tick.
        if not self._places_sane(s):
            return
        field = s.num_cars or len(s.order)
        for c in s.order:
            # rF2 reports P255 for a car that has no position yet — in the
            # garage, on the way to the grid, and for a tick or two after the
            # green. Folding that into the arc gave every driver a "worst" of
            # 255, and the booth then announced recoveries of thirty-one
            # places on lap two: it was reading the placeholder, not a race.
            if not c.place or c.place > field or getattr(c, "in_garage", False):
                continue
            st = self._story.get(c.id)
            if st is None:
                self._story[c.id] = {"best": c.place, "worst": c.place,
                                     "now": c.place, "hold": (c.place, 1)}
                continue

            # A PLACE MUST HOLD BEFORE IT COUNTS.
            #
            # `_places_sane` rejects P255 and duplicates, but around a
            # standing start rF2 also publishes orders that are SCRAMBLED yet
            # perfectly valid — a complete 1..N permutation in which cars
            # briefly hold places they never ran. That passes every check
            # above, and because `worst` only ever grows, one such tick is
            # permanent: it is where "that's 30 places clawed back by Alain
            # Prost" came from, about a man who started third.
            #
            # So a place has to be reported for several consecutive ticks
            # before the arc will learn it. A real overtake holds; a
            # re-sort artefact is gone by the next tick.
            st["now"] = c.place
            held, n = st.get("hold") or (c.place, 0)
            n = n + 1 if held == c.place else 1
            st["hold"] = (c.place, n)
            if n < ARC_CONFIRM_TICKS:
                continue
            st["best"] = min(st["best"], c.place)
            st["worst"] = max(st["worst"], c.place)

    @staticmethod
    def _places_sane(s):
        """Is this tick's classification a real running order?

        The same test `rf2_session._track_grid` applies to the grid: places
        1..N with nothing missing and nothing repeated. rF2 publishes
        scrambled orders around session transitions and standing starts, and
        anything that REMEMBERS a place — the arc, the grid — must refuse to
        learn from one of those ticks.
        """
        order = getattr(s, "order", None) or []
        n = len(order)
        if n < 2:
            return False
        places = [c.place for c in order]
        return (all(p and 0 < p <= n for p in places)
                and len(set(places)) == n)

    @staticmethod
    def _has_grid(car):
        """Did this car's starting position get captured cleanly?

        `started_place` is 0 when the grid was never seen in a sane state —
        see `rf2_session._track_grid`. Every line that mentions the grid is
        gated on this, because "up from P0 on the grid" is worse than saying
        nothing about the grid at all.
        """
        return bool(car is not None and getattr(car, "started_place", 0))

    def _enough_race(self, s):
        """Has enough happened for a claim ABOUT THE RACE SO FAR to be true?

        "He's having a great afternoon", "he's climbed six places", "that's a
        recovery drive" are all statements about a body of racing. Two laps in
        there is no body of racing to describe, and saying it anyway is the
        single clearest way the booth sounds like it is not watching: the
        viewer can see it is lap two.

        Both conditions have to hold, because either alone is wrong somewhere:
        laps alone would gate a five-lap sprint out of ever having a story,
        and fraction alone would let a sixty-lap race make sweeping claims on
        lap three.
        """
        if s.kind != "race" or not s.started:
            return False
        if (s.leader_laps or 0) < STORY_MIN_LAPS:
            return False
        p = self._progress(s)
        return p is None or p >= STORY_MIN_FRACTION

    def story_of(self, car):
        return self._story.get(car.id) if car is not None else None

    # -- broadcast bookends ----------------------------------------------------
    def _bookends(self, s, now, events=()):
        """The scripted top and tail of the programme.

        These are the moments where TIMING is the content, so they use
        pre-rendered stings rather than a live render — a "lights out!" that
        arrives four seconds after the lights go out is not a call, it is a
        report. Returns True if a bookend fired and the normal event pass
        should be skipped this tick.
        """
        st = self._sting_bank()

        # OPEN THE SHOW — queue the running order, do not speak yet.
        #
        # This used to be three independent checks (intro, scene-set, lights
        # out) each racing the others and each guessing whether the one before
        # it had happened. Depending on how the session was entered they fired
        # out of order, on top of each other, or — the reported bug — not at
        # all, because green arrived before the intro's turn came round.
        #
        # It is a SEQUENCE, so it is written as one: a queue of stages drained
        # a beat at a time, with green flag as a hard cut that ends it.
        if (not self._said_intro and s.num_cars > 0
                and s.kind in ("race", "quali", "practice", "test")):
            self._said_intro = True
            self._pre = list(PRE_RACE if s.kind == "race" else PRE_QUALI)
            self._pre_failed = set()   # one retry per stage, per sequence
            # WHO HE IS GETS SAID ONCE A SESSION, AT THE FIRST MENTION.
            self._status_named = False
            self._status_told = False
            self._status_follow = 0.0
            self._pre_last = 0.0
            self._pre_at = now

        # LIGHTS OUT — the single most timing-critical line in the product,
        # and it outranks everything still sitting in the pre-race queue.
        if s.kind == "race" and s.green and not self._season_asked:
            # The prompt never survives the start. Unanswered means COUNT IT:
            # the result still has to survive the completion check, and a
            # menu action can undo it, whereas a race that quietly failed to
            # count cannot be recovered at all.
            self._season_asked = True

        if s.kind == "race" and s.green and not self._said_start:
            # Dropping in at COUNTDOWN leaves no room for a running order, so
            # the welcome and the start become the same beat: the show still
            # opens with "you're watching FACTORtv", it just opens ON the
            # green. Never starting the show at all is the one outcome that is
            # not allowed.
            if self._pre and self._pre[0] == "intro" and self._pre_stage(s, now, st):
                return True
            self._pre = []
            self._said_start = True
            self._cat_last["start"] = now
            # Do not cut the intro off mid-sentence. The lights-out sting
            # interrupts whatever is playing, which is right for an incident
            # and wrong three seconds after the show opened.
            grp = "restart" if (s.leader_laps or 0) > 0 else "lightsout"
            fresh_intro = now - self._intro_at < 3.0
            text = st.play(grp, interrupt=not fresh_intro) if st else None
            if text:
                self._show_caption(text, cast_mod.PLAY, now)
                self._last_spoke = now
                return True
            # No sting cached yet (first run, or offline). Fall back to a live
            # line so the race still gets a start call, just a beat late.
            self._say("start", self._kw(s, drv=s.leader), s, now, force=True)
            return True

        # THE RUNNING ORDER — welcome, circuit, grid, format. One stage per
        # beat, and only while there is genuinely nothing else happening.
        #
        # News ends it, the same way the green flag does. Qualifying is where
        # this bites: provisional pole can change hands while the booth is
        # still setting the scene, and a scripted line about the circuit
        # while the timesheet is being rewritten is the wrong programme.
        if self._pre:
            if events and max(PRIORITY.get(e[0], 0) for e in events) >= PRE_YIELD:
                # YIELD THE TICK. DO NOT THROW THE SEQUENCE AWAY.
                #
                # This DISCARDED the queue, and in a qualifying session that
                # meant the entire pre-session sequence — welcome, season,
                # career, circuit — never aired at all. A quali session has a
                # full timesheet from the first tick, those events outrank
                # `PRE_YIELD`, and so the whole thing was binned before a word
                # of it was spoken. It is why the user heard no rookie line: it
                # was never dropped for being wrong, it was dropped for being
                # scripted.
                #
                # News still beats the script — it simply takes the TICK rather
                # than the programme, and the sequence resumes when the sheet
                # is quiet. `PRE_HOLD` stops it dribbling out an hour later:
                # after that the moment has genuinely passed.
                if now - getattr(self, "_pre_at", now) > PRE_HOLD:
                    self._pre = []
            elif self._pre_stage(s, now, st):
                return True

        # THE END OF QUALIFYING — a programme has an ending too.
        #
        # Asked for directly: "there is a chequered flag when the session is
        # over, and the commentators and race engineer never get triggered".
        # A qualifying session simply stopped: the last thing said was
        # whatever colour happened to be in the queue, and then silence
        # through the flag, the final order and the walk to parc fermé.
        #
        # Handled before the race wrap below because `s.finished` is true for
        # ANY session type — the win call would otherwise fire on a qualifying
        # session that has no winner, only a pole.
        if (s.kind in ("quali", "practice") and s.finished
                and not self._said_win):
            self._said_win = True
            # Same chequered sting the race gets. It is the same flag.
            text = st.play("chequered", interrupt=True) if st else None
            if text:
                self._show_caption(text, cast_mod.PLAY, now)
                self._last_spoke = now
            # BANK THE RESULT BEFORE SAYING ANYTHING ABOUT IT. "Quali results
            # must be remembered when a session finishes" — and the engineer's
            # "last time out you put it fourth" reads it back a session later,
            # by which time there is nothing in shared memory to recover it
            # from.
            self._quali_bank(s)
            self._bank_quali_story(s)
            self._post = list(POST_QUALI)
            return True

        if (s.kind in ("quali", "practice") and s.finished
                and self._said_win and not self._signed_off):
            if self._post and self._post_stage(s, now):
                return True
            if not self._post and now - self._last_spoke > 4.0:
                self._signed_off = True
                text = st.play("outro") if st else None
                if text:
                    self._show_caption(text, cast_mod.PLAY, now)
                return True
            return False

        # THE WIN — sting on the flag, then the named call behind it.
        if s.finished and not self._said_win and s.leader is not None:
            self._said_win = True
            text = st.play("victory", interrupt=True) if st else None
            if text:
                self._show_caption(text, cast_mod.PLAY, now)
                self._last_spoke = now
            # THE FLAG. This is where a championship result is written, and it
            # happens before the wrap so the standings the booth is about to
            # read are the ones including this race.
            #
            # IT IS PROVISIONAL UNTIL HIS OWN RACE IS OVER. The flag falls for
            # the WINNER; a driver a lap down, or coasting on an empty tank, has
            # not finished anything yet — and his place on the road at that
            # moment is not his result. The user led on the last lap, ran out of
            # fuel, and his log says it exactly:
            #
            #   [2097.6s] PLAYER  Dante Kandasamy  P4      <- banked
            #   [2109.4s] STATE   lap 7/7  P10  fuel=0.0   <- what happened
            #
            # P4 went into the championship for a race he finished tenth. So
            # `_season_settle` follows him until the game says his race is done
            # (`mFinishStatus`) and re-banks the result as it changes. This is
            # LAW 2's other half: that law asks whether the RACE was completed,
            # and this asks whether HE completed it.
            if not self._season_done:
                self._season_done = True
                me = s.player
                waiting = (me is not None
                           and not getattr(me, "finish_status", 0))
                self._season_record(s, final=not waiting)
                if waiting:
                    self._season_settle = (now, me.place)
            cat, kw = self._win_call(s)
            # The plain `win` pool is the fallback, and it always exists — a
            # race that ends without a victory call is unforgivable, and a
            # story-shaped pool can legitimately be empty for this era.
            if not self._say(cat, kw, s, now, force=True):
                self._say("win", kw, s, now, force=True)
            self._post = list(POST_RACE)
            return True

        # THE WRAP — the counterpart to the running order at the top. A
        # broadcast does not stop at the flag: there is a podium to read, a
        # verdict on how it was won, and a goodbye. Previously the whole of
        # that was a single outro sting nine seconds after the win, which
        # ended the show before it had said anything about the race.
        if s.finished and self._said_win and not self._signed_off:
            if self._post and self._post_stage(s, now):
                return True
            if not self._post and now - self._last_spoke > 4.0:
                self._signed_off = True
                text = st.play("outro") if st else None
                if text:
                    self._show_caption(text, cast_mod.PLAY, now)
                return True
        return False

    def _post_stage(self, s, now):
        """One beat of the wrap. Same contract as `_pre_stage`."""
        if self.tts.speaking or now - self._last_spoke < POST_RACE_GAP:
            return False
        stage = self._post.pop(0)
        order = s.order
        top = [c for c in order[:3]]

        # -- THE END OF QUALIFYING ------------------------------------------
        # THE ORDER COMES FROM THE TIMESHEET, NOT FROM `s.order`. In a timed
        # session rF2's position field is the running order on the road as
        # often as it is the classification, and reading `s.order[0]` as the
        # pole man is how a booth announces pole for whoever happened to be
        # in front at the flag. `_sheet` sorts by best lap, which is what
        # decides a qualifying session.
        if stage in ("pole", "frontrow", "qverdict", "yours", "qsignoff"):
            sheet = self._sheet(s)
            if not sheet:
                return False            # nobody set a time: nothing to say
            me = s.player
            poleman = sheet[0]
            second = sheet[1] if len(sheet) > 1 else None
            third = sheet[2] if len(sheet) > 2 else None

            if stage == "pole":
                kw = self._kw(s, drv=poleman, t=spoken_lap(poleman.best_lap))
                if second is not None:
                    kw["gap"] = self._margin(second.best_lap
                                             - poleman.best_lap)
                    kw["b"] = second.display_name
                    return self._say("quali_over_pole", kw, s, now, force=True)
                # LAW 5: a margin slot with nobody to be ahead of stays out of
                # the template entirely rather than airing empty.
                return self._say("quali_over_solo", kw, s, now, force=True)

            if stage == "frontrow":
                if second is None:
                    return False
                kw = self._kw(s, drv=poleman, b=second,
                              c=(third.display_name if third is not None
                                 else ""))
                cat = ("quali_over_top3" if third is not None
                       else "quali_over_top2")
                return self._say(cat, kw, s, now, force=True)

            if stage == "qverdict":
                # Chuck on somebody OTHER than the pole man. Pole has already
                # had two beats; what a viewer cannot get from the sheet is
                # what third place has to do about it tomorrow.
                subject = third if third is not None else second
                if subject is None:
                    return False
                i = sheet.index(subject) + 1
                return self._say("quali_over_verdict",
                                 self._kw(s, drv=subject,
                                          pos=spoken_place(i)),
                                 s, now, force=True)

            if stage == "yours":
                # The player, wherever he finished — and skipped rather than
                # faked when he set no time at all.
                if me is None or not me.best_lap:
                    return False
                i = next((n + 1 for n, c in enumerate(sheet)
                          if c.id == me.id), 0)
                if not i:
                    return False
                if i == 1:
                    return False        # the pole beat already said it
                kw = self._kw(s, drv=me, pos=spoken_place(i),
                              gap=self._margin(me.best_lap
                                               - poleman.best_lap))
                return self._say("quali_over_player", kw, s, now, force=True)

            if stage == "qsignoff":
                return self._say("quali_over_signoff", self._kw(s), s, now,
                                 force=True)

        if stage == "podium":
            # `podium_final` is the whole top three read out, which is a
            # different line from `podium` — that one is for a single driver
            # securing a place mid-race and reads as a non-sequitur here.
            if len(top) < 3:
                return False
            return self._say("podium_final",
                             self._kw(s, drv=top[0], a=top[1], b=top[2],
                                      pos=spoken_place(1)), s, now, force=True)
        if stage == "tally":
            # WHERE THIS WIN SITS IN HIS CAREER. "That is the one hundred and
            # sixth Grand Prix win of Lewis Hamilton's career" — the ninety-
            # five he arrived with, plus the eleven you have taken as him.
            #
            # Gated on the win having been BANKED: `season_wins` counts
            # recorded rounds, so outside career mode, or after a race that
            # failed THE LAW, this is silent rather than quoting a total that
            # does not include the race just finished.
            cat, kw = self._tally_call(s)
            return bool(cat) and self._say(cat, kw, s, now, force=True)

        if stage == "topraces":
            # HOW THE PODIUM GOT THERE. The result is on screen; what is not
            # is which of them had to work for it.
            return self._wrap_story(s, now, top)

        if stage == "impressed":
            # Chuck's own pick, and it must not be the winner — the booth has
            # a dozen ways to praise him already, and the thing a viewer
            # cannot get anywhere else is which OTHER drive was worth it.
            return self._wrap_impressed(s, now)

        if stage == "championship":
            # The scoreboard. A season needs one read out, and this is the
            # only moment in the broadcast where the standings are news.
            cat, kw = self._championship_call(s)
            return bool(cat) and self._say(cat, kw, s, now, force=True)

        if stage == "verdict":
            # Chuck's summing up. He gets the last word on HOW it was won,
            # which is the difference between a result and a race. Again a
            # dedicated pool: `verdict` judges a single overtake.
            return self._say("race_verdict", self._kw(s, drv=s.leader), s, now,
                             persona=cast_mod.ANALYST, force=True)
        if stage == "signoff":
            return self._say("signoff", self._kw(s, drv=s.leader), s, now,
                             force=True)
        return False

    # -- the season -------------------------------------------------------------
    #
    # Two things happen here and they are deliberately separate, because they
    # carry very different risk:
    #
    #   CONTEXT is automatic. If the circuit and class match a round of the
    #   active career, the booth knows it is round six and says so. Being
    #   wrong costs one sentence.
    #
    #   RECORDING is confirmed, and only ever happens at the chequered flag
    #   with the player classified and the distance actually covered. Writing
    #   a result into a championship cannot be undone by the next race, and a
    #   standings table that silently banked an abandoned attempt is wrong in
    #   a way the user cannot see.

    def _season_arm(self, s):
        """Work out which round of the active career this session is.

        Done once per session rather than per tick: the answer cannot change
        while the same session is loaded, and it is the input to a prompt the
        user is about to be asked.
        """
        self._season_round = None
        car = getattr(s, "player", None)
        career = getattr(self, "season", None)
        circuit = getattr(s, "circuit", None)
        # CONTEXT is armed for qualifying and practice too — knowing this is
        # round three of five matters as much on a Saturday as on a Sunday,
        # and it is how the user hears that career mode is running before the
        # race itself. RECORDING remains race-only: `_season_record` is
        # called from the chequered-flag bookend, which no other session has.
        if (career is None or car is None or circuit is None
                or not circuit.known
                or s.kind not in ("race", "quali", "practice")):
            return
        # THE SEASON YEAR GOES WITH IT, for a rung that locks one. The era is
        # built from the WHOLE class list, which is what dates a team-named
        # Formula One grid — one constructor on its own cannot be dated.
        _e = getattr(s, "player_era", None) or getattr(s, "era", None)
        self._season_round = career.match(circuit.slug,
                                          getattr(car, "cls", None),
                                          year=getattr(_e, "year", None),
                                          vehicle=getattr(car, "vehicle", ""))
        # The default is to count it. The user can decline from the prompt or
        # drop the result afterwards from the menu, and both of those are
        # easier to reach for than a race that quietly failed to count.
        self._season_count = bool(self._season_round) and bool(
            getattr(self, "season_record", True))

    def season_answer(self, yes):
        """The user's answer to the pre-race prompt. True if there was one to
        answer — the hotkeys are live all the time and must do nothing at all
        when no prompt is showing."""
        if not self._season_round or self._season_asked:
            return False
        self._season_asked = True
        self._season_count = bool(yes)
        return True

    def season_prompt(self, s):
        """What the prompt card should say, or None when it should not show.

        Only before the green flag: asking mid-race is asking about a
        decision already made, and asking after it is too late to matter.
        """
        rnd = self._season_round
        career = getattr(self, "season", None)
        if (career is None or not rnd or self._season_asked
                or s is None or s.kind != "race" or s.started):
            return None
        total = career.total_rounds
        return {
            "name": career.name,
            "round": ("Round %d of %d" % (rnd["n"], total) if total
                      else "Round %d" % rnd["n"]),
            "event": rnd.get("event", ""),
            # Re-running a round is allowed, and saying so out loud is the
            # difference between a helpful prompt and a trap.
            "rerun": bool(rnd.get("done")),
        }

    def _season_call(self, s):
        """The pre-race season line: which round, and where he stands."""
        career = getattr(self, "season", None)
        rnd = getattr(self, "_season_round", None)
        if career is None or not rnd:
            return None, {}
        st = career.title_state()
        total = career.total_rounds
        # `event` falls back to the circuit: a season with no fixed calendar
        # has no event names, and an empty slot airs as "The , and the start
        # of a brand new season."
        circuit = getattr(s, "circuit", None)
        kw = self._kw(s, drv=s.player, n=rnd["n"], total=total,
                      event=(rnd.get("event")
                             or (circuit.name if circuit is not None else "")))
        # Two different "rounds left" exist and confusing them produces a
        # sentence that is simply false. `title_state.rounds_left` counts
        # UNRACED rounds, which is the right number for points-available
        # maths. What a commentator means by "three to go" is rounds after
        # this one ON THE CALENDAR, which is what goes in the line.
        kw["left"] = max(0, total - rnd["n"]) if total else 0
        if st:
            kw.update({"leader": st["leader"], "pts": st["my_points"] or 0,
                       "gap": st["my_gap"] if st["my_gap"] is not None else "",
                       "pos": spoken_place(st["my_place"])})
        # WHERE IN THE SEASON WE ARE. A season has a shape exactly as a race
        # does — the opener where nobody has a point, the settling rounds, the
        # halfway mark, the run-in, the finale — and without saying so every
        # round sounds identical except for its number.
        phase = career.phase(rnd["n"])
        if phase == "opener" and not career.rounds:
            # THE FIRST SESSION OF A CAREER. Says the format out loud —
            # which championship, how many rounds, that there is a title at
            # the end — so it is audible that career mode is running at all,
            # rather than the user having to infer it from being called by a
            # different name.
            if not self._said_launch:
                self._said_launch = True
                return ("season_launch" if total
                        else "season_launch_open"), kw
            return "season_opener", kw
        # WHAT HE HAS TO DO TODAY, AND IT OUTRANKS EVERY OTHER SEASON LINE.
        #
        # Asked for exactly: "big twist in the story of the championship, the
        # championship leader has qualified P12, this means they will need to
        # at least finish P5 or higher in tomorrow's race to secure the season
        # win". On the last afternoon of a season that is not colour, it is
        # the entire reason the viewer is watching.
        #
        # `title_scenarios` returns None unless the arithmetic is exact, so
        # this beat simply does not exist for a season that cannot count its
        # own rounds. LAW 4 is enforced at the source rather than here.
        sc = career.title_scenarios(field=len(s.order) or None)
        if sc and not sc.get("decided") and sc.get("secure"):
            kw["need"] = spoken_place(sc["secure"])
            kw["rival"] = sc.get("rival") or ""
            if sc.get("secure_any"):
                # "He needs to finish twelfth" is a strange sentence when
                # twelfth pays nothing. What is true is that he only has to
                # take the flag.
                return "title_needs_finish", kw
            if sc.get("rival"):
                return "title_needs", kw
        if phase == "finale":
            return "season_finale", kw
        if phase == "midway":
            return "season_midway", kw
        # A title claim needs a real gap AND enough season behind it to mean
        # anything. Two rounds in, the championship table is noise.
        if st and st["my_place"] and st["rounds_done"] >= TITLE_TALK_AFTER:
            if phase == "late":
                return "season_late", kw
            if st["my_place"] == 1:
                return "title_lead", kw
            if st["my_gap"] is not None:
                return "title_chase", kw
        if phase == "late":
            return "season_late", kw
        if not total:
            return "season_round_open", kw
        # A season with a length but no calendar has no event names, so it
        # cannot use the lines built round "the {event}".
        return ("season_round" if rnd.get("event")
                else "season_round_anytrack"), kw

    def _story_kw(self, s, arc):
        """Slots for one driver's arc. Shared by the mid-race report and the
        wrap so the two can never describe the same afternoon differently."""
        return self._kw(s, drv=arc.car,
                        pos=spoken_place(arc.place),
                        grid=spoken_place(arc.grid),
                        best=spoken_place(arc.best),
                        worst=spoken_place(arc.worst),
                        n=self._places_text(max(abs(arc.gained),
                                                arc.recovered, arc.slid)),
                        offs=self._times_text(arc.offs))

    def _wrap_story(self, s, now, top):
        """One of the podium finishers, described by how he got there.

        Picks the man with the most to say rather than the winner: the winner
        is covered by the win call, the podium read and the verdict, and
        saying a fourth thing about him is how a wrap becomes a lap of
        honour. A podium of three drivers who all started where they finished
        produces nothing, and the beat is dropped.
        """
        for arc in story_mod.field(self, s, top=3):
            cat = arc.headline()
            if cat in (None, "story_holding", "story_out"):
                continue
            return self._say(cat, self._story_kw(s, arc), s, now,
                             persona=cast_mod.ANALYST, force=True)
        return False

    def _wrap_impressed(self, s, now):
        """Chuck's drive of the day. Never the winner.

        An exchange rather than a line, because "who impressed you?" is a
        question and Chuck answering an unasked one sounds like a man talking
        to himself. Both halves go in the same breath — see `_story_report`.
        """
        winner = s.leader
        best = None
        for arc in story_mod.field(self, s, top=STORY_FOCUS):
            if winner is not None and arc.car is winner:
                continue
            if arc.headline() in (None, "story_holding", "story_out",
                                  "story_slide", "story_dropping",
                                  "story_undone", "story_losing"):
                continue        # "impressed" means impressed
            best = arc
            break
        if best is None:
            return False
        era = s.player_era or s.era
        kw = self._story_kw(s, best)
        q, _i, _o = lines_mod.pick("wrap_ask_impressed", era, kw)
        a, ai, _o2 = lines_mod.pick("wrap_impressed", era, kw)
        if not q or not a:
            return False
        self.tts.speak(q, cast_mod.PLAY, intensity=0)
        self.tts.speak(a, cast_mod.ANALYST, intensity=ai)
        self._last_spoke = now
        self._cat_last["wrap_impressed"] = now
        self._show_caption(q, cast_mod.PLAY, now)
        self._pending_caption = (a, cast_mod.ANALYST, now + 0.1)
        return True

    def _tally_call(self, s):
        """Where the win just taken sits in the winner's career.

        Returns (category, slots) or (None, {}). Silent unless three things
        are all true: we hold a real historical record for this driver, the
        result has been banked into a career, and the win is in it. A running
        total that does not include the race the viewer has just watched is
        worse than no running total.
        """
        career = self._active_career()
        rnd = getattr(self, "_season_round", None)
        w = s.leader
        if career is None or not rnd or w is None:
            return None, {}
        era = s.player_era or s.era
        stg = self._driver_record(w, era, career)
        if stg is not None:
            # Re-read against the round just banked, so the tally includes the
            # race the viewer has this moment watched.
            stg = drivers_mod.standing(stg.name, era, career, upto=rnd["n"])
        if stg is None or stg.season_wins <= 0:
            return None, {}
        kw = self._kw(s, drv=w, pos=spoken_place(1))
        kw.update(stg.slots())
        kw["drv"] = stg.name
        # A first-ever win and a hundred-and-sixth are not the same sentence,
        # and only one of them is worth an intensity of three.
        return ("driver_first_win" if stg.first_win else "driver_win_tally"), kw

    def _championship_call(self, s):
        """The post-race standings, computed AFTER the result was recorded."""
        career = getattr(self, "season", None)
        if career is None or not getattr(self, "_season_round", None):
            return None, {}
        st = career.title_state()
        if not st or not st["table"]:
            return None, {}
        total = career.total_rounds
        rnd = self._season_round
        kw = self._kw(s, drv=s.player, leader=st["leader"],
                      pts=st["leader_points"], n=st["rounds_done"],
                      total=total,
                      # Rounds still to come after the one just finished —
                      # see the note in `_season_call`.
                      left=max(0, total - rnd["n"]) if total else 0,
                      pos=spoken_place(st["my_place"]),
                      gap=st["my_gap"] if st["my_gap"] is not None else "")
        # The title being mathematically settled is the biggest thing that
        # can happen to a season, and it is stated only when the maths is
        # exact — `decided` is False whenever the remaining points are
        # unknown, which is every open season.
        if st["decided"]:
            # WHOSE title is it, in the history of the sport?
            #
            # This is the payoff for the driver knowledge base. Racing as
            # Hamilton and taking the championship is not "the title is
            # settled", it is HIS EIGHTH — and if Mansell takes it in 1988 it
            # is his first, and if an AI Senna takes it, it is his first too.
            # The booth is the only thing in the room that can say which.
            era = s.player_era or s.era
            who = st["leader"]
            if drivers_mod.just_won_title(who, era, career, rnd["n"]):
                stg = drivers_mod.standing(who, era, career, upto=rnd["n"])
                kw.update(stg.slots())
                kw["drv"] = stg.name
                return ("driver_title_first" if stg.new_champion
                        else "driver_title_more"), kw
            return "title_decided", kw
        # WHAT THE RESULT MEANS FOR THE SEASON.
        #
        # "The championship lead belongs to Lewis Hamilton" was the entire
        # implication the wrap ever drew. The gap and the rounds remaining are
        # both exact when `title_state` gives them, so they can be said out
        # loud — and when it cannot give them (an open season with no declared
        # length) `rounds_left` is None and none of this is offered, which is
        # LAW 4 doing its job rather than a missing feature.
        gap = (st["leader_points"] - st["second_points"]) if st["second"] else 0
        left = st.get("rounds_left")
        if left:
            kw = dict(kw)
            kw["pts"] = "%d" % gap
            kw["left"] = self._rounds_text(left)
            if gap and gap >= self._big_lead(career, left):
                return "champ_extends", kw
            if gap:
                return "champ_closes", kw
        if st["my_place"] == 1:
            return "championship_lead", kw
        return "championship_after", kw

    @staticmethod
    def _rounds_text(n):
        return "one round" if n == 1 else "%d rounds" % n

    @staticmethod
    def _big_lead(career, left):
        """The points gap above which a lead is worth calling a cushion.

        Measured against what is actually still available — a 25-point lead
        is enormous with one round left and nothing at all with eight. Uses
        the career's own points table rather than a constant, so a mod with
        its own scoring does not make the booth talk nonsense.
        """
        win = career.points_for(1) or 25
        return win * max(1, left) * 0.5

    # How long the result is allowed to keep changing after the flag. A car
    # coasting to the line takes tens of seconds; nothing legitimate takes
    # three minutes, and after that the last thing seen is the honest answer.
    RESULT_SETTLE_MAX = 180.0

    def _season_resettle(self, s, now):
        """Re-bank the result while the player's own race is still going.

        THE FLAG IS THE WINNER'S, NOT HIS. `record` replaces a round with the
        same number, so this is not a second result — it is the same result,
        corrected, and it stops the moment the game says his race is over.

        IT WRITES ON CHANGE, NOT ON EVERY TICK. His place moves a handful of
        times while he coasts; a save at 20Hz for three minutes would be four
        thousand writes of a career file for one race.
        """
        pend = getattr(self, "_season_settle", None)
        if not pend or not s.valid:
            return
        started, last = pend
        me = s.player
        if me is None:
            self._season_settle = None
            return
        done = bool(getattr(me, "finish_status", 0))
        if me.place and me.place != last:
            # NO POST YET. A result sheet quotes his finishing position and is
            # frozen when sent, so a letter generated off a provisional place
            # would sit in the archive congratulating him on a fourth place he
            # did not get. The store may be corrected; a letter may not.
            self._season_record(s, final=False)
            last = me.place
        if done or (now - started) > self.RESULT_SETTLE_MAX:
            # ONE LAST WRITE ON THE WAY OUT. The place that mattered may have
            # changed on the very tick the game classified him, and the whole
            # point of this is that the LAST answer is the real one.
            self._season_record(s)
            self._season_settle = None
            self._log("RESULT", "settled P%s status=%s laps=%s%s"
                      % (me.place, getattr(me, "finish_status", 0),
                         me.laps,
                         "" if done else " (timed out)"))
        else:
            self._season_settle = (started, last)

    def _season_record(self, s, final=True):
        """Bank the result. `final` decides whether the POST goes out with it.

        Builds the classification from the live session rather than waiting
        for rF2 to write its XML on exit, because the XML does not exist yet
        at the moment the booth needs to talk about the standings — and
        because "he completed the race" is a fact this code can see directly.
        """
        career = getattr(self, "season", None)
        rnd = getattr(self, "_season_round", None)
        me = s.player
        if (career is None or not rnd or me is None
                or not getattr(self, "_season_count", False)):
            return None
        cls = getattr(me, "cls", "")
        # SOME MODS NAME A CLASS PER TEAM — twenty cars across ten "classes".
        # Filtering the field by class then leaves a championship computed
        # from two drivers. A class that covers only a sliver of the grid is
        # a team label, so the whole grid is the field and nothing is locked.
        # A team-named field IS the whole grid: the championship covers every
        # constructor class in `cls_any`, so the field is anyone in one of
        # them rather than anyone sharing the player's team.
        members = career.data.get("cls_any") or []
        if members:
            same = [c for c in s.order if getattr(c, "cls", "") in members]
        else:
            same = [c for c in s.order if getattr(c, "cls", "") == cls]
        real_class = len(same) >= max(3, len(s.order) * CLASS_SHARE)
        field = same if real_class else list(s.order)
        race_laps = max((c.laps or 0 for c in field), default=0)
        fastest = min((c for c in field if c.best_lap),
                      key=lambda c: c.best_lap, default=None)
        result = {
            "n": rnd["n"], "slug": rnd["slug"],
            "event": rnd.get("event") or getattr(s.circuit, "name", ""),
            "when": time.time(), "cls": cls if real_class else "",
            "me": me.display_name,
            "pos": me.place, "grid": getattr(me, "started_place", 0) or 0,
            "field": len(field), "laps": me.laps or 0,
            "race_laps": race_laps,
            "dnf": me.finish_status in (2, 3),
            "classified": [(c.display_name, c.place) for c in field],
            "fastest": fastest.display_name if fastest is not None else "",
        }
        # THE MAN IN THE OTHER SIDE OF THE GARAGE, recorded with the result.
        #
        # The season head-to-head — "three-two in qualifying" — cannot be
        # computed later from `classified`, because that is a list of NAMES
        # and nothing in the store says which of them shared his car. The
        # only place that knows is here, live, where `CarClass` still means
        # the constructor.
        #
        # Stored per round rather than per season on purpose: a driver can
        # change team mid-career, and a season that quietly re-labelled his
        # old results would make the head-to-head wrong for both men.
        mate = self._team_mate(s)
        if mate is not None:
            result["team"] = cls
            result["mate"] = mate.display_name
            result["mate_pos"] = mate.place
        # `Career.record` applies THE LAW again and can still refuse this.
        # That duplication is deliberate: the caller is the thing most likely
        # to be wrong, so the store does not trust it.
        rnd = career.record(result)
        if rnd is not None and final:
            # THE POST ARRIVES BECAUSE THE RESULT DID. Generating mail here
            # rather than only when the panel is opened is what makes the
            # badge appear during the slowing-down lap — and `refresh` is
            # idempotent, so the menu calling it again a minute later posts
            # nothing. A refusal by THE LAW sends no mail at all, which is
            # correct: there is no result to write a letter about.
            try:
                import inbox as inbox_mod
                import news as news_mod
                inbox_mod.refresh(career)
                # THE NEWS FEED IS GIVEN THE LIVE ERA, which the session knows
                # exactly and a career file can only infer from a class string.
                news_mod.refresh(career, era=getattr(s, "era", None))
                # THE STORY NEVER TOUCHES THE BOOTH. It is refreshed here only
                # because this is where a result is banked; nothing it returns
                # is ever spoken, and no line pool reads it.
                import personal as personal_mod
                personal_mod.refresh(career)
            except Exception:
                pass
        return rnd

    # -- the past ---------------------------------------------------------------
    def _ladder_call(self, s, pre=False):
        """What the booth may say about the CAREER this race belongs to.

        Returns (category, kw), or (None, {}) when there is no ladder career —
        which is every one-off race and every plain season, and must cost the
        broadcast nothing.

        EVERY FACT COMES FROM THE STORE AND WAS WATCHED. Seasons this overlay
        recorded, races it timed, championships it scored. That is what makes
        this the one kind of driver knowledge a fictional GT4 grid can carry:
        we are not claiming anything about the AI, we are talking about the man
        the viewer is watching, whose record we have.

        Ordered by how much the claim is worth RIGHT NOW rather than by how
        impressive it is. A promotion decided this afternoon outranks a career
        total, because the viewer can watch the first one happen.
        """
        career = getattr(self, "season", None)
        if career is None or not getattr(career, "on_ladder", False):
            return None, {}
        # OUTSIDE A CAREER ROUND, SAY NOTHING. A career stays loaded in the
        # settings for as long as it exists, so a one-off race run for fun
        # still has one attached — the same gate `_active_career` applies to
        # the driver records, and for the same reason.
        if not getattr(self, "_season_round", None):
            return None, {}
        me = s.player
        if me is None:
            return None, {}
        r = career.resume() or {}
        ev = career.evaluate() or {}
        nat = career.nationality
        kw = self._kw(s, drv=me, cat="_career", series=ev.get("tier_name", ""),
                      nat=nations_mod.demonym(nat),
                      adj=nations_mod.adjective(nat),
                      below=r.get("reigning", ""),
                      need=("P%d" % ev["needs"]) if ev.get("needs") else "",
                      seasons=drivers_mod.spoken_number(r.get("seasons") or 0),
                      races=r.get("races") or 0,
                      wins=r.get("wins") or 0,
                      titles=drivers_mod.spoken_number(r.get("title_count") or 0),
                      left=max(0, (career.total_rounds or 0)
                               - len(career.rounds)))
        rnd = self._season_round
        last_round = (career.total_rounds
                      and rnd.get("n") == career.total_rounds)

        # THE JUNIOR PROGRAMME, and it outranks the ordinary career lines for
        # the same reason a promotion does: it is what THIS afternoon is
        # actually for, and the viewer can watch it being decided.
        #
        # Every slot comes from the programme he signed, so nothing here is a
        # claim about a real team's plans - it is a fact about his career,
        # which is the line the whole ladder commentary already holds.
        try:
            import programme as prog_mod
            pstate = prog_mod.state(career)
            _pk, pblock = prog_mod.signed(career)
        except Exception:
            pstate, pblock = None, None
        if pblock:
            # THE MAN IN THE OTHER CAR IS WHOEVER IS ACTUALLY IN IT.
            #
            # The programme decides the TEAM, two years earlier, when he signs
            # in Formula 2 — and the class lock binds the season to that
            # constructor once he races it. What it cannot decide is which of
            # the team's two entries he loads in the game, because rF2 makes
            # that choice and each car is a specific driver's (`#11 - Sergio
            # Perez`, class `Red Bull`).
            #
            # So the stored lead is the EXPECTATION and the live team-mate is
            # the FACT. Take the fact when there is one: a line that names
            # Hamilton at a driver who is actually sharing a garage with
            # Bottas is wrong in a way the timing screen shows.
            mate = self._guard("team_mate", self._team_mate, s, fallback=None)
            kw.update({"prog": pblock.get("name", ""),
                       "f1team": pblock.get("f1_team", ""),
                       "lead": (mate.display_name if mate is not None
                                else pblock.get("f1_lead", "")),
                       "f2team": pblock.get("f2_team", "")})
            if pstate in (prog_mod.SIGNED, prog_mod.RETRY):
                # The last round with the title AND the seat on it is the
                # biggest thing this booth can be told about a season.
                if last_round:
                    return "prog_last_chance", kw
                return "prog_stake", kw
            if pstate == prog_mod.SEAT:
                # HIS FIRST RACE IN THE SEAT. Once - after that he is a
                # Formula One driver and the arrival is no longer news.
                if not career.rounds:
                    return "prog_debut", kw
                return "prog_measured", kw
        # A HOME RACE, and it outranks everything except the season being
        # decided today. It is the one fact here a viewer feels rather than
        # notes — and it is derived, not asked for: the circuit knows its
        # country and the career knows his.
        circuit = getattr(s, "circuit", None)
        # `Track.country` IS A METHOD. Reading it as an attribute handed
        # `is_home` a function object, which raised — and because `_filler`
        # asks for a career line on every quiet tick, that one wrong `getattr`
        # silenced the ENTIRE booth for the back half of a race: 2,618
        # tracebacks in one session, every one of them swallowed.
        cty = getattr(circuit, "country", "") if circuit is not None else ""
        if callable(cty):
            try:
                cty = cty()
            except Exception:
                cty = ""
        home = bool(nat and cty and nations_mod.is_home(nat, cty))
        # 1. THE SEASON IS BEING DECIDED TODAY. Nothing else here competes.
        if last_round and ev.get("needs") and not ev.get("top"):
            return "ladder_last_chance", kw
        # A HOME WIN, after the flag — the one line here that is worth more
        # than anything else in this pool, and it is the only one that can
        # only be said once the race is over. Ask any driver on a grid which
        # victory he would take and this is the one he names.
        if (home and getattr(s, "finished", False)
                and getattr(me, "place", 0) == 1):
            return "ladder_home_win", kw
        # THE MOMENT HE BECOMES A CHAMPION. The single most valuable line in
        # this product, and the one thing here that can only be said in the
        # four seconds after a chequered flag — "from rookie to champion".
        #
        # It is gated on `status_changed()`, which WRITES: the status is
        # remembered so this can never fire twice for one championship, and so
        # the news feed and the booth cannot disagree about when it happened.
        if getattr(s, "finished", False) and career.status()[0] in (
                "champion", "multi", "legend"):
            risen = career.status_changed()
            if risen:
                return ("status_arrival" if risen[0] == "champion"
                        else "status_arrival_more"), kw
        # 2. HOME. Said once, in the pre-race build-up, because it is a fact
        #    about the AFTERNOON rather than about the man — and because a
        #    grandstand full of his own people is the sort of thing a
        #    commentator mentions before the start, not on lap thirty.
        if home and pre:
            return "ladder_home", kw
        # 2. HIS FIRST RACE AT THIS RUNG — true exactly once per division, and
        #    only sayable because the store knows how many rounds are in it.
        if not career.rounds:
            if r.get("reigning_now") and r.get("reigning"):
                return "ladder_reigning", kw
            if r.get("seasons"):
                return "ladder_first_race", kw
        # THE RIVALRY, and it outranks the record lines because it is about
        # THIS afternoon rather than about a career. `Career.rivals()` is the
        # same detector the news feed uses, so the paper and the booth can
        # never disagree about who is fighting whom.
        riv = career.rivals()
        if riv:
            kw = dict(kw, b=riv["b"], pts=riv["points"])
            # THE NEEDLE IS ONLY MENTIONED IF IT WAS PRINTED. The booth
            # referring to "what was said in the press conference" when
            # nothing was ever published is the booth inventing an event —
            # so it reads the same archive the player can open and read.
            try:
                import inbox as inbox_mod
                said = any(m.get("kind") == "news_needle"
                           for m in inbox_mod.messages(career, feed="news"))
            except Exception:
                said = False
            if said and riv["player"]:
                return "ladder_needle", kw
            if riv["player"]:
                return "ladder_rivalry", kw

        # 3. THE RUN-IN, when the promotion is close enough to be real.
        if ev.get("needs") and kw["left"] and kw["left"] <= 2:
            return "ladder_title_run", kw
        # A DRIVER NOBODY HAS EVER SEEN IS INTRODUCED AS WHAT HE IS.
        #
        # The user's first qualifying session of a brand new USF2000 career
        # opened with the promotion line — "there is a seat above this
        # championship and P5 is what it costs" — and never once said the word
        # rookie. That is the wrong sentence for the first minute of a career:
        # what a viewer needs on a debut is who this man is, and the seat above
        # is a thing to talk about once he has started racing for it.
        if (not (r.get("seasons") or 0)) and not career.rounds:
            return "status_rookie", kw
        if pre and ev.get("needs"):
            return "ladder_promotion", kw
        # 4. WHAT HE HAS DONE. Only once there is something to say — a driver
        #    in his first season has no record and the booth stays quiet about
        #    it rather than padding.
        if r.get("arcs_won"):
            return "ladder_arc", kw
        if (r.get("wins") or 0) >= 3 and (r.get("title_count") or 0):
            return "ladder_record", kw
        # WHAT THE SPORT CALLS HIM NOW. Above the nationality because it is
        # about what he has DONE rather than where he is from, and below the
        # record lines because "eleven wins" is a harder fact than "champion".
        #
        # THE REWARD FOR CLIMBING. A player who spent ten seasons getting out
        # of karting should hear the booth's name for him change as he does —
        # rookie, riser, contender, champion, legend — and every one of those
        # thresholds is something this overlay watched him cross.
        cat = {"rookie": "status_rookie", "riser": "status_riser",
               "contender": "status_contender", "champion": "status_champion",
               "multi": "status_multi",
               "legend": "status_legend"}.get(career.status()[0])
        # `status_riser` names the division he climbed out of, so it needs one
        # — a driver promoted from a path he joined at the top has no {below}.
        if cat == "status_riser" and not kw.get("below"):
            cat = "status_contender"
        if cat:
            return cat, kw

        # WHERE HE IS FROM, when there is nothing bigger to say. Bottom of the
        # order deliberately: it is atmosphere, and it must never displace a
        # fact about what he has actually done.
        if kw.get("nat"):
            return "ladder_nation", kw
        if (r.get("seasons") or 0) >= 2:
            return "ladder_climb", kw
        return None, {}

    def _register_call(self, s):
        """What KIND of racing this is — the tone, not the knowledge.

        Karting commentary is not Formula One commentary. That difference is
        cheap to have and expensive to fake: a register line says something
        true about the LEVEL, which needs no history at all, and it is why a
        club meeting can sound like a club meeting without anybody inventing a
        club driver's biography.
        """
        career = getattr(self, "season", None)
        if career is None or not getattr(career, "on_ladder", False):
            return None, {}
        if not getattr(self, "_season_round", None):
            return None, {}
        reg = career.register
        cat = {"grassroots": "reg_grassroots", "junior": "reg_junior",
               "professional": "reg_professional"}.get(reg)
        # The archive register has its own voice already — `booth_archive.json`
        # and Brett in the chair — and a second one talking over it would be
        # two different programmes at once.
        if not cat:
            return None, {}
        return cat, self._kw(s, drv=s.player)

    def _career_call(self, s):
        """What the booth may truthfully say about this driver at this
        circuit. Returns (category, kw), or (None, {}) when it knows nothing.

        Everything here is a claim about the real world that the user can
        check against his own memory, so the ordering is by how STRONG the
        claim is: a win here outranks a podium, which outranks "you were
        seventh last time". Anything not backed by a recorded result simply
        produces no line — the same discipline the track knowledge follows.
        """
        hist = getattr(self, "career", None)
        me = s.player
        circuit = getattr(s, "circuit", None)
        if hist is None or me is None or circuit is None or not circuit.known:
            return None, {}
        kw = self._kw(s, drv=me, trk=circuit.name)
        # THIS SEASON FIRST. "We were here in round two as well" is a stronger
        # and more immediate thing to say than a record from a career ago, and
        # it is the only version of track memory an open season can have —
        # where the same circuit may well come round again.
        career = getattr(self, "season", None)
        if career is not None:
            been = career.visits(circuit.slug)
            if been:
                last = been[-1]
                kw.update({"n": last.get("n", 0),
                           "pos": spoken_place(last.get("pos")),
                           "count": len(been)})
                if last.get("dnf"):
                    return "season_here_dnf", kw
                # A win needs its own wording: `spoken_place(1)` is "the
                # lead", and "he took the lead out of it" is not English.
                return ("season_here_won" if last.get("pos") == 1
                        else "season_here"), kw

        rec = hist.at(circuit.slug, getattr(me, "cls", None))
        if rec is None:
            # A circuit he has never raced is worth saying ONCE, and only
            # when there is a career to compare it against. "First time at
            # Monza" is a fact; on race one of an empty history it is noise.
            if hist.races >= FIRST_VISIT_AFTER:
                return "career_first_visit", kw
            return None, {}

        visits = rec.get("visits", 0)
        kw.update({
            "n": visits, "pos": spoken_place(rec.get("best")),
            "last": spoken_place(rec.get("last")),
            "wins": rec.get("wins", 0),
            "event": rec.get("event", "") or circuit.name,
        })
        # The class qualifier matters: winning here in a 1992 Williams is not
        # a claim you can make about a 2025 car. When the record comes from a
        # different class the wording has to stay generic, so those lines are
        # a separate pool rather than the same one with a slot.
        if not rec.get("same_class"):
            return "career_been_here", kw
        if rec.get("wins") and not self._record_denies_win(s, me):
            return "career_won_here", kw
        if rec.get("podiums"):
            return "career_podium_here", kw
        if rec.get("last_dnf"):
            return "career_dnf_here", kw
        if rec.get("last"):
            return "career_back", kw
        return "career_been_here", kw

    def _record_denies_win(self, s, me):
        """Would "a winner here already" contradict what we know about him?

        THE BOOTH HAS TWO SOURCES AND THEY MUST NOT DISAGREE. `career.py`
        knows what the USER has done at this circuit, folded out of every
        result XML on the machine. `drivers.py` knows what the man whose name
        is on the car has actually done in this sport, history plus this
        career. Both are true about different things, and the live log caught
        them contradicting each other inside one broadcast:

            [1235.7s] Lando Norris is still looking for that first Grand Prix win.
            [2342.1s] This is happy ground for Lando Norris — a winner at Albert Park already.

        Both lines were "correct". The first is Norris's real 2021 record; the
        second is the user's own history at Albert Park, wearing his name. A
        viewer cannot see the seam and simply hears the booth contradict
        itself about the driver it has been talking about all afternoon.

        So the DRIVER RECORD WINS, because it is the source the booth has
        already been quoting — and because a claim about a real man's career
        is the one a viewer can check. This does not touch "you have raced
        here", "you were on the podium here" or "you retired here last time":
        those are claims about the user's own weekend history and nothing in
        `drivers.py` contradicts them. Only the WIN collides, because a first
        Grand Prix win is a thing the record explicitly tracks.

        Silent — not wrong — when there is no record for the man, which is
        every driver outside the three seasons `drivers.json` holds.
        """
        st = self._driver_record(me, s.player_era or s.era,
                                 self._active_career())
        if st is None:
            return False
        return bool(getattr(st, "winless", False))

    def _win_call(self, s):
        """Which victory this was.

        The same chequered flag means four different things depending on how
        it was arrived at, and a booth that says "he wins the race" to a
        last-corner pass and to a forty-second cruise is not watching the same
        race the viewer is. The arc recorded all afternoon by `_track_story`
        finally pays for itself here.
        """
        w = s.leader
        second = s.order[1] if len(s.order) > 1 else None
        gap = second.gap_ahead if second else None
        st = self._story.get(w.id) or {}
        kw = self._kw(s, drv=w, a=w, b=second, gap=spoken_gap(gap),
                      pos=spoken_place(1),
                      from_pos=spoken_place(st.get("worst")
                                            or getattr(w, "started_place", 0)))
        if gap is not None and gap < 1.0:
            return "win_wire", kw
        if (st.get("worst") or 1) - 1 >= 6:
            return "win_comeback", kw
        if (getattr(w, "places_gained", 0) or 0) >= 5:
            kw["from_pos"] = spoken_place(getattr(w, "started_place", 0)
                                          or (1 + (w.places_gained or 0)))
            return "win_charge", kw
        if gap is not None and gap < 3.0:
            return "win_duel", kw
        return "win", kw

    def _guard(self, label, fn, *a, **kw):
        """Run one COLOUR SOURCE. Its failure costs a line, never the booth.

        Asked plainly: *"so you sure the commentary won't break again?"* The
        honest answer is that a single wrong attribute took the booth off the
        air for half a race, and no amount of care makes that impossible
        again. What can be made impossible is the CONSEQUENCE.

        The booth is a pipeline of independent sources — battles, the career,
        the circuit, the archive — feeding one ranker. Any one of them raising
        used to abort the whole tick, and because the filler runs on every
        quiet tick, an exception in a source that fires constantly is
        indistinguishable from the commentary being switched off. That is what
        happened, twice, and both times it was invisible: the traceback was
        swallowed at the top of `update_booth` and never written down.

        So a source that raises now loses ITS line and nothing else, and it
        says so in the log. The report is deduplicated by fault, with a count,
        because the failure that caused this wrote 2,618 identical tracebacks
        and a 3.4MB log nobody could read.

        Returns `fallback` (default None) when the source failed.
        """
        fallback = kw.pop("fallback", None)
        try:
            return fn(*a, **kw)
        except Exception:
            import traceback as _tb
            tb = _tb.format_exc()
            # The fault is the last frame plus the exception: the same bug on
            # every tick is one entry, a NEW bug is never hidden by an old one.
            sig = (label, tb.strip().rsplit(chr(10), 2)[-2:][0] if tb else "",
                   tb.strip().rsplit(chr(10), 1)[-1])
            seen = getattr(self, "_guard_seen", None)
            if seen is None:
                seen = self._guard_seen = {}
            seen[sig] = seen.get(sig, 0) + 1
            n = seen[sig]
            # Every failure for the first few, then powers of ten. A source
            # that is broken for an hour should be loud once, not 2,618 times.
            if n <= 3 or n in (10, 100, 1000, 10000):
                self._log("BOOTH", "%s failed (x%d): %s"
                          % (label, n, tb.replace(chr(10), " | ")))
            return fallback

    def _log(self, tag, msg):
        """A diagnostic line, on the console and in the session log.

        The overlay swallows exceptions on purpose — a broadcast that stops
        because one line raised is worse than a missing line — but a swallowed
        exception with no name is how the rookie call went missing for two
        sessions. This is the channel for "it was attempted and it failed",
        and it writes where the user already looks: `_session_log.txt`.
        """
        line = "[booth] %-8s %s" % (tag, msg)
        try:
            print(line)
        except Exception:
            pass
        try:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "_session_log.txt")
            if os.path.exists(path):
                with io.open(path, "a", encoding="utf-8") as f:
                    f.write(line + chr(10))
        except Exception:
            pass

    def _pre_stage(self, s, now, st):
        """Air the next stage of the pre-race running order. True if it aired.

        A stage that produces nothing — no circuit knowledge, no grid to
        describe — is dropped rather than retried, so a quiet stage never
        wedges the sequence and stops the ones behind it.
        """
        if not self._pre:
            return False
        # A beat between stages. Short, because the whole sequence has to fit
        # in whatever gap the session gives us, but not zero: four lines back
        # to back is a man reading a card, not a broadcast opening.
        if self.tts.speaking or now - self._last_spoke < PRE_RACE_GAP:
            return False
        stage = self._pre.pop(0)
        # A CRASHING BEAT MUST NOT SWALLOW THE PROGRAMME IN SILENCE.
        #
        # The user's first qualifying session of a USF2000 career opened,
        # named the season correctly, and then said nothing about the man at
        # all: the `career` beat raised, `update_booth` caught it at the top
        # of the tick, and the stage was already popped — so the rookie line
        # was lost with no way to tell from the outside that it had ever been
        # attempted. The log showed a traceback truncated above the frame that
        # would have named the cause.
        #
        # So the beat is fenced HERE, where the stage name is still in hand:
        # the failure is reported with the stage that caused it, and the stage
        # goes back on the front of the queue ONCE. A beat that fails twice is
        # genuinely broken and is dropped rather than retried forever.
        try:
            return self._pre_beat(s, now, st, stage)
        except Exception:
            import traceback as _tb
            self._log("BOOTH", "pre-stage %r crashed: %s"
                      % (stage, _tb.format_exc().replace(chr(10), " | ")))
            if stage not in getattr(self, "_pre_failed", ()):
                self._pre_failed = set(getattr(self, "_pre_failed", ())) | {stage}
                self._pre.insert(0, stage)
            return False

    def _pre_beat(self, s, now, st, stage):
        """One stage of the pre-session running order. See `_pre_stage`."""
        if stage == "intro":
            self._intro_at = now
            text = st.play("intro") if st else None
            if text:
                self._show_caption(text, cast_mod.PLAY, now)
                self._last_spoke = now
                return True
            return self._say("session", self._kw(s), s, now, force=True)

        if stage == "scene":
            return self._track_line(s, now, "character", force=True)

        if stage == "grid":
            # Who is on pole and who is alongside. Meaningless before the
            # order settles, which is why it sits behind the circuit line.
            if len(s.order) < 2 or not s.leader:
                return False
            return self._say("pregrid",
                             self._kw(s, a=s.leader, b=s.order[1],
                                      pos=spoken_place(1)), s, now, force=True)

        if stage == "who":
            # WHO IS ON POLE. The grid beat names him; this one says who he
            # is, which is the single most natural thing a broadcast does in
            # the last minute before a start — "Lewis, the seven-time world
            # champion, chasing an eighth".
            #
            # Drops silently for any grid we hold no records for, which is
            # most of them, and costs the opening sequence nothing when it
            # does. `force=True` bypasses the family gate deliberately: this
            # is the moment the fact is worth most, and the gate exists to
            # stop the booth reciting records DURING a race.
            for cat, kw, _subj in self._driver_facts(s, now, force=True):
                if self._driver_line(cat, kw, s, now, force=True):
                    return True
            return False

        if stage == "archive":
            # Only on a historic session, and only when there is a line for
            # the era. A modern race never sees this stage at all.
            if not cast_mod.is_historic():
                return False
            return self._say("archive_open", self._kw(s), s, now, force=True)

        if stage == "season":
            # Where this race sits in the season. Drops silently when no
            # career matches the circuit, which is the normal case for a
            # one-off race and must not cost the show a beat.
            cat, kw = self._season_call(s)
            return bool(cat) and self._say(cat, kw, s, now, force=True)

        if stage == "career":
            # WHOSE CAREER THIS IS. Straight after the season beat, because
            # "round four of six" and "and a Formula 2 seat rides on it" are
            # one thought — and before the circuit, because a viewer wants to
            # know who he is watching before he is told where they are.
            #
            # Drops silently outside a ladder career, which is every one-off
            # race, and costs the sequence nothing when it does.
            cat, kw = self._ladder_call(s, pre=True)
            if cat and self._say(cat, kw, s, now, force=True):
                return True
            cat, kw = self._register_call(s)
            return bool(cat) and self._say(cat, kw, s, now, force=True)

        if stage == "history":
            # What happened last time we were here. Drops silently on a
            # circuit the driver has never raced, which is most of them at
            # the start of a career.
            cat, kw = self._career_call(s)
            return bool(cat) and self._say(cat, kw, s, now, force=True)

        if stage == "qstart":
            # The counterpart to the grid + format beats in a race: what this
            # session is for, said once, at the top.
            cat = ("practice_start" if s.kind in ("practice", "test")
                   else "quali_start")
            return self._say(cat, self._kw(s), s, now, force=True)

        if stage == "format":
            # How long this is going to take. The single most useful thing a
            # viewer joining a broadcast can be told, and the frame every
            # later "half distance" or "ten to go" call hangs off.
            return self._say("race_duration",
                             self._kw(s, dist=self._distance_text(s)),
                             s, now, force=True)
        return False

    def _new_session(self, s):
        # THE QUALIFYING STORY IS THE ONE THING THAT SURVIVES A SESSION
        # CHANGE, and it is cleared only when a NEW qualifying session starts
        # — never on the way into the race, which is the session that needs
        # to look back at it.
        if s is not None and getattr(s, "kind", "") == "quali":
            self._quali_story.clear()
        self._prev.clear()
        self._cat_last.clear()
        self._said_start = False
        self._said_lastlap = False
        self._said_win = False
        self._best_lap_seen = None
        self._battle_since.clear()
        self._title_side = None
        self._mate_last = -1e9
        # A fight belongs to the session it happened in. Carrying any of this
        # across a restart is how "they have been at this for eight laps"
        # gets said about a race that started ninety seconds ago.
        self._pending_pass = []
        self._pass_sting_at = 0.0
        self._battle_done = []
        self._battle_clear.clear()
        self._three_since = None
        self._trades.clear()
        self._pending_caption = None
        self._reaction_for = None
        self._said_intro = False
        self._signed_off = False
        self._said_chequered = False
        self._yellow_on = False
        # NOTHING SURVIVES A SESSION CHANGE, including a safety car. A state
        # left set would have the next race believing it is already neutralised.
        self._sc_state = 0
        self._sc_since = None
        self._arm_waited = False
        self._intro_at = 0.0
        self._pre = []
        self._pre_last = 0.0
        self._post = []
        self._convo = None
        self._convo_done.clear()
        self._last_lap_seen = -1
        self._marks_done.clear()
        self._incidents = []
        self._sting_at = 0.0
        self._sting_any = 0.0
        self._named_incident = True
        self._q_best = None
        self._q_pole = None
        self._q_bests.clear()
        self._q_pole_hist = []
        self._q_duel_at = 0.0
        self._q_all_run = False
        self._q_bench_secs = None
        self._q_final = False
        self._q_set = 0
        self._q_banked = False
        self._q_climb.clear()
        self._story_told.clear()
        self._hist_told.clear()
        self._season_armed = False
        self._season_round = None
        self._season_asked = False
        self._season_count = False
        self._season_done = False
        self._season_settle = None
        self._last_pass = None
        self._story.clear()
        self._led_laps.clear()
        self._lead_changes = 0
        self._led_seen = -1
        self._facts_said.clear()
        self._driver_said.clear()
        # A car halfway through an excursion when the session ended must not
        # have it graded and announced against the new one.
        self._off_watch.clear()
        self._off_last.clear()
        self._off_count.clear()
        self.player_off = None
        self.player_lap_deleted = None
        self._q_deleted_at = -1e9
        self._q_count_flag = None
        self._phase = "mid"
        self._front_fight = False
        self._length = None
        self._length_at = 0
        # The engineer's per-session budget and state machine live on the
        # radio mixin; the booth is the only thing that knows a session has
        # changed, so it hands the news over rather than each mixin having to
        # detect it independently.
        if hasattr(self, "radio_new_session"):
            self.radio_new_session()
        lines_mod.reset_session()

    def _snapshot(self, s):
        # THE CONFIRMED PLACE IS SNAPSHOTTED TOO, and it is the whole reason the
        # pass detector works. `_detect` settles the confirmed map once per tick
        # into `_conf_now`; if it never ran this tick (a bookend-only path, or a
        # qualifying session) the raw place stands in, which is right — there is
        # no confirmed history to carry forward yet.
        conf = getattr(self, "_conf_now", None) or {}
        self._prev = {c.id: _Snap(c, conf.get(c.id)) for c in s.order}

    def _count_led(self, s):
        """Credit the leader with each lap he completes in front.

        Counted rather than inferred. The `stat` pool used to be handed
        `len(s.order)` for every one of its numbers, so "that's twenty laps in
        front" aired in a fifteen-lap race — it was the size of the grid. A
        number the booth says out loud has to be a number something measured.
        """
        lead = s.leader
        if lead is None or not s.green:
            return
        done = s.leader_laps or 0
        if done <= 0 or done == getattr(self, "_led_seen", -1):
            return
        self._led_seen = done
        # CLAMPED TO THE LAPS ACTUALLY RUN. Nobody can have led more laps than
        # the leader has completed, so this is a fact the number can be held
        # against — and it makes "Hamilton has led this Grand Prix for twenty
        # laps" impossible on lap five of a fifteen-lap race, which is what the
        # user heard.
        #
        # The cause was a race RESTART that the booth did not notice, leaving
        # the previous attempt's tally in place and adding to it; that is fixed
        # separately (RESTART_ET_DROP). This is the belt as well as the braces,
        # because a wrong number said with confidence is the fastest way for a
        # booth to stop being believed, and there will be other ways to miss a
        # restart. LAW 17: a number the booth says out loud has to be one
        # something measured.
        self._led_laps[lead.id] = min(self._led_laps.get(lead.id, 0) + 1, done)

    def _laps_led(self, car):
        return self._led_laps.get(getattr(car, "id", None), 0) if car else 0

    @staticmethod
    def _laps_text(n):
        """"twelve laps" / "one lap". The slot carries its own noun and its
        own plural, because the frames around it vary and LAW 13 says the
        template may not supply a determiner."""
        return "1 lap" if n == 1 else "%d laps" % n

    @staticmethod
    def _changes_text(n):
        return "twice" if n == 2 else "%d times" % n

    @staticmethod
    def _top3_covered(s):
        """Are the top three genuinely within a second on their best laps?

        The line that claims this used to be offered unconditionally, which
        made it an assertion rather than an observation. Now it is only
        offered when it is true, and it needs three real lap times to be
        true at all.
        """
        best = [c.best_lap for c in s.order[:3]
                if getattr(c, "best_lap", None)]
        if len(best) < 3:
            return False
        return (max(best) - min(best)) < 1.0

    # -- speaking -------------------------------------------------------------
    def _say(self, cat, kw, s, now, persona=None, force=False):
        """Speak one line if cooldowns and personas allow. True if it aired.

        `force` bypasses the cooldowns entirely, for the scripted bookends —
        the start and the finish must be called whatever else just happened.
        """
        prio = PRIORITY.get(cat, 0)
        gap = URGENT_COOLDOWN if prio >= 75 else GLOBAL_COOLDOWN
        if not force and now - self._last_spoke < gap:
            return False
        cool = COOLDOWNS.get(cat, 10.0)
        if cat in COLOUR_CATS:
            cool *= COLOUR_SCALE.get(self._length or "normal", 1.0)
        if not force and now - self._cat_last.get(cat, 0.0) < cool:
            return False
        # Never talk over the previous line unless this is genuinely urgent.
        if not force and self.tts.speaking and prio < 80:
            return False

        who = cast_mod.who_says(cat, prefer=persona)
        era = s.player_era or s.era
        text, intensity, override = lines_mod.pick(cat, era, kw)
        if not text:
            return False
        if override and cast_mod.can_say(override, cat):
            who = override

        # The big moments get the swelling delivery. Gated hard: if everything
        # builds, nothing does.
        build = intensity >= 3 and cat in ("win", "leadchange", "lastlap",
                                           "start", "overtake_multi")
        self.tts.speak(text, who, intensity=intensity, build=build,
                       name=kw.get("_name", ""))
        # One more line has gone to air. `_status_form` seeds on this so a
        # mention is stable while a tick composes it and varies between
        # mentions — which is the whole difference between "one time in six"
        # and "every time, all session".
        self._say_n = getattr(self, "_say_n", 0) + 1
        if cat in INCIDENT_CATS and kw.get("drv"):
            self._named_incident = True
        # HE HAS NOW BEEN NAMED. LAW 11: the flag is set because a line AIRED,
        # never because one was composed — `_kw` builds far more lines than
        # the booth ever speaks, and flipping this on composition is how the
        # introduction gets spent on a sentence nobody heard.
        me = getattr(s, "player", None)
        if (me is not None and kw.get("_name")
                and kw["_name"] == getattr(me, "name", None)):
            if not getattr(self, "_status_named", False):
                self._status_named = True
                # ...and the follow-up thought a commentator always has after
                # introducing somebody: what he is, and what may come of him.
                if not getattr(self, "_status_told", False):
                    self._status_follow = now
        self._last_spoke = now
        self._cat_last[cat] = now
        # THE TEAM-MATE FAMILY. Six pools that all mean "the man in the other
        # side of the garage"; stamped here, on the line that actually went
        # to air (LAW 11), so a composed-and-refused line cannot spend the
        # gate.
        if cat in MATE_CATS:
            self._mate_last = now
        # SAID ONCE PER SESSION, whichever route said it — the pre-session
        # career beat and the follow-up after his first mention are two ways
        # of reaching the same sentence, and only one of them may win.
        if cat in STATUS_CATS:
            self._status_told = True
            self._status_follow = 0.0
        self._show_caption(text, who, now)
        return True

    # An excursion is graded on how badly it went, not on the fact of it.
    # Two wheels on the grass at Copse is a moment; four wheels in the gravel
    # with the speed halved is an incident, and calling both the same way is
    # how a booth stops being believed.
    OFF_WHEELS = 2          # wheels off the racing surface to open a watch
    OFF_MAX_S = 8.0         # grade it anyway if he never comes back
    OFF_SPIN_FRAC = 0.58    # lost 40%+ of entry speed -> a spin, not a slide
    OFF_WIDE_FRAC = 0.85    # a real loss of pace, short of a spin
    OFF_WIDE_S = 0.9        # ...or simply a LONG time with wheels off
    OFF_COOLDOWN = 20.0     # per car. A car recovering after an off keeps
                            # tripping the detector, so the gap has to outlast
                            # the recovery, not just the call.

    def _track_limits_ground_truth(self, s, now):
        """Did rF2's OWN warning just fire for a track-limits or cut event?

        `s.status_message_new` is edge-triggered (LAW 1) by `rf2_session`,
        so this is True for exactly one tick per message — never re-read
        while the same warning stays on screen.

        Keyword-gated rather than "any new message", because the same buffer
        also carries penalty notices and pit instructions, and treating
        those as an off would put the sting and the engineer's "are you
        okay" over a message that was never about running wide at all.
        """
        if not getattr(s, "status_message_new", False):
            return False
        if now - self._off_last.get("__status", -1e9) < self.OFF_COOLDOWN:
            return False
        msg = (getattr(s, "status_message", "") or "").lower()
        hit = any(w in msg for w in ("track limit", "cut track", "off track",
                                     "off-track", "exceeded track"))
        if hit:
            self._off_last["__status"] = now
        return hit

    def _excursion_events(self, c, p, s, now):
        """One car's excursion, graded and turned into calls.

        LIVES HERE, AND NOT INSIDE `_detect`, BECAUSE QUALIFYING NEEDS IT TOO.
        It was written inline in the race detector, and `_quali_detect` is a
        separate function — so for the whole of a qualifying session NOTHING
        looked at the surface at all. A driver could put all four wheels in
        the gravel on a hot lap and get silence from the booth, silence from
        the sting bank, and silence from the engineer, because `player_off`
        is set here and nowhere else. That is exactly what the user reported.

        An off is an off in any session; what CHANGES with the session is
        what it costs, and that is the caller's business, not this method's.
        """
        out = []
        if not (self._interesting(c) and s.green and not c.in_pits):
            return out
        ev = self._track_excursion(c, p, s, now)
        if ev and c.is_player:
            # Published for the ENGINEER, who has to react to your off
            # whether or not the booth chose to call it. Consumed and
            # cleared by RadioMixin; the booth never reads it back.
            self.player_off = (ev, now)
        if ev in ("spin", "offtrack"):
            # STING, THEN THE NAME, THEN THE REACTION — as one sequence.
            #
            # This used to fire the sting and then OFFER the naming line as an
            # ordinary event, and the live log shows what that produced:
            # three stings in a qualifying session, and not one of them
            # followed by a name. The reason is exact — `offtrack` carries
            # priority 50, `_say` refuses anything under 80 while audio is
            # playing, and the sting IS audio. So the alert reliably silenced
            # the line that explains it, and because detection is edge-
            # triggered the call was gone for ever. The viewer got "we've got
            # a car in trouble!" and never found out who.
            #
            # `_incident_report` speaks the whole thing itself, in one breath,
            # the way the crosstalk two-hander already does.
            if self._incident_report(s, now, c, ev):
                return out
            # No sequence (no lines, or one just went out) — fall back to the
            # single named call rather than leaving the sting unexplained.
            self._incident_sting(now)
            out.append((self._incident_cat(ev, now), self._kw(s, drv=c), c))
        elif ev == "ranwide":
            # A moment rather than an incident. Worth a sentence, not
            # worth an alarm — and calling every tidy-up "he's off!"
            # is how a booth spends its credibility.
            out.append(("ranwide", self._kw(s, drv=c), c))
        elif c.is_player and self._track_limits_ground_truth(s, now):
            # THE GAME'S OWN WARNING, as a backstop.
            #
            # `_track_excursion` infers an off from wheel telemetry or
            # a speed drop, and it can genuinely miss one — a car that
            # runs wide onto flat, grippy tarmac loses little speed
            # and may not cross the wheels-off threshold at all. rF2's
            # own track-limits message is ground truth from the sim,
            # not an inference, so it catches exactly the case the
            # surface detector was built to catch and sometimes does
            # not: a real off that cost no lap time.
            #
            # Graded as "ranwide" — a warning, not a crash — because
            # the message says a limit was crossed, not how badly.
            self.player_off = ("ranwide", now)
            out.append(("ranwide", self._kw(s, drv=c), c))
        return out

    def _track_excursion(self, c, p, s, now):
        """Has this car just been off? Returns "spin" / "offtrack" / "ranwide"
        or None, once, when the excursion ENDS.

        rF2 gives a per-wheel `mSurfaceType`, so unlike the RaceRoom overlay
        this is a fact rather than an inference from a speed drop. That matters
        for the case the old detector was silent on: a car that runs wide onto
        tarmac runoff and keeps its foot in loses no speed at all.

        Reported on the way BACK, not on the way off, because the grading needs
        to know how bad it got — and because a car still in the gravel is not
        yet a story with an ending.
        """
        cid = c.id
        spd = c.speed or 0.0
        # getattr, not attribute access: the synthetic cars the tests and
        # preview build do not carry telemetry, and "no telemetry" is already
        # a case this has to handle honestly.
        off = getattr(c, "wheels_off", None)

        if off is None:
            # No telemetry for this car, so we genuinely do not know where its
            # wheels are. Fall back to the speed-drop inference rather than
            # asserting it stayed on the road.
            drop = (p.speed or 0.0) - spd
            if now - self._off_last.get(cid, -1e9) < self.OFF_COOLDOWN:
                return None
            if drop > 55.0 and spd < 60.0:
                self._off_last[cid] = now
                self._off_count[cid] = self._off_count.get(cid, 0) + 1
                return "spin"
            if drop > 45.0 and spd < 110.0:
                self._off_last[cid] = now
                self._off_count[cid] = self._off_count.get(cid, 0) + 1
                return "offtrack"
            if drop > 30.0 and spd < 130.0:
                self._off_last[cid] = now
                self._off_count[cid] = self._off_count.get(cid, 0) + 1
                return "ranwide"
            return None

        w = self._off_watch.get(cid)
        if off >= self.OFF_WHEELS:
            if w is None:
                # Entry speed is sampled from the PREVIOUS tick: by the time
                # two wheels are on the grass the car may already be slowing,
                # and grading against that understates every off.
                self._off_watch[cid] = [off, max(p.speed or 0.0, spd), spd, now]
            else:
                w[0] = max(w[0], off)
                w[2] = min(w[2], spd)
            w = self._off_watch[cid]
            if now - w[3] < self.OFF_MAX_S:
                return None          # still out there; wait for the ending
        elif w is None:
            return None

        max_wheels, ref, low, since = w
        self._off_watch.pop(cid, None)
        if now - self._off_last.get(cid, -1e9) < self.OFF_COOLDOWN:
            return None
        ref = max(ref, 1.0)
        dur = now - since
        if low < ref * self.OFF_SPIN_FRAC:
            self._off_last[cid] = now
            self._off_count[cid] = self._off_count.get(cid, 0) + 1
            return "spin"
        if max_wheels >= 4:
            self._off_last[cid] = now
            self._off_count[cid] = self._off_count.get(cid, 0) + 1
            return "offtrack"
        if low < ref * self.OFF_WIDE_FRAC or dur >= self.OFF_WIDE_S:
            self._off_last[cid] = now
            self._off_count[cid] = self._off_count.get(cid, 0) + 1
            return "ranwide"
        # Two wheels brushing the grass for a fraction of a second, no pace
        # lost. That is not an excursion, it is a racing line.
        return None

    def _incident_cat(self, base, now):
        """Which flavour of "somebody's off" this is.

        A booth that reports the third incident in ten seconds in exactly the
        words it used for the first is not watching the same race the viewer
        is. Three things change the call:

          * it is not the first — "and X is off as well"
          * several at once — "it's chaos out there"
          * it landed on top of a conversation — the booth has to apologise
            for cutting in, which is the single most human thing it does

        The cut-in case only became possible now that there is a conversation
        to cut into; RacerTV had the lines and FACTORtv had nowhere to use
        them.
        """
        self._incidents = [t for t in self._incidents if now - t < CHAOS_WINDOW]
        n = len(self._incidents)
        self._incidents.append(now)
        if self._convo is not None:
            # Abandon the exchange here rather than waiting for the ranking
            # pass, so the apology and the abandonment are the same decision.
            self._convo = None
            return "offtrack_cut"
        if n >= 2:
            return "offtrack_chaos"
        if n == 1:
            return "offtrack_more"
        return base

    def _sting_bank(self):
        """The sting bank, bound on FIRST USE by whoever needs it first.

        It used to be bound only inside `_bookends`, and `_tick_body` runs
        DETECTION BEFORE BOOKENDS — so on the opening tick of a session
        `self._stings` was still None while the detectors were running, and an
        incident on that tick got no alert. Binding here removes the ordering
        dependency altogether rather than moving it somewhere else.
        """
        if self._stings is None:
            self._stings = getattr(self, "sting_bank", None)
        return self._stings

    def _sting(self, now, group, gap=STING_GAP):
        """Fire a pre-rendered reaction NOW, if one is cached and it is not
        treading on another.

        Stings exist for moments where a 2-6 second live render arrives after
        the thing it describes. The cost is that they are name-free and
        interchangeable, so they are rate-limited as a group: three canned
        reactions inside ten seconds sounds like a soundboard, not a booth.
        """
        st = self._sting_bank()
        if st is None or now - self._sting_any < gap:
            return False
        text = st.play(group)
        if not text:
            return False
        self._sting_any = now
        self._show_caption(text, cast_mod.PLAY, now)
        self._last_spoke = now
        return True

    def _incident_report(self, s, now, car, ev):
        """The whole incident, as three beats in one breath.

        The shape the user asked for, in his words: the pundit cuts in — "hold
        on, there's been an incident" — then "the pundit must also report on
        the incident directly after that", naming the driver, and then Miles
        answers him. Sting, identification, reaction.

        WHY IT IS SPOKEN HERE INSTEAD OF OFFERED AS AN EVENT. The old version
        rang the sting and queued the naming line for the normal ranking pass,
        and the live log is unambiguous about the result: three alerts in one
        qualifying session, none of them ever followed by a name. `offtrack`
        is priority 50, `_say` drops anything below 80 while audio is playing,
        and the sting is audio — so the alert silenced its own explanation
        every single time. Detection is edge-triggered, so there was no second
        chance. Queuing all of it together is the same fix, for the same
        reason, that the crosstalk two-hander already documents: `tts.speak`
        only enqueues, and a beat scheduled for later lands in the silence its
        own render created.

        WHY THE PUNDIT NAMES IT. He is the one who interrupted, so he owes the
        viewer the identification — and it hands the play-by-play seat a reply
        to make, which is what turns an announcement into a booth. It also
        means the caption colour changes with the voice, so the sequence reads
        as two people rather than one man talking twice.
        """
        st = self._sting_bank()
        if st is None or now - self._sting_at < INCIDENT_SEQ_GAP:
            return False
        era = s.player_era or s.era
        # CUTTING INTO A CONVERSATION IS ITS OWN SENTENCE, and keeping it was
        # worth the extra pool: apologising for the interruption is the single
        # most human thing this booth does. The existing `offtrack_cut` is
        # Miles apologising to Chuck, which is the wrong direction now that
        # the pundit is the one interrupting — hence the mirror.
        #
        # DECIDED BEFORE THE SLOTS ARE BUILT, because `_kw` now takes the
        # category: it is what tells the status form whether this is a line
        # the status belongs in. Building `kw` first read `id_cat` before it
        # existed, which is a NameError on every incident in the product.
        if self._convo is not None:
            id_cat = "incident_cut_id"
        else:
            id_cat = "incident_id_spin" if ev == "spin" else "incident_id_off"
        kw = self._kw(s, drv=car, pos=spoken_place(car.place), cat=id_cat)
        ident, i_int, _o = lines_mod.pick(id_cat, era, kw)
        react, r_int, _o2 = lines_mod.pick("incident_react", era, kw)
        if not ident:
            return False

        # BEAT 1. Name-free by necessity — at the instant of the moment
        # nobody knows who it was, which is exactly why beats 2 and 3 exist.
        alert = st.play("alert")
        self._sting_at = now
        self._sting_any = now
        if alert:
            self._show_caption(alert, cast_mod.ANALYST, now)

        # BEAT 2. The debt paid: the driver, by name.
        self.tts.speak(ident, cast_mod.ANALYST, intensity=i_int)
        self._named_incident = True
        self._cat_last[id_cat] = now
        # Marked here rather than by the caller, so the chaos/repeat grading
        # sees this incident even though it never went through `_incident_cat`.
        self._incidents = [t for t in self._incidents if now - t < CHAOS_WINDOW]
        self._incidents.append(now)

        # BEAT 3. The reply. Skipped rather than faked if the pool is empty,
        # because two beats that land is better than three where one is blank.
        if react:
            self.tts.speak(react, cast_mod.PLAY, intensity=r_int)
            self._cat_last["incident_react"] = now
            # Armed, not shown: captions follow `tts.now_playing`, so this
            # appears when Miles is actually audible instead of on top of the
            # line he is answering.
            self._pending_caption = (react, cast_mod.PLAY, now + 0.1)
        else:
            self._pending_caption = None
        if alert:
            # The identification's own caption has to wait for the alert to
            # finish, and the reply's for the identification. Only one can be
            # pending, so the identification is shown immediately after the
            # sting caption and the reply takes the armed slot above.
            self._show_caption(ident, cast_mod.ANALYST, now)

        self._last_spoke = now
        # A conversation cannot survive somebody going off, and abandoning it
        # here makes the abandonment and the interruption the same decision.
        self._convo = None
        return True

    def _pass_matters(self, s, car, victim, newp):
        """Is this pass worth a sting, or is it one for the queue?

        The user's call, and the reason it is a gate rather than a volume
        knob: a sting cuts through everything, so if every pass fires one the
        sting stops meaning anything and we have rebuilt the brake-temperature
        problem in the commentary. Two things qualify:

          * A pass into the front of the field. That is the race.
          * A pass involving the PLAYER, either way round. He is driving; a
            place he took or lost is the only thing on the timing screen he
            can feel, and it is the specific complaint that started this
            work.
        """
        if newp <= PASS_STING_PLACES:
            return True
        me = getattr(s, "player", None)
        if me is None:
            return False
        return car.id == me.id or (victim is not None and victim.id == me.id)

    def _overtake_report(self, s, now, car, victim, cat, kw):
        """Sting, name, verdict - the pass, in one breath.

        EXACTLY THE SHAPE `_incident_report` USES, AND FOR THE SAME REASON.
        The pass was being detected and then dropped: `_say` refuses anything
        under priority 80 while audio is playing, `overtake` is 60, and there
        is no queue behind it, so a move made while Miles was talking was
        gone. Speaking all of it here means the sequence cannot lose a tick
        to itself or to anything else.

        THE `pass` STINGS ALREADY EXISTED. Six of them, rendered to disk on
        every startup since the sting module was written, and `_sting` has
        only ever been called for `lastlap` and `retire` - so they have never
        once played. That is the fourth piece of built-and-unreachable
        content this project has turned up, and the reason LAW 21 asks for a
        caller and a test rather than for the content to look right.

        WHO SAYS WHAT IS THE OPPOSITE OF AN INCIDENT, deliberately. Nobody
        knows who has gone off, so the analyst identifies and the play-by-play
        seat replies. Everybody can see who just went past, so the CALL is
        the play-by-play seat's - it is the single most play-by-play thing in
        the sport - and the analyst gives the verdict on whether it was any
        good.
        """
        # IT BYPASSES ONE RULE AND ONE ONLY: "never talk over the previous
        # line unless this is urgent", which is the rule that was silently
        # eating passes. Every other restraint still applies, and the first
        # version of this skipped the lot - forty swaps produced sixty lines
        # and `boothtest.py` section 3 caught it immediately. A booth that
        # calls every place change the instant it happens is not a fix for a
        # booth that called none of them, it is the same failure inverted.
        #
        # A refusal here is not a loss: the caller falls through to the
        # ordinary event path, which queues the pass for a few seconds.
        st = self._sting_bank()
        if now - self._pass_sting_at < PASS_SEQ_GAP:
            return False
        if now - self._last_spoke < GLOBAL_COOLDOWN:
            return False
        if now - self._cat_last.get(cat, 0.0) < COOLDOWNS.get(cat, 10.0):
            return False
        era = s.player_era or s.era
        text, intensity, override = lines_mod.pick(cat, era, kw)
        if not text:
            return False

        # BEAT 1. Name-free, and it lands on the moment rather than after a
        # 2-6 second render. A missing bank is not a failure: the call below
        # is the part that carries the information.
        alert = st.play("pass") if st is not None else None
        if alert:
            self._pass_sting_at = now
            self._sting_any = now
            self._show_caption(alert, cast_mod.PLAY, now)

        # BEAT 2. The call.
        who = cast_mod.PLAY
        if override and cast_mod.can_say(override, cat):
            who = override
        build = intensity >= 3 and cat in ("leadchange", "overtake_multi")
        self.tts.speak(text, who, intensity=intensity, build=build,
                       name=kw.get("_name", ""))
        self._cat_last[cat] = now
        self._last_spoke = now
        # The call's caption replaces the sting's immediately: the sting is a
        # noise, the call is the information, and the viewer wants the name
        # on screen rather than "hold on" for the length of a render.
        self._show_caption(text, who, now)

        # LAW 11, and it has to be done by hand here because this path does
        # not go through `_say`. The status form spends its one introduction
        # on the first line that AIRS, and this one has just aired.
        me = getattr(s, "player", None)
        if (me is not None and kw.get("_name")
                and kw["_name"] == getattr(me, "name", None)
                and not getattr(self, "_status_named", False)):
            self._status_named = True
            if not getattr(self, "_status_told", False):
                self._status_follow = now

        # BEAT 3. The verdict, queued in the same breath so the renderer has
        # it ready while Miles is still talking.
        self._maybe_crosstalk(cat, kw, now, s)
        # A pass cannot survive a conversation either - the booth has moved on
        # to the racing, and coming back to "so as I was saying" after a move
        # for the lead is a booth that was not watching.
        if self._convo is not None and cat in ("leadchange", "retake"):
            self._convo = None
        return True

    def _incident_sting(self, now):
        """Fire the name-free alert immediately, if one is cached."""
        st = self._sting_bank()
        if st is None or now - self._sting_at < 12.0:
            return
        text = st.play("alert")
        if text:
            self._sting_at = now
            # The alert is deliberately nameless. Until a line names the
            # driver, the booth owes the viewer that identification — and if
            # it never arrives, it has to be given late rather than dropped.
            self._named_incident = False
            self._show_caption(text, cast_mod.ANALYST, now)

    # -- track knowledge --------------------------------------------------------
    def _track_line(self, s, now, kind, force=False):
        """Speak something true about THIS circuit.

        Delivered straight from `tracks.json` rather than through the line
        pools, because these are facts about a real place rather than
        templates — there is nothing to fill in and nothing to gate on era.
        Anything the booth does not recognise simply produces no line, which
        is the correct behaviour for a circuit we know nothing about.
        """
        circuit = getattr(s, "circuit", None)
        if circuit is None or not circuit.known:
            return False
        if kind == "character":
            text = circuit.character()
        else:
            pool = circuit.facts()
            if not pool:
                return False
            # ONE FACT AT MOST ONCE PER SESSION.
            #
            # The shared bag is right for dialogue pools with dozens of
            # entries, but a circuit has three or four facts, and its
            # recency block lifts after a few minutes — so Montreal's
            # island-in-the-Saint-Lawrence line went out three times in one
            # qualifying session. A viewer notices that immediately.
            #
            # Session-scoped: the used set is cleared with the session, so
            # the next race may reuse them all.
            used = self._facts_said.setdefault(circuit.slug, set())
            fresh = [f for f in pool if f not in used]
            if not fresh:
                # Everything said already. Better to repeat the least recent
                # than to go silent for the rest of a long race.
                used.clear()
                fresh = list(pool)
            key = "track_fact|%s" % circuit.slug
            entry = lines_mod._bag.pick(key, [{"t": f} for f in fresh])
            text = entry["t"] if entry else ""
            if text:
                used.add(text)
        if not text:
            return False
        cat = "track_character" if kind == "character" else "track_fact"
        if not force:
            if now - self._last_spoke < GLOBAL_COOLDOWN:
                return False
            if now - self._cat_last.get(cat, 0.0) < COOLDOWNS.get(cat, 120.0):
                return False
            if self.tts.speaking:
                return False
        # Track colour belongs to the analyst: it is context, not action.
        self.tts.speak(text, cast_mod.ANALYST, intensity=0)
        self._last_spoke = now
        self._cat_last[cat] = now
        self._show_caption(text, cast_mod.ANALYST, now)
        return True

    # -- who these people are ---------------------------------------------------
    #
    # The booth's biggest blind spot was that it knew the race perfectly and
    # knew nothing about the sport. `drivers.py` is the knowledge; this is the
    # editorial layer that decides when any of it is worth saying.
    #
    # Three gates, in this order, and each one exists because of a way this
    # feature could get annoying rather than wrong:
    #
    #   the FAMILY gate    every driver fact is the same kind of sentence, so
    #                      they share one long cooldown (LAW 15).
    #   ONCE PER DRIVER    per category, per session. Telling the viewer twice
    #                      that Hamilton is the reigning champion is worse
    #                      than never telling him.
    #   FOCUS              only drivers the viewer can plausibly see.
    #
    # Being WRONG is handled a layer down: `drivers.lookup` returns None for
    # any name it cannot resolve and for any era it does not have, and
    # `slots_for` refuses a category the driver's record does not support.

    def _levity_ok(self, s, now):
        """Is this a moment where a joke is allowed AT ALL?

        A hard veto, checked before any light line is offered rather than
        after it is picked, because the failure this prevents is the booth
        being funny over somebody's afternoon ending. See the LEVITY block
        above for why the gate is this generous.

        Returns True only when the race is running normally and nothing has
        recently gone wrong for anybody.
        """
        # Something is on fire somewhere. `_incidents` holds the times of the
        # recent ones and `_sting_at` the last nameless alert, which fires for
        # things the booth has not even identified yet — and "we do not know
        # what just happened" is the worst possible moment for a punchline.
        if now - self._sting_at < LEVITY_AFTER_INCIDENT:
            return False
        if self._incidents and now - max(self._incidents) < LEVITY_AFTER_INCIDENT:
            return False
        if self._yellow_on or getattr(s, "full_course_yellow", False):
            return False
        # The closing phase of any race, and the whole late phase of one that
        # settles a championship. "Late" is a fifth of the race, which is a
        # lot of silence — but a title decider is the one broadcast where the
        # tension is the product.
        if self._phase == "closing":
            return False
        if self._phase == "late" and self._title_at_stake():
            return False
        # A race that has not settled yet. Lap one is not funny, it is busy.
        if (s.leader_laps or 0) < LEVITY_MIN_LAPS and not s.max_laps:
            return False
        if s.max_laps and (s.leader_laps or 0) < min(LEVITY_MIN_LAPS,
                                                     s.max_laps // 4):
            return False
        # The player having a bad time. He is the one man on the grid who
        # cannot be the joke, because he is the one actually living it.
        me = s.player
        if me is not None:
            if getattr(self, "player_off", None):
                return False
            if max(getattr(me, "damage", None) or (0,)) > 0:
                return False
            if getattr(me, "in_pits", False):
                return False
        return True

    # The elaborated history categories, one per `drivers.CATEGORIES` entry
    # that has a long-form answer written for it. Anything not in here simply
    # keeps the short `booth_driver.json` form, which is correct — not every
    # fact deserves a paragraph.
    HIST_ANSWER = {
        "driver_reigning": "hist_reigning",
        "driver_chasing": "hist_chasing",
        "driver_champion": "hist_champion",
        "driver_winner": "hist_winner",
        "driver_winless": "hist_winless",
        "driver_rookie": "hist_rookie",
        "driver_new_team": "hist_new_team",
        "driver_favourite": "hist_favourite",
        "driver_season_wins": "hist_season_wins",
        "driver_note": "hist_note",
    }

    def _history_report(self, s, now):
        """Miles asks who a driver IS, and Chuck explains at length.

        The short form in `booth_driver.json` states a record — "Verstappen
        has ten wins" — and the user's complaint about it was exact: "one
        statement and then theres no conversation, full stop". It averages
        ten words a line.

        This is the same knowledge in the other register: what the record
        MEANS rather than what it is, as a two-hander, at Chuck's full length.
        Both registers are kept, because a quick fact is right when the booth
        is busy and a conversation is right when it is not.

        Every gate is the one the short form already uses — same
        `drivers.CATEGORIES`, same live `Standing` — so this can no more be
        said about the wrong driver than the short version can.
        """
        era = s.player_era or s.era
        if drivers_mod.season_of(era) is None:
            return False
        if now - self._cat_last.get("driver_ask", 0.0) < COOLDOWNS["driver_ask"]:
            return False
        if self.tts.speaking or now - self._last_spoke < GLOBAL_COOLDOWN:
            return False
        career = self._active_career()
        me = s.player
        cars = list(s.order[:DRIVER_FOCUS]) + ([me] if me is not None else [])
        # SPREAD ACROSS THE GRID BEFORE GOING BACK TO ANYBODY.
        #
        # Taking the first driver with an unused angle meant the leader got
        # all five of his in a row before the booth mentioned a second man —
        # which is the same repetition complaint in a new costume. Drivers
        # nobody has been asked about yet come first.
        def _asked(c):
            # Resolved to the CANONICAL name, because that is what
            # `_hist_told` is keyed by — the mod's spelling and the record's
            # differ, and sorting on the wrong one silently does nothing.
            d = self._driver_record(c, era)
            return len(self._hist_told.get(d.name, ())) if d else 99
        cars.sort(key=_asked)
        for c in cars:
            if c is None:
                continue
            drv = self._driver_record(c, era, career)
            if drv is None:
                continue
            told = self._hist_told.setdefault(drv.name, set())
            for cat in drivers_mod.eligible(drv):
                ans = self.HIST_ANSWER.get(cat)
                if ans is None or cat in told:
                    continue
                slots = drivers_mod.slots_for(drv, cat)
                if not slots:
                    continue
                kw = self._kw(s, drv=c)
                kw.update(slots)
                kw["drv"] = drv.name
                q, _i, _o = lines_mod.pick("driver_ask", era, kw)
                a, ai, _o2 = lines_mod.pick(ans, era, kw)
                if not q or not a:
                    continue
                told.add(cat)
                self.tts.speak(q, cast_mod.PLAY, intensity=0)
                self.tts.speak(a, cast_mod.ANALYST, intensity=ai)
                self._last_spoke = now
                self._cat_last["driver_ask"] = now
                self._cat_last[ans] = now
                self._show_caption(q, cast_mod.PLAY, now)
                self._pending_caption = (a, cast_mod.ANALYST, now + 0.1)
                return True
        return False

    def _story_report(self, s, now):
        """Miles asks Chuck how a driver's race has gone, and Chuck answers.

        THE THING THE BOOTH WAS MISSING. In a fifty-two minute live race it
        held eight conversations and not one of them was about a driver — they
        were all about the circuit or the field in general. A broadcast asks
        this question all afternoon, and it is the main way a viewer learns
        that the twelve cars behind the leader are having races of their own.

        Both halves go out in the SAME breath, for the reason the crosstalk
        code already documents: `tts.speak` only enqueues and a render takes
        seconds, so scheduling the answer for later lands it in the silence
        its own render created.

        The answer is chosen by the driver's own `Arc.headline()`, so it can
        only ever be true of the man being asked about.
        """
        if not s.green or s.kind != "race":
            return False
        if now - self._cat_last.get("story_ask", 0.0) < COOLDOWNS["story_ask"]:
            return False
        if self.tts.speaking or now - self._last_spoke < GLOBAL_COOLDOWN:
            return False
        if not self._enough_race(s):
            return False        # a race needs to have happened to report on

        arcs = story_mod.field(self, s, top=STORY_FOCUS)
        for arc in arcs:
            cat = arc.headline()
            # ONE REPORT PER DRIVER PER SESSION. The second one would be about
            # the same afternoon with two more laps on it.
            if cat is None or arc.name in self._story_told:
                continue
            kw = self._kw(s, drv=arc.car,
                          pos=spoken_place(arc.place),
                          grid=spoken_place(arc.grid),
                          best=spoken_place(arc.best),
                          worst=spoken_place(arc.worst),
                          n=self._places_text(max(abs(arc.gained),
                                                  arc.recovered, arc.slid)),
                          offs=self._times_text(arc.offs))
            q, _i, _o = lines_mod.pick("story_ask", s.player_era or s.era, kw)
            a, ai, _o2 = lines_mod.pick(cat, s.player_era or s.era, kw)
            if not q or not a:
                continue
            self._story_told.add(arc.name)
            self.tts.speak(q, cast_mod.PLAY, intensity=0)
            self.tts.speak(a, cast_mod.ANALYST, intensity=ai)
            self._last_spoke = now
            self._cat_last["story_ask"] = now
            self._cat_last[cat] = now
            self._show_caption(q, cast_mod.PLAY, now)
            # The answer's caption is armed rather than shown: the drawing
            # follows `tts.now_playing`, so it appears when Chuck is actually
            # audible rather than on top of the question.
            self._pending_caption = (a, cast_mod.ANALYST, now + 0.1)
            return True
        return False

    @staticmethod
    def _places_text(n):
        return "one place" if n == 1 else "%d places" % n

    @staticmethod
    def _times_text(n):
        return {1: "once", 2: "twice", 3: "three times"}.get(n, "%d times" % n)

    def _class_filler(self, s, now):
        """The race as the mixed grid actually experiences it.

        In a multiclass race the overall order is not the result. A GT3 car
        running ninth may be leading its class, and calling him ninth tells
        the viewer nothing about the race he is in. `Car.place_class` has
        been computed on every tick since the session module was written and
        read by absolutely nothing.

        Silent in a single-class race, which is almost all of them — and
        silent on a team-named F1 grid, because `s.multiclass` now excludes
        those (they are one championship wearing ten class labels).
        """
        out = []
        if not getattr(s, "multiclass", False) or not s.green:
            return out
        me = s.player
        # THE CLASS LEADER, when he is not also the race leader — otherwise
        # the booth is announcing the same man twice in different words.
        for c in s.order[:STORY_FOCUS]:
            if getattr(c, "place_class", 0) == 1 and c.place != 1:
                out.append(("class_lead",
                            self._kw(s, drv=c, pos=spoken_place(c.place),
                                     cls=c.cls), c))
                break
        # WHERE THE PLAYER REALLY IS. The single most useful thing the booth
        # can say to a man in a slower class.
        if me is not None and getattr(me, "place_class", 0):
            if me.place_class != me.place:
                out.append(("class_pos",
                            self._kw(s, drv=me, pos=spoken_place(me.place),
                                     cpos=spoken_rank(me.place_class),
                                     cls=me.cls), me))
        # A FIGHT THAT IS ONLY A FIGHT IN CLASS — two cars of the same class
        # close together. Worth more than a road-position battle between two
        # cars that are not racing each other at all.
        for c in s.order[:STORY_FOCUS]:
            ahead = s.car_ahead(c)
            if ahead is None or c.in_pits or ahead.in_pits:
                continue
            if ahead.cls != c.cls or (c.gap_ahead or 99.0) >= STRIKE_GAP:
                continue
            out.append(("class_battle",
                        self._kw(s, a=c, b=ahead, cls=c.cls,
                                 cpos=spoken_rank(getattr(ahead,
                                                          "place_class", 0)),
                                 gap=spoken_gap(c.gap_ahead)), c))
            break
        # TRAFFIC: a car of another class close ahead. In endurance racing
        # this is most of the skill and none of the timing screen.
        if me is not None:
            ahead = s.car_ahead(me)
            if (ahead is not None and ahead.cls != me.cls
                    and not ahead.in_pits
                    and 0.0 < (me.gap_ahead or 99.0) < STRIKE_GAP):
                out.append(("class_traffic", self._kw(s, drv=me, b=ahead), me))
        return out

    def _levity(self, s, now):
        """Something light, when the race can afford one. Usually nothing.

        Two gates before anything is offered: `_levity_ok` decides whether the
        MOMENT allows humour at all, and the family gap decides whether the
        booth has been funny too recently. Both are hard, because the ranking
        pass cannot be trusted with this — a joke that merely loses the tick
        to an incident was still a joke offered while somebody was in the
        wall, and the next quiet tick would air it.
        """
        out = []
        if not self._levity_ok(s, now):
            return out
        last = max((self._cat_last.get(c, 0.0) for c in HUMOUR_CATS))
        if now - last < HUMOUR_FAMILY_GAP:
            return out

        # GROUNDED DIGS FIRST. A dig at a driver only works when the viewer
        # has watched the same thing the booth is teasing him about — which
        # is also what keeps it affectionate rather than arbitrary.
        #
        # Stuck behind the same car for a very long time. Twice the threshold
        # that already earns a "sustained battle" call, so this is a stalemate
        # the viewer is bored of too.
        for c in s.order[:DRIVER_FOCUS]:
            ahead = s.car_ahead(c)
            if ahead is None or c.in_pits or ahead.in_pits:
                continue
            if (c.gap_ahead or 99.0) >= STRIKE_GAP:
                continue
            if self._battle_held(c, ahead, now) >= LONG_FIGHT * 2:
                out.append(("dig_stuck", self._kw(s, a=c, b=ahead), c))
                break

        # A driver who keeps finding the scenery. Three separate excursions,
        # not two: two is unlucky, three is a pattern the viewer has noticed
        # as well, and that is the difference between a joke and a sneer.
        worst_id, worst_n = None, 0
        for cid, n in self._off_count.items():
            if n > worst_n:
                worst_id, worst_n = cid, n
        if worst_n >= DIG_WIDE_OFFS:
            car = next((c for c in s.order if c.id == worst_id), None)
            if car is not None and not car.in_pits:
                out.append(("dig_wide", self._kw(s, drv=car), car))

        # THE TWO OF THEM. Always available, never about anybody driving, and
        # the reason this feature is safe at all.
        out.append(("booth_joke", self._kw(s, drv=s.leader), None))
        out.append(("booth_dig", self._kw(s), None))
        out.append(("analyst_dig", self._kw(s), None))
        return out

    def _title_at_stake(self):
        """Could this race settle the championship?

        Only ever True with a career whose maths is exact — `title_state`
        returns None or an unknown `rounds_left` for an open season with no
        declared length, and an unknown is not a title decider (LAW 4).
        """
        career = self._active_career()
        if career is None:
            return False
        st = career.title_state()
        if not st or st.get("rounds_left") is None:
            return False
        # The last round always is. Before that, it is a decider only if the
        # lead is small enough to be overturned in one race.
        if st["rounds_left"] <= 1:
            return True
        return False

    @staticmethod
    def _driver_record(car, era, career=None):
        """The knowledge-base record for a car, trying BOTH names it carries.

        A car has two: `name` is what rF2 reported, and `display_name` is what
        the overlay is willing to say out loud. For the AI they are the same.
        FOR THE PLAYER THEY ARE NOT — rF2 reports the profile name, which is
        usually the placeholder "Your Name", and the career's chosen driver
        name lives in `display_name`.

        Preferring `name` therefore meant that racing a career AS Max
        Verstappen produced no facts about Max Verstappen: the booth had his
        whole record and could not connect it to the car the user was
        driving. Both are tried, and either resolving is enough.
        """
        for n in (getattr(car, "display_name", ""), getattr(car, "name", "")):
            if not n:
                continue
            rec = drivers_mod.standing(n, era, career)
            if rec is not None:
                return rec
        return None

    def _active_career(self):
        """The career THIS SESSION belongs to, or None.

        Not the same question as "is a career loaded". A career stays loaded
        in the settings for as long as it exists, so a one-off race for fun
        still has `self.season` pointing at one — and reading a running total
        out of it would mean the booth crediting a Silverstone race the user
        ran for enjoyment to a championship it was never part of.

        `_season_round` is the honest signal: it is set by `_season_arm` only
        when the circuit and class actually match a round of the career, and
        it is None for every race outside it. Outside a career the booth falls
        back to pure history — which is the correct broadcast for a one-off
        anyway: who these drivers were, not how your season is going.
        """
        return (getattr(self, "season", None)
                if getattr(self, "_season_round", None) else None)

    def _driver_facts(self, s, now, force=False):
        """Candidate "who is this" lines. Empty most of the time, by design.

        Returns filler events in the usual (category, slots, subject) shape,
        so they compete with the rest of the colour on staleness rather than
        jumping the queue. `force` skips the family gate for the scripted
        pre-race beat, where introducing the man on pole IS the point and
        there is nothing else competing for the time.
        """
        out = []
        era = getattr(s, "player_era", None) or getattr(s, "era", None)
        if drivers_mod.season_of(era) is None:
            return out          # not a season we know: no lines, ever
        # The family gate. One driver fact per two and a half minutes, whoever
        # it is about and whatever category it belongs to.
        last = max((self._cat_last.get(c, 0.0) for c in DRIVER_CATS))
        if not force and now - last < DRIVER_FAMILY_GAP:
            return out

        me = s.player
        seen = set()
        # CONTINUITY. The record read here is the LIVE one — the history plus
        # whatever this career has already done to it — and not the frozen
        # entry in `drivers.json`.
        #
        # Without that, a Mansell who took his first Grand Prix win in round
        # two is still "still looking for that first win" in round three, and
        # the booth has visibly stopped watching its own championship. Passing
        # the career here is the whole fix: `winless` becomes false the moment
        # he wins, `driver_winner` becomes true in the same instant, and a
        # note that the season has falsified goes quiet.
        #
        # ...but ONLY in a career race. A one-off gets the historical record
        # untouched, because there is no season for it to be part of — see
        # `_active_career`.
        career = self._active_career()
        for c in list(s.order[:DRIVER_FOCUS]) + ([me] if me is not None else []):
            if c is None or c.id in seen:
                continue
            seen.add(c.id)
            drv = self._driver_record(c, era, career)
            if drv is None:
                continue
            said = self._driver_said.setdefault(drv.name, set())
            # ONE ABOUT THE MAN, ONE ABOUT HIS CAR.
            #
            # `eligible` is ranked by how interesting the fact is, and the
            # team lines sit at the bottom of it — correctly, because who a
            # driver is beats what his car is like. But taking only the first
            # eligible category per driver then meant the team layer never
            # surfaced at all, for anybody, ever: there is always a driver
            # fact ahead of it. So the two groups are drawn separately and
            # both are offered, and the ranking still decides which of the
            # two actually airs.
            groups = set()
            for cat in drivers_mod.eligible(drv):
                grp = "team" if cat.startswith("team_") else "driver"
                if grp in groups or cat in said:
                    continue
                slots = drivers_mod.slots_for(drv, cat)
                if not slots:
                    continue
                groups.add(grp)
                # The booth's own slots first, so {trk} and {lap} still work,
                # then the driver's — his name must win, because `_kw` fills
                # {drv} from the CAR and the car's display name may be the
                # user's chosen alias rather than the man in the record book.
                kw = self._kw(s, drv=c)
                kw.update(slots)
                out.append((cat, kw, c))
                if len(groups) == 2:
                    break       # one about the man, one about his car
        return out

    def _driver_line(self, cat, kw, s, now, force=False):
        """Air a driver fact and remember that it was aired.

        LAW 11: the "already said" mark is set here, on the way out of a
        successful `_say`, and not when the line was offered. Offering happens
        several times a minute; airing happens once, and a fact marked as said
        when it was only offered is a fact the viewer never hears.
        """
        if not self._say(cat, kw, s, now, force=force):
            return False
        name = kw.get("drv") or ""
        if name:
            self._driver_said.setdefault(name, set()).add(cat)
        return True

    # -- conversation ----------------------------------------------------------
    def _start_convo(self, s, now):
        """Miles asks Chuck a question. True if the exchange opened.

        This is the other half of crosstalk. `_maybe_crosstalk` lets Chuck
        REACT to a call; this lets the two of them actually talk during dead
        air, which is what a commentary box sounds like when nothing is
        happening — and dead air is most of a long race.
        """
        era = s.player_era or s.era
        kw = self._convo_kw(s)
        avoid = set(self._convo_done)
        # The lore topic answers with a real fact about the real circuit, so
        # it is only offered when there is one. A circuit the booth has never
        # heard of simply never comes up in conversation — which is far
        # better than Chuck being asked about it and inventing something.
        fact = self._circuit_fact(s)
        if fact:
            kw["fact"] = fact
        else:
            avoid.add("lore")
        # A race has to have happened before the booth can discuss how it is
        # going. Non-race sessions are always "ready": a practice session has
        # no arc to be too early in.
        ready = s.kind != "race" or self._enough_race(s)
        name, topic = lines_mod.topic_for(era, self._phase, avoid=avoid,
                                          race_ready=ready)
        if not topic:
            return False
        # Which question, not just which topic — the answer is bound to it.
        q, qi = lines_mod.topic_question(name, kw)
        if not q:
            return False
        # THE QUESTION AND THE ANSWER ARE QUEUED TOGETHER.
        #
        # They used to be separate beats, each waiting for the previous to
        # finish playing before it was even queued — and `tts.speak()` only
        # ENQUEUES: a live edge-tts render takes 2-6 seconds, which did not
        # start until the question had finished. The result was a question,
        # a long silence, and then an answer, which is exactly what two men
        # in different rooms sound like.
        #
        # Queued back to back the renderer has the answer ready before the
        # question stops playing, and they run together the way an exchange
        # in a commentary box actually does.
        a = lines_mod.topic_line(name, "a", kw, qi=qi)
        self.tts.speak(q, cast_mod.PLAY, intensity=1)
        if a:
            self.tts.speak(a, cast_mod.ANALYST, intensity=1)
        self._last_spoke = now
        self._cat_last["interview"] = now
        self._show_caption(q, cast_mod.PLAY, now)
        # Topics do not repeat within a session. Hearing "who's impressed
        # you?" twice in one race exposes the whole mechanism.
        self._convo_done.add(name)
        # Only the ACK is left as a droppable beat: it is the one part of an
        # exchange that can be abandoned without leaving a question hanging.
        self._convo = ({"topic": name, "stage": "ack", "kw": kw, "at": now,
                        "answer": a} if a else None)
        return True

    def _continue_convo(self, s, now):
        """Close the exchange: Miles takes it back. True if something aired.

        The question and the answer are queued together by `_start_convo`, so
        the only beat left here is the acknowledgement — and the caption for
        the answer, which has to appear when the answer is HEARD rather than
        when it was queued.
        """
        c = self._convo
        if c is None:
            return False
        # An exchange that cannot be finished promptly is dropped. A reply
        # that arrives twenty seconds after the question is not a reply.
        if now - c["at"] > CONVO_TIMEOUT:
            self._convo = None
            return False

        # The answer is already playing or about to. Put its caption up on
        # the beat, then wait for the audio to finish before the ack.
        if c.get("answer") and not c.get("captioned"):
            if now - c["at"] >= CONVO_BEAT:
                c["captioned"] = True
                self._show_caption(c["answer"], cast_mod.ANALYST, now)
            return False

        if self.tts.speaking or now - self._last_spoke < CONVO_BEAT:
            return False

        # Miles takes it back about half the time. Always acknowledging turns
        # every exchange into the same three-beat rhythm; never doing it
        # leaves Chuck talking into a void.
        import random
        if random.random() >= CONVO_ACK:
            self._convo = None
            return False
        text = lines_mod.topic_line(c["topic"], "ack", c["kw"])
        self._convo = None
        if not text:
            return False
        self.tts.speak(text, cast_mod.PLAY, intensity=1)
        self._show_caption(text, cast_mod.PLAY, now)
        self._last_spoke = now
        return True

    def _circuit_fact(self, s):
        """One unused fact about this circuit, drawn from the same bag the
        standalone `track_fact` line uses — so a fact told in conversation is
        not repeated as colour ten minutes later."""
        circuit = getattr(s, "circuit", None)
        if circuit is None or not circuit.known:
            return ""
        pool = circuit.facts()
        if not pool:
            return ""
        entry = lines_mod._bag.pick("track_fact|%s" % circuit.slug,
                                    [{"t": f} for f in pool])
        return entry["t"] if entry else ""

    def _convo_kw(self, s):
        """Slots for a whole exchange, fixed at the moment the question is
        asked. Re-deriving them for the answer meant Chuck could be asked
        about the leader and answer about whoever had inherited the lead in
        the meantime."""
        lead = s.leader
        second = s.order[1] if len(s.order) > 1 else None
        return self._kw(s, a=lead, b=second, drv=lead,
                        gap=spoken_gap(second.gap_ahead if second else None))

    def _maybe_crosstalk(self, cat, kw, now, s, answer=None,
                         chance=None):
        """Chuck answers the call Miles has just made — IN THE SAME BREATH.

        This used to be scheduled: the reply was noted, and a later tick
        looked for a gap in which to say it. Two things were wrong with that.
        `tts.speak()` only enqueues and a live render takes 2-6 seconds, so
        the reply's render did not START until a gap had already appeared —
        and the gap it was waiting for was the silence the render created.
        The reply landed several seconds after the moment it was answering,
        which is the difference between a conversation and two men narrating
        past each other.

        Queued immediately, the renderer has Chuck's line ready while Miles is
        still talking, and the answer follows the call the way it would in a
        real booth. The cost is that it can no longer be cancelled — which is
        acceptable, because a verdict on a pass that just happened is still a
        true thing to say a few seconds later.
        """
        import random
        # A reaction armed by a detector for this specific call.
        armed = self._reaction_for
        if armed and armed[0] == cat and not answer:
            answer, chance = armed[1], armed[2]
        if armed and armed[0] == cat:
            self._reaction_for = None
        if answer:
            # An explicitly requested reaction. Used where the DECISION to
            # react is a judgement the caller has already made — a benchmark
            # lap in qualifying only earns one once the session has matured
            # (see `_quali_lap_notable`), so it cannot live in the table.
            answer_cat, chance = answer, (chance if chance is not None else 1.0)
        else:
            spec = CROSSTALK_CATS.get(cat)
            if not spec:
                return
            answer_cat, chance = spec
        if random.random() > chance:
            return
        if not cast_mod.can_say(cast_mod.ANALYST, answer_cat):
            return
        era = s.player_era or s.era
        text, intensity, _ = lines_mod.pick(answer_cat, era, kw)
        if not text:
            return
        self.tts.speak(text, cast_mod.ANALYST, intensity=intensity)
        self._cat_last[answer_cat] = now
        # The caption follows a beat later, when the line is actually heard.
        self._pending_caption = (text, cast_mod.ANALYST,
                                 now + CROSSTALK_WINDOW)

    def _show_caption(self, text, who, now):
        # Every path that puts something to air comes through here — live
        # lines, stings and conversation beats alike — which makes it the one
        # honest place to record who last had the microphone.
        self._last_voice = who
        self._caption = (text, who)
        # Roughly reading speed, floored so short calls stay up long enough
        # to be read at racing speed.
        self._caption_until = now + max(2.5, min(9.0, len(text) / 14.0))

    # -- detection -------------------------------------------------------------
    def _detect(self, s, now):
        out = []

        # A PASS THAT LOST ITS TICK GETS A FEW MORE. Detection is
        # edge-triggered, so before this existed a move made while the booth
        # was mid-sentence was gone for good - which is exactly what happened
        # to the user's pass for a podium place. It is re-offered, not
        # re-detected: same call, same words, ranked against whatever else is
        # happening, and dropped when it stops being news.
        if self._pending_pass:
            self._pending_pass = [p for p in self._pending_pass
                                  if p[3] > now]
            out.extend((cat, kw, car) for cat, kw, car, _x in
                       self._pending_pass)

        # NOTE: the start and the win are NOT handled here. They are broadcast
        # BOOKENDS and belong to `_bookends`, which fires a pre-rendered sting
        # so the call lands on the moment rather than after a render. Having
        # both paths own them meant the same event could be announced twice.
        if (s.max_laps and s.laps_left == 1 and not self._said_lastlap
                and s.green):
            self._said_lastlap = True
            # Sting first: "last lap" is a moment, and a live render puts it
            # several corners late. The named call follows behind it.
            self._sting(now, "lastlap")
            out.append(("lastlap", self._kw(s), None))

        # --- per-car ----------------------------------------------------------
        # Everything below is a DELTA and needs last tick to compare against.
        if not self._prev:
            return out
        confirmed = self.tracker.confirmed_places(s)
        # Settled once per tick and read by `_snapshot`, so the confirmed place
        # this tick becomes the confirmed place last tick — which is the only
        # pair of numbers an overtake may be measured between.
        self._conf_now = confirmed
        for c in s.order:
            p = self._prev.get(c.id)
            if p is None:
                continue

            # A PASS IS A CHANGE IN THE CONFIRMED PLACE, MEASURED AGAINST THE
            # CONFIRMED PLACE LAST TICK. THIS LINE SILENCED EVERY OVERTAKE CALL
            # IN THE PRODUCT.
            #
            # It used to read `p.place - newp`: last tick's RAW place against
            # this tick's CONFIRMED place. `PLACE_CONFIRM_S` is 0.35s and a tick
            # is 50ms, so the confirmed place lags the raw one by about seven
            # ticks — and the two therefore differ by exactly one only if a pass
            # happens to be seven ticks old, which is a thing the raw snapshot
            # has long since forgotten. Every real pass produced `gained == 0`
            # on the tick it happened, `-1` on the next, and `0` for ever
            # after. The user drove from thirteenth to the LEAD in a seven-lap
            # race and heard nothing, and the log shows no pass sting of any
            # kind in a whole session.
            #
            # The confirmation itself was right and stays: a flicker at a timing
            # line must not become a phantom pass (LAW 12). What was wrong was
            # comparing a filtered signal against an unfiltered one — and it
            # cost nothing at the time it was written, because a de-bounced
            # value is obviously the correct thing to read. Both sides have to
            # come from the same filter, or the edge lands between them.
            newp = confirmed.get(c.id, c.place)
            gained = p.conf - newp
            # `_interesting` gates this too. Without it the booth narrates a
            # swap for P19 with the same weight as a move for the lead, which
            # is the single fastest way to make it feel like noise.
            if (gained > 0 and not c.in_pits and not p.in_pits and s.green
                    and self._interesting(c)):
                # The car passed is the one that PREVIOUSLY held the place
                # the passer now occupies — not the place the passer came
                # from. Looking up the old place found nobody, so every
                # overtake was silently discarded for want of a victim.
                victim = self._who_was(s, newp)
                if gained == 1 and victim is not None:
                    cat = "leadchange" if newp == 1 else "overtake"
                    if newp == 1:
                        # Counted at DETECTION, not when a line airs: the
                        # call can lose the tick to something bigger, and
                        # "the lead has changed hands three times" must be
                        # true whether or not the booth got to say so.
                        self._lead_changes += 1
                    # A pass that took a while to arrive is a different story
                    # from one that just happened. `_battle_since` has been
                    # timing this exact fight all along and nothing was
                    # consuming it — so a move that ended two laps of pressure
                    # was called in the same words as an easy run down the
                    # inside.
                    # Only counts if the fight was against THIS victim — see
                    # `_update_battles`.
                    held = self._battle_held(c, victim, now)
                    if newp != 1 and held >= LONG_FIGHT:
                        cat = "overtake_long"
                    # A place taken straight back is a different, better story
                    # again: it says these two are RACING. Reported as its own
                    # category so it never reads as a repeat of the call
                    # thirty seconds ago.
                    lp = self._last_pass
                    if (lp and lp[0] == victim.id and lp[1] == c.id
                            and now - lp[3] < RETAKE_WINDOW):
                        cat = "retake"
                    self._last_pass = (c.id, victim.id, newp, now)
                    # The fight is over: whoever wins it, the clock restarts.
                    self._battle_since.pop(c.id, None)
                    self._battle_since.pop(victim.id, None)
                    # ...and neither of them is "escaping" from a fight that
                    # has just been settled by a pass.
                    self._battle_clear.pop(c.id, None)
                    self._battle_clear.pop(victim.id, None)
                    # TWO MEN TRADING A PLACE ALL AFTERNOON is a better story
                    # than either pass, so the swaps are counted per PAIR.
                    # Counted at detection for the same reason the lead
                    # changes are: it has to be true whether or not the booth
                    # got to say so.
                    pair = frozenset((c.id, victim.id))
                    tr = [t for t in self._trades.get(pair, ())
                          if now - t < TRADE_WINDOW]
                    tr.append(now)
                    self._trades[pair] = tr
                    kw = self._kw(s, a=c, b=victim, pos=spoken_place(newp),
                                  dur=self._fight_text(held, s),
                                  n=len(tr))
                    if len(tr) >= TRADE_MIN and newp != 1:
                        # It is no longer a pass, it is what these two have
                        # been doing. The lead is exempt: a lead changing
                        # hands repeatedly is already the biggest call the
                        # booth has, and downgrading it would be absurd.
                        cat = "battle_traded"
                    # HIS OWN TEAM-MATE IS NOT AN ORDINARY VICTIM.
                    #
                    # Same car, same team, same information — so it is the
                    # one overtake on the grid that cannot be explained away
                    # by machinery, and the only one a garage argues about
                    # afterwards. Checked here rather than in the pools
                    # because it is a fact about WHO, and `_team_mate` is the
                    # only thing that knows.
                    # THE LEAD IS EXEMPT, same as a traded place is. Taking
                    # the LEAD of the race off your team-mate is a lead
                    # change first and a team-mate story second — downgrading
                    # it would make the biggest call in the race smaller
                    # because of who happened to be in the way.
                    mate = self._team_mate(s) if newp != 1 else None
                    if mate is not None:
                        me_ = getattr(s, "player", None)
                        if me_ is not None:
                            if c.id == me_.id and victim.id == mate.id:
                                cat = "mate_pass"
                            elif c.id == mate.id and victim.id == me_.id:
                                cat = "mate_passed"
                                # ONE SLOT NAME, ONE MEANING (LAW 17). Every
                                # line in this family is written with {a} as
                                # the PLAYER and {b} as the man in the other
                                # side of the garage — but `kw` was built as
                                # (passer, victim), which reverses them when
                                # it is the team-mate doing the passing. The
                                # first draft aired "Verstappen past Russell"
                                # about Russell passing Verstappen: every
                                # word true, and the sentence backwards.
                                kw = self._kw(s, a=me_, b=mate,
                                              pos=spoken_place(newp),
                                              dur=self._fight_text(held, s),
                                              n=len(tr))
                    # THE MOMENT, WITH AUDIO ON IT. Spoken here rather than
                    # returned as an event, so a busy tick cannot bin it.
                    if (self._pass_matters(s, c, victim, newp)
                            and self._overtake_report(s, now, c, victim,
                                                      cat, kw)):
                        continue
                    kw["_pass_key"] = (c.id, victim.id, newp)
                    out.append((cat, kw, c))
                    # ...and if it was not big enough for a sting, it still
                    # gets a few seconds to find a gap rather than being
                    # dropped on the tick it happened.
                    self._pending_pass.append((cat, kw, c, now + PASS_RETRY))
                elif 1 < gained <= 3:
                    # A gain of more than three places inside one 50ms tick is
                    # not racing, it is the field being re-ordered (a restart,
                    # a car entering the pits, scoring settling after the
                    # green). The live test produced "takes 6 places in one
                    # move!" repeatedly from exactly that.
                    out.append(("overtake_multi",
                                self._kw(s, a=c, n=gained,
                                         pos=spoken_place(newp)), c))

            # retirement
            if c.finish_status in (2, 3) and p.finished not in (2, 3):
                if self._interesting(c):
                    self._sting(now, "retire")
                out.append(("retire", self._kw(s, drv=c), c))

            # pit entry
            if c.in_pits and not p.in_pits and s.green:
                out.append(("pit", self._kw(s, drv=c,
                                            pos=spoken_place(c.place)), c))

            # spin / excursion
            out.extend(self._excursion_events(c, p, s, now))

            # fastest lap of the session
            if (c.best_lap and (self._best_lap_seen is None
                                or c.best_lap < self._best_lap_seen - 1e-4)):
                self._best_lap_seen = c.best_lap
                if c.laps > 1 and s.green:
                    out.append(("fastlap",
                                self._kw(s, drv=c, t=spoken_lap(c.best_lap)), c))

        # --- flags -------------------------------------------------------------
        # EDGE-TRIGGERED, not level-triggered. A yellow is an EVENT ("we have
        # yellow flags"), not a status to be re-read every twenty seconds.
        #
        # The level-triggered version produced 19 of 19 booth lines as yellow
        # flags across a whole race: rF2 kept a sector flag raised, the
        # condition stayed true, and the category cooldown simply metered out
        # a fresh phrasing of the same fact forever. Because yellow outranks
        # almost everything, it also starved every other kind of commentary —
        # the analyst never spoke once.
        #
        # So the flag state is remembered, and only TRANSITIONS are called.
        # THE SAFETY CAR IS ITS OWN SEQUENCE, and a full course yellow is not a
        # waved yellow. See `_safety_call`.
        sc = self._safety_call(s, now)
        if sc:
            out.extend(sc)

        yellow_now = bool(any(s.yellow_sectors)) and not s.full_course_yellow
        was_yellow = getattr(self, "_yellow_on", False)
        if yellow_now != was_yellow:
            self._yellow_on = yellow_now
            if yellow_now:
                out.append(("yellow", self._kw(s), None))
            elif s.green and not getattr(self, "_sc_state", 0):
                # Clearing the yellow is news too, and it is the cue the
                # driver actually needs — but the safety car has its OWN green
                # call, and both of them firing is the booth saying the same
                # thing twice in one breath.
                out.append(("green_again", self._kw(s), None))

        out.extend(self._title_watch(s, now))
        return out

    # rF2's OWN SAFETY CAR STATE MACHINE (`mYellowFlagState`), every value of
    # which the user's log shows ticking over while the booth said nothing:
    #
    #   1 pending      the yellow is called
    #   2 pit closed   nobody may stop
    #   3 pit open, lead lap only
    #   4 pit open     the cheap stop, and the strategic beat of the period
    #   5 last lap     the safety car comes in at the end of this lap
    #   6 resume       green
    #
    # Named here rather than inline because a bare `== 5` in a booth method is
    # unreadable, and because the next person to touch this needs the table.
    SC_PENDING, SC_PIT_SHUT, SC_PIT_LEAD, SC_PIT_OPEN = 1, 2, 3, 4
    SC_LAST_LAP, SC_RESUME = 5, 6

    def _safety_call(self, s, now):
        """The safety car, called the way a broadcast calls it.

        Reported by the user after driving it: *"a safety car deployed towards
        the end of the race and there was 0 commentary involved"*, and *"when
        the safety car ended it was on the last lap of the race and that sort of
        drama needs to be commentated on"*. He is right twice, and the log is
        damning — six minutes and twenty-two seconds of full course yellow, one
        line about "waved yellows" at the start of it, and silence through a
        restart that landed on the final lap.

        THE DATA WAS ALL THERE. `mYellowFlagState` walked 1 -> 2 -> 3 -> 4 -> 5
        -> 6 in his log, which is a complete broadcast in itself: deployed, pits
        shut, pits open, safety car in this lap, green. The overlay read the
        single boolean `full_course_yellow` and threw the rest away.

        EDGE-TRIGGERED ON THE STATE (LAW 1), so a six-minute period produces
        five or six calls rather than one every twenty seconds — the failure the
        old level-triggered yellow already taught this file once.

        NOTHING HERE CLAIMS TO KNOW WHY. The overlay knows the field has been
        neutralised; it does not know whether a car is in the wall. The incident
        detector owns causes and has its own sting; this owns the consequence.
        """
        if s.kind != "race":
            return []
        state = int(getattr(s, "yellow", 0) or 0)
        fcy = bool(getattr(s, "full_course_yellow", False))
        was = getattr(self, "_sc_state", 0)
        if not fcy and not was:
            return []
        out = []
        kw = self._kw(s)
        if fcy and not was:
            # DEPLOYED — and it speaks in TWO VOICES in one breath, the shape
            # `_incident_report` proved: the call and then what it costs. A
            # sequence that leaves the analyst's reply to the next quiet tick
            # is a sequence that loses it to the next event.
            out.append(("sc_out", kw, None))
            out.append(("sc_out_why", kw, None))
        elif fcy and state != was:
            if state == self.SC_PIT_SHUT:
                out.append(("sc_pits_shut", kw, None))
            elif state == self.SC_PIT_OPEN:
                out.append(("sc_pits_open", kw, None))
            elif state == self.SC_LAST_LAP:
                out.append(("sc_ending", kw, None))
                out.append(("sc_ending_why", kw, None))
        if was and (not fcy or state == self.SC_RESUME):
            # GREEN. The restart is the whole point of the period, and a
            # restart that lands on the last lap is a different event from a
            # restart with fifteen laps to run — one lap, a bunched field and
            # no time to plan anything. That is what the user got, and it is
            # the biggest call in this file.
            last = bool(s.max_laps and (s.laps_left or 0) <= 1)
            if last:
                out.append(("sc_green_last", kw, None))
                out.append(("sc_green_last_why", kw, None))
            else:
                out.append(("sc_green", kw, None))
            self._sc_state = 0
            self._sc_since = None
            return out
        if fcy:
            self._sc_state = max(1, state)
            if getattr(self, "_sc_since", None) is None:
                self._sc_since = now
        return out

    def _safety_filler(self, s, now):
        """Colour while the field circulates. The reason the six minutes were
        silent, and it is not a content problem.

        `_filler` opens with `if not s.green: return out` — so under a full
        course yellow the ENTIRE colour tail is switched off, and the booth has
        nothing left to say at exactly the moment a real broadcast talks most.
        The gate is right for what it was written for (nobody is racing, so
        battles and passes are nonsense) and wrong about everything else.

        WHAT IS OFFERED HERE IS ONLY WHAT IS TRUE OF A NEUTRALISED FIELD: that
        it is bunched, that nothing will change until the green, and the wait
        itself. Standings and the career/circuit colour come through the normal
        path once this returns, ranked on staleness like everything else.
        """
        if not getattr(self, "_sc_state", 0):
            return []
        out = [("sc_field", self._kw(s), None)]
        since = getattr(self, "_sc_since", None)
        if since is not None and (now - since) > SC_LONG:
            # A LONG ONE IS ITS OWN OBSERVATION. Six minutes behind a safety car
            # is a thing the viewer is living through, and a booth that never
            # acknowledges it is not in the room.
            out.append(("sc_wait", self._kw(s), None))
        return out

    def _title_watch(self, s, now):
        """He has crossed the line the championship is decided on.

        Asked for in the user's own words: *"and now he is up to p6, the
        championship leader only needs to get p5 to win it all, this is
        frantic!!"* — the thing that turns the last race of a season into the
        last race of a season.

        EDGE-TRIGGERED (LAW 1), and this is not a small point. The condition
        "he is inside the position he needs" is TRUE for most of a good
        afternoon, and a level-triggered version of this would say it every
        twenty seconds for half an hour. The booth remembers which side of the
        line he was on and calls only the crossings.

        BOTH DIRECTIONS, because losing it is the same story as gaining it.
        Dropping out of the position that wins a championship, with six laps
        left, is the most dramatic thing that can happen in a season.

        THE ARITHMETIC IS NEVER DONE HERE. `title_scenarios()` owns it, has a
        brute-force test against every permutation, and returns None the
        moment it cannot be exact — so this method cannot invent a claim even
        if it wants to.
        """
        career = getattr(self, "season", None)
        rnd = getattr(self, "_season_round", None)
        if career is None or not rnd or s.kind != "race" or not s.green:
            return []
        me = getattr(s, "player", None)
        if me is None or not self._places_sane_now(s):
            return []
        sc = career.title_scenarios(field=len(s.order) or None)
        # Only on the afternoon it can actually be settled. With two rounds
        # left "he needs fifth" is a fact about a race that is not this one.
        if not sc or sc.get("decided") or sc.get("left") != 1:
            self._title_side = None
            return []
        need = sc.get("secure")
        if not need:
            self._title_side = None
            return []
        inside = me.place <= need
        was = getattr(self, "_title_side", None)
        self._title_side = inside
        if was is None or was == inside:
            return []
        kw = self._kw(s, drv=me, pos=spoken_place(me.place),
                      need=spoken_place(need),
                      rival=sc.get("rival") or "")
        return [("title_live" if inside else "title_lost", kw, me)]

    def _places_sane_now(self, s):
        """A 1..N order with no duplicates, this tick.

        LAW 12 in miniature. rF2 publishes scrambled-but-valid orders around
        restarts, and a phantom place here would announce a championship
        won or lost on a tick nobody drove.
        """
        places = [c.place for c in s.order if not c.in_pits]
        return bool(places) and 0 not in places and 255 not in places

    # -- qualifying and practice -----------------------------------------------
    #
    # A qualifying session has no overtakes, no gaps that mean anything, and
    # no story of position — it has a TIMESHEET, and the drama is entirely in
    # who is on top of it and how long is left. So it gets its own detection
    # and its own filler rather than a race's with the volume turned down.
    #
    # rF2 reports `mCountLapFlag` but this build never populates the per-car
    # `last_lap_valid`, so there is deliberately no "lap deleted" call: a
    # phantom deletion would be the single most damaging thing the booth
    # could invent, because the viewer can see the timing screen disagree.

    @staticmethod
    def _sheet(s):
        """The timesheet: everyone with a time, fastest first.

        Sorted on the LAP, not on `mPlace`. In qualifying the two normally
        agree, but place is the field that goes to 255 in the garage and
        scrambles around session changes, and a top-three readout built from
        a scrambled order is a lie the viewer can see on their own screen.
        """
        return sorted((c for c in s.order if c.best_lap),
                      key=lambda c: c.best_lap)

    @staticmethod
    def _margin(g):
        """A qualifying margin, spoken the way a commentator says one.

        NOT `_gap`, which is the radio's phrasing and bottoms out at "right
        on your tail" — true of a car behind you, meaningless about a lap
        time on a sheet.
        """
        if g is None:
            return ""
        g = abs(g)
        if g >= 1.0:
            # "1.0 seconds behind him" is not English. Everything else reads
            # correctly to one decimal.
            return "a second" if round(g, 1) == 1.0 else "%.1f seconds" % g
        # HALF UP, explicitly. Python's round() is banker's rounding, which
        # sends 0.25 to "2 tenths" and 0.35 to "4 tenths" — inconsistent in a
        # way a viewer reading the timing screen would notice.
        t = int(g * 100 + 0.5)
        if t >= 10:
            tenths = int(g * 10 + 0.5)
            # 0.96 rounds to ten tenths, and "10 tenths off" is not something
            # anybody says. Promote it to the seconds form instead.
            if tenths >= 10:
                return "a second"
            return "a tenth" if tenths == 1 else "%d tenths" % tenths
        if t <= 0:
            return "nothing at all"
        return "a hundredth" if t == 1 else "%d hundredths" % t

    def _quali_detect(self, s, now):
        out = []
        sheet = self._sheet(s)
        # SATURDAY IS THE CLEANEST TEAM-MATE COMPARISON THERE IS. Same car,
        # same fuel, one lap each, and no strategy to hide behind — which is
        # why it is the number a Formula One paddock quotes first.
        #
        # THE ORDER COMES FROM `_sheet`, NOT FROM `place`: in a timed session
        # rF2's position field is as often the running order on the road as
        # the classification, which is the trap the pole call had to be fixed
        # for (see `qualitest.py` section 13).
        #
        # This pool shipped with a priority, a cooldown, a crosstalk entry and
        # NO EMITTER — written in the same session that cited LAW 21 about
        # four other pools. `lines.py` reported it healthy the whole time,
        # because the lines are valid; they were simply unreachable.
        mate = self._team_mate(s)
        me_q = getattr(s, "player", None)
        if (mate is not None and me_q is not None and len(sheet) > 1
                and now - self._mate_last >= MATE_FAMILY_GAP):
            ids = [c.id for c in sheet]
            if me_q.id in ids and mate.id in ids:
                mine = ids.index(me_q.id)
                theirs = ids.index(mate.id)
                gap = abs((me_q.best_lap or 0.0) - (mate.best_lap or 0.0))
                cat = ("mate_quali_up" if mine < theirs
                       else "mate_quali_down")
                out.append((cat, self._kw(s, a=me_q, b=mate, cat=cat,
                                          gap=spoken_gap(gap),
                                          pos=spoken_place(mine + 1)), me_q))
        set_count = len(sheet)
        best_c = sheet[0] if sheet else None
        best_t = best_c.best_lap if best_c is not None else None
        runner_up = sheet[1] if len(sheet) > 1 else None

        if best_c is not None and (self._q_best is None
                                   or best_t < self._q_best - 1e-4):
            prev_best, prev_pole = self._q_best, self._q_pole
            self._q_best, self._q_pole = best_t, best_c.id
            # A new benchmark by the driver who already held it is a
            # personal improvement; by anybody else it is a change at the
            # top, which is the moment of the session.
            gain = (prev_best - best_t) if prev_best else None
            kw = self._kw(s, drv=best_c, t=spoken_lap(best_t),
                          gap=(self._margin(gain) if gain else ""),
                          pos=spoken_place(1))
            cat = ("quali_pole" if prev_pole != best_c.id
                   else "quali_fastlap")
            out.append((cat, kw, best_c))
            # WAS THAT LAP WORTH TALKING ABOUT?
            #
            # Not every provisional pole is. The first driver to set a time
            # takes the top of the sheet by default, and gushing about it is
            # nonsense — he has beaten nobody, and somebody will beat him in
            # ten minutes. A lap is worth a reaction when the session has
            # matured enough for the benchmark to mean something AND the lap
            # actually took real time out of an established one.
            # ARMED here, fired after the call itself has been spoken.
            # Reacting from inside detection queued Chuck's verdict BEFORE
            # Miles had made the call he was verdicting, which is worse than
            # not reacting at all.
            if self._quali_lap_notable(s, set_count, gain):
                self._reaction_for = (cat, "quali_lap_praise",
                                      QUALI_PRAISE_CHANCE)

            # WHERE THE LAP CAME FROM.
            #
            # Chuck already says "watch the middle sector on that one", which
            # was pure decoration — nothing checked. rF2 does publish it:
            # `mBestLapSector1/2` are the sectors OF THE BEST LAP, so the
            # three add up to the lap and comparing them against the benchmark
            # they beat is honest. A theoretical best assembled from three
            # different laps would not be; that lap was never driven.
            sec = self._sector_story(best_c)
            if sec is not None and self._q_bench_secs:
                out.append(sec)
            self._q_bench_secs = self._sectors_of(best_c)

            # HOW GOOD WAS IT? A benchmark is only meaningful against the man
            # it beat, so the margin comes from the runner-up's ACTUAL lap
            # rather than from `gain` — which is the improvement on the old
            # benchmark and says nothing about the size of the advantage.
            # Only offered once there is somebody to be ahead of; the first
            # driver to set a time leads by nothing (LAW 5, and the exact
            # mistake `quali_pole` already carries a warning about).
            if runner_up is not None and prev_pole != best_c.id:
                edge = runner_up.best_lap - best_t
                if edge >= QUALI_BIG_MARGIN:
                    out.append(("quali_margin_big",
                                self._kw(s, drv=best_c, b=runner_up,
                                         gap=self._margin(edge),
                                         t=spoken_lap(best_t)), best_c))
                elif edge <= QUALI_SLIM_MARGIN:
                    out.append(("quali_margin_slim",
                                self._kw(s, drv=best_c, b=runner_up,
                                         gap=self._margin(edge),
                                         t=spoken_lap(best_t)), best_c))

            # A FIGHT FOR POLE. One change at the top is a driver going
            # fastest; several between the same two men is a duel, and it is
            # the story of the session. Tracked as a rolling window so a
            # scrap in the first five minutes does not still count as a duel
            # half an hour later.
            self._q_pole_hist = [(i, t) for i, t in self._q_pole_hist
                                 if now - t < QUALI_DUEL_WINDOW]
            self._q_pole_hist.append((best_c.id, now))
            ids = [i for i, _t in self._q_pole_hist]
            if len(ids) >= QUALI_DUEL_SWAPS and len(set(ids)) == 2:
                other_id = next(i for i in ids if i != best_c.id)
                other = s.cars.get(other_id) if hasattr(s, "cars") else None
                other = other or next((c for c in s.order
                                       if c.id == other_id), None)
                if other is not None and now - self._q_duel_at > QUALI_DUEL_CD:
                    self._q_duel_at = now
                    out.append(("quali_duel",
                                self._kw(s, a=best_c, b=other, drv=best_c,
                                         n=len(ids)), best_c))

        # Anyone else finding time and climbing the sheet.
        for c in s.order:
            if not c.best_lap:
                continue
            prev = self._q_bests.get(c.id)
            self._q_bests[c.id] = c.best_lap
            if (prev and c.best_lap < prev - 1e-4 and c.id != self._q_pole
                    and (c.is_player or c.place <= 6)):
                out.append(("quali_improve",
                            self._kw(s, drv=c, pos=spoken_place(c.place),
                                     t=spoken_lap(c.best_lap)), c))

        # The run to the flag. Once only, and only when there is a clock to
        # run out — an open practice session never has a "last chance".
        rem = getattr(s, "time_left", None)
        if (rem is not None and 0 < rem < QUALI_FINAL and not self._q_final
                and set_count):
            self._q_final = True
            out.append(("quali_final", self._kw(s), None))
        # AN OFF IS AN OFF IN QUALIFYING TOO.
        #
        # This was the whole of the user's report: he ran wide on a hot lap in
        # a qualifying session and got nothing — no sting, no call, and no
        # engineer, because `player_off` is published by the excursion code
        # and the excursion code only ever ran inside `_detect`, which
        # qualifying does not use.
        #
        # The calls themselves need no qualifying variant: `ranwide` and the
        # incident pools are written about the MOMENT — "runs wide there and
        # bleeds a little time" — and never about places lost, so they are as
        # true on a hot lap as in a race. What qualifying adds is the lap
        # (below); what it must not add is a second, contradictory grading.
        if self._prev:
            for c in s.order:
                p = self._prev.get(c.id)
                if p is not None:
                    out.extend(self._excursion_events(c, p, s, now))

        # THE LAP THAT NO LONGER COUNTS.
        out.extend(self._lap_deleted(s, now))

        self._q_set = set_count
        self._quali_bank(s)
        self._bank_quali_story(s)
        return out

    def _lap_deleted(self, s, now):
        """rF2 has just chalked a lap off. Say so.

        THIS WAS DELIBERATELY NOT BUILT, AND THE REASON HAS EXPIRED. The
        handover records `quali_deleted` as refused because
        `Car.last_lap_valid` is declared in `rf2_session` and never assigned,
        so there was no honest source and "a phantom deletion the timing
        screen contradicts costs more than the line is worth". That was
        right. It is no longer the situation: the extended buffer's
        `mStatusMessage` is the SIM'S OWN on-screen warning, which is where a
        deletion is announced to the driver, and it is now read (see
        `_track_limits_ground_truth`).

        So this stays gated on the game saying it, never on inference. No
        message, no line — a lap the timing screen still shows as standing is
        exactly the wrongness the refusal was protecting against.

        Kept SEPARATE from the off itself on purpose. They are two different
        pieces of news and only one of them is guaranteed: you can run wide
        without losing a lap, and on some circuits and rulesets you can lose
        one without a visible off. Detecting them together would make each
        depend on the other being noticed.
        """
        out = []
        if s.kind not in ("quali", "practice", "test", "warmup"):
            return out
        me = s.player
        if me is None:
            return out

        # PRIMARY SOURCE: THE SIM'S OWN COUNT FLAG, which is a number.
        #
        # The first live run settled the question the status message could
        # not: 40 minutes, a full qualifying session, and the log contains
        # ZERO status messages. Either this plugin build never writes
        # `mStatusMessage` or it writes it for events the user did not
        # trigger — and a feature that depends on pattern-matching on-screen
        # English was always the weaker half of the design anyway.
        #
        # `mCountLapFlag` is on the vehicle struct that is already read every
        # tick: 0 = do not count the lap, 1 = count the lap but not its time,
        # 2 = count both. Below 2 means the time is not going on the sheet,
        # which is exactly what a driver means by "they took my lap away".
        #
        # Edge-triggered on the transition (LAW 1), and only from a lap that
        # WAS counting — the flag sits low in the pits and on an out-lap, and
        # announcing those as deletions would be worse than saying nothing.
        flag = getattr(me, "count_lap", None)
        was = self._q_count_flag
        self._q_count_flag = flag
        if (flag is not None and was is not None and was >= 2 and flag < 2
                and s.green and not me.in_pits):
            return self._deleted_call(s, now, me)

        # SECONDARY: the on-screen warning, kept because it is the only source
        # that exists if a future plugin build stops publishing the flag, and
        # because it costs nothing to leave in.
        if not getattr(s, "status_message_new", False):
            return out
        msg = (getattr(s, "status_message", "") or "").lower()
        # Both halves must be present. "INVALID" alone appears in messages
        # that have nothing to do with a lap, and "LAP" alone is in most of
        # them — a driver told his lap was deleted when it was not is the
        # failure this whole feature was held back over.
        if not any(w in msg for w in DELETED_WORDS):
            return out
        if "lap" not in msg:
            return out
        return self._deleted_call(s, now, me)

    def _deleted_call(self, s, now, me):
        """The call itself, once something honest has said a lap is gone."""
        if now - self._q_deleted_at < QUALI_DELETED_GAP:
            return []
        self._q_deleted_at = now
        # Published for the engineer exactly as an off is. He is the one who
        # tells a driver his lap has gone; the booth remarks on it.
        self.player_lap_deleted = now
        return [("quali_deleted", self._kw(s, drv=me), me)]

    @staticmethod
    def _sectors_of(c):
        """The three sectors of this driver's best lap, or None.

        All three or nothing: a partial split cannot be compared, and two
        sectors out of three is exactly the shape of an answer that sounds
        authoritative and is wrong.
        """
        s1 = getattr(c, "best_s1", None)
        s2 = getattr(c, "best_s2", None)
        s3 = getattr(c, "best_s3", None)
        if not (s1 and s2 and s3):
            return None
        return (s1, s2, s3)

    def _sector_story(self, c):
        """Which sector the new benchmark was won in, if one stands out."""
        now_s = self._sectors_of(c)
        was = self._q_bench_secs
        if now_s is None or was is None:
            return None
        d = [was[i] - now_s[i] for i in range(3)]      # + means time GAINED
        best_i = max(range(3), key=lambda i: d[i])
        gained = d[best_i]
        if gained <= 0:
            return None                                 # won it nowhere
        share = gained / max(1e-6, sum(x for x in d if x > 0))
        kw = {"sec": ("the first sector", "the middle sector",
                      "the final sector")[best_i],
              "gap": self._margin(gained),
              "drv": c.display_name}
        if share >= QUALI_SECTOR_SHARE:
            # One sector carried the lap.
            return ("quali_lap_sector", kw, c)
        # Time found everywhere is a different, and better, story.
        return ("quali_lap_allround", kw, c)

    def _quali_tail(self, s, run, total):
        """The BOTTOM of the timesheet.

        A qualifying broadcast is not only about pole. Somebody is
        seventeenth and a second and a half off, and saying so — without
        sneering — is half of what makes a session feel covered.

        Gated hard, because it is the easiest place in the whole booth to say
        something untrue:

          * a real field, not four cars in a test session
          * MOST of the field has actually run, so the tail is a tail and not
            simply the men who have not been out yet
          * the driver is genuinely off the pace by a measurable amount

        The percentage is real (his lap against pole), never invented, and
        the lines never claim to know WHY — "the pace isn't in the car" is
        Chuck's opinion and is written as one, not as a fact.
        """
        out = []
        if total < QUALI_TAIL_MIN_FIELD or len(run) < total * QUALI_TAIL_SHARE:
            return out
        pole = run[0].best_lap
        last = run[-1]
        if not pole or not last.best_lap or last is run[0]:
            return out

        off = last.best_lap - pole
        pct = (last.best_lap / pole - 1.0) * 100.0
        if off >= QUALI_OFFPACE_S:
            out.append(("quali_tail",
                        self._kw(s, drv=last, pos=spoken_place(len(run)),
                                 gap=self._margin(off),
                                 pct="%.1f" % (100.0 + pct)), last))

        # A NAMED driver a long way off, from the back half of the sheet.
        # Picked as the worst offender rather than at random, so the call is
        # about the man it is most true of.
        if len(run) >= QUALI_TAIL_MIN_FIELD:
            back = run[len(run) // 2:]
            worst = max(back, key=lambda c: c.best_lap - pole, default=None)
            if worst is not None and worst is not last:
                off_w = worst.best_lap - pole
                if off_w >= QUALI_OFFPACE_S:
                    idx = run.index(worst) + 1
                    out.append(("quali_offpace",
                                self._kw(s, drv=worst, pos=spoken_place(idx),
                                         gap=self._margin(off_w)), worst))

        # The player, if he is the one down there. Kept separate so the booth
        # can be honest about him without using a line written to be unkind
        # about somebody else.
        me = s.player
        if me is not None and me.best_lap and me is not run[0]:
            idx = run.index(me) + 1 if me in run else 0
            off_me = me.best_lap - pole
            if idx >= QUALI_TAIL_FROM and off_me >= QUALI_OFFPACE_S:
                out.append(("quali_player_offpace",
                            self._kw(s, drv=me, pos=spoken_place(idx),
                                     gap=self._margin(off_me)), me))
        return out

    def _quali_bank(self, s):
        """Remember where the player qualified, once the session is over.

        The engineer's "last time out you put it fourth" is a fact from a
        session that has ENDED — there is nothing in shared memory to read it
        from once the race loads, so it has to be banked while it is still
        visible. Recorded against the round the career is on, so it survives
        into the race weekend it belongs to.
        """
        career = getattr(self, "season", None)
        me = s.player
        if (career is None or me is None or not career.uses_quali
                or s.kind != "quali" or self._q_banked):
            return
        # Only once the session is genuinely finished: a provisional position
        # mid-session is not where he qualified.
        if not s.finished:
            return
        run = [c for c in s.order if c.best_lap]
        if not run or not me.best_lap:
            return
        run.sort(key=lambda c: c.best_lap)
        pos = next((i + 1 for i, c in enumerate(run) if c.id == me.id), 0)
        if not pos:
            return
        self._q_banked = True
        circuit = getattr(s, "circuit", None)
        rnd = career.next_round() or {}
        # THE OTHER CAR'S SLOT ON THE SAME SHEET. Saturday is where a
        # team-mate comparison is cleanest — same car, same fuel, one lap
        # each — and the ORDER COMES FROM `run`, sorted on lap time, not from
        # `place`: in a timed session rF2's position field is as often the
        # running order on the road as the classification, which is the same
        # trap the pole call had to be fixed for.
        mate = self._team_mate(s)
        mate_pos = 0
        if mate is not None:
            mate_pos = next((i + 1 for i, c in enumerate(run)
                             if c.id == mate.id), 0)
        career.record_quali(rnd.get("n") or (len(career.rounds) + 1), pos,
                            len(run), circuit.slug if circuit else "",
                            mate_pos=mate_pos,
                            mate=mate.display_name if mate is not None else "")

    def _bank_quali_story(self, s):
        """Remember HOW qualifying went, for the whole grid, for the race.

        The grid slot survives a session change on its own — `started_place`
        is a fact rF2 supplies. The STORY of qualifying does not, and it is
        the single thing the user noticed missing: he had a session he was
        proud of, took pole late, and the booth never referred to it again.

        Keyed by driver NAME, because car ids do not survive a session
        change. Only what was measured: where he finished the session, how
        many places he moved in its closing stretch, and whether his
        benchmark arrived late enough to be the one that stood.
        """
        if s.kind != "quali" or not s.finished:
            return
        run = [c for c in s.order if getattr(c, "best_lap", None)]
        if len(run) < 2:
            return
        run.sort(key=lambda c: c.best_lap)
        late = self._q_pole_hist[-1][1] if self._q_pole_hist else None
        for i, c in enumerate(run):
            name = c.display_name or c.name
            # "Late" means HIS lap was the one that took the top spot in the
            # closing stretch, which is the thing worth remembering — not
            # merely that somebody did.
            was_late = bool(
                late is not None and self._q_final
                and self._q_pole_hist and self._q_pole_hist[-1][0] == c.id)
            note = story_mod.quali_note(
                i + 1, len(run), was_late,
                # Places climbed since we first had a full sheet. Unknown
                # rather than zero when we never saw one — `quali_note`
                # treats it as not notable, which is the safe direction.
                self._q_climb.get(c.id, 0))
            if note:
                self._quali_story[story_mod._key(name)] = note

    def _quali_lap_notable(self, s, set_count, gain):
        """Is this benchmark lap worth the booth remarking on?

        The user's own framing, and it is exactly right: a pole lap early in
        the session means nothing, because the man has beaten nobody and will
        be beaten shortly. What makes a lap notable is that it arrived when
        the sheet was already established.

        Three ways to qualify, any one of which is enough:

          * the session is into its closing stretch, where a benchmark is
            likely to be the one that stands
          * most of the field has run, so there is a real order to head
          * the lap took a genuinely large chunk out of the previous best,
            which is remarkable whenever it happens

        A first-ever time in a session never qualifies: `gain` is None,
        `set_count` is 1, and no clock has run down.
        """
        if set_count < 2:
            return False
        rem = getattr(s, "time_left", None)
        dur = getattr(s, "end_et", 0.0) or 0.0
        if rem is not None and dur and (rem / dur) <= QUALI_LATE_FRACTION:
            return True
        field = s.num_cars or len(s.order)
        if field and set_count >= field * QUALI_RUN_FRACTION:
            return True
        return bool(gain and gain >= QUALI_BIG_GAIN)

    def _quali_filler(self, s, now):
        """Colour for a session where nothing happens for minutes at a time.

        Which is most of qualifying: the interesting question is not what is
        happening but what the timesheet MEANS, and — the state RacerTV found
        by watching — whether anything is on it at all yet.
        """
        out = []
        total = len(s.order)
        if not total:
            return out
        run = self._sheet(s)
        kw = self._kw

        if total == 1:
            # A private test day. Pretending there is a field is the fastest
            # way to sound like a machine reading a template.
            out.append(("quali_solo", kw(s, drv=s.order[0]), s.order[0]))
        elif not run:
            out.append(("quali_nobody", kw(s), None))
        elif len(run) == 1:
            out.append(("quali_onlyone", kw(s, drv=run[0]), run[0]))
        else:
            # "Plenty still to come" is false once everybody has run, so the
            # count splits in two rather than airing a line the timing screen
            # contradicts.
            #
            # But "the whole field has run" is a STATE, not an event (LAW 1).
            # Offered every pass it cycled its four lines for the rest of the
            # session — four different ways of saying the same unchanging
            # thing, over and over. It is worth exactly one mention, at the
            # moment it becomes true.
            if len(run) >= total:
                if not self._q_all_run:
                    self._q_all_run = True
                    out.append(("quali_all_run",
                                kw(s, set=len(run), total=total), None))
            else:
                out.append(("quali_count",
                            kw(s, set=len(run), total=total), None))
            if len(run) >= 3:
                # ONE READOUT OF THE SHEET PER PASS, not two.
                #
                # `quali_standings` gives the order, `quali_top3` gives the
                # order WITH the margins. Both are worth having — "Senna,
                # Prost, Mansell" and "Senna by two tenths" are different
                # sentences — but offering both meant they aired back to
                # back and the booth read the same three names twice in ten
                # seconds. Alternated, so the sheet is described differently
                # each time rather than described twice.
                self._q_read = not getattr(self, "_q_read", False)
                if self._q_read:
                    out.append(("quali_top3",
                                kw(s, p1=run[0].display_name,
                                   p2=run[1].display_name,
                                   p3=run[2].display_name,
                                   t=spoken_lap(run[0].best_lap),
                                   g2=self._margin(run[1].best_lap
                                                   - run[0].best_lap),
                                   g3=self._margin(run[2].best_lap
                                                   - run[1].best_lap),
                                   drv=run[0]), run[0]))
                else:
                    out.append(("quali_standings",
                                kw(s, p1=run[0].display_name,
                                   p2=run[1].display_name,
                                   p3=run[2].display_name,
                                   drv=run[0]), run[0]))

            # Likewise, at most ONE call about the bottom of the sheet per
            # pass — they are three angles on the same fact.
            tail = self._quali_tail(s, run, total)
            if tail:
                self._q_tail_i = (getattr(self, "_q_tail_i", -1) + 1)
                out.append(tail[self._q_tail_i % len(tail)])

        # A FULL PIT LANE IS ONLY A STORY WHILE THERE IS STILL RUNNING TO DO.
        #
        # These lines say things like "nobody wants to go early" and "the
        # circuit is empty" — true of a session holding fire, nonsense at the
        # end of one, when everybody is in the pits because they have
        # finished. The live log has it going out after "all 20 have set a
        # time now", which the viewer can see is wrong.
        in_pits = sum(1 for c in s.order if c.in_pits)
        yet_to_run = total - len(run)
        if (total > 2 and in_pits >= total * 0.6
                and yet_to_run >= max(2, total * QUALI_PITS_WAITING)):
            out.append(("quali_pits", kw(s, n=in_pits), None))

        me = s.player
        if s.kind in ("practice", "test"):
            out.append(("practice_note", kw(s, drv=me or s.order[0]),
                        me or s.order[0]))
            out.append(("quali_goals", kw(s, drv=me or s.order[0]), None))
            if me is not None and getattr(s, "time_left", None) is None:
                out.append(("quali_open_laps",
                            kw(s, drv=me, laps=me.laps or 0), me))

        # Colour. The circuit, the cars and WHO THESE PEOPLE ARE are the only
        # subjects that exist in an empty session, and the booth talking to
        # itself is worth more here than it is in a race. Qualifying is in
        # fact the best place in the whole broadcast for a driver's record:
        # there is time, and the timesheet has just put his name on screen.
        out.extend(self._driver_facts(s, now))
        # QUALIFYING IS WHERE THIS BELONGS MOST. There is time, the timesheet
        # has just put the man's name on screen, and there is no racing to
        # talk over.
        out.append(("driver_ask", kw(s), None))
        out.append(("interview", kw(s), None))
        out.append(("car_character", kw(s), None))
        out.append(("analysis_era", kw(s), None))
        out.append(("track_fact", kw(s), None))
        return out

    def _filler(self, s, now):
        """When nothing happened, find something true and worth saying.

        Ordered by how much it actually adds. A booth with nothing to report
        should mostly say nothing, so this is deliberately thin and heavily
        cooled-down.
        """
        out = []
        if len(s.order) < 2:
            return out
        if not s.green:
            # A NEUTRALISED FIELD IS NOT A REASON TO GO QUIET — it is when a
            # broadcast talks most, and this early return is why the user's
            # six-minute safety car period contained one line.
            #
            # The gate is right about RACING: no battles, no passes, no closing
            # laps, because nobody is racing. It was wrong about everything
            # else. So under a safety car the colour that is still true gets
            # through — the bunched field, the wait, and then the standings and
            # the career/circuit colour by the normal route below.
            sc = self._safety_filler(s, now)
            if not sc:
                return out
            out.extend(sc)
            # THE ORDER IS STILL TRUE, and it is the one number a viewer wants
            # while nothing is happening: who is where when this goes green.
            # Nothing else from the racing tail is offered — `_flow_filler` is
            # about gaps and closing laps, and a gap behind a safety car is a
            # bus queue.
            out.append(("standings", self._kw(s), None))
            return out
        me = s.player
        lead = s.leader

        # THE UNPAID DEBT. The alert sting is nameless by necessity — at the
        # moment of the moment nobody knows who it was. Normally the named
        # line follows a beat later, but if it was suppressed (the booth was
        # mid-sentence, or the incident lost the tick to something bigger)
        # the viewer is left with "somebody's gone off" and never finds out
        # who. Real commentators come back to it.
        if (not self._named_incident
                and LATE_ID[0] < now - self._sting_at < LATE_ID[1]):
            hurt = min((c for c in s.order if not c.in_pits),
                       key=lambda c: c.speed or 999.0, default=None)
            if hurt is not None and (hurt.speed or 999.0) < 140.0:
                self._named_incident = True
                out.append(("offtrack_late", self._kw(s, drv=hurt), hurt))

        # A FIGHT THAT RESOLVED. `_update_battles` publishes these; consumed
        # here so a resolution is ranked against everything else rather than
        # spoken over the top of it. `pulling_away` is written from the
        # DEFENDER's point of view - he is the one who has done something -
        # so he is `a` and the man who could not find a way past is `b`.
        while self._battle_done:
            chaser, defender, held = self._battle_done.pop(0)
            # TWO POOLS, BECAUSE THESE ARE TWO DIFFERENT SENTENCES. Every
            # line in `pulling_away` was written about the LEADER edging
            # clear - "at the front", "away from the field", "that lead is
            # out to" - which is true of one escape in twenty and absurd
            # about a fight for seventh. `battle_escaped` is the resolution
            # of a fight between two named men.
            #
            # Both were unreachable until now: `pulling_away` had no emitter
            # at all, and because nothing ever drew it nobody ever noticed
            # that ALL SIX of its lines need a `{gap}` this code has to
            # supply. An unreachable pool is not merely silent, it is
            # untested prose - which is the other half of why LAW 21 asks
            # for a caller.
            gap = spoken_gap(chaser.gap_ahead or 0.0)
            cat = "pulling_away" if defender.place == 1 else "battle_escaped"
            out.append((cat,
                        self._kw(s, a=defender, b=chaser, drv=defender,
                                 gap=gap,
                                 pos=spoken_place(defender.place),
                                 dur=self._fight_text(held, s)), defender))

        # THREE CARS FOR ONE PLACE. A queue is not two adjacent fights: it is
        # one piece of road that three people want, and the man in front is
        # defending against a car that is itself being harried. Reported for
        # the front of the field only, where the place being fought over is
        # worth the interruption.
        three = self._three_way(s, now)
        if three is not None:
            lead, mid, last = three
            out.append(("battle_three",
                        self._kw(s, a=lead, b=mid, c=last,
                                 pos=spoken_place(lead.place)), lead))

        # a live battle involving someone worth watching
        for c in s.order[:8]:
            ahead = s.car_ahead(c)
            if ahead is None or c.in_pits or ahead.in_pits:
                continue
            g = c.gap_ahead or 99.0
            if g >= STRIKE_GAP:
                continue
            held = self._battle_held(c, ahead, now)
            # A fight that has LASTED is a better story than a fight that
            # exists, and it is the one thing a viewer can see that a
            # timing screen cannot express. Same two cars, different call.
            if held >= LONG_FIGHT:
                out.append(("battle_sustained",
                            self._kw(s, a=c, b=ahead, gap=spoken_gap(g),
                                     dur=self._fight_text(held, s),
                                     pos=spoken_place(ahead.place)), c))
                break
            if held > 3.0:
                out.append(("battle", self._kw(s, a=c, b=ahead,
                                               gap=spoken_gap(g),
                                               pos=spoken_place(ahead.place)),
                            c))
                break

        # WHERE HE STANDS AGAINST THE OTHER CAR. Not a battle — they may be
        # half a lap apart — but the comparison every team makes first, and
        # the only one on the grid with nothing to explain it away.
        #
        # Offered as colour, so it is ranked on staleness like everything else
        # and cannot interrupt the racing; the family gate (MATE_CATS) stops
        # it becoming a nag, because unlike a battle this is TRUE all
        # afternoon.
        # WHAT DIVISION THIS ACTUALLY IS.
        #
        # `era.classify` reports a Tatuus F4 and a 2021 Formula One car as the
        # same discipline in the same period — because that is what they are,
        # single-seaters of the same decade — so no era gate can ever make the
        # booth say "these F4 cars". The LADDER RUNG is the only thing that
        # knows, and it is right here.
        #
        # A rung with no pool says nothing at all, which is the honest default
        # and lets a division be added to the data without touching this.
        if getattr(self, "_season_round", None):
            car_ = getattr(self, "season", None)
            tier = None
            if car_ is not None and getattr(car_, "on_ladder", False):
                prog = car_.ladder
                tier = (prog.tier() or {}) if prog is not None else None
            key = (tier or {}).get("key")
            if key and lines_mod.pool("div_%s" % key):
                out.append(("div_%s" % key,
                            self._kw(s, drv=me, series=self._series_name(s)),
                            me))

        mate = self._team_mate(s)
        # THE SEASON'S HEAD-TO-HEAD. A standing fact rather than news, so it
        # sits behind the same family gate and a long cooldown — and it is
        # only ever offered inside a career round, because outside one the
        # store has no season to count.
        if (mate is not None and me is not None
                and getattr(self, "_season_round", None)
                and now - self._mate_last >= MATE_FAMILY_GAP):
            car = getattr(self, "season", None)
            rec = None
            if car is not None:
                rec = self._guard("mate_record", car.team_mate_record,
                                  fallback=None)
            if rec:
                if rec["quali_up"] or rec["quali_down"]:
                    out.append(("mate_record",
                                self._kw(s, a=me, b=mate, cat="mate_record",
                                         n=rec["quali_up"],
                                         m=rec["quali_down"]), me))
                if rec["races_up"] or rec["races_down"]:
                    out.append(("mate_record_races",
                                self._kw(s, a=me, b=mate,
                                         cat="mate_record_races",
                                         n=rec["races_up"],
                                         m=rec["races_down"]), me))

        if (mate is not None and me is not None and not mate.in_pits
                and not me.in_pits
                and now - self._mate_last >= MATE_FAMILY_GAP):
            gapl = getattr(me, "gap_leader", None)
            gapm = getattr(mate, "gap_leader", None)
            if gapl is not None and gapm is not None:
                d = abs(gapl - gapm)
                cat = "mate_ahead" if me.place < mate.place else "mate_behind"
                out.append((cat, self._kw(s, a=me, b=mate, cat=cat,
                                          gap=spoken_gap(d),
                                          pos=spoken_place(me.place)), me))

        # the player closing on the car ahead
        if me is not None and me.place > 1:
            ahead = s.car_ahead(me)
            if ahead is not None and 0.3 < (me.gap_ahead or 99) < 3.0:
                out.append(("closing", self._kw(s, a=me, b=ahead,
                                                gap=spoken_gap(me.gap_ahead)), me))

        if s.max_laps and s.laps_left and 1 < s.laps_left <= 5:
            out.append(("final_laps", self._kw(s, laps=s.laps_left), None))

        second = s.order[1] if len(s.order) > 1 else None
        gap2 = (second.gap_ahead if second else None)
        if lead is not None and second is not None:
            out.append(("standings", self._kw(s, drv=lead, b=second,
                                              gap=spoken_gap(gap2)), lead))

        out.extend(self._flow_filler(s, now, lead, second, gap2))

        # THE OPENING LAP HAS ONE JOB: THE FIGHT AT THE FRONT.
        #
        # The user's report: right after lights out the booth sounds "very
        # random" — a driver fact or a circuit fact competing for the mic
        # while cars are still fighting into turn one. None of the real
        # events (overtakes, battles) were the problem; REAL events already
        # out-rank filler by priority. The problem was that filler itself had
        # no phase awareness at all, so the moment there was a single quiet
        # tick in the opening laps, colour was exactly as likely to fill it
        # as anything track-relevant.
        #
        # So the whole tail of this function — who these people are, their
        # season, their car, a circuit fact, a joke — is withheld until the
        # race has a shape of its own. `_race_phase` already scales "opening"
        # with race length (one lap on a sprint, two on anything longer), so
        # this reuses that boundary rather than inventing a new one.
        if self._phase == "opening":
            return out

        # MULTICLASS. `place_class` was computed on every tick and read by
        # nothing at all — so a GT3 car leading its class while running
        # ninth overall was called "ninth", which is not his race. Kept in
        # the closing laps too: a class battle is the result for those cars.
        out.extend(self._class_filler(s, now))

        # THE CLOSING LAPS HAVE ONE JOB: THE RESULT, AND WHATEVER IS STILL
        # BEING FOUGHT OVER. Driver backstory, a circuit fact or a joke in
        # the last laps is the same "random" complaint at the other end of
        # the broadcast from the opening-lap one above — nobody wants a fact
        # about the venue while the podium is still being decided.
        # `_flow_filler`, already called above, covers what IS wanted here:
        # the gap to the flag, the podium fight, laps left.
        if self._phase == "closing":
            return out

        # Who these people are. Above the generic colour because a true fact
        # about a named man beats an observation about racing in general, and
        # below everything that is actually happening on track.
        out.extend(self._driver_facts(s, now))

        # WHOSE CAREER THIS IS — the same kind of fact one level up. It sits
        # with the driver briefing because it IS a briefing: who is out there
        # and what he has done. Ranked on staleness with the rest of the
        # colour rather than jumping the queue.
        #
        # BEHIND ONE FAMILY GATE FOR THE WHOLE GROUP (LAW 15). "No television
        # money in this paddock" followed by "he came up through every rung of
        # this" is one thought said twice, and the register lines are in the
        # family for exactly that reason.
        #
        # THE PHASE GATES ABOVE ALREADY EXCLUDE IT from the opening and
        # closing laps, which is right: a career fact during the run to the
        # flag is the booth looking away from the race.
        if now - max(self._cat_last.get(c, 0.0)
                     for c in LADDER_CATS) > LADDER_FAMILY_GAP:
            # The career is ONE source among many here. It was the source
            # that raised, and it took every other one down with it.
            cat, kw = self._guard("career colour", self._ladder_call, s,
                                  fallback=(None, {}))
            if not cat:
                cat, kw = self._register_call(s)
            if cat:
                out.append((cat, kw, me))

        # SETTLING gets the briefing and nothing else. Who is driving and what
        # he is driving is what a real booth does once the order has formed —
        # it is ABOUT the cars on screen. A joke, a circuit fact or a
        # retrospective on somebody's afternoon is not, and three laps in
        # there is barely an afternoon to look back on. The widening the user
        # asked for at this point is a DEPTH change (`FOCUS_LIMIT`), not a
        # licence for colour.
        if self._phase == "settling":
            out.append(("car_character", self._kw(s), None))
            return out

        # HOW A DRIVER'S RACE HAS GONE. The most interesting thing the booth
        # can say when nothing is happening in front of it, and the thing a
        # viewer cannot get from the timing screen.
        out.append(("story_ask", self._kw(s), None))
        out.append(("driver_ask", self._kw(s), None))

        # LEVITY, and it goes through its own gate rather than relying on
        # ranking. A joke that merely LOSES to an incident is still a joke
        # that was offered while somebody was in the wall, and the ranking is
        # not something to trust with that.
        out.extend(self._levity(s, now))

        # colour: the analyst filling honest dead air.
        #
        # `car_character` is what THIS KIND OF CAR is like, gated on era
        # capability rather than on a season we hold records for — so it
        # reaches the Group C race and the Super Touring grid and the GT3
        # field, not only the three Formula One seasons. It is the layer that
        # gives a one-off race something true to say about the machinery.
        out.append(("car_character", self._kw(s), None))
        out.append(("analysis_era", self._kw(s), None))
        out.append(("analysis", self._kw(s, drv=me or lead), None))
        # Track knowledge is the LAST resort, below every other kind of
        # colour — it is the most obviously "filler" thing the booth can do,
        # and a circuit fact over a live battle would be absurd.
        out.append(("track_fact", self._kw(s), None))
        return out

    @staticmethod
    def _place_bonus(e):
        """How much the POSITION an event concerns adds to its ranking.

        Events are (category, slots, subject); the subject is the car the
        line is about, and may be None for something that concerns the race
        as a whole — which gets no bonus rather than a default, because "the
        whole race" is not a position.
        """
        car = e[2] if len(e) > 2 else None
        place = getattr(car, "place", None) if car is not None else None
        if not place:
            return 0
        return PLACE_WEIGHT.get(place, PLACE_WEIGHT_TAIL)

    def _front_fight_live(self, s):
        """Is the LEAD being fought over, right now?

        True only when the car in second is inside striking distance of the
        leader. Deliberately not "is there a battle event" — the override
        below has to hold for the whole run to the flag, not just on the tick
        a battle was detected, or the booth would drift back to the midfield
        between calls about the very thing deciding the race.
        """
        if s.kind != "race" or not s.green:
            return False
        for c in s.order:
            if getattr(c, "place", None) == 2:
                if c.in_pits or getattr(c, "laps_down", 0):
                    return False
                return 0.0 < (c.gap_ahead or 99.0) < STRIKE_GAP
        return False

    def _front_bonus(self, e):
        """The closing-laps override: a fight for the lead beats everything.

        Zero while the leader is uncontested and zero for anything not
        concerning the top two, so a procession is never shouted about and the
        wide view of the race survives.

        The bonus is full weight in `late` and `closing`, where a fight for
        the lead IS the broadcast, and reduced in the body of the race — where
        it still has to beat a midfield move, because the man chasing the
        leader is the story either way.
        """
        if not self._front_fight:
            return 0
        car = e[2] if len(e) > 2 else None
        place = getattr(car, "place", None) if car is not None else None
        if place not in LATE_FRONT_PLACES:
            return 0
        return (LATE_FRONT_BONUS if self._phase in ("late", "closing")
                else FRONT_BONUS)

    def _rank_filler(self, events, now):
        """Order colour by STALENESS, not by importance.

        Events are ranked by priority, because when two things happen at once
        the bigger one is the story. Filler is the opposite problem: strict
        priority means the same three or four categories win every slot, the
        ones below them never come up at all, and an hour of racing is
        narrated by a handful of sentences — which is precisely the failure
        this whole pass exists to fix.

        So the longest-unsaid thing goes first, with priority worth about a
        minute of staleness as a tiebreak. Everything gets its turn, and the
        turns still come in a sensible order.
        """
        unseen = now - 600.0        # never said this session: near the front,
                                    # but not so far ahead it jumps a live fight

        def score(e):
            cat = e[0]
            # A position bonus is worth real staleness here, so a fight at
            # the front outranks an older line about the midfield instead of
            # patiently waiting its turn behind it.
            s = ((now - self._cat_last.get(cat, unseen))
                 + PRIORITY.get(cat, 0) * 2.0
                 + self._place_bonus(e) * 3.0
                 + self._front_bonus(e) * 3.0)
            # Hand the microphone back. Ranking on staleness alone let Chuck
            # deliver five observations in a row, because the analyst owns
            # most of the colour categories — and two people taking turns is
            # the entire reason there are two of them.
            if cast_mod.who_says(cat) == self._last_voice:
                s -= HANDOVER_BONUS
            return s
        return sorted(events, key=score, reverse=True)

    def _flow_filler(self, s, now, lead, second, gap2):
        """The race told as a race: where we are, what the numbers mean, and
        who is quietly having a good afternoon.

        This is the answer to the 60-lap problem. A race whose middle hour is
        covered by four filler categories has fifty laps of the same six
        sentences; what an actual broadcast does in that hour is report the
        lap, mark the distance, read what the gaps MEAN, look down the field
        for the story nobody's watching, and — most of all — have the two of
        them talk to each other.
        """
        out = []
        kw = self._kw
        laps_done = s.leader_laps or 0
        togo = s.laps_left or 0

        # WHERE WE ARE. Reported on a lap boundary rather than a timer, so it
        # lands as news rather than as a clock.
        if s.max_laps and laps_done != self._last_lap_seen:
            self._last_lap_seen = laps_done
            if laps_done >= 2 and self._phase in ("mid", "settling"):
                out.append(("lap_report",
                            kw(s, drv=lead, b=second, lap=laps_done,
                               laps=togo, gap=spoken_gap(gap2),
                               dist=self._distance_text(s)), lead))
            mark = self._distance_mark(s, laps_done)
            if mark:
                out.append(("lap_milestone",
                            kw(s, drv=lead, mark=mark, lap=laps_done,
                               gap=spoken_gap(gap2)), lead))

        # The clock, on a timed race, at the marks that actually mean
        # something to a viewer rather than every time we look at it.
        if not s.max_laps and getattr(s, "time_left", None):
            mark = self._time_mark(s.time_left, getattr(s, "end_et", 0.0) or 0.0)
            if mark:
                out.append(("time_remaining",
                            kw(s, drv=lead, mins=mark), lead))

        # WHAT THE NUMBERS MEAN. Chuck's job, and the difference between a
        # timing screen with a voice and an analyst.
        if lead is not None and second is not None and gap2 is not None:
            if self._phase in ("late", "closing") and togo:
                out.append(("insight_laps_left",
                            kw(s, drv=second, b=lead, laps=togo,
                               gap=spoken_gap(gap2)), lead))
            if gap2 >= BIG_LEAD:
                out.append(("insight_lead_big",
                            kw(s, drv=lead, b=second, gap=spoken_gap(gap2)),
                            lead))
            elif gap2 <= SLIM_LEAD:
                out.append(("insight_lead_slim",
                            kw(s, drv=lead, b=second, gap=spoken_gap(gap2)),
                            lead))

        # THE PODIUM as a thing in itself, which is how viewers watch a race
        # even when the lead is settled.
        if len(s.order) >= 4:
            third, fourth = s.order[2], s.order[3]
            spread = (third.gap_leader or 0.0)
            if (third.gap_ahead or 99) < STRIKE_GAP or (fourth.gap_ahead or 99) < STRIKE_GAP:
                out.append(("insight_podium_fight",
                            kw(s, a=third, b=fourth, drv=third), third))
            elif (fourth.gap_ahead or 0) > 8.0 and self._phase in ("mid", "late"):
                out.append(("podium_lock", kw(s, drv=third), third))
            out.append(("podium_watch",
                        kw(s, drv=third, pos=spoken_place(3),
                           gap=spoken_gap(third.gap_ahead)), third))
            if spread:
                out.append(("insight_field_spread",
                            kw(s, n=len(s.order), gap=spoken_gap(spread)), None))

        # THE FIELD. Deliberately gated to the middle of longer races: in a
        # sprint the front is the whole story, and in the closing laps a P12
        # scrap is an interruption.
        # `settling` is included deliberately: a fight that formed behind the
        # leaders on lap three IS the broadening the phase exists for. It is
        # colour that waits, not racing.
        if (self._phase in ("mid", "settling")
                and self._length in ("normal", "long", "endurance")):
            # A midfield fight is happening NOW, so it needs no history and
            # is callable from lap one.
            pair = self._midpack_battle(s, now)
            if pair:
                a, b = pair
                out.append(("midpack",
                            kw(s, a=a, b=b, pos=spoken_place(b.place)), a))
            # A recovery drive is a claim about the race so far, so it does.
            mover = self._best_mover(s) if self._enough_race(s) else None
            if mover is not None:
                st = self._story.get(mover.id) or {}
                out.append(("midpack_recovery",
                            kw(s, drv=mover, pos=spoken_place(mover.place),
                               from_pos=spoken_place(st.get("worst"))), mover))

        # THE GRID. What a driver has actually made of where he started, which
        # is the frame a commentator reaches for constantly and the booth had
        # no way of expressing. Only when the grid was captured cleanly, and
        # only once the race means something.
        if self._enough_race(s):
            for c in s.order[:10]:
                if not self._has_grid(c) or abs(c.places_gained) < GRID_MOVE:
                    continue
                out.append((
                    "grid_progress" if c.places_gained > 0 else "grid_slipped",
                    kw(s, drv=c, pos=spoken_place(c.place),
                       n=abs(c.places_gained)), c))
                break

        # THE ARC. `_track_story` has been recording every driver's best and
        # worst place all race; this is the thing that finally consumes it.
        # Gated on there being a race to have an arc across.
        arc = self._arc_story(s) if self._enough_race(s) else None
        if arc:
            cat, car, st = arc
            out.append((cat,
                        kw(s, drv=car, pos=spoken_place(car.place),
                           from_pos=spoken_place(st["worst"] if cat == "arc_recovered"
                                                 else st["best"]),
                           n=abs(car.place - (st["worst"] if cat == "arc_recovered"
                                              else st["best"]))), car))

        # THE BOOTH ITSELF. Lowest priority of anything here, and the thing
        # that makes the other two hours bearable.
        if self._phase in ("mid", "late") and lead is not None:
            out.append(("interview", kw(s), None))
        if lead is not None and second is not None:
            out.append(("summary", kw(s, drv=lead, b=second, laps=togo,
                                      gap=spoken_gap(gap2)), lead))
        # THE MEASURED FACTS. Each of these has its own pool and its own
        # slot, because one slot name meaning three different things is how
        # "twenty laps in front" got on air in a fifteen-lap race.
        led = self._laps_led(lead)
        if led >= 5 and lead is not None:
            out.append(("stat_laps_led",
                        kw(s, drv=lead, led=self._laps_text(led)), lead))
        if self._lead_changes >= 2:
            out.append(("stat_lead_changes",
                        kw(s, chg=self._changes_text(self._lead_changes)),
                        None))
        running = len([c for c in s.order if not getattr(c, "retired", False)])
        if running >= 6 and running == self._field_size:
            # Only worth saying while NOBODY has dropped out. "Twenty still
            # running" when three have retired is the kind of small wrongness
            # the timing screen contradicts.
            out.append(("stat_running",
                        kw(s, cars="%d cars" % running), None))
        if self._top3_covered(s):
            out.append(("stat_covered", kw(s), None))
        # The archive framing, as colour. Gated on the seat rather than on a
        # year test here, so there is exactly one place that decides what
        # counts as historic.
        if cast_mod.is_historic():
            out.append(("archive_era", kw(s), None))
            out.append(("archive_watch", kw(s), None))
        # The station ident. Rare, and worth having: viewers arrive in the
        # middle of a race and a broadcast that never says what it is leaves
        # them guessing.
        # The ident cannot claim to be live over archive footage.
        hist = cast_mod.is_historic()
        # ONE OF THE FAMILY AT A TIME (LAW 15). Offered as a group so the gate
        # is checked once, upstream of the ranking — the same reason levity is
        # vetoed rather than ranked. Three station lines that each win a quiet
        # tick in turn is a promo reel, and each one of them is correct.
        last = max((self._cat_last.get(c, 0.0) for c in STATION_CATS))
        if now - last < STATION_FAMILY_GAP:
            return out
        out.append(("broadcast_archive" if hist else "broadcast", kw(s), None))
        # THE REST OF THE NETWORK. A real station plugs its other channel and
        # has a house history, and both are continuity rather than racing —
        # so they sit at the very bottom of the filler, below the ident that
        # is already the lowest thing here.
        #
        # The two channels are a fact about this product, not an invention:
        # `cast.set_era` puts Brett in the chair before 2000 and Miles after,
        # so FACTORtv Classic is genuinely where the archive fixtures are and
        # the plug describes something that exists. Each man points at the
        # OTHER channel — nobody plugs himself.
        out.append(("broadcast_promo_archive" if hist
                    else "broadcast_promo", kw(s), None))
        out.append(("broadcast_racertv_archive" if hist
                    else "broadcast_racertv", kw(s), None))
        return out

    def _update_battles(self, s, now):
        """How long each car has been locked onto the one in front.

        Swept across the WHOLE field once a tick, and deliberately NOT inside
        the loop that reports fights. That loop stops at the first fight
        worth calling, so when the clearing lived inside it every car behind
        that one kept a timer nothing ever reset — and a pair eight seconds
        apart was eventually announced as having been nose to tail for eight
        laps. It was, once, against somebody else, half an hour earlier.

        The opponent is stored with the timer for the same reason: a fight is
        between two specific cars, and when the car ahead changes the elapsed
        time belongs to a different story.
        """
        for c in s.order:
            ahead = s.car_ahead(c)
            gap = c.gap_ahead if c.gap_ahead is not None else 99.0
            if (ahead is None or c.in_pits or ahead.in_pits
                    or gap >= STRIKE_GAP or not s.green):
                # A FIGHT THAT ENDS WITHOUT A PASS IS STILL AN ENDING, and
                # until now it was simply forgotten: the timer was dropped
                # and `pulling_away` - which exists, with six lines - had no
                # emitter to reach it. This is the resolution the user asked
                # for: the defender held on and got away.
                #
                # THE GAP IS NOT ENOUGH ON ITS OWN. It crosses STRIKE_GAP
                # every lap on every circuit, so an escape has to be BIGGER
                # than the fight threshold and has to have LASTED - trigger
                # and clear point, LAW 18. Without the hold this fires out of
                # the last corner of every lap of every race.
                rec = self._battle_since.pop(c.id, None)
                if (rec is not None and ahead is not None and not c.in_pits
                        and not ahead.in_pits and s.green
                        and rec[1] == ahead.id
                        and now - rec[0] >= BATTLE_RESOLVE_MIN
                        and gap >= BATTLE_CLEAR_GAP):
                    self._battle_clear[c.id] = (now, ahead.id, now - rec[0])
                continue
            # Back inside the fight: whatever escape was building is off.
            self._battle_clear.pop(c.id, None)
            prev = self._battle_since.get(c.id)
            if prev is None or prev[1] != ahead.id:
                self._battle_since[c.id] = (now, ahead.id)

        # An escape only counts once it has been held. Checked in its own
        # pass so a car that has left the pack entirely is reported once and
        # then forgotten rather than every tick for the rest of the race.
        for cid, (at, aid, held) in list(self._battle_clear.items()):
            if now - at < BATTLE_CLEAR_HOLD:
                continue
            del self._battle_clear[cid]
            chaser = next((c for c in s.order if c.id == cid), None)
            defender = next((c for c in s.order if c.id == aid), None)
            if chaser is None or defender is None:
                continue
            if chaser.in_pits or defender.in_pits:
                # He did not pull away, the other man stopped. Reporting that
                # as racecraft is the kind of small wrongness a viewer can
                # see on the timing screen.
                continue
            self._battle_done.append((chaser, defender, held))

    def _battle_held(self, c, ahead, now):
        """Seconds this exact pair have been fighting. Zero if they are not."""
        rec = self._battle_since.get(c.id)
        if not rec or (ahead is not None and rec[1] != ahead.id):
            return 0.0
        return now - rec[0]

    def _team_mate(self, s):
        """The other car in the player's team, or None.

        THE MOST F1 THING IN THE SPORT, and it turns out to be free.

        For the Formula One mods rF2 reports the CONSTRUCTOR as the CarClass —
        "Ferrari", "Mercedes", "Red Bull" — which is the quirk `era.team_field`
        already exists to detect, because `career.py` has to tell a
        team-named grid apart from a genuine multi-class race. So the man in
        the other side of the garage is simply the other car sharing the
        player's class. No data file, no lookup, no guessing, and it is
        correct on every tick.

        IT IS SILENT EVERYWHERE ELSE, and that is right rather than a gap.
        In USF2000 the class is "Championship" and the entrant lives only in
        the result file, so a live team-mate cannot be known — and inventing
        one would be the first false claim this booth has ever made about who
        somebody drives for.

        A CLASS WITH MORE THAN TWO CARS IS NOT A TEAM. Some of these mods
        carry spare AI entries under the same constructor; if the class holds
        anything other than exactly one other car, there is no unambiguous
        team-mate and the answer is None.
        """
        me = getattr(s, "player", None)
        if me is None or not getattr(me, "cls", ""):
            return None
        try:
            team_named = era_mod.team_field(
                getattr(s, "classes", []) or []) is not None
        except Exception:
            team_named = False
        if not team_named:
            # THE CLASS IS THE SERIES, NOT THE TEAM — which is every division
            # except the two Formula One mods. The entrant is only in the
            # result file, so it is learned from history and applied live.
            return self._team_mate_learned(s)
        mates = [c for c in s.order
                 if c is not me and getattr(c, "cls", "") == me.cls]
        if len(mates) == 1:
            return mates[0]
        return None

    def _team_mate_learned(self, s):
        """The team-mate in a championship whose class is the SERIES.

        In Formula 2 every car on the grid reports "Formula 2 2019", so the
        trick that works in the Formula One mods — where the CarClass IS the
        constructor — has nothing to work with. The entrant exists only in the
        result file.

        SO IT IS LEARNED AND THEN APPLIED LIVE. `career.History` folds
        `TeamName` off every result it scans, including qualifying sessions,
        so one session with a grid is enough to know who drives for whom for
        the rest of the career. That is the same shape as the driver roster
        the New Career menu is built from, using a field that has been parsed
        since the module was written and read by nothing.

        IT REFUSES RATHER THAN GUESSES, in three places: no history, no
        pairing for the player, or anything other than exactly one other car
        on his team. A stale pairing costs one silent line; a wrong one would
        be a false claim about who somebody drives for, which is the thing
        this booth has never done.
        """
        me = getattr(s, "player", None)
        hist = getattr(self, "career", None)
        if me is None or hist is None or not getattr(me, "cls", ""):
            return None
        lookup = getattr(hist, "team_of", None)
        if not callable(lookup):
            return None
        mine = self._guard("team_of", lookup, me.display_name, me.cls,
                           fallback="")
        if not mine:
            return None
        mates = []
        for c in s.order:
            if c is me or getattr(c, "cls", "") != me.cls:
                continue
            if self._guard("team_of", lookup, c.display_name, c.cls,
                           fallback="") == mine:
                mates.append(c)
        return mates[0] if len(mates) == 1 else None

    def _three_way(self, s, now):
        """Three cars covered by a strike, held long enough to be a queue.

        Returns (leader of the three, middle, last) or None.

        WHY IT IS NOT JUST TWO BATTLES NEXT TO EACH OTHER. The middle car is
        in both of them, and that is the whole situation: he cannot commit to
        a move on the man in front without opening the door to the man
        behind. A booth that calls it as two separate fights has described
        the timing screen rather than the race.

        Front of the field only. Three cars nose to tail for fourteenth is
        true and it is not worth interrupting anything for, and the depth
        limit the rest of the booth uses (`_interesting`) already encodes
        where the line is.

        The hold is its own thing rather than `_battle_held` on both pairs,
        because a queue forms and breaks constantly through traffic - what
        makes it a story is that it has PERSISTED, and the timer has to
        belong to the trio rather than to either pair.
        """
        best = None
        for i in range(min(len(s.order), 8) - 2):
            lead, mid, last = s.order[i], s.order[i + 1], s.order[i + 2]
            if any(x.in_pits for x in (lead, mid, last)):
                continue
            if not self._interesting(lead):
                continue
            if ((mid.gap_ahead or 99.0) >= STRIKE_GAP
                    or (last.gap_ahead or 99.0) >= STRIKE_GAP):
                continue
            best = (lead, mid, last)
            break
        if best is None:
            self._three_since = None
            return None
        ids = tuple(x.id for x in best)
        if self._three_since is None or self._three_since[0] != ids:
            self._three_since = (ids, now)
            return None
        if now - self._three_since[1] < THREE_WAY_HOLD:
            return None
        return best

    def _midpack_battle(self, s, now):
        """A close fight outside the top places, held for long enough to be
        real. Returns (chaser, defender) or None."""
        for c in s.order[5:]:
            if c.in_pits or (c.gap_ahead or 99) >= STRIKE_GAP:
                continue
            ahead = s.car_ahead(c)
            if ahead is None or ahead.in_pits:
                continue
            if self._battle_held(c, ahead, now) > 5.0:
                return c, ahead
        return None

    def _best_mover(self, s):
        """The driver who has gained the most on their worst place — the
        recovery drive nobody in the booth has noticed yet.

        Explicitly NOT the front of the race. The whole premise of the line
        is that this driver has gone unmentioned, and it fired for the race
        leader — "nobody's mentioned Ayrton Senna, and he's climbed to the
        lead" — about the one man the booth had been talking about all
        afternoon. A charge to the front is a real story, but it belongs to
        `arc_recovered`, which says so in those terms.
        """
        best, gain = None, 0
        for c in s.order:
            st = self._story.get(c.id)
            if not st or c.in_pits or c.place <= MIDPACK_FROM:
                continue
            g = st["worst"] - c.place
            if g > gain and g >= 4:
                best, gain = c, g
        return best

    def _arc_story(self, s):
        """A driver whose race has a shape worth stating outright."""
        for c in s.order[:12]:
            st = self._story.get(c.id)
            if not st or c.in_pits:
                continue
            if st["worst"] - c.place >= 6:
                return "arc_recovered", c, st
            if c.place - st["best"] >= 6:
                return "arc_cost", c, st
        return None

    def _fight_text(self, secs, s):
        """How long a fight has been going on, said the way a commentator
        says it.

        Laps where a lap is a meaningful unit, and time where it is not — "for
        the last three laps" is how this is described on television, but at
        the Nordschleife two minutes of pressure is not even one lap and
        calling it "half a lap" understates it badly.
        """
        pace = getattr(s, "best_lap_time", None) or 0.0
        if pace and secs >= pace * 1.6:
            return "%d laps" % int(secs / pace)
        if pace and secs >= pace * 0.8:
            return "a lap"
        if secs >= 90:
            return "well over a minute"
        if secs >= 45:
            return "the best part of a minute"
        return "several corners"

    def _distance_text(self, s):
        """How the race length is said out loud."""
        if s.max_laps:
            return "%d laps" % s.max_laps
        dur = getattr(s, "end_et", 0.0) or 0.0
        if dur >= 3600:
            h = dur / 3600.0
            return "%g hours" % round(h, 1)
        if dur:
            return "%d minutes" % int(round(dur / 60.0))
        return "the full distance"

    def _distance_mark(self, s, laps_done):
        """Quarter, half and three-quarter distance, once each.

        Half distance is the one that always fires; the quarters are only
        worth marking on a race long enough for them to be far apart.
        """
        if not s.max_laps or s.max_laps < 8:
            return None
        marks = [(0.5, "half distance")]
        if s.max_laps >= 25:
            marks += [(0.25, "quarter distance"),
                      (0.75, "three-quarter distance")]
        for frac, name in marks:
            if name in self._marks_done:
                continue
            if laps_done >= int(round(s.max_laps * frac)):
                self._marks_done.add(name)
                return name
        return None

    def _time_mark(self, rem, dur):
        """Clock marks on a timed race, once each.

        Marks longer than the race itself are skipped, or a twenty-minute
        sprint opens by announcing an hour to go.
        """
        for mins in (60, 30, 15, 10, 5, 2):
            if mins in self._marks_done or mins * 60.0 >= dur:
                continue
            if rem <= mins * 60.0:
                self._marks_done.add(mins)
                return ("one hour" if mins == 60 else
                        "two minutes" if mins == 2 else "%d minutes" % mins)
        return None

    # -- helpers ---------------------------------------------------------------
    def _interesting(self, c):
        """Is this car worth commenting on RIGHT NOW?

        The player is always in scope. Everyone else is judged against the
        current phase, so the same P9 battle is worth calling in the middle of
        the race and not worth interrupting the last lap for.
        """
        return bool(c.is_player) or self._focus(c.place)

    def _who_was(self, s, place):
        """The car that previously held `place` — the one just passed.

        BOTH SIDES CONFIRMED, for the same reason the pass itself is: mixing the
        de-bounced place with the raw one means the victim is looked up in a
        different instant from the pass, and the answer is then nobody. A pass
        with no victim is discarded, so this is the second way one line could
        silence every overtake in the product.
        """
        conf = getattr(self, "_conf_now", None) or {}
        for c in s.order:
            p = self._prev.get(c.id)
            if p is None:
                continue
            if p.conf == place and conf.get(c.id, c.place) > place:
                return c
        return None

    def _status_call(self, s):
        """The line that says what the player is. (category, kw) or (None, {}).

        Reuses the same six pools the pre-session career beat draws on, so
        there is exactly one place in the product where "he is a rookie" is
        written — asked for as LAW: a milestone renders the EXISTING event,
        never a second detector.
        """
        career = getattr(self, "season", None)
        if career is None or not getattr(career, "on_ladder", False):
            return None, {}
        if not getattr(self, "_season_round", None) or s.player is None:
            return None, {}
        try:
            key = (career.status() or ("", ""))[0]
            r = career.resume() or {}
        except Exception:
            return None, {}
        cat = {"rookie": "status_rookie", "riser": "status_riser",
               "contender": "status_contender", "champion": "status_champion",
               "multi": "status_multi", "legend": "status_legend"}.get(key)
        if not cat:
            return None, {}
        # `status_riser` names the division he climbed out of. Without one it
        # cannot be said, so it becomes the line that needs no history.
        if cat == "status_riser" and not r.get("reigning"):
            cat = "status_contender"
        kw = self._kw(s, drv=s.player, cat=cat,
                      series=(career.evaluate() or {}).get("tier_name", ""),
                      below=r.get("reigning", ""),
                      seasons=drivers_mod.spoken_number(r.get("seasons") or 0),
                      races=r.get("races") or 0, wins=r.get("wins") or 0,
                      titles=drivers_mod.spoken_number(r.get("title_count") or 0))
        return cat, kw

    def _status_form(self, s, name, apt=False):
        """His name as a broadcast would say it, given what he has won.

        Asked for directly: *"the booth should basically call me by two
        things, either my name or my status — either 'Dante Kandasamy', 'The
        Rookie', 'Dante Kandasamy the Rookie' or 'The Rookie Dante
        Kandasamy'"*.

        THE FIRST TIME HE IS NAMED IN A SESSION, THE NAME CARRIES THE STATUS.
        A spin in qualifying reads "that is Dante Kandasamy, the rookie, off
        at turn four" rather than a bare surname a viewer has no reason to
        care about yet — and after that he is simply himself, with the status
        form returning occasionally so it stays a way of referring to him
        rather than an announcement made once.

        Returns the name UNCHANGED outside a ladder career, and whenever the
        store has no status to add — which is every one-off race, and costs
        nothing when it is.
        """
        career = getattr(self, "season", None)
        if not name or career is None or not getattr(career, "on_ladder", False):
            return name
        if not getattr(self, "_season_round", None):
            return name
        try:
            label = (career.status() or ("", ""))[1]
        except Exception:
            return name
        if not label:
            return name
        tag = "the " + label.lower()
        # THE SEED HAS TO BE STABLE PER MENTION, NOT PER SESSION.
        #
        # It used to be `hash((name, self._pre_at))`, which does not change
        # for the whole session — so `seed % 5` was not "one mention in five",
        # it was ALL of them or NONE of them. The live log is the proof: the
        # word "rookie" nineteen times against thirty-three uses of his name,
        # which is not a one-in-five that got lucky, it is a coin that landed
        # once and stayed there.
        #
        # `_say_n` counts lines that have actually AIRED, so it is constant
        # while a tick composes its candidates — `_kw` builds far more lines
        # than the booth ever speaks — and moves on once one of them does.
        seed = abs(hash((name, getattr(self, "_say_n", 0))))
        if not getattr(self, "_status_named", False):
            # THE INTRODUCTION. Once per session, whatever the line is about:
            # this is the moment the viewer is told who he is watching.
            return ("%s, %s," % (name, tag)) if seed % 2 else ("%s %s" % (tag, name))

        # AFTER THAT, HE IS A NAME — AND MOSTLY A SURNAME.
        #
        # The user: "there must be a balance and more often than not use more
        # of the surname to address the player". That is also simply how a
        # broadcast talks: the full name is for the introduction and the big
        # moments, and the rest of the afternoon is surnames.
        surname = self._surname(name)
        if apt and seed % 6 == 0:
            # ...AND THE STATUS ONLY WHERE IT FITS. "That's the rookie off at
            # turn four" earns its place because the mistake and the status
            # are the same thought. "The rookie is four tenths down in sector
            # two" is a status badge stapled to a gap. The caller says which
            # kind of line this is; anything that does not say gets a name.
            return tag
        return name if seed % 3 == 0 else surname

    @staticmethod
    def _surname(name):
        """The last name, for a booth that has already introduced him.

        Suffixes are stripped rather than read out — "Kandasamy Jr." is a
        surname, "Jr." is not — and a single-word name is returned whole,
        which is what a driver racing under one name should get.
        """
        parts = [p for p in (name or "").split() if p]
        while len(parts) > 1 and parts[-1].strip(".").lower() in (
                "jr", "sr", "ii", "iii", "iv"):
            parts.pop()
        return parts[-1] if parts else name

    def _kw(self, s, a=None, b=None, drv=None, c=None, **extra):
        """Slot dictionary for a template.

        Names go in as display names, and `_name` carries the raw name so the
        TTS can pick a nationality-matched voice for driver radio.
        """
        def nm(c):
            return c.display_name if c is not None else ""
        # Where the subject of this line started. The grid slot was never
        # filled, so the booth could not say "up from twelfth on the grid" —
        # the single most natural way a commentator frames a driver's race.
        # Empty when the grid was never captured cleanly, and the lines that
        # use it are gated on `_has_grid` so it never airs blank.
        subj = drv or a
        # HIS NAME CARRIES HIS STATUS the first time it is said. Only the
        # player's, and only inside a career: every other name on the grid is
        # a name.
        # WHICH KIND OF LINE THIS IS, so the status form can be used where it
        # belongs and nowhere else. Popped rather than left in the slots: an
        # unconsumed `cat` key would be a template slot named "cat", one typo
        # away from airing.
        _cat = extra.pop("cat", None)
        apt = _cat in STATUS_APT and _cat not in STATUS_SELF

        def nms(c):
            n = nm(c)
            return (self._status_form(s, n, apt=apt)
                    if c is not None and getattr(c, "is_player", False) else n)
        # THE THIRD MAN. `{c}` already meant exactly this in the qualifying
        # wrap ("...and {c} third"), where the caller passes a NAME rather
        # than a car - so this accepts either and folds a car through `nms`
        # like the other two. One slot, one meaning (LAW 17): wherever `{c}`
        # appears it is the third driver in the sentence, and the three-way
        # battle call needs it to carry the player's status form the same way
        # `a` and `b` do.
        kw = {
            "a": nms(a), "b": nms(b), "drv": nms(drv or a),
            "c": c if isinstance(c, str) else nms(c),
            "grid": (spoken_place(getattr(subj, "started_place", 0))
                     if subj is not None else ""),
            # Prefer the resolved circuit name ("Spa-Francorchamps") over
            # rF2's own ("Belgium"), which is often the country or the town.
            "trk": (s.circuit.name if getattr(s, "circuit", None)
                    and s.circuit.known else self._short_track(s.track)),
            "lap": (s.leader_laps or 0) + 1,
            "laps": s.laps_left or 0,
            "cls": (s.player.cls if s.player else ""),
            "series": self._series_name(s),
            "yr": s.era.year if s.era else "",
            "_name": (drv or a or b).name if (drv or a or b) else "",
        }
        kw.update(extra)
        return kw

    def _series_name(self, s):
        """What to call the championship being raced.

        THE CHAMPIONSHIP NAMES ITSELF. THE CAR NEVER NAMES IT.

        This was a live, game-breaking bug and it is worth stating exactly.
        The user started a USF2000 career, and the booth opened qualifying
        with "the 2000 Formula One season" — because this function had no
        access to the career at all (it was a `@staticmethod` taking only the
        session) and fell back to inferring a name from the CAR: `era.classify`
        reads the "2000" in "USF2000" as a year and the chassis as a
        single-seater, so the guess was a Formula One season a quarter of a
        century ago.

        A guess about which championship the user is driving is not a small
        wrongness. It is the line that exists to tell him career mode is
        running, and getting it wrong tells him the overlay has no idea what
        he is doing.

        So the order is: what the CAREER says it is, and only then what the car
        suggests.

          1. THE DIVISION, for a ladder career. "USF2000", "Hot hatch",
             "Formula 3" — the name on his own entry list, which is what he
             asked for: *"they must use the car class name as the title for
             the season"*.
          2. THE LOCKED CAR CLASS of a plain career, for the same reason.
          3. A SERIES era.py actually recognises by name, with its year.
          4. The class of the car on track — a real string off the grid rather
             than a category invented from one.
          5. A discipline word, and only for a season we can genuinely date.

        The old step-5 guess survives at the bottom because it is right for the
        mods it was written for (the 1988 F1 field has no series string and IS
        the 1988 Formula One season), and it can no longer reach a career: by
        the time anything gets that far there is no championship to be wrong
        about.
        """
        career = getattr(self, "season", None)
        if career is not None and getattr(self, "_season_round", None):
            ev = (career.evaluate() or {}) if hasattr(career, "evaluate") else {}
            if ev.get("tier_name"):
                # THE LAST TWO RUNGS CARRY THEIR YEAR. See `ladder.YEAR_RUNGS`
                # for why this is the season exception rather than the layout
                # one: a championship is his to be told about, and the whole
                # climb is pointed at a specific season.
                try:
                    import ladder as _lad
                    prog = career.ladder
                    yr = _lad.named_year(
                        (prog.tier() or {}) if prog is not None else None,
                        getattr(s, "player_era", None) or getattr(s, "era", None))
                except Exception:
                    yr = None
                if yr:
                    return "%d %s" % (yr, ev["tier_name"])
                return ev["tier_name"]
            locked = career.data.get("cls")
            if locked:
                return locked
        e = getattr(s, "player_era", None) or getattr(s, "era", None)
        if e is None:
            return "field"
        if e.series:
            return ("%d %s" % (e.year, e.series)) if e.year else e.series
        cls = getattr(getattr(s, "player", None), "cls", "")
        if cls:
            return cls
        by_disc = {"formula": "Formula One", "f1": "Formula One",
                   "stock": "stock car", "proto": "sportscar",
                   "gt": "GT", "touring": "touring car",
                   "openwheel": "single-seater", "kart": "karting"}
        name = by_disc.get(getattr(e, "discipline", ""), "")
        if e.year and name:
            return "%d %s" % (e.year, name)
        return name or (str(e.year) if e.year else "field")

