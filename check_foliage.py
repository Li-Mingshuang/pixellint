"""Verification for the foliage set (foliage.py).

Pixel art is deterministic, so everything that decides whether this set reads
is assertable instead of eyeballed:

  * structure      - exact sizes, palette-only, ONE connected body per grid
                     (a "scattered patch" is allowed to be concave, but not to
                     have floating pixels)
  * readability    - dE76 between every touching colour pair; only hard
                     failures count, warnings are the author's call
  * grounding      - the plant base rows are the lowest opaque row; the hen's
                     feet land on row 9 in ALL four frames
  * head lock      - the hen's 4x4 head block is byte-identical in all four
                     frames and never shifts sideways: every row *and* column
                     offset is scanned, and the single hit must be dx == 0
  * planted body   - only the head and the 1px neck column may differ between
                     frames; the tail, breast, legs and feet are locked
  * rhythm         - no step may change nothing, and the four steps must change
                     a similar number of pixels
  * raster truth   - foliage_preview.png and chicken.gif must decode back to
                     the grids pixel for pixel, so the assets on disk are
                     provably the art in foliage.py and not a stale render

    python check_foliage.py

Exits non-zero if anything fails.
"""

from pathlib import Path

from PIL import Image

from foliage import (
    BASES,
    BUSH_H,
    BUSH_W,
    CHICKEN,
    CHICKEN_BG,
    CHICKEN_FRAME_MS,
    CHICKEN_GROUND_ROW,
    CHICKEN_H,
    CHICKEN_HEAD_ROWS,
    CHICKEN_SCALE,
    CHICKEN_W,
    FLOWERPATCH_BASE_ROW,
    FLOWERPATCH_H,
    FLOWERPATCH_W,
    GRASS_BG,
    HEAD,
    HEAD_COL,
    HEAD_H,
    HEAD_W,
    MUSHROOMS_H,
    MUSHROOMS_W,
    PLANTS,
    PREVIEW_SCALE,
    SIZES,
    preview_layout,
)
from pixelkit import SCENE_PALETTE, check_grid, report_separation

N_FRAMES = len(CHICKEN)
OUT_DIR = Path(__file__).resolve().parent / "assets"

# The texture the hen is allowed to redraw: the head window (cols 8-11) and the
# neck column (col 7).  Everything left of the neck is planted.
MOVING_COLS = range(HEAD_COL - 1, CHICKEN_W)
BODY_TOP = 5              # the shoulder row; the body and legs never move
LEG_TOP = 8


def find_head(grid) -> list[tuple[int, int]]:
    """Every (dx, dy) at which the HEAD block matches: ALL row/col offsets.

    ``dx`` is measured against HEAD_COL, so dx == 0 means "no sideways drift".
    """
    hits = []
    for y0 in range(0, CHICKEN_H - HEAD_H + 1):
        for x0 in range(0, CHICKEN_W - HEAD_W + 1):
            if all(grid[y0 + r][x0:x0 + HEAD_W] == HEAD[r] for r in range(HEAD_H)):
                hits.append((x0 - HEAD_COL, y0))
    return hits


def lowest_opaque_row(grid) -> int:
    return max(y for y in range(len(grid)) if any(c != "." for c in grid[y]))


def changed(a, b) -> int:
    return sum(
        1
        for y in range(CHICKEN_H)
        for x in range(CHICKEN_W)
        if a[y][x] != b[y][x]
    )


def preview_problems() -> list[str]:
    """foliage_preview.png must decode back to the plant grids, pixel for pixel.

    The strip is PREVIEW_SCALE x with the plants laid left to right on one
    baseline, so every authored pixel owns a scale x scale block; sampling the
    middle of each block proves the PNG on disk really is the art in foliage.py.
    """
    path = OUT_DIR / "foliage_preview.png"
    if not path.exists():
        return [f"{path.name} is missing - run foliage.py first"]
    img = Image.open(path).convert("RGBA")
    _, _, baseline, xs = preview_layout()
    problems = []
    for name, grid in PLANTS.items():
        w, h = SIZES[name]
        x0, y0 = xs[name], baseline - BASES[name]
        for y in range(h):
            for x in range(w):
                px = (x0 + x) * PREVIEW_SCALE + PREVIEW_SCALE // 2
                py = (y0 + y) * PREVIEW_SCALE + PREVIEW_SCALE // 2
                if not (0 <= px < img.width and 0 <= py < img.height):
                    problems.append(f"{name}: pixel ({x},{y}) samples off the canvas")
                    continue
                key = grid[y][x]
                want = (*GRASS_BG, 255) if key == "." else SCENE_PALETTE[key]
                got = img.getpixel((px, py))
                if got != want:
                    problems.append(
                        f"foliage_preview.png {name} pixel ({x},{y}) is {got}, expected {want}"
                    )
    return problems[:8]


def gif_problems() -> list[str]:
    """chicken.gif must be a 4-frame 160ms loop that decodes back to the grids."""
    path = OUT_DIR / "chicken.gif"
    if not path.exists():
        return [f"{path.name} is missing - run foliage.py first"]
    img = Image.open(path)
    problems = []
    if getattr(img, "n_frames", 1) != N_FRAMES:
        problems.append(f"chicken.gif has {getattr(img, 'n_frames', 1)} frames, expected {N_FRAMES}")
    if img.size != (CHICKEN_W * CHICKEN_SCALE, CHICKEN_H * CHICKEN_SCALE):
        problems.append(
            f"chicken.gif is {img.size}, expected {(CHICKEN_W * CHICKEN_SCALE, CHICKEN_H * CHICKEN_SCALE)}"
        )
    if img.info.get("duration") != CHICKEN_FRAME_MS:
        problems.append(f"chicken.gif duration is {img.info.get('duration')}ms, expected {CHICKEN_FRAME_MS}ms")
    if img.info.get("loop", None) != 0:
        problems.append(f"chicken.gif loop is {img.info.get('loop')}, expected 0 (loop forever)")
    if problems:
        return problems

    mismatches = 0
    for i in range(N_FRAMES):
        img.seek(i)
        rgb = img.convert("RGB")
        for y in range(CHICKEN_H):
            for x in range(CHICKEN_W):
                key = CHICKEN[i][y][x]
                want = CHICKEN_BG if key == "." else SCENE_PALETTE[key][:3]
                got = rgb.getpixel(
                    (x * CHICKEN_SCALE + CHICKEN_SCALE // 2, y * CHICKEN_SCALE + CHICKEN_SCALE // 2)
                )
                if got != want:
                    mismatches += 1
                    if mismatches <= 3:
                        problems.append(
                            f"chicken.gif f{i} pixel ({x},{y}) is {got}, expected {want}"
                        )
    if mismatches > 3:
        problems.append(f"chicken.gif has {mismatches} pixels that do not decode back to the grids")
    return problems


def main() -> int:
    problems: list[str] = []
    report: list[str] = []

    # -- structure: exact sizes, palette-only, one connected body ------------
    expected = {
        "bush": (BUSH_W, BUSH_H),
        "flowerpatch": (FLOWERPATCH_W, FLOWERPATCH_H),
        "mushrooms": (MUSHROOMS_W, MUSHROOMS_H),
    }
    for name, grid in PLANTS.items():
        w, h = expected[name]
        if SIZES[name] != (w, h):
            problems.append(f"{name}: exported size is {SIZES[name]}, expected {(w, h)}")
        if len(grid) != h or any(len(r) != w for r in grid):
            problems.append(f"{name}: grid is {len(grid)}x{len(grid[0])}, expected {h}x{w}")
            continue
        problems += check_grid(grid, name)
        if "." not in "".join(grid):
            problems.append(f"{name}: no transparent surrounding pixels")
        if lowest_opaque_row(grid) != BASES[name]:
            problems.append(
                f"{name}: base row is {BASES[name]} but the lowest opaque row is "
                f"{lowest_opaque_row(grid)}"
            )
    report.append(
        "plant shapes       : "
        + ", ".join(f"{n} {SIZES[n][0]}x{SIZES[n][1]} base row {BASES[n]}" for n in PLANTS)
    )
    # A patch that fills its whole base row is a hedge; the notches are the point.
    notched = sum(1 for c in PLANTS["flowerpatch"][FLOWERPATCH_BASE_ROW] if c == ".")
    report.append(f"flowerpatch base   : {notched} transparent column(s) in the base row (scatter, not hedge)")
    if notched < 2:
        problems.append("flowerpatch base row is solid - that reads as a hedge, not a patch")

    # -- readability: hard failures only ------------------------------------
    sep_failures = []
    sep_warnings = []
    for name, grid in PLANTS.items():
        failures, _ = report_separation(grid, name)
        sep_failures += failures
        sep_warnings += failures.warnings
    for i, grid in enumerate(CHICKEN):
        failures, _ = report_separation(grid, f"chicken f{i}")
        sep_failures += failures
        sep_warnings += failures.warnings
    problems += sep_failures
    report.append(
        "colour separation  : "
        + ("ok - every touching pair clears its tier" if not sep_failures else "FAIL")
        + f" ({len(sep_warnings)} advisory warning(s) left alone)"
    )

    # -- chicken: size, connectedness, planted body -------------------------
    for i, grid in enumerate(CHICKEN):
        if len(grid) != CHICKEN_H or any(len(r) != CHICKEN_W for r in grid):
            problems.append(
                f"chicken f{i}: grid must be {CHICKEN_W}x{CHICKEN_H}, got {len(grid)}x{len(grid[0])}"
            )
            continue
        problems += check_grid(grid, f"chicken f{i}")
    report.append(f"chicken shape      : {N_FRAMES} frames, {CHICKEN_W}x{CHICKEN_H} each, one connected body each")

    # only the head window and the neck column may differ between frames
    for i, grid in enumerate(CHICKEN):
        stray = [
            (x, y)
            for y in range(CHICKEN_H)
            for x in range(CHICKEN_W)
            if grid[y][x] != CHICKEN[0][y][x] and x not in MOVING_COLS
        ]
        if stray:
            problems.append(f"chicken f{i}: {len(stray)} pixel(s) outside the head/neck moved: {stray[:6]}")
    planted = all(
        CHICKEN[i][y][:HEAD_COL] == CHICKEN[0][y][:HEAD_COL]
        for i in range(N_FRAMES)
        for y in range(BODY_TOP, CHICKEN_H)
    )
    report.append(
        "planted body       : rows 5-9 cols 0-7 identical in all frames: "
        + ("ok" if planted else "FAIL")
    )

    # -- head lock: byte-identical, one hit, no sideways drift --------------
    windows, offsets = [], []
    for i, grid in enumerate(CHICKEN):
        hits = find_head(grid)
        if len(hits) != 1:
            problems.append(
                f"chicken f{i}: head block matched at {hits}, expected exactly one offset"
            )
            continue
        dx, dy = hits[0]
        if dx != 0:
            problems.append(f"chicken f{i}: head block drifted {dx} column(s) sideways")
        windows.append([grid[dy + r][HEAD_COL:HEAD_COL + HEAD_W] for r in range(HEAD_H)])
        offsets.append(dy)
    if len(windows) == N_FRAMES:
        if any(win != HEAD for win in windows):
            problems.append("head block is not byte-identical to HEAD in every frame")
        report.append(
            f"head window        : x{HEAD_COL}..{HEAD_COL + HEAD_W - 1}, {HEAD_H} rows, "
            "one hit per frame, identical bytes in all frames"
        )
        report.append(
            f"head row offsets   : {offsets}  (expected {list(CHICKEN_HEAD_ROWS)}: whole-row shift, dx == 0)"
        )
        if offsets != list(CHICKEN_HEAD_ROWS):
            problems.append(f"head row offsets are {offsets}, expected {list(CHICKEN_HEAD_ROWS)}")
        if len(set(offsets)) != N_FRAMES:
            problems.append(f"two frames share a head offset {offsets} - they are the same picture")

    # -- grounding: the feet never leave the ground -------------------------
    feet, foot_rows = [], []
    for i, grid in enumerate(CHICKEN):
        low = lowest_opaque_row(grid)
        foot_rows.append(low)
        if low != CHICKEN_GROUND_ROW:
            problems.append(
                f"chicken f{i}: lowest opaque row is {low}, expected {CHICKEN_GROUND_ROW}"
            )
        on_ground = sum(1 for x in range(CHICKEN_W) if grid[CHICKEN_GROUND_ROW][x] != ".")
        if on_ground < 3:
            problems.append(f"chicken f{i}: only {on_ground} pixel(s) on row {CHICKEN_GROUND_ROW}")
        feet.append(sum(1 for x in range(CHICKEN_W) if grid[CHICKEN_GROUND_ROW][x] == "Y"))
    report.append(f"chicken foot rows  : {foot_rows}  (expected {[CHICKEN_GROUND_ROW] * N_FRAMES})")
    if len(set(foot_rows)) != 1:
        problems.append(f"foot row is not constant across frames: {foot_rows} - the hen hopped")
    foot_rows_bytes = {CHICKEN[i][CHICKEN_GROUND_ROW] for i in range(N_FRAMES)}
    report.append(
        f"ground row content : {len(foot_rows_bytes)} distinct row(s) across frames - "
        + ("ok, both feet planted every frame" if len(foot_rows_bytes) == 1 else "FAIL")
    )
    if len(foot_rows_bytes) != 1:
        problems.append(f"row {CHICKEN_GROUND_ROW} differs between frames: {sorted(foot_rows_bytes)}")
    if feet != [6] * N_FRAMES:
        problems.append(f"row {CHICKEN_GROUND_ROW} carries {feet} Y pixels per frame, expected 6")
    legs_locked = all(CHICKEN[i][LEG_TOP] == CHICKEN[0][LEG_TOP] for i in range(N_FRAMES))
    report.append(
        f"legs row {LEG_TOP}         : " + ("identical in all frames" if legs_locked else "FAIL")
    )
    if not legs_locked:
        problems.append(f"row {LEG_TOP} (the legs) is not identical in all frames")

    # -- rhythm: no step may jump relative to the others --------------------
    diffs = [changed(CHICKEN[i], CHICKEN[(i + 1) % N_FRAMES]) for i in range(N_FRAMES)]
    report.append(f"changed px per step: {diffs}  (last entry is the loop wrap)")
    if min(diffs) == 0:
        problems.append(f"a step changes nothing: {diffs}")
    elif max(diffs) > 2.2 * min(diffs):
        problems.append(f"loop wrap jumps: changed-pixel counts {diffs} are too uneven")
    else:
        report.append("rhythm             : ok - every step changes a similar amount")

    # -- the rendered assets must decode back to these grids ----------------
    raster = preview_problems()
    problems += raster
    report.append(
        "foliage_preview.png: "
        + ("ok - all 3 plants decode back to the grids pixel for pixel" if not raster else "FAIL")
    )
    gif = gif_problems()
    problems += gif
    report.append(
        "chicken.gif        : "
        + (
            f"ok - {N_FRAMES} frames, {CHICKEN_FRAME_MS}ms, loops, decodes back to the grids"
            if not gif
            else "FAIL"
        )
    )

    # -- output ------------------------------------------------------------
    print("-- foliage set ----------------------------------------------")
    for line in report:
        print(f"  {line}")
    if sep_warnings:
        print("  warnings left alone (not failures):")
        for wmsg in sorted(set(sep_warnings)):
            print(f"    {wmsg}")
    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print(
            "  ok    all grids sound, zero hard separation failures, hen head locked "
            f"to whole rows, feet on row {CHICKEN_GROUND_ROW} in all {N_FRAMES} frames"
        )
    print(f"\n  failures : {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
