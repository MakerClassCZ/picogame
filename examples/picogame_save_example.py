# picogame persistence demo (NVM): proves the save survives a reboot.
# A boot counter increments every power-on/reset (so you SEE persistence even
# without scoring); A adds to the score, B saves it as the highscore.
# Copy with picogame_save.py to CIRCUITPY. No reflash needed (NVM is built in).

import picogame_input
import picogame_clock
import picogame_save

# Buttons() gives auto per-board pin profiles + just_pressed() edge detection,
# so the demo carries only the save logic it is meant to showcase. Clock paces.
btns = picogame_input.Buttons()
clock = picogame_clock.Clock(60)

# The first arg is THIS game's key. A different game using the same NVM slot
# would fail the key check and get its own defaults, never our highscore.
save = picogame_save.Save("savedemo", {"hiscore": ("I", 0), "boots": ("H", 0)})
data = save.load()
data["boots"] += 1
save.save(data)        # persist the boot counter right away

print("boot #%d  |  stored hiscore = %d" % (data["boots"], data["hiscore"]))
print("A = +100 score, B = save as hiscore. RESET the board to confirm it persisted.")
print("Tip: change the key above to see load() fall back to defaults (foreign slot).")

score = 0
while True:
    btns.poll()
    if btns.just_pressed(btns.A):
        score += 100
        print("score =", score)
    if btns.just_pressed(btns.B):
        if score > data["hiscore"]:
            data["hiscore"] = score
            save.save(data)
            print("NEW HIGHSCORE saved:", score)
        else:
            print("not a highscore (best = %d)" % data["hiscore"])
    clock.tick()
