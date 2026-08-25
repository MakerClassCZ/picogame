# Closed-loop driver for the Pico Wing showcase gif. Reads the game's live globals each frame and
# actually PLAYS the shmup: it locks onto the nearest live raider ABOVE the ship (bullets fly up),
# slides the ship under it, and fires the autocannon on a HEAT-aware duty cycle so shots connect and
# raiders explode instead of the old "weave-and-miss" clip. The gun overheats and LOCKS on a long
# hold (HEAT_PER_SHOT ramps to 100), so we fire until the gauge is hot then release to cool - reading
# st.heat / st.gun_locked directly - which keeps a near-continuous stream of kills without ever jamming.
# Used via gen_gif.py --control.

def control(g, fr, pad, cs):
    st = g["st"]
    if st.state != "play":                       # title / game-over: pulse A to (re)start
        cs["a"] = not cs.get("a", False)
        pad.set("A" if cs["a"] else "")
        return
    plane = g["plane"]
    enemies = g["enemies"]
    items = enemies.items
    px, py = plane.fx, plane.fy

    # Lock the raider needing the LEAST sideways travel (nearest in x, still above the ship): the ship
    # settles under it fast and the raider descends into the upward bullet stream = a reliable kill.
    # Hysteresis (switch only for a target >25 px closer) stops the ship thrashing between two drifters.
    tgt = cs.get("tgt", -1)
    cur = None
    if 0 <= tgt < len(items):
        e = items[tgt]
        if e.visible and e.fy < py:
            cur = e
    best = None
    bestdx = 1e9
    for i, e in enumerate(items):
        if not e.visible or e.fy >= py:
            continue
        d = abs(e.fx - px)
        if d < bestdx:
            bestdx = d
            best = e
            besti = i
    if cur is None:
        if best is not None:
            cs["tgt"] = besti
    elif best is not None and bestdx + 25 < abs(cur.fx - px):
        cs["tgt"] = besti                          # a much easier target appeared -> switch
        cur = best
    if cur is not None:
        best = cur                                 # keep firing on the locked target

    steer = ""
    if best is not None:
        dx = best.fx - px
        if dx > 2:
            steer = "RIGHT"
        elif dx < -2:
            steer = "LEFT"

    # HEAT hysteresis: keep firing until the gauge is nearly hot, then let go until it cools - so the
    # cannon streams almost continuously but the overheat lock (heat>=100) never trips.
    firing = cs.get("fire", True)
    if st.gun_locked:
        firing = False
    elif firing and st.heat >= 82:
        firing = False
    elif (not firing) and st.heat <= 24:
        firing = True
    cs["fire"] = firing

    keys = []
    if firing:
        keys.append("A")
    if steer:
        keys.append(steer)
    pad.set(",".join(keys))
