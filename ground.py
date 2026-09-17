
# What this module delivers. See docs/authoring.md.
SHIPPED = ('GROUND',)

"""The ground layer: 160x40 of walkable dirt path through a grass field.

Composited at scene rows 56..95, so GROUND row 0 is scene row 56 and GROUND
row 39 is scene row 95. GROUND row 23 is scene row 79 -- GROUND_LINE, the row
the character's and the dog's feet land on -- and is therefore pure walkable
turf/dirt everywhere: no outline, no stone, no flower.

Layout, top to bottom:

  rows  0..17   turf field: `G` base, organic `g` shadow patches, `E` blade
                tips, tufts (a `g` clump with lit `E` tips), flowers
  rows 18..29   the dirt path, `N` body with `n` grit, clumps and a broken
                dark line along its lower lip. The top edge wobbles between
                rows 18 and 21 and the bottom edge between rows 25 and 29, so
                the path is never thinner than five rows and always straddles
                row 23. Turf overhangs the top edge and a grass fringe breaks
                the bottom edge, which is what keeps the boundary organic
                rather than ruled.
  rows 30..33   turf field again, same vocabulary as the top
  rows 34..39   the same turf, progressively darkened towards `g` in soft
                clumps, with tall dark blades along the bottom edge: the
                foreground depth cue.

Two colour notes:

  * `R`/`r` stones sit on the path, in the turf and at the path edge. The
    palette scan says `n`-`r` (dirt shadow vs stone shadow) is the one illegal
    adjacency in this key set at SCENE_TIERS (dE 29.8 < the 32 material floor),
    so any `n` that ends up touching an `r` is nudged to plain `N`. Every other
    pair used here clears its floor, most of them comfortably.
  * `G`-`g` and `G`-`E` are declared shade pairs in the shared palette, so the
    turf ramp is judged against the 15 shade floor rather than the 32 material
    floor, which is exactly what a base colour and its own shadow should get.

The layer is horizontally tileable. Every feature is stamped modulo 160, and
the path edges are periodic value noise (cell counts that divide 160), so both
the scattered detail and the dirt boundary wrap edge to edge with no seam.
`check_ground.py` asserts that column 159 and column 0 satisfy the same
separation check as a real adjacency, on all 40 rows.

Authored as one character per pixel into the shared SCENE_PALETTE, and frozen
here as literals so the art cannot drift. No transparent pixels: a ground layer
has no holes.
"""

GROUND: list[str] = [
    "ggggggggggggggggggggggggggggggggggggggggggggggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGggggggggggggggggggggggggggggggGGgggggggggggggg",  # scene row 56
    "ggggggggggggggggggggggggggggggggggggggggggggggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGggggggggggggggggggggggggggGGGGGGGGGGggggggggg",
    "GGGGGGGGGGGGGgggggggggggggggggggggggggggggggggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGgggggggggggggggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG",  # scene row 58 = GROUND_TOP
    "GGGGGGGGGGGGGGGgggggggggggggggggggggggggggEgEggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGgggggggggggggggggggggggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGgggggggggggggggggggggggEggggggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGggggggggggggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGggggggggggggggggggggggggggggggggGGGGGGGGGGGggggggggggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGggggGGGGGGGGGGGGGGGGGGGGGG",
    "ggggGGGGGGGGGGGGGGGGgggggggggggggggggGGGgggggggggggGGGGGGGGGgggEgEgEgggggggggGGEGGGGGGGGGGGGGGGGYGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGggggggggGGGGGGGGGGGGGGGGGGGGg",
    "gggggGGGGGGGGGGGGGGGGGGGgggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGgggggggggggggggggggggGEGEGGGGGGGGGGGYnYGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGggggGGGGGGGGGGGGGGGGGGGGgg",
    "gggggggGGGGGGGGGGGGYGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGgggggggggggggggggggggggggggGGGGGGEGEGgYGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGEGEGGGGGGGGGGGGGGGGGGGGGGGggg",
    "ggggggggGGGGGGGGGGYnYGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGggggggggggggggggggggggggggggggGGGGgggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGEGgGgGGGGGGGGGGGGGGGGGGGGGGGggg",
    "gggggGGGGGGGGGGGGGGYGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGgggggggggggggggggggggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGgggggGGGGGGGGGGGGGGGGGGGGGGGGgg",
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGgggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGGRRRGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGyGGGGGGGGGGGGGEGGGEGGGG",
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGGrrrGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGEGEGEGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGyYyGGGGGGGGGGGGgGEGgGGGG",
    "gggggggggggggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGggygggggggggggggggggggggggggGGGGGGgggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGyGGGGGGGGGGGGGggggggggg",
    "gggggggggggggggggggggGGGGGGGGGGGGGGGGGGGGGGGGGgggggggggggyYyggggggggggggggggggggggggggGGGGGGGggggggggggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGggggggggggggg",
    "ggggggggggggggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGgggggggyggggggggggGGGGRRGgggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGgggggg",
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGrrGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGNNNGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGNNGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGNEEgggggggGGGGGGGGGGGGGNNNNgggGNNNGGGGGGGGGggggggNNggggNGGGGGGGggNNNNNNNNNNNNNNNNNNNNNNNNGGGGGGGGGGGGGGGGGGGEEEGGGGGGGGGGGGGGGGNNNNggggGGGGGGGGGGGGGGGG",
    "ggNNNNNNNNNNnNNNNNngNNNNNNNNNNNNnnNNNNNgNNnNNNNNNNggnnNNNNNnNNNnnNNNNNggnnNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNggggEENNNNggENRRgggNNNNNNNNNNNNNNnNNNNNnGGGEEEEEEEEggNNN",
    "nNNNNNNNNNNNnNNNNNNNnNnNNNnNNNNNnNnNNnNNNNNNNNNNNNnNNNNNNNNNNNNNNNnNNNNNnNNnNNNNNNnNNNNNNNNNNNNNNNNNNNNnnnNNNNNnNNNNNrrrNNNNNNNNNNNnnNNNNNNNNNNNggENNNEENNNNnnnN",
    "NNNNNNNNNNNNNNnNNNNNNNNNNNNNnNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNnnNnNnNNNNNNNNNNnNnNNNNnNNNNNNNnnnnnNNNNNNNNNNNNNNNNNnnnnnNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN",
    "NnNNNNNnNNNNNNNNNNNNNNNNNNNNNNNNNNnNNnNNNNNNNNNNNNNnnNNNNNNNNNNNNNNNNNnNNNNNNNNNNnNNNNNnNNNNNNNNNNNnNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNnNnNNNNNNNNNNNNNNNNN",  # scene row 79 = GROUND_LINE, feet land here (walkable)
    "NNNNNNNnNNNNNNNNNNNNNNnNNNNNNNNNNNNNnnnNNNNNNNNNNNNnnnNNNNNNNNNnnNNNNNNNNNnNNNNNNNNNnnNNNNNNNNNNNNNnNNNNNNNNNNNNnNNNNNNnnnnNNNNNNNNNNNNNNNNNnnNNNNNNNNNNNNNNNNNN",
    "NNNNnNNNNNNNNNNNnNNNNNNNNNNNNNNNNNNNNNNNNNNNnNNNNNNnnnNNNNNNnNNNNNNnNNnNNNnNNNNNNNNNNNNNNNNNNNNNNNnnNNNnNNNNnnNNNNnNNNNnnnnNNNNNNNNNNNNnNNNNNnNNNNNNNNNNNNNNNNNN",
    "NNNNNnnnnnnnnnnNNnnnnNNNNNNNnNNNNNNnnnnnNNNNNNNNNNnnnnnnnnNNnnNNNNNNNNNnnnnNNNNNNNNNNNNNNNNNNNNnnnNNNNNnnnnnNNNNNnnnnnNNnnnnnNNNNNNNNNNNnnnnnnnnnNNNNNNNnNNnnNNN",
    "NNNNNNNNNNNNNNNNNNNNNnnnnnnnnnNNNNNNNNNNggggEEEENNNNNNNNNNNNNNnnnNNNnnnNNNNNNNNNNNNNNnnnNNNNNNNNNNNNnnnNNNNNEEgggNNNNNNNNNNNNNNNEEEEEEEENNNNNNNNNNNNnnnnnnNnnnnn",
    "ggggggggggGggggggggENNNNNNNNNNNNEEgggGGGGGGGGGGGEEGGGGGGGGGGGGNNNNNNNNNEEgEgggggNNNNNNNNNNNNEEEEEEEENNNgggEEggggggggggggGGGGgNNNggggggggEEEEEEEEggggNNNNNNNNNNNN",
    "ggggGGGGGGGGGggggggGEEEEEEEEEEEEggGGGGGGGGGGGGGGggGGGGGGGGGGGGGGGGGGGGEGgGgGEGGGEEEEEgggggEEgggggggggggggggggggggGGGGGGGGGGGGggEGGGGGGGGgEggggGGGGGGGGEEEEEEEEEE",
    "ggggGGGGGGGGGGGggGGGGGGGGGGGGGggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGgggggyGGggggggggggggggggggggggEgRRRggGGGGGGGGGGGGGGGGGGGGGGGGEGEGgGGGGGGGGGGGGgEgggggggg",
    "ggggGGGGGGGGGGgggggGGGGGGGGGGGGGGYGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGEGGGGGGGyYyGGGGGGgggggggggggggggggggrrrgGGGGGGGGGGGGGGGGGGGGGGEGGgggggGGGGGGGRRGGGGgGEgEgggg",
    "gggggGGGGGGGGggggggggGGGGGGGGGGGYnYGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGEGgGEGGGGGGyGGGGGGGGGGGGGGgggggggggggggggGGGGGGGGGGGYGGGGGGGGGEGgGEGGGGGGGGGGGrrrGGGgggggggggg",
    "ggggggGGGGGGgggggggggggGGGGGGGGGGYGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGgggggGGGGGGGGGGGGGGGGGGGGGGggggggggggggGGGGGGGGGGGGYnYGGGGGGGGgggggGGGGGGGGGGGGGGGGGgggggggggg",
    "gggggGGGGGGGGggggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGgggggggggggggggGGGGGGGGGGGYGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGggggggggggg",
    "ggggGGGGGGGgggggggggggggggggggggggggggggggggggggggGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGgggggggggggggggggggggGGGGGGGGGGGGGGggggggggGGGGGGGGGGGGGGGGgggggggggggg",
    "ggggGggggggggggggggggggggggggggggggggggggggggggggggggGGGGGgggggggggggggGGGGGGGGGGGGGGgggggggggggggggggggggggggggggggGGgggggggggggggggGGGGgGGGGGGGGGGgggggggggggg",
    "gggggggggggggggggggggggggggggggggggggggggggggggggggggggGGGgGGGGGGGGGGggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg",
    "gggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg",
    "gggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg",  # scene row 95, foreground shadow
]
