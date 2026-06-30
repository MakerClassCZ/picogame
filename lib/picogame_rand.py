# picogame_rand - a tiny SEEDABLE random number generator + helpers.
# Why not the `random` module? A seedable, deterministic RNG gives reproducible runs (replays,
# ghosts) and daily-challenge style seeds, and the helpers (weighted picks, shuffle bag) are the
# ones small games actually need. Fast xorshift32 - no float unless you ask for it.
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


class Rand:
    def __init__(self, seed=None):
        self.seed(_default_seed() if seed is None else seed)

    def seed(self, s):
        self._s = (int(s) & 0xFFFFFFFF) or 0x1234   # xorshift must not be 0

    def _next(self):                                # xorshift32
        x = self._s
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self._s = x & 0xFFFFFFFF
        return self._s

    def below(self, n):                             # 0 .. n-1
        return self._next() % n if n > 0 else 0

    def randint(self, a, b):                        # a .. b inclusive
        if b < a:
            raise ValueError("randint: b < a")
        return a + self._next() % (b - a + 1)

    def random(self):                               # 0.0 <= x < 1.0
        return self._next() / 4294967296.0

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
