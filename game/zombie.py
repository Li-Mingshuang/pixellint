"""The zombie: a 22x32 side-view shambler, facing LEFT, in three clips.

Authored the house way -- every frame below is an explicit list of 32 strings
of 22 characters, one character per pixel, one index into
``gamepalette.GAME_PALETTE``.  Nothing is computed at build time; what you read
is what gets rasterised.  ``check_zombie.py`` proves it instead of an eye.

    ZOMBIE["walk"]    4 frames   the lurch: uneven gait, one shoulder dropped
    ZOMBIE["attack"]  2 frames   the arms come up and reach forward
    ZOMBIE["death"]   5 frames   stagger, buckle, fold, hit the ground, settle

Design notes
------------
*Sickly green skin* ``Z`` with ``z`` shadows, *ragged clothes* ``Q`` with ``q``,
one *glowing eye* ``V`` two pixels wide, and a ``K`` outline.  Six keys, no
more -- it is a night sprite and every extra tone is one more thing the eye has
to sort out in the dark.

*It has to look wrong.*  The head is set forward of the chest on a four-pixel
black neck, so the skull juts out over the body; the crown sits back of centre
so the face tilts down.  The back shoulder arrives two rows late (``b2`` versus
the front one at ``b0``) -- that is the dropped shoulder.  The near arm hangs in
front of the chest in lit rags ``Q``, drifting two pixels forward on the way
down; the far arm hangs off the dropped shoulder *behind* the body in shadowed
rags ``q``, one pixel further down again.  Nothing is mirrored from the player.

*Light from the upper left*, in every frame: the leading edge of every limb and
the top of the skull are ``Z``/``Q``, the trailing and lower edges are ``z``/``q``,
the far arm is ``q`` throughout, and the black outline sits under and behind.

*Grounding.*  Walk and attack all put the lowest opaque pixel on row 31 -- the
low frame's leg is one row of art shorter than the high frame's, so the knee
bends while the planted sole stays exactly where it was.  In the passing frames
only the planted foot reaches row 31; the lifted one holds at row 30.

*The head is a window, not a drawing per frame.*  ``HEAD`` is the same ten by
nine block in all four walk frames and only ever moves by whole rows (row 1 on
the contact frames, row 0 on the passing ones), which is why the head lolls
without the cycle looking jittery.  ``check_zombie.py`` scans every row and
column offset to prove it never drifts sideways.

*The death clip is a collapse, measured.*  The body's total opaque height runs
30, 25, 15, 9, 7 rows: it only ever goes down.  The last two frames drop the eye
entirely -- the glow going out is the read that it is finished, and the head
block changes to ``HEAD_DOWN``, which is the same skull squashed flat with a
dead socket where the glow was.
"""

import sys
from pathlib import Path

from PIL import Image

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gamepalette import GAME_PALETTE          # noqa: E402
from pixelkit import build, preview           # noqa: E402

W, H = 22, 32
GROUND_ROW = 31          # the row a planted sole lands on, in walk and attack
FRAME_MS = 110           # one frame of the death clip
SCALE = 6                # preview / gif upscale
PAD = 6                  # gap between frames in the preview sheet
BG = (26, 28, 34)        # dark night backdrop, so the sprite is judged at night

OUT_DIR = _ROOT / "assets"

HEAD_COL = 3             # x of HEAD[0][0] in every walk and attack frame

# The head block, ten wide by nine tall, at column HEAD_COL of every walk and
# attack frame.  Byte-identical in all of them: the walk cycle's head is only
# ever allowed to move by whole rows, and check_zombie.py scans every row *and*
# column offset to prove it never shifts sideways.
#
#   h0  ...KKKK...   crown, set back so the skull tilts forward
#   h1  .KKZZZZKK.   skull
#   h2  KZZZZZzzK.   brow
#   h3  KZVVZZzzK.   the glowing eye, two pixels, dead centre of the face
#   h4  KZZZZZZzK.   cheek
#   h5  KZZKKZzK..   the mouth, a black slot under the eye
#   h6  KZZZZZzK..   jaw
#   h7  KZZZZZK...   chin
#   h8  ..KKKK....   neck stub: four pixels of shadow under the jaw
HEAD = [
    "...KKKK...",
    ".KKZZZZKK.",
    "KZZZZZzzK.",
    "KZVVZZzzK.",
    "KZZZZZZzK.",
    "KZZKKZzK..",
    "KZZZZZzK..",
    "KZZZZZK...",
    "..KKKK....",
]

# The same skull, squashed flat with the glow out: the last two death frames.
HEAD_DOWN = [
    ".KKKKK....",
    "KZZZZzK...",
    "KZKZZzzK..",
    "KZZZZZzK..",
    "KZZKKzzK..",
    ".KKKKKK...",
]

ZOMBIE: dict[str, list[list[str]]] = {
    # -- walk --------------------------------------------------------------
    "walk": [
        # frame 0  contact -- front foot forward, both soles on 31, body low
        [
            "......................",
            "......KKKK............",
            "....KKZZZZKK..........",
            "...KZZZZZzzK..........",
            "...KZVVZZzzK..........",
            "...KZZZZZZzK..........",
            "...KZZKKZzK...........",
            "...KZZZZZzK...........",
            "...KZZZZZK............",
            ".....KKKK.............",
            "......KQQQqK..........",
            "....KQqKQQQqqK........",
            "....KQqKQQQqqqKqqK....",
            "...KQqKQQQQQqqKqqK....",
            "...KQqKQQQQqqqKqqK....",
            "...KQqKQQQQqqqKqqK....",
            "...KQqKQQQQqqqKqqK....",
            "..KQqKKQQQQqqqKqqK....",
            "..KQqKKQQQqqqqKqqK....",
            "..KQqKKQQqqqqKqqK.....",
            "..KQqKQQqqqqqKqqK.....",
            "..KZzKQQqqqqKKqzK.....",
            "..KZzKQqqqqqKKzzK.....",
            "......KQQQQqqK........",
            ".....KQqK.KQqK........",
            ".....KQqK.KQqK........",
            "....KQqK...KQqK.......",
            "....KZzK...KZzK.......",
            "....KZzK...KZzK.......",
            "...KZzK....KZzK.......",
            "..KZZzK...KZZzK.......",
            "..KKZZzKK.KKZZzKK.....",
        ],
        # frame 1  passing -- body up one, back leg swinging through, lifted
        [
            "......KKKK............",
            "....KKZZZZKK..........",
            "...KZZZZZzzK..........",
            "...KZVVZZzzK..........",
            "...KZZZZZZzK..........",
            "...KZZKKZzK...........",
            "...KZZZZZzK...........",
            "...KZZZZZK............",
            ".....KKKK.............",
            "......KQQQqK..........",
            "....KQqKQQQqqK........",
            "....KQqKQQQqqqKqqK....",
            "...KQqKQQQQQqqKqqK....",
            "...KQqKQQQQqqqKqqK....",
            "...KQqKQQQQqqqKqqK....",
            "...KQqKQQQQqqqKqqK....",
            "...KQqKQQQQqqqKqqK....",
            "...KQqKQQQqqqqKqqK....",
            "...KQqKQQqqqqKqqK.....",
            "...KQqKQqqqqqKqqK.....",
            "...KZzKQqqqqKKqzK.....",
            "...KZzKqqqqqKKzzK.....",
            "......KQQQQqqK........",
            "......KQqK.KQqK.......",
            "......KQqK.KQqK.......",
            "......KQqKKQqK........",
            ".....KQqK.KZzK........",
            ".....KZzKKZzK.........",
            ".....KZzKKZZzK........",
            "....KZzK.KZZzK........",
            "...KZZzK.KKZZzKK......",
            "...KKZZzKK............",
        ],
        # frame 2  contact -- the short shuffling half-step, feet close together
        [
            "......................",
            "......KKKK............",
            "....KKZZZZKK..........",
            "...KZZZZZzzK..........",
            "...KZVVZZzzK..........",
            "...KZZZZZZzK..........",
            "...KZZKKZzK...........",
            "...KZZZZZzK...........",
            "...KZZZZZK............",
            ".....KKKK.............",
            "......KQQQqK..........",
            "....KQqKQQQqqK........",
            "....KQqKQQQqqqKqqK....",
            "...KQqKQQQQQqqKqqK....",
            "...KQqKQQQQqqqKqqK....",
            "...KQqKQQQQqqqKqqK....",
            "...KQqKQQQQqqqKqqK....",
            "..KQqKKQQQQqqqKqqK....",
            "..KQqKKQQQqqqqKqqK....",
            "..KQqKKQQqqqqKqqK.....",
            "..KQqKQQqqqqqKqqK.....",
            ".KZzKKQQqqqqKKqzK.....",
            ".KZzKKQqqqqqKKzzK.....",
            "......KQQQQqqK........",
            ".......KQqKQqK........",
            ".......KQqKQqK........",
            "......KQqKKQqK........",
            "......KZzKKZzK........",
            "......KZzKKZzK........",
            ".....KZzK.KZzK........",
            "....KZZzKKZZzK........",
            "....KKZZzKKZZzKK......",
        ],
        # frame 3  passing -- front foot lifted, the drag that starts the lurch
        [
            "......KKKK............",
            "....KKZZZZKK..........",
            "...KZZZZZzzK..........",
            "...KZVVZZzzK..........",
            "...KZZZZZZzK..........",
            "...KZZKKZzK...........",
            "...KZZZZZzK...........",
            "...KZZZZZK............",
            ".....KKKK.............",
            "......KQQQqK..........",
            "....KQqKQQQqqK........",
            "....KQqKQQQqqqKqqK....",
            "...KQqKQQQQQqqKqqK....",
            "...KQqKQQQQqqqKqqK....",
            "...KQqKQQQQqqqKqqK....",
            "...KQqKQQQQqqqKqqK....",
            "..KQqKKQQQQqqqKqqK....",
            "..KQqKKQQQqqqqKqqK....",
            "..KQqKKQQqqqqKqqK.....",
            "..KQqKQQqqqqqKqqK.....",
            "..KZzKQQqqqqKKqzK.....",
            "..KZzKQqqqqqKKzzK.....",
            "......KQQQQqqK........",
            ".....KQqK..KQqK.......",
            ".....KQqK..KQqK.......",
            ".....KQqK..KQqK.......",
            "....KZzK....KQqK......",
            "....KZzK....KZzK......",
            "....KZzK....KZzK......",
            "...KZZzK....KZzK......",
            "..KKZZzKK..KZZzK......",
            "...........KKZZzKK....",
        ],
    ],
    # -- attack ------------------------------------------------------------
    "attack": [
        # frame 0  winding up -- the near arm rises to chest height, the far arm
        [
            "......................",
            "......KKKK............",
            "....KKZZZZKK..........",
            "...KZZZZZzzK..........",
            "...KZVVZZzzK..........",
            "...KZZZZZZzK..........",
            "...KZZKKZzK...........",
            "...KZZZZZzK...........",
            "...KZZZZZK............",
            ".....KKKK.............",
            "......KQQQqK..........",
            "....KQqKQQQqqK........",
            "...KqqKQQQQqqqK.......",
            ".KqzKQqKQQQQqqK.......",
            "...KQqKQQQQqqqK.......",
            "..KQqKQQQQQqqqK.......",
            ".KZzKKQQQQQqqqK.......",
            "..KZzKKQQQQqqqK.......",
            "......KQQQqqqqK.......",
            "......KQQqqqqK........",
            ".....KQQqqqqqK........",
            ".....KQQqqqqK.........",
            ".....KQqqqqqK.........",
            "......KQQQQqqK........",
            "....KQqK...KQqK.......",
            "....KQqK...KQqK.......",
            "...KQqK.....KQqK......",
            "...KZzK.....KZzK......",
            "..KZzK......KZzK......",
            "..KZZzK.....KZzK......",
            ".KZZzK.....KZZzK......",
            ".KKZZzKK...KKZZzKK....",
        ],
        #          still hangs, which is what makes the reach read as a reach
        [
            "......................",
            "......KKKK............",
            "....KKZZZZKK..........",
            "...KZZZZZzzK..........",
            "...KZVVZZzzK..........",
            "...KZZZZZZzK..........",
            "...KZZKKZzK...........",
            "...KZZZZZzK...........",
            "...KZZZZZK............",
            ".....KKKK.............",
            "......KQQQqK..........",
            "....KQqKQQQqqK........",
            ".....KQQQQQqqqK.......",
            "KqqqqqKQQQQQqqK.......",
            "KzzqqqKQQQQqqqK.......",
            "KQQQQQKQQQQqqqK.......",
            "KZZQQQKQQQQqqqK.......",
            "......KQQQQqqqK.......",
            "......KQQQqqqqK.......",
            "......KQQqqqqK........",
            ".....KQQqqqqqK........",
            ".....KQQqqqqK.........",
            ".....KQqqqqqK.........",
            "......KQQQQqqK........",
            "....KQqK...KQqK.......",
            "....KQqK...KQqK.......",
            "...KQqK.....KQqK......",
            "...KZzK.....KZzK......",
            "..KZzK......KZzK......",
            "..KZZzK.....KZzK......",
            ".KZZzK.....KZZzK......",
            ".KKZZzKK...KKZZzKK....",
        ],
    ],
    # -- death -------------------------------------------------------------
    "death": [
        # frame 0  the hit -- on both feet still, arms flung forward, 30 rows tall
        [
            "......................",
            "......................",
            "......KKKK............",
            "....KKZZZZKK..........",
            "...KZZZZZzzK..........",
            "...KZVVZZzzK..........",
            "...KZZZZZZzK..........",
            "...KZZKKZzK...........",
            "...KZZZZZzK...........",
            "...KZZZZZK............",
            ".....KKKK.............",
            "......KQQQqK..........",
            "....KQqKQQQqqK........",
            "...KQqKQQQQqqqKqqK....",
            "..KQqKKQQQQQqqKqqK....",
            ".KQqKKQQQQQqqqKqqK....",
            ".KZzKKQQQQQqqqKqqK....",
            ".....KQQQQQqqqKqqK....",
            "......KQQQQqqqKqqK....",
            "......KQQQqqqqKqqK....",
            "......KQQqqqqKqqK.....",
            ".....KQQqqqqqKqqK.....",
            ".....KQQqqqqKKqzK.....",
            ".....KQqqqqqKKzzK.....",
            "......KQQQQqqK........",
            ".....KQqK.KQqK........",
            ".....KQqK.KQqK........",
            "....KQqK..KQqK........",
            "....KZzK...KZzK.......",
            "...KZzK....KZzK.......",
            "..KZZzK...KZZzK.......",
            "..KKZZzKK.KKZZzKK.....",
        ],
        # frame 1  knees buckle -- the body sags into a squat, 25 rows
        [
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......KKKK............",
            "....KKZZZZKK..........",
            "...KZZZZZzzK..........",
            "...KZVVZZzzK..........",
            "...KZZZZZZzK..........",
            "...KZZKKZzK...........",
            "...KZZZZZzK...........",
            "...KZZZZZK............",
            ".....KKKK.............",
            "......KQQQqK..........",
            "....KQqKQQQqqK........",
            "...KQqKQQQQqqqKqqK....",
            "...KQqKQQQQQqqKqqK....",
            "..KQqKQQQQQqqqKqqK....",
            "..KQqKQQQQQqqqKqqK....",
            ".KZzKKQQQQQqqKqqK.....",
            ".KZzKKQQQQQqqKqqK.....",
            ".....KQqqqqqKKzzK.....",
            "......KQQQQqqK........",
            "....KQqK.KQqK.........",
            "...KQqK..KZzK.........",
            "...KZzK...KZzK........",
            "..KZzK....KZzK........",
            "..KZZzK..KZZzK........",
            "..KKZZzKKKKZZzKK......",
        ],
        # frame 2  fold -- doubled over onto the knees, the head hangs, 15 rows
        [
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "............KQQQqK....",
            "...........KQQQQQqqK..",
            "..........KQQQQQqqqK..",
            "....KKKK..KQqKQQqqK...",
            "..KKZZZZKKKQqKQQqqK...",
            ".KZZZZZzzKKQqKQqqqK...",
            ".KZVVZZzzKKQqKQqqqqK..",
            ".KZZZZZZzKKQqKQQqqqK..",
            ".KZZKKZzK.KQqKKQqqqqK.",
            ".KZZZZZzK.KQqKQQqqqK..",
            ".KZZZZZK..KZzKQqqK....",
            "...KKKK...KZzKqK......",
            ".........KQQQqK.......",
            ".........KQQQqKQQqK...",
            ".........KKQQQqKZZzK..",
        ],
        # frame 3  impact -- face down, one arm thrown over the head, 9 rows
        [
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......KQqKKQQQqK......",
            ".....KQqKKQQQQQqqK....",
            "...KZZzKKQQQQQqqqKQQqK",
            "...KKKKK.KQQQQQqqKQQqK",
            "..KZZZZzKKQQQQqqKQQqK.",
            "..KZKZZzzKKQQQqqKZzK..",
            "..KZZZZZzK.KQQqqKZZzK.",
            "..KZZKKzzK..KQqqKZZzK.",
            "...KKKKKK...KKQKKZZzKK",
        ],
        # frame 4  settle -- the heap flattens and the glow goes out, 7 rows
        [
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "......................",
            "....KQqKKQQQqK........",
            "...KKKKK..KQQQQqqK....",
            "..KZZZZzK.KQQQQqqqK...",
            "..KZKZZzzKKQQQqqqK....",
            "..KZZZZZzK.KQQqqqKZzK.",
            "..KZZKKzzK.KQqqqqKZZzK",
            "...KKKKKK..KKQQKKZZzKK",
        ],
    ],
}


def main() -> None:
    """Render the preview sheet and the death gif, then report."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    clips = list(ZOMBIE.items())
    images = {name: [build(g, GAME_PALETTE) for g in frames] for name, frames in clips}

    # Preview sheet: one row per clip, frames left to right, 6x on the dark
    # backdrop.  Nothing is drawn on top of a sprite, so check_zombie.py can
    # decode this PNG straight back into the grids.
    cols = max(len(frames) for _, frames in clips)
    sheet = Image.new(
        "RGBA",
        (PAD + cols * (W * SCALE + PAD), PAD + len(clips) * (H * SCALE + PAD)),
        (*BG, 255),
    )
    for r, (name, frames) in enumerate(clips):
        for c, img in enumerate(images[name]):
            sheet.alpha_composite(
                preview(img, SCALE, BG),
                (PAD + c * (W * SCALE + PAD), PAD + r * (H * SCALE + PAD)),
            )
    sheet_path = OUT_DIR / "zombie_preview.png"
    sheet.save(sheet_path)

    # Death gif: plays ONCE.  No ``loop`` argument, so Pillow writes no Netscape
    # looping extension at all -- a looping death is a comedy.
    gif_frames = [
        preview(img, SCALE, BG).convert("RGB").convert(
            "P", palette=Image.Palette.ADAPTIVE, colors=64
        )
        for img in images["death"]
    ]
    gif_path = OUT_DIR / "zombie_death.gif"
    gif_frames[0].save(
        gif_path,
        save_all=True,
        append_images=gif_frames[1:],
        duration=FRAME_MS,
        optimize=False,
    )

    used = sorted({c for frames in ZOMBIE.values() for g in frames for row in g for c in row if c != "."})
    print(f"grid      : {W}x{H} x {sum(len(f) for f in ZOMBIE.values())} frames "
          f"({', '.join(f'{k} {len(v)}' for k, v in clips)})")
    print(f"colours   : {len(used)} used -> {used}")
    print(f"ground    : row {GROUND_ROW} in every walk and attack frame")
    print(f"death     : {[max(y for y in range(H) for x in range(W) if g[y][x] != '.') - min(y for y in range(H) for x in range(W) if g[y][x] != '.') + 1 for g in ZOMBIE['death']]} rows tall, shrinking")
    print(f"wrote     : {sheet_path}  ({sheet.width}x{sheet.height})")
    print(f"wrote     : {gif_path}  ({W * SCALE}x{H * SCALE}, {FRAME_MS}ms/frame, plays once)")


if __name__ == "__main__":
    main()
