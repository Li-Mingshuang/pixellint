"""Assertions over a composed scene.

The interesting one is loop closure. Rather than eyeballing whether the GIF
jumps when it wraps, this composes frame `loop_frames` -- one past the last
rendered frame -- and asserts it is pixel-identical to frame 0. If that holds,
the loop is mathematically seamless rather than hopefully seamless.
"""

import sys
from pathlib import Path

from pixelkit import (SCENE_PALETTE, SCENE_TIERS, check_grid,
                      report_separation)

HERE = Path(__file__).resolve().parent


def main(argv: list[str]) -> int:
    import scene as S

    spec_path = Path(argv[1]) if len(argv) > 1 else HERE / "scenes" / "meadow.json"
    spec = S.load_spec(spec_path)
    sc = S.Scene(spec)
    W, H = sc.w, sc.h

    problems = []
    for m in sc.missing:
        problems.append(f"layer not resolved -> {m}")

    grids = [sc.compose(f) for f in range(sc.loop_frames)]

    print(f"-- shape + palette ({spec['name']}) " + "-" * 24)
    bad = 0
    for i, g in enumerate(grids):
        if len(g) != H or any(len(r) != W for r in g):
            problems.append(f"frame {i}: not {W}x{H}")
            bad += 1
            continue
        stray = {c for row in g for c in row} - set(SCENE_PALETTE)
        if stray:
            problems.append(f"frame {i}: keys outside SCENE_PALETTE: {sorted(stray)}")
            bad += 1
    print(f"  {'ok  ' if not bad else 'FAIL'} {len(grids)} frames of {W}x{H}, "
          f"all colours from the shared palette")

    print("\n-- loop closure ---------------------------------------------")
    wrapped = sc.compose(sc.loop_frames)
    drift = sum(1 for y in range(H) for x in range(W)
                if wrapped[y][x] != grids[0][y][x])
    if drift == 0:
        print(f"  ok    frame {sc.loop_frames} is pixel-identical to frame 0 "
              f"-> the loop is mathematically seamless")
    else:
        where = [(x, y) for y in range(H) for x in range(W)
                 if wrapped[y][x] != grids[0][y][x]][:10]
        problems.append(f"loop does not close: {drift} px differ, first at {where}")
        print(f"  FAIL  {drift} pixel(s) differ between frame {sc.loop_frames} and frame 0")

    steps = [sum(1 for y in range(H) for x in range(W)
                 if grids[i][y][x] != grids[(i + 1) % sc.loop_frames][y][x])
             for i in range(sc.loop_frames)]
    lo, hi = min(steps), max(steps)
    print(f"  changed px per step: min={lo} max={hi}")
    if hi > 3 * max(lo, 1):
        problems.append(f"motion is uneven across the loop: {lo}..{hi}")
        print("  FAIL  uneven motion")
    else:
        print("  ok    motion is even across the loop")

    print("\n-- animated layers stay on the ground ------------------------")
    # NOTE: this deliberately checks the layer's OWN grid arithmetic rather than
    # scanning the composed frame. An earlier version scanned the columns a
    # sprite occupies for the lowest opaque pixel -- which started returning the
    # ground layer's row 95 the moment a ground layer existed. The scene is
    # occluded by design, so the honest place to check a sprite's height is the
    # sprite.
    for layer, grid in sc.layers:
        if not layer.get("animated"):
            continue
        label = layer["name"]
        lows = [S.lowest_opaque_row(f) for f in grid]
        uniq = sorted(set(lows))
        if len(uniq) != 1:
            problems.append(
                f"{label}: frames have different heights (lowest rows {uniq}); "
                f"it will bob off the ground")
            print(f"  FAIL  {label}: frames have different heights {uniq}")
        elif layer.get("base") is None:
            problems.append(f"{label}: animated layer has no 'base' to pin it to")
            print(f"  FAIL  {label}: no base row")
        else:
            print(f"  ok    {label}: {len(grid)} frames of {len(grid[0])} rows, "
                  f"lowest row {uniq[0]} -> pinned to scene row {layer['base']}")

    print("\n-- scene colour separation ----------------------------------")
    fails, rows = report_separation(grids[0], spec["name"], tiers=SCENE_TIERS)
    for _, a, b, d, dl, floor, kind in sorted(rows, key=lambda r: r[3])[:8]:
        print(f"    {a}-{b}  dE={d:5.1f}  dL={dl:4.2f}  need>={floor:.0f} ({kind})")
    print(f"  distinct colours in scene : {len({c for r in grids[0] for c in r if c != '.'})}")
    print(f"  adjacent pairs checked    : {len(rows)}")
    if fails:
        problems += fails
        print(f"  FAIL  {len(fails)} pair(s) below threshold")
    else:
        print("  ok    every adjacent pair passes")
    if fails.warnings:
        print(f"  note  {len(fails.warnings)} tight-but-usable pair(s), listed above as WARN")

    # -- composition ------------------------------------------------------
    # Two objects may share a colour, or stand close together, but not both.
    # This is the assertion form of a real complaint: the dog was drawn in the
    # fence's own wood brown and stood on top of it, and the rock sat inside the
    # cottage's stone foundation in the same stone. Same colour *and* adjacent
    # makes two objects read as one.
    #
    # Depth counts as distance. A barrel in the foreground at base row 90 and a
    # fence at base row 76 read as two separate objects even when they overlap in
    # x, because the depth cue separates them -- so the check only fires when the
    # pair is close in BOTH x and depth.
    print("\n-- composition: no object may share a colour AND a position ----")
    comp = spec.get("composition", {})
    min_gap = comp.get("min_gap", 8)
    depth_close = comp.get("depth_close", 8)
    need_shared = comp.get("shared_colours", 2)
    ignore = set(comp.get("ignore_colours", ["K"]))

    placements = []
    for layer, grid in sc.layers:
        if layer.get("tile_horizontal") or "base" not in layer:
            continue                      # full-width layers are not objects
        one = grid[0] if layer.get("animated") else grid
        cols = {c for row in one for c in row if c != "."} - ignore
        placements.append({
            "name": layer["name"],
            "x": layer["x"],
            "base": layer["base"],
            "width": len(one[0]),
            "colours": cols,
        })

    conflicts = []
    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            a, b = placements[i], placements[j]
            shared = a["colours"] & b["colours"]
            gap = max(b["x"] - (a["x"] + a["width"]), a["x"] - (b["x"] + b["width"]))
            dz = abs(a["base"] - b["base"])
            separable = gap >= min_gap or dz >= depth_close
            both_bad = len(shared) >= need_shared and not separable
            tag = "FAIL " if both_bad else "ok   "
            if both_bad:
                conflicts.append(
                    f"{a['name']}/{b['name']}: share {len(shared)} colour(s) "
                    f"{sorted(shared)}, only {gap}px apart in x and {dz} rows in depth")
            print(f"  {tag} {a['name']:<9} / {b['name']:<9}  dx={gap:>4}px  dz={dz:>3}  "
                  f"shared={sorted(shared) if shared else 'none'}")
    problems += conflicts

    print()
    for p in problems:
        print(f"  FAIL  {p}")
    print(f"failures: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
