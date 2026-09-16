"""The player: a survivor in a dark green jacket, 24x32, side view facing right.

Authored the house way -- one character is one pixel is one index into
``gamepalette.GAME_PALETTE`` -- and verified by assertion rather than by eye.
Nothing here is traced or estimated: every frame is built from explicit row
strings so that the invariants ``check_player.py`` enforces are structural, not
hopeful.

Three invariants drive the whole layout, and each one is a design decision
before it is a test:

  * GROUND.  The boots' sole is row 31 in all nine frames.  Every clip -- idle,
    walk, shoot -- drops the sole on the same row, because a sprite whose feet
    move between clips floats and sinks when the game blits it at GROUND_Y.
    The two walk "passing" frames raise the body one row; the planted leg is
    therefore one row longer in those frames rather than the whole sprite being
    one row shorter.

  * HEAD LOCK.  ``HEAD`` is one 9x9 block, spliced in by ``compose`` with a
    byte-for-byte copy.  Its column never changes -- only its row, and by at
    most one -- so the head cannot jitter sideways.  The block is placed with
    an assertion that it never has to overwrite anything, which is what makes
    "byte-identical" true rather than merely intended.

  * LIGHT.  The light comes from the upper left, in every frame of every clip.
    Uppercase keys (J jacket, P pants, S skin, G/N gun) face up and left;
    their lowercase shadows (j, p, s, g) face down and right.  The far leg is
    drawn entirely in ``p``, which is both the correct shadow and what makes
    the two legs separable at all.

The gun is one shape per orientation, reused verbatim:

  * ``GUN_DOWN`` hangs muzzle-down from the hand in idle and in every walk
    frame -- "held low".  Only ``N``, ``G`` and ``g`` are ever visible on it
    below the fist, so its highlight/mid/dark read survives the grip.
  * ``GUN_SIDE`` points right, level with the shoulder, in the shoot clip.  The
    three shoot frames move it by whole pixels only -- raise (12,12), FIRE
    (14,10) with a muzzle flash, recover (13,11) -- so the kick is a rise plus
    an extension, and every step changes a comparable number of pixels.
"""

import sys
from pathlib import Path

from PIL import Image

# The palette and the assertion helpers live at the repo root, so a direct
# `python game/player.py` has to find them without being run as a module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gamepalette import GAME_PALETTE  # noqa: E402
from pixelkit import build, preview  # noqa: E402

# --------------------------------------------------------------------------
# Canvas
# --------------------------------------------------------------------------
W, H = 24, 32
GROUND_ROW = 31            # the sole row, identical in all nine frames
HEAD_COL = 6               # the head never leaves this column
HEAD_H = 9

# Rendering
SCALE = 6
PAD = 6
BG = (58, 62, 74)          # dark street grey
FRAME_MS = 90

# --------------------------------------------------------------------------
# The head.  9x9, facing right: crown outline, hair over the back and fringe,
# face at the front, one eye pixel, jaw tapering to the chin.  Light from the
# upper left, so the lower-front of the face carries the shadow tone.
# --------------------------------------------------------------------------
HEAD = [
    "..KKKKK..",   # crown
    ".KHHHHHK.",   #
    "KHHHHHHHK",   # hair
    "KHHHHHSSK",   # fringe ends, forehead appears
    "KHHHSSSSK",   # brow
    "KHHSSKSSK",   # eye (K) toward the front
    "KHSSSSSSK",   # cheek
    ".KSSSsSK.",   # jaw, shadow on the lower front
    "..KSSSK..",   # chin
]
HEAD_W = len(HEAD[0])

NECK_X, NECK = 8, "KsssK"

# --------------------------------------------------------------------------
# Torso.  (dx, row) where dx is added to TORSO_X; y0 is the shoulder row.
# --------------------------------------------------------------------------
TORSO_X = 5
_SH, _WA = (0, "KJJJJJJjjK"), (1, "KJJJJJjjK")
# The last hem row is deliberately all-over J rather than j.  j and p are the
# one pair in this palette that does not separate (dE 8.3), and the hips below
# are p, so the hem must not present its shadow to them: a lighting choice made
# *because* it is the readable one, not contortion to silence a warning.
_HE, _HEM = (0, "KJJJJJJjjK"), (0, "KJJJJJJJJK")
TORSO = [_SH, _SH, _SH, _WA, _WA, _WA, _HE, _HEM]              # 8 rows, y11-18
TORSO_BREATH = [_SH, _SH, _SH, _WA, _WA, _WA, _WA, _HE, _HEM]  # 9 rows, y10-18

HIPS_X, HIPS = 5, "KPPPPPPppK"

# --------------------------------------------------------------------------
# Legs.  A leg is a 5-wide rod (K + 3 fill + K) plus a boot; the near rod is
# P, the far rod is p.  Rod rows are (y, x); the boot is (x, y, width).
# --------------------------------------------------------------------------
LEG_STRIDE_A = {                       # contact: near foot forward
    "near": ([(20, 9), (21, 9), (22, 10), (23, 10), (24, 10),
              (25, 11), (26, 11), (27, 11), (28, 11)], (11, 29, 7)),
    "far":  ([(20, 5), (21, 5), (22, 4), (23, 4), (24, 4),
              (25, 3), (26, 3), (27, 3), (28, 3)], (3, 29, 6)),
}
LEG_STRIDE_B = {                       # contact: far foot forward
    "near": ([(20, 5), (21, 5), (22, 4), (23, 4), (24, 4),
              (25, 3), (26, 3), (27, 3), (28, 3)], (3, 29, 7)),
    "far":  ([(20, 9), (21, 9), (22, 10), (23, 10), (24, 10),
              (25, 11), (26, 11), (27, 11), (28, 11)], (11, 29, 6)),
}
LEG_STAND = {                          # both feet planted under the hips
    "near": ([(y, 9) for y in range(20, 29)], (9, 29, 7)),
    "far":  ([(y, 5) for y in range(20, 29)], (5, 29, 6)),
}
# Passing frames: the body is one row higher, so the hip row is 18 and the
# planted leg runs one row longer -- the sole still lands on row 31.
LEG_PASS_FAR_UP = {                    # near planted, far swinging through
    "near": ([(y, 9) for y in range(19, 29)], (9, 29, 7)),
    "far":  ([(y, 4) for y in range(19, 27)], (4, 27, 6)),
}
LEG_PASS_NEAR_UP = {                   # far planted, near swinging through
    "near": ([(y, 4) for y in range(19, 27)], (4, 27, 7)),
    "far":  ([(y, 9) for y in range(19, 29)], (9, 29, 6)),
}

# --------------------------------------------------------------------------
# Guns.  ``GUN_DOWN`` hangs muzzle-down from the fist; ``GUN_SIDE`` points
# right at shoulder height.
# --------------------------------------------------------------------------
GUN_DOWN = [
    ".KK.",
    "KGGK",
    "KGGK",
    "KNGK",   # first row the fist leaves visible
    "KGGK",
    "KNgK",
    ".KgK",
    ".KgK",
    ".KgK",
    ".KgK",
    ".KK.",   # muzzle
]
GUN_SIDE = [
    "..KKKKKK",   # 0  top of the receiver and barrel
    "KNNGGGGK",   # 1  barrel: highlight up-left, body, muzzle face at the right
    "KGggggKK",   # 2  underside in shadow
    ".KgK....",   # 3  pistol grip, hanging under the receiver's rear
]
# Offsets from the muzzle, so the flash is welded to the barrel end.  Every
# pixel is 4-adjacent to the muzzle outline: check_grid would fail otherwise.
FLASH = [(0, -1, "X"), (0, 0, "W"), (1, 0, "X"), (0, 1, "X"), (1, 1, "Y")]


# --------------------------------------------------------------------------
# Canvas helpers.  Overlap is an error unless it is deliberate, which is how
# the head lock and the limb attachments stay honest while composing.
# --------------------------------------------------------------------------
def blank():
    return [["."] * W for _ in range(H)]


def put(g, x, y, ch, force=False):
    if ch == ".":
        return
    if not (0 <= x < W and 0 <= y < H):
        raise IndexError(f"({x},{y}) is outside the {W}x{H} canvas")
    if g[y][x] != "." and g[y][x] != ch and not force:
        raise ValueError(f"overlap at ({x},{y}): {g[y][x]} would become {ch}")
    g[y][x] = ch


def text(g, x, y, s, force=False):
    for i, ch in enumerate(s):
        put(g, x + i, y, ch, force)


def block(g, b, x0, y0, force=False):
    for r, line in enumerate(b):
        text(g, x0, y0 + r, line, force)


def compose(*parts):
    g = blank()
    for fn in parts:
        fn(g)
    return ["".join(r) for r in g]


def head(g, dy):
    """Splice HEAD in whole.  Never overwrites: the block is placed, not drawn."""
    block(g, HEAD, HEAD_COL, dy)


def torso(g, y0, rows=None):
    text(g, NECK_X, y0 - 1, NECK)
    for i, (dx, row) in enumerate(rows or TORSO):
        text(g, TORSO_X + dx, y0 + i, row)


def leg(g, spec, fill, force=False, shade_from=None):
    """One leg: a 5-wide rod (K + 3 fill + K) over a boot.

    ``shade_from`` drops the rod's front column to the shadow tone from that row
    down -- the light is up and to the left, so the lower front goes dark.  The
    far leg is already drawn wholly in ``p``.
    """
    rows, (bx, by, bw) = spec
    for y, x in rows:
        if shade_from is not None and y >= shade_from:
            text(g, x, y, "K" + fill * 2 + "p" + "K", force=force)
        else:
            text(g, x, y, "K" + fill * 3 + "K", force=force)
    body = "K" + "B" * (bw - 2) + "K"
    text(g, bx, by, body, force=force)
    text(g, bx, by + 1, body, force=force)
    text(g, bx, by + 2, "K" * bw, force=force)


def legs(g, spec, hip_y, force=False):
    """Far leg first so the near leg occludes it, exactly as it would in life."""
    text(g, HIPS_X, hip_y, HIPS, force=force)
    leg(g, spec["far"], "p", force=force)
    leg(g, spec["near"], "P", force=True, shade_from=24)


# --------------------------------------------------------------------------
# Arms.  ``arm_down`` hangs the near arm off the shoulder and puts the fist on
# the pistol grip; ``arm_side`` reaches forward to a gun held at the shoulder.
# --------------------------------------------------------------------------
def arm_down(g, gun_x, gun_y):
    """Gun low in front of the hip.  Every part rides off gun_x/gun_y, so the
    whole arm swings with the weapon and the fist can never leave the grip."""
    dx = gun_x - GUN_X
    dy = gun_y - GUN_Y
    block(g, GUN_DOWN, gun_x, gun_y, force=True)          # gun first ...
    for y, x in [(12, 11), (13, 11), (14, 12), (15, 13)]:
        text(g, x + dx, y + dy, "KjjK", force=True)       # ... arm in front of it
    text(g, 13 + dx, 16 + dy, "KSSSK", force=True)        # ... then the fist
    text(g, 13 + dx, 17 + dy, "KSSsK", force=True)
    text(g, 13 + dx, 18 + dy, "KsssK", force=True)


def arm_side(g, gun_x, gun_y):
    """Gun up at the shoulder, held in both hands.

    Drawn back to front -- arm, then weapon, then fists -- because that is the
    depth order: the forearm passes behind the receiver and the hands close over
    the grip and the foregrip.  Getting this backwards buries the receiver under
    the sleeve and the weapon stops reading.
    """
    hy = gun_y + 3                     # the grip row, the last gun block row
    for y in range(12, hy + 1):        # 1. the near arm, behind the weapon
        text(g, min(gun_x, 10 + (y - 12)), y, "KjjK", force=True)
    block(g, GUN_SIDE, gun_x, gun_y, force=True)          # 2. the weapon
    text(g, gun_x + 1, hy, "KSSsK", force=True)           # 3. fist on the grip
    text(g, gun_x + 1, hy + 1, "KsssK", force=True)
    text(g, gun_x + 3, hy - 1, "KSSK", force=True)        # support hand, foregrip


def flash(g, gun_x, gun_y):
    mx, my = gun_x + 7, gun_y + 1                          # the muzzle face
    for dx, dy, ch in FLASH:
        put(g, mx + 1 + dx, my + dy, ch)


# --------------------------------------------------------------------------
# Frames.  LOW = head row 1, torso rows 11-18, hips 19.   HIGH = everything one
# row up and the planted leg one row longer, so the sole stays on row 31.
# --------------------------------------------------------------------------
LOW, HIGH = 1, 0
TORSO_LOW, TORSO_HIGH = 11, 10
HIP_LOW, HIP_HIGH = 19, 18
GUN_X, GUN_Y = 15, 16      # idle carry: clear of the thigh, muzzle to row 26


def idle_a():
    return compose(
        lambda g: head(g, LOW),
        lambda g: torso(g, TORSO_LOW),
        lambda g: legs(g, LEG_STAND, HIP_LOW),
        lambda g: arm_down(g, GUN_X, GUN_Y),
    )


def idle_b():
    # Breathing: the chest, shoulders, head, arms and gun all rise one row --
    # the torso stretches by a waist row rather than lifting off the hips, so
    # the jacket stays joined to the pelvis and the feet never move.
    return compose(
        lambda g: head(g, HIGH),
        lambda g: torso(g, TORSO_HIGH, TORSO_BREATH),
        lambda g: legs(g, LEG_STAND, HIP_LOW),
        lambda g: arm_down(g, GUN_X, GUN_Y - 1),
    )


def walk_frame(spec, hip_y, bob, swing):
    return compose(
        lambda g: head(g, LOW if bob == 0 else HIGH),
        lambda g: torso(g, TORSO_LOW if bob == 0 else TORSO_HIGH),
        lambda g: legs(g, spec, hip_y),
        lambda g: arm_down(g, GUN_X + swing, GUN_Y + bob),
    )


def shoot_frame(gx, gy, fired=False):
    def draw(g):
        arm_side(g, gx, gy)
        if fired:
            flash(g, gx, gy)
    return compose(
        lambda g: head(g, LOW),
        lambda g: torso(g, TORSO_LOW),
        lambda g: legs(g, LEG_STAND, HIP_LOW),
        draw,
    )


PLAYER = {
    "idle": [
        idle_a(),
        idle_b(),
    ],
    "walk": [
        walk_frame(LEG_STRIDE_A, HIP_LOW, 0, +1),    # contact, near foot forward
        walk_frame(LEG_PASS_FAR_UP, HIP_HIGH, -1, 0),  # passing, far leg swings
        walk_frame(LEG_STRIDE_B, HIP_LOW, 0, -1),    # contact, far foot forward
        walk_frame(LEG_PASS_NEAR_UP, HIP_HIGH, -1, 0),  # passing, near leg swings
    ],
    "shoot": [
        shoot_frame(12, 12),          # raise
        shoot_frame(14, 10, True),    # FIRE: kicked up, extended, flashing
        shoot_frame(13, 11),          # recover
    ],
}
CLIPS = ("idle", "walk", "shoot")


def all_frames():
    for name in CLIPS:
        for grid in PLAYER[name]:
            yield name, grid


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------
def sheet(path):
    """Every frame of every clip: one clip per row, frames left to right."""
    cols = max(len(PLAYER[c]) for c in CLIPS)
    cell_w, cell_h = W * SCALE, H * SCALE
    img = Image.new("RGBA", (cols * cell_w + PAD * (cols + 1),
                             len(CLIPS) * cell_h + PAD * (len(CLIPS) + 1)),
                    (30, 32, 40, 255))
    for r, name in enumerate(CLIPS):
        for c, grid in enumerate(PLAYER[name]):
            x = PAD + c * (cell_w + PAD)
            y = PAD + r * (cell_h + PAD)
            img.alpha_composite(preview(build(grid, GAME_PALETTE), SCALE, BG), (x, y))
    img.save(path)
    return path


def gif(path, clip="shoot"):
    frames = [
        preview(build(g, GAME_PALETTE), SCALE, BG).convert("RGB").convert(
            "P", palette=Image.Palette.ADAPTIVE, colors=64)
        for g in PLAYER[clip]
    ]
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=FRAME_MS, loop=0, optimize=False)
    return path


def main():
    out = Path(__file__).resolve().parent.parent / "assets"
    out.mkdir(parents=True, exist_ok=True)
    print(f"frames : {sum(len(PLAYER[c]) for c in CLIPS)} across {len(CLIPS)} clips, {W}x{H} each")
    print(f"ground : row {GROUND_ROW} (sole) in every frame")
    print(f"wrote  : {sheet(out / 'player_preview.png')}")
    print(f"wrote  : {gif(out / 'player_shoot.gif')}")


if __name__ == "__main__":
    main()
