# picogame_tiles - per-tile METADATA FLAGS (a tile-property bitfield), keyed by TILE INDEX
# (the flags belong to the tile graphic, shared by every cell that uses it). Turns tile collision
# and logic into one-liners, so you don't hand-roll a side table in every game.
#
#   import picogame_tiles as tiles
#   tf = tiles.TileFlags({1: tiles.SOLID, 2: tiles.SOLID | tiles.HAZARD, 5: tiles.LADDER})
#   if tf.at_px(tm, x, y, tiles.B_SOLID): ...        # is the tile under pixel (x, y) solid?
#   if tf.at(tm, tx, ty, tiles.B_HAZARD): hurt()     # by cell
#   tf.set(3, tiles.B_COIN)                          # flag tile 3 at runtime
#
# Bake the {tile: flags} table from your scene/map JSON (the editor can paint flags per tile).

# Named BIT indices (0..7) + their MASKs. Eight user-defined flags.
B_SOLID, B_HAZARD, B_LADDER, B_PLATFORM, B_WATER, B_COIN, B_EXIT, B_CUSTOM = range(8)
SOLID = 1 << B_SOLID
HAZARD = 1 << B_HAZARD
LADDER = 1 << B_LADDER
PLATFORM = 1 << B_PLATFORM
WATER = 1 << B_WATER
COIN = 1 << B_COIN
EXIT = 1 << B_EXIT
CUSTOM = 1 << B_CUSTOM


class TileFlags:
    def __init__(self, flags=None, tile_px=8):
        """flags: {tile_index: bitfield} dict (sparse), OR a list/bytes/bytearray indexed by
        tile index (dense). A dense table is kept as a compact bytearray (one byte per tile -
        the 8 flags fit), NOT expanded into a per-tile dict, so a 256-tile table costs 256 bytes
        instead of hundreds of Python objects. tile_px = tile size for the pixel helpers."""
        self.tile_px = tile_px
        if isinstance(flags, (list, tuple, bytes, bytearray)):
            self._dense = bytearray(flags)   # compact + mutable; index == tile id
            self.f = None
        else:
            self._dense = None               # sparse: a dict keyed by the tiles that carry flags
            self.f = dict(flags) if flags else {}

    def get(self, tile, bit=None):
        """Full bitfield of a tile, or one bool flag if `bit` (a B_* index) is given."""
        if self._dense is not None:
            v = self._dense[tile] if 0 <= tile < len(self._dense) else 0
        else:
            v = self.f.get(tile, 0)
        return v if bit is None else bool(v & (1 << bit))

    def set(self, tile, bit, value=True):
        if self._dense is not None:
            if 0 <= tile < len(self._dense):     # dense table is fixed-size (0..len-1)
                v = self._dense[tile]
                self._dense[tile] = (v | (1 << bit)) if value else (v & ~(1 << bit))
            return
        v = self.f.get(tile, 0)
        nv = (v | (1 << bit)) if value else (v & ~(1 << bit))
        if nv:
            self.f[tile] = nv
        elif tile in self.f:
            del self.f[tile]                     # drop cleared tiles - don't accumulate 0 entries

    def at(self, tilemap, tx, ty, bit):
        """Flag `bit` of the tile at cell (tx, ty) of a Tilemap."""
        return self.get(tilemap.tile(tx, ty), bit)

    def at_px(self, tilemap, px, py, bit):
        """Flag `bit` of the tile under MAP-LOCAL pixel (px, py) - the common collision probe.
        If the map isn't at screen (0, 0), subtract its origin from px/py yourself."""
        t = self.tile_px
        return self.get(tilemap.tile(px // t, py // t), bit)
