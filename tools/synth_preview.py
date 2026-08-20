#!/usr/bin/env python3
# Desktop preview of picogame_synth SFX: render synthio-style notes to WAV so the sound
# set can be AUDITIONED on a PC (the simulator is silent - synthio is device-only). The
# model mirrors lib/picogame_synth.py: 256-sample single-cycle oscillators (sine/saw/
# triangle/square/noise), an ADSR envelope (press-and-hold; with sustain=0 a note is a
# blip of length attack+decay), a per-note amplitude, and a pitch-bend LFO (one sine
# sweep, then hold). This is an APPROXIMATION for tuning by ear, not a bit-exact device
# render - lock the numbers here, then port them into the game's SND_* notes.
#
#   python3 tools/synth_preview.py                 # render the squest set -> tools/out/*.wav + _all.wav
#   python3 tools/synth_preview.py --play          # also play the montage (needs `aplay`/`afplay`)

import argparse
import math
import os
import subprocess
import wave

import numpy as np

SR = 22050
_LEN = 256
_AMP = 28000


def _square():
    return np.array([1.0 if i < _LEN // 2 else -1.0 for i in range(_LEN)])


def _saw():
    return np.array([2.0 * i / _LEN - 1.0 for i in range(_LEN)])


def _triangle():
    return np.array([2.0 * abs(2.0 * i / _LEN - 1.0) - 1.0 for i in range(_LEN)])


def _sine():
    return np.sin(2 * np.pi * np.arange(_LEN) / _LEN)


def _noise():
    out = np.empty(_LEN)
    s = 0x1234
    for i in range(_LEN):
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        out[i] = ((s >> 8) % (2 * _AMP) - _AMP) / _AMP
    return out


WAVES = {"square": _square(), "saw": _saw(), "triangle": _triangle(),
         "sine": _sine(), "noise": _noise()}
_sn = _sine() + 0.5 * _noise()
WAVES["sine_noise"] = _sn / np.abs(_sn).max()      # snare body (picogame_synth.mix(SINE,(NOISE,.5)))


def _pulse(duty):
    hi = max(1, min(_LEN - 1, int(_LEN * duty)))
    return np.array([1.0 if i < hi else -1.0 for i in range(_LEN)])


WAVES["pulse25"] = _pulse(0.25)                    # picogame_synth.square(duty=) NES timbres
WAVES["pulse12"] = _pulse(0.125)


def midi_to_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def render(midi, wave="square", attack=0.005, decay=0.06, sustain=0.0,
           amplitude=0.6, bend=None, tail=0.03):
    """Render one note to a float32 mono signal at SR. `bend` = (semitones, ms)."""
    base = midi_to_hz(midi)
    dur = attack + decay + tail
    n = max(1, int(SR * dur))
    t = np.arange(n) / SR
    if bend:
        semi, ms = bend
        period = ms / 1000.0
        ph = np.clip(t / period, 0.0, 1.0)        # one sine cycle, then hold at the end value
        freq = base * 2 ** ((semi / 12.0) * np.sin(2 * np.pi * ph))
    else:
        freq = np.full(n, base)
    phase = (np.cumsum(freq) / SR) % 1.0          # phase-accumulate into the cycle table
    tbl = WAVES[wave]
    osc = tbl[(phase * _LEN).astype(int) % _LEN]
    env = np.zeros(n)                             # ADSR, press & hold (sustain held; no release)
    a = max(1, int(SR * attack))
    d = int(SR * decay)
    env[:a] = np.linspace(0.0, 1.0, a)
    de = min(a + d, n)
    if de > a:
        env[a:de] = np.linspace(1.0, sustain, de - a)
    env[de:] = sustain
    return osc * env * amplitude


def to_int16(sig):
    return np.clip(sig * 32767, -32768, 32767).astype(np.int16)


def write_wav(path, sig):
    w = wave.open(path, "w")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(to_int16(sig).tobytes())
    w.close()


def _biquad(sig, cutoff, high_pass=False, q=0.7071):
    """RBJ biquad LP/HP, mirrors the synthio.Biquad a drum() note carries."""
    w0 = 2 * math.pi * cutoff / SR
    cw, sw = math.cos(w0), math.sin(w0)
    alpha = sw / (2 * q)
    if high_pass:
        b0, b1, b2 = (1 + cw) / 2, -(1 + cw), (1 + cw) / 2
    else:
        b0, b1, b2 = (1 - cw) / 2, 1 - cw, (1 - cw) / 2
    a0, a1, a2 = 1 + alpha, -2 * cw, 1 - alpha
    b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
    out = np.zeros(len(sig))
    x1 = x2 = y1 = y2 = 0.0
    for i, x in enumerate(sig):
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        out[i] = y
        x2, x1, y2, y1 = x1, x, y1, y
    return out


def render_drum(frequencies, times, waves, cutoff=None, high_pass=False,
                drop=6.0, drop_ms=50.0, amplitude=0.8, tail=0.08):
    """Mirror of picogame_synth.drum(): 2-3 fixed-frequency notes with per-note decays,
    one shared LINEAR pitch drop (`drop` semitones over drop_ms), then one biquad."""
    dur = max(times) + tail
    n = max(1, int(SR * dur))
    t = np.arange(n) / SR
    bend_oct = (drop / 12.0) * np.clip(1.0 - t / (drop_ms / 1000.0), 0.0, 1.0)
    if not isinstance(waves, (list, tuple)):
        waves = [waves]
    if not isinstance(amplitude, (list, tuple)):
        amplitude = [amplitude]
    sig = np.zeros(n)
    for i, f in enumerate(frequencies):
        freq = f * 2 ** bend_oct
        phase = (np.cumsum(freq) / SR) % 1.0
        tbl = WAVES[waves[i % len(waves)]]
        osc = tbl[(phase * _LEN).astype(int) % _LEN]
        env = np.maximum(0.0, 1.0 - t / times[i % len(times)])   # attack 0, linear-ish decay
        sig += osc * env * amplitude[i % len(amplitude)]
    sig /= len(frequencies)
    if cutoff:
        sig = _biquad(sig, cutoff, high_pass)
    return sig


def render_spec(spec):
    """A spec is one note dict, {'drum': {...}} for a drum, or {'seq': [...], 'gap': s}."""
    if "drum" in spec:
        return render_drum(**spec["drum"])
    if "seq" in spec:
        gap = np.zeros(int(SR * spec.get("gap", 0.05)))
        parts = []
        for nd in spec["seq"]:
            parts.append(render(**nd))
            parts.append(gap)
        return np.concatenate(parts)
    return render(**spec)


# --- squest synthio SFX set: short, dry square beeps; bend only on the two zaps + death;
# kills/pickup/surface are quick arpeggios (sound-designer palette, mirrors SND_* in the game) ---
SQUEST = {
    "fire":    {"midi": 88, "wave": "square", "attack": 0.003, "decay": 0.03, "amplitude": 0.55, "bend": (-5, 25)},
    "efire":   {"midi": 55, "wave": "square", "attack": 0.003, "decay": 0.05, "amplitude": 0.5, "bend": (-4, 35)},
    "hit":     {"seq": [{"midi": 76, "wave": "square", "attack": 0.003, "decay": 0.035, "amplitude": 0.6},
                        {"midi": 83, "wave": "square", "attack": 0.003, "decay": 0.035, "amplitude": 0.6}], "gap": 0.03},
    "subhit":  {"seq": [{"midi": m, "wave": "square", "attack": 0.003, "decay": 0.045, "amplitude": 0.7}
                        for m in (64, 71, 78)], "gap": 0.03},
    "pick":    {"seq": [{"midi": 84, "wave": "square", "attack": 0.003, "decay": 0.03, "amplitude": 0.55},
                        {"midi": 91, "wave": "square", "attack": 0.003, "decay": 0.03, "amplitude": 0.55}], "gap": 0.025},
    "surface": {"seq": [{"midi": m, "wave": "square", "attack": 0.004, "decay": 0.05, "amplitude": 0.6}
                        for m in (72, 76, 79, 84)], "gap": 0.035},
    "oxlow":   {"seq": [{"midi": 60, "wave": "square", "attack": 0.003, "decay": 0.05, "amplitude": 0.5},
                        {"midi": 53, "wave": "square", "attack": 0.003, "decay": 0.05, "amplitude": 0.5}] * 3, "gap": 0.16},
    "refill":  {"seq": [{"midi": 50 + k * 3, "wave": "square", "attack": 0.003, "decay": 0.025, "amplitude": 0.45}
                        for k in range(7)], "gap": 0.02},
    "die":     {"seq": [{"midi": 64, "wave": "square", "attack": 0.003, "decay": 0.05, "amplitude": 0.6},
                        {"midi": 56, "wave": "square", "attack": 0.003, "decay": 0.05, "amplitude": 0.6},
                        {"midi": 48, "wave": "square", "attack": 0.003, "decay": 0.05, "amplitude": 0.6},
                        {"midi": 40, "wave": "square", "attack": 0.004, "decay": 0.20, "amplitude": 0.6,
                         "bend": (-4, 250)}], "gap": 0.04},               # descending square sink (B)
}


# --- Pictor: the events the PicoLibSDK original plays as ADPCM samples (throw/gun, enemyhit,
# glass, fail, bigbonus), synthesised instead. Numbers mirror the SND_* notes in the game. ---
PICTOR = {
    "throw":   {"midi": 84, "wave": "square", "attack": 0.005, "decay": 0.035, "amplitude": 0.30, "bend": (-9, 45)},
    "seed":    {"midi": 96, "wave": "square", "attack": 0.005, "decay": 0.020, "amplitude": 0.22, "bend": (-5, 25)},
    "hit":     {"midi": 72, "wave": "triangle", "attack": 0.005, "decay": 0.045, "amplitude": 0.45, "bend": (-7, 60)},
    "boom":    {"midi": 40, "wave": "triangle", "attack": 0.004, "decay": 0.20, "amplitude": 0.55, "bend": (-5, 220)},
    "hurt":    {"midi": 52, "wave": "triangle", "attack": 0.005, "decay": 0.14, "amplitude": 0.60, "bend": (-6, 160)},
    "morph":   {"midi": 64, "wave": "sine", "attack": 0.005, "decay": 0.10, "amplitude": 0.45, "bend": (9, 110)},
    "clear":   {"seq": [{"midi": m, "wave": "triangle", "attack": 0.005, "decay": d, "amplitude": a}
                        for m, d, a in ((69, 0.06, 0.5), (73, 0.06, 0.5), (76, 0.06, 0.5), (81, 0.22, 0.55))],
                "gap": 0.10},
    "over":    {"seq": [{"midi": 57, "wave": "triangle", "attack": 0.005, "decay": 0.08, "amplitude": 0.55},
                        {"midi": 50, "wave": "triangle", "attack": 0.005, "decay": 0.08, "amplitude": 0.55},
                        {"midi": 43, "wave": "triangle", "attack": 0.005, "decay": 0.30, "amplitude": 0.5,
                         "bend": (-4, 320)}], "gap": 0.14},
}
PICTOR_ORDER = ("throw", "seed", "hit", "boom", "hurt", "morph", "clear", "over")

# --- "analog" drum kit (mirrors picogame_synth.kick/snare/hat/tom; numbers from
# relic-se's CircuitPython_SynthVoice, MIT). tune-shifted variants included because a
# tiny PWM speaker plays nothing at 41 Hz - audition, pick, lock the tune into the game. ---
DRUMS = {
    "kick":     {"drum": {"frequencies": (53.0, 72.0, 41.0), "times": (0.075, 0.055, 0.095),
                          "waves": "sine", "cutoff": 2000, "drop": 8.0, "drop_ms": 45, "amplitude": 0.9}},
    "kick_hi":  {"drum": {"frequencies": (106.0, 144.0, 82.0), "times": (0.075, 0.055, 0.095),
                          "waves": "sine", "cutoff": 2500, "drop": 8.0, "drop_ms": 45, "amplitude": 0.9}},
    "snare":    {"drum": {"frequencies": (90.0, 135.0, 165.0), "times": (0.115, 0.095, 0.115),
                          "waves": "sine_noise", "cutoff": 9500, "drop": 3.0, "amplitude": 0.8}},
    "hat":      {"drum": {"frequencies": (90.0, 135.0, 165.0), "times": (0.1125, 0.0925, 0.1125),
                          "waves": "noise", "cutoff": 9500, "high_pass": True, "drop": 0, "amplitude": 0.6}},
    "openhat":  {"drum": {"frequencies": (90.0, 135.0, 165.0), "times": (0.625, 0.605, 0.625),
                          "waves": "noise", "cutoff": 9500, "high_pass": True, "drop": 0, "amplitude": 0.6}},
    "tom_mid":  {"drum": {"frequencies": (196.3,), "times": (0.3, 0.025),
                          "waves": ("triangle", "noise"), "cutoff": 4000, "drop": 4.0, "amplitude": 0.8}},
    "tom_floor": {"drum": {"frequencies": (131.7,), "times": (0.375, 0.025),
                           "waves": ("triangle", "noise"), "cutoff": 4000, "drop": 4.0, "amplitude": 0.8}},
    # bell partials (CedarGrove Chime table): root + 1.48x + 1.35x, root rings longest
    "bell":     {"drum": {"frequencies": (880.0, 1302.4, 1188.0), "times": (0.7, 0.45, 0.3),
                          "waves": "sine", "drop": 0, "amplitude": (0.64, 0.152, 0.08), "tail": 0.2}},
    "bell_hi":  {"drum": {"frequencies": (1318.0, 1950.6, 1779.3), "times": (0.7, 0.45, 0.3),
                          "waves": "sine", "drop": 0, "amplitude": (0.64, 0.152, 0.08), "tail": 0.2}},
    # picogame_synth.square(duty=): same note E5, duty 50% -> 25% -> 12.5%
    "pulse_cmp": {"seq": [{"midi": 76, "wave": "square", "attack": 0.004, "decay": 0.22, "amplitude": 0.55},
                          {"midi": 76, "wave": "pulse25", "attack": 0.004, "decay": 0.22, "amplitude": 0.55},
                          {"midi": 76, "wave": "pulse12", "attack": 0.004, "decay": 0.22, "amplitude": 0.55}],
                  "gap": 0.18},
}
DRUMS_ORDER = ["kick", "kick_hi", "snare", "hat", "openhat", "tom_mid", "tom_floor",
               "bell", "bell_hi", "pulse_cmp"]

# render order for the montage
ORDER = ["fire", "efire", "hit", "subhit", "pick", "surface", "oxlow", "refill", "die"]


def build(sfx_set, outdir, label, order=None):
    os.makedirs(outdir, exist_ok=True)
    montage = []
    gap = np.zeros(int(SR * 0.45))
    for name in order or ORDER:
        if name not in sfx_set:
            continue
        sig = render_spec(sfx_set[name])
        write_wav(os.path.join(outdir, name + ".wav"), sig)
        montage.append(sig)
        montage.append(gap)
    allp = os.path.join(outdir, "_all_%s.wav" % label)
    write_wav(allp, np.concatenate(montage))
    print("wrote %d SFX + montage -> %s" % (len(montage) // 2, allp))
    return allp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out"))
    ap.add_argument("--label", default=None)
    ap.add_argument("--set", default="squest", choices=("squest", "drums", "pictor"))
    ap.add_argument("--play", action="store_true")
    args = ap.parse_args()
    label = args.label or args.set
    if args.set == "drums":
        allp = build(DRUMS, args.out, label, DRUMS_ORDER)
    elif args.set == "pictor":
        allp = build(PICTOR, args.out, label, PICTOR_ORDER)
    else:
        allp = build(SQUEST, args.out, label)
    if args.play:
        for player in (("aplay", allp), ("afplay", allp), ("paplay", allp)):
            try:
                subprocess.run(player, check=True)
                break
            except Exception:
                continue


if __name__ == "__main__":
    main()
