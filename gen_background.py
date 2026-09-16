"""Authoring tool for the four parallax background layers in game/background.py.

This is NOT imported by the game and NOT imported by check_background.py.  It is
the generator that produced the literal grids once; `game/background.py` holds
the frozen output, exactly the way `sky.py` holds frozen literals and no longer
carries its generator.  Keep this file so the art can be re-tuned by editing a
number instead of 320 characters.

Run:  python gen_background.py        (rewrites game/background.py)

Method, per layer:

  SKY     procedural.  25 luminance steps across 96 rows: four flat bands
          (`1` `2` `3` `4`) joined by three seven-row ramps.  A ramp row mixes
          its two band keys on an 8x8 ordered Bayer lattice, so a row holds an
          exact k/8 share of the lighter key and every row inside a plateau
          holds an identical key count -- the ramp steps, it never chatters.
          320 % 8 == 0, so the lattice wraps exactly at the tile edge.
          Stars and a moon are stamped on top (see STARS/MOON below).

  FAR     procedural.  A hand-authored table of ruins (x, width, top, profile)
          rasterised column by column; the profile function decides each
          column's crown height, and the crowning pixel becomes the `6` lit rim
          that the city glow catches.  Plus a tower crane and antennae.  One
          massif is centred on the tile seam so the wrap carries real substance.

  MID     procedural.  Same table-and-rasterise idea at a larger scale, with
          four tones: `C` body, `c` shadow (shaded flank, under-rim, base),
          `5` deep void (window holes, collapsed floors), `E` lit window.
          Windows are stamped on a deterministic grid inside each mass; one
          massif crosses the tile seam.

  STREET  procedural.  Opaque asphalt field: `r` grain whose density ramps up
          toward the bottom (foreground depth), `r` cracks walked as polylines,
          `r`/`5` potholes with a `C` broken lip, `C`/`c` debris, and an `M`
          dashed centre line on a period-32 rhythm that leaves the tile seam
          inside a gap.

Determinism: every random-looking decision comes from `h()` below, a 32-bit
integer hash.  Nothing depends on `random`, on dict ordering or on the Python
version, so re-running this file reproduces game/background.py byte for byte
apart from the timestamp-free header it writes.

Palette safety (this is why the art looks the way it does):

  `4`-`6` is a HARD FAILURE at dE 7.75 / dL 0.07 -- the horizon-haze key and the
  far-building lit edge cannot touch.  So stars keyed `6` are confined to rows
  0..60 where the sky is still `1`/`2`/`3`; the haze band and its ramp carry `M`
  stars instead, which clear every sky key.  `3`-`4` is only a warning
  (dE 17.9), which is what a gradient step is meant to be.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gamepalette import GAME_W  # noqa: E402

W = GAME_W
SKY_H, FAR_H, MID_H, STREET_H = 96, 56, 64, 40
OUT = ROOT / "game" / "background.py"


# --------------------------------------------------------------------------
# deterministic hash -- portable, no `random` module, no version drift
# --------------------------------------------------------------------------
def h(*vals) -> float:
    x = 0x9E3779B1
    for v in vals:
        x = ((x ^ (int(v) & 0xFFFFFFFF)) * 0x85EBCA6B) & 0xFFFFFFFF
        x ^= x >> 13
        x = (x * 0xC2B2AE35) & 0xFFFFFFFF
        x ^= x >> 16
    return x / 4294967296.0


# ==========================================================================
# SKY -- 320 x 96
# ==========================================================================
BAYER8 = (
    (0, 32, 8, 40, 2, 34, 10, 42),
    (48, 16, 56, 24, 50, 18, 58, 26),
    (12, 44, 4, 36, 14, 46, 6, 38),
    (60, 28, 52, 20, 62, 30, 54, 22),
    (3, 35, 11, 43, 1, 33, 9, 41),
    (51, 19, 59, 27, 49, 17, 57, 25),
    (15, 47, 7, 39, 13, 45, 5, 37),
    (63, 31, 55, 23, 61, 29, 53, 21),
)

# The classic Bayer matrix is a permutation of 0..63 taken as a whole, but a
# single row of it is NOT a permutation of 0..7 -- so thresholding with it makes
# the light share of a row jump around instead of stepping (measured: row 26 of
# a test run came out 100% light and row 27 only 75%, i.e. the ramp went
# backwards).  The sky ramp is controlled per ROW, so it needs a lattice whose
# every row holds each residue exactly once.  `DITHER_PERM[y]` is coprime with 8
# (a bijection on 0..7) and `(x + 3y) % 8` is a bijection over a row's columns,
# so a row lit where `(r * DITHER_PERM[y]) % 8 < k` holds exactly `40 * k` of its
# 320 pixels -- for every k, in every row -- while still scattering which columns
# are lit from row to row instead of ruling diagonal stripes.  BAYER8 is kept
# above only as the record of what was tried first.
DITHER_PERM = (1, 3, 5, 7, 5, 3, 7, 1)


def dither_on(x: int, y: int, k: int) -> bool:
    r = (x + 3 * y) % 8
    return ((r * DITHER_PERM[y % 8]) % 8) < k

# 25 steps: level // 8 picks the band key, level % 8 the share of the next key.
#   0..20   '1'          21..27   ramp 1->2      28..40   '2'
#   41..47  ramp 2->3    48..63   '3'           64..70   ramp 3->4
#   71..95  '4'
SKY_PLATEAU = (
    (0, 20, 0), (28, 40, 8), (48, 63, 16), (71, 95, 24),
)
SKY_RAMP = ((21, 27, 0), (41, 47, 8), (64, 70, 16))


def sky_level(y: int) -> int:
    for a, b, base in SKY_RAMP:
        if a <= y <= b:
            return base + (y - a + 1)
    for a, b, lv in SKY_PLATEAU:
        if a <= y <= b:
            return lv
    raise ValueError(y)


MOON = (238, 20, 8)             # cx, cy, radius
MOON_CRATERS = ((-3, -2, 2), (2, 3, 2), (4, -3, 1), (-4, 4, 1))


def sky_bands() -> list[str]:
    rows = []
    for y in range(SKY_H):
        lv = sky_level(y)
        to_index = lv // 8
        dark = "1234"[to_index]
        share = lv % 8
        if share == 0:
            rows.append(dark * W)
            continue
        light = "1234"[to_index + 1]
        rows.append("".join(light if dither_on(x, y, share) else dark
                            for x in range(W)))
    return rows


def sky_stars(rows: list[str]) -> int:
    """Sparse 1-2px stars.  `6` only where the sky is `1`/`2`/`3`."""
    taken = set()
    cx, cy, r = MOON
    for y in range(SKY_H):
        for x in range(W):
            if (x - cx) ** 2 + (y - cy) ** 2 <= (r + 3) ** 2:
                taken.add((x, y))

    placed = 0
    for i in range(4000):
        if placed >= 24:
            break
        x = 4 + int(h(i, 7) * 311)              # 4..314
        y = 3 + int(h(i, 11) * 82)              # 3..84
        key = "6" if y <= 60 else "M"           # 4-6 is a hard failure: keep clear
        pair = h(i, 13) < 0.25
        cells = [(x, y)] + ([(x + 1, y)] if pair else [])
        if any(c in taken for c in cells):
            continue
        for cx_, cy_ in cells:
            rows[cy_] = rows[cy_][:cx_] + key + rows[cy_][cx_ + 1:]
            taken.add((cx_, cy_))
        placed += 1
    return placed


def sky_moon(rows: list[str]) -> None:
    cx, cy, r = MOON
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                rows[y] = rows[y][:x] + "M" + rows[y][x + 1:]
    # a `6` limb on the lower-right arc, where the disc turns away
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if r * r - 2 * r < d2 <= r * r and (x - cx) - (y - cy) >= 0:
                rows[y] = rows[y][:x] + "6" + rows[y][x + 1:]
    for ox, oy, cr in MOON_CRATERS:
        for y in range(cy + oy - cr, cy + oy + cr + 1):
            for x in range(cx + ox - cr, cx + ox + cr + 1):
                if (x - cx - ox) ** 2 + (y - cy - oy) ** 2 <= cr * cr:
                    if rows[y][x] == "M":
                        rows[y] = rows[y][:x] + "6" + rows[y][x + 1:]


def build_sky() -> list[str]:
    rows = sky_bands()
    sky_moon(rows)
    sky_stars(rows)
    return rows


# ==========================================================================
# shared component helper
# ==========================================================================
def cyclic_components(grid):
    """4-connected components with the horizontal wrap, i.e. the tile as tiled."""
    hh, ww = len(grid), len(grid[0])
    seen, comps = set(), []
    for y in range(hh):
        for x in range(ww):
            if grid[y][x] == "." or (x, y) in seen:
                continue
            stack, comp = [(x, y)], []
            seen.add((x, y))
            while stack:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                for nb in (((cx + 1) % ww, cy), ((cx - 1) % ww, cy),
                           (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nb[1] < hh and grid[nb[1]][nb[0]] != "." and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
            comps.append(sorted(comp))
    return comps


def drop_specks(g, grid, min_px=4):
    """Delete stray rubble specks -- one floating pixel reads as a dead pixel."""
    dropped = 0
    for comp in cyclic_components(grid):
        if len(comp) < min_px:
            for x, y in comp:
                g[y][x] = "."
            dropped += 1
    return dropped


# ==========================================================================
# profiles shared by FAR and MID
# ==========================================================================
def make_profile(kind: str, w: int, top: int, salt: int) -> list[int]:
    if kind == "slab":
        return [top] * w
    if kind == "tower":
        cols = [top] * w
        if w >= 5:
            notch = 1 + int(h(salt, 5) * (w - 4))
            cols[notch] = top + 2
            cols[min(w - 1, notch + 1)] = top + 1
        else:
            cols[w // 2] = top + 1
        return cols
    if kind == "broken":
        cols, cur = [], top + int(h(salt, 17) * 5)
        for i in range(w):
            if h(salt, i, 23) < 0.30:
                cur = top + int(h(salt, i, 29) * 7)
            cols.append(cur)
        return cols
    if kind == "stepped":
        steps = 2 + int(h(salt, 31) * 3)
        return [top + int(h(salt, i * steps // w, 37) * 8) for i in range(w)]
    raise ValueError(kind)


# ==========================================================================
# FAR -- 320 x 56
# ==========================================================================
# (x, width, top row, profile).  The last entry is centred on the tile seam:
# 296..319 + 0..23, 48 columns of substance across the wrap.
FAR_RUINS = (
    (26, 13, 33, "broken"),
    (44, 7, 17, "tower"),
    (55, 17, 29, "broken"),
    (82, 9, 11, "tower"),
    (95, 5, 24, "slab"),
    (106, 22, 35, "broken"),
    (139, 10, 21, "tower"),
    (154, 6, 38, "slab"),
    (164, 24, 27, "stepped"),
    (194, 8, 15, "tower"),
    (207, 15, 31, "broken"),
    (232, 6, 41, "slab"),
    (243, 5, 25, "tower"),
    (252, 24, 32, "broken"),
    (296, 48, 26, "stepped"),
)

# tower crane: (row range of the jib, x range), mast, hanging cable + hook
CRANE_JIB_Y = (6, 8)
CRANE_JIB_X = (230, 290)
CRANE_MAST_X = (260, 262)
CRANE_HOOK_X = 292
CRANE_HOOK_Y = 20


def far_build() -> list[str]:
    g = [["."] * W for _ in range(FAR_H)]

    def put(x, y, ch):
        if 0 <= y < FAR_H:
            g[y][x % W] = ch

    for (bx, bw, top, kind) in FAR_RUINS:
        tops = make_profile(kind, bw, top, bx)
        rim = 2 if (kind in ("tower", "stepped") and bw >= 8) else 1
        for i in range(bw):
            x = (bx + i) % W
            t = max(0, min(FAR_H - 1, tops[i]))
            for y in range(t, FAR_H):
                put(x, y, "5")
            for d in range(rim):
                if t + d < FAR_H:
                    put(x, t + d, "6")
        # antennae on the towers
        if kind == "tower":
            ax = (bx + bw // 2) % W
            a_top = max(0, tops[bw // 2] - 4 - int(h(bx, 41) * 4))
            for y in range(a_top, tops[bw // 2] - 1):
                put(ax, y, "6")
            put((ax - 1) % W, a_top, "6")
            put((ax + 1) % W, a_top, "6")

    # --- tower crane ------------------------------------------------------
    jy0, jy1 = CRANE_JIB_Y
    for y in range(jy0, jy1 + 1):
        for x in range(CRANE_JIB_X[0], CRANE_JIB_X[1] + 1):
            put(x, y, "6" if y == jy0 else "5")
    for x in range(CRANE_MAST_X[0], CRANE_MAST_X[1] + 1):
        for y in range(jy0, FAR_H):
            put(x, y, "5")
        put(x, jy0, "6")
    put(CRANE_MAST_X[1], jy0, "6")
    for y in range(jy1 + 1, CRANE_HOOK_Y + 1):          # hoist cable
        put(CRANE_HOOK_X, y, "6")
    for x in range(CRANE_HOOK_X - 1, CRANE_HOOK_X + 2):  # hook block
        for y in range(CRANE_HOOK_Y + 1, CRANE_HOOK_Y + 3):
            put(x, y, "5")
    put(CRANE_HOOK_X, CRANE_HOOK_Y + 1, "6")
    for x in range(CRANE_JIB_X[0], CRANE_JIB_X[0] + 4):  # counterweight
        for y in range(jy0, jy1 + 2):
            put(x, y, "5")
    return ["".join(r) for r in g]


# ==========================================================================
# MID -- 320 x 64
# ==========================================================================
# (x, width, top row, profile).  The last entry crosses the tile seam:
# 290..319 + 0..33, 64 columns of substance, and no gap is cut near the seam.
MID_BLOCKS = (
    (36, 20, 24, "broken"),
    (60, 12, 12, "tower"),
    (76, 26, 28, "broken"),
    (106, 9, 18, "tower"),
    (119, 18, 22, "broken"),
    (141, 14, 8, "tower"),
    (159, 8, 32, "slab"),
    (171, 22, 18, "stepped"),
    (197, 11, 11, "tower"),
    (212, 26, 25, "broken"),
    (242, 9, 16, "tower"),
    (255, 14, 20, "broken"),
    (273, 14, 30, "slab"),
    (290, 64, 18, "stepped"),
)

MID_BASE_SHADOW = 3        # bottom rows of every mass are in the rubble shadow
WINDOW_PITCH_X, WINDOW_PITCH_Y = 6, 8
WINDOW_W, WINDOW_H = 2, 3
MID_LIT_CHANCE = 0.13      # `E` windows are the one warm accent: keep them rare


def mid_build() -> list[str]:
    g = [["."] * W for _ in range(MID_H)]

    def put(x, y, ch):
        if 0 <= y < MID_H:
            g[y][x % W] = ch

    for (bx, bw, top, kind) in MID_BLOCKS:
        tops = make_profile(kind, bw, top, bx)
        lo = min(tops)

        # 1. concrete body: `C` above the shadow line, `c` below it.  The line
        #    drops to the right, because the moon sits up and to the right, so
        #    each mass carries a diagonal light-to-shadow break instead of a
        #    flat band.
        for i in range(bw):
            x = (bx + i) % W
            t = tops[i]
            split = t + (MID_H - t) // 2 + int((bw - i) * 0.18)
            for y in range(t, MID_H):
                put(x, y, "C" if y < split else "c")
            put(x, t, "C")                     # lit broken rim
            if t + 1 < MID_H:
                put(x, t + 1, "c")             # shadow cast under the rim
            if t + 2 < MID_H and h(x, 3) < 0.55:
                put(x, t + 2, "c")

        # 2. shaded left flank -- the side turned away from the moon
        flank = 3 if bw >= 20 else (2 if bw >= 8 else 1)
        for i in range(min(flank, bw)):
            x = (bx + i) % W
            for y in range(tops[i] + 1, MID_H):
                put(x, y, "c")

        # 3. base rubble shadow along the bottom
        for i in range(bw):
            x = (bx + i) % W
            for y in range(MID_H - MID_BASE_SHADOW, MID_H):
                if g[y][x] != ".":
                    put(x, y, "c")

        # 4. collapsed floor slabs: a `5` void under a `c` break line
        y = lo + 6
        while y < MID_H - MID_BASE_SHADOW - 4:
            if h(bx, y, 53) < 0.75:
                for i in range(bw):
                    x = (bx + i) % W
                    if g[y][x] == "." or tops[i] > y:
                        continue
                    put(x, y, "5")
                    if h(x, y, 59) < 0.55:
                        put(x, y + 1, "c")
            y += 8

        # 5. window holes on a fixed grid inside the mass; `E` lit ones are rare
        wy = int(lo) + 4
        while wy + WINDOW_H - 1 < MID_H - MID_BASE_SHADOW:
            wx = bx + 3
            while wx + WINDOW_W - 1 <= bx + bw - 3:
                lit = h(wx, wy, 61) < MID_LIT_CHANCE
                for dx in range(WINDOW_W):
                    for dy in range(WINDOW_H):
                        x, y = (wx + dx) % W, wy + dy
                        if not (0 <= y < MID_H) or g[y][x] == ".":
                            continue
                        if y < tops[(wx + dx - bx) % bw] + 2:
                            continue
                        if y >= MID_H - MID_BASE_SHADOW:
                            continue
                        put(x, y, "E" if lit else "5")
                wx += WINDOW_PITCH_X
            wy += WINDOW_PITCH_Y

        # 6. a collapsed slot: a notch between two wings, stopping short of the
        #    base so the mass stays one piece.  Blocks in 40..280 only, so no
        #    slot is ever cut into the tile seam.
        if bw >= 18 and 40 <= bx % W <= 280:
            sx = (bx + bw // 2) % W
            for y in range(lo + 3, MID_H - MID_BASE_SHADOW + 1):
                put(sx, y, ".")

    # 7. rubble spilling into the alleys between masses
    for i in range(220):
        x = int(h(i, 71) * W)
        y = MID_H - 1 - int(h(i, 73) * 3)
        if g[y][x] != ".":
            continue
        g[y][x] = "C" if h(i, 79) < 0.55 else "c"
        if h(i, 83) < 0.45 and g[y][(x + 1) % W] == ".":
            g[y][(x + 1) % W] = "c"
        if y - 1 >= 0 and h(i, 89) < 0.30 and g[y - 1][x] == ".":
            g[y - 1][x] = "c"
    drop_specks(g, ["".join(r) for r in g])
    return ["".join(r) for r in g]


# ==========================================================================
# STREET -- 320 x 40
# ==========================================================================
STREET_CLEAN_ROWS = 2          # the walkable surface: uniform asphalt
MARK_ROW, MARK_H = 18, 2
MARK_ON, MARK_PERIOD = 16, 32


def street_build() -> list[str]:
    g = [["R"] * W for _ in range(STREET_H)]

    # --- asphalt grain, denser toward the bottom (foreground depth) --------
    for y in range(STREET_CLEAN_ROWS, STREET_H):
        density = 0.05 + 0.20 * (y - STREET_CLEAN_ROWS) / (STREET_H - 1 - STREET_CLEAN_ROWS)
        x = 0
        while x < W:
            if h(x, y, 101) < density:
                run = 1 + int(h(x, y, 103) * 3)
                for k in range(run):
                    g[y][(x + k) % W] = "r"
                x += run
            x += 1

    # --- cracks: polylines walked left to right ---------------------------
    for c in range(14):
        x = int(h(c, 107) * W)
        y = 3 + int(h(c, 109) * (STREET_H - 6))
        steps = 8 + int(h(c, 113) * 22)
        for _ in range(steps):
            if 0 <= y < STREET_H:
                g[y][x % W] = "r"
                if h(x, y, 127) < 0.18:
                    g[y][(x + 1) % W] = "r"
            y += -1 if h(x, y, 131) < 0.45 else (1 if h(x, y, 137) < 0.5 else 0)
            x += 1 + (1 if h(x, y, 139) < 0.30 else 0)
            y = max(2, min(STREET_H - 1, y))

    # --- potholes: `r` bowl, `5` core, `C` broken lip ---------------------
    for p in range(5):
        px = int(h(p, 149) * W)
        py = 8 + int(h(p, 151) * (STREET_H - 14))
        rx = 3 + int(h(p, 157) * 4)
        ry = 1 + int(h(p, 163) * 2)
        for dy in range(-ry, ry + 1):
            for dx in range(-rx, rx + 1):
                if (dx * dx) / (rx * rx) + (dy * dy) / (ry * ry) <= 1.0:
                    x, y = (px + dx) % W, py + dy
                    if 0 <= y < STREET_H:
                        g[y][x] = "r"
        for dx in range(-1, 2):
            y = py - ry - 1
            if 3 <= y < STREET_H:
                g[y][(px + dx) % W] = "C"
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                x, y = (px + dx) % W, py + dy
                if 0 <= y < STREET_H and abs(dx) + abs(dy) <= 1:
                    g[y][x] = "5"

    # --- debris: concrete chunks with a shadow step down-right ------------
    for d in range(26):
        x = int(h(d, 167) * W)
        y = 4 + int(h(d, 173) * (STREET_H - 6))
        wdt = 1 + int(h(d, 179) * 3)
        hgt = 1 + int(h(d, 181) * 2)
        for dx in range(wdt):
            for dy in range(hgt):
                xx, yy = (x + dx) % W, y + dy
                if 0 <= yy < STREET_H:
                    g[yy][xx] = "C"
        for dx in range(wdt + 1):
            xx, yy = (x + dx) % W, y + hgt
            if 0 <= yy < STREET_H:
                g[yy][xx] = "c"

    # --- road markings: dashed centre line, seam lands inside a gap -------
    for y in range(MARK_ROW, MARK_ROW + MARK_H):
        for x in range(W):
            if x % MARK_PERIOD < MARK_ON:
                g[y][x] = "M"
    return ["".join(r) for r in g]


# ==========================================================================
# emit
# ==========================================================================
DOCSTRING = '''"""Parallax background: four 320-wide layers, frozen as literal grids.

One character is one pixel and one index into `gamepalette.GAME_PALETTE`.  The
grids below are the art, not a runtime recipe -- nothing here computes at import
time.  `gen_background.py` is the authoring tool that produced them and is the
place to re-tune a number; this file is the picture.

    layer    size       opaque?   contents
    SKY      320 x  96  yes       four band keys `1` `2` `3` `4` joined by
                                  Bayer-dithered ramps, stars, a moon
    FAR      320 x  56  no        `5` skyline silhouettes, `6` lit rims, a
                                  tower crane, antennae
    MID      320 x  64  no        `C` concrete masses, `c` shadows, `5` voids,
                                  `E` lit windows, rubble
    STREET   320 x  40  yes       `R` asphalt, `r` grain/cracks/potholes, `M`
                                  dashed centre line, `C`/`c` debris

Compositing (see LAYER_OFFSETS / Z_ORDER): each layer's row 0 lands on this
scene row of a 320x180 viewport.

    SKY     0    rows   0.. 95     the sky is behind everything
    FAR    40    rows  40.. 95     far skyline, bottoms hidden by MID
    MID    84    rows  84..147     nearer ruins, bases on the road
    STREET 148   rows 148..187     the top row is the surface, so its top row
                                   lands on gamepalette.GROUND_Y and the bottom
                                   eight rows fall off the bottom of the screen

TILEABILITY.  All four layers repeat every 320 columns.  Every stamp in the
generator is applied modulo 320 (so a massif centred on the seam draws on both
sides of it), the sky dither lattice has period 8 and 320 % 8 == 0, and the road
marking rhythm has period 32 with 320 % 32 == 0, so the seam falls inside a gap
between dashes.  FAR and MID each carry one massif straddling the seam with tens
of columns of substance on each side, so the wrap is a real join and not a 1px
sliver.  `check_background.py` asserts all of this, and asserts that the wrap
pair clears the same dE76 rule as any other touching pair, per row.

PALETTE NOTES.  `4`-`6` (horizon haze vs far lit rim) is a hard separation
failure at dE 7.75, so `6` stars live only in rows 0..60 where the sky is still
`1`/`2`/`3`, and the haze band carries `M` stars instead.  `3`-`4` (dE 17.9) and
`C`-`M` / `c`-`R` / `C`-`6` are warnings, not failures, and are used as such.

DARKNESS ORDER.  FAR is a `5` near-black silhouette by palette design (lum
0.032), so no honest arrangement makes MID's concrete lighter-than-sky bodies
darker *per opaque pixel* than FAR.  MID therefore earns "darker and more
solid" the two ways it can: it blanks far more of the frame (coverage roughly
twice FAR's) and its mass is carried by its dark tones -- `c` shadow plus `5`
void, not by the lit `C` faces.  `check_background.py` asserts both, and reports
the raw numbers rather than pretending the first one holds.
"""'''


def emit(name: str, grid: list[str]) -> str:
    lines = [f"{name}: list[str] = ["]
    for i, row in enumerate(grid):
        lines.append(f'    "{row}",  # {i:2d}')
    lines.append("]")
    return "\n".join(lines)


def main() -> int:
    sky = build_sky()
    far = far_build()
    mid = mid_build()
    street = street_build()

    parts = [
        DOCSTRING,
        "",
        "# Each layer's row 0 lands on this scene row of a 320x180 viewport.",
        "# Back to front; nothing below the sky is drawn over nothing.",
        "Z_ORDER: list[str] = [\"SKY\", \"FAR\", \"MID\", \"STREET\"]",
        "LAYER_OFFSETS: dict[str, int] = {\"SKY\": 0, \"FAR\": 40, \"MID\": 84, \"STREET\": 148}",
        "",
        emit("SKY", sky),
        "",
        emit("FAR", far),
        "",
        emit("MID", mid),
        "",
        emit("STREET", street),
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts), encoding="utf-8")

    def cov(grid):
        op = sum(1 for r in grid for c in r if c != ".")
        return op, op / (len(grid) * len(grid[0]))

    print(f"wrote {OUT}")
    for name, grid in (("SKY", sky), ("FAR", far), ("MID", mid), ("STREET", street)):
        op, c = cov(grid)
        keys = "".join(sorted(set("".join(grid)) - {"."}))
        print(f"  {name:6s} {len(grid[0])}x{len(grid):3d}  opaque {op:5d} ({c*100:5.1f}%)  keys {keys}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
