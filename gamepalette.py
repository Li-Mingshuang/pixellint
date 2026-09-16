"""Palette and canvas spec for the zombie-shooter demo.

The game is its own art direction -- night, ruined city, desaturated greens and
greys, one warm accent for muzzle flash and blood -- so it carries its own locked
palette rather than inheriting the meadow's. Every sprite in `game/` indexes into
this and nothing else.

Uppercase keys are base tones, lowercase are their shadows, matching the
convention used everywhere else in the repo.
"""

GAME_W = 320
GAME_H = 180
GROUND_Y = 148          # the row feet stand on
TILE_W = 320            # every background band tiles at this width

GAME_PALETTE: dict[str, tuple[int, int, int, int]] = {
    ".": (0, 0, 0, 0),
    "K": (0x0b, 0x0d, 0x12, 255),   # outline, near black

    # --- night sky. Each band is >= 1.7x the luminance of the one above it,
    #     which is what makes a step read down in the dark end of the scale
    #     where absolute differences are tiny. ------------------------------
    "1": (0x0e, 0x14, 0x22, 255),   # sky top
    "2": (0x1a, 0x24, 0x38, 255),   # sky mid        1.8x
    "3": (0x2e, 0x3e, 0x5e, 255),   # sky low        1.7x
    "4": (0x55, 0x68, 0x8f, 255),   # horizon haze, lit by the city below

    # --- far skyline -----------------------------------------------------
    "5": (0x07, 0x08, 0x0d, 255),   # far building silhouette (far below any sky band)
    "6": (0x6b, 0x7a, 0x9e, 255),   # far building, lit edge (clearly above the sky)

    # --- mid ruins -------------------------------------------------------
    "C": (0x6e, 0x76, 0x84, 255),   # concrete
    "c": (0x2e, 0x3d, 0x5c, 255),   # concrete shadow (blue enough to clear the neutral asphalt)
    "E": (0xd8, 0xb4, 0x5c, 255),   # lit window

    # --- street ----------------------------------------------------------
    "R": (0x3e, 0x43, 0x4c, 255),   # asphalt
    "r": (0x1c, 0x1f, 0x24, 255),   # asphalt shadow
    "M": (0x9a, 0xa2, 0xac, 255),   # road marking

    # --- player. Shadows shift dark AND cool, which is both correct for
    #     night lighting and what keeps them clear of their base tone. -----
    "H": (0x33, 0x24, 0x1a, 255),   # hair
    "S": (0xe8, 0xbb, 0x92, 255),   # skin
    "s": (0x9c, 0x6a, 0x56, 255),   # skin shadow
    "J": (0x56, 0x68, 0x3f, 255),   # jacket
    "j": (0x2c, 0x36, 0x2a, 255),   # jacket shadow
    "P": (0x6e, 0x66, 0x57, 255),   # pants
    "p": (0x40, 0x3b, 0x32, 255),   # pants shadow
    "B": (0x21, 0x1d, 0x19, 255),   # boots

    # --- gun -------------------------------------------------------------
    "G": (0x4a, 0x50, 0x58, 255),   # gun body
    "g": (0x1c, 0x21, 0x28, 255),   # gun dark
    "N": (0x7c, 0x84, 0x8e, 255),   # gun highlight

    # --- zombie ----------------------------------------------------------
    "Z": (0x8f, 0xa8, 0x5e, 255),   # zombie skin
    "z": (0x54, 0x67, 0x33, 255),   # zombie skin shadow
    "Q": (0x58, 0x4a, 0x41, 255),   # zombie rags
    "q": (0x2c, 0x24, 0x20, 255),   # zombie rags shadow
    "V": (0xe8, 0xe0, 0x4a, 255),   # zombie eye

    # --- blood -----------------------------------------------------------
    "U": (0x8c, 0x1f, 0x1f, 255),   # blood
    "u": (0x44, 0x0e, 0x0e, 255),   # blood dark
    "v": (0xd0, 0x40, 0x40, 255),   # blood bright

    # --- muzzle flash / fire ---------------------------------------------
    "W": (0xff, 0xfb, 0xe0, 255),   # flash core
    "X": (0xff, 0xd2, 0x4a, 255),   # flash yellow
    "Y": (0xe8, 0x78, 0x2a, 255),   # flash orange

    # --- hud -------------------------------------------------------------
    "F": (0xe0, 0x4a, 0x38, 255),   # health / danger
    "O": (0x78, 0xc8, 0x50, 255),   # objective
}

# Pairs that are a base colour and its own shadow.
GAME_SHADE_PAIRS = {
    frozenset(p) for p in (
        "Ss", "Jj", "Pp", "Zz", "Qq", "Uu", "23", "34", "Cc", "Rr",
        "5c", "6D", "12",
    )
}
