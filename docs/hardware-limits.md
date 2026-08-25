# Hardware limits: clocks, SPI & the display

How the core clock, the peripheral clock and the display SPI relate on RP2 boards, where their
limits are, and how to measure them. The results on this page come from a PicoPad (RP2040) and
a PicoPad with its chip replaced by an RP2350 (Pico 2).

For the RAM budget and deployment, see **[HARDWARE.md](hardware.md)**. For the fast and portable
rendering paths, see the **[engine guide](engine.md#under-the-hood)**.

Looking for what the engine can and can't do in a *game* — RAM, frame rate, features? See
**[Coming from another engine](/concepts/coming-from/)** and **[Fit it in RAM](/memory/)**. This page is
firmware clock / SPI / display tuning.

---

## 1. The clock chain (what drives what)

```text
        PLL_SYS ──> clk_sys ──> the CPU cores
                        └─────> clk_peri ──> SPI, UART, …  (CircuitPython: clk_peri = clk_sys, undivided)
        XIP/QMI flash clock is derived from clk_sys too (a separate divider)
        PLL_USB ──> 48 MHz USB  (independent — the USB-CDC REPL is unaffected by overclocking)
```

Two consequences that drive everything below:

1. **`clk_peri` follows `clk_sys`.** On CircuitPython the peripheral clock is the system clock,
   undivided. So **changing the core clock changes the SPI input clock**, and therefore the
   display clock. You cannot tune one without thinking about the other.
2. **Default `clk_sys` differs by chip:** RP2040 = **125 MHz**, RP2350 = **150 MHz**. A constant
   tuned for one chip lands differently on the other (see §3).

---

## 2. How the display SPI clock is derived

The display is an ST7789 on a 4-wire SPI bus. Its clock comes from the PL022 SPI peripheral,
which divides `clk_peri` by an **even integer** (`CPSDVSR × (1+SCR)`), and the SDK picks the
divider so the actual clock is the **highest achievable that does NOT exceed your request**:

```text
actual_spi_hz = clk_peri / even_divider     # largest result <= requested baudrate
```

You request a baudrate in `board.c` (`common_hal_fourwire_fourwire_construct(... baudrate ...)`).
The request is a **ceiling**, not an exact value: if the exact value isn't an even division of
`clk_peri`, you get the next one *down*.

Worked examples (request 62.5 MHz in every case):

| clk_peri (= clk_sys) | even divisors near 62.5 | picked | actual SPI |
|---|---|---|---|
| 125 MHz (RP2040 stock) | /2 = 62.5 | /2 | **62.5 MHz** (exact) |
| 150 MHz (RP2350 stock) | /2 = 75 (> 62.5, rejected), /4 = 37.5 | /4 | **37.5 MHz** |
| 200 MHz | /2 = 100 (rej.), /4 = 50 | /4 | **50 MHz** |
| 225 MHz | /2 = 112.5 (rej.), /4 = 56.25 | /4 | **56.25 MHz** |
| 250 MHz | /2 = 125 (rej.), /4 = 62.5 | /4 | **62.5 MHz** (exact) |

**Key trap:** the same 62.5 MHz request gives 62.5 on RP2040 (125/2) but only **37.5** on a
stock-150 MHz RP2350 (because 150/2 = 75 overshoots and rounds down to 150/4). To get a good
display clock on RP2350 you must pick a `clk_sys` whose even divisions land where you want,
e.g. **250 MHz → /4 = exactly 62.5 MHz**, the in-spec maximum (see §3, §4).

To get the SPI clock you must request `request = actual` *or higher but below 2×actual*; the
safe rule is **request exactly the clock you want** and verify which divider it picked.

---

## 3. The datasheet limit (and running past it)

The **ST7789 datasheet** rates the **serial write clock** at **tSCYCW = 16 ns min → 62.5 MHz max**
(reads are far slower, ~6.6 MHz, but the display is write-only here). So **62.5 MHz is the
in-spec ceiling** for pushing pixels.

In practice the panel often runs **above** spec on a given board:

- On this PicoPad, **75 MHz** SPI (RP2350 at 150 MHz, /2) produced a **clean image**, ~20% over
  spec, works on this unit at room temperature.
- "Works here" is **not** "guaranteed everywhere": over-spec clocking can fail on another panel,
  at temperature extremes, at a different voltage, or on longer/worse wiring. Treat it as a
  per-unit experiment, not a shippable default.

Because the PL022 only divides by even integers, from a given `clk_sys` you usually have just
two choices bracketing the spec, e.g. from 150 MHz: **75** (over) or **37.5** (well under),
nothing at 62.5. Picking `clk_sys` is how you hit a good in-spec clock (250 → 62.5).

The SPI clock is the *one* transfer knob the divider gives you. A second, orthogonal lever for a
**transfer-bound** platform is **`Display(rgb444=True)`** (12-bit packed pixels, ~25% less SPI per
frame, gated by `picogame.RGB444_SUPPORTED`). It trades a per-strip pack cost for fewer bytes on the
wire, so it only wins where the panel is the bottleneck. It's compiled out on the CPU-balanced
PicoPad. See [The firmware build](/firmware/).

---

## 4. Overclocking the core

> **On the measured RP2350 PicoPad, overclocking reduced performance.** Although 250 MHz would
> set SPI to an exact, in-spec 62.5 MHz, every measured rendering mode was about **2× slower**
> at 225 MHz than at the default 150 MHz:
>
> | mode | stock 150 MHz | overclocked 225 MHz |
> |---|---|---|
> | HEAVY (CPU/blit-bound) | ~31 fps | **~15 fps** |
> | STRESS (full-frame, SPI-bound) | ~44 fps | **~16 fps** |
> | default (dirty-rect) | ~95 fps | **~42 fps** |
>
> **Why it backfires:** raising `clk_sys` without re-tuning the QMI/XIP **flash timing** makes
> code execute from flash with wait-states. The core ticks faster but instruction throughput
> *drops*; that loss outweighs the clock gain. CircuitPython's `set_sys_clock_khz`
> (whether via `microcontroller.cpu.frequency` or a `board_init` call) does **not** re-tune the
> flash; designs that overclock successfully (e.g. PicoDVI at 252 MHz) run their hot loop from
> RAM, not XIP. Re-tuning the QMI timing for the new clock is flash-chip-specific and fiddly,
> and on top of that 250 MHz independently scrambled the display (§4b), so the practical answer
> is **stay at the stock clock and get your display speed from the SPI divider (§2/§3) instead.**

The notes below are kept because they're still true *if* you ever do overclock (and the
two rules are how you avoid bricking the display while finding that out).

### Two rules for test builds

**(a) Set the clock at BOOT, in `board.c board_init()`, BEFORE the display SPI is constructed,
NOT at runtime.** Changing `microcontroller.cpu.frequency` at runtime **corrupts a live ST7789**:
the VREG voltage bump (CircuitPython raises core voltage for >133 MHz) and the PLL reconfigure
glitch `clk_peri` while the panel is mid-transaction, scrambling it. Measured: a runtime change
to *any* value ≥133 MHz scrambled the display; ≤120 MHz (no VREG change) was fine. Doing it in
`board_init` before the display exists avoids the glitch entirely:

```c
#include "hardware/clocks.h"
#include "hardware/vreg.h"
#include "hardware/timer.h"

void board_init(void) {
    vreg_set_voltage(VREG_VOLTAGE_1_20);   // required for >133 MHz
    busy_wait_us(10000);                    // let the voltage settle
    set_sys_clock_khz(225000, true);        // THEN raise the clock
    // ... only now construct the display SPI (it inits at the final clk_peri) ...
}
```

VREG voltage tiers CircuitPython uses: ≤133 MHz → 1.10 V, >133 MHz → 1.20 V, ≥300 MHz → 1.20 V,
≥400 MHz → 1.30 V.

**(b) Display command timing set the limit before the chip did.** The RP2350 booted and ran at
250 MHz (a simple game like Train was clean), but heavy rendering showed **artefacts around the
dirty regions**: at 250 MHz the CPU issues the per-rect window-setup commands (CASET / RASET /
RAMWR plus the DC/CS GPIO toggles) faster than the ST7789 reliably latches them, so an occasional
window lands wrong and the strip is written slightly off. This is a **core-clock** effect, not an
SPI-data-rate one: it appeared at 250 MHz/62.5 MHz SPI while 150 MHz/75 MHz SPI was clean (slower
SPI, faster core → still broke). It shows up wherever there are many window setups per frame
(lots of dirty rects, full-frame redraws), and barely on light dirty-rect games.

Binary search on this board found the *display* ceiling: **150 · 200 · 225 MHz clean · 250 MHz
dirty** (panel-command limit between 225 and 250). But see the box above, even at the clean
200/225 the board ran ~2× slower overall (flash/XIP), so the board ships **stock 150 MHz**, not
an overclock. The clock is not the lever here; the SPI divider is.

### The trade-off

Overclocking raises the CPU but (via the even-divider rule) often *lowers* the in-spec SPI clock:

| Build | core | display SPI | result |
|---|---|---|---|
| **stock + "spi75" (shipped)** | 150 MHz | 75 MHz (over spec, clean here) | **fastest overall on this board** |
| boot-225 (rejected) | 225 MHz | 56.25 MHz (in spec) | ~2× slower (flash/XIP, see the box in §4) |

The overclock's lower SPI *and* its flash penalty both pushed the wrong way, so the
recommended RP2350 PicoPad config is **stock 150 MHz with a 75 MHz SPI request** (`/2`).

The clock/SPI-divider coupling above is the general trade-off (you can't max both from one even
divider) - but note it never made overclocking win on the measured board: the XIP wait-state
penalty (§4) dominated for every workload. On this hardware, stay at stock and choose the SPI
divider; treat "overclock a CPU-bound game" as a hypothesis to re-measure on other boards, not
advice.

---

## 5. How to test it

Run a benchmark whose toggles isolate each regime:

| Toggle | Isolates | Read |
|---|---|---|
| `FAST = True/False` | fast DMA vs portable renderer | are they different? (only multi-strip transfers differ) |
| `STRESS = True` | forces a full-frame repaint every frame | the **SPI-bound** ceiling (∝ SPI clock) |
| `HEAVY = True` | a few big scale+rotate sprites | the **CPU/blit-bound** case (∝ core clock) |
| `OVERCLOCK = …` | runtime core clock | **leave None on the PicoPad**: runtime change corrupts the display; overclock at boot in firmware instead |

Reading the results:

- **Default mode (small sprites) is a poor metric:** 25 scattered sprites exceed the limit of
  six dirty regions. The least expensive pairs are then merged until six remain, and their
  total area varies as the sprites move. FPS therefore changes with the sprite layout. Use
  `STRESS` for a repeatable full-frame workload or `HEAVY` for a repeatable CPU workload.
- **`STRESS` is designed to expose the transfer-bound case.** If its FPS changes roughly in
  proportion to the SPI clock, SPI transfer is the bottleneck in that configuration.
- **`HEAVY` is designed to expose the CPU/blit-bound case.** Compare it across builds to see
  whether a core-clock change improves instruction throughput on that board.

Spotting an over-clock that's too high for the display:

- **Artefacts around / at the edges of dirty regions**, smearing, or shifted strips in heavy
  rendering, while a light scene (or a simple game) still looks fine. That's the window-command
  timing ceiling (§4b), not a crash.
- A clock too high for the **chip/flash** instead fails harder: it won't boot or hard-faults.
- **Recover with BOOTSEL:** if the firmware no longer boots after a clock change, hold BOOTSEL
  and re-flash a known-good `.uf2`.

Finding the ceiling: build firmwares at descending core clocks (250 → 225 → 200 → …), flash each,
run `STRESS` + `HEAVY`, and keep the **highest clock with no dirty-region artefacts**. Change the
clock only in `board.c board_init` (not at runtime), and re-check which SPI divider the new
`clk_peri` selected (§2).
