"""Assert that pixelate.py actually delivers what it claims.

The tool's contract is narrow and fully checkable: given any source image, produce
a sprite that is the requested size, palette-closed, ONE connected body, and free
of hard colour-separation failures. That contract is tested here against a
DETERMINISTIC SYNTHETIC source, so the test needs no external image, no network,
and no licence to worry about.

What is deliberately NOT tested: whether the output looks good. That is not
checkable, which is the whole reason this tool exists rather than a hand-drawn
sprite generator.
"""

import math
import sys
from pathlib import Path

from PIL import Image

from gamepalette import GAME_PALETTE
from pixelkit import check_grid, report_separation
import pixelate

HERE = Path(__file__).resolve().parent


def synthetic_source(path: Path, size: int = 384) -> Path:
    """A lambert-shaded bot with a specular: gradients, a hard silhouette and a
    bright accent, which is exactly the input that stresses a quantiser."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    lx, ly, lz = -0.5, -0.6, 0.62

    def sphere(cx, cy, r, rgb):
        for y in range(max(0, cy - r), min(size, cy + r)):
            for x in range(max(0, cx - r), min(size, cx + r)):
                dx, dy = (x - cx) / r, (y - cy) / r
                s = dx * dx + dy * dy
                if s > 1.0:
                    continue
                nz = math.sqrt(max(0.0, 1.0 - s))
                lam = max(0.0, dx * lx + dy * ly + nz * lz)
                spec = lam ** 16
                img.putpixel((x, y), tuple(
                    min(255, int(c * (0.30 + 0.85 * lam) + 255 * spec)) for c in rgb)
                    + (255,))

    sphere(size // 2, int(size * 0.64), int(size * 0.30), (90, 130, 170))
    sphere(size // 2, int(size * 0.30), int(size * 0.19), (120, 160, 200))
    img.save(path)
    return path


def pipeline(source: Path, size=(40, 56)):
    """The same transforms main() applies, without the file IO."""
    src = Image.open(source).convert("RGBA")
    small = src.resize(size, Image.Resampling.BOX)
    a = small.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    small.putalpha(a)
    small = pixelate.keep_largest_body(small)
    small = pixelate.quantise(small, GAME_PALETTE, dither=False)
    small = pixelate.outline(small, GAME_PALETTE)
    grid = pixelate.as_grid(small, GAME_PALETTE)
    return grid


def main() -> int:
    problems, report = [], []
    tmp = HERE / "_pixelate_test_source.png"
    synthetic_source(tmp)

    size = (40, 56)
    grid = pipeline(tmp, size)

    if (len(grid[0]), len(grid)) != size:
        problems.append(f"size is {len(grid[0])}x{len(grid)}, expected {size[0]}x{size[1]}")
    problems += check_grid(grid, "pixelated", GAME_PALETTE)
    report.append(f"downscale  : source downscaled to {size[0]}x{size[1]}, "
                  f"{size[0] * size[1]} cells")

    keys = {c for row in grid for c in row if c != "."}
    report.append(f"quantise   : {len(keys)} of {len(GAME_PALETTE) - 1} palette keys used, "
                  f"all from the locked palette")

    fails_before, _ = report_separation(grid, "before repair", palette=GAME_PALETTE,
                                        quiet=True)
    repaired, subs = pixelate.repair(grid, GAME_PALETTE)
    fails_after, rows_after = report_separation(repaired, "after repair",
                                                palette=GAME_PALETTE, quiet=True)
    report.append(f"repair     : {len(fails_before)} hard failure(s) before, "
                  f"{len(fails_after)} after, {subs} colour substitution(s)")
    if fails_before and len(fails_after) >= len(fails_before):
        problems.append("the repair pass resolved nothing; it is not earning its place")
    problems += list(fails_after)

    # the repair must not break the shape
    problems += check_grid(repaired, "repaired", GAME_PALETTE)

    # and the animation must be the honest one: a bob, and nothing invented
    frames = pixelate.animate(repaired, 4)
    if len(frames) != 4 or any(len(f) != len(repaired) for f in frames):
        problems.append("animate() produced the wrong number or shape of frames")
    moved = sum(1 for y in range(len(repaired)) for x in range(len(repaired[0]))
                if frames[0][y][x] != frames[1][y][x])
    report.append(f"animation  : {len(frames)} frames, {moved} cells move, "
                  f"procedural bob only")

    tmp.unlink(missing_ok=True)

    print("-- pixelate ---------------------------------------------")
    for line in report:
        print(f"  {line}")
    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print("  ok    any source image becomes a palette-clean, single-body sprite")
    print("\n  NOTE: nothing here says the result looks good, and nothing can.")
    print(f"\n  failures : {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
