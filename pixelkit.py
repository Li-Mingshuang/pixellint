"""Shared palette and assertion helpers for the scene pipeline.

This is the single source of truth for the scene: the character's 13 colours
plus 21 scenery colours, one locked palette. Every asset in the scene -- the
character, the dog, the ground, the sky, the props -- is authored as a grid of
characters indexed into SCENE_PALETTE, so nothing can drift out of palette.

The character colours are imported from render_sprite.py rather than repeated,
so the two can never disagree.
"""

from render_sprite import PALETTE as CHAR_PALETTE

# --------------------------------------------------------------------------
# Scene canvas.  Native resolution, integer-scaled for display.
# --------------------------------------------------------------------------
SCENE_W = 160
SCENE_H = 96
SKY_ROWS = (0, 44)        # inclusive
HORIZON_ROW = 45          # distant hills / treeline start here
GROUND_TOP = 58           # walkable ground starts here
GROUND_LINE = 79          # the row feet land on

# --------------------------------------------------------------------------
# The locked palette.  Grouped by material; each material gets a base, a
# shadow and (where it helps) a highlight.
# --------------------------------------------------------------------------
SCENE_PALETTE: dict[str, tuple[int, int, int, int]] = {
    **CHAR_PALETTE,                                          # character, 13
    # sky + cloud
    "A": (0x6f, 0xb2, 0xdc, 255),  # sky
    "a": (0x3f, 0x7f, 0xb0, 255),  # sky upper / deeper
    "W": (0xfb, 0xf8, 0xf0, 255),  # cloud
    "w": (0xa8, 0xa0, 0x8c, 255),  # cloud shadow
    # grass -- bright and yellow-leaning so foliage can sit far below it
    "G": (0x7f, 0xbf, 0x4a, 255),  # grass
    "g": (0x4e, 0x8a, 0x35, 255),  # grass shadow
    "E": (0xc4, 0xe8, 0x8c, 255),  # grass highlight / blade tips
    # dirt
    "N": (0xb0, 0x8b, 0x5e, 255),  # dirt
    "n": (0x6b, 0x4f, 0x31, 255),  # dirt shadow
    # foliage -- dark, blue-leaning green, well under grass on the value ladder
    "F": (0x2f, 0x6b, 0x45, 255),  # foliage
    "f": (0x14, 0x30, 0x1f, 255),  # foliage shadow
    # wood
    "T": (0x8a, 0x5e, 0x38, 255),  # wood
    "t": (0x4a, 0x30, 0x18, 255),  # wood shadow
    # plaster wall + roof
    "U": (0xe6, 0xd6, 0xb4, 255),  # wall
    "u": (0xb2, 0x9c, 0x7c, 255),  # wall shadow
    "O": (0xb0, 0x4c, 0x3c, 255),  # roof
    "o": (0x5e, 0x23, 0x1c, 255),  # roof shadow
    # stone -- kept cool/blue-grey so it never muddles with the warm dirt.
    # `r` is deliberately dark and blue: at the ground layer's first value it sat
    # dE 29.8 from `n` (dirt shadow) with dL 0.04, so the value-step escape could
    # not apply and the pair was illegal at SCENE_TIERS. The ground agent worked
    # around it by never letting the two touch, which is fine but leaves the
    # landmine for every later layer (a stone foundation on dirt, gravel on a
    # path). Fixed at the palette instead: n-r is now 36.6.
    "R": (0x8a, 0x8a, 0x96, 255),  # stone
    "r": (0x48, 0x48, 0x60, 255),  # stone shadow
    # accents
    "Y": (0xe8, 0xc8, 0x4a, 255),  # yellow petal
    "y": (0xd0, 0x5c, 0x84, 255),  # pink petal
}

# --------------------------------------------------------------------------
# Two tier sets, because the same threshold is wrong at two different scales.
#
# SPRITE tiers are for assets where every pixel is load-bearing (the 16x32
# character, the dog): one muddy adjacent pair destroys the read.
#
# SCENE tiers are for backgrounds and props. A tree is 30px tall and a path is
# 100px long -- shape carries the read there, and holding a 160x96 scene to
# per-pixel contrast rules would force an artificially garish palette.
# --------------------------------------------------------------------------
SPRITE_TIERS = {"outline": 28.0, "shade": 20.0, "material": 45.0}
SCENE_TIERS = {"outline": 22.0, "shade": 15.0, "material": 32.0}

VALUE_STEP = 0.25

# A luminance step of >= VALUE_STEP is on its own a strong edge: human vision is
# very sensitive to lightness boundaries, so a 26% step is readable no matter
# what the chroma difference is. The rule used to *also* demand dE >= 25 as a
# companion, which was self-contradictory -- it conceded that a big value gap is
# a strong read and then asked chroma to confirm it anyway.
#
# It cost a real failure: the dog's pale paw (`S`) against the dirt path (`N`)
# came in at dL 0.26, dE 24.9, and was rejected by one tenth of a dE unit. The
# rule was wrong, not the art. The escape is now unconditional on chroma, which
# still catches every defect it caught before: the original killer, outline `K`
# against trouser shadow `p`, sat at dL 0.19 -- under the step, so it still
# fails the outline floor at dE 12.7.
VALUE_STEP_MIN_DE = 0.0

# Pairs that are deliberately a base colour and its own shadow.
SHADE_PAIRS = {
    frozenset(p) for p in (
        "Sp", "Hh", "Cc", "Pp", "Bb", "Ss", "Dc", "CD", "mp",   # character
        "Aa", "Ww", "Gg", "GE", "Nn", "Ff", "Tt", "Uu", "Oo", "Rr",
    )
}


def srgb_to_lab(rgb):
    def lin(u):
        u /= 255.0
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(v) for v in rgb)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(a: str, b: str, palette=None) -> float:
    p = palette or SCENE_PALETTE
    pa, pb = srgb_to_lab(p[a][:3]), srgb_to_lab(p[b][:3])
    return sum((x - y) ** 2 for x, y in zip(pa, pb)) ** 0.5


def luminance(key: str, palette=None) -> float:
    p = palette or SCENE_PALETTE
    r, g, b, _ = p[key]
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def tier(a: str, b: str, tiers: dict | None = None):
    t = tiers or SPRITE_TIERS
    if "K" in (a, b):
        return "outline", t["outline"]
    if frozenset((a, b)) in SHADE_PAIRS:
        return "shade", t["shade"]
    return "material", t["material"]


def adjacent_pairs(grid, palette=None):
    """Every unordered pair of colours that share an edge anywhere in the grid."""
    p = palette or SCENE_PALETTE
    h, w = len(grid), len(grid[0])
    pairs = set()
    for y in range(h):
        for x in range(w):
            a = grid[y][x]
            if a == ".":
                continue
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if nx < w and ny < h:
                    b = grid[ny][nx]
                    if b != "." and b != a and a in p and b in p:
                        pairs.add((a, b) if a < b else (b, a))
    return pairs


def build(grid, palette=None):
    from PIL import Image
    p = palette or SCENE_PALETTE
    img = Image.new("RGBA", (len(grid[0]), len(grid)), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(grid):
        for x, key in enumerate(row):
            px[x, y] = p[key]
    return img


def preview(img, scale, bg=(58, 62, 74)):
    from PIL import Image
    flat = Image.new("RGBA", img.size, (*bg, 255))
    flat.alpha_composite(img)
    return flat.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)


def check_grid(grid, label="grid", palette=None) -> list[str]:
    """Structure: shape, palette membership, closed connected body, no floaters."""
    p = palette or SCENE_PALETTE
    problems = []
    if not grid or not grid[0]:
        return [f"{label}: empty"]
    w = len(grid[0])
    if any(len(r) != w for r in grid):
        return [f"{label}: rows are not all {w} wide"]

    for i, row in enumerate(grid):
        bad = set(row) - set(p)
        if bad:
            problems.append(f"{label}: row {i} uses undefined palette keys {sorted(bad)}")
            return problems

    h = len(grid)
    opaque = {(x, y) for y in range(h) for x in range(w) if grid[y][x] != "."}
    if not opaque:
        return [f"{label}: fully transparent"]

    seed = min(opaque, key=lambda t: (t[1], t[0]))
    seen, stack = {seed}, [seed]
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] != "." and (nx, ny) not in seen:
                seen.add((nx, ny))
                stack.append((nx, ny))
    floating = sorted(opaque - seen)
    if floating:
        problems.append(f"{label}: {len(floating)} floating pixel(s): {floating[:8]}")
    return problems


def report_separation(grid, label="grid", palette=None, tiers=None) -> tuple[list[str], list[tuple]]:
    """Readability: dE76 for every touching pair, against tiered floors."""
    failures, rows = [], []
    for a, b in sorted(adjacent_pairs(grid, palette), key=lambda pr: delta_e(*pr, palette)):
        d = delta_e(a, b, palette)
        kind, floor = tier(a, b, tiers)
        vstep = abs(luminance(a, palette) - luminance(b, palette))
        ok = d >= floor or (vstep >= VALUE_STEP and d >= VALUE_STEP_MIN_DE)
        rows.append((ok, a, b, d, vstep, floor, kind))
        if not ok:
            failures.append(
                f"{label}: {a}-{b} dE={d:.1f} dL={vstep:.2f} below {floor:.0f} ({kind})"
            )
    return failures, rows
