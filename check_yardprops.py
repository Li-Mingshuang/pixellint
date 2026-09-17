"""Integrity + readability checks for the four large rural props (yardprops.py).

Pixel art is deterministic, so everything that decides whether a prop reads can
be asserted instead of eyeballed:

  * size and shape      - each grid is exactly the stated WxH, every row the
                          stated width, only SCENE_PALETTE keys
  * single body         - one connected opaque blob, no floating pixels
  * outline coverage    - every opaque pixel that faces background (a
                          transparent neighbour, or the canvas edge) is K, so no
                          prop can leak a raw fill colour into the grass or sky
  * BASE convention     - the lowest opaque row is the last row of the grid, so
                          every prop stands on the ground wherever it is placed,
                          and the BASE row itself is outline-or-background only
  * colour separation   - Lab dE76 for every pair of colours that actually touch,
                          against the shared SEP_RULES, with the tightest pair
                          per prop reported
  * reported geometry   - every geometry constant yardprops.py exports is checked
                          against the pixels it claims to describe: the well's
                          elliptical mouth and its stone flanks, the scarecrow's
                          eyes / mouth / crossbar / shirt / fringe, the wagon's
                          drawbar overhang and its wheel hubs, the haystack's
                          footprint and the raggedness of its edge
  * documented escapes  - the pairs the module docstring says are kept apart
                          (P/p against the scarecrow's T/t frame above all) are
                          asserted to still be apart
  * rendered artifact   - assets/yardprops_preview.png decodes back to the
                          authored pixels, and every prop's base row really does
                          land on the single shared baseline

Run after any tweak to yardprops.py.
"""

from pathlib import Path

from PIL import Image

from pixelkit import SCENE_PALETTE, SCENE_TIERS, check_grid, report_separation, preview
from yardprops import (
    BASES,
    GRASS_BG,
    HAYSTACK,
    HAYSTACK_BASE_COLS,
    HAYSTACK_BASE_ROW,
    HAYSTACK_CROWN_ROW,
    HAYSTACK_H,
    HAYSTACK_SHADOW_ROWS,
    HAYSTACK_W,
    HAYSTACK_WIDEST_COLS,
    PREVIEW_SCALE,
    PROPS,
    SCARECROW,
    SCARECROW_BASE_ROW,
    SCARECROW_CROSSBAR_ROWS,
    SCARECROW_EYE_ROW,
    SCARECROW_FRINGE_ROWS,
    SCARECROW_H,
    SCARECROW_MOUTH_ROW,
    SCARECROW_SHIRT_COLS,
    SCARECROW_SHIRT_ROWS,
    SCARECROW_STAKE_COLS,
    SCARECROW_W,
    SIZES,
    WAGON,
    WAGON_BASE_ROW,
    WAGON_BED_COLS,
    WAGON_BED_ROWS,
    WAGON_CARGO_COLS,
    WAGON_DRAWBAR_COLS,
    WAGON_DRAWBAR_OVERHANG,
    WAGON_DRAWBAR_ROWS,
    WAGON_H,
    WAGON_W,
    WAGON_WHEEL_COLS,
    WAGON_WHEEL_HUB_ROW,
    WAGON_WHEEL_TOP_ROW,
    WELL,
    WELL_BASE_ROW,
    WELL_BUCKET_COLS,
    WELL_BUCKET_ROWS,
    WELL_EAVE_ROW,
    WELL_H,
    WELL_MOUTH_COLS,
    WELL_MOUTH_ROWS,
    WELL_RIM_COLS,
    WELL_RIM_TOP_ROW,
    WELL_ROOF_ROWS,
    WELL_ROPE_COLS,
    WELL_UPRIGHT_COLS,
    WELL_W,
    WELL_WINDLASS_ROWS,
    compose_preview,
    preview_layout,
    render_preview,
)

ASSETS = Path(__file__).resolve().parent / "assets"

EXPECTED_SIZES = {
    "well": (20, 22),
    "haystack": (24, 18),
    "scarecrow": (14, 30),
    "wagon": (28, 18),
}
EXPECTED_BASES = {"well": 21, "haystack": 17, "scarecrow": 29, "wagon": 17}

NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))
STONE = frozenset("Rr")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def span(grid: list[str], y: int) -> tuple[int, int]:
    """(first, last) opaque column on row `y`, or (-1, -1)."""
    cols = [x for x, c in enumerate(grid[y]) if c != "."]
    return (cols[0], cols[-1]) if cols else (-1, -1)


def runs(grid: list[str], y: int, key: str) -> list[tuple[int, int]]:
    """Every maximal run of `key` on row `y`, as inclusive (x0, x1) pairs."""
    found, start = [], None
    for x, c in enumerate(grid[y]):
        if c == key:
            if start is None:
                start = x
        elif start is not None:
            found.append((start, x - 1))
            start = None
    if start is not None:
        found.append((start, len(grid[y]) - 1))
    return found


def cols_of(grid: list[str], key: str) -> list[tuple[int, int]]:
    return [(x, y) for y, row in enumerate(grid) for x, c in enumerate(row) if c == key]


# --------------------------------------------------------------------------
# structural checks, one per hard requirement
# --------------------------------------------------------------------------
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


def check_outline(label: str, grid: list[str]) -> list[str]:
    """Any opaque pixel facing background -- or the canvas edge -- must be K."""
    h, w = len(grid), len(grid[0])
    leaks = []
    for y in range(h):
        for x in range(w):
            if grid[y][x] in (".", "K"):
                continue
            for dx, dy in NEIGHBOURS:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < w and 0 <= ny < h) or grid[ny][nx] == ".":
                    leaks.append((x, y, grid[y][x]))
                    break
    if leaks:
        return [f"{label}: {len(leaks)} unoutlined silhouette pixel(s): {leaks[:8]}"]
    return []


def check_base(label: str, grid: list[str], base_row: int) -> list[str]:
    """The lowest opaque row is the grid's own last row: nothing floats."""
    h = len(grid)
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
    top = min(opaque_rows)
    if top != 0 and not any(grid[0][x] != "." for x in range(len(grid[0]))):
        problems.append(f"{label}: rows above the art are not empty (top opaque row {top})")
    return problems


def check_no_touch(label: str, grid: list[str], left: set[str], right: set[str]) -> list[str]:
    """No pixel of `left` may share an edge with a pixel of `right`."""
    h, w = len(grid), len(grid[0])
    bad = []
    for y in range(h):
        for x in range(w):
            if grid[y][x] not in left:
                continue
            for dx, dy in NEIGHBOURS:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] in right:
                    bad.append((x, y, grid[y][x], grid[ny][nx]))
    if bad:
        return [f"{label}: {sorted(left)} touches {sorted(right)} at {bad[:6]}"]
    return []


# --------------------------------------------------------------------------
# reported geometry, per prop
# --------------------------------------------------------------------------
def check_wagon_geometry() -> tuple[list[str], list[str]]:
    problems = []
    if WAGON_DRAWBAR_OVERHANG != WAGON_DRAWBAR_COLS[1] - WAGON_BED_COLS[1]:
        problems.append(f"wagon: WAGON_DRAWBAR_OVERHANG {WAGON_DRAWBAR_OVERHANG} != "
                        f"{WAGON_DRAWBAR_COLS[1]} - {WAGON_BED_COLS[1]}")

    # the bed really is the widest thing above the wheels, and the drawbar is
    # the only part of the wagon that reaches past it
    blo, bhi = WAGON_BED_COLS
    for y in WAGON_BED_ROWS:
        if "." in WAGON[y][blo:bhi + 1]:
            problems.append(f"wagon: bed row {y} has a hole inside {WAGON_BED_COLS}")
    for y in (WAGON_BED_ROWS[0], WAGON_BED_ROWS[1]):
        if set(WAGON[y][blo:bhi + 1]) != {"K"}:
            problems.append(f"wagon: bed rail row {y} is not solid K across {WAGON_BED_COLS}")
    beyond = [(x, y) for y in range(WAGON_H) for x in range(bhi + 1, WAGON_W) if WAGON[y][x] != "."]
    strays = [(x, y) for x, y in beyond
              if not (WAGON_DRAWBAR_COLS[0] <= x <= WAGON_DRAWBAR_COLS[1]
                      and WAGON_DRAWBAR_ROWS[0] <= y <= WAGON_DRAWBAR_ROWS[1])]
    if strays:
        problems.append(f"wagon: pixels past the bed outside the drawbar's box: {strays[:6]}")
    if sorted({y for _x, y in beyond}) != list(range(WAGON_DRAWBAR_ROWS[0], WAGON_DRAWBAR_ROWS[1] + 1)):
        problems.append(f"wagon: rows reaching past the bed are {sorted({y for _x, y in beyond})}, "
                        f"drawbar claims {WAGON_DRAWBAR_ROWS}")
    if max(span(WAGON, y)[1] for y in range(WAGON_H)) != WAGON_DRAWBAR_COLS[1]:
        problems.append(f"wagon: nothing reaches col {WAGON_DRAWBAR_COLS[1]}")
    tip = [y for y in range(WAGON_H) if WAGON[y][WAGON_DRAWBAR_COLS[1]] != "."]
    if tip != list(range(WAGON_DRAWBAR_ROWS[0] + 2, WAGON_DRAWBAR_ROWS[1] + 1)):
        problems.append(f"wagon: the drawbar's outermost column is opaque on rows {tip}; "
                        f"it should step down over the bar's last 5 rows")
    if not any(WAGON[y][x] == "T" for y in range(WAGON_DRAWBAR_ROWS[0], WAGON_DRAWBAR_ROWS[1] + 1)
               for x in range(bhi + 1, WAGON_DRAWBAR_COLS[1] + 1)):
        problems.append("wagon: the drawbar carries no T at all")

    # wheels: 9px, spoked, hide their top two rows behind the bed, land on BASE
    for lo, hi in WAGON_WHEEL_COLS:
        if hi - lo + 1 != 9:
            problems.append(f"wagon: wheel at cols {lo}-{hi} is {hi - lo + 1}px, not 9")
        hub = WAGON[WAGON_WHEEL_HUB_ROW][lo:hi + 1]
        if "T" not in hub:
            problems.append(f"wagon: wheel at cols {lo}-{hi} has no T spokes on the hub row")
        if not set(hub) & STONE:
            problems.append(f"wagon: wheel at cols {lo}-{hi} has no R/r rim on the hub row")
        seen = {c for y in range(WAGON_WHEEL_TOP_ROW, WAGON_H) for c in WAGON[y][lo:hi + 1]}
        if seen - set(".KRrtT"):
            problems.append(f"wagon: wheel at cols {lo}-{hi} uses foreign colours {sorted(seen - set('.KRrtT'))}")
    for y in range(WAGON_WHEEL_TOP_ROW, WAGON_WHEEL_TOP_ROW + 2):
        if set(WAGON[y]) & STONE:
            problems.append(f"wagon: R/r shows on row {y} -- the bed should hide the wheel tops")
    ground = [x for x in range(WAGON_W) if WAGON[WAGON_BASE_ROW][x] != "."]
    inside = all(any(lo <= x <= hi for lo, hi in WAGON_WHEEL_COLS) for x in ground)
    if not inside:
        problems.append(f"wagon: BASE row touches the ground outside the wheels at "
                        f"{[x for x in ground if not any(lo <= x <= hi for lo, hi in WAGON_WHEEL_COLS)]}")
    if len(ground) < 6:
        problems.append(f"wagon: only {len(ground)}px of wheel reach the BASE row, it will look balanced on points")

    # cargo: an N heap, sitting in the bed's middle, K-sealed so it never meets T
    if not any("N" in WAGON[y] for y in range(0, WAGON_BED_ROWS[0])):
        problems.append("wagon: no N cargo above the bed rail")
    for x, y in cols_of(WAGON, "N"):
        if not (WAGON_CARGO_COLS[0] <= x <= WAGON_CARGO_COLS[1] and y < WAGON_BED_ROWS[0]):
            problems.append(f"wagon: cargo leaks to {(x, y)}, outside {WAGON_CARGO_COLS}")
            break
    problems += check_no_touch("wagon", WAGON, {"N"}, set("Tt"))

    lo, hi = WAGON_CARGO_COLS
    report = (f"wagon     bed cols {WAGON_BED_COLS[0]}-{WAGON_BED_COLS[1]} rows "
              f"{WAGON_BED_ROWS[0]}-{WAGON_BED_ROWS[1]}; cargo N cols {lo}-{hi}; "
              f"drawbar cols {WAGON_DRAWBAR_COLS[0]}-{WAGON_DRAWBAR_COLS[1]} = "
              f"{WAGON_DRAWBAR_OVERHANG}px past the bed, rows "
              f"{WAGON_DRAWBAR_ROWS[0]}-{WAGON_DRAWBAR_ROWS[1]}; wheels "
              + " / ".join(f"{a}-{b}" for a, b in WAGON_WHEEL_COLS)
              + f", {len(ground)}px on the BASE row")
    return problems, [report]


def check_well_geometry() -> tuple[list[str], list[str]]:
    problems = []

    # the mouth is an ellipse: three rows, widest in the middle, stone on BOTH
    # flanks of every one of them, and centred on the grid.
    widths = []
    for y in range(WELL_MOUTH_ROWS[0], WELL_MOUTH_ROWS[1] + 1):
        spans = runs(WELL, y, "t")
        if len(spans) != 1:
            problems.append(f"well: row {y} has {len(spans)} t runs; the mouth should be one")
            continue
        x0, x1 = spans[0]
        widths.append(x1 - x0 + 1)
        if not set(WELL[y][x0 - 3:x0]) & STONE or not set(WELL[y][x1 + 1:x1 + 4]) & STONE:
            problems.append(f"well: the t mouth on row {y} is not flanked by R/r stone")
        if x0 + x1 != WELL_W - 1:
            problems.append(f"well: mouth on row {y} spans {x0}-{x1}, not centred in {WELL_W}px")
    if widths != [8, 10, 8]:
        problems.append(f"well: mouth rows are {widths}px wide, expected the ellipse [8, 10, 8]")
    if WELL_MOUTH_COLS[1] - WELL_MOUTH_COLS[0] + 1 != max(widths):
        problems.append(f"well: WELL_MOUTH_COLS {WELL_MOUTH_COLS} does not match the widest mouth row")
    if len(cols_of(WELL, "t")) < 30:
        problems.append("well: the mouth carries almost no t; it will not read as a hole")

    # the rim: a solid K lid, and the reported widest columns
    if set(WELL[WELL_RIM_TOP_ROW]) - {".", "K"} or WELL[WELL_RIM_TOP_ROW].count("K") < 10:
        problems.append(f"well: rim cap row {WELL_RIM_TOP_ROW} is not a solid K lid")
    rim = [span(WELL, y) for y in range(WELL_H)]
    widest = max(range(WELL_H), key=lambda y: rim[y][1] - rim[y][0])
    if rim[widest] != WELL_RIM_COLS:
        problems.append(f"well: widest rim row is {widest} at {rim[widest]}, "
                        f"reported WELL_RIM_COLS {WELL_RIM_COLS}")

    # the roof is a pitched triangle with a lit and a shadowed slope
    r0, r1 = WELL_ROOF_ROWS
    roof_widths = [span(WELL, y)[1] - span(WELL, y)[0] + 1 for y in range(r0, r1 + 1)]
    if roof_widths != [4, 6, 8, 10, 12]:
        problems.append(f"well: roof courses are {roof_widths}px, expected [4, 6, 8, 10, 12]")
    for y in range(r0 + 1, r1 + 1):
        if WELL[y].count("O") == 0 or WELL[y].count("o") == 0:
            problems.append(f"well: roof row {y} is missing its lit or shadowed slope")
    roof_top, eave = span(WELL, r1), span(WELL, WELL_EAVE_ROW)
    if set(WELL[WELL_EAVE_ROW]) != {"K", "."}:
        problems.append(f"well: eave row {WELL_EAVE_ROW} is not solid outline")
    if (eave[0], eave[1]) != (roof_top[0] - 2, roof_top[1] + 2):
        problems.append(f"well: eave {eave} does not overhang the roof {roof_top} by 2px a side")

    # the windlass bridges both uprights; the bucket hangs between them off a
    # rope that starts on the bar's underside
    l_up, r_up = WELL_UPRIGHT_COLS
    for y in range(WELL_WINDLASS_ROWS[0], WELL_WINDLASS_ROWS[1] + 1):
        if span(WELL, y) != (l_up[0], r_up[1]):
            problems.append(f"well: windlass row {y} spans {span(WELL, y)}, "
                            f"does not bridge the uprights {WELL_UPRIGHT_COLS}")
    mid = range(WELL_WINDLASS_ROWS[0] + 1, WELL_WINDLASS_ROWS[1])
    if not all(set("Tt") & set(WELL[y][l_up[1] + 1:r_up[0]]) for y in mid):
        problems.append("well: the windlass carries no T/t between the uprights")
    rope_lo, rope_hi = WELL_ROPE_COLS
    rope_row = [y for y in range(WELL_H)
                if any(WELL[y][x] == "t" for x in range(rope_lo, rope_hi + 1))
                and y > WELL_WINDLASS_ROWS[1] and y < WELL_BUCKET_ROWS[0]]
    if not rope_row or min(rope_row) != WELL_WINDLASS_ROWS[1] + 1:
        problems.append(f"well: the rope does not start on row {WELL_WINDLASS_ROWS[1] + 1}")
    if not (rope_row[-1] < WELL_BUCKET_ROWS[0]):
        problems.append("well: the rope does not reach the bucket")

    # the bucket: U body, u shading, between the uprights, with a K mouth and base
    lo, hi = WELL_BUCKET_COLS
    body_rows = range(WELL_BUCKET_ROWS[0] + 1, WELL_BUCKET_ROWS[1])
    for y in body_rows:
        if runs(WELL, y, "U") != [(lo + 1, lo + 2)] or runs(WELL, y, "u") != [(lo + 3, lo + 4)]:
            problems.append(f"well: bucket row {y} is not K U U u u K across {WELL_BUCKET_COLS}")
    if WELL[WELL_BUCKET_ROWS[0]][lo:hi + 1] != "K" * (hi - lo + 1):
        problems.append(f"well: the bucket's mouth row {WELL_BUCKET_ROWS[0]} is not a K rim at "
                        f"{WELL_BUCKET_COLS}")
    bucket_px = sum(1 for c in "".join(WELL[y][lo:hi + 1] for y in body_rows) if c in "Uu")
    if bucket_px < 8:
        problems.append(f"well: the bucket carries only {bucket_px}px of U/u; it will not read")
    if not (l_up[1] < lo and hi < r_up[0]):
        problems.append(f"well: the bucket {WELL_BUCKET_COLS} does not hang between the uprights")

    report = (f"well      mouth rows {WELL_MOUTH_ROWS[0]}-{WELL_MOUTH_ROWS[1]} "
              f"({widths[0]}/{widths[1]}/{widths[2]}px t, stone both flanks), "
              f"rim cols {WELL_RIM_COLS[0]}-{WELL_RIM_COLS[1]}, "
              f"windlass rows {WELL_WINDLASS_ROWS[0]}-{WELL_WINDLASS_ROWS[1]}, "
              f"rope cols {rope_lo}-{rope_hi}, bucket {bucket_px}px U/u at cols {lo}-{hi}")
    return problems, [report]


def check_haystack_geometry() -> tuple[list[str], list[str]]:
    problems = []
    lo, hi = HAYSTACK_BASE_COLS
    if set(HAYSTACK[HAYSTACK_BASE_ROW]) != {"K", "."} or span(HAYSTACK, HAYSTACK_BASE_ROW) != (lo, hi):
        problems.append(f"haystack: BASE row is not a solid K footprint at {HAYSTACK_BASE_COLS}")
    edges = [span(HAYSTACK, y) for y in range(HAYSTACK_H)]
    left = [e[0] for e in edges]
    belly = [y for y in range(HAYSTACK_H) if edges[y] == HAYSTACK_WIDEST_COLS]
    if not belly or min(belly) != 10:
        problems.append(f"haystack: rows at the full {HAYSTACK_WIDEST_COLS} width are {belly}")
    if any(left[i + 1] > left[i] for i in range(min(belly) - 1)):
        problems.append(f"haystack: left edge {left} is not a monotone dome shoulder")
    steps = [abs(left[i + 1] - left[i]) for i in range(HAYSTACK_H - 1)]
    if max(steps) < 2:
        problems.append(f"haystack: left edge steps {steps} never jump -- that is a smooth arc, "
                        f"not a ragged thatch edge")
    if span(HAYSTACK, HAYSTACK_CROWN_ROW)[1] - span(HAYSTACK, HAYSTACK_CROWN_ROW)[0] + 1 != 6:
        problems.append("haystack: the crown row is not 6px")
    shadow = range(HAYSTACK_SHADOW_ROWS[0], HAYSTACK_SHADOW_ROWS[1] + 1)
    if not all(set("tn") & set(HAYSTACK[y]) for y in shadow):
        problems.append("haystack: no t/n ground shadow in the rows above the BASE")
    top_light = sum(HAYSTACK[y].count("E") for y in range(0, 6))
    low_light = sum(HAYSTACK[y].count("E") for y in range(HAYSTACK_H - 7, HAYSTACK_H))
    if top_light <= low_light:
        problems.append(f"haystack: {top_light} E in the top six rows vs {low_light} in the bottom "
                        f"seven -- the light is not coming from the upper-left")
    if sum(HAYSTACK[y].count("E") for y in range(HAYSTACK_H)) == 0:
        problems.append("haystack: no E highlight anywhere, the dome has no lit shoulder")

    report = (f"haystack  crown {span(HAYSTACK, HAYSTACK_CROWN_ROW)[1] - span(HAYSTACK, HAYSTACK_CROWN_ROW)[0] + 1}px, "
              f"belly rows {min(belly)}-{max(belly)} at {HAYSTACK_WIDEST_COLS[1] - HAYSTACK_WIDEST_COLS[0] + 1}px, "
              f"base cols {lo}-{hi}, edge jumps up to {max(steps)}px, "
              f"E {top_light} high / {low_light} low")
    return problems, [report]


def check_scarecrow_geometry() -> tuple[list[str], list[str]]:
    problems = []
    head = span(SCARECROW, SCARECROW_EYE_ROW)
    eyes = [x for x in range(head[0] + 1, head[1]) if SCARECROW[SCARECROW_EYE_ROW][x] == "K"]
    if len(eyes) != 2:
        problems.append(f"scarecrow: row {SCARECROW_EYE_ROW} has {len(eyes)} K pixels inside the "
                        f"head, expected exactly 2 eyes")
    elif eyes[0] + eyes[1] != head[0] + head[1]:
        problems.append(f"scarecrow: eyes at {eyes} are not symmetric inside the head {head}")
    mouth = runs(SCARECROW, SCARECROW_MOUTH_ROW, "t")
    if len(mouth) != 1:
        problems.append(f"scarecrow: row {SCARECROW_MOUTH_ROW} has {len(mouth)} t runs, expected one mouth")
    elif not (head[0] < mouth[0][0] and mouth[0][1] < head[1]):
        problems.append(f"scarecrow: the mouth {mouth[0]} runs into the head's edge {head}")
    elif mouth[0][1] - mouth[0][0] + 1 < 3:
        problems.append(f"scarecrow: the mouth is only {mouth[0][1] - mouth[0][0] + 1}px wide")

    c0, c1 = SCARECROW_CROSSBAR_ROWS
    for y in range(c0, c1 + 1):
        if span(SCARECROW, y) != (0, SCARECROW_W - 1):
            problems.append(f"scarecrow: crossbar row {y} spans {span(SCARECROW, y)}, "
                            f"it should run the full {SCARECROW_W}px")
    for y in range(c0 + 1, c1):
        if set("Tt") & set(SCARECROW[y]) and set("Pp") & set(SCARECROW[y]):
            if not set("K") & set(SCARECROW[y][SCARECROW_SHIRT_COLS[0] - 1:SCARECROW_SHIRT_COLS[0]]):
                problems.append(f"scarecrow: the shirt on crossbar row {y} has no K edge of its own")

    # the shirt body hangs under the shoulders at its own columns
    lo, hi = SCARECROW_SHIRT_COLS
    body = range(SCARECROW_FRINGE_ROWS[1] + 1, SCARECROW_SHIRT_ROWS[1] - 1)
    for y in body:
        if span(SCARECROW, y) != (lo - 1, hi + 1):
            problems.append(f"scarecrow: shirt row {y} spans {span(SCARECROW, y)}, expected "
                            f"{(lo - 1, hi + 1)}")
        if runs(SCARECROW, y, "P") != [(lo, lo + 3)] or runs(SCARECROW, y, "p") != [(lo + 4, hi)]:
            problems.append(f"scarecrow: shirt row {y} is not P P P P p p between the K edges")
    if not any(SCARECROW[y].count("p") and SCARECROW[y].count("P") for y in body):
        problems.append("scarecrow: the shirt has no lit/shadowed split")

    # straw fringe at both cuffs and at the hem, ragged rather than a straight bar
    cuff = [SCARECROW[y].count("Y") for y in range(SCARECROW_FRINGE_ROWS[0], SCARECROW_FRINGE_ROWS[1] + 1)]
    hem = SCARECROW[SCARECROW_SHIRT_ROWS[1] - 1]
    if sum(cuff) < 4 or max(cuff) == min(cuff) == 0:
        problems.append(f"scarecrow: the cuffs carry no Y straw (rows {SCARECROW_FRINGE_ROWS})")
    if hem.count("Y") < 3:
        problems.append(f"scarecrow: the hem row is not ragged straw ({hem.count('Y')}px of Y)")
    if len(set(cuff)) < 2:
        problems.append(f"scarecrow: the cuff fringe is a flat bar {cuff}, not ragged")

    stake = SCARECROW_STAKE_COLS
    if span(SCARECROW, SCARECROW_BASE_ROW) != stake or set(SCARECROW[SCARECROW_BASE_ROW]) != {"K", "."}:
        problems.append(f"scarecrow: the stake does not land on the BASE row at {stake}")
    above = [y for y in range(SCARECROW_SHIRT_ROWS[1] + 1, SCARECROW_BASE_ROW)]
    for y in above:
        if span(SCARECROW, y) != stake:
            problems.append(f"scarecrow: the stake row {y} spans {span(SCARECROW, y)}, expected {stake}")
    head_rows = range(SCARECROW_EYE_ROW, SCARECROW_MOUTH_ROW + 1)
    if not all(SCARECROW[y].count("U") + SCARECROW[y].count("u") > 0 for y in head_rows):
        problems.append("scarecrow: the head is not U/u straw-stuffed between the eyes and the mouth")

    problems += check_no_touch("scarecrow", SCARECROW, set("Pp"), set("Tt"))
    report = (f"scarecrow eyes cols {eyes} inside head {head}, mouth cols "
              f"{mouth[0][0]}-{mouth[0][1]} t, crossbar rows {c0}-{c1} full {SCARECROW_W}px, "
              f"shirt cols {lo}-{hi} rows {body[0]}-{body[-1]}, cuff straw {cuff}, "
              f"hem {hem.count('Y')}px Y, stake cols {stake[0]}-{stake[1]}")
    return problems, [report]


def check_metadata() -> tuple[list[str], list[str]]:
    problems, report = [], []
    if SIZES != EXPECTED_SIZES:
        problems.append(f"SIZES {SIZES} != {EXPECTED_SIZES}")
    if BASES != EXPECTED_BASES:
        problems.append(f"BASES {BASES} != {EXPECTED_BASES}")
    if (WELL_W, WELL_H) != EXPECTED_SIZES["well"]:
        problems.append("well: declared W/H constants disagree with SIZES")
    if (HAYSTACK_W, HAYSTACK_H) != EXPECTED_SIZES["haystack"]:
        problems.append("haystack: declared W/H constants disagree with SIZES")
    if (SCARECROW_W, SCARECROW_H) != EXPECTED_SIZES["scarecrow"]:
        problems.append("scarecrow: declared W/H constants disagree with SIZES")
    if (WAGON_W, WAGON_H) != EXPECTED_SIZES["wagon"]:
        problems.append("wagon: declared W/H constants disagree with SIZES")

    for part in (check_well_geometry, check_haystack_geometry,
                 check_scarecrow_geometry, check_wagon_geometry):
        p, r = part()
        problems += p
        report += r

    # the escapes the module docstring promises
    problems += check_no_touch("well bucket", WELL, set("Uu"), {"N", "n"})
    return problems, report


# --------------------------------------------------------------------------
# rendered artifact
# --------------------------------------------------------------------------
def check_preview() -> tuple[list[str], list[str]]:
    """The PNG on disk must decode back to the authored props, pixel for pixel."""
    problems, report = [], []
    path = ASSETS / "yardprops_preview.png"
    if not path.exists():
        path = render_preview()           # fresh checkout: build it once
        report.append("preview  was missing, rendered from yardprops.py")
    img = Image.open(path).convert("RGBA")
    width, height, baseline, xs = preview_layout()

    if img.size != (width * PREVIEW_SCALE, height * PREVIEW_SCALE):
        problems.append(f"preview: size {img.size} != {(width * PREVIEW_SCALE, height * PREVIEW_SCALE)}")
        return problems, report

    expected = preview(compose_preview(), PREVIEW_SCALE, GRASS_BG)
    if list(img.getdata()) != list(expected.getdata()):
        got, want = img.load(), expected.load()
        x, y = next((x, y) for y in range(img.height) for x in range(img.width)
                    if got[x, y] != want[x, y])
        problems.append(
            f"preview: pixel ({x},{y}) is {got[x, y]}, expected {want[x, y]} "
            f"-- native ({x // PREVIEW_SCALE},{y // PREVIEW_SCALE}); re-run yardprops.py"
        )

    px = img.load()
    for name, grid in PROPS.items():
        col = next((c for c, ch in enumerate(grid[BASES[name]]) if ch == "K"), None)
        if col is None:
            problems.append(f"{name}: BASE row has no K pixel to anchor on")
            continue
        sx = (xs[name] + col) * PREVIEW_SCALE + PREVIEW_SCALE // 2
        got = px[sx, baseline * PREVIEW_SCALE + PREVIEW_SCALE // 2]
        if got != SCENE_PALETTE["K"]:
            problems.append(f"{name}: BASE does not land on the shared baseline row (got {got})")
        above = px[sx, (baseline - 1) * PREVIEW_SCALE + PREVIEW_SCALE // 2]
        if above == (*GRASS_BG, 255):
            problems.append(f"{name}: nothing sits on the baseline at col {col}")

    report.append(f"preview  {img.size[0]}x{img.size[1]} at {PREVIEW_SCALE}x on grass, "
                  f"{len(PROPS)} props on baseline native row {baseline} -> {path.name}")
    return problems, report


def main() -> int:
    problems: list[str] = []
    report: list[str] = []

    declared = {
        "well": (WELL, WELL_W, WELL_H, WELL_BASE_ROW),
        "haystack": (HAYSTACK, HAYSTACK_W, HAYSTACK_H, HAYSTACK_BASE_ROW),
        "scarecrow": (SCARECROW, SCARECROW_W, SCARECROW_H, SCARECROW_BASE_ROW),
        "wagon": (WAGON, WAGON_W, WAGON_H, WAGON_BASE_ROW),
    }

    print("-- structure ------------------------------------------------")
    for name, (grid, w, h, base) in declared.items():
        problems += check_size(name, grid, w, h)
        problems += check_grid(grid, name)
        problems += check_outline(name, grid)
        problems += check_base(name, grid, base)
        print(f"  {name:<9} {w}x{h}  BASE row {base} = grid row {len(grid) - 1}  "
              f"{len({c for r in grid for c in r if c != '.'})} colours")

    print("\n-- colour separation (dE76, adjacent pairs, SCENE_TIERS) ----")
    for name, (grid, *_rest) in declared.items():
        failures, rows = report_separation(grid, name, tiers=SCENE_TIERS)
        problems += failures
        worst = min(rows, key=lambda r: r[3]) if rows else None
        print(f"  {name:<9} {len(rows):>2} touching pairs, hard failures {len(failures)}"
              + (f"; tightest {worst[1]}-{worst[2]} dE={worst[3]:.1f} dL={worst[4]:.2f} "
                 f"(floor {worst[5]:.0f}, {worst[6]})" if worst else ""))

    print("\n-- reported geometry ---------------------------------------")
    geo_problems, geo_report = check_metadata()
    problems += geo_problems
    for line in geo_report:
        print(f"  {line}")

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
        print("        lowest opaque row is the grid's last row, readable under SCENE_TIERS, every")
        print("        reported geometry constant true, documented escapes held, preview decodes")
    print(f"  failures : {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
