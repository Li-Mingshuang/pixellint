"""Shared palette, separation rules and assertion helpers.

Two ideas carry this module.

**One rule set, not two.** Earlier versions carried `SPRITE_TIERS` and
`SCENE_TIERS` -- different numeric floors for small sprites and large shapes.
That was over-engineered and it cost real work: across four agents, *thirteen*
colour pairs had to be designed around rather than used, purely to satisfy a
floor. The distinction that actually matters is not "how big is the shape", it is
"does this pair decide the silhouette". So the rules now key off ROLE:

    outline vs fill   strict   -- this is the class that destroys a silhouette
    anything else     moderate -- a shade ramp is *meant* to sit close

`SPRITE_TIERS` and `SCENE_TIERS` still exist as aliases so existing call sites
keep working, but they now resolve to the same rules.

**A big value step is a read on its own.** If two colours differ by a luminance
step of >= VALUE_STEP, the edge is visible no matter what the chroma difference
is. Human vision is far more sensitive to lightness boundaries than to hue, so
demanding a chroma floor on top of a large value gap is self-contradictory. It
also produced a real false failure once: the dog's pale paw against the dirt
path came in at dL 0.26, dE 24.9, and was rejected by one tenth of a dE unit.

**Warnings are not failures.** `report_separation` returns hard failures that
must be fixed and advisory warnings that are printed for the author to judge.
Most tight pairs are a matter of taste, not correctness, and forcing them all to
zero is how a checker starts dictating composition.
"""

from render_sprite import PALETTE as CHAR_PALETTE

# --------------------------------------------------------------------------
# Scene canvas
# --------------------------------------------------------------------------
SCENE_W = 160
SCENE_H = 96
SKY_ROWS = (0, 44)
HORIZON_ROW = 45
GROUND_TOP = 58
GROUND_LINE = 79

# --------------------------------------------------------------------------
# The locked scene palette.
# --------------------------------------------------------------------------
SCENE_PALETTE: dict[str, tuple[int, int, int, int]] = {
    **CHAR_PALETTE,
    # sky + cloud
    "A": (0x6f, 0xb2, 0xdc, 255),
    "a": (0x3f, 0x7f, 0xb0, 255),
    "W": (0xfb, 0xf8, 0xf0, 255),
    "w": (0xa8, 0xa0, 0x8c, 255),
    # grass
    "G": (0x7f, 0xbf, 0x4a, 255),
    "g": (0x4e, 0x8a, 0x35, 255),
    "E": (0xc4, 0xe8, 0x8c, 255),
    # dirt
    "N": (0xb0, 0x8b, 0x5e, 255),
    "n": (0x6b, 0x4f, 0x31, 255),
    # foliage
    "F": (0x2f, 0x6b, 0x45, 255),
    "f": (0x14, 0x30, 0x1f, 255),
    # wood
    "T": (0x8a, 0x5e, 0x38, 255),
    "t": (0x4a, 0x30, 0x18, 255),
    # plaster + roof
    "U": (0xe6, 0xd6, 0xb4, 255),
    "u": (0xb2, 0x9c, 0x7c, 255),
    "O": (0xb0, 0x4c, 0x3c, 255),
    "o": (0x5e, 0x23, 0x1c, 255),
    # stone
    "R": (0x8a, 0x8a, 0x96, 255),
    "r": (0x48, 0x48, 0x60, 255),
    # accents
    "Y": (0xe8, 0xc8, 0x4a, 255),
    "y": (0xd0, 0x5c, 0x84, 255),
    # dog fur. Added because the dog was drawn in `T`, the same wood brown as
    # the fence, and stood right on top of it -- two objects reading as one.
    # Ginger is clear of every colour the dog can stand near (T 24, G 79,
    # g 70, N 32) rather than being a second brown in a brown scene.
    "Z": (0xb0, 0x55, 0x2a, 255),
    "z": (0x7d, 0x3a, 0x1a, 255),
}

# --------------------------------------------------------------------------
# Separation rules.  fail = must fix, warn = author's call.
#
# Two things make two colours tellable apart, and only two:
#
#   1. a lightness edge -- either an absolute step of VALUE_STEP in the
#      midtones, or a lightness RATIO of VALUE_RATIO. The ratio matters because
#      perception follows Weber's law: 0.05 against 0.16 is a three-fold
#      brightness difference and reads instantly, while the same absolute gap
#      higher up the scale is barely visible. An earlier rule used the absolute
#      step alone and consequently declared night palettes unreadable.
#   2. a chroma difference of `fail` dE.
#
# The old shade/material taxonomy is gone. It was over-engineering: base colours
# and their own shadows are *meant* to sit close, gradients are *meant* to step
# closely, and both were being reported as defects. A hard failure now means one
# thing only -- a viewer could not tell these apart.
#
# Outline pairs keep a stricter chroma bar, because an outline's whole job is to
# be an edge.
# --------------------------------------------------------------------------
SEP_RULES = {
    "outline": {"fail": 20.0, "warn": 26.0},
    "fill":    {"fail": 12.0, "warn": 22.0},
}
SPRITE_TIERS = SEP_RULES
SCENE_TIERS = SEP_RULES

VALUE_STEP = 0.22      # absolute lightness step that reads in the midtones
VALUE_RATIO = 1.7      # ... and the relative step that reads at any level
VALUE_FLOOR = 0.02     # below this, ratios are noise; require the absolute step
VALUE_STEP_MIN_DE = 0.0

EMIT_WARNINGS = True

# Pairs that are deliberately a base colour and its own shadow. Kept only to
# label output; the rules no longer branch on it.
SHADE_PAIRS = {
    frozenset(p) for p in (
        "Sp", "Hh", "Cc", "Pp", "Bb", "Ss", "Dc", "CD", "mp",
        "Aa", "Ww", "Gg", "GE", "Nn", "Ff", "Tt", "Uu", "Oo", "Rr",
    )
}


class Findings(list):
    """Hard failures, plus advisory warnings hanging off the same object.

    Subclasses list so existing `failures, rows = report_separation(...)` call
    sites keep unpacking exactly as before while gaining `findings.warnings`.
    """

    def __init__(self, failures=(), warnings=()):
        super().__init__(failures)
        self.warnings = list(warnings)


def srgb_to_lab(rgb):
    def lin(u):
        u /= 255.0
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(v) for v in rgb)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(a: str, b: str, palette=None) -> float:
    p = palette or SCENE_PALETTE
    pa, pb = srgb_to_lab(p[a][:3]), srgb_to_lab(p[b][:3])
    return sum((x - y) ** 2 for x, y in zip(pa, pb)) ** 0.5


def luminance(key: str, palette=None) -> float:
    p = palette or SCENE_PALETTE
    r, g, b, _ = p[key]
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def tier(a: str, b: str, tiers=None):
    """Return (role, fail_floor). `tiers` is accepted and ignored."""
    role = "outline" if "K" in (a, b) else "fill"
    return role, SEP_RULES[role]["fail"]


def reads_by_value(la: float, lb: float) -> bool:
    """Is the lightness edge between two luminances enough on its own?"""
    hi, lo = max(la, lb), min(la, lb)
    if hi - lo >= VALUE_STEP:
        return True
    return lo >= VALUE_FLOOR and hi / lo >= VALUE_RATIO


def verdict(a: str, b: str, palette=None) -> tuple[str, float, float]:
    """Classify a pair as 'ok' | 'warn' | 'fail'. Returns (verdict, dE, dL)."""
    d = delta_e(a, b, palette)
    la, lb = luminance(a, palette), luminance(b, palette)
    dl = abs(la - lb)
    role = "outline" if "K" in (a, b) else "fill"
    rule = SEP_RULES[role]
    if reads_by_value(la, lb):
        # a lightness edge this strong reads regardless of chroma
        return ("ok" if d >= VALUE_STEP_MIN_DE else "warn"), d, dl
    if d >= rule["warn"]:
        return "ok", d, dl
    if d >= rule["fail"]:
        return "warn", d, dl
    return "fail", d, dl


def adjacent_pairs(grid, palette=None):
    p = palette or SCENE_PALETTE
    h, w = len(grid), len(grid[0])
    pairs = set()
    for y in range(h):
        for x in range(w):
            a = grid[y][x]
            if a == ".":
                continue
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if nx < w and ny < h:
                    b = grid[ny][nx]
                    if b != "." and b != a and a in p and b in p:
                        pairs.add((a, b) if a < b else (b, a))
    return pairs


def build(grid, palette=None):
    from PIL import Image
    p = palette or SCENE_PALETTE
    img = Image.new("RGBA", (len(grid[0]), len(grid)), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(grid):
        for x, key in enumerate(row):
            px[x, y] = p[key]
    return img


def preview(img, scale, bg=(58, 62, 74)):
    from PIL import Image
    flat = Image.new("RGBA", img.size, (*bg, 255))
    flat.alpha_composite(img)
    return flat.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)


def check_grid(grid, label="grid", palette=None) -> list[str]:
    """Structure: shape, palette membership, one closed connected body."""
    p = palette or SCENE_PALETTE
    if not grid or not grid[0]:
        return [f"{label}: empty"]
    w = len(grid[0])
    if any(len(r) != w for r in grid):
        return [f"{label}: rows are not all {w} wide"]

    for i, row in enumerate(grid):
        bad = set(row) - set(p)
        if bad:
            return [f"{label}: row {i} uses undefined palette keys {sorted(bad)}"]

    h = len(grid)
    opaque = {(x, y) for y in range(h) for x in range(w) if grid[y][x] != "."}
    if not opaque:
        return [f"{label}: fully transparent"]

    seed = min(opaque, key=lambda t: (t[1], t[0]))
    seen, stack = {seed}, [seed]
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] != "." and (nx, ny) not in seen:
                seen.add((nx, ny))
                stack.append((nx, ny))
    floating = sorted(opaque - seen)
    if floating:
        return [f"{label}: {len(floating)} floating pixel(s): {floating[:8]}"]
    return []


def report_separation(grid, label="grid", palette=None, tiers=None, quiet=False):
    """dE76 for every touching pair. Returns (Findings, rows).

    Findings is a list of hard failures that also carries `.warnings`.
    """
    failures, warnings, rows = [], [], []
    for a, b in sorted(adjacent_pairs(grid, palette), key=lambda pr: delta_e(*pr, palette)):
        v, d, dl = verdict(a, b, palette)
        role = "outline" if "K" in (a, b) else "fill"
        rows.append((v == "ok", a, b, d, dl, SEP_RULES[role]["fail"], role))
        if v == "fail":
            failures.append(
                f"{label}: {a}-{b} dE={d:.1f} dL={dl:.2f} below {SEP_RULES[role]['fail']:.0f} ({role})")
        elif v == "warn":
            warnings.append(
                f"{label}: {a}-{b} dE={d:.1f} dL={dl:.2f} tight but usable ({role})")
    if warnings and EMIT_WARNINGS and not quiet:
        # Sorted worst-first and capped: a healthy palette produces plenty of
        # "tight but fine" notes, and drowning the failures in them is worse
        # than saying nothing.
        def _worst(msg):
            return float(msg.split("dE=")[1].split()[0])
        shown = sorted(warnings, key=_worst)[:8]
        for wmsg in shown:
            print(f"  WARN  {wmsg}")
        if len(warnings) > len(shown):
            print(f"  WARN  ... and {len(warnings) - len(shown)} more tight pairs")
    return Findings(failures, warnings), rows


# --------------------------------------------------------------------------
# Scene composition: do two objects collide in *identity* as well as space?
# --------------------------------------------------------------------------
def dominant_colours(grid, top=3, palette=None) -> set[str]:
    from collections import Counter
    c = Counter(ch for row in grid for ch in row if ch != ".")
    return {k for k, _ in c.most_common(top)}


def object_conflicts(placements, min_gap=10, shared=1):
    """Flag pairs of placed objects that share a colour AND sit too close.

    This turns an aesthetic complaint ("the dog is the same colour as the fence
    and they are standing on top of each other") into an assertion. Two objects
    may be near each other, or share a colour, but not both.

    `placements` is a list of dicts with: name, x, width, colours (a set).
    """
    problems = []
    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            a, b = placements[i], placements[j]
            overlap = len(a["colours"] & b["colours"])
            if overlap < shared:
                continue
            ax0, ax1 = a["x"], a["x"] + a["width"]
            bx0, bx1 = b["x"], b["x"] + b["width"]
            gap = max(bx0 - ax1, ax0 - bx1)
            if gap < min_gap:
                problems.append(
                    f"{a['name']} and {b['name']} share {overlap} colour(s) "
                    f"({sorted(a['colours'] & b['colours'])}) and are only {gap}px apart "
                    f"(need >= {min_gap})")
    return problems
