"""Scenery props for the pixel scene: tree, cottage, fence section and boulder.

House style (see render_sprite.py): every prop is authored as an explicit list of
equal-length strings where ONE CHARACTER = ONE PIXEL = ONE INDEX INTO
pixelkit.SCENE_PALETTE.  Nothing here invents colour; '.' is transparent.

CONVENTION: the lowest opaque row of each grid is the BASE -- that row sits on
the ground (pixelkit.GROUND_LINE = 79 in the scene) when the prop is placed.

Palette keys actually used, and why:

  TREE   K outline | T/t trunk wood | F/f canopy foliage | G canopy highlight
  HOUSE  K outline | U/u plaster | O/o roof | T/t door + window frame
         R/r stone foundation and chimney | A glass (sky blue)
  FENCE  K outline | T pickets/rails | t shadowed side of every member
  ROCK   K outline | R stone | r stone shadow

Palette pairs that had to be worked around.  These all fail SCENE_TIERS as
material pairs (no shade-pair exemption, and dL too small for the value-step
escape), so they must simply never touch -- check_props.py is what keeps them
apart:

  * wood T may NOT touch wall shadow u (dE 25.7) nor roof shadow o (26.9), so
    each wooden element on the cottage is wrapped in its own K edge and no wood
    is ever placed directly against shaded plaster or shaded roof.
  * wood shadow t may NOT touch u either way, nor canopy shadow f (27.8): the
    canopy underside is a solid K rim (row 24) and the trunk's t only appears
    below it.
  * wall shadow u may NOT touch foundation stone R (27.3), so the wall's right
    shadow band stops on row 28 and the wall base row 29 is plain U.
  * G (grass green) is used for the canopy highlight rather than E: E is the
    grass *blade tip* colour, near-white (L 0.83), and against F it flattens the
    canopy's value ladder.  Nothing in these props is authored as bare grass, so
    G reads as sunlit foliage here.
  * A (sky blue) glass may not touch stone R (27.4) -- it never does, the window
    sits well above the foundation.

Run `python check_props.py` after any tweak; `python props.py` re-renders
assets/props_preview.png.
"""

from pathlib import Path

from pixelkit import SCENE_PALETTE, build, check_grid, preview

OUT_DIR = Path(__file__).resolve().parent / "assets"

# --------------------------------------------------------------------------
# TREE -- 40 rows x 28 cols.  Broad deciduous tree: 25-row canopy dome, an
# 11-row trunk and a 4-row root flare.  Light from the upper-left, so the
# canopy highlight G hugs the top-left rim, the deep foliage shadow f crescents
# through the lower-right, and the trunk keeps T lit / t shadowed.
#
# The dome is deliberately not a stack of rectangles: its per-row widths step
# 10,12,14,16,18,20,21,22,24,25,26,27,28,28,27,26,25,24,23,22,20,19,18,16,14 --
# two pixels at a time at the crown, ONE pixel at a time through the waist, so
# the silhouette curves instead of cornering.  check_props.py asserts the
# profile stays unimodal and never jumps by more than 2px.
# --------------------------------------------------------------------------
TREE: list[str] = [
    ".........KKKKKKKKKK.........",  # 0  crown cap, 10px so row 1 stays outlined
    "........KGGGFFFffffK........",  # 1
    ".......KGGGGFFFfffffK.......",  # 2
    "......KGGGGGFFFFfffffK......",  # 3
    ".....KGGGGGGFFFFffffffK.....",  # 4
    "....KGGGGGGFFFFFfffffffK....",  # 5
    "...KGGGGGGFFFFFffffffffK....",  # 6
    "...KGGGGGGFFFFFFffffffffK...",  # 7
    "..KGGGGGFFFFFFFffffffffffK..",  # 8
    ".KGGGGGFFFFFFFfffffffffffK..",  # 9
    ".KGGGGGFFFFFFFFfffffffffffK.",  # 10
    "KGGGGGFFFFFFFFffffffffffffK.",  # 11
    "KGGGGGFFFFFFFFfffffffffffffK",  # 12 widest, 28px
    "KGGGGFFFFFFFFffffffffffffffK",  # 13
    ".KGGGGFFFFFFFffffffffffffffK",  # 14
    ".KGGGFFFFFFFffffffffffffffK.",  # 15
    "..KGGFFFFFFFffffffffffffffK.",  # 16
    "..KGFFFFFFFffffffffffffffK..",  # 17 highlight band has foreshortened away
    "...KFFFFFFFffffffffffffffK..",  # 18
    "...KFFFFFFffffffffffffffK...",  # 19
    "....KFFFFffffffffffffffK....",  # 20
    ".....KFFFFfffffffffffffK....",  # 21
    ".....KFFFfffffffffffffK.....",  # 22
    "......KFFffffffffffffK......",  # 23
    ".......KKKKKKKKKKKKKK.......",  # 24 solid shadowed underside of the canopy
    "...........KTTTtK...........",  # 25 trunk: K rim, T lit, t shadowed
    "...........KTTTtK...........",  # 26
    "...........KTTTtK...........",  # 27
    "...........KTTTtK...........",  # 28
    "...........KTTTtK...........",  # 29
    "...........KTTTtK...........",  # 30
    "...........KTTTtK...........",  # 31
    "...........KTTTtK...........",  # 32
    "...........KTTTtK...........",  # 33
    "...........KTTTtK...........",  # 34
    "...........KTTTtK...........",  # 35
    "..........KTTTTttK..........",  # 36 root flare begins
    ".........KTTTTTtttK.........",  # 37
    ".........KTTTTTtttK.........",  # 38
    ".........KKKKKKKKKK.........",  # 39 BASE row (10px of wood sitting on grass)
]

TREE_W, TREE_H = 28, 40
TREE_BASE_ROW = TREE_H - 1
TREE_TRUNK_COLS = (11, 16)        # inclusive, K rim to K rim

# --------------------------------------------------------------------------
# HOUSE -- 34 rows x 46 cols.  Pitched roof on a plaster cottage with a stone
# foundation, a plank door, a blue-glass window and a stone chimney standing on
# the shadowed (right) slope.
#
# CHIMNEY GEOMETRY, for the scene's smoke emitter.  All values are sprite-native
# (0-based rows and cols); if the cottage is placed at (house_x, house_y):
#
#   cap / outer silhouette : cols 32-38, top row 2
#   FLUE OPENING (the hole) : cols 33-37, top row 3   <-- release smoke here
#
#   so smoke pixels belong at scene x = house_x + 33 .. house_x + 37,
#   scene y = house_y + 3 (the mouth's own row; the cap above it is row 2).
#   The chimney is 7px wide and 12 rows tall, and its bottom edge is a staircase
#   that follows the roof slope -- column c ends on row c-25 -- with the roof
#   reading in front of it below that.
# --------------------------------------------------------------------------
HOUSE: list[str] = [
    "..............................................",  # 0
    "..............................................",  # 1
    "................................KKKKKKK.......",  # 2  chimney cap
    "..................KKKKKKKKKK....KrrrrrK.......",  # 3  ridge cap + flue mouth
    ".................KOOOOOoooooK...KrrrrrK.......",  # 4
    "................KOOOOOOooooooK..KRRRrrK.......",  # 5
    "...............KOOOOOOOoooooooK.KRRRrrK.......",  # 6
    "..............KOOOOOOOOooooooooKKRRRrrK.......",  # 7
    ".............KOOOOOOOOOoooooooooKRRRrrK.......",  # 8
    "............KOOOOOOOOOOooooooooooKRRrrK.......",  # 9  chimney meets the slope
    "...........KOOOOOOOOOOOoooooooooooKRrrK.......",  # 10
    "..........KOOOOOOOOOOOOooooooooooooKrrK.......",  # 11
    ".........KOOOOOOOOOOOOOoooooooooooooKrK.......",  # 12
    "........KOOOOOOOOOOOOOOooooooooooooooKK.......",  # 13
    ".......KOOOOOOOOOOOOOOOoooooooooooooooK.......",  # 14
    "......KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK......",  # 15 eave line
    "........KuuuuuuuuuuuuuuuuuuuuuuuuuuuuK........",  # 16 shade under the eaves
    "........KUUUUUUUUUUUUUUUUUUUUUUUUUUuuK........",  # 17 plaster wall
    "........KUUUUUUUUUUUUUUUUUUUUUUUUUUuuK........",  # 18
    "........KUUUUUUUUUUUUUUUUUUUUUUUUUUuuK........",  # 19
    "........KUUKKKKKKKKKKUUUUKKKKKKKKKKuuK........",  # 20 door + window lintels
    "........KUUKTTTTTtttKUUUUKTAAAAAAtKuuK........",  # 21 door leaf T/t, glass A
    "........KUUKTTTTTtttKUUUUKTAAAAAAtKuuK........",  # 22
    "........KUUKTTTTTtttKUUUUKTAAAAAAtKuuK........",  # 23
    "........KUUKTTTTTtttKUUUUKTAAAAAAtKuuK........",  # 24
    "........KUUKTTTTTtKtKUUUUKKKKKKKKKKuuK........",  # 25 knob (K) + window sill
    "........KUUKTTTTTtttKUUUUUUUUUUUUUUuuK........",  # 26
    "........KUUKTTTTTtttKUUUUUUUUUUUUUUuuK........",  # 27
    "........KUUKTTTTTtttKUUUUUUUUUUUUUUuuK........",  # 28
    "........KUUKTTTTTtttKUUUUUUUUUUUUUUUUK........",  # 29 wall base is U, never u
    ".......KRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRK.......",  # 30 stone foundation
    ".......KRRRRRRrRRRRRRRRRRRrRRRRRRRRRRRK.......",  # 31 seams r
    ".......KrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrK.......",  # 32 shadowed bottom course
    ".......KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK.......",  # 33 BASE row
]

HOUSE_W, HOUSE_H = 46, 34
HOUSE_BASE_ROW = HOUSE_H - 1
CHIMNEY_CAP_COLS = (32, 38)      # inclusive: outer silhouette of the cap
CHIMNEY_CAP_ROW = 2
CHIMNEY_FLUE_COLS = (33, 37)     # inclusive: the opening smoke rises from
CHIMNEY_FLUE_ROW = 3
DOOR_COLS = (11, 20)             # inclusive, K frame to K frame
WINDOW_COLS = (25, 34)
WINDOW_ROWS = (20, 25)

# --------------------------------------------------------------------------
# FENCE -- 14 rows x 32 cols, HORIZONTALLY TILEABLE: column 31 is a gap column
# and column 0 is the K edge of a post, so N copies side by side give a
# continuous run with one post every 32px and a 3px gap between members.
#
# Members are K, T, T, t, K -- lit left, shadowed right, outlined both sides,
# and 5px of solid K on the BASE row: a capped post at cols 0-4 (full height)
# and pickets at cols 8-12, 16-20, 24-28 (tips on row 2).  Two rails run the
# full width behind them, rows 3-6 and rows 9-12, each K / T / t / K, so the
# rails read continuously through the gaps and across the tile seam.
# --------------------------------------------------------------------------
FENCE: list[str] = [
    "KKKKK...........................",  # 0  post cap
    "KTTtK...........................",  # 1
    "KTTtK...KKKKK...KKKKK...KKKKK...",  # 2  picket tips
    "KTTtKKKKKTTtKKKKKTTtKKKKKTTtKKKK",  # 3  top rail, upper edge
    "KTTtKTTTKTTtKTTTKTTtKTTTKTTtKTTT",  # 4  top rail
    "KTTtKtttKTTtKtttKTTtKtttKTTtKttt",  # 5  top rail, shadowed under-edge
    "KTTtKKKKKTTtKKKKKTTtKKKKKTTtKKKK",  # 6  top rail, lower edge
    "KTTtK...KTTtK...KTTtK...KTTtK...",  # 7  open run between the rails
    "KTTtK...KTTtK...KTTtK...KTTtK...",  # 8
    "KTTtKKKKKTTtKKKKKTTtKKKKKTTtKKKK",  # 9  bottom rail, upper edge
    "KTTtKTTTKTTtKTTTKTTtKTTTKTTtKTTT",  # 10 bottom rail
    "KTTtKtttKTTtKtttKTTtKtttKTTtKttt",  # 11 bottom rail, shadowed under-edge
    "KTTtKKKKKTTtKKKKKTTtKKKKKTTtKKKK",  # 12 bottom rail, lower edge
    "KKKKK...KKKKK...KKKKK...KKKKK...",  # 13 BASE row
]

FENCE_W, FENCE_H = 32, 14
FENCE_TILE_W = 32                 # columns; column 31 joins column 0 seamlessly
FENCE_BASE_ROW = FENCE_H - 1
FENCE_MEMBER_COLS = ((0, 4), (8, 12), (16, 20), (24, 28))

# --------------------------------------------------------------------------
# ROCK -- 10 rows x 14 cols.  Rounded boulder: lit upper-left, r shadow
# lower-right, flat-ish 12px base that tucks a pixel in at each bottom corner.
# --------------------------------------------------------------------------
ROCK: list[str] = [
    "....KKKKKK....",  # 0
    "...KRRRRrrK...",  # 1
    "..KRRRRRrrrK..",  # 2
    "..KRRRRRrrrK..",  # 3
    ".KRRRRRRrrrrK.",  # 4
    ".KRRRRRRrrrrK.",  # 5
    "KRRRRRRRrrrrrK",  # 6
    "KRRRRRRRrrrrrK",  # 7
    "KRRRRRRRrrrrrK",  # 8
    ".KKKKKKKKKKKK.",  # 9  BASE row: flat, 12px wide
]

ROCK_W, ROCK_H = 14, 10
ROCK_BASE_ROW = ROCK_H - 1

PROPS: dict[str, list[str]] = {"tree": TREE, "house": HOUSE, "fence": FENCE, "rock": ROCK}
SIZES: dict[str, tuple[int, int]] = {
    "tree": (TREE_W, TREE_H),
    "house": (HOUSE_W, HOUSE_H),
    "fence": (FENCE_W, FENCE_H),
    "rock": (ROCK_W, ROCK_H),
}
BASES: dict[str, int] = {
    "tree": TREE_BASE_ROW,
    "house": HOUSE_BASE_ROW,
    "fence": FENCE_BASE_ROW,
    "rock": ROCK_BASE_ROW,
}

GRASS_BG = SCENE_PALETTE["G"][:3]     # the backdrop the scene's ground uses
PREVIEW_SCALE = 6
GAP = 6                               # transparent columns between props
PAD = 4                               # transparent rows above and below


def preview_layout() -> tuple[int, int, int, dict[str, int]]:
    """(width, height, baseline_row, {name: x}) of the native preview canvas."""
    order = ["tree", "house", "fence", "rock"]
    width = sum(SIZES[n][0] for n in order) + GAP * (len(order) - 1) + PAD * 2
    height = max(SIZES[n][1] for n in order) + PAD * 2
    xs, x = {}, PAD
    for name in order:
        xs[name] = x
        x += SIZES[name][0] + GAP
    return width, height, height - 1 - PAD, xs


def compose_preview() -> "Image.Image":
    """Native-resolution canvas: all four props side by side on one baseline."""
    from PIL import Image

    width, height, baseline, xs = preview_layout()
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for name, x in xs.items():
        canvas.alpha_composite(build(PROPS[name]), (x, baseline - BASES[name]))
    return canvas


def render_preview(path: Path | None = None, scale: int = PREVIEW_SCALE) -> Path:
    """All four props side by side at `scale`x on grass, on one shared baseline."""
    out = Path(path) if path else OUT_DIR / "props_preview.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    preview(compose_preview(), scale, GRASS_BG).save(out)
    return out


def main() -> None:
    for name, grid in PROPS.items():
        w, h = SIZES[name]
        assert len(grid) == h, f"{name}: {len(grid)} rows, expected {h}"
        assert all(len(r) == w for r in grid), f"{name}: not every row is {w} wide"
        problems = check_grid(grid, name)
        assert not problems, problems
        assert grid[BASES[name]].count(".") + grid[BASES[name]].count("K") == w, \
            f"{name}: BASE row must be outline or background only"
    path = render_preview()
    print("props : " + ", ".join(f"{n} {SIZES[n][0]}x{SIZES[n][1]}" for n in PROPS))
    print(f"wrote : {path}")


if __name__ == "__main__":
    main()
