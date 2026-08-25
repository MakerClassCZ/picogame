# Closed-loop driver for the Star Cluster showcase gif. The old clip was almost all combat; this one
# leads with the TRADE, the game's spine, and keeps combat to a short tail. It reads g["state"] and
# sequences by phase (each phase spends a fixed frame budget), driving single-frame button EDGES for the
# menu's just_pressed / held RIGHT-LEFT for the market's buy/sell repeat:
#
#   MARKET (~40%): dock at the home system Vetis, then BUY a run of FOOD (hold RIGHT) and SELL some back
#                  (hold LEFT) so cargo + credits visibly move, then dwell on the market UI.
#   MAP    (~35%): B back to the galaxy map, tour the node network (UP Fepha / LEFT Vetis / DOWN Raron)
#                  so the risk-lit gate links show, ending the cursor on Raron - a "!!" DANGER hop.
#   COMBAT (~25%): A jumps Vetis->Raron, which on day 1 is a GUARANTEED pirate ambush (precomputed from
#                  the deterministic galaxy seed), then sweep the crosshair onto the pirate and fire the
#                  overheating gun (heat-gated so it never locks) for the short combat tail.
# Used via gen_gif.py --control.

TOUR = (("UP", 20), ("LEFT", 20), ("DOWN", 22))     # cursor tour of the map, ending on Raron


def control(g, fr, pad, cs):
    state = g["state"]
    ph = cs.setdefault("ph", "dock")
    k = cs.get("k", 0)
    cs["k"] = k + 1

    def go(p):
        cs["ph"] = p
        cs["k"] = 0

    if ph == "dock":                                 # map -> open the market on the docked system
        if state == "market":
            go("buy"); pad.set(""); return
        if state != "map":                           # wait out the title splash, keep k pinned at 0
            pad.set(""); cs["k"] = 0; return
        pad.set("A" if k == 0 else "")               # first map frame: one A edge opens the market
        return

    if ph == "buy":                                  # hold RIGHT: buy a run of FOOD (row 0)
        pad.set("RIGHT")
        if k >= 34:
            go("sell")
        return

    if ph == "sell":                                 # hold LEFT: sell it back (credits climb, cargo drops)
        pad.set("LEFT")
        if k >= 30:
            go("mkdwell")
        return

    if ph == "mkdwell":                              # sit on the market UI so it reads
        pad.set("")
        if k >= 12:
            go("back")
        return

    if ph == "back":                                # B -> galaxy map
        if state == "map":
            go("tour"); pad.set(""); return
        pad.set("B" if k == 0 else "")
        return

    if ph == "tour":                                # walk the cursor across the node network
        ti = cs.get("ti", 0)
        if ti >= len(TOUR):
            go("jump"); pad.set(""); return
        key, wait = TOUR[ti]
        tk = cs.get("tk", 0)
        pad.set(key if tk == 0 else "")             # single-frame edge, then dwell
        tk += 1
        if tk >= wait:
            cs["ti"] = ti + 1
            cs["tk"] = 0
        else:
            cs["tk"] = tk
        return

    if ph == "jump":                                # A -> jump into the ambush
        if state == "cockpit":
            go("combat"); pad.set(""); return
        pad.set("A" if k == 0 else "")
        return

    # combat: sweep the crosshair onto the nearest live pirate and fire on a heat-safe duty cycle
    foes = g["foes"]; fal = g["fal"]
    rx = g["rx"]; ry = g["ry"]
    tx = ty = None
    bd = 1e18
    for i in range(len(foes)):
        if fal[i]:
            d = (foes[i].fx - rx) ** 2 + (foes[i].fy - ry) ** 2
            if d < bd:
                bd = d
                tx, ty = foes[i].fx, foes[i].fy
    keys = []
    if tx is not None:
        if tx - rx > 4:
            keys.append("RIGHT")
        elif tx - rx < -4:
            keys.append("LEFT")
        if ty - ry > 4:
            keys.append("DOWN")
        elif ty - ry < -4:
            keys.append("UP")
    firing = cs.get("cf", True)
    if g["locked"]:
        firing = False
    elif firing and g["heat"] >= 70:
        firing = False
    elif (not firing) and g["heat"] <= 20:
        firing = True
    cs["cf"] = firing
    if firing and tx is not None and abs(tx - rx) < 10 and abs(ty - ry) < 10:
        keys.append("A")                            # only when the crosshair is on the target
    pad.set(",".join(keys))
