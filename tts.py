# -*- coding: utf-8 -*-
"""
FACTORtv — voice engine.

Primary engine is edge-tts (Microsoft's free online NEURAL voices — genuinely
human, real accents), decoded with miniaudio, then shaped. Falls back to
offline SAPI so the overlay still talks with no internet. A TTS failure can
never affect the overlay: every path here returns quietly rather than raising.

This is a deliberate port of the RacerTV chain, whose tuning was settled BY
EAR over a long period. The values below are not guesses and should not be
"tidied" without listening to the result. The load-bearing findings, kept
because each one was a regression at some point:

  * ENERGY COMES FROM RATE AND VOLUME, NOT PITCH. The obvious way to make a
    commentator sound excited is to raise pitch, and it makes him sound
    robotic and small. The `_HYPE` ladder moves rate and volume hard and
    pitch barely at all.

  * BIG MOMENTS SWELL CONTINUOUSLY. A line rendered clause-by-clause with a
    louder gain per clause has an audible step at each boundary. `_build`
    renders the clauses separately for rising rate/pitch, then applies ONE
    smoothstep loudness envelope across the whole joined waveform, so the
    volume glides rather than jumps.

  * THE ENGINEER DOES NOT GET THE RADIO FILTER. The band-pass flattens the
    neural prosody that makes the voice sound human. Rival drivers sound
    better through it, your engineer sounds better clean. (An older report
    that removing the band-pass made drivers sound robotic was a
    misattribution — they were failing to render and falling back to SAPI.
    Don't re-litigate it from that.)

  * THE BAND-PASS STAYS OPEN. 220-5200 Hz with tanh drive of only 1.03.
    Narrower and harder sounds more "radio" and destroys the accents that
    make the grid feel like different people.

  * STATIC IS SCALED BY THE ENVELOPE. A flat noise floor hisses through every
    silence. Multiplying it by the voice envelope keeps gaps clean.

What is new here versus RacerTV: a render CACHE keyed on
(text, voice, rate, pitch, volume). The booth repeats stock phrases across a
race weekend, and re-synthesising them costs a network round trip each time.
Cached lines air instantly, which also removes most of the lag between an
event happening and it being called.
"""
import hashlib
import math
import os
import queue
import random
import re
import struct
import subprocess
import sys
import threading
import time
import wave

import cast as cast_mod

try:
    import winsound
except Exception:
    winsound = None

try:
    import asyncio
    import edge_tts
    import miniaudio
    _HAVE_EDGE = True
    _EDGE_ERR = ""
except Exception as _ex:
    _HAVE_EDGE = False
    _EDGE_ERR = "%s: %s" % (type(_ex).__name__, _ex)

_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(_DIR, "_voice_cache")
TMP_DIR = os.path.join(_DIR, "_voice_tmp")
TRANSCRIPT = os.path.join(_DIR, "_transcript.log")

# ---- tuning (settled by ear; see module docstring before changing) --------
NOISE = 0.012        # static floor — low, so the voice stays clean
DRIVE = 1.03         # very light distortion — keep the voice clear
BAND_LO = 220.0      # radio band-pass, deliberately WIDE so accents survive
BAND_HI = 5200.0
SHIMMER = 0.05       # gentle AM movement on radio voices
# How long to wait before re-asking the edge service after a failed render.
# Multiplied by the attempt number, so the second wait is longer.
EDGE_RETRY_WAIT = 0.6

MASTER_VOL = 1.0
LOUDNESS = 1.0
CLICK_GAIN_IN = 0.35   # squelch click before a radio line
CLICK_GAIN_OUT = 0.22  # and after — both well UNDER the voice
CLAUSE_GAP_S = 0.045   # breath between clauses in a swelling line
CACHE_MAX_FILES = 1200

# Excitement ladder: (rate, pitch, volume) by intensity.
#
# PITCH BARELY MOVES, and at rest it does not move at all. The earlier ladder
# sat a calm line at -9Hz and stacked the persona's own offset on top, so the
# analyst was speaking roughly 13Hz below his natural pitch all race. Azure's
# neural voices are modelled at their own pitch; shifting them is resampling,
# and resampling is exactly what makes a good voice sound processed and fake.
#
# Energy therefore comes from RATE and VOLUME, which are genuinely re-rendered
# rather than shifted, and pitch is left almost alone.
_HYPE = {
    0: ("+0%", "+0Hz", "+4%"),
    1: ("+7%", "+0Hz", "+12%"),
    2: ("+14%", "+2Hz", "+20%"),
    3: ("+20%", "+4Hz", "+26%"),
}

# The continuous swell used for big-moment lines.
_BUILD = dict(rate0=0, rate1=4,        # barely a nudge; the swell is volume
              pitch0=-2, pitch1=5,
              gain0=1.0, gain1=2.0)    # applied as an eased envelope, no steps

# Three treatments, not two.
#
#   BOOTH     heard in the room. Normalise only — no clicks, no filter.
#   ENGINEER  on the radio, but on a MODERN intercom: squelch clicks and the
#             radio level treatment, but NO band-pass. The filter flattens the
#             neural prosody that makes him sound human, and he is the voice
#             you hear most, so he is the one it hurts most.
#   RIVALS    full chain including the band-pass. They sound better for it,
#             and it separates them from your own engineer instantly.
BOOTH_PERSONAS = {cast_mod.PLAY, cast_mod.ANALYST}
NO_BANDPASS = {cast_mod.ENGINEER}


def _ensure_dirs():
    for d in (CACHE_DIR, TMP_DIR):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass


def _log_transcript(persona, text):
    """Every line that actually AIRS, in full, in order.

    Exists to make repetition auditable: reading a whole race back is the only
    reliable way to judge whether the writing is varied enough.
    """
    try:
        with open(TRANSCRIPT, "a", encoding="utf-8") as f:
            f.write("%s  %-8s %s\n" % (time.strftime("%H:%M:%S"), persona, text))
    except Exception:
        pass



# --------------------------------------------------------------------------
# spoken form
#
# What is WRITTEN on screen and what is SENT to the synthesiser are not the
# same string, and conflating them produces the single most embarrassing class
# of bug in a voiced product.
#
# The trigger was the channel name. Azure treats a run of capitals followed by
# lowercase as an initialism, so "FACTORtv" was read out as
# "F. A. C. T. O. R. tee vee" — in the intro sting, which is the very first
# thing anyone hears.
#
# Captions and the transcript keep the written form; only the audio path is
# rewritten.
# --------------------------------------------------------------------------
_SPEAK_FIXES = [
    # Brand. Spaced so it is read as two words rather than an acronym.
    (re.compile(r"\bFACTOR ?tv\b", re.I), "Factor T V"),
    # Position shorthand: "P4" spells as "pee four" only if it is separated.
    (re.compile(r"\bP(\d{1,2})\b"), r"P \1"),
    # Sector labels, which otherwise come out as "ess one".
    (re.compile(r"\bS([123])\b"), r"sector \1"),
    # Units that only ever appear on screen; if one leaks into a line it
    # should at least be said properly.
    (re.compile(r"\bkm/h\b", re.I), "kilometres per hour"),
    (re.compile(r"\bL/lap\b", re.I), "litres per lap"),
    # An em dash is a breath, not a word. Azure handles a comma better.
    (re.compile(r"\s*\u2014\s*"), ", "),
]


def speakable(text):
    """Rewrite display text into something the synthesiser reads correctly."""
    out = text or ""
    for pat, rep in _SPEAK_FIXES:
        out = pat.sub(rep, out)
    return out

# --------------------------------------------------------------------------
# audio helpers
# --------------------------------------------------------------------------
def _soft(x):
    """Safety limiter. Linear well below full scale, soft above."""
    a = abs(x)
    if a <= 0.95:
        return x
    return math.copysign(0.95 + (a - 0.95) / (1.0 + (a - 0.95) * 4.0), x)


def _gentle(x):
    """Gentle saturator — linear to 0.75, soft knee above.

    Fattens a gained clause so it reads LOUDER without the harsh wall of a
    hard limiter, which is what makes the swell sound like enthusiasm rather
    than clipping.
    """
    a = abs(x)
    if a <= 0.75:
        return x
    e = a - 0.75
    return math.copysign(0.75 + e / (1.0 + e * 2.5), x)


def _radioize(samples, rate, drive=DRIVE, noise=NOISE, lo=BAND_LO, hi=BAND_HI,
              shimmer=SHIMMER):
    """Band-pass to the radio band, light distortion, static under the voice.

    One-pole filters rather than anything fancier: the point is a suggestion
    of a radio link, not an emulation of one. Anything steeper starts eating
    the consonants.
    """
    out = [0.0] * len(samples)
    dt = 1.0 / rate
    a_lp = dt / (1.0 / (2 * math.pi * hi) + dt)
    rc_hp = 1.0 / (2 * math.pi * lo)
    a_hp = rc_hp / (rc_hp + dt)
    lp = prev_x = prev_hp = 0.0
    for i, x in enumerate(samples):
        lp += a_lp * (x - lp)
        hp = a_hp * (prev_hp + lp - prev_x)
        prev_x, prev_hp = lp, hp
        v = math.tanh(hp * drive)
        n = random.uniform(-1.0, 1.0)
        env = abs(v)
        # Static scaled by the envelope so silences stay quiet.
        v = v * (1.0 + n * shimmer) + n * noise * env
        out[i] = max(-1.0, min(1.0, v * 0.97))
    return out


def _click(rate, ms=80):
    """Squelch click for the top and tail of a radio transmission."""
    n = max(1, int(rate * ms / 1000.0))
    out = []
    for i in range(n):
        p = i / float(n)
        env = math.exp(-p * 18.0)
        out.append(random.uniform(-1.0, 1.0) * env * 0.5)
    return out


def _write_wav(path, rate, samples, gain=1.0):
    try:
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            frames = bytearray()
            for s in samples:
                v = int(max(-1.0, min(1.0, s * gain)) * 32767)
                frames += struct.pack("<h", v)
            w.writeframes(bytes(frames))
        return True
    except Exception:
        return False


def _read_wav(path):
    try:
        with wave.open(path, "rb") as w:
            rate = w.getframerate()
            n = w.getnframes()
            raw = w.readframes(n)
        vals = struct.unpack("<%dh" % (len(raw) // 2), raw)
        return rate, [v / 32768.0 for v in vals]
    except Exception:
        return None, None


def _decode_mp3(path):
    d = miniaudio.decode_file(path, output_format=miniaudio.SampleFormat.SIGNED16,
                              nchannels=1, sample_rate=24000)
    return d.sample_rate, [s / 32768.0 for s in d.samples]


def _split_clauses(text):
    """Split into rising clauses on strong boundaries.

    Tiny fragments are merged back — rendering a one-word snippet on its own
    gives it an unnatural isolated stress.
    """
    parts = re.split(r"(?<=[!.?])(?=\s)|(?<=—)\s*|(?<=,)\s+", text)
    parts = [p.strip() for p in parts if p.strip()]
    merged = []
    for p in parts:
        if merged and len(p.split()) < 2:
            merged[-1] = merged[-1] + " " + p
        else:
            merged.append(p)
    return merged


# --------------------------------------------------------------------------
# the engine
# --------------------------------------------------------------------------
class Tts(object):
    """Queued, non-blocking speech.

    One generator thread synthesises, one player thread plays. Speech is
    always queued and never rendered on the caller's thread, because a
    network synth takes hundreds of milliseconds and the overlay tick must
    not stall behind it.
    """

    def __init__(self, volume=1.0, enabled=True):
        _ensure_dirs()
        self.volume = volume
        self.enabled = enabled
        self.engine = "edge" if _HAVE_EDGE else "sapi"
        self.gen_q = queue.Queue()
        self.play_q = queue.Queue()
        self._seq = 0
        self._epoch = 0
        self._speaking = None
        self.now_playing = None     # (persona, text, started_at) while audible
        self.sapi_falls = 0         # lines that dropped to the offline voice
        self._alive = True
        self._cache_index = set()
        self._scan_cache()
        self._gen_t = threading.Thread(target=self._gen_loop, daemon=True)
        self._play_t = threading.Thread(target=self._play_loop, daemon=True)
        self._gen_t.start()
        self._play_t.start()

    # -- cache ---------------------------------------------------------------
    def _scan_cache(self):
        try:
            self._cache_index = set(os.listdir(CACHE_DIR))
        except Exception:
            self._cache_index = set()

    def _cache_key(self, text, voice, rate, pitch, vol, fx):
        h = hashlib.sha1(("%s|%s|%s|%s|%s|%s" % (text, voice, rate, pitch, vol,
                                                 fx)).encode("utf-8"))
        return h.hexdigest()[:20] + ".wav"

    def _cache_trim(self):
        """Keep the cache bounded, oldest-first."""
        try:
            files = [(os.path.getmtime(os.path.join(CACHE_DIR, f)), f)
                     for f in os.listdir(CACHE_DIR)]
            if len(files) <= CACHE_MAX_FILES:
                return
            files.sort()
            for _, f in files[:len(files) - CACHE_MAX_FILES]:
                try:
                    os.remove(os.path.join(CACHE_DIR, f))
                    self._cache_index.discard(f)
                except Exception:
                    pass
        except Exception:
            pass

    # -- public --------------------------------------------------------------
    def speak(self, text, persona=cast_mod.PLAY, intensity=0, seed=0,
              build=False, priority=1, name=""):
        """Queue a line. Returns immediately.

        `build` asks for the swelling delivery — use it for the genuinely big
        moments (a win, a lead change on the last lap) and nothing else, or
        the effect stops meaning anything.
        """
        if not self.enabled or not text:
            return
        self._seq += 1
        self.gen_q.put({
            "text": text, "persona": persona, "intensity": intensity,
            "seed": seed, "build": build, "prio": priority, "name": name,
            "epoch": self._epoch, "seq": self._seq,
        })

    def play_file(self, path, persona=cast_mod.PLAY, text=""):
        """Play an already-rendered wav immediately.

        Deliberately jumps the generation queue: this exists for stings,
        whose entire purpose is to land at the moment of the event. Going
        through the normal path would reintroduce the render latency the
        sting was created to avoid.
        """
        if not self.enabled or not path:
            return
        self._seq += 1
        self.play_q.put((self._seq, path, persona, text))

    def interrupt(self):
        """Drop everything queued and stop the current line.

        Used when something more important happens mid-sentence — a crash
        during a routine standings read. Bumping the epoch invalidates work
        already in flight without having to drain the queues.
        """
        self._epoch += 1
        for q in (self.gen_q, self.play_q):
            try:
                while True:
                    q.get_nowait()
            except queue.Empty:
                pass
        try:
            if winsound:
                winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

    @property
    def speaking(self):
        return self._speaking is not None or not self.play_q.empty()

    def set_volume(self, v):
        self.volume = max(0.0, min(1.0, v))

    # -- master volume ---------------------------------------------------------
    #
    # IT WAS A DEAD KNOB. `self.volume` has been stored since the class was
    # written, `Tts(volume=cfg["volume"])` has been passing 0.9 into it, and
    # NOTHING EVER READ IT — exactly the shape of the deleted
    # `cast.intensity_voice`, which also looked like the knob you would reach
    # for and also changed nothing. Anyone lowering it heard no difference and
    # would reasonably conclude the setting was broken. It was.
    #
    # WHY THE PCM IS SCALED RATHER THAN THE SYNTHESIS. edge-tts takes a volume
    # argument, but that value is part of the RENDER CACHE KEY — so moving a
    # slider would invalidate every cached line and re-render the lot, one
    # 2-6 second render at a time, exactly when the user is fiddling. Scaling
    # the finished PCM is instant, applies to the STINGS and the mail tone as
    # well (they were mixed against the commentary and must stay in
    # proportion), and leaves the expensive cache untouched.
    #
    # The scaled copies are cached beside the originals and keyed by level, so
    # a repeated line at a settled volume costs nothing after the first play.

    def _scaled(self, wav):
        """A copy of this wav at the master volume, or the original.

        Returns the original at full volume and on any failure: a line the
        user cannot hear because the scaler broke is far worse than a line
        that is louder than he wanted.
        """
        v = float(getattr(self, "volume", 1.0) or 0.0)
        if v >= 0.995:
            return wav
        step = int(round(v * 20)) * 5          # 5% buckets, so the cache is finite
        out = "%s.v%03d.wav" % (os.path.splitext(wav)[0], step)
        if os.path.exists(out):
            return out
        try:
            import array
            import wave
            with wave.open(wav, "rb") as r:
                params = r.getparams()
                if params.sampwidth != 2:
                    return wav                 # only 16-bit PCM is handled
                frames = r.readframes(params.nframes)
            a = array.array("h")
            a.frombytes(frames)
            scale = v * v      # PERCEIVED loudness, not linear amplitude: half
                               # on the slider should sound like half.
            for i, x in enumerate(a):
                a[i] = int(x * scale)
            tmp = out + ".tmp"
            with wave.open(tmp, "wb") as w:
                w.setparams(params)
                w.writeframes(a.tobytes())
            os.replace(tmp, out)
            return out
        except Exception:
            return wav

    def close(self):
        self._alive = False
        self.interrupt()

    # -- generation -----------------------------------------------------------
    def _gen_loop(self):
        while self._alive:
            try:
                job = self.gen_q.get(timeout=0.2)
            except queue.Empty:
                continue
            if job["epoch"] != self._epoch:
                continue          # superseded while queued
            try:
                wav = self._render(job)
            except Exception:
                wav = None
            if wav and job["epoch"] == self._epoch:
                self.play_q.put((job["seq"], wav, job["persona"], job["text"]))

    def _render(self, job):
        # `text` is what gets SPOKEN; the caption and transcript keep the
        # original written form from the job.
        text = speakable(job["text"])
        persona = job["persona"]
        # The driver NAME must reach the casting, or nationality-based
        # accent selection never fires and every rival falls back to the
        # generic seed pool — the accents would be configured correctly
        # and simply never used.
        cfg = cast_mod.voice_for(persona, job.get("seed", 0),
                                 name=job.get("name", ""))
        voice = cfg.get("voice")
        booth = persona in BOOTH_PERSONAS
        bandpass = not booth and persona not in NO_BANDPASS
        rate, pitch, vol = _HYPE.get(min(3, job.get("intensity", 0)), _HYPE[0])
        # The persona's resting rate/pitch offsets the hype ladder, so a
        # naturally slower analyst stays slower even when animated.
        rate = self._combine(cfg.get("rate", "+0%"), rate, "%")
        pitch = self._combine(cfg.get("pitch", "+0Hz"), pitch, "Hz")

        key = self._cache_key(text, voice, rate, pitch, vol,
                              "b" if job.get("build")
                              else ("r" if bandpass else ("e" if not booth else "c")))
        cached = os.path.join(CACHE_DIR, key)
        if key in self._cache_index and os.path.exists(cached):
            return cached

        samples, srate, prebuilt = None, 24000, False
        if self.engine == "edge":
            try:
                if job.get("build"):
                    res = self._build(text, voice)
                    if res:
                        srate, samples, prebuilt = res
                if samples is None:
                    srate, samples = self._edge(text, voice, rate, pitch, vol)
            except Exception:
                samples = None
            # RETRY BEFORE GIVING UP. The edge service throttles bursts, and
            # the booth now queues several lines together — a question and its
            # answer, a call and its verdict. A single hiccup used to drop
            # that line to the offline SAPI voice, which is why a robotic
            # female voice appeared "at random points" mid-broadcast: it was
            # never a mis-configured persona, it was one failed request.
            #
            # Second attempt after a beat, then the persona's fallback voice,
            # and only then the offline engine.
            for attempt, v in ((1, voice), (2, cfg.get("fallback") or voice)):
                if samples is not None:
                    break
                time.sleep(EDGE_RETRY_WAIT * attempt)
                try:
                    srate, samples = self._edge(text, v, rate, pitch, vol)
                except Exception:
                    samples = None
        if samples is None:
            # Genuinely offline, or the service is refusing. The voice will
            # sound wrong and that is the correct outcome — silence would be
            # worse — but it is COUNTED so a test run can show how often it
            # happened instead of leaving it as a mystery.
            self.sapi_falls += 1
            try:
                srate, samples = self._sapi(text)
            except Exception:
                samples = None
        if not samples:
            return None

        if prebuilt:
            # The build ramp already set the levels. Peak-normalising here
            # would flatten the swell straight back out.
            mixed = [_soft(x) for x in samples]
        elif booth:
            peak = max((abs(x) for x in samples), default=0.0) or 1.0
            g = min(4.0, 0.97 / peak) * MASTER_VOL * LOUDNESS
            mixed = [_soft(x * g) for x in samples]
        else:
            # Radio framing. The band-pass drops the level a long way, so
            # normalise the voice FIRST and then drive it, or the radio ends
            # up inaudible under the engine. The engineer skips the filter
            # itself but keeps the clicks and the level treatment, so he still
            # reads as "on the radio" without losing his prosody.
            vs = _radioize(samples, srate) if bandpass else list(samples)
            vpk = max((abs(x) for x in vs), default=0.0) or 1.0
            vs = [x * (0.95 / vpk) for x in vs]
            mixed = ([c * CLICK_GAIN_IN for c in _click(srate)] + vs
                     + [c * CLICK_GAIN_OUT for c in _click(srate, 50)])
            mixed = [_soft(s * MASTER_VOL * LOUDNESS * 1.2) for s in mixed]

        if _write_wav(cached, srate, mixed):
            self._cache_index.add(key)
            self._cache_trim()
            return cached
        return None

    @staticmethod
    def _combine(base, hype, unit):
        """Add a persona's resting offset to the hype ladder's value."""
        try:
            b = int(str(base).rstrip(unit).rstrip("%") or 0)
            h = int(str(hype).rstrip(unit).rstrip("%") or 0)
        except Exception:
            return hype
        return ("%+d" % (b + h)) + ("%" if unit == "%" else "Hz")

    def _tmp(self, ext):
        self._seq += 1
        return os.path.join(TMP_DIR, "t%d_%d.%s" % (os.getpid(), self._seq, ext))

    def _edge(self, text, voice, rate, pitch, vol):
        mp3 = self._tmp("mp3")
        try:
            com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch,
                                       volume=vol)
            asyncio.run(com.save(mp3))
            return _decode_mp3(mp3)
        finally:
            try:
                os.remove(mp3)
            except Exception:
                pass

    def _build(self, text, voice):
        """Render a big moment so the excitement SWELLS smoothly through it.

        Two layers, kept separate so the swell is natural rather than stepped:
        rate and pitch rise per clause (small, and far less audible than a
        volume jump, so discrete steps are fine there); loudness rises as ONE
        continuous eased envelope across the whole concatenated waveform.

        The discrete per-clause gain step was the jarring part in an earlier
        version — it landed exactly on a silence boundary, which is where the
        ear is most sensitive to it.
        """
        clauses = _split_clauses(text)
        if len(clauses) < 2:
            return None
        n = len(clauses)
        b = _BUILD
        rendered = []
        srate = 24000
        for i, clause in enumerate(clauses):
            p = i / (n - 1.0)
            rate = "%+d%%" % int(round(b["rate0"] + p * (b["rate1"] - b["rate0"])))
            pitch = "%+dHz" % int(round(b["pitch0"] + p * (b["pitch1"] - b["pitch0"])))
            sr, s = self._edge(clause, voice, rate, pitch, "+0%")
            srate = sr
            rendered.append(s)
        # Reference off the FIRST clause so the opening sits at about a normal
        # line's loudness, then apply that one factor to all of them — which
        # preserves edge's own natural relative levels between clauses.
        ref_pk = max((abs(x) for x in rendered[0]), default=0.0) or 1.0
        ref = 0.90 / ref_pk
        gap = [0.0] * int(srate * CLAUSE_GAP_S)
        joined = []
        for i, s in enumerate(rendered):
            joined.extend(x * ref for x in s)
            if i < n - 1:
                joined.extend(gap)
        N = len(joined) or 1
        g0, g1 = b["gain0"], b["gain1"]
        out = []
        for i, x in enumerate(joined):
            p = i / (N - 1.0) if N > 1 else 1.0
            e = p * p * (3.0 - 2.0 * p)          # smoothstep ease
            out.append(_gentle(x * (g0 + (g1 - g0) * e)))
        return srate, out, True

    def _sapi(self, text):
        """Offline fallback. Noticeably more robotic — that is expected, not
        a bug, and it is still better than silence."""
        wav = self._tmp("wav")
        safe = text.replace("'", "''")
        ps = ("Add-Type -AssemblyName System.Speech; "
              "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              "$s.SetOutputToWaveFile('%s'); $s.Speak('%s'); $s.Dispose()"
              % (wav.replace("\\", "\\\\"), safe))
        try:
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy",
                            "Bypass", "-Command", ps],
                           capture_output=True, timeout=20)
            r, s = _read_wav(wav)
            return (r or 22050), (s or [])
        finally:
            try:
                os.remove(wav)
            except Exception:
                pass

    # -- playback --------------------------------------------------------------
    def _play_loop(self):
        while self._alive:
            try:
                seq, wav, persona, text = self.play_q.get(timeout=0.2)
            except queue.Empty:
                continue
            if not os.path.exists(wav):
                continue
            self._speaking = persona
            # PUBLISHED so the caption can follow the audio instead of
            # guessing. A line is queued seconds before it is heard — the
            # render alone is 2-6s — so a subtitle drawn at queue time is a
            # subtitle for a line nobody has said yet. This is the only
            # moment at which "is being spoken right now" is true.
            self.now_playing = (persona, text, time.time())
            _log_transcript(persona, text)
            try:
                if winsound:
                    # Synchronous so lines never overlap. The queue is what
                    # keeps the overlay responsive, not async playback.
                    winsound.PlaySound(self._scaled(wav),
                                       winsound.SND_FILENAME)
            except Exception:
                pass
            finally:
                self._speaking = None
                self.now_playing = None


def _demo():
    """Speak one line per persona so the chain can be judged by ear."""
    t = Tts()
    print("engine: %s%s" % (t.engine, "" if _HAVE_EDGE else " (%s)" % _EDGE_ERR))
    tests = [
        (cast_mod.PLAY, "And we are racing at Zandvoort!", 3, False),
        (cast_mod.PLAY, "Verstappen goes through on Russell!", 2, False),
        (cast_mod.ANALYST,
         "That's the difference. He's carrying more speed through the middle "
         "sector, and the front tyre is taking it.", 0, False),
        (cast_mod.ENGINEER, "Box this lap, box this lap.", 1, False),
        (cast_mod.DRIVER, "He pushed me clean off the road out there!", 2, False),
        (cast_mod.PLAY,
         "Down the inside — he's got him — Verstappen takes the lead of the "
         "Grand Prix!", 3, True),
    ]
    for persona, text, inten, build in tests:
        print("  %-8s %s" % (persona, text))
        t.speak(text, persona, intensity=inten, build=build, seed=3)
    t0 = time.time()
    while (t.speaking or not t.gen_q.empty()) and time.time() - t0 < 120:
        time.sleep(0.2)
    time.sleep(0.5)
    print("done — transcript at %s" % TRANSCRIPT)


if __name__ == "__main__":
    _demo()
