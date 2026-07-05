# Picatro - "The Pico Circus": a Balatro-like poker deckbuilder (real drawn cards + a scoring-tally juice pass).
# Play a poker hand -> CHIPS x MULT; Acts (jokers) warp scoring (order matters!); the DISCARD is a weapon
# (discarding banks its suit's effect onto the next played hand). Beat the blind in 3 hands / 3 discards.
# Cards = 8x StripDraw (0 RAM) with red/black pips + lift + cursor; PLAY runs a chips->mult->SLAM tally.
# Controls: D-pad L/R cursor | UP select (max 5) / DOWN deselect | A PLAY | B DISCARD | A continue (result).
# 2-button-board friendly: uses only D-pad + A + B (no X/Y).
# Run:  cd repos/picogame-final && python3 sim/run.py games/picogame_picatro.py --backend pygame

import gc
import random
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp
import picogame_ui as ui
import terminalio
import board
import picatro_art as art        # PAL8 Act icons from PixelLab (Pico Circus)

def C(r, g, b):
    return pg.rgb565(r, g, b)

CREAM = C(232, 220, 188)         # letterpress paper
INK = C(40, 32, 24)
TEAL = C(20, 120, 120)           # CHIPS ink
VERM = C(200, 60, 50)           # MULT ink
SELC = C(30, 120, 60)            # selected marker
CARDFACE = C(250, 247, 238)      # card face (crisp on the cream table)
REDSUIT = C(198, 56, 46)         # hearts + diamonds
HILITE = C(228, 176, 60)         # cursor highlight (warm brass = the big top)
# real card row (8x StripDraw, 0 RAM): rest low, LIFT up when selected (the Ants "cards not text" trick)
CARD_W, CARD_H, CARD_GAP, CARD_X0 = 32, 44, 35, 6   # gap 39->35 so up to 9 cards fit (still 32px each)
CARD_STRIP_Y, CARD_STRIP_H = 156, 58
BASE_HAND, MAX_HAND = 8, 9   # hand is normally 8; a spade discard digs to 9 for one action, then settles to 8
CARRY_HAND = True            # cards left in hand carry into the next blind (spend-vs-save across the run)

RANKS = "23456789TJQKA"          # index 0..12 (internal; 'T' = Ten)
RANK_DISP = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")   # shown on the card face
SUITS = "SHDC"                   # 0 spade, 1 heart, 2 diamond, 3 club
RANK_CHIPS = (2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11)
HAND_NAME = ("High Card", "Pair", "Two Pair", "Three-Kind", "Straight",
             "Flush", "Full House", "Four-Kind", "Straight Flush")
HAND_BASE = ((5, 1), (10, 2), (20, 2), (30, 2), (30, 4), (35, 3), (35, 4), (55, 6), (75, 8))
# The 3 fixed passive Acts (jokers), always on. Ringmaster rewards suit VARIETY (the anti-Flush lever).
ACTS = ("Grinder(+3c/card)", "Steady(+3 mult)", "Ringmaster(+1 mult/extra suit)")

DEBUG = True                     # console status dump for mechanics tuning (set False to silence)


WILD_RANK = 13                   # the Understudy: rank sentinel (one past Ace). Suit is a REAL fixed suit 0..3.
def is_wild(c):
    return c[0] == WILD_RANK

def _card(c):                    # (rank, suit) -> "10H" / "AS" for the debug console (SHDC = spade/heart/diamond/club)
    return ("?" + SUITS[c[1]]) if is_wild(c) else (RANK_DISP[c[0]] + SUITS[c[1]])

scene, _, _ = picogame_game.setup(strip_h=12, background=CREAM)
clock = picogame_clock.Clock(30)
btn = picogame_input.Buttons()

# --- HUD + screen labels (text-mode cards; fixed-width terminalio for alignment) ---
L = terminalio.FONT
top_lbl = ui.SceneLabel(scene, pg, L, 4, 3, INK, CREAM)
# the 3 active Acts shown as PixelLab icons (the bill), with their text below
ACT_ICONS = (art.knife(pg), art.strongman(pg), art.ringmaster(pg))   # Grinder / Steady / Ringmaster
act_sprites = []
for i, bm in enumerate(ACT_ICONS):
    s = pg.Sprite(bm, 8 + i * 26, 18)   # the 3 Act icons (jokers), a compact bill at the top-left
    scene.add(s)
    act_sprites.append(s)               # kept so the scoring tally can flash the Act that is firing
acts_lbl = ui.SceneLabel(scene, pg, L, 92, 20, INK, CREAM)     # what each Act does, beside the icons
result_lbl = ui.SceneLabel(scene, pg, L, 4, 64, TEAL, CREAM)
banked_lbl = ui.SceneLabel(scene, pg, L, 4, 88, TEAL, CREAM)     # chips-breakdown line on the score screen
mult_lbl = ui.SceneLabel(scene, pg, L, 4, 108, VERM, CREAM)      # mult-breakdown line on the score screen
help_lbl = ui.SceneLabel(scene, pg, L, 4, 226, INK, CREAM)

parts = pg.Particles(64, size=2, gravity=0.05, fade=True)    # slam pop + win/finale confetti fountains
scene.add(parts)

# one-time how-to card at run start (0-RAM SceneBox; dismiss with A) - teaches PLAY vs DISCARD, not a wall
howto = ui.SceneBox(scene, pg, L, 14, 38, 292, 118, INK, C(244, 236, 210), nlines=8, border=INK)

# big WIN / BUSTED banner: ONE reusable sprite of scaled text. Text is re-rendered into a shared buffer
# (via Canvas, in place) then revealed - no per-event Sprite churn, and Scene has no remove().
W, H = board.DISPLAY.width, board.DISPLAY.height
_BFW, _BFH = L.get_bounding_box()[:2]
_BANNER_CH = 10                                         # widest word (8: "CLEARED!") + 1 char padding each side
_BANNER_W = _BFW * _BANNER_CH
_banner_buf = bytearray(_BANNER_W * _BFH * 2)           # RGB565
_banner_bm = pg.Bitmap(_banner_buf, _BANNER_W, _BFH, format=pg.RGB565, frames=1, stride=_BANNER_W)
_banner_cv = pg.Canvas(_BANNER_W, _BFH, buffer=_banner_buf)
banner = pg.Sprite(_banner_bm, W // 2, 104)
banner.anchor = (0.5, 0.5)
banner.scale = 4                                        # terminalio 8px -> 32px tall: unmissable
banner.visible = False
scene.add(banner)

def show_banner(text, fg, bg):                          # centered text in the shared buffer, then reveal
    _banner_cv.clear(bg)
    _banner_cv.text((_BANNER_W - _BFW * len(text)) // 2, 0, text, fg, L)
    banner.visible = True
    banner.touch()

def clear_banner():
    banner.visible = False

# End-of-run message, GRADED by blinds cleared (0..4). Picatro is hard on purpose, so 3 cleared is a
# genuine success, not a failure - the banner even goes red -> amber -> green. Keep each word <= 8 chars.
BUST_MSG = (
    ("WARM-UP!", "The crowd's still filing in. Encore!"),   # 0 cleared
    ("NOT BAD!", "One blind down - the tent noticed you."),  # 1
    ("GOOD RUN", "Two blinds! The Ringmaster tips his hat."),# 2
    ("BRAVO!",   "Three blinds - a true circus act!"),       # 3
    ("SO CLOSE", "Four down, one to go - what a show!"),     # 4
)

def bust_look(cleared):
    word, flavor = BUST_MSG[cleared if cleared < len(BUST_MSG) else len(BUST_MSG) - 1]
    if cleared >= 3:                     # a real success -> green
        bg, fg = SELC, CREAM
    elif cleared == 2:                   # getting there -> amber
        bg, fg = HILITE, INK
    else:                                # short run -> warm red, but the words stay kind
        bg, fg = VERM, CREAM
    return word, fg, bg, flavor

# --- state ---
SELECT, RESULT, OVER, WIN, SCORING, HOWTO, FINAL = 0, 1, 2, 3, 4, 5, 6
LAST_BLIND = 5                          # 5 targets in new_blind(); clearing blind #5 = the run is won


class State:
    def __init__(self):
        self.deck = []          # draw pile of (rank, suit)
        self.hand = []          # current hand, list of (rank, suit)
        self.sel = []           # bool per hand slot
        self.cur = 0
        self.state = SELECT     # state-machine phase
        self.blind = self.target = self.total = self.hands = self.discards = 0
        self.bank_c = self.bank_m = 0
        self.bank_xc = 0        # banked clubs count -> next hand's mult x(1 + 0.5*bank_xc)
        self.msg = ""
        # scoring-slam animation (the Balatro tally: hand-name -> count chips -> count mult -> SLAM)
        self.sc_type = self.sc_chips = self.sc_mult = self.sc_val = self.sc_t = self.sc_ring = self.sc_grind = self.sc_rankc = 0
        self.sc_scored = []     # scored cards of the last play (debug: shows kicker exclusion)
        self.sc_xcf = 1.0       # banked-clubs multiplier factor of the last play
        self.sc_bankc = self.sc_bankm = self.sc_bankxc = 0   # banks used by the last play (for the breakdown)
        self.sc_idxs = []
        self.bust_flavor = ""   # graded, upbeat end-of-run quip (set when the run ends short)
        self.wild_suit = 0      # the Understudy's fixed printed suit (0..3), chosen once per run
        self.wild_live = True   # is the ONE Understudy still in play (deck/hand)? False once played/discarded


st = State()


def dbg_status(tag):                  # one-line snapshot of the whole game state, for mechanics tuning
    if not DEBUG:
        return
    xm = 1.0 + 0.5 * st.bank_xc
    print("[%s] blind %d  %d/%d  hands %d disc %d | hand: %s | banked +%dc +%dm x%.1f" % (
        tag, st.blind, st.total, st.target, st.hands, st.discards,
        " ".join(_card(c) for c in st.hand), st.bank_c, st.bank_m, xm))


def shuffle(lst):                    # CircuitPython's random has no shuffle() - Fisher-Yates via randint
    for i in range(len(lst) - 1, 0, -1):
        j = random.randint(0, i)
        lst[i], lst[j] = lst[j], lst[i]


def fresh_deck():
    d = [(r, s) for r in range(13) for s in range(4)]
    if st.wild_live:                                  # the ONE Understudy, if not yet spent this run
        d.append((WILD_RANK, st.wild_suit))          # carry_deal() drops it again if it's held in hand
    shuffle(d)
    return d


def deal():
    st.deck = fresh_deck()
    st.hand = [st.deck.pop() for _ in range(BASE_HAND)]
    st.sel = [False] * BASE_HAND
    st.cur = 0
    st.bank_c = st.bank_m = 0
    st.bank_xc = 0


def carry_deal():
    # carry-hand: KEEP the current hand into the new blind. Reshuffle a fresh deck minus the held
    # cards, reset banks, and top up ONLY if below 8 -- carried cards crowd out fresh draws. That
    # crowding-out is the self-balancing cost that makes hoarding a real bet, not free value.
    held = st.hand
    st.deck = [c for c in fresh_deck() if c not in held]
    while len(st.hand) < BASE_HAND and st.deck:
        st.hand.append(st.deck.pop())
    st.sel = [False] * len(st.hand)
    st.cur = min(st.cur, len(st.hand) - 1)
    st.bank_c = st.bank_m = 0
    st.bank_xc = 0


def new_blind(reset_run):
    if reset_run:
        st.blind = 1
        st.wild_suit = random.randint(0, 3)   # fresh run: a new Understudy, one printed suit, back in play
        st.wild_live = True
    else:
        st.blind += 1
    st.target = (500, 1300, 2100, 2900, 3700)[min(st.blind - 1, 4)]
    st.total = 0
    st.hands, st.discards = 3, 3
    if reset_run or not CARRY_HAND:
        deal()                       # fresh run (or carry disabled): a brand-new hand
    else:
        carry_deal()                 # advancing after a clear: keep the hand (spend-vs-save arc)
    st.state = SELECT
    dbg_status("NEW BLIND")


def selected_cards():
    return [st.hand[i] for i in range(len(st.hand)) if st.sel[i]]


def classify(cards):
    n = len(cards)
    rc = [0] * 13
    sc = [0] * 4
    for r, s in cards:
        rc[r] += 1
        sc[s] += 1
    counts = sorted((c for c in rc if c), reverse=True)
    distinct = sorted(set(r for r, s in cards))
    flush = n == 5 and max(sc) == 5
    straight = False
    if n == 5 and len(distinct) == 5:
        if distinct[4] - distinct[0] == 4:
            straight = True
        elif distinct == [0, 1, 2, 3, 12]:   # A-2-3-4-5 wheel
            straight = True
    if straight and flush:
        t = 8
    elif counts[0] == 4:
        t = 7
    elif counts[0] == 3 and len(counts) > 1 and counts[1] == 2:
        t = 6
    elif flush:
        t = 5
    elif straight:
        t = 4
    elif counts[0] == 3:
        t = 3
    elif counts[0] == 2 and len(counts) > 1 and counts[1] == 2:
        t = 2
    elif counts[0] == 2:
        t = 1
    else:
        t = 0
    # scored cards
    if t >= 4:
        scored = list(cards)
    elif t == 7:
        scored = [c for c in cards if rc[c[0]] == 4]
    elif t == 3:
        scored = [c for c in cards if rc[c[0]] == 3]
    elif t in (1, 2):
        scored = [c for c in cards if rc[c[0]] == 2]
    else:
        scored = [max(cards)]
    return t, scored


def _eval(cards):
    # Pure score of a CONCRETE 5-card list (no Understudy), no side effects. Returns everything the
    # tally/breakdown needs so score_play() and the wild search share ONE scoring formula (no drift).
    t, scored = classify(cards)
    base_c, base_m = HAND_BASE[t]
    rankc = sum(RANK_CHIPS[r] for r, s in scored)
    grind = 3 * len(scored)
    ring = len(set(s for r, s in cards)) - 1
    chips = base_c + rankc + st.bank_c + grind
    xcf = 1.0 + 0.5 * st.bank_xc
    mult = base_m + st.bank_m + 3 + ring
    if st.bank_xc:
        mult = int(mult * xcf)
    return t, scored, rankc, grind, ring, xcf, chips, mult, chips * mult


def resolve_selection(cards):
    # The Understudy is rank-only with a FIXED suit: at PLAY, pick the rank that maximizes score for THIS
    # selection, but never a Straight Flush (capped at Four-Kind). Scoped to the <=5 picked cards (studio
    # spec) -> at most 13 evals, one-shot. Returns a concrete list (no wild) for scoring.
    wi = [k for k in range(len(cards)) if is_wild(cards[k])]
    if not wi:
        return cards
    i = wi[0]
    ws = cards[i][1]
    others = [cards[k] for k in range(len(cards)) if k != i]
    oset = set(others)
    best = None
    best_key = (-1, -1)          # (score, hand-type) -> higher score, then higher type on ties
    for r in range(13):
        cand = (r, ws)
        if cand in oset:         # can't become a card already in the same play
            continue
        res = _eval(others + [cand])
        if res[0] == 8:          # Understudy never forms a Straight Flush
            continue
        key = (res[8], res[0])
        if key > best_key:
            best_key = key
            best = cand
    if best is None:             # degenerate (everything excluded) -> a harmless Ace of the printed suit
        best = (12, ws)
    out = list(cards)
    out[i] = best
    return out


def score_play(cards):
    cards = resolve_selection(cards)                     # concretize the Understudy first (rank-only)
    t, scored, rankc, grind, ring, xcf, chips, mult, val = _eval(cards)
    # store the full breakdown so the debug console (and tally) can show WHERE the score came from
    st.sc_scored = scored
    st.sc_rankc = rankc                                  # chips from the scored cards' ranks
    st.sc_grind = grind                                  # Grinder: +3 chips per scored card
    st.sc_ring = ring                                    # Ringmaster: +1 mult per suit beyond the first
    st.sc_bankc, st.sc_bankm, st.sc_bankxc = st.bank_c, st.bank_m, st.bank_xc   # store for the breakdown
    st.sc_xcf = xcf                                      # banked clubs: x(1+0.5n), non-compounding
    return t, chips, mult, val


def banked_label():                      # HUD string for what a discard has banked onto the next hand
    xm = ("  x%.1f" % (1.0 + 0.5 * st.bank_xc)) if st.bank_xc else ""
    return "banked: +%dc +%dm%s -> next hand" % (st.bank_c, st.bank_m, xm)


def draw_back(k):
    for _ in range(k):
        if st.deck:
            st.hand.append(st.deck.pop())


def draw_pip(v, suit, cx, cy, col):      # procedural suit symbol (0 RAM, real ♠♥♦♣ - no art needed)
    if suit == 2:                        # diamond - a clean tall rhombus
        v.fill_triangle(cx, cy - 7, cx - 5, cy, cx + 5, cy, col)
        v.fill_triangle(cx, cy + 7, cx - 5, cy, cx + 5, cy, col)
    elif suit == 1:                      # heart - two round lobes over a point
        v.fill_circle(cx - 3, cy - 2, 3, col)
        v.fill_circle(cx + 3, cy - 2, 3, col)
        v.fill_rect(cx - 5, cy - 2, 11, 2, col)          # bridge the lobes (no dip)
        v.fill_triangle(cx - 6, cy - 1, cx + 6, cy - 1, cx, cy + 7, col)
    elif suit == 0:                      # spade - blade point-up over a flared stem
        v.fill_triangle(cx, cy - 7, cx - 6, cy + 2, cx + 6, cy + 2, col)
        v.fill_circle(cx - 3, cy + 1, 3, col)
        v.fill_circle(cx + 3, cy + 1, 3, col)
        v.fill_triangle(cx - 4, cy + 7, cx + 4, cy + 7, cx, cy + 1, col)   # stem flare
    else:                                # club - three lobes over a flared stem
        v.fill_circle(cx, cy - 4, 3, col)
        v.fill_circle(cx - 4, cy + 1, 3, col)
        v.fill_circle(cx + 4, cy + 1, 3, col)
        v.fill_triangle(cx - 4, cy + 7, cx + 4, cy + 7, cx, cy + 1, col)   # stem flare


class Card:                              # one hand slot, drawn straight into the strip (no retained buffer)
    def __init__(self, i):
        self.i = i
        self.x = CARD_X0 + i * CARD_GAP
        self.y = CARD_STRIP_Y
        self.sd = pg.StripDraw(self.draw, self.x, self.y, CARD_W, CARD_STRIP_H, always_dirty=False)
        scene.add(self.sd)

    def draw(self, v, vx, vy, vw, vh):
        # the view spans the whole dirty region; (vx,vy) is its origin -> draw at ABSOLUTE coords minus it
        ox = self.x - vx
        oy = self.y - vy
        v.fill_rect(ox, oy, CARD_W, CARD_STRIP_H, CREAM)  # erase only OUR rect (covers rest + lift zone)
        i = self.i
        if i >= len(st.hand):
            return                                        # empty slot
        r, s = st.hand[i]
        wild = is_wild((r, s))
        cy = oy + (2 if (i < len(st.sel) and st.sel[i]) else 12)   # selected cards LIFT up
        col = REDSUIT if s in (1, 2) else INK
        if i == st.cur:                                   # cursor = warm brass frame behind the face
            v.fill_round_rect(ox, cy - 2, CARD_W, CARD_H + 4, 5, HILITE)
        if wild:                                          # the Understudy: gold keyline = a rare card
            v.fill_round_rect(ox + 1, cy - 1, CARD_W - 2, CARD_H + 2, 5, HILITE)
        v.fill_round_rect(ox + 2, cy, CARD_W - 4, CARD_H, 4, CARDFACE)
        v.text(ox + 5, cy + 3, "?" if wild else RANK_DISP[r], col, L)   # '?' rank = any rank; real suit stays
        draw_pip(v, s, ox + CARD_W // 2, cy + 30, col)    # suit pip, centre-lower (real, even for the wild)


card_slots = [Card(i) for i in range(MAX_HAND)]   # NB: NOT 'cards' - play/discard bind a local 'cards'; slot 8 is used only when a spade dig grows the hand to 9


def invalidate_cards():
    for c in card_slots:
        c.sd.invalidate()


# ---------------- audio (guarded: synthio device-only; sim silent -> no-ops) ----------------
_frame = 0
_seq = []                                 # pending arpeggio notes [play_frame, note], drained each frame
try:
    import synthio                         # noqa
    import picogame_synth as snd

    _synth = snd.Synth(sfx_level=0.7)
    SQ, TR = snd.SQUARE, snd.TRIANGLE

    def _n(m, w, dec=0.04, amp=0.5, att=0.003, bend=None):
        return snd.note(m, w, attack=att, decay=dec, amplitude=amp,
                        bend=snd.pitch_bend(bend[0], bend[1]) if bend else None)

    SND_NAV = _n(78, SQ, 0.015, 0.28)
    SND_PICK = _n(81, SQ, 0.02, 0.4, bend=(3, 25))
    SND_CLEAR = _n(74, SQ, 0.03, 0.4, bend=(-3, 40))
    SEQ_PLAY = (_n(60, SQ, 0.02, 0.45), _n(67, SQ, 0.04, 0.5))
    SEQ_CHIPS = tuple(_n(72 + k, SQ, 0.018, 0.4) for k in range(6))       # rising chip ticker
    SEQ_MULT = tuple(_n(76 + k * 2, TR, 0.02, 0.45) for k in range(5))    # mult ticker (diff timbre)
    SEQ_SLAM = (_n(48, TR, 0.04, 0.6, bend=(-4, 45)), _n(84, SQ, 0.05, 0.55), _n(91, SQ, 0.14, 0.6, bend=(4, 110)))
    SEQ_DISCARD = (_n(66, TR, 0.05, 0.4, bend=(-5, 90)), _n(58, TR, 0.09, 0.4, bend=(-4, 110)))
    SEQ_WIN = (_n(67, TR, 0.05, 0.6), _n(72, TR, 0.05, 0.6), _n(76, TR, 0.05, 0.6), _n(79, TR, 0.14, 0.65))
    SEQ_BUST = (_n(55, SQ, 0.06, 0.6), _n(48, SQ, 0.06, 0.6), _n(40, SQ, 0.22, 0.6, bend=(-4, 240)))

    def sfx(n):
        if n is not None:
            _synth.sfx(n)

    def sfx_seq(notes):
        for i, nn in enumerate(notes):
            _seq.append([_frame + i, nn])
except Exception:
    SND_NAV = SND_PICK = SND_CLEAR = None
    SEQ_PLAY = SEQ_CHIPS = SEQ_MULT = SEQ_SLAM = SEQ_DISCARD = SEQ_WIN = SEQ_BUST = ()

    def sfx(n):
        pass

    def sfx_seq(notes):
        pass


new_blind(True)
st.state = HOWTO                          # open on the how-to card (dismiss with A)
howto.show([
    "PICATRO  -  THE PICO CIRCUS",
    "Beat each TARGET in 3 hands + 3 discards.",
    "UP pick (max 5)   A PLAY = CHIPS x MULT",
    "B DISCARD picked = bank a suit bonus",
    "  onto your NEXT hand (the twist!)",
    "3 Acts (top-left) auto-boost every hand",
    "gold '?' card = the Understudy: any rank",
    "press A to begin",
])
print("Picatro prototype. L/R move, UP/DN pick, A PLAY, B DISCARD.")
while True:
    btn.poll()
    _frame += 1
    _i = 0                                    # drain scheduled arpeggio notes due this frame
    while _i < len(_seq):
        if _seq[_i][0] <= _frame:
            sfx(_seq[_i][1])
            _seq.pop(_i)
        else:
            _i += 1

    if st.state == HOWTO:
        top_lbl.set("")
        help_lbl.set("")
        if btn.just_pressed(btn.A):           # dismiss the how-to card, begin play
            howto.hide()
            st.state = SELECT
            invalidate_cards()

    elif st.state == SELECT:
        if btn.just_pressed(btn.RIGHT):
            st.cur = (st.cur + 1) % len(st.hand)
            invalidate_cards()
            sfx(SND_NAV)
        if btn.just_pressed(btn.LEFT):
            st.cur = (st.cur - 1) % len(st.hand)
            invalidate_cards()
            sfx(SND_NAV)
        if btn.just_pressed(btn.UP):              # UP = pick the card under the cursor (it lifts up)
            if not st.sel[st.cur] and sum(st.sel) < 5:
                st.sel[st.cur] = True
                invalidate_cards()
                sfx(SND_PICK)
        if btn.just_pressed(btn.DOWN):            # DOWN = drop it back (deselect)
            if st.sel[st.cur]:
                st.sel[st.cur] = False
                invalidate_cards()
                sfx(SND_CLEAR)
        # PLAY -> run the scoring tally (score is added at the SLAM, cards stay lifted until then)
        if btn.just_pressed(btn.A) and any(st.sel) and st.hands > 0:
            cards = selected_cards()
            if any(is_wild(c) for c in cards):       # the Understudy is one-shot: playing it spends it
                st.wild_live = False
            t, chips, mult, sc = score_play(cards)   # also stores st.sc_grind / st.sc_ring for the tally
            if DEBUG:
                bc, bm = HAND_BASE[t]
                add_m = bm + st.bank_m + 3 + st.sc_ring
                print("PLAY  %s" % " ".join(_card(c) for c in cards))
                print("  %s   scored: %s" % (HAND_NAME[t], " ".join(_card(c) for c in st.sc_scored)))
                print("  chips  %d base  +%d cards  +%d Grinder  +%d bank  = %d" % (
                    bc, st.sc_rankc, st.sc_grind, st.bank_c, chips))
                print("  mult   %d base  +%d bank  +3 Steady  +%d Ring (%d suits)  = %d" % (
                    bm, st.bank_m, st.sc_ring, st.sc_ring + 1, add_m))
                if st.bank_xc:
                    print("  club   x%.1f  ->  mult %d" % (st.sc_xcf, mult))
                print("  SCORE  %d x %d = %d    total %d -> %d / %d" % (
                    chips, mult, sc, st.total, st.total + sc, st.target))
            st.bank_c = st.bank_m = st.bank_xc = 0    # banked bonuses consumed by this hand
            st.hands -= 1
            st.sc_type, st.sc_chips, st.sc_mult, st.sc_val = t, chips, mult, sc
            st.sc_idxs = [i for i in range(len(st.hand)) if st.sel[i]]
            st.sc_t = 0
            st.state = SCORING
            sfx_seq(SEQ_PLAY)
        # DISCARD = weapon
        if btn.just_pressed(btn.B) and any(st.sel) and st.discards > 0:
            cards = selected_cards()
            clubs = 0
            has_spade = False
            dbg_lines = []
            for r, s in cards:
                if is_wild((r, s)):       # tossing the Understudy banks its PRINTED suit, then it's gone
                    st.wild_live = False
                if s == 1:
                    st.bank_c += 4        # heart  -> +chips
                    dbg_lines.append("+4c    (%s)" % _card((r, s)))
                elif s == 2:
                    st.bank_m += 1        # diamond -> +mult
                    dbg_lines.append("+1m    (%s)" % _card((r, s)))
                elif s == 3:
                    clubs += 1            # club -> xmult (count accumulates; applied non-compounding)
                    dbg_lines.append("+0.5x  (%s)" % _card((r, s)))
                else:                     # spade -> ONE bonus draw (flat, capped - doesn't scale with count)
                    dbg_lines.append(("+1 draw (%s)" if not has_spade else "no extra draw, capped (%s)") % _card((r, s)))
                    has_spade = True
            st.bank_xc += clubs
            st.discards -= 1
            idxs = [i for i in range(len(st.hand)) if st.sel[i]]
            for i in reversed(idxs):
                st.hand.pop(i)
            # settle to base 8, +1 for a spade "dig" this discard (never accumulates -> hand is only ever 8 or 9)
            target = BASE_HAND + (1 if has_spade else 0)
            draw_back(target - len(st.hand))
            grew = len(st.hand) > BASE_HAND                 # got the dig card (ended at 9)
            st.sel = [False] * len(st.hand)
            st.cur = min(st.cur, len(st.hand) - 1)
            invalidate_cards()
            sfx_seq(SEQ_DISCARD)
            if grew:
                sfx(SND_PICK)                               # small chirp: drew an extra card to pick from
            xm = ("  x%.1f" % (1.0 + 0.5 * st.bank_xc)) if st.bank_xc else ""
            st.msg = "banked +%dc +%dm%s%s -> next hand" % (
                st.bank_c, st.bank_m, xm, "  +1 card" if grew else "")
            st.state = SELECT              # discard doesn't score -> straight back to the hand
            invalidate_cards()             # (banked bonus shows above the cards; no A-confirm needed)
            if DEBUG:
                print("DISCARD  %s" % " ".join(_card(c) for c in cards))
                for _l in dbg_lines:
                    print("    %s" % _l)
                print("  => banked +%dc +%dm x%.1f   %s   (disc left %d)" % (
                    st.bank_c, st.bank_m, 1.0 + 0.5 * st.bank_xc,
                    "hand->9 (+1 card)" if grew else "hand->8", st.discards))
            dbg_status("after DISCARD")

        top_lbl.set("BLIND %d   %d / %d   hands %d  disc %d" % (st.blind, st.total, st.target, st.hands, st.discards))
        acts_lbl.set("Grind+3c Steady+3m Ring+1/suit")  # what each Act (icon at left) does
        result_lbl.set(st.msg)
        banked_lbl.set(banked_label() if (st.bank_c or st.bank_m or st.bank_xc)
                       else "UP/DN pick up to 5  -  A play them  -  B discard = banks a bonus")
        help_lbl.set("L/R move  UP/DN pick  A PLAY  B DISCARD")

    elif st.state == SCORING:                 # the tally: name -> chips count-up -> mult count-up -> SLAM
        st.sc_t += 1
        P1, P2, P3 = 10, 26, 42               # phase ends (frames)
        if st.sc_t < P3 and (btn.just_pressed(btn.A) or btn.just_pressed(btn.B)):
            st.sc_t = P3                       # any press skips straight to the slam
        name = HAND_NAME[st.sc_type]
        blink = HILITE if (st.sc_t // 3) & 1 else 0       # flash the Act(s) that are firing right now
        for s in act_sprites:
            s.flash = 0
        if P1 <= st.sc_t < P2:                            # chips phase -> Grinder (+3c per card)
            act_sprites[0].flash = blink
        elif P2 <= st.sc_t < P3:                          # mult phase -> Steady (+ Ringmaster if multi-suit)
            act_sprites[1].flash = blink
            if st.sc_ring > 0:
                act_sprites[2].flash = blink
        top_lbl.set("BLIND %d   %d / %d   hands %d  disc %d" % (st.blind, st.total, st.target, st.hands, st.discards))
        help_lbl.set("")
        if st.sc_t < P1:
            result_lbl.set(name)
            banked_lbl.set(""); mult_lbl.set("")
        elif st.sc_t < P2:                     # count the chips up
            if st.sc_t == P1:
                sfx_seq(SEQ_CHIPS)             # rising chip ticker
            shown = int(st.sc_chips * (st.sc_t - P1) / (P2 - P1))
            result_lbl.set("%s    %d" % (name, shown))
            banked_lbl.set("counting chips..."); mult_lbl.set("")
        elif st.sc_t < P3:                     # chips done, count the mult up
            if st.sc_t == P2:
                sfx_seq(SEQ_MULT)             # mult ticker
            shownm = 1 + int((st.sc_mult - 1) * (st.sc_t - P2) / (P3 - P2))
            result_lbl.set("%s    %d  x %d" % (name, st.sc_chips, shownm))
            banked_lbl.set(""); mult_lbl.set("")
        elif st.sc_t == P3:                    # SLAM: bank the score, coin-burst (no invert flash)
            st.total += st.sc_val
            if DEBUG:
                print("SLAM  +%d -> total %d / %d  (%s)" % (
                    st.sc_val, st.total, st.target,
                    "CLEARED" if st.total >= st.target else ("BUST" if st.hands == 0 else "continue")))
            sfx_seq(SEQ_SLAM)
            parts.emit(160, 118, 12 + st.sc_type * 2, 4, 26, HILITE)  # coin pop (bigger for rarer hands)
            for i in reversed(st.sc_idxs):     # NOW retire the played cards + redraw the hand
                st.hand.pop(i)
            draw_back(max(0, BASE_HAND - len(st.hand)))   # settle back to base 8 (never leaves a 9-residual)
            st.sel = [False] * len(st.hand)
            st.cur = min(st.cur, len(st.hand) - 1)
            invalidate_cards()
            dbg_status("after PLAY")
        else:                                  # HOLD: full point breakdown, ALWAYS wait for A
            bc, bm = HAND_BASE[st.sc_type]
            result_lbl.set("%s   %d x %d = %d" % (name, st.sc_chips, st.sc_mult, st.sc_val))
            banked_lbl.set("chips %d+%d+%dG%s = %d" % (bc, st.sc_rankc, st.sc_grind,
                           ("+%dk" % st.sc_bankc if st.sc_bankc else ""), st.sc_chips))
            mult_lbl.set("mult %d+3S%s%s%s = %d" % (bm,
                         ("+%dR" % st.sc_ring if st.sc_ring else ""),
                         ("+%dk" % st.sc_bankm if st.sc_bankm else ""),
                         (" x%.1f" % st.sc_xcf if st.sc_bankxc else ""), st.sc_mult))
            help_lbl.set("A: continue")
            if btn.just_pressed(btn.A):
                summary = "%s  %d x %d = %d" % (name, st.sc_chips, st.sc_mult, st.sc_val)
                banked_lbl.set(""); mult_lbl.set("")          # clear breakdown before leaving the screen
                if st.total >= st.target:
                    st.msg = summary               # keep the tally on the WIN / FINAL screen
                    if st.blind >= LAST_BLIND:      # end-of-GAME: a huge triple-colour burst
                        st.state = FINAL
                        show_banner("YOU WIN!", INK, HILITE)
                        parts.emit(70, 110, 20, 7, 55, HILITE)
                        parts.emit(160, 110, 20, 7, 55, VERM)
                        parts.emit(250, 110, 20, 7, 55, TEAL)
                    else:                          # end-of-BLIND: a two-colour double burst
                        st.state = WIN
                        show_banner("CLEARED!", CREAM, SELC)
                        parts.emit(90, 108, 22, 6, 48, HILITE)
                        parts.emit(230, 108, 22, 6, 48, VERM)
                    sfx_seq(SEQ_WIN)
                elif st.hands == 0:
                    st.msg = summary               # ...and on the end-of-run screen
                    st.state = OVER
                    _w, _fg, _bg, st.bust_flavor = bust_look(st.blind - 1)   # graded by blinds cleared
                    show_banner(_w, _fg, _bg)
                    sfx_seq(SEQ_BUST)
                else:
                    st.state = SELECT

    elif st.state == RESULT:
        result_lbl.set(st.msg)
        help_lbl.set("A: continue")
        top_lbl.set("BLIND %d   %d / %d   hands %d  disc %d" % (st.blind, st.total, st.target, st.hands, st.discards))
        banked_lbl.set(banked_label() if (st.bank_c or st.bank_m or st.bank_xc) else "")
        if btn.just_pressed(btn.A):
            st.state = SELECT
            invalidate_cards()

    elif st.state == WIN:
        top_lbl.set("BLIND %d CLEARED!  %d / %d" % (st.blind, st.total, st.target))
        result_lbl.set(st.msg)
        help_lbl.set("A: next blind  (your cards carry over)")
        if _frame % 4 == 0:                        # gentle confetti keeps raining while the banner holds
            parts.emit(random.randint(16, 300), 6, 2, 2, 52, HILITE if (_frame // 4) & 1 else VERM)
        if btn.just_pressed(btn.A):
            clear_banner()
            new_blind(False)
            invalidate_cards()

    elif st.state == OVER:
        cleared = st.blind - 1
        top_lbl.set("You cleared %d of %d blinds!" % (cleared, LAST_BLIND))
        result_lbl.set(st.bust_flavor)                 # graded, upbeat circus quip
        banked_lbl.set(""); mult_lbl.set("")           # clear the scoring breakdown lines
        help_lbl.set("A: new run")
        if btn.just_pressed(btn.A):
            clear_banner()
            new_blind(True)
            invalidate_cards()

    else:  # FINAL - all LAST_BLIND blinds cleared, the whole run is won
        top_lbl.set("YOU BEAT THE PICO CIRCUS!")
        result_lbl.set(st.msg)                          # the winning hand's tally
        banked_lbl.set("all %d blinds cleared - take a bow!" % LAST_BLIND)
        help_lbl.set("A: new run")
        if _frame % 2 == 0:                             # nonstop dense multi-colour celebration fountain
            parts.emit(random.randint(12, 306), 4, 3, 2, 58, (HILITE, VERM, TEAL)[(_frame // 2) % 3])
        if btn.just_pressed(btn.A):
            clear_banner()
            for s in act_sprites:
                s.flash = 0
            new_blind(True)
            invalidate_cards()

    parts.tick()
    scene.refresh()
    clock.tick()
