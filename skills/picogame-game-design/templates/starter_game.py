# picogame starter — a runnable skeleton to copy and reshape into your game.
# It already has the standard structure the skill teaches (SKILL.md §1.6):
#   setup -> HUD -> State object -> TITLE / PLAY / OVER state machine -> loop in a function.
# Replace the marked sections. Validate it headless in the simulator (screenshot = your eyes):
#   python3 sim/run.py templates/starter_game.py --frames 80 --hold RIGHT --shot /tmp/shot.png
# (For the human to actually play it: python3 sim/run.py templates/starter_game.py --backend pygame)
#
# Deploy: copy this file to CIRCUITPY as code.py plus the picogame_* helpers it imports.


import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shapes
import picogame_ui as ui

# --- colors (ALWAYS via rgb565 — never raw 0xRRGGBB) ---
BG = pg.rgb565(18, 22, 36)
INK = pg.rgb565(255, 255, 255)
HERO = pg.rgb565(240, 90, 90)

W, H = picogame_game.screen()
BAR = 16                                          # reserve a top HUD strip

# --- tuning knobs: named constants at the top of the file. On CircuitPython the game's
# source sits on the drive, so players adjust difficulty/effects HERE — no settings menu needed.
SPEED = 3
START_LIVES = 3

# setup() takes over the display and returns a retained Scene + its two strip buffers.
scene, bufA, bufB = picogame_game.setup(background=BG, top=BAR)
buttons = picogame_input.Buttons()
clock = picogame_clock.Clock(30)                  # frame cap (fps)

# --- HUD (camera-independent text bar) ---
hud = ui.HudBar(pg, picogame_game.display(), bufA, 0, 0, W, BAR, pg.rgb565(12, 14, 26))
score_label = hud.label(terminalio.FONT, 4, 3, INK, "SCORE 0")
msg_label = hud.label(terminalio.FONT, W - 100, 3, INK, "A = START")
hud.draw()

# --- game objects: engine objects stay MODULE GLOBALS (built once, never rebuilt) -----
# Prototype with generated shapes; swap in real art later (a Bitmap from png2picogame).
hero = pg.Sprite(shapes.circle(16, HERO), W // 2, H // 2)
hero.anchor = (0.5, 0.5)
scene.add(hero)

# --- state machine + State object (SKILL.md §1.6) ------------------------------------
TITLE, PLAY, OVER = 0, 1, 2                       # int states: cheaper compares than strings


class State:
    """ALL mutable game state in ONE object — never rebound, reset in place."""

    def __init__(self):
        self.state = TITLE                        # boot into the title, not straight into play
        self.score = 0
        self.lives = START_LIVES
        self.reset()

    def reset(self):
        self.score = 0
        self.lives = START_LIVES
        hero.move(W // 2, H // 2)                 # reset positions; free pooled sprites here too


st = State()


def new_game():
    st.reset()
    st.state = PLAY


def update():
    """Game rules go here: move things, spawn/despawn, collisions, scoring."""
    hero.x += (buttons.is_pressed(buttons.RIGHT) - buttons.is_pressed(buttons.LEFT)) * SPEED
    hero.y += (buttons.is_pressed(buttons.DOWN) - buttons.is_pressed(buttons.UP)) * SPEED
    hero.x = max(8, min(W - 8, hero.x))
    hero.y = max(BAR + 8, min(H - 8, hero.y))
    # example rules: A scores, B costs a life (replace with real collisions/scoring)
    if buttons.just_pressed(buttons.A):
        st.score += 1
    if buttons.just_pressed(buttons.B):
        st.lives -= 1
        if st.lives <= 0:
            st.state = OVER                       # end the run; peak-end: show the score big


def draw_hud():
    score_label.set("SCORE %d" % st.score)        # update the label handle...
    if st.state == PLAY:
        msg_label.set("LIVES %d" % st.lives)
    else:
        msg_label.set("A = START")
    hud.draw()                                    # ...then repaint the bar


print("starter — arrows move, A scores, B loses a life. Reshape me into your game.")


def main():
    # The per-frame loop lives in a FUNCTION (not at module scope): inside a function, name lookups are
    # array-indexed locals instead of globals-dict lookups — a measured on-device win (SKILL.md §1.6).
    # Hoist the hot per-frame calls to locals once here:
    poll = buttons.poll
    pressed = buttons.just_pressed
    A = buttons.A
    refresh = scene.refresh
    tick = clock.tick
    h_score = h_lives = h_state = None            # HUD shadow copies: SCALARS, not a tuple - a
                                                  #  `key = (a, b, c)` per frame allocates every
                                                  #  frame (the MUST in engine-capabilities.md)
    while True:
        poll()                                    # 1. input
        if st.state == PLAY:                      # most-frequent state first
            update()                              # 2. update game state
        elif pressed(A):                          # TITLE and OVER: A = (re)start
            new_game()                            # INSTANT restart — reset in place, no reload
        refresh()                                 # 3. draw what changed (dirty-rect)
        if st.score != h_score or st.lives != h_lives or st.state != h_state:
            h_score, h_lives, h_state = st.score, st.lives, st.state   # repaint on CHANGE only
            draw_hud()                            # safe AFTER refresh() ONLY because the scene never
                                                  # draws into the reserved band (top=BAR); an overlay
                                                  # ON the play area needs picogame_game.overlay()
        tick()                                    # 4. hold the framerate


main()                                            # module bottom: kick it off (starts in TITLE)
