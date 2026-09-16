"""A small friendly farm dog, drawn as a 20x14 four-frame trot cycle.

Authored the house way: every frame is a list of equal-length strings, one
character per pixel, one index into ``pixelkit.SCENE_PALETTE``.  Nothing is
computed at build time -- what you read below is exactly what gets rasterised.

Design notes
------------
The dog is a *side profile facing right*, so it trots beside the front-facing
character without fighting it for the viewer's eye.  It is 20 wide, 14 tall,
and every frame is the same three stacks:

    rows 0- 8   upper body: tail + back + chest + head   (head is x12-x19)
    rows 9-13   legs (5 rows when the body is up, 4 when it is down)
    row  13     paws.  Always.  A dog that floats one frame reads as broken.

The cycle is the standard trot, and the two rules that keep it from looking
hand-made are asserted in ``check_dog.py`` rather than eyeballed:

  * the head is the *same nine-byte window* in all four frames and only ever
    moves by a whole row (1px, in lockstep with the body bob).  A face that
    drifts a column between frames is the classic tell of a jittery cycle.
  * the planted paw lands on row 13 in every frame, and the lifted paw lands
    on row 12 -- alternating front, back, front, back.

Palette
-------
Four keys, on purpose: ``T`` ginger fur, ``S`` cream muzzle/brisket/paws,
``K`` outline + eye, ``y`` pink tongue.

The obvious next step -- shading the fur with ``t`` (wood shadow) -- is illegal
in this palette: ``t`` against the outline ``K`` is dE 24.7 with dL 0.12, under
the 28 outline floor, and the value-step escape cannot rescue it (0.12 < 0.25).
Every fur pixel of a 20x14 dog touches the outline somewhere, so a ``t``-shaded
coat would mean fencing ``t`` into an interior stripe, which at this size reads
as more outline rather than as shading.  The cream ``S`` carries the form
instead: dE 41.6 from ``T`` with a 0.43 luminance step, so the muzzle, brisket
and socks each read as their own material.

``N``/``n`` dirt-browns were the other candidate (both clear the outline tier
against ``K`` and would have allowed a genuine two-tone coat), and were rejected
because the dog trots *on* the dirt path, which is ``N`` itself -- a dirt-brown
dog would dissolve into the ground it stands on.
"""

from pathlib import Path

from PIL import Image

from pixelkit import SCENE_PALETTE, build, preview

OUT_DIR = Path(__file__).resolve().parent / "assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 20, 14

# --------------------------------------------------------------------------
# The head block.  Columns 12-19 (8 wide) x 6 rows, byte-identical in every
# frame -- check_dog.py scans every row *and* column offset to prove it never
# shifts sideways.
#
#   r0  .KK.....   ear tip          r3  KTKTSSSK   eye, cream muzzle, nose
#   r1  KTTK....   ear              r4  KTTTSSSK   cheek, muzzle, nose
#   r2  KTTTKKKK   crown + muzzle   r5  KKTTSyK.   jaw, tongue hanging out
# --------------------------------------------------------------------------
HEAD = [
    ".KK.....",
    "KZZK....",
    "KZZZKKKK",
    "KZKZSSSK",
    "KZZZSSSK",
    "KKZZSyK.",
]

HEAD_COL = 12           # x of HEAD[0][0]
HEAD_H = len(HEAD)      # 6

GROUND_ROW = 13         # the row the planted paws land on
BOB_ROWS = (1, 0, 1, 0)  # head/body row offset per frame: 1px bob, twice

# --------------------------------------------------------------------------
# The frames.  Frame 0 and 2 are contact (body low, both paws down); 1 and 3
# are passing (body up 1, front paw lifted / rear paw lifted).  The tail sways
# left-mid-right-mid, which is what separates the two contact frames.
# --------------------------------------------------------------------------
DOG_FRAMES: list[list[str]] = [
    # frame 0 - contact, body low, tail swung left, both paws planted
    [
        "....................",
        ".............KK.....",
        ".KK.........KZZK....",
        "KZZK........KZZZKKKK",
        "KZZK........KZKZSSSK",
        ".KZZKKKKKKKKKZZZSSSK",
        "..KZZZZZZZZZKKZZSyK.",
        "..KZZZZZZSSK........",
        "..KZZZZZZSSK........",
        "..KKKKKKKKKK........",
        "...KZZK.KZZK........",
        "...KZZK.KZZK........",
        "...KZZK.KZZK........",
        "...KSSSKSSSK........",
    ],
    # frame 1 - passing, body up 1, tail up the middle, FRONT paw lifted
    [
        ".............KK.....",
        "..KK........KZZK....",
        ".KZZK.......KZZZKKKK",
        ".KZZK.......KZKZSSSK",
        ".KZZKKKKKKKKKZZZSSSK",
        "..KZZZZZZZZZKKZZSyK.",
        "..KZZZZZZSSK........",
        "..KZZZZZZSSK........",
        "..KKKKKKKKKK........",
        "...KZZK.KZZK........",
        "...KZZK.KZZK........",
        "...KZZK.KZZK........",
        "...KZZKSSSK.........",
        "...KSSSK............",
    ],
    # frame 2 - contact, body low, tail swung right, both paws planted
    [
        "....................",
        ".............KK.....",
        "...KK.......KZZK....",
        "..KZZK......KZZZKKKK",
        "..KZZK......KZKZSSSK",
        ".KZZKKKKKKKKKZZZSSSK",
        "..KZZZZZZZZZKKZZSyK.",
        "..KZZZZZZSSK........",
        "..KZZZZZZSSK........",
        "..KKKKKKKKKK........",
        "...KZZK.KZZK........",
        "...KZZK.KZZK........",
        "...KZZK.KZZK........",
        "...KSSSKSSSK........",
    ],
    # frame 3 - passing, body up 1, tail up the middle, REAR paw lifted
    [
        ".............KK.....",
        "..KK........KZZK....",
        ".KZZK.......KZZZKKKK",
        ".KZZK.......KZKZSSSK",
        ".KZZKKKKKKKKKZZZSSSK",
        "..KZZZZZZZZZKKZZSyK.",
        "..KZZZZZZSSK........",
        "..KZZZZZZSSK........",
        "..KKKKKKKKKK........",
        "...KZZK.KZZK........",
        "...KZZK.KZZK........",
        "...KZZK.KZZK........",
        "....KSSSKZZK........",
        ".......KSSSK........",
    ],
]

FRAME_MS = 140
SCALE = 8
PAD = 6
BG = SCENE_PALETTE["G"][:3]     # grass green, so the dog is judged on grass
GROUND = SCENE_PALETTE["g"][:3]  # grass shadow, marks the row the paws land on


def main() -> None:
    images = [build(g) for g in DOG_FRAMES]

    # Side-by-side strip.  The ground line is drawn in the padding *below* each
    # sprite rather than across it, so the paws stay exactly as authored and the
    # raster can be decoded straight back into the grids by check_dog.py.
    strip = Image.new(
        "RGBA",
        (len(images) * W * SCALE + PAD * (len(images) + 1), H * SCALE + PAD * 2),
        (*GROUND, 255),
    )
    for i, img in enumerate(images):
        x0 = PAD + i * (W * SCALE + PAD)
        strip.alpha_composite(preview(img, SCALE, BG), (x0, PAD))
        for x in range(x0, x0 + W * SCALE):
            for y in range(PAD + H * SCALE, PAD + H * SCALE + 3):
                strip.putpixel((x, y), (*GROUND, 255))
    preview_path = OUT_DIR / "dog_preview.png"
    strip.save(preview_path)

    # Looping GIF, one lap per 140ms frame.
    gif_frames = [
        preview(img, SCALE, BG).convert("RGB").convert(
            "P", palette=Image.Palette.ADAPTIVE, colors=64
        )
        for img in images
    ]
    gif_path = OUT_DIR / "dog.gif"
    gif_frames[0].save(
        gif_path,
        save_all=True,
        append_images=gif_frames[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=False,
    )

    used = sorted({c for g in DOG_FRAMES for row in g for c in row if c != "."})
    print(f"grid      : {W}x{H} x {len(DOG_FRAMES)} frames")
    print(f"colours   : {len(used)} used -> {used}")
    print(f"ground    : planted paws on row {GROUND_ROW} in every frame")
    print(f"wrote     : {preview_path}  ({strip.width}x{strip.height})")
    print(f"wrote     : {gif_path}  ({W * SCALE}x{H * SCALE}, {FRAME_MS}ms/frame)")


if __name__ == "__main__":
    main()
