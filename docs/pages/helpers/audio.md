---
title: "Audio & music"
description: "Play WAV samples, synthesize SFX and MIDI with synthio, or use the ready-made picogame_sfx kit."
---

:::caution[Where audio plays: playground, simulator, device]
- **Device** — everything (real synthio + PWM/I2S).
- **Browser playground** — `tone()` beeps and the `picogame_sfx` kit play via WebAudio (press a key first to unlock sound); custom `picogame_synth` voices don't (no synthio backend in the browser).
- **Desktop simulator, live window** (`--backend pygame`, the default) — `picogame_synth` SFX and music **do** play through `pygame.mixer`: an approximation for tuning by ear, not bit-exact. Headless runs (`--shot` / CI) and `picogame_audio` sample playback stay silent.
- Audition synth SFX offline with `tools/synth_preview.py`, and confirm the real mix on hardware.
:::

picogame offers four audio layers. `picogame_audioout` picks the board's output device (PWM or I2S DAC).
`picogame_audio` mixes `.wav` files and generated PCM tones. `picogame_synth` creates notes in real time
with synthio and avoids a PCM buffer for every effect. `picogame_sfx` adds a ready-made set of named game
sounds over the synthesizer. See [/hardware/](/hardware/) for board audio setup and
[/reference/](/reference/) for signatures.

## picogame_audioout — one output for every board

`picogame_audio` and `picogame_synth` both get their output device from `picogame_audioout.make_output()`,
so a game needs **no board-specific audio code**. It auto-selects:

- an **I2S DAC** (e.g. the Fruit Jam's TLV320) when the board exposes `board.I2S_BCLK`,
- otherwise a **PWM** output on the board's speaker pin (or a pin you pass).

You normally never call it directly — construct `Audio()` / `Synth()` and it happens for you. `make_output(sample_rate=22050, pin=None)` is there if you want the raw device; passing an explicit `pin` **forces PWM**.

**Volume (I2S DAC boards):** the TLV320 driver's defaults are deliberately very quiet, so on a Fruit Jam sound can seem absent until you raise them in `settings.toml` — `PICOGAME_AUDIO_OUT` (`headphone`/`speaker`/`both`), `PICOGAME_DAC_VOLUME`, `PICOGAME_HP_VOLUME`, `PICOGAME_SPK_VOLUME` (integer dB, keep `<= 0`). See the [settings.toml reference](/custom-board/).

:::caution[Fruit Jam: install the DAC driver or it's silent]
I2S audio needs `adafruit_tlv320` **and** `adafruit_bus_device` in `CIRCUITPY/lib` (from the Adafruit
bundle / `circup`) — they are **not** bundled with picogame. If they're missing, audio silently falls
back to a PWM pin the DVI board doesn't have, so there's no sound. Set `PICOGAME_DEBUG = 1` to print the
reason (`[picogame] audioout: I2S DAC driver missing …`) to the serial console.
:::

## picogame_audio

A convenience layer over CircuitPython's audio stack (`audiocore` + `audiomixer`) on top of the
`picogame_audioout` output. Reach for it when you have `.wav` assets to play, or want simple beeps without bundling files. It sets up a mixer with several voices so a shot, an explosion, and looping music can all sound at once. The defaults (22050 Hz, mono, 16-bit signed) match typical ugame `.wav` assets - any sample you play must match that format.

### `Audio(pin=None, voices=4, sample_rate=22050, channels=1, bits=16, signed=True)`

Constructs the audio output and starts the mixer playing immediately. `pin=None` lets `picogame_audioout` pick the device (I2S DAC or the board's PWM speaker pin); an explicit `pin` forces PWM on that pin. `voices` is the number of simultaneous channels; voice 0 is reserved for music and voices 1..N-1 are used round-robin for sound effects. The other args define the sample format every clip must match.

- `load(path)` - opens a `.wav` file as a reusable `WaveFile` sample. Build it once and keep the returned object alive (it holds the open file); replaying it is cheap.
- `play(sample, *, voice=None, loop=False, volume=1.0)` - plays a sample. `voice` is keyword-only; `None` picks the next round-robin sfx voice. `volume` sets that voice's level (0.0-1.0). Returns the voice index it used.
- `sfx(sample, volume=1.0)` - fire-and-forget effect on a free sfx voice (calls `play` with `loop=False`). Returns the voice index.
- `music(sample, loop=True, volume=1.0)` - plays on the reserved music voice (voice 0), looping by default.
- `stop(voice=None)` - stops one voice, or every voice if `voice` is `None`.
- `stop_music()` - stops just the music voice.
- `is_playing` (property) - `True` if any voice is currently playing.
- `deinit()` - releases the audio output. The output device is a singleton, so call this before constructing a second `Audio()` (or a `Synth()` sharing the pin) - otherwise the next one raises *pin in use*.

### `tone(frequency=440, ms=120, sample_rate=22050, volume=0.6)`

Builds a short square-wave `RawSample` in RAM - a beep with no `.wav` file needed. Good for prototyping and simple blips. Pass it straight to `sfx`/`play`.

```python
import picogame_audio
import picogame_input

audio = picogame_audio.Audio()        # PWM audio, 4 voices
pew = picogame_audio.tone(880, 90)    # high blip, built once
boom = picogame_audio.tone(140, 200)  # low thud

btns = picogame_input.Buttons()
while True:
    btns.poll()
    if btns.just_pressed(btns.A):
        audio.sfx(pew)                # overlaps on a free voice
    if btns.just_pressed(btns.B):
        audio.sfx(boom, volume=0.8)
```

:::note[Gotchas]
- Every sample must match the mixer's format. A 44100 Hz or stereo `.wav` will play wrong (or error); resample assets to 22050 Hz mono 16-bit first.
- Keep `load()` results alive - if the `WaveFile` is garbage-collected the open file goes with it. Load clips once at startup, not per frame.
- `tone()` builds a `RawSample` in RAM (about `sample_rate * ms / 1000 * 2` bytes each). Many long tones can exhaust the heap. Keep them short and few, lower both the mixer and tone `sample_rate` (for example to `8000`), or use `picogame_synth` to avoid a separate PCM buffer for every effect.
- You only have `voices-1` sfx channels; rapid-fire effects round-robin and will cut each other off once they wrap.
:::

## picogame_synth

`picogame_synth` wraps synthio oscillators, ADSR envelopes, pitch-bend LFOs, and low-pass filters.
It avoids storing a PCM buffer for every effect, but still allocates the audio output buffer, mixer,
waveforms, and note objects. Use it for a larger SFX set or MIDI music when WAV assets would consume
too much RAM or flash.

The module is safe to import on firmware without audio. If audio initialisation fails, its API becomes
a silent no-op; check `AVAILABLE` or `synth.available` only when the UI needs to expose audio settings.
The desktop simulator's live pygame window plays these `picogame_synth` voices through `pygame.mixer` (an approximation for tuning by ear); headless runs stay silent. Either way the same game path runs unchanged.

Built-in waveform constants (one-cycle, signed 16-bit arrays you share across notes): `SINE`, `SAW`, `TRIANGLE`, `SQUARE`, `NOISE`. The functions `sine()`, `saw()`, `triangle()`, `square()`, `noise()` build fresh copies if you need them. For a crisp arcade blip reach for a short `SQUARE` note (`SINE` and `TRIANGLE` read softer and rounder).

### `note(midi, waveform=None, attack=0.005, decay=0.06, sustain=0.0, release=0.08, amplitude=0.6, bend=None, cutoff=None)`

Builds a reusable note/SFX/instrument - the core building block. `midi` is a MIDI note number (60 = middle C, 72 = C5). `waveform` is one of the constants above. `attack`/`decay`/`sustain`/`release` shape the ADSR envelope in seconds (a short decay with `sustain=0.0` gives a percussive blip). `amplitude` is loudness (0.0-1.0). `bend` takes a `pitch_bend` LFO for a pitch sweep (a quick wobble; see `pitch_bend`); `cutoff` adds a low-pass filter at that many Hz to round off harsh tones. Build each note once and replay it.

### `pitch_bend(semitones, ms, waveform=None, once=True)`

Returns a `synthio.LFO` for a note's `bend`. With `once=True` it is a **one-shot sine sweep**: over `ms` the pitch swings toward `semitones` and back - a *wobble/swoop*, not a clean monotonic glide. Keep `ms` short (about the note's `attack+decay`) so mostly the rise (positive = zap up) or fall (negative = drop) is heard; a long `ms` lets the return swing show and sounds wobbly.

### `Synth(pin=None, sample_rate=22050, buffer_size=2048, music_level=0.4, sfx_level=0.7)`

Sets up the output (via `picogame_audioout` — I2S DAC or PWM, same as `Audio`) and a 2-voice mixer: voice 0 for music (a `MidiTrack`), voice 1 for the live synth used by SFX. `pin=None` auto-selects the device; an explicit `pin` forces PWM. `music_level`/`sfx_level` are the starting mix levels for those two voices.

- `sfx(n)` - plays note `n` as a one-shot effect. It retriggers the note's LFOs first (so a repeated zap sounds identical every time), then calls `release_all_then_press`, so back-to-back SFX cut cleanly.
- `press(n)` / `release(n)` - hold and release a note manually, for sounds that last as long as a button is held rather than firing once.
- `music(midi_track)` - plays a `MidiTrack` (from `load_midi`) on voice 0, looping.
- `stop_music()` - stops the music voice.

### `Drone(synth, waveform=None, amplitude=0.35, attack=0.03, release=0.12)`

A continuously **held** note for engine, siren, or drone-style sounds - press it once, then steer its pitch/volume live each frame. Where `note()`/`sfx` fire a one-shot, a `Drone` keeps a single note sounding on the SFX voice; synthio reads the note's live `.frequency`/`.amplitude` per audio buffer, so the tone tracks whatever you feed it (e.g. an engine note driven by car speed). `synth` is a live `Synth`; `waveform` defaults to `SAW`.

- `.start()` - press the held note (idempotent - safe to call again while playing).
- `.set(frequency, amplitude=None)` - update the live pitch (Hz) every frame, and optionally the volume.
- `.stop()` - release the note (e.g. on the title or results screen).

```python
eng = snd.Drone(s, waveform=snd.SAW)
eng.start()                                    # at race start
# each frame, rev = speed / max_speed in 0..1:
eng.set(70 + 270 * rev, amplitude=0.2 + 0.5 * rev)
eng.stop()                                     # on the title / results screen
```

### `load_midi(path, sample_rate=22050, waveform=None, envelope=None, tempo=120, ppqn=240)`

Loads a `.mid` file as a `synthio.MidiTrack` for `Synth.music`. `waveform` and `envelope` select
the instrument voice for the track; `tempo` (BPM) and `ppqn` set playback speed. The loader accepts
a standard format-0 SMF header.

```python
import picogame_synth as snd
import picogame_input

s = snd.Synth()
# Each SFX is a Note built ONCE (envelope + optional bend + filter).
blip = snd.note(72, snd.SQUARE, decay=0.10)
zap = snd.note(60, snd.SAW, decay=0.18, cutoff=4000, bend=snd.pitch_bend(12, 180))
boom = snd.note(45, snd.NOISE, attack=0.0, decay=0.30, amplitude=0.55, cutoff=2800)

btn = picogame_input.Buttons()
while True:
    btn.poll()
    if btn.just_pressed(btn.A):
        s.sfx(zap)
```

:::note[Gotchas]
- No import guard needed: the module runs as silent no-ops on audio-less firmware, and a `Synth()` that fails mid-init (tight heap, claimed pin) degrades the same way instead of raising.
- Build each `note()` once at startup and replay it; `sfx` handles retriggering. Rebuilding notes per frame wastes time and breaks LFO retrigger.
- The simulator's live window approximates these voices through `pygame.mixer`; for an exact preview render SFX to WAV with `tools/synth_preview.py`, then
  confirm the final balance on the target speaker. Pitch contours can carry meaning: rising for a gain,
  falling for a loss, and alternating tones for a warning.
- It is the synthesizer that makes sound, not the note object - effects only play through a live `Synth`, and there are just two mixer voices (one music, one SFX), so overlapping synth SFX share a single voice.
:::

## picogame_sfx

`picogame_sfx` provides one cohesive set of named effects over `picogame_synth`. Use it when the
built-in arcade-style sounds fit the game. Build custom `picogame_synth.note()` objects when the kit
does not cover an event or the game needs a different audio identity. With no audio, every call is a
silent no-op.

### `Kit(synth)`

Build the theme's voices **once** from a live `picogame_synth.Synth()`, then fire effects by name (and call `tick()` once per frame). Each call maps to a game *event*; the kit arbitrates them by priority through the single SFX voice, so a big scene sound briefly holds off the small feedback blips instead of being cut by them.

| Call | Fires on | Preview |
|---|---|---|
| `blip()` | UI tick — menu move, select, confirm | <audio controls preload="none" src="/audio/sfx_blip.mp3"></audio> |
| `coin()` | a pickup / gained value | <audio controls preload="none" src="/audio/sfx_coin.mp3"></audio> |
| `powerup()` | level / wave clear, upgrade | <audio controls preload="none" src="/audio/sfx_powerup.mp3"></audio> |
| `zap()` | **your** shot or dash | <audio controls preload="none" src="/audio/sfx_zap.mp3"></audio> |
| `pew()` | an **enemy** fired | <audio controls preload="none" src="/audio/sfx_pew.mp3"></audio> |
| `jump()` | a jump / launch | <audio controls preload="none" src="/audio/sfx_jump.mp3"></audio> |
| `hit()` | a hit landed on an enemy | <audio controls preload="none" src="/audio/sfx_hit.mp3"></audio> |
| `hurt()` | **you** took damage | <audio controls preload="none" src="/audio/sfx_hurt.mp3"></audio> |
| `boom()` | something destroyed / ended | <audio controls preload="none" src="/audio/sfx_boom.mp3"></audio> |
| `explosion()` | a big scene blast | <audio controls preload="none" src="/audio/sfx_explosion.mp3"></audio> |

`hit()` varies its brightness across a rapid burst so repeats don't grate; pass `rotate=False` for identical hits. Call `tick()` **once per frame** — it plays out the coin/powerup arpeggios and counts down the protected windows.

Volume/mute live on the `Synth`: `synth.set_levels(music=None, sfx=None)` sets either mixer level (0.0-1.0), and `synth.mute(on)` silences everything while remembering the levels. Wire these to a `picogame_options` menu + `picogame_save` for a persisted volume control.

```python
import picogame_synth as snd
import picogame_sfx as sfx
import picogame_input

s = snd.Synth()
kit = sfx.Kit(s)                       # builds the signature voices once (silent no-op if no audio)

btn = picogame_input.Buttons()
while True:
    btn.poll()
    if btn.just_pressed(btn.A):
        kit.zap()                      # your shot
    if btn.just_pressed(btn.B):
        kit.jump()
    # ... on a kill: kit.boom();  on taking damage: kit.hurt();  on a pickup: kit.coin()
    kit.tick()                         # once per frame - drives sequences + priority windows
```

:::note[Gotchas]
- Build the `Kit` **once** at startup and reuse it; it pre-builds every voice. Rebuilding per frame wastes time and heap.
- Call `kit.tick()` **every frame**, next to `clock.tick()`. Miss it and the arpeggio effects (coin, powerup) and the protected windows stop working.
- It shares `picogame_synth`'s single SFX voice, so effects are monophonic - the priority arbitration decides which one wins when two fire close together (that's the point of the windows).
- The simulator's live window plays the kit (approximate); for an exact audition render it to WAV before flashing (see `picogame_synth`'s note above), then lock the feel on hardware.
:::
