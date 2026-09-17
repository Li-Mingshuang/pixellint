# Pipeline evaluation

28 assets, 121,870 cells, 603 adjacent colour pairs adjudicated.

| asset | size | frames | tier | cells | keys | pairs | min margin | warnings | failures | check ms |
|---|---|---|---|---|---|---|---|---|---|---|
| `background.SKY` | 320x96 | 1 | L | 30720 | 6 | 11 | 0.01 | 2 | 0 | 127.5 |
| `background.MID` | 320x64 | 1 | L | 20480 | 4 | 6 | 0.13 | 0 | 0 | 32.0 |
| `background.FAR` | 320x56 | 1 | L | 17920 | 2 | 1 | 7.65 | 0 | 0 | 18.0 |
| `background.STREET` | 320x40 | 1 | M | 12800 | 6 | 12 | 0.04 | 2 | 0 | 42.4 |
| `zombie.death` | 22x32 | 5 | S | 3520 | 6 | 45 | 0.02 | 0 | 0 | 5.3 |
| `player.walk` | 24x32 | 4 | S | 3072 | 12 | 100 | 0.02 | 8 | 0 | 7.0 |
| `zombie.walk` | 22x32 | 4 | S | 2816 | 6 | 38 | 0.02 | 0 | 0 | 6.2 |
| `player.shoot` | 24x32 | 3 | S | 2304 | 15 | 79 | 0.02 | 6 | 0 | 5.2 |
| `player.idle` | 24x32 | 2 | S | 1536 | 12 | 50 | 0.02 | 4 | 0 | 2.4 |
| `zombie.attack` | 22x32 | 2 | S | 1408 | 6 | 20 | 0.02 | 0 | 0 | 4.8 |
| `effects.muzzle` | 16x12 | 4 | XS | 768 | 3 | 6 | 0.13 | 0 | 0 | 0.6 |
| `effects.impact` | 10x10 | 3 | XS | 300 | 3 | 3 | 0.13 | 0 | 0 | 0.5 |
| `effects.dust` | 12x8 | 3 | XS | 288 | 2 | 2 | 0.15 | 0 | 0 | 0.3 |
| `effects.blood` | 8x8 | 3 | XS | 224 | 3 | 6 | 0.24 | 3 | 0 | 0.4 |
| `effects.bloodpool` | 20x8 | 1 | XS | 160 | 3 | 2 | 0.24 | 1 | 0 | 0.3 |
| `effects.bullet` | 10x4 | 2 | XS | 80 | 3 | 4 | 0.13 | 0 | 0 | 0.2 |
| `effects.casing` | 5x4 | 2 | XS | 40 | 3 | 6 | 2.27 | 0 | 0 | 0.2 |
| `effects.gib` | 4x4 | 3 | XS | 34 | 3 | 7 | 0.24 | 3 | 0 | 0.2 |
| `sky.BACKDROP` | 160x58 | 1 | M | 9280 | 8 | 14 | 0.15 | 1 | 0 | 48.5 |
| `ground.GROUND` | 160x40 | 1 | M | 6400 | 9 | 23 | 0.09 | 0 | 0 | 21.4 |
| `walk_cycle.FRAMES` | 16x32 | 4 | S | 2048 | 13 | 92 | 0.02 | 4 | 0 | 9.0 |
| `props.HOUSE` | 46x34 | 1 | S | 1564 | 10 | 18 | 0.07 | 1 | 0 | 5.7 |
| `props.TREE` | 28x40 | 1 | S | 1120 | 6 | 8 | 0.14 | 1 | 0 | 3.9 |
| `dog.DOG_FRAMES` | 20x14 | 4 | S | 1120 | 4 | 20 | 0.44 | 0 | 0 | 1.8 |
| `sky.CLOUD_STRIP` | 64x12 | 1 | XS | 768 | 2 | 1 | 0.57 | 0 | 0 | 0.8 |
| `render_sprite.SPRITE` | 16x32 | 1 | XS | 512 | 13 | 23 | 0.02 | 1 | 0 | 1.6 |
| `props.FENCE` | 32x14 | 1 | XS | 448 | 3 | 3 | 0.14 | 0 | 0 | 1.8 |
| `props.ROCK` | 14x10 | 1 | XS | 140 | 3 | 3 | 0.15 | 0 | 0 | 0.3 |

## What these numbers are not

- **margin is readability slack, not beauty.** An asset can sit far above every floor and still be ugly. The pipeline cannot tell.
- **cells is an authoring-surface proxy, not difficulty.** A 30,720-cell sky gradient is far easier than a 512-cell face, because the gradient was procedural and the face was reasoned about cell by cell.
- **check_ms is assertion cost only.** It excludes authoring cost, which is where the real spend is and which this repo does not instrument at all.
