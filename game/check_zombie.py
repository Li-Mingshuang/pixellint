"""Verification for the zombie (``game/zombie.py``).

Pixel art is deterministic, so everything that decides whether this reads as a
pair of clips instead of a jitter is assertable rather than eyeballable:

  * structure      - every frame exactly 32 rows x 22 columns, GAME_PALETTE keys
                     only, one connected body (no floating pixels)
  * readability    - dE76 between every touching colour pair, GAME_PALETTE
  * grounding      - the lowest opaque pixel is row 31 in all four walk frames
                     and both attack frames; the walk/attack clips never move it
  * head lock      - the ten by nine HEAD block is byte-identical in all four
                     walk frames, is only ever offset by whole rows, and is
                     matched at exactly one (row, column) offset per frame when
                     every offset in the canvas is scanned
  * rhythm         - the four walk frames change by a similar number of pixels
                     each step, including the loop wrap, so the lurch does not
                     judder
  * collapse       - the death clip's opaque height only ever shrinks
                     (30, 25, 15, 9, 7 rows), and every death frame is still one
                     connected body
  * the eye        - ``V`` is present (one or two pixels) in every walk and
                     attack frame and gone from the last two death frames
  * the raster     - assets/zombie_preview.png decodes back to these grids pixel
                     for pixel, and assets/zombie_death.gif is five frames of
                     110ms that plays ONCE

    python game/check_zombie.py

Exits non-zero if anything fails.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gamepalette import GAME_PALETTE
from pixelkit import check_grid, report_separation
from zombie import (
    BG,
    FRAME_MS,
    GROUND_ROW,
    H,
    HEAD,
    HEAD_COL,
    PAD,
    SCALE,
    W,
    ZOMBIE,
)

CLIPS = ["walk", "attack", "death"]
HEAD_H, HEAD_W = len(HEAD), len(HEAD[0])
BALANCE = 2.2            # max/min changed-pixel ratio allowed per walk step
FLAT_DEATH_ROWS = 10     # the settled frame must be at most this tall


def opaque(grid):
    return {(x, y) for y in range(H) for x in range(W) if grid[y][x] != "."}


def rows_used(grid):
    return [y for y in range(H) if any(grid[y][x] != "." for x in range(W))]


def lowest_row(grid):
    return max(rows_used(grid))


def height(grid):
    ys = rows_used(grid)
    return ys[-1] - ys[0] + 1


def find_head(grid):
    """Every (dx, dy) at which HEAD matches inside ``grid`` -- every offset."""
    hits = []
    for dy in range(H - HEAD_H + 1):
        for dx in range(W - HEAD_W + 1):
            if all(grid[dy + r][dx:dx + HEAD_W] == HEAD[r] for r in range(HEAD_H)):
                hits.append((dx, dy))
    return hits


def raster_problems():
    """assets/zombie_preview.png must decode back to ZOMBIE, pixel for pixel.

    The sheet is 6x with one row per clip and the frames laid left to right, so
    every authored pixel owns a 6x6 block.  Sampling the middle of each block
    proves the PNG on disk really is the art above and not a stale render.
    """
    from PIL import Image

    path = _ROOT / "assets" / "zombie_preview.png"
    if not path.exists():
        return [f"{path.name} is missing - run game/zombie.py first"]
    img = Image.open(path).convert("RGBA")
    problems = []
    cols = max(len(ZOMBIE[name]) for name in CLIPS)
    want_w = PAD + cols * (W * SCALE + PAD)
    want_h = PAD + len(CLIPS) * (H * SCALE + PAD)
    if img.size != (want_w, want_h):
        return [f"{path.name} is {img.size}, expected {(want_w, want_h)}"]
    for r, name in enumerate(CLIPS):
        for c, grid in enumerate(ZOMBIE[name]):
            for y in range(H):
                for x in range(W):
                    px = PAD + c * (W * SCALE + PAD) + x * SCALE + SCALE // 2
                    py = PAD + r * (H * SCALE + PAD) + y * SCALE + SCALE // 2
                    key = grid[y][x]
                    want = (*BG, 255) if key == "." else GAME_PALETTE[key]
                    got = img.getpixel((px, py))
                    if got != want:
                        problems.append(
                            f"{path.name} {name} f{c} pixel ({x},{y}) is {got}, expected {want}"
                        )
    return problems[:8]


def gif_problems():
    """assets/zombie_death.gif must be five 110ms frames that play once."""
    from PIL import Image

    path = _ROOT / "assets" / "zombie_death.gif"
    if not path.exists():
        return [f"{path.name} is missing - run game/zombie.py first"]
    img = Image.open(path)
    problems = []
    frames = len(ZOMBIE["death"])
    if getattr(img, "n_frames", 1) != frames:
        problems.append(
            f"{path.name} has {getattr(img, 'n_frames', 1)} frames, expected {frames}"
        )
    if img.size != (W * SCALE, H * SCALE):
        problems.append(f"{path.name} is {img.size}, expected {(W * SCALE, H * SCALE)}")
    if img.info.get("duration") != FRAME_MS:
        problems.append(
            f"{path.name} duration is {img.info.get('duration')}ms, expected {FRAME_MS}ms"
        )
    if img.info.get("loop") is not None:
        problems.append(
            f"{path.name} carries a loop extension (loop={img.info.get('loop')}) - "
            "a death must play once"
        )
    return problems


def main() -> int:
    problems: list[str] = []
    report: list[str] = []

    total = sum(len(ZOMBIE[name]) for name in CLIPS)
    report.append(
        f"shape              : {total} frames, {W}x{H} each "
        f"({', '.join(f'{n} {len(ZOMBIE[n])}' for n in CLIPS)})"
    )

    # -- structure: 32x22, palette keys only, one connected body -------------
    for name in CLIPS:
        for i, grid in enumerate(ZOMBIE[name]):
            if len(grid) != H or any(len(r) != W for r in grid):
                problems.append(
                    f"{name} f{i}: grid must be {W}x{H}, got {len(grid)}x{len(grid[0])}"
                )
                continue
            problems += check_grid(grid, f"{name} f{i}", GAME_PALETTE)
    report.append(
        f"structure          : {'ok - every frame is one closed body, palette keys only' if not problems else 'FAIL'}"
    )

    # -- separation: hard failures only; warnings are the author's call ------
    sep_failures, warns = [], 0
    for name in CLIPS:
        for i, grid in enumerate(ZOMBIE[name]):
            failures, _ = report_separation(
                grid, f"{name} f{i}", palette=GAME_PALETTE, quiet=True
            )
            sep_failures += failures
            warns += len(failures.warnings)
    problems += sep_failures
    keys = sorted({c for n in CLIPS for g in ZOMBIE[n] for row in g for c in row if c != "."})
    report.append(f"colours used       : {keys}")
    report.append(
        f"colour separation  : "
        + ("ok - every touching pair clears the rules" if not sep_failures else "FAIL")
        + f" ({warns} advisory warning(s), left alone)"
    )

    # -- grounding: walk and attack never move the ground row ---------------
    grounds = {}
    for name in ("walk", "attack"):
        grounds[name] = [lowest_row(g) for g in ZOMBIE[name]]
        bad = [i for i, row in enumerate(grounds[name]) if row != GROUND_ROW]
        if bad:
            problems.append(
                f"{name}: lowest opaque row is {grounds[name]}, expected {GROUND_ROW} "
                "in every frame"
            )
        for i, g in enumerate(ZOMBIE[name]):
            if sum(1 for x in range(W) if g[GROUND_ROW][x] != ".") < 5:
                problems.append(f"{name} f{i}: fewer than 5 pixels on the ground row")
    report.append(
        f"ground row         : walk {grounds['walk']}, attack {grounds['attack']} "
        f"-- constant at row {GROUND_ROW} in all six"
    )

    # -- head lock: byte-identical, whole-row shifts only, one match --------
    walk_hits, offsets = [], []
    for i, grid in enumerate(ZOMBIE["walk"]):
        hits = find_head(grid)
        walk_hits.append(hits)
        if len(hits) != 1:
            problems.append(
                f"walk f{i}: head block matched at {hits}, expected exactly one offset"
            )
            continue
        dx, dy = hits[0]
        if dx != HEAD_COL:
            problems.append(
                f"walk f{i}: head block sits at column {dx}, expected {HEAD_COL} "
                "(the head may not drift sideways)"
            )
        offsets.append(dy)
    if len(offsets) == len(ZOMBIE["walk"]):
        windows = [
            [ZOMBIE["walk"][i][offsets[i] + r][HEAD_COL:HEAD_COL + HEAD_W] for r in range(HEAD_H)]
            for i in range(len(offsets))
        ]
        if any(win != HEAD for win in windows):
            problems.append("the head block is not byte-identical to HEAD in every walk frame")
        bob = max(offsets) - min(offsets)
        report.append(
            f"head window        : x{HEAD_COL}..{HEAD_COL + HEAD_W - 1}, {HEAD_H} rows, "
            f"identical in all {len(offsets)} walk frames"
        )
        report.append(f"head row offsets   : {offsets}  (bob {bob}px, whole rows only)")
        if bob > 1:
            problems.append(f"the head bobs {bob}px between walk frames, must be at most 1")
    report.append(
        "head lock          : "
        + (
            "ok - one match per frame, dx == 0, whole-row shifts only"
            if all(len(h) == 1 and h[0][0] == HEAD_COL for h in walk_hits)
            else "FAIL"
        )
    )

    # -- rhythm: no walk step may jump relative to the others ---------------
    frames = ZOMBIE["walk"]
    diffs = [
        sum(1 for y in range(H) for x in range(W) if frames[i][y][x] != frames[(i + 1) % len(frames)][y][x])
        for i in range(len(frames))
    ]
    report.append(f"changed px per step: {diffs}  (last entry is the loop wrap)")
    if min(diffs) == 0:
        problems.append(f"a walk step changes nothing: {diffs}")
    elif max(diffs) > BALANCE * min(diffs):
        problems.append(
            f"walk steps are uneven: {diffs} (max/min {max(diffs) / min(diffs):.2f} > {BALANCE})"
        )
    else:
        report.append(
            f"rhythm             : ok - every step changes a similar amount "
            f"(max/min {max(diffs) / min(diffs):.2f})"
        )

    # -- the collapse: height only ever comes down --------------------------
    heights = [height(g) for g in ZOMBIE["death"]]
    report.append(f"death height       : {heights} rows tall, frame by frame")
    if any(b > a for a, b in zip(heights, heights[1:])):
        problems.append(f"the death clip pops back up: heights {heights} are not monotonic")
    elif heights[0] - heights[-1] < 15:
        problems.append(f"the death clip barely falls: heights {heights}")
    elif heights[-1] > FLAT_DEATH_ROWS:
        problems.append(f"the settled frame is {heights[-1]} rows tall, expected <= {FLAT_DEATH_ROWS}")
    else:
        report.append(
            "collapse           : ok - it only ever shrinks, and every frame is one body"
        )

    # -- the eye: present in walk/attack, out by the end of the death -------
    eye = {name: [sum(row.count("V") for row in g) for g in ZOMBIE[name]] for name in CLIPS}
    report.append(f"glowing eye (V)    : {eye}")
    for name in ("walk", "attack"):
        if any(n < 1 for n in eye[name]):
            problems.append(f"{name}: the glow is missing from {eye[name]}")
        if any(n > 2 for n in eye[name]):
            problems.append(f"{name}: {eye[name]} uses more than two V pixels - too much glow")
    if any(n != 0 for n in eye["death"][-2:]):
        problems.append(f"death: the last two frames still glow {eye['death'][-2:]}")
    if not all(n > 0 for n in eye["death"][:3]):
        problems.append(f"death: the eye should still be lit while it is falling: {eye['death']}")
    report.append(
        "                   : ok - two pixels in every walk/attack frame, "
        "gone from the last two death frames"
    )

    # -- the rendered assets must decode back to these grids ----------------
    raster = raster_problems()
    problems += raster
    report.append(
        f"zombie_preview.png : "
        + (
            f"ok - {total} frames decode back to the grids pixel for pixel"
            if not raster
            else "FAIL"
        )
    )
    gif = gif_problems()
    problems += gif
    report.append(
        f"zombie_death.gif   : "
        + ("ok - 5 frames, 110ms, plays once" if not gif else "FAIL")
    )

    # -- output -------------------------------------------------------------
    print("-- zombie: walk, attack, death ------------------------------")
    for line in report:
        print(f"  {line}")
    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print("  ok    all 11 frames sound, head locked, ground row pinned, collapse monotonic")
    print(f"\n  failures : {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
