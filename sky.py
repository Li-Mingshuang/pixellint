
# What this module delivers. The rest of what it defines is either a
# composition block or a lookup table, and measuring those double-counts or
# misfires -- see docs/authoring.md.
SHIPPED = ('BACKDROP', 'CLOUD_STRIP',)

"""Sky backdrop and cloud layer for the 160x96 scene.

One character is one pixel and one index into pixelkit.SCENE_PALETTE; the grids
below are the art, not a runtime recipe.

BACKDROP -- 160 x 58, fully opaque, composited at scene rows 0..57.
  rows  0..44  sky.  The palette carries only two usable sky tones (a deeper
               blue, A lighter blue), so the banded ramp is an ordered dither
               on one nested lattice -- A where (x + y) % 4 == 0, then in
               (0, 2), then in (0, 1, 2) -- giving five flat steps of 0 / 25 /
               50 / 75 / 100 per cent A.  Every row inside a band holds the
               same number of A pixels, so the ramp steps between bands and
               never chatters row to row.
  rows 45..57  horizon band, four receding layers: sky, a far ridge (R body
               capped with a one pixel r silhouette line), rolling hills (G),
               a far treeline (F with f canopy undersides), then a two row g
               base band that seats the range on the ground at row 58.  Row 57
               is solid g and uniform, so it butts cleanly onto the ground
               layer with no ragged edge and no gap.

CLOUD_STRIP -- 64 x 12, a horizontally tiling cloud band.  Three clouds of
different size and height, with 3 / 10 / 2 columns of sky between them so the
repeat does not announce itself; the largest straddles column 63/0, so its dx = -1 column is
column 63 and its dx = 0 column is column 0 -- one shape wrapping the seam, with
identical depth and identical shading on both sides.  W body, w underside, .
sky showing through.  Rows 0 and 11 are empty, so the band never needs a
vertical join.

Palette notes (SCENE_TIERS floors, dE76) -- pairs deliberately avoided:
  R-A 27.4 is under the 32 material floor, so the stone base tone may never
      border sky at all: the ridge body is capped with an r line wherever it
      meets the sky (A-r 43.6), and R only ever meets r, G and F.
  a-C 10.9 and C-A 17.3 are under 32, so the shirt blues cannot be used as
      intermediate ramp steps; the sky is a/A dither only.
  g-F 26.7 is under 32, so grass shadow never touches foliage base: the g base
      band starts two rows below the lowest treeline pixel.

Derivation, for whoever has to re-tune this: the hill crest is a clamped sum of
three sines over x (rows 50..55), the ridge silhouette a clamped sum of two
(rows 45..50), and the treeline is 21 deterministic clumps standing on hill
crests no lower than row 54, crowns clamped out of the sky rows and canopy
undersides in f.  Nothing here computes at import time -- the grids below are
the literal art, so a change to this file is a change to the picture.
"""

BACKDROP: list[str] = [
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # 0
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # 1
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # 2
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # 3
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # 4
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # 5
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # 6
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # 7
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # 8
    "aaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaA",  # 9
    "aaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAa",  # 10
    "aAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaa",  # 11
    "AaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaa",  # 12
    "aaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaA",  # 13
    "aaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAa",  # 14
    "aAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaa",  # 15
    "AaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaa",  # 16
    "aaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaAaaaA",  # 17
    "AaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAa",  # 18
    "aAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaA",  # 19
    "AaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAa",  # 20
    "aAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaA",  # 21
    "AaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAa",  # 22
    "aAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaA",  # 23
    "AaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAa",  # 24
    "aAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaA",  # 25
    "AaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAa",  # 26
    "aAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAA",  # 27
    "AAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAa",  # 28
    "AAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaA",  # 29
    "AaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAA",  # 30
    "aAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAA",  # 31
    "AAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAa",  # 32
    "AAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaA",  # 33
    "AaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAA",  # 34
    "aAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAAaAAA",  # 35
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 36
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 37
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 38
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 39
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 40
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 41
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 42
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 43
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 44
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAArrrrrrrrrrrrrrrrrrrrrrrrrrrrrAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 45
    "AAAAAAAAAAAAAAAAAAAAAAAAArrrrrrrrRRRRRRRRRRRRRRRRRRRRRRRRRRRRRrrrrrrAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFAAAAAAAAAAAAAAAAAAAAAAA",  # 46
    "rrrAAAAAAAAAArrrrrrrrrrrrRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRrrrrrrAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFFFAAAAAAAAAAAFFFAAAAAAAA",  # 47
    "RFFFrrrrrrrrrRRRFFFFFRRRRRRRRRRRRRRRRRRRRRRRRFFFRRRRRRRRRRRRRRRRRRRRRRRRRRrrrrrrrrAAAAAAAAAAAAAAAAAAAAAAAArrrrrrrrrrrrrrrrrrrrAAAAAAAAAFFFAAAAFFFAAAFFFFFAAFFFAA",  # 48
    "FFFFFFFFFRRRRRRFFFFFFFRRRFFFRRRRRRRRRRRRRFRRFFFFFRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRrrrrrrrrrrrrrrFrrrrrrrrrRRRRRRRFFFRRRRFRRRRRrrFrrrrrrFFFAAAFFFFFAAFFFFFAFFFFFr",  # 49
    "FFFFFFFFFFRRFFFFFFFFFFRRFFFFFRRFFFFFRRRRFFFRFFFFFRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRFFFFFRRRRFFFRRRFFFRFFFRRRRFFFFFRRFFFRRRRRFFFRRRRGfffGGGfffffGGFFFFFrFFFFFR",  # 50
    "fffFFFFFFFRFFFFFFFFFFFRRFFFFFRFFFFFFFRGGfffGFFFFFRRFFFRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRFFFFFFFRRRFFFRRFFFFFFFFFGRRFFFFFRRFFFRRRRRFFFGGGGGGGGGGGGGGGGGGfffffGFFFFFR",  # 51
    "GGGfffffffGfffffffffffGGfffffGfffffffGGGGGGGfffffGFFFFFRRRRRRRRRRRRRRRRRRRRRRRRRRRFRRFFFFFFFRRRfffGGfffffffffGGGfffffGGFFFRGGGGfffGGGGGGGGGGGGGGGGGGGGGGGGfffffR",  # 52
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGfffffGRRRRRRRRRRRRRRRRRRRRRRRRRFFFGfffffffGGGGGGGGGGGGGGGGGGGGGGGGGGGfffGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG",  # 53
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGRRRRRRRRRRRRRRRRRRGGGGfffGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG",  # 54
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG",  # 55
    "gggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg",  # 56
    "gggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg",  # 57
]

CLOUD_STRIP: list[str] = [
    "................................................................",  # 0
    "................................................................",  # 1
    "W..WWWW..............WWWWW..................................WWWW",  # 2
    "WWWWWWWW...........WWWWWWWWW..............................WWWWWW",  # 3
    "WWWWWWWWWW........WWWWWWWWWWW...........................WWWWWWWW",  # 4
    "WWWWWWWWWWW......WWWWwwwwwWWWW.........................WWWWWWWWW",  # 5
    "WWWWWWWWWWWW....wwwwwwwwwwwwwww.......................WWWWWWWWWW",  # 6
    "wwwwwwwwwwWW................................WWW......WWWwwwwwwww",  # 7
    "wwwwwwwwwwwww..............................WWWWW....wwwwwwwwwwww",  # 8
    "..........................................WWWWWWW...............",  # 9
    ".........................................wwwwwwwww..............",  # 10
    "................................................................",  # 11
]
