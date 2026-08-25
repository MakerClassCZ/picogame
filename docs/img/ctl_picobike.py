# Closed-loop driver for the picobike showcase gif: holds throttle (B), climbs the gears (taps A once
# past each upshift gate) for real racing speed, and steers toward road centre (st.lateral -> 0) to
# counter the bend's centrifugal pull, so the bike follows the winding pseudo-3D road. gen_gif.py --control.
def control(g, fr, pad, cs):
    st = g["st"]; GATE = g["GEAR_GATE"]
    keys = ["B"]                                   # throttle always
    if cs.get("acd", 0) > 0: cs["acd"] -= 1
    if st.gear < 4 and st.speed > GATE[st.gear] + 1.0 and cs.get("acd", 0) == 0:
        keys.append("A"); cs["acd"] = 7            # pulse A -> shift up a gear (just_pressed edge)
    if st.lateral > 12: keys.append("LEFT")        # steer back toward road centre
    elif st.lateral < -12: keys.append("RIGHT")
    pad.set(",".join(keys))
