"""Verification for the player sprite and his gun (player.py).

Pixel art is deterministic, so everything that decides whether these nine
frames read as one survivor standing, walking and firing -- rather than as nine
loose pictures -- is an assertion:

  * structure    - 24x32 every frame, palette-only, one connected body
  * readability  - dE76 over every touching colour pair, GAME_PALETTE rules
  * grounding    - the sole is row 31 in every frame of every clip.  A sprite
                   whose feet move between clips floats and sinks in game
  * head lock    - the HEAD block appears at exactly one (dx, dy) per frame,
                   dx == 0 always, and its bytes are identical everywhere.  A
                   head that drifts a column is the classic hand-made walk bug
  * rhythm       - within each clip no step changes wildly more than another,
                   so the cycle does not lurch
  * the rasters  - player_preview.png decodes back to these grids pixel for
                   pixel, and player_shoot.gif is 3 frames at 90ms, looping

    python game/check_player.py

Exits non-zero if anything fails.
"""

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game.player import (  # noqa: E402
    BG,
    CLIPS,
    FRAME_MS,
    GROUND_ROW,
    H,
    HEAD,
    HEAD_COL,
    PAD,
    PLAYER,
    SCALE,
    W,
    all_frames,
)
from gamepalette import GAME_PALETTE  # noqa: E402
from pixelkit import check_grid, report_separation  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "assets"
HEAD_H, HEAD_W = len(HEAD), len(HEAD[0])
MAX_STEP_RATIO = 2.5


def lowest_row(grid):
    rows = [y for y in range(H) if any(grid[y][x] != "." for x in range(W))]
    return max(rows) if rows else None


def find_head(grid):
    """Every (dx, dy) at which HEAD matches inside ``grid``.

    Scans row offsets AND column offsets, as check_dog.py does: a match found
    only at dx == 0, exactly once, is the proof that the head neither drifts
    sideways nor aliases onto some other part of the body.
    """
    hits = []
    for dy in range(0, H - HEAD_H + 1):
        for dx in range(-HEAD_COL, W - HEAD_COL - HEAD_W + 1):
            x0 = HEAD_COL + dx
            if all(grid[dy + r][x0:x0 + HEAD_W] == HEAD[r] for r in range(HEAD_H)):
                hits.append((dx, dy))
    return hits


def raster_problems():
    """player_preview.png must decode back to PLAYER, pixel for pixel.

    The sheet is one clip per row, frames left to right, at SCALE.  Sampling
    the middle of each pixel's SCALE x SCALE block proves the PNG on disk is
    this art and not a stale render.
    """
    path = ASSETS / "player_preview.png"
    if not path.exists():
        return [f"{path.name} is missing - run player.py first"]
    img = Image.open(path).convert("RGBA")
    cols = max(len(PLAYER[c]) for c in CLIPS)
    want_size = (cols * W * SCALE + PAD * (cols + 1),
                 len(CLIPS) * H * SCALE + PAD * (len(CLIPS) + 1))
    if img.size != want_size:
        return [f"{path.name} is {img.size}, expected {want_size}"]
    problems = []
    for r, name in enumerate(CLIPS):
        for c, grid in enumerate(PLAYER[name]):
            ox = PAD + c * (W * SCALE + PAD)
            oy = PAD + r * (H * SCALE + PAD)
            for y in range(H):
                for x in range(W):
                    got = img.getpixel((ox + x * SCALE + SCALE // 2,
                                        oy + y * SCALE + SCALE // 2))
                    want = (*BG, 255) if grid[y][x] == "." else GAME_PALETTE[grid[y][x]]
                    if got != want:
                        problems.append(
                            f"{path.name} {name}[{c}] pixel ({x},{y}) is {got}, expected {want}")
    return problems[:8]


def gif_problems():
    path = ASSETS / "player_shoot.gif"
    if not path.exists():
        return [f"{path.name} is missing - run player.py first"]
    img = Image.open(path)
    clip = PLAYER["shoot"]
    problems = []
    if getattr(img, "n_frames", 1) != len(clip):
        problems.append(f"{path.name} has {getattr(img, 'n_frames', 1)} frames, expected {len(clip)}")
    if img.size != (W * SCALE, H * SCALE):
        problems.append(f"{path.name} is {img.size}, expected {(W * SCALE, H * SCALE)}")
    if img.info.get("duration") != FRAME_MS:
        problems.append(f"{path.name} duration is {img.info.get('duration')}ms, expected {FRAME_MS}ms")
    if img.info.get("loop") != 0:
        problems.append(f"{path.name} loop is {img.info.get('loop')}, expected 0 (loop forever)")
    return problems


def main() -> int:
    problems, report = [], []

    # -- structure ---------------------------------------------------------
    for name, grid in all_frames():
        problems += check_grid(grid, name, GAME_PALETTE)
    shapes = {(len(g), len(g[0])) for _, g in all_frames()}
    n_frames = sum(len(PLAYER[c]) for c in CLIPS)
    if shapes != {(H, W)}:
        problems.append(f"frames are {sorted(shapes)}, expected every frame to be {H}x{W}")
    report.append(f"shape            : {n_frames} frames across {len(CLIPS)} clips, {W}x{H} each")

    # -- readability -------------------------------------------------------
    sep_failures = []
    for name, grid in all_frames():
        failures, _ = report_separation(grid, name, GAME_PALETTE)
        sep_failures += failures
    problems += sep_failures
    used = sorted({c for _, g in all_frames() for row in g for c in row if c != "."})
    report.append(f"colours used     : {used}")
    report.append(f"separation       : {'ok - no hard failure in any frame' if not sep_failures else 'FAIL'}")

    # -- grounding: same sole row in every frame of every clip -------------
    for name, grid in all_frames():
        sole = lowest_row(grid)
        if sole != GROUND_ROW:
            problems.append(f"{name}: lowest opaque row is {sole}, expected {GROUND_ROW}")
        elif sum(1 for x in range(W) if grid[GROUND_ROW][x] != ".") < 5:
            problems.append(f"{name}: only a sliver of the sole is on row {GROUND_ROW}")
    rows = {lowest_row(g) for _, g in all_frames()}
    if rows != {GROUND_ROW}:
        problems.append(f"ground row differs between frames: {sorted(rows)}")
    report.append(f"ground row       : row {GROUND_ROW} in all {n_frames} frames"
                  if rows == {GROUND_ROW} else f"ground row       : {sorted(rows)} FAIL")

    # -- head lock ---------------------------------------------------------
    offsets = []
    for name, grid in all_frames():
        hits = find_head(grid)
        if len(hits) != 1:
            problems.append(f"{name}: HEAD matched at {hits}, expected exactly one hit")
            continue
        dx, dy = hits[0]
        if dx != 0:
            problems.append(f"{name}: head block drifted {dx} column(s) sideways")
        offsets.append((name, dy))
        window = [grid[dy + r][HEAD_COL:HEAD_COL + HEAD_W] for r in range(HEAD_H)]
        if window != HEAD:
            problems.append(f"{name}: head window is not byte-identical to HEAD")
    if len(offsets) == n_frames:
        drift = max(dy for _, dy in offsets) - min(dy for _, dy in offsets)
        if drift > 1:
            problems.append(f"head row offsets span {drift}px, must be at most 1")
        report.append(f"head window      : x{HEAD_COL}..{HEAD_COL + HEAD_W - 1}, "
                      f"{HEAD_H} rows, byte-identical in all {n_frames} frames")
        report.append(f"head offsets     : {[dy for _, dy in offsets]}  (whole rows only, dx == 0, unique match)")

    # -- rhythm: no step inside a clip may lurch relative to its siblings --
    for name in CLIPS:
        clip = PLAYER[name]
        deltas = [
            sum(1 for y in range(H) for x in range(W) if clip[i][y][x] != clip[(i + 1) % len(clip)][y][x])
            for i in range(len(clip))
        ]
        if min(deltas) == 0:
            problems.append(f"{name}: a step changes nothing: {deltas}")
        elif max(deltas) > MAX_STEP_RATIO * min(deltas):
            problems.append(f"{name}: changed-pixel counts {deltas} are too uneven")
        else:
            report.append(f"rhythm {name:<6}    : changed px {deltas} (max/min "
                          f"{max(deltas) / min(deltas):.2f} <= {MAX_STEP_RATIO})")

    # -- the rendered assets must decode back to these grids ---------------
    raster = raster_problems()
    problems += raster
    report.append(f"player_preview   : {'ok - every frame decodes back pixel for pixel' if not raster else 'FAIL'}")
    gif = gif_problems()
    problems += gif
    report.append(f"player_shoot.gif : {'ok - ' + str(len(PLAYER['shoot'])) + ' frames, ' + str(FRAME_MS) + 'ms, loops' if not gif else 'FAIL'}")

    # -- output ------------------------------------------------------------
    print("-- player: idle / walk / shoot ------------------------------")
    for line in report:
        print(f"  {line}")
    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print(f"  ok    all {n_frames} frames sound, head locked to whole rows, "
              f"row {GROUND_ROW} grounded in every clip")
    print(f"\n  failures : {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
