# picogame_iso: isometric projection - the cheapest pseudo-3D there is. No perspective, no divide,
# just integer add/shift, which is why it runs well on the RP2040. You keep your world on a grid;
# this maps a cell (gx, gy) + elevation to screen pixels and gives the back-to-front key for the
# painter's order isometric scenes need. Unlocks iso RPG / strategy / tactics / builder / puzzle.
#
#   iv = IsoView(ox, oy, tw, th)   # tw,th = tile half-width, half-height (2:1 diamond: th = tw//2)
#   sx, sy = iv.to_screen(gx, gy, h=0)
#   key    = iv.depth(gx, gy, h=0)  # sort your objects by this, draw ascending (far -> near)
#   top, right, left = iv.cube_faces(gx, gy, height_px)   # 3 visible faces of a raised block


class IsoView:
    def __init__(self, ox, oy, tw, th):
        # ox, oy = screen pixel of grid origin (0, 0). Grid +x runs down-right, +y down-left.
        self.ox = ox
        self.oy = oy
        self.tw = tw
        self.th = th

    def to_screen(self, gx, gy, h=0):
        """Grid point (gx, gy) + elevation h (pixels up) -> (sx, sy) screen pixels. Integer add/shift
        only - no divide, no perspective."""
        return (self.ox + int((gx - gy) * self.tw),
                self.oy + int((gx + gy) * self.th) - h)

    def depth(self, gx, gy, h=0):
        """Painter's key: larger = nearer the viewer (draw later, on top). gx+gy is the iso depth; the
        small height term keeps a tall thing in front of a flat thing one cell behind it."""
        return (gx + gy) * 256 + h

    def screen_to_grid(self, sx, sy):
        """Inverse: screen pixel -> fractional grid (gx, gy) at elevation 0 (for picking/mouse/cursor)."""
        dx = (sx - self.ox) / self.tw
        dy = (sy - self.oy) / self.th
        return ((dy + dx) * 0.5, (dy - dx) * 0.5)

    def emit_blocks(self, cells, tv, tc):
        """Alloc-free batch builder: write the flat-shaded cube triangles for MANY blocks straight into
        the tv (int16 array, 6 coords/tri) and tc (uint16 array, 1 colour/tri) buffers, ready for one
        `Canvas.fill_triangles(tv, tc, n)`. `cells` = iterable of `(gx, gy, h, (col_left, col_right,
        col_top))`, already back-to-front sorted (sort by `depth()`) with colours pre-shaded via
        `pg.rgb565`. Returns the triangle count. ~2x faster than looping `cube_faces` + a packer, because
        it computes the 7 screen points from two integer bases (no per-corner tuples, no method calls,
        no divide) - which matters because this Python geometry loop, not the C fill, dominates a
        rebuild-every-frame iso frame. Static/grid scenes: call once and cache; only scrolling/animating
        heights need it per frame."""
        ox, oy, tw, th = self.ox, self.oy, self.tw, self.th
        nt = 0
        for gx, gy, h, cols in cells:
            sx = ox + (gx - gy) * tw
            sy = oy + (gx + gy) * th          # elev-0 screen y of corner a
            ay = sy - h                        # a=(sx, ay)   top diamond at elevation h
            bx = sx + tw; by = sy + th - h     # b
            cx = sx;      cy = sy + 2 * th - h # c (front corner)
            dx = sx - tw; dy = by              # d (same y as b)
            b0y = sy + th; c0y = sy + 2 * th   # base (elev 0) y of b/d and c
            cl, cr, ct = cols
            o = nt * 6                          # left face (d, c, c0, d0)
            tv[o] = dx; tv[o + 1] = dy; tv[o + 2] = cx; tv[o + 3] = cy; tv[o + 4] = cx; tv[o + 5] = c0y
            tc[nt] = cl; nt += 1
            o = nt * 6
            tv[o] = dx; tv[o + 1] = dy; tv[o + 2] = cx; tv[o + 3] = c0y; tv[o + 4] = dx; tv[o + 5] = b0y
            tc[nt] = cl; nt += 1
            o = nt * 6                          # right face (b, c, c0, b0)
            tv[o] = bx; tv[o + 1] = by; tv[o + 2] = cx; tv[o + 3] = cy; tv[o + 4] = cx; tv[o + 5] = c0y
            tc[nt] = cr; nt += 1
            o = nt * 6
            tv[o] = bx; tv[o + 1] = by; tv[o + 2] = cx; tv[o + 3] = c0y; tv[o + 4] = bx; tv[o + 5] = b0y
            tc[nt] = cr; nt += 1
            o = nt * 6                          # top face (a, b, c, d)
            tv[o] = sx; tv[o + 1] = ay; tv[o + 2] = bx; tv[o + 3] = by; tv[o + 4] = cx; tv[o + 5] = cy
            tc[nt] = ct; nt += 1
            o = nt * 6
            tv[o] = sx; tv[o + 1] = ay; tv[o + 2] = cx; tv[o + 3] = cy; tv[o + 4] = dx; tv[o + 5] = dy
            tc[nt] = ct; nt += 1
        return nt

    def cube_faces(self, gx, gy, h):
        """The three visible faces of a 1x1 block on cell (gx, gy) raised `h` px: (top, right, left),
        each a 4-point screen polygon. Feed to fill_triangles (2 tris/face) for a flat-shaded iso block.
        Convenient for a few blocks; for many-per-frame use `emit_blocks` (alloc-free, ~2x)."""
        s = self.to_screen
        # top diamond corners at elevation h
        a = s(gx, gy, h)          # back
        b = s(gx + 1, gy, h)      # right
        c = s(gx + 1, gy + 1, h)  # front
        d = s(gx, gy + 1, h)      # left
        # front vertical edge base (elevation 0)
        b0 = s(gx + 1, gy, 0)
        c0 = s(gx + 1, gy + 1, 0)
        d0 = s(gx, gy + 1, 0)
        top = (a, b, c, d)
        right = (b, c, c0, b0)    # +x face (down-right)
        left = (d, c, c0, d0)     # +y face (down-left)
        return top, right, left
