"""Draw a Stardew-flavoured 16x32 pixel character from an ASCII grid.

Native resolution is a true 16x32 pixel canvas (same sprite spec Stardew Valley
uses). Everything is authored cell-by-cell in SPRITE below, then rendered with a
locked palette so the result can never drift into "fake pixel art".
"""

from pathlib import Path

from PIL import Image

OUT_DIR = Path(__file__).resolve().parent / "assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Locked palette. 14 colours total, warm/earthy, Stardew-adjacent.
# --------------------------------------------------------------------------
PALETTE: dict[str, tuple[int, int, int, int]] = {
    ".": (0, 0, 0, 0),            # transparent
    "K": (0x1e, 0x14, 0x16, 255),  # outline
    "H": (0x5c, 0x3a, 0x1e, 255),  # hair
    "h": (0x9c, 0x66, 0x34, 255),  # hair highlight
    "S": (0xf4, 0xcd, 0xa6, 255),  # skin
    "s": (0xc9, 0x8a, 0x5c, 255),  # skin shadow
    "m": (0x8c, 0x44, 0x36, 255),  # mouth
    "C": (0x5a, 0x92, 0xd0, 255),  # shirt
    "c": (0x2d, 0x51, 0x83, 255),  # shirt shadow / arm separation
    "D": (0x1f, 0x34, 0x50, 255),  # collar
    "P": (0x8f, 0x70, 0x48, 255),  # overalls
    "p": (0x5a, 0x45, 0x30, 255),  # overalls shadow
    "B": (0xc0, 0x8a, 0x3c, 255),  # boot leather
    "b": (0x8a, 0x5f, 0x30, 255),  # boot shadow
}

W, H = 16, 32

# Facing the camera. Head rows 1-10, torso 11-20, legs 21-30.
SPRITE: list[str] = [
    "................",  # 0
    ".....KKKKKK.....",  # 1  crown, rounded off
    "....KHHHHHHK....",  # 2
    "...KhhhhHHHHK...",  # 3  hair highlight (light from upper-left)
    "...KHHHHHHHHK...",  # 4  fringe
    "...KHSSSSSsHK...",  # 5  forehead, temples, right side in shadow
    "...KHSKSSKsHK...",  # 6  eyes
    "...KHSSSSSsHK...",  # 7
    "...KSSSmmSsSK...",  # 8  mouth
    "....KSSSSSSK....",  # 9  jaw taper
    ".....KssssK.....",  # 10 neck (shadowed under the chin)
    "...KCCDDDDCCK...",  # 11 shoulder line, narrower than the arms below
    "..KCcCPCCPCcCK..",  # 12 arms pop out 1px each side; straps from the shoulders
    "..KCcCPCCPCcCK..",  # 13
    "..KCcCPCCPCcCK..",  # 14
    "..KCcCPCCPCcCK..",  # 15
    "..KCcCPCCPCcCK..",  # 16
    "..KCCPPPPPPCCK..",  # 17 bib, shirt shows at the flanks
    "..KCCPPPPPPCCK..",  # 18
    "..KCCPPPPPPCCK..",  # 19
    "..KSCPPPPPPCSK..",  # 20 hands
    "...KPPPPPPPPK...",  # 21 hips
    "...KPPPKKPPPK...",  # 22 legs split
    "...KPPPKKPPPK...",  # 23
    "...KPPPKKPPPK...",  # 24
    "...KPPPKKPPPK...",  # 25
    "...KpppKKpppK...",  # 26 lower leg shading
    "...KpppKKpppK...",  # 27
    "..KBBBBKKBBBBK..",  # 28 boots
    "..KbbbbKKbbbbK..",  # 29
    "..KKKKKKKKKKKK..",  # 30 boot soles
    "................",  # 31
]


def validate(grid: list[str]) -> None:
    assert len(grid) == H, f"expected {H} rows, got {len(grid)}"
    for i, row in enumerate(grid):
        assert len(row) == W, f"row {i} has {len(row)} cols, expected {W}"
        bad = set(row) - set(PALETTE)
        assert not bad, f"row {i} uses undefined palette keys: {sorted(bad)}"


def build(grid: list[str]) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(grid):
        for x, key in enumerate(row):
            px[x, y] = PALETTE[key]
    return img


def preview(img: Image.Image, scale: int = 12, bg: tuple[int, int, int] = (58, 62, 74)) -> Image.Image:
    """Nearest-neighbour upscale on a flat backdrop so it is readable in a viewer."""
    flat = Image.new("RGBA", img.size, (*bg, 255))
    flat.alpha_composite(img)
    return flat.resize((W * scale, H * scale), Image.Resampling.NEAREST)


def main() -> None:
    validate(SPRITE)
    sprite = build(SPRITE)

    used = {c for row in SPRITE for c in row if c != "."}
    native_path = OUT_DIR / "char_native.png"
    preview_path = OUT_DIR / "char_preview.png"
    sheet_path = OUT_DIR / "char_sheet.png"

    sprite.save(native_path)
    preview(sprite).save(preview_path)

    # Proof sheet: the native sprite next to a 4x reference, on a checkerboard.
    checker = Image.new("RGBA", (W * 4, H * 4))
    cpx = checker.load()
    for y in range(H * 4):
        for x in range(W * 4):
            tone = 210 if ((x // 4) + (y // 4)) % 2 == 0 else 180
            cpx[x, y] = (tone, tone, tone, 255)
    checker.alpha_composite(sprite.resize((W * 4, H * 4), Image.Resampling.NEAREST))
    pad = 8
    sheet = Image.new("RGBA", (W * 12 + W * 4 + pad * 3, H * 12 + pad * 2), (30, 32, 40, 255))
    sheet.alpha_composite(preview(sprite), (pad, pad))
    sheet.alpha_composite(checker, (pad * 2 + W * 12, pad))
    sheet.save(sheet_path)

    print(f"grid      : {W}x{H}")
    print(f"colours   : {len(used)} used / {len(PALETTE) - 1} defined -> {sorted(used)}")
    for p in (native_path, preview_path, sheet_path):
        print(f"wrote     : {p}")


if __name__ == "__main__":
    main()
