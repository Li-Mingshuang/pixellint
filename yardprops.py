"""Larger rural scenery props: a stone well, a haystack, a scarecrow, a cart.

House style (see props.py, render_sprite.py): every prop is authored as an
explicit list of equal-length strings where ONE CHARACTER = ONE PIXEL = ONE
INDEX INTO pixelkit.SCENE_PALETTE.  Nothing here invents colour; '.' is
transparent.

CONVENTION (same as props.py): the lowest opaque row of each grid is the BASE --
that row sits on the ground (pixelkit.GROUND_LINE = 79 in the scene) wherever the
prop is placed.  Every one of the four grids ends on its own bottom row, so a
composer can put all four on one baseline and none of them floats.

LIGHT: upper-left, always.  Highlights hug the upper-left rim, shadows the
lower-right, on every prop -- the well's roof is O on the left slope and o on the
right, its rim stone is R left / r right; the haystack is E/Y straw upper-left
running to n/t lower-right; the scarecrow's shirt is P left / p right; the
wagon's planks are T on top and t underneath, its wheels R on the lit rim and r
on the shadowed one.

Palette keys used, and why:

  WELL      K outline | R/r stone rim | t well mouth, rope and shading
            T/t uprights + windlass | O/o roof | U/u bucket
  HAYSTACK  K outline | E/Y lit straw | N/n shaded thatch | t ground shadow
  SCARECROW K outline | T/t cross frame | P/p shirt | U/u straw head
            t stitched mouth | Y straw fringe
  WAGON     K outline | T/t bed, planks, spokes, drawbar | N cargo
            R/r iron wheel rims

Palette pairs that had to be worked around.  These fail the SEP_RULES `fill`
floor (dE76 < 12 with no lightness escape), so they must simply never touch --
check_yardprops.py is what keeps them apart:

  * P may not touch T (9.0) and p may not touch t (9.9): the scarecrow's shirt
    and its cross frame are different browns at the same lightness.  Every shirt
    edge is therefore its own K garment edge, so the frame is only ever met by
    K, never by P or p.
  * T may not touch n (11.9) and N may not touch u (12.0): the wagon's cargo is
    a K-sealed heap inside a T bed (N-T alone is a warning at 17.5), and the
    well's bucket never meets dirt.  The haystack carries no wood at all, so its
    deep straw shade n can never land beside a T.
  * p may not touch n (8.0): the scarecrow has no dirt-brown in it.

Run `python check_yardprops.py` after any tweak; `python yardprops.py` re-renders
assets/yardprops_preview.png.
"""

from pathlib import Path

from pixelkit import SCENE_PALETTE, build, check_grid, preview

OUT_DIR = Path(__file__).resolve().parent / "assets"

# --------------------------------------------------------------------------
# WELL -- 22 rows x 20 cols.  Four stacked pieces so the silhouette can never
# read as one grey lump: a small pitched O/o roof (rows 0-4), its eave, two T/t
# uprights with a T windlass bar slung between them, a U bucket on a t rope, and
# an 18px stone rim whose top surface is an ellipse in R/r around a 10px dark t
# mouth.
#
# The rim is built as an arch, not a band: row 16 is the back cap (the bucket's
# base lands on it), rows 17-19 are the ring itself -- stone on both flanks with
# the t mouth between -- row 20 is the front course that closes the hole, and row
# 21 is the contact outline.  check_yardprops.py asserts the mouth really is an
# ellipse (8 / 10 / 8 px across rows 17-19) and that stone flanks it on both
# sides on every one of those rows.
# --------------------------------------------------------------------------
WELL: list[str] = [
    "........KKKK........",  # 0  roof ridge cap
    ".......KOOooK.......",  # 1  lit left slope O, shadowed right slope o
    "......KOOOoooK......",  # 2
    ".....KOOOOooooK.....",  # 3
    "....KOOOOOoooooK....",  # 4  widest roof course, 12px
    "..KKKKKKKKKKKKKKKK..",  # 5  eave: overhangs the uprights by 1px each side
    "..KTtK........KTtK..",  # 6  uprights, K rim / T lit / t shadowed / K rim
    "..KTtK........KTtK..",  # 7
    "..KTtKKKKKKKKKKTtK..",  # 8  windlass bar (3 courses) slung between them
    "..KTtKTTTTTTttKTtK..",  # 9  bar body: T lit to the left, t in shadow
    "..KTtKKKKKKKKKKTtK..",  # 10
    "..KTtK...KtK..KTtK..",  # 11 t rope, 3px so it can carry its own outline
    "..KTtK...KtK..KTtK..",  # 12
    "..KTtK.KKKKKK.KTtK..",  # 13 bucket mouth
    "..KTtK.KUUuuK.KTtK..",  # 14 bucket: U lit left, u shadowed right
    "..KKKK.KUUuuK.KKKK..",  # 15 upright feet are solid K
    "....KKKKKKKKKKKK....",  # 16 back cap of the rim, meeting the bucket base
    "..KKRRttttttttrrKK..",  # 17 rim ring: R lit flank, 8px t mouth, r shadow
    ".KRRRttttttttttrrrK.",  # 18 the mouth is widest here, 10px
    ".KRRRRttttttttrrrrK.",  # 19 tapers back to 8px: an ellipse, not a slot
    ".KRRRRRRRRRrrrrrrrK.",  # 20 rim wall, closing the hole from the front
    ".KKKKKKKKKKKKKKKKKK.",  # 21 BASE row: the well sits on this line
]

WELL_W, WELL_H = 20, 22
WELL_BASE_ROW = WELL_H - 1
WELL_ROOF_ROWS = (0, 4)           # inclusive: the pitched O/o roof
WELL_EAVE_ROW = 5
WELL_UPRIGHT_COLS = ((2, 5), (14, 17))
WELL_WINDLASS_ROWS = (8, 10)      # inclusive: bar courses
WELL_ROPE_COLS = (9, 11)          # inclusive: hangs from the bar's centre
WELL_BUCKET_COLS = (7, 12)        # inclusive: the U bucket
WELL_BUCKET_ROWS = (13, 16)
WELL_RIM_COLS = (1, 18)           # inclusive: outer silhouette at its widest
WELL_RIM_TOP_ROW = 16             # back cap; the bucket's base merges into it
WELL_MOUTH_COLS = (5, 14)         # inclusive: widest row of the dark opening
WELL_MOUTH_ROWS = (17, 19)        # inclusive: the t mouth, 3 rows tall

# --------------------------------------------------------------------------
# HAYSTACK -- 18 rows x 24 cols.  PROCEDURAL, then frozen: the dome spans and
# the thatch tones below are generated by gen_yardprops.py (a light ramp from the
# upper-left -- E lit straw, Y, N, n -- plus a period-7 dark strand and a period-5
# lit strand, +0.40 on the bottom two rows for the ground shadow) and the literal
# grid here is the frozen output, exactly the way sky.py holds frozen literals.
# Re-run `python gen_yardprops.py` to check this grid still matches the recipe.
#
# The silhouette is a dome that bulges to 22px and tucks back to 20 at the base;
# its edge jitters by 1-2px from row to row and the outline pass turns every fill
# pixel that faces the sky into K, which is what gives the ragged thatch edge.
# Rows 15-16 carry the t/n ground shadow and row 17 is the contact outline.
# --------------------------------------------------------------------------
HAYSTACK: list[str] = [
    ".........KKKKKK.........",  # 0  crown cap, 6px
    "........KEEENYNKK.......",  # 1  E sunlit straw hugging the upper-left
    ".......KEEYYYYNNNK......",  # 2
    ".....KKEYYYYYYNnNK......",  # 3  left edge juts out 2px: ragged
    ".....KYEYEYYYNYNNNK.....",  # 4
    "....KEEYYYYNYNNNNNnK....",  # 5
    "...KEEEYYNYYYNNNnNNNKK..",  # 6  right edge juts out: ragged
    "...KEYYYYYYYYNNNNNNnK...",  # 7
    "..KEYYYYYYYNNYNNNNNnnK..",  # 8
    ".KYYEYYYYYNNNNNNNnnNnK..",  # 9
    ".KYYYYYYNYYNNNNnNNNnNnK.",  # 10 widest, 22px
    ".KYYYYNYYNNYNnNNNNnnnnK.",  # 11
    ".KEYNYYYYNNNNNNNNNnnnnK.",  # 12
    ".KYYYYYYYNNNNNNNnnNnnnK.",  # 13
    ".KYYYYYNNYNNNNnNnnnNntK.",  # 14
    ".KNNNnNNNnNntnnnntttttK.",  # 15 thatch darkens into the ground shadow
    "..KnnnnnnttntttttttttK..",  # 16
    "..KKKKKKKKKKKKKKKKKKKK..",  # 17 BASE row: the whole 20px footprint
]

HAYSTACK_W, HAYSTACK_H = 24, 18
HAYSTACK_BASE_ROW = HAYSTACK_H - 1
HAYSTACK_CROWN_ROW = 0
HAYSTACK_BASE_COLS = (2, 21)      # inclusive: the footprint on the BASE row
HAYSTACK_WIDEST_COLS = (1, 22)    # inclusive: the belly, rows 10-15
HAYSTACK_SHADOW_ROWS = (15, 16)   # inclusive: t/n ground shadow above the base

# --------------------------------------------------------------------------
# SCARECROW -- 30 rows x 14 cols.  Stake T/t over a K row; U/u straw-stuffed
# head on rows 3-12 with K eyes on row 7 and a t stitched mouth on row 9; the
# cross frame is a 3-course T/t bar on rows 13-15 running the full 14px width;
# a P/p shirt hangs from it to row 24, and Y straw fringe sticks out of the two
# cuffs (rows 16-18) and the ragged hem (row 25).
#
# The shirt is drawn with a K edge of its own wherever it meets the frame --
# that is not decoration, it is the only thing keeping P (9.0) and p (9.9) off
# T and t.
# --------------------------------------------------------------------------
SCARECROW: list[str] = [
    "......KK......",  # 0  stake tip
    ".....KTtK.....",  # 1  stake, T lit left / t shadowed right
    ".....KTtK.....",  # 2
    ".....KKKK.....",  # 3  head crown cap
    "....KUUuuK....",  # 4  straw-stuffed head, lit upper-left
    "...KUUUUuuK...",  # 5
    "..KUUUUUUuuK..",  # 6
    "..KUUKUUKUuK..",  # 7  K eyes
    "..KUUUUUUuuK..",  # 8
    "..KUUttttUuK..",  # 9  t stitched mouth
    "..KUUUUUUuuK..",  # 10
    "...KUUUUuuK...",  # 11 chin tapers
    "....KUUuuK....",  # 12
    "KKKKKKKKKKKKKK",  # 13 crossbar, upper face
    "KTTKPPPPppKttK",  # 14 bare frame T at the left wrist, t at the right; sleeves
    "KKKKKKKKKKKKKK",  # 15 crossbar, lower face
    "KYYKKPPppKKYYK",  # 16 straw fringe at both cuffs
    "KYK.KPPppK.KYK",  # 17 ... ragged: the left tooth hangs a row longer
    "KK..KPPppK..KK",  # 18
    "...KPPPPppK...",  # 19 shirt body
    "...KPPPPppK...",  # 20
    "...KPPPPppK...",  # 21
    "...KPPPPppK...",  # 22
    "...KYKYYKYK...",  # 23 ragged straw hem
    "...KKKKKKKK...",  # 24 hem's K bottom edge
    ".....KTtK.....",  # 25 stake below the shirt
    ".....KTtK.....",  # 26
    ".....KTtK.....",  # 27
    ".....KTtK.....",  # 28
    ".....KKKK.....",  # 29 BASE row: the stake is driven in on this line
]

SCARECROW_W, SCARECROW_H = 14, 30
SCARECROW_BASE_ROW = SCARECROW_H - 1
SCARECROW_STAKE_COLS = (5, 8)       # inclusive, K rim to K rim
SCARECROW_HEAD_ROWS = (3, 12)       # inclusive
SCARECROW_EYE_ROW = 7
SCARECROW_MOUTH_ROW = 9
SCARECROW_CROSSBAR_ROWS = (13, 15)  # inclusive: the arms bar
SCARECROW_SHIRT_ROWS = (13, 24)     # inclusive: from the shoulders to the hem
SCARECROW_SHIRT_COLS = (4, 9)       # inclusive: the body under the shoulders
SCARECROW_FRINGE_ROWS = (16, 18)    # inclusive: cuff straw; hem straw is row 23

# --------------------------------------------------------------------------
# WAGON -- 18 rows x 28 cols.  Side view, front to the RIGHT: a K-sealed N
# cargo heap on rows 0-3, a plank bed 22px wide on rows 4-10, two 9px spoked
# wheels whose upper two rows are hidden behind the bed, and a T/t drawbar that
# leaves the bed's lower-right corner and steps down to the ground clearance.
#
# WHEEL GEOMETRY: 9x9, drawn at rows 9-17 (wheel row = scene row - 9) and cols
# 2-10 / 13-21.  The rim is R on the lit upper-left and r on the shadowed
# lower-right, the interior is t with a T cross of spokes and a T hub on wheel
# row 4 (scene row 13), and each wheel rests on 3px of K at scene row 17.
#
# DRAWBAR OVERHANG: the drawbar is the only part of the wagon that reaches past
# the bed.  WAGON_BED_COLS says the bed ends at col 22; the bar runs cols 23-27,
# so WAGON_DRAWBAR_OVERHANG = 5px beyond the bed's right edge, and it is 5px
# taller bar-stepping down 1px per 2 columns from rows 7-11 to rows 9-13.
# --------------------------------------------------------------------------
WAGON: list[str] = [
    "..........KKKK..............",  # 0  cargo heap, K-sealed
    ".........KNNNNK.............",  # 1
    "........KNNNNNNK............",  # 2
    ".......KNNNNNNNNK...........",  # 3
    ".KKKKKKKKKKKKKKKKKKKKKK.....",  # 4  top rail, full 22px bed width
    ".KTTTTTtTTTTTTTTtTTTTTK.....",  # 5  plank bed, t seams at cols 7 and 16
    ".KTTTTTtTTTTTTTTttttttK.....",  # 6  the shadow line sweeps left as it falls
    ".KTTTTTtTTttttttttttttKKK...",  # 7  ... and the T drawbar leaves here
    ".KttttttttttttttttttttKTTKK.",  # 8  bed underside in shadow
    ".KttttttttttttttttttttKTTTTK",  # 9
    ".KKKKKKKKKKKKKKKKKKKKKKttttK",  # 10 bed floor; the wheels start behind it
    "...KRtTtrK....KRtTtrK..KKttK",  # 11 wheel row 2: rim R lit / r shadowed
    "..KRttTttrK..KRttTttrK...KKK",  # 12 wheel row 3
    "..KRTTTTtrK..KRTTTTtrK.....K",  # 13 wheel row 4: the T spokes cross the hub
    "..KRttTttrK..KRttTttrK......",  # 14
    "...KRtTtrK....KRtTtrK.......",  # 15
    "....KRRrK......KRRrK........",  # 16
    ".....KKK........KKK.........",  # 17 BASE row: both wheels rest here
]

WAGON_W, WAGON_H = 28, 18
WAGON_BASE_ROW = WAGON_H - 1
WAGON_CARGO_COLS = (7, 16)          # inclusive: visible heap above the rail
WAGON_BED_COLS = (1, 22)            # inclusive: the bed box
WAGON_BED_ROWS = (4, 10)            # inclusive
WAGON_WHEEL_COLS = ((2, 10), (13, 21))
WAGON_WHEEL_D = 9                   # a wheel is 9x9, drawn at rows 9-17
WAGON_WHEEL_TOP_ROW = 9
WAGON_WHEEL_HUB_ROW = 13            # scene row of the hub / spoke cross
WAGON_DRAWBAR_COLS = (23, 27)       # inclusive: where it leaves the bed
WAGON_DRAWBAR_ROWS = (7, 13)        # inclusive: rows it sweeps through
WAGON_DRAWBAR_OVERHANG = WAGON_DRAWBAR_COLS[1] - WAGON_BED_COLS[1]   # 5px

PROPS: dict[str, list[str]] = {
    "well": WELL,
    "haystack": HAYSTACK,
    "scarecrow": SCARECROW,
    "wagon": WAGON,
}
SIZES: dict[str, tuple[int, int]] = {
    "well": (WELL_W, WELL_H),
    "haystack": (HAYSTACK_W, HAYSTACK_H),
    "scarecrow": (SCARECROW_W, SCARECROW_H),
    "wagon": (WAGON_W, WAGON_H),
}
BASES: dict[str, int] = {
    "well": WELL_BASE_ROW,
    "haystack": HAYSTACK_BASE_ROW,
    "scarecrow": SCARECROW_BASE_ROW,
    "wagon": WAGON_BASE_ROW,
}

GRASS_BG = SCENE_PALETTE["G"][:3]     # the backdrop the scene's ground uses
PREVIEW_SCALE = 5
GAP = 6                               # transparent columns between props
PAD = 4                               # transparent rows above and below


def preview_layout() -> tuple[int, int, int, dict[str, int]]:
    """(width, height, baseline_row, {name: x}) of the native preview canvas."""
    order = ["well", "haystack", "scarecrow", "wagon"]
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
    out = Path(path) if path else OUT_DIR / "yardprops_preview.png"
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
    print("yardprops : " + ", ".join(f"{n} {SIZES[n][0]}x{SIZES[n][1]}" for n in PROPS))
    print(f"wrote     : {path}")


if __name__ == "__main__":
    main()
