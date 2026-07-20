# picogame audio helper: thin convenience layer over CircuitPython's audio stack
# (audiopwmio + audiocore + audiomixer) for the PicoPad's PWM audio,
# no firmware changes - those modules are enabled by default on RP2040.
#
# A Mixer lets sound effects overlap and play under music. IMPORTANT: every
# sample (WaveFile / RawSample) must match the Mixer's format
# (sample_rate / channel_count / bits_per_sample / samples_signed). The defaults
# below (22050 Hz, mono, 16-bit signed) match typical ugame .wav assets.

import audiocore
import audiomixer
import picogame_audioout


class Audio:
    def __init__(self, pin=None, voices=4, sample_rate=22050, channels=1,
                 bits=16, signed=True):
        if voices < 2:                                     # voice 0 is music, 1.. are sfx; with
            raise ValueError("Audio needs voices >= 2 "    # only 1 voice the default sfx path
                             "(voice 0 = music, 1.. = sfx)")  # would index a nonexistent voice
        # Platform audio output: I2S DAC on the Fruit Jam, PWM on PicoPad-class boards, resolved by
        # picogame_audioout (an explicit `pin` forces PWM). Keeps games board-agnostic.
        self.out = picogame_audioout.make_output(sample_rate, pin)
        try:                                               # if the mixer alloc / play() raises
            self.mixer = audiomixer.Mixer(                 # (MemoryError on a tight heap), release
                voice_count=voices, sample_rate=sample_rate, channel_count=channels,  # the PWM pin
                bits_per_sample=bits, samples_signed=signed)  # so a later Audio()/Synth() can claim
            self.out.play(self.mixer)                      # it (the caller has no object to deinit).
        except Exception:
            self.out.deinit()
            raise
        self.voices = voices
        self.music_voice = 0      # voice 0 reserved for background music
        self._sfx_next = 1        # round-robin over voices 1..voices-1

    def load(self, path):
        """Open a .wav as a reusable sample (keep the returned object alive)."""
        return audiocore.WaveFile(open(path, "rb"))

    def play(self, sample, *, voice=None, loop=False, volume=1.0):
        """Play a sample on a voice (default: round-robin sfx voice). Returns the voice index."""
        if voice is None:
            voice = self._sfx_next
            self._sfx_next += 1
            if self._sfx_next >= self.voices:
                self._sfx_next = 1
        v = self.mixer.voice[voice]
        v.level = volume
        v.play(sample, loop=loop)
        return voice

    def sfx(self, sample, volume=1.0):
        """Fire-and-forget sound effect on a free sfx voice."""
        return self.play(sample, loop=False, volume=volume)

    def music(self, sample, loop=True, volume=1.0):
        """Play looping background music on the reserved music voice."""
        self.play(sample, voice=self.music_voice, loop=loop, volume=volume)

    def stop(self, voice=None):
        if voice is None:
            for v in self.mixer.voice:
                v.stop()
        else:
            self.mixer.voice[voice].stop()

    def stop_music(self):
        self.mixer.voice[self.music_voice].stop()

    def deinit(self):
        """Release the PWM audio pin (board.AUDIO is a singleton). Call when tearing down a scene that
        built its own Audio, or the NEXT Audio() raises 'pin in use'."""
        try:
            self.out.deinit()
        except Exception:
            pass

    @property
    def is_playing(self):
        for v in self.mixer.voice:           # a plain loop - no generator object per poll
            if v.playing:
                return True
        return False


def tone(frequency=440, ms=120, sample_rate=22050, volume=0.6):
    """Build a short square-wave RawSample (no .wav file needed) for testing /
    simple beeps. Matches a mono 16-bit signed Mixer."""
    import array
    import math
    n = max(1, int(sample_rate * ms / 1000))
    amp = int(32767 * volume)
    period = max(2, int(sample_rate / max(1, frequency)))
    buf = array.array("h", (amp if (i % period) < (period // 2) else -amp for i in range(n)))
    return audiocore.RawSample(buf, sample_rate=sample_rate)
