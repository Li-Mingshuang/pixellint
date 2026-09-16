"""Four-frame front-facing walk cycle for the 16x32 character.

The cycle is the standard contact / passing / contact / passing rhythm:

    frame 0  contact   body low,  both feet planted, left arm swung forward
    frame 1  passing   body up 1, left foot lifted,   right leg extended
    frame 2  contact   body low,  both feet planted, right arm swung forward
    frame 3  passing   body up 1, right foot lifted,  left leg extended

Two rules make it read as walking instead of jittering, and both are asserted
in check_sprite.py rather than eyeballed:

  * the head never moves sideways -- only its row changes, by exactly 1px, on
    the passing frames.  A head that drifts a column between frames is the
    single most common reason a hand-made walk cycle looks wrong.
  * the planted foot always lands on the same ground row (30), so the
    character does not slide or float.
"""

from pathlib import Path

from PIL import Image

from render_sprite import H, PALETTE, W, build, preview

OUT_DIR = Path(__file__).resolve().parent / "assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Body block, low (head rows 1-10, torso 11-20).  Raised frames reuse this
# shifted up by one row.
HEAD = [
    ".....KKKKKK.....",  # 0 crown
    "....KHHHHHHK....",  # 1
    "...KhhhhHHHHK...",  # 2 hair highlight, light from upper-left
    "...KHHHHHHHHK...",  # 3 fringe
    "...KHSSSSSsHK...",  # 4 forehead
    "...KHSKSSKsHK...",  # 5 eyes
    "...KHSSSSSsHK...",  # 6
    "...KSSSmmSsSK...",  # 7 mouth
    "....KSSSSSSK....",  # 8 jaw taper
    ".....KssssK.....",  # 9 neck
]

TORSO = [
    "...KCCDDDDCCK...",  # shoulder line, 10 wide
    "..KCcCPCCPCcCK..",  # arms pop out 1px; overall straps from the shoulders
    "..KCcCPCCPCcCK..",
    "..KCcCPCCPCcCK..",
    "..KCcCPCCPCcCK..",
    "..KCcCPCCPCcCK..",
    "..KCCPPPPPPCCK..",  # bib
    "..KCCPPPPPPCCK..",
    "..KCCPPPPPPCCK..",
    "..KSCPPPPPPCSK..",  # both hands
]

# Both feet planted, ground row 30.  The last two rows are the arm-swing
# variants, which is what separates the two contact frames.
LEGS_PLANTED = [
    "...KPPPPPPPPK...",  # hips
    "...KPPPKKPPPK...",
    "...KPPPKKPPPK...",
    "...KPPPKKPPPK...",
    "...KPPPKKPPPK...",
    "...KpppKKpppK...",
    "...KpppKKpppK...",
    "..KBBBBKKBBBBK..",
    "..KbbbbKKbbbbK..",
    "..KKKKKKKKKKKK..",  # both soles on the ground
    "................",
]

# Body raised 1px: the lifted foot's sole sits one row higher than the planted
# foot's, which stays on row 30.
LEGS_LIFT_LEFT = [
    "...KPPPPPPPPK...",  # hips (row 20)
    "...KPPPKKPPPK...",
    "...KPPPKKPPPK...",
    "...KPPPKKPPPK...",
    "...KPPPKKPPPK...",
    "...KpppKKPPPK...",  # left leg is the short one, so it shades first
    "...KpppKKpppK...",
    "..KBBBBKKpppK...",  # left boot top (lifted)
    "..KbbbbKKBBBBK..",  # left boot body / right boot top
    "..KKKKKKKbbbbK..",  # left sole at 29 ... right boot body
    "........KKKKKK..",  # right sole still on the ground at 30
]

LEGS_LIFT_RIGHT = [
    "...KPPPPPPPPK...",
    "...KPPPKKPPPK...",
    "...KPPPKKPPPK...",
    "...KPPPKKPPPK...",
    "...KPPPKKPPPK...",
    "...KPPPKKpppK...",
    "...KpppKKpppK...",
    "...KpppKKBBBBK..",  # right boot top (lifted)
    "..KBBBBKKbbbbK..",
    "..KbbbbKKKKKKK..",  # right sole at 29
    "..KKKKKK........",  # left sole still on the ground at 30
]


def frame(*, raised: bool, legs: list[str], torso: list[str] | None = None) -> list[str]:
    """Compose one 16x32 frame from the shared head/torso/leg blocks.

    The ``legs`` block is authored so that its first row is the hip row: 21 for
    a grounded frame, 20 for a raised one.  Raising therefore means the whole
    body block simply starts one row higher -- the planted foot stays on row 30
    either way, which is what stops the character from floating.
    """
    body = HEAD + (torso or TORSO)
    pad = "................"
    if raised:
        grid = body + legs + [pad]      # rows 0-19 body, 20-30 legs, 31 empty
    else:
        grid = [pad] + body + legs      # row 0 empty, 1-20 body, 21-31 legs
    assert len(grid) == H, f"frame is {len(grid)} rows, expected {H}"
    return grid


# Contact frames: the arm that swings forward gets a hand on the bottom torso
# row, the arm that swings back ends one row higher and leaves a gap below.
TORSO_LEFT_ARM_FWD = TORSO[:-2] + [
    "..KCCPPPPPPCSK..",  # right arm ended: hand one row up
    "..KSCPPPPPPCK...",  # left hand down and forward
]
TORSO_RIGHT_ARM_FWD = TORSO[:-2] + [
    "..KSCPPPPPPCCK..",  # left arm ended
    "...KCPPPPPPCSK..",  # right hand down and forward
]

FRAMES: list[list[str]] = [
    frame(raised=False, legs=LEGS_PLANTED, torso=TORSO_LEFT_ARM_FWD),
    frame(raised=True, legs=LEGS_LIFT_LEFT),
    frame(raised=False, legs=LEGS_PLANTED, torso=TORSO_RIGHT_ARM_FWD),
    frame(raised=True, legs=LEGS_LIFT_RIGHT),
]

SCALE = 8
GIF_SCALE = 16
BG = (58, 62, 74)


def main() -> None:
    images = [build(g) for g in FRAMES]

    # Side-by-side strip with the ground line drawn in, so a sliding foot is
    # obvious at a glance.
    pad = 6
    strip = Image.new(
        "RGBA", (len(images) * W * SCALE + pad * (len(images) + 1), H * SCALE + pad * 2),
        (30, 32, 40, 255),
    )
    for i, img in enumerate(images):
        strip.alpha_composite(preview(img, SCALE, BG), (pad + i * (W * SCALE + pad), pad))
        # ground line
        gy = pad + 30 * SCALE + SCALE - 1
        for x in range(pad + i * (W * SCALE + pad), pad + i * (W * SCALE + pad) + W * SCALE):
            strip.putpixel((x, gy), (255, 90, 90, 255))
    strip_path = OUT_DIR / "walk_strip.png"
    strip.save(strip_path)

    # Looping GIF on a flat backdrop.  Two scales: 8x for reference, 16x so the
    # animation is actually judgeable on a modern display.
    for scale, name in ((SCALE, "walk.gif"), (GIF_SCALE, "walk_large.gif")):
        frames = [
            preview(img, scale, BG).convert("RGB").convert(
                "P", palette=Image.Palette.ADAPTIVE, colors=64
            )
            for img in images
        ]
        path = OUT_DIR / name
        frames[0].save(
            path,
            save_all=True,
            append_images=frames[1:],
            duration=130,
            loop=0,
            optimize=False,
        )
        print(f"wrote     : {path}  ({W * scale}x{H * scale}, {len(frames)} frames)")

    for i, img in enumerate(images):
        img.save(OUT_DIR / f"walk_f{i}.png")

    print(f"frames    : {len(FRAMES)}  ({W}x{H} each)")
    print(f"wrote     : {strip_path}")
    print(f"wrote     : {OUT_DIR / 'walk_f0.png'} .. walk_f{len(FRAMES) - 1}.png")


if __name__ == "__main__":
    main()
