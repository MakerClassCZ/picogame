# picogame_synth: real on-device sound via synthio - no WAV files, no sample RAM.
#
# CircuitPython's synthio generates audio in real time (oscillators + ADSR envelopes +
# LFOs + filters), so a whole SFX set or a MIDI tune costs almost no RAM. This wraps the
# Fruitris pattern (PWMAudioOut -> Mixer -> Synthesizer) with built-in waveforms, so games
# can finally make noise on the PicoPad/PicoSystem. (Sample-based audio lives in
# picogame_audio; this is the synthesis path.)
#
#   import picogame_synth as snd
#   s = snd.Synth()                                   # board.AUDIO, PWM out
#   beep = snd.note(72, snd.SQUARE, decay=0.08)       # an SFX (build once)
#   s.sfx(beep)                                       # fire it (retriggers cleanly)
#
# Uses synthio + audiopwmio + audiomixer when the firmware has them (both our boards do).
# SAFE ON AUDIO-LESS FIRMWARE: if those modules are missing, importing this lib still works
# and the whole API degrades to silent no-ops (Synth/Drone/note/load_midi all accept the same
# args and return inert values). ALSO SAFE ON A TIGHT HEAP: if Synth() itself fails mid-init
# (MemoryError allocating the mixer buffers, or the pin is claimed), the instance degrades to
# the same silent no-ops instead of raising - a game needs ZERO try/except guard code either
# way. Branch on the module flag `AVAILABLE` (modules present) or `synth.available` (this
# instance actually has audio out) if you want e.g. to hide a volume option.
# (The simulator provides its own synthio stub, so under the sim the real path runs.)

import array
import math
import os

try:
    import synthio
    from audiomixer import Mixer
    import picogame_audioout            # shared PWM/I2S output factory (I2S DAC on the Fruit Jam)
    AVAILABLE = True
except ImportError:            # no synthio/audiomixer (audio-less firmware or desktop) -> silent no-op
    AVAILABLE = False

try:
    from micropython import const
except ImportError:            # desktop Python has no micropython module
    def const(x):
        return x

# ---- built-in oscillator waveforms (signed 16-bit, one cycle) ----
_LEN = const(256)
_AMP = const(28000)


def sine():
    return array.array("h", [int(_AMP * math.sin(2 * math.pi * i / _LEN)) for i in range(_LEN)])


def saw():
    return array.array("h", [int(_AMP * (2.0 * i / _LEN - 1.0)) for i in range(_LEN)])


def triangle():
    return array.array("h", [int(_AMP * (2.0 * abs(2.0 * i / _LEN - 1.0) - 1.0)) for i in range(_LEN)])


def square(duty=0.5):
    """Square/pulse wave. `duty` = high fraction of the cycle: 0.5 = classic square,
    0.25 / 0.125 = the thinner NES pulse timbres - same note, audibly different colour."""
    hi = max(1, min(_LEN - 1, int(_LEN * duty)))
    return array.array("h", [_AMP if i < hi else -_AMP for i in range(_LEN)])


def noise():
    out = array.array("h", bytes(2 * _LEN))
    s = 0x1234
    for i in range(_LEN):
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        out[i] = (s >> 8) % (2 * _AMP) - _AMP
    return out


# Prebuilt singletons (share one waveform across notes - they're read-only). Built ONLY
# on an audio-capable build: an audio-less firmware can't play them, so it keeps inert
# None placeholders (~2.5 KiB saved) while `snd.SQUARE` etc. still resolve (games alias
# them at import; the no-op note() ignores the waveform anyway).
# RAMP: a 2-sample LFO shape; with once=True the LFO interpolates max->min LINEARLY over
# 1/rate seconds - a clean ramp (pitch_bend(waveform=RAMP) = straight glide vs sine wobble).
if AVAILABLE:
    SINE = sine()
    SAW = saw()
    TRIANGLE = triangle()
    SQUARE = square()
    NOISE = noise()
    RAMP = array.array("h", [32767, -32768])
else:
    SINE = SAW = TRIANGLE = SQUARE = NOISE = RAMP = None


class _Null:
    """Inert stand-in for notes/LFOs/tracks/mixers: calls and indexing return self, unknown
    attribute reads return self, attribute writes stick (Drone.set, drone.note.waveform = ...),
    truth value is False. Used by the no-op fallback below AND by a Synth that failed to
    initialise (MemoryError on a tight heap) - so the API stays call-safe either way."""

    def __call__(self, *args, **kwargs):
        return self

    def __getattr__(self, name):
        return self

    def __getitem__(self, i):
        return self

    def __bool__(self):
        return False


def note(midi, waveform=None, attack=0.005, decay=0.06, sustain=0.0, release=0.08,
         amplitude=0.6, bend=None, cutoff=None):
    """Build a reusable SFX/instrument note. `midi` = MIDI number (60 = middle C);
    `bend` = an LFO (see pitch_bend) for a slide; `cutoff` = low-pass filter Hz."""
    env = synthio.Envelope(attack_time=attack, decay_time=decay,
                           sustain_level=sustain, release_time=release)
    flt = synthio.Biquad(synthio.FilterMode.LOW_PASS, cutoff) if cutoff else None
    return synthio.Note(frequency=synthio.midi_to_hz(midi), waveform=waveform,
                        envelope=env, amplitude=amplitude, bend=bend, filter=flt)


def pitch_bend(semitones, ms, waveform=None, once=True):
    """An LFO for note `bend`: slide by `semitones` over `ms` ms (e.g. a laser zap).
    Default LFO shape is a sine (a wobble); pass waveform=RAMP for a straight glide."""
    return synthio.LFO(waveform=waveform, rate=1000.0 / ms, scale=semitones / 12.0, once=once)


class Synth:
    """PWM audio out -> a mixer with a music voice + a synth voice for SFX.

    Init is self-guarding: on a heap too tight for the mixer buffers (MemoryError) or a
    claimed pin, the instance degrades to silent no-ops instead of raising - the game runs
    without sound and without any try/except of its own. Check `.available` to branch."""

    def __init__(self, pin=None, sample_rate=22050, buffer_size=2048,
                 music_level=0.4, sfx_level=0.7):
        self.sample_rate = sample_rate
        self.music_level = music_level    # remembered DESIRED levels (mute keeps them, so
        self.sfx_level = sfx_level         # set_levels() while muted stays silent until unmute)
        self._muted = False
        self._last_sfx = None        # last one-shot SFX; released on the next sfx so HELD notes
        #                              (a Drone engine/siren) and the music voice are never cut off
        self._seq = None             # the ACTIVE sequence (the caller's own event list; reused,
        self._seq_i = 0              # never copied) + read cursor + fire frame -> zero per-fire
        self._seq_base = 0           # allocation (monophonic: only one sequence pending at a time)
        self._frame = 0
        self._win = 0                # protected-window frames left; _winp = its priority
        self._winp = 0
        try:
            self.audio = picogame_audioout.make_output(sample_rate, pin)   # I2S/PWM; raises -> silent
            self.mixer = Mixer(voice_count=2, sample_rate=sample_rate, channel_count=1,
                               bits_per_sample=16, buffer_size=buffer_size)
            self.audio.play(self.mixer)
            self.mixer.voice[0].level = music_level      # voice 0: music (MidiTrack)
            self.mixer.voice[1].level = sfx_level        # voice 1: live synth SFX
            self.synth = synthio.Synthesizer(sample_rate=sample_rate, channel_count=1)
            self.mixer.voice[1].play(self.synth)
            self.available = True
        except Exception as e:       # MemoryError on a tight heap / pin in use -> run silent
            import picogame_debug     # settings.toml PICOGAME_DEBUG=1 -> print the real reason (else silent)
            picogame_debug.note("synth: init failed ->", repr(e))
            out = getattr(self, "audio", None)
            if out is not None and not isinstance(out, _Null):
                try:
                    out.deinit()     # release the pin so a later Audio()/Synth() can claim it
                except Exception:
                    pass
            self.audio = self.mixer = self.synth = _Null()
            self.available = False

    @staticmethod
    def _retrigger(nn):
        """Retrigger a note's LFOs so a repeat sounds identical. Reads fields directly -
        no aggregate tuple built (this runs on every SFX / hit spam)."""
        b = nn.bend
        if isinstance(b, synthio.LFO):
            b.retrigger()
        a = nn.amplitude
        if isinstance(a, synthio.LFO):
            a.retrigger()
        f = nn.filter
        if isinstance(f, synthio.Biquad) and isinstance(f.frequency, synthio.LFO):
            f.frequency.retrigger()

    def _emit(self, n):
        """Raw monophonic press: retrigger the voice's LFOs, release the previous SFX
        (never held drones / music), press. No arbitration - used by sfx() after it
        wins, and by tick() for the tail notes of a sequence (which already won)."""
        if isinstance(n, tuple):                 # a layered voice: retrigger each note
            for nn in n:
                self._retrigger(nn)
        else:
            self._retrigger(n)                   # single note - no (n,) allocation
        if self._last_sfx is not None:           # release only the previous SFX, never held drones
            self.synth.release(self._last_sfx)
        self.synth.press(n)                      # synthio takes a Note or an iterable of Notes
        self._last_sfx = n

    def sfx(self, n, priority=0, window=0):
        """Play a one-shot SFX - a Note or a TUPLE of Notes (a layered voice). Monophonic
        last-wins: cuts the previous SFX (leaves held drones + music). `priority`/`window`
        add channel arbitration: while a higher-priority sound holds a protected `window`
        (frames), a LOWER-priority call is DROPPED (returns False) - spam can't erase it.
        Firing cancels any pending sequence tail. Defaults (0,0) = plain last-wins."""
        if not self.available:                   # a failed-init Synth is a true no-op
            return False
        if self._win > 0 and priority < self._winp:
            return False                         # dropped inside a higher sound's window
        self._seq = None                         # a new discrete sound cancels a pending sequence
        self._emit(n)
        self._win = window                       # ALWAYS reset (window=0 clears a stale window,
        self._winp = priority                    # so a replaced sound's window can't leak forward)
        return True

    def sfx_seq(self, events, priority=0, window=0):
        """Fire a timed sequence: events = [(delay_frames, voice), ...] (delays relative to
        now; events[0] is the trigger). The trigger goes through sfx() arbitration; the tail
        is read straight from `events` by tick() (no copy, no per-fire allocation). Dropped
        trigger -> nothing scheduled."""
        if not self.available or not events or not self.sfx(events[0][1], priority, window):
            return False
        self._seq = events                       # reuse the caller's immutable list as-is
        self._seq_i = 1
        self._seq_base = self._frame
        return True

    def tick(self):
        """Advance the protected window + release due sequence notes - call once per frame.
        Tail notes bypass arbitration (they belong to the sound that already won)."""
        if self._win > 0:
            self._win -= 1
        self._frame += 1
        s = self._seq
        if s is None:
            return
        while self._seq_i < len(s) and self._frame - self._seq_base >= s[self._seq_i][0]:
            self._emit(s[self._seq_i][1])
            self._seq_i += 1
        if self._seq_i >= len(s):
            self._seq = None

    def press(self, n):
        self.synth.press(n)

    def release(self, n):
        self.synth.release(n)

    def music(self, midi_track):
        self.mixer.voice[0].play(midi_track, loop=True)

    def stop_music(self):
        self.mixer.voice[0].stop()

    def set_levels(self, music=None, sfx=None):
        """Runtime volume (0.0-1.0). This is the knob; the Synth owns no settings. A game
        builds a volume row with picogame_options, reads it (`m.value("vol")`), optionally
        persists it with picogame_save, and calls set_levels itself - no coupling either way.
        Updating a level while muted changes only the REMEMBERED level, not the live output."""
        if music is not None:
            self.music_level = music
        if sfx is not None:
            self.sfx_level = sfx
        if not self._muted:                  # muted output stays silent until unmute
            self._apply_levels()

    def _apply_levels(self):
        try:
            self.mixer.voice[0].level = 0.0 if self._muted else self.music_level
            self.mixer.voice[1].level = 0.0 if self._muted else self.sfx_level
        except (AttributeError, IndexError):
            pass                             # _Null mixer on a failed-init Synth

    def mute(self, on):
        """Silence both voices (on=True) or restore the remembered levels (on=False)."""
        self._muted = on
        self._apply_levels()


class Drone:
    """A continuously-HELD note for engine / siren / drone sounds. Press it once, then call
    set(freq, amp) every frame: synthio reads the note's live .frequency/.amplitude per audio
    buffer, so the pitch tracks whatever you feed it (e.g. an engine note driven by car speed).
    Cheap - one held note on the SFX voice.

        eng = snd.Drone(s, waveform=snd.SAW)
        eng.start()                                         # at race start
        eng.set(70 + 270 * rev, amplitude=0.2 + 0.5 * rev)  # each frame, rev = speed/max 0..1
        eng.stop()                                          # on the title / results screen
    """

    def __init__(self, synth, waveform=None, amplitude=0.35, attack=0.03, release=0.12):
        self.synth = synth
        self.note = synthio.Note(
            frequency=110.0, waveform=waveform if waveform is not None else SAW,
            envelope=synthio.Envelope(attack_time=attack, decay_time=0.0,
                                      sustain_level=1.0, release_time=release),
            amplitude=amplitude)
        self.playing = False

    def start(self):
        if not self.playing:
            self.synth.press(self.note)
            self.playing = True

    def set(self, frequency, amplitude=None):
        self.note.frequency = frequency
        if amplitude is not None:
            self.note.amplitude = amplitude

    def stop(self):
        if self.playing:
            self.synth.release(self.note)
            self.playing = False


def load_midi(path, sample_rate=22050, waveform=None, envelope=None, tempo=120, ppqn=240):
    """Load a .mid file as a synthio.MidiTrack to play on the music voice (Synth.music)."""
    with open(path, "rb") as f:
        if f.read(4) != b"MThd":
            f.seek(0)
        else:
            # already consumed the 4-byte "MThd" magic; a standard format-0 SMF header is 22 bytes
            # total (MThd chunk 14 + MTrk header 8), so skip the remaining 18 to land on event 0.
            f.read(18)
        return synthio.MidiTrack(f.read(), tempo=ppqn * tempo // 60,
                                 sample_rate=sample_rate, waveform=waveform, envelope=envelope)


# ---- silent no-op fallback (audio-less firmware) ----------------------------------------
# When synthio/audiopwmio/audiomixer are missing, the definitions below SHADOW the real
# note/pitch_bend/Synth/Drone/load_midi above (which stay byte-identical for the normal
# path). Same signatures, no audio hardware touched, no mixers/buffers allocated - every
# call is a cheap no-op so game audio code runs unchanged, just silently. The waveform
# constants above are None placeholders on this path (nothing can play them).

if not AVAILABLE:

    # (_Null lives at module level above - shared with the failed-init degrade path.)

    def note(midi, waveform=None, attack=0.005, decay=0.06, sustain=0.0, release=0.08,
             amplitude=0.6, bend=None, cutoff=None):
        return _Null()

    def pitch_bend(semitones, ms, waveform=None, once=True):
        return _Null()

    def load_midi(path, sample_rate=22050, waveform=None, envelope=None, tempo=120, ppqn=240):
        return _Null()

    class Synth:
        """No-op Synth: same surface, no audio out, no mixer, no synthesizer."""

        def __init__(self, pin=None, sample_rate=22050, buffer_size=2048,
                     music_level=0.4, sfx_level=0.7):
            self.sample_rate = sample_rate
            self.music_level = music_level   # parity with the real Synth: reading synth.sfx_level
            self.sfx_level = sfx_level        # must work on an audio-less build, not AttributeError
            self._muted = False
            self.audio = _Null()
            self.mixer = _Null()
            self.synth = _Null()
            self._last_sfx = None
            self.available = False

        def sfx(self, n, priority=0, window=0):
            return False

        def sfx_seq(self, events, priority=0, window=0):
            return False

        def tick(self):
            pass

        def press(self, n):
            pass

        def release(self, n):
            pass

        def music(self, midi_track):
            pass

        def stop_music(self):
            pass

        def set_levels(self, music=None, sfx=None):
            if music is not None:
                self.music_level = music
            if sfx is not None:
                self.sfx_level = sfx

        def mute(self, on):
            self._muted = on

    class Drone:
        """No-op Drone: keeps the .note / .playing surface so per-frame set() calls work."""

        def __init__(self, synth, waveform=None, amplitude=0.35, attack=0.03, release=0.12):
            self.synth = synth
            self.note = _Null()
            self.playing = False

        def start(self):
            self.playing = True

        def set(self, frequency, amplitude=None):
            self.note.frequency = frequency
            if amplitude is not None:
                self.note.amplitude = amplitude

        def stop(self):
            self.playing = False
