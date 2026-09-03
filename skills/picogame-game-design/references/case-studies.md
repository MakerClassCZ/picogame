# Case studies — the loop in practice (design intent → MVP in sim → screenshot → adjust → validate)

Short illustrations of how design decisions map onto engine blocks and what sim screenshots reveal.

- **A top-down racing game**: verb = *steer*; a `Tilemap` track + a `Sprite` car rotated at runtime
  (`sprite.angle`) + a camera (`set_view`) + a best-lap record/replay ghost (int16 arrays to
  fit RAM); tuned entirely via sim screenshots.
- **A pseudo-3D racing game**: wanted the OutRun feel with zero buffer → a `StripDraw` scanline road
  + a replay ghost. Lesson: a flat top-down car sprite read as 2D against the perspective road — a
  pre-rendered (slightly tilted) sprite fixed it; a *game-feel* bug only visible in a screenshot.
- **Starfall** (endless/arcade) — *the specific choices below are this game's answers to the Part 1
  questions, not the genre's*: verb = *catch*;
  readability via shape+colour (green circle gems vs red square bombs); fixed sprite pool (no per-frame
  alloc); juice = pop-ring + beep on catch, tray-flash + shake on a hit; difficulty ramps fall-speed
  and spawn-rate; instant restart. Designed and validated entirely in the simulator.
