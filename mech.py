"""PILOTPUP: a humanoid mech suit with a dog in the cockpit. 64x96.

REQUESTED: "穿在人形机甲那种, 能画多大多精致画多好" -- a dog wearing a humanoid
mech, as large and as detailed as the pipeline will carry. This is 6,144 cells
per frame, 3.6x the previous largest animated asset.

Palette: `gamepalette.GAME_PALETTE`.

    K  outline            G  armour plate        g  armour shadow
    N  armour highlight   C/c  secondary plate    M  edge highlight, W  glass glint
    B  joints and seals   V  optic / sensor glow  X/Y  energy
    H  fur (the dog)      S  muzzle

APPROACH, and why it is not all hand-authored. 96 rows of 64 characters typed by
hand has a high error rate and, worse, produces flat plates: real mech art is
defined by consistent plate structure -- every panel lit from the same direction,
every seam in the same weight. So the REGULAR part is generated:

  * `SILHOUETTE` gives, per row, which column spans are solid. This is the shape,
    and it is the part that is genuinely a design decision.
  * `armour()` fills those spans and derives the outline, the upper-left highlight
    and the lower-right shadow from the shape itself, so the lighting cannot
    drift between plates.

The IRREGULAR part is hand-authored as `PATCHES` and pasted over the top: the
sensor head, the cockpit with the dog visible through the glass, the chest vents,
the hands, the knee and ankle actuators. Those are judgement, not formula.

This is the pattern documented in docs/authoring.md: generate what is regular,
hand-place what is not, then freeze the result and assert it.
"""

from gamepalette import GAME_PALETTE
from pixelkit import build, preview

W, H = 64, 96
GROUND_ROW = 95

SHIPPED = ("FRAMES",)
PALETTE = GAME_PALETTE

# ---------------------------------------------------------------------------
# SILHOUETTE: per row, the solid column spans, inclusive. "l-r" or "a-b,c-d".
# This table is the mech's shape and the only part of the geometry that is a
# drawing decision rather than a consequence of one.
# ---------------------------------------------------------------------------
SIL = [
    "31-32",                                  # 0   antenna
    "30-33",                                  # 1
    "30-33",                                  # 2
    "29-34",                                  # 3
    "25-38", "25-38", "25-38", "25-38",       # 4-7   sensor head
    "24-39", "24-39", "24-39",                # 8-10  visor brow
    "25-38", "25-38",                         # 11-12 jaw
    "26-37", "27-36", "28-35",                # 13-15 chin taper
    "28-35", "29-34", "29-34", "29-34",       # 16-19 neck
    "29-34", "27-36",                         # 20-21 collar
    "18-45", "14-49", "11-52",                # 22-24 shoulder slope
    "5-58", "3-60", "2-61",                   # 25-27 pauldron flare
    "2-61", "2-61", "2-61", "2-61",           # 28-31 pauldron
    "2-61", "2-61", "2-61", "2-61",           # 32-35
    "3-60", "4-59",                           # 36-37 pauldron taper
    # arms separate from the torso: arm, gap, torso, gap, arm
    "7-17,21-42,46-56",                       # 38
    "7-17,21-42,46-56",                       # 39
    "7-17,21-42,46-56",                       # 40
    "7-17,21-42,46-56",                       # 41
    "7-17,21-42,46-56",                       # 42
    "8-17,21-42,46-55",                       # 43
    "8-17,22-41,46-55",                       # 44
    "8-17,22-41,46-55",                       # 45
    "8-17,23-40,46-55",                       # 46  waist narrows
    "9-17,23-40,46-54",                       # 47
    "9-17,24-39,46-54",                       # 48
    "9-17,24-39,46-54",                       # 49
    "10-17,25-38,46-53",                      # 50
    "10-17,25-38,46-53",                      # 51
    "10-17,26-37,46-53",                      # 52
    "10-17,26-37,46-53",                      # 53
    "10-17,26-37,46-53",                      # 54
    "11-17,26-37,46-52",                      # 55
    # hands: the spans widen to 8-19 / 44-55 to match the HAND patch exactly.
    # A patch that paints outside the declared silhouette is a defect the
    # silhouette assertion catches -- it did, on all eight of these rows.
    "8-19,27-36,44-55",                       # 56
    "8-19,27-36,44-55",                       # 57
    "8-19,27-36,44-55",                       # 58
    "8-19,27-36,44-55",                       # 59
    "8-19,27-36,44-55",                       # 60
    "8-19,27-36,44-55",                       # 61
    "10-17,27-36,46-53",                      # 62
    "11-16,27-36,47-52",                      # 63  fingers/thumb taper
    "18-45",                                  # 64  hips
    "17-46", "17-46",                         # 65-66
    "16-47", "16-47",                         # 67-68
    "17-46", "17-46",                         # 69-70
    "18-45",                                  # 71
    "18-45",                                  # 72
    # legs split
    "17-29,34-46",                            # 73
    "17-29,34-46",                            # 74
    "17-29,34-46",                            # 75
    "17-29,34-46",                            # 76
    "18-29,34-45",                            # 77
    "18-29,34-45",                            # 78
    "19-29,34-44",                            # 79  knee
    "19-29,34-44",                            # 80
    "19-29,34-44",                            # 81
    "19-29,34-44",                            # 82
    "20-29,34-43",                            # 83  shin narrows
    "20-29,34-43",                            # 84
    "20-29,34-43",                            # 85
    "20-29,34-43",                            # 86
    "20-29,34-43",                            # 87
    "19-30,33-44",                            # 88  ankle flare
    "18-30,33-45",                            # 89
    "15-30,33-48",                            # 90  foot
    "14-30,33-49",                            # 91
    "14-30,33-49",                            # 92
    "13-30,33-50",                            # 93
    "13-30,33-50",                            # 94
    "13-30,33-50",                            # 95
]


def parse_sil(entry: str):
    out = []
    for part in entry.split(","):
        a, b = part.split("-")
        out.append((int(a), int(b)))
    return out


# PLATE TONES, by body zone. Each zone gets a three-step window from ONE grey
# ladder, and neighbouring zones slide by one step.
#
# This is the fix for the reason the first version read as an ugly grey slab, and
# the diagnosis came from measurement, not taste: legibility.py reported tones/px
# of 4.9 for this sprite against 9.5 for the simplest tree and 41.8 for the 16x32
# farmer. 2,864 pixels were being drawn in three armour tones. The first
# hypothesis -- that the generator had sliced the body into confetti with 2px
# shading bands -- was WRONG: mean run length was 2.82, above the median, and
# isolated pixels 1.3%. It was not noisy. It was FLAT, which is the opposite
# failure and needed the opposite fix.
#
# The ladder is derived, not guessed. `verdict()` was run over every consecutive
# pair of grey palette entries, and `N-C` (5.9), `G-R` (5.6) and `g-r` (1.8) fail
# the floor, so C, R and r are skipped:
#
#     W > M > N > G > c > g > B      steps: 11.5, 21.1, 17.3, 20.4, 7.4
#
# Every internal and cross-zone boundary is then at least one whole ladder step
# apart, which is why this passes where the first sliding scheme did not: that one
# put `C` next to `N` and landed at dE 5.9 against a floor of 6.
PLATE_TONES = {
    (0, 21):   ("W", "M", "N"),     # sensor head -- brightest, it is the focal point
    (22, 37):  ("M", "N", "G"),     # pauldrons
    (38, 55):  ("M", "N", "G"),     # chest, framing the cockpit
    (56, 63):  ("N", "G", "c"),     # forearms and hands
    (64, 72):  ("c", "g", "B"),     # hips -- darkest, they sit in their own shadow
    (73, 89):  ("N", "G", "c"),     # legs
    (90, 95):  ("G", "c", "g"),     # feet -- cool, they are on the ground
}


def tones_for(row: int) -> tuple[str, str, str]:
    for (lo, hi), t in PLATE_TONES.items():
        if lo <= row <= hi:
            return t
    return ("N", "G", "g")


def armour(sil) -> list[list[str]]:
    """Fill the silhouette, then derive outline, highlight and shadow from it.

    Deriving the lighting from the SHAPE rather than painting it per plate is what
    keeps 96 rows consistent: every panel gets its highlight two pixels in from the
    upper-left edge and its shadow two pixels in from the lower-right, because the
    only thing that decides is where the edge is.

    The three tones come from `PLATE_TONES`, so the lighting rule is constant and
    the MATERIAL varies by zone. Getting that backwards -- one material, lighting
    varying -- is what produces a uniform slab.
    """
    filled = [[False] * W for _ in range(H)]
    for r, entry in enumerate(sil):
        for l, rr in parse_sil(entry):
            for c in range(l, rr + 1):
                filled[r][c] = True

    def f(r, c):
        return 0 <= r < H and 0 <= c < W and filled[r][c]

    grid = [["."] * W for _ in range(H)]
    for r in range(H):
        for c in range(W):
            if not filled[r][c]:
                continue
            light, base, dark = tones_for(r)
            if not (f(r - 1, c) and f(r + 1, c) and f(r, c - 1) and f(r, c + 1)):
                grid[r][c] = "K"                      # boundary
                continue
            depth = []
            for dr, dc in ((-1, 0), (0, -1)):
                n = 0
                while f(r + dr * (n + 1), c + dc * (n + 1)) and n < 3:
                    n += 1
                depth.append(n)
            if min(depth) <= 1:
                grid[r][c] = light                    # lit from the upper left
                continue
            depth = []
            for dr, dc in ((1, 0), (0, 1)):
                n = 0
                while f(r + dr * (n + 1), c + dc * (n + 1)) and n < 3:
                    n += 1
                depth.append(n)
            grid[r][c] = dark if min(depth) <= 1 else base
    return grid


# ---------------------------------------------------------------------------
# PATCHES: hand-authored detail, pasted at an offset. Irregular by nature.
# ---------------------------------------------------------------------------
# The cockpit. This is the whole point of the sprite, so it is the one part that
# got the most hand work: 18x20, pasted into the chest at (28, 23).
#
# The dog is SEATED AND OPERATING, not just a head behind glass:
#   rows  2-11  the dog's head, ears up, in a frame of cockpit interior
#   rows 11-14  shoulders and body, seated upright
#   rows 15-16  both forepaws reaching forward, gripping the control sticks
#   rows 17-18  the instrument panel, lit
# The `B` at the sides is the seat's roll bar, which is what makes it read as an
# interior rather than a window.
COCKPIT = [                                    # 18 wide, pasted at (28, 23)
    "KKKKKKKKKKKKKKKKKK",
    "KWW22222222222MMMK",                      # glass glint, upper left
    "K2BBBBBBBBBBBBBB2K",                      # seat roll bar
    "K2BHHHHHHHHHHHHB2K",                      # dog's head
    "K2BHKHHHHHHHHKHB2K",                      # ear tips
    "K2BHHKHHHHHHKHHB2K",                      # ears
    "K2BHHHHHHHHHHHHB2K",
    "K2BHSVHHHHHHVSHB2K",                      # eyes
    "K2BHSSSSSSSSSSHB2K",                      # muzzle
    "K2BHSSKKKKKKSSHB2K",                      # mouth
    "K2BHHSSSSSSSSHHB2K",                      # chin
    "K2BHHHHHHHHHHHHB2K",                      # neck
    "K2BHHHHHHHHHHHHB2K",                      # shoulders
    "K22HHHHHHHHHHHH22K",                      # body, seated
    "K22HHHHHHHHHHHH22K",
    "K2SSHHHHHHHHHHSS2K",                      # forepaws reaching forward
    "K2SBHHHHHHHHHHSB2K",                      # gripping the sticks
    "K2VYBBBBBBBBBBYV2K",                      # instrument panel, lit
    "K2222222222222222K",
    "KKKKKKKKKKKKKKKKKK",
]

VISOR = [                                      # 16 wide, pasted at (8, 24)
    "KVVVVVVVVVVVVVVK",
    "KVVVVVVVVVVVVVVK",
    "KVVVVVVVVVVVVVVK",
]

CHEST_VENT_L = [                               # 8 wide, pasted at (27, 4)
    "KKKKKKKK",
    "KcCCCCcK",
    "KcCCCCcK",
    "KcCCCCcK",
    "KKKKKKKK",
]
CHEST_VENT_R = [                               # 8 wide, pasted at (27, 52)
    "KKKKKKKK",
    "KcCCCCcK",
    "KcCCCCcK",
    "KcCCCCcK",
    "KKKKKKKK",
]

HAND = [                                       # 12 wide, pasted at (56, 8)
    "KKKKKKKKKKKK",
    "KGGGGBBBGGGK",
    "KGGBBBBBGGGK",
    "KGBBBBBBBBGK",
    "KGBBBBBBBBGK",
    "KKGGBBBBGKKK",
    "..KKKKKKKK..",
    "...KKKKKK...",
]
HAND_R = [                                     # 12 wide, pasted at (56, 44)
    "KKKKKKKKKKKK",
    "KGGGGBBBGGGK",
    "KGGBBBBBGGGK",
    "KGBBBBBBBBGK",
    "KGBBBBBBBBGK",
    "KKGGBBBBGKKK",
    "..KKKKKKKK..",
    "...KKKKKK...",
]

KNEE = [                                       # 10 wide, pasted at (78, 20)
    "KKKKKKKKKK",
    "KBBBBBBBBK",
    "KBBVVVVBBK",
    "KBBVVVVBBK",
    "KBBBBBBBBK",
    "KKKKKKKKKK",
]
KNEE_R = [                                     # 10 wide, pasted at (78, 34)
    "KKKKKKKKKK",
    "KBBBBBBBBK",
    "KBBVVVVBBK",
    "KBBVVVVBBK",
    "KBBBBBBBBK",
    "KKKKKKKKKK",
]

INSIGNIA = [                                   # 8 wide, pasted at (66, 28)
    "KKKKKKKK",
    "KYYYYYYK",
    "KYKKKKYK",
    "KYKYYKYK",
    "KYKKKKYK",
    "KYYYYYYK",
    "KKKKKKKK",
]

# Pauldron grilles. The single most mech-defining detail in the whole sprite: a
# plain plate reads as a shoulder pad, a louvred one reads as engineering.
PAULDRON_L = [                                 # 12 wide, pasted at (27, 5)
    "KKKKKKKKKKKK",
    "KcCCCCCCCCcK",
    "KcCCCCCCCCcK",
    "KKKKKKKKKKKK",
    "KGGGGGGGGGGK",
    "KgGGGKKGGGgK",
    "KGGGGGGGGGGK",
    "KKKKKKKKKKKK",
]
PAULDRON_R = [                                 # 12 wide, pasted at (27, 47)
    "KKKKKKKKKKKK",
    "KcCCCCCCCCcK",
    "KcCCCCCCCCcK",
    "KKKKKKKKKKKK",
    "KGGGGGGGGGGK",
    "KgGGGKKGGGgK",
    "KGGGGGGGGGGK",
    "KKKKKKKKKKKK",
]

# (row, col, patch). Later entries paste over earlier ones.
# The vent zones the idle animation pulses: (row, col, width, height) of the
# pauldron grilles, which is where the lit plate cells live.
VENT_ZONES = ((27, 5, 12, 8), (27, 47, 12, 8))

PATCHES = [
    (8, 24, VISOR),
    (27, 5, PAULDRON_L),
    (27, 47, PAULDRON_R),
    (28, 23, COCKPIT),
    (66, 28, INSIGNIA),
    (56, 8, HAND),
    (56, 44, HAND_R),
    (78, 20, KNEE),
    (78, 34, KNEE_R),
]


def paste(grid, r0, c0, patch):
    for dr, row in enumerate(patch):
        for dc, ch in enumerate(row):
            if ch == ".":
                continue
            r, c = r0 + dr, c0 + dc
            if 0 <= r < H and 0 <= c < W:
                grid[r][c] = ch


def compose(vent_shift: int = 0) -> list[str]:
    """One frame.

    The idle animation is deliberately tiny -- the chest vents step through
    closed / half-lit / wide. A 64x96 mech that flails reads as a toy; a big
    machine breathing reads as a big machine.
    """
    grid = armour(SIL)
    for r0, c0, patch in PATCHES:
        paste(grid, r0, c0, patch)
    if vent_shift:
        tone = ("c", "Y", "X")[min(vent_shift, 3) - 1]
        for r0, c0, pw, ph in VENT_ZONES:
            for dr in range(ph):
                for dc in range(pw):
                    if grid[r0 + dr][c0 + dc] in ("C", "c"):
                        grid[r0 + dr][c0 + dc] = tone
    return ["".join(row) for row in grid]


FRAMES = [
    compose(),
    compose(vent_shift=1),
    compose(vent_shift=2),
    compose(vent_shift=1),
]

FRAME_MS = 180
SCALE = 4          # preview sheet and GIF
HERO_SCALE = 8     # single-frame hero, for actually looking at the detail
BG = GAME_PALETTE["R"]


def main() -> None:
    from pathlib import Path
    from PIL import Image

    out = Path(__file__).resolve().parent / "assets"
    out.mkdir(exist_ok=True)

    images = [build(g, GAME_PALETTE) for g in FRAMES]
    sheet = Image.new("RGBA", (len(FRAMES) * W * SCALE + (len(FRAMES) + 1) * 8,
                               H * SCALE + 16), (28, 30, 36, 255))
    for i, im in enumerate(images):
        sheet.alpha_composite(preview(im, SCALE, BG[:3]), (8 + i * (W * SCALE + 8), 8))
    sheet.save(out / "mech_preview.png")

    build(FRAMES[0], GAME_PALETTE).resize(
        (W * HERO_SCALE, H * HERO_SCALE), Image.Resampling.NEAREST).save(
            out / "mech_hero.png")

    gif = [preview(im, SCALE, BG[:3]).convert("RGB").convert(
        "P", palette=Image.Palette.ADAPTIVE, colors=64) for im in images]
    gif[0].save(out / "mech.gif", save_all=True, append_images=gif[1:],
                duration=FRAME_MS, loop=0, optimize=False)

    print(f"frames : {len(FRAMES)} of {W}x{H}  ({W * H} cells each)")
    print(f"wrote  : {out / 'mech_preview.png'}")
    print(f"wrote  : {out / 'mech_hero.png'}")
    print(f"wrote  : {out / 'mech.gif'}  ({FRAME_MS}ms, loops)")


if __name__ == "__main__":
    main()
