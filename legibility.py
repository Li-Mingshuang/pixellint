"""Measurable proxies for why a sprite reads as clean or as mush.

I have said repeatedly that this pipeline cannot tell whether art is good. That is
true of *taste* -- it cannot tell a charming face from a dull one. It is NOT true
of several things that make pixel art read badly, and those are worth measuring:

  outline_ratio   fraction of opaque pixels that are outline. A sprite that is
                  mostly outline is a sprite with no internal mass.
  mean_run        average length of a horizontal run of one colour. Short runs
                  mean the image is sliced into confetti.
  isolated        fraction of pixels whose colour differs from all four
                  neighbours. Pixel art is built from shapes, not from dust.
  flatness        share of the largest single-colour connected region. Low means
                  nothing has any body to it.
  symmetry        mask against its own mirror. Asymmetry is fine for a creature
                  and wrong for a machine, so this is context, not a verdict.
  tones           distinct colours per 1000 opaque pixels. A rough palette
                  economy check.
  dominant        share of the single most common FILL colour, outline excluded.
                  This is the one that caught the mech. `tones` counts how many
                  colours are used and cannot see that one of them holds 60% of
                  the sprite; a big flat slab and a well-modelled figure can use
                  the same palette and score identically on it.

Run it on assets you consider good AND on ones you consider bad. The numbers only
mean something RELATIVE to that calibration; a threshold invented without it would
just be another arbitrary floor, which is the mistake this repo keeps documenting.

    python legibility.py                 # compare every asset
    python legibility.py mech mechdog    # named modules only
"""

import sys
from pathlib import Path

from gamepalette import GAME_PALETTE
from pixelkit import SCENE_PALETTE

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "game"))


def analyse(grid, palette) -> dict:
    h, w = len(grid), len(grid[0])
    opaque = [(x, y) for y in range(h) for x in range(w) if grid[y][x] != "."]
    n = len(opaque)
    if not n:
        return {}
    oset = set(opaque)

    def at(x, y):
        return grid[y][x] if 0 <= x < w and 0 <= y < h else "."

    outline = sum(1 for x, y in opaque if grid[y][x] == "K")

    runs = []
    for y in range(h):
        run = 0
        for x in range(w):
            if grid[y][x] == ".":
                if run:
                    runs.append(run)
                run = 0
            elif x and grid[y][x] == grid[y][x - 1]:
                run += 1
            else:
                if run:
                    runs.append(run)
                run = 1
        if run:
            runs.append(run)

    isolated = sum(1 for x, y in opaque
                   if all(at(x + dx, y + dy) not in (".", grid[y][x])
                          for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))

    # largest single-colour connected region
    seen, best = set(), 0
    for p in opaque:
        if p in seen:
            continue
        colour = grid[p[1]][p[0]]
        stack, size = [p], 0
        seen.add(p)
        while stack:
            cx, cy = stack.pop()
            size += 1
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (cx + dx, cy + dy)
                if q in oset and q not in seen and grid[q[1]][q[0]] == colour:
                    seen.add(q)
                    stack.append(q)
        best = max(best, size)

    mirror = sum(1 for x, y in opaque if (w - 1 - x, y) in oset)

    fills = {}
    for x, y in opaque:
        if grid[y][x] != "K":
            fills[grid[y][x]] = fills.get(grid[y][x], 0) + 1
    fill_total = sum(fills.values())
    dominant = max(fills.values()) / fill_total if fill_total else 0.0

    return {
        "px": n,
        "outline_ratio": outline / n,
        "mean_run": sum(runs) / len(runs) if runs else 0,
        "isolated": isolated / n,
        "flatness": best / n,
        "symmetry": mirror / n,
        "tones": len({grid[y][x] for x, y in opaque}) / n * 1000,
        "dominant": dominant,
    }


def gather(names):
    out = []
    for p in sorted(HERE.glob("*.py")) + sorted((HERE / "game").glob("*.py")):
        stem = p.stem
        if stem.startswith("_") or stem.startswith("check_") or stem in (
                "pixelkit", "gamepalette", "evaluate", "legibility", "build",
                "plan_scene", "scene", "export_game_atlas", "render_game_gif",
                "verify_reproducible", "pixelate"):
            continue
        if names and stem not in names:
            continue
        try:
            mod = __import__(stem)
        except Exception:
            continue
        pal = getattr(mod, "PALETTE", None) or (
            GAME_PALETTE if (HERE / "game" / p.name).exists() else SCENE_PALETTE)
        shipped = getattr(mod, "SHIPPED", None)
        for attr in (shipped or dir(mod)):
            if not isinstance(attr, str) or attr.startswith("_"):
                continue
            v = getattr(mod, attr, None)
            frames = None
            if isinstance(v, list) and v and isinstance(v[0], list) and v[0] \
                    and isinstance(v[0][0], str):
                frames = v
            elif isinstance(v, list) and v and isinstance(v[0], str) \
                    and _looks_like_grid(v, pal):
                frames = [v]
            elif isinstance(v, dict):
                # a container dict: take its values that are grids
                for k, vv in v.items():
                    if isinstance(vv, list) and vv and isinstance(vv[0], list):
                        out.append((f"{stem}.{k}", vv[0], pal))
                        break
                continue
            if frames:
                out.append((f"{stem}.{attr}", frames[0], pal))
    return out


def _looks_like_grid(v, pal):
    """list[str] where every row is the same width AND every char is a palette key.

    Without the palette test, a list of NAMES -- `PREVIEW_ORDER`, `Z_ORDER` -- looks
    exactly like a grid, and the analyser tries to index it as pixels. That is the
    same confusion that bit export_game_atlas.py earlier; naming conventions do not
    distinguish "a grid" from "a list of strings", content does.
    """
    if len(v) < 2 or len({len(r) for r in v}) != 1:
        return False
    return all(c in pal for r in v for c in r)


def main() -> int:
    names = set(sys.argv[1:])
    rows, broken = [], []
    for label, grid, pal in gather(names):
        widths = {len(r) for r in grid}
        if len(widths) != 1:
            broken.append((label, sorted(widths)))
            continue
        m = analyse(grid, pal)
        if m:
            rows.append((label, m))

    if broken:
        print("-- ragged grids (row widths disagree) " + "-" * 52)
        for label, widths in broken:
            print(f"  {label}: widths {widths}")
        print("  This is a real defect, not a measurement problem: a grid whose rows")
        print("  differ in width cannot be rendered or asserted meaningfully.\n")

    if not rows:
        print("nothing to analyse")
        return 1

    print("=" * 100)
    print("LEGIBILITY PROXIES   (lower outline/isolated/dominant is cleaner; "
          "higher run/flatness is more solid)")
    print("=" * 100)
    print(f"  {'asset':<26} {'px':>6} {'outline':>8} {'run':>5} {'isolated':>9} "
          f"{'flat':>6} {'symm':>6} {'tones':>6} {'domin':>6}")
    for label, m in sorted(rows, key=lambda r: -r[1]["dominant"]):
        print(f"  {label:<26} {m['px']:>6} {m['outline_ratio']:>8.2f} "
              f"{m['mean_run']:>5.2f} {m['isolated']:>9.3f} {m['flatness']:>6.2f} "
              f"{m['symmetry']:>6.2f} {m['tones']:>6.1f} {m['dominant']:>6.2f}")

    doms = [m["dominant"] for _, m in rows]
    runs = [m["mean_run"] for _, m in rows]
    print(f"\n  dominant fill share: min {min(doms):.2f}, median "
          f"{sorted(doms)[len(doms) // 2]:.2f}, max {max(doms):.2f}")
    print("  A sprite whose biggest single fill colour holds most of its pixels is")
    print("  a flat slab no matter how many colours it technically uses.")
    print(f"  mean run: min {min(runs):.2f}, median "
          f"{sorted(runs)[len(runs) // 2]:.2f}, max {max(runs):.2f}")
    print("  A sprite far below the median run length is sliced into confetti;")
    print("  one far above it is a few big blobs with no internal structure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
