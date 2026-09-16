"""Integrity + readability checks for the ground layer.

Same method as check_sprite.py, applied to a background: pixel art is
deterministic, so everything that decides whether the layer "reads" can be
asserted instead of eyeballed. On top of the shared structural and separation
checks this file asserts the three properties that are specific to a scrolling
ground layer:

  * shape          - 40 rows of exactly 160, only SCENE_PALETTE keys, no
                     transparent pixels (a ground layer has no holes)
  * tileability    - column 159 wraps onto column 0 when the scene scrolls, so
                     that seam must be a legitimate adjacency on every row, not
                     just a harmless-looking one. Checked per row, and again on
                     the whole layer duplicated left-to-right so the seam is
                     judged by exactly the same code path as real adjacencies.
  * walkability    - GROUND row 23 is scene row GROUND_LINE, the line the
                     character's and the dog's feet land on. It must be turf or
                     path all the way across: never `K` outline, never a stone,
                     never a flower.

Run after any tweak to ground.py.
"""

from pathlib import Path

from PIL import Image

from pixelkit import (
    GROUND_LINE, SCENE_PALETTE, SCENE_TIERS, VALUE_STEP, VALUE_STEP_MIN_DE,
    build, check_grid, delta_e, luminance, preview, report_separation, tier,
)

from ground import GROUND

ASSETS = Path(__file__).resolve().parent / "assets"

W, H = 160, 40
SCENE_TOP = 56                       # scene row the ground layer is composited at
FOOT_ROW = GROUND_LINE - SCENE_TOP   # 23 -- scene row 79 lands on GROUND row 23

GRASS = set("GgE")                   # turf: base, shadow patch, blade tip
PATH = set("Nn")                     # dirt: body, shadow
WALKABLE = GRASS | PATH


def pair_ok(a: str, b: str) -> tuple[bool, float, float, float, str]:
    """The same verdict report_separation() gives, for one ordered pair."""
    if a == b:
        return True, 0.0, 0.0, 0.0, "same colour"
    d = delta_e(a, b)
    vstep = abs(luminance(a) - luminance(b))
    kind, floor = tier(a, b, SCENE_TIERS)
    ok = d >= floor or (vstep >= VALUE_STEP and d >= VALUE_STEP_MIN_DE)
    return ok, d, vstep, floor, kind


def check_shape() -> list[str]:
    """40x160, palette-clean, fully opaque, and a walkable foot line."""
    problems = check_grid(GROUND, "ground")          # shape, keys, connectivity

    if len(GROUND) != H:
        problems.append(f"ground: {len(GROUND)} rows, expected {H}")

    for i, row in enumerate(GROUND):
        if len(row) != W:
            problems.append(f"ground: row {i} is {len(row)} cols, expected {W}")

    holes = [(x, y) for y in range(len(GROUND)) for x in range(len(GROUND[y]))
             if GROUND[y][x] == "."]
    if holes:
        problems.append(f"ground: {len(holes)} transparent pixel(s), e.g. {holes[:8]}")

    bad = sorted(set("".join(GROUND)) - set(SCENE_PALETTE))
    if bad:
        problems.append(f"ground: undefined palette keys {bad}")

    # The foot line has to be walkable: turf or dirt across the whole width.
    offenders = sorted({GROUND[FOOT_ROW][x] for x in range(W)} - WALKABLE)
    if offenders:
        problems.append(
            f"ground: foot line (row {FOOT_ROW} = scene row {GROUND_LINE}) "
            f"contains non-walkable colours {offenders}"
        )

    return problems


def check_seam() -> tuple[list[str], list[str]]:
    """Horizontal tileability. Returns (problems, report lines)."""
    problems: list[str] = []
    report: list[str] = []
    checked = 0
    worst = None

    # 1. Per row: the wrapped neighbour pair gets the identical treatment a real
    #    adjacency gets -- same dE76, same tier floor, same value-step escape.
    for y in range(len(GROUND)):
        a, b = GROUND[y][W - 1], GROUND[y][0]
        ok, d, vstep, floor, kind = pair_ok(a, b)
        checked += 1
        if a != b:
            if not ok:
                problems.append(
                    f"ground: seam row {y} col 159->0 is {a}-{b} dE={d:.1f} "
                    f"dL={vstep:.2f} below {floor:.0f} ({kind})"
                )
            if worst is None or d < worst[0]:
                worst = (d, y, a, b, floor, kind)

    report.append(f"seam rows checked  : {checked} ({W - 1}->0 on every row)")
    if worst:
        d, y, a, b, floor, kind = worst
        report.append(
            f"tightest seam pair : row {y} {a}-{b} dE={d:.1f} vs floor {floor:.0f} ({kind})"
        )
    else:
        report.append("tightest seam pair : every row wraps to the same colour")

    # 2. Stronger: duplicate the layer left-to-right and run the shared
    #    separation report over both copies. The seam is then just another
    #    adjacency, judged by the exact code path used everywhere else.
    tiled = [r + r for r in GROUND]
    seam_failures, _ = report_separation(tiled, "ground x2", tiers=SCENE_TIERS)
    seam_only = [f for f in seam_failures]
    if seam_only:
        problems += seam_only
    else:
        report.append("tiled 2x report    : no failures across 320 columns")

    return problems, report


def check_raster() -> list[str]:
    """The preview on disk must decode back to the authored grid, pixel for pixel."""
    path = ASSETS / "ground_preview.png"
    if not path.exists():
        return [f"ground: {path.name} missing -- run this script to render it"]
    img = Image.open(path).convert("RGBA")
    if (img.width, img.height) != (W * 4, H * 4):
        return [f"ground: {path.name} is {img.width}x{img.height}, expected {W * 4}x{H * 4}"]
    inv = {v: k for k, v in SCENE_PALETTE.items()}
    px = img.load()
    decoded = ["".join(inv[px[x * 4, y * 4]] for x in range(W)) for y in range(H)]
    return [] if decoded == GROUND else [f"ground: {path.name} does not match GROUND"]


def main() -> int:
    problems = check_shape()
    seam_problems, seam_report = check_seam()
    problems += seam_problems

    # Render first, then assert the PNG on disk decodes back to GROUND.
    ASSETS.mkdir(parents=True, exist_ok=True)
    out = ASSETS / "ground_preview.png"
    preview(build(GROUND), 4).save(out)
    problems += check_raster()

    print("-- ground layer (160x40, composited at scene rows 56..95) ----")
    print(f"  rows x cols        : {len(GROUND)} x {sorted({len(r) for r in GROUND})}")
    used = sorted(set("".join(GROUND)))
    print(f"  colours used       : {used}")
    print(f"  transparent pixels : {sum(r.count('.') for r in GROUND)}")
    print(f"  foot line row {FOOT_ROW:2d}    : {'walkable' if not problems else 'see failures'}"
          f" ({sorted(set(GROUND[FOOT_ROW]))})")

    # Where the dirt actually sits, per row -- the path's vertical envelope.
    band = [y for y in range(H) if sum(GROUND[y].count(c) for c in PATH) > W * 0.5]
    print(f"  path envelope      : rows {band[0]}..{band[-1]} (modal band), "
          f"foot row {FOOT_ROW} inside={band[0] <= FOOT_ROW <= band[-1]}")

    for line in seam_report:
        print(f"  {line}")

    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print("  ok    40x160, opaque, palette-clean, seamless, foot line walkable")

    print("\n-- colour separation against SCENE_TIERS --------------------")
    failures, rows = report_separation(GROUND, "ground", tiers=SCENE_TIERS)
    for line in failures:
        print(f"  FAIL  {line}")
    print(f"  pairs checked      : {len(rows)}")
    print(f"  failures           : {len(failures)}")

    print(f"\nwrote {out}  ({W * 4}x{H * 4}, 4x nearest)")

    return 1 if problems or failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
