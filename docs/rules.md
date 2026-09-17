# The separation rule

`pixelkit.report_separation` is the check that does the most work and has been
wrong the most times. This is its full story, including every calibration
mistake, because the mistakes are the useful part.

## What it does

It finds every pair of colours that **share an edge anywhere in the image** — not
every pair in the palette, only the ones that actually touch — converts both to
CIELAB, and decides whether a viewer could tell them apart.

```python
failures, rows = report_separation(grid, "label")
# failures is a Findings: a list of hard failures that also carries .warnings
```

Touching pairs are what matter. Two palette entries that are nearly identical are
harmless if they never meet; two that are far apart are wasted if they only ever
meet in a corner.

## The rule

A pair is readable if **either** of two things is true.

### 1. A lightness edge

```
|dL| >= VALUE_STEP (0.22)   OR   max/min >= VALUE_RATIO (1.7)
```

The **ratio** half is not decoration. Perception follows Weber's law: brightness
differences are judged relative to the background, not absolutely. In a night
palette, 0.05 against 0.16 is a **three-fold** difference and reads instantly —
but the absolute gap is only 0.11, under the step. An earlier version used the
absolute step alone and consequently declared honest night palettes unreadable.
That is why the zombie shooter's dark palette passes at all.

`VALUE_FLOOR` guards the divide: below 0.02 luminance the ratio is numerical
noise and only the absolute step counts.

### 2. A chroma difference, against a role-dependent floor

| role | hard failure below | warning below |
|---|---|---|
| outline vs fill | **ΔE 24** | ΔE 30 |
| anything else | **ΔE 6** | ΔE 22 |

**The asymmetry is the single most important decision in this repo.** An outline
exists to be an edge; a silhouette that dissolves is unrecoverable, so that floor
stays strict. Everything above "literally the same colour" is a judgement call,
and judgement calls belong in the warnings where a person can see them and decide.

A pair that trips neither mechanism is a **hard failure**. A pair that is close
but visible is a **warning**, printed worst-first and capped at eight, so real
failures are not drowned in notes.

## How it was calibrated, badly, four times

Every one of these came from a check firing on a difference no display can show.

**1. Material floors of 45 and 32 made agents route art around a number.**
Across four parallel agents, **thirteen distinct colour pairs** were designed
around rather than used:

| pair | ΔE | floor then | what it cost |
|---|---|---|---|
| `t`–`o` | 17.6 | 32 | no wood on the shaded roof slope |
| `a`–`C` | 10.9 | 32 | shirt blues unusable as sky gradient steps |
| `g`–`F` | 26.7 | 32 | grass shadow may never meet foliage |
| `K`–`t` | 24.7 | 28 | no two-tone fur on a 20px dog |
| `u`–`R` | 27.3 | 32 | wall shadow stops a row above the foundation |
| `R`–`A` | 27.4 | 32 | far ridge needs a 1px cap to face the sky |
| …and seven more | | | |

The sky agent's own working notes: *"`a`-`C` 10.9 and `C`-`A` 17.3 are under 32,
so the shirt blues cannot be used as intermediate ramp steps; the sky is `a`/`A`
dither only."* That is a threshold dictating composition.

**2. The dog's paw against the dirt path: ΔE 24.9 against a required 25.** Rejected
by **0.1**. The rule had already conceded that a large lightness step reads on its
own (`dL 0.26`), then demanded chroma confirm it anyway. Self-contradictory.

**3. A sky gradient's own two steps: ΔE 19.7 against a floor of 20.** Rejected by
**0.3**. Adjacent bands of a gradient are *supposed* to be close. That is what a
gradient is.

**4. The well's plaster shadow against the dirt: ΔE 12.0 against a floor of 12.**
Rejected by **0.03**.

After the fourth, the conclusion was not "lower it slightly" but that **a fill
pair is the wrong thing to gate at all.** Hence ΔE 6.

## A false positive that was cited as proof

The repo's headline war story used to be that the check "caught a killer": outline
`K` against trouser shadow `p` at ΔE 12.7, supposedly merging and destroying the
silhouette. Under the measure that actually matters — lightness ratio — that pair
sits at **3.2×** and reads perfectly well. Dark trousers with a black outline is
standard pixel art.

The check flagged something almost certainly fine, the palette was changed to
satisfy it, and the episode was then cited as justification for keeping the check
strict. **That is circular**, and it is the failure mode this whole document is
about.

## What the taxonomy cost

Earlier versions also carried a `shade` / `material` distinction with declared
exceptions (`SHADE_PAIRS`). It is gone. Base colours and their own shadows are
*meant* to sit close; gradients *are* ramps. Nineteen declared exceptions existed
purely to stop the checker firing on normal shading, which is a strong smell that
the taxonomy was modelling the wrong thing.

## Testing the rule itself

`check_thresholds.py` pins the rule against **synthetic inputs**:

```
(dE, dL, floor, should_pass)
```

Testing it against the live palette is not a test. The palette keeps getting
fixed, so a pair that used to fail starts passing and the "regression test"
quietly stops asserting anything. That happened here: a first version asserted
`K`-`p` should fail, but the palette had already been rebalanced from ΔE 12.7 to
28.2, so the assertion was checking a value that no longer existed.

The suite covers the rejects (degenerate same-colour, the original 12.7, a pair
0.9 short of its floor and 0.01 short of the step), the chroma passes (overalls vs
shirt: same lightness, opposite hue), the value passes, and — separately — **the
tier asymmetry itself**, so a later tweak cannot flatten it back out.

## If a check fails by a hair

Suspect the check first. Concretely:

1. Is the pair governed by chroma or by a lightness edge? `verdict()` returns
   which, plus dE and dL.
2. If it is a fill pair failing by under ~2 ΔE, the art is almost certainly fine.
3. If it is an **outline** pair failing, take it seriously — that is the one that
   decides whether the silhouette reads.
4. If a *whole class* of pairs is failing, the palette is wrong, not the art.

## Files

- `pixelkit.py` — `SEP_RULES`, `VALUE_STEP`, `VALUE_RATIO`, `reads_by_value()`,
  `verdict()`, `report_separation()`
- `check_thresholds.py` — the rule's own regression suite
- `evaluate.py` — reports each asset's **relative margin** (0.0 = exactly on the
  line, 0.5 = clears it by half again)
