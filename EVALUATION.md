# Pipeline evaluation

44 assets, 125,478 cells, 749 adjacent colour pairs adjudicated.

| asset | size | frames | tier | cells | keys | pairs | min margin | warnings | failures | check ms |
|---|---|---|---|---|---|---|---|---|---|---|
| `background.SKY` | 320x96 | 1 | L | 30720 | 6 | 11 | 0.01 | 2 | 0 | 71.6 |
| `background.MID` | 320x64 | 1 | L | 20480 | 4 | 6 | 0.13 | 0 | 0 | 16.9 |
| `background.FAR` | 320x56 | 1 | L | 17920 | 2 | 1 | 7.65 | 0 | 0 | 9.4 |
| `background.STREET` | 320x40 | 1 | M | 12800 | 6 | 12 | 0.04 | 2 | 0 | 28.8 |
| `zombie.death` | 22x32 | 5 | S | 3520 | 6 | 45 | 0.02 | 0 | 0 | 2.6 |
| `player.walk` | 24x32 | 4 | S | 3072 | 12 | 100 | 0.02 | 8 | 0 | 3.5 |
| `zombie.walk` | 22x32 | 4 | S | 2816 | 6 | 38 | 0.02 | 0 | 0 | 3.4 |
| `player.shoot` | 24x32 | 3 | S | 2304 | 15 | 79 | 0.02 | 6 | 0 | 3.5 |
| `player.idle` | 24x32 | 2 | S | 1536 | 12 | 50 | 0.02 | 4 | 0 | 1.9 |
| `zombie.attack` | 22x32 | 2 | S | 1408 | 6 | 20 | 0.02 | 0 | 0 | 1.4 |
| `effects.muzzle` | 16x12 | 4 | XS | 768 | 3 | 6 | 0.13 | 0 | 0 | 0.3 |
| `effects.impact` | 10x10 | 3 | XS | 300 | 3 | 3 | 0.13 | 0 | 0 | 0.2 |
| `effects.DUST_FRAMES` | 12x8 | 3 | XS | 288 | 2 | 2 | 0.15 | 0 | 0 | 0.2 |
| `effects.BLOOD_FRAMES` | 8x8 | 3 | XS | 224 | 3 | 6 | 0.24 | 3 | 0 | 0.2 |
| `effects.BLOODPOOL` | 20x8 | 1 | XS | 160 | 3 | 2 | 0.24 | 1 | 0 | 0.2 |
| `effects.BULLET_FRAMES` | 10x4 | 2 | XS | 80 | 3 | 4 | 0.13 | 0 | 0 | 0.1 |
| `player.GUN_DOWN` | 4x11 | 1 | XS | 44 | 4 | 6 | 0.44 | 1 | 0 | 0.2 |
| `effects.CASING_FRAMES` | 5x4 | 2 | XS | 40 | 3 | 6 | 5.53 | 0 | 0 | 0.1 |
| `effects.gib` | 4x4 | 3 | XS | 34 | 3 | 7 | 0.24 | 3 | 0 | 0.1 |
| `player.GUN_SIDE` | 8x4 | 1 | XS | 32 | 4 | 6 | 0.44 | 1 | 0 | 0.1 |
| `sky.BACKDROP` | 160x58 | 1 | M | 9280 | 8 | 14 | 0.15 | 1 | 0 | 22.3 |
| `ground.GROUND` | 160x40 | 1 | M | 6400 | 9 | 23 | 0.09 | 0 | 0 | 16.1 |
| `walk_cycle.FRAMES` | 16x32 | 4 | S | 2048 | 13 | 92 | 0.02 | 4 | 0 | 6.8 |
| `props.HOUSE` | 46x34 | 1 | S | 1564 | 10 | 18 | 0.07 | 1 | 0 | 1.8 |
| `props.tree` | 28x40 | 1 | S | 1120 | 6 | 8 | 0.01 | 1 | 0 | 2.0 |
| `dog.DOG_FRAMES` | 20x14 | 4 | S | 1120 | 4 | 20 | 0.44 | 0 | 0 | 1.3 |
| `sky.CLOUD_STRIP` | 64x12 | 1 | XS | 768 | 2 | 1 | 0.57 | 0 | 0 | 0.4 |
| `render_sprite.SPRITE` | 16x32 | 1 | XS | 512 | 13 | 23 | 0.02 | 1 | 0 | 1.9 |
| `yardprops.wagon` | 28x18 | 1 | XS | 504 | 6 | 10 | 0.14 | 0 | 0 | 0.7 |
| `foliage.CHICKEN` | 12x10 | 4 | XS | 480 | 6 | 32 | 0.31 | 4 | 0 | 0.8 |
| `props.FENCE` | 32x14 | 1 | XS | 448 | 3 | 3 | 0.14 | 0 | 0 | 0.8 |
| `yardprops.well` | 20x22 | 1 | XS | 440 | 9 | 14 | 0.14 | 1 | 0 | 0.7 |
| `yardprops.HAYSTACK` | 24x18 | 1 | XS | 432 | 6 | 12 | 0.09 | 1 | 0 | 0.8 |
| `yardprops.scarecrow` | 14x30 | 1 | XS | 420 | 8 | 13 | 0.14 | 2 | 0 | 0.6 |
| `foliage.BUSH` | 18x14 | 1 | XS | 252 | 4 | 3 | 0.32 | 0 | 0 | 0.4 |
| `farmprops.signpost` | 8x20 | 1 | XS | 160 | 3 | 3 | 0.14 | 0 | 0 | 0.2 |
| `farmprops.logpile` | 16x10 | 1 | XS | 160 | 5 | 8 | 0.14 | 1 | 0 | 0.3 |
| `props.rock` | 14x10 | 1 | XS | 140 | 3 | 3 | 0.15 | 0 | 0 | 0.3 |
| `farmprops.BARREL` | 10x14 | 1 | XS | 140 | 5 | 9 | 0.14 | 0 | 0 | 0.4 |
| `farmprops.CRATE` | 12x11 | 1 | XS | 132 | 3 | 3 | 0.14 | 0 | 0 | 0.3 |
| `foliage.FLOWERPATCH` | 16x8 | 1 | XS | 128 | 5 | 4 | 0.42 | 0 | 0 | 0.2 |
| `farmprops.stump` | 12x9 | 1 | XS | 108 | 6 | 10 | 0.00 | 1 | 0 | 0.3 |
| `farmprops.milkchurn` | 8x12 | 1 | XS | 96 | 4 | 5 | 0.15 | 0 | 0 | 0.2 |
| `foliage.MUSHROOMS` | 10x8 | 1 | XS | 80 | 5 | 8 | 0.18 | 1 | 0 | 0.2 |

## Iteration

Attempts-to-green is consecutive failures before a check's most recent success, read from `.pipeline-runs.jsonl`. It is the closest thing here to a difficulty measure, and it is limited: it covers only runs since logging was added, and it is per script rather than per asset.

| script | attempts to green | total runs | failures |
|---|---|---|---|
| `check_sprite.py` | 1 | 4 | 0 |
| `check_scene.py` | 1 | 4 | 0 |
| `check_dog.py` | 1 | 4 | 0 |
| `check_farmprops.py` | 1 | 4 | 0 |
| `check_foliage.py` | 1 | 4 | 0 |
| `check_game.py` | 1 | 4 | 0 |
| `check_ground.py` | 1 | 4 | 0 |
| `check_props.py` | 1 | 4 | 0 |
| `check_sky.py` | 1 | 4 | 0 |
| `check_thresholds.py` | 1 | 4 | 0 |
| `check_yardprops.py` | 1 | 4 | 0 |
| `game/check_background.py` | 1 | 4 | 0 |
| `game/check_effects.py` | 1 | 4 | 0 |
| `game/check_player.py` | 1 | 4 | 0 |
| `game/check_zombie.py` | 1 | 4 | 0 |

## What these numbers are not

- **margin is readability slack, not beauty.** An asset can sit far above every floor and still be ugly. The pipeline cannot tell.
- **cells is an authoring-surface proxy, not difficulty.** A 30,720-cell sky gradient is far easier than a 512-cell face, because the gradient was procedural and the face was reasoned about cell by cell.
- **check_ms is assertion cost only.** It excludes authoring cost, which is where the real spend is and which this repo does not instrument at all.
