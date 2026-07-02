# Simulator stand-in for CircuitPython's device-only `synthio`. Just enough of the API that
# picogame_synth uses, backed by _simaudio (renders notes -> pygame.mixer). On hardware the REAL
# synthio is used; this file is only found under CPython (the sim dir is on sys.path).

import _simaudio

midi_to_hz = _simaudio.midi_to_hz


class Envelope:
    def __init__(self, attack_time=0.005, decay_time=0.06, sustain_level=0.0, release_time=0.08):
        self.attack_time = attack_time
        self.decay_time = decay_time
        self.sustain_level = sustain_level
        self.release_time = release_time


class LFO:
    def __init__(self, waveform=None, rate=1.0, scale=1.0, once=False):
        self.waveform = waveform
        self.rate = rate
        self.scale = scale
        self.once = once

    def retrigger(self):
        pass                                   # the sim bakes the sweep into the rendered clip


class FilterMode:
    LOW_PASS = "low_pass"


class Biquad:
    def __init__(self, mode, frequency):
        self.mode = mode
        self.frequency = frequency


class Note:
    def __init__(self, frequency=440.0, waveform=None, envelope=None, amplitude=1.0,
                 bend=None, filter=None):
        self.frequency = frequency
        self.waveform = waveform
        self.envelope = envelope or Envelope()
        self.amplitude = amplitude
        self.bend = bend
        self.filter = filter


def _parse_events(data):
    """Parse raw MTrk event bytes (as load_midi/our in-code builder emit) -> [(midi, on_tick, dur_tick)]."""
    notes, active = [], {}
    i, tick, ln = 0, 0, len(data)
    while i < ln:
        delta = 0                              # variable-length delta time
        while i < ln:
            b = data[i]
            i += 1
            delta = (delta << 7) | (b & 0x7F)
            if not (b & 0x80):
                break
        tick += delta
        if i >= ln:
            break
        st = data[i]
        i += 1
        if st == 0xFF:                         # meta event: <type> <len> <bytes>
            if i + 1 >= ln:
                break
            i += 1
            mlen = data[i]
            i += 1 + mlen
            continue
        if i + 1 >= ln:
            break
        note = data[i]
        vel = data[i + 1]
        i += 2
        if (st & 0xF0) == 0x90 and vel > 0:
            active[note] = tick
        else:                                  # note-off (0x80, or 0x90 with velocity 0)
            on = active.pop(note, None)
            if on is not None:
                notes.append((note, on, max(1, tick - on)))
    return notes


class MidiTrack:
    def __init__(self, events, tempo=960, sample_rate=22050, waveform=None, envelope=None):
        self._tempo = tempo                    # ticks per second
        self._wave = waveform
        self._env = envelope or Envelope()
        try:
            self._notes = _parse_events(bytes(events))
        except Exception:
            self._notes = []


class Synthesizer:
    def __init__(self, sample_rate=22050, channel_count=1):
        self._voice = None                     # set by the Mixer voice that plays this synth

    def press(self, note):
        lvl = self._voice.level if self._voice is not None else 0.7
        _simaudio.play_note(note, lvl)

    def release(self, note):
        pass                                   # one-shot clips self-terminate
