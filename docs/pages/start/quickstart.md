---
title: Get it on your device
description: Flash the picogame firmware, then download the ready-made games pack for your board — a launcher boots so you can pick a game and play.
sidebar:
  label: Get it on your device
  order: 5
---

Two steps put a menu of ready-to-play games on your handheld: flash the firmware once, then copy the
pack for your board onto the drive. No coding needed — a [launcher](/launcher/) boots and lets you
pick a game with the D-pad.

## 1. Flash the firmware

The firmware **is** the picogame engine — a CircuitPython build with the native-C module baked in. You
flash it once per board.

Download the `.uf2` for your board from [Supported hardware](/supported-hardware/#download-firmware),
hold **BOOTSEL** while you plug the board in, and drag the `.uf2` onto the drive that appears. The
board reboots and shows up as a **`CIRCUITPY`** drive.

## 2. Download the pack for your board

Each pack is a ready `CIRCUITPY` layout — the launcher, the games and demos (compiled `.mpy`), the
helper libraries and fonts. Pick the one for your board and **extract it onto the `CIRCUITPY` drive**.

- **[RP2040 — PicoPad, plain Pico](/download/picogame-rp2040.zip)** — a tight-RAM set (8 games +
  10 demos) tuned to fit the RP2040. Start here on a PicoPad or a bare Pico.
- **[RP2350 — PicoPad 2, Pico 2](/download/picogame-rp2350.zip)** — the full portfolio (every game and
  demo) with intro splashes, for RP2350-class boards with RAM to spare.
- **[Fruit Jam](/download/picogame-fruitjam.zip)** — the full portfolio plus a `settings.toml` that
  sets the Fruit Jam audio levels and DVI display.

Not sure which chip your board has? See [Supported hardware](/supported-hardware/).

## 3. Play

Eject the drive and reset the board. The launcher lists the games — **UP/DOWN** to move, **A** to
play, the board's **RESET** button to come back to the menu.

## Next

- Add your own game to the menu, or see how the launcher finds games → [The games menu](/launcher/).
- Want to build a game rather than play the packs? → [Your first game](/start/first-game/) and
  [Run on hardware](/hardware/).
