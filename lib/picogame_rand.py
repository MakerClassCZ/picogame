# picogame_rand - a tiny SEEDABLE random number generator + helpers.
# Why not the `random` module? A seedable, deterministic RNG gives reproducible runs (replays,
# ghosts) and daily-challenge style seeds, independent streams (one per world system), and the
# helpers (weighted picks, shuffle bag) are the ones small games actually need. No float unless
# you ask for it.
#
# The core is a combined 30-bit Lehmer generator (two prime-modulus MLCGs, Schrage's method,
# difference of the two states; period ~2^58). Every intermediate stays below 2^30, i.e. inside
# a MicroPython SMALL INT on 32-bit boards - the previous xorshift32 overflowed it on every call
# (~5 heap big-int allocs, ~250 us + GC churn per number on RP2040; measured 5 ms/frame in a game
# rolling it per enemy per frame). Now a call is a handful of small-int ops, alloc-free.
# NOTE 2026-08-17: the seed -> sequence mapping CHANGED with this rewrite (deliberately: nothing
# shipped depends on the old sequences).
#
#   rng = Rand(1234)            # fixed seed -> reproducible
#   rng = Rand()               # time-seeded
#   rng.below(6)               # 0..5
#   rng.randint(1, 6)          # 1..6 inclusive
#   rng.chance(0.25)           # True ~25% of the time
#   rng.choice(items)          # one item
#   rng.shuffle(my_list)       # in place
#   rng.weighted([5, 3, 1])    # index 0/1/2 by weight (fair, no streak control)
#   bag = Bag([0,1,2,3,4,5,6], rng); bag.next()   # 7-bag: every value once per cycle (anti-streak)


def _default_seed():
    try:
        import time
        return (time.monotonic_ns() & 0xFFFFFFFF) or 0x1234
    except Exception:
        return 0x1234


# Two prime moduli just under 2^30 with primitive-root multipliers < 2^15 (Schrage-safe: both
# a*(x%q) and r*(x//q) stay < 2^30, and r < q). Chosen by a 2-D lattice + chi-square sweep.
_M1 = 1073741789      # 2^30 - 35
_A1 = 32767
_Q1 = _M1 // _A1      # 32768
_R1 = _M1 % _A1       # 32733
_M2 = 1073741717      # 2^30 - 107
_A2 = 32765
_Q2 = _M2 // _A2      # 32773
_R2 = _M2 % _A2       # 32720
_MAX = _M1 - 1        # _next() range: 1 .. _MAX  (~30 bits)


class Rand:
    def __init__(self, seed=None):
        self.seed(_default_seed() if seed is None else seed)

    def seed(self, s):
        s = int(s) & 0x3FFFFFFF                     # 30 bits of seed material (small int)
        self._x = s % (_M1 - 1) + 1                 # 1 .. M1-1 (never 0: MLCG fixed point)
        self._y = (s ^ 0x2545F491) % (_M2 - 1) + 1  # decorrelated second stream, 1 .. M2-1

    def _next(self):                                # combined 30-bit Lehmer, alloc-free
        x = self._x
        x = _A1 * (x % _Q1) - _R1 * (x // _Q1)
        if x < 0:
            x += _M1
        self._x = x
        y = self._y
        y = _A2 * (y % _Q2) - _R2 * (y // _Q2)
        if y < 0:
            y += _M2
        self._y = y
        z = x - y
        if z < 1:
            z += _MAX
        return z                                    # 1 .. _MAX

    def below(self, n):                             # 0 .. n-1
        return self._next() % n if n > 0 else 0

    def randint(self, a, b):                        # a .. b inclusive
        if b < a:
            raise ValueError("randint: b < a")
        return a + self._next() % (b - a + 1)

    def random(self):                               # 0.0 <= x < 1.0
        return (self._next() - 1) / 1073741788.0    # (z-1)/_MAX: 0.0 .. <1.0

    def chance(self, p):                            # True with probability p (0..1)
        return self.random() < p

    def choice(self, seq):
        if not seq:
            raise ValueError("choice from empty sequence")
        return seq[self._next() % len(seq)]

    def shuffle(self, lst):                         # Fisher-Yates, in place
        for i in range(len(lst) - 1, 0, -1):
            j = self._next() % (i + 1)
            lst[i], lst[j] = lst[j], lst[i]

    def weighted(self, weights):                    # return an index, picked by weight
        total = 0
        for w in weights:
            total += w
        if total <= 0:
            raise ValueError("weighted: total weight must be > 0")
        r = self._next() % total
        for i, w in enumerate(weights):
            if r < w:
                return i
            r -= w
        return len(weights) - 1


class Bag:
    """Shuffle-bag / '7-bag' randomizer: yields every item once per cycle in a shuffled order,
    so you never get long streaks or droughts (how modern Tetris draws pieces). Fairer than
    independent random picks for spawns/pieces."""

    def __init__(self, items, rng):
        self.items = list(items)
        if not self.items:
            raise ValueError("Bag needs >= 1 item")
        self.rng = rng
        self._i = len(self.items)                   # force a reshuffle on first next()

    def next(self):
        if self._i >= len(self.items):
            self.rng.shuffle(self.items)
            self._i = 0
        v = self.items[self._i]
        self._i += 1
        return v
