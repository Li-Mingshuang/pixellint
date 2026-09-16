"""Integrity + readability checks for the four scenery props (props.py).

Pixel art is deterministic, so everything that decides whether a prop reads can
be asserted instead of eyeballed:

  * size and shape      - each grid is exactly the stated WxH, every row the
                          stated width, only SCENE_PALETTE keys
  * single body         - one connected opaque blob, no floating pixels
  * outline coverage    - every opaque pixel that faces background (a
                          transparent neighbour, or the canvas edge) is K, so
                          no prop can leak a raw fill colour into the grass or
                          the sky
  * BASE convention     - the lowest opaque row is the row that sits on the
                          ground, and it is outline-or-background only
  * colour separation   - Lab dE76 for every pair of colours that actually touch,
                          against SCENE_TIERS
  * fence tiling        - column 31 joined to column 0 stays readable, and so
                          does a full second tile (proves seamlessness)
  * reported geometry   - the chimney's column range / flue row and the fence
                          tile width match the pixels they claim to describe
  * rendered artifact   - assets/props_preview.png decodes back to the authored
                          pixels, and every prop's base row really does land on
                          the single shared baseline

Run after any tweak to props.py.
"""

from pathlib import Path

from PIL import Image

from pixelkit import SCENE_PALETTE, SCENE_TIERS, check_grid, report_separation, preview
from props import (
    BASES,
    CHIMNEY_CAP_COLS,
    CHIMNEY_CAP_ROW,
    CHIMNEY_FLUE_COLS,
    CHIMNEY_FLUE_ROW,
    FENCE,
    FENCE_BASE_ROW,
    FENCE_MEMBER_COLS,
    FENCE_TILE_W,
    FENCE_W,
    GRASS_BG,
    HOUSE,
    HOUSE_BASE_ROW,
    HOUSE_H,
    HOUSE_W,
    PREVIEW_SCALE,
    PROPS,
    ROCK,
    ROCK_BASE_ROW,
    ROCK_H,
    ROCK_W,
    SIZES,
    TREE,
    TREE_BASE_ROW,
    TREE_H,
    TREE_TRUNK_COLS,
    TREE_W,
    compose_preview,
    preview_layout,
    render_preview,
)

ASSETS = Path(__file__).resolve().parent / "assets"

EXPECTED_SIZES = {
    "tree": (28, 40),
    "house": (46, 34),
    "fence": (32, 14),
    "rock": (14, 10),
}
EXPECTED_BASES = {"tree": 39, "house": 33, "fence": 13, "rock": 9}

NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def check_size(label: str, grid: list[str], w: int, h: int) -> list[str]:
    problems = []
    if (w, h) != EXPECTED_SIZES[label]:
        problems.append(f"{label}: declared size {w}x{h}, expected {EXPECTED_SIZES[label]}")
    if len(grid) != h:
        problems.append(f"{label}: {len(grid)} rows, expected {h}")
    for i, row in enumerate(grid):
        if len(row) != w:
            problems.append(f"{label}: row {i} is {len(row)} cols, expected {w}")
    bad = sorted({c for r in grid for c in r} - set(SCENE_PALETTE))
    if bad:
        problems.append(f"{label}: undefined palette keys {bad}")
    return problems


def check_outline(label: str, grid: list[str], wrap_x: bool = False) -> list[str]:
    """Any opaque pixel facing background must be K.

    `wrap_x` is for a horizontally tileable sprite: its left and right columns
    are a SEAM, not a silhouette, so the horizontal neighbours are taken across
    the wrap and the canvas's left/right edges are not background.  The seam is
    then covered by the fence tiling check instead.
    """
    h, w = len(grid), len(grid[0])
    leaks = []
    for y in range(h):
        for x in range(w):
            if grid[y][x] in (".", "K"):
                continue
            for dx, dy in NEIGHBOURS:
                nx, ny = x + dx, y + dy
                if dx and wrap_x:
                    nx %= w
                elif not (0 <= nx < w):
                    leaks.append((x, y, grid[y][x]))
                    break
                if not (0 <= ny < h) or grid[ny][nx] == ".":
                    leaks.append((x, y, grid[y][x]))
                    break
    if leaks:
        return [f"{label}: {len(leaks)} unoutlined silhouette pixel(s): {leaks[:8]}"]
    return []


def check_base(label: str, grid: list[str], base_row: int) -> list[str]:
    h, w = len(grid), len(grid[0])
    problems = []
    opaque_rows = [y for y in range(h) if any(c != "." for c in grid[y])]
    lowest = max(opaque_rows)
    if lowest != base_row:
        problems.append(f"{label}: lowest opaque row is {lowest}, declared BASE is {base_row}")
    if base_row != h - 1:
        problems.append(f"{label}: BASE {base_row} is not the last row ({h - 1})")
    stray = sorted(set(grid[base_row]) - {".", "K"})
    if stray:
        problems.append(f"{label}: BASE row should be outline/background only, found {stray}")
    return problems


def wrap(grid: list[str], times: int = 1) -> list[str]:
    """Column 31 joined to column 0: the tile seam, then a whole second tile."""
    return [row * (times + 1) for row in grid]


def check_metadata() -> list[str]:
    problems = []
    if (HOUSE_W, HOUSE_H) != EXPECTED_SIZES["house"]:
        problems.append("house: declared W/H wrong")
    if FENCE_TILE_W != FENCE_W:
        problems.append(f"fence: tile width {FENCE_TILE_W} != grid width {FENCE_W}")
    if SIZES != EXPECTED_SIZES:
        problems.append(f"SIZES {SIZES} != {EXPECTED_SIZES}")
    if BASES != EXPECTED_BASES:
        problems.append(f"BASES {BASES} != {EXPECTED_BASES}")

    lo, hi = CHIMNEY_CAP_COLS
    if HOUSE[CHIMNEY_CAP_ROW][lo:hi + 1] != "K" * (hi - lo + 1):
        problems.append(f"chimney: cap row {CHIMNEY_CAP_ROW} cols {lo}-{hi} is not solid K")
    top = min(y for y in range(HOUSE_H) for x in range(lo, hi + 1) if HOUSE[y][x] != ".")
    if top != CHIMNEY_CAP_ROW:
        problems.append(f"chimney: topmost opaque row is {top}, reported {CHIMNEY_CAP_ROW}")

    flo, fhi = CHIMNEY_FLUE_COLS
    if not all(HOUSE[CHIMNEY_FLUE_ROW][c] == "r" for c in range(flo, fhi + 1)):
        problems.append(f"chimney: flue row {CHIMNEY_FLUE_ROW} cols {flo}-{fhi} is not the r mouth")
    if flo <= lo or fhi >= hi:
        problems.append("chimney: flue opening must sit inside the cap's silhouette")
    # the bottom edge staircases down the roof slope: column c ends on row c-25.
    for c in range(lo, hi + 1):
        if HOUSE[c - 25][c] not in "RrK":
            problems.append(f"chimney: col {c} does not end on row {c - 25}")
        if HOUSE[c - 24][c] not in "OoK":
            problems.append(f"chimney: col {c} is not met by roof on row {c - 24}")

    # fence: on row 7 only the members are drawn (the rails run on rows 3-6 and
    # 9-12), so row 7 is where the picket rhythm is read off.  Every gap must be
    # the same width and col 31 must fall in a gap, so the seam joins a gap to
    # the next tile's post outline.
    members_row = FENCE[7]
    declared_members = {x for a, b in FENCE_MEMBER_COLS for x in range(a, b + 1)}
    opaque_cols = {x for x in range(FENCE_W) if members_row[x] != "."}
    if opaque_cols != declared_members:
        extra = sorted(opaque_cols - declared_members)
        missing = sorted(declared_members - opaque_cols)
        problems.append(f"fence: member columns mismatch (missing {missing}, extra {extra})")
    gaps, run = [], 0
    for x in range(FENCE_W):
        if members_row[x] != ".":
            if run:
                gaps.append(run)
            run = 0
        else:
            run += 1
    gaps.append(run)                       # the closing gap wraps onto col 0
    if sorted(set(gaps)) != [3]:
        problems.append(f"fence: gaps between members are {gaps}, expected all 3")
    if FENCE_MEMBER_COLS[0][0] != 0:
        problems.append("fence: the run must start with a member at col 0")
    if not all(FENCE[y][0] == "K" for y in range(len(FENCE))):
        problems.append("fence: col 0 must be the post's outline on every row")
    if FENCE[FENCE_BASE_ROW][FENCE_W - 1] != ".":
        problems.append("fence: col 31 of the BASE row must be gap, or the seam colour-flips")
    return problems


def check_preview() -> tuple[list[str], list[str]]:
    """The PNG on disk must decode back to the authored props, pixel for pixel.

    Rebuilds the expected image from the grids (compose_preview is what
    render_preview draws, so there is one source of truth) and compares EVERY
    pixel, background included: a stray pixel anywhere is a failure, and so is a
    preview left stale by an edit to the grids.
    """
    problems, report = [], []
    path = ASSETS / "props_preview.png"
    if not path.exists():
        path = render_preview()           # fresh checkout: build it once
        report.append("preview  was missing, rendered from props.py")
    img = Image.open(path).convert("RGBA")
    width, height, baseline, xs = preview_layout()

    if img.size != (width * PREVIEW_SCALE, height * PREVIEW_SCALE):
        problems.append(f"preview: size {img.size} != {(width * PREVIEW_SCALE, height * PREVIEW_SCALE)}")
        return problems, report

    expected = preview(compose_preview(), PREVIEW_SCALE, GRASS_BG)
    if list(img.getdata()) != list(expected.getdata()):
        got, want = img.load(), expected.load()
        bad = next((x, y) for y in range(img.height) for x in range(img.width)
                   if got[x, y] != want[x, y])
        x, y = bad
        scale = PREVIEW_SCALE
        problems.append(
            f"preview: pixel ({x},{y}) is {got[x, y]}, expected {want[x, y]} "
            f"-- native ({x // scale},{y // scale}); re-run props.py"
        )

    # the BASE of every prop must sit on the one shared baseline row
    px = img.load()
    for name, grid in PROPS.items():
        col = next((c for c, ch in enumerate(grid[BASES[name]]) if ch == "K"), None)
        if col is None:
            problems.append(f"{name}: BASE row has no K pixel to anchor on")
            continue
        got = px[(xs[name] + col) * PREVIEW_SCALE + PREVIEW_SCALE // 2,
                 baseline * PREVIEW_SCALE + PREVIEW_SCALE // 2]
        if got != SCENE_PALETTE["K"]:
            problems.append(f"{name}: BASE does not land on the shared baseline row (got {got})")
        above = px[(xs[name] + col) * PREVIEW_SCALE + PREVIEW_SCALE // 2,
                   (baseline - 1) * PREVIEW_SCALE + PREVIEW_SCALE // 2]
        if above == (*GRASS_BG, 255):
            problems.append(f"{name}: nothing sits on the baseline at col {col}")

    report.append(f"preview  {img.size[0]}x{img.size[1]} at {PREVIEW_SCALE}x on grass, "
                  f"{len(PROPS)} props on baseline native row {baseline} -> {path.name}")
    return problems, report


def check_canopy_roundness() -> tuple[list[str], list[int]]:
    """A round canopy cannot be a stack of rectangles.

    Reads the canopy's silhouette (rows 0-24, everything above the trunk) and
    asserts the width profile is unimodal, never jumps more than 2px between
    rows, and only holds its full width for a couple of rows.  A square blob
    fails all three.
    """
    canopy = [row for row in TREE[:25]]
    widths = [len(row) - row.index("K") - row[::-1].index("K") for row in canopy]
    problems = []
    peak = widths.index(max(widths))
    if widths[:peak] != sorted(widths[:peak]) or widths[peak:] != sorted(widths[peak:], reverse=True):
        problems.append(f"tree: canopy widths {widths} are not unimodal, so the dome lumps")
    steps = [abs(widths[i + 1] - widths[i]) for i in range(len(widths) - 1)]
    if max(steps) > 2:
        problems.append(f"tree: canopy width jumps {max(steps)}px in one row ({widths})")
    flat = sum(1 for w in widths if w == max(widths))
    if flat > 3:
        problems.append(f"tree: {flat} rows share the full width {max(widths)}, that is a slab")
    for i, row in enumerate(canopy):
        left = row.index("K")
        right = len(row) - row[::-1].index("K") - 1
        if left != 27 - right and abs(left - (27 - right)) > 1:
            problems.append(f"tree: canopy row {i} is off-centre (cols {left}-{right})")
            break
    return problems, widths


def main() -> int:
    problems: list[str] = []
    report: list[str] = []

    declared = {
        "tree": (TREE, TREE_W, TREE_H, TREE_BASE_ROW),
        "house": (HOUSE, HOUSE_W, HOUSE_H, HOUSE_BASE_ROW),
        "fence": (FENCE, FENCE_W, FENCE_TILE_W and len(FENCE), FENCE_BASE_ROW),
        "rock": (ROCK, ROCK_W, ROCK_H, ROCK_BASE_ROW),
    }

    print("-- structure ------------------------------------------------")
    for name, (grid, w, h, base) in declared.items():
        problems += check_size(name, grid, w, h)
        problems += check_grid(grid, name)
        problems += check_outline(name, grid, wrap_x=(name == "fence"))
        problems += check_base(name, grid, base)
        print(f"  {name:<5} {w}x{h}  base row {base}  "
              f"{len({c for r in grid for c in r if c != '.'})} colours"
              + ("  (outline checked across the tile seam)" if name == "fence" else ""))

    print("\n-- colour separation (dE76, adjacent pairs, SCENE_TIERS) ----")
    for name, (grid, *_rest) in declared.items():
        failures, rows = report_separation(grid, name, tiers=SCENE_TIERS)
        problems += failures
        worst = min(rows, key=lambda r: r[3]) if rows else None
        print(f"  {name:<5} {len(rows)} touching pairs, failures {len(failures)}"
              + (f", tightest {worst[1]}-{worst[2]} dE={worst[3]:.1f} (need>={worst[5]:.0f})"
                 if worst else ""))

    print("\n-- fence tiling --------------------------------------------")
    seam_failures, seam_rows = report_separation(wrap(FENCE, 1), "fence+seam", tiers=SCENE_TIERS)
    double_failures, double_rows = report_separation(wrap(FENCE, 2), "fence x3", tiers=SCENE_TIERS)
    problems += seam_failures + double_failures
    print(f"  tile width        : {FENCE_TILE_W} cols (col 31 joins col 0)")
    print(f"  seam pairs        : {len(seam_rows)} checked, {len(seam_failures)} failures")
    print(f"  two full tiles    : {len(double_rows)} pairs checked, {len(double_failures)} failures")
    new_at_seam = set(seam_rows) - set(report_separation(FENCE, "f", tiers=SCENE_TIERS)[1])
    print(f"  pairs new to seam : {sorted({(r[1], r[2]) for r in new_at_seam}) or 'none'}")

    print("\n-- reported geometry ---------------------------------------")
    problems += check_metadata()
    roundness_problems, canopy_widths = check_canopy_roundness()
    problems += roundness_problems
    lo, hi = CHIMNEY_CAP_COLS
    flo, fhi = CHIMNEY_FLUE_COLS
    print(f"  tree canopy widths: {canopy_widths}  (rows 0-24, unimodal, <=2px/row)")
    print(f"  chimney cap       : cols {lo}-{hi} (7px), top row {CHIMNEY_CAP_ROW}, height to row {hi - 24}")
    print(f"  chimney flue      : cols {flo}-{fhi} (5px), top row {CHIMNEY_FLUE_ROW}"
          f"  -> smoke x = house_x+{flo}..house_x+{fhi}, y = house_y+{CHIMNEY_FLUE_ROW}")
    print(f"  fence tile width  : {FENCE_TILE_W} cols; members at "
          + ", ".join(f"{a}-{b}" for a, b in FENCE_MEMBER_COLS))
    print(f"  tree trunk        : cols {TREE_TRUNK_COLS[0]}-{TREE_TRUNK_COLS[1]}, base row {TREE_BASE_ROW}")
    print(f"  house door/window : door cols 11-20, window cols 25-34 rows 20-25")

    print("\n-- rendered preview ----------------------------------------")
    preview_problems, preview_report = check_preview()
    problems += preview_problems
    for line in preview_report:
        print(f"  {line}")

    print()
    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print("  ok    all four props: exact size, palette-closed, single body, outline closed,")
        print("        base row on the ground line, readable under SCENE_TIERS, fence tiles clean")
    print(f"  failures : {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
