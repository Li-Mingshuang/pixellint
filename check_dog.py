"""Verification for the dog trot cycle (dog.py).

Pixel art is deterministic, so the things that decide whether a cycle reads as
a trot instead of a jitter are all assertable:

  * structure      - 20x14 every frame, palette-only, one connected body
  * readability    - dE76 between every touching colour pair, SPRITE_TIERS
  * head lock      - the head block is byte-identical in all four frames and
                     never shifts sideways: only whole-row offsets are allowed
  * grounding      - the lowest opaque pixel is row 13 in every frame, and the
                     lifted paw is exactly one row above it
  * alternation    - the lifted paw alternates FRONT, back, FRONT, back
  * wag            - the tail tip actually moves between the contact frames,
                     otherwise frames 0 and 2 would be the same picture

    python check_dog.py

Exits non-zero if anything fails.
"""

from dog import (
    BG,
    BOB_ROWS,
    DOG_FRAMES,
    FRAME_MS,
    GROUND_ROW,
    H,
    HEAD,
    HEAD_COL,
    HEAD_H,
    PAD,
    SCALE,
    W,
)
from pixelkit import SCENE_PALETTE, SPRITE_TIERS, check_grid, report_separation

PAW_LIFT_ROW = GROUND_ROW - 1
# (rear, front) lowest opaque row per frame: contact, front up, contact, rear up
EXPECTED_FEET = [
    (GROUND_ROW, GROUND_ROW),
    (GROUND_ROW, PAW_LIFT_ROW),
    (GROUND_ROW, GROUND_ROW),
    (PAW_LIFT_ROW, GROUND_ROW),
]
EXPECTED_TAIL_TIPS = [1, 2, 3, 2]   # left, middle, right, middle
REAR_PAW_COLS = range(4, 7)         # the rear pad (x3-x7 including its outline)
FRONT_PAW_COLS = range(8, 11)       # the front pad (x7-x11 including its outline)


def opaque(grid):
    return {(x, y) for y in range(len(grid)) for x in range(len(grid[0])) if grid[y][x] != "."}


def lowest_row(grid, x0=0, x1=W):
    rows = [y for y in range(H) for x in range(x0, x1) if grid[y][x] != "."]
    return max(rows) if rows else None


def paw_row(grid, cols):
    """Lowest opaque row inside a paw's own columns (the pad itself)."""
    rows = [y for y in range(H) for x in cols if grid[y][x] != "."]
    return max(rows) if rows else None


def find_head(grid):
    """Every (dx, dy) at which the HEAD block matches inside ``grid``."""
    hits = []
    for dy in range(0, H - HEAD_H + 1):
        for dx in range(-6, 7):
            x0, x1 = HEAD_COL + dx, HEAD_COL + dx + len(HEAD[0])
            if x0 < 0 or x1 > W:
                continue
            if all(grid[dy + r][x0:x1] == HEAD[r] for r in range(HEAD_H)):
                hits.append((dx, dy))
    return hits


def tail_tip(grid):
    """Column of the highest tail pixel (the tail lives left of the body)."""
    rows = min(y for y in range(1, 5) for x in range(0, 6) if grid[y][x] != ".")
    return min(x for x in range(0, 6) if grid[rows][x] != ".")


def raster_problems() -> list[str]:
    """dog_preview.png must decode back to DOG_FRAMES, pixel for pixel.

    The strip is 8x with the frames laid out left to right, so every authored
    pixel owns an 8x8 block.  Sampling the middle of each block proves the PNG
    on disk really is the art below, not a stale render.
    """
    from pathlib import Path

    from PIL import Image

    path = Path(__file__).resolve().parent / "assets" / "dog_preview.png"
    if not path.exists():
        return [f"{path.name} is missing - run dog.py first"]
    img = Image.open(path).convert("RGBA")
    problems = []
    for i, grid in enumerate(DOG_FRAMES):
        for y in range(H):
            for x in range(W):
                px = PAD + i * (W * SCALE + PAD) + x * SCALE + SCALE // 2
                py = PAD + y * SCALE + SCALE // 2
                want = (*BG, 255) if grid[y][x] == "." else SCENE_PALETTE[grid[y][x]]
                got = img.getpixel((px, py))
                if got != want:
                    problems.append(
                        f"dog_preview.png f{i} pixel ({x},{y}) is {got}, expected {want}"
                    )
    return problems[:8]


def gif_problems() -> list[str]:
    """dog.gif must be a 4-frame loop at FRAME_MS, or it will not animate."""
    from pathlib import Path

    from PIL import Image

    path = Path(__file__).resolve().parent / "assets" / "dog.gif"
    if not path.exists():
        return [f"{path.name} is missing - run dog.py first"]
    img = Image.open(path)
    problems = []
    if getattr(img, "n_frames", 1) != len(DOG_FRAMES):
        problems.append(f"dog.gif has {getattr(img, 'n_frames', 1)} frames, expected {len(DOG_FRAMES)}")
    if img.size != (W * SCALE, H * SCALE):
        problems.append(f"dog.gif is {img.size}, expected {(W * SCALE, H * SCALE)}")
    duration = img.info.get("duration")
    if duration != FRAME_MS:
        problems.append(f"dog.gif duration is {duration}ms, expected {FRAME_MS}ms")
    if not img.info.get("loop", None) == 0:
        problems.append(f"dog.gif loop is {img.info.get('loop')}, expected 0 (loop forever)")
    return problems


def main() -> int:
    problems: list[str] = []
    report: list[str] = []

    # -- structure ---------------------------------------------------------
    for i, grid in enumerate(DOG_FRAMES):
        problems += check_grid(grid, f"dog f{i}")
        if len(grid) != H or any(len(r) != W for r in grid):
            problems.append(f"dog f{i}: grid must be {W}x{H}, got {len(grid)}x{len(grid[0])}")
    report.append(f"shape              : {len(DOG_FRAMES)} frames, {W}x{H} each")

    # -- readability -------------------------------------------------------
    sep_failures = []
    for i, grid in enumerate(DOG_FRAMES):
        failures, _ = report_separation(grid, f"dog f{i}", tiers=SPRITE_TIERS)
        sep_failures += failures
    problems += sep_failures
    keys = sorted({c for g in DOG_FRAMES for row in g for c in row if c != "."})
    report.append(f"colours used       : {keys}")
    report.append(f"colour separation  : {'ok - every touching pair clears SPRITE_TIERS' if not sep_failures else 'FAIL'}")

    # -- head lock: byte-identical, no sideways drift, whole-row shift only --
    windows, offsets = [], []
    for i, grid in enumerate(DOG_FRAMES):
        hits = find_head(grid)
        if len(hits) != 1:
            problems.append(f"dog f{i}: head block matched at {hits}, expected exactly one hit")
            continue
        dx, dy = hits[0]
        if dx != 0:
            problems.append(f"dog f{i}: head block drifted {dx} column(s) sideways")
        windows.append([grid[dy + r][HEAD_COL:HEAD_COL + len(HEAD[0])] for r in range(HEAD_H)])
        offsets.append(dy)
    if len(windows) == len(DOG_FRAMES):
        if any(win != HEAD for win in windows):
            problems.append("head block is not byte-identical to HEAD in every frame")
        report.append(f"head window        : x{HEAD_COL}..{HEAD_COL + len(HEAD[0]) - 1}, {HEAD_H} rows, identical in all 4 frames")
        report.append(f"head row offsets   : {offsets}  (expected {list(BOB_ROWS)}: whole-row bob only)")
        if offsets != list(BOB_ROWS):
            problems.append(f"head row offsets are {offsets}, expected {list(BOB_ROWS)}")
        bob = max(offsets) - min(offsets)
        report.append(f"body bob           : {bob}px (must be <= 1)")
        if bob > 1:
            problems.append(f"body bob is {bob}px, must be at most 1px")
        if any(win != windows[0] for win in windows):
            problems.append("head window bytes differ between frames - the head is not locked")

    # -- grounding: the paw that is down always lands on row 13 -------------
    feet = []
    for i, grid in enumerate(DOG_FRAMES):
        low = lowest_row(grid)
        if low != GROUND_ROW:
            problems.append(f"dog f{i}: lowest opaque row is {low}, expected {GROUND_ROW}")
        on_ground = sum(1 for x in range(W) if grid[GROUND_ROW][x] != ".")
        if on_ground < 5:
            problems.append(f"dog f{i}: only {on_ground} pixel(s) on row {GROUND_ROW}")
        feet.append((paw_row(grid, REAR_PAW_COLS), paw_row(grid, FRONT_PAW_COLS)))
    report.append(f"paws (rear, front) : {feet}")
    report.append(f"ground row         : row {GROUND_ROW} in all {len(DOG_FRAMES)} frames - " +
                  ("ok" if all(f == GROUND_ROW for pair in feet for f in pair if f == GROUND_ROW) else "check"))
    if feet != EXPECTED_FEET:
        problems.append(f"foot alternation is {feet}, expected {EXPECTED_FEET}")
    else:
        report.append("foot alternation   : ok - both down, FRONT lifted, both down, REAR lifted")

    # -- tail wag: the contact frames must not be the same picture ----------
    tips = [tail_tip(g) for g in DOG_FRAMES]
    report.append(f"tail tip columns   : {tips}  (expected {EXPECTED_TAIL_TIPS})")
    if tips != EXPECTED_TAIL_TIPS:
        problems.append(f"tail tip columns are {tips}, expected {EXPECTED_TAIL_TIPS}")

    # -- rhythm: no step may jump relative to the others --------------------
    diffs = []
    for i in range(len(DOG_FRAMES)):
        a, b = DOG_FRAMES[i], DOG_FRAMES[(i + 1) % len(DOG_FRAMES)]
        diffs.append(sum(1 for y in range(H) for x in range(W) if a[y][x] != b[y][x]))
    report.append(f"changed px per step: {diffs}  (last entry is the loop wrap)")
    if min(diffs) == 0:
        problems.append(f"a step changes nothing: {diffs}")
    elif max(diffs) > 2.2 * min(diffs):
        problems.append(f"loop wrap jumps: changed-pixel counts {diffs} are too uneven")
    else:
        report.append("rhythm             : ok - every step changes a similar amount")

    # -- the rendered assets must decode back to these grids ----------------
    raster = raster_problems()
    problems += raster
    report.append(f"dog_preview.png    : {'ok - 4 frames decode back to the grids pixel for pixel' if not raster else 'FAIL'}")
    gif = gif_problems()
    problems += gif
    report.append(f"dog.gif            : {'ok - 4 frames, ' + str(FRAME_MS) + 'ms, loops' if not gif else 'FAIL'}")

    # -- output ------------------------------------------------------------
    print("-- dog trot cycle -------------------------------------------")
    for line in report:
        print(f"  {line}")
    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print("  ok    all 4 frames sound, head locked to whole rows, row 13 grounded")
    print(f"\n  failures : {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
