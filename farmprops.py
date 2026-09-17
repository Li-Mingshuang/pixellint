"""Utilitarian farmyard props: barrel, crate, signpost, stump, log pile, churn.

Sibling of props.py and authored the same way (see render_sprite.py): every prop
is an explicit list of equal-length strings where ONE CHARACTER = ONE PIXEL = ONE
INDEX INTO pixelkit.SCENE_PALETTE.  Nothing here invents colour; '.' is
transparent; the silhouette is closed with `K`.

CONVENTION: the lowest opaque row of each grid is its own last row -- the BASE --
so the prop stands on the ground on whatever row it is placed against
(pixelkit.GROUND_LINE = 79 in the scene).  The BASE row is outline/background
only, like props.py, so a prop always ends on a clean dark footprint.

LIGHT: upper-left, scene-wide.  Every prop keeps its lit side up-and-left and its
shadow (`t`, `r`, `u`) down-and-right: barrel/crate/signpost/post wood is T on
the left and t on the right, the stump's cut face is u-ringed with its wood
shadow on the right, the log pile's logs are T on top and t underneath, and the
churn is R with the r shadow on its right flank.  Nothing here is centre-lit, so
nothing contradicts the tree, fence or cottage it will stand next to.

Palette keys used, and why:

  BARREL    K outline | T/t staves | R/r iron hoops
  CRATE     K outline | T/t slats, t for the gaps between them
  SIGNPOST  K outline | T/t post and board | t for the carved line on the board
  STUMP     K outline | T body, t shadow | U pale cut face, u growth ring
            | F shoots off the flanks
  LOGPILE   K outline | T bark, t shadowed underside | U cut end, u its shadow
  MILKCHURN K outline | R body, r shadow | W metal highlight

No hard separation failures against SCENE_PALETTE: the only fill pairs that
*fail* anywhere near this set are T-n and u-N (both dirt), and no prop here is
ever placed against dirt -- they stand on grass, on their own K footprint.
Warnings are left alone on purpose: U-u (the stump's pale ring, dE 20.8) and K-f
are the palette telling the truth about a shade ramp, not a defect.

THE BRIEF'S `M` HIGHLIGHT DOES NOT EXIST.  SCENE_PALETTE has no uppercase M --
the only M-family key is lowercase `m`, the character's MOUTH (0x8c4436, a dull
brick red), which is useless as a metal specular.  The churn therefore uses `W`
(0xfbf8f0), the palette's pale key and the natural read for a tin highlight; it
is called out in check_farmprops.py so the substitution is visible rather than
silent.

Run `python check_farmprops.py` after any tweak; `python farmprops.py` re-renders
assets/farmprops_preview.png.
"""

from pathlib import Path

from pixelkit import SCENE_PALETTE, build, check_grid, preview

# What this module delivers. The rest of what it defines is either a
# composition block or a lookup table, and measuring those double-counts or
# misfires -- see docs/authoring.md.
SHIPPED = ('BARREL', 'CRATE', 'SIGNPOST', 'STUMP', 'LOGPILE', 'MILKCHURN',)


OUT_DIR = Path(__file__).resolve().parent / "assets"

# --------------------------------------------------------------------------
# BARREL -- 14 rows x 10 cols.  A staved barrel with iron hoops top and bottom:
# the top hoop is 8px, the middle four body rows bulge to the full 10px, the
# lower hoop is 10px, and the bottom four rows taper back to 8px, so the
# silhouette curves instead of reading as a tub.  Staves read off the one t
# seam at col 4 and the shadowed right flank (cols 6-8).
#
# GEOMETRY: the two iron hoops are BARREL_HOOP_ROWS = (1, 2) and (7, 8); the
# BASE row is a flat 8px footprint (cols 1-8) so the barrel cannot look tipped.
# --------------------------------------------------------------------------
BARREL: list[str] = [
    "..KKKKKK..",  # 0  top rim (6px opening)
    ".KRRRRrrK.",  # 1  upper iron hoop
    ".KRRRRrrK.",  # 2
    "KTTtTTtttK",  # 3  body bulges to the full 10px
    "KTTtTTtttK",  # 4
    "KTTtTTtttK",  # 5
    "KTTtTTtttK",  # 6
    "KRRRRRrrrK",  # 7  lower iron hoop
    "KRRRRRrrrK",  # 8
    ".KTTtTttK.",  # 9  taper back in below the hoop
    ".KTTtTttK.",  # 10
    ".KTTtTttK.",  # 11
    ".KTTtTttK.",  # 12
    ".KKKKKKKK.",  # 13 BASE row: flat 8px footprint, 1px tucked in per corner
]

BARREL_W, BARREL_H = 10, 14
BARREL_BASE_ROW = BARREL_H - 1
BARREL_HOOP_ROWS = ((1, 2), (7, 8))
BARREL_FOOT_COLS = (1, 8)         # inclusive, the BASE row's footprint

# --------------------------------------------------------------------------
# CRATE -- 11 rows x 12 cols.  Slatted crate: three horizontal boards, each two
# lit rows deep, separated by a one-row gap of solid t, with the front face lit
# T on the left eight columns and t on the right two.  The outline is a plain
# rectangle (cols 0 and 11, rows 0 and 10), which is what makes a crate read as
# a crate; the slat rhythm is what stops it reading as a box.
# --------------------------------------------------------------------------
CRATE: list[str] = [
    "KKKKKKKKKKKK",  # 0  top rim
    "KTTTTTTTTttK",  # 1  slat 1, upper row (lit)
    "KTTTTTTTTttK",  # 2  slat 1, lower row
    "KttttttttttK",  # 3  gap between slats 1 and 2
    "KTTTTTTTTttK",  # 4  slat 2
    "KTTTTTTTTttK",  # 5
    "KttttttttttK",  # 6  gap
    "KTTTTTTTTttK",  # 7  slat 3
    "KTTTTTTTTttK",  # 8
    "KttttttttttK",  # 9  shadowed bottom course
    "KKKKKKKKKKKK",  # 10 BASE row: full-width footprint
]

CRATE_W, CRATE_H = 12, 11
CRATE_BASE_ROW = CRATE_H - 1
CRATE_SLAT_ROWS = ((1, 2), (4, 5), (7, 8))
CRATE_GAP_ROWS = (3, 6, 9)

# --------------------------------------------------------------------------
# SIGNPOST -- 20 rows x 8 cols.  A 4px post (cols 2-5) carrying a small 8px
# board across rows 3-7: the board is bracketed across the post rather than
# slung from it, because at 8px a board hanging on a visible hook would cost the
# only column the board has room to overhang with.  It still reads as a hanging
# sign because the board is twice the post's width and overhangs it on both
# sides, and because the post runs on above the board (rows 0-2) as well as
# below it -- neither of which a fixed notice board would do.
#
# Row 5 is the weathered/carved line on the board (a solid t band between two T
# rows), and rows 9, 14 are grain bands down the post.  Two 1px chips
# (SIGNPOST_CHIP_ROWS) bite the post's right edge on row 12 and its left edge on
# row 16 so the post reads as weathered rather than as a clean batten.
# --------------------------------------------------------------------------
SIGNPOST: list[str] = [
    "..KKKK..",  # 0  post cap
    "..KTtK..",  # 1
    "..KTtK..",  # 2
    "KKKKKKKK",  # 3  board, top edge
    "KTTTTTtK",  # 4  board face (lit upper-left, t down the right)
    "KTtttttK",  # 5  carved line
    "KTTTTTtK",  # 6  board face
    "KKKKKKKK",  # 7  board, bottom edge
    "..KTtK..",  # 8  post continues
    "..KttK..",  # 9  grain band
    "..KTtK..",  # 10
    "..KTtK..",  # 11
    "..KTK...",  # 12 chip: the post loses its shadowed column
    "..KTtK..",  # 13
    "..KttK..",  # 14 grain band
    "..KTtK..",  # 15
    "...KtK..",  # 16 chip: the post loses its lit column
    "..KTtK..",  # 17
    "..KTtK..",  # 18
    "..KKKK..",  # 19 BASE row: the post's own 4px footprint
]

SIGNPOST_W, SIGNPOST_H = 8, 20
SIGNPOST_BASE_ROW = SIGNPOST_H - 1
SIGNPOST_POST_COLS = (2, 5)       # inclusive, K rim to K rim
SIGNPOST_BOARD_ROWS = (3, 7)      # inclusive; the board is the full 8px there
SIGNPOST_CHIP_ROWS = (12, 16)

# --------------------------------------------------------------------------
# STUMP -- 9 rows x 12 cols.  A cut stump: three rows of pale cut face on top
# (U with a u growth ring round a U pith), a 8px wood body below it (T lit
# left, t shadowed right) and a 10px root flare on the BASE row.  Two F shoots
# sucker off the flanks at rows 5-7 -- each is a K cap with F beneath it, tucked
# against the body's own K rim, so they are part of the one connected body and
# still outlined where they face grass.
#
# GEOMETRY: the cut face is STUMP_FACE_ROWS = (1, 3) and the widest row of the
# face (cols 1-10) overhangs the body by 1px per side, the way an old cut face
# stands proud of eroded bark.
# --------------------------------------------------------------------------
STUMP: list[str] = [
    "...KKKKKK...",  # 0  back rim of the cut face
    "...KuuuuK...",  # 1  face: the u growth ring
    "..KuuUUuuK..",  # 2  face: ring closes round a pale U pith
    ".KuuUUUUuuK.",  # 3  face at its widest, overhanging the bark
    "..KTTTtttK..",  # 4  bark: T lit left, t shadowed right
    ".KKTTTtttKKK",  # 5  K = the caps of both shoots
    "KFKTTTtttKFK",  # 6  F = the shoots themselves
    "KFKTTTtttKFK",  # 7
    ".KKKKKKKKKK.",  # 8  BASE row: 10px root flare
]

STUMP_W, STUMP_H = 12, 9
STUMP_BASE_ROW = STUMP_H - 1
STUMP_FACE_ROWS = (1, 3)          # inclusive, the pale U cut face
STUMP_SHOOT_COLS = (1, 10)        # the F column of the left and right shoot
STUMP_FOOT_COLS = (1, 10)         # inclusive, the BASE row's root flare

# --------------------------------------------------------------------------
# LOGPILE -- 10 rows x 16 cols.  Four logs in two tiers, cut ends toward the
# viewer: the lower tier is two 8px logs on rows 5-9, the upper tier two 6px
# logs on rows 0-4, inset 2px per side, so the stack steps in like a pile
# instead of a wall of bricks.  Each log is a rounded bar -- its first and last
# row are inset 1px per side -- with T bark, a U cut end (u on the shadowed
# lower row) at its right end, and its whole underside in t: that t under every
# log is the shading *between* the logs, which is what separates them without a
# second outline.  The upper tier's K caps land directly on the lower tier's K
# caps, so all four logs are one connected body with one closed silhouette.
# --------------------------------------------------------------------------
LOGPILE: list[str] = [
    "...KKKK..KKKK...",  # 0  upper tier: top rims of the two 6px logs
    "..KTTUUKKTTUUK..",  # 1
    "..KTTUUKKTTUUK..",  # 2
    "..KttuuKKttuuK..",  # 3  underside in shadow, cut end's lower half in u
    "...KKKK..KKKK...",  # 4
    ".KKKKKK..KKKKKK.",  # 5  lower tier: top rims of the two 8px logs
    "KTTTTUUKKTTTTUUK",  # 6
    "KTTTTUUKKTTTTUUK",  # 7
    "KttttuuKKttttuuK",  # 8
    ".KKKKKK..KKKKKK.",  # 9  BASE row: 12px across the two footprints
]

LOGPILE_W, LOGPILE_H = 16, 10
LOGPILE_BASE_ROW = LOGPILE_H - 1
LOGPILE_TIER_ROWS = ((0, 4), (5, 9))   # inclusive, upper tier then lower tier
LOGPILE_LOGS = 4
LOGPILE_FOOT_COLS = ((1, 6), (9, 14))  # inclusive, the BASE row's footprints

# --------------------------------------------------------------------------
# MILKCHURN -- 12 rows x 8 cols.  A tin churn: a 4px lid on top, a pinched
# neck (the narrowest row, cols 2-5), then a 6px body running down to the BASE
# row.  The W highlight is the 1px specular column at col 2, hard against the
# upper-left rim, with R through the middle and r down the right flank -- R/W/r
# is the whole metal ramp and there is no W anywhere near the bottom.
#
# GEOMETRY: the small handles are 1px tabs (MILKCHURN_HANDLE_ROWS) at cols 0
# and 7.  They are drawn in R, not K, on purpose: a K tab against the body's own
# K rim would be invisible, so the tab is metal and the K that outlines it is the
# silhouette pixel outside it.
# --------------------------------------------------------------------------
MILKCHURN: list[str] = [
    "..KKKK..",  # 0  lid rim (4px)
    ".KWRRrK.",  # 1  lid
    ".KKKKKK.",  # 2  lid skirt / seam onto the neck
    "..KRrK..",  # 3  neck, the narrowest row
    ".KWRRrK.",  # 4  shoulder
    ".KWRRrK.",  # 5
    "KRWRRrRK",  # 6  handles
    "KRWRRrRK",  # 7  handles
    ".KWRRrK.",  # 8  body
    ".KWRRrK.",  # 9
    ".KRRrrK.",  # 10 base course, no highlight, r moving in from the right
    ".KKKKKK.",  # 11 BASE row: 6px footprint
]

MILKCHURN_W, MILKCHURN_H = 8, 12
MILKCHURN_BASE_ROW = MILKCHURN_H - 1
MILKCHURN_NECK_ROW = 3
MILKCHURN_HANDLE_ROWS = (6, 7)
MILKCHURN_FOOT_COLS = (1, 6)      # inclusive, the BASE row's footprint

FARMPROPS: dict[str, list[str]] = {
    "barrel": BARREL,
    "crate": CRATE,
    "signpost": SIGNPOST,
    "stump": STUMP,
    "logpile": LOGPILE,
    "milkchurn": MILKCHURN,
}
SIZES: dict[str, tuple[int, int]] = {
    "barrel": (BARREL_W, BARREL_H),
    "crate": (CRATE_W, CRATE_H),
    "signpost": (SIGNPOST_W, SIGNPOST_H),
    "stump": (STUMP_W, STUMP_H),
    "logpile": (LOGPILE_W, LOGPILE_H),
    "milkchurn": (MILKCHURN_W, MILKCHURN_H),
}
BASES: dict[str, int] = {
    "barrel": BARREL_BASE_ROW,
    "crate": CRATE_BASE_ROW,
    "signpost": SIGNPOST_BASE_ROW,
    "stump": STUMP_BASE_ROW,
    "logpile": LOGPILE_BASE_ROW,
    "milkchurn": MILKCHURN_BASE_ROW,
}

GRASS_BG = SCENE_PALETTE["G"][:3]     # the backdrop the scene's ground uses
PREVIEW_SCALE = 6
GAP = 6                               # transparent columns between props
PAD = 4                               # transparent rows above and below

PREVIEW_ORDER = ["barrel", "crate", "signpost", "stump", "logpile", "milkchurn"]


def preview_layout() -> tuple[int, int, int, dict[str, int]]:
    """(width, height, baseline_row, {name: x}) of the native preview canvas."""
    width = sum(SIZES[n][0] for n in PREVIEW_ORDER) + GAP * (len(PREVIEW_ORDER) - 1) + PAD * 2
    height = max(SIZES[n][1] for n in PREVIEW_ORDER) + PAD * 2
    xs, x = {}, PAD
    for name in PREVIEW_ORDER:
        xs[name] = x
        x += SIZES[name][0] + GAP
    return width, height, height - 1 - PAD, xs


def compose_preview() -> "Image.Image":
    """Native-resolution canvas: all six props side by side on one baseline."""
    from PIL import Image

    width, height, baseline, xs = preview_layout()
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for name, x in xs.items():
        canvas.alpha_composite(build(FARMPROPS[name]), (x, baseline - BASES[name]))
    return canvas


def render_preview(path: Path | None = None, scale: int = PREVIEW_SCALE) -> Path:
    """All six props side by side at `scale`x on grass, on one shared baseline."""
    out = Path(path) if path else OUT_DIR / "farmprops_preview.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    preview(compose_preview(), scale, GRASS_BG).save(out)
    return out


def main() -> None:
    for name, grid in FARMPROPS.items():
        w, h = SIZES[name]
        assert len(grid) == h, f"{name}: {len(grid)} rows, expected {h}"
        assert all(len(r) == w for r in grid), f"{name}: not every row is {w} wide"
        problems = check_grid(grid, name)
        assert not problems, problems
        assert grid[BASES[name]].count(".") + grid[BASES[name]].count("K") == w, \
            f"{name}: BASE row must be outline or background only"
    path = render_preview()
    print("farmprops : " + ", ".join(f"{n} {SIZES[n][0]}x{SIZES[n][1]}" for n in FARMPROPS))
    print(f"wrote     : {path}")


if __name__ == "__main__":
    main()
