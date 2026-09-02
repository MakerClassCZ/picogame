# picogame music: play PICO-8 tracker music through synthio - the import path for the
# known "no music" gap. Author songs in the PICO-8 tracker (or its free web clones),
# bake with tools/p8music.py, play here. No on-device editor, no new format.
#
#   import picogame_synth, picogame_music, my_song
#   synth = picogame_synth.Synth()
#   music = picogame_music.Player(synth, my_song)
#   music.play(0)                      # pattern index; honors loop/stop flags
#   ... in the game loop: music.tick() # once per frame
#
# Plays on the mixer's MUSIC voice (voice 0, own synthesizer) - `set_levels(music=...)`
# fades it, and the sfx Kit on voice 1 can never cut a music note. Shares the voice
# with `load_midi` MidiTracks: use one music system at a time.
#
# MEASURED COST (PicoPad RP2040, review/synth_music_bench.py): 4 sustained voices with
# note churn + LFO = ~3.0 ms/frame at 30 fps, no extra frame spikes, sfx on top ~free.
# Scales with channels (~0.75 ms each) - tight games bake with `p8music.py --channels 2`.
# RAM: song bank ~1-2 KB typical; the waveforms are picogame_synth's shared tables (the
# 25 % pulse is the one wave without a shared table - built once per Player, 512 B).
#
# Bank format (generated module): SFX = {id: (speed, loop0, loop1, bytes 32*3)} with
# 3 bytes/note = pitch, (wave<<4)|volume, effect; PATTERNS = ((ch0,ch1,ch2,ch3,flags),...)
# with 0xFF = channel off, flags: 1 = loop start, 2 = loop end, 4 = stop.
#
# Effect mapping (everything possible runs in synthio's C side - no 128 Hz Python tick):
# slide/drop = one-shot bend ramp, vibrato = shared LFO, fade in/out = one-shot amplitude
# ramp, arpeggio = frequency mutation from tick() at sub-note rate (the only Python-paced
# effect). Approximations: tilted-saw->saw, organ->triangle, phaser->sine, noise = stored
# noise cycle; custom instruments (waveform 8-15) are baked to square by the tool (warned).
# In the sim (no audio backend) the player is a silent no-op - no guards needed in games.

import time

import synthio

import picogame_synth as _ps

try:
    from micropython import const
except ImportError:
    def const(x):
        return x

# Timebase: supervisor.ticks_ms() (a small int, wraps at 2**29 ms) instead of monotonic_ns(),
# which is a big-int after ~1 s of uptime and so allocated on every tick(). Deadlines are kept
# in 1/16 ms units RELATIVE TO THE PATTERN START (a PICO-8 tick = 1/128 s = 125 of them, exact),
# so a pattern of any speed stays a small int and the wrap only touches the one subtraction.
_MASK = const((1 << 29) - 1)
_TICK = const(125)                  # PICO-8 tick = 1/128 s in 1/16 ms; note duration = speed ticks

try:
    from supervisor import ticks_ms as _ms
except ImportError:                 # sim / desktop: same 2**29 period, same math
    _mono = time.monotonic
    def _ms():
        return int(_mono() * 1000) & _MASK

# PICO-8 pitch 0 = C0 = 65.406 Hz
_FREQ = tuple(65.406 * (2 ** (p / 12)) for p in range(64))


def _ramp(a, b):
    import array
    return array.array("h", (a, b))


class Player:
    def __init__(self, synth_host, bank, level=1.0, _now=_ms, _synth=None):
        """`synth_host` = picogame_synth.Synth; `bank` = a generated song module (or any
        object with .SFX and .PATTERNS). `level` scales all music volumes 0..1.
        `_now` = a millisecond clock (test hook; wraps like supervisor.ticks_ms).
        The player brings its OWN synthesizer on the mixer's MUSIC voice (voice 0 - the
        same slot `load_midi` uses), so `set_levels(music=...)` applies to it and the
        sfx Kit's note management never touches music notes. One music system at a time
        on that voice: PICO-8 music or a MidiTrack, not both."""
        self._on = bool(getattr(synth_host, "available", False))
        if not self._on:
            self._synth = None
        elif _synth is not None:
            self._synth = _synth                 # test hook
        else:
            self._synth = synthio.Synthesizer(sample_rate=synth_host.sample_rate,
                                              channel_count=1)
            synth_host.mixer.voice[0].play(self._synth)
        self._sfx = bank.SFX
        self._patterns = bank.PATTERNS
        self._level = level
        self._now = _now
        self._t0 = 0                         # ms at pattern start; deadlines count from it
        self._pulse = None                   # the 25 % pulse table, built on first use
        self._vib = None
        self._down = _ramp(32767, 0)         # one-shot ramps (scaled per use)
        # soft edges on every note - without an envelope synthio starts/cuts samples
        # instantly and the edges click audibly at note rate (PICO-8 smooths them too)
        self._env = synthio.Envelope(attack_time=0.005, decay_time=0.0,
                                     sustain_level=1.0, release_time=0.04)
        self._pattern = -1
        self._loop_start = 0
        self._playing = False
        # per channel: sfx id, note index, next-note deadline, live Note, arp state
        self._ch_sfx = [0xFF] * 4
        self._ch_i = [0] * 4
        self._ch_next = [0] * 4
        self._ch_note = [None] * 4
        self._ch_arp = [None] * 4            # (freqs, sub_dur_ns, next_ns, idx) or None
        # Build the shared waveforms this bank uses NOW (startup): picogame_synth makes
        # its tables on first use, and a first use from tick() would build one mid-frame.
        if self._on:
            used = 0
            for _speed, _l0, _l1, data in self._sfx.values():
                for i in range(1, len(data), 3):
                    if data[i] & 0x0F:                       # volume > 0: the note sounds
                        used |= 1 << ((data[i] >> 4) & 7)
            for w in range(8):
                if used & (1 << w):
                    self._wave(w)

    @property
    def available(self):
        return self._on

    # --- waveforms (PICO-8 0-7 -> picogame_synth's shared read-only tables) ------------
    def _wave(self, w):
        if w == 3:
            return _ps.SQUARE
        if w == 0 or w == 5:
            return _ps.TRIANGLE              # triangle / organ approx
        if w == 1 or w == 2:
            return _ps.SAW                   # tilted saw approx / saw
        if w == 6:
            return _ps.NOISE
        if w == 4:                           # pulse: the one shape without a shared table
            if self._pulse is None:
                self._pulse = _ps.square(0.25)
            return self._pulse
        return _ps.SINE                      # phaser approx

    # --- transport ----------------------------------------------------------------
    def play(self, pattern=0, level=None):
        if level is not None:
            self._level = level
        if not self._on:
            return
        self.stop()
        self._loop_start = pattern
        self._start_pattern(pattern)

    def stop(self):
        if not self._on:
            return
        for ch in range(4):
            n = self._ch_note[ch]
            if n is not None:
                self._synth.release(n)
                self._ch_note[ch] = None
            self._ch_sfx[ch] = 0xFF
            self._ch_arp[ch] = None
        self._playing = False

    def _start_pattern(self, pi):
        row = self._patterns[pi]
        self._pattern = pi
        if row[4] & 1:
            self._loop_start = pi
        self._t0 = self._now()               # every channel restarts at 0 from here
        for ch in range(4):
            sid = row[ch]
            self._ch_sfx[ch] = sid if sid in self._sfx else 0xFF
            if self._ch_sfx[ch] == 0xFF and self._ch_note[ch] is not None:
                self._synth.release(self._ch_note[ch])   # channel absent in the new pattern
                self._ch_note[ch] = None
            self._ch_i[ch] = 0
            self._ch_next[ch] = 0
            self._ch_arp[ch] = None
        self._playing = True

    # --- per-frame ------------------------------------------------------------------
    def tick(self):
        """Advance the song; call once per frame. Cheap when nothing is due."""
        if not self._playing:
            return
        now = ((self._now() - self._t0) & _MASK) << 4      # 1/16 ms since pattern start
        leader_done = False
        for ch in range(4):
            sid = self._ch_sfx[ch]
            if sid == 0xFF:
                continue
            arp = self._ch_arp[ch]
            if arp is not None and now >= arp[2]:
                freqs, sub, _next, idx = arp
                idx = (idx + 1) % 4
                n = self._ch_note[ch]
                if n is not None:
                    n.frequency = freqs[idx]
                self._ch_arp[ch] = (freqs, sub, now + sub, idx)
            if now < self._ch_next[ch]:
                continue
            speed, _l0, _l1, data = self._sfx[sid]
            dur = max(1, speed) * _TICK
            i = self._ch_i[ch]
            if i >= 32:
                if self._ch_note[ch] is not None:        # a finished channel goes silent
                    self._synth.release(self._ch_note[ch])
                    self._ch_note[ch] = None
                if ch == self._leader():
                    leader_done = True
                continue
            self._note_on(ch, sid, i, dur, now)
            self._ch_i[ch] = i + 1
            self._ch_next[ch] += dur
            if self._ch_i[ch] >= 32 and ch == self._leader():
                leader_done = True
        if leader_done:
            self._advance_pattern()

    def _leader(self):
        for ch in range(4):
            if self._ch_sfx[ch] != 0xFF:
                return ch
        return 0

    def _advance_pattern(self):
        flags = self._patterns[self._pattern][4]
        if flags & 4:
            self.stop()
            return
        if flags & 2:
            self._start_pattern(self._loop_start)
            return
        nxt = self._pattern + 1
        if nxt >= len(self._patterns):
            self._start_pattern(self._loop_start)
        else:
            self._start_pattern(nxt)

    # --- note handling ----------------------------------------------------------------
    def _note_on(self, ch, sid, i, dur, now):
        old = self._ch_note[ch]
        if old is not None:
            self._synth.release(old)
            self._ch_note[ch] = None
        self._ch_arp[ch] = None
        _speed, _l0, _l1, data = self._sfx[sid]
        o = i * 3
        pitch = data[o]
        wv = data[o + 1]
        fx = data[o + 2]
        vol = wv & 0x0F
        wave = (wv >> 4) & 0x0F
        if vol == 0:
            return                            # rest
        amp = (vol / 7.0) * self._level
        note = synthio.Note(_FREQ[pitch & 63], waveform=self._wave(wave & 7),
                            amplitude=amp, envelope=self._env)
        secs = dur / 16000.0
        if fx == 1 and i > 0:                 # slide from the previous row's pitch
            prev = data[o - 3] & 63
            note.bend = synthio.LFO(waveform=self._down, once=True, rate=1 / secs,
                                    scale=(prev - pitch) / 12.0)
        elif fx == 2:                         # vibrato (one shared LFO)
            if self._vib is None:
                self._vib = synthio.LFO(rate=7.5, scale=0.0208)   # ~quarter semitone
            note.bend = self._vib
        elif fx == 3:                         # drop
            note.bend = synthio.LFO(waveform=self._down, once=True, rate=1 / secs,
                                    scale=-2.0)
        elif fx == 4:                         # fade in
            note.amplitude = synthio.LFO(waveform=self._down, once=True, rate=1 / secs,
                                         scale=-amp, offset=amp)
        elif fx == 5:                         # fade out
            note.amplitude = synthio.LFO(waveform=self._down, once=True, rate=1 / secs,
                                         scale=amp)
        elif fx == 6 or fx == 7:              # arpeggio over the row group of 4
            g = (i & ~3) * 3
            freqs = tuple(_FREQ[data[g + k * 3] & 63] for k in range(4))
            # picotool spec: steps run "at speed 2 (fast) / 4 (slow)" - ABSOLUTE ticks
            sub = (2 if fx == 6 else 4) * _TICK
            self._ch_arp[ch] = (freqs, sub, now + sub, i & 3)
        self._synth.press(note)
        self._ch_note[ch] = note
