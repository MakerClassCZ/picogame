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


def render_spec(spec):
    """A spec is one note dict, or {'seq': [note dicts], 'gap': s} for a sequence."""
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

# render order for the montage
ORDER = ["fire", "efire", "hit", "subhit", "pick", "surface", "oxlow", "refill", "die"]


def build(sfx_set, outdir, label):
    os.makedirs(outdir, exist_ok=True)
    montage = []
    gap = np.zeros(int(SR * 0.45))
    for name in ORDER:
        if name not in sfx_set:
            continue
        sig = render_spec(sfx_set[name])
        write_wav(os.path.join(outdir, name + ".wav"), sig)
        montage.append(sig)
        montage.append(gap)
    allp = os.path.join(outdir, "_all_%s.wav" % label)
    write_wav(allp, np.concatenate(montage))
    print("wrote %d SFX + montage -> %s" % (len(ORDER), allp))
    return allp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out"))
    ap.add_argument("--label", default="squest")
    ap.add_argument("--play", action="store_true")
    args = ap.parse_args()
    allp = build(SQUEST, args.out, args.label)
    if args.play:
        for player in (("aplay", allp), ("afplay", allp), ("paplay", allp)):
            try:
                subprocess.run(player, check=True)
                break
            except Exception:
                continue


if __name__ == "__main__":
    main()
