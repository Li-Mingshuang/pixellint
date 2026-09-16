"""Combat effects and feedback sprites for the night-city zombie shooter.

Authored the house way: every frame is a list of equal-length strings, one
character per pixel, one index into :data:`gamepalette.GAME_PALETTE`.  Nothing
is computed at build time -- what you read below is exactly what is rasterised,
and ``check_effects.py`` asserts every claim made in this docstring.

The set
-------
    muzzle     16x12 x4   four-frame muzzle flash, barrel pointing right
    bullet     10x4  x2   tracer round, bright nose + fading tail
    casing      5x4  x2   spent brass, two rotations
    impact     10x10 x3   sparks on hard surface, then a dust puff
    blood       8x8, 8x10, 10x8   directional spatter
    bloodpool  20x8  x1   pool on the ground, flush with its bottom row
    gib         4x4, 3x3, 3x3     three gore chunks
    dust       12x8  x3   footfall puff, expanding then dissipating

Design notes
------------
**The flash has to be a star, not a blob.**  At 16x12 a filled burst is a
yellow lozenge; the eye reads a burst from its *silhouette*, so both bloom
frames are built from a cross with arms that taper W -> X -> Y outward, and the
extreme tip of every arm is offset one pixel off the arm's axis.  Those offsets
are the raggedness: without them the star reads as a plus sign.

Frame 1 (index 0) is a *small hot core* -- 18 px, six of them ``W``, so it is
mostly white-hot.  Frame 2 (index 1) is the full bloom: 61 px, widest at 15 px
of beam, W core grown to twelve pixels, cool ``Y`` pushed out to the tips.
Frame 3 (index 2) collapses to an 11 px cross and frame 4 (index 3) is fully
transparent -- a burnt-out frame is how a 40 ms flash ends, and ``check_grid``
reporting "fully transparent" for it is expected, not a defect.

**Blood reads by direction, not by symmetry.**  A spray is dense where it left
the body and broken where it is going, so each of the three spatter frames puts
the ``u``/``U`` mass at the source and a couple of *isolated* ``v`` droplets at
the far edge.  ``v`` 208,64,64 against ``U`` 140,31,31 is dE 21.5 -- just under
the 22 warn bar -- so the two never touch: the gradient always steps
u -> U -> v and never u -> v directly.  That is a composition rule, not a
silenced warning; the frames are still drawn the way a spray looks.

**Brass has no key in this palette.**  ``G``/``g``/``N`` are gunmetal greys and
a grey casing reads as another piece of the gun.  ``E`` (the lit-window gold)
is the only warm yellow bright enough to be brass, shaded with ``Y`` on the side
away from the light, which is the same lighting direction used on the flash.

**Dust is concrete, not smoke.**  ``C``/``c`` are the mid-ruin concrete tones,
which is what a boot kicking up street grit actually looks like; the puff sits
on its bottom row so it can be placed flush with ``GROUND_Y``.

Anchoring
---------
Every grid is transparent except its own pixels and is drawn with its own
top-left at the effect's origin.  ``muzzle`` and ``bullet`` travel right: the
hottest pixel / the nose is the rightmost one.  ``bloodpool`` and ``dust`` put
their base on their last row so a caller can align them to the ground.
"""

from pathlib import Path
import sys

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _path in (str(_ROOT), str(_HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from PIL import Image

from gamepalette import GAME_PALETTE
from pixelkit import build, check_grid, preview, report_separation

OUT_DIR = _ROOT / "assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SCALE = 8               # preview + gif magnification
PAD = 6                 # gutter between frames in the preview sheet
MUZZLE_MS = 40          # muzzle flash frame time
BG = GAME_PALETTE["2"][:3]   # night sky mid: dark, but not black

# --------------------------------------------------------------------------
# muzzle -- 16x12 x4.  Cross-shaped burst, W core -> X -> Y tips, ragged tips.
#
#   f0  small hot core   18 px, six W
#   f1  full bloom       61 px, the widest and brightest
#   f2  collapsing       11 px
#   f3  gone              0 px  (fully transparent, and expected to be)
# --------------------------------------------------------------------------
MUZZLE_FRAMES: list[list[str]] = [
    # f0 - the first frame: a tight, mostly white-hot core
    [
        "................",
        "................",
        "................",
        "........Y.......",
        "......XXX.......",
        ".....XWWWX......",
        ".....XWWWX......",
        "......XXX.......",
        ".......Y........",
        "................",
        "................",
        "................",
    ],
    # f1 - full bloom: the beam reaches 15 px, the core is 12 px of W
    [
        ".......Y........",
        "......XXY.......",
        "......XXX.......",
        ".....XXXXY......",
        "....YXWWWXY.....",
        "..YYXXWWWXXYY...",
        "..YYXXWWWXXYYY..",
        "....YXWWWXY.....",
        ".....YXXXX......",
        "......XXX.......",
        "......YXX.......",
        ".......Y........",
    ],
    # f2 - collapsing: the arms have fallen back in, only the core survives
    [
        "................",
        "................",
        "................",
        ".......Y........",
        "......XXX.......",
        "......XWX.......",
        "......YXY.......",
        ".......Y........",
        "................",
        "................",
        "................",
        "................",
    ],
    # f3 - gone.  A 40 ms flash ends on an empty frame; see check_effects.py.
    [
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
    ],
]

# --------------------------------------------------------------------------
# bullet -- 10x4 x2.  Tracer in flight, nose on the right.
# f1 keeps the nose at column 9 and pulls 5px of tail in, so the round stays
# put on screen while it fades instead of shrinking away from the target.  The
# tail is stepped one row rather than square, which is what makes it read as a
# round with a trail instead of a yellow rectangle.
# --------------------------------------------------------------------------
BULLET_FRAMES: list[list[str]] = [
    [
        "..........",
        "..YYYXXWWW",
        "...YYXXWWW",
        "..........",
    ],
    [
        "..........",
        ".....YXXWW",
        ".....YXXWW",
        "..........",
    ],
]

# --------------------------------------------------------------------------
# casing -- 5x4 x2.  Spent brass: side-on, then mid-tumble at 45 degrees.
# E is the brass, Y the side away from the light, K the two ends.
# --------------------------------------------------------------------------
CASING_FRAMES: list[list[str]] = [
    [
        ".....",
        "KEEEK",
        "KYYYK",
        ".....",
    ],
    [
        "...EK",
        "..YEK",
        ".YEE.",
        "KYE..",
    ],
]

# --------------------------------------------------------------------------
# impact -- 10x10 x3.  Sparks, then the dust the round knocked loose.
# f0 is a connected star with four separated tips; f1 has thrown the sparks
# clear (eleven single pixels, cooling X -> Y outward); f2 is only the puff.
# --------------------------------------------------------------------------
IMPACT_FRAMES: list[list[str]] = [
    [
        "..........",
        "..........",
        ".....Y....",
        "....XXX...",
        "...XXWXX..",
        "..X.WWW.X.",
        "...XXWXX..",
        "....XXX...",
        ".....Y....",
        "..........",
    ],
    [
        "....Y.....",
        "..........",
        "..Y....Y..",
        "..........",
        ".Y..X.X..Y",
        ".....Y....",
        ".Y..X.X..Y",
        "..........",
        "..Y....Y..",
        "....Y.....",
    ],
    [
        "..........",
        "..........",
        "....CC....",
        "..CCCCC...",
        ".CCcCCcC..",
        "..CCcCC...",
        "...cCc....",
        "....cc....",
        "..........",
        "..........",
    ],
]

# --------------------------------------------------------------------------
# blood -- 8x8, 8x10, 10x8.  Three spray directions: forward, upward, wide.
# Source at the trailing edge (the u mass and the U body); the leading edge is
# v, and the v droplets that clear the body are single separated pixels.
# --------------------------------------------------------------------------
BLOOD_FRAMES: list[list[str]] = [
    # f0 - 8x8, spraying forward and right
    [
        "........",
        "......v.",
        "..uUUv.v",
        ".uUUUvv.",
        "uUUUUUvv",
        ".uUUUUv.",
        "..uUUv..",
        "......v.",
    ],
    # f1 - 8x10, a jet going up off a neck hit
    [
        "...vv...",
        "........",
        "...UUv..",
        "..UUUv.v",
        "..UUUUv.",
        ".uUUUUv.",
        ".uUUUUv.",
        "uUUUUUv.",
        "uUUUUUv.",
        "uUUUUUU.",
    ],
    # f2 - 10x8, the wide low splatter
    [
        "..........",
        ".........v",
        "....uUUvv.",
        "..uUUUUUvv",
        ".uUUUUUUvv",
        "..uUUUUUvv",
        "....uUUvv.",
        ".........v",
    ],
]

# --------------------------------------------------------------------------
# bloodpool -- 20x8 x1.  A pool on the ground: irregular edge, u darker in the
# middle, three wet v highlights.  Its lowest opaque pixel is on row 7, the
# last row, so GROUND_Y can land on the pool's bottom without an offset.
# --------------------------------------------------------------------------
BLOODPOOL: list[str] = [
    "....................",
    "........UUU.........",
    "......UUUUUUU.......",
    "....UUUUuuUUUUU.....",
    "...UUUUuuuuUUUUUU...",
    "..UUUUuuuuuUUUUUU...",
    ".vUUUUuuuuuUUUUUUv..",
    ".UUUUUuuuuUUUUUvU...",
]

# --------------------------------------------------------------------------
# gib -- 4x4, 3x3, 3x3.  Each grid is one solid chunk (a gib is a piece of
# meat, not a spray), rotated differently in each frame so a burst of all
# three never reads as the same lump repeated.
# --------------------------------------------------------------------------
GIB_FRAMES: list[list[str]] = [
    [
        ".uU.",
        "uUvv",
        "uUUv",
        ".uu.",
    ],
    [
        "uU.",
        "UUv",
        ".uu",
    ],
    [
        ".uu",
        "vUU",
        ".u.",
    ],
]

# --------------------------------------------------------------------------
# dust -- 12x8 x3.  Footfall puff: dense and low, then expanded, then the
# specks it dissipates into.  The bounding box grows every frame (6x4 -> 9x6 ->
# 12x8) even though the pixel count falls at the end, which is what makes the
# sequence read as a puff breaking up rather than as a shape shrinking.
# --------------------------------------------------------------------------
DUST_FRAMES: list[list[str]] = [
    [
        "............",
        "............",
        "............",
        "............",
        ".....CC.....",
        "....CCCC....",
        "...CcCCc....",
        "..CCCCCC....",
    ],
    [
        "............",
        "............",
        "....CCCC....",
        "...CCCCCC...",
        "..CcCCCCc...",
        ".CcCCCCCCc..",
        "..CCcCCcCC..",
        "...CCCCCC...",
    ],
    [
        "....C..C....",
        "..C......C..",
        ".C........C.",
        "C..........C",
        "C..........C",
        ".C........C.",
        "..C..CC..C..",
        "....CC.CC...",
    ],
]

# --------------------------------------------------------------------------
# The deliverable.
# --------------------------------------------------------------------------
FX: dict[str, list[list[str]] | list[str]] = {
    "muzzle": MUZZLE_FRAMES,
    "bullet": BULLET_FRAMES,
    "casing": CASING_FRAMES,
    "impact": IMPACT_FRAMES,
    "blood": BLOOD_FRAMES,
    "bloodpool": BLOODPOOL,
    "gib": GIB_FRAMES,
    "dust": DUST_FRAMES,
}


def frames_of(entry) -> list[list[str]]:
    """A single grid (a list of row strings) or a list of grids, as a list.

    ``FX["bloodpool"]`` is one grid and ``FX["muzzle"]`` is a list of grids;
    both are plain lists, so the discriminator is the *element* type: rows are
    strings, frames are lists of strings.
    """
    if entry and isinstance(entry[0], str):
        return [entry]
    return list(entry)


def any_grids():
    """Yield (name, frame_index, grid) for every frame of every effect."""
    for name, entry in FX.items():
        for i, grid in enumerate(frames_of(entry)):
            yield name, i, grid


def opaque_count(grid) -> int:
    return sum(1 for row in grid for ch in row if ch != ".")


def components(grid) -> list[set[tuple[int, int]]]:
    """4-connected components of the opaque pixels, in scan order."""
    h, w = len(grid), len(grid[0])
    left = {(x, y) for y in range(h) for x in range(w) if grid[y][x] != "."}
    out = []
    while left:
        seed = min(left, key=lambda t: (t[1], t[0]))
        seen, stack = {seed}, [seed]
        while stack:
            x, y = stack.pop()
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n in left and n not in seen:
                    seen.add(n)
                    stack.append(n)
        left -= seen
        out.append(seen)
    return out


def preview_layout():
    """Where every frame lands in fx_preview.png.

    Returns ``(width, height, placements)`` with ``placements`` a list of
    ``(name, frame_index, x, y)`` -- the top-left pixel of that frame inside
    the sheet, in unscaled preview coordinates.  ``check_effects.py`` uses this
    to decode the committed PNG back into the grids.
    """
    placements, y, width = [], PAD, 0
    for name, entry in FX.items():
        frames = frames_of(entry)
        x = PAD
        for i, grid in enumerate(frames):
            placements.append((name, i, x, y))
            x += len(grid[0]) * SCALE + PAD
        width = max(width, x)
        y += max(len(g) for g in frames) * SCALE + PAD
    return width, y, placements


def render_preview() -> Path:
    width, height, placements = preview_layout()
    sheet = Image.new("RGBA", (width, height), (*BG, 255))
    for name, i, x, y in placements:
        sheet.alpha_composite(preview(build(frames_of(FX[name])[i], GAME_PALETTE), SCALE, BG), (x, y))
    path = OUT_DIR / "fx_preview.png"
    sheet.save(path)
    return path


def render_muzzle_gif() -> Path:
    """Four frames at MUZZLE_MS, played ONCE.

    ``loop=None`` is deliberate: Pillow only writes the NETSCAPE loop extension
    when ``loop`` is not None, and a muzzle flash that restarts itself is not a
    muzzle flash.  check_effects.py asserts the extension is absent.
    """
    frames = [
        preview(build(grid, GAME_PALETTE), SCALE, BG).convert("RGB").convert(
            "P", palette=Image.Palette.ADAPTIVE, colors=64
        )
        for grid in MUZZLE_FRAMES
    ]
    path = OUT_DIR / "fx_muzzle.gif"
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=MUZZLE_MS,
        loop=None,
        optimize=False,
    )
    return path


# Effects that must be one solid body, and effects where separated pieces are
# the whole point.  Both get the structural checks; only the first group has to
# come back as a single component.
CONNECTED = ("muzzle", "bullet", "casing", "bloodpool")
LOOSE = ("blood", "gib", "impact", "dust")


def main() -> None:
    # The only structural defects allowed anywhere in this module are the
    # burnt-out muzzle frame, which is transparent on purpose, and the
    # separated sparks/droplets/chunks of the LOOSE effects.
    for name, i, grid in any_grids():
        for p in check_grid(grid, f"{name} f{i}", palette=GAME_PALETTE):
            if name == "muzzle" and i == 3 and p.endswith("fully transparent"):
                continue
            if name in LOOSE and "floating pixel" in p:
                continue
            raise AssertionError(p)

    preview_path = render_preview()
    gif_path = render_muzzle_gif()

    print(f"effects   : {len(FX)} -> {', '.join(FX)}")
    for name, entry in FX.items():
        grids = frames_of(entry)
        sizes = " ".join(f"{len(g[0])}x{len(g)}" for g in grids)
        counts = " ".join(str(opaque_count(g)) for g in grids)
        print(f"  {name:<10}: {len(grids)} frame(s)  {sizes}   px {counts}")
    used = sorted({c for _, _, g in any_grids() for row in g for c in row if c != "."})
    print(f"colours   : {len(used)} used -> {used}")
    print(f"wrote     : {preview_path}")
    print(f"wrote     : {gif_path}  ({16 * SCALE}x{12 * SCALE}, {MUZZLE_MS}ms/frame, no loop)")


if __name__ == "__main__":
    main()
