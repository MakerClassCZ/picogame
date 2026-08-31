# lib/ — picogame helper modules

The `picogame_*` modules a game imports. The native engine (`import picogame as pg`) is in the
firmware; everything here is plain Python on top of it, and you only pay for what you import.

## Which one do I want

| I want to… | Look at |
|---|---|
| stand a game up — display, scene, buttons, frame timing | `picogame_game` · `picogame_input` · `picogame_clock` |
| load a level built in the [editor](https://picogame.makerclass.cz/editor/) | `picogame_scene` (`picogame_scenebake` to bake its JSON on the device) |
| put text, a HUD, menus or an options screen on screen | `picogame_ui` · `picogame_font` · `picogame_bitfont` · `picogame_options` |
| make art without an art pipeline | `picogame_shapes` (shapes → bitmaps) · `picogame_palette` (recolour, cycle, fade) |
| make a hit feel like a hit — shake, flash, tween, fades | `picogame_fx` |
| spawn many things; animate; read tile properties; script a sequence | `picogame_pool` · `picogame_anim` · `picogame_tiles` · `picogame_seq` |
| do pseudo-3D — a Mode-7 floor, corridors, an OutRun road, isometric | `picogame_mode7` · `picogame_ray` · `picogame_road` · `picogame_iso` |
| make sound and music | `picogame_sfx` (ready-made kit) · `picogame_synth` · `picogame_audio` · `picogame_music` |
| save progress, stream big data, run a cutscene | `picogame_save` · `picogame_stream` · `picogame_cutscene` |
| use a USB gamepad, a keyboard or an I2C pad | `picogame_usbpad` · `picogame_usbkbd` · `picogame_i2cpad` |
| get vectors/easing, or randomness a run can reproduce | `picogame_math` · `picogame_rand` |
| ship several games on one device, with a menu to pick one | `picogame_launcher` |
| find where the RAM went | `picogame_debug` · `picogame_arena` |

**One sentence per module, grouped the same way:
[the picogame-libs README](https://github.com/MakerClassCZ/picogame-libs#readme)** — that index is
the complete one and a test keeps it that way. Full signatures: **[`docs/reference.md`](../docs/reference.md)**, right here in the clone (also served at [picogame.makerclass.cz/reference/](https://picogame.makerclass.cz/reference/)).

## About this folder

**Do not edit these files here.** This folder is a **generated mirror** of
[picogame-libs](https://github.com/MakerClassCZ/picogame-libs) — the single source of truth for the
`picogame_*` helper library (its own repo, changelog, and releases). It is vendored into this repo so a
clone is **self-contained**: the simulator and the games here import these modules with no extra setup.

- **Source of truth:** picogame-libs — edit, version, and read the changelog there. A fix sent here
  is overwritten by the next mirror; send it there and it reaches everyone.
- **On a CircuitPython device:** prefer `circup install` from picogame-libs (versioned, with a changelog)
  over copying these by hand; or copy the matching `.mpy` from picogame-libs `mpy/` for less RAM.
