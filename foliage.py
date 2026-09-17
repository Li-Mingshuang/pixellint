"""Small foliage details for the pixel scene, plus one animated critter.

House style (see render_sprite.py and props.py): every prop is authored as an
explicit list of equal-length strings where ONE CHARACTER = ONE PIXEL = ONE
INDEX INTO ``pixelkit.SCENE_PALETTE``.  Nothing is computed at build time --
what you read below is exactly what gets rasterised -- and '.' is transparent.

Deliverables
------------
  BUSH          18x14, ONE grid   rounded leafy bush
  FLOWERPATCH   16x8,  ONE grid   low scattered clump of flowers and grass
  MUSHROOMS     10x8,  ONE grid   three mushrooms of different heights
  CHICKEN       12x10, FOUR frames, side view facing right, pecking idle

CONVENTION: the lowest opaque row of every grid is the BASE -- that row sits on
the ground (``pixelkit.GROUND_LINE`` = 79 in the scene) when the prop is placed.
For CHICKEN the base row *is* the ground row, and it never changes: a hen pecks,
it does not hop.

Palette keys actually used, and why:

  BUSH         F body | f underside shadow | G sunlit highlights upper-left
               | t woody stems at the base
  FLOWERPATCH  G/g grass blades | E pale stems | Y yellow head | y pink head
  MUSHROOMS    U caps | O/o cap spots | u stems | g grass base
  CHICKEN      K outline + eye | U/u body | O/o comb and wattle | Y beak + legs

Separation notes (``python check_foliage.py`` keeps these honest):

  * Nothing here needs a K rim the way the fence and the cottage did.  Foliage
    is read against grass, and F against the grass backdrop G is dE 48.3 with a
    0.29 luminance step, so the bush holds its own silhouette without an
    outline; the mushrooms are the same story in reverse, U against grass G at
    dE 53.9.
  * The one tight pair that genuinely cannot be designed away is U-u (dE 20.8,
    dL 0.22) where each mushroom's cap meets its own stem.  A cap has to sit on
    its stem, so this pair is left as a WARNING rather than being fenced off
    with an invented outline colour: a shade that close to its own base is what
    a shade is for.
  * BUSH never mixes F/f against the grass g: the stems are t (wood), which is
    dE 42.2 from F and 27.8 from f, both clear -- an earlier draft had the stems
    as g and the bush grew a second, invisible silhouette.
  * CHICKEN's comb/wattle o against the outline K is the tightest pair on the
    bird at dE 31.3, which clears the 20 outline floor.  Y next to o (80.0) and
    U next to u (20.8, the belly under the breast) are the same story: tight but
    readable, and both are shading rather than edges.

Run ``python foliage.py`` to re-render assets/foliage_preview.png and
assets/chicken.gif; run ``python check_foliage.py`` after any tweak.
"""

from pathlib import Path

from PIL import Image

from pixelkit import SCENE_PALETTE, build, check_grid, preview

OUT_DIR = Path(__file__).resolve().parent / "assets"

# --------------------------------------------------------------------------
# BUSH -- 14 rows x 18 cols.  Rounded leafy bush with no outline: the body F
# carries the silhouette against the grass, the sunlit G clump hugs the
# upper-left rim and the f shadow swallows the whole underside, out of which
# three t woody stems stand on the base row.
#
# The dome is not a stack of rectangles.  Per-row opaque widths step
# 6,10,13,14,16,17,18,18,17,15,13,11,9 so the crown curves in two pixels at a
# time and the waist closes one pixel at a time; the G highlight is 14 pixels
# total, walking down the left edge from cols 6-7 to col 0 and then gone.
# --------------------------------------------------------------------------
BUSH: list[str] = [
    "......GGFFff......",  # 0  crown cap
    "....GGGFFFFfff....",  # 1
    "...GGGFFFFFFFfff..",  # 2
    "..GGGFFFFFFFFFff..",  # 3
    ".GGFFFFFFFFFFffff.",  # 4
    "GFFFFFFFFFFFFffff.",  # 5  left edge reaches col 0
    "FFFFFFFFFFFFFfffff",  # 6  widest, 18px
    "FFFFFFFFFFFfffffff",  # 7
    ".FFFFFFFFFFfffffff",  # 8  highlight has foreshortened away
    "..FFFFFFFFfffffff.",  # 9
    "...FFFFFFfffffff..",  # 10
    "....fffffffffff...",  # 11 underside in full shadow
    ".....ftfftfftf....",  # 12 stems breaking out of the shadow
    ".....tt.tt.tt.....",  # 13 BASE row: three woody feet on the grass
]

BUSH_W, BUSH_H = 18, 14
BUSH_BASE_ROW = BUSH_H - 1
BUSH_STEM_COLS = (6, 9, 12)       # the t columns the stems rise through

# --------------------------------------------------------------------------
# FLOWERPATCH -- 8 rows x 16 cols.  A low, scattered clump rather than a hedge:
# the two flower heads sit at different heights and different columns, the
# tufts run to four different heights, and the base row is two 2px notches
# short of solid.  Those notches are what keep it from reading as a lawn
# edge -- and rows 6 bridges them, which is also what keeps the whole patch a
# single connected body.  check_foliage.py asserts that connectivity.
#
#   rows 0-2  Y head (11px diamond, cols 4-8) on the E stem in col 6
#   rows 1-3  y head (9px block, cols 11-13) on the E stem in col 12
#   rows 3-7  tufts left (cols 1-2), middle (cols 8-9), right (cols 14-15)
#   row  7    BASE row, g, with notches at cols 4-5 and cols 10-11
# --------------------------------------------------------------------------
FLOWERPATCH: list[str] = [
    ".....YYY........",  # 0  yellow head tip
    "....YYYYY..yyy..",  # 1  yellow head widest; pink head begins
    ".....YYY...yyy..",  # 2
    "..G...E....yyy.G",  # 3  left blade tip G; Y stem; pink head base
    ".gg...E.....E.gg",  # 4  pink head is done, its E stem starts
    ".gg...E.Gg..E.gg",  # 5  middle tuft tip
    ".gggggEgggggEggg",  # 6  low grass -- bridges the two base notches
    "gggg..gggg..gggg",  # 7  BASE row
]

FLOWERPATCH_W, FLOWERPATCH_H = 16, 8
FLOWERPATCH_BASE_ROW = FLOWERPATCH_H - 1
FLOWERPATCH_STEM_COLS = (6, 12)   # the E stems the two heads stand on

# --------------------------------------------------------------------------
# MUSHROOMS -- 8 rows x 10 cols.  Three mushrooms of three heights on one g
# grass base row: a tall one (cap rows 0-1, 5-row stem), a medium one (cap
# rows 2-3, 3-row stem) and a short button (cap rows 4-5, 1-row stem).
#
# The caps are U with O/o spots and the stems u -- note that the cap/stem joint
# is the palette's one tight pair (U-u, dE 20.8).  That is allowed to stand:
# check_foliage.py reports it as a warning, not a failure, and fencing it with
# an outline would be drawing around a checker rather than drawing a mushroom.
# Nothing else touches: U-O 57.8, o-U 68.8, u-g 45.5, U-G 53.9.
# --------------------------------------------------------------------------
MUSHROOMS: list[str] = [
    "UUU.......",  # 0  tall cap: crown
    "UOU.......",  # 1  tall cap: O spot
    ".u..UUU...",  # 2  tall stem; medium cap crown
    ".u..oOU...",  # 3  medium cap: o and O spots
    ".u...u.UUU",  # 4  short cap crown
    ".u...u.UOo",  # 5  short cap: O and o spots
    "gugggugugu",  # 6  grass tufts between the three stems
    "gggggggggg",  # 7  BASE row
]

MUSHROOMS_W, MUSHROOMS_H = 10, 8
MUSHROOMS_BASE_ROW = MUSHROOMS_H - 1
MUSHROOM_STEM_COLS = (1, 5, 8)    # tall, medium and short stem columns

PLANTS: dict[str, list[str]] = {
    "bush": BUSH,
    "flowerpatch": FLOWERPATCH,
    "mushrooms": MUSHROOMS,
}
SIZES: dict[str, tuple[int, int]] = {
    "bush": (BUSH_W, BUSH_H),
    "flowerpatch": (FLOWERPATCH_W, FLOWERPATCH_H),
    "mushrooms": (MUSHROOMS_W, MUSHROOMS_H),
}
BASES: dict[str, int] = {
    "bush": BUSH_BASE_ROW,
    "flowerpatch": FLOWERPATCH_BASE_ROW,
    "mushrooms": MUSHROOMS_BASE_ROW,
}
PLANT_ORDER = ["bush", "flowerpatch", "mushrooms"]

# --------------------------------------------------------------------------
# CHICKEN -- 10 rows x 12 cols, FOUR frames, side view FACING
# RIGHT.  A small hen: U body over a u belly, O/o comb and wattle, Y beak and
# legs, K outline and a single K eye.
#
# The cycle is a pecking idle and it obeys the two rules dog.py obeys, which
# check_foliage.py asserts rather than trusting:
#
#   * the HEAD block is the same 4x4 byte window in all four frames and only
#     ever moves by whole ROWS.  The check scans every row *and* every column
#     offset to prove it never drifts sideways (dx == 0 in every frame).
#   * the feet land on row 9 in every frame.  The hen pecks; it does not hop.
#
# Everything outside the head and the 1px neck is planted: rows 5-7 of the
# body, the tail at rows 3-4, the legs and the feet are byte-identical in all
# four frames.  The neck is the column of U at col 7 between the head's back
# and the body's shoulder; it shortens by one row per step of the dip and is
# gone by the deepest frame, which is what makes the peck read as the head
# coming down on a neck rather than as a head sliding down a pole.
# --------------------------------------------------------------------------
CHICKEN_W, CHICKEN_H = 12, 10
CHICKEN_GROUND_ROW = CHICKEN_H - 1        # row 9: both feet, every frame

#   r0  .OO.   comb                r2  KUKY   eye (K) + beak tip (Y)
#   r1  KUUK   crown + outline     r3  .Koo   jaw outline + wattle
HEAD = [
    ".OO.",
    "KUUK",
    "KUKY",
    ".Koo",
]
HEAD_COL = 8          # x of HEAD[0][0]
HEAD_W = len(HEAD[0])  # 4
HEAD_H = len(HEAD)     # 4

# Whole-row offsets of the head block per frame: stand, dip 1, beak down 3,
# rise to 2.  Four DIFFERENT poses -- offsets 0,2,4,2 would make frames 1 and 3
# the same picture -- with steps of 1,2,1,2 rows, so the pixel churn per step
# stays within a factor of 1.7 of the smallest step.
CHICKEN_HEAD_ROWS = (0, 1, 3, 2)

# The neck: col-7 U pixels between the head and the body's shoulder.  Frame 2
# (the deepest dip) needs none -- the hen's head is tucked against its breast.
CHICKEN_NECK_ROWS = ((2, 3, 4), (3, 4), (4,), ())

CHICKEN: list[list[str]] = [
    # frame 0 - stand: head up, 3-row neck
    [
        ".........OO.",  # 0  comb
        "........KUUK",  # 1  crown
        ".......UKUKY",  # 2  neck U | eye K | beak Y
        "uu.....U.Koo",  # 3  tail tip | neck | jaw + wattle
        ".uu....U....",  # 4  tail | neck base
        "..KUUUUK....",  # 5  shoulder
        ".KUUUUUK....",  # 6  breast
        "KuuuuuuK....",  # 7  belly, in shadow
        "...Y..Y.....",  # 8  legs
        "..YYY.YYY...",  # 9  GROUND row: both feet planted
    ],
    # frame 1 - dip: head one row down, neck two rows
    [
        "............",  # 0
        ".........OO.",  # 1  comb
        "........KUUK",  # 2  crown
        "uu.....UKUKY",  # 3  tail | neck | eye + beak
        ".uu....U.Koo",  # 4  tail | neck | jaw + wattle
        "..KUUUUK....",  # 5
        ".KUUUUUK....",  # 6
        "KuuuuuuK....",  # 7
        "...Y..Y.....",  # 8
        "..YYY.YYY...",  # 9
    ],
    # frame 2 - beak down: head three rows down, no neck left, mouth at row 6
    [
        "............",  # 0
        "............",  # 1
        "............",  # 2
        "uu.......OO.",  # 3  tail | comb
        ".uu.....KUUK",  # 4  tail | crown
        "..KUUUUKKUKY",  # 5  shoulder touches the head's back | eye + beak
        ".KUUUUUK.Koo",  # 6  breast | jaw + wattle down at the grass
        "KuuuuuuK....",  # 7
        "...Y..Y.....",  # 8
        "..YYY.YYY...",  # 9
    ],
    # frame 3 - rise: head two rows down, one row of neck back
    [
        "............",  # 0
        "............",  # 1
        ".........OO.",  # 2  comb
        "uu......KUUK",  # 3  tail | crown
        ".uu....UKUKY",  # 4  tail | neck | eye + beak
        "..KUUUUK.Koo",  # 5  shoulder | jaw + wattle
        ".KUUUUUK....",  # 6
        "KuuuuuuK....",  # 7
        "...Y..Y.....",  # 8
        "..YYY.YYY...",  # 9
    ],
]

CHICKEN_FRAME_MS = 160
CHICKEN_SCALE = 8
CHICKEN_BG = SCENE_PALETTE["G"][:3]     # grass green, so the hen is judged on grass

GRASS_BG = SCENE_PALETTE["G"][:3]       # the backdrop the scene's ground uses
PREVIEW_SCALE = 6
GAP = 6                                 # transparent columns between plants
PAD = 6                                 # transparent rows above and below


def preview_layout() -> tuple[int, int, int, dict[str, int]]:
    """(width, height, baseline_row, {name: x}) of the native preview canvas."""
    width = sum(SIZES[n][0] for n in PLANT_ORDER) + GAP * (len(PLANT_ORDER) - 1) + PAD * 2
    height = max(SIZES[n][1] for n in PLANT_ORDER) + PAD * 2
    xs, x = {}, PAD
    for name in PLANT_ORDER:
        xs[name] = x
        x += SIZES[name][0] + GAP
    return width, height, height - 1 - PAD, xs


def compose_preview() -> Image.Image:
    """Native-resolution canvas: all three plants side by side on one baseline."""
    width, height, baseline, xs = preview_layout()
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for name, x in xs.items():
        canvas.alpha_composite(build(PLANTS[name]), (x, baseline - BASES[name]))
    return canvas


def render_preview(path: Path | None = None, scale: int = PREVIEW_SCALE) -> Path:
    """The three static plants side by side at `scale`x on grass, one baseline."""
    out = Path(path) if path else OUT_DIR / "foliage_preview.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    preview(compose_preview(), scale, GRASS_BG).save(out)
    return out


def render_chicken_gif(path: Path | None = None, scale: int = CHICKEN_SCALE) -> Path:
    """The 4-frame peck as a looping GIF, one lap per CHICKEN_FRAME_MS."""
    out = Path(path) if path else OUT_DIR / "chicken.gif"
    out.parent.mkdir(parents=True, exist_ok=True)
    frames = [
        preview(build(grid), scale, CHICKEN_BG).convert("RGB").convert(
            "P", palette=Image.Palette.ADAPTIVE, colors=64
        )
        for grid in CHICKEN
    ]
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=CHICKEN_FRAME_MS,
        loop=0,
        optimize=False,
    )
    return out


def main() -> None:
    for name, grid in PLANTS.items():
        w, h = SIZES[name]
        assert len(grid) == h, f"{name}: {len(grid)} rows, expected {h}"
        assert all(len(r) == w for r in grid), f"{name}: not every row is {w} wide"
        problems = check_grid(grid, name)
        assert not problems, problems
    for i, grid in enumerate(CHICKEN):
        assert len(grid) == CHICKEN_H and all(len(r) == CHICKEN_W for r in grid), \
            f"chicken f{i}: grid must be {CHICKEN_W}x{CHICKEN_H}"
        problems = check_grid(grid, f"chicken f{i}")
        assert not problems, problems

    preview_path = render_preview()
    gif_path = render_chicken_gif()

    print("plants: " + ", ".join(f"{n} {SIZES[n][0]}x{SIZES[n][1]}" for n in PLANT_ORDER))
    print(f"chicken: {CHICKEN_W}x{CHICKEN_H} x {len(CHICKEN)} frames, feet on row "
          f"{CHICKEN_GROUND_ROW}, head rows {list(CHICKEN_HEAD_ROWS)}")
    print(f"wrote : {preview_path}")
    print(f"wrote : {gif_path}  ({CHICKEN_W * CHICKEN_SCALE}x{CHICKEN_H * CHICKEN_SCALE}, "
          f"{CHICKEN_FRAME_MS}ms/frame)")


if __name__ == "__main__":
    main()
