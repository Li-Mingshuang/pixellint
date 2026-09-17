"""MECHPUP: a puppy in a mech suit. 24x18, 4-frame trot, facing right.

Palette: `gamepalette.GAME_PALETTE`, because a mech needs real metal and that
palette has it -- `G`/`g`/`N` are gunmetal, `H` is a warm brown for the dog
inside the suit, and `V` is a glowing optic. The scene palette only has stone
grey, which reads as masonry rather than armour.

    K  outline            G  armour plate        g  armour shadow
    N  armour highlight   H  fur (the dog)       V  optic, lit
    Y  energy, hot

Design: the dog is still a dog. The head carries a helmet with a lit visor band,
the back has a vent stack, and the paws are energy pads. Fur shows at the muzzle
-- a mech suit with nothing visible inside would just be a robot.

Geometry is a LEFT/RIGHT split, not a stack: columns 0-15 hold the torso and legs,
columns 16-23 hold the head. The two regions overlap vertically, so they are
composed per row rather than concatenated as blocks. An earlier version of this
file tried to stack them and produced garbage.

Ground row is 17 (the last row) in all four frames, and the head is byte-identical
across frames with whole-row shifts only -- both asserted in check_mechdog.py.
A trot at this size reads best as two visible legs, same as the 20x14 dog; four
legs turn into mush.
"""

from gamepalette import GAME_PALETTE
from pixelkit import build, preview

W, H = 24, 18
LEFT_W, RIGHT_W = 16, 8
GROUND_ROW = 17

# The head, columns 16-23. Spliced in whole and never redrawn per frame.
#
# The chin row is all outline. An earlier version ended on filled armour, which
# left four pixels of plate facing straight down with no edge -- the kind of thing
# that reads as a torn sprite and that the outline assertion catches immediately.
HELM = [
    ".KKKKKK.",       # 0  helmet crest
    "KGGGGGGK",       # 1
    "KGNNNGGK",       # 2  plate highlight
    "KGVVVVGK",       # 3  visor band, lit
    "KGVVVVGK",       # 4
    "KGGGGGGK",       # 5  jaw
    "KGHHHGGK",       # 6  muzzle -- the dog showing through
    ".KKKKKK.",       # 7  chin, all outline
]

# Torso and back, columns 0-15, nine rows. The RIGHT edge is `K` on every row:
# an earlier version tapered the plate inward and left several rows with bare
# armour facing transparency, which the outline rule catches and which read as a
# torn edge.
TORSO = [
    "....KKKKKKKKKKKK",   # 0  back plate
    "...KGGGGGGGGGGGK",   # 1
    "..KgNGGGGGGGGGGK",   # 2  vent highlight
    ".KgNGGGGGGGGGGGK",   # 3
    "KgNGGGGGGGGGGGGK",   # 4
    "KgNGGGGGGGGGGGGK",   # 5
    ".KgGGGGGGGGGGGGK",   # 6
    "..KgGGGGGGGGGGGK",   # 7
    "...KKKKKKKKKKKKK",   # 8  belly plate, fully outlined
]

# Tail, columns 0-4, four rows, sitting above the torso's top-left corner. The wag
# is the tail standing one row taller, and it is what separates the two contact
# frames.
#
# Two earlier attempts failed in instructive ways: widening the back plate's
# outline by two columns changed pixels without reading as a tail at all, and a
# diagonal tail put fill pixels against transparency with no outline. Both
# variants below are closed shapes whose base row touches the torso at col 4.
TAIL_UP = [
    "KKKK.",
    "KGGK.",
    "KGGK.",
    "KKKKK",
]
TAIL_DOWN = [
    ".....",
    "KKKK.",
    "KGGK.",
    "KKKKK",
]

# Legs, columns 0-15, authored PER ROLE. A grounded frame gets 4 rows and a blank
# row above the torso; a raised frame gets 5 rows and no blank. Both put the
# planted paw on row 17.
#
# Shifting one leg block up and dropping its last row is the obvious shortcut and
# it silently removes the paw pads; that is what the first version did.
#
# A LIFTED pad needs its own outline row underneath. It is in the air, so nothing
# else is there to edge it, and without it the assertion reports two bare `Y`
# pixels facing a gap.
LEGS_PLANTED = [               # 3 rows of leg + pad + contact outline
    ".....KGGK..KGGK.",
    ".....KGGK..KGGK.",
    ".....KYYK..KYYK.",
    ".....KKKK..KKKK.",
]
LEGS_FRONT_UP = [              # front leg one row short, pad edged from below
    ".....KGGK..KGGK.",
    ".....KGGK..KGGK.",
    ".....KGGK..KGGK.",
    ".....KGGK..KYYK.",
    ".....KYYK..KKKK.",
]
LEGS_REAR_UP = [               # rear leg one row short
    ".....KGGK..KGGK.",
    ".....KGGK..KGGK.",
    ".....KGGK..KGGK.",
    ".....KYYK..KGGK.",
    ".....KKKK..KYYK.",
]

TORSO_TOP, HELM_TOP, LEG_TOP = 4, 0, 13


def compose(raised: bool, legs: list[str], tail_up: bool) -> list[str]:
    """Assemble one frame.

    `raised` shifts the head and torso down by one row and hands the legs one
    extra row, which is what keeps the planted paw on row 17 in both cases. The
    tail rides on the same offset so it stays welded to the back plate.
    """
    tail = TAIL_UP if tail_up else TAIL_DOWN

    dy = 0 if raised else 1
    left, right = {}, {}
    for i, row in enumerate(tail):
        assert len(row) == 5, f"tail row {i} is {len(row)} wide, expected 5"
        left[dy + i] = row + "." * (LEFT_W - 5)
    for i, row in enumerate(TORSO):
        left[dy + TORSO_TOP + i] = row
    for i, row in enumerate(legs):
        left[dy + LEG_TOP + i] = row
    for i, row in enumerate(HELM):
        right[dy + HELM_TOP + i] = row

    grid = []
    for r in range(H):
        l = left.get(r, "." * LEFT_W)
        rt = right.get(r, "." * RIGHT_W)
        assert len(l) == LEFT_W and len(rt) == RIGHT_W, f"row {r}: {len(l)}+{len(rt)}"
        grid.append(l + rt)
    assert len(grid) == H, f"{len(grid)} rows"
    return grid


FRAMES = [
    compose(raised=False, legs=LEGS_PLANTED, tail_up=False),
    compose(raised=True, legs=LEGS_FRONT_UP, tail_up=True),
    compose(raised=False, legs=LEGS_PLANTED, tail_up=True),
    compose(raised=True, legs=LEGS_REAR_UP, tail_up=False),
]

# What this module delivers. HELM, TORSO, TAIL_* and LEGS_* are composition blocks
# that FRAMES is assembled from, so measuring both would double-count the same
# authored cells. Declaring exports beats growing an exclusion list in the
# measuring tool -- see docs/authoring.md.
SHIPPED = ("FRAMES",)

# Drawn in the GAME palette, not the scene one. This module lives at the repo root
# but a mech needs real metal, and only the game palette has gunmetal; measuring it
# against the scene palette reports `V` as an undefined key.
PALETTE = GAME_PALETTE

FRAME_MS = 140
SCALE = 8
PAD = 6
BG = GAME_PALETTE["R"]        # asphalt


def main() -> None:
    from pathlib import Path
    from PIL import Image

    out = Path(__file__).resolve().parent / "assets"
    out.mkdir(exist_ok=True)

    images = [build(g, GAME_PALETTE) for g in FRAMES]
    strip = Image.new("RGBA", (len(FRAMES) * W * SCALE + (len(FRAMES) + 1) * PAD,
                               H * SCALE + 2 * PAD), (28, 30, 36, 255))
    for i, im in enumerate(images):
        strip.alpha_composite(preview(im, SCALE, BG[:3]),
                              (PAD + i * (W * SCALE + PAD), PAD))
    strip.save(out / "mechdog_preview.png")

    gif = [preview(im, SCALE, BG[:3]).convert("RGB").convert(
        "P", palette=Image.Palette.ADAPTIVE, colors=64) for im in images]
    gif[0].save(out / "mechdog.gif", save_all=True, append_images=gif[1:],
                duration=FRAME_MS, loop=0, optimize=False)

    print(f"frames : {len(FRAMES)} of {W}x{H}")
    print(f"wrote  : {out / 'mechdog_preview.png'}")
    print(f"wrote  : {out / 'mechdog.gif'}  ({FRAME_MS}ms, loops)")


if __name__ == "__main__":
    main()
