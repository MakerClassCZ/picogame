# Simulator stand-in for CircuitPython's `audiomixer`. A Mixer of Voices. picogame_synth uses
# voice 0 = looping music, voice 1 = the live SFX Synthesizer. A MidiTrack source routes to
# _simaudio (real sound via pygame.mixer); anything else (sample WaveFiles from picogame_audio)
# stays a silent no-op, exactly as before - so the sample-audio path is unaffected.

import _simaudio


class _Voice:
    def __init__(self):
        self.level = 1.0
        self.playing = False
        self._music = False

    def play(self, source, loop=False):
        if hasattr(source, "_notes"):          # a synthio MidiTrack -> looping music
            self._music = True
            self.playing = True
            _simaudio.play_music(source, self.level)
        else:                                  # a Synthesizer (SFX) reads .level at press; samples = no-op
            self._music = False
            try:
                source._voice = self
            except Exception:
                pass

    def stop(self):
        self.playing = False
        if self._music:
            _simaudio.stop_music()


class Mixer:
    def __init__(self, voice_count=2, sample_rate=22050, channel_count=1,
                 bits_per_sample=16, buffer_size=1024, **kw):
        self.voice = [_Voice() for _ in range(voice_count)]
