"""Draw every panel against a synthetic session. Catches layout crashes
without needing rFactor 2 running."""
import os, sys, tkinter as tk
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import era as era_mod
from overlay_common import TH, UI
from overlay_panel import TCanvas
from overlay_panels import PanelsMixin
from overlay_draw import DrawMixin
from overlay_dash import DashMixin, FuelModel

class C:
    def __init__(s, cid, place, name):
        s.id=cid; s.place=place; s.name=name; s.display_name=name
        s.is_player=(place==4); s.in_pits=False; s.laps=8; s.laps_down=0
        s.gap_ahead=1.2; s.gap_leader=float(place)*1.4; s.gap_behind=1.0
        s.best_lap=71.234+place*0.2; s.last_lap=71.9; s.places_gained=1
        s.last_s1=21.1; s.last_s2=24.3; s.last_s3=25.8
        s.best_s1=21.0; s.best_s2=24.2; s.best_s3=25.7
        s.sector=2; s.purple_lap=(place==1); s.tyre_front='Soft'; s.tyre_rear='Soft'
        s.pos=(place*40.0, place*25.0); s.damage=(0,1,0,0,0,0,0,0)
        s.tyre_wear=(.9,.88,.7,.68); s.tyre_temp=(92,95,101,104)
        s.brake_temp=(420,440,380,395); s.fuel=38.0; s.fuel_cap=100.0
        s.rpm=10500; s.max_rpm=13000; s.gear=5; s.speed=245.0
        s.battery=.6; s.flap=1; s.penalties=0; s.finish_status=0
        s.cls='F1 Test 2025'; s.vehicle=name; s.control=0
        s.blue_flag=False; s.under_yellow=False; s.pit_stops=0
class S:
    def __init__(s, finished=False):
        names=['Verstappen','Russell','Leclerc','Kandasamy','Hamilton','Piastri']
        s.order=[C(i+1,i+1,n) for i,n in enumerate(names)]
        s.cars={c.id:c for c in s.order}; s.player=s.order[3]; s.leader=s.order[0]
        s.valid=True; s.track='HockenheimRing GP'; s.track_len=4574.0
        s.kind='race'; s.green=not finished; s.finished=finished; s.started=True
        s.max_laps=17; s.laps_left=9; s.leader_laps=8; s.num_cars=len(s.order)
        s.session_index=10; s.multiclass=False; s.classes=['F1 Test 2025']
        s.full_course_yellow=False; s.yellow_sectors=(0,0,0); s.yellow=0
        s.time_left=None; s.phase_name='green'
        s.best_s1=21.0; s.best_s2=24.1; s.best_s3=25.6
        s.best_lap_time=71.0; s.best_lap_driver='Verstappen'
        s.era=era_mod.classify('F1 Test 2025','Max'); s.player_era=s.era
    def car_ahead(s,c):
        i=c.place-1; return s.order[i-1] if 0<i<len(s.order) else None
    def car_behind(s,c):
        i=c.place-1; return s.order[i+1] if 0<=i<len(s.order)-1 else None

root=tk.Tk(); root.withdraw()
cv=tk.Canvas(root,width=1920,height=1080); 
UI.k=1.25
TH.apply(era_mod.skin_for(era_mod.classify('F1 Test 2025','Max')))

class Host(DrawMixin, PanelsMixin, DashMixin):
    def __init__(s):
        import tkinter.font as tkfont
        s.root=root; s.game_rect=(0,0,1920,1080)
        for n,sz in (('f_speed',26),('f_speed_sm',14),('f_gear',22),('f_gear_sm',14),('f_gear_big',38),
                     ('f_small',10),('f_row',10),('f_tiny',8),('f_logo',17),('f_logo_sm',12)):
            setattr(s,n,('Arial',int(sz*1.25),'bold') if 'speed' in n or 'gear' in n or n in('f_small','f_logo','f_logo_sm') else ('Arial',int(sz*1.25)))
        s.logo_img=None; s.logo_w=0
        s.tower_rows=16; s.relative_rows=3; s.tower_interval=True
        s.show_dash=True; s.show_sectors=True; s.show_map=True
        s.booth_enabled=True; s.radio_enabled=True; s.rival_enabled=True
        s.show_tower=True; s.show_relative=True; s.menu_open=True
        s.fuel_model=FuelModel(); s.fuel_model.laps=[2.4,2.5]
        s.cfg={}; s._panels_drawn=[]
        s.menu_page='main'; s._menu_confirm=None; s._menu_preset='f1_2025'
        s._menu_rounds=0; s._menu_offset=0
        import career as _c; s.career=_c.History()
        s.tracker=type('T',(),{'display_name':None})()
        s.season=None; s.season_record=True
    def _begin_panel(s,name,x,y,w,h,clickable=False):
        s._panels_drawn.append((name,int(w),int(h),int(x),int(y)))
        class P:
            def canvas_at(self,ox,oy): return TCanvas(cv,ox,oy)
        return P()
    def _hide_panel(s,n): pass
    def _dash_reserved(s): return 300

h=Host()
fails=[]
def check(c, l, e=""):
    print(("  [ OK ] " if c else "  [FAIL] ") + l + (("  " + e) if e else ""))
    if not c:
        fails.append(l)

def try_draw(label, fn, *a):
    try:
        fn(*a); print("  [ OK ] %s" % label)
    except Exception as e:
        import traceback; print("  [FAIL] %s -> %s" % (label, e))
        traceback.print_exc(); fails.append(label)

print("\nRACE IN PROGRESS")
s=S()
for lbl,fn in (('header',h.draw_header),('tower',h.draw_tower),('relative',h.draw_relative),
               ('flags',h.draw_flags),('dash',h.draw_dash),('sectors',h.draw_sectors),
               ('map',h.draw_map),('podium',h.draw_podium)):
    try_draw(lbl, fn, s)
try_draw('settings menu', h.draw_settings)
# The menu has to be reachable with NO session at all — that is when a career
# gets configured, and it used to be skipped by the same early return that
# hides the broadcast panels.
h._panels_drawn = []
try_draw('menu with no session', h.draw_menu_button)
try_draw('menu page with no session', h.draw_settings)
check_no_session = [n for n, *_ in h._panels_drawn]
check(("menubtn" in check_no_session and "menu" in check_no_session),
      "the menu draws with no session loaded", str(check_no_session))
# The caption box must sit on the bottom edge beside the map, clear of the
# dash, and out of the centre where the driver is looking.
h.tts = type('T', (), {'now_playing': ('PLAY',
    'Verstappen goes through on Russell and it is a lead change here at '
    'Hockenheim with fifteen laps still to run!', 0.0)})()
try_draw('caption box', h.draw_caption, 0.0)
# Every page of the menu has to draw, including the ones reached only after a
# destructive click.
# THE INBOX PAGES NEED REAL POST. With no career the only branch that ever
# draws is "No career loaded" — and the layout risk here is the opposite case:
# a two-paragraph letter is by far the tallest thing this panel ever renders.
import shutil as _shutil, tempfile as _tempfile
import season as _S, inbox as _inbox
from overlay_panels import MAIL_WRAP as _WRAP
_S.CAREER_DIR = _tempfile.mkdtemp(prefix="factortv_panel_")
h.season = _S.create("open", me="Kandasamy", rounds=3,
                     ladder_path="single_seater", tier_index=2)
for _i, _p in enumerate([2, 1, 1], 1):
    h.season.record({"n": _i, "slug": "t%d" % _i, "pos": _p, "laps": 20,
                     "race_laps": 20,
                     "classified": [("Kandasamy", _p),
                                    ("A Rival", 1 if _p != 1 else 2)]})
_inbox.refresh(h.season)
h._mail_open = _inbox.messages(h.season)[0]["id"]
h._mail_offset = 0
try_draw('inbox button', h.draw_inbox_button)
# THREE MODES, AND THEY ARE DIFFERENT GAMES. The badge is the only thing on
# screen that says which one is running, so all three states must draw.
h.menu_open = False
try_draw('mode badge (campaign)', h.draw_mode_badge)
_was = h.season; h.season = None
try_draw('mode badge (no career)', h.draw_mode_badge)
h.season = _S.create("open", me="Kandasamy", rounds=5)
try_draw('mode badge (plain season)', h.draw_mode_badge)
check(not h.season.on_ladder, "a plain season is not a campaign")
# A CAREER LOADED, AND A RACE THAT IS NOT ONE OF ITS ROUNDS. Nothing will be
# recorded and the booth will say nothing about the championship — and the
# driver has to be able to SEE that before the green flag rather than work it
# out afterwards from a standings table that did not move.
h.season = _was
h._season_armed = True
h._season_round = None
try_draw('mode badge (off-career)', h.draw_mode_badge)
h._season_round = {"n": 1, "slug": "x"}
h._season_armed = False
h.season = _was
h.menu_open = True
check(any(n == 'inboxbtn' for n, *_ in h._panels_drawn),
      "the envelope draws once a career exists")
h.menu_page = 'mail'
_rows = h._rows_mail()
_long = [r['label'] for r in _rows
         if r.get('kind') == 'text' and len(r['label']) > _WRAP]
check(not _long, "every line of a letter fits the column", str(_long[:2]))
check(sum(1 for r in _rows if r.get('kind') == 'text') >= 8,
      "and a letter is long enough to be one",
      str(sum(1 for r in _rows if r.get('kind') == 'text')))
h.menu_page = 'main'
for page in ('career','career_new','career_len','career_cls','career_name','career_load','career_delete','career_path','career_plen','career_ladder','career_nextlen','inbox','mail','record','divisions','legal','confirm'):
    h.menu_page=page
    h._menu_confirm=("Delete 'F1 2025'?","del_now","x")
    try_draw('menu page: %s' % page, h.draw_settings)
h.menu_page='main'

# The record and divisions views read STRAIGHT from the same objects the rules
# use, so a wrong row here means the screen and the rules disagree.
h.menu_page = 'record'
_rec = h._rows_record()
check(any(r['label'] == 'Wins' for r in _rec),
      "the record view names his totals",
      str([r['label'] for r in _rec][:7]))
check(any(r['label'] == 'Career' and '%' in str(r.get('note')) for r in _rec),
      "and shows career progress as a percentage",
      str([r.get('note') for r in _rec][:3]))
_div = h._rows_divisions()
check(sum(1 for r in _div if 'racing now' in str(r.get('note'))) == 1,
      "the divisions view marks exactly one rung as current",
      str([r.get('note') for r in _div]))
check(any('needs P' in str(r.get('note', '')) for r in _div),
      "and says what a locked rung would cost",
      str([r.get('note') for r in _div]))
h.menu_page = 'main'

_shutil.rmtree(_S.CAREER_DIR, ignore_errors=True)

print("\nNEW MAIL: A TONE AND A BUBBLE")
# Both are triggered by the unread count GOING UP rather than by a flag,
# because mail is generated in three different places — a banked result, the
# panel refreshing, the story — and a flag would have to be set correctly in
# all three.
import time
import overlay_panels as _op
_played = []
class _TTS:
    speaking = False
    def play_file(self, path, **kw):
        _played.append(os.path.basename(path))
h.tts = _TTS()
h.season = _was
h._inbox_seen = None
h._inbox_flash = 0
h.draw_inbox_button()          # first frame just learns the count
check(not _played, "nothing sounds on the first frame — that is not new mail",
      str(_played))
_inbox.read_all(h.season)
h.draw_inbox_button()
check(not _played, "and nothing sounds when the count goes DOWN")
h.season.data["mail"].append(
    {"id": "ping", "kind": "beat", "feed": "mail", "from": "Mel",
     "subject": "s", "body": ["a", "b"], "when": 1, "round": 0,
     "read": False})
h._panels_drawn = []
h.draw_inbox_button()
check(_played == ["mail.wav"], "a letter arriving sounds once", str(_played))
check(time.time() - h._inbox_flash < 1.0, "and raises the bubble")
h.draw_inbox_button(); h.draw_inbox_button()
check(_played == ["mail.wav"], "and only once, however many frames follow",
      str(_played))

# MAIL IS NEVER URGENT. A sting interrupts on purpose; this does the opposite.
h.tts.speaking = True
h.season.data["mail"].append(
    {"id": "ping2", "kind": "beat", "feed": "mail", "from": "Mel",
     "subject": "s", "body": ["a", "b"], "when": 1, "round": 0,
     "read": False})
h.draw_inbox_button()
check(_played == ["mail.wav"],
      "NOTHING SOUNDS OVER THE COMMENTARY — the bubble does the work alone",
      str(_played))
check(os.path.exists(os.path.join(_op._STING_DIR, _op.MAIL_SOUND)),
      "and the tone is actually shipped", _op.MAIL_SOUND)
h.tts.speaking = False

print("\nTHE CORNER DOES NOT OVERLAP ITSELF")
# THE BUG THIS EXISTS FOR: `draw_status` was written to clear a single 30px
# hamburger; the envelope was later added into exactly the gap it was leaving,
# and the mode badge went under both. On a loading screen — which is precisely
# when the status box is on show — it sat on top of the one control the user
# needed at that moment, and the user could "barely even see the email button".
#
# Every panel that lives in the top-left is now measured from one shared strip
# (`overlay_common.CONTROL_*`), and this checks the rectangles rather than the
# arithmetic, because the arithmetic was what was wrong.
class _NoCars:
    valid = True
    num_cars = 0
    track = "Road America"
    on_air = True
    circuit = None

h._panels_drawn = []
h.menu_open = False
h.draw_menu_button()
h.draw_inbox_button()
h.draw_mode_badge()
h.draw_status(_NoCars(), True)
corner = [(n, x, y, x + w, y + hh) for n, w, hh, x, y in h._panels_drawn]
bad = []
for i, (n1, ax0, ay0, ax1, ay1) in enumerate(corner):
    for n2, bx0, by0, bx1, by1 in corner[i + 1:]:
        if ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1:
            bad.append("%s x %s" % (n1, n2))
check(not bad, "no two corner panels share a pixel", str(bad))
check(len(corner) == 4, "and all four of them drew",
      str([n for n, *_ in corner]))
# The open menu drops below the whole strip, not on top of the badge.
h.menu_open = True
h._panels_drawn = []
h.draw_settings()
menu = [r for r in h._panels_drawn if r[0] == "menu"]
if menu:
    _n, _w, _hh, _x, _y = menu[0]
    from overlay_common import CONTROL_H as _CH, EDGE as _E
    check(_y >= UI(_E) + UI(_CH), "the menu opens below the strip, not over it",
          "%d vs %d" % (_y, UI(_E) + UI(_CH)))
h.menu_open = True

print("\nTHE SEASON HAS TO BE READABLE, BECAUSE A SIM IS NEVER WATCHED")
# The user, after simulation went in: "one thing I see missing now that I can
# simulate is the option to see previous race results, and also a
# championship standings option."
#
# He is right, and it is a consequence of the feature: a race he drove he
# watched, but a simulated round produced positions and points and nothing
# else. Without these two pages the sim banks a result into a table nobody
# can read.
h.season = _S.create("open", me="Kandasamy", rounds=5,
                     ladder_path="touring", tier_index=0)
for _n in (1, 2, 3):
    h.season.record({"n": _n, "slug": "t%d" % _n, "pos": _n, "laps": 20,
                     "race_laps": 20,
                     "classified": [("Kandasamy", _n), ("A Rival", 1),
                                    ("B Rival", 2), ("C Rival", 3)]})
h.season.simulate_round(n=4, slug="t4", event="Round 4",
                        names=["A Rival", "B Rival", "C Rival"])

_st = h._rows_standings()
check(any("pts" in (r.get("note") or "") for r in _st),
      "the championship page shows a points table")
check(any("Kandasamy" in (r.get("label") or "") for r in _st),
      "with him in it")

_rs = h._rows_results()
check(len([r for r in _rs if "Round" in (r.get("label") or "")
           or r.get("note", "").startswith("P")]) >= 4,
      "the results page lists every round")
# A SIMULATED ROUND SAYS SO. Hiding it would claim he drove races he did not.
check(any("(sim)" in (r.get("note") or "") for r in _rs),
      "and a simulated round is marked as one",
      str([r.get("note") for r in _rs]))

# BOTH PAGES MUST BE REACHABLE. A nav key that is not in the router lands on
# the main menu, which looks like the button doing nothing.
for _k, _want in (("page_standings", "standings"), ("page_results", "results")):
    h.menu_page = "career"
    h._menu_hit(_k)
    check(h.menu_page == _want, "%s routes to %s" % (_k, _want), h.menu_page)
h.menu_page = "main"

try_draw("standings page", h.draw_settings)
h.menu_page = "results"
try_draw("results page", h.draw_settings)
h.menu_page = "main"


print("\nTHE RESULT CARD SAYS WHICH RESULT IT IS")
# It said "RACE RESULT" after a qualifying session. The panel was written
# for the flag at the end of a race and then reused for the end of every
# session - the right reuse and the wrong caption.
import overlay_panels as _op2
_cap = []
class _Cap(TCanvas.__bases__[0] if TCanvas.__bases__ else object):
    pass
_real_text = TCanvas.create_text
def _spy(self, *a, **k):
    if k.get("text"):
        _cap.append(str(k["text"]))
    return _real_text(self, *a, **k)
TCanvas.create_text = _spy
try:
    for _kind, _want in (("race", "RACE RESULT"),
                         ("quali", "QUALIFYING RESULT"),
                         ("practice", "PRACTICE RESULT")):
        _cap[:] = []
        _s = S(finished=True); _s.kind = _kind
        h.draw_podium(_s)
        check(_want in _cap, "a %s session says %r" % (_kind, _want),
              str([t for t in _cap if "RESULT" in t]))
finally:
    TCanvas.create_text = _real_text


print("\nTHE DIVISION MARK SITS IN A GAP THAT ALREADY EXISTED")
# The top right belongs to the RELATIVE panel — that is why the inbox went
# top left when it was built. The division logo is allowed up there only
# because the relative panel starts 78 logical pixels down and nothing draws
# in the band above it.
#
# Checked as arithmetic on the constants rather than by rendering, because
# rendering it needs the user's own Pictures folder and a test that depends
# on somebody's photographs is a test that fails on a clean machine.
from overlay_common import EDGE as _EDGE
# No box any more — the mark is composited straight onto the chroma key, so
# the only things between the screen edge and the relative panel are the
# margin and the mark itself.
_logo_bottom = UI(_EDGE) + UI(_op.PanelsMixin.LOGO_H)
_rel_top = UI(78)
check(_logo_bottom <= _rel_top,
      "the division logo clears the relative panel",
      "logo ends %d, relative starts %d" % (_logo_bottom, _rel_top))

# ...AND IT IS NEVER DRAWN FOR SOMEBODY WHO IS NOT IN A DIVISION. A one-off
# race, or a plain season with no ladder, has no division to have a mark for
# — and showing the last one would be a claim about which championship he is
# driving in, which is the mistake this product has already made once.
h._panels_drawn = []
h.season = None
h.draw_division_logo()
check(not [r for r in h._panels_drawn if r[0] == "divlogo"],
      "no career, no mark")


class _PlainSeason:
    on_ladder = False
    def evaluate(self):
        return {}


h.season = _PlainSeason()
h._panels_drawn = []
h.draw_division_logo()
check(not [r for r in h._panels_drawn if r[0] == "divlogo"],
      "a season with no ladder has no division mark either")


# ...AND IT DOES DRAW FOR A DIVISION THAT HAS ONE, IN A RACE.
#
# The mark is a permanent piece of furniture, not a menu decoration: it is
# drawn from BOTH branches of the frame in `factor_tv`, the one that runs with
# no session and the one that runs during a race. The image is stubbed here so
# this passes on a machine with no photographs on it — what is being tested is
# the wiring, not the user's folders.
import newsart as _newsart
_real_logo = _newsart.logo
_stub = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "icon_helmet_1.png")


class _LadderSeason:
    on_ladder = True
    name = "Formula 3"
    def evaluate(self):
        return {"tier_name": "Formula 3"}


try:
    _newsart.logo = lambda name: _stub if os.path.exists(_stub) else None
    h.season = _LadderSeason()
    h._panels_drawn = []
    h.draw_division_logo()
    drew = [r for r in h._panels_drawn if r[0] == "divlogo"]
    check(bool(drew) or not os.path.exists(_stub),
          "a ladder division with a mark draws it", str(drew))
    # The frame draws it in the racing path as well as the menu path — the
    # user asked for it in a race specifically, and a call site is the only
    # thing that can answer that.
    _src = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "factor_tv.py"), encoding="utf-8").read()
    check(_src.count("self.draw_division_logo()") >= 2,
          "and the frame draws it in a session as well as out of one",
          "%d call sites" % _src.count("self.draw_division_logo()"))
finally:
    _newsart.logo = _real_logo
    h.season = None

print("\nNO PANEL IS EVER PLACED OFF THE DESKTOP")
# Reported twice: the division's mark cut off by the right-hand edge of the
# screen. Every panel is positioned from `game_rect`, so all twenty of them are
# one bad rect away from the same fault — and `Panel.place` is the only place in
# the product that actually puts a window somewhere, so the guard belongs there
# rather than in the twenty callers.
from overlay_panel import clamp_to_screen as _clamp

_one = (0, 0, 1920, 1080)
check(_clamp(1719, 22, 179, 70, _one) == (1719, 22),
      "a panel that already fits is not moved")
check(_clamp(1850, 22, 179, 70, _one) == (1741, 22),
      "one hanging off the right edge is pulled back to touch it",
      str(_clamp(1850, 22, 179, 70, _one)))
check(_clamp(-40, -10, 200, 100, _one) == (0, 0),
      "and one off the top left is pulled back the other way",
      str(_clamp(-40, -10, 200, 100, _one)))
# THE VIRTUAL DESKTOP, NOT THE PRIMARY MONITOR. A game on a second screen draws
# legitimately outside the primary one, and clamping to it would drag every
# panel off the game and onto the wrong display — a worse bug than the one this
# fixes.
_two = (0, 0, 3840, 1080)
check(_clamp(3600, 22, 179, 70, _two) == (3600, 22),
      "a panel on a second monitor is left where it is",
      str(_clamp(3600, 22, 179, 70, _two)))
# UNKNOWN BOUNDS MEAN DO NOT MOVE ANYTHING. A bad reading would relocate the
# whole overlay, and a panel in the wrong place is worse than one hanging off an
# edge.
check(_clamp(5000, 5000, 100, 100, (0, 0, 0, 0)) == (5000, 5000),
      "and nothing is clamped against bounds we could not read")
# A panel BIGGER than the desktop keeps its origin: the top-left is the half
# with the labels on it.
check(_clamp(0, 0, 4000, 2000, _one) == (0, 0),
      "an oversized panel is not centred")


print("\nTHE END OF A SEASON IS THE ONE THING THE MENU MUST NOT WHISPER")
# The user simulated a karting season to its end and nearly missed the row that
# takes the Formula 4 seat: it was reachable only through settings -> Career,
# nine rows down, drawn exactly like every other row. A campaign that cannot
# continue without him has to SAY so — on screen, and on the screen he already
# opens between sessions.


# A REAL CAREER, NOT A FAKE. This is the page that reads the store through
# `inbox.refresh` / `news.refresh` on every draw, so a shim with the four
# attributes the row code happens to touch would prove nothing about the screen
# (LAW 0). Two cars and two rounds is a whole karting season won.
import shutil as _shutil, tempfile as _tempfile
import season as _S
_old_dir = _S.CAREER_DIR
_S.CAREER_DIR = _tempfile.mkdtemp(prefix="factortv_panel_")


def _ladder_career(results, length=2):
    car = _S.create("open", me="Dante Kandasamy", rounds=length,
                    ladder_path="single_seater", tier_index=0)
    car.data["nationality"] = "Australia"
    for i, pos in enumerate(results, start=1):
        car.record({"n": i, "slug": "trk%d" % i, "pos": pos,
                    "laps": 20, "race_laps": 20,
                    "classified": [("Dante Kandasamy", pos),
                                   ("A Rival", 1 if pos != 1 else 2)]})
    return car


try:
    _done = _ladder_career([1, 1])
    _mid = _ladder_career([1])
    check(h._ladder_waiting(_done) is not None,
          "a completed ladder season is a decision waiting")
    check("Formula 4" in h._waiting_label(h._ladder_waiting(_done)),
          "and the tell NAMES the seat rather than 'something is waiting'",
          h._waiting_label(h._ladder_waiting(_done)))
    check(h._ladder_waiting(_mid) is None,
          "a season still running is not asking him for anything")

    # THE ROUTE HE ASKED FOR: on the inbox page, and marked.
    h.season = _done
    h._mail_feed = "mail"
    _rows = h._rows_inbox()
    _seat = [r for r in _rows if r.get("key") == "page_ladder"]
    check(bool(_seat), "the end-of-season decision is ON THE INBOX PAGE")
    check(bool(_seat) and _seat[0].get("hot"),
          "and it is drawn hot, which no other row on the page is")
    # ...AND IT IS NOT A MESSAGE. The archive stays a uniform list of subject
    # lines, because that is the mechanism the story's ending depends on. A
    # career decision is chrome; the moment it gets an id it has become mail.
    _msgs = [r for r in _rows if str(r.get("key", "")).startswith("mail:")]
    check(bool(_msgs), "the letters are there to be flagged in the first place",
          "%d messages" % len(_msgs))
    check(all(not r.get("hot") and not r.get("danger") for r in _msgs),
          "and no LETTER is flagged, ever",
          "%d flagged" % len([r for r in _msgs if r.get("hot")]))

    # THE OLD CAREER PAGE IS GONE — it was thirty grey rows of sentences and the
    # dashboard replaced it. The decision is checked on the dashboard below.
    # THE DASHBOARD MARKS IT TOO, and the settings row that used to is gone with
    # the career page — the career is not a setting. The surface that carries the
    # tell on screen is now the trophy button, which is drawn with a ring around
    # it whenever a decision is waiting.
    h.menu_page = "dash"
    _drows = h._rows_dash()
    check(any(r.get("key") == "page_ladder" and r.get("hot")
              for r in _drows),
          "the dashboard marks the decision as well",
          str([r.get("key") for r in _drows if r.get("hot")]))
    # ON THE SETTINGS PAGE, which is what this is about — the dashboard itself
    # links to Manage career and is supposed to.
    h.menu_page = "main"
    _srows = h._menu_rows()
    check(not any(str(r.get("key", "")).startswith("page_career")
                  for r in _srows),
          "and the career has left the settings page entirely",
          str([r.get("key") for r in _srows]))
    check(not any(r.get("key") == "page_inbox" for r in _srows),
          "along with the post, which lives in the dashboard now")

    # A DIVISION IS NOT THE SAME SIZE OF COMMITMENT AS THE ONE ABOVE IT.
    #
    # Asked for: "can we not choose race length also when we get a promotion?
    # for example if I want to do only a 3 race season for karting but then a 5
    # race season for F4." `advance(rounds=)` and `_start_rung` have taken a
    # length since the ladder was wired and nothing ever passed one, so every
    # rung inherited the number chosen once at the top of the career.
    #
    # DRIVEN THROUGH THE REAL CLICKS, not by calling `advance` directly — the
    # part that was missing was the MENU, so a test that skips the menu tests
    # the half that already worked (LAW 0, in its usual costume).
    short = _ladder_career([1, 1, 1], length=3)
    h.season = short
    h.menu_page = "career_ladder"
    _lrows = h._rows_ladder()
    check(any(r.get("key") == "page_nextlen" for r in _lrows),
          "the end-of-season page offers the next season's length",
          str([r.get("key") for r in _lrows]))
    check(h._next_length(short) == 3,
          "and it defaults to the length he has been racing",
          str(h._next_length(short)))
    h._menu_hit("page_nextlen")
    check(h.menu_page == "career_nextlen", "the length page opens")
    _keys = [r.get("key") for r in h._rows_nextlen()]
    check("nextlen:5" in _keys and "nextlen:0" in _keys,
          "with the other lengths and 'same as this season' on it", str(_keys))
    h._menu_hit("nextlen:5")
    check(h.menu_page == "career_ladder" and h._next_length(short) == 5,
          "picking one comes back with it chosen", str(h._next_length(short)))
    h._menu_hit("adv:promote")
    check(h.menu_page == "confirm", "taking the seat still confirms first")
    check("5 races" in (h._menu_confirm or ("",))[0],
          "and the confirmation SAYS how long the next season is",
          (h._menu_confirm or ("",))[0])
    h._menu_hit("confirm_yes")
    check(short.name == "Formula 4" and short.total_rounds == 5,
          "a 3-race karting season promotes into a 5-race Formula 4",
          "%s / %s rounds" % (short.name, short.total_rounds))
    check(short.data["ladder_history"][0]["rounds"] == 3,
          "and karting is archived at the length it was actually run",
          str(short.data["ladder_history"][0]["rounds"]))
    # SPENT ON THE SEASON IT WAS CHOSEN FOR. A pending length left lying around
    # would re-apply at the next promotion — a length he picked two divisions
    # ago, silently.
    check(getattr(h, "_next_len", None) is None,
          "the choice is spent, not remembered into the division after")
    check(h._next_length(short) == 5,
          "so the default is now the season he is actually racing",
          str(h._next_length(short)))
    # IGNORING THE PAGE CHANGES NOTHING, which is what makes this safe to add:
    # a driver who never opens it gets the behaviour the career had before.
    same = _ladder_career([1, 1, 1], length=3)
    h.season = same
    h._menu_hit("adv:promote")
    h._menu_hit("confirm_yes")
    check(same.total_rounds == 3,
          "and a promotion nobody asked a question about keeps the old length",
          str(same.total_rounds))

    # THE BADGE ON SCREEN, and the CAMPAIGN branch was UNREACHABLE — it sat
    # inside the OFF-CAREER branch below an unconditional reassignment, so a
    # ladder career racing a real round was labelled SEASON and OFF-CAREER
    # could never be shown at all.
    _texts = []
    _real_ct = TCanvas.create_text
    def _spy_ct(self, x, y, **kw):
        _texts.append(str(kw.get("text", "")))
        return _real_ct(self, x, y, **kw)
    TCanvas.create_text = _spy_ct
    h.menu_open = False
    h.season = _done
    h.draw_mode_badge()
    check(any("SEASON OVER" in t for t in _texts),
          "the badge says SEASON OVER while a seat is waiting", str(_texts))
    h.season = _mid
    h._season_round = 2
    h._season_armed = True
    del _texts[:]
    h.draw_mode_badge()
    check(any("CAMPAIGN" in t for t in _texts),
          "a ladder career in a real round is a CAMPAIGN, not a SEASON",
          str(_texts))
    h._season_round = None
    del _texts[:]
    h.draw_mode_badge()
    check(any("OFF-CAREER" in t for t in _texts),
          "and a race that is not one of its rounds says OFF-CAREER",
          str(_texts))
finally:
    TCanvas.create_text = _real_ct
    h.season = None
    h._season_round = None
    h._season_armed = False
    _S.CAREER_DIR = _old_dir

print("\nVOLUME: A KNOB THAT ACTUALLY TURNS SOMETHING")
# IT WAS DEAD. `Tts.volume` had been stored since the class was written and
# read by nothing at all — the same shape as the deleted `cast.intensity_voice`
# — so anybody who lowered it heard no difference and would reasonably decide
# the setting was broken. It was.
import tts as _tts, wave as _wave, array as _array
import shutil as _sh, tempfile as _tf
_d = _tf.mkdtemp(); _src = os.path.join(_d, "t.wav")
_sh.copy(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "stings", "mail.wav"), _src)
_t = _tts.Tts.__new__(_tts.Tts)
def _peak(p):
    with _wave.open(p, "rb") as r:
        a = _array.array("h"); a.frombytes(r.readframes(r.getnframes()))
    return max(abs(x) for x in a)
_t.volume = 1.0
check(_t._scaled(_src) == _src, "full volume touches nothing at all")
_t.volume = 0.5
check(_peak(_t._scaled(_src)) < _peak(_src) * 0.6,
      "half volume is audibly quieter",
      "%d -> %d" % (_peak(_src), _peak(_t._scaled(_src))))
_t.volume = 0.0
check(_peak(_t._scaled(_src)) == 0, "and zero is silent")
_t.volume = 0.5
check(_t._scaled(_src) == _t._scaled(_src),
      "the scaled copy is cached rather than rebuilt per line")
_sh.rmtree(_d, ignore_errors=True)

h.menu_page = "main"
h.cfg["volume"] = 0.6
rows = h._menu_rows()
sl = [r for r in rows if r.get("kind") == "slider"]
check(len(sl) == 1, "the menu has a volume slider", str(len(sl)))
check("60%" in str(sl[0].get("note")), "showing the current level",
      str(sl[0].get("note")))
h.tts = type("T", (), {"set_volume": lambda s, v: None})()
h._menu_slide("vol", 0.33)
check(abs(h.cfg["volume"] - 0.35) < 0.01,
      "and a click sets it, rounded to a 5% step", str(h.cfg["volume"]))

print("\nYOUR OWN DRIVER NAMES")
# Neither source the picker draws on can contain a name he invented: one is
# what rF2 reported in his results, the other is the record book.
import drivers as _drv
check("Dante Kandasamy" in _drv.my_names() and "Over Boy" in _drv.my_names(),
      "the names file is read", str(_drv.my_names()))
# The MENU is where his names are stacked on top of the knowledge base —
# `picker_names` itself stays the pure "who is really on this grid" answer,
# which drivertest.py holds it to.
h.menu_page = "career_name"
h.season = _was
h._menu_offset = 0
_rows = h._rows_name()
_listed = [r["label"] for r in _rows if str(r.get("key", "")).startswith("name:")]
check(_listed[:2] == _drv.my_names(),
      "his own names come first in the picker, ahead of the real ones",
      str(_listed[:3]))
check(len(_listed) == len(set(_listed)), "with nothing listed twice")
h.menu_page = "main"

# THE DISCLAIMER HAS TO BE FINDABLE. The news feed dramatises rivalries and
# invents quotes; a disclaimer filed three menus away from the thing it is
# about is a disclaimer for the author's benefit rather than the reader's.
h.menu_page = "main"
_main = [r.get("key") for r in h._menu_rows()]
check("page_legal" in _main, "the disclaimer is on the main menu", str(_main))
h.menu_page = "inbox"
h._mail_feed = "news"
_news = [r.get("key") for r in h._rows_inbox()]
check("page_legal" in _news, "and on the news tab, where the fiction is",
      str(_news[:4]))
h._mail_feed = "mail"
h.menu_page = "legal"
_words = " ".join(r["label"] for r in h._rows_legal()).lower()
check("fiction" in _words and "not real statements" in _words,
      "and it says plainly what it is disclaiming", _words[:70])
h.menu_page = "main"

# NOTHING THE DASH DRAWS MAY LAND OUTSIDE ITS OWN COLUMN.
#
# The gear block on the period dials is drawn OUTSIDE the dial, to the left,
# and the column did not know. Tightening the card clipped it against the
# border on every pre-1980 car — the user saw it before this test did, which is
# the whole reason the check now exists. It measures the geometry rather than
# the drawing, so it holds at any UI scale.
import overlay_dash as _D
for _cls in ("Brabham 1966", "F1 1988 Historic Edition", "GT3 World Series",
             "F1 Test 2025", "NASCAR"):
    _e = era_mod.classify(_cls, "")
    TH.apply(era_mod.skin_for(_e))
    _col, _left = h.gauge_col(_e)
    _r = h.gauge_r
    _shift = _left - (_col - 2 * h.gauge_clear - _left)
    _cx = _shift / 2.0 + _col / 2.0          # centre, relative to the column
    if TH.dial == "analogue":
        # The gear text is centred at cx - r - UI(24); allow half a glyph.
        _edge = _cx - _r - UI(24) - UI(12)
        check(_edge >= 0, "%s: the gear block stays inside its column" % _cls,
              "%.0fpx over" % -_edge)
    _right = _col - (_cx + h.gauge_clear)
    check(_right >= -1, "%s: and the instrument does too" % _cls,
          "%.0fpx over" % -_right)
TH.apply(era_mod.skin_for(era_mod.classify("F1 Test 2025", "Max")))

print("\nAFTER THE FLAG")
s2=S(finished=True)
try_draw('podium', h.draw_podium, s2)

print("\nSHIFT CUE")
import gauge as _g, overlay_dash as _D
# EVERY gauge must have one. The needle dials were gated out of it, which
# left the 1970s and 1960s cars — the ones with no rev ladder to read — as
# the only instruments with no shift cue at all.
_missing, _same = [], []
for _style, _sp in _D.GAUGE_SPECS.items():
    _mid = (_sp["shift_from"] + _sp["shift_to"]) / 2.0
    _cold = _g.render(_style, _sp, 120, 120, 0.60, _sp["redline_at"])
    _hot = _g.render(_style, _sp, 120, 120, _mid, _sp["redline_at"])
    _over = _g.render(_style, _sp, 120, 120, 0.995, _sp["redline_at"])
    if list(_cold.getdata()) == list(_hot.getdata()):
        _missing.append(_style)
    if list(_hot.getdata()) == list(_over.getdata()):
        _same.append(_style)
check(not _missing, "every gauge changes at the shift point", repr(_missing))
# ...and "shift now" must never look like "you are over it", which is the one
# distinction the cue exists to draw. The WEC and DTM shift colour was red —
# the same as the limiter colour — so the two states were identical.
check(not _same, "and the limiter never looks identical to the shift window",
      repr(_same))
_bad = [k for k, _p in _g.GAUGE_COLORS.items()
        if _p["shift"].lower() == _p["red"].lower()]
check(not _bad, "no palette uses one colour for both", repr(_bad))

print("\nPANEL GEOMETRY (1920x1080 @ 1.25x)")
seen={}
for name,w,ht,x,y in h._panels_drawn: seen[name]=(w,ht,x,y)
for name,(w,ht,x,y) in sorted(seen.items()):
    off = "  <-- OFF SCREEN" if (x<0 or y<0 or x+w>1920 or y+ht>1080) else ""
    print("  %-10s %4dx%-4d at (%4d,%4d)%s" % (name,w,ht,x,y,off))
    if off: fails.append(name+" offscreen")

print("\nLAW 9 — NO MIXIN METHOD IS DEFINED TWICE")
# `BoothMixin._kw` once shadowed `RadioMixin._kw` and the engineer read a
# Python repr aloud on air. `_gap` and `_lap` were the same violation sitting
# quietly: byte-identical copies in both mixins, so the MRO resolved BOTH to
# the booth's and editing the radio's changed nothing at all, silently.
#
# This walks the real mixins rather than checking two names, so the next
# duplicate is caught the day it is written.
import overlay_booth as _ob, overlay_radio as _or, overlay_rival as _ov
MIXINS = [("BoothMixin", _ob.BoothMixin), ("RadioMixin", _or.RadioMixin),
          ("RivalMixin", _ov.RivalMixin)]
own = {}
for _name, _cls in MIXINS:
    for _attr, _val in vars(_cls).items():
        if _attr.startswith("__"):
            continue
        if callable(_val) or isinstance(_val, staticmethod):
            own.setdefault(_attr, []).append(_name)
clash = {a: w for a, w in own.items() if len(w) > 1}
check(not clash,
      "no method name is defined by two mixins that share a host",
      str(sorted(clash.items())[:3]))

# ...and the shared helpers really do live in ONE place now.
from overlay_common import spoken_gap, spoken_lap, fmt_lap
check(spoken_gap(0.2) == "2 tenths" and spoken_gap(2.5) == "2.5 seconds"
      and spoken_gap(0.01) == "right on your tail" and spoken_gap(None) == "--",
      "spoken_gap reads the way a commentator says a gap")
check(spoken_lap(91.234) == "1:31.234" and spoken_lap(None) == "",
      "and spoken_lap returns EMPTY for no time, not a placeholder",
      repr(spoken_lap(None)))
# `fmt_lap` is the panel's version and must keep its placeholder — a caption
# reads "--:--.---" fine and a synthesiser does not.
check(fmt_lap(None) == "--:--.---",
      "while fmt_lap keeps the dashes, because a PANEL wants them")

# THE OTHER TAB HAS TO ANNOUNCE ITSELF. Reported as "there was NO news reports
# about it either" — about a career whose save held the piece, on the news feed,
# as the newest item in it. It was one tab away, and nothing on the screen said
# so while the inbox he WAS looking at collected six letters about the same
# weekend.
import inbox as _ibx
_fc = h.season
if _fc is not None:
    h.menu_page = "inbox"
    h._mail_feed = "mail"
    # ONE UNREAD NEWS ITEM, injected so the badge branch is actually exercised —
    # a fixture with an empty news feed only ever tests the quiet case.
    _fc.data.setdefault("mail", []).append(
        {"kind": "news_prog_callup", "feed": "news", "id": "paneltest:news",
         "from": "FACTORtv News", "subject": "A seat has changed hands",
         "body": ["Body."], "when": 9999999999})
    _un = _ibx.unread(_fc, feed="news")
    _row = h._rows_inbox()[0]
    if _un:
        check("new news" in str(_row.get("note", "")),
              "the inbox says how much unread news is waiting",
              str(_row.get("note")))
        check(_row.get("hot"), "and the row is marked so it reads as new",
              str(_row.get("hot")))
    else:
        check("see news" in str(_row.get("note", "")),
              "with nothing unread it just offers the tab",
              str(_row.get("note")))
    # AND IT STILL SWITCHES TABS, which is the row's actual job.
    check(str(_row.get("key")) == "mailfeed:news",
          "and the row still switches to the news tab", str(_row.get("key")))
    h._mail_feed = "mail"
    h.menu_page = "main"

# THE CAREER DASHBOARD. Asked for after living with the old career page: "theres
# literally not much happening there and its all just a bunch of words ... Can we
# have a career dashboard instead, and then the Email icon lives insde the
# dashboard instead and then the email icon truns into a Trophy icon".
_dc = h.season
if _dc is not None:
    h.menu_page = "dash"
    _rows = h._rows_dash()
    _kinds = [r.get("kind") for r in _rows]
    check("head" in _kinds, "the dashboard opens with a header card", str(_kinds[:3]))
    check("tiles" in _kinds, "and the numbers are tiles, not sentences")
    _head = [r for r in _rows if r.get("kind") == "head"][0]
    check(_head.get("label") == _dc.me,
          "the header names the driver", str(_head.get("label")))
    check(0.0 <= float(_head.get("val") or 0) <= 1.0,
          "with a season-progress ring inside 0..1", str(_head.get("val")))
    check("/" in str(_head.get("ring")) or str(_head.get("ring")).isdigit(),
          "and the rounds written in it", str(_head.get("ring")))
    _tiles = [r for r in _rows if r.get("kind") == "tiles"][0]["tiles"]
    check(len(_tiles) == 4, "four of them", str(len(_tiles)))
    check([t["label"] for t in _tiles] == ["champ", "points", "wins", "podiums"],
          "and they are the four facts he asked the old page for",
          str([t["label"] for t in _tiles]))
    # THE POST LIVES IN HERE NOW, both feeds, with their counts.
    _keys = [r.get("key") for r in _rows]
    check("page_inbox" in _keys and "page_news" in _keys,
          "the post and the news are rows on the dashboard", str(_keys))
    # ...AND THE HOUSEKEEPING IS NOT, because the first version of this page came
    # out taller than the screen, which defeats the point of a dashboard.
    check("page_delete" not in _keys and "career_close" not in _keys,
          "while deleting and closing a career are one row further in",
          str(_keys))
    check("page_career" in _keys, "which the dashboard links to")
    _mrows = h._rows_manage()
    _mkeys = [r.get("key") for r in _mrows]
    for _k in ("career_quali", "page_nation", "career_close",
               "page_delete"):
        check(_k in _mkeys, "manage career holds %s" % _k, str(_mkeys))
    check(any(r.get("key") == "page_dash" for r in _mrows),
          "and gets back to the dashboard", str(_mkeys[-2:]))
    # A LOGO IS OPTIONAL AND ITS ABSENCE IS NOT A GAP. The marks are the
    # player's own files and are not shipped.
    check("logo" in _head, "the header asks for a division mark")
    # EVERY ROW THE PAGE DRAWS HAS A KIND THE RENDERER KNOWS.
    _known = {"head", "tiles", "bar", "band", "gap", "info", "action", "nav",
              "toggle", "slider", "text", "image", "logo"}
    check(all(k in _known for k in _kinds),
          "and nothing on it is a kind the renderer cannot draw",
          str([k for k in _kinds if k not in _known]))
    h.menu_page = "main"

# THE TROPHY IS PERMANENT, AND THAT IS A ROUTE-TO-THE-PRODUCT PROBLEM RATHER
# THAN A COSMETIC ONE.
#
# The envelope was hidden whenever no career existed, which was reasonable while
# the way to START one was Settings -> Career -> New career. Moving the career out
# of settings deleted that row and left the overlay with NO WAY IN: no button to
# click, and a player looking at a settings page that no longer mentions careers.
# He hit it within minutes: "now we have moved the career so there is no way to
# activate the email icon ... must be permantly there".


class _BtnHost(PanelsMixin):
    """Enough host to run the button's drawing code and record what it did."""

    def __init__(self, career):
        self.season = career
        self.menu_open = False
        self.menu_page = "main"
        self.game_rect = (0, 0, 1920, 1080)
        self.cfg = {}
        self.hidden = []
        self.drew = 0
        for n, sz in (("f_small", 10), ("f_row", 10), ("f_tiny", 8)):
            setattr(self, n, ("Arial", sz))

    def _begin_panel(self, name, x, y, w, h, clickable=False):
        host = self

        class _C(object):
            def __getattr__(self_inner, _n):
                def _draw(*a, **k):
                    host.drew += 1
                    return 1
                return _draw

        class _P(object):
            def canvas_at(self_inner, ox, oy):
                return _C()
        return _P()

    def _hide_panel(self, n):
        self.hidden.append(n)


for _lbl, _car in (("with no career at all", None),
                   ("with a career loaded", h.season)):
    _bh = _BtnHost(_car)
    _bh.draw_inbox_button()
    check(_bh._inbox_btn_rect is not None,
          "the trophy is on screen and clickable %s" % _lbl,
          str(_bh._inbox_btn_rect))
    check("inboxbtn" not in _bh.hidden,
          "and is never hidden %s" % _lbl, str(_bh.hidden))
    check(_bh.drew > 5, "and it actually draws a trophy %s" % _lbl,
          "%d canvas calls" % _bh.drew)

# ...AND THE DASHBOARD IT OPENS IS USABLE FROM NOTHING, or the button is a door
# to an empty room.
_none = _BtnHost(None)
_nrows = _none._rows_dash()
_nkeys = [r.get("key") for r in _nrows]
check("page_new" in _nkeys,
      "with no career, the dashboard offers to start one", str(_nkeys))
check("page_load" in _nkeys, "and to load one")
check(any(r.get("hot") for r in _nrows),
      "and the way in is marked, because it is the only thing to do")

# EVERY NAV KEY ON EVERY PAGE HAS TO LEAD SOMEWHERE.
#
# The router maps the short name after `page_` through a table and falls back to
# `"main"` for anything it does not recognise — so a mistyped key does not fail,
# it SILENTLY SENDS THE PLAYER TO THE SETTINGS PAGE. The dashboard shipped with
# `page_career_new` where the router knows `page_new`, and the whole suite passed
# because the tests asserted the keys I had invented rather than the keys the
# router understands. He found it in one click: "when i pres load career or new
# career it just takes me back to the settings page".
#
# THE TABLE IS THE ONLY AUTHORITY, and this walks every page against it.
import io as _io2
import re as _re
_src = _io2.open(_op.__file__, encoding="utf-8").read()
_i = _src.index('self.menu_page = {"career": "career"')
_j = _src.index("}.get(key[5:]", _i)
_router = set(_re.findall(r'"(\w+)":\s*"', _src[_i:_j]))
check(len(_router) > 15, "the router's page table can be read",
      "%d names" % len(_router))

_PAGES = ("main", "dash", "career", "career_new", "career_load",
          "career_delete", "career_nation", "career_path", "career_plen",
          "career_ladder", "career_nextlen", "inbox", "record", "standings",
          "results", "divisions", "legal")
_special = {"page_inbox", "page_news"}      # handled above the table, by name
_bad = []
for _pg in _PAGES:
    h.menu_page = _pg
    try:
        _rows = h._menu_rows()
    except Exception as _e:
        _bad.append("%s raised %s" % (_pg, _e))
        continue
    for _r in _rows:
        _k = str(_r.get("key") or "")
        if not _k.startswith("page_") or _k in _special:
            continue
        if _k[5:] not in _router:
            _bad.append("%s -> %s" % (_pg, _k))
h.menu_page = "main"
check(not _bad,
      "and every page_ key on every page resolves to a real page",
      "; ".join(_bad[:4]))

print("\n" + ("FAILED: %d" % len(fails) if fails else "ALL PASSED"))
root.destroy()
sys.exit(1 if fails else 0)
