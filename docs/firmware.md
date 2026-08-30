# The firmware build

The PicoPad firmware is a CircuitPython build with the native `picogame` module enabled.

## Building & flashing

Prerequisites: **ARM GCC ≥ 14** and initialized submodules.

```bash
# from the CircuitPython fork root
make -C ports/raspberrypi BOARD=pajenicko_picopad -j"$(nproc)"
```

Output: `ports/raspberrypi/build-pajenicko_picopad/firmware.uf2`. Flash it over
**BOOTSEL** (hold BOOTSEL while plugging in, then drag the `.uf2` onto the `RPI-RP2` drive)
like any CircuitPython firmware.

See [Run on hardware](hardware.md) for the device side and [Fit it in RAM](memory.md) for the
RAM budget.

## Where picogame lives in the tree

The engine lives in the `picogame` branch of the CircuitPython fork. Two module directories
contain the implementation, and build flags select the module and optional backends.

| Path | What |
|---|---|
| `shared-bindings/picogame/` | the Python-facing API + docstrings: `__init__`, `Scene`, `Sprite`, `Bitmap`, `Tilemap`, `Canvas`, `Particles`, `Display`, `Framebuffer` |
| `shared-module/picogame/` | the **portable** C core — the blit / scene / tilemap / particles / canvas implementation, no port dependencies |
| `ports/*/common-hal/picogame/Display.c` | the optional per-port fast display backend (raspberrypi + espressif provide one) |

Build-system hooks:

| File | Change |
|---|---|
| `py/circuitpy_mpconfig.mk` | registers the five `CIRCUITPY_PICOGAME*` flags — all default `0` |
| `py/circuitpy_defns.mk` | compiles `picogame/%` only when `CIRCUITPY_PICOGAME = 1`; adds `common-hal/picogame/Display.c` only when `FAST_DISPLAY = 1` |
| `ports/raspberrypi/boards/pajenicko_picopad/` | the board that opts in (config below) |

### The port intervention: the fast display path

The portable core in `shared-module/` never touches hardware — it blits pixels into a strip
buffer and hands that buffer to a `busdisplay` through `bus.send`. This is the portable path
for ports that compile picogame and expose a compatible SPI display. Each `bus.send` **blocks**
the CPU until the strip has finished
transferring over SPI, so rendering and transfer happen strictly one after the other.

`ports/raspberrypi/common-hal/picogame/Display.c` is the one place the engine reaches into
the port, to remove that stall. It drives the RP2040's SPI and DMA directly:

- **Overlap.** It double-buffers strips and DMAs one strip out over SPI *while the CPU blits
  the next* — render and transfer run concurrently instead of serially. It waits on the
  previous DMA only just before reusing that buffer.
- **Raw streaming.** It opens the panel's GRAM window once (via `busdisplay`, which drives DC
  high for the first data strip), then streams the remaining strips as raw DMA with no
  per-strip reconfiguration or DC toggling.
- **One DMA channel, reused.** The channel is claimed once and kept across soft resets and
  game launches; the pico-SDK doesn't free it on soft reset, so claiming per-construct would
  leak channels until DMA is exhausted.

This is what `CIRCUITPY_PICOGAME_FAST_DISPLAY` gates — both the `pg.Display` type and the
common-hal file. **The flag is optional.** With it off, picogame still runs everywhere via the
portable `bus.send` renderer; it's just slower because each strip transfer blocks. The overlap
only helps when a repaint spans multiple strips, so the win grows with per-strip blit cost:
near zero for a small dirty-region update and larger for a full-frame, transform-heavy
scene. Treat the 25–30% measured on the PicoPad benchmark as configuration-specific; see
[Clocks, SPI & display limits](hardware-limits.md) for the test setup.

## Board configuration

A board turns the engine on in its `mpconfigboard.mk`:

```make
CIRCUITPY_PICOGAME = 1                # compile the engine in
CIRCUITPY_PICOGAME_FAST_DISPLAY = 1   # async-DMA display backend (raspberrypi port)
CIRCUITPY_PICOGAME_RGB444 = 0         # panel COLMOD capability (see Build flags)
OPTIMIZATION_FLAGS = -O2 …            # tuned for the Cortex-M0+ (see appendix)
CFLAGS += -DCIRCUITPY_FIRMWARE_SIZE='(1536 * 1024)'   # + a matching linker-script change
```

**Display SPI clock (in `board.c`).** Request **62.5 MHz** (125/2) for the ST7789, not 60 —
the PL022's even-only divider rounds 60 down to half speed. See
[Clocks, SPI & display limits](hardware-limits.md).

**Keep the image general-purpose.** Leave the full module set on; only disable what this
device physically can't use.

| Module | State | Why |
|---|---|---|
| `picogame` (+ fast DMA display) | **on** | the engine |
| native `_stage` (`CIRCUITPY_STAGE`) | on | runs the original ugame/stage games head-to-head with the **picogame-stage** shim |
| `ulab`, `synthio`, audio, `displayio`, `bitmaptools`, `vectorio`, Wi-Fi, `keypad`, … | on | general-purpose, they fit |
| `picodvi`, `_eve` | off | no DVI / FT8xx hardware on this device |
| `qrio` | off | QR *decode* needs a camera the PicoPad lacks; also drops its ~32 KB `quirc` backend (QR *generation* via `adafruit_miniqr` is unaffected) |

The measured build used about **88%** of its 1.5 MB firmware region; this changes with the
CircuitPython version and enabled modules.

## Build flags

| Flag | Default | What it does |
|---|---|---|
| `CIRCUITPY_PICOGAME` | `0` | compile the engine in |
| `CIRCUITPY_PICOGAME_FAST_DISPLAY` | `0` | use the port's async-DMA `Display` (raspberrypi + espressif); other boards fall back to the portable `bus.send` renderer |
| `CIRCUITPY_PICOGAME_RGB444` | `0` | board declares its panel supports 12-bit RGB444 (COLMOD), exposed as `picogame.RGB444_SUPPORTED` so a game can enable `Display(rgb444=True)` only where it helps. Off on PicoPad — on this CPU-balanced panel the per-strip pack cost ≥ the SPI saving. |
| `CIRCUITPY_PICOGAME_FRAMEBUFFER` | `0` | full-frame RAM-framebuffer backend for scanout platforms (RP2350 DVI/HSTX, the desktop sim, the WASM playground) instead of an SPI strip bus |
| `CIRCUITPY_PICOGAME_ROMFS_KB` | `0` | carves a flash asset region (in KB) for 0-copy ROMFS-XIP bitmaps; only the `-romfs` firmware variants set it (e.g. `64`) |

**Render-strip height.** On an SPI display, the screen is painted in horizontal strips of
`STRIP_H` rows. `picogame_game.setup()` allocates two `width × STRIP_H × 2`-byte buffers;
the framebuffer path returns `None` for both and does not allocate them. The SPI default is
keyed to `FAST_DISPLAY`: **8** rows with DMA and **24** without. These are performance defaults
for the measured paths; a smaller value always uses less buffer RAM. Override per board with
`-DPICOGAME_STRIP_H=N`, or per game via `picogame_game.setup(strip_h=N)`; read it at runtime
as `picogame.STRIP_H`. More in [Fit it in RAM](memory.md).

---

## Appendix: compiler optimization (tuned −O2)

CircuitPython's rp2 port defaults to `-O3`. On the PicoPad's Cortex-M0+ (no SIMD, no FPU,
16 KB XIP cache) most of what `-O3` adds is dead weight — the auto-vectorizers have no SIMD to
target, and function cloning / heavy loop unrolling only grow flash. So the board ships
**`-O2` plus the five cheap loop passes that do help the pixel loops**, matching `-O3` engine
speed within ~1 % for ~150 KB less flash:

```make
OPTIMIZATION_FLAGS = -O2 -funswitch-loops -fpredictive-commoning -fgcse-after-reload \
                     -ftree-partial-pre -fsplit-paths
```

The MicroPython interpreter core (`gc.o`, `vm.o`) stays at `-O3` via CircuitPython's
`SUPEROPT_*` settings, so Python execution speed is unaffected. The single hottest loop (the
plain sprite blit) additionally carries a `#pragma GCC unroll 4` — ~8 % faster on the M0+ for
+0.3 KB; `-funroll-loops` firmware-wide would overflow the flash region.

Measured on-device, all builds on CircuitPython 10.3.0; **lower is faster**, best in each
column **bold**. **Engine** = `picogame_bench_hotpath.py` (108 sprites of 32×32 over 120
frames at 320×240, ms/frame min); **Python** = `bench_optlevel.py` (ms/op); **flash** = full
image, KB. The `O2+` row is the shipped build (baseline); each `🟢/🟡/🔴` marks how far a
cell sits from it (better / ≤5 % worse / >5 % worse).

| | bg-fill<br><sub>ms</sub> | plain<br><sub>ms</sub> | plain+bg<br><sub>ms</sub> | tint<br><sub>ms</sub> | transpose<br><sub>ms</sub> | bignum<br><sub>ms</sub> | int<br><sub>ms</sub> | float<br><sub>ms</sub> | fib<br><sub>ms</sub> | ulab-py<br><sub>ms</sub> | ulab-np<br><sub>ms</sub> | flash<br><sub>KB</sub> |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `-O3` *(rp2 default)* | **24.9** 🟢<sub>−1.2%</sub> | 36.3 🟡<sub>+0.8%</sub> | 37.0 🟡<sub>+0.1%</sub> | **80.2** 🟢<sub>−0.5%</sub> | 46.1 🟡<sub>+0.3%</sub> | 98.8 🔴<sub>+8.8%</sub> | 20.84 🟡<sub>+2.1%</sub> | 40.80 🟡<sub>+1.3%</sub> | **657.8** 🟢<sub>−0.0%</sub> | **2.63** 🟢<sub>−2.2%</sub> | 0.76 🔴<sub>+17%</sub> | 1499 🔴<sub>+11%</sub> |
| `-O2` | 25.3 🟡<sub>+0.4%</sub> | 38.2 🔴<sub>+5.9%</sub> | 39.1 🔴<sub>+5.7%</sub> | 81.2 🟡<sub>+0.8%</sub> | 53.9 🔴<sub>+17%</sub> | 92.0 🟡<sub>+1.3%</sub> | **20.29** 🟢<sub>−0.6%</sub> | 40.34 🟡<sub>+0.1%</sub> | 660.2 🟡<sub>+0.3%</sub> | 3.77 🔴<sub>+40%</sub> | 0.66 🟡<sub>+1.5%</sub> | 1326 🟢<sub>−1.4%</sub> |
| `-Os` | 27.0 🔴<sub>+7.4%</sub> | 43.6 🔴<sub>+21%</sub> | 46.4 🔴<sub>+25%</sub> | 121.9 🔴<sub>+51%</sub> | 103.0 🔴<sub>+124%</sub> | 113.3 🔴<sub>+25%</sub> | 21.18 🟡<sub>+3.7%</sub> | 44.07 🔴<sub>+9.4%</sub> | 667.3 🟡<sub>+1.4%</sub> | 3.00 🔴<sub>+11%</sub> | 0.73 🔴<sub>+12%</sub> | **1167** 🟢<sub>−13%</sub> |
| `O3−` *(−O3 minus vectorizers + cloning)* | 25.2 🟡<sub>+0.1%</sub> | 36.2 🟡<sub>+0.5%</sub> | 37.2 🟡<sub>+0.6%</sub> | 81.5 🟡<sub>+1.1%</sub> | 46.1 🟡<sub>+0.2%</sub> | 96.1 🔴<sub>+5.8%</sub> | 20.32 🟢<sub>−0.5%</sub> | 40.95 🟡<sub>+1.7%</sub> | 662.8 🟡<sub>+0.7%</sub> | 2.75 🟡<sub>+2.2%</sub> | 0.68 🟡<sub>+4.6%</sub> | 1480 🔴<sub>+10%</sub> |
| **`O2+`** *(shipped — baseline)* | 25.2 | **36.0** | **37.0** | 80.6 | **46.0** | **90.8** | 20.42 | **40.28** | 658.0 | 2.69 | **0.65** | 1345 |

`-Os` shrinks flash most but wrecks the affine/blend loops (`tint` +51 %, `transpose` +124 %);
`O3−` matches engine speed yet stays +134 KB because `-O3`'s firmware-wide inlining survives;
the Python columns barely move since the interpreter core is `-O3` in every build.
(`bench_displayio.py` was flat across opt levels, so it's omitted.)
