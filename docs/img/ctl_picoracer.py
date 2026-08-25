# Closed-loop driver for the picoracer showcase gif. Presses B at the title, waits out the 3-2-1
# countdown, then RACES: a wide fan of road.at_px probes steers toward the average on-road bearing (reads
# 90-degree corners correctly — a narrow probe U-turned at the first one), while the throttle runs the
# straights near top speed (~4.7 target) and brakes into corners (detected by the road running out
# straight ahead) down to ~2.2, then accelerates out — an accelerate / brake-turn / accelerate rhythm
# that stays on the racing line (100% on-road). Capture ~frame 48 (the countdown) through the corners.
import math

def control(g, fr, pad, cs):
    st = g["st"]
    mode = getattr(st, "mode", "race")
    if mode == "start":
        pad.set("B"); return
    if mode == "countdown":
        pad.set(""); return

    road = g["road"]; tm = g["tm"]; tiles = g["tiles"]
    WW = g["WORLD_W"]; WH = g["WORLD_H"]; T = g["T"]

    def onroad(bearing, L):
        r = math.radians(bearing)
        x = st.subx + math.sin(r) * L
        y = st.suby - math.cos(r) * L
        return road.at_px(tm, max(0, min(WW - 1, int(x))), max(0, min(WH - 1, int(y))), tiles.B_SOLID)

    th = st.th
    Lf = T * 2.4
    fan = (-85, -65, -45, -28, -14, 0, 14, 28, 45, 65, 85)     # wide fan -> reads 90-degree corners
    roadb = [b for b in fan if onroad(th + b, Lf)]
    desired = sum(roadb) / len(roadb) if roadb else 0.0
    if desired > 9: steer = "RIGHT"
    elif desired < -9: steer = "LEFT"
    else: steer = ""

    # corner detection = road runs out STRAIGHT ahead (width-bias-free); brake before it, then floor it
    if not onroad(th, T * 2.2): tgt = 2.2         # in the corner
    elif not onroad(th, T * 3.6): tgt = 3.2       # corner approaching -> ease off
    else: tgt = 4.7                                # clear straight -> FAST
    if st.speed > tgt + 0.5: gas = "A"
    elif st.speed < tgt - 0.3: gas = "B"
    else: gas = ""
    pad.set(",".join(k for k in (gas, steer) if k))
