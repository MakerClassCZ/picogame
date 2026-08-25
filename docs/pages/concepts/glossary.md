---
title: Glossary
description: Plain-language definitions of the game-making words used across these docs — written for people who know CircuitPython but are new to games.
sidebar:
  order: 2
---

This glossary explains the game-development terms used throughout the docs. Where useful, it
connects them to concepts from CircuitPython `displayio`.

## Sprite

A movable picture: the player, an enemy, a bullet, a coin. It wraps a `Bitmap` and has a
position you change each frame. Closest `displayio` analogy: a single `TileGrid` you reposition,
except a picogame sprite also flips, scales, rotates, and animates.

## Layer

One thing the scene draws, stacked back-to-front like sheets of glass. A sprite, a tilemap, a
canvas and so on are all "layer kinds"; the order you add them is the order they're painted.

## Tilemap

A big area built from a small set of repeating tile pictures (a background, a brick wall, a
level grid), stored as **1 byte per cell** (the tile number), so it's far cheaper than one sprite
per cell. Like a grid of `displayio` `TileGrid` cells.

## Scene and retained mode

picogame is **retained mode**: you build the objects once with `scene.add(...)`, and the engine
*remembers* them. Each frame you change what moved and call `scene.refresh()`; you don't
redraw everything yourself. (The opposite, **immediate mode**, means you clear and redraw the
whole screen every frame by hand.) A `Scene` is the container holding all your layers.

## Dirty rectangle

The region that changed since the last frame. Because the scene remembers everything (above), it
can work out which regions moved and **repaint only those**. "Dirty" means "changed and needs repainting."

## Blit

To copy a picture's pixels onto the screen (or into another drawing surface). `displayio` hides
this behind Groups and TileGrids, so you may never have typed it; in picogame it's the basic
"stamp this bitmap here" operation.

## Game loop

The heartbeat of every game: each frame, **read input → update the world → draw → wait a bit**,
then repeat. picogame games are all this same shape.

## Frame

This word means two different things, so watch the context:

- a **screen frame** — one turn of the game loop (one repaint), as in "each frame you move the player";
- an **animation frame** — one picture in a bitmap's strip of pictures, as in "advance `sprite.frame`
  to the next walk pose."

## Anchor

The pivot point a sprite scales and rotates around, given as fractions of its size: `(0.5, 0.5)`
is the centre, `(0.5, 1.0)` the bottom-centre. Its position and rotation are measured about this point.

## AABB

A box overlap test, short for *axis-aligned bounding box*, a plain (non-rotated) rectangle drawn
around a sprite. "Do these two AABBs overlap?" is the cheapest way to check if two things collide.

## Object pool

A fixed set of sprites you create **once** and recycle (spawn / free) instead of making and
deleting them mid-game. Creating and destroying objects each frame fragments the tiny RAM; a pool
avoids that. Reach for `picogame_pool` for bullets, enemies, coins, anything that comes and goes.

## Wire-order colour

The byte order the display panel expects over SPI, which is **not** the same as a plain
`0xRRGGBB` literal. Always build colours with `pg.rgb565(r, g, b)`; passing a raw hex literal gives
wrong colours. (This is the one colour footgun coming from `displayio`.)

## Juice

The small, cheap touches that make a game *feel* good: a hit-flash, a screen shake, a spark, a
beep on the key action. Standard game-maker slang; `picogame_fx` provides most of it.

## Parallax

Background layers that scroll **slower** than the foreground, creating an illusion of depth (think
of distant hills drifting by slower than the roadside).

## Coyote time and jump buffering

Two small fairness tricks: **coyote time** lets the player still jump for a few frames after
walking off a ledge; **jump buffering** honours a jump pressed just before landing. Both make
controls feel forgiving (`picogame_input.Timer`).

## Ghost lap

In racing games, a translucent replay of your best lap shown on the track so you can race against
your own record.

## State machine

The game switches between named modes (title → playing → game-over). One `state` variable decides
what updates and draws each frame.

## Stride

How many **pixels** one row of a bitmap's source data spans. Leave it `0` and the engine assumes
the data is tightly packed (one row is `width × frames` pixels, the full horizontal atlas); set it
only when you're pointing at a **sub-window of a larger image**, where each row in memory is wider
than the part you're drawing. A constructor argument on `Bitmap(...)`.

## StripDraw and Canvas

Two ways to draw custom pixels, traded off by memory (see [Drawing paths](/concepts/drawing-paths/)
for the full picture):

- **Canvas** — a retained pixel buffer (`width × height × 2` bytes) you draw onto and reuse; right
  for a panel that changes rarely.
- **StripDraw** — a buffer-less layer that draws into each live strip. It retains **0 pixel bytes**,
  but its callback still uses CPU each time the region repaints. Use it for full-frame effects and
  dynamic HUD or text.
