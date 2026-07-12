# picogame_sfx: the SIGNATURE picogame sound - one ready-made SFX theme over picogame_synth.
#
# OPTIONAL, self-contained theme library. Import the theme you want as `sfx`:
#
#   import picogame_synth as snd
#   import picogame_sfx as sfx                 # the signature ("Fat Arcade Lite") theme
#   s = snd.Synth()
#   kit = sfx.Kit(s)                           # builds this theme's voices ONCE
#   ...
#   kit.coin(); kit.zap(); kit.explosion()     # fire-and-forget
#   ...
#   kit.tick()                                 # once per frame (drives multi-note sequences)
#
# A DIFFERENT THEME IS A PEER FILE, not a subclass or a parameter: e.g. a future
# picogame_sfx_chip.py, self-contained the same way, exposing its own Kit (possibly with
# extra sounds). You import exactly ONE theme and alias it `sfx`; they never coexist, so
# each theme carrying its own recipe helpers is fine (no runtime cost, nothing shared to
# break). The only shared layer is picogame_synth (the channel) - kept lean on purpose so
# a game hand-rolling its own sound isn't handed SFX-recipe clutter it won't use.
#
# WHERE THE WORK LIVES: the CHANNEL - monophonic last-wins, priority + protected window,
# the frame sequencer - is picogame_synth.Synth (sfx/sfx_seq/tick), reusable by anyone.
# THIS FILE is one theme: its own synthesis helpers (_crack/_body/_fall/...), its voice
# recipes, its Kit (the named methods + the vocabulary priority numbers).
#
# Palette ("Fat Arcade Lite"): tonal cues (blip/coin/powerup/zap/pew/jump) = one note on
# a baked FAT table (square lead + saw an octave below, always low-passed); impacts
# (hit/hurt/boom) = a noise crack + a ring-mod 2f/3f body graded by pitch+length;
# explosion = one aperiodic bend-smear noise crack. Everything stays in the PicoPad
# speaker's band (~200 Hz-5 kHz); at most ~2 voices sound at once. ~3 KB, no big tables.
#
# SAFE EVERYWHERE: audio-less firmware -> silent no-ops; a Kit on a Synth that failed init
# (synth.available == False) allocates NOTHING and stays inert. Check kit.available.
#
# Vocabulary (review/audio-vocabulary.md - the SHARED design, kept as a doc not shared
# code): classes blip(UI) < pew/zap/jump/hit(Feedback) < hurt < coin/boom(Event) <
# powerup/explosion(Scene). A scene event holds a protected window during which lower
# classes are dropped, so a hit spam can't erase a boss explosion. hurt = "the hit was ON
# YOU". hit pitch-rotates +-2 st per fire (anti-fatigue, rotate=False). Windows assume 30 fps.

import picogame_synth as snd

try:
    import array
    import synthio
    AVAILABLE = snd.AVAILABLE
except ImportError:
    AVAILABLE = False

# Per-slot priority class (higher = wins) and protected window in frames @30 fps.
# These are the VOCABULARY - theme-independent, so they live here, not in a theme dict.
# pew shares the Feedback class with zap/hit (all prio 20): honest last-wins. (An earlier
# pew=18 did nothing - priority only bites inside a protected window, which Feedback has none.)
_PRIO = {"blip": 10, "pew": 20, "zap": 20, "jump": 20, "hit": 20, "hurt": 25,
         "coin": 30, "boom": 30, "powerup": 40, "explosion": 40}
_WIN = {"hurt": 4, "boom": 3, "powerup": 5, "explosion": 18}


if AVAILABLE:

    # ---- generic synthesis primitives (shared with any theme module) ----
    def _env(attack, decay, release):
        return synthio.Envelope(attack_time=attack, decay_time=decay,
                                sustain_level=0.0, release_time=release)

    def _lp(cutoff, q=0.7):
        try:
            return synthio.Biquad(synthio.FilterMode.LOW_PASS, cutoff, Q=q)
        except TypeError:              # older firmware without Q
            return synthio.Biquad(synthio.FilterMode.LOW_PASS, cutoff)

    def _fall(semitones, ms):
        """One-shot linear pitch fall: starts semitones/12 octaves up, lands on base."""
        k = semitones / 24.0
        return synthio.LFO(waveform=snd.RAMP, rate=1000.0 / ms, scale=k, offset=k, once=True)

    def _rise(semitones, ms):
        """One-shot linear pitch rise: starts on base, climbs semitones/12 octaves up."""
        k = semitones / 24.0
        return synthio.LFO(waveform=snd.RAMP, rate=1000.0 / ms, scale=-k, offset=k, once=True)

    def _curve(points, semitones, ms):
        """One-shot pitch bend tracing a custom contour: `points` = normalized bend values in
        [-1, 1] as a fraction of the span (0 = base, 1 = span up), traversed once over `ms` then
        held. bend is in OCTAVES (log = perceptually linear). A stepped `points` list reads as
        audible pitch STEPS on the piezo (smooth contours don't) - used for the jump whoop."""
        wav = array.array("h", [max(-32767, min(32767, int(p * 32767))) for p in points])
        return synthio.LFO(waveform=wav, rate=1000.0 / ms, scale=semitones / 12.0,
                           offset=0.0, once=True)

    def _sweep_lp(hi, lo, ms, q=1.1):
        """Biquad whose cutoff falls hi->lo over ms (an LFO on its frequency)."""
        lfo = synthio.LFO(waveform=snd.RAMP, rate=1000.0 / ms,
                          scale=(hi - lo) / 2.0, offset=(hi + lo) / 2.0, once=True)
        try:
            return synthio.Biquad(synthio.FilterMode.LOW_PASS, lfo, Q=q)
        except TypeError:
            return synthio.Biquad(synthio.FilterMode.LOW_PASS, lfo)

    def _crack(decay, cutoff, amplitude, q=0.9):
        """A filtered noise transient (the attack of an impact)."""
        return synthio.Note(frequency=720.0, waveform=snd.NOISE,
                            envelope=_env(0.0, decay, max(0.03, decay * 0.5)),
                            amplitude=amplitude, filter=_lp(cutoff, q))

    def _body(base, decay, amplitude, drop, drop_ms):
        """A ring-mod 2f/3f body: carrier 2.5*base x ring 0.5*base -> sidebands on 2f+3f,
        both oscillators falling together so the pair stays ratio-locked."""
        fall = _fall(drop, drop_ms)
        n = synthio.Note(frequency=base * 2.5, waveform=snd.SINE,
                         envelope=_env(0.0, decay, decay * 0.36),
                         amplitude=amplitude, bend=fall, filter=_lp(2100, 0.72))
        try:
            n.ring_frequency = base * 0.5
            n.ring_waveform = snd.SINE
            n.ring_bend = fall
        except Exception:
            pass                       # older firmware: a plain falling sine body
        return n

    def _smear(decay, amplitude, hi, lo, ms, scale=0.45):
        """De-buzz NOISE body: a free-running bend keeps shifting the table repeat rate (the ear
        never locks to a pitch) under a falling LP sweep. NO ring modulation, so it stays natural
        on a full-range speaker - the ring-mod _body is inaudible on the piezo but metallic on
        headphones. Same technique as the explosion. Inaudible-body corner on the piezo = free."""
        return synthio.Note(frequency=659.0, waveform=snd.NOISE,
                            envelope=_env(0.0, decay, decay * 0.5), amplitude=amplitude,
                            bend=synthio.LFO(rate=3.1, scale=scale), filter=_sweep_lp(hi, lo, ms))

    # ---- the arcade theme (default palette) ----
    def _fat_table():
        """Square lead + saw an octave below, baked into ONE 256-sample cycle."""
        acc = [0] * 256
        for i in range(256):
            acc[i] = int(0.42 * 28000 * (2.0 * i / 256 - 1.0))
            acc[i] += int(0.58 * (28000 if (i % 128) < 64 else -28000))
        peak = max(max(acc), -min(acc))
        return array.array("h", [v * 28000 // peak for v in acc])

    def _build_voices(synth):
        """Build this theme's voice dict. Each slot = [(delay_frames, voice), ...]; a
        single-shot is [(0, note)], a layered voice is [(0, (noteA, noteB))], a sequence
        lists more events."""
        fat = _fat_table()

        def _fat_note(midi, decay, amplitude, cutoff, bend=None):
            return synthio.Note(frequency=synthio.midi_to_hz(midi) * 0.5, waveform=fat,
                                envelope=_env(0.001, decay, decay * 0.65),
                                amplitude=amplitude, bend=bend, filter=_lp(cutoff))

        # hit (headphone rework): a bright noise crack + a tiny smear-noise flick - the SAME noise
        # family as boom/explosion (signature cohesion), NO ring-mod body (that was metallic on
        # headphones). On the piezo the crack carries it. Anti-fatigue: the crack's cutoff rotates
        # over 3 steps per fire (audible brightness jitter, replacing the old +-2 st pitch rotation).
        hit_crack = _crack(0.036, 2300, 0.66, q=1.05)
        return {
            "blip": [(0, _fat_note(84, 0.05, 0.55, 3000))],
            "coin": [(0, _fat_note(79, 0.10, 0.80, 3400)),          # G5 -> C6, 2 frames
                     (2, _fat_note(84, 0.16, 0.86, 3400))],
            "powerup": [(i * 3, _fat_note(m, 0.12, 0.74, 3000))     # C-E-G-C arpeggio
                        for i, m in enumerate((72, 76, 79, 84))],
            "zap": [(0, _fat_note(72, 0.16, 0.52, 3100, bend=_fall(26, 140)))],  # long, bright, big fall
            # enemy fire: on a piezo, LOUD = bright energy in the 2-6 kHz resonance, so
            # "dark + low" (what a full-range speaker uses for enemy fire) is exactly the
            # inaudible corner. Flip it: pew is HIGH + BRIGHT + THIN + SHORT with a quick
            # drop - a thin "tik" clearly above the player's fat descending zap. Audible;
            # reads as "not your shot" by register + thinness, never by being darker.
            "pew": [(0, _fat_note(88, 0.05, 0.55, 3600, bend=_fall(7, 45)))],
            # jump: one FAT note whose bend climbs a 3-STEP staircase over an octave - the steps
            # are audible on the piezo (a smooth rise is not, and reads generic), yet it's one
            # continuous whoop, NOT the coin's discrete arpeggio. Hardware listening winner
            # ("jG", 2026-07-12). Same voice cost as zap (1 note + 1 bend LFO).
            "jump": [(0, _fat_note(62, 0.13, 0.60, 3300,
                                   bend=_curve([0.0, 0.30, 0.34, 0.63, 0.67, 1.0], 12, 120)))],
            "hit": [(0, (hit_crack, _smear(0.05, 0.5, 4000, 1500, 60, scale=0.3)))],   # crack + flick
            # hurt = "the hit was ON YOU": a crack + a FAT tone that GLIDES DOWN ~10 st. The
            # falling contour (negative = damage) makes it structurally unlike hit's short snap -
            # on the piezo a mere pitch-transpose of hit was too close to tell apart. Same 2-voice
            # budget as hit (and cheaper: a plain falling note, no ring-mod body).
            "hurt": [(0, (_crack(0.04, 1800, 0.55, q=1.05),
                          _fat_note(57, 0.17, 0.60, 2400, bend=_curve([0.0, -1.0], 10, 170))))],
            "boom": [(0, (_crack(0.06, 1750, 0.62, q=1.05),                  # crack + low smear-noise
                          _smear(0.28, 0.85, 3200, 120, 260, scale=0.40)))],
            "explosion": [(0, synthio.Note(                                 # 5h: aperiodic bend-smear
                frequency=659.0, waveform=snd.NOISE,
                envelope=_env(0.0, 0.70, 0.35), amplitude=0.85,
                bend=synthio.LFO(rate=3.1, scale=0.45),
                filter=_sweep_lp(5500, 250, 580)))],
            # rotation hook: the crack note whose FILTER CUTOFF rotates over 3 steps (brightness
            # jitter, anti-fatigue on rapid fire). A theme without this key gets no hit rotation.
            "_hit_rot": (hit_crack, (2000.0, 2300.0, 2650.0)),
        }

    class Kit:
        """This theme's SFX set. Build ONCE; fire with the named methods; tick() per frame."""

        def __init__(self, synth):
            self._s = synth
            self.available = bool(getattr(synth, "available", False))
            self._rot = 0
            self._rot_note = None
            if not self.available:
                self._v = None
                return
            self._v = _build_voices(synth)
            rot = self._v.get("_hit_rot")
            if rot:
                self._rot_note, self._rot_cuts = rot

        def _play(self, name):
            """Fire slot `name`; returns True if the channel accepted it (False if dropped
            inside a higher sound's protected window)."""
            return (self._s.sfx_seq(self._v[name], _PRIO[name], _WIN.get(name, 0))
                    if self.available else False)

        def blip(self):
            """UI: "input accepted" (menu nav, select, confirm)."""
            self._play("blip")

        def coin(self):
            """Event: "you gained value" (pickup, coin, checkpoint)."""
            self._play("coin")

        def powerup(self):
            """Scene: "your state improved" (level/wave clear, upgrade). Protected 180 ms."""
            self._play("powerup")

        def zap(self):
            """Feedback: "YOUR action fired" (shoot, dash). Descending glide."""
            self._play("zap")

        def pew(self):
            """Feedback: an ENEMY fired (lower, darker than zap - not your action)."""
            self._play("pew")

        def jump(self):
            """Feedback: a jump/launch. RISING pitch (positive), unlike zap's fall."""
            self._play("jump")

        def hit(self, rotate=True):
            """Feedback: "a hit landed on an enemy/object". Short bright noise snap; the crack's
            cutoff rotates over 3 steps per fire (anti-fatigue) unless rotate=False."""
            if not self.available:
                return
            if rotate and self._rot_note is not None:
                nxt = (self._rot + 1) % 3        # rotate the crack cutoff, fire, and ADVANCE the
                try:                             # rotation ONLY if the channel accepted it - a hit
                    self._rot_note.filter.frequency = self._rot_cuts[nxt]   # dropped in a window
                except Exception:                # must not burn a rotation step.
                    pass
                if self._play("hit"):
                    self._rot = nxt
            else:
                self._play("hit")

        def hurt(self):
            """Feedback+: "the hit was ON YOU" - the player-took-damage decision cue.
            Darker and a fifth below hit; may interrupt a plain hit, never the reverse."""
            self._play("hurt")

        def boom(self):
            """Event: "something was destroyed/ended" (kill, break, line clear)."""
            self._play("boom")

        def explosion(self):
            """Scene: the big one (player/boss death, bomb). Protected 600 ms - lower
            classes are dropped while it plays out."""
            self._play("explosion")

        def tick(self):
            """Drive the channel's sequencer + protected window - call once per frame.
            (Delegates to the Synth; a game already ticking the synth can skip this.)"""
            if self.available:
                self._s.tick()

else:                                  # audio-less firmware / plain desktop: silent no-ops

    class Kit:
        """No-op Kit: same surface, no audio."""

        def __init__(self, synth):
            self.available = False

        def blip(self):
            pass

        def coin(self):
            pass

        def powerup(self):
            pass

        def zap(self):
            pass

        def pew(self):
            pass

        def jump(self):
            pass

        def hit(self, rotate=True):
            pass

        def hurt(self):
            pass

        def boom(self):
            pass

        def explosion(self):
            pass

        def tick(self):
            pass
