# Desktop audio backend for the simulator: lets picogame_synth actually MAKE SOUND on a PC so the
# audio can be heard while play-testing (the device uses real synthio; CPython has none). It renders
# synthio-style notes (256-sample oscillator + ADSR + one pitch-bend sweep - the SAME model as
# tools/synth_preview.py) to int16 buffers and plays them through pygame.mixer. It is an APPROXIMATION
# for tuning/feel, NOT bit-exact to the RP2040. Fully guarded: if pygame/mixer/audio is unavailable
# (headless CI, --backend pil), everything degrades to a SILENT no-op and never raises - so it must
# never break a normal sim run just by existing.

import math

try:
    import numpy as np
except Exception:                        # numpy should be present (the sim uses it), but stay safe
    np = None

_SR = 22050
_ready = None                            # None = not yet tried; True/False after lazy init
_mixer = None
_sfx_chan = None
_music_chan = None
_cache = {}                              # id(note) -> pygame.Sound


def _init():
    """Lazily bring up pygame.mixer. Returns True on success; False -> silent mode."""
    global _ready, _mixer, _sfx_chan, _music_chan
    if _ready is not None:
        return _ready
    _ready = False
    if np is None:
        return False
    try:
        import pygame
        # pygame.init() (the pygame backend) auto-inits the mixer at 44100 - our buffers are 22050 mono,
        # so force our format (else everything plays at the wrong pitch/speed).
        cur = pygame.mixer.get_init()
        if cur != (_SR, -16, 1):
            if cur:
                pygame.mixer.quit()
            pygame.mixer.pre_init(frequency=_SR, size=-16, channels=1, buffer=512)
            pygame.mixer.init()
        pygame.mixer.set_num_channels(8)
        _mixer = pygame.mixer
        _music_chan = pygame.mixer.Channel(0)     # reserved: looping music
        _sfx_chan = pygame.mixer.Channel(1)       # monophonic SFX (mirrors the device's single sfx voice)
        _ready = True
    except Exception:
        _ready = False
    return _ready


def midi_to_hz(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def _osc_env(freq_hz, table, env, amp, bend, n):
    """Render n samples: phase-accumulate through `table` at freq (+ optional bend LFO), apply ADSR."""
    t = np.arange(n) / _SR
    base = float(freq_hz)
    if bend is not None and getattr(bend, "rate", 0):
        period = 1.0 / max(1e-6, float(bend.rate))
        ph = np.clip(t / period, 0.0, 1.0)                    # one sweep, then hold (matches synth_preview)
        freq = base * 2.0 ** (float(bend.scale) * np.sin(2 * np.pi * ph))
    else:
        freq = np.full(n, base)
    tbl = np.frombuffer(bytes(table), dtype="<i2").astype(np.float32)
    L = len(tbl) or 1
    phase = (np.cumsum(freq) / _SR) % 1.0
    osc = tbl[(phase * L).astype(np.int32) % L]
    a = max(1, int(_SR * getattr(env, "attack_time", 0.005)))
    d = int(_SR * getattr(env, "decay_time", 0.06))
    s = float(getattr(env, "sustain_level", 0.0))
    r = int(_SR * getattr(env, "release_time", 0.08))
    e = np.zeros(n)
    e[:a] = np.linspace(0.0, 1.0, a)
    de = min(a + d, n)
    if de > a:
        e[a:de] = np.linspace(1.0, s, de - a)
    e[de:] = s
    if r > 0 and n > r:                                       # release ramp at the tail
        e[n - r:] *= np.linspace(1.0, 0.0, r)
    return osc * e * float(amp)


def _render_note(note):
    env = note.envelope
    dur = (getattr(env, "attack_time", 0.005) + getattr(env, "decay_time", 0.06)
           + getattr(env, "release_time", 0.08) + 0.04)
    n = max(1, int(_SR * dur))
    sig = _osc_env(note.frequency, note.waveform, env, note.amplitude, note.bend, n)
    return np.clip(sig, -32767, 32767).astype("<i2").tobytes()


def _render_track(track):
    """Render a parsed MidiTrack's note spans into one int16 loop buffer."""
    if not track._notes:
        return b""
    tps = float(track._tempo) or 240.0                        # ticks per second
    end_tick = max(on + du for (_m, on, du) in track._notes)
    n = max(1, int(_SR * (end_tick / tps)))
    buf = np.zeros(n, dtype=np.float32)
    for m, on, du in track._notes:
        start = int(_SR * (on / tps))
        ln = max(1, int(_SR * (du / tps)))
        seg = _osc_env(midi_to_hz(m), track._wave, track._env, 0.5, None, ln)
        end = min(start + ln, n)
        if end > start:
            buf[start:end] += seg[:end - start]
    return np.clip(buf, -32767, 32767).astype("<i2").tobytes()


def _sound(raw):
    try:
        return _mixer.Sound(buffer=raw) if raw else None
    except Exception:
        return None


def play_note(note, level):
    """Play a one-shot SFX note on the monophonic SFX channel (a new one cuts the previous)."""
    if not _init():
        return
    try:
        snd = _cache.get(id(note))
        if snd is None:
            snd = _sound(_render_note(note))
            _cache[id(note)] = snd
        if snd is not None:
            snd.set_volume(max(0.0, min(1.0, level)))
            _sfx_chan.play(snd)
    except Exception:
        pass


def play_music(track, level):
    if not _init():
        return
    try:
        snd = _cache.get(id(track))
        if snd is None:
            snd = _sound(_render_track(track))
            _cache[id(track)] = snd
        if snd is not None:
            snd.set_volume(max(0.0, min(1.0, level)))
            _music_chan.play(snd, loops=-1)
    except Exception:
        pass


def stop_music():
    if _music_chan is not None:
        try:
            _music_chan.stop()
        except Exception:
            pass
