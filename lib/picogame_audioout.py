# picogame_audioout: create the platform's audio OUTPUT device, so picogame_audio and
# picogame_synth share ONE detection path and games need no board-specific code.
#
# Returns an AudioOut-like object with the usual `.play(sample_or_mixer)` / `.deinit()` API
# (audiopwmio.PWMAudioOut and audiobusio.I2SOut both have it), so the Mixer/Synthesizer code
# above it is identical on every board. Selection order:
#   1. explicit `pin`               -> PWM on that pin (caller override)
#   2. board.I2S_BCLK + a TLV320 DAC -> I2S (Fruit Jam: audiobusio.I2SOut + adafruit_tlv320)
#   3. board.AUDIO/SPEAKER/BUZZER    -> PWM (PicoPad/PicoSystem/...)
#   4. nothing                       -> raise (caller decides: Audio raises, Synth goes silent)
#
# Fruit Jam I2S needs the TLV320DAC3100 configured over I2C first, so the `adafruit_tlv320` +
# `adafruit_bus_device` drivers must be present in CIRCUITPY/lib (install from the Adafruit library
# bundle / circup - NOT bundled with picogame). If they're absent this path silently falls back, so
# games still run (just no sound on the Fruit Jam). Output target (headphone/speaker/both) is
# `PICOGAME_AUDIO_OUT` in settings.toml (default headphone). No external MCLK (BCLK-derived PLL).
import os
import board
import picogame_debug as _dbg

_KEEP = []   # holds DAC objects alive for the process: a native I2SOut can't carry the reference


def _db(name, default):
    """A dB volume from settings.toml (int like `PICOGAME_HP_VOLUME = -10`, or a str), else `default`.
    Clamped to a SAFE window and non-finite rejected, so a garbage setting ('nan'/'inf'/'999') can't
    drive the DAC to a hearing-damaging endpoint - it falls back to `default` or the window edge."""
    v = os.getenv(name)
    if v is None:
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f or f == float("inf") or f == float("-inf"):   # NaN / +-inf -> default
        return default
    return max(-80.0, min(0.0, f))   # dB: 0 = loudest sane (line level); below = quieter


def make_output(sample_rate=22050, pin=None):
    """Return this board's audio output device (raises RuntimeError if none is available)."""
    if pin is None and hasattr(board, "I2S_BCLK"):
        out = _try_i2s(sample_rate)
        if out is not None:
            return out
    return _make_pwm(pin)


def _try_i2s(sample_rate):
    """Fruit Jam-class I2S DAC path. Returns the I2SOut, or None to fall back (driver absent,
    DAC not detected / mis-wired) so a board with I2S pins but no DAC still finds PWM."""
    try:
        import audiobusio
        import adafruit_tlv320
    except ImportError as e:
        # This board HAS I2S pins but the DAC driver isn't installed -> the #1 Fruit Jam "no sound"
        # cause. Diagnose it (falls back to PWM, which a DVI board lacks -> silent). Install
        # adafruit_tlv320 + adafruit_bus_device (circup / the Adafruit bundle).
        _dbg.note("audioout: I2S DAC driver missing (install adafruit_tlv320) ->", repr(e))
        return None
    try:
        import time
        dac = adafruit_tlv320.TLV320DAC3100(board.I2C())
        sel = os.getenv("PICOGAME_AUDIO_OUT", "headphone")
        if sel in ("headphone", "both"):
            dac.headphone_output = True
        if sel in ("speaker", "both"):
            dac.speaker_output = True
        # The driver's *_output defaults are deliberately VERY quiet (headphone_volume default -30.1 dB)
        # for hearing/speaker safety - raise to an audible level. All three are dB and tunable in
        # settings.toml (integers): PICOGAME_DAC_VOLUME = main fader (keep <=0 to avoid DSP clipping);
        # PICOGAME_HP_VOLUME / PICOGAME_SPK_VOLUME = analog trim, 0 = loud/line-level ... -78 = silent
        # (raise toward 0 = louder). In its OWN try: the analog trims clip internally and dac_volume is
        # clamped, but a bad value must never kill the I2S path (worst case = quiet, not no audio).
        try:
            dac.dac_volume = _db("PICOGAME_DAC_VOLUME", -3)
            if sel in ("headphone", "both"):
                dac.headphone_volume = _db("PICOGAME_HP_VOLUME", -10)
            if sel in ("speaker", "both"):
                dac.speaker_volume = _db("PICOGAME_SPK_VOLUME", -10)
        except Exception as e:
            _dbg.note("audioout: DAC volume set failed ->", repr(e))
        dac.configure_clocks(sample_rate=sample_rate)   # mclk_freq=None -> PLL from BCLK, no MCLK pin
        time.sleep(0.35)                                 # let the DAC output ramp before playback
        out = audiobusio.I2SOut(board.I2S_BCLK, board.I2S_WS, board.I2S_DIN)
        _KEEP.append(dac)        # keep the DAC + its I2C device alive (I2SOut can't hold the ref)
        return out
    except Exception as e:
        _dbg.note("audioout: I2S DAC init failed ->", repr(e))
        return None


def _make_pwm(pin):
    import audiopwmio
    p = _resolve_pwm_pin(pin)
    if p is None:
        raise RuntimeError("no audio output: no I2S DAC and no PWM pin "
                           "(set PICOGAME_AUDIO in settings.toml, or pass a pin)")
    return audiopwmio.PWMAudioOut(p)


def _resolve_pwm_pin(pin=None):
    """PWM speaker pin: explicit -> settings.toml PICOGAME_AUDIO -> common board names."""
    if pin is not None:
        return pin
    name = os.getenv("PICOGAME_AUDIO")
    if name:
        p = getattr(board, name, None)
        if p is None:
            try:
                import microcontroller
                p = getattr(microcontroller.pin, name, None)
            except ImportError:
                pass
        if p is not None:
            return p
    return (getattr(board, "AUDIO", None) or getattr(board, "SPEAKER", None)
            or getattr(board, "BUZZER", None))
